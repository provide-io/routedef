# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "check_build_install.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_build_install", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_build_install"] = module
    spec.loader.exec_module(module)
    return module


def test_build_install_script_finds_single_wheel(tmp_path: Path) -> None:
    script = load_script()
    wheel = tmp_path / "routedef-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel")

    assert script.find_wheel(tmp_path) == wheel


def test_build_install_script_rejects_missing_wheel(tmp_path: Path) -> None:
    script = load_script()

    try:
        script.find_wheel(tmp_path)
    except RuntimeError as exc:
        assert str(exc) == "expected exactly one built wheel, found 0"
    else:
        raise AssertionError("missing wheel was accepted")


def test_build_install_script_smoke_code_exercises_public_api() -> None:
    script = load_script()

    assert "RouteDef" in script.SMOKE_CODE
    assert "path_for" in script.SMOKE_CODE
    assert "__version__" in script.SMOKE_CODE
