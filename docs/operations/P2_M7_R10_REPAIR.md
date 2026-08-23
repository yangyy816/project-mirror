# P2-M7-R10 — Compose JSON-lines artifact repair

- `BOOTSTRAP_STATUS`: `OK`.
- `TASK_ID`: `P2-M7-R10`.
- `OBJECTIVE`: accept Docker Compose JSON Lines status output in the R09 allowlisted artifact sanitizer.
- `WHY_DELEGATED`: R09 exact-SHA run `32620673480` passed all quality gates but failed only because Compose emitted one JSON
  object per line rather than one JSON array.
- `SCOPE` / `ALLOWED_FILES_OR_MODULES`: CI artifact sanitizer, its focused test and this repair record only.
- `EXPECTED_CHANGE`: parse empty, JSON array/object or JSON Lines input into the existing fixed compose-status projection.
- `FORBIDDEN_SCOPE`: CI Gate weakening, artifact allowlist expansion, workflow/product/schema/API/dependency/Provider/M5/M6 or
  production changes.
- `DEPENDENCIES`: R09 candidate `b6bbf0f` and its exact failure log.
- `ACCEPTANCE_CRITERIA`: Compose JSON Lines produces the same path-free allowlisted output; previous JSON forms remain valid.
- `VALIDATION_COMMANDS`: focused sanitizer test, Ruff, Prettier, mypy, contract check, same-SHA CI and eight-artifact scan.
- `SECURITY_NOTES`: raw Compose data remains unuploaded; parser errors do not echo raw input.
- `PRIVACY_NOTES`: no user data or private input is read.
- `DATA_NOTES`: no authority/fixture/migration changes.
- `LICENSE_NOTES`: no dependency or model change.
- `ROLLBACK`: disable unaccepted candidate; no persistent data changes.
- `RECOMMENDED_AGENT`: Principal / Terra Medium.
- `RECOMMENDED_MODEL_TIER`: Terra Medium.
- `ESCALATION_CONDITION`: any need to upload raw logs or loosen the artifact boundary is `ESCALATION_REQUIRED`.
- `OUTPUT_FORMAT`: common P2-M7 bounded-task report.

`P2_M7_R10: IMPLEMENTATION_IN_PROGRESS`
