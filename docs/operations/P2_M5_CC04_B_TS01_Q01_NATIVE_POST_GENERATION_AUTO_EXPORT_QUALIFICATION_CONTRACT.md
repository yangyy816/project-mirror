# P2-M5 CC04-B TS01-Q01 Native Post-Generation Auto-Export Qualification Contract

## Status and bounded authority

- BOOTSTRAP_STATUS: OK
- TASK_ID: CC04-B-TS01-Q01-C01
- QUALIFICATION_TASK_ID: CC04-B-TS01-Q01
- TASK_NAME: Native Post-Generation Auto-Export Capability Qualification Contract
- OWNER_DECISION_ID: OD-P2-M5-CC04-B-TS01-Q01-001
- OWNER_SELECTION: AUTHORIZE_SINGLE_TS01_FIX_001_NATIVE_AUTO_EXPORT_QUALIFICATION_CALL
- BASELINE_SHA: d4da336874483af9b76b16677b1e0a6e12ee26db
- BASELINE_CI_RUN: 32661022182
- BASELINE_MIGRATION_HEAD: 0014_m5_eval_authority
- CONTRACT_CANDIDATE: THIS_COMMIT
- AUTHORITY_CONDITION:
  EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE
- PRE_CONDITION_CURRENT_STATE:
  R19_AND_TS01_T01_ACCEPTED;GENERATION_CALLS=0;RAW_OUTPUTS=0;TS01_CALLS=0;TS01_OUTPUTS=0;TS01_GLOBAL_RESERVATION=0;CAL_REQ_001=NOT_CONSUMED

This commit accepts only the one-call qualification contract. It does not call image generation, reserve the fixture
unit, create an output, staging target, custody root, private locator, Prompt file, Asset, identity, cohort, MVR,
QuestionBank object, or MR01 reviewer.

## Inherited authority and one-call envelope

- TS01_CHANGE_CONTROL_SHA: d4da336874483af9b76b16677b1e0a6e12ee26db
- TS01_CHANGE_CONTROL_CI_RUN: 32661022182
- NATIVE_TRANSCRIPT_STAGING_POLICY_VERSION: p2-m5-cc04-b-e01-native-transcript-staging-v1
- NATIVE_TRANSCRIPT_STAGING_POLICY_SHA256:
  c5b2a15f3d8801e1eba28d5a4eabb4f35b06ffb7aa3abb9747890e504ecc753a
- NATIVE_TRANSCRIPT_STAGING_POLICY_CANONICAL_UTF8_BYTE_LENGTH: 882
- DESTINATION_BOUND_DIRECT_WRITE_REQUALIFICATION: PROHIBITED
- DS01_Q01_RETRY: PROHIBITED
- QUALIFICATION_ORDINAL: TS01-FIX-001
- AUTHORIZED_CALL_COUNT: 1
- AUTHORIZED_RETURNED_OUTPUT_MAX: 1
- RETRY: 0
- CONCURRENCY: 1
- PLATFORM_CREDIT_OR_OTHER_RESOURCE_IMPACT: COUNTS_TOWARD_CODEX_USAGE_LIMITS
- EXACT_PLATFORM_USAGE_AMOUNT: UNKNOWN_OR_NULL_UNTIL_DISPATCH_AND_PLATFORM_ACCOUNTING
- FORMAL_CALIBRATION_GENERATION_BUDGET_IMPACT: 0
- FORMAL_CALIBRATION_RAW_OUTPUT_BUDGET_IMPACT: 0
- FORMAL_REQUEST_ORDINAL_IMPACT: NONE
- CAL_REQ_001_STATUS: MUST_REMAIN_NOT_CONSUMED
- TS01_FIXTURE_GLOBAL_NATIVE_OUTPUT_RESERVATION_IMPACT: 1_WITHIN_FROZEN_64_NOT_ADDITIVE
- GLOBAL_NATIVE_OUTPUT_CAPACITY_BEFORE_DISPATCH: 64
- GLOBAL_NATIVE_OUTPUT_CAPACITY_AFTER_DISPATCH: 63
- TS01_FIXTURE_GLOBAL_NATIVE_OUTPUT_RESERVATION_REFUND: PROHIBITED_AFTER_DISPATCH
- PRIVATE_STORAGE_ACCOUNTING: WITHIN_EXISTING_8_GIB_GLOBAL_HARD_CEILING_NO_ADDITIVE_ENVELOPE

