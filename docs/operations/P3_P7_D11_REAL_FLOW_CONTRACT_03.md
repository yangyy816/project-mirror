# P3–P7 Demo D11 Real Flow Contract 03

## Decision status

```text
CONTRACT_ID: P3_P7_D11_REAL_FLOW_CONTRACT_03
TRACK: DEMO_PROTOTYPE
STATUS: PRINCIPAL_ACCEPTED_FOR_ISOLATED_IMPLEMENTATION
BASE_SHA: ff1fcc38f37c9d61b1b5729a9664048a45c2a42b
INTEGRATION_GATES: D03_TASK_ACCEPTED_AND_D11_CONTRACT_02_ACCEPTED
MIGRATION_CHANGE: NONE
PUBLIC_API_CHANGE: ADDITIVE_SESSION_SCOPED_ANALYSIS_ACTION_AND_COMPLETION_PROJECTION
PRODUCTION_AUTHORIZATION: NONE
REAL_USER_AUTHORIZATION: NONE
```

## Product slice

The second D11 real-flow slice is:

```text
OWNER_BOUND_DEMO_SESSION
-> SERVER_RESOLVED_CANONICAL_SOURCE
-> D03_ANALYSIS_JOB
-> COMPLETED_SELF_STATE_REFERENCE
```

It starts and observes D03 through the server-only Demo bridge. It does not run
M3 during tests, begin D04, expose authority IDs to the browser, or change D03
runtime and persistence semantics.

## Additive D03 action

The accepted `POST /api/v1/demo/analyses` contract remains unchanged for
existing callers. Add:

```text
POST /api/v1/demo/sessions/{session_id}/analysis
Idempotency-Key: required
request body: none
response: existing DemoJobAcceptedResponse (202)
```

The application service must derive the source from the active owner-bound
Session rather than accept a source override:

1. lock and revalidate the actor and Session;
2. require the exact `DemoSessionConfig/v1` identity binding;
3. replay current synthetic admission;
4. resolve the identity's `formal_canonical_asset_id` and digest; and
5. call the existing D03 create transaction, which repeats the same
   Session/identity/source checks before persisting the run.

The final D03 transaction remains the only creation authority. A resolution
read cannot authorize a run by itself. Existing actor/key idempotency,
concurrent winner, Job/Run/Binding atomicity, queue routing and reconciliation
remain unchanged.

## Completed SelfState projection

The existing `GET /api/v1/demo/analyses/{analysis_id}` response gains the
backward-compatible nullable field:

```text
self_state_id: DemoId | null
```

Exact state union:

- `PENDING`: `observation_digest` and `self_state_id` are null;
- `SUPPORTED` or `UNSUPPORTED`: both fields are non-null and identify the
  Observation and SelfState published by the same analysis transaction;
- failed, rejected or cancelled jobs retain the existing non-success response.

Snapshot reads must replay the unique Observation, Baseline and SelfState and
their actor/session/parent links. A completed Job with any missing, duplicate or
cross-bound row is authority corruption, never a partial success. These IDs are
for the authenticated server-to-server contract and are not browser output.

## Browser bridge

Add one same-origin BFF route:

```text
POST /api/demo/analysis
GET  /api/demo/analysis
```

Both methods reject Authorization, query and body overrides and require the
existing opaque HttpOnly Session handle. Responses use `Cache-Control:
no-store` and contain no upstream ID or digest.

`POST` creates or replays the analysis through the new session-scoped API. The
server registry allocates and retains one random create idempotency key before
the upstream call. An uncertain response keeps that same key for retry; the
same handle cannot create a second analysis. The upstream response is accepted
only when status, capability, Job ID, target type, analysis ID and authority
digest shapes all match the expected D03 contract. Browser response:

```json
{ "status": "PENDING" }
```

`GET` first reads the bound Job. Pending/running state projects to `PENDING`.
Terminal failure projects only `CANCELLED`, `REJECTED` or `FAILED`. A completed
Job causes one analysis snapshot read; the bridge verifies the internal Session
ID, analysis ID, observation digest and SelfState ID before retaining the
SelfState reference server-side. Browser response:

```json
{
  "status": "COMPLETED",
  "analysis_state": "SUPPORTED | UNSUPPORTED",
  "self_state": "READY"
}
```

Job ID, analysis ID, Session ID, source Asset ID, SelfState ID, actor/identity
ID, bearer and authority digests must not enter browser JSON, DOM, URL, storage
or logs. Logout, expiry or configuration-fingerprint mismatch deletes the
entire server registry entry, including analysis references.

Cancellation is intentionally outside this slice. It will use the existing
Job cancel authority when a product UI actually exposes cancellation; absence
of a browser cancel action does not weaken the Worker/Job cancellation model.

## No-migration boundary

No database change is required. The accepted schema already has immutable
Run source fields, one Observation per Run, owner-bound Baseline and SelfState
links, and atomic completion. This slice only adds a server-resolved application
entry point, a read projection and ephemeral BFF references.

## Acceptance

- the original analysis endpoint remains byte-for-byte OpenAPI compatible;
- the additive action rejects inactive/cross-actor Sessions and cannot accept a
  source override;
- final D03 create revalidates the resolved exact source in its own transaction;
- same key replay, different-session collision and concurrent winner pass;
- pending and complete snapshot unions are exact; partial/cross-bound graphs
  fail closed;
- browser POST retry reuses one server idempotency key;
- browser poll validates Job target and completed analysis binding;
- no forbidden ID, digest, bearer or private value reaches browser surfaces;
- OpenAPI/generated client, Ruff, strict mypy, targeted PostgreSQL, Web tests,
  build, Playwright, Gitleaks and one integrated-SHA CI pass before acceptance.
