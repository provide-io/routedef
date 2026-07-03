# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from routedef import get_header, normalize_headers


def test_normalize_headers_lowercases_header_names() -> None:
    assert normalize_headers({"Content-Type": "application/json"}) == {"content-type": "application/json"}


def test_get_header_uses_case_insensitive_lookup() -> None:
    headers = {"Content-Type": "application/json", "X-Trace": "abc"}

    assert get_header(headers, "content-type") == "application/json"
    assert get_header(headers, "CONTENT-TYPE") == "application/json"
    assert get_header(headers, "x-trace") == "abc"


def test_get_header_returns_none_when_missing() -> None:
    assert get_header({"content-type": "text/plain"}, "accept") is None
