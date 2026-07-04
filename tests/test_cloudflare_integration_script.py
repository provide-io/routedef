# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from pytest import MonkeyPatch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "check_cloudflare_worker.py"
EXAMPLE_ROOT = ROOT / "examples" / "cloudflare-worker"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_cloudflare_worker", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_cloudflare_worker"] = module
    spec.loader.exec_module(module)
    return module


def test_cloudflare_worker_example_files_exist() -> None:
    assert (EXAMPLE_ROOT / "pyproject.toml").is_file()
    assert (EXAMPLE_ROOT / "wrangler.jsonc").is_file()
    assert (EXAMPLE_ROOT / "src" / "entry.py").is_file()


def test_cloudflare_worker_script_builds_expected_paths() -> None:
    script = load_script()

    paths = script.integration_paths(ROOT)

    assert paths.example_root == EXAMPLE_ROOT
    assert paths.entrypoint == EXAMPLE_ROOT / "src" / "entry.py"
    assert paths.wrangler_config == EXAMPLE_ROOT / "wrangler.jsonc"


def test_cloudflare_worker_script_uses_expected_probe_requests() -> None:
    script = load_script()

    assert script.probe_requests("http://127.0.0.1:8787") == (
        script.Probe("GET", "http://127.0.0.1:8787/v1/items/7?q=desk", None, 200, {"id": "7", "q": "desk"}),
        script.Probe("POST", "http://127.0.0.1:8787/v1/items", b'{"name":"desk"}', 201, {"name": "desk"}),
        script.Probe("GET", "http://127.0.0.1:8787/missing", None, 404, {"detail": "not found"}),
    )


def test_cloudflare_worker_script_startup_timeout_default(monkeypatch: MonkeyPatch) -> None:
    script = load_script()
    monkeypatch.delenv(script.STARTUP_TIMEOUT_ENV, raising=False)

    assert script.startup_timeout_seconds() == 180.0


def test_cloudflare_worker_script_startup_timeout_env(monkeypatch: MonkeyPatch) -> None:
    script = load_script()
    monkeypatch.setenv(script.STARTUP_TIMEOUT_ENV, "12.5")

    assert script.startup_timeout_seconds() == 12.5


def test_cloudflare_worker_script_rejects_nonpositive_timeout(monkeypatch: MonkeyPatch) -> None:
    script = load_script()
    monkeypatch.setenv(script.STARTUP_TIMEOUT_ENV, "0")

    with pytest.raises(ValueError, match=script.STARTUP_TIMEOUT_ENV):
        script.startup_timeout_seconds()


def test_cloudflare_worker_script_startup_attempts_default(monkeypatch: MonkeyPatch) -> None:
    script = load_script()
    monkeypatch.delenv(script.STARTUP_ATTEMPTS_ENV, raising=False)

    assert script.startup_attempts() == 3


def test_cloudflare_worker_script_startup_attempts_env(monkeypatch: MonkeyPatch) -> None:
    script = load_script()
    monkeypatch.setenv(script.STARTUP_ATTEMPTS_ENV, "2")

    assert script.startup_attempts() == 2


def test_cloudflare_worker_script_rejects_nonpositive_attempts(monkeypatch: MonkeyPatch) -> None:
    script = load_script()
    monkeypatch.setenv(script.STARTUP_ATTEMPTS_ENV, "0")

    with pytest.raises(ValueError, match=script.STARTUP_ATTEMPTS_ENV):
        script.startup_attempts()


def test_cloudflare_worker_script_retries_startup_failures(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    script = load_script()
    project_root = tmp_path / "project"
    project_root.mkdir()
    attempts = 0

    monkeypatch.setenv(script.STARTUP_ATTEMPTS_ENV, "2")
    monkeypatch.setattr(script, "materialize_project", lambda *_args: project_root)
    monkeypatch.setattr(script, "choose_port", lambda _host, _port: 8787)
    monkeypatch.setattr(script, "create_uv_wrapper", lambda _project_root: {})
    monkeypatch.setattr(script, "run_sync", lambda _project_root, _env: None)

    def run_worker(*_args: Any, **_kwargs: Any) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise script.WorkerStartupError("not reachable")

    monkeypatch.setattr(script, "run_worker", run_worker)

    script.run_integration(ROOT, tmp_path, host="127.0.0.1", port=0)

    assert attempts == 2
