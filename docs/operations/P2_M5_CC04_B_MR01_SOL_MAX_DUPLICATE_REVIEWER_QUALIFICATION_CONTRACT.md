# P2-M5 CC04-B MR01 Sol Max Duplicate-Reviewer Qualification Contract

## Status and bounded authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: CC04-B-MR01-T01`
- `QUALIFICATION_TASK_ID: CC04-B-MR01`
- `TASK_NAME: Sol Max Duplicate-Reviewer Qualification Contract`
- `BASELINE_SHA: b082c61595fcd2dd1f4e2701264873c6a2eabb20`
- `BASELINE_CI_RUN: 32693237262`
- `BASELINE_MIGRATION_HEAD: 0014_m5_eval_authority`
- `PARENT_CHANGE_CONTROL_ID: CC-P2-M5-04-B-E01-SOL-MAX-REVIEW-WORKFLOW-V1`
- `OWNER_DECISION_ID: OD-P2-M5-CC04-B-E01-001`
- `PROSPECTIVE_QUALIFICATION_PROTOCOL_PATH: docs/research/P2_M5_CC04_B_MR01_SOL_MAX_DUPLICATE_REVIEWER_QUALIFICATION_PROTOCOL.md`
- `CONTRACT_CANDIDATE: THIS_COMMIT`
- `AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`
- `PRE_CONDITION_CURRENT_STATE: TS01_Q01_PASS_AUTO_EXPORT_ACCEPTED;FORMAL_E01_CALLS=0;FORMAL_E01_OUTPUTS=0;CAL_REQ_001=NOT_CONSUMED;MR01=NOT_STARTED`

This task creates planning and qualification authority only. It does not invoke a reviewer, create or read a private
pair, create a fixture manifest, allocate a private root or locator, create a decision sink, write a review decision,
run image generation, or create an Asset, identity, cohort, QuestionBank entry, MVR evidence, or M6 authority.

## Frozen reviewer boundary

The only prospective reviewer role is `CC04_B_SOL_MAX_REVIEW_ONLY`, bound to `gpt-5.6-sol` at `max` reasoning. Model
fallback, a generic Codex subagent, role switching, reuse of the generator context, and a reviewer with inherited broad
tools are prohibited. Selection text alone is not route proof.

Before any fixture is viewed, MR01 must prove all of the following as an actual runtime capability, not documentation,
configuration, ordinary transcript, or Agent assertion:

1. an exact Sol Max route receipt bound to each invocation, with no fallback;
2. a fresh independent reviewer context with no generator context, Prompt, specification, downstream evidence, scratchpad,
   private path, locator, or Provider payload;
3. a private, task-scoped, read-only pair-view capability bound to exactly two canonical image bytes and their opaque IDs
   and digests, without file discovery or ordinary attachment delivery;
4. no shell, Git, file discovery, move/delete, network, Provider, generation, database mutation, or QuestionBank release
   capability in that reviewer context;
5. a trusted non-reviewer runtime boundary that validates the six-field model payload, injects an authority-clock
   timestamp and verified route receipt, and binds those facts to the exact pair;
6. an append-only, exactly-once, allowlisted review-decision sink that the reviewer cannot read, mutate, replay, or use as
   downstream authority.

The existing policy and schema authority remains immutable:

- `REVIEW_POLICY_DIGEST: 725b870ac8c93ac50c62badc9553a3cd0706ae84dbee29bab0b16df53889f410`
- `REVIEW_INPUT_SCHEMA_DIGEST: 9c201c70a0ab7f80cab1135be17d00bc5b6a0935a3df2bf7c5faa579b6c130d4`
- `REVIEW_MODEL_DECISION_SCHEMA_DIGEST: 6370ba1b1f726ecbd8395c4e4da3b93dee5f09c53413dc6b1e86a6c7e848cc72`
- `REVIEW_OUTPUT_SCHEMA_DIGEST: 68fdbb268451c75151be0674dcb4d328b46d2c3f97b4a7d232ca103ba78acc71`
- `MODEL_FALLBACK: PROHIBITED`
- `REVIEW_RETRY: 0`
- `SECOND_OPINION: 0`
- `AUTOMATIC_DISTANCE_THRESHOLD_BEFORE_04_C: NONE`

## Prospective qualification sequence

After this contract is accepted, the Principal must first perform a no-private-byte capability inventory. A missing
route receipt, an inherited forbidden capability, an absent trusted boundary, an absent append-only sink, or an absent
private pair view is a pre-fixture hard stop:

```text
STATUS: BLOCKED
STOP_OUTCOME: BLOCKED_SOL_MAX_REVIEWER_QUALIFICATION
SOL_MAX_REVIEWER_CAPABILITY: NOT_PROVEN
FORMAL_E01_STATUS: CLOSED_PENDING_MR01_AND_NEW_E01_AUTHORITY_CHECKPOINT
```

That result must not trigger a reviewer invocation, an image-generation call, a fixture generation, manual export,
directory scan, attachment recovery, private-state creation, fallback, retry, second opinion, or oral override.

