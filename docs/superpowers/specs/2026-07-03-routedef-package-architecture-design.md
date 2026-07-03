# Routedef Package Architecture Design

Date: 2026-07-03

## Purpose

`routedef` will be a small Python package that lets Provide.io and Undef Python HTTP services define routes once and run them through multiple runtime adapters. The immediate goal is to remove FastAPI/ASGI from Cloudflare Python Worker hot paths while keeping equivalent local FastAPI support.

The package will live at `/Users/tim/code/gh/provide-io/routedef`, use SPDX headers for `provide.io llc`, and target Python 3.11+.

## Scope

In scope:

- A runtime-neutral route contract.
- Deterministic path-template compilation and matching.
- A route table abstraction with ordered dispatch and duplicate detection.
- A FastAPI adapter for local/dev/server runtime.
- A Cloudflare Python Workers adapter for direct Worker request dispatch.
- Strict testing, type checking, coverage, complexity, security, license, and mutation gates.

Out of scope:

- Built-in long-term compatibility modules for `uwarp` or existing `undef-*` route shapes.
- App-specific authentication models.
- App-specific authorization policy.
- ASGI bridging.
- WebSocket routing.
- OpenAPI schema generation beyond what the FastAPI adapter naturally exposes.

Temporary migration shims belong in consuming repositories, such as `uwarp.core.route_def` or `undef.billing.route_def`, not in `routedef`.

## Package Layout

```text
routedef/
  pyproject.toml
  README.md
  LICENSE
  REUSE.toml
  .pre-commit-config.yaml
  .secrets.baseline
  VERSION
  src/
    routedef/
      __init__.py
      py.typed
      contracts.py
      errors.py
      headers.py
      matching.py
      request.py
      response.py
      table.py
      types.py
      adapters/
        __init__.py
        fastapi.py
        cloudflare.py
  tests/
    test_contracts.py
    test_matching.py
    test_table.py
    test_headers.py
    test_fastapi_adapter.py
    test_cloudflare_adapter.py
    test_undef_style.py
    test_uwarp_style.py
  scripts/
    check_spdx_headers.py
    check_max_loc.py
    check_xenon.py
    check_licenses.py
  docs/
    architecture.md
    migration.md
    superpowers/
      specs/
        2026-07-03-routedef-package-architecture-design.md
  .ci/
    max-loc-baseline.json
    xenon-baseline.json
    mutation-baseline.json
```

No file may exceed 500 lines. If a file approaches the limit, split it into a package module with a clear name. Prefer modules and subpackages over large underscore-prefixed helper files.

`__init__.py` files will export public symbols only. They must contain no feature logic.

## Core Contract

The canonical handler model is a single request object:

```python
async def handler(request: RouteRequest[AuthT, ContextT]) -> RouteResponse:
    ...
```

Core public types:

- `RouteDef[AuthT, ContextT]`
- `RouteRequest[AuthT, ContextT]`
- `RouteResponse`
- `RouteHandler[AuthT, ContextT]`
- `RouteTable[AuthT, ContextT]`
- `CompiledRoute[AuthT, ContextT]`
- `RouteMatch[AuthT, ContextT]`

`RouteDef` includes method, path template, handler, and app-defined metadata. Route names, auth-required flags, and policy-specific values belong in metadata or in the consuming application. It does not include built-in role, grant, player, sysop, or webhook semantics.

`RouteRequest` will include normalized method, runtime path, matched route path, path parameters, query parameters, headers, parsed body, raw body, auth value, and context value.

`RouteResponse` will include status, body, headers, and optional content type handling. It must support JSON-like values, text, bytes, and empty bodies.

## Metadata And Policy

App policy stays app-owned. `routedef` will expose typed callback points rather than fixed auth models:

- A context provider builds per-request app context.
- An auth provider authenticates a raw runtime request for a route.
- An enforcer applies route metadata and app-specific policy.
- Body readers and error mappers may be overridden where runtimes need custom behavior.

The first version should keep route metadata simple and stable. A mapping-based metadata field is acceptable if public helpers preserve clear typing at adapter boundaries.

## Path Matching

