# P2-M4 T07 Integrated Evaluation Preregistration

## Authority

- Accepted measurement/plan authority: ADR-040.
- Execution authority: ADR-036–039 and `P2_M4_EXECUTION_PROTOCOL.md`.
- Candidate: `OPENCV_5_0_0_BOUNDED_TRANSITIVE_SOURCE_V2`.
- Vision/model: P2-M3 V03 source-built private synthetic runtime and fixed model bundle only.
- Public API, production geometry, real-user facial processing and QuestionBank release: prohibited.

This document is committed before any T07 holdout variant is generated or measured. A holdout failure cannot be
repaired by editing this version; a new candidate requires forward research change control and a new holdout cohort.

## Fixed identity split

Canonical split envelope schema: `mirror.p2-m4.t07-identity-split/v1`.

Calibration asset SHA-256 values, in fixed order:

1. `71fc0fadc69841664664cd912132edb2d64adc227a78755be38dedf5113add1e`
2. `3532d0f7e30d64916a81059c24e6e0ea33f3c9fa5fff66600f7131a6728c9a05`

Calibration split digest:
`bd51d39d8db0072739fd1e8976a226701aca80f7b203acb76b75cace507a844e`.

Holdout asset SHA-256 values, in fixed order:

1. `a84f6a0316a665f311b42bf4c88d51caab1e0327109529d72f1a05d45940c3c5`
2. `c225320284eceec77dbdf24d9a806ce77f030f40f17237487719411bcc8255c5`

Holdout split digest:
`22ec319dadf23d62d9627121a363384cad196728f6e5902ab8b78d7e083cbc86`.

The two sets must be disjoint by identity ID, Asset ID and normalized SHA-256. No asset may be silently replaced.

## Fixed evaluation contract

- Target: `jaw_width`; directions: `INCREASE`, `DECREASE`; requested magnitude: `30_000 ppm`.
- Measurements, topology and local-field formula: exactly ADR-040.
- Plan builder version: `p2-m4-t07-jaw-local-field-v1`.
- Plan admission confidence kind: `POLICY_ADMISSION_FLOOR`; value: `500_000 ppm`.
- Output policy: `image-sanitizer-v1`; transform algorithm: `opencv-piecewise-affine-v1`.
- Windows runtime manifest:
  `27b33d646d8587f76d5ca317ac9d6aec95bc04fd87d413bb3dd6394f9694bb7a`.
- Linux runtime manifest:
  `5d0e9ee323d7daea78e8baaeec63917c7a1867301ec5f7c71685fa9cbed311d8`.
- Model SHA-256:
  `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`.
- Repeats: three transforms and three Vision measurements per identity/direction/platform.
- Same-platform output SHA-256 must be identical across transform repeats.
- Cross-platform bytes are compared but only measurement equivalence is claimed unless bytes are actually identical.
- Committed evidence contains no image, raw landmark, private path, object key or executable log.

## Stop rules

T07 evaluation is complete only if every mandatory attempt and negative control executes with zero skip. The research
candidate becomes `FURTHER_RESEARCH`, without threshold relaxation, if any of the following occurs:

- source/holdout checksum or identity split mismatch;
- missing/extra topology edge group, point or triangle;
- runtime/model/plan digest mismatch;
- transform rejection, face count other than one, incomplete/non-finite landmarks or failed close;
- requested target direction is not observed on either holdout identity;
- same-platform output replay differs;
- Windows/Linux target direction disagrees;
- any mandatory negative control fails at its intended boundary.

Control deltas and cross-platform measurement deltas are always recorded. T07 deliberately sets no isolation PASS
tolerance; P2-M5 must preregister those thresholds using calibration evidence and a new holdout.

## Mandatory negative controls

1. calibration/holdout overlap detector rejects any duplicate identity/Asset/SHA-256;
2. unsupported geometry dimension is rejected before plan construction;
3. runtime manifest mismatch is rejected before native execution;
4. source/spec/plan digest mismatch is rejected;
5. duplicate or unordered topology payload is rejected;
6. synthetic foldover plan is rejected;
7. source-result checksum alias is rejected;
8. malformed/incomplete Vision output is rejected;
9. evidence redaction scan rejects paths, image bytes, object keys and raw landmarks.

## Interpretation

Passing this protocol means the integrated evaluation is reproducible and honestly measured. It does not establish
M5 variable isolation, promote `jaw_width` to `READY`, satisfy the 4-dimension/24-identity MVR, authorize production
geometry or approve real-user facial processing.

`P2_M4_T07_HOLDOUT_EXECUTED: NO`
