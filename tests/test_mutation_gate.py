# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

import importlib.util
from pathlib import Path
from types import ModuleType


def load_mutation_gate() -> ModuleType:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "mutation_gate.py"
    spec = importlib.util.spec_from_file_location("mutation_gate", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_surviving_mutants_parses_only_survivors() -> None:
    mutation_gate = load_mutation_gate()

    output = """
        routedef.version.x_load_version__mutmut_1: survived
        routedef.version.x_load_version__mutmut_2: killed
        routedef.version.x_load_version__mutmut_3: survived
    """

    assert mutation_gate.surviving_mutants(output) == (
        "routedef.version.x_load_version__mutmut_1: survived",
        "routedef.version.x_load_version__mutmut_3: survived",
    )


def test_disallowed_survivors_ignores_documented_equivalents() -> None:
    mutation_gate = load_mutation_gate()

    output = """
        routedef.adapters.fastapi.x_build_fastapi_router__mutmut_148: survived
        routedef.version.x_load_version__mutmut_3: survived
    """

    assert mutation_gate.disallowed_survivors(output) == ("routedef.version.x_load_version__mutmut_3: survived",)
