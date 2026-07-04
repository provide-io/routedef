# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AdapterErrorKind = Literal["not_found", "forbidden", "bad_request", "body_too_large", "exception"]


@dataclass(frozen=True, slots=True)
class AdapterError:
    kind: AdapterErrorKind
    status: int
    message: str
    exception: Exception | None = None
