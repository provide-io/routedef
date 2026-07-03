# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

import json
from collections.abc import Mapping
from typing import Final, cast
from urllib.parse import parse_qsl

from routedef.errors import BadRequestBody
from routedef.types import JSONValue

DEFAULT_TEXT_ENCODING: Final = "utf-8"  # pragma: no mutate - UTF-8 aliases are equivalent.


def parse_query(query_string: str | bytes) -> Mapping[str, str]:
    query_text = query_string.decode() if isinstance(query_string, bytes) else query_string
    return dict(parse_qsl(query_text, keep_blank_values=True))


def decode_json_body(raw_body: bytes) -> JSONValue:
    try:
        return cast(JSONValue, json.loads(raw_body))  # pragma: no mutate - cast is runtime-neutral.
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BadRequestBody("request body is not valid JSON") from exc


def decode_text_body(raw_body: bytes, encoding: str = DEFAULT_TEXT_ENCODING) -> str:
    try:
        return raw_body.decode(encoding)
    except UnicodeDecodeError as exc:
        raise BadRequestBody("request body is not valid text") from exc
