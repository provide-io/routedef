# RouteDef Examples 🧭

These samples show app-owned integration patterns without adding long-term compatibility modules to `routedef`.

| Example | What It Shows |
| --- | --- |
| [`policy/metadata_enforcer.py`](https://github.com/provide-io/routedef/blob/main/examples/policy/metadata_enforcer.py) | Route metadata driving an authorization enforcer. |
| [`policy/token_auth.py`](https://github.com/provide-io/routedef/blob/main/examples/policy/token_auth.py) | Bearer-token parsing into `RouteRequest.auth`. |
| [`legacy_handlers/split_arguments.py`](https://github.com/provide-io/routedef/blob/main/examples/legacy_handlers/split_arguments.py) | A local adapter around legacy split-argument handlers. |
| [`cloudflare-worker`](https://github.com/provide-io/routedef/blob/main/examples/cloudflare-worker) | A runnable Cloudflare Python Worker fixture. |

Keep production policy code in the consuming app. RouteDef’s job is to carry metadata, context, auth, and request
data consistently across runtimes.
