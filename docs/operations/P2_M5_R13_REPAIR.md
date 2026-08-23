# P2-M5-R13 CC04-A Proposal Residual State Semantics Repair

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R13`
- `FAILURE_SOURCE: R12_SOL_HIGH_REVIEW_RESIDUAL_STATE_INCONSISTENCY`
- `P2_M5_R12: FAILED_AT_763EEB0_RUN_32616944692_RESIDUAL_STATE_INCONSISTENCY`
- `P2_M5_R13: LOCAL_CANDIDATE_PENDING_VALIDATION`
- `CC04_A_OWNER_DECISION_CLOSURE: PENDING_R13_ACCEPTANCE`

## Bounded repair packet

- `OBJECTIVE`: clarify only the two Proposal passages that could reclassify accepted Owner constraints as current unresolved decisions.
- `WHY_REPAIR_NOT_CHANGE_CONTROL`: no Owner decision, envelope, Gate, research design, or downstream state changes; the repair aligns Proposal semantics with existing Owner Decision Pack and Register authority.
- `SCOPE`: the table explanatory sentence and one stop/escalation rule in the Proposal.
- `EXPECTED_CHANGE`: state that the table summarizes but cannot replace accepted authority, and reserve Owner escalation only for future scope change.
- `ALLOWED_FILES_OR_MODULES`: this record and `docs/research/P2_M5_CC04_FRESH_STUDY_PROPOSAL.md`.
- `FORBIDDEN_SCOPE`: every other file and all source/generation/private input/cohort/Asset/identity/Vision/measurement/transform/threshold/holdout/04-B/MVR/M6/production activity.
- `DEPENDENCIES`: `763eeb0d5bc12ddb8d96f64e8dc0739014425337`, run `32616944692`, `OD-P2-M5-CC04-001`, D01, Owner Decision Pack, Register, and ADR-041/047/049/050.
- `INPUTS_AND_ASSUMPTIONS`: R12 CI/artifact/security passed but Sol review found the two documented semantic defects; R12 is not rewritten or accepted.
- `ACCEPTANCE_CRITERIA`: exact two-path allowlist; no Owner/envelope/Gate drift; Proposal explicitly preserves accepted envelope; current missing facts use named Gates; only future change/expansion/exception/violation uses `OWNER_DECISION_REQUIRED_FOR_SCOPE_CHANGE`.
- `VALIDATION_COMMANDS`: scoped formatting, `git diff --check`, two-path check, authority comparison, leakage/binary/zero-diff scans, full local Gate, exact-SHA CI/artifact/Security/Sol evidence.
- `SECURITY_NOTES`: no network, Provider, generation, private input, secret, or production change.
- `PRIVACY_NOTES`: no User/real-person/private byte/locator/Prompt/key/URL/credential input.
- `DATA_NOTES`: no research object or evidence is created, read, or changed.
- `LICENSE_NOTES`: no source-rights, dependency, model, runtime, or Provider disposition change.
- `ROLLBACK`: reject the normal forward child; never amend `763eeb0`.
- `RECOMMENDED_AGENT: Principal / Sol High`; `RECOMMENDED_MODEL_TIER: Sol High`.
- `ESCALATION_CONDITIONS`: any third changed file or Owner/Gate/design/downstream drift is out of scope.
- `OUTPUT_FORMAT`: status, path/diff validation, semantic checks, CI/artifact/review evidence, and explicit acceptance state.
