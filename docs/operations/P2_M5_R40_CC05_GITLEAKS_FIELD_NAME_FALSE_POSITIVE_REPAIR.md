# P2-M5-R40 — CC05 Gitleaks Field-name False-positive Repair

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R40`
- `TASK_NAME: CC05 Gitleaks Field-name False-positive Repair`
- `PREDECESSOR_CANDIDATE: 0500b9e60822d81811f85f2926534b26ad86a088`
- `PREDECESSOR_RUN: 33237701875_ATTEMPT_1`
- `PREDECESSOR_FAILURE_GATE: SECRET_SCAN_GENERIC_API_KEY_FALSE_POSITIVE`
- `REPAIR_CLASS: L1_BOUNDED_DETERMINISTIC_REPAIR`
- `REPAIR_SCOPE: MACHINE_POLICY_METADATA_LABEL_AND_DERIVED_DIGEST_REFERENCES_ONLY`

## Preserved predecessor evidence

The predecessor remains a normal immutable Git commit and failed overall CI. Its
`quality-and-integration` and `docker-validation` jobs passed; `secret-scan` failed with exactly one
Gitleaks `generic-api-key` result on the public canonical OpenAPI checksum metadata label in
`P2_QUESTIONBANK_GENERATION_POLICY_V3.json`. The result did not identify a credential, Provider fact,
private locator, Prompt, seed, image, object key or signed URL.

The failed run is not rerun or reclassified as a passing candidate. CC05 remains ineffective and R39
remains current until this repair's new commit independently completes every CC05 Gate.

## Root cause and repair

The original metadata label contained the token `openapi` immediately before a high-entropy public
SHA-256 value. Gitleaks 8.24.3 therefore matched its default `generic-api-key` heuristic even though the
value is the repository's public canonical contract digest.

R40 renames only that metadata label to `baseline_contract_canonical_sha256`, updates the deterministic
contract test, recomputes the machine policy content digest, and mirrors the new policy digest in the
canonical Acceptance and Execution Protocol true-EOF blocks. The referenced OpenAPI content and its
canonical SHA-256 value do not change.

No Gitleaks allowlist, workflow, scan mode, report, threshold or secret rule is changed. The repair does
not suppress the historical finding and does not weaken any mandatory Gate.

## Frozen boundaries

```text
IMAGEGEN_CALLS_EXECUTED_IN_R40: 0
IMAGE_BYTES_CREATED_OR_READ: 0
CAL_REQ_002_CONSUMED: NO
OPENAPI_CONTENT_CHANGED: NO
MIGRATION_HEAD_CHANGED: NO
DEPENDENCY_OR_MODEL_ARTIFACT_CHANGED: NO
PRIVATE_INPUT_ACCESSED: NO
QUESTIONBANK_RELEASE_AUTHORIZED: NO
REAL_USER_FACIAL_PROCESSING_AUTHORIZED: NO
```

## Acceptance criteria

1. The machine policy content digest is canonical and matches both true-EOF mirrors.
2. The public canonical contract digest value still matches the unchanged parsed OpenAPI document.
3. Targeted policy tests and Ruff pass with no skipped mandatory case.
4. Gitleaks scans the repaired tracked material with zero result; no new exception is added.
5. The repair receives a normal non-force push and a new exact-SHA CI run with all three mandatory jobs
   and all eight artifact families passing before Security, Sol High and Principal acceptance.

`P2_M5_R40_STATUS: LOCAL_REPAIR_PENDING_TRACKED_EVIDENCE`

`CC_P2_M5_05_STATUS: CANDIDATE_NOT_ACCEPTED`

`P2_M5_STATE: EXECUTING`
