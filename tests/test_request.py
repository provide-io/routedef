# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

import pytest

from routedef import BadRequestBody, decode_json_body, decode_text_body, parse_query


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
