# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import subprocess
import sys
from typing import cast

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from routedef import JSONValue, RouteDef, RouteRequest, RouteResponse
from routedef.adapters.fastapi import build_fastapi_router


def client_for(routes: list[RouteDef[object, object]]) -> TestClient:
    app = FastAPI()
    app.include_router(build_fastapi_router(routes))
    return TestClient(app)


async def echo_query(request: RouteRequest[object, object]) -> RouteResponse:
    return RouteResponse.json(
        cast(
            JSONValue,
            {
                "path": request.path,
                "route_path": request.route_path,
                "query": dict(request.query),
                "path_params": dict(request.path_params),
                "trace": request.headers["x-trace"],
            },
        )
    )


async def echo_json(request: RouteRequest[object, object]) -> RouteResponse:
    return RouteResponse.json(
        cast(
            JSONValue,
            {
                "body": request.body,
                "raw_body": request.raw_body.decode(),
            },
        )
    )


async def bytes_handler(request: RouteRequest[object, object]) -> RouteResponse:
    return RouteResponse.bytes(b"\x00\x01raw", headers={"x-kind": "bytes"})


def test_fastapi_adapter_handles_get_query() -> None:
    client = client_for([RouteDef("GET", "/v1/items/{id}", echo_query)])

    response = client.get("/v1/items/42?q=books&empty=", headers={"x-trace": "abc"})

    assert response.status_code == 200
    assert response.json() == {
        "path": "/v1/items/42",
        "route_path": "/v1/items/{id}",
        "query": {"q": "books", "empty": ""},
        "path_params": {"id": "42"},
        "trace": "abc",
    }


def test_fastapi_adapter_handles_post_json() -> None:
    client = client_for([RouteDef("POST", "/v1/items", echo_json)])

    response = client.post("/v1/items", json={"name": "desk"})

    assert response.status_code == 200
    assert response.json() == {"body": {"name": "desk"}, "raw_body": '{"name":"desk"}'}


def test_fastapi_adapter_handles_json_suffix_content_type() -> None:
    client = client_for([RouteDef("POST", "/v1/items", echo_json)])

    response = client.post("/v1/items", content=b'{"name":"desk"}', headers={"content-type": "application/merge+json"})

    assert response.status_code == 200
    assert response.json() == {"body": {"name": "desk"}, "raw_body": '{"name":"desk"}'}


def test_fastapi_adapter_keeps_empty_json_body_empty() -> None:
    client = client_for([RouteDef("POST", "/v1/items", echo_json)])

    response = client.post("/v1/items", content=b"", headers={"content-type": "application/json"})

    assert response.status_code == 200
    assert response.json() == {"body": None, "raw_body": ""}


def test_fastapi_adapter_returns_400_for_invalid_json() -> None:
    client = client_for([RouteDef("POST", "/v1/items", echo_json)])

    response = client.post(
        "/v1/items",
        content=b"{bad",
        headers={"content-type": "Application/JSON; charset=utf-8; boundary=x"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "request body is not valid JSON"}


def test_fastapi_adapter_returns_bytes_response() -> None:
    client = client_for([RouteDef("GET", "/v1/blob", bytes_handler)])

    response = client.get("/v1/blob")

    assert response.status_code == 200
    assert response.content == b"\x00\x01raw"
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["x-kind"] == "bytes"


def test_fastapi_adapter_uses_context_provider() -> None:
    async def handler(request: RouteRequest[object, dict[str, str]]) -> RouteResponse:
        return RouteResponse.json({"name": request.context["name"]})

    async def context_provider(request: Request) -> dict[str, str]:
        return {"name": request.headers["x-name"]}

    app = FastAPI()
    app.include_router(
        build_fastapi_router(
            [RouteDef("GET", "/v1/context", handler)],
            context_provider=context_provider,
        )
    )
    client = TestClient(app)

    response = client.get("/v1/context", headers={"x-name": "ctx"})

    assert response.status_code == 200
    assert response.json() == {"name": "ctx"}


def test_fastapi_adapter_uses_auth_provider() -> None:
    async def handler(request: RouteRequest[str, dict[str, str]]) -> RouteResponse:
        return RouteResponse.json({"auth": request.auth, "name": request.context["name"]})

    router = build_fastapi_router(
        [RouteDef("GET", "/v1/ping", handler)],
        context_provider=lambda request: {"name": "ctx"},
        auth_provider=lambda route, request, context: "auth",
    )
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/v1/ping")

    assert response.status_code == 200
    assert response.json() == {"auth": "auth", "name": "ctx"}


def test_fastapi_adapter_allows_enforcer_success() -> None:
    async def handler(request: RouteRequest[str, dict[str, str]]) -> RouteResponse:
        return RouteResponse.json({"auth": request.auth})

    def auth_provider(route: RouteDef[str, dict[str, str]], request: Request, context: dict[str, str]) -> str:
        assert route.path == "/v1/allowed"
        assert request.url.path == "/v1/allowed"
        assert context["name"] == "ctx"
        return "user"

    def enforcer(route: RouteDef[str, dict[str, str]], request: Request, context: dict[str, str], auth: str) -> bool:
        assert route.method == "GET"
        assert request.url.path == "/v1/allowed"
        assert context["name"] == "ctx"
        assert auth == "user"
        return True

    app = FastAPI()
    app.include_router(
        build_fastapi_router(
            [RouteDef("GET", "/v1/allowed", handler)],
            context_provider=lambda request: {"name": "ctx"},
            auth_provider=auth_provider,
            enforcer=enforcer,
        )
    )
    client = TestClient(app)

    response = client.get("/v1/allowed")

    assert response.status_code == 200
    assert response.json() == {"auth": "user"}


def test_fastapi_adapter_denies_enforcer_false_with_403() -> None:
    async def handler(request: RouteRequest[object, object]) -> RouteResponse:
        return RouteResponse.json({"ok": True})

    app = FastAPI()
    app.include_router(
        build_fastapi_router(
            [RouteDef("GET", "/v1/denied", handler)],
            enforcer=lambda route, request, context, auth: False,
        )
    )
    client = TestClient(app)

    response = client.get("/v1/denied")

    assert response.status_code == 403
    assert response.json() == {"detail": "forbidden"}


def test_fastapi_adapter_uses_enforcer_response() -> None:
    async def handler(request: RouteRequest[object, object]) -> RouteResponse:
        return RouteResponse.json({"ok": True})

    app = FastAPI()
    app.include_router(
        build_fastapi_router(
            [RouteDef("GET", "/v1/policy", handler)],
            enforcer=lambda route, request, context, auth: RouteResponse.json({"detail": "custom"}, status=401),
        )
    )
    client = TestClient(app)

    response = client.get("/v1/policy")

    assert response.status_code == 401
    assert response.json() == {"detail": "custom"}


def test_core_import_does_not_require_fastapi() -> None:
    script = """
import importlib.abc
import sys

class BlockFastAPI(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "fastapi" or fullname.startswith("fastapi."):
            raise AssertionError("fastapi import attempted")
        return None

sys.meta_path.insert(0, BlockFastAPI())
import routedef
assert "fastapi" not in sys.modules
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
