# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Iterator, Mapping
from types import ModuleType
from typing import TypeAlias, TypeVar, cast

import pytest

from routedef import JSONValue, RouteDef, RouteRequest, RouteResponse, RouteTable
from routedef.adapters.cloudflare import CloudflareDispatcher, CloudflareHeaders, CloudflareRequest

AuthT = TypeVar("AuthT")
ContextT = TypeVar("ContextT")
ToPyArrayBufferBody: TypeAlias = bytes | bytearray


def request_headers(headers: CloudflareHeaders | None) -> CloudflareHeaders:
    return {} if headers is None else headers


class FakeCloudflareResponse:
    def __init__(self, body: bytes, *, status: int = 200, headers: Mapping[str, str] | None = None) -> None:
        self.body = body
        self.status = status
        self.headers = dict(headers or {})


class FakeIndexOnlyHeaders:
    def __init__(self, headers: Mapping[str, str]) -> None:
        self._headers = {name.lower(): value for name, value in headers.items()}

    def __getitem__(self, name: str) -> str:
        return self._headers[name.lower()]


class FakeGetOnlyHeaders:
    def __init__(self, headers: Mapping[str, str]) -> None:
        self._headers = {name.lower(): value for name, value in headers.items()}

    def get(self, name: str) -> str | None:
        return self._headers.get(name.lower())


class FakeItemsOnlyHeaders:
    def __init__(self, headers: Mapping[str, str]) -> None:
        self._headers = dict(headers)

    def items(self) -> tuple[tuple[str, str], ...]:
        return tuple(self._headers.items())


class FakeIterableHeaders:
    def __init__(self, headers: Mapping[str, str]) -> None:
        self._headers = tuple(headers.items())

    def __iter__(self) -> Iterator[tuple[str, str]]:
        return iter(self._headers)


class FakeRequest:
    def __init__(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: CloudflareHeaders | None = None,
        body: bytes = b"",
    ) -> None:
        self.url = url
        self.method = method
        self.headers = request_headers(headers)
        self.body = body
        self.array_buffer_reads = 0

    async def arrayBuffer(self) -> bytearray:
        self.array_buffer_reads += 1
        return bytearray(self.body)


class FakeToPyArrayBuffer:
    def __init__(self, body: ToPyArrayBufferBody) -> None:
        self._body = body

    def __bytes__(self) -> bytes:
        raise TypeError("direct bytes conversion is unavailable")

    def to_py(self) -> ToPyArrayBufferBody:
        return self._body


class FakeToPyArrayBufferRequest:
    def __init__(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: CloudflareHeaders | None = None,
        body: ToPyArrayBufferBody = b"",
    ) -> None:
        self.url = url
        self.method = method
        self.headers = request_headers(headers)
        self.body = body

    async def arrayBuffer(self) -> FakeToPyArrayBuffer:
        return FakeToPyArrayBuffer(self.body)


class FakeTextRequest:
    def __init__(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: CloudflareHeaders | None = None,
        body: str = "",
    ) -> None:
        self.url = url
        self.method = method
        self.headers = request_headers(headers)
        self.body = body
        self.text_reads = 0

    async def text(self) -> str:
        self.text_reads += 1
        return self.body


class FakeEmptyRequest:
    def __init__(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: CloudflareHeaders | None = None,
    ) -> None:
        self.url = url
        self.method = method
        self.headers = request_headers(headers)


@pytest.fixture(autouse=True)
def workers_module(monkeypatch: pytest.MonkeyPatch) -> None:
    module = ModuleType("workers")
    module.__dict__["Response"] = FakeCloudflareResponse
    monkeypatch.setitem(sys.modules, "workers", module)


async def echo_request(request: RouteRequest[object, object]) -> RouteResponse:
    return RouteResponse.json(
        cast(
            JSONValue,
            {
                "method": request.method,
                "path": request.path,
                "route_path": request.route_path,
                "path_params": dict(request.path_params),
                "query": dict(request.query),
                "headers": dict(request.headers),
                "body": request.body,
                "raw_body": request.raw_body.decode(),
                "auth": request.auth,
                "context": request.context,
            },
        )
    )


