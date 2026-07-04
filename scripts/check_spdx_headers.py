# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import sys
from pathlib import Path

COPYRIGHT_LINE = "# SPDX" + "-FileCopyrightText: Copyright (c) 2026 provide.io llc"
LICENSE_LINE = "# SPDX" + "-License-Identifier: MIT"
EXPECTED_HEADER = (COPYRIGHT_LINE, LICENSE_LINE)
DEFAULT_ROOTS = ("src", "tests", "scripts")
SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".mutmut-cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "htmlcov",
    "mutants",
}


def iter_python_files(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file() and root.suffix == ".py":
            files.append(root)
            continue
        for path in root.rglob("*.py"):
            if not any(part in SKIP_DIRS for part in path.parts):
                files.append(path)
    return tuple(sorted(files))


def header_lines(path: Path) -> tuple[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    first = lines[0] if lines else ""
    second = lines[1] if len(lines) > 1 else ""
    return first, second


def files_missing_spdx(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    return tuple(path for path in paths if header_lines(path) != EXPECTED_HEADER)


def parse_args(argv: tuple[str, ...]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Require Provide.io SPDX headers on Python files.")
    parser.add_argument("roots", nargs="*", default=DEFAULT_ROOTS, help="Files or directories to scan.")
    return parser.parse_args(argv)


def main(argv: tuple[str, ...] | None = None) -> int:
    args = parse_args(tuple(sys.argv[1:] if argv is None else argv))
    roots = tuple(Path(root) for root in args.roots)
    missing = files_missing_spdx(iter_python_files(roots))
    if not missing:
        return 0

    print("Python files missing the required SPDX header:")
    for path in missing:
        print(f"  {path}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
