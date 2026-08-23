# P2-M7-R14 — real internal CLI composition repair

## Status

`EXECUTION_READY`

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
