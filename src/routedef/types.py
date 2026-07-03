# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Mapping
from typing import TypeAlias

JSONValue: TypeAlias = (
    None | bool | int | float | str | list["JSONValue"] | tuple["JSONValue", ...] | Mapping[str, "JSONValue"]
)