Path templates use FastAPI-style placeholders such as `/v1/orders/{order_id}`.

Matching rules:

- Methods normalize to uppercase.
- Static path segments match exactly.
- Placeholder segments match exactly one segment.
- `RouteTable` returns URL-decoded placeholder values. Adapters that use native runtime matching must produce the same decoded path parameter values.
- Duplicate route detection is fail-fast.
- Route table order is deterministic.

Greedy catch-all segments are not part of v1 unless a current migration target requires them. If needed, they should be explicit syntax, not an accidental behavior of the last placeholder.

## Adapters

### FastAPI Adapter

`routedef.adapters.fastapi` exposes `build_fastapi_router(...)`, which builds a FastAPI `APIRouter` for the caller to include on an app.

Responsibilities:

- Convert FastAPI `Request` into `RouteRequest`.
- Invoke context/auth/enforcement callbacks.
- Decode request body consistently.
- Convert `RouteResponse` into FastAPI `Response`.
- Preserve route path templates for FastAPI routing and OpenAPI where possible.

The FastAPI dependency is optional and imported only by the adapter module.

### Cloudflare Adapter

`routedef.adapters.cloudflare` dispatches Cloudflare Python Worker requests directly.

Responsibilities:

- Read method, URL, path, query, headers, and body from Cloudflare request objects.
- Match against `RouteTable`.
- Invoke context/auth/enforcement callbacks.
- Convert `RouteResponse` into `workers.Response`.
- Avoid FastAPI and ASGI dependencies.

The adapter is named `cloudflare`, not `worker`, because generic worker naming is too broad and the adapter must handle Cloudflare-specific request/response behavior.

## Migration Strategy

Initial migrations should not add compatibility code to `routedef`.

Suggested order:

1. Build `routedef` core and adapters.
2. Migrate `undef-notify` first because its route surface is small.
3. Migrate `undef-billing` once role policy and response behavior are proven.
4. Migrate `undef-admin` after grant/scope enforcement hooks are proven.
5. Migrate `undef-account` and `undef-account-linked` off ASGI-in-Worker.
6. Migrate `taybols` after account validates the same model.
7. Treat `undef-engine` separately because its Durable Object and FastAPI coupling is larger.

Consumers may keep temporary local shims during migration. Those shims should be deleted once call sites use canonical `routedef` APIs.

## Quality Gates

Required:

- Ruff format and lint.
- Mypy strict.
- Ty check.
- Bandit.
- Vulture.
- Xenon.
- Pip-audit.
- REUSE license checks.
- SPDX header checks.
- Pytest with 100% branch coverage.
- Mutmut mutation testing with zero surviving mutants for release.

Mutation testing should be a manual or release gate, not a normal per-commit hook.

Development workflow must verify early:

- Run ruff and mypy after each completed source file or coherent file group.
- Run focused tests after each completed behavior slice.
- Run full quality gates before any completion claim.

## Pre-Commit Baseline

The pre-commit configuration should be based on strict Provide.io package conventions, closest to `provide-io/pymutant-mcp`, with service-specific hooks omitted.

Include:

- `reuse`.
- Ruff format and lint with fixes.
- Codespell.
- Detect-secrets with baseline.
- SPDX header check.
- Max LOC check with 500 line limit.
- Mypy strict.
- Ty.
- Bandit.
- Pytest with coverage.
- Pip-audit.
- Xenon.
- Vulture.
- License check.
- Manual mutation gates.

Do not include frontend, Terraform, or Worker sync hooks in this library repo.

## Acceptance Criteria

- The package installs on Python 3.11+.
- Core imports have no FastAPI dependency.
- FastAPI adapter imports FastAPI only inside the adapter surface.
- Cloudflare adapter has no FastAPI or ASGI dependency.
- All public package exports come from `__init__.py` without implementation logic.
- No source, test, or script file exceeds 500 lines.
- Tests demonstrate `undef`-style role policy, `undef-admin`-style authorization callbacks, uwarp-style route handler adaptation in consumer-side examples, and Taybols-style JWT user auth without putting compatibility modules in `routedef`.
- Test suite reaches 100% branch coverage.
- Mutation gate has zero surviving mutants before release.
