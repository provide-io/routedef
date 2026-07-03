# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Iterable, Mapping
from importlib import import_module
from typing import Generic, Protocol, SupportsBytes, TypeAlias, TypeVar, cast, runtime_checkable
from urllib.parse import urlsplit

from routedef.adapters.errors import AdapterError
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
ErrorHandler = Callable[[AdapterError, "CloudflareRequest"], MaybeAwaitable[RouteResponse]]
ArrayBufferBody: TypeAlias = bytes | bytearray | memoryview
ArrayBufferProxyBody: TypeAlias = ArrayBufferBody | Iterable[int] | SupportsBytes
HeaderPair: TypeAlias = tuple[str, str]
HeaderPairs: TypeAlias = Iterable[HeaderPair]
ResponseFactory: TypeAlias = Callable[..., object]

JSON_CONTENT_TYPE = "application/json"
JSON_SUFFIX = "+json"
TEXT_PREFIX = "text/"
LOOKUP_HEADER_NAMES: tuple[str, ...] = (
    "accept",
    "accept-encoding",
    "authorization",
    "cache-control",
    "content-length",
    "content-type",
    "cookie",
    "host",
    "if-match",
    "if-modified-since",
    "if-none-match",
    "if-unmodified-since",
    "referer",
    "user-agent",
    "x-forwarded-for",
    "x-forwarded-host",
    "x-forwarded-proto",
    "x-real-ip",
)
__all__ = ("AdapterError", "CloudflareDispatcher", "CloudflareRequest")


@runtime_checkable
class HeaderItems(Protocol):
    def items(self) -> HeaderPairs: ...


@runtime_checkable
class HeaderGetter(Protocol):
    def get(self, name: str) -> str | None: ...


@runtime_checkable
class HeaderIndexer(Protocol):
    def __getitem__(self, name: str) -> str: ...


@runtime_checkable
class ArrayBufferProxy(Protocol):
    def to_py(self) -> ArrayBufferProxyBody: ...


CloudflareHeaders: TypeAlias = Mapping[str, str] | HeaderPairs | HeaderItems | HeaderGetter | HeaderIndexer
ArrayBufferResult: TypeAlias = ArrayBufferBody | ArrayBufferProxy


class CloudflareRequest(Protocol):
    method: str
    url: str
    headers: CloudflareHeaders


@runtime_checkable
class ArrayBufferRequest(CloudflareRequest, Protocol):
    def arrayBuffer(self) -> Awaitable[ArrayBufferResult]: ...


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
        error_handler: ErrorHandler | None = None,
        max_body_bytes: int | None = None,
    ) -> None:
        self._route_table = route_table
        self._context_provider = context_provider
        self._auth_provider = auth_provider
        self._enforcer = enforcer
        self._error_handler = error_handler
        self._max_body_bytes = max_body_bytes

    async def dispatch(self, request: CloudflareRequest) -> object:
        url = urlsplit(request.url)
        match = self._route_table.match(request.method, url.path)
        if match is None:
            return await self._error_response(AdapterError("not_found", 404, "not found"), request)

        context: ContextT = await self._resolve_context(request)
        auth: AuthT = await self._resolve_auth(match.route, request, context)
        enforcement: EnforcerResult = await self._resolve_enforcement(match.route, request, context, auth)
        if isinstance(enforcement, RouteResponse):
            return _to_cloudflare_response(enforcement)
        if enforcement is False:
            return await self._error_response(AdapterError("forbidden", 403, "forbidden"), request)

        try:
            route_request = await _to_route_request(
                request, match.route, match.path_params, context, auth, max_body_bytes=self._max_body_bytes
            )
        except _InvalidBody as exc:
            return await self._error_response(AdapterError("bad_request", 400, str(exc)), request)
        except _BodyTooLarge as exc:
            return await self._error_response(AdapterError("body_too_large", 413, str(exc)), request)
        try:
            route_response = await match.route.handler(route_request)
        except Exception as exc:
            return await self._error_response(AdapterError("exception", 500, str(exc), exc), request)
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

    async def _error_response(self, error: AdapterError, request: CloudflareRequest) -> object:
        if self._error_handler is None:
            return _to_cloudflare_response(RouteResponse.json({"detail": error.message}, status=error.status))
        return _to_cloudflare_response(await _resolve(self._error_handler(error, request)))


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
    *,
    max_body_bytes: int | None,
) -> RouteRequest[AuthT, ContextT]:
    url = urlsplit(request.url)
    headers = _normalize_cloudflare_headers(request.headers)
    raw_body = await _read_raw_body(request)
    if max_body_bytes is not None and len(raw_body) > max_body_bytes:
        raise _BodyTooLarge("request body is too large")
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


def _normalize_cloudflare_headers(headers: CloudflareHeaders) -> Mapping[str, str]:
    if isinstance(headers, Mapping):
        return _normalize_mapping_headers(headers)  # pragma: no mutate - mapping behavior is covered via dispatch.
    if isinstance(headers, HeaderItems):
        return _normalize_header_pairs(headers.items())
    if isinstance(headers, Iterable):
        return _normalize_iterable_headers(headers)
    return _normalize_lookup_headers(headers)


def _normalize_mapping_headers(headers: CloudflareHeaders) -> Mapping[str, str]:
    return normalize_headers(cast(Mapping[str, str], headers))  # pragma: no mutate - cast is runtime-neutral.


def _normalize_iterable_headers(headers: CloudflareHeaders) -> Mapping[str, str]:
    return _normalize_header_pairs(cast(HeaderPairs, headers))  # pragma: no mutate - cast is runtime-neutral.


def _normalize_header_pairs(headers: HeaderPairs) -> Mapping[str, str]:
    return {name.lower(): value for name, value in headers}


def _normalize_lookup_headers(headers: HeaderGetter | HeaderIndexer) -> Mapping[str, str]:
    normalized: dict[str, str] = {}
    for name in LOOKUP_HEADER_NAMES:
        value = _lookup_header(headers, name)
        if value is not None:
            normalized[name] = value
    return normalized


def _lookup_header(headers: HeaderGetter | HeaderIndexer, name: str) -> str | None:
    if isinstance(headers, HeaderGetter):
        value = headers.get(name)
        if value is not None:
            return value
    if isinstance(headers, HeaderIndexer):
        try:
            return headers[name]
        except (IndexError, KeyError, TypeError):
            return None
    return None


async def _read_raw_body(request: CloudflareRequest) -> bytes:
    if isinstance(request, ArrayBufferRequest):
        return _array_buffer_to_bytes(await request.arrayBuffer())
    if isinstance(request, TextRequest):
        return (await request.text()).encode()
    return b""


def _array_buffer_to_bytes(body: ArrayBufferResult) -> bytes:
    if isinstance(body, ArrayBufferProxy):
        return bytes(body.to_py())
    return bytes(body)


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


class _BodyTooLarge(Exception):
    pass
