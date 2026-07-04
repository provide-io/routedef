# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any, cast

import pytest

from routedef import CompiledRoute, RouteConfigError, RouteDef, RouteMatch, RouteRequest, RouteResponse, RouteTable


async def echo(request: RouteRequest[None, object]) -> RouteResponse:
    return RouteResponse.json({"path": request.path})


async def fallback(request: RouteRequest[None, object]) -> RouteResponse:
    return RouteResponse.json({"path": request.path, "fallback": True})


def test_route_table_matches_in_registration_order() -> None:
    specific_route = RouteDef("GET", "/v1/items/special", echo)
    placeholder_route = RouteDef("GET", "/v1/items/{id}", fallback)
    table = RouteTable([specific_route, placeholder_route])

    match = table.match("GET", "/v1/items/special")

    assert match is not None
    assert match.route is specific_route
    assert match.path_params == {}


def test_route_table_returns_none_when_no_route_matches() -> None:
    table = RouteTable(
        [
            RouteDef("GET", "/v1/items/{id}", echo),
            RouteDef("POST", "/v1/items", echo),
        ]
    )

    assert table.match("GET", "/v1/users/42") is None
    assert table.match("DELETE", "/v1/items/42") is None


def test_route_table_normalizes_match_method() -> None:
    table = RouteTable([RouteDef("GET", "/v1/items/{id}", echo)])
    match = table.match("get", "/v1/items/42")
    assert match is not None
    assert match.path_params == {"id": "42"}


@pytest.mark.parametrize("method", ["", "   "])
def test_route_table_rejects_empty_match_method(method: str) -> None:
    table = RouteTable([RouteDef("GET", "/v1/items/{id}", echo)])

    with pytest.raises(RouteConfigError) as exc_info:
        table.match(method, "/v1/items/42")

    assert str(exc_info.value) == "route method must not be empty"


def test_route_table_rejects_duplicate_method_and_path() -> None:
    with pytest.raises(RouteConfigError) as exc_info:
        RouteTable(
            [
                RouteDef("GET", "/v1/items/{id}", echo),
                RouteDef("get", "/v1/items/{id}", fallback),
            ]
        )

    assert str(exc_info.value) == "route table contains duplicate route GET /v1/items/{id}"


def test_route_table_rejects_duplicate_route_names() -> None:
    with pytest.raises(RouteConfigError) as exc_info:
        RouteTable(
            [
                RouteDef("GET", "/v1/items", echo, name="items"),
                RouteDef("POST", "/v1/items", fallback, name="items"),
            ]
        )

    assert str(exc_info.value) == "route table contains duplicate route name 'items'"


def test_route_match_exposes_route_and_read_only_path_params() -> None:
    route = RouteDef("GET", "/v1/{org}/items/{id}", echo)
    table = RouteTable([route])

    match = table.match("GET", "/v1/acme/items/42")

    assert isinstance(match, RouteMatch)
    assert match.route is route
    assert match.path_params == {"org": "acme", "id": "42"}
    with pytest.raises(TypeError):
        cast(Any, match.path_params)["id"] = "99"


def test_route_table_exposes_immutable_compiled_routes() -> None:
    route = RouteDef("GET", "/v1/items/{id}", echo)
    table = RouteTable([route])
    compiled_routes = table.routes

    assert isinstance(compiled_routes, tuple)
    assert len(compiled_routes) == 1
    assert isinstance(compiled_routes[0], CompiledRoute)
    assert compiled_routes[0].route is route
    assert compiled_routes[0].compiled_path.path_template == "/v1/items/{id}"
    with pytest.raises(AttributeError):
        cast(Any, table).routes = ()
    with pytest.raises(AttributeError):
        cast(Any, compiled_routes[0]).route = RouteDef("GET", "/v1/other", echo)
