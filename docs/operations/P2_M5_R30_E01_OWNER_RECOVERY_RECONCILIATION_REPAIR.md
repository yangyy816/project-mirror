# P2-M5-R30 E01 Owner Recovery Reconciliation Repair

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R30`
- `OWNER_DECISION_ID: OD-P2-M5-CC04-B-E01-R29-001`
- `PREDECESSOR_CANDIDATE: d4bd223679fb53a317477d72caeca2cd8d76e44f`
- `PREDECESSOR_STATUS: R29_CANDIDATE_NOT_ACCEPTED_PRESERVED_AS_HISTORICAL_EVIDENCE`
- `R30_AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`

## Bounded forward-repair packet

`R30` is the minimum normal forward repair needed because the unaccepted R29 candidate did not fully record the
Owner's exact cleanup attestation, committed-registration receipt gate, and complete no-decode ordering. It does not
amend, reset, rebase, or otherwise rewrite R29. R29's CI, artifact, and review evidence remains historical evidence
only and is not an acceptance of R29.

- `SCOPE`: this repair record, the accepted E01 execution contract, and the canonical/mirror current-authority tails.
- `ALLOWED_FILES_OR_MODULES`: this file; `docs/operations/P2_M5_CC04_B_E01_FRESH_CALIBRATION_EXECUTION_CONTRACT.md`; `docs/operations/P2_M5_ACCEPTANCE.md`; and `docs/operations/P2_M5_EXECUTION_PROTOCOL.md`.
- `FORBIDDEN_SCOPE`: no image generation; no retry or replacement; no Owner-decision, resource-envelope, review-policy, QuestionBank, MVR, M6, schema, migration, CI, dependency, runtime, private-byte, private-locator, Prompt, MEMORY, shared-summary, or P2-M7 change.
- `NEXT_CHECKPOINT`: `CC04-B-E01-A02`, only after R30 is independently accepted. A02, not R30, is the only allowed place to materialize the v2 first-wave presentation-context authority for `CAL-REQ-002` onward.

## Preserved CAL-REQ-001 incident and cleanup reconciliation

The following are immutable incident facts, not an admission, QA, screening, or replacement record:

```text
CAL_REQ_001: CONSUMED
CAL_REQ_001_RETRY: PROHIBITED
CAL_REQ_001_GENERATION_CALLS: 1
CAL_REQ_001_RAW_OUTPUTS: 1
CAL_REQ_001_OUTPUT_SHA256: FCFD73D5841C37931B2A62EB18941A1AB8C90D075E71E6F327DC2F4F94FD723F
CAL_REQ_001_MEDIA_TYPE: IMAGE_PNG
CAL_REQ_001_BYTE_SIZE: 1863683
CAL_REQ_001_ACTUAL_DIMENSIONS: 1402x1122
CAL_REQ_001_DETERMINISTIC_QA: NOT_EXECUTED
CAL_REQ_001_MODEL_SCREENING: NOT_EXECUTED
CAL_REQ_001_ADMISSION: NOT_EXECUTED
CAL_REQ_001_PROVISIONAL_ACCEPTED: 0
CAL_REQ_001_FAILURE: OUTPUT_DECODE_BEFORE_OUTPUT_REGISTRATION
CAL_REQ_001_INITIAL_CLEANUP: FAILED_PLATFORM_DELETE_DENIED
CAL_REQ_001_OWNER_CLEANUP: COMPLETE_EXACT_SHA_VERIFIED_AND_ABSENCE_VERIFIED
CAL_REQ_001_CLEANUP_STATUS: COMPLETE_AFTER_OWNER_EXACT_DELETION
CAL_REQ_001_SOURCE_COPY: ABSENT_VERIFIED
CAL_REQ_001_STAGING_COPY: ABSENT_VERIFIED
CAL_REQ_001_PROJECT_CUSTODY_LIVE_BYTES: 0
CAL_REQ_001_PLATFORM_TRANSCRIPT_COPY: EXISTS_OR_UNKNOWN_NOT_UNDER_PROJECT_REGISTRY_DELETION_NOT_VERIFIED
CAL_REQ_001_FINAL_DISPOSITION: FAILED_NON_ADMISSIBLE_NO_RETRY
```

No source, staging, parent-directory, registry, object-key, URL, or other locator is recorded here. The Owner's
attestation applies only to the two exact project-custody source and staging files; it does not prove deletion of a
platform transcript copy.

## Frozen register-before-decode rule for CAL-REQ-002 and later

For each returned output, the only valid sequence is:

1. irrevocably consume the request ordinal at native dispatch;
2. receive the exact native generated-artifact handle;
3. create a new exact-byte copy in the preauthorized Git-external staging target;
4. compute exact SHA-256 and byte size;
5. classify media type and magic bytes without image decode;
6. append and commit the immutable per-output registry record;
7. receive and verify the committed-registration receipt;
8. only then decode and read dimensions;
9. canonical normalization;
10. deterministic hard QA;
11. pHash and targeted duplicate-candidate selection;
12. lightweight independent Sol group screening; and
13. provisional admission or rejection.

Before step 7 succeeds, dimensions, EXIF, decoders, previews, thumbnails, Pillow, OpenCV, browser-image parsing,
landmarks, face count, pHash, normalization, QA, screening, and admission are prohibited. Pre-registration work is
limited to byte-preserving copy, digest, byte count, non-decoding magic/media classification, exact ordinal/handle
binding, and registry append. A registration failure is `OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE`: the ordinal stays
consumed, no decode or later ordinal may proceed, and no generation retry is permitted.

If `CAL-REQ-002` has `DECODE_BEFORE_REGISTRATION`, stop with
`REPEATED_OUTPUT_REGISTRATION_ORDER_VIOLATION`; no ordinary Repair may resume generation.

The immutable registry record must contain an opaque output ID, request ordinal, source kind and delivery class, exact
generated-artifact receipt, source and staging SHA-256, byte size, media type, magic-byte class, generation
specification version and digest, assignment-manifest version and digest, request/output ledger status, custody status,
retention class, cleanup policy, registration timestamp, and a valid registration-commit receipt. `REGISTRATION_STATUS`
must be `COMMITTED` before step 8.

## Accounting and execution boundary

```text
FORMAL_E01_GENERATION_CALLS_EXECUTED: 1
FORMAL_E01_RAW_OUTPUTS_CREATED: 1
FORMAL_E01_PROVISIONAL_ACCEPTED_IDENTITIES: 0
NEXT_UNUSED_FORMAL_ORDINAL: CAL-REQ-002
CALIBRATION_REQUEST_CALL_MAX: 32
CALIBRATION_RAW_OUTPUT_MAX: 32
CALIBRATION_ADMITTED_IDENTITY_TARGET: 24
FORMAL_CALLS_REMAINING: 31
FORMAL_RAW_OUTPUT_CAPACITY_REMAINING: 31
TS01_FIXTURE_GLOBAL_NATIVE_OUTPUT_RESERVATION_CONSUMED: 1
FORMAL_CAL_REQ_001_GLOBAL_OUTPUT_CONSUMED: 1
GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING: 62
```

R30 does not authorize `CAL-REQ-002`, any A02 file, or a first-wave presentation-policy change. Until R30 and then A02
have independently passed every required same-SHA Gate and Principal acceptance, E01 remains fail-closed.

`GENERATION_SPECIFICATION_V2` is deferred to accepted A02 for `CAL-REQ-002` through `CAL-REQ-032`; v1 remains the
historical specification for the failed `CAL-REQ-001` and must not be silently overwritten.
