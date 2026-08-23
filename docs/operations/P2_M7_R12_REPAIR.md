# P2-M7-R12 — CI evidence migration-head coverage repair

- `BOOTSTRAP_STATUS`: `OK`.
- `TASK_ID`: `P2-M7-R12`.
- `OBJECTIVE`: update the existing CI migration-head coverage assertion for the fifth, P2-M7-specific evidence
  generator introduced by T07.
- `WHY_DELEGATED`: candidate `a0c5481` / run `32627371712` proved that the new generator is correctly wired but the
  pre-existing count assertion still encodes four generators; no product, migration or browser failure occurred.
- `SCOPE` / `ALLOWED_FILES_OR_MODULES`: `services/api/tests/test_migrations.py` and this repair record only.
- `EXPECTED_CHANGE`: retain the exact current migration-head assertion and change only its expected generator count
  from four to five.
- `FORBIDDEN_SCOPE`: migration revision change, workflow Gate weakening, evidence schema change, product logic,
  public API, dependency, Provider, M5/M6, production, artifact-policy or Playwright changes.
- `DEPENDENCIES`: T07 candidate `a0c5481`; exact CI failure at
  `test_ci_evidence_tracks_current_migration_head` in run `32627371712`.
- `ACCEPTANCE_CRITERIA`: the assertion verifies all five generators use `0014_m5_eval_authority`; no obsolete
  `0009_generation_batch_pipeline` reference is permitted; targeted test and complete same-SHA CI pass.
- `VALIDATION_COMMANDS`: targeted P2-M7 plus migration evidence test, Ruff format/lint, strict mypy, `git diff --check`,
  full same-SHA CI and artifact inspection.
- `SECURITY_NOTES`: preserves, rather than bypasses, the migration-head integrity assertion.
- `PRIVACY_NOTES`: no private input, user data, asset, Prompt or raw payload is read or added.
- `DATA_NOTES`: no database authority, migration or persistent data changes.
- `LICENSE_NOTES`: no dependency, model, artifact or external service change.
- `ROLLBACK`: disable this unaccepted repair candidate; no persistent data is changed.
- `RECOMMENDED_AGENT`: Principal / Terra Medium.
- `RECOMMENDED_MODEL_TIER`: Terra Medium.
- `ESCALATION_CONDITION`: any requirement to change the migration head, weaken CI or alter the frozen T07 evidence
  boundary is `ESCALATION_REQUIRED`.
- `OUTPUT_FORMAT`: common P2-M7 bounded-task report.

`P2_M7_R12: IMPLEMENTATION_IN_PROGRESS`