def dispatch(
    dispatcher: CloudflareDispatcher[AuthT, ContextT],
    request: CloudflareRequest,
) -> FakeCloudflareResponse:
    return cast(FakeCloudflareResponse, asyncio.run(dispatcher.dispatch(request)))


def response_json(response: FakeCloudflareResponse) -> dict[str, object]:
    return cast(dict[str, object], json.loads(response.body))


def test_cloudflare_dispatcher_dispatches_with_context_and_auth() -> None:
    async def handler(request: RouteRequest[str, dict[str, str]]) -> RouteResponse:
        return RouteResponse.json({"auth": request.auth, "runtime": request.context["runtime"]})

    dispatcher = CloudflareDispatcher(
        RouteTable([RouteDef("GET", "/v1/items/{id}", handler)]),
        context_provider=lambda request: {"runtime": "cf"},
        auth_provider=lambda route, request, context: "user",
    )

    response = cast(
        FakeCloudflareResponse,
        asyncio.run(dispatcher.dispatch(FakeRequest("https://x.test/v1/items/7", method="GET"))),
    )

    assert response.status == 200
    assert response_json(response) == {"auth": "user", "runtime": "cf"}


def test_cloudflare_dispatcher_handles_json_body() -> None:
    dispatcher = CloudflareDispatcher(RouteTable([RouteDef("POST", "/v1/items", echo_request)]))

    response = dispatch(
        dispatcher,
        FakeRequest(
            "https://x.test/v1/items",
            method="POST",
            headers={"Content-Type": "application/json"},
            body=b'{"name":"desk"}',
        ),
    )

    assert response.status == 200
    assert response_json(response)["body"] == {"name": "desk"}
    assert response_json(response)["raw_body"] == '{"name":"desk"}'


def test_cloudflare_dispatcher_handles_request_without_body_reader() -> None:
    dispatcher = CloudflareDispatcher(RouteTable([RouteDef("POST", "/v1/items", echo_request)]))

    response = dispatch(dispatcher, FakeEmptyRequest("https://x.test/v1/items", method="POST"))

    assert response.status == 200
    assert response_json(response)["body"] is None
    assert response_json(response)["raw_body"] == ""


def test_cloudflare_dispatcher_handles_text_body_from_text_reader() -> None:
    dispatcher = CloudflareDispatcher(RouteTable([RouteDef("POST", "/v1/notes", echo_request)]))
    request = FakeTextRequest(
        "https://x.test/v1/notes",
        method="POST",
        headers={"Content-Type": "text/plain; charset=utf-8"},
        body="hello",
    )

    response = dispatch(dispatcher, request)

    assert request.text_reads == 1
    assert response.status == 200
    assert response_json(response)["body"] == "hello"
    assert response_json(response)["raw_body"] == "hello"


def test_cloudflare_dispatcher_preserves_raw_binary_body_without_decoding() -> None:
    dispatcher = CloudflareDispatcher(RouteTable([RouteDef("POST", "/v1/blob", echo_request)]))

    response = dispatch(
        dispatcher,
        FakeRequest(
            "https://x.test/v1/blob",
            method="POST",
            headers={"Content-Type": "application/octet-stream"},
            body=b"raw",
        ),
    )

    assert response.status == 200
    assert response_json(response)["body"] is None
    assert response_json(response)["raw_body"] == "raw"


def test_cloudflare_dispatcher_prefers_array_buffer_body_reader() -> None:
    dispatcher = CloudflareDispatcher(RouteTable([RouteDef("POST", "/v1/items", echo_request)]))
    request = FakeRequest(
        "https://x.test/v1/items",
        method="POST",
        headers={"Content-Type": "application/json"},
        body=b'{"ok":true}',
    )

    response = dispatch(dispatcher, request)

    assert request.array_buffer_reads == 1
    assert response.status == 200
    assert response_json(response)["body"] == {"ok": True}


