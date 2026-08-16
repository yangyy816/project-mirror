# P2-M2 Acceptance Evidence

## Status

- Milestone: `P2-M2 — Generation Batch and Provider Pipeline`
- State: `EXECUTING`
- Frozen entry SHA: `4a69f93f0d092afa0b520bbfb6e7d192e0f3dff1`
- Migration target: `0009_generation_batch_pipeline`
- External Gate: `EXTERNAL_VALIDATION_REQUIRED: IMAGE_GENERATION_PROVIDER`

## Mandatory evidence matrix

| Gate            | Required evidence                                     | Current status |
| --------------- | ----------------------------------------------------- | -------------- |
| Scope           | synthetic-only generation; no M3/public API           | PENDING        |
| Database        | `0008→0009→0008→0009`, drift and invariants           | PENDING        |
| Batch/item      | monotonic lifecycle, idempotency and concurrency      | PENDING        |
| Budget/cost     | row-lock admission, ceilings and append-only facts    | PENDING        |
| Worker          | reference-only, at-least-once, retry/cancel/reconcile | PENDING        |
| Raw storage     | private namespace, conflict, orphan/TTL cleanup       | PENDING        |
| Provenance      | actual Provider facts and immutable evidence          | PENDING        |
| Prompt/security | ephemeral redacted material, zero log/task leakage    | PENDING        |
| Provider        | approved controlled real-candidate benchmark          | NOT VERIFIED   |
| Supply chain    | no unapproved dependency/model; SBOM/license evidence | PENDING        |
| Regression      | P1/P2-M1, OpenAPI, Docker and zero-skip CI            | PENDING        |

No row may be marked PASS from a plan, Mock result or unexecuted command. A candidate Provider is
not production-approved by completing a benchmark, and benchmark output cannot become a released
asset in M2.

`P2_M2_GATE: NOT_EVALUATED`
