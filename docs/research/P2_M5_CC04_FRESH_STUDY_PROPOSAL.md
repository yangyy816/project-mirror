# P2-M5 CC04 Fresh Study Proposal

## Status and authority

- Document version: `p2-m5-cc04-fresh-study-proposal/v1`.
- Status: `OWNER_DECISION_RECORDED_REVIEW_AND_EVIDENCE_GATES_OPEN_NO_EXECUTION_AUTHORITY`.
- Task: `CC-P2-M5-04-A`.
- Authority: ADR-041, ADR-047, ADR-049, ADR-050, the CC04 fresh-evidence protocol, and the accepted CC04-A
  proposal-task contract.
- Current milestone: P2-M5 is `EXECUTING`; `P2_MVR_V1_RESULT: NOT_EVALUATED`.

This remains a planning artifact, not a study specification or execution approval. `OD-P2-M5-CC04-001` now records its
source scope, envelope, candidate-family, versioning, split, control, custody, and disposition constraints in the Owner
Decision Pack. License, provenance, security, privacy, runtime qualification, reproducibility, diversity, duplicate,
and isolation outcomes remain open or evidence-gated; no candidate, threshold, tolerance, formula, runtime result,
custody locator, schedule, or implementation path is selected.

## Purpose

The only proposed future sequence is:

```text
04-A proposal-only decision closure
→ 04-B fresh calibration
→ 04-C fresh calibration and diagnostic evidence
→ 04-D immutable preregistration
→ 04-E sealed identity-disjoint holdout and independent review
→ separate M5 technical/MVR disposition
```

Every arrow requires an independently accepted bounded task. A satisfactory `04-E` result is not itself an M5
technical or MVR decision.

## Non-negotiable boundaries

- All possible future evidence remains synthetic-only, private and independently versioned. No real-person, User, or
  sensitive-classification input is in scope.
- The legacy recovery line is historical context only. It must not be selected, discovered, copied, reconstructed,
  inferred from, compared against, or used to substitute fresh evidence.
- Every future source, Asset, identity, measurement, transform, signature, policy, split, runtime/model manifest,
  output and report requires new authority, a fresh version/digest, and ADR-049 recoverable custody.
- The existing adult boundary, no-beauty-score, no-sensitive-inference, anti-homogenization and production-fail-closed
  invariants remain unchanged. A proposal cannot introduce an adult-policy exception or a minor-ambiguity bypass.
- This document cannot authorize source acquisition, generation, download, installation, private-input access,
  model/runtime adoption, measurement, transform, threshold selection, or downstream Gate opening.

## Required independent decisions before any 04-B work

| Decision category                        | Required admission evidence                                                                                           | Mandatory independent disposition                                       |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Fresh origin and rights                  | source classification, origin, ownership/rights, retention and provenance evidence                                    | `LICENSE_REVIEW_REQUIRED` until accepted                                |
| Adult and safety boundary                | synthetic-only and adult-boundary evidence; review process that cannot bypass a hard failure                          | `SECURITY_REVIEW_REQUIRED` and `PRIVACY_REVIEW_REQUIRED` until accepted |
| Candidate-family admission               | fresh candidate manifest compliance with the accepted constraints                                                     | `OWNER_ACCEPTED_FRESH_CANDIDATE_FAMILY_CONSTRAINTS`                     |
| Bounded resource envelope                | future compliance with the accepted bounded envelope                                                                  | `OWNER_ACCEPTED_BOUNDED_RESOURCE_ENVELOPE`                              |
| Algorithm, runtime and Provider boundary | qualification tier, model/runtime provenance, license, telemetry and zero-network assessment                          | `LICENSE_REVIEW_REQUIRED` and `SECURITY_REVIEW_REQUIRED` until accepted |
| Policy and ontology                      | fresh digest-bearing authority matching the accepted versioning constraint                                            | `OWNER_ACCEPTED_NEW_VERSIONED_POLICY_ONTOLOGY_AUTHORITY`                |
| Calibration and holdout separation       | fresh split implementation matching the accepted sealed isolation rule                                                | `OWNER_ACCEPTED_SEALED_IDENTITY_DISJOINT_SPLIT_RULE`                    |
| Negative controls                        | explicit controls for legacy reuse, real/User input, malformed/tampered inputs, hidden network and unsupported claims | `SECURITY_REVIEW_REQUIRED` until accepted                               |
| Private evidence custody                 | ADR-049 task receipt, opaque recoverable locator, digest/type/scope and cleanup plan                                  | `PRIVACY_REVIEW_REQUIRED` until accepted                                |
| Reproducibility and platform evidence    | version capture, repeatability plan and platform-variance evidence                                                    | `FURTHER_RESEARCH` if insufficient                                      |
| Diversity and isolation evidence         | non-sensitive morphology/style diversity, duplicate and mode-collapse evidence                                        | `FURTHER_RESEARCH` if insufficient                                      |
| M5 disposition separation                | separate post-`04-E` technical and MVR disposition tasks                                                              | `OWNER_ACCEPTED_SEPARATE_TECHNICAL_AND_MVR_DISPOSITION`                 |

The Owner-accepted dispositions in this table are synchronized summaries of `OD-P2-M5-CC04-001`, the Owner Decision
Pack, and the Decision Register. The table does not replace those authorities or grant execution authority. The bounded
resource envelope and every other Owner-accepted constraint remain in force exactly as recorded; this proposal does not
create, modify, expand, transfer, or consume them.

## Stop and escalation rules

- Missing or unknown authority, source rights, retention, telemetry, artifact, custody or qualification facts result in
  `FURTHER_RESEARCH`, `DEFERRED_EXTERNAL_DEPENDENCY`, or the applicable review-required state; they must not be
  represented by placeholder values.
- Within the already accepted scope, missing source-rights, retention, telemetry, runtime-qualification,
  threshold/formula/candidate evidence, custody-implementation evidence, or other required facts resolve through their
  named License, Security, Privacy, evidence, deferred-dependency, or `FURTHER_RESEARCH` Gate. They must not be
  represented by placeholders or silently promoted to Owner approval.
- Only a future change, expansion, exception, or violation affecting architecture, schema/public contract, a Product
  Invariant, the adult boundary, Provider/production scope, the accepted resource envelope, the accepted
  calibration/holdout isolation rule, or the accepted custody boundary is `OWNER_DECISION_REQUIRED_FOR_SCOPE_CHANGE`
  before a later task is written. Implementing the already accepted constraints does not require the same Owner decision
  again.
- Any legacy-evidence reference that would affect selection, comparison, replacement or execution is a hard stop.
- Any request that would expose private bytes, a locator, Prompt, object key, signed URL or credential is a hard stop.

## Current result

`04-A` now has a proposal, decision register, and Owner Decision Pack only. Once this closure receives exact-SHA
acceptance, only `04-B` contract writing becomes eligible; the contract remains uncreated and execution remains closed.
`04-B` through `04-E`, T06, MVR, M6, production geometry, QuestionBank release, and real-user processing remain closed.
