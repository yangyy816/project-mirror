# P2-M7-R08 — T04 runbook formatting repair

- `BOOTSTRAP_STATUS`: `OK`.
- `TASK_ID`: `P2-M7-R08`.
- `OBJECTIVE`: correct the exact Prettier failure from T04 candidate
  `67d005e3b8356b452c4e4291ed46aa81240bf3cf` without changing T04 behavior.
- `WHY_DELEGATED`: the same-SHA quality job stopped at runbook formatting; retrying without a diff would conceal a
  deterministic defect.
- `SCOPE` / `ALLOWED_FILES_OR_MODULES`: `P2_M7_OPERATIONS_RUNBOOK.md`, this repair record, and no other files.
- `EXPECTED_CHANGE`: canonical Prettier formatting only.
- `FORBIDDEN_SCOPE`: workflow/Gate changes, Python behavior, schema/migration, Provider, CLI, dependency, OpenAPI,
  M5/M6, production, private input and test-semantic changes.
- `DEPENDENCIES`: failed same-SHA run `32619223752`.
- `INPUTS_AND_ASSUMPTIONS`: CI logs identify only `docs/operations/P2_M7_OPERATIONS_RUNBOOK.md` as the quality failure;
  the missing Playwright evidence upload is a post-failure cascade, not an independently asserted defect.
- `ACCEPTANCE_CRITERIA`: `pnpm.cmd format:check` passes; the runbook's cost, redaction and no-deployment boundaries are
  byte-for-byte semantically unchanged after formatting.
- `VALIDATION_COMMANDS`: scoped Prettier write/check, `pnpm.cmd format:check`, `git diff --check`, targeted Python
  regression, then a fresh same-SHA CI run.
- `SECURITY_NOTES`: formatting may not add a diagnostic payload, credential, URL, object key or private path.
- `PRIVACY_NOTES`: synthetic-only and no-user-data boundary remains unchanged.
- `DATA_NOTES`: no authority row, research input or fixture changes.
- `LICENSE_NOTES`: no dependency, model or artifact changes.
- `ROLLBACK`: disable the unaccepted candidate; no database state changed.
- `RECOMMENDED_AGENT`: Principal / Terra Medium.
- `RECOMMENDED_MODEL_TIER`: Terra Medium.
- `ESCALATION_CONDITION`: any behavior, workflow or Gate change is `ESCALATION_REQUIRED`.
- `OUTPUT_FORMAT`: common P2-M7 bounded-task report.

`P2_M7_R08: IMPLEMENTATION_IN_PROGRESS`
