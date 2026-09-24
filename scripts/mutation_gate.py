# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from __future__ import annotations

import subprocess
import sys

ALLOWED_SURVIVORS = {
    # FastAPI treats include_in_schema=None the same as include_in_schema=False
    # for the generated catch-all route. Tests assert the route is absent from
    # OpenAPI, so this mutant is equivalent rather than under-tested behavior.
    "routedef.adapters.fastapi.x_build_fastapi_router__mutmut_148: survived",
    # RouteResponse.body already defaults to None, so dropping the explicit
    # body=None from RouteResponse.empty builds the same response.
    "routedef.contracts.xǁRouteResponseǁempty__mutmut_5: survived",
}


def surviving_mutants(output: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in output.splitlines() if line.strip().endswith(": survived"))


def disallowed_survivors(output: str) -> tuple[str, ...]:
    return tuple(survivor for survivor in surviving_mutants(output) if survivor not in ALLOWED_SURVIVORS)


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)  # noqa: S603


def main() -> int:
    run_result = run_command(["mutmut", "run"])
    print(run_result.stdout, end="")

    results = run_command(["mutmut", "results"])
    print(results.stdout, end="")

    survivors = disallowed_survivors(results.stdout)
    if survivors:
        print("Surviving mutants detected:")
        for survivor in survivors:
            print(f"  {survivor}")
        return 1

    if results.returncode != 0 and not surviving_mutants(results.stdout):
        return results.returncode

    if run_result.returncode != 0 and not surviving_mutants(results.stdout):
        return run_result.returncode

    print("No surviving mutants detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
