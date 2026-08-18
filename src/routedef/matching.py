# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from re import Pattern
from urllib.parse import quote, unquote

from routedef.errors import RouteConfigError

_BRACE_PATTERN = re.compile(r"[{}]")
_PLACEHOLDER_NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


@dataclass(frozen=True, slots=True)
class CompiledPath:
    path_template: str
    pattern: Pattern[str]
    param_names: tuple[str, ...]


def compile_path_template(path_template: str) -> CompiledPath:
    _validate_path_template(path_template)
    pattern_parts = ["^"]
    param_names: list[str] = []
    position = 0

    for brace_match in _BRACE_PATTERN.finditer(path_template):
        brace_position = brace_match.start()
        if brace_position < position:
            continue
        if brace_match.group() == "}":  # pragma: no mutate - alternate path raises the same config error.
            raise RouteConfigError("route path placeholder name is invalid")

        pattern_parts.append(re.escape(path_template[position:brace_position]))
        placeholder_end = path_template.find("}", brace_position + 1)  # pragma: no mutate - equivalent search start.
        if placeholder_end == -1:
            raise RouteConfigError("route path placeholder name is invalid")

        placeholder_name = path_template[brace_position + 1 : placeholder_end]
        _validate_placeholder_name(placeholder_name)
        if placeholder_name in param_names:
            raise RouteConfigError(f"route path placeholder {placeholder_name!r} is duplicated")

        param_names.append(placeholder_name)
        pattern_parts.append(f"(?P<{placeholder_name}>[^/]+)")
        position = placeholder_end + 1

    pattern_parts.append(re.escape(path_template[position:]))
    pattern_parts.append("$")
    return CompiledPath(
        path_template=path_template, pattern=re.compile("".join(pattern_parts)), param_names=tuple(param_names)
    )


def match_path(
    compiled_path: CompiledPath, path: str, *, strict_segments: bool = False
) -> dict[str, str] | None:
    """Match ``path`` and return its decoded params, or None if it does not match.

    Matching runs against the still-percent-encoded path, so ``(?P<name>[^/]+)``
    enforces "one path segment" on the wire. Decoding happens AFTER that check,
    which means a param can arrive carrying characters that would have changed
    the routing decision had they been present before the match: ``%2F`` decodes
    to ``/``, ``%3F`` to ``?``, ``%23`` to ``#``. The pattern guarantees one
    segment; the value handed back does not carry that guarantee.

    That is deliberate and must stay the default -- an identifier may legitimately
    contain a slash (an OIDC ``sub``, an object key), and refusing to decode one
    would make those resources unaddressable.

    It is a hazard only when a caller re-emits the decoded value into a URL. The
    safe pairing is `expand_path_template`, which quotes with ``safe=""`` and so
    puts the value back exactly where it came from. Anything that interpolates a
    param into an upstream path with an f-string has stepped outside it.

    ``strict_segments`` is for routes whose params are opaque ids that may never
    contain a slash -- a proxy forwarding to an upstream service, typically. With
    it, a param that decodes to something spanning segments is simply not a
    match, and the request falls through to a 404 rather than reaching a handler
    holding a value its route never promised. That mirrors the rule
    `expand_path_template` already enforces in the outbound direction.
    """
    match = compiled_path.pattern.fullmatch(path)
    if match is None:
        return None
    params: dict[str, str] = {}
    for name in compiled_path.param_names:
        value = unquote(match.group(name))
        if strict_segments and "/" in value:
            return None
        params[name] = value
    return params


def expand_path_template(path_template: str, path_params: Mapping[str, object], *, encode: bool = True) -> str:
    compiled_path = compile_path_template(path_template)
    expected = set(compiled_path.param_names)
    provided = set(path_params)
    missing = expected - provided
    if missing:
        raise RouteConfigError(f"missing path params: {', '.join(sorted(missing))}")
    unknown = provided - expected
    if unknown:
        raise RouteConfigError(f"unknown path params: {', '.join(sorted(unknown))}")

    expanded = path_template
    for name in compiled_path.param_names:
        value = str(path_params[name])
        if encode:
            value = quote(value, safe="")  # pragma: no mutate - alphanumeric safe mutations are equivalent.
        elif "/" in value:
            raise RouteConfigError(f"path param {name!r} must not contain '/'")
        expanded = expanded.replace(f"{{{name}}}", value)
    return expanded


def _validate_path_template(path_template: str) -> None:
    if not path_template.strip():
        raise RouteConfigError("route path must not be empty")
    if not path_template.startswith("/"):
        raise RouteConfigError("route path must start with '/'")


def _validate_placeholder_name(placeholder_name: str) -> None:
    if _PLACEHOLDER_NAME_PATTERN.fullmatch(placeholder_name) is None:
        raise RouteConfigError("route path placeholder name is invalid")
