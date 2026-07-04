# RouteDef 🧭

Runtime-neutral route definitions for Python services.

`routedef` gives applications one route contract that can be mounted into multiple runtimes. The core package has
no FastAPI, Cloudflare, ASGI, auth, database, or application dependency. Runtime-specific code lives in adapters.

## Installation 📦

```bash
pip install routedef
```

Install the FastAPI extra only in services that mount routes into FastAPI:

```bash
pip install "routedef[fastapi]"
```

Cloudflare Python Workers use the `routedef.adapters.cloudflare` adapter from the base package and run inside the
Cloudflare Python Workers runtime.

## What It Provides ✅

- `RouteDef`: method, path template, handler, and metadata.
- `RouteRequest`: canonical request object for handlers.
- `RouteResponse`: canonical response object for handlers.
- `RouteTable`: ordered method/path matching with `{path_param}` extraction.
- `build_fastapi_router`: FastAPI router integration.
- `CloudflareDispatcher`: direct Cloudflare Python Workers integration.

## Why Use It 🎯

Use `RouteDef` when you need the same route definitions to work across more than one Python runtime, especially
when migrating between framework-hosted APIs and Cloudflare Python Workers.

- One handler contract instead of per-runtime handler shapes.
- App-owned auth and authorization through metadata, auth providers, and enforcers.
- Dependency-free core package with optional runtime adapters.
- Testable route behavior without starting a web server.
- Migration-friendly wrappers for legacy split-argument handlers.

## Why Not 🚧

Do not use `RouteDef` as a full web framework, ORM, dependency injection container, auth library, or request
validation system. It intentionally does not own app policy, storage, schemas, background jobs, or runtime
lifecycle. If a service will only ever run in one framework and already has a stable route layer, the adapter
boundary may not be worth adding.

## Architecture 🏗️

![routedef request flow](https://raw.githubusercontent.com/provide-io/routedef/main/docs/diagrams/routedef-flow.svg)

![routedef package boundaries](https://raw.githubusercontent.com/provide-io/routedef/main/docs/diagrams/runtime-adapters.svg)

See [docs/architecture.md](https://github.com/provide-io/routedef/blob/main/docs/architecture.md) for package
boundaries and [examples/README.md](https://github.com/provide-io/routedef/blob/main/examples/README.md) for
generic samples covering route metadata policy, bearer-token auth, and legacy split-argument handlers.

## Basic Usage 🚀

```python
from routedef import RouteDef, RouteRequest, RouteResponse, RouteTable


async def get_item(request: RouteRequest[None, dict[str, object]]) -> RouteResponse:
    return RouteResponse.json({"id": request.path_params["id"]})


route_defs = [RouteDef("GET", "/v1/items/{id}", get_item)]
routes = RouteTable(route_defs)
```

## FastAPI

```python
from fastapi import FastAPI
from routedef.adapters.fastapi import build_fastapi_router

app = FastAPI()
app.include_router(build_fastapi_router(route_defs))
```

## Cloudflare Python Workers

```python
from routedef.adapters.cloudflare import CloudflareDispatcher
from workers import WorkerEntrypoint

dispatcher = CloudflareDispatcher(routes)


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        return await dispatcher.dispatch(request)
```

A real local Cloudflare fixture lives in
[examples/cloudflare-worker](https://github.com/provide-io/routedef/blob/main/examples/cloudflare-worker). Run it with:

```bash
uv run python scripts/check_cloudflare_worker.py
```

The integration script vendors the local `src/routedef` package into a temporary Python Worker project, runs
`pywrangler sync`, starts `wrangler@latest dev`, and probes routes over HTTP.

## Quality Gates 🧪

```bash
uv run pre-commit run --all-files
uv run pytest -q --cov=src/routedef --cov-branch --cov-report=term-missing --cov-fail-under=100
uv run pre-commit run mutation-sweep --hook-stage manual
uv run pre-commit run cloudflare-worker-integration --hook-stage manual
```

The project requires 100% branch coverage, strict typing, security/dead-code/complexity checks, REUSE compliance,
max-LOC checks, mutation testing, and a Cloudflare Worker runtime integration gate.
