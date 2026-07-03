# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import builtins
from collections.abc import Awaitable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Generic, Protocol, TypeVar, cast

from routedef.errors import RouteConfigError
from routedef.types import JSONValue

AuthT = TypeVar("AuthT")
ContextT = TypeVar("ContextT")
ValueT = TypeVar("ValueT")


def _normalize_method(method: str) -> str:
    normalized = method.strip().upper()
    if not normalized:
        raise RouteConfigError("route method must not be empty")
    return normalized


def _validate_path(path: str) -> str:
    if not path.strip():
        raise RouteConfigError("route path must not be empty")
    if not path.startswith("/"):
        raise RouteConfigError("route path must start with '/'")
    return path


def _readonly_mapping(mapping: Mapping[str, ValueT]) -> Mapping[str, ValueT]:
    snapshot: dict[str, ValueT] = {key: _typed_snapshot(value) for key, value in mapping.items()}
    return MappingProxyType(snapshot)


def _typed_snapshot(value: ValueT) -> ValueT:
    return cast(ValueT, _deep_snapshot(value))  # pragma: no mutate - cast is runtime-neutral.


def _deep_snapshot(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _deep_snapshot(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_deep_snapshot(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_deep_snapshot(item) for item in value)
    return value


def _normalized_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {name.lower(): value for name, value in headers.items()}


def _headers_with_content_type(headers: Mapping[str, str], content_type: str | None) -> Mapping[str, str]:
    normalized_headers = _normalized_headers(headers)
    if content_type is not None and "content-type" not in normalized_headers:
        header_name = "content-type"  # pragma: no mutate - response construction normalizes header keys.
        normalized_headers[header_name] = content_type
    return _readonly_mapping(normalized_headers)


class RouteHandler(Protocol[AuthT, ContextT]):
    def __call__(self, request: RouteRequest[AuthT, ContextT], /) -> Awaitable[RouteResponse]: ...


@dataclass(frozen=True, slots=True)
class RouteDef(Generic[AuthT, ContextT]):
    method: str
    path: str
    handler: RouteHandler[AuthT, ContextT]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", _normalize_method(self.method))
        object.__setattr__(self, "path", _validate_path(self.path))
        object.__setattr__(self, "metadata", _readonly_mapping(self.metadata))


@dataclass(frozen=True, slots=True, kw_only=True)
class RouteRequest(Generic[AuthT, ContextT]):
    method: str
    path: str
    route_path: str
    auth: AuthT
    context: ContextT
    path_params: Mapping[str, str] = field(default_factory=dict)
    query: Mapping[str, str] = field(default_factory=dict)
    headers: Mapping[str, str] = field(default_factory=dict)
    body: object | None = None
    raw_body: builtins.bytes = b""

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", _normalize_method(self.method))
        object.__setattr__(self, "path", _validate_path(self.path))
        object.__setattr__(self, "route_path", _validate_path(self.route_path))
        object.__setattr__(self, "path_params", _readonly_mapping(self.path_params))
        object.__setattr__(self, "query", _readonly_mapping(self.query))
        object.__setattr__(self, "headers", _readonly_mapping(self.headers))
        object.__setattr__(self, "body", _deep_snapshot(self.body))


@dataclass(frozen=True, slots=True, kw_only=True)
class RouteResponse:
    status: int = 200
    body: object | None = None
    headers: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "body", _deep_snapshot(self.body))
        object.__setattr__(self, "headers", _readonly_mapping(_normalized_headers(self.headers)))

    @classmethod
    def json(cls, body: JSONValue, *, status: int = 200, headers: Mapping[str, str] | None = None) -> RouteResponse:
        return cls(status=status, body=body, headers=_headers_with_content_type(headers or {}, "application/json"))

    @classmethod
    def text(cls, body: str, *, status: int = 200, headers: Mapping[str, str] | None = None) -> RouteResponse:
        return cls(
            status=status,
            body=body,
            headers=_headers_with_content_type(headers or {}, "text/plain; charset=utf-8"),
        )

    @classmethod
    def bytes(
        cls,
        body: builtins.bytes,
        *,
        status: int = 200,
        headers: Mapping[str, str] | None = None,
        content_type: str = "application/octet-stream",
    ) -> RouteResponse:
        return cls(status=status, body=body, headers=_headers_with_content_type(headers or {}, content_type))

    @classmethod
    def empty(cls, *, status: int = 204, headers: Mapping[str, str] | None = None) -> RouteResponse:
        return cls(status=status, body=None, headers=_headers_with_content_type(headers or {}, None))
