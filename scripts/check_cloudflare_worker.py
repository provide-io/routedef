# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 0
STARTUP_TIMEOUT_SECONDS = 180.0
STARTUP_TIMEOUT_ENV = "ROUTEDEF_CLOUDFLARE_STARTUP_TIMEOUT"
STARTUP_ATTEMPTS = 3
STARTUP_ATTEMPTS_ENV = "ROUTEDEF_CLOUDFLARE_STARTUP_ATTEMPTS"


def subprocess_path() -> str:
    act_node_bins = tuple(sorted(Path("/opt/acttoolcache/node").glob("*/*/bin"), reverse=True))
    if act_node_bins:
        return os.pathsep.join((*(str(path) for path in act_node_bins), os.environ["PATH"]))
    return os.environ["PATH"]


def subprocess_env() -> dict[str, str]:
    return os.environ | {"MALLOC_CONF": "trust_madvise:false", "PATH": subprocess_path()}


def startup_timeout_seconds() -> float:
    value = os.environ.get(STARTUP_TIMEOUT_ENV)
    if value is None:
        return STARTUP_TIMEOUT_SECONDS
    timeout = float(value)
    if timeout <= 0:
        raise ValueError(f"{STARTUP_TIMEOUT_ENV} must be greater than zero")
    return timeout


def startup_attempts() -> int:
    value = os.environ.get(STARTUP_ATTEMPTS_ENV)
    if value is None:
        return STARTUP_ATTEMPTS
    attempts = int(value)
    if attempts <= 0:
        raise ValueError(f"{STARTUP_ATTEMPTS_ENV} must be greater than zero")
    return attempts


class WorkerStartupError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class IntegrationPaths:
    root: Path
    example_root: Path
    entrypoint: Path
    wrangler_config: Path


@dataclass(frozen=True, slots=True)
class Probe:
    method: str
    url: str
    body: bytes | None
    status: int
    payload: dict[str, object]


def integration_paths(root: Path) -> IntegrationPaths:
    example_root = root / "examples" / "cloudflare-worker"
    return IntegrationPaths(
        root=root,
        example_root=example_root,
        entrypoint=example_root / "src" / "entry.py",
        wrangler_config=example_root / "wrangler.jsonc",
    )


def probe_requests(base_url: str) -> tuple[Probe, ...]:
    return (
        Probe("GET", f"{base_url}/v1/items/7?q=desk", None, 200, {"id": "7", "q": "desk"}),
        Probe("POST", f"{base_url}/v1/items", b'{"name":"desk"}', 201, {"name": "desk"}),
        Probe("GET", f"{base_url}/missing", None, 404, {"detail": "not found"}),
    )


def choose_port(host: str, port: int) -> int:
    if port != 0:
        return port
    with socket.socket() as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def materialize_project(paths: IntegrationPaths, destination: Path) -> Path:
    project_root = destination / "cloudflare-worker"
    shutil.copytree(paths.example_root, project_root)
    shutil.copytree(paths.root / "src" / "routedef", project_root / "src" / "routedef")
    shutil.copy2(paths.root / "VERSION", project_root / "VERSION")
    return project_root


def require_executable(name: str) -> str:
    executable = shutil.which(name, path=subprocess_path())
    if executable is None:
        raise RuntimeError(f"{name} is required to run the Cloudflare Worker integration")
    return executable


def create_uv_wrapper(project_root: Path) -> dict[str, str]:
    real_uv = require_executable("uv")
    bin_dir = project_root / ".routedef-bin"
    bin_dir.mkdir()
    wrapper = bin_dir / "uv"
    wrapper.write_text(
        "\n".join(
            (
                "#!/usr/bin/env python3",
                "import subprocess",
                "import sys",
                f"REAL_UV = {real_uv!r}",
                "",
                "if len(sys.argv) > 1 and sys.argv[1] == '--version':",
                "    result = subprocess.run([REAL_UV, *sys.argv[1:]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)",
                "    lines = (",
                "        line",
                "        for line in result.stdout.splitlines()",
                "        if 'MADV_DONTNEED' not in line and 'expected behaviour if you are running under QEMU' not in line",
                "    )",
                "    output = '\\n'.join(lines)",
                "    if output:",
                "        print(output)",
                "    raise SystemExit(result.returncode)",
                "",
                "raise SystemExit(subprocess.call([REAL_UV, *sys.argv[1:]]))",
                "",
            )
        )
    )
    wrapper.chmod(0o755)
    env = subprocess_env()
    return env | {"PATH": f"{bin_dir}{os.pathsep}{env['PATH']}"}


