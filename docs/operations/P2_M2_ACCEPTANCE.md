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
| Scope           | synthetic-only generation; no M3/public API           | T06 PASS            |
| Database        | `0008→0009→0008→0009`, drift and invariants           | T02 PASS            |
| Batch/item      | monotonic lifecycle, idempotency and concurrency      | T02/T03 PASS        |
| Budget/cost     | row-lock admission, ceilings and append-only facts    | T02/T03 PASS        |
| Worker          | reference-only, at-least-once, retry/cancel/reconcile | T05 PASS            |
| Raw storage     | private namespace, conflict, orphan/TTL cleanup       | T04 PASS            |
| Provenance      | actual Provider facts and immutable evidence          | T02 FOUNDATION PASS |
| Prompt/security | ephemeral redacted material, zero log/task leakage    | T03/T06 PASS        |
| Provider        | approved controlled real-candidate benchmark          | NOT VERIFIED        |
| Supply chain    | no unapproved dependency/model; SBOM/license evidence | T06 LOCAL PASS      |
| Regression      | P1/P2-M1, OpenAPI, Docker and zero-skip CI            | T06 LOCAL PASS      |

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

## T04 accepted evidence

- The first-party synthetic storage port now supports bounded immutable create-if-absent,
  inspect, stream and exact-reference delete. Mock remains deterministic and zero-network;
  Tencent remains an explicit fail-closed candidate.
- `LocalSyntheticRawStorageProvider` is development/test infrastructure only. It maps opaque
  references through a one-way digest into `internal-synthetic/v1/raw`, atomically installs a
  payload/metadata object directory, rejects traversal, symlinks, unexpected members, corrupt
  metadata, size/checksum mismatch and conflicting replay, and removes only an exact validated
  object directory. No object key crosses the adapter boundary.
- Raw references are deterministic per item/attempt without exposing either identifier.
  PostgreSQL advisory locking coordinates raw completion and failed-attempt orphan cleanup after the common
  `batch → item → job/attempt` order.
- Retention cleanup leaves `SyntheticSourceObject` authority intact, deletes only the blob and
  appends one immutable deletion-evidence row. A delete-before-commit crash is recovered as an
  idempotent `not_found` fact; repeated cleanup does not rewrite evidence. Orphan deletion requires
  a matching failed, quiescent attempt and refuses active work or a referenced object.
- Principal validation passed Ruff format/lint, strict mypy and 51 Linux tests across Provider,
  production config, T02/T03 PostgreSQL invariants/concurrency, raw storage integrity, orphan/TTL
  reconciliation and crash retry with zero skip. No dependency, model, real-person image, live
  call, public API or migration was added.

`P2_M2_T04: TASK_ACCEPTED`

## T05 accepted evidence

- `SyntheticGenerationTaskMessage` contains only item, Job, request and schema references. The
  Celery-independent executor resolves the exact PostgreSQL lease, materializes Prompt only at the
  Provider call boundary, persists actual cost before raw completion, and makes duplicate delivery
  a safe no-op.
- LocalTaskRunner and Celery both implement the same first-party dispatcher port. Celery uses late
  acknowledgement, worker-lost recovery, bounded retry and the dedicated `mirror.synthetic` queue;
  reconciliation redispatches only pending or expired exact references.
- CI/development Celery uses the explicit local private synthetic adapter on the shared private
  volume, not a task-local in-memory store. Production still requires generation and synthetic
  storage to be disabled. Candidate Tencent adapters remain fail closed and no live network path,
  dependency, model or public API was added.
- `P2-M2-R03` fixes terminal aggregation so a cancelled single-item batch cannot be mislabeled
  `FAILED` after its expired lease quiesces. `P2-M2-R04` maps database IDs to canonical first-party
  policy/template references and turns invalid Prompt authority into a redacted domain rejection.
- Principal validation passed Ruff and strict mypy across API/Worker source, deterministic failure
  tests for Provider/storage/database paths, and 22 Linux tests with zero skip across real
  PostgreSQL, Redis/Celery, exact reservation concurrency, stale-lease recovery, cancellation,
  cost preservation, immutable raw storage, duplicate delivery and cross-process blob reopening.
  The isolated worker and database were removed after zero active connections; all five Compose
  services were then updated to the candidate image/configuration and returned healthy.