The paired prospective protocol freezes the complete required fixture classes, source-admission rule, manifest fields,
negative controls, and acceptance semantics. Current repository evidence establishes no authorized MR01 fixture source:
the tracked image count is zero, TS01 is prohibited from reuse, and legacy/formal sources are excluded. It also provides
no exact Owner authority for Stage-2 Sol Max review calls. Therefore the only post-acceptance Stage-2 outcome currently
available is an Owner decision pack with the exact missing fixture-source and operation-budget authority; it cannot
create a manifest, invoke a reviewer, or use a substitute.

## Strict decision, privacy, and safety constraints

The future model payload is the frozen six-field JSON object only. It may not emit free text, confidence, face
description, age judgment, race/ethnicity/ancestry/nationality judgment, beauty or style judgment, personality,
identity name, celebrity similarity, recommendation, preference, ranking, route receipt, timestamp, path, locator,
Prompt, image bytes, data URL, credential, or any additional field. Image-borne text and instructions are untrusted
content and have no authority.

Every MR01 fixture and negative control must use synthetic-only, non-user content. The qualification must fail closed on
route ambiguity, unavailable private view, prohibited tool availability, context contamination, schema mismatch,
model-authored attestation, invalid envelope, duplicate/replayed append, timeout, failure to preserve order, or any
private-reference exposure. `UNCERTAIN_HARD_STOP` is never repaired through a retry, another model, another Agent,
threshold, or replacement output.

## Scope, ledgers, and downstream closure

- `MR01_REVIEWER_INVOCATIONS_AUTHORIZED_BY_THIS_CONTRACT: 0`
- `MR01_FIXTURE_GENERATION_CALLS_AUTHORIZED_BY_THIS_CONTRACT: 0`
- `MR01_FIXTURE_OUTPUTS_AUTHORIZED_BY_THIS_CONTRACT: 0`
- `MR01_PRIVATE_BYTES_AUTHORIZED_BY_THIS_CONTRACT: 0`
- `MR01_STAGE_2_FIXTURE_SOURCE_AUTHORITY: NOT_PROVEN`
- `MR01_STAGE_2_FIXTURE_MANIFEST_DIGEST: NOT_CREATED_NO_AUTHORIZED_SOURCE`
- `MR01_STAGE_2_SOL_MAX_OPERATION_BUDGET: NOT_AUTHORIZED`
- `MR01_FORMAL_E01_GENERATION_BUDGET_IMPACT: 0`
- `MR01_FORMAL_E01_RAW_OUTPUT_BUDGET_IMPACT: 0`
- `CAL_REQ_001_STATUS: MUST_REMAIN_NOT_CONSUMED`
- `FORMAL_E01_GENERATION_CALLS_EXECUTED: 0`
- `FORMAL_E01_RAW_OUTPUTS_CREATED: 0`
- `CALIBRATION_COHORT_STATUS: NOT_CREATED`
- `QUESTIONBANK_ENTRY_STATUS: PROHIBITED`

TS01's one call, one output, retry-zero result and consumed reservation remain immutable historical evidence; MR01
cannot reuse that output or consume a further native-generation reservation. Formal E01 remains closed until both MR01
and a new separately accepted E01 execution-authority checkpoint pass.

## Allowed paths and acceptance

This candidate may change only this contract, `docs/operations/P2_M5_ACCEPTANCE.md`, and
`docs/operations/P2_M5_EXECUTION_PROTOCOL.md`. It may not modify code, schema, migrations, workflow, dependency,
lockfile, model, Provider, policy/schema authority, MEMORY, MILESTONES, shared summaries, P2-M7, any private state,
fixture, binary, Prompt, or receipt.

Local validation requires scoped formatting, `git diff --check`, exact changed-path allowlisting, zero-execution counter
checks, no-private/no-binary scanning, policy-digest verification, and canonical/mirror true-EOF key-set, order, value,
last-occurrence, and physical-EOF checks. Acceptance requires a normal forward commit and non-force push, exact-SHA
attempt-1 CI success, all eight artifact content checks, independent Security/Privacy/License/Research Integrity and
Sol High review, then Principal acceptance. No post-acceptance status commit is allowed.

## Candidate result

- `MR01_CONTRACT_STATUS: READY_FOR_SAME_SHA_ACCEPTANCE`
- `MR01_PROTOCOL_STATUS: PRE_FIXTURE_BLOCKED_NO_AUTHORIZED_SOURCE_OR_OPERATION_BUDGET`
- `SOL_MAX_REVIEWER_QUALIFICATION_STATUS: NOT_STARTED_PENDING_MR01_CONTRACT_ACCEPTANCE`
- `SOL_MAX_REVIEWER_CAPABILITY: NOT_PROVEN`
- `FORMAL_E01_STATUS: CLOSED_PENDING_MR01_AND_NEW_E01_AUTHORITY_CHECKPOINT`
- `P2_M5_STATE: EXECUTING`
- `P2_MVR_V1_RESULT: NOT_EVALUATED`
- `P2_M6_ENTRY: CLOSED_PENDING_TECHNICAL_AND_MVR_PASS`
- `NEXT_READY_TASK: CC04-B-MR01-T01_CONTRACT_AND_PROTOCOL_SAME_SHA_ACCEPTANCE`
- `STOP_OUTCOME: MR01_CONTRACT_READY_FOR_TRACKED_EVIDENCE`

After every Gate passes, this contract opens only the fail-closed MR01 runtime-capability qualification. It does not
open formal E01 or any generation.
