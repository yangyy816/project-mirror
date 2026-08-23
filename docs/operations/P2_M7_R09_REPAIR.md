# P2-M7-R09 — CI artifact path-redaction repair

- `BOOTSTRAP_STATUS`: `OK`.
- `TASK_ID`: `P2-M7-R09`.
- `OBJECTIVE`: remove absolute runner-path leakage from CI artifacts while preserving the existing quality, supply-chain,
  Docker and bounded Playwright Gates.
- `WHY_DELEGATED`: exact-SHA R08 artifact inspection and independent reviews found path-bearing raw logs and license
  inventory; this is a deterministic CI-evidence defect, not a reason to weaken the Gate.
- `SCOPE` / `ALLOWED_FILES_OR_MODULES`: CI artifact projection script, workflow artifact inputs, focused CI tests and
  this repair record only.
- `EXPECTED_CHANGE`: artifacts contain allowlisted license/compose summaries and Playwright attempt facts, never raw
  installation or compose output with runner paths.
- `FORBIDDEN_SCOPE`: workflow Gate weakening, test-semantic relaxation, product/runtime/schema/migration/API/OpenAPI,
  Provider/dependency/model, M5/M6, production, private input and any credential change.
- `DEPENDENCIES`: R08 exact-SHA run `32619678560` and two independent conditional reviews.
- `ACCEPTANCE_CRITERIA`: path, URL, image, Prompt, object-key and credential scans are clean across all eight artifacts;
  Playwright remains bounded with its current retry/timeout contract; dependency audit and Docker validation still run.
- `VALIDATION_COMMANDS`: focused sanitizer/workflow tests, scoped Prettier, Ruff, mypy, contract check, source scans,
  full same-SHA CI and eight-artifact content inspection.
- `SECURITY_NOTES`: raw command output remains ephemeral runner-local diagnostic material and is not emitted or uploaded.
- `PRIVACY_NOTES`: no user data, synthetic asset, Prompt or private input is read or added.
- `DATA_NOTES`: no database authority or fixture changes.
- `LICENSE_NOTES`: audit commands remain unchanged; only their artifact projection is reduced to an allowlist.
- `ROLLBACK`: retain the existing hard CI Gates and disable the unaccepted candidate; no persistent data changes.
- `RECOMMENDED_AGENT`: Principal / Terra Medium.
- `RECOMMENDED_MODEL_TIER`: Terra Medium.
- `ESCALATION_CONDITION`: any need for a new dependency, artifact upload of raw data, Gate weakening or contract change is
  `ESCALATION_REQUIRED`.
- `OUTPUT_FORMAT`: common P2-M7 bounded-task report.

`P2_M7_R09: IMPLEMENTATION_IN_PROGRESS`
