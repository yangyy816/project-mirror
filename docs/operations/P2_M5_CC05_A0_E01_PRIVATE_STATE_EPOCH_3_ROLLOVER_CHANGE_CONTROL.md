# CC-P2-M5-05-A0 — E01 Private-state Epoch-3 Rollover Authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: CC-P2-M5-05-A0`
- `TASK_NAME: E01 Private-state Epoch-3 Rollover Authority`
- `OWNER_AUTHORITY: OD-P2-M5-CC04-001`
- `PREDECESSOR_ACCEPTED_AUTHORITY: cdcc2591f42ead6769107e423eecce16fa9261d7`
- `PREDECESSOR_CI_RUN: 33238015901`
- `PREDECESSOR_STATUS: CC05_AND_R40_PRINCIPAL_ACCEPTED`
- `CHANGE_CLASS: FORWARD_PRIVATE_CUSTODY_AUTHORITY_ONLY`
- `AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`

## Trigger and evidence boundary

After CC05/R40 acceptance, the current Principal session no longer has the exact task-scoped private locator for the
accepted E01 epoch-2 control state. The accepted logical recovery receipt, tracked bootstrap digest, resource facts and
current ordinal remain valid historical evidence, but none is a locator capability. ADR-049 prohibits disk search,
parent enumeration, globbing, path guessing, sibling lookup or silent byte reconstruction.

This change control makes no claim that the epoch-2 root or bytes are absent, deleted or cleaned up. It retires only
their execution custody and preserves the possibility of orphaned non-user synthetic-local metadata. Epoch-2 private
state, registry, specification, Prompt, assignment ledger and locator are prohibited from future recovery or reuse.

The existing Owner decision delegates creation of new versions, digests and Principal-owned private custody receipts
inside the frozen resource, source, synthetic-only and non-production envelope. A new Owner decision is therefore not
required for this zero-generation rollover. Any change to resource limits, Provider/model, retry/refund, retention,
production, real-user handling or the formal adult boundary remains Owner-gated.

## A0 effect after acceptance

A0 is tracked authority only. It creates no private root, bootstrap, control file, Prompt, image, ordinal, output,
decode, QA, screening, admission or cleanup action.

```text
IMAGEGEN_CALLS_EXECUTED_IN_CC05_A0: 0
CAL_REQ_ORDINALS_CONSUMED_IN_CC05_A0: 0
RAW_OUTPUTS_CREATED_IN_CC05_A0: 0
PRIVATE_ROOTS_CREATED_IN_CC05_A0: 0
PRIVATE_BYTES_CREATED_OR_READ_IN_CC05_A0: 0
DECODE_QA_SCREENING_OR_ADMISSION_IN_CC05_A0: 0
```

After every A0 Gate and Principal acceptance, the epoch-2 execution custody is retired as
`EVIDENCE_LOCATION_LOST_NO_SCAN_NO_GUESS`. Active execution custody becomes `NONE_PENDING_CC05_A`; epoch-3 is only
`PROSPECTIVE_AUTHORIZED_NOT_CREATED`. `CAL-REQ-002` remains unconsumed and cannot be dispatched.

## Authorized successor — CC-P2-M5-05-A

Only after A0 acceptance may the Principal execute `CC-P2-M5-05-A_PRIVATE_POLICY_MATERIALIZATION`. CC05-A must remain
zero-generation and stop before any dispatch. It must:

1. select one exact task-owned target inside the repository-ignored project-private namespace already authorized by
   ADR-049 and the Owner's project-private retention rule;
2. prove the exact target absent, non-reparse and contained before using create-new/no-overwrite operations;
3. create exactly one epoch-3 root, one fixed bootstrap entrypoint, one detached bootstrap digest and one recoverable
   Principal private-output registry receipt;
4. create new epoch-3 private registry, generation specification, V3 policy envelope, Prompt template, admission
   rubric and assignment/request/output ledgers; no epoch-2 private byte or digest may be copied or reconstructed;
5. bind the accepted V3 digest `984bd78a39a002d179afcb3a17ba6eb8004e2588363ea9cbbc943e4f80d3fe19`,
   the accepted CC05 authority, the public immutable 32-ordinal morphology/style table and the preserved resource
   accounting;
