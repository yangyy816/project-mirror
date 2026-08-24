# P2-M5-R31 E01 Current Resource Authority Repair

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R31`
- `OWNER_DECISION_ID: OD-P2-M5-CC04-B-E01-R29-001`
- `PREDECESSOR_CANDIDATE: b2012f50c2323d0ad9b8dc7b276e54090db88f26`
- `PREDECESSOR_STATUS: R30_CANDIDATE_NOT_ACCEPTED_PRESERVED_AS_HISTORICAL_EVIDENCE`
- `R31_AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`

## Bounded forward repair

Independent Sol High review found `R30_CURRENT_AUTHORITY_RESOURCE_LEDGER_CONFLICT`: the R30 repair record correctly
reported global remaining capacity as 62, but the R30 canonical/mirror current-authority tails did not govern that key
or the related remaining/consumption keys. Earlier `63` values could therefore be mistakenly read as current. R31
adds one complete true-EOF authority tail in each canonical/mirror state file; it does not amend, reset, rebase, or
otherwise rewrite R30. R30's exact-SHA CI, artifact, and Security/Privacy/License/Research PASS evidence remains
historical evidence only; R30 has no Principal acceptance.

- `SCOPE`: this repair record and canonical/mirror current-authority tails only.
- `ALLOWED_FILES_OR_MODULES`: this file, `docs/operations/P2_M5_ACCEPTANCE.md`, and `docs/operations/P2_M5_EXECUTION_PROTOCOL.md` only.
- `FORBIDDEN_SCOPE`: no E01 contract/policy change, image generation, retry, replacement, private input, private locator,
  Prompt, image bytes, schema, migration, CI, dependency, runtime, resource-envelope change, A02 creation, MVR, M6,
  QuestionBank, MEMORY, shared-summary, or P2-M7 change.

## Preserved no-retry and no-reuse boundary

`CAL-REQ-001` remains consumed and non-admissible. A same-Prompt or changed-Prompt regeneration, replacement image,
calibration-cohort use, holdout use, QuestionBank use, admission, or counter refund is prohibited. The exact source and
staging copies are absent as Owner-attested, while a platform transcript copy remains
`EXISTS_OR_UNKNOWN_NOT_UNDER_PROJECT_REGISTRY_DELETION_NOT_VERIFIED`. The next ordinal remains `CAL-REQ-002`, but is
not authorized until R31 and then the separate A02 checkpoint have each passed every required Gate and Principal
acceptance.

## Correct current ledger

```text
FORMAL_E01_GENERATION_CALLS_EXECUTED: 1
FORMAL_E01_RAW_OUTPUTS_CREATED: 1
FORMAL_E01_PROVISIONAL_ACCEPTED_IDENTITIES: 0
CALIBRATION_REQUEST_CALL_MAX: 32
CALIBRATION_RAW_OUTPUT_MAX: 32
CALIBRATION_ADMITTED_IDENTITY_TARGET: 24
FORMAL_CALLS_REMAINING: 31
FORMAL_RAW_OUTPUT_CAPACITY_REMAINING: 31
TS01_FIXTURE_GLOBAL_NATIVE_OUTPUT_RESERVATION_CONSUMED: 1
FORMAL_CAL_REQ_001_GLOBAL_OUTPUT_CONSUMED: 1
GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING: 62
```

No value in this repair changes a quota, returns a consumed call/raw output, or authorizes an additional output.
