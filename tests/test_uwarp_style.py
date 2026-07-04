# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import TypeAlias, cast

from routedef import JSONValue, RouteDef, RouteHandler, RouteRequest, RouteResponse, RouteTable

GameContext: TypeAlias = dict[str, object]
UwarpAuth: TypeAlias = dict[str, object]
UwarpHandler: TypeAlias = Callable[
    [Mapping[str, str], object | None, Mapping[str, str], object, UwarpAuth],
    Awaitable[RouteResponse],
]


def adapt_uwarp(handler: UwarpHandler) -> RouteHandler[UwarpAuth, GameContext]:
    async def wrapped(request: RouteRequest[UwarpAuth, GameContext]) -> RouteResponse:
        return await handler(
            request.path_params,
            request.body,
            request.query,
            request.context["game"],
            request.auth,
        )

    return wrapped


async def split_arg_move_handler(
    path_params: Mapping[str, str],
    body: object | None,
    query: Mapping[str, str],
    game: object,
    auth: UwarpAuth,
) -> RouteResponse:
    typed_body = cast(Mapping[str, object], body)
    typed_game = cast(Mapping[str, object], game)
    return RouteResponse.json(
        cast(
            JSONValue,
            {
                "match_id": path_params["match_id"],
                "move": typed_body["move"],
                "debug": query["debug"],
                "game": typed_game["id"],
                "player": auth["player_id"],
            },
        )
    )


async def _dispatch_uwarp(
    route: RouteDef[UwarpAuth, GameContext],
    request: RouteRequest[UwarpAuth, GameContext],
) -> RouteResponse:
    table = RouteTable([route])
    match = table.match(request.method, request.path)
    assert match is not None
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


def test_uwarp_split_arg_handler_can_be_adapted_to_route_handler() -> None:
    route: RouteDef[UwarpAuth, GameContext] = RouteDef(
        "POST", "/games/{match_id}/moves", adapt_uwarp(split_arg_move_handler)
    )
    request = RouteRequest[UwarpAuth, GameContext](
        method="POST",
        path="/games/match-42/moves",
        route_path="/games/{match_id}/moves",
        query={"debug": "true"},
        body={"move": "Nf3"},
        auth={"player_id": "player-7"},
        context={"game": {"id": "chess"}},
    )

    response = asyncio.run(_dispatch_uwarp(route, request))

    assert response.status == 200
    assert response.body == {
        "match_id": "match-42",
        "move": "Nf3",
        "debug": "true",
        "game": "chess",
        "player": "player-7",
    }
