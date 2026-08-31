# P3–P7 D11 Trace UI Contract 01

Status: `UI_CONTRACT_ONLY`

The browser uses only same-origin Next.js endpoints. `POST` and `DELETE`
`/api/demo/session` create and clear an opaque HttpOnly handle; no browser
request supplies a bearer, actor, session identifier, or upstream base URL.
Requests with an Origin or `Sec-Fetch-Site` must prove same origin (and at
least one of those headers must be present). Client Authorization, query/body
overrides, duplicate parameters, and internal URL/session/actor overrides are
rejected.

The handle is random 64-hex, HttpOnly, SameSite=Strict, path-scoped to
`/api/demo`, and has a 60–900 second bounded TTL. A process-memory registry
stores only handle, server-bound session id, and expiry; it sweeps expired
entries, reuses a valid handle, and caps itself at 64 entries. It never stores
the bearer. Reuse also requires the currently configured session id to match;
configuration rotation invalidates the old handle. Server restarts invalidate
handles. Session routes accept a zero-body request only and do not read a
request body.

`GET /api/demo/recall?recall_at=<explicit ISO-8601 timezone timestamp>` reads
the server-bound session and forwards that identical canonical timestamp to the
existing Context and Trace API routes. Context compilation and trace evidence
digests must match; a mismatch returns `STALE_RESPONSE` and is not rendered.

The real route currently returns only Context projection and Trace digest/id.
The event list, source, precedence, and watermark panel is an explicitly
labelled synthetic fixture view model: `SYNTHETIC_DEMO`,
`RUNTIME_EVIDENCE_DEFERRED`, and `UI_CONTRACT_ONLY`. It is never presented as a
real D02 runtime flow or E2E evidence.

Upstream authorization, conflict, unsupported, and availability failures are
reduced to stable redacted envelopes. Every BFF response is `Cache-Control:
no-store` and varies on Cookie. Bearers, upstream paths, response payloads,
and internal configuration are not placed in the DOM, browser storage, URL,
client props, or client error messages.

The bridge implementation is marked `server-only` in production builds. The
Vitest resolver substitutes only that sentinel with an empty test shim; client
components do not import the bridge module. A failed logout remains `DENIED` or
`UNAVAILABLE` in the UI rather than claiming that the session was ended.
