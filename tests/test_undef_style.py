# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TypeAlias, cast

from routedef import JSONValue, RouteDef, RouteRequest, RouteResponse, RouteTable


@dataclass(frozen=True, slots=True)
class BillingUser:
    user_id: str
    roles: frozenset[str]


@dataclass(frozen=True, slots=True)
class AdminUser:
    user_id: str
    scopes: frozenset[str]


@dataclass(frozen=True, slots=True)
class TaybolsUser:
    sub: str
    email: str
    scopes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IncomingRequest:
    method: str
    path: str
    headers: Mapping[str, str]


BillingContext: TypeAlias = dict[str, object]
BillingRoute: TypeAlias = RouteDef[BillingUser, BillingContext]
BillingRequest: TypeAlias = RouteRequest[BillingUser, BillingContext]
BillingEnforcer: TypeAlias = Callable[
    [BillingRoute, IncomingRequest, BillingContext, BillingUser], bool | RouteResponse
]

AdminContext: TypeAlias = dict[str, object]
AdminRoute: TypeAlias = RouteDef[AdminUser, AdminContext]
AdminRequest: TypeAlias = RouteRequest[AdminUser, AdminContext]
AdminAuthorize: TypeAlias = Callable[[AdminUser, str, Mapping[str, object]], bool]
AdminEnforcer: TypeAlias = Callable[[AdminRoute, IncomingRequest, AdminContext, AdminUser], bool | RouteResponse]

TaybolsContext: TypeAlias = dict[str, object]
TaybolsRoute: TypeAlias = RouteDef[TaybolsUser, TaybolsContext]
TaybolsRequest: TypeAlias = RouteRequest[TaybolsUser, TaybolsContext]


async def billing_handler(request: BillingRequest) -> RouteResponse:
    return RouteResponse.json(
        {
            "account_id": request.path_params["account_id"],
            "actor": request.auth.user_id,
            "tenant": cast(str, request.context["tenant"]),
        }
    )


async def admin_handler(request: AdminRequest) -> RouteResponse:
    return RouteResponse.json({"deleted": request.path_params["user_id"], "actor": request.auth.user_id})


async def taybols_handler(request: TaybolsRequest) -> RouteResponse:
    return RouteResponse.json(
        {
            "sub": request.auth.sub,
            "email": request.auth.email,
            "scopes": list(request.auth.scopes),
            "app": cast(str, request.context["app"]),
        }
    )


def billing_role_enforcer(
    route: BillingRoute,
    request: IncomingRequest,
    context: BillingContext,
    auth: BillingUser,
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
                "tenant": cast(str, context["tenant"]),
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


def taybols_auth_provider(
    route: TaybolsRoute,
    request: IncomingRequest,
    context: TaybolsContext,
) -> TaybolsUser:
    assert route.metadata["auth"] == "taybols-jwt"
    assert context["app"] == "taybols"
    scheme, _, token = request.headers["authorization"].partition(" ")
    assert scheme == "Bearer"
    claims = _decode_fake_jwt_payload(token)
    return TaybolsUser(
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


async def _dispatch_billing(
    route: BillingRoute,
    incoming: IncomingRequest,
    context: BillingContext,
    auth: BillingUser,
    enforcer: BillingEnforcer,
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


async def _dispatch_taybols(
    route: TaybolsRoute,
    incoming: IncomingRequest,
    context: TaybolsContext,
) -> RouteResponse:
    table = RouteTable([route])
    match = table.match(incoming.method, incoming.path)
    assert match is not None
    auth = taybols_auth_provider(match.route, incoming, context)
    route_request = RouteRequest(
        method=incoming.method,
        path=incoming.path,
        route_path=match.route.path,
        headers=incoming.headers,
        auth=auth,
        context=context,
    )
    return await match.route.handler(route_request)


def test_undef_billing_role_metadata_is_enforced_from_route_def() -> None:
    route = RouteDef(
        "GET",
        "/accounts/{account_id}/invoices",
        billing_handler,
        metadata={"roles": ("billing:read",)},
    )
    incoming = IncomingRequest("GET", "/accounts/acct_123/invoices", {})
    context: BillingContext = {"tenant": "acme"}

    allowed = asyncio.run(
        _dispatch_billing(
            route,
            incoming,
            context,
            BillingUser("user-ok", frozenset({"billing:read"})),
            billing_role_enforcer,
        )
    )
    denied = asyncio.run(
        _dispatch_billing(
            route,
            incoming,
            context,
            BillingUser("user-no", frozenset({"support:read"})),
            billing_role_enforcer,
        )
    )

    assert allowed.status == 200
    assert allowed.body == {"account_id": "acct_123", "actor": "user-ok", "tenant": "acme"}
    assert denied.status == 403
    assert denied.body == {
        "detail": "forbidden",
        "required_roles": ["billing:read"],
        "path": "/accounts/acct_123/invoices",
        "tenant": "acme",
    }


def test_undef_admin_authorize_callback_wraps_into_enforcer() -> None:
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


def test_taybols_jwt_bearer_token_becomes_route_auth_user() -> None:
    token = _fake_jwt({"sub": "user_123", "email": "dev@taybols.test", "scopes": ["games:play"]})
    route = RouteDef(
        "GET",
        "/taybols/me",
        taybols_handler,
        metadata={"auth": "taybols-jwt"},
    )
    incoming = IncomingRequest("GET", "/taybols/me", {"authorization": f"Bearer {token}"})
    context: TaybolsContext = {"app": "taybols"}

    response = asyncio.run(_dispatch_taybols(route, incoming, context))

    assert response.status == 200
    assert response.body == {
        "sub": "user_123",
        "email": "dev@taybols.test",
        "scopes": ["games:play"],
        "app": "taybols",
    }
