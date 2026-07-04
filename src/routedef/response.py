# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

import json
from typing import Final, Literal, cast

from routedef.contracts import RouteResponse
from routedef.headers import get_header

ResponseBodyKind = Literal["empty", "bytes", "text", "json"]
CONTENT_TYPE_HEADER: Final = "content-type"  # pragma: no mutate - header lookup is case-insensitive.


def response_body_kind(response: RouteResponse) -> ResponseBodyKind:
    if response.status == 204 or response.body is None:
        return "empty"
    if isinstance(response.body, bytes):
        return "bytes"
    if isinstance(response.body, str):
        return "text"
    return "json"


def serialize_response_body(response: RouteResponse) -> bytes:
    body_kind = response_body_kind(response)
    if body_kind == "empty":
        return b""
    if body_kind == "bytes":
        return cast(bytes, response.body)  # pragma: no mutate - cast is runtime-neutral.
    if body_kind == "text":
        return cast(str, response.body).encode()  # pragma: no mutate - cast is runtime-neutral.
    return json.dumps(response.body, separators=(",", ":")).encode()


def response_content_type(response: RouteResponse) -> str | None:
    return get_header(response.headers, CONTENT_TYPE_HEADER)
