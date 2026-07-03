# Routedef Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the initial `routedef` Python package with runtime-neutral route contracts, FastAPI and Cloudflare adapters, strict quality gates, 100% branch coverage, and mutation testing configuration.

**Architecture:** Core modules under `src/routedef` have no FastAPI, ASGI, Cloudflare, or app-auth dependency. Runtime adapters live under `src/routedef/adapters` and translate native request/response objects to the canonical `RouteRequest -> RouteResponse` handler model. App auth, authorization, storage, and context remain external callback policy.

**Tech Stack:** Python 3.11+, hatchling, pytest, pytest-cov, ruff, mypy strict, ty, bandit, vulture, xenon, pip-audit, REUSE, mutmut.

---

## File Map

- `pyproject.toml`: metadata, extras, strict tools, coverage, mutmut.
- `.pre-commit-config.yaml`: Provide.io strict hooks, no frontend/Terraform/Worker sync hooks.
- `LICENSE`, `REUSE.toml`, `.secrets.baseline`, `VERSION`, `README.md`: repo metadata.
- `src/routedef/__init__.py`: public exports only; no feature logic.
- `src/routedef/py.typed`: typed package marker.
- `src/routedef/errors.py`: `RouteConfigError`, `RouteDispatchError`, `BadRequestBody`.
- `src/routedef/types.py`: `AuthProvider`, `ContextProvider`, `Enforcer`, body-reader aliases.
- `src/routedef/contracts.py`: `RouteDef`, `RouteRequest`, `RouteResponse`, `RouteHandler`.
- `src/routedef/headers.py`: case-insensitive header normalization helpers.
- `src/routedef/request.py`: query/body/path helper functions.
- `src/routedef/response.py`: response body classification and serialization helpers.
- `src/routedef/matching.py`: path-template compile/match.
- `src/routedef/table.py`: immutable ordered route table.
- `src/routedef/adapters/fastapi.py`: FastAPI adapter.
- `src/routedef/adapters/cloudflare.py`: direct Cloudflare Python Worker dispatcher.
- `tests/`: one focused test module per source module plus migration-style tests.
- `scripts/`: SPDX, LOC, xenon, license checks.
- `.ci/`: strict empty baselines.
- `docs/architecture.md`, `docs/migration.md`: public docs.

All files must stay under 500 lines. Split by module before any file reaches 450 lines. Prefer clear module names over underscore-heavy helper files. `__init__.py` files export symbols only.

## Task 1: Scaffold And Tooling

**Files:** create `pyproject.toml`, `.pre-commit-config.yaml`, `LICENSE`, `REUSE.toml`, `.secrets.baseline`, `VERSION`, `README.md`, `src/routedef/__init__.py`, `src/routedef/py.typed`, `tests/test_package_metadata.py`.

- [ ] Write `tests/test_package_metadata.py`:

```python
from pathlib import Path


def test_version_file() -> None:
    assert Path("VERSION").read_text(encoding="utf-8").strip() == "0.1.0"


def test_package_exports() -> None:
    import routedef

    assert isinstance(routedef.__all__, tuple)
    assert routedef.__version__ == "0.1.0"
```

- [ ] Run `uv run pytest tests/test_package_metadata.py -q`; expect import/config failure.
- [ ] Add scaffold. `pyproject.toml` uses `requires-python = ">=3.11"`, `license = "Apache-2.0"`, author `provide.io llc`, hatchling, ruff, mypy strict, ty, pytest coverage fail-under 100, mutmut, and dev deps for all gates.
- [ ] Add SPDX headers to Python files:

```python
# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0
```

- [ ] Run early checks:

```bash
uv run ruff format src tests
uv run ruff check --fix src tests
uv run mypy src tests
uv run pytest tests/test_package_metadata.py -q
```

- [ ] Commit: `git add . && git commit -m "chore: scaffold routedef package"`.

## Task 2: Contracts And Errors

**Files:** create `src/routedef/errors.py`, `src/routedef/types.py`, `src/routedef/contracts.py`; modify `src/routedef/__init__.py`; create `tests/test_contracts.py`.

- [ ] Write tests for method normalization, path validation, immutable route/request state, metadata preservation, JSON/text/bytes/empty response constructors, and route handler protocol use:

