# P2-M7-R07 — static backend-result projection validation repair

## Bounded task contract

- `BOOTSTRAP_STATUS`: `OK`.
- `TASK_ID`: `P2-M7-R07`.
- `OBJECTIVE`: close the remaining T02 backend-result redaction bypass by canonicalizing every backend result through
  the base first-party result type and validating all renderable projection fields with non-overridable module-level
  functions.
- `WHY_DELEGATED`: independent R06 security review proved that dynamic `__post_init__` dispatch could be bypassed by a
  forged subclass, allowing an unsafe projection status through. Review of the same renderable projection also found
  that `currency` lacked a runtime closed allowlist. This is one deterministic output-boundary repair.
- `EXPECTED_CHANGE`: replace dynamic instance validation with base-result reconstruction, statically validate exact
  projection type/status/currency/count/amount fields, and add forged-subclass plus nonallowlisted-currency regressions.
- `SCOPE` / `ALLOWED_FILES_OR_MODULES`: `synthetic_dataset/operations.py`, its targeted contract test and this repair
  record only.
- `FORBIDDEN_SCOPE`: no new state/currency authority, schema, migration, dependency, Provider, CLI, database,
  API/OpenAPI, M5/M6 behavior, production enablement, private input, audit-authority change or test weakening.
- `DEPENDENCIES`: R06 candidate `fa6f7b2c11f15a45c18302405030da8e3286e686`, run `32594798200`, and independent
  security proof that subclass-overridden dynamic validation returned `SECRET_LIKE_TOKEN` from a backend result.
- `INPUTS_AND_ASSUMPTIONS`: existing batch/item states and CNY/USD currency literal are the already typed, accepted
  first-party projection vocabulary. A backend object is untrusted until it has been reconstructed as the exact base
  result and static validators have run.
- `ACCEPTANCE_CRITERIA`: forged result/projection subclasses cannot bypass validation; nonallowlisted status or currency
  is rejected without echo; safe existing projection remains renderable; no authority outside T02 changes.
- `VALIDATION_COMMANDS`: scoped/full Ruff format and lint, strict mypy, targeted/full pytest, contract check, source
  negative scans, `git diff --check`, then a new exact-SHA CI run and artifact inspection.
- `SECURITY_NOTES`: removes dynamic validation dispatch from the untrusted backend boundary and closes all text-valued
  fields of the future CLI-renderable projection.
- `PRIVACY_NOTES`: no User, real-person data, Prompt, image, object key, URL, private path or credential can enter an
  accepted projection.
- `DATA_NOTES`: no persistence authority or record changes.
- `LICENSE_NOTES`: no dependency, SDK, model, weight or data artifact changes.
- `ROLLBACK`: reject this unaccepted forward repair; do not restore dynamic validation dispatch or free-form projection
  fields.
- `RECOMMENDED_AGENT`: Principal / Terra High implementation boundary.
- `RECOMMENDED_MODEL_TIER`: Terra High.
- `OUTPUT_FORMAT`: the P2-M7 common bounded-task output format in the execution protocol.
- `ESCALATION_CONDITION`: any need for new state/currency values, schema/API/authentication change, dependency/Provider
  behavior, M5/M6 change or output-policy exception is `ESCALATION_REQUIRED`.

## Preserved boundaries

- No CLI, direct SQL, Provider, storage, public API, OpenAPI, schema, migration, dependency, model, private input,
  M5 fresh-study or M6 release/revoke behavior is added or changed.
- Production remains disabled, and T03 remains closed until Principal acceptance after R07 evidence.

`P2_M7_R07: IMPLEMENTATION_IN_PROGRESS`
