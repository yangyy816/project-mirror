# P2-M3 V03 Calibration Report

## Scope

This report freezes the calibration-derived policy for the exact source-built MediaPipe
`v0.10.35-r21` private synthetic candidate. It does not approve the official wheels, model
distribution, production Vision or real-user facial processing. Holdout assets were not executed by
the Vision runtime before this policy freeze.

Before calibration, a deterministic Pillow decode of all eight normalized V01 files was used only
to reconcile opaque checksums with source references. That operation produced no Vision inference,
measurement result or human presentation review and is not calibration or holdout evidence.

## Calibration execution

- Inputs: `v01-category-a-01` through `v01-category-d-01`.
- Negative controls: deterministic `no_face_v1`, `multi_face_v1`, `small_face_v1` and `roll_v1`.
- Platforms: Windows AMD64 process-specific outbound deny/capture and Linux x86-64 Docker
  `--network none`.
- Repetitions: ten per input/control/platform; 160 total runtime executions.
- Runtime configuration: still-image CPU, `num_faces=2`, all three upstream confidence inputs `0.5`,
  blendshapes disabled and facial transformation matrices enabled.
- Network evidence: zero Windows outbound block events; Linux network namespace disabled.

All four calibration inputs returned exactly one face, 478 landmarks, bounded finite X/Y coordinates,
finite Z coordinates and a 4x4 transformation matrix. Within-platform landmark and matrix spans were
zero across all repetitions.

Negative controls separated the intended boundaries:

- `no_face_v1`: stable count `0`.
- `multi_face_v1`: stable count `2`.
- `small_face_v1`: stable landmark bounding-box area approximately `0.013843`, versus calibration
  range approximately `0.216783` to `0.273659`.
- `roll_v1`: matrix Z rotation approximately `45.2633` degrees, versus calibration absolute maximum
  below `0.384` degrees.

Cross-platform maxima across calibration inputs were:

- landmark coordinate absolute difference: `0.00002643535`;
- transformation matrix value absolute difference: `0.0004025`;
- landmark bounding-box area absolute difference: `0.00000326456`;
- matrix-derived rotation absolute difference: `0.001134` degrees.

Latency was recorded for operational evidence but is not a QA hard gate. Linux P95 included isolated
host scheduling outliers; this does not change deterministic measurements.

## Frozen policy

The immutable policy envelope is `P2_M3_V03_QA_POLICY_V1.json`. Thresholds were selected before any
holdout runtime execution, with explicit margins around calibration distributions and the intended
negative-control separations. Automatic hard failures cannot be overridden by human review.

Both SHA-256 digests use UTF-8 canonical JSON with non-finite numbers rejected, ASCII escaping,
lexicographically sorted keys and compact separators. `qa_policy_content_digest` covers only the
`qa_policy_content` object. `document_digest` covers the complete policy envelope after omitting the
`document_digest` member itself, so it binds the policy content digest, thresholds, runtime/model
references, calibration evidence and the canonicalization rule without becoming self-referential.

Adult presentation, likeness risk, license scope, text/watermark and background suitability remain
explicit hard-gate operator reviews. The Vision model does not estimate age or sensitive traits.

`P2_M3_V03_CALIBRATION: PASS`

`P2_M3_V03_HOLDOUT_EXECUTED: NO`
