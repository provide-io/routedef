# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from typing import Any, cast

import pytest

from routedef import BadRequestBody, RouteConfigError, RouteRequest, decode_json_body, decode_text_body, parse_query


def test_parse_query_keeps_blank_values() -> None:
    assert parse_query("q=books&empty=&flag") == {"q": "books", "empty": "", "flag": ""}


def test_parse_query_accepts_bytes() -> None:
    assert parse_query(b"q=books&empty=") == {"q": "books", "empty": ""}


def test_decode_json_body_returns_json_value() -> None:
    assert decode_json_body(b'{"ok":true,"items":[1]}') == {"ok": True, "items": [1]}


def test_decode_json_body_failure_is_explicit() -> None:
    with pytest.raises(BadRequestBody) as exc_info:
        decode_json_body(b"{bad")

    assert str(exc_info.value) == "request body is not valid JSON"


def test_decode_text_body_uses_utf8_by_default() -> None:
    assert decode_text_body(b"created") == "created"


def test_decode_text_body_failure_is_explicit() -> None:
    with pytest.raises(BadRequestBody) as exc_info:
        decode_text_body(b"\xff")

    assert str(exc_info.value) == "request body is not valid text"


@pytest.mark.parametrize(
    ("method", "path", "route_path", "message"),
    [
        ("", "/v1/items", "/v1/items", "route method must not be empty"),
        ("GET", "", "/v1/items", "route path must not be empty"),
        ("GET", "bad", "/v1/items", "route path must start with '/'"),
        ("GET", "/v1/items", "bad", "route path must start with '/'"),
    ],
)
def test_route_request_rejects_invalid_routing_fields(
    method: str,
    path: str,
    route_path: str,
    message: str,
) -> None:
    with pytest.raises(RouteConfigError) as exc_info:
        RouteRequest[None, object](
            method=method,
            path=path,
            route_path=route_path,
            auth=None,
            context=object(),
        )

    assert str(exc_info.value) == message


def test_route_request_snapshots_body_container_values() -> None:
    body: dict[str, object] = {"item": ("one", {"featured"}), "tags": ["new"]}

    request = RouteRequest[None, object](
        method="post",
        path="/v1/items",
        route_path="/v1/items",
        path_params={"id": "1"},
        query={"q": "books"},
        headers={"x-trace": "abc"},
        auth=None,
        context=object(),
        body=body,
        raw_body=b"raw",
    )
    cast(Any, body["tags"]).append("sale")

    assert request.method == "POST"
    assert request.path_params == {"id": "1"}
    assert request.query == {"q": "books"}
    assert request.headers == {"x-trace": "abc"}
    assert request.body == {"item": ("one", frozenset({"featured"})), "tags": ["new"]}
    assert request.raw_body == b"raw"
