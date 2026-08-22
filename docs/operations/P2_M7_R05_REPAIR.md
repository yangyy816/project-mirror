# P2-M7-R05 — opaque correlation and result-redaction repair

## Bounded task contract

- `BOOTSTRAP_STATUS`: `OK`.
- `TASK_ID`: `P2-M7-R05`.
- `OBJECTIVE`: prevent free-text `request_id` or result `code` values from entering a renderable operation result by
  requiring the same opaque 32-character lowercase hexadecimal correlation reference and a closed first-party result
  code allowlist at both command and result boundaries.
- `WHY_DELEGATED`: independent security review of the green R04 candidate identified a deterministic secret-/Prompt-like
  correlation echo path that CI did not exercise. This forward repair closes that fixed T02 redaction defect rather
  than weakening the output boundary or rerunning CI.
- `EXPECTED_CHANGE`: require opaque correlation references at both command and result boundaries, reject result codes
  outside a closed first-party taxonomy, and normalize unknown backend rejection codes before a renderable result is
  constructed.
- `SCOPE` / `ALLOWED_FILES_OR_MODULES`: `synthetic_dataset/operations.py`, its targeted contract test, and this repair
  record only.
- `FORBIDDEN_SCOPE`: no workflow, schema, migration, dependency, Provider, CLI, database, API/OpenAPI, M5/M6 behavior,
  production enablement, private input, existing audit authority or test-semantic weakening.
- `DEPENDENCIES`: exact R04 candidate `f127cb8fed3b407e2b095bde68e033cb7e49dc04`, same-SHA run `32592792717`, and
  the independent security finding that `request_id` accepted arbitrary printable single-line text.
- `INPUTS_AND_ASSUMPTIONS`: the T02 command/result correlation is an opaque internal reference, not a user- or
  Provider-supplied text field. Existing first-party IDs use the same 32-character hexadecimal shape.
- `ACCEPTANCE_CRITERIA`: command and result reject non-opaque correlation values and non-allowlisted result codes
  without echoing them; successful results retain only opaque correlation references and first-party codes; no
  behavior outside that validation boundary changes.
- `VALIDATION_COMMANDS`: scoped/full Ruff format and lint, strict mypy, targeted/full pytest, contract check, source
  negative scans, `git diff --check`, then a new exact-SHA CI run and artifact inspection.
- `SECURITY_NOTES`: avoids untrusted free text in future CLI-renderable result correlation and code fields while
  preserving a closed stable rejection taxonomy; backend exceptions and unknown backend rejection codes remain
  redacted.
- `PRIVACY_NOTES`: no User, real-person data, Prompt, image, object key, URL, private path or credential is added or
  accepted as an operation correlation reference.
- `DATA_NOTES`: no persistence authority or record is modified; this is validation of an in-memory typed contract.
- `LICENSE_NOTES`: no dependency, SDK, model, weight or data artifact is added.
- `ROLLBACK`: reject this unaccepted forward repair; do not restore the unsafe free-text correlation contract.
- `RECOMMENDED_AGENT`: Principal / Terra Medium implementation boundary.
- `RECOMMENDED_MODEL_TIER`: Terra Medium.
- `OUTPUT_FORMAT`: the P2-M7 common bounded-task output format in the execution protocol.
- `ESCALATION_CONDITION`: any need for a new identifier authority, schema/API change, authentication model, dependency,
  Provider behavior, M5/M6 behavior or output-policy exception is `ESCALATION_REQUIRED`.

## Preserved boundaries

- No CLI, direct SQL, Provider, storage, public API, OpenAPI, schema, migration, dependency, model, private input,
  M5 fresh-study or M6 release/revoke behavior is added or changed.
- Production remains disabled, and the repair does not claim authenticated-operator integration before later M7 work.

`P2_M7_R05: IMPLEMENTATION_IN_PROGRESS`
