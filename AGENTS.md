<!--
SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
SPDX-License-Identifier: Apache-2.0
-->

# Repository Guidelines

## Project Structure & Module Organization

- `src/routedef/`: public RouteDef contracts, path matching, response/request helpers, and route table logic.
- `src/routedef/adapters/`: runtime adapters for web frameworks and edge runtimes.
- `tests/`: pytest suite. Keep broad adapter tests split before any file reaches 500 LOC.
- `examples/`: runnable integration fixtures, including the Cloudflare Python Worker example.
- `scripts/`: quality, build, mutation, and integration gate helpers.
- `docs/`: architecture, migration, diagrams, and package positioning docs.

This is a single Python package using a `src/` layout. Do not add feature logic to `__init__.py`; only re-export stable public API there.

## Build, Test, and Development Commands

Use `uv` for all Python environment and tool execution.

- `uv sync`: install package and dev dependencies.
- `uv run ruff check src tests scripts`: lint Python files.
- `uv run mypy src tests`: run strict type checks.
- `uv run ty check src tests`: run the secondary type checker.
- `uv run pytest -q --cov=src/routedef --cov-branch --cov-report=term-missing --cov-fail-under=100`: run the full coverage gate.
- `uv run python scripts/mutation_gate.py`: run the mutation gate.
- `uv run pre-commit run --all-files`: run the local quality suite.
- `uv run python scripts/check_build_install.py`: build and smoke-test wheel installation.
- `uv run python scripts/check_cloudflare_worker.py`: run the Cloudflare Worker integration fixture.

CI/CD changes must be verified with `act` only before they are called ready:

- `act pull_request -j quality`
- `act pull_request -j package`
- `act pull_request -j cloudflare-worker`
- `act pull_request -j mutation`

## Coding Style & Naming Conventions

- Python 3.11+ is the supported runtime floor.
- Use 4-space indentation and full type annotations for public functions.
- Modules, functions, and variables use `snake_case`; classes use `PascalCase`; constants use `UPPER_SNAKE_CASE`.
- Keep every source, test, script, and documentation file at or below 500 LOC. Split by package/module responsibility before a file approaches the limit.
- Prefer modules over underscore-prefixed large files when a feature needs to be split, and export the stable surface through `__init__.py`.
- Keep adapters thin; shared routing behavior belongs in contracts, matching, table, request, response, or narrowly named helper modules.
- Do not add a long-term `compat` layer. Prefer explicit modern APIs and migration docs.
- Use SPDX headers on tracked source, test, script, docs, and config files where the local license hooks expect them.

## Testing Guidelines

- Test framework: `pytest`.
- Coverage requirement: 100% statement and branch coverage for `src/routedef`.
- Mutation testing is a required quality gate. Any equivalent survivor must be documented in `scripts/mutation_gate.py` with a concrete reason.
- Add property/parameterized coverage for path templates, route matching, body parsing, and adapter error paths when changing those surfaces.
- Adapter behavior must stay equivalent across FastAPI and Cloudflare Worker integrations unless a difference is explicitly documented.
- Integration coverage should exercise both FastAPI and Cloudflare Worker paths for request routing, JSON bodies, path params, not-found behavior, and adapter errors.

## CI, Security, and Release Gates

The GitHub Actions workflow is the CI source of truth and should stay aligned with this file. It must cover:

- strict pre-commit checks,
- Python 3.11, 3.12, and 3.13 quality matrix,
- 100% branch coverage,
- wheel/sdist build and install smoke test,
- Cloudflare Worker integration,
- mutation gate.

Security and maintenance gates include Bandit, pip-audit, vulture, xenon, SPDX/license checks, secrets scanning, ruff, mypy, and ty. Do not bypass these to make a release.

## Commit & Pull Request Guidelines

- Use Conventional Commit style, for example `feat: add route name lookup`.
- Keep commits scoped to one logical change.
- Do not amend or rewrite commits unless explicitly asked.
- Do not use destructive git commands without explicit approval.
- PRs should include the behavior summary, API changes, migration notes when relevant, and exact local/`act` verification commands.
