# CC-P2-M5-05-C0 — E01 Private-state Epoch-4 Rollover Authority

## Bounded task contract

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: CC-P2-M5-05-C0`
- `OBJECTIVE`: establish forward-only authority for a later epoch-4 private-state materialization without searching,
  copying, reconstructing or reusing any epoch-3 private material.
- `WHY_THIS_TASK_EXISTS`: accepted CC05-B closed the epoch-3 locator as `EVIDENCE_LOCATION_LOST`. The accepted
  formal V3 change control explicitly permits a separately authorized forward epoch, and the accepted A0 epoch-3
  rollover is the governing zero-generation precedent.
- `SCOPE`: this change-control record, complete canonical/mirror true-EOF overlays, the deterministic non-image
  authority test and one concise durable MEMORY record.
- `ALLOWED_FILES_OR_MODULES`: this record, `P2_M5_ACCEPTANCE.md`, `P2_M5_EXECUTION_PROTOCOL.md`,
  `test_questionbank_generation_policy_v3.py` and `MEMORY.md`.
- `FORBIDDEN_SCOPE`: no private root, registry, Prompt, rubric, policy instance or ledger creation; no private
  locator search; no image generation, Provider call, ordinal consumption, output, decode, QA, screening, admission,
  threshold, MVR, M6, QuestionBank release, public API, schema, migration, dependency, model or workflow change.
- `DEPENDENCIES`: accepted CC05-B candidate `40f7c6bee88196e8730f8df1a521c46775b77f5c`, run
  `33251230684`, eight inspected artifact families, independent Security and Sol High reviews, accepted formal V3
  change control, accepted A0 precedent, ADR-049, the private-input delegation protocol and Owner authority
  `OD-P2-M5-CC04-001`.
- `INPUTS_AND_ASSUMPTIONS`: epoch-3 historical tracked/redacted evidence is immutable; its execution locator is
  unavailable; `CAL-REQ-001` remains consumed/failed/no-retry; `CAL-REQ-002` remains unconsumed; the resource
  ledger remains `31/31/62`; no epoch-3 private byte or digest is available or required.
- `ACCEPTANCE_CRITERIA`: complete mirrored append-only authority, zero private materialization and zero generation,
  unchanged resource ledger, focused tests, normal non-force push, exact-SHA three-job CI, eight artifact-family
  inspections, independent Security/Privacy/License/Research review, Sol High final review and Principal acceptance.
- `VALIDATION_COMMANDS`: focused policy-v3 pytest, Ruff format/lint for the changed test, tracked-diff allowlist,
  private-material/no-path scan and canonical/mirror key-order/value comparison; same-SHA CI supplies the full Gate.
- `RECOMMENDED_AGENT: Principal`
- `RECOMMENDED_MODEL_TIER: Sol High`
- `OUTPUT_FORMAT`: tracked change-control record plus complete canonical/mirror current-state blocks; no private
  locator, path, Prompt, image byte, object key, signed URL, Provider payload or credential.
- `ESCALATION_CONDITION`: any proposal to alter the frozen resource/source/adult/synthetic-only envelope, search or
  reconstruct epoch-3, create epoch-4 private state before C0 acceptance, or change Provider/model/retry/refund/
  retention/production/real-user scope.

## Accepted predecessor

CC05-B is accepted at `40f7c6bee88196e8730f8df1a521c46775b77f5c`. Same-SHA run `33251230684`
passed all three mandatory jobs. Eight artifact families containing eleven files were inspected and bound to that
SHA and migration head `0014_m5_eval_authority`; the full Python suite reported 762 passed with one existing optional
evidence skip; Phase 1/M1/M2/M3 reported `1/98/52/46` with zero failure, error or skip; Browser Integration passed
`5/5`; Gitleaks reported zero results. Independent Security and Sol High reviews passed, and Principal accepted the
candidate. No post-acceptance commit was required.

The accepted CC05-B result remains `EVIDENCE_LOCATION_LOST`. The exact D02-R2 handle request is separately closed
negative evidence and is not reopened by this task.

## Authority basis

The accepted formal V3 change control requires stop-without-search when the current private root cannot be recovered
and expressly permits a separately authorized forward epoch. `OD-P2-M5-CC04-001` already delegates creation of new
versions, digests and Principal-owned private custody within the frozen resource, source, synthetic-only,
non-production envelope. A0 establishes the exact precedent: first accept a tracked zero-generation rollover, then
materialize the new private epoch in a separate Principal-only task.

C0 therefore requires no new Owner decision. It does not alter resource limits, Provider/model, retry/refund,
retention, the formal adult boundary, production status or real-user scope.

## Epoch-3 disposition

Epoch-3 remains immutable historical evidence. Its execution custody is retired because the exact task-scoped locator
is unavailable. C0 makes no claim that its bytes are absent, deleted or cleaned up.

The following remain prohibited:

- disk, directory, registry, Docker volume, local-storage or sibling-worktree search;
- locator guessing, latest-pointer inference or path reconstruction;
- copying, reading or hashing epoch-3 private bytes;
- reusing epoch-3 private digests as epoch-4 digests;
- asking the Owner to reconstruct Principal-created evidence; and
- treating any historical output ID, receipt ID or digest as a locator capability.

## C0 effect after acceptance

C0 is tracked authority only. It creates no private root, bootstrap, registry, specification, policy instance, Prompt,
rubric, ledger, image, output, ordinal, decode, QA, screening or admission.

```text
IMAGEGEN_CALLS_EXECUTED_IN_CC05_C0: 0
CAL_REQ_ORDINALS_CONSUMED_IN_CC05_C0: 0
RAW_OUTPUTS_CREATED_IN_CC05_C0: 0
PRIVATE_ROOTS_CREATED_IN_CC05_C0: 0
PRIVATE_BYTES_CREATED_READ_OR_COPIED_IN_CC05_C0: 0
PROMPT_POLICY_RUBRIC_MATERIALIZATION_IN_CC05_C0: 0
DECODE_QA_SCREENING_OR_ADMISSION_IN_CC05_C0: 0
```

C0 itself does not satisfy CC05-B's resume predicate because it supplies no recoverable handle. After all C0 Gates
and Principal acceptance, epoch-4 is only `PROSPECTIVE_AUTHORIZED_NOT_CREATED`, active execution custody remains
none, and the sole next task is the separate Principal-only `CC-P2-M5-05-C_PRIVATE_POLICY_MATERIALIZATION`.

## Authorized successor — CC-P2-M5-05-C

Only after C0 acceptance may Principal execute CC05-C. CC05-C must remain zero-generation and stop before dispatch.
It must:

1. select one exact task-owned target inside the already authorized repository-ignored project-private namespace;
2. prove the exact target absent, non-reparse and contained before create-new/no-overwrite;
3. create exactly one epoch-4 root, fixed bootstrap entrypoint, detached bootstrap digest and recoverable exact
   task-scoped private-output registry receipt;
4. create all-new epoch-4 private registry, generation specification, V3 policy envelope, Prompt template, admission
   rubric and assignment/request/output ledgers with all-new versions and digests;
5. copy, read, hash, infer or reconstruct zero epoch-3 private bytes or digests;
6. bind the accepted public V3 policy and immutable 32-ordinal public assignment semantics without claiming private
   byte inheritance;
7. preserve `CAL-REQ-001: CONSUMED_FAILED_NO_RETRY`, `CAL-REQ-002: NOT_CONSUMED` and `31/31/62`;
8. atomically serialize, flush, close, reread and digest every new control file, then prove fixed-entrypoint
   fresh-process recovery; and
9. emit only redacted tracked evidence with opaque IDs, versions, digests, counters and allowlisted outcomes.

CC05-C may not generate an image, consume an ordinal, read image bytes, decode, run QA, screen or admit a source.
Generation remains separately gated after CC05-C acceptance.

## Preserved accounting and boundaries

```text
CAL_REQ_001_STATUS: CONSUMED_FAILED_NO_RETRY
CAL_REQ_002_STATUS: NOT_CONSUMED
FORMAL_E01_GENERATION_CALLS_EXECUTED: 1
FORMAL_E01_RAW_OUTPUTS_CREATED: 1
FORMAL_E01_PROVISIONAL_ACCEPTED_IDENTITIES: 0
FORMAL_CALLS_REMAINING: 31
FORMAL_RAW_CAPACITY_REMAINING: 31
GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING: 62
FORMAL_E01_GENERATION_CONCURRENCY: 1
FORMAL_E01_TRANCHE_MAX_CALLS: 4
FORMAL_E01_GENERATION_RETRY: 0
```

No refund, reset, retry, replacement, threshold, holdout, MVR, M6, QuestionBank release, production Provider,
production geometry or real-user facial-processing authority is created.

## Stop conditions

Stop without creating epoch-4 private state if:

- C0 has not completed every acceptance Gate;
- accepted predecessor, resource ledger, next ordinal or public V3 authority cannot be proved;
- any operation would search, guess, enumerate, recover, copy, hash or reuse epoch-3 private state;
- a private root, Prompt, rubric, policy instance or ledger would be created during C0;
- any resource counter changes or `CAL-REQ-002` is consumed;
- any generation, output, image-byte read, decode, QA, screening or admission occurs;
- any private Prompt, locator, path, byte or Provider payload enters tracked or reviewer-visible material; or
- canonical and mirror current-state maps differ in key set, order or value.

## Candidate status

- `CC_P2_M5_05_C0_STATUS: PASS_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE`
- `AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_SAME_SHA_CI_EIGHT_ARTIFACT_CONTENT_CHECKS_SECURITY_SOL_AND_PRINCIPAL_ACCEPTANCE`
- `CC05_B_RESUME_PREDICATE_SATISFIED_BY_C0: NO`
- `E01_EPOCH_4_STATUS_AFTER_ACCEPTANCE: PROSPECTIVE_AUTHORIZED_NOT_CREATED`
- `NEXT_READY_TASK_AFTER_ACCEPTANCE: CC-P2-M5-05-C_PRIVATE_POLICY_MATERIALIZATION`
- `P2_M5_STATE: EXECUTING`
- `P2_M5_TECHNICAL_GATE: NOT_EVALUATED`
- `P2_MVR_V1_RESULT: NOT_EVALUATED`
- `P2_M6_ENTRY: CLOSED`
