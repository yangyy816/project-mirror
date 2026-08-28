# P3–P7 D02-R2 Registry R07 — Exact Predecessor Root Replay Repair

## Status

```text
TASK_ID: P3_P7_D02_R2_R07_PREDECESSOR_ROOT_REPLAY
TRACK: DEMO_PROTOTYPE
TASK_CLASS: BOUNDED_OPERATIONAL_REPAIR
STATUS: IMPLEMENTING
BASE_SHA: 48b23cb68a753228b4adcc89c13d0c6ddb7c00e1
CC11_OR_CC12: FORBIDDEN
PUBLIC_API_CHANGE: NONE
MIGRATION_OR_ORM_CHANGE: NONE
PRIVATE_ROOT_MUTATION_AUTHORIZED_BY_PLAN: NO
IMAGEGEN_CALLS_AUTHORIZED_BY_PLAN: 0
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

## Blocking defect

The single accepted E1 root receipt predates the R06 Windows ACL hardening implementation. Its immutable digest is
already frozen by the accepted migration contract, dispatch acceptance and locator-custody authority. The current R06
loader accepts only a receipt generated with the R06 implementation SHA, so it rejects the exact predecessor receipt
even though both implementations freeze the same registry schema-contract and normalized DDL.

Archiving and rebuilding the root would change the root receipt, execution-contract and common-genesis digests and
would split accepted downstream authority. Creating an E2 root would change the frozen root ID, basename and contract.
Neither path is authorized.

## Exact compatibility tuple

```text
EVIDENCE_ROOT_ID: P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT
PREDECESSOR_ROOT_RECEIPT_DIGEST: c3ae43887d51d15347153e392ca092866dff890bdcda959572cc1dd07e6195c4
PREDECESSOR_IMPLEMENTATION_SHA: 06ab0db004b6d2a8204a263762ccabb30b4e9b81
PREDECESSOR_IMPLEMENTATION_TREE: 0268ad827759c2f349363ec2f0cd924429b0b4a5
PREDECESSOR_ACCEPTANCE_CHECKPOINT_SHA: 1f3e9d2a6e81fc608f35db78fc19d3581b4c4455
PREDECESSOR_ACCEPTANCE_RECORD_DIGEST: 249f4b1840b379fb54647fa6bf7586b22448a1646f5ace0aaab1ae7666ba92b7
R06_IMPLEMENTATION_SHA: ab08a6e861ec364c62a6ab3dcf46a69483f1b741
R06_ACCEPTANCE_CHECKPOINT_SHA: 3c743cdf5167bf3484be98b4f50e0ea6c77c5f13
R06_ACCEPTANCE_RECORD_DIGEST: a7170831675c35aaf9354a12a788d16251ec40d98fcd472c8f4c78dbf3f1d1e3
REGISTRY_SCHEMA_CONTRACT_DIGEST: e45bee49655805da14e26a6d9f882245be41e2931f063b357de800b0848413d0
REGISTRY_NORMALIZED_DDL_SHA256: b92c9cf02e0593cdbbe9cb182e5fa230bd6a5845eef3c872b997dfa73eac9389
```

## Frozen repair semantics

- The predecessor implementation is historical data authority only. It must not be imported, checked out for
  execution, or used to create a root.
- The successor loader may replay only the exact predecessor receipt digest above after independently replaying the
  exact predecessor and R06 acceptance bytes from their fixed tracked Git checkpoints.
- The predecessor acceptance must remain an ancestor of the accepted successor implementation, and both must bind the
  same schema-contract and normalized DDL digests.
- The existing root receipt, registries, genesis, events and receipts are never rewritten, re-signed, renamed, copied
  or supplemented with an implementation-transition control object.
- Normal successor receipt validation remains unchanged. Any other receipt, predecessor, acceptance record, schema,
  DDL, basename, ACL, reparse state or canonical payload mismatch remains fail closed.
- Root creation continues to build only the active successor receipt. No compatibility branch may generate a
  predecessor receipt.
- Before source generation, the Principal must replay the exact root, both registry copies and all existing history;
  prove that existing validation/review outputs have no product-DAG dependency; and confirm zero existing source,
  M3/M4, screening, QuestionBank or PostgreSQL-admission evidence.

## Implementation ownership and validation

Only the Integration Principal may change:

```text
services/api/src/mirror_api/demo_d02_r2_private_registry.py
services/api/tests/test_demo_d02_r2_private_registry.py
docs/operations/P3_P7_D02_R2_REGISTRY_R07_IMPLEMENTATION_ACCEPTANCE.json
```

Mandatory validation is targeted pytest, Ruff format/check, strict mypy, `git diff --check`, independent exact-SHA
review, same-SHA CI and Principal acceptance. Until all pass, the private root remains read-only and ImageGen calls
remain zero.

## Exit predicate

```text
R07_IMPLEMENTATION_ACCEPTED: REQUIRED
EXACT_E1_PREDECESSOR_REPLAY: PASS_REQUIRED
TWO_COPY_REGISTRY_REPLAY: PASS_REQUIRED
EXISTING_PRODUCT_EVIDENCE: MUST_EQUAL_0
GENERATION_PREREGISTRATION_AND_8_NAME_RECEIPTS: REQUIRED_BEFORE_CALL_1
IMAGEGEN_ORDINALS: [1, 2, 3, 4]
IMAGEGEN_RETRY: 0
IMAGEGEN_CONCURRENCY: 1
D02_R2_TASK_ACCEPTED: NO
D03_D04_B_D07_B: BLOCKED
```
