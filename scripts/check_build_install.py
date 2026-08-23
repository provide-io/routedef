# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SMOKE_CODE = """
import routedef
from routedef import RouteDef, RouteResponse

async def handler(request):
    return RouteResponse.json({"ok": True})

route = RouteDef("GET", "/v1/items/{item_id}", handler, name="item-detail")
assert route.path_for(item_id="desk/chair") == "/v1/items/desk%2Fchair"
assert routedef.__version__ == "0.2.0"
"""


def run_command(args: list[str], *, cwd: Path) -> None:
    result = subprocess.run(args, cwd=cwd, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)  # noqa: S603
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        raise RuntimeError(f"command failed: {' '.join(args)}")


def uv_command() -> str:
    executable = shutil.which("uv")
    if executable is None:
        raise RuntimeError("uv is required to run the build/install smoke test")
    return executable


def find_wheel(dist_dir: Path) -> Path:
    wheels = tuple(dist_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected exactly one built wheel, found {len(wheels)}")
    return wheels[0]


def create_venv(path: Path, *, cwd: Path) -> Path:
    run_command([uv_command(), "venv", str(path)], cwd=cwd)
    if sys.platform == "win32":
        return path / "Scripts" / "python.exe"
    return path / "bin" / "python"


def run_build_install(root: Path, tmp_root: Path) -> None:
    dist_dir = root / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    run_command([uv_command(), "build", "--wheel", "--sdist"], cwd=root)
    wheel = find_wheel(dist_dir)
    python = create_venv(tmp_root / "venv", cwd=root)
    run_command([uv_command(), "pip", "install", "--python", str(python), str(wheel)], cwd=root)
    run_command([str(python), "-c", SMOKE_CODE], cwd=root)


def parse_args(argv: tuple[str, ...]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build routedef and smoke-test the installed wheel.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--tmp-root", type=Path, default=Path(tempfile.gettempdir()) / "routedef-build-install")
    return parser.parse_args(argv)


def main(argv: tuple[str, ...] | None = None) -> int:
    args = parse_args(tuple(sys.argv[1:] if argv is None else argv))
    tmp_root = args.tmp_root.resolve()
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True)
    try:
        run_build_install(args.root.resolve(), tmp_root)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