def run_sync(project_root: Path, env: dict[str, str]) -> None:
    result = subprocess.run(  # noqa: S603
        [require_executable("uvx"), "--from", "workers-py", "pywrangler", "sync"],
        cwd=project_root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        raise RuntimeError("pywrangler sync failed")


def wait_for_worker(base_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + startup_timeout_seconds()
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise WorkerStartupError("pywrangler dev exited before the Worker became reachable")
        try:
            urllib.request.urlopen(f"{base_url}/missing", timeout=1.0).close()  # noqa: S310  # nosec B310
            return
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return
        except (OSError, TimeoutError, urllib.error.URLError):
            time.sleep(0.5)
    raise TimeoutError(f"Worker did not become reachable at {base_url}")


def run_probe(probe: Probe) -> None:
    request = urllib.request.Request(  # noqa: S310
        probe.url,
        data=probe.body,
        method=probe.method,
        headers={"content-type": "application/json"} if probe.body is not None else {},
    )
    try:
        response = urllib.request.urlopen(request, timeout=5.0)  # noqa: S310  # nosec B310
        status = response.status
        body = response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read()
    if status != probe.status:
        raise AssertionError(f"{probe.method} {probe.url} returned {status}, expected {probe.status}")
    payload = json.loads(body)
    if payload != probe.payload:
        raise AssertionError(f"{probe.method} {probe.url} returned {payload!r}, expected {probe.payload!r}")


def run_worker(project_root: Path, env: dict[str, str], *, host: str, port: int, base_url: str) -> None:
    command = [require_executable("npx"), "--yes", "wrangler@latest", "dev", "--ip", host, "--port", str(port)]
    output_path = project_root / "wrangler-dev.log"
    output_file = output_path.open("w+", encoding="utf-8")
    process = subprocess.Popen(  # noqa: S603
        command,
        cwd=project_root,
        stdout=output_file,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    failed = False
    try:
        wait_for_worker(base_url, process)
        for probe in probe_requests(base_url):
            run_probe(probe)
    except BaseException:
        failed = True
        raise
    finally:
        process.terminate()
        try:
            process.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10.0)
        output_file.flush()
        output_file.seek(0)
        output = output_file.read()
        output_file.close()
        if failed or process.returncode not in (0, -15, 143):
            print(output, file=sys.stderr)


def run_integration(root: Path, tmp_root: Path, *, host: str, port: int) -> None:
    project_root = materialize_project(integration_paths(root), tmp_root)
    port = choose_port(host, port)
    base_url = f"http://{host}:{port}"
    env = create_uv_wrapper(project_root)
    run_sync(project_root, env)
    attempts = startup_attempts()
    for attempt in range(1, attempts + 1):
        try:
            run_worker(project_root, env, host=host, port=port, base_url=base_url)
            return
        except (TimeoutError, WorkerStartupError):
            if attempt == attempts:
                raise
            print(
                f"Worker startup failed on attempt {attempt}; retrying {attempts - attempt} more time(s)",
                file=sys.stderr,
            )


def parse_args(argv: tuple[str, ...]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Cloudflare Python Worker integration fixture.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--tmp-root", type=Path, default=Path(tempfile.gettempdir()) / "routedef-cloudflare-worker")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser.parse_args(argv)


def main(argv: tuple[str, ...] | None = None) -> int:
    args = parse_args(tuple(sys.argv[1:] if argv is None else argv))
    tmp_root = args.tmp_root.resolve()
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True)
    try:
        run_integration(args.root.resolve(), tmp_root, host=args.host, port=args.port)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
