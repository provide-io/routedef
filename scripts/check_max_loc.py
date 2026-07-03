# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ROOTS = (".",)
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


@dataclass(frozen=True, slots=True)
class LineCount:
    path: Path
    lines: int


def is_counted_file(path: Path) -> bool:
    return path.is_file() and not any(part in SKIP_DIRS for part in path.parts)


def git_tracked_files(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    args = ["git", "ls-files", "--", *(str(root) for root in roots)]
    result = subprocess.run(args, check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)  # noqa: S603
    if result.returncode != 0:
        return ()
    return tuple(Path(line) for line in result.stdout.splitlines() if line)


def iter_counted_files(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    tracked = git_tracked_files(roots)
    if tracked:
        return tuple(sorted(path for path in tracked if is_counted_file(path)))

    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        if is_counted_file(root):
            files.append(root)
            continue
        if root.is_dir():
            files.extend(path for path in root.rglob("*") if is_counted_file(path))
    return tuple(sorted(files))


def count_lines(path: Path) -> int:
    with path.open(encoding="utf-8") as file:
        return sum(1 for _ in file)


def oversized_files(paths: tuple[Path, ...], max_lines: int) -> tuple[LineCount, ...]:
    return tuple(LineCount(path, count_lines(path)) for path in paths if count_lines(path) > max_lines)


def parse_args(argv: tuple[str, ...]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail if project files exceed the configured line count.")
    parser.add_argument("--max-lines", type=int, default=500)
    parser.add_argument("--roots", nargs="+", default=DEFAULT_ROOTS)
    return parser.parse_args(argv)


def main(argv: tuple[str, ...] | None = None) -> int:
    args = parse_args(tuple(sys.argv[1:] if argv is None else argv))
    bad = oversized_files(iter_counted_files(tuple(Path(root) for root in args.roots)), args.max_lines)
    if not bad:
        return 0

    print(f"Files over {args.max_lines} lines:")
    for item in bad:
        print(f"  {item.path}: {item.lines}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
