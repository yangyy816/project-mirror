# P3–P7 Demo D11 Real Flow Contract 09

## Decision status

```text
CONTRACT_ID: P3_P7_D11_REAL_FLOW_CONTRACT_09
TRACK: DEMO_PROTOTYPE
STATUS: PRINCIPAL_ACCEPTED_FOR_ISOLATED_IMPLEMENTATION
BASE_SHA: 6921de2e090aacacb6d5078d53c7d43cad153776
INTEGRATION_GATE: CONTRACT_06_07_08_INTEGRATED_EXACT_SHA_CI_PASS
PUBLIC_API_CHANGE: NONE
MIGRATION_CHANGE: NONE
WORKER_CHANGE: NONE
BROWSER_AUTHORITY_CHANGE: OPAQUE_STATUS_ONLY
PRODUCTION_AUTHORIZATION: NONE
REAL_USER_AUTHORIZATION: NONE
```

## Product slice

This slice continues the real synthetic Demo after `PROFILE_READY` through one
deterministic D08 edit:

```text
PROFILE_READY
-> Session canonical source editing admission
-> deterministic plan admission
-> deterministic execution admission
-> exact published result replay
-> IMAGE_VERSION_READY
```

It does not display image bytes, start D06 self-transfer, write D09 feedback,
invoke a Provider, or expose upstream authority to the browser.

## Browser contract

Add same-origin routes:

```text
POST /api/demo/edit
GET  /api/demo/edit
```

POST accepts exactly:

```json
{
  "operation": "EXPOSURE",
  "value_ppm": 250000
}
```

Allowed operations and request ranges are:

- `CROP`: integer `[1, 250000]`;
- `ROTATE`, `EXPOSURE`, `CONTRAST`, `SATURATION`, `TEMPERATURE`: integer
  `[-1000000, 1000000]`.

The existing deterministic planner remains the final authority for
quantization, locks, prohibited operations and operation-specific effects.
Values quantized to zero fail closed. `GEOMETRY`, `MAKEUP`, `GENERATIVE`,
`RESTORE` and `ROLLBACK` are not accepted in this slice.

Browser responses contain only:

```text
PENDING
IMAGE_VERSION_READY
REJECTED
FAILED
CANCELLED
```

or an existing safe error code. No Session, Job, Binding, EditingSession, Plan,
ToolRun, VerificationResult, ImageVersion or Asset ID/digest may enter browser
JSON, DOM, URL, storage or logs.

## Server state machine

The D11 registry retains one immutable operation/value request and these
server-only stages:

```text
EDIT_SESSION_STARTING
EDIT_SESSION_PENDING
PLAN_STARTING
PLAN_PENDING
EXECUTION_STARTING
EXECUTION_PENDING
IMAGE_VERSION_READY
```

1. Editing admission calls `POST /api/v1/demo/editing-sessions` with the exact
   bound Session ID and `source_selector=SESSION_CANONICAL_ASSET`.
2. Its Job poll must replay `P6_EDITING`, Binding digest and
   `EDITING_SESSION` target ID/digest.
3. Plan admission calls the exact editing-session target with the frozen
   browser operation/value. Its Job poll must replay the exact `EDIT_PLAN`
   target and digest.
4. Execution admission calls the exact RESULT plan with
   `execution_mode=DETERMINISTIC_RASTER` and the plan target authority digest.
5. Execution polling must replay the same Job/Binding/Plan target. Only after
   `COMPLETED` may the BFF call Contract 07's exact execution-result endpoint.
6. The result must match the retained Job, Session, EditingSession, Plan,
   Binding and plan digest and must have `version_kind=EDITED`. The complete
   ToolRun/verifier/ImageVersion/Asset projection remains server-only.

The BFF must not use active/latest ImageVersion, output digest lookup, a
browser-supplied ID or the legacy ToolRun GET as the result resolver.

## Idempotency, races and retry

Each admission stage receives a different random server-side idempotency key,
created and retained before its first upstream await. An uncertain retry uses
the same key and immutable request. Same-stage calls are single-flight.

Every await is followed by compare-and-set checks for the same opaque handle,
Session object, edit object and configuration fingerprint. Logout, Session
expiry, configuration rotation or a newer action invalidates old responses.

Only one edit may be created per Demo Session in this slice. Repeating the same
operation/value resumes it; a different request returns `CONFLICT`. Terminal
execution states never create a replacement Job. Polling is one second, at
most 120 times; timeout is recoverable and never rebuilds a stage.

## UI

After `PROFILE_READY`, render one operation selector and operation-aware value
input. The user explicitly starts the edit. Visible states are:

```text
EDIT_STARTING
EDIT_PENDING
IMAGE_VERSION_READY
ERROR
```

The ready message states only that one synthetic edit result has been
published. It does not claim production, display a beauty score, expose
authority fields, or pretend that real before/after media is available.

## Change boundary

Allowed changes are limited to the D11 server registry, one same-origin edit
route, the real-flow component, deterministic fake API and focused Web/
Playwright tests, plus this contract.

Explicitly forbidden:

- API, OpenAPI, generated-client, ORM, migration or Worker changes;
- Provider, D02 private state or image-byte access;
- D06/D09/D10 execution;
- browser storage, analytics or upstream authority disclosure;
- second-edit, restore or rollback behavior.

## Acceptance

Acceptance requires:

- server tests for all admission stages, exact Job/target/digest replay,
  retained keys, single-flight, terminal states and result mismatch;
- CAS tests for logout, expiry, configuration rotation and stale generations;
- component tests for operation ranges, explicit start, pending, ready, safe
  error and retry behavior;
- Playwright coverage of the complete Session→D03→D04→D05→D08 status flow;
- browser requests with no Authorization override and DOM/URL/storage with no
  upstream ID/digest/bearer/private locator;
- Web formatting, lint, strict TypeScript, unit tests, production build and one
  wave-level integrated CI pass.
