# P2-M5-R65 — custody-loss retirement and CAL-REQ-005 durable preflight

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R65`
- `OWNER_DECISION_ID: OD-P2-M5-R64-CAL004-FINAL-INDEXED-RECOVERY-001`
- `BASELINE_SHA: 4dfb939d4e31655bf65071e8b3420e95eb4d7f5e`
- `CHANGE_CLASS: FORWARD_ONLY_INCIDENT_CLOSURE_AND_NEXT_ORDINAL_AUTHORITY`
- `STATUS: EXECUTION_READY`

## Incident disposition

The final Owner-authorized path-only recovery reached its 200,000-entry
budget before it could establish an exact CAL-REQ-004 private object. This is
not proof that historical bytes or receipts never existed. It is sufficient
evidence that they are unrecoverable within the final authorized project-private
scope.

CAL-REQ-004 is therefore permanently retired with:

```text
CAL_REQ_004_STATUS: CONSUMED_REGISTERED_PRE_DECODE_PRIVATE_OBJECT_UNRECOVERABLE_WITHIN_AUTHORIZED_SCOPE
CAL_REQ_004_FINAL_DISPOSITION: FAILED_INFRASTRUCTURE_EVIDENCE_LOCATION_LOST_NO_RETRY
CAL_REQ_004_REDISPATCH: PROHIBITED
CAL_REQ_004_RETRY: PROHIBITED
CAL_REQ_004_REPLACEMENT: PROHIBITED
CAL_REQ_004_COUNTER_REFUND: PROHIBITED
CAL_REQ_004_POST_HOC_REGISTRATION: PROHIBITED
CAL_REQ_004_DECODE: NOT_EXECUTED
CAL_REQ_004_M3: NOT_EXECUTED
CAL_REQ_004_QA: NOT_EXECUTED
CAL_REQ_004_SCREENING: NOT_EXECUTED
CAL_REQ_004_ADMISSION: NOT_EXECUTED
CAL_REQ_004_PROJECT_LIVE_BYTES: UNKNOWN_NOT_CLAIMED
CAL_REQ_004_PLATFORM_COPY: EXISTS_OR_UNKNOWN_NOT_UNDER_RECOVERABLE_PROJECT_CUSTODY
```

No old overlay, receipt, state, image, Prompt, model, registry record, schema,
migration, OpenAPI, Provider, policy, resource ceiling, M6 state or QuestionBank
release changes are authorized by R65.

## CAL-REQ-005 preflight

R65 must create no image or consumed ordinal. Its only prospective execution
authority is a non-image dry-run for the versioned
`p2-m5-cal-req-005-end-to-end-durable-handle-v1` contract. The dry-run must
prove create-new staging, registry and receipt flow, terminal state and
fresh-process recovery while formal calls, raw capacity and ordinal impact all
remain zero. A decoder stub may only validate orchestration; it cannot replace
the real decode or M3 Gate.

Before any CAL-REQ-005 dispatch, an exact accepted runtime, model, zero-egress
authority and real M3 executor handle remain required. Missing authority keeps
dispatch fail closed. R65 cannot use Mock, rebuild or download a runtime, or
call image generation.

## Conditional true EOF

```text
P2_M5_R65: PASS_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE
CAL_REQ_004_STATUS: CONSUMED_REGISTERED_PRE_DECODE_PRIVATE_OBJECT_UNRECOVERABLE_WITHIN_AUTHORIZED_SCOPE
CAL_REQ_004_FINAL_DISPOSITION: FAILED_INFRASTRUCTURE_EVIDENCE_LOCATION_LOST_NO_RETRY
CAL_REQ_004_REDISPATCH: PROHIBITED
CAL_REQ_004_RETRY: PROHIBITED
NEXT_UNUSED_FORMAL_ORDINAL: CAL-REQ-005
FORMAL_CALLS_REMAINING: 28
FORMAL_RAW_CAPACITY_REMAINING: 28
GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING: 59
CAL_REQ_005_DURABLE_PREFLIGHT: REQUIRED_ZERO_IMAGE_ZERO_ORDINAL
CAL_REQ_005_DISPATCH_AUTHORIZED: TRUE_FOR_ONE_EXACT_CALL_AFTER_R65_ALL_GATES_AND_END_TO_END_DURABLE_PREFLIGHT
P2_M5_NEXT_ACTION: EXECUTE_CAL_REQ_005
NEXT_READY_TASK: EXECUTE_CAL_REQ_005
POST_ACCEPTANCE_COMMIT_REQUIRED: NO
```
