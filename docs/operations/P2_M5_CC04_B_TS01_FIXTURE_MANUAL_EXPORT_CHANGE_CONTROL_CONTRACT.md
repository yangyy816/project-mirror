# P2-M5 CC04-B TS01 Fixture Manual-Export Change-Control Contract

## Status and authority

- BOOTSTRAP_STATUS: OK
- TASK_ID: CC04-B-TS01-T02
- CHANGE_CONTROL_ID: CC-P2-M5-04-B-TS01-FIXTURE-MANUAL-EXPORT-V1
- OWNER_DECISION_ID: OD-P2-M5-CC04-B-TS01-Q01-001
- BASELINE_FAILED_CANDIDATE: 470f2fdb76731784c6a7879b978f160c827e10c3
- BASELINE_CI_RUN: 32688068326
- BASELINE_CI_ATTEMPT: 1
- BASELINE_SECURITY_RESULT: FAILED
- BASELINE_SOL_HIGH_RESULT: FAIL
- CANDIDATE: THIS_COMMIT
- AUTHORITY_CONDITION:
  EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE

This is the minimal forward change control required to implement the Owner's explicit authorization for
Owner-mediated export of the same `TS01-FIX-001` qualification output. It does not amend, reset, rebase, reinterpret,
or accept the failed baseline candidate. No generation, output, reservation, private root, staging target, calibration
ordinal, or formal E01 state is created by this contract.

## Preserved failed evidence

Commit `470f2fdb76731784c6a7879b978f160c827e10c3` and run `32688068326` remain immutable evidence:

- exact-SHA attempt-1 CI: three jobs PASS;
- eight unexpired exact-SHA artifacts: actual-content audit PASS;
- current-tail structure and canonical/mirror equality: PASS;
- independent Security: FAILED;
- independent Sol High: FAIL;
- primary defect: the current tail bound qualification fallback to an exact `CAL_REQ` ordinal while simultaneously
  prohibiting `CAL_REQ_001` consumption;
- policy defect: accepted TS01-T01 reserved manual fallback for a later formal ordinal and did not yet authorize
  manual export of the qualification fixture itself.

The seven absolute paths separately observed in Playwright and Docker logs are standard non-private runner/container
paths. Sol High determined they are outside R19's node-license-specific path-redaction Gate and do not disclose a
staging or custody locator.

## Exact prospective change

The accepted TS01-T01 policy remains unchanged for future formal `CAL-REQ-xxx` ordinals. This change adds one narrower
Owner-authorized qualification policy:

- POLICY_PATH: docs/research/P2_M5_CC04_B_TS01_FIXTURE_MANUAL_EXPORT_POLICY.md
- POLICY_VERSION: p2-m5-cc04-b-ts01-fixture-manual-export-v1
- POLICY_SHA256: 922f71d439ccfe6818c8afc83f0c75efeee4457256af83e915a0acec1b06f018
- POLICY_CANONICAL_UTF8_BYTE_LENGTH: 905
- QUALIFICATION_ORDINAL: TS01-FIX-001
- EXPECTED_EXPORT_FILENAME: qf-001-7c9e4a2b.png
- OWNER_EXPORT_REQUIRED_FORMAT: EXACT_QUALIFICATION_ORDINAL_TS01_FIX_001
- OWNER_REPLY: EXPORTED_TS01_FIX_001
- GENERATION_RETRY: 0
- REPLACEMENT_OUTPUT: 0
- FORMAL_CALIBRATION_CALL_IMPACT: 0
- FORMAL_CALIBRATION_RAW_OUTPUT_IMPACT: 0
- FORMAL_REQUEST_ORDINAL_IMPACT: NONE
- CAL_REQ_001_STATUS: MUST_REMAIN_NOT_CONSUMED

The same-output fallback is available only after the single authorized native call returns and exact original-byte
auto-export is not proven. It cannot be used to obtain a second image, retry generation, substitute another file,
scan for a file, overwrite a target, or admit the fixture into any Project Mirror dataset authority.

## Allowed paths

This change control may modify exactly:

1. `docs/operations/P2_M5_CC04_B_TS01_FIXTURE_MANUAL_EXPORT_CHANGE_CONTROL_CONTRACT.md`;
2. `docs/research/P2_M5_CC04_B_TS01_FIXTURE_MANUAL_EXPORT_POLICY.md`;
3. `docs/operations/P2_M5_ACCEPTANCE.md`;
4. `docs/operations/P2_M5_EXECUTION_PROTOCOL.md`.

It may not modify the failed Q01 contract, accepted TS01-T01 contract or policy, E01 contract, CI, application code,
tests, dependencies, schema, migration, OpenAPI, model or Provider boundaries, private state, MEMORY, MILESTONES,
shared summaries, or P2-M7.

## Validation and acceptance

Local validation requires exact changed-path allowlisting, scoped formatting, `git diff --check`, canonical policy
byte/digest validation, Acceptance/Execution governed-key order and value equality, no duplicate current-tail keys,
last-occurrence and physical true-EOF checks, zero generation/output/reservation/private-state counters, `CAL-REQ-001`
isolation, and P2-M7 untouched.

Tracked acceptance requires a normal forward commit, fast-forward non-force push, exact-SHA attempt-1 CI, exactly
eight unexpired artifacts with actual-content checks, independent Security/Privacy/License/Research Integrity,
independent Sol High, and Principal acceptance. No post-acceptance commit is allowed.

## Candidate result

- CHANGE_CONTROL_RESULT: PASS_AT_THIS_COMMIT_AFTER_ALL_GATES
- TS01_Q01_CONTRACT_RESULT: ONE_CALL_QUALIFICATION_CONTRACT_ACCEPTED_WITH_OWNER_AUTHORIZED_SAME_FIXTURE_MANUAL_FALLBACK_AFTER_ALL_GATES
- TS01_FIXTURE_STATUS: NOT_DISPATCHED
- GENERATION_CALLS_EXECUTED: 0
- RAW_OUTPUTS_CREATED: 0
- TS01_QUALIFICATION_GENERATION_CALLS_EXECUTED: 0
- TS01_QUALIFICATION_OUTPUTS_CREATED: 0
- TS01_FIXTURE_GLOBAL_NATIVE_OUTPUT_RESERVATION_CONSUMED: 0
- CAL_REQ_001_STATUS: NOT_CONSUMED
- NEXT_READY_TASK: CC04-B-TS01-Q01_TS01_FIX_001_DISPATCH_AFTER_CHANGE_CONTROL_ACCEPTANCE
- STOP_OUTCOME: READY_FOR_TRACKED_EVIDENCE
