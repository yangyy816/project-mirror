# P3–P7 Demo D11 Real Flow Contract 02

## Decision status

```text
CONTRACT_ID: P3_P7_D11_REAL_FLOW_CONTRACT_02
TRACK: DEMO_PROTOTYPE
STATUS: PRINCIPAL_ACCEPTED_FOR_ISOLATED_IMPLEMENTATION
BASE_SHA: 464e63542b9f2d9a242ac2493f0cb6efbdc5fb92
INTEGRATION_GATE: D03_EXACT_SHA_CI_PASS
PUBLIC_API_SHAPE_CHANGE: NONE
PUBLIC_API_BEHAVIOR_CHANGE: ACTIVATE_EXISTING_IDENTITY_AND_SESSION_CONTRACTS
MIGRATION_CHANGE: NONE
PRODUCTION_AUTHORIZATION: NONE
REAL_USER_AUTHORIZATION: NONE
```

## Product slice

The first executable D11 real-flow slice is:

```text
CURRENT_ADMITTED_D02_SYNTHETIC_IDENTITY
-> OWNER_BOUND_DEMO_SESSION
-> SERVER_ONLY_BROWSER_HANDLE
```

This slice activates the already published `GET /api/v1/demo/identities` and
`POST /api/v1/demo/sessions` contracts. It does not start D03, alter D02
authority, expose image bytes, or claim a complete browser-to-Worker flow.

## Identity projection

`GET /api/v1/demo/identities` is authenticated by the existing Demo bearer and
returns only current D02 generic synthetic admissions. The implementation must:

- revalidate the current actor;
- select only current leaf `ADMIT` rows using the exact accepted generic
  identity schema;
- replay `mirror_demo_require_current_synthetic_admission` for every returned
  identity;
- return rows ordered by `identity_id` ascending; and
- fail the whole read closed when any selected authority cannot be replayed.

The response remains the existing minimal projection:

```text
identity_id
canonical_asset_digest
admission_status = ADMITTED
```

It must not contain an Asset ID, object key, URL, locator, Prompt, receipt,
landmark, measurement, private path, or Provider detail. A genuinely empty
current set returns an empty list. Authority or database failure returns a
redacted `503`; it must not be misreported as an empty set.

## Session creation

`POST /api/v1/demo/sessions` remains server-to-server and accepts the existing
request fields `synthetic_identity_id` and `context_seed`, plus the required
`Idempotency-Key` header. In one PostgreSQL transaction it must:

1. lock and revalidate the active Demo actor;
2. revalidate the requested exact current synthetic admission;
3. create one immutable `DemoSession/v1` whose config is exactly
   `DemoSessionConfig/v1` plus that identity ID;
4. set a fixed Demo API session lifetime of 900 seconds; and
5. serialize same actor/operation/key creation with a PostgreSQL transaction
   advisory lock before binding the response through the existing
   `session.create` semantic idempotency authority.

Same actor/key/payload replay returns the same session. A different payload for
the same actor/key returns the existing idempotency collision. Invalid or
non-current identities are reported with one non-enumerating unavailable
response. Actor, session status, expiry and Asset authority are never caller
controlled. Any error leaves zero Session or command-binding partial rows.

No migration is required: `DemoSession`, its actor foreign key and immutable
authority fields already exist; `DemoCommandBinding` already admits
`session.create`; D03 already requires the exact session config shape and
current-admission replay.

## Browser bridge

The browser continues to call only `POST /api/demo/session` with no body and no
Authorization header. The Next server must:

1. read an exact server-only `DEMO_BOOTSTRAP_IDENTITY_ID`;
2. list current identities with the server-only Demo bearer and require that
   the configured identity is present;
3. generate a fresh 32-byte context seed and server-side idempotency key;
4. create the upstream API Session;
5. cap the browser handle lifetime to the lesser of the configured 60–900
   second bridge TTL and the upstream Session lifetime; and
6. store only the upstream Session ID and expiry in the bounded in-process
   registry, plus a one-way binding fingerprint used to invalidate handles
   whenever server-only identity, bearer, upstream origin or TTL configuration
   changes.

The browser receives only a random 64-hex HttpOnly, SameSite=Strict,
`/api/demo`-scoped cookie and a redacted readiness response. Missing or stale
configuration, identity mismatch, upstream failure, invalid expiry and
registry exhaustion all fail closed without returning upstream identifiers.

The current recall bridge must also stop returning the outer or nested upstream
`session_id` to the browser. It may use that ID internally to verify Context and
Trace agreement before projecting the response.

## Security and privacy boundary

- Demo bearer, actor ID, upstream Session ID, synthetic identity ID and Asset
  IDs remain server-side and must not enter browser JSON, DOM, URL, local
  storage or client logs.
- Private D02 bytes, locators, Prompt, object keys, signed URLs, credentials and
  task-scoped runtime handles are outside this slice.
- Browser overrides of identity, session, actor, Asset, seed, expiry,
  idempotency key or Authorization remain rejected.
- The endpoint is synthetic-Demo-only and creates no production or real-user
  authorization.

## Acceptance

- current-admission list, stable ordering, empty set and fail-closed corruption
  behavior pass in real PostgreSQL;
- session creation, replay, payload collision, concurrent winner, inactive
  actor, unknown/non-generic identity and zero-partial rollback pass;
- API route error mappings remain redacted and exact;
- browser bootstrap uses only server-side identity/seed/key selection;
- no upstream actor/session/identity/Asset ID or bearer appears in browser
  responses;
- logout, expiry, rotation and capacity behavior remain fail closed;
- OpenAPI and generated client have zero drift; and
- Ruff, strict mypy, targeted Python/TypeScript tests, build, Playwright,
  Gitleaks and one integrated-SHA CI pass before this slice is accepted.
