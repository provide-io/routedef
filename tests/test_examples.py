# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import cast

from routedef import RouteResponse

ROOT = Path(__file__).resolve().parents[1]


def _load_example(path: str) -> ModuleType:
    example_path = ROOT / path
    module_name = f"routedef_example_{example_path.parent.name}_{example_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, example_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_metadata_enforcer_example_runs() -> None:
    module = _load_example("examples/policy/metadata_enforcer.py")

    allowed, denied = cast(tuple[RouteResponse, RouteResponse], asyncio.run(module.run_example()))

    assert allowed.status == 200
    assert allowed.body == {"project_id": "project-123", "actor": "user-ok", "workspace": "acme"}
    assert denied.status == 403
    assert denied.body == {
        "detail": "forbidden",
        "required_roles": ["reports:read"],
        "path": "/projects/project-123/reports",
        "workspace": "acme",
    }


def test_token_auth_example_runs() -> None:
    module = _load_example("examples/policy/token_auth.py")

    response = cast(RouteResponse, asyncio.run(module.run_example()))

    assert response.status == 200
    assert response.body == {
        "subject": "user-123",
        "scopes": ["profile:read", "projects:read"],
        "issuer": "example-idp",
    }


def test_split_arguments_example_runs() -> None:
    module = _load_example("examples/legacy_handlers/split_arguments.py")

    response = cast(RouteResponse, asyncio.run(module.run_example()))

    assert response.status == 200
    assert response.body == {
        "project_id": "project-123",
        "event": "deployed",
        "debug": "true",
        "session": "session-123",
        "actor": "user-123",
    }
