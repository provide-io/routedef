# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Mapping
from importlib.metadata import PackageNotFoundError
from typing import Any, cast

import pytest

from routedef import (
    RouteConfigError,
    RouteDef,
    RouteRequest,
    RouteResponse,
    response_body_kind,
    response_content_type,
    serialize_response_body,
)
from routedef.version import load_version


async def handler(request: RouteRequest[object, object]) -> RouteResponse:
    return RouteResponse.json({"ok": True})


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


def test_route_def_normalizes_and_snapshots_metadata() -> None:
    metadata: dict[str, object] = {"policy": {"roles": ["admin"], "flags": {"write"}}}

    route: RouteDef[object, object] = RouteDef(" get ", "/v1/items", handler, metadata=metadata)
    cast(Any, metadata["policy"])["roles"].append("sysop")
    cast(Any, metadata["policy"])["flags"].add("delete")

    policy = cast(Mapping[str, object], route.metadata["policy"])
    assert route.method == "GET"
    assert route.path == "/v1/items"
    assert policy["roles"] == ("admin",)
    assert policy["flags"] == frozenset({"write"})


@pytest.mark.parametrize(
    ("method", "path", "message"),
    [
        ("", "/v1/items", "route method must not be empty"),
        ("GET", "", "route path must not be empty"),
        ("GET", "bad", "route path must start with '/'"),
    ],
)
def test_route_def_rejects_invalid_fields(method: str, path: str, message: str) -> None:
    with pytest.raises(RouteConfigError) as exc_info:
        RouteDef(method, path, handler)

    assert str(exc_info.value) == message


def test_response_content_type_preserves_explicit_header() -> None:
    response = RouteResponse.json({"ok": True}, headers={"Content-Type": "application/problem+json"})

    assert response.headers == {"content-type": "application/problem+json"}
    assert response_content_type(response) == "application/problem+json"


def test_empty_response_keeps_headers_without_content_type() -> None:
    response = RouteResponse.empty(headers={"x-empty": "1"})

    assert response.headers == {"x-empty": "1"}
    assert response_content_type(response) is None


def test_load_version_falls_back_to_version_file(monkeypatch: pytest.MonkeyPatch) -> None:
    import routedef.version as version_module

    def raise_package_not_found(_: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr(version_module, "_metadata_version", raise_package_not_found)

    assert load_version() == "0.1.0"
