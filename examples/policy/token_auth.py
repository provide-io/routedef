# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeAlias, cast

from routedef import RouteDef, RouteRequest, RouteResponse, RouteTable


@dataclass(frozen=True, slots=True)
class User:
    subject: str
    scopes: frozenset[str]


@dataclass(frozen=True, slots=True)
class IncomingRequest:
    method: str
    path: str
    headers: Mapping[str, str]


Context: TypeAlias = dict[str, object]
Route: TypeAlias = RouteDef[User, Context]
Request: TypeAlias = RouteRequest[User, Context]


def parse_bearer_token(route: Route, incoming: IncomingRequest, context: Context) -> User:
    if route.metadata.get("auth") != "bearer-token":
        raise ValueError("unsupported auth metadata")
    if context.get("issuer") != "example-idp":
        raise ValueError("unsupported token issuer")

    scheme, _, token = incoming.headers.get("authorization", "").partition(" ")
    if scheme != "Bearer" or not token:
        raise ValueError("missing bearer token")

    subject, _, scopes = token.partition("|")
    return User(subject=subject, scopes=frozenset(scope for scope in scopes.split(",") if scope))


async def get_profile(request: Request) -> RouteResponse:
    return RouteResponse.json(
        {
            "subject": request.auth.subject,
            "scopes": sorted(request.auth.scopes),
            "issuer": cast(str, request.context["issuer"]),
        }
    )


async def dispatch(route: Route, incoming: IncomingRequest, context: Context) -> RouteResponse:
    table = RouteTable([route])
    match = table.match(incoming.method, incoming.path)
    if match is None:
        return RouteResponse.json({"detail": "not found"}, status=404)

    auth = parse_bearer_token(match.route, incoming, context)
    request = RouteRequest(
        method=incoming.method,
        path=incoming.path,
        route_path=match.route.path,
        headers=incoming.headers,
        auth=auth,
        context=context,
    )
    return await match.route.handler(request)


async def run_example() -> RouteResponse:
    route = RouteDef("GET", "/me", get_profile, metadata={"auth": "bearer-token"})
    incoming = IncomingRequest("GET", "/me", {"authorization": "Bearer user-123|profile:read,projects:read"})
    return await dispatch(route, incoming, {"issuer": "example-idp"})
