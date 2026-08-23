# P2-M5 CC04 Fresh Study Decision Register

## Register status

- Register version: `p2-m5-cc04-decision-register/v1`.
- Scope: `CC-P2-M5-04-A` proposal-only governance.
- Overall disposition: `OWNER_DECISION_RECORDED_REVIEW_AND_EVIDENCE_GATES_OPEN`.

This is a mixed-disposition register: no row remains `UNDECIDED`. Owner-accepted rows are frozen constraints, not
execution approval; review-required rows remain open; and evidence-gated rows remain not preapproved. No row alone
authorizes `04-B` execution.

| ID          | Decision category                           | Current disposition                                           | Evidence required before a later decision                                | Stop if missing or conflicting                       |
| ----------- | ------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------ | ---------------------------------------------------- |
| `CC04-A-01` | Fresh source/origin and rights              | `OWNER_SOURCE_SELECTED_PENDING_LICENSE_AND_PROVENANCE_REVIEW` | rights, retention, provenance, fresh digest, non-legacy separation       | `LICENSE_REVIEW_REQUIRED`                            |
| `CC04-A-02` | Adult and safety admission                  | `SECURITY_AND_PRIVACY_REVIEW_REQUIRED`                        | adult hard-fail review without age estimation or bypass                  | `SECURITY_AND_PRIVACY_REVIEW_REQUIRED`               |
| `CC04-A-03` | Candidate-family admission                  | `OWNER_ACCEPTED_FRESH_CANDIDATE_FAMILY_CONSTRAINTS`           | fresh four-bidirectional-dimension minimum across three region groups    | `FURTHER_RESEARCH_INSUFFICIENT_CANDIDATE_DIMENSIONS` |
| `CC04-A-04` | Resource envelope                           | `OWNER_ACCEPTED_BOUNDED_RESOURCE_ENVELOPE`                    | later envelope compliance; no consumption here                           | `FURTHER_RESEARCH_RESOURCE_ENVELOPE_EXHAUSTED`       |
| `CC04-A-05` | Algorithm/runtime/Provider qualification    | `LICENSE_AND_SECURITY_REVIEW_REQUIRED`                        | fresh provenance, license, security, telemetry, platform evidence        | `LICENSE_AND_SECURITY_REVIEW_REQUIRED`               |
| `CC04-A-06` | Policy and ontology authority               | `OWNER_ACCEPTED_NEW_VERSIONED_POLICY_ONTOLOGY_AUTHORITY`      | fresh digest-bearing versioned authority                                 | `OWNER_DECISION_REQUIRED_FOR_SCOPE_CHANGE`           |
| `CC04-A-07` | Calibration/holdout split                   | `OWNER_ACCEPTED_SEALED_IDENTITY_DISJOINT_SPLIT_RULE`          | fresh 24 plus 24 isolated and sealed split                               | `OWNER_DECISION_REQUIRED_FOR_SCOPE_CHANGE`           |
| `CC04-A-08` | Negative-control protocol                   | `SECURITY_REVIEW_REQUIRED`                                    | all required reuse, input, network, digest, leakage, and bypass controls | `SECURITY_REVIEW_REQUIRED`                           |
| `CC04-A-09` | Private evidence custody                    | `PRIVACY_REVIEW_REQUIRED`                                     | ADR-049 recoverable Principal custody and cleanup                        | `PRIVACY_REVIEW_REQUIRED`                            |
| `CC04-A-10` | Reproducibility/platform variance           | `EVIDENCE_GATED_NOT_PREAPPROVED`                              | fresh repeatability and platform evidence                                | `FURTHER_RESEARCH`                                   |
| `CC04-A-11` | Diversity, duplicate and isolation evidence | `EVIDENCE_GATED_NOT_PREAPPROVED`                              | fresh diversity, duplicate, mode-collapse, and sealed-holdout evidence   | `FURTHER_RESEARCH`                                   |
| `CC04-A-12` | M5 disposition boundary                     | `OWNER_ACCEPTED_SEPARATE_TECHNICAL_AND_MVR_DISPOSITION`       | separate post-`04-E` technical and MVR tasks                             | `OWNER_DECISION_REQUIRED_FOR_SCOPE_CHANGE`           |

## Register invariants

- No entry is execution approval, a custody locator, or an execution date. Owner-accepted constraints record source scope, envelope, policy/ontology, and split boundaries without adopting a runtime, selecting an instance, or authorizing execution.
- No entry may inherit a concrete value from the legacy recovery line, an upstream claim, an existing runtime or a
  planned acquisition.
- `04-E` is limited to sealed identity-disjoint holdout evidence plus independent review. It cannot release a
  QuestionBank or decide the M5 technical/MVR Gate.
- Current open gates are `LICENSE_REVIEW_REQUIRED`, `SECURITY_REVIEW_REQUIRED`, `PRIVACY_REVIEW_REQUIRED`,
  `EVIDENCE_GATED_NOT_PREAPPROVED`, `FURTHER_RESEARCH`, and `DEFERRED_EXTERNAL_DEPENDENCY`. A future change,
  expansion, or violation of an Owner-accepted constraint is `OWNER_DECISION_REQUIRED_FOR_SCOPE_CHANGE`.

## Next permitted action

After this Owner Decision Closure receives its own exact-SHA acceptance, the next permitted action is only `04-B`
contract writing at `ELIGIBLE_NOT_EXECUTION_AUTHORIZATION`; it neither creates nor executes `04-B`.

## Final checkpoint state

`FINAL_ACCEPTANCE_CHECKPOINT: THIS_COMMIT`

`AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_CHECKPOINT_SAME_SHA_CI_ARTIFACT_SECURITY_SOL_AND_PRINCIPAL_ACCEPTANCE`

Closure is conditionally accepted; the next permitted action is a separate `04-B` contract-writing task only. No row authorizes execution, and `CC04_B_CONTRACT: NOT_CREATED` with execution closed remains current.
