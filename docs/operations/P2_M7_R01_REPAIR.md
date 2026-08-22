# P2-M7-R01 — Bounded-task contract completeness

## Problem

The initial P2-M7 T01 candidate froze the correct architecture boundary but abbreviated T01–T08 cards. It did not
explicitly provide every standing contract field required for autonomous execution. This is a governance completeness
defect, not a change to data authority, schema, public API, security model, dependency disposition or milestone scope.

## Repair

The execution protocol now supplies a named common safety baseline and complete per-task fields for T01–T08, including
why delegated, allowed modules, expected change, dependencies, acceptance, validation, security/privacy/data/license,
rollback, model tier, escalation and output format. T07 and T08 additionally state that artifact content must be
readable and inspected; service-side artifact metadata cannot close that requirement.

## Preserved boundaries

- P2-M5 CC04-A execution remains `CLOSED_PENDING_SEPARATE_DECISION_AUTHORITY`.
- P2-M6 release/revoke remains closed.
- No implementation, migration, dependency, model artifact, Provider call, public API, private input or image is added.
- Existing P2-M7 T01 remains unaccepted until same-SHA content-level artifact inspection and independent review finish.

## Validation

- scoped Prettier and `git diff --check`;
- required-field scan over T01–T08/R01;
- no public-route or dependency-manifest diff;
- same-SHA CI plus content-level eight-artifact inspection before acceptance.

`P2_M7_R01: READY_FOR_TRACKED_EVIDENCE`
