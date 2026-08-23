# P2-M7-R04 — T02 CI Ruff import and export ordering repair

## Bounded task contract

- `BOOTSTRAP_STATUS`: `OK`.
- `TASK_ID`: `P2-M7-R04`.
- `OBJECTIVE`: resolve the exact `RUF022` and `I001` errors reported by the `17fdecb` same-SHA CI run without changing
  T02 behavior or scope.
- `WHY_DELEGATED`: the prior formatter-only repair did not cover CI lint's export-order and import-block checks; this
  deterministic defect requires an explicit bounded follow-up, not a rerun.
- `SCOPE` / `ALLOWED_FILES_OR_MODULES`: the T02 package export, operations import block and this repair record only.
- `FORBIDDEN_SCOPE`: no workflow, schema, migration, dependency, Provider, CLI, database, API, M5/M6 behavior,
  production enablement, private input or test-semantic change.
- `DEPENDENCIES`: failed exact-SHA candidate `17fdecb971d902e23efa33468c94a6c2f38d0cc2`, run `32591891291`.
- `INPUTS_AND_ASSUMPTIONS`: the authoritative CI log reports only `RUF022` and `I001`; all other quality stages were
  not run after the lint stop and are not inferred as passed.
- `ACCEPTANCE_CRITERIA`: CI Ruff's import and `__all__` ordering requirements are satisfied, targeted/full local
  quality remains green, and all T02 closed boundaries remain unchanged.
- `VALIDATION_COMMANDS`: scoped/full Ruff format and lint, strict mypy, targeted/full pytest, contract check,
  `git diff --check`, then a new same-SHA CI run.
- `RECOMMENDED_AGENT`: Principal / Terra Medium implementation boundary.
- `RECOMMENDED_MODEL_TIER`: Terra Medium.
- `OUTPUT_FORMAT`: the P2-M7 common bounded-task output format in the execution protocol.
- `ESCALATION_CONDITION`: any semantic failure, required workflow change or closed-boundary conflict is
  `ESCALATION_REQUIRED`.

## Preserved boundaries

- No production capability, CLI, direct database path, Provider, schema, migration, API/OpenAPI, dependency, model,
  private input, M5 fresh study or M6 release/revoke behavior is added or changed.
- The exact same code remains synthetic-only and deterministic; this repair only changes source ordering.

`P2_M7_R04: IMPLEMENTATION_IN_PROGRESS`
