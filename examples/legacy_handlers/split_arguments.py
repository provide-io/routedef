# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import TypeAlias, cast

from routedef import JSONValue, RouteDef, RouteHandler, RouteRequest, RouteResponse, RouteTable

Context: TypeAlias = dict[str, object]
SessionAuth: TypeAlias = dict[str, object]
LegacyHandler: TypeAlias = Callable[
    [Mapping[str, str], object | None, Mapping[str, str], object, SessionAuth],
    Awaitable[RouteResponse],
]


def adapt_split_arguments(handler: LegacyHandler) -> RouteHandler[SessionAuth, Context]:
    async def wrapped(request: RouteRequest[SessionAuth, Context]) -> RouteResponse:
        return await handler(
            request.path_params,
            request.body,
            request.query,
            request.context["session"],
            request.auth,
        )

    return wrapped


async def create_event(
    path_params: Mapping[str, str],
    body: object | None,
    query: Mapping[str, str],
    session: object,
    auth: SessionAuth,
) -> RouteResponse:
    typed_body = cast(Mapping[str, object], body)
    typed_session = cast(Mapping[str, object], session)
    return RouteResponse.json(
        cast(
            JSONValue,
            {
                "project_id": path_params["project_id"],
                "event": typed_body["event"],
                "debug": query.get("debug", "false"),
                "session": typed_session["id"],
                "actor": auth["user_id"],
            },
        )
    )


async def run_example() -> RouteResponse:
    route: RouteDef[SessionAuth, Context] = RouteDef(
        "POST",
        "/projects/{project_id}/events",
        adapt_split_arguments(create_event),
    )
    table = RouteTable([route])
    request = RouteRequest[SessionAuth, Context](
        method="POST",
        path="/projects/project-123/events",
        route_path="/projects/{project_id}/events",
        query={"debug": "true"},
        body={"event": "deployed"},
        auth={"user_id": "user-123"},
        context={"session": {"id": "session-123"}},
    )
    match = table.match(request.method, request.path)
    if match is None:
        return RouteResponse.json({"detail": "not found"}, status=404)

    matched_request = RouteRequest(
        method=request.method,
        path=request.path,
        route_path=match.route.path,
        path_params=match.path_params,
        query=request.query,
        headers=request.headers,
        body=request.body,
        raw_body=request.raw_body,
        auth=request.auth,
        context=request.context,
    )
    return await match.route.handler(matched_request)
