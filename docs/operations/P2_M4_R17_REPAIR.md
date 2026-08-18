# P2-M4-R17 Data-Rights Lock-Order Repair

## Status and authority

- Status: `READY_FOR_TRACKED_EVIDENCE`.
- Trigger: P2-M4 acceptance closure run `32166922750` failed in the Phase 1 data-rights vertical test with a
  PostgreSQL deadlock.
- Authority: the accepted Phase 1 data-rights lifecycle, P2-M4 technical `PASS`, and the existing P2-M4
  acceptance closure sequence.
- Boundary: forward repair only. No schema, migration, public API, authorization, deletion semantics, Phase 1
  frozen evidence or P2-M4 research result changes are permitted.
- P2-M5, production geometry, real-user facial processing and QuestionBank release remain closed.

## Reproduced failure

The failure was reproduced against the live Compose PostgreSQL and Celery topology. A duplicate account-deletion
delivery could race with evidence insertion or a data-export delivery in either inverse order:

```text
evidence unique row -> account deletion request
account deletion completion -> account deletion request -> evidence row

account deletion export cleanup -> export request -> export job via trigger
data export processing -> export job -> export request
```

The first bounded replay passed once and reproduced a PostgreSQL `DeadlockDetected` on the second run. This is a
real latent concurrency defect, not a documentation-only closure failure or a basis for classifying the test as
flaky.

## Repair contract

- `BOOTSTRAP_STATUS`: `OK`.
- `TASK_ID`: `P2-M4-R17`.
- `OBJECTIVE`: establish one lock order for account-deletion authority, data-export job authority, target request
  rows and append-only evidence.
- `WHY_DELEGATED`: not delegated; the repair collides with the Principal-owned acceptance closure.
- `SCOPE`: account deletion application service, focused PostgreSQL concurrency regression, and forward closure
  evidence.
- `ALLOWED_FILES_OR_MODULES`: `account_deletion/service.py`, its focused tests, P2-M4 acceptance/log/MEMORY
  closure records.
- `EXPECTED_CHANGE`: evidence transactions lock their account-deletion request before insertion; export cleanup
  locks deterministic data-export jobs before data-export request rows.
- `FORBIDDEN_SCOPE`: historical migration edits, trigger weakening, retry masking, schema/API changes, deletion
  policy changes, production enablement, P2-M5 work or `.tmp` access.
- `DEPENDENCIES`: PostgreSQL row locking and the immutable data-rights request-to-job authority.
- `INPUTS_AND_ASSUMPTIONS`: `job_id` and owner authority on data-rights request rows are immutable; storage delete
  operations remain idempotent.
- `ACCEPTANCE_CRITERIA`: duplicate account-deletion processing is idempotent without deadlock; concurrent live
  Celery delivery and direct processing complete; exactly one evidence row remains per target; all prior
  data-rights semantics and tests remain unchanged.
- `VALIDATION_COMMANDS`: focused PostgreSQL tests, repeated live Compose/Celery vertical flow, complete API/Worker
  pytest, Ruff, strict mypy, contracts check, Alembic lifecycle/check, Docker health/smoke and exact-SHA Actions.
- `SECURITY_NOTES`: trigger and owner checks remain intact; no exception swallowing or weaker isolation is allowed.
- `PRIVACY_NOTES`: no user payload, image, Prompt, object key or database row is added to committed evidence.
- `DATA_NOTES`: no migration or authority-row rewrite.
- `LICENSE_NOTES`: no dependency or model artifact change.
- `ROLLBACK`: revert the service/test/doc repair before any dependent freeze-state commit.
- `RECOMMENDED_AGENT`: Principal / Terra High implementation boundary.
- `RECOMMENDED_MODEL_TIER`: Terra High because transaction ordering and duplicate delivery are involved.
- `OUTPUT_FORMAT`: standard bounded-task report plus exact-SHA CI evidence.
- `ESCALATION_CONDITION`: any need to change schema, triggers, public contracts, authorization or deletion policy.

## Frozen order

```text
account deletion request authority
-> data-export job authority (stable Job.id order)
-> data-export request authority (stable request id order)
-> append-only deletion evidence
```

## Local evidence

- The unmodified acceptance closure SHA `75c59ed39be34102d2e6e042a248801c17861cfb` failed run `32166922750`
  only in `quality-and-integration`; Docker and Gitleaks passed. The PostgreSQL trace confirmed a real tuple-lock
  deadlock rather than a stale tool state.
- Before repair, the live Compose/Celery vertical flow reproduced `DeadlockDetected` on bounded replay 2.
- After repair, the focused account-deletion/data-export PostgreSQL suite passed 9 tests and the same live
  Compose/Celery vertical flow passed 20 consecutive runs.
- A fresh PostgreSQL database plus isolated Redis DB/Celery worker completed the full API/Worker suite. Ruff,
  strict mypy, complete pnpm/contracts, fresh `->0013`, `0013->0012->0013`, `alembic check`, Docker build,
  five-service health and API/Web smoke all passed.
- No dependency, model, image, migration, OpenAPI artifact or private path was added.

The tracked repair candidate and exact-SHA Actions/artifact review remain mandatory.

`P2_M4_R17_GATE: READY_FOR_TRACKED_EVIDENCE`
