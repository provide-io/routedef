# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from collections.abc import Mapping
from typing import TypeAlias

JSONValue: TypeAlias = (
    bool | int | float | str | list["JSONValue"] | tuple["JSONValue", ...] | Mapping[str, "JSONValue"] | None
)