```python
async def echo(request: RouteRequest[str, dict[str, object]]) -> RouteResponse:
    return RouteResponse.json({"auth": request.auth, "path": request.path})
```

- [ ] Assert `RouteDef("get", "/v1/items/{id}", echo).method == "GET"` and `RouteDef("GET", "bad", echo)` raises `RouteConfigError`.
- [ ] Run `uv run pytest tests/test_contracts.py -q`; expect missing type failures.
- [ ] Implement the minimal contracts. `RouteDef` rejects empty paths and paths not starting with `/`. `RouteRequest` includes method, path, route_path, path_params, query, headers, body, raw_body, auth, context. `RouteResponse` supports `json`, `text`, `bytes`, and `empty`.
- [ ] Run:

```bash
uv run ruff format src/routedef tests/test_contracts.py
uv run ruff check --fix src/routedef tests/test_contracts.py
uv run mypy src tests
uv run pytest tests/test_contracts.py -q
```

- [ ] Commit: `git add src/routedef tests/test_contracts.py && git commit -m "feat: add route contracts"`.

## Task 3: Headers, Request, And Response Helpers

**Files:** create `src/routedef/headers.py`, `src/routedef/request.py`, `src/routedef/response.py`; modify `src/routedef/__init__.py`; create `tests/test_headers.py`, `tests/test_request.py`, `tests/test_response.py`.

- [ ] Write tests for `normalize_headers`, case-insensitive lookup, query parsing with blank values, JSON decoding success/failure, body kind detection, bytes passthrough, text content type, JSON serialization, and 204 empty handling.
- [ ] Include these assertions:

```python
assert normalize_headers({"Content-Type": "application/json"}) == {"content-type": "application/json"}
assert response_body_kind(RouteResponse.bytes(b"x")) == "bytes"
assert response_body_kind(RouteResponse.empty(204)) == "empty"
```

- [ ] Run `uv run pytest tests/test_headers.py tests/test_request.py tests/test_response.py -q`; expect missing helper failures.
- [ ] Implement helpers in the named modules only. Keep serialization deterministic with `json.dumps(..., separators=(",", ":"))`.
- [ ] Run:

```bash
uv run ruff format src/routedef tests/test_headers.py tests/test_request.py tests/test_response.py
uv run ruff check --fix src/routedef tests/test_headers.py tests/test_request.py tests/test_response.py
uv run mypy src tests
uv run pytest tests/test_headers.py tests/test_request.py tests/test_response.py -q
```

- [ ] Commit: `git add src/routedef tests/test_headers.py tests/test_request.py tests/test_response.py && git commit -m "feat: add request response helpers"`.

## Task 4: Path Matching

**Files:** create `src/routedef/matching.py`; modify `src/routedef/__init__.py`; create `tests/test_matching.py`.

- [ ] Write tests for static match, placeholder match, URL-decoded params, method-independent path matching, invalid placeholder names, duplicate placeholder names, and no slash crossing:

```python
compiled = compile_path_template("/v1/files/{name}")
assert match_path(compiled, "/v1/files/a%20b.txt") == {"name": "a b.txt"}
assert match_path(compiled, "/v1/files/a/b") is None
```

- [ ] Run `uv run pytest tests/test_matching.py -q`; expect missing matching failures.
- [ ] Implement `CompiledPath`, `compile_path_template`, and `match_path`. Use placeholder regex `[A-Za-z_][A-Za-z0-9_]*`, static `re.escape`, segment pattern `[^/]+`, and `urllib.parse.unquote`.
- [ ] Run:

```bash
uv run ruff format src/routedef/matching.py tests/test_matching.py
uv run ruff check --fix src/routedef/matching.py tests/test_matching.py
uv run mypy src tests
uv run pytest tests/test_matching.py -q
```

- [ ] Commit: `git add src/routedef/matching.py src/routedef/__init__.py tests/test_matching.py && git commit -m "feat: add path matching"`.

## Task 5: Route Table

**Files:** create `src/routedef/table.py`; modify `src/routedef/__init__.py`; create `tests/test_table.py`.

