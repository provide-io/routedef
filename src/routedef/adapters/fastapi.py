# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import TypeAlias, TypeVar, cast

from fastapi import APIRouter, Request, Response

from routedef.contracts import RouteDef, RouteRequest, RouteResponse
from routedef.errors import BadRequestBody
from routedef.headers import get_header
from routedef.request import decode_json_body, parse_query
from routedef.response import serialize_response_body
from routedef.table import RouteTable

AuthT = TypeVar("AuthT")
ContextT = TypeVar("ContextT")
ValueT = TypeVar("ValueT")

MaybeAwaitable: TypeAlias = Awaitable[ValueT] | ValueT
ContextProvider = Callable[[Request], MaybeAwaitable[ContextT]]
AuthProvider = Callable[[RouteDef[AuthT, ContextT], Request, ContextT], MaybeAwaitable[AuthT]]
EnforcerResult = None | bool | RouteResponse
Enforcer = Callable[[RouteDef[AuthT, ContextT], Request, ContextT, AuthT], MaybeAwaitable[EnforcerResult]]

JSON_CONTENT_TYPE = "application/json"
JSON_SUFFIX = "+json"


def build_fastapi_router(
    routes: Iterable[RouteDef[AuthT, ContextT]],
    *,
    context_provider: ContextProvider[ContextT] | None = None,
    auth_provider: AuthProvider[AuthT, ContextT] | None = None,
    enforcer: Enforcer[AuthT, ContextT] | None = None,
) -> APIRouter:
    route_table = RouteTable(routes)
    router = APIRouter()

    async def handle(request: Request) -> Response:
        match = route_table.match(request.method, request.url.path)
        assert match is not None

        context: ContextT = await _resolve_context(context_provider, request)
        auth: AuthT = await _resolve_auth(auth_provider, match.route, request, context)
        enforcement: EnforcerResult = await _resolve_enforcement(enforcer, match.route, request, context, auth)
        if isinstance(enforcement, RouteResponse):
            return _to_fastapi_response(enforcement)
        if enforcement is False:
            return _to_fastapi_response(RouteResponse.json({"detail": "forbidden"}, status=403))

        try:
            route_request = await _to_route_request(request, match.route, match.path_params, context, auth)
        except _InvalidJSON as exc:
            return _to_fastapi_response(RouteResponse.json({"detail": str(exc)}, status=400))
        route_response = await match.route.handler(route_request)
        return _to_fastapi_response(route_response)

    for route in route_table.routes:
        router.add_api_route(route.route.path, handle, methods=[route.route.method])

    return router


async def _resolve_context(
    context_provider: ContextProvider[ContextT] | None,
    request: Request,
) -> ContextT:
    if context_provider is None:
        return cast(ContextT, None)  # pragma: no mutate - cast is runtime-neutral.
    return await _resolve(context_provider(request))


async def _resolve_auth(
    auth_provider: AuthProvider[AuthT, ContextT] | None,
    route: RouteDef[AuthT, ContextT],
    request: Request,
    context: ContextT,
) -> AuthT:
    if auth_provider is None:
        return cast(AuthT, None)  # pragma: no mutate - cast is runtime-neutral.
    return await _resolve(auth_provider(route, request, context))


async def _resolve_enforcement(
    enforcer: Enforcer[AuthT, ContextT] | None,
    route: RouteDef[AuthT, ContextT],
    request: Request,
    context: ContextT,
    auth: AuthT,
) -> EnforcerResult:
    if enforcer is None:
        return None
    return await _resolve(enforcer(route, request, context, auth))


async def _resolve(value: MaybeAwaitable[ValueT]) -> ValueT:
    if inspect.isawaitable(value):
        return await cast(Awaitable[ValueT], value)  # pragma: no mutate - cast is runtime-neutral.
    return value


async def _to_route_request(
    request: Request,
    route: RouteDef[AuthT, ContextT],
    path_params: Mapping[str, str],
    context: ContextT,
    auth: AuthT,
) -> RouteRequest[AuthT, ContextT]:
    raw_body = await request.body()
    try:
        body = decode_json_body(raw_body) if raw_body and _is_json_request(request) else None
    except BadRequestBody as exc:
        raise _InvalidJSON(str(exc)) from exc

    return RouteRequest(
        method=request.method,
        path=request.url.path,
        route_path=route.path,
        path_params=path_params,
        query=parse_query(request.url.query),
        headers=dict(request.headers),
        body=body,
        raw_body=raw_body,
        auth=auth,
        context=context,
    )


def _is_json_request(request: Request) -> bool:
    content_type = get_header(dict(request.headers), "content-type") or ""  # pragma: no mutate
    media_type = content_type.partition(";")[0].strip().lower()
    return media_type == JSON_CONTENT_TYPE or media_type.endswith(JSON_SUFFIX)


def _to_fastapi_response(response: RouteResponse) -> Response:
    body = serialize_response_body(response)
    return Response(
        content=body,
        status_code=response.status,
        headers=dict(response.headers),
    )


class _InvalidJSON(Exception):
    pass
