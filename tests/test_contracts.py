# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest

from routedef import JSONValue, RouteConfigError, RouteDef, RouteRequest, RouteResponse


async def echo(request: RouteRequest[str, dict[str, object]]) -> RouteResponse:
    return RouteResponse.json({"auth": request.auth, "path": request.path})


def test_route_method_normalizes_to_uppercase() -> None:
    route = RouteDef("get", "/v1/items/{id}", echo)

    assert route.method == "GET"
    assert route.name is None


@pytest.mark.parametrize("method", ["", "   "])
def test_route_rejects_empty_method(method: str) -> None:
    with pytest.raises(RouteConfigError) as exc_info:
        RouteDef(method, "/v1/items/{id}", echo)

    assert str(exc_info.value) == "route method must not be empty"


@pytest.mark.parametrize("path", ["", "   "])
def test_route_rejects_empty_path(path: str) -> None:
    with pytest.raises(RouteConfigError) as exc_info:
        RouteDef("GET", path, echo)

    assert str(exc_info.value) == "route path must not be empty"


def test_route_rejects_path_without_leading_slash() -> None:
    with pytest.raises(RouteConfigError) as exc_info:
        RouteDef("GET", "bad", echo)

    assert str(exc_info.value) == "route path must start with '/'"


def test_route_rejects_empty_name() -> None:
    with pytest.raises(RouteConfigError) as exc_info:
        RouteDef("GET", "/v1/items/{id}", echo, name=" ")

    assert str(exc_info.value) == "route name must not be empty"


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


def test_route_path_for_expands_encoded_params() -> None:
    route = RouteDef("GET", "/v1/accounts/{account_id}/items/{item_id}", echo, name="item-detail")

    assert route.path_for(account_id="acct 1", item_id="desk/chair") == "/v1/accounts/acct%201/items/desk%2Fchair"


def test_route_path_for_rejects_missing_params() -> None:
    route = RouteDef("GET", "/v1/items/{id}", echo)

    with pytest.raises(RouteConfigError, match="missing path params"):
        route.path_for()


def test_route_path_for_rejects_unknown_params() -> None:
    route = RouteDef("GET", "/v1/items/{id}", echo)

    with pytest.raises(RouteConfigError, match="unknown path params"):
        route.path_for(id="7", extra="ignored")


def test_route_path_for_rejects_slashes_when_not_encoded() -> None:
    route = RouteDef("GET", "/v1/items/{id}", echo)

    with pytest.raises(RouteConfigError, match="must not contain '/'"):
        route.path_for(encode=False, id="desk/chair")


def test_route_metadata_nested_values_are_deeply_snapshotted() -> None:
    metadata_source: dict[str, object] = {
        "policy": {"roles": ["admin"], "flags": {"write"}},
        "order": ("first", "second"),
    }
    route = RouteDef("GET", "/v1/items/{id}", echo, metadata=metadata_source)
    cast(Any, metadata_source["policy"])["roles"].append("sysop")
    cast(Any, metadata_source["policy"])["flags"].add("delete")

    policy = cast(Mapping[str, object], route.metadata["policy"])
    with pytest.raises(TypeError):
        cast(Any, policy)["roles"] = ("guest",)
    with pytest.raises(AttributeError):
        cast(Any, policy["roles"]).append("guest")
    with pytest.raises(AttributeError):
        cast(Any, policy["flags"]).add("read")

    assert policy["roles"] == ("admin",)
    assert policy["flags"] == frozenset({"write"})
    assert route.metadata["order"] == ("first", "second")


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
    original_context = request.context
    context["db"] = object()

    with pytest.raises(AttributeError):
        cast(Any, request).path = "/changed"

    for field in (request.path_params, request.query, request.headers):
        assert isinstance(field, Mapping)
        with pytest.raises(TypeError):
            cast(Any, field)["new"] = "value"

    assert request.method == "POST"
    assert request.path_params == {"id": "123"}
    assert request.query == {"q": "books"}
    assert request.headers == {"x-trace": "abc"}
    assert request.context is original_context


def test_request_preserves_dict_context_runtime_type() -> None:
    context: dict[str, object] = {"db": object()}
    request = RouteRequest[str, dict[str, object]](
        method="GET",
        path="/v1/items",
        route_path="/v1/items",
        auth="user-1",
        context=context,
    )
    context["request_id"] = "abc"

    assert request.context is context
    assert isinstance(request.context, dict)
    assert request.context.get("request_id") == "abc"


def test_request_body_nested_values_are_deeply_snapshotted() -> None:
    body: dict[str, object] = {"item": {"tags": ["new"], "flags": {"featured"}}}
    request = RouteRequest[None, object](
        method="POST",
        path="/v1/items",
        route_path="/v1/items",
        auth=None,
        context=object(),
        body=body,
    )
    cast(Any, body["item"])["tags"].append("sale")
    cast(Any, body["item"])["flags"].add("archived")

    item = cast(dict[str, object], cast(dict[str, object], request.body)["item"])

    assert item["tags"] == ["new"]
    assert item["flags"] == frozenset({"featured"})


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


def test_response_content_type_is_case_insensitive() -> None:
    response = RouteResponse.json({"detail": "missing"}, headers={"Content-Type": "application/problem+json"})

    assert response.headers == {"content-type": "application/problem+json"}
    assert len(response.headers) == 1


def test_json_constructor_accepts_json_value() -> None:
    body: JSONValue = {"ok": True, "items": [{"id": 1}], "next": None}
    response = RouteResponse.json(body)
    response_body = cast(dict[str, object], response.body)

    assert response_body["ok"] is True
    assert response_body["items"] == [{"id": 1}]
    assert response_body["next"] is None


def test_json_response_body_is_serializable() -> None:
    response = RouteResponse.json({"ok": True})

    assert json.dumps(response.body) == '{"ok": true}'


def test_json_response_body_is_copied_from_caller_input() -> None:
    body: dict[str, JSONValue] = {"items": [{"id": 1}]}
    response = RouteResponse.json(body)
    body["items"] = [{"id": 2}]

    assert response.body == {"items": [{"id": 1}]}


def test_json_response_body_preserves_serializable_tuple_snapshot() -> None:
    response = RouteResponse.json(("ok", {"id": 1}))

    assert response.body == ("ok", {"id": 1})
    assert json.dumps(response.body) == '["ok", {"id": 1}]'


def test_json_response_rejects_bytes_in_type_checkers(tmp_path: Path) -> None:
    snippet = tmp_path / "bytes_json.py"
    snippet.write_text(
        "from routedef import RouteResponse\n\nRouteResponse.json(b'not-json')\n",
        encoding="utf-8",
    )

    mypy_result = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", str(snippet)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    ty_result = subprocess.run(
        [sys.executable, "-m", "ty", "check", str(snippet)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    assert mypy_result.returncode != 0, mypy_result.stdout
    assert "bytes" in mypy_result.stdout
    assert ty_result.returncode != 0, ty_result.stdout
    assert "bytes" in ty_result.stdout


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
