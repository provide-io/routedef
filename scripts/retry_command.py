# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import subprocess
import sys

DEFAULT_ATTEMPTS = 3
DEFAULT_RETRY_EXIT_CODES = (139,)


def parse_args(argv: tuple[str, ...]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retry a command for known transient process exits.")
    parser.add_argument("--attempts", type=int, default=DEFAULT_ATTEMPTS)
    parser.add_argument(
        "--exit-code",
        type=int,
        action="append",
        dest="exit_codes",
        default=[],
        help="Exit code to retry; may be provided more than once.",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.attempts <= 0:
        parser.error("--attempts must be greater than zero")
    if not args.command:
        parser.error("command is required")
    if args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("command is required")
    return args


def main(argv: tuple[str, ...] | None = None) -> int:
    args = parse_args(tuple(sys.argv[1:] if argv is None else argv))
    retry_exit_codes = frozenset((*DEFAULT_RETRY_EXIT_CODES, *args.exit_codes))
    result: subprocess.CompletedProcess[bytes] = subprocess.CompletedProcess(args.command, 1)
    for attempt in range(1, args.attempts + 1):
        result = subprocess.run(args.command, check=False)  # noqa: S603
        if result.returncode not in retry_exit_codes or attempt == args.attempts:
            return result.returncode
        print(
            f"{args.command[0]} exited {result.returncode}; retrying {args.attempts - attempt} more time(s)",
            file=sys.stderr,
        )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
