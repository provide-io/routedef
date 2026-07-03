# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping
from importlib import import_module
from typing import Generic, Protocol, TypeAlias, TypeVar, cast, runtime_checkable
from urllib.parse import urlsplit

from routedef.contracts import RouteDef, RouteRequest, RouteResponse
from routedef.errors import BadRequestBody
from routedef.headers import get_header, normalize_headers
from routedef.request import decode_json_body, decode_text_body, parse_query
from routedef.response import serialize_response_body
from routedef.table import RouteTable

AuthT = TypeVar("AuthT")
ContextT = TypeVar("ContextT")
ValueT = TypeVar("ValueT")

MaybeAwaitable: TypeAlias = Awaitable[ValueT] | ValueT
ContextProvider = Callable[["CloudflareRequest"], MaybeAwaitable[ContextT]]
AuthProvider = Callable[[RouteDef[AuthT, ContextT], "CloudflareRequest", ContextT], MaybeAwaitable[AuthT]]
EnforcerResult = None | bool | RouteResponse
Enforcer = Callable[[RouteDef[AuthT, ContextT], "CloudflareRequest", ContextT, AuthT], MaybeAwaitable[EnforcerResult]]
ArrayBufferBody: TypeAlias = bytes | bytearray | memoryview
ResponseFactory: TypeAlias = Callable[..., object]

JSON_CONTENT_TYPE = "application/json"
JSON_SUFFIX = "+json"
TEXT_PREFIX = "text/"


class CloudflareRequest(Protocol):
    method: str
    url: str
    headers: Mapping[str, str]


@runtime_checkable
class ArrayBufferRequest(CloudflareRequest, Protocol):
    def arrayBuffer(self) -> Awaitable[ArrayBufferBody]: ...


@runtime_checkable
class TextRequest(CloudflareRequest, Protocol):
    def text(self) -> Awaitable[str]: ...


class CloudflareDispatcher(Generic[AuthT, ContextT]):
    def __init__(
        self,
        route_table: RouteTable[AuthT, ContextT],
        *,
        context_provider: ContextProvider[ContextT] | None = None,
        auth_provider: AuthProvider[AuthT, ContextT] | None = None,
        enforcer: Enforcer[AuthT, ContextT] | None = None,
    ) -> None:
        self._route_table = route_table
        self._context_provider = context_provider
        self._auth_provider = auth_provider
        self._enforcer = enforcer

    async def dispatch(self, request: CloudflareRequest) -> object:
        url = urlsplit(request.url)
        match = self._route_table.match(request.method, url.path)
        if match is None:
            return _to_cloudflare_response(RouteResponse.json({"detail": "not found"}, status=404))

        context: ContextT = await self._resolve_context(request)
        auth: AuthT = await self._resolve_auth(match.route, request, context)
        enforcement: EnforcerResult = await self._resolve_enforcement(match.route, request, context, auth)
        if isinstance(enforcement, RouteResponse):
            return _to_cloudflare_response(enforcement)
        if enforcement is False:
            return _to_cloudflare_response(RouteResponse.json({"detail": "forbidden"}, status=403))

        try:
            route_request = await _to_route_request(request, match.route, match.path_params, context, auth)
        except _InvalidBody as exc:
            return _to_cloudflare_response(RouteResponse.json({"detail": str(exc)}, status=400))
        route_response = await match.route.handler(route_request)
        return _to_cloudflare_response(route_response)

    async def _resolve_context(self, request: CloudflareRequest) -> ContextT:
        if self._context_provider is None:
            return cast(ContextT, None)  # pragma: no mutate - cast is runtime-neutral.
        return await _resolve(self._context_provider(request))

    async def _resolve_auth(
        self,
        route: RouteDef[AuthT, ContextT],
        request: CloudflareRequest,
        context: ContextT,
    ) -> AuthT:
        if self._auth_provider is None:
            return cast(AuthT, None)  # pragma: no mutate - cast is runtime-neutral.
        return await _resolve(self._auth_provider(route, request, context))

    async def _resolve_enforcement(
        self,
        route: RouteDef[AuthT, ContextT],
        request: CloudflareRequest,
        context: ContextT,
        auth: AuthT,
    ) -> EnforcerResult:
        if self._enforcer is None:
            return None
        return await _resolve(self._enforcer(route, request, context, auth))


async def _resolve(value: MaybeAwaitable[ValueT]) -> ValueT:
    if inspect.isawaitable(value):
        return await cast(Awaitable[ValueT], value)  # pragma: no mutate - cast is runtime-neutral.
    return value


async def _to_route_request(
    request: CloudflareRequest,
    route: RouteDef[AuthT, ContextT],
    path_params: Mapping[str, str],
    context: ContextT,
    auth: AuthT,
) -> RouteRequest[AuthT, ContextT]:
    url = urlsplit(request.url)
    headers = normalize_headers(request.headers)
    raw_body = await _read_raw_body(request)
    try:
        body = _decode_body(raw_body, headers)
    except BadRequestBody as exc:
        raise _InvalidBody(str(exc)) from exc

    return RouteRequest(
        method=request.method,
        path=url.path,
        route_path=route.path,
        path_params=path_params,
        query=parse_query(url.query),
        headers=headers,
        body=body,
        raw_body=raw_body,
        auth=auth,
        context=context,
    )


async def _read_raw_body(request: CloudflareRequest) -> bytes:
    if isinstance(request, ArrayBufferRequest):
        return bytes(await request.arrayBuffer())
    if isinstance(request, TextRequest):
        return (await request.text()).encode()
    return b""


def _decode_body(raw_body: bytes, headers: Mapping[str, str]) -> object | None:
    if not raw_body:
        return None
    if _is_json_request(headers):
        return decode_json_body(raw_body)
    if _is_text_request(headers):
        return decode_text_body(raw_body)
    return None


def _is_json_request(headers: Mapping[str, str]) -> bool:
    media_type = _media_type(headers)
    return media_type == JSON_CONTENT_TYPE or media_type.endswith(JSON_SUFFIX)


def _is_text_request(headers: Mapping[str, str]) -> bool:
    return _media_type(headers).startswith(TEXT_PREFIX)


def _media_type(headers: Mapping[str, str]) -> str:
    content_type = get_header(headers, "content-type") or ""  # pragma: no mutate
    return content_type.partition(";")[0].strip().lower()


def _to_cloudflare_response(response: RouteResponse) -> object:
    workers = import_module("workers")
    response_factory = cast(ResponseFactory, workers.Response)  # pragma: no mutate - cast is runtime-neutral.
    return response_factory(
        serialize_response_body(response),
        status=response.status,
        headers=dict(response.headers),
    )


class _InvalidBody(Exception):
    pass
