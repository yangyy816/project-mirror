# P2-M2 Acceptance Evidence

## Status

- Milestone: `P2-M2 — Generation Batch and Provider Pipeline`
- State: `EXECUTING`
- Frozen entry SHA: `4a69f93f0d092afa0b520bbfb6e7d192e0f3dff1`
- Migration target: `0009_generation_batch_pipeline`
- External Gate: `EXTERNAL_VALIDATION_REQUIRED: IMAGE_GENERATION_PROVIDER`

## Mandatory evidence matrix

| Gate            | Required evidence                                     | Current status      |
| --------------- | ----------------------------------------------------- | ------------------- |
| Scope           | synthetic-only generation; no M3/public API           | PENDING             |
| Database        | `0008→0009→0008→0009`, drift and invariants           | T02 PASS            |
| Batch/item      | monotonic lifecycle, idempotency and concurrency      | T02/T03 PASS        |
| Budget/cost     | row-lock admission, ceilings and append-only facts    | T02/T03 PASS        |
| Worker          | reference-only, at-least-once, retry/cancel/reconcile | PENDING             |
| Raw storage     | private namespace, conflict, orphan/TTL cleanup       | PENDING             |
| Provenance      | actual Provider facts and immutable evidence          | T02 FOUNDATION PASS |
| Prompt/security | ephemeral redacted material, zero log/task leakage    | T03 PASS            |
| Provider        | approved controlled real-candidate benchmark          | NOT VERIFIED        |
| Supply chain    | no unapproved dependency/model; SBOM/license evidence | PENDING             |
| Regression      | P1/P2-M1, OpenAPI, Docker and zero-skip CI            | PENDING             |

No row may be marked PASS from a plan, Mock result or unexecuted command. A candidate Provider is
not production-approved by completing a benchmark, and benchmark output cannot become a released
asset in M2.

`P2_M2_GATE: NOT_EVALUATED`

## T02 accepted evidence

- Forward migration `0009_generation_batch_pipeline` adds the six ADR-025 authorities without
  modifying `0001` through `0008` or public OpenAPI.
- Real PostgreSQL executed fresh upgrade, `0008→0009→0008→0009`, `alembic check`, 14 migration and
  invariant tests, and the concurrent two-writer cost race with zero skip.
- PostgreSQL rejects incomplete batch queueing, inconsistent terminal aggregates, incomplete or
  mismatched `RAW_STORED` evidence, budget overspend, invalid timestamp/reference/actor shapes and
  mutation of append-only authority.
- A downgrade containing M2 authority/evidence fails closed with
  `0009 downgrade would discard generation authority or evidence`.
- Ruff, strict mypy and diff checks pass. No dependency, model, real image, Provider credential,
  network call or public API was added.

`P2_M2_T02: TASK_ACCEPTED`

## T03 accepted evidence

- Typed application/repository contracts implement concurrent idempotent batch creation,
  exact item/Job creation, queue/status/cancel transitions, concurrency-limited reservation,
  retry and remaining-budget admission, safe failure finalization, idempotent cost posting and
  atomic `source + generation evidence + cost → RAW_STORED` completion without adding a public API
  or Celery/Provider SDK dependency.
- Prompt materialization requires the matching leased JobAttempt, exact lease token and an
  unexpired lease. `EphemeralPrompt` is bounded, redacted from `str`/`repr` and rejects
  serialization; invalid or expired leases return only the safe
  `prompt_material_unavailable` code.
- `P2-M2-R01` aligns generation evidence and cost trigger locking with application transitions as
  `GenerationBatch → GenerationItem`. A deterministic PostgreSQL regression holds the batch lock,
  proves the cost writer is waiting on that authority, then completes item/batch finalization
  without a deadlock before the cost writer commits.
- `P2-M2-R02` permits Provider safety reason facts using the already accepted hyphenated or
  underscored canonical shape (`^[a-z][a-z0-9_-]{2,63}$`) without transforming the actual fact.
- Principal validation passed Ruff format/lint, strict mypy, 19 real-PostgreSQL migration,
  invariant/concurrency and application-service tests, plus `alembic check` with zero drift.
  No dependency, model, real-person image, live call or public contract was added.

`P2_M2_T03: TASK_ACCEPTED`
