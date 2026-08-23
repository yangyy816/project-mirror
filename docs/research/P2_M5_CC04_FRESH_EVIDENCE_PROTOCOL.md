# P2-M5 CC04 Fresh Evidence Line Protocol

## Authority and status

- Change control: `CC-P2-M5-04` / ADR-050.
- Current bounded stage: `04-A — Owner Decision Closure, no study execution`.
- Legacy status: CC02-C is `EVIDENCE_LOCATION_LOST` / `FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE`.
- M5 status: `EXECUTING`; `P2_MVR_V1_RESULT: NOT_EVALUATED`.

This protocol preserves, rather than repairs or replaces, the CC01-C/CC02 history. It defines a potential future
independent research line and does not itself authorize a new source Asset, identity, image generation, Vision call,
transform, threshold, report, private-input read or output root.

## Separation invariants

1. Legacy reports, cases, Assets, identities, outputs, aggregates and locators are never selected, copied, normalized,
   replayed, inferred from or compared as new-study inputs.
2. New evidence receives fresh identity/Asset/policy/split/runtime/output authority and digest. It never uses legacy
   evidence IDs or retroactively changes legacy status.
3. A new successful output is not a legacy drift comparison or a CC02 diagnosis. It may only support the independently
   preregistered fresh study that produced it.
4. New private output must be registered by Principal with an opaque recoverable locator before the producing task closes.
   Missing locator/digest/type/scope evidence stops that task; disk/parent/volume discovery and reconstruction remain
   forbidden.
5. All existing product, synthetic-only, adult-boundary, anti-homogenization, no-sensitive-inference and production
   fail-closed constraints remain unchanged.

## Stage boundaries

| Stage  | Allowed outcome                                                | Forbidden outcome                                              |
| ------ | -------------------------------------------------------------- | -------------------------------------------------------------- |
| `04-G` | governance packet / `FURTHER_RESEARCH`                         | assets, providers, measurements, thresholds, private reads     |
| `04-A` | versioned proposal or explicit stop                            | legacy input reuse, hidden resource expansion, model adoption  |
| `04-B` | fresh bounded calibration cohort                               | real/legacy asset reuse, holdout access, production generation |
| `04-C` | complete fresh candidate-family evidence                       | READY/threshold selection after unseen holdout access          |
| `04-D` | immutable policy/split preregistration                         | post-access threshold or candidate edits                       |
| `04-E` | sealed identity-disjoint holdout evidence + independent review | M6 release or production enablement without all Gates          |

## `04-G` acceptance contract

- Scope: ADR-050, this protocol and forward state references only.
- Required result: a tracked, exact-SHA reviewed statement that the future line is independent and legacy evidence will
  not be regenerated, substituted or silently reclassified.
- Negative controls: attempted legacy locator discovery; use of old case/identity/Asset IDs; old-output recreation;
  unversioned resource count; threshold/candidate/algorithm decision; real or user input; dependency/model addition.
- Exit: only `04-A` proposal planning becomes eligible. It is not execution authorization. After an independently
  accepted `04-E`, a separate M5 technical/MVR disposition may be considered; that disposition is not part of `04-E`.

`CC_P2_M5_04_G: GOVERNANCE_ACCEPTED_AT_3AC41C3_RUN_32582621932_ATTEMPT_1`

`CC_P2_M5_04_A_PROPOSAL_PLANNING: ELIGIBLE_NOT_EXECUTION_AUTHORIZATION`

`CC_P2_M5_04_A_EXECUTION: CLOSED`

`CC_P2_M5_04_B_TO_E: CLOSED`

`CC02_C_INPUT_RECOVERY: EVIDENCE_LOCATION_LOST`

`CC_P2_M5_02_C_REPLAY: NOT_EXECUTED_FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE`

`P2_M5_T06_ENTRY: CLOSED`

`P2_MVR_V1_RESULT: NOT_EVALUATED`

`P2_M6_ENTRY: CLOSED_PENDING_TECHNICAL_AND_MVR_PASS`

## CC04-A Owner Decision Closure

`OD-P2-M5-CC04-001` is recorded through D01 and the Owner Decision Pack only. It supplies future source, adult-boundary, candidate-family, resource-envelope, versioning, split, negative-control, custody, and separate-disposition constraints; it does not authorize acquisition, generation, private input, cohort/Asset/identity creation, measurement, transform, threshold, holdout, runtime adoption, Provider use, or production enablement.

`CC_P2_M5_04_A_D01_CONTRACT: PASS_AT_7659EED_RUN_32592430642`

`CC04_A_OWNER_DECISION_CLOSURE: LOCAL_CANDIDATE_PENDING_VALIDATION`

`CC04_B_CONTRACT_WRITING: CLOSED_PENDING_OWNER_DECISION_CLOSURE`

`CC04_B_CONTRACT: NOT_CREATED`

`CC04_B_EXECUTION: CLOSED_PENDING_SEPARATE_CONTRACT_ACCEPTANCE`

## Final status-only acceptance checkpoint

- Current bounded stage: `CC04-A closure conditionally accepted by this checkpoint`.
- `FINAL_ACCEPTANCE_CHECKPOINT: THIS_COMMIT`.
- `AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_CHECKPOINT_SAME_SHA_CI_ARTIFACT_SECURITY_SOL_AND_PRINCIPAL_ACCEPTANCE`.
- `CC04_A_OWNER_DECISION_CLOSURE: PASS_AT_THIS_ACCEPTANCE_CHECKPOINT`.
- `CC04_B_CONTRACT_WRITING: ELIGIBLE_NOT_EXECUTION_AUTHORIZATION`.
- `CC04_B_CONTRACT: NOT_CREATED`; `CC04_B_EXECUTION: CLOSED_PENDING_SEPARATE_CONTRACT_ACCEPTANCE`.

This checkpoint opens neither `04-C` through `04-E`, T06, MVR, M6, generation, private input, cohort, Asset, identity, Vision, measurement, transform, threshold, or holdout work.