The fixture cannot enter calibration, holdout, Asset, SyntheticIdentity, cohort, formal duplicate pairs, 04-C through
04-E, MVR, M6, QuestionBank, production, or real-user processing. Failure never refunds the reservation or permits a
second call.

## Fixture and tracked-redaction contract

- FIXTURE_PROMPT_CLASS: NON_PERSON_NON_SENSITIVE_TECHNICAL_GEOMETRIC_TEST_IMAGE
- REQUESTED_OUTPUT_COUNT: 1
- REQUESTED_IMAGE_SIZE: 1024x1024
- PEOPLE_OR_FACES: PROHIBITED
- TEXT_LOGO_WATERMARK: PROHIBITED
- REAL_PERSON_OR_USER_REFERENCE: PROHIBITED
- USER_DATA: PROHIBITED
- SECRET_CREDENTIAL_PRIVATE_PATH_OR_LOCATOR: PROHIBITED
- FIXTURE_OUTPUT_ADMISSION: PROHIBITED
- FIXTURE_OUTPUT_QUESTIONBANK_USE: PROHIBITED
- EXPECTED_EXPORT_FILENAME: qf-001-7c9e4a2b.png

The exact Owner-authorized tool Prompt remains transient tool input only. Prompt plaintext, raw payload, image bytes,
Base64, data URL, private path, locator, object key, signed URL, and credential must not enter Git, CI artifacts,
MEMORY, commit messages, logs, reviewer packets, or governance status.

## Dispatch transaction

Only after this contract completes every acceptance Gate may the Principal prepare dispatch. Immediately before the
sole tool call, a Git-external append-only receipt atomically records:

```text
TS01_FIXTURE_ID: TS01-FIX-001
TS01_FIXTURE_STATUS: DISPATCH_PREPARED
TS01_FIXTURE_GLOBAL_NATIVE_OUTPUT_RESERVATION_CONSUMED: 1
GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING: 63
TS01_QUALIFICATION_GENERATION_CALLS_EXECUTED: 1_AT_DISPATCH
CAL_REQ_001_STATUS: NOT_CONSUMED
```

Those facts never roll back. No background, repeated, sibling-Agent, altered-Prompt, alternate-tool, or second
generation call is permitted.

## Export qualification

Check the same output in order: EXACT_NATIVE_GENERATED_ARTIFACT_HANDLE, then EXACT_NATIVE_ATTACHMENT_HANDLE. PASS
requires a platform handle bound one-to-one to this call and output; original bytes; SHA-256, media type, magic class,
byte size, dimensions; automatic copy to one pre-authorized absent Git-external target; fixed filename; equal source
and staging digests; and zero listing, enumeration, glob, Downloads/Desktop/temp/cache scan, clipboard, data URL,
screenshot, re-render, recent-file inference, overwrite, substitution, or retry.

UI rendering, generic download, schema prose, an Agent claim, or an unreadable/unbound handle is insufficient. Missing
proof yields NATIVE_AUTO_EXPORT_CAPABILITY: NOT_PROVEN without another call.

If auto export is not proven, stop on the same output with:

```text
STATUS: OWNER_EXPORT_REQUIRED
QUALIFICATION_ORDINAL: TS01-FIX-001
AUTO_EXPORT_RESULT: NOT_PROVEN
GENERATION_RETRY_ALLOWED: NO
EXPECTED_EXPORT_FILENAME: qf-001-7c9e4a2b.png
```

The Owner exports that exact result and replies only `EXPORTED TS01-FIX-001`. The Principal reads only the exact
expected file through the pre-authorized task capability, without parent listing, glob, search, cache inspection,
alternate upload, or modification-time inference. Manual PASS requires ordinal/filename binding, absence evidence,
digest/type/magic/size/dimensions, staging integrity, custody promotion, no overwrite/retry, and cleanup evidence.

