# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"


def load_script(name: str) -> ModuleType:
    script_path = SCRIPT_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_spdx_header_check_accepts_required_header(tmp_path: Path) -> None:
    script = load_script("check_spdx_headers")
    checked = tmp_path / "module.py"
    checked.write_text(
        f"{script.COPYRIGHT_LINE}\n{script.LICENSE_LINE}\n\nVALUE = 1\n",
        encoding="utf-8",
    )

    assert script.files_missing_spdx((checked,)) == ()
    assert script.main((str(tmp_path),)) == 0


def test_spdx_header_check_rejects_missing_header(tmp_path: Path) -> None:
    script = load_script("check_spdx_headers")
    checked = tmp_path / "module.py"
    checked.write_text("VALUE = 1\n", encoding="utf-8")

    assert script.files_missing_spdx((checked,)) == (checked,)
    assert script.main((str(tmp_path),)) == 1


def test_max_loc_finds_oversized_text_file(tmp_path: Path) -> None:
    script = load_script("check_max_loc")
    checked = tmp_path / "long.md"
    checked.write_text("line\n" * 3, encoding="utf-8")

    result = script.oversized_files((checked,), 2)

    assert len(result) == 1
    assert result[0].path == checked
    assert result[0].lines == 3
    assert script.main(("--max-lines", "2", "--roots", str(tmp_path))) == 1


def test_max_loc_ignores_skipped_directories(tmp_path: Path) -> None:
    script = load_script("check_max_loc")
    ignored = tmp_path / ".venv" / "long.py"
    ignored.parent.mkdir()
    ignored.write_text("line\n" * 10, encoding="utf-8")

    assert script.iter_counted_files((tmp_path,)) == ()
    assert script.main(("--max-lines", "2", "--roots", str(tmp_path))) == 0


def test_xenon_command_uses_thresholds_and_paths() -> None:
    script = load_script("check_xenon")
    args = script.parse_args(
        (
            "--max-absolute",
            "B",
            "--max-modules",
            "A",
            "--max-average",
            "A",
            "--paths",
            "src/routedef",
            "tests",
        )
    )

    assert script.build_command(args) == [
        "xenon",
        "--max-absolute",
        "B",
        "--max-modules",
        "A",
        "--max-average",
        "A",
        "src/routedef",
        "tests",
    ]


def test_license_command_runs_reuse_lint() -> None:
    script = load_script("check_licenses")

    assert script.build_command() == ["reuse", "lint"]


@pytest.mark.parametrize(
    "name",
    ("check_spdx_headers", "check_max_loc", "check_xenon", "check_licenses"),
)
def test_quality_scripts_have_required_spdx_header(name: str) -> None:
    script_path = SCRIPT_DIR / f"{name}.py"
    copyright_line = "# SPDX" + "-FileCopyrightText: Copyright (c) 2026 provide.io llc"
    license_line = "# SPDX" + "-License-Identifier: Apache-2.0"

    assert script_path.read_text(encoding="utf-8").splitlines()[:2] == [copyright_line, license_line]
