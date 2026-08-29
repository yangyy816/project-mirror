# CC-P2-M5-05-D0 — Built-in ImageGen Output Contract Recovery

## Status

`EXECUTION_READY`

Architecture authority: ADR-053

Implementation task: `P2-M5-R50`

## Repository truth

- Baseline branch: `codex/p2-m5-cc05a-epoch3-rollover`
- Baseline SHA: `f7e4599512a817065b7dbc6d493663409d5d17ef`
- Baseline same-SHA CI: run `33262430349`, attempt 1, three mandatory jobs PASS
- Migration head: `0014_m5_eval_authority`
- OpenAPI, schema, dependencies and workflow are unchanged by this change control
- Eight existing `.task-ci-*` directories are protected and out of scope

## Immutable incident facts

```text
CAL_REQ_002_STATUS: CONSUMED_FAILED_NO_RETRY
CAL_REQ_002_FAILURE_PHASE: OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE
CAL_REQ_002_FAILURE_REASON: GENERATED_ARTIFACT_RECEIPT_INVALID
CAL_REQ_002_DECODE_PERFORMED: false
CAL_REQ_002_DIMENSIONS_READ: false
CAL_REQ_002_QA_SCREENING_ADMISSION: 0
CAL_REQ_002_RAW_OUTPUT_CUSTODY: EVIDENCE_LOCATION_LOST
CAL_REQ_002_RETRY: PROHIBITED
NEXT_UNUSED_FORMAL_ORDINAL: CAL-REQ-003
FORMAL_CALLS_REMAINING: 30
FORMAL_RAW_CAPACITY_REMAINING: 30
GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING: 61
GLOBAL_NATIVE_OUTPUT_CONSUMED: 3
```

Attempt/failure receipts remain recoverable in project-local Git-ignored Principal custody. No raw image obtained a
project-local canonical copy. This change control must not search for, decode, regenerate, refund or replace that output.

## Objective

Freeze a forward-only contract that safely persists a built-in imagegen `image_url` data URL into Project Mirror private
custody before image decode, while preserving the existing exact-path API and immutable failed-call ledger.

## In scope

- project-local private-output custody rule;
- strict data-URL transport capture contract;
- mandatory capture sidecar and existing registration evidence binding;
- exact crash recovery without duplicate counters;
- immutable terminal-root to fresh-root rollover;
- zero-generation synthetic byte tests;
- append-only canonical/mirror current-state authority.

## Out of scope

- any imagegen call or retry;
- recovery/search/read of the lost raw output;
- image decode, dimensions, QA, screening, admission or QuestionBank selection;
- schema/migration, OpenAPI, dependency, model, Provider adapter, workflow or public API changes;
- M6, technical Gate, MVR, production or real-user facial processing.

## Frozen implementation contract

1. Existing `register_output_before_decode(...)` remains path-only and keeps its trust model.
2. New `register_imagegen_data_url_before_decode(...)` accepts only the exact data URL already hash-bound by
   `record_output_returned` to the expected opaque output ID.
3. Registration-attempt evidence commits before Base64 transport decode.
4. Transport decode is bounded and is not image/pixel decode.
5. Only strict `image/png`, `image/jpeg` and `image/webp` Base64 data URLs are accepted; declared MIME must match magic.
6. Plaintext data URL is never persisted or logged.
7. Bytes are create-new-or-verify-exact under the existing project-local overlay staging directory.
8. A capture sidecar is create-new, digest-bound and mandatory before registration can commit.
9. Existing output record/registration receipt bind capture, source/staging checksum, bytes, MIME/magic and
   `decode_performed=false` / `dimensions_read=false`.
10. Same exact predecessor/input can roll forward after a partial event/state/receipt or staging/sidecar write without
    incrementing counters twice.
11. Terminal `CAL-REQ-002` root never reopens. A new root derives all counters and `CAL-REQ-003` from its exact verified
    predecessor and records a cross-root digest binding.
12. All new private receipts/files have recoverable copies inside the project worktree's dedicated Git-ignored namespace.

## Allowed files

- `docs/adr/ADR-053-project-local-private-custody-and-imagegen-output-bridge.md`
- `docs/operations/P2_M5_CC05_D0_IMAGEGEN_OUTPUT_BRIDGE_CHANGE_CONTROL.md`
- `docs/operations/P2_M5_R50_IMAGEGEN_OUTPUT_BRIDGE_CONTRACT.md`
- `docs/operations/P2_M5_ACCEPTANCE.md`
- `docs/operations/P2_M5_EXECUTION_PROTOCOL.md`
- `AGENTS.md`
- `services/api/tests/test_questionbank_generation_policy_v3.py` for append-only D0 authority regression
- after D0 acceptance only:
  - `services/api/src/mirror_api/synthetic_dataset/private_execution_overlay.py`
  - `services/api/tests/test_private_execution_overlay.py`

## Forbidden files and actions

- `MEMORY.md` until Principal disposition;
- migrations, ORM/schema, OpenAPI/generated contracts, lockfiles, dependencies, models and workflow;
- private bytes or locators in Git;
- `.task-ci-*`, `.tmp`, unrelated worktrees or protected user changes;
- commit/push of any image or Prompt;
- any generation, Provider, Vision, transform or admission execution.

## D0 acceptance gates

```text
tracked governance diff only
→ Markdown/diff/source scans
→ candidate commit and normal non-force push
→ exact-SHA three-job CI
→ eight artifact families inspected
→ independent security/privacy/license/research review
→ Sol High final review
→ Principal acceptance
→ R50 implementation opens
```

## Stop rules

- Any need to retry/refund `CAL-REQ-002`, read lost raw bytes, weaken register-before-decode, persist data URL plaintext,
  change schema/public contract/dependency/workflow or open M6 stops R50 and returns to Principal.
- Any private output without a recoverable project-local ignored copy is `PRIVATE_OUTPUT_CUSTODY_INCOMPLETE` and cannot be
  consumed by a later task.
- D0 and R50 create zero generation calls and zero raw outputs.

## Current disposition

```text
P2_M5_STATE: EXECUTING
P2_M5_TECHNICAL_GATE: NOT_EVALUATED
P2_MVR_V1_RESULT: NOT_EVALUATED
P2_M6_ENTRY: CLOSED_PENDING_TECHNICAL_AND_MVR_PASS
D0_GENERATION_CALLS: 0
D0_RAW_OUTPUTS_CREATED: 0
D0_IMAGE_BYTES_READ: 0
D0_DECODE_QA_SCREENING_ADMISSION: 0
D0_NEXT_TASK: D0_SAME_SHA_GATES
```