## Results, retention, and downstream stop

Legal results are PASS_AUTO_EXPORT, PASS_MANUAL_EXPORT_FALLBACK, BLOCKED_EXPORT_CAPABILITY, or FAILED. The fixture is
never admitted. Retained tracked evidence is limited to allowlisted IDs, counts, reservation, redacted handle status,
digest, type, size, dimensions, export mode, digest equality, custody/cleanup status, reason code, and transcript-copy
custody disclosure. Fixture-byte cleanup never refunds the reservation. The transcript copy remains
EXISTS_OR_UNKNOWN, NOT_UNDER_PROJECT_REGISTRY, and DELETION_NOT_VERIFIED.

MR01 starts only after the completed qualification result passes its own same-SHA CI, eight artifact content checks,
independent Security/Privacy/License/Research Integrity, Sol High, and Principal acceptance. Formal E01 remains zero
and closed until MR01 and a new execution-authority checkpoint pass.

## Changed paths and acceptance

This candidate may change exactly this contract, `docs/operations/P2_M5_ACCEPTANCE.md`, and
`docs/operations/P2_M5_EXECUTION_PROTOCOL.md`. It may not modify code, schema, migration, API, workflow, dependency,
lockfile, model, Provider, TS01-T01 policy, MEMORY, MILESTONES, shared summaries, P2-M7, private state, Prompt, or binary
content.

Local checks require scoped Prettier, git diff --check, exact allowlist, marker/prohibition scans, policy digest, zero
counters and reservation, CAL-REQ isolation, retry-zero and 64-to-63 arithmetic, no-private/no-binary scans, and exact
canonical/mirror true-EOF order, equality, uniqueness, last occurrence, and physical EOF. Acceptance additionally
requires normal forward commit/push, same-SHA attempt-1 three-job PASS, eight exact-SHA artifacts, independent
Security/Privacy/License/Research Integrity and Sol High PASS, and Principal acceptance. No post-acceptance status
commit is allowed.

## Candidate result

- TS01_Q01_CONTRACT_STATUS: READY_FOR_SAME_SHA_ACCEPTANCE
- TS01_QUALIFICATION_STATUS: NOT_STARTED_PENDING_CONTRACT_ACCEPTANCE
- TS01_FIXTURE_STATUS: NOT_DISPATCHED
- TS01_FIXTURE_GLOBAL_NATIVE_OUTPUT_RESERVATION_CONSUMED: 0
- GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING: 64
- TS01_QUALIFICATION_GENERATION_CALLS_EXECUTED: 0
- TS01_QUALIFICATION_OUTPUTS_CREATED: 0
- FORMAL_E01_GENERATION_CALLS_EXECUTED: 0
- GENERATION_CALLS_EXECUTED: 0
- RAW_OUTPUTS_CREATED: 0
- CAL_REQ_001_STATUS: NOT_CONSUMED
- REQUEST_ORDINAL_CONSUMED: NONE
- PRIVATE_ROOT_OR_LOCATOR_CREATED: NO
- GENERATION_SPECIFICATION_CREATED: NO
- CALIBRATION_COHORT_STATUS: NOT_CREATED
- SOL_MAX_REVIEWER_QUALIFICATION_STATUS: NOT_STARTED
- CC04_B_EXECUTION: CLOSED_PENDING_TS01_MR01_AND_NEW_E01_AUTHORITY
- P2_M5_STATE: EXECUTING
- P2_MVR_V1_RESULT: NOT_EVALUATED
- P2_M6_ENTRY: CLOSED_PENDING_TECHNICAL_AND_MVR_PASS
- NEXT_READY_TASK: CC04-B-TS01-Q01_CONTRACT_SAME_SHA_ACCEPTANCE
- STOP_OUTCOME: TS01_Q01_ONE_CALL_QUALIFICATION_CONTRACT_READY_FOR_TRACKED_EVIDENCE

After every Gate passes, this contract opens only the single TS01-FIX-001 dispatch transaction.
