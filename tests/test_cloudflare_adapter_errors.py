# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import asyncio
import json
import sys
from types import ModuleType
from typing import TypeVar, cast

import pytest
from cloudflare_fakes import FakeCloudflareResponse, FakeRequest

from routedef import JSONValue, RouteDef, RouteRequest, RouteResponse, RouteTable
from routedef.adapters.cloudflare import AdapterError, CloudflareDispatcher, CloudflareRequest

AuthT = TypeVar("AuthT")
ContextT = TypeVar("ContextT")


@pytest.fixture(autouse=True)
def workers_module(monkeypatch: pytest.MonkeyPatch) -> None:
    module = ModuleType("workers")
    module.__dict__["Response"] = FakeCloudflareResponse
    monkeypatch.setitem(sys.modules, "workers", module)


async def echo_json(request: RouteRequest[object, object]) -> RouteResponse:
    return RouteResponse.json(cast(JSONValue, {"body": request.body, "raw_body": request.raw_body.decode()}))


def dispatch(
    dispatcher: CloudflareDispatcher[AuthT, ContextT],
    request: CloudflareRequest,
) -> FakeCloudflareResponse:
    return cast(FakeCloudflareResponse, asyncio.run(dispatcher.dispatch(request)))


def response_json(response: FakeCloudflareResponse) -> dict[str, object]:
    return cast(dict[str, object], json.loads(response.body))


def test_cloudflare_dispatcher_allows_body_at_size_limit() -> None:
    dispatcher = CloudflareDispatcher(RouteTable([RouteDef("POST", "/v1/items", echo_json)]), max_body_bytes=2)

    response = dispatch(
        dispatcher,
        FakeRequest("https://x.test/v1/items", method="POST", headers={"Content-Type": "application/json"}, body=b"{}"),
    )

    assert response.status == 200
    assert response_json(response) == {"body": {}, "raw_body": "{}"}


def test_cloudflare_dispatcher_uses_error_handler_for_body_too_large() -> None:
    def error_handler(error: AdapterError, request: CloudflareRequest) -> RouteResponse:
        return RouteResponse.json(
            {"kind": error.kind, "status": error.status, "message": error.message, "url": request.url},
            status=499,
        )

    dispatcher = CloudflareDispatcher(
        RouteTable([RouteDef("POST", "/v1/items", echo_json)]),
        error_handler=error_handler,
        max_body_bytes=1,
    )

    response = dispatch(
        dispatcher,
        FakeRequest("https://x.test/v1/items", method="POST", headers={"Content-Type": "application/json"}, body=b"{}"),
    )

    assert response.status == 499
    assert response_json(response) == {
        "kind": "body_too_large",
        "status": 413,
        "message": "request body is too large",
        "url": "https://x.test/v1/items",
    }


def test_cloudflare_dispatcher_error_handler_receives_exception_status_and_cause() -> None:
    async def broken(request: RouteRequest[object, object]) -> RouteResponse:
        raise ValueError("boom")

    def error_handler(error: AdapterError, request: CloudflareRequest) -> RouteResponse:
        return RouteResponse.json(
            {
                "exception": type(error.exception).__name__ if error.exception is not None else None,
                "kind": error.kind,
                "message": error.message,
                "status": error.status,
                "url": request.url,
            },
            status=499,
        )

    dispatcher = CloudflareDispatcher(
        RouteTable([RouteDef("GET", "/v1/broken", broken)]),
        error_handler=error_handler,
    )

    response = dispatch(dispatcher, FakeRequest("https://x.test/v1/broken", method="GET"))

    assert response.status == 499
    assert response_json(response) == {
        "exception": "ValueError",
        "kind": "exception",
        "message": "boom",
        "status": 500,
        "url": "https://x.test/v1/broken",
    }
