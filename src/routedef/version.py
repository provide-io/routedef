# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _metadata_version
from pathlib import Path
from typing import Final

_PACKAGE_NAME: Final = "routedef"
_FALLBACK_VERSION: Final = "0.1.0"
_VERSION_FILE: Final = Path(__file__).resolve().parents[2] / "VERSION"


def load_version() -> str:
    try:
        return _metadata_version(_PACKAGE_NAME)
    except PackageNotFoundError:
        if not _VERSION_FILE.exists():
            return _FALLBACK_VERSION
        return _VERSION_FILE.read_text(encoding="utf-8").strip()  # pragma: no mutate - UTF-8 aliases equivalent.


__version__ = load_version()
