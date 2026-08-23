# P2-M7-R14 — real internal CLI composition repair

## Status

`PASS`

## Finding

The T08 final review found that the installed `mirror-dataset` entrypoint constructs an empty
`SyntheticDatasetOperationService`. Positive command tests inject fake backends, so the real entrypoint cannot reach
the already accepted batch-operation backend or PostgreSQL cost read model. The CLI correctly fails closed, but it is
not yet the internal application-service control plane required by ADR-051.

## Bounded task contract

- `TASK_ID`: `P2-M7-R14`
- `OBJECTIVE`: compose the real non-production `mirror-dataset` entrypoint with the accepted PostgreSQL-backed batch
  status/cancel and cost-summary application services while retaining capability-specific fail-closed behavior.
- `WHY_DELEGATED`: not delegated; the Principal owns the integration boundary and protected concurrent worktree.
- `SCOPE`: first-party CLI composition, accepted operation service/backends, explicit database-environment handling,
  real entrypoint/subprocess PostgreSQL tests, and R14 evidence records.
- `ALLOWED_FILES_OR_MODULES`: `mirror_dataset.py`, `operations.py`, `operations_integration.py`, necessary bounded
  changes in `operations_projection.py`, P2-M7 CLI/PostgreSQL/projection tests, this repair record, acceptance,
  execution protocol, runbook, and autonomous log.
- `EXPECTED_CHANGE`: the real CLI creates the approved async engine/session boundary only after non-production and
  explicit database configuration checks; batch status/cancel use the accepted application backend; cost summary uses
  the accepted PostgreSQL read model; unavailable capabilities remain stably unavailable.
- `FORBIDDEN_SCOPE`: CLI SQL, new schema/migration or persistence authority, admin/public HTTP, OpenAPI/generated
  contract change, new dependency, Provider/storage/task-runner call, production enablement, M5 research execution,
  M6 release/revoke, provenance/QA authority invention, or weaker authorization/redaction/recovery semantics.
- `DEPENDENCIES`: R13 accepted at `690dd78` / run `32630571003`; accepted T02-T07/R12 application contracts; ADR-051.
- `INPUTS_AND_ASSUMPTIONS`: PostgreSQL remains authoritative; the environment and database URL are explicit operator
  inputs; no operator-auth role model is added; existing actor/reason/request/expected-state validation remains the
  command boundary.
- `ACCEPTANCE_CRITERIA`: without fake injection, the installed entrypoint performs batch status/cancel and cost summary
  against a real non-production PostgreSQL database through application services; cost output preserves actual,
  estimated, pending, unavailable, and per-currency separation; provenance/QA remain unavailable; production rejects
  before engine/session construction; retry, audit, redaction, and stale-state guarantees remain intact; CLI contains
  no direct SQL.
- `VALIDATION_COMMANDS`: focused real-entrypoint/subprocess PostgreSQL tests, production/no-config/unavailable/redaction
  negative tests, full P2-M7 suite, Ruff, strict mypy, migration lifecycle, OpenAPI drift, complete Python/TypeScript/
  Docker/Gitleaks/license/SBOM Gate, same-SHA GitHub Actions, eight-artifact inspection, independent security review,
  and independent Sol final review.
- `SECURITY_NOTES`: database configuration and failure details must not be rendered; production must reject before any
  connection attempt; output remains on the existing fixed allowlist.
- `PRIVACY_NOTES`: synthetic authority IDs and aggregate costs only; no image, Prompt, object key, URL, Provider raw
  payload, credential, private path, or real-user data.
- `DATA_NOTES`: no new authority or migration; mutations and reads use the existing PostgreSQL transaction/read-model
  boundaries.
- `LICENSE_NOTES`: no dependency, model, weight, dataset, or external-service change.
- `ROLLBACK`: remove the unaccepted real composition and retain the existing fail-closed empty service; no schema
  rollback.
- `RECOMMENDED_AGENT`: Principal bounded implementation.
- `RECOMMENDED_MODEL_TIER`: Terra High because the frozen implementation combines async resource lifecycle,
  PostgreSQL transactions, subprocess behavior, and fail-closed recovery paths.
- `ESCALATION_CONDITION`: any need for a new table, migration, role/auth authority, public API, dependency, cost
  semantic, production capability, M5/M6 behavior, or direct CLI infrastructure authority stops R14 and requires
  forward change control.
- `OUTPUT_FORMAT`: standard Project Mirror bounded-task report.

R14 does not accept T08 or evaluate the M7 Gate. Those decisions require R14 exact-SHA evidence, artifact inspection,
independent security/privacy/license review, independent Sol final review, and Principal acceptance.

## Local implementation evidence

- The real non-production entrypoint now reads only the explicit
  `MIRROR_DATASET_DATABASE_ENVIRONMENT` and `MIRROR_DATASET_DATABASE_URL` configuration names, rejects production
  before engine/session construction, and delegates engine/session lifetime to one bounded composition module.
- The composition registers only the accepted `GenerationBatchService` status/cancel backend and
  `PostgresCostSummaryReadModel`. Provenance and QA remain capability-specific unavailable; no SQL, Provider, storage,
  task-runner, HTTP, public API, migration, dependency, model, M5 or M6 path was added.
- Cost output uses typed nested aggregates and preserves actual, estimated, pending and unavailable categories plus
  per-currency amounts. Database configuration and failures are converted to fixed result codes and are never rendered.
