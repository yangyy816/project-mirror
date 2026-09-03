# P3–P7 Demo D11 Real Flow Contract 06

## Decision status

```text
CONTRACT_ID: P3_P7_D11_REAL_FLOW_CONTRACT_06
TRACK: DEMO_PROTOTYPE
STATUS: PRINCIPAL_ACCEPTED_FOR_ISOLATED_IMPLEMENTATION
BASE_SHA: 537c21b240ad169dbf410d582daf5955c3b3d4c5
INTEGRATION_GATE: CONTRACT_05_INTEGRATED_EXACT_SHA_CI_PASS
PUBLIC_API_SHAPE_CHANGE: ADDITIVE_PROFILE_JOB_RESULT_READ
PUBLIC_API_BEHAVIOR_CHANGE: PRESENT
MIGRATION_CHANGE: NONE
PRODUCTION_AUTHORIZATION: NONE
REAL_USER_AUTHORIZATION: NONE
```

## Product slice

This slice extends the synthetic-only Demo flow through the accepted D05
profile compiler:

```text
QUESTIONNAIRE_COMPLETED
-> PROFILE_COMPILE_JOB
-> EXACT_JOB_BINDING
-> EXACT_PROFILE_COMPILATION_BUNDLE
-> PROFILE_READY
```

It does not start D06, display a profile or score, expose upstream identifiers,
process a real user image, invoke a Provider, or authorize production use.

## Exact result authority

The only valid result resolver is the existing unique authority chain:

```text
Job.id
-> DemoJobBinding.job_id
-> DemoProfileCompilationBundle.demo_job_binding_id
```

Add this read-only Demo API operation:

```text
GET /api/v1/demo/profiles/compilation-jobs/{job_id}/result
operationId: demoGetProfileCompilationResultByJob
authentication: DemoBearerAuth
request body: none
Idempotency-Key: not accepted
```

A ready response is exactly:

```json
{
  "status": "PROFILE_READY",
  "job_id": "<DemoId>",
  "session_id": "<DemoId>",
  "profile_id": "<DemoId>",
  "job_binding_digest": "<DemoDigest>",
  "compilation_digest": "<DemoDigest>"
}
```

`profile_id` is the immutable compilation bundle ID. The operation must not
return DesiredDeltaProfile, StyleProfile, Constraint, questionnaire, actor or
SelfState identifiers.

The result service is read-only. It must not call the side-effectful profile
`compile()` path, create an Attempt, materialize a Profile, modify a Job, or
select `/profiles/active`. Active/latest ordering is not authority for a
specific Job.

Within one database transaction the service must:

1. read the exact owner-bound Job and unique JobBinding;
2. replay `profile.compile`, target type `DEMO_ACTOR`, target ID and digest,
   exact Session ownership, compiler version and empty Job payload;
3. map `PENDING` and `RUNNING` to not-ready;
4. map `REJECTED`, `FAILED` and `CANCELLED` to terminal;
5. for `COMPLETED`, require the exact completed JobAttempt and
   `PROFILE_COMPILED` result shape;
6. read the unique bundle through the binding;
7. replay the bundle canonical payload, digest and exact Desired, Style,
   persistent-constraint and Session-constraint lineage; and
8. return the stable result without writes.

Repeated and concurrent reads must return the same result and create zero new
rows or versions. A completed Job without its exact bundle, or any malformed
Job/Attempt/binding/bundle graph, is authority corruption rather than an empty
or latest result.

## API failure contract

Errors retain the standard `code`, `message`, `request_id`, `details` shape and
must not disclose internal identifiers or graph differences:

- missing Job, missing binding or foreign owner: `404
DEMO_PROFILE_AUTHORITY_UNAVAILABLE`;
- `PENDING` or `RUNNING`: `409 DEMO_PROFILE_RESULT_NOT_READY`;
- `REJECTED`, `FAILED` or `CANCELLED`: `409
DEMO_PROFILE_RESULT_TERMINAL`;
- inconsistent completed authority: `503
DEMO_PROFILE_AUTHORITY_CORRUPT`.

The existing compile, active-profile and generic Job contracts remain
byte-compatible.

## Same-origin BFF boundary

Add same-origin routes:

```text
POST /api/demo/profile
GET  /api/demo/profile
```

They accept no browser-supplied upstream ID, bearer, digest, compiler version,
query override or idempotency key. The server registry may start profile
compilation only after the exact bound questionnaire is terminal
`COMPLETED`. It retains the random create idempotency key before the first
upstream await and reuses it after uncertain network outcomes.

The registry binds the exact Job ID, JobBinding digest, actor target authority
and eventual bundle result. Every upstream await uses compare-and-set checks
against the current opaque handle, Session and profile binding so logout,
expiry, configuration rotation or a newer action cannot revive stale state.
The BFF must use the dedicated exact result operation after Job completion and
must never call `/profiles/active`.

Browser JSON is restricted to:

```text
PENDING
PROFILE_READY
REJECTED
FAILED
CANCELLED
```

No Job, Session, actor, profile, bundle or authority ID/digest may enter browser
JSON, DOM, URL, storage or logs.

## Browser state machine

After questionnaire completion the same action generation automatically starts
one profile compilation:

```text
COMPLETED
-> PROFILE_STARTING
-> PROFILE_PENDING
-> PROFILE_READY | REJECTED | FAILED | CANCELLED | ERROR
```

Polling remains fixed at one second with at most 120 polls. Timeout is a
recoverable local error and never creates a second Job. Retry reuses the bound
Job and retained server-side key. End Demo remains serialized with pending
requests and invalidates all older responses.

The ready view states only that the preference profile is prepared. It does not
show profile content, a beauty score, hidden inference, internal authority, or
D06 controls.

## Change boundary

Allowed changes are limited to the D05 read service and dependency, Demo
response schema/router/tests, generated OpenAPI client, D11 server registry and
profile BFF, the existing interactive component/tests, and this contract.

Explicitly forbidden:

- migration or ORM changes;
- Job target/schema changes;
- Worker changes;
- `/profiles/active` semantic changes;
- D06–D12 implementation;
- Provider or private-input access;
- browser persistence, analytics or upstream identifier disclosure.

## Acceptance

Acceptance requires:

- real PostgreSQL tests for exact replay, owner isolation, pending, every
  terminal state, missing bundle, malformed completed authority and repeated
  read zero-write behavior;
- API tests for the four safe error classes and exact response shape;
- additive-only OpenAPI/generated-client drift validation;
- BFF tests for single-flight, retained idempotency, exact Job/result binding,
  compare-and-set races and browser non-disclosure;
- UI tests for automatic start, polling, recovery, terminal states, logout and
  stale-response suppression;
- Web lint, strict TypeScript, formatting, unit tests, production build and the
  focused Playwright real-flow scenario;
- Ruff, strict mypy, Gitleaks, diff check and one integrated-SHA CI pass.
