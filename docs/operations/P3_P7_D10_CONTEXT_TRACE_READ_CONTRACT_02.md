# P3–P7 D10 Context and Trace Read Contract 02

```text
TASK: D10 — owner-bound Context and trace recall
TRACK: DEMO_PROTOTYPE
CONTRACT_ID: P3_P7_D10_CONTEXT_TRACE_READ_CONTRACT_02
STATUS: PRINCIPAL_FROZEN_FOR_IMPLEMENTATION
SUPERSEDES_ROUTE_BOUNDARY: P3_P7_D10_MEMORY_CONTEXT_CONTRACT_01
SCHEMA_CHANGE: NONE
ORM_CHANGE: NONE
PUBLIC_API_CHANGE: REQUIRED_QUERY_PARAMETER_ONLY
D02_PRIVATE_INPUT: NONE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

## Decision

Both existing read operations require an explicit timezone-aware `recall_at` query parameter:

```text
GET /api/v1/demo/sessions/{session_id}/context?recall_at=<RFC3339 timestamp>
GET /api/v1/demo/traces/{session_id}?recall_at=<RFC3339 timestamp>
```

The caller-supplied time is the sole expiry and as-of selection input. The router must not read the wall clock, infer a
time from request arrival, or choose an expired Context through an implicit fallback. Missing, malformed or timezone-naive
values fail closed.

Both routes authenticate the Demo actor, bind the requested session to that actor, and call the existing D10
`recall_context` authority. That authority revalidates the active Profile, Context expiry, event chain, lifecycle
invalidations and accepted-episode dependencies before returning.

The Context response preserves its frozen shape and maps the recalled Context digest to `compilation_digest`. The trace
response returns the same selected Context's digest as `evidence_digest` and its exact `context_compilation_id`. Neither
route creates or modifies Profile, Context, Event, Episode, Job or JobBinding authority.

## Failure semantics

- missing or invalid `recall_at`: `422`;
- unknown, unauthorized, expired or lifecycle-stale Context/session: `404 DEMO_MEMORY_AUTHORITY_UNAVAILABLE`;
- corrupt Context or ledger authority: `503 DEMO_MEMORY_AUTHORITY_CORRUPT`.

This contract does not authorize the queued Context compiler. Its durable explicit-as-of request authority remains
deferred until the D02 migration lease is released.
