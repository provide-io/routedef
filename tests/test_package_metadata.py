# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path


def test_version_file() -> None:
    assert Path("VERSION").read_text(encoding="utf-8").strip() == "0.1.0"


def test_package_exports() -> None:
    import routedef

    assert isinstance(routedef.__all__, tuple)
    assert routedef.__version__ == "0.1.0"
