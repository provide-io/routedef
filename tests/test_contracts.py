# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

import asyncio
from collections.abc import Mapping
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from typing import Any, cast

import pytest
from pytest import MonkeyPatch

from routedef import RouteConfigError, RouteDef, RouteRequest, RouteResponse


async def echo(request: RouteRequest[str, dict[str, object]]) -> RouteResponse:
    return RouteResponse.json({"auth": request.auth, "path": request.path})


def test_route_method_normalizes_to_uppercase() -> None:
    route = RouteDef("get", "/v1/items/{id}", echo)

    assert route.method == "GET"


@pytest.mark.parametrize("method", ["", "   "])
def test_route_rejects_empty_method(method: str) -> None:
    with pytest.raises(RouteConfigError, match="method"):
        RouteDef(method, "/v1/items/{id}", echo)


@pytest.mark.parametrize("path", ["", "   ", "bad"])
def test_route_rejects_invalid_path(path: str) -> None:
    with pytest.raises(RouteConfigError, match="path"):
        RouteDef("GET", path, echo)


def test_route_is_immutable_and_metadata_is_read_only() -> None:
    metadata_source = {"roles": ("admin",), "retry": True}
    route = RouteDef("GET", "/v1/items/{id}", echo, metadata=metadata_source)
    metadata_source["retry"] = False

    with pytest.raises(AttributeError):
        cast(Any, route).method = "POST"

    with pytest.raises(TypeError):
        cast(Any, route.metadata)["retry"] = False

    assert route.metadata["roles"] == ("admin",)
    assert route.metadata["retry"] is True


def test_request_is_immutable_and_mapping_fields_are_read_only() -> None:
    path_params = {"id": "123"}
    query = {"q": "books"}
    headers = {"x-trace": "abc"}
    context = {"db": object()}
    request = RouteRequest(
        method="post",
        path="/v1/items/123",
        route_path="/v1/items/{id}",
        path_params=path_params,
        query=query,
        headers=headers,
        body={"name": "desk"},
        raw_body=b'{"name":"desk"}',
        auth="user-1",
        context=context,
    )
    path_params["id"] = "999"
    query["q"] = "tables"
    headers["x-trace"] = "def"
    context["db"] = object()

    with pytest.raises(AttributeError):
        cast(Any, request).path = "/changed"

    for field in (request.path_params, request.query, request.headers, request.context):
        assert isinstance(field, Mapping)
        with pytest.raises(TypeError):
            cast(Any, field)["new"] = "value"

    assert request.method == "POST"
    assert request.path_params == {"id": "123"}
    assert request.query == {"q": "books"}
    assert request.headers == {"x-trace": "abc"}
    assert tuple(request.context) == ("db",)


def test_request_preserves_non_mapping_context() -> None:
    context = object()
    request = RouteRequest[None, object](
        method="GET",
        path="/v1/items",
        route_path="/v1/items",
        auth=None,
        context=context,
    )

    assert request.context is context


def test_response_is_immutable_and_headers_are_read_only() -> None:
    response = RouteResponse.text("ok", headers={"x-trace": "abc"})

    with pytest.raises(AttributeError):
        cast(Any, response).status = 500

    with pytest.raises(TypeError):
        cast(Any, response.headers)["x-trace"] = "def"

    assert response.headers == {"content-type": "text/plain; charset=utf-8", "x-trace": "abc"}


def test_response_constructors_create_expected_state() -> None:
    json_response = RouteResponse.json({"ok": True}, status=201, headers={"cache-control": "no-store"})
    text_response = RouteResponse.text("created", status=202)
    bytes_response = RouteResponse.bytes(b"raw", status=203, content_type="application/octet-stream")
    empty_response = RouteResponse.empty(status=204, headers={"x-empty": "1"})

    assert json_response.status == 201
    assert json_response.body == {"ok": True}
    assert json_response.headers == {"cache-control": "no-store", "content-type": "application/json"}
    assert text_response.status == 202
    assert text_response.body == "created"
    assert text_response.headers == {"content-type": "text/plain; charset=utf-8"}
    assert bytes_response.status == 203
    assert bytes_response.body == b"raw"
    assert bytes_response.headers == {"content-type": "application/octet-stream"}
    assert empty_response.status == 204
    assert empty_response.body is None
    assert empty_response.headers == {"x-empty": "1"}


def test_route_handler_protocol_use() -> None:
    route = RouteDef("GET", "/v1/echo", echo)
    context: dict[str, object] = {"request_id": "abc"}
    request = RouteRequest(
        method="GET",
        path="/v1/echo",
        route_path="/v1/echo",
        auth="token",
        context=context,
    )

    async def call_handler() -> RouteResponse:
        return await route.handler(request)

    response: RouteResponse = asyncio.run(call_handler())

    assert response.body == {"auth": "token", "path": "/v1/echo"}


def test_version_fallback_remains_covered_for_focused_contract_run(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    import routedef.version as version_module

    version_file = tmp_path / "VERSION"
    version_file.write_text("9.8.7\n", encoding="utf-8")

    def missing_metadata(_package_name: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr(version_module, "_metadata_version", missing_metadata)
    monkeypatch.setattr(version_module, "_VERSION_FILE", version_file)

    assert version_module.load_version() == "9.8.7"
