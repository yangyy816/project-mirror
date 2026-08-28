# P3–P7 D02-R2 Execution Epoch 02 — Forward Product Execution Recovery

## Status

```text
AUTHORITY_ID: P3_P7_D02_R2_EXECUTION_EPOCH_02
PARENT_CHANGE_CONTROL: P3_P7_D02_CC_08
CHANGE_CLASS: FORWARD_PRODUCT_EXECUTION_RECOVERY
TRACK: DEMO_PROTOTYPE
GOAL_EPOCH_ID: P3_P7_COMPLETE_DEMO_EPOCH_02
STATUS: PRINCIPAL_ACCEPTED
BASE_SHA: 1caa313793eebcaf704a4332360928c87076e739
INDEPENDENT_PLAN_REVIEW: PASS
INDEPENDENT_REVIEWED_CANDIDATE_SHA256: 196e2b3b02b417d86addfe89d8e8440dca80f6a40098c507bae2d81e251fdf54
PRINCIPAL_ACCEPTANCE_BOUNDARY: PLAN_ONLY_IMPLEMENTATION_NOT_ACCEPTED
CC11_OR_CC12: FALSE
PUBLIC_API_CHANGE: NONE
MIGRATION_OR_ORM_CHANGE: NONE
PROVIDER_CONTROL_PLANE_INVOCATION_CHANGE: NONE
RESERVE_AUTHORIZATION_STATE_CHANGE: E2_ONLY_ACTIVATION
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

This authority directly unblocks the D02-R2 source cohort after one accepted
ImageGen call returned a valid PNG that the local receiver falsely rejected.
It is not a new evidence, custody, host-binding, ETW, or environment-hardening
cycle. CC09 and CC10 remain closed and `EVIDENCE_CUSTODY_HOST_BINDING` remains
`FROZEN_DEFERRED`.

## Predecessor terminal state

The following E1 history is immutable and must never be rewritten, completed
late, or reclassified as admitted product evidence:

```text
E1_EVIDENCE_ROOT_ID: P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT
E1_STATE: FAILED_CLOSED
E1_ORDINAL_1: CONSUMED
E1_ORDINALS_2_4: CLOSED_UNUSED
E1_LATE_PUBLISH: FORBIDDEN
E1_ROOT_MUTATION: FORBIDDEN
E1_ROOT_RECEIPT_DIGEST: c3ae43887d51d15347153e392ca092866dff890bdcda959572cc1dd07e6195c4
E1_EXECUTION_CONTRACT_DIGEST: d362c3fb25303ca9e1863bdf8fc4f92edb8c044cc42751280bec26595eaca388
E1_TERMINAL_REGISTRY_EVENT_COUNT: 10
E1_TERMINAL_REGISTRY_HEAD: 4792ec870f1db3b1b8b9086a477eeb6369d4bfb3f2200bf8ab48d2af13320b66
E1_TERMINAL_SNAPSHOT_DIGEST: ebba32ed2645d175d4a3ae75b6b50a3c63a3e75d9a4019ef301cc7f8e8a3e70b
E1_NEGATIVE_RECEIPT_AUTHORITY_DIGEST: edfb8733e6742b986c8d14d061d3ac3106c72931ed48b85a9efe2e67105bf9b9
E1_PRODUCT_EVENT_COUNT: 0
E1_PARTIAL_SOURCE_AUTHORITY: ZERO
E1_POSTGRESQL_ADMISSION: NOT_STARTED
```

The first call returned one `image/png` data URL whose decoded bytes were a
valid single-frame PNG. That fact classifies the defect as
`VALID_MEDIA_NOT_ADMITTED_DUE_TO_LOCAL_RECEIVER_ASSERTION_FALSE_NEGATIVE`; it
does not authorize late E1 admission.

## E2 execution identity

```text
E2_TASK_ID: P3_P7_D02_R2_EXECUTION_02
E2_SOURCE_PRODUCER_TASK_ID: P3_P7_D02_R2_SOURCE_COHORT_02
E2_REVIEW_TASK_ID: P3_P7_D02_R2_EVIDENCE_REVIEW_02
E2_DISPATCH_EPOCH: 2
E2_PRIVATE_NAMESPACE_ID: pm-p3p7-d02-r2-cc08-e2
E2_EVIDENCE_ROOT_ID: P3_P7_D02_R2_CC08_E2_EVIDENCE_ROOT
E2_EVIDENCE_ROOT_BASENAME: p3-p7-d02-r2-cc08-e2-evidence
E2_REGISTRY_COPY_A_ID: P3_P7_D02_R2_CC08_E2_REGISTRY_A
E2_REGISTRY_COPY_B_ID: P3_P7_D02_R2_CC08_E2_REGISTRY_B
E2_SOURCE_COUNT: 4
E2_CALLS_AUTHORIZED: 4_RESERVE_CALLS
E2_RETRY_CEILING: 0
E2_CONCURRENCY: 1
E2_OUTPUTS_PER_CALL: 1
TOTAL_ACTUAL_CALL_CEILING_AFTER_E2: 5
ORIGINAL_MAXIMUM_TOTAL_CALL_CAPACITY: 8
```

The four E2 calls activate the four reserve calls already frozen by the
accepted generation capability. They do not transfer E1 ordinals 2–4. E2 has
new ordinals 1–4, output IDs, name receipts, allocation manifest and producer
dispatch.

## Designated evidence folder

All E2 private bytes and receipts must remain inside the one Principal-chosen,
Git-external folder whose basename is
`p3-p7-d02-r2-cc08-e2-evidence`. The absolute locator remains Principal-only.
The folder must not be a worktree, `.tmp/`, ordinary CI artifact, cache,
coordination mailbox, Downloads/Desktop folder, cloud-synced folder, symlink,
junction or reparse point.

The first immutable file is exactly:

```text
D02_R2_EVIDENCE_ROOT_NAME_RECEIPT.json
```

No source, provenance, registry, allocation or failure bytes may be written
before that name receipt is durably created and replayed. Before call 1 the
Principal must complete this exact non-cyclic sequence:

1. initialize matching empty A/B registries;
2. create the three output-name receipts for the preregistration, allocation
   manifest and producer dispatch;
3. create the eight source/provenance output-name receipts and one preallocated
   cohort-failure `NEGATIVE_RECEIPT` name receipt;
4. create, seal and register the generation preregistration as committed event
   1 in both copies;
5. create, seal and register the allocation manifest as committed event 2 in
   both copies;
6. create, seal and register the producer dispatch as committed event 3 in both
   copies; and
7. replay both copies and require equal event count `3`, equal ordered roles,
   equal head and equal semantic snapshot before releasing call 1.

The registry is empty only immediately after initialization. It is not empty at
the ImageGen release boundary. None of the eight source/provenance name receipts
or the failure name receipt is a registered output until its corresponding
output actually exists, is sealed and is committed through both copies.

The unused failure name receipt is allocation evidence only and does not state
that a failure occurred.

## Registry implementation isolation

The accepted E1 implementation and its acceptance records remain byte-for-byte
unchanged and are executable only from the exact accepted detached E1 SHA for
read-only replay. E2 must not modify, import as a writer, monkeypatch, context
switch or globally reconfigure E1.

E2 uses a separate tracked writable implementation:

```text
services/api/src/mirror_api/demo_d02_r2_private_registry_e2.py
services/api/tests/test_demo_d02_r2_private_registry_e2.py
```

It preserves the E1 SQLite DDL, schema-contract digest, canonical event schema,
append-only triggers, singleton roles and two-copy transaction/recovery
algorithm, while independently binding the E2 root, task, namespace, copy IDs
and epoch. Cross-epoch receipt, registry, event, allocation or fully re-signed
payload splices fail closed before mutation.

The intentional branch-local code duplication is accepted for this prototype
because it preserves E1 replay and minimizes product delay. A future formal
promotion must consolidate the engine under a new formal authority; it must
not cherry-pick either Demo registry as production authority.

## Reserve activation and request authority

The accepted E1 generation capability and its tracked JSON remain unchanged.
E2 adds one narrow reserve-activation/request implementation with exact
ownership:

```text
services/api/src/mirror_api/demo_d02_r2_generation_epoch2.py
services/api/tests/test_demo_d02_r2_generation_epoch2.py
```

The implementation validates and binds all of the following before it may
construct any request:

```text
ACCEPTED_CAPABILITY_DIGEST: 891988bd0abe14c0c83c6750d63c36029b65053041049f1892819d75272b2696
ACCEPTED_E2_PLAN_DIGEST: EXACT_FINAL_TRACKED_PLAN_DIGEST
E1_TERMINAL_REGISTRY_HEAD: 4792ec870f1db3b1b8b9086a477eeb6369d4bfb3f2200bf8ab48d2af13320b66
E1_ACTUAL_CALL_COUNT: 1
E2_DISPATCH_EPOCH: 2
E2_ROOT_ID: P3_P7_D02_R2_CC08_E2_EVIDENCE_ROOT
E2_TASK_ID: P3_P7_D02_R2_EXECUTION_02
E2_PRODUCER_TASK_ID: P3_P7_D02_R2_SOURCE_COHORT_02
E2_PRIVATE_NAMESPACE_ID: pm-p3p7-d02-r2-cc08-e2
E2_NEW_OUTPUT_IDS_AND_ALLOCATIONS: EXACTLY_FOUR_DISTINCT_PAIRS
E2_RESERVE_CALLS_AUTHORIZED: 4
E2_RETRY_CEILING: 0
E2_CONCURRENCY: 1
TOTAL_ACTUAL_CALL_CEILING: 5
```

The final tracked plan digest is injected by the accepted implementation
closure; the literal placeholder above is never accepted at runtime. The
module then freezes:

```text
ACCEPTED_FORWARD_CHANGE_CONTROL: THIS_AUTHORITY
NEW_DISPATCH_EPOCH: 2
NEW_OUTPUT_IDS: REQUIRED
NEW_ALLOCATIONS: REQUIRED
RESERVE_CALLS_AUTHORIZED: 4
RESERVE_STATE: ACTIVATED_FOR_E2_ONLY
PRIMARY_OR_E1_CALLS_AUTHORIZED: 0
```

The only remote control-plane invocation remains `image_gen.imagegen`.
Direct HTTP, SDK, URL input, reference images, credentials, arbitrary network
clients and production Provider calls remain forbidden. Prompt text and
locators remain Principal-only and never enter Git, registry, logs, MEMORY or
reports.

The public-egress exception is a default-deny, single-use, ordinal-scoped
control-plane lease. It is acquired immediately before one approved call and
revoked in an unconditional `finally` boundary as soon as that call returns,
raises, is cancelled or is interrupted. PNG validation, private writes,
sealing and registry commits all execute after revocation with
`PUBLIC_INTERNET_EGRESS: DENIED`. Any stop, invalid envelope, write failure,
seal failure or registration failure also verifies that no lease remains; a
lease cannot be carried to the next ordinal.

## Receiver repair contract

The receiver is a new tracked local boundary:

```text
services/api/src/mirror_api/demo_d02_r2_generation_receiver.py
services/api/tests/test_demo_d02_r2_generation_receiver.py
```

It accepts only one `image_url: str`; `output_hint` is ignored by the caller and
is never opened. The only accepted envelope is the exact ASCII prefix
`data:image/png;base64,` followed by canonical Base64.

Frozen validation configuration:

```text
MEDIA_TYPE: image/png
MAXIMUM_BYTES: 20971520
MAXIMUM_CANONICAL_BASE64_PAYLOAD_BYTES: 27962028
MAXIMUM_COMPLETE_DATA_URL_ASCII_BYTES: 27962050
MINIMUM_EDGE_PIXELS: 64
MAXIMUM_EDGE_PIXELS: 8192
MAXIMUM_PIXEL_COUNT: 40000000
FRAME_COUNT: 1
ANIMATION: FORBIDDEN
TRAILING_BYTES_AFTER_IEND: FORBIDDEN
```

The receiver must validate, in memory and before any write:

- exact data-URL shape and canonical strict Base64;
- ASCII payload length no greater than `4 * ceil(MAXIMUM_BYTES / 3)` before
  invoking Base64 decode, and complete data-URL length no greater than the
  prefix plus that payload;
- decoded byte ceiling and PNG signature;
- bounded chunk lengths, CRC for every chunk, IHDR first, one final IEND and no
  trailing bytes;
- Pillow PNG verify, reopen/load, exact format, single frame, dimensions and
  pixel ceiling.

Only then may the Principal-owned destination capability perform direct
create-new writing. The sequence is complete-write, file `fsync`, close,
parent-directory durability, no-follow bounded reread, byte equality, rehash
and redecode. The receiver never resolves a root locator and never seals or
registers an output.

## Per-call execution sequence

For each E2 ordinal, serially:

```text
validate exact request and unused allocation
→ invoke one approved ImageGen call
→ receive and validate PNG fully in memory
→ create-new source bytes at the preallocated destination
→ durability and independent replay
→ create provenance JSON without Prompt, locator or Provider guesses
→ create source/provenance seals
→ append identical A/B registry transactions
→ create generation receipt
→ verify committed registry heads before the next call
```

Any failed call, invalid envelope, failed write, failed seal or failed
registration consumes that E2 ordinal, sets the E2 cohort `FAILED_CLOSED` and
closes later E2 calls. There is no retry, replacement, suffix or fifth E2 call.

## Mandatory validation

Before E2 root creation or ImageGen:

- exact E1 detached replay, two-copy equality, 10-event terminal head and zero
  product event count;
- exact plan review and Principal acceptance;
- E2 registry fresh-root/create/replay/append/recovery/corruption tests;
- E1 root receipt and registry before/after manifest equality;
- cross-epoch splice and E1-mutation rejection tests;
- receiver positive PNG and all envelope/container/decode/destination failure
  tests;
- success, exception, invalid envelope, cancellation, interruption,
  write/seal/register failure and every stop rule all revoke the ordinal-scoped
  control-plane lease before any further work;
- Ruff format/check, strict mypy, targeted pytest and `git diff --check`;
- changed-code same-SHA CI before private execution.

After four source registrations, the core execution returns to
`PUBLIC_INTERNET_EGRESS: DENIED` for M3, M4, screening, PostgreSQL import and all
subsequent D02 work.

## Stop rules

```text
E1_MUTATION_ATTEMPT_STOP
E1_LATE_PUBLISH_STOP
E2_FORWARD_AUTHORITY_MISSING_OR_MISMATCH_STOP
E2_PREDECESSOR_TERMINAL_DIGEST_MISMATCH_STOP
E2_ROOT_NAME_COLLISION_STOP
E2_OUTPUT_NAME_OR_ID_COLLISION_STOP
E2_CALL_LEDGER_PRIOR_COUNT_NOT_EXACTLY_1_STOP
E2_CALL_CEILING_STOP
E2_RETRY_CEILING_STOP
E2_CONCURRENCY_CEILING_STOP
E2_RECEIVER_ENVELOPE_STOP
E2_SOURCE_DECODE_STOP
E2_SOURCE_OUTPUT_REGISTRATION_FAILED
E2_PROMPT_OR_LOCATOR_LEAK_STOP
GENERATION_CAPABILITY_AUTHORITY_MISMATCH_STOP
GENERATION_RESERVE_CALL_NOT_AUTHORIZED_STOP
EXTERNAL_RUNTIME_DEPENDENCY_FOUND
```

## Exit boundary

Successful four-source generation advances only to M3/M4 source observation
and pair screening. It does not accept D02-R2. D02-R2 acceptance still requires
the real 4-source / 48-case / 96-M4 / 144-result-M3 / 48-gate / 48-manual-review
/ 52-image / 1326-pHash / 24-screened-pair / 16-selected-pair execution and the
single-transaction PostgreSQL QuestionBank admission.

```text
D02_R2_TASK_ACCEPTED: NO
D03: BLOCKED_PENDING_D02_R2_TASK_ACCEPTED
D04_B: BLOCKED_PENDING_D02_R2_AND_D03_TASK_ACCEPTED
D07_B: BLOCKED_PENDING_D02_R2_AND_D03_TASK_ACCEPTED
REAL_USER_VALIDITY: NOT_EVALUATED
PRODUCTION_SECURITY: DEFERRED_FOR_FORMAL_PHASE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```