6. preserve `CAL-REQ-001` as consumed, failed, non-admissible and non-retryable, while making only
   `CAL-REQ-002..CAL-REQ-032` prospective;
7. preregister an exact adult-only declared-age assignment for every remaining ordinal before any output is seen,
   using only `ADULT_18_19` and `ADULT_20_25` and the V3 pack distribution contract;
8. atomically serialize, flush, close, reread and digest every control file, refresh the bootstrap and detached digest,
   and pass fixed-entrypoint fresh-process recovery; and
9. produce only redacted tracked evidence containing opaque IDs, versions, digests, counters and allowlisted outcomes.

The new private ledger may reproduce the public assignment semantics, but it is a new forward ledger and must not be
described as an epoch-2 byte recovery. The complete Prompt, seed value, private locator, path, image bytes, object key,
signed URL, Provider payload and credentials remain outside Git, ordinary logs, CI artifacts, MEMORY and reviewer
packets.

## Preserved accounting and boundaries

```text
CAL_REQ_001_STATUS: CONSUMED_FAILED_NO_RETRY
FORMAL_E01_GENERATION_CALLS_EXECUTED: 1
FORMAL_E01_RAW_OUTPUTS_CREATED: 1
FORMAL_E01_PROVISIONAL_ACCEPTED_IDENTITIES: 0
FORMAL_CALLS_REMAINING: 31
FORMAL_RAW_CAPACITY_REMAINING: 31
GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING: 62
NEXT_UNUSED_FORMAL_ORDINAL: CAL-REQ-002
CAL_REQ_002_STATUS: NOT_CONSUMED
FORMAL_E01_GENERATION_CONCURRENCY: 1
FORMAL_E01_TRANCHE_MAX_CALLS: 4
FORMAL_E01_GENERATION_RETRY: 0
```

No refund, reset, retry, replacement, threshold, holdout, MVR, M6, QuestionBank release, production Provider,
production geometry or real-user facial-processing authority is created.

## Stop conditions

Stop without creating an alternate root or epoch-4 if any of the following occurs:

- A0 has not completed all acceptance Gates;
- predecessor authority, counter, ordinal or V3 digest cannot be proved;
- an operation would search, guess, enumerate, recover or reuse epoch-2;
- the exact epoch-3 target exists, is a reparse point, escapes its approved namespace or has uncertain authority;
- create-new, atomic serialization, digest verification or fresh-process recovery fails;
- any resource counter changes, `CAL-REQ-001` is rebound/retried/replaced, or `CAL-REQ-002` is consumed;
- any image generation, image-byte read, decode, QA, screening or admission occurs in A0 or CC05-A;
- any private Prompt, locator, path, byte or Provider payload enters tracked or reviewer-visible material; or
- canonical and mirror current-state maps differ in key set, order or value.

## Acceptance criteria

1. The changed scope is this record, the canonical/mirror true-EOF overlays and the existing deterministic authority
   test required to keep append-only tail parsing exact.
2. Epoch-2 historical evidence is preserved without absence or cleanup claims; recovery/search/reuse remains prohibited.
3. Epoch-3 remains prospective and uncreated; active execution custody is none; generation and ordinal counters are zero
   for A0.
4. `1/1/0`, `31/31/62`, `CAL-REQ-001` and `CAL-REQ-002` facts are unchanged.
5. V3 adult-only, nonsexual, synthetic-only, no-scoring, pair, Demo and private-data boundaries remain unchanged.
6. Scoped formatting, diff/allowlist/no-leak/counter/tail tests pass, followed by normal non-force push, exact-SHA CI,
   all eight artifact-family inspections, independent Security/Privacy/License/Research review, Sol High final review
   and Principal acceptance.

`CC_P2_M5_05_A0_STATUS: LOCAL_CANDIDATE_PENDING_TRACKED_GATES`

`P2_M5_STATE: EXECUTING`

`P2_M5_TECHNICAL_GATE: NOT_EVALUATED`

`P2_MVR_V1_RESULT: NOT_EVALUATED`

`P2_M6_ENTRY: CLOSED`
