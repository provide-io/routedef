# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

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
