# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import subprocess
import sys


def build_command() -> list[str]:
    return ["reuse", "lint"]


def main() -> int:
    result = subprocess.run(build_command(), check=False)  # noqa: S603
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