@pytest.mark.parametrize("body", [b'{"ok":true}', bytearray(b'{"ok":true}')])
def test_cloudflare_dispatcher_handles_to_py_array_buffer_proxy(body: ToPyArrayBufferBody) -> None:
    dispatcher = CloudflareDispatcher(RouteTable([RouteDef("POST", "/v1/items", echo_request)]))
    request = FakeToPyArrayBufferRequest(
        "https://x.test/v1/items",
        method="POST",
        headers={"Content-Type": "application/json"},
        body=body,
    )

    with pytest.raises(TypeError, match="direct bytes conversion is unavailable"):
        bytes(FakeToPyArrayBuffer(body))

    response = dispatch(dispatcher, request)

    assert response.status == 200
    assert response_json(response)["body"] == {"ok": True}
    assert response_json(response)["raw_body"] == '{"ok":true}'


def test_cloudflare_dispatcher_handles_query_params() -> None:
    dispatcher = CloudflareDispatcher(RouteTable([RouteDef("GET", "/v1/items/{id}", echo_request)]))

    response = dispatch(dispatcher, FakeRequest("https://x.test/v1/items/7?q=books&empty=", method="GET"))

    assert response.status == 200
    assert response_json(response)["path"] == "/v1/items/7"
    assert response_json(response)["route_path"] == "/v1/items/{id}"
    assert response_json(response)["path_params"] == {"id": "7"}
    assert response_json(response)["query"] == {"q": "books", "empty": ""}


def test_cloudflare_dispatcher_normalizes_headers() -> None:
    dispatcher = CloudflareDispatcher(RouteTable([RouteDef("GET", "/v1/headers", echo_request)]))

    response = dispatch(
        dispatcher,
        FakeRequest(
            "https://x.test/v1/headers", method="GET", headers={"X-Trace": "abc", "Content-Type": "text/plain"}
        ),
    )

    assert response.status == 200
    assert response_json(response)["headers"] == {"x-trace": "abc", "content-type": "text/plain"}


def test_cloudflare_dispatcher_normalizes_items_only_headers() -> None:
    dispatcher = CloudflareDispatcher(RouteTable([RouteDef("GET", "/v1/headers", echo_request)]))

    response = dispatch(
        dispatcher,
        FakeRequest(
            "https://x.test/v1/headers",
            method="GET",
            headers=FakeItemsOnlyHeaders({"X-Trace": "abc", "Content-Type": "text/plain"}),
        ),
    )

    assert response.status == 200
    assert response_json(response)["headers"] == {"x-trace": "abc", "content-type": "text/plain"}


def test_cloudflare_dispatcher_normalizes_iterable_pair_headers() -> None:
    dispatcher = CloudflareDispatcher(RouteTable([RouteDef("GET", "/v1/headers", echo_request)]))

    response = dispatch(
        dispatcher,
        FakeRequest(
            "https://x.test/v1/headers",
            method="GET",
            headers=FakeIterableHeaders({"X-Trace": "abc", "Content-Type": "text/plain"}),
        ),
    )

    assert response.status == 200
    assert response_json(response)["headers"] == {"x-trace": "abc", "content-type": "text/plain"}


def test_cloudflare_dispatcher_reads_json_content_type_from_index_only_headers() -> None:
    dispatcher = CloudflareDispatcher(RouteTable([RouteDef("POST", "/v1/items", echo_request)]))

    response = dispatch(
        dispatcher,
        FakeRequest(
            "https://x.test/v1/items",
            method="POST",
            headers=FakeIndexOnlyHeaders({"Content-Type": "application/json"}),
            body=b'{"name":"desk"}',
        ),
    )

    assert response.status == 200
    assert response_json(response)["headers"] == {"content-type": "application/json"}
    assert response_json(response)["body"] == {"name": "desk"}


def test_cloudflare_dispatcher_reads_text_content_type_from_get_only_headers() -> None:
    dispatcher = CloudflareDispatcher(RouteTable([RouteDef("POST", "/v1/notes", echo_request)]))

    response = dispatch(
        dispatcher,
        FakeTextRequest(
            "https://x.test/v1/notes",
            method="POST",
            headers=FakeGetOnlyHeaders({"Content-Type": "text/plain; charset=utf-8"}),
            body="hello",
        ),
    )

    assert response.status == 200
    assert response_json(response)["headers"] == {"content-type": "text/plain; charset=utf-8"}
    assert response_json(response)["body"] == "hello"


