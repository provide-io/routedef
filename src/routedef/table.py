# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Generic, TypeVar

from routedef.contracts import RouteDef
from routedef.errors import RouteConfigError
from routedef.matching import CompiledPath, compile_path_template, match_path

AuthT = TypeVar("AuthT")
ContextT = TypeVar("ContextT")


@dataclass(frozen=True, slots=True)
class CompiledRoute(Generic[AuthT, ContextT]):
    route: RouteDef[AuthT, ContextT]
    compiled_path: CompiledPath


@dataclass(frozen=True, slots=True)
class RouteMatch(Generic[AuthT, ContextT]):
    route: RouteDef[AuthT, ContextT]
    path_params: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "path_params", MappingProxyType(dict(self.path_params)))


@dataclass(frozen=True, slots=True)
class RouteTable(Generic[AuthT, ContextT]):
    routes: tuple[CompiledRoute[AuthT, ContextT], ...]

    def __init__(self, routes: Iterable[RouteDef[AuthT, ContextT]]) -> None:
        compiled_routes: list[CompiledRoute[AuthT, ContextT]] = []
        seen_routes: set[tuple[str, str]] = set()
        seen_names: set[str] = set()

        for route in routes:
            route_key = (route.method, route.path)
            if route_key in seen_routes:
                raise RouteConfigError(f"route table contains duplicate route {route.method} {route.path}")
            seen_routes.add(route_key)
            if route.name is not None:
                if route.name in seen_names:
                    raise RouteConfigError(f"route table contains duplicate route name {route.name!r}")
                seen_names.add(route.name)
            compiled_routes.append(CompiledRoute(route=route, compiled_path=compile_path_template(route.path)))

        object.__setattr__(self, "routes", tuple(compiled_routes))

    def match(self, method: str, path: str) -> RouteMatch[AuthT, ContextT] | None:
        normalized_method = _normalize_method(method)
        for compiled_route in self.routes:
            if compiled_route.route.method != normalized_method:
                continue

            path_params = match_path(compiled_route.compiled_path, path)
            if path_params is not None:
                return RouteMatch(route=compiled_route.route, path_params=path_params)

        return None


def _normalize_method(method: str) -> str:
    normalized = method.strip().upper()
    if not normalized:
        raise RouteConfigError("route method must not be empty")
    return normalized