- [ ] Write tests for ordered matching, no match, method normalization, duplicate `(method, path)` rejection, and `RouteMatch.route/path_params`:

```python
table = RouteTable([RouteDef("GET", "/v1/items/{id}", echo)])
match = table.match("get", "/v1/items/42")
assert match is not None
assert match.path_params == {"id": "42"}
```

- [ ] Run `uv run pytest tests/test_table.py -q`; expect missing table failures.
- [ ] Implement immutable `CompiledRoute`, `RouteMatch`, and `RouteTable`. Store compiled routes in a tuple and preserve registration order.
- [ ] Run:

```bash
uv run ruff format src/routedef/table.py tests/test_table.py
uv run ruff check --fix src/routedef/table.py tests/test_table.py
uv run mypy src tests
uv run pytest tests/test_table.py -q
```

- [ ] Commit: `git add src/routedef/table.py src/routedef/__init__.py tests/test_table.py && git commit -m "feat: add route table"`.

## Task 6: FastAPI Adapter

**Files:** create `src/routedef/adapters/__init__.py`, `src/routedef/adapters/fastapi.py`; create `tests/test_fastapi_adapter.py`; modify `pyproject.toml` for optional `fastapi` extra and test dependency.

- [ ] Write tests using `FastAPI` and `TestClient` for GET query, POST JSON, invalid JSON 400, bytes response, context provider, auth provider, enforcer success/failure, and core import without FastAPI.
- [ ] Include policy callback test:

```python
router = build_fastapi_router(
    [RouteDef("GET", "/v1/ping", handler)],
    context_provider=lambda request: {"name": "ctx"},
    auth_provider=lambda route, request, context: "auth",
)
```

- [ ] Run `uv run pytest tests/test_fastapi_adapter.py -q`; expect missing adapter failures.
- [ ] Implement `build_fastapi_router`. Adapter converts FastAPI `Request` to `RouteRequest`, calls callbacks, catches invalid JSON as 400, and converts `RouteResponse` to FastAPI `Response`.
- [ ] Run:

```bash
uv run ruff format src/routedef/adapters tests/test_fastapi_adapter.py
uv run ruff check --fix src/routedef/adapters tests/test_fastapi_adapter.py
uv run mypy src tests
uv run pytest tests/test_fastapi_adapter.py -q
```

- [ ] Commit: `git add pyproject.toml src/routedef/adapters tests/test_fastapi_adapter.py && git commit -m "feat: add fastapi adapter"`.

## Task 7: Cloudflare Adapter

**Files:** create `src/routedef/adapters/cloudflare.py`; create `tests/test_cloudflare_adapter.py`.

- [ ] Write tests with fake request objects and fake `workers.Response` installed through `sys.modules`. Cover JSON body, text body, `arrayBuffer`, query params, header normalization, 404 no-match, enforcer rejection, and response conversion.
- [ ] Include dispatch assertion:

```python
dispatcher = CloudflareDispatcher(
    RouteTable([RouteDef("GET", "/v1/items/{id}", handler)]),
    context_provider=lambda request: {"runtime": "cf"},
    auth_provider=lambda route, request, context: "user",
)
response = await dispatcher.dispatch(FakeRequest("https://x.test/v1/items/7", method="GET"))
assert response.status == 200
```

- [ ] Run `uv run pytest tests/test_cloudflare_adapter.py -q`; expect missing adapter failures.
- [ ] Implement `CloudflareDispatcher`. Import `workers.Response` only when creating the response. Do not import FastAPI or ASGI. Read body from `arrayBuffer()` if available, otherwise `text()`.
- [ ] Run:

```bash
uv run ruff format src/routedef/adapters/cloudflare.py tests/test_cloudflare_adapter.py
uv run ruff check --fix src/routedef/adapters/cloudflare.py tests/test_cloudflare_adapter.py
uv run mypy src tests
uv run pytest tests/test_cloudflare_adapter.py -q
```

- [ ] Commit: `git add src/routedef/adapters/cloudflare.py tests/test_cloudflare_adapter.py && git commit -m "feat: add cloudflare adapter"`.

## Task 8: Migration-Style Tests And Docs

