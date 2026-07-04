# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import subprocess
import sys


def parse_args(argv: tuple[str, ...]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run xenon with the repository complexity thresholds.")
    parser.add_argument("--max-absolute", default="C")
    parser.add_argument("--max-modules", default="B")
    parser.add_argument("--max-average", default="A")
    parser.add_argument("--paths", nargs="+", default=["src/routedef"])
    return parser.parse_args(argv)


def build_command(args: argparse.Namespace) -> list[str]:
    return [
        "xenon",
        "--max-absolute",
        args.max_absolute,
        "--max-modules",
        args.max_modules,
        "--max-average",
        args.max_average,
        *args.paths,
    ]


def main(argv: tuple[str, ...] | None = None) -> int:
    args = parse_args(tuple(sys.argv[1:] if argv is None else argv))
    result = subprocess.run(build_command(args), check=False)  # noqa: S603
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
