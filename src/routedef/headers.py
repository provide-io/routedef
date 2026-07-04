# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from collections.abc import Mapping


def normalize_headers(headers: Mapping[str, str]) -> Mapping[str, str]:
    return {name.lower(): value for name, value in headers.items()}


def get_header(headers: Mapping[str, str], name: str) -> str | None:
    normalized_name = name.lower()
    for header_name, value in headers.items():
        if header_name.lower() == normalized_name:
            return value
    return None
