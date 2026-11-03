# ADR-0015: GET /v1/ws also accepts §5 auth via query parameters
Status: accepted

## Context
§5's request-auth scheme is a single `Authorization: SQDL1 device=..., ts=..., nonce=..., sig=...`
header, verified against a signing input of `method + "\n" + path(+query) + "\n" + ts + "\n"` +
nonce + BLAKE2b(body). Every route uses it, `GET /v1/ws` (§6) included.

This is unreachable from a real browser. A browser's native `WebSocket` constructor has no
parameter, option, or workaround for setting a custom header on the upgrade request - this is a
platform limitation, not an implementation gap in any one client. Every other authenticated route
is called via `fetch`/`XMLHttpRequest`, which *can* set `Authorization` freely; `GET /v1/ws` is the
only one that can't. Found live: webclient's `core`-provided Ktor-JS HTTP client accepted the
`header("Authorization", ...)` call in its WebSocket DSL without error, but the browser silently
dropped it - every real-browser `GET /v1/ws` attempt got a 401 "missing or malformed Authorization
header," meaning live-updates over WebSocket had never actually worked from webclient.

## Decision
`GET /v1/ws` additionally accepts the same four fields as URL query parameters -
`?device=...&ts=...&nonce=...&sig=...`, same base64url encoding as the header's own values - used
only when the `Authorization` header is absent. No other route gains this fallback.

The signing input is unchanged in shape, but for this one route it is always computed over the
bare path (`/v1/ws`, never `/v1/ws?device=...`), regardless of whether the header or the query
parameters carried the four fields. The query string is never itself part of what's signed - this
mirrors how the header's own transport is already out-of-band from the signing input today, and
sidesteps the obvious circularity of a signature that would otherwise need to cover its own
encoded representation. `/v1/ws` has no other legitimate query parameters, so excluding the query
string entirely from its signing input (rather than, say, excluding just these four reserved
names) costs nothing and stays simple.

Scoped to this one route deliberately, not offered as a general alternative to the header
everywhere: every other route doesn't have this problem, and widening where signed auth material
is allowed to appear (URLs end up in proxy/access logs, browser history, referrer headers far more
often than headers do) should track an actual need, not get offered pre-emptively. The four values
are short-lived (§5's 60s window) and single-use (replay cache) regardless of which transport
carries them, and the device public key is not secret - the same safety reasoning presigned-URL
schemes (S3 etc.) already rely on - but "acceptable when necessary" isn't "default everywhere."

A client doesn't need to pick a transport conditionally per platform: since the one route this
applies to has no other legitimate query usage, every implementation can simply always use query
parameters for `GET /v1/ws` specifically (header omitted for this one call) rather than branching
on which engine/platform it's running under.

## Consequences
+ `GET /v1/ws` is now actually reachable from a real browser - this was a functional gap in every
  shipped webclient release before this, not a regression.
+ No change to the header-based path for every other route, and no new crypto primitive - same
  signing input shape, same four fields, same window, same replay cache.
+ A client no longer needs platform-specific logic to authenticate the WS upgrade - one code path
  (query parameters) works uniformly everywhere.
− `device`/`ts`/`nonce`/`sig` now appear in a URL for this one route, where they're more likely to
  land in a proxy or server access log than a header would be - accepted given the values' short
  lifetime, single-use replay protection, and non-secret device key, but worth relay operators
  being aware their own access logs (never relay's own `logRequests`, which only ever logs method/
  pattern/status - CLAUDE.md's "never log... auth headers" rule extends to never logging query
  strings either, for exactly this reason) could now capture this route's query string.
