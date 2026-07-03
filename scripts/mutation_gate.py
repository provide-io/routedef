# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import subprocess
import sys


def surviving_mutants(output: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in output.splitlines() if line.strip().endswith(": survived"))


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)  # noqa: S603


def main() -> int:
    run_result = run_command(["mutmut", "run"])
    print(run_result.stdout, end="")
    if run_result.returncode != 0:
        return run_result.returncode

    results = run_command(["mutmut", "results"])
    print(results.stdout, end="")
    if results.returncode != 0:
        return results.returncode

    survivors = surviving_mutants(results.stdout)
    if survivors:
        print("Surviving mutants detected:")
        for survivor in survivors:
            print(f"  {survivor}")
        return 1

    print("No surviving mutants detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
