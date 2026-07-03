# routedef Architecture

`routedef` keeps route declarations, matching, request/response contracts, and web-runtime adapters separate.
The core package has no framework dependency, and adapters are the only place runtime-specific objects belong.

## Package Layout

- `routedef.contracts` defines `RouteDef`, `RouteHandler`, `RouteRequest`, and `RouteResponse`.
- `routedef.table` compiles a collection of route definitions into a `RouteTable` and returns `RouteMatch` values.
- `routedef.matching` owns path template parsing and path-parameter extraction.
- `routedef.request`, `routedef.response`, and `routedef.headers` contain small serialization helpers shared by adapters.
- `routedef.adapters.fastapi` exposes FastAPI integration.
- `routedef.adapters.cloudflare` exposes Cloudflare Workers integration.

`routedef.__init__` re-exports the canonical public API only. It must not contain feature logic.

## Core Contracts

A route is a method, path template, handler, and optional metadata:

```python
from routedef import RouteDef, RouteRequest, RouteResponse


async def handler(request: RouteRequest[dict[str, object], dict[str, object]]) -> RouteResponse:
    return RouteResponse.json({"account": request.path_params["account_id"]})


route = RouteDef(
    "GET",
    "/accounts/{account_id}/invoices",
    handler,
    metadata={"roles": ("billing:read",)},
)
```

Handlers receive one `RouteRequest` and return one `RouteResponse`. Consumers that previously used split
arguments should adapt their handlers locally instead of adding compatibility modules to this package.

## Matching And Tables

`RouteTable` preserves registration order, normalizes methods, rejects duplicate method/path pairs, and returns
path parameters from `{name}` placeholders:

```python
from routedef import RouteTable

table = RouteTable([route])
match = table.match("GET", "/accounts/acct_123/invoices")
assert match is not None
assert match.route is route
assert match.path_params == {"account_id": "acct_123"}
```

Adapters use the match to construct a `RouteRequest` with the runtime request method, concrete path, canonical
route path, path parameters, query, headers, body, raw body, auth, and context.

## Adapters

Adapters translate one host runtime into the canonical contracts:

- They construct a `RouteTable`.
- They call optional context providers.
- They call optional auth providers.
- They call optional enforcers.
- They decode the host request into a `RouteRequest`.
- They serialize `RouteResponse` back to the host response type.

Auth providers and enforcers receive the matched `RouteDef`, so route metadata remains the policy bridge for
applications such as `undef-billing` and `undef-admin`.

## Optional Dependency Isolation

Core imports must work without FastAPI, Cloudflare Workers, or any app-specific dependency installed. Optional
runtime dependencies stay under `routedef.adapters.*`, and applications import only the adapter they need.

Cloudflare-specific integration uses explicit Cloudflare names, such as `CloudflareDispatcher` and
`CloudflareRequest`. Avoid generic worker abstractions that hide the runtime boundary.

## No Compatibility Modules

Do not add `routedef.compat` or app-named compatibility packages. Migration code belongs in the consuming
application or in test-local examples. The package should keep one canonical route API and small adapters around
that API.
