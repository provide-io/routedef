# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TypeAlias, cast

from routedef import JSONValue, RouteDef, RouteRequest, RouteResponse, RouteTable


@dataclass(frozen=True, slots=True)
class ReportUser:
    user_id: str
    roles: frozenset[str]


@dataclass(frozen=True, slots=True)
class AdminUser:
    user_id: str
    scopes: frozenset[str]


@dataclass(frozen=True, slots=True)
class TokenUser:
    sub: str
    email: str
    scopes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IncomingRequest:
    method: str
    path: str
    headers: Mapping[str, str]


ReportContext: TypeAlias = dict[str, object]
ReportRoute: TypeAlias = RouteDef[ReportUser, ReportContext]
ReportRequest: TypeAlias = RouteRequest[ReportUser, ReportContext]
ReportEnforcer: TypeAlias = Callable[[ReportRoute, IncomingRequest, ReportContext, ReportUser], bool | RouteResponse]

AdminContext: TypeAlias = dict[str, object]
AdminRoute: TypeAlias = RouteDef[AdminUser, AdminContext]
AdminRequest: TypeAlias = RouteRequest[AdminUser, AdminContext]
AdminAuthorize: TypeAlias = Callable[[AdminUser, str, Mapping[str, object]], bool]
AdminEnforcer: TypeAlias = Callable[[AdminRoute, IncomingRequest, AdminContext, AdminUser], bool | RouteResponse]

TokenContext: TypeAlias = dict[str, object]
TokenRoute: TypeAlias = RouteDef[TokenUser, TokenContext]
TokenRequest: TypeAlias = RouteRequest[TokenUser, TokenContext]


async def report_handler(request: ReportRequest) -> RouteResponse:
    return RouteResponse.json(
        {
            "project_id": request.path_params["project_id"],
            "actor": request.auth.user_id,
            "workspace": cast(str, request.context["workspace"]),
        }
    )


async def admin_handler(request: AdminRequest) -> RouteResponse:
    return RouteResponse.json({"deleted": request.path_params["user_id"], "actor": request.auth.user_id})


async def token_handler(request: TokenRequest) -> RouteResponse:
    return RouteResponse.json(
        {
            "sub": request.auth.sub,
            "email": request.auth.email,
            "scopes": list(request.auth.scopes),
            "issuer": cast(str, request.context["issuer"]),
        }
    )


def report_role_enforcer(
    route: ReportRoute,
    request: IncomingRequest,
    context: ReportContext,
    auth: ReportUser,
) -> bool | RouteResponse:
    required_roles = set(cast(tuple[str, ...], route.metadata.get("roles", ())))
    if required_roles <= auth.roles:
        return True
    return RouteResponse.json(
        cast(
            JSONValue,
            {
                "detail": "forbidden",
                "required_roles": sorted(required_roles),
                "path": request.path,
                "workspace": cast(str, context["workspace"]),
            },
        ),
        status=403,
    )


def admin_enforcer_from_authorize(authorize: AdminAuthorize) -> AdminEnforcer:
    def enforcer(
        route: AdminRoute,
        request: IncomingRequest,
        context: AdminContext,
        auth: AdminUser,
    ) -> bool | RouteResponse:
        permission = cast(str, route.metadata["permission"])
        resource: dict[str, object] = {
            "method": route.method,
            "path": request.path,
            "route_path": route.path,
            "organization": context["organization"],
        }
        return authorize(auth, permission, resource)

    return enforcer


def token_auth_provider(
    route: TokenRoute,
    request: IncomingRequest,
    context: TokenContext,
) -> TokenUser:
    assert route.metadata["auth"] == "bearer-token"
    assert context["issuer"] == "example-idp"
    scheme, _, token = request.headers["authorization"].partition(" ")
    assert scheme == "Bearer"
    claims = _decode_fake_jwt_payload(token)
    return TokenUser(
        sub=cast(str, claims["sub"]),
        email=cast(str, claims["email"]),
        scopes=tuple(cast(list[str], claims["scopes"])),
    )


def _decode_fake_jwt_payload(token: str) -> Mapping[str, JSONValue]:
    _, payload, _ = token.split(".")
    padding = "=" * (-len(payload) % 4)
    decoded = base64.urlsafe_b64decode(f"{payload}{padding}")
    return cast(Mapping[str, JSONValue], json.loads(decoded))


def _fake_jwt(claims: Mapping[str, JSONValue]) -> str:
    encoded_claims = base64.urlsafe_b64encode(json.dumps(claims, separators=(",", ":")).encode()).decode()
    return f"test.{encoded_claims.rstrip('=')}.signature"


