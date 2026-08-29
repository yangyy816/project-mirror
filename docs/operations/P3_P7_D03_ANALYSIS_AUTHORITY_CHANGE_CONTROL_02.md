# P3–P7 Demo D03 Analysis Authority Change Control 02

```text
CHANGE_CONTROL_ID: P3_P7_D03_CC_02
TRACK: DEMO_PROTOTYPE
STATUS: EXECUTING
SUPERSEDES_HISTORY: NO
PRODUCTION_AUTHORIZATION: NONE
```

## Context

The accepted D03 authority persists the AnalysisRun, formal Job and
DemoJobBinding before Celery dispatch. Two forward recovery gaps remain in the
application wiring:

1. a broker/API failure after commit can leave a PENDING Job undispatched;
2. a worker loss after claim can leave a RUNNING Job after its lease expires.

Neither gap permits fake runtime evidence, Provider fallback or an in-place
`FAILED -> PENDING` transition.

## Decision

- The PENDING Job plus immutable DemoJobBinding/AnalysisRun is the durable
  dispatch intent. Creating or replaying the same semantic request may safely
  dispatch the same reference-only message again while the Job is PENDING.
- A maintenance reconciler may redispatch PENDING Jobs and RUNNING Jobs whose
  lease is expired. Duplicate messages remain safe because PostgreSQL claim is
  serialized.
- D03 retry is bounded to three JobAttempts. An expired current attempt is
  append-only terminalized as `FAILED/D03_LEASE_EXPIRED` before a new attempt
  is created. The Job remains RUNNING; it never transitions through FAILED or
  PENDING during retry.
- Expiry of the third attempt terminalizes the Job and current attempt as
  `FAILED/D03_LEASE_RETRY_EXHAUSTED`.
- Completion, rejection, failure and cancellation remain terminal and cannot
  publish after a lease is superseded or expired.
- The forward migration is `demo_0011_d03_job_recovery`, down revision
  `demo_0010_d03_analysis_run`. Downgrade fails closed when multi-attempt D03
  evidence exists.

## Boundaries

- No M3 runtime/model handle is materialized by this change.
- No Provider or public-network call is introduced.
- No public request/response schema or OpenAPI operation is changed.
- D03 remains `TASK_ACCEPTED_DOMAIN_READY_ROUTE_PENDING` until this repair is
  integrated and validated. Fresh runtime evidence remains deferred.
