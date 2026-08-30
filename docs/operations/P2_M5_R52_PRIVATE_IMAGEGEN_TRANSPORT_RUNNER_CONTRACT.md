# P2-M5-R52 — Private ImageGen No-Echo Transport Runner

## Status

`EXECUTING`

## Incident authority

`CAL-REQ-003` was the one exact successor authorized by accepted R50/R51. The built-in image generation call returned,
but the first orchestration process used a closed non-TTY stdin pipe. The capture process therefore received an empty
string and the accepted R50 bridge correctly failed closed before image decode.

```text
CAL_REQ_003_STATUS: CONSUMED_FAILED_NO_RETRY
CAL_REQ_003_FAILURE_PHASE: OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE
CAL_REQ_003_FAILURE_REASON: IMAGEGEN_DATA_URL_HEADER_INVALID
CAL_REQ_003_DECODE_PERFORMED: false
CAL_REQ_003_DIMENSIONS_READ: false
CAL_REQ_003_QA_SCREENING_ADMISSION: 0
CAL_REQ_003_RAW_OUTPUT_CUSTODY: EVIDENCE_LOCATION_LOST
NEXT_UNUSED_FORMAL_ORDINAL: CAL-REQ-004
FORMAL_CALLS_REMAINING: 29
FORMAL_RAW_CAPACITY_REMAINING: 29
GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING: 60
GLOBAL_NATIVE_OUTPUT_CONSUMED: 4
```

The call is not refundable or retryable. R52 must not search for, recover, regenerate or replace its output.

## Objective

Provide a bounded Principal-only transport runner that is started and verified ready before a future built-in imagegen
call, disables terminal echo, accepts exactly one bounded data-URL line through stdin, and invokes the accepted R50
register-before-decode bridge without exposing private bytes or locators in command arguments or output.

## Allowed scope

- a private session-handle schema stored only in the project-local Git-ignored namespace;
- create-or-verify-exact session-handle persistence;
- digest-bound consumed-overlay verification;
- Windows console and POSIX terminal no-echo handling;
- bounded, complete, ASCII-only one-line input;
- sanitized READY and result output;
- synthetic byte fixtures and negative tests;
- append-only Acceptance and Execution Protocol evidence.

## Forbidden scope

- any image generation, Provider call, Prompt export, image decode, dimension read, QA, screening or admission;
- retry, refund or replacement of `CAL-REQ-003`;
- authorization or dispatch of `CAL-REQ-004` before R52 same-SHA gates and Principal acceptance;
- schema, migration, OpenAPI, dependency, workflow, public API or production changes;
- private locator, data URL, image bytes, Prompt or Provider payload in Git, logs, MEMORY or CI artifacts;
- M5 technical/MVR Gate, M6 entry, production or real-user facial processing.

## Frozen execution order for a future exact call

```text
verified READY overlay
→ prepare and consume one authorized ordinal
→ create digest-bound project-local private session handle
→ start no-echo runner
→ runner verifies consumed overlay and emits READY_NO_ECHO
→ only then invoke built-in imagegen
→ write returned data URL through no-echo stdin
→ R50 record-output-returned and register-before-decode
→ fresh verification
```

If the runner is not READY, imagegen must not be called. If imagegen fails before returning a data URL, the runner is
terminated and the consumed dispatch receives final failure evidence. Invalid returned transport is counted once and
fails closed; it is never silently retried.

## Acceptance criteria

- handle is canonical, create-or-verify-exact, Git-ignored and bound to one consumed overlay receipt;
- receipt containment, digest, controller, ordinal, action and opaque output bindings are verified before READY;
- non-TTY input fails before READY;
- TTY echo is disabled and restored on Windows and POSIX;
- incomplete, oversized and non-ASCII input fails closed;
- successful synthetic PNG transport reaches `OUTPUT_REGISTERED_PRE_DECODE` with zero image decode and dimensions read;
- data-URL plaintext is absent from handle, receipts and sanitized output;
- replay after registration is rejected;
- Ruff, strict mypy, focused tests, full regression and exact-SHA remote gates pass;
- independent security and Sol High final review pass before Principal acceptance.

## Post-acceptance boundary

R52 acceptance proves only the transport runner. It does not itself authorize generation. The post-acceptance successor
must name exactly one of:

```text
P2_M5_R52: PASS_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE
CAL_REQ_004_DISPATCH_AUTHORIZED: TRUE_FOR_ONE_EXACT_CALL_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE
CC04_B_EXECUTION: READY_FOR_ONE_EXACT_CAL_REQ_004_CALL_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE
FORMAL_E01_STATUS: READY_TO_EXECUTE_CAL_REQ_004_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE
P2_M5_NEXT_ACTION: EXECUTE_CAL_REQ_004
NEXT_READY_TASK: EXECUTE_CAL_REQ_004
STOP_OUTCOME: NONE_AFTER_R52_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE_ELSE_R52_PENDING_GATES
POST_ACCEPTANCE_COMMIT_REQUIRED: NO
```

or a concrete non-generation blocker/repair. It must not point back to completed R52 gates and must not create a new
Owner Gate solely for mechanical status synchronization.
