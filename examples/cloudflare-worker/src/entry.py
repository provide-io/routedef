# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import cast

from workers import WorkerEntrypoint

from routedef import JSONValue, RouteDef, RouteRequest, RouteResponse, RouteTable
from routedef.adapters.cloudflare import CloudflareDispatcher


async def get_item(request: RouteRequest[None, dict[str, str]]) -> RouteResponse:
    return RouteResponse.json(
        cast(
            JSONValue,
            {
                "id": request.path_params["id"],
                "q": request.query.get("q"),
            },
        )
    )


async def create_item(request: RouteRequest[None, dict[str, str]]) -> RouteResponse:
    body = cast(dict[str, object], request.body)
    return RouteResponse.json(cast(JSONValue, {"name": body["name"]}), status=201)


dispatcher = CloudflareDispatcher(
    RouteTable(
        [
            RouteDef("GET", "/v1/items/{id}", get_item),
            RouteDef("POST", "/v1/items", create_item),
        ]
    ),
    context_provider=lambda _request: {"runtime": "cloudflare"},
)


class Default(WorkerEntrypoint):
    async def fetch(self, request: object) -> object:
        return await dispatcher.dispatch(request)
