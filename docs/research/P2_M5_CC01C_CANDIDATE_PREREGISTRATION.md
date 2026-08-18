# P2-M5 CC-P2-M5-01-C Candidate Preregistration

## Authority and status

- Machine-readable authority: `P2_M5_CC01C_CANDIDATE_MANIFEST.json`.
- Manifest content digest: `eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4`.
- Stage B accepted candidate: `7282094406b9754368709f543c4fda54b2e57490`; run `32197326163`.
- Stage B acceptance checkpoint: `0a46f0f6889b4fd0e05cec9b78f66a20c8c56ef1`; run `32197913261`.
- Status: `PREREGISTERED_NOT_EXECUTED`.

This checkpoint is committed before any Stage C candidate measurement or transform. It binds the complete six-item
candidate family, exact landmark formulas, plan builders, magnitude grid, platform/repeat rules, control dimensions,
artifact gates, missingness rules and failure interpretations. It does not read a candidate measurement, select a
tolerance or promote a dimension.

## Fixed screening design

- Calibration cohort: the 12 Stage B identities only; no M4-seen identity and no future holdout identity.
- Candidate family: `jaw_width`, `eye_spacing`, `nose_width`, `mouth_width`, `chin_height` and `cheekbone_width`.
- Region groups: `lower_face`, `periocular`, `central_face` and `perioral`.
- Directions and magnitudes: `INCREASE` and `DECREASE` at `15_000` and `30_000 ppm`.
- Repeats: three transform/Vision repeats for every identity, candidate, direction, magnitude and platform.
- Platforms: the exact accepted Windows and Debian 12-compatible Linux private runtimes; Linux remains zero-network.
- Resource ceiling: `1_728` transform/Vision rows, zero retries and concurrency one per platform.
- Measurement space: normalized image X/Y only. Z, hidden population priors, absolute target faces and sensitive
  classifications are prohibited.
- Controls: every non-target member of the six-dimension family is retained for each row. There is no imputation;
  every candidate needs all 12 identities to be eligible for Stage D consideration.

The paired-width plans use source-relative symmetric horizontal Gaussian fields. `chin_height` uses a source-relative
vertical Gaussian field centered on landmark 152. The machine-readable manifest is authoritative for every anchor,
formula, sigma and displacement denominator.

## Interpretation

Stage C records distributions; it does not contain a PASS tolerance. Same-platform output must replay bit-exactly.
Cross-platform bytes are compared but need not match; all cross-platform measurement differences are retained. A
missing row, runtime mismatch, foldover, wrong target direction, unresolved artifact or mandatory negative-control
failure keeps that candidate out of Stage D and records `FURTHER_RESEARCH` without editing this version.

All six candidates must be reported even when they fail. Stage D may open only after tracked Stage C evidence and can
preregister a holdout only if at least four bidirectional candidates span three region groups. Stage D must create a
new immutable evaluation-policy/ontology/split authority; no threshold is backfilled into this manifest.

No image, raw landmark, Prompt, private path, object key, Provider payload, model binary or runtime binary is committed.
Production geometry, real-user facial processing, Stage D–E, T06–T08, MVR, M6 and QuestionBank release remain closed.

`CC_P2_M5_01_C_MANIFEST: LOCAL_CANDIDATE_NOT_EXECUTED`

`CC_P2_M5_01_C_EXECUTION: CLOSED_PENDING_MANIFEST_TRACKED_ACCEPTANCE`
