# P2-M4 T08 Forward Repair Report

## Result

The four bounded repairs raised by the independent T08 review are implemented and have focused local evidence.
This is a forward report: it does not alter ADR-040, the T07 preregistration, the original T07 evidence or any private
attempt record.

`P2_M4_T08_REPAIR_IMPLEMENTATION: READY_FOR_FULL_GATE`

`P2_M4_RESEARCH_HANDOFF: FURTHER_RESEARCH_FOR_M5_ISOLATION`

The second statement remains unchanged. The repaired replay does not promote `jaw_width`, define an M5 tolerance or
claim that a two-identity cohort satisfies the M5 MVR.

## Closed review findings

- `P2-M4-R13`: calibration and holdout are now independently bound by SyntheticIdentity ID, Asset ID and normalized
  SHA-256. Cross-split overlap and within-split duplication fail closed on each authority axis.
- `P2-M4-R14`: the complete platform-specific Vision closure, exact model and exact topology are verified before
  topology parsing, output-root creation or native execution.
- `P2-M4-R15`: current-state governance now names P2-M4 as `EXECUTING` and P2-M3 as `FROZEN` without rewriting
  historical records.
- `P2-M4-R16`: persisted execution rehydrates the exact approved ontology, verifies its digest and re-enforces
  `READY | EXPERIMENTAL` membership for the target and every control dimension before source or result I/O.

## Replay reconciliation

- Windows and Linux used fresh private output roots and the unchanged two-identity, bidirectional, three-repeat
  holdout.
- All four repaired outputs are byte-identical to their original T07 counterparts and across platforms.
- All repaired measurements equal their original platform measurements.
- The output SHA-256 sequence remains
  `519a9612...`, `39eae092...`, `52f26526...`, `173f82c5...`.
- Maximum cross-platform measurement difference remains `0.000011863707220088893`.
- Maximum absolute control relative delta remains `0.011420225249709091`; it is evidence for later isolation
  research, not an accepted tolerance.

The redacted machine-readable authority, runtime closure, private manifest/report hashes and reconciliation facts are
recorded in `P2_M4_T08_REPAIR_EVIDENCE.json`. No private path, image, raw landmark, object key, model, executable or
binary is committed.

## Remaining boundary

Full local validation, same-SHA GitHub Actions and both independent T08 reviews remain mandatory before the Principal
may decide the P2-M4 Gate. P2-M5, production geometry, real-user facial processing and QuestionBank release remain
closed.