- Real subprocess tests against PostgreSQL prove status, stale-state rejection, cancellation, exact replay with one
  authoritative audit effect, cost projection, read-only behavior, unavailable provenance/QA, and configuration
  redaction. The complete focused P2-M7 suite reports `77 passed`, zero skip.
- The full isolated Linux PostgreSQL/Redis/Celery regression reports `809 passed` with one existing optional
  private-runtime skip; the Node sanitizer suite reports `16 passed`. Ruff format/lint and strict mypy over `130`
  source files pass. Fresh migration, `0014 -> 0013 -> 0014`, Alembic check, contract drift, TypeScript lint/typecheck/
  tests/build and Playwright `5/5` pass.
- Docker Compose configuration, API/Worker/Web builds, five-service health, API live/ready, Web, Celery ping and
  container Alembic check pass. The built image rejects production as `operation_production_disabled`; a configured
  non-production lookup reaches PostgreSQL and returns `operation_target_not_found` for an absent opaque target.
- Python and Node dependency audits report zero known vulnerabilities after restoring the repository-locked
  `pip==26.2.1`; license inventories and a CycloneDX 1.6 SBOM were regenerated. Gitleaks 8.28.0 full history scans
  `292` commits and reports no leaks; its exact 15-path candidate-index `--no-git` scan also reports no leaks.
- Repo-wide `pnpm check` reaches only the formatter failure in protected pre-existing `AGENTS.md` and
  `docs/operations/MODEL_ROUTING_POLICY.md`; R14 does not modify them. All applicable TypeScript sub-gates and
  task-owned formatting checks pass independently. Same-SHA CI remains authoritative for the clean candidate tree.

`P2_M7_R14: READY_FOR_TRACKED_EVIDENCE`

`P2_M7_T08: FAIL_AT_9584177_FINAL_REVIEW`

`P2_M7_GATE: NOT_EVALUATED`

## Tracked evidence and independent review

- Candidate `c15fd29340552f7c4d4b3348f862da6deb242986` completed exact-SHA GitHub Actions run `32636243642`,
  attempt 1. `quality-and-integration`, `secret-scan` and `docker-validation` all succeeded.
- The quality job passed Ruff, strict mypy over 130 source files, PostgreSQL migration lifecycle/check, Linux Celery,
  full Python (`814 passed` and one existing optional private-runtime skip), TypeScript/build, five Browser Integration
  tests, unchanged contracts, dependency/license audits and CycloneDX 1.6 SBOM generation. The fixed M7 evidence slice
  records 75 passes, zero failure/error/skip and eight passed boundary checks.
- Principal inspected all eight unexpired artifacts and 12 fixed-relative members. They bind the exact candidate,
  migration head `0014_m5_eval_authority` and unchanged OpenAPI digest. SARIF has zero results; Docker has five
  running/healthy services; Playwright acquisition succeeded on attempt 1; Celery has no failure record. Protected
  path/payload/image/credential scans are zero, and the task-owned inspection directory was deleted.
- Independent security/privacy/data/supply-chain review returned `PASS` with no repair. Independent Sol final review
  returned `PASS_FOR_R14_EXACT_SHA_PREREQUISITE` and closed the prior real-composition and replay/audit findings.
  Principal independently reviewed and accepts the actual R14 diff subject to the milestone acceptance closure's own
  same-SHA Gate.
- The two new real PostgreSQL subprocess composition tests ran in the exact-SHA full Python collection but are not
  enumerated by the fixed six-file targeted M7 JUnit slice. Both reviewers treated this as non-blocking evidence
  granularity; no missing execution or Gate waiver is claimed.

`P2_M7_R14: PASS_PENDING_ACCEPTANCE_CLOSURE_CI_AT_C15FD29_RUN_32636243642_ATTEMPT_1`

`P2_M7_T08: PASS_PENDING_ACCEPTANCE_CLOSURE_CI_AT_C15FD29_RUN_32636243642_ATTEMPT_1`

`P2_M7_GATE: PASS_PENDING_ACCEPTANCE_CLOSURE_CI`

`P2_M7_STATE: EXECUTING`

`P2_M7_NEXT_ACTION: ACCEPTANCE_CLOSURE_CI`

## Acceptance closure confirmation

- Documentation-only closure `3af45337149c791b6c9905db2d7e3b673a83478c` passed exact-SHA run
  `32638417120`, attempt 1, across all three mandatory jobs.
- Principal inspected all eight unexpired artifacts and 12 fixed-relative members. Exact SHA, migration head, OpenAPI,
  M7 tests/checks, Gitleaks, Docker, Playwright, Celery, license/SBOM and protected-content evidence are consistent with
  the accepted R14 candidate. Inspection/cache roots were deleted and verified absent.
- R14 acceptance is effective. The milestone technical Gate is `PASS`; production remains `NOT_DEPLOYED`,
  provenance/QA remain unavailable, and M5/M6 boundaries are unchanged. The separate freeze-state commit still requires
  its own same-SHA remote Gate before final remote freeze evidence is reported.

`P2_M7_ACCEPTANCE_CLOSURE: PASS_AT_3AF4533_RUN_32638417120_ATTEMPT_1`

`P2_M7_R14: PASS_AT_C15FD29_RUN_32636243642_ATTEMPT_1`

`P2_M7_T08: PASS_AT_C15FD29_RUN_32636243642_ATTEMPT_1`

`P2_M7_GATE: PASS`

`P2_M7_STATE: PASS`

`P2_M7_FREEZE_STATE: PENDING_SAME_SHA_CI`