**Files:** create `tests/test_undef_style.py`, `tests/test_uwarp_style.py`, `docs/architecture.md`, `docs/migration.md`; modify `src` only for canonical API gaps.

- [ ] Write tests proving four consumer patterns without adding `routedef.compat`: `undef-billing` role metadata via enforcer, `undef-admin` authorize callback via enforcer, Taybols JWT user via auth provider, and uwarp split-arg handler via a test-local adapter:

```python
def adapt_uwarp(handler: UwarpHandler) -> RouteHandler[object, dict[str, object]]:
    async def wrapped(request: RouteRequest[object, dict[str, object]]) -> RouteResponse:
        return await handler(
            path_params=request.path_params,
            body=request.body,
            query=request.query,
            game=request.context["game"],
            auth=request.auth,
        )
    return wrapped
```

- [ ] Run `uv run pytest tests/test_undef_style.py tests/test_uwarp_style.py -q`; expect failures only where canonical APIs need tightening.
- [ ] Update canonical APIs if required; do not add compatibility modules.
- [ ] Write docs with the same examples and migration order.
- [ ] Run:

```bash
uv run ruff format src tests docs
uv run ruff check --fix src tests
uv run mypy src tests
uv run pytest tests/test_undef_style.py tests/test_uwarp_style.py -q
```

- [ ] Commit: `git add src tests/test_undef_style.py tests/test_uwarp_style.py docs/architecture.md docs/migration.md && git commit -m "test: prove migration route styles"`.

## Task 9: Quality Scripts And Release Gates

**Files:** create `scripts/check_spdx_headers.py`, `scripts/check_max_loc.py`, `scripts/check_xenon.py`, `scripts/check_licenses.py`, `.ci/max-loc-baseline.json`, `.ci/xenon-baseline.json`, `.ci/mutation-baseline.json`; modify `.pre-commit-config.yaml`, `pyproject.toml`.

- [ ] Add scripts under 500 lines each. `check_max_loc.py` must fail any non-`.git` project file over 500 lines. `check_spdx_headers.py` must require the Provide.io SPDX header in Python files.
- [ ] Run focused script checks:

```bash
uv run python scripts/check_spdx_headers.py
uv run python scripts/check_max_loc.py --max-lines 500 --roots src tests scripts docs
uv run python scripts/check_xenon.py --max-absolute C --max-modules B --max-average A --paths src/routedef
uv run python scripts/check_licenses.py
```

- [ ] Run full verification:

```bash
uv run ruff format --check src tests scripts
uv run ruff check src tests scripts
uv run mypy src tests
uv run ty check src tests
uv run bandit -r src -q -ll
uv run pytest -q --cov=src/routedef --cov-branch --cov-report=term-missing --cov-fail-under=100
uv run vulture --min-confidence 80 src/routedef tests scripts
uv run xenon --max-absolute C --max-modules B --max-average A src/routedef
uv run python -m pip_audit --path .
uv run reuse lint
```

- [ ] Run mutation gate:

```bash
uv run mutmut run
uv run mutmut results
```

Expected: zero surviving mutants. Add targeted tests for any surviving mutants and rerun.

- [ ] Commit: `git add scripts .ci .pre-commit-config.yaml pyproject.toml src tests docs && git commit -m "chore: add quality gates"`.

## Final Verification

- [ ] Run `git status --short`; expect a clean tree.
- [ ] Run `uv run pre-commit run --all-files`; expect all hooks pass.
- [ ] Run `uv run pre-commit run mutation-sweep --hook-stage manual`; expect zero surviving mutants.
- [ ] Run `find . -path ./.git -prune -o -type f -print | xargs wc -l | sort -nr | head`; expect no project file over 500 lines.

## Self-Review

- Spec coverage: scaffold, SPDX, 3.11+, dependency-free core, FastAPI adapter, Cloudflare adapter, app-owned policy, no long-term compatibility modules, no generic worker-named adapter, 500-line cap, early checks, 100% branch coverage, and mutation testing are all covered.
- Red-flag scan: no deferred implementation markers or long-term compatibility namespace is present.
- Type consistency: all tasks use the canonical `RouteRequest[AuthT, ContextT] -> RouteResponse` model and keep adapter callbacks external.
