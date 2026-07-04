# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeAlias, cast

from routedef import JSONValue, RouteDef, RouteRequest, RouteResponse, RouteTable


@dataclass(frozen=True, slots=True)
class User:
    user_id: str
    roles: frozenset[str]


@dataclass(frozen=True, slots=True)
class IncomingRequest:
    method: str
    path: str
    headers: Mapping[str, str]


Context: TypeAlias = dict[str, object]
Route: TypeAlias = RouteDef[User, Context]
Request: TypeAlias = RouteRequest[User, Context]


async def list_reports(request: Request) -> RouteResponse:
    return RouteResponse.json(
        {
            "project_id": request.path_params["project_id"],
            "actor": request.auth.user_id,
            "workspace": cast(str, request.context["workspace"]),
        }
    )


def enforce_roles(route: Route, incoming: IncomingRequest, context: Context, user: User) -> bool | RouteResponse:
    required_roles = set(cast(tuple[str, ...], route.metadata.get("roles", ())))
    if required_roles <= user.roles:
        return True
    return RouteResponse.json(
        cast(
            JSONValue,
            {
                "detail": "forbidden",
                "required_roles": sorted(required_roles),
                "path": incoming.path,
                "workspace": cast(str, context["workspace"]),
            },
        ),
        status=403,
    )


async def dispatch(route: Route, incoming: IncomingRequest, context: Context, user: User) -> RouteResponse:
    table = RouteTable([route])
    match = table.match(incoming.method, incoming.path)
    if match is None:
        return RouteResponse.json({"detail": "not found"}, status=404)

    enforcement = enforce_roles(match.route, incoming, context, user)
    if isinstance(enforcement, RouteResponse):
        return enforcement

    request = RouteRequest(
        method=incoming.method,
        path=incoming.path,
        route_path=match.route.path,
        path_params=match.path_params,
        headers=incoming.headers,
        auth=user,
        context=context,
    )
    return await match.route.handler(request)


async def run_example() -> tuple[RouteResponse, RouteResponse]:
    route = RouteDef(
        "GET",
        "/projects/{project_id}/reports",
        list_reports,
        metadata={"roles": ("reports:read",)},
    )
    incoming = IncomingRequest("GET", "/projects/project-123/reports", {})
    context: Context = {"workspace": "acme"}

    allowed = await dispatch(route, incoming, context, User("user-ok", frozenset({"reports:read"})))
    denied = await dispatch(route, incoming, context, User("user-no", frozenset()))
    return allowed, denied
