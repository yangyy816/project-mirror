# P2-M5 CC04-B TS01 Fixture Manual-Export Policy

## Authority and scope

- POLICY_VERSION: p2-m5-cc04-b-ts01-fixture-manual-export-v1
- OWNER_DECISION_ID: OD-P2-M5-CC04-B-TS01-Q01-001
- QUALIFICATION_ORDINAL: TS01-FIX-001
- SCOPE: ONE_OWNER_AUTHORIZED_NON_PERSON_NON_SENSITIVE_NATIVE_QUALIFICATION_OUTPUT_ONLY
- FORMAL_CALIBRATION_ORDINAL_IMPACT: NONE
- CAL_REQ_001_STATUS: MUST_REMAIN_NOT_CONSUMED

This policy is a prospective, Owner-authorized exception to the earlier TS01-T01 rule that reserved manual export for
a later formal `CAL-REQ` ordinal. It applies only to the single TS01-Q01 qualification result authorized by
`OD-P2-M5-CC04-B-TS01-Q01-001`. It does not change the formal E01 manual-export workflow, revive destination-bound
direct write, or authorize another generation.

## Canonical policy payload

The canonical UTF-8 payload is the exact JSON string below, including its final LF and excluding the Markdown fence:

```json
{
  "policy_version": "p2-m5-cc04-b-ts01-fixture-manual-export-v1",
  "owner_decision_id": "OD-P2-M5-CC04-B-TS01-Q01-001",
  "qualification_ordinal": "TS01-FIX-001",
  "expected_filename": "qf-001-7c9e4a2b.png",
  "auto_export_failure_result": "NOT_PROVEN",
  "manual_export_status": "OWNER_EXPORT_REQUIRED",
  "owner_reply": "EXPORTED TS01-FIX-001",
  "generation_retry": 0,
  "replacement_output": 0,
  "formal_cal_req_impact": 0,
  "cal_req_001": "NOT_CONSUMED",
  "exact_same_returned_output": 1,
  "target_preexistence": "HARD_STOP_NO_OVERWRITE",
  "discovery": "EXACT_PREAUTHORIZED_TARGET_ONLY_NO_ENUMERATION_GLOB_SCAN_CLIPBOARD_SCREENSHOT_OR_RECENT_FILE_GUESS",
  "required_validation": "EXACT_FILENAME,SHA256,MEDIA_TYPE,MAGIC_BYTES,BYTE_SIZE,DIMENSIONS,ORDINAL_BINDING,STAGING_INTEGRITY,CUSTODY_PROMOTION",
  "fixture_admission": "PROHIBITED",
  "cleanup": "REQUIRED_WITHOUT_RESERVATION_REFUND"
}
```

The digest and UTF-8 byte length are recorded by the change-control contract and current authority tail. Any byte
change requires a new forward policy version and new acceptance Gates.

## Manual fallback transaction

Manual fallback is available only after the one authorized native call has returned its only output and neither an
exact generated-artifact handle nor an exact attachment handle can prove access to the original bytes. Codex must not
generate again. It returns exactly:

```text
STATUS: OWNER_EXPORT_REQUIRED
QUALIFICATION_ORDINAL: TS01-FIX-001
AUTO_EXPORT_RESULT: NOT_PROVEN
GENERATION_RETRY_ALLOWED: NO
EXPECTED_EXPORT_FILENAME: qf-001-7c9e4a2b.png
```

The Owner saves only that exact displayed result and replies only `EXPORTED TS01-FIX-001`. The Principal then reads
only the pre-authorized exact target. It may not enumerate a parent directory, use a glob, scan Downloads, Desktop,
Temp, cache, or browser directories, use clipboard or screenshot recovery, infer a recent file, accept a substitute,
or overwrite an existing target.

Manual fallback PASS requires exact filename and ordinal binding, proof that the target did not exist before export,
SHA-256, media type, magic bytes, byte size, dimensions, staging integrity, custody promotion, and no retry. Missing,
mismatched, substituted, late, or overwritten bytes hard-stop the qualification. Dispatch has already consumed the
one global native-output reservation, and no failure refunds it.

## Non-expansion boundary

This policy does not authorize a formal calibration call or raw output, consume `CAL-REQ-001`, create an Asset,
SyntheticIdentity, cohort, duplicate-pair admission, QuestionBank entry, MVR result, M6 entry, or production use. The
fixture remains non-person, non-sensitive, Git-external, task-scoped, and cleanup-bound. Formal E01 manual fallback
continues to use its own `CAL-REQ-xxx` ordinal only after MR01 and a new execution-authority checkpoint pass.