async def _dispatch_report(
    route: ReportRoute,
    incoming: IncomingRequest,
    context: ReportContext,
    auth: ReportUser,
    enforcer: ReportEnforcer,
) -> RouteResponse:
    table = RouteTable([route])
    match = table.match(incoming.method, incoming.path)
    assert match is not None
    enforcement = enforcer(match.route, incoming, context, auth)
    if isinstance(enforcement, RouteResponse):
        return enforcement
    assert enforcement is True
    route_request = RouteRequest(
        method=incoming.method,
        path=incoming.path,
        route_path=match.route.path,
        path_params=match.path_params,
        headers=incoming.headers,
        auth=auth,
        context=context,
    )
    return await match.route.handler(route_request)


async def _dispatch_admin(
    route: AdminRoute,
    incoming: IncomingRequest,
    context: AdminContext,
    auth: AdminUser,
    enforcer: AdminEnforcer,
) -> RouteResponse:
    table = RouteTable([route])
    match = table.match(incoming.method, incoming.path)
    assert match is not None
    enforcement = enforcer(match.route, incoming, context, auth)
    if isinstance(enforcement, RouteResponse):
        return enforcement
    if enforcement is False:
        return RouteResponse.json({"detail": "forbidden"}, status=403)
    route_request = RouteRequest(
        method=incoming.method,
        path=incoming.path,
        route_path=match.route.path,
        path_params=match.path_params,
        headers=incoming.headers,
        auth=auth,
        context=context,
    )
    return await match.route.handler(route_request)


async def _dispatch_token(
    route: TokenRoute,
    incoming: IncomingRequest,
    context: TokenContext,
) -> RouteResponse:
    table = RouteTable([route])
    match = table.match(incoming.method, incoming.path)
    assert match is not None
    auth = token_auth_provider(match.route, incoming, context)
    route_request = RouteRequest(
        method=incoming.method,
        path=incoming.path,
        route_path=match.route.path,
        headers=incoming.headers,
        auth=auth,
        context=context,
    )
    return await match.route.handler(route_request)


def test_route_metadata_roles_are_enforced_from_route_def() -> None:
    route = RouteDef(
        "GET",
        "/projects/{project_id}/reports",
        report_handler,
        metadata={"roles": ("reports:read",)},
    )
    incoming = IncomingRequest("GET", "/projects/project-123/reports", {})
    context: ReportContext = {"workspace": "acme"}

    allowed = asyncio.run(
        _dispatch_report(
            route,
            incoming,
            context,
            ReportUser("user-ok", frozenset({"reports:read"})),
            report_role_enforcer,
        )
    )
    denied = asyncio.run(
        _dispatch_report(
            route,
            incoming,
            context,
            ReportUser("user-no", frozenset({"support:read"})),
            report_role_enforcer,
        )
    )

    assert allowed.status == 200
    assert allowed.body == {"project_id": "project-123", "actor": "user-ok", "workspace": "acme"}
    assert denied.status == 403
    assert denied.body == {
        "detail": "forbidden",
        "required_roles": ["reports:read"],
        "path": "/projects/project-123/reports",
        "workspace": "acme",
    }


def test_authorize_callback_wraps_into_enforcer() -> None:
    route = RouteDef(
        "DELETE",
        "/admin/users/{user_id}",
        admin_handler,
        metadata={"permission": "admin.users.delete"},
    )
    incoming = IncomingRequest("DELETE", "/admin/users/u_123", {})
    context: AdminContext = {"organization": "provide"}
    calls: list[tuple[AdminUser, str, Mapping[str, object]]] = []

    def authorize(user: AdminUser, permission: str, resource: Mapping[str, object]) -> bool:
        calls.append((user, permission, resource))
        return permission in user.scopes and resource["organization"] == "provide"

    response = asyncio.run(
        _dispatch_admin(
            route,
            incoming,
            context,
            AdminUser("admin-1", frozenset({"admin.users.delete"})),
            admin_enforcer_from_authorize(authorize),
        )
    )

    assert response.status == 200
    assert response.body == {"deleted": "u_123", "actor": "admin-1"}
    assert calls == [
        (
            AdminUser("admin-1", frozenset({"admin.users.delete"})),
            "admin.users.delete",
            {
                "method": "DELETE",
                "path": "/admin/users/u_123",
                "route_path": "/admin/users/{user_id}",
                "organization": "provide",
            },
        )
    ]


def test_bearer_token_becomes_route_auth_user() -> None:
    token = _fake_jwt({"sub": "user_123", "email": "dev@example.test", "scopes": ["profile:read"]})
    route = RouteDef(
        "GET",
        "/me",
        token_handler,
        metadata={"auth": "bearer-token"},
    )
    incoming = IncomingRequest("GET", "/me", {"authorization": f"Bearer {token}"})
    context: TokenContext = {"issuer": "example-idp"}

    response = asyncio.run(_dispatch_token(route, incoming, context))

    assert response.status == 200
    assert response.body == {
        "sub": "user_123",
        "email": "dev@example.test",
        "scopes": ["profile:read"],
        "issuer": "example-idp",
    }
