# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "retry_command.py"


def run_retry_command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (sys.executable, str(SCRIPT_PATH), *args),
        check=False,
        capture_output=True,
        text=True,
    )


def test_retry_command_retries_configured_exit_code(tmp_path: Path) -> None:
    marker = tmp_path / "attempts.txt"
    command = (
        "from pathlib import Path; import sys; "
        f"path = Path({str(marker)!r}); "
        "attempts = int(path.read_text() or '0') if path.exists() else 0; "
        "path.write_text(str(attempts + 1)); "
        "raise SystemExit(7 if attempts == 0 else 0)"
    )

    result = run_retry_command("--attempts", "2", "--exit-code", "7", "--", sys.executable, "-c", command)

    assert result.returncode == 0
    assert marker.read_text() == "2"
    assert "retrying 1 more time" in result.stderr


def test_retry_command_preserves_unconfigured_failure() -> None:
    result = run_retry_command("--attempts", "2", "--exit-code", "7", "--", sys.executable, "-c", "raise SystemExit(8)")

    assert result.returncode == 8
    assert "retrying" not in result.stderr
