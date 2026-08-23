# P2-M7-R11 — Gitleaks artifact member and parser-error redaction repair

- `BOOTSTRAP_STATUS`: `OK`.
- `TASK_ID`: `P2-M7-R11`.
- `OBJECTIVE`: eliminate the remaining runner-workspace ZIP member name from the Gitleaks artifact and ensure malformed
  Compose JSON/JSON Lines never echoes raw input in sanitizer errors.
- `WHY_DELEGATED`: independent R10 security and final reviews found two deterministic CI-evidence redaction defects after
  run `32621351113`; neither is a reason to weaken the Gitleaks or Docker gates.
- `SCOPE` / `ALLOWED_FILES_OR_MODULES`: the CI workflow's Gitleaks artifact packaging, artifact sanitizer, focused CI
  tests and this repair record only.
- `EXPECTED_CHANGE`: retain the existing Gitleaks action with its automatic upload disabled, copy its SARIF to a fixed
  runner-temp staging filename, upload only that file, and replace raw JSON parser errors with fixed messages.
- `FORBIDDEN_SCOPE`: Gitleaks scan weakening, artifact allowlist expansion, workflow/product/schema/API/dependency/
  Provider/M5/M6/production changes, raw log upload, private input or credential changes.
- `DEPENDENCIES`: R10 candidate `dcb831a` / run `32621351113`; artifact member `work/project-mirror/project-mirror/
results.sarif`; malformed JSON Lines marker reproduction.
- `ACCEPTANCE_CRITERIA`: eight artifacts have no runner/workspace path in contents or archive member names; malformed
  JSON/JSON Lines rejects without raw input in stdout/stderr; Gitleaks still runs and uploads a zero-result SARIF;
  valid object/array/empty/JSON Lines Compose forms retain the existing fixed projection.
- `VALIDATION_COMMANDS`: focused sanitizer/workflow tests, Ruff, Prettier, strict mypy, contract check, source scans,
  Linux no-network sanitizer probe, full same-SHA CI and eight-artifact archive-member/content inspection.
- `SECURITY_NOTES`: raw Gitleaks upload is disabled before a fixed-name staging copy; parser failures use fixed errors and
  never include raw input.
- `PRIVACY_NOTES`: no user data, synthetic asset, Prompt or private input is read or added.
- `DATA_NOTES`: no authority, fixture, migration or asset change.
- `LICENSE_NOTES`: the existing Gitleaks action/version remains unchanged; no dependency or model change.
- `ROLLBACK`: preserve the existing scan and artifact count while disabling this unaccepted candidate; no persistent data
  change.
- `RECOMMENDED_AGENT`: Principal / Terra Medium.
- `RECOMMENDED_MODEL_TIER`: Terra Medium.
- `ESCALATION_CONDITION`: any need to suppress Gitleaks, upload raw data, add a dependency or alter a product/public/
  M5/M6 boundary is `ESCALATION_REQUIRED`.
- `OUTPUT_FORMAT`: common P2-M7 bounded-task report.

`P2_M7_R11: IMPLEMENTATION_IN_PROGRESS`
