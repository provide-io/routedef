# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from routedef import (
    RouteResponse,
    response_body_kind,
    response_content_type,
    serialize_response_body,
)


def test_response_body_kind_detects_bytes() -> None:
    assert response_body_kind(RouteResponse.bytes(b"x")) == "bytes"


def test_response_body_kind_detects_empty_status_204() -> None:
    assert response_body_kind(RouteResponse.empty(204)) == "empty"


def test_serialize_response_body_passes_bytes_through() -> None:
    body = b"raw"

    assert serialize_response_body(RouteResponse.bytes(body)) is body


def test_text_response_serializes_utf8_and_reports_content_type() -> None:
    response = RouteResponse.text("created")

    assert response_body_kind(response) == "text"
    assert serialize_response_body(response) == b"created"
    assert response_content_type(response) == "text/plain; charset=utf-8"


def test_json_response_serializes_with_compact_separators() -> None:
    response = RouteResponse.json({"ok": True, "items": [1]})

    assert response_body_kind(response) == "json"
    assert serialize_response_body(response) == b'{"ok":true,"items":[1]}'
    assert response_content_type(response) == "application/json"


def test_empty_status_204_serializes_to_empty_bytes() -> None:
    response = RouteResponse.empty(status=204)

    assert response_body_kind(response) == "empty"
    assert serialize_response_body(response) == b""


def test_status_204_overrides_non_empty_body() -> None:
    response = RouteResponse(status=204, body=b"must not be sent")

    assert response_body_kind(response) == "empty"
    assert serialize_response_body(response) == b""


def test_response_content_type_preserves_explicit_header() -> None:
    response = RouteResponse.json({"ok": True}, headers={"Content-Type": "application/problem+json"})

    assert response.headers == {"content-type": "application/problem+json"}
    assert response_content_type(response) == "application/problem+json"


def test_empty_response_keeps_headers_without_content_type() -> None:
    response = RouteResponse.empty(headers={"x-empty": "1"})

    assert response.headers == {"x-empty": "1"}
    assert response_content_type(response) is None
