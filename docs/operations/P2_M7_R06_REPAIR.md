# P2-M7-R06 — closed renderable projection-status repair

## Bounded task contract

- `BOOTSTRAP_STATUS`: `OK`.
- `TASK_ID`: `P2-M7-R06`.
- `OBJECTIVE`: close the final T02 renderable-output gap by ensuring that `DatasetOperationProjection.target_status`
  can only contain values from existing frozen first-party generation batch/item state authorities and is revalidated
  at the backend result boundary.
- `WHY_DELEGATED`: the independent Sol final review of green R05 candidate `4e13c86` proved that the broad uppercase
  state grammar still allowed a secret-like value to enter a future CLI-renderable projection. This is a deterministic
  forward repair, not a CI rerun or a T03 rendering workaround.
- `EXPECTED_CHANGE`: replace the open target-status regex with a derived closed allowlist from
  `GenerationBatchState` and `GenerationItemState`, recursively validate a backend result's projection before return,
  and add direct plus forged-backend non-echo regressions.
- `SCOPE` / `ALLOWED_FILES_OR_MODULES`: `synthetic_dataset/operations.py`, its targeted contract test and this repair
  record only.
- `FORBIDDEN_SCOPE`: no new state authority, schema, migration, dependency, Provider, CLI, database, API/OpenAPI,
  M5/M6 behavior, production enablement, private input, audit-authority change or test-semantic weakening.
- `DEPENDENCIES`: R05 candidate `4e13c86fe6c936b0da783b87f9ca84699d1f31bc`, same-SHA run `32593999102`, and the
  final-review proof that `SECRET_LIKE_TOKEN` matches the former open renderable projection state grammar.
- `INPUTS_AND_ASSUMPTIONS`: `GenerationBatchState` and `GenerationItemState` are accepted P2 typed state authorities;
  this repair does not add or reinterpret their values. Backend results are an untrusted application boundary even
  when a first-party dataclass constructor would normally validate them.
- `ACCEPTANCE_CRITERIA`: a non-authoritative or secret-like projection status is rejected without echo; forged backend
  results are normalized to a safe result code; accepted existing batch/item statuses remain renderable; no boundary
  outside T02 changes.
- `VALIDATION_COMMANDS`: scoped/full Ruff format and lint, strict mypy, targeted/full pytest, contract check, source
  negative scans, `git diff --check`, then a new exact-SHA CI run and artifact inspection.
- `SECURITY_NOTES`: closes a future CLI-renderable text channel at its typed source and makes backend boundary
  revalidation explicit; a later CLI must not substitute a weaker output filter.
- `PRIVACY_NOTES`: no User, real-person data, Prompt, image, object key, URL, private path or credential is added or
  permitted in any result projection.
- `DATA_NOTES`: no persistence authority or record is modified; the change only validates an in-memory internal
  contract.
- `LICENSE_NOTES`: no dependency, SDK, model, weight or data artifact is added.
- `ROLLBACK`: reject this unaccepted forward repair; do not restore a free-form renderable status contract.
- `RECOMMENDED_AGENT`: Principal / Terra Medium implementation boundary.
- `RECOMMENDED_MODEL_TIER`: Terra Medium.
- `OUTPUT_FORMAT`: the P2-M7 common bounded-task output format in the execution protocol.
- `ESCALATION_CONDITION`: any need to create a state taxonomy, alter accepted first-party state values, change schema/API,
  add authentication/Provider behavior, change M5/M6 behavior or make an output-policy exception is
  `ESCALATION_REQUIRED`.

## Preserved boundaries

- No CLI, direct SQL, Provider, storage, public API, OpenAPI, schema, migration, dependency, model, private input,
  M5 fresh-study or M6 release/revoke behavior is added or changed.
- Production remains disabled, and T03 remains closed until the Principal accepts T02 after R06 evidence.

`P2_M7_R06: IMPLEMENTATION_IN_PROGRESS`
