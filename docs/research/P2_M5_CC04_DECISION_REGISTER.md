# P2-M5 CC04 Fresh Study Decision Register

## Register status

- Register version: `p2-m5-cc04-decision-register/v1`.
- Scope: `CC-P2-M5-04-A` proposal-only governance.
- Overall disposition: `ALL_CONCRETE_DECISIONS_UNDECIDED`.

This register is intentionally a list of unresolved decisions. An `UNDECIDED` row is not a provisional approval,
default, inherited value or permission to begin work. No row may be implemented until its own bounded decision task has
the required authority, validation, same-SHA CI, artifact inspection and independent review.

| ID          | Decision category                           | Current disposition | Evidence required before a later decision                                                          | Stop if missing or conflicting |
| ----------- | ------------------------------------------- | ------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------ |
| `CC04-A-01` | Fresh source/origin and rights              | `UNDECIDED`         | synthetic-only origin, rights/retention/provenance facts, fresh digest and non-legacy separation   | `LICENSE_REVIEW_REQUIRED`      |
| `CC04-A-02` | Adult and safety admission                  | `UNDECIDED`         | adult-boundary and hard-failure review evidence without age estimation or a bypass                 | `SECURITY_REVIEW_REQUIRED`     |
| `CC04-A-03` | Candidate-family admission                  | `UNDECIDED`         | fresh-family evidence, no real/User input and no legacy selection/reuse                            | `OWNER_DECISION_REQUIRED`      |
| `CC04-A-04` | Resource, retry, cost and storage envelope  | `UNDECIDED`         | independent justification and bounded operational evidence                                         | `OWNER_DECISION_REQUIRED`      |
| `CC04-A-05` | Algorithm/runtime/Provider qualification    | `UNDECIDED`         | exact provenance, license, security, telemetry, platform and fail-closed evidence                  | `LICENSE_REVIEW_REQUIRED`      |
| `CC04-A-06` | Policy and ontology authority               | `UNDECIDED`         | versioned content, digest, transition and validation authority                                     | `OWNER_DECISION_REQUIRED`      |
| `CC04-A-07` | Calibration/holdout split                   | `UNDECIDED`         | fresh identity-disjoint split evidence and sealed-access process                                   | `OWNER_DECISION_REQUIRED`      |
| `CC04-A-08` | Negative-control protocol                   | `UNDECIDED`         | controls for legacy reuse, real/User data, malformed inputs, hidden network and unsupported claims | `SECURITY_REVIEW_REQUIRED`     |
| `CC04-A-09` | Private evidence custody                    | `UNDECIDED`         | ADR-049 recoverable custody, opaque locator, digest/type/scope and cleanup evidence                | `PRIVACY_REVIEW_REQUIRED`      |
| `CC04-A-10` | Reproducibility/platform variance           | `UNDECIDED`         | version capture, repeatability and platform-variance evidence                                      | `FURTHER_RESEARCH`             |
| `CC04-A-11` | Diversity, duplicate and isolation evidence | `UNDECIDED`         | non-sensitive diversity, duplicate and mode-collapse evidence                                      | `FURTHER_RESEARCH`             |
| `CC04-A-12` | M5 disposition boundary                     | `UNDECIDED`         | proof that any technical/MVR disposition is separately decided after `04-E`                        | `OWNER_DECISION_REQUIRED`      |

## Register invariants

- No entry is a source, candidate, resource quantity, algorithm, runtime, model, Provider, policy, ontology,
  threshold, split, budget, custody locator or execution date.
- No entry may inherit a concrete value from the legacy recovery line, an upstream claim, an existing runtime or a
  planned acquisition.
- `04-E` is limited to sealed identity-disjoint holdout evidence plus independent review. It cannot release a
  QuestionBank or decide the M5 technical/MVR Gate.
- The possible honest outcomes remain `OWNER_DECISION_REQUIRED`, `LICENSE_REVIEW_REQUIRED`,
  `SECURITY_REVIEW_REQUIRED`, `PRIVACY_REVIEW_REQUIRED`, `DEFERRED_EXTERNAL_DEPENDENCY` and
  `FURTHER_RESEARCH`.

## Next permitted action

The next permitted action is validation and review of this proposal-only documentation. It is not fresh-study
execution and does not open `04-B` or a later stage.