`P2_M2_T05: TASK_ACCEPTED`

## T06 accepted evidence

- Independent security evaluation proves that `SyntheticGenerationTaskMessage` contains exactly
  item, Job, request and schema references and rejects Prompt, bytes, image, URL, policy payload,
  object key, credential and secret fields. AST/source scans reject network/Provider SDK imports,
  literal external URLs and sensitive logging paths across the M2 application and Worker source.
- The same evaluation proves that internal P2 contracts leave OpenAPI and generated TypeScript
  unchanged, production generation/storage remain disabled, and M2 does not create M3 QA,
  SyntheticIdentity, variant, QuestionBank release or real-user processing authority.
- `P2-M2-R05` removes the raw Provider/storage exception chain from the generic Celery retry
  fallback. Its regression asserts the precise safe exception type/message, no `__cause__`, and no
  Provider response detail in the surfaced failure.
- Principal validation passed Ruff format/lint across 156 files, strict mypy across 98 sources,
  contract drift, complete `pnpm check` including 54 Web tests and Next build, and diff checks.
  Fresh Linux containers passed 307 API tests plus 27 Worker tests with zero skip against isolated
  PostgreSQL, Redis and a real Celery worker, including partial failure, budget/retry, cancellation,
  duplicate delivery, stale lease, orphan cleanup, provenance and storage integrity paths.
- Both isolated databases, the dedicated Redis test DB and the temporary Worker container were
  removed after testing; the five normal Compose services returned healthy. Windows host pytest
  could not use either the pre-existing or newly isolated temp directory because of runtime ACLs,
  so it is not claimed as evidence; the zero-skip Docker/Linux run is authoritative.
- No dependency, model artifact, real-person fixture, live Provider call, public API or migration
  was added. The controlled real-Provider benchmark remains the explicit T07 external Gate.

`P2_M2_T06: TASK_ACCEPTED`

## T07 external Provider Gate assessment

- The Provider registry still describes Tencent/image-generation implementations as candidates
  that fail closed. No Adapter is approved for a live call and no real Provider credential is
  present or required for deterministic M2 implementation.
- The model/data license registry keeps the future image-generation Provider at `CANDIDATE` and
  `PRODUCTION_BLOCKED`: exact model terms, training/data terms, region, retention, public training,
  subprocessors, deletion, output rights, safety and cost evidence remain unknown.
- A Mock result cannot satisfy this Gate, and calling an unapproved Provider would violate the M2
  execution contract. T07 therefore records no fabricated benchmark, output or cost fact.
- T08 may still produce same-SHA deterministic CI and independent review evidence, but M2 can be at
  most `CONDITIONAL`, cannot become `PASS`/`FROZEN`, and cannot open M3 until this external Gate is
  completed under separate approval.

`P2_M2_T07: BLOCKED`

`EXTERNAL_VALIDATION_REQUIRED: IMAGE_GENERATION_PROVIDER`

## T08 candidate evidence implementation

- `mirror.p2-m2.ci-evidence/v1` binds a full candidate SHA, unique `0009` migration head, OpenAPI
  digest, zero-failure/error/skip JUnit summary and seven required M2 deterministic checks. Its
  external Provider field is deliberately fixed to `external_validation_required` with
  `production_approved=false`; CI cannot manufacture Provider approval.
- The Linux CI Celery worker now subscribes to `mirror.synthetic`, matching Compose and allowing
  the existing full Python gate plus the dedicated M2 round trip to execute instead of timing out.
- Local isolated Linux validation passed all 37 evidence cases with zero skip and generated a
  readable allowlisted artifact. Same-SHA GitHub Actions and independent final review remain
  pending, so this section is not yet a T08 acceptance or Milestone Gate decision.

`P2_M2_T08_LOCAL_EVIDENCE: PASS`

`P2_M2_T08_REMOTE_EVIDENCE: PENDING`