def test_cloudflare_dispatcher_returns_400_for_invalid_json() -> None:
    dispatcher = CloudflareDispatcher(RouteTable([RouteDef("POST", "/v1/items", echo_request)]))

    response = dispatch(
        dispatcher,
        FakeRequest(
            "https://x.test/v1/items",
            method="POST",
            headers={"Content-Type": "Application/JSON; charset=utf-8"},
            body=b"{bad",
        ),
    )

    assert response.status == 400
    assert response_json(response) == {"detail": "request body is not valid JSON"}


def test_cloudflare_dispatcher_returns_404_for_no_match() -> None:
    dispatcher = CloudflareDispatcher(RouteTable([RouteDef("GET", "/v1/items", echo_request)]))

    response = dispatch(dispatcher, FakeRequest("https://x.test/v1/missing", method="GET"))

    assert response.status == 404
    assert response_json(response) == {"detail": "not found"}


def test_cloudflare_dispatcher_denies_enforcer_false_with_403() -> None:
    dispatcher = CloudflareDispatcher(
        RouteTable([RouteDef("GET", "/v1/denied", echo_request)]),
        enforcer=lambda route, request, context, auth: False,
    )

    response = dispatch(dispatcher, FakeRequest("https://x.test/v1/denied", method="GET"))

    assert response.status == 403
    assert response_json(response) == {"detail": "forbidden"}


def test_cloudflare_dispatcher_supports_async_callbacks() -> None:
    async def handler(request: RouteRequest[str, dict[str, str]]) -> RouteResponse:
        return RouteResponse.json({"auth": request.auth, "runtime": request.context["runtime"]})

    async def context_provider(request: CloudflareRequest) -> dict[str, str]:
        assert request.url == "https://x.test/v1/async"
        return {"runtime": "cf"}

    async def auth_provider(
        route: RouteDef[str, dict[str, str]],
        request: CloudflareRequest,
        context: dict[str, str],
    ) -> str:
        assert route.path == "/v1/async"
        assert request.url == "https://x.test/v1/async"
        assert context == {"runtime": "cf"}
        return f"{route.method}:{context['runtime']}"

    async def enforcer(
        route: RouteDef[str, dict[str, str]],
        request: CloudflareRequest,
        context: dict[str, str],
        auth: str,
    ) -> bool:
        assert route.path == "/v1/async"
        assert request.url == "https://x.test/v1/async"
        assert context == {"runtime": "cf"}
        return auth == "GET:cf"

    dispatcher = CloudflareDispatcher(
        RouteTable([RouteDef("GET", "/v1/async", handler)]),
        context_provider=context_provider,
        auth_provider=auth_provider,
        enforcer=enforcer,
    )

    response = dispatch(dispatcher, FakeRequest("https://x.test/v1/async", method="GET"))

    assert response.status == 200
    assert response_json(response) == {"auth": "GET:cf", "runtime": "cf"}


def test_cloudflare_dispatcher_uses_enforcer_response() -> None:
    dispatcher = CloudflareDispatcher(
        RouteTable([RouteDef("GET", "/v1/policy", echo_request)]),
        enforcer=lambda route, request, context, auth: RouteResponse.json({"detail": "custom"}, status=401),
    )

    response = dispatch(dispatcher, FakeRequest("https://x.test/v1/policy", method="GET"))

    assert response.status == 401
    assert response_json(response) == {"detail": "custom"}


def test_cloudflare_dispatcher_converts_route_response() -> None:
    async def handler(request: RouteRequest[object, object]) -> RouteResponse:
        return RouteResponse.text("created", status=201, headers={"X-Result": "yes"})

    dispatcher = CloudflareDispatcher(RouteTable([RouteDef("POST", "/v1/items", handler)]))

    response = dispatch(dispatcher, FakeRequest("https://x.test/v1/items", method="POST"))

    assert response.status == 201
    assert response.body == b"created"
    assert response.headers == {"x-result": "yes", "content-type": "text/plain; charset=utf-8"}
