# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from dataclasses import dataclass
from re import Pattern
from urllib.parse import unquote

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


def match_path(compiled_path: CompiledPath, path: str) -> dict[str, str] | None:
    match = compiled_path.pattern.fullmatch(path)
    if match is None:
        return None
    return {name: unquote(match.group(name)) for name in compiled_path.param_names}


def _validate_path_template(path_template: str) -> None:
    if not path_template.strip():
        raise RouteConfigError("route path must not be empty")
    if not path_template.startswith("/"):
        raise RouteConfigError("route path must start with '/'")


def _validate_placeholder_name(placeholder_name: str) -> None:
    if _PLACEHOLDER_NAME_PATTERN.fullmatch(placeholder_name) is None:
        raise RouteConfigError("route path placeholder name is invalid")
