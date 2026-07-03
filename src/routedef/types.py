# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Mapping, Sequence
from typing import TypeAlias

JSONValue: TypeAlias = None | bool | int | float | str | Sequence["JSONValue"] | Mapping[str, "JSONValue"]
