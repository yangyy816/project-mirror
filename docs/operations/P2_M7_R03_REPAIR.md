# P2-M7-R03 — T02 cross-platform Ruff formatting repair

## Bounded task contract

- `BOOTSTRAP_STATUS`: `OK`.
- `TASK_ID`: `P2-M7-R03`.
- `OBJECTIVE`: make the already-pushed T02 Python files conform to the CI Ruff formatter without changing their
  operation or redaction semantics.
- `WHY_DELEGATED`: the exact same code passed the local formatter but the authoritative Linux CI formatter rejected
  two line wraps; the defect must remain explicit rather than being hidden by a retry.
- `SCOPE` / `ALLOWED_FILES_OR_MODULES`: the two T02 Python files and this repair record only.
- `FORBIDDEN_SCOPE`: no workflow, schema, migration, dependency, Provider, CLI, database, API, M5/M6 behavior,
  production enablement, private input or test-semantic change.
- `DEPENDENCIES`: failed exact-SHA T02 candidate `ef71af8f78e4ab7aeda43263087e985c53c57cfd`, run `32590893026`.
- `INPUTS_AND_ASSUMPTIONS`: the failure is limited to Ruff's reported line wrapping; it is not a Python behavior,
  test, migration, Browser, dependency or security failure.
- `ACCEPTANCE_CRITERIA`: the two reported files satisfy CI formatting; Ruff lint, strict mypy, targeted tests and
  `git diff --check` remain successful; all closed M5/M6 and production boundaries remain unchanged.
- `VALIDATION_COMMANDS`: scoped Ruff format/lint, strict mypy, targeted pytest, `git diff --check`, then a new
  same-SHA CI run.
- `RECOMMENDED_AGENT`: Principal / Terra Medium implementation boundary.
- `RECOMMENDED_MODEL_TIER`: Terra Medium.
- `OUTPUT_FORMAT`: the P2-M7 common bounded-task output format in the execution protocol.
- `ESCALATION_CONDITION`: any non-format failure, required workflow change, semantic code change or closed-boundary
  conflict is `ESCALATION_REQUIRED`.

## Repair

- Wrap `SyntheticDatasetOperationService.__init__` and one test construction exactly as required by the CI Ruff
  formatter.
- Retain the T02 unknown-environment hard rejection and all deterministic tests.

## Preserved boundaries

- No database, provider, storage, CLI, public API, OpenAPI, migration, dependency, model, private input or runtime
  production capability is added or changed.
- P2-M5 fresh-study execution, P2-M6 release/revoke and production CLI enablement remain closed.

`P2_M7_R03: IMPLEMENTATION_IN_PROGRESS`
