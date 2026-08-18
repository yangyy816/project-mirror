# P2-M3 V03 Holdout Report

## Scope and frozen authority

The four private V01 holdout assets were executed only after QA policy commit `f7b76b2` completed
same-SHA GitHub Actions run `32091490211` with all three jobs successful. Runtime, model, policy and
thresholds remained unchanged from calibration. The official MediaPipe wheels remain rejected; this
report covers only the source-built `v0.10.35-r21` private synthetic candidate.

## Execution

- Inputs: `v01-category-a-02` through `v01-category-d-02`.
- Platforms: Windows AMD64 with process-specific outbound deny/capture, and Linux x86-64 Docker with
  `--network none`.
- Repetitions: ten per input per platform, 80 successful inference runs total.
- Windows outbound block events: zero.
- Linux network mode: disabled.
- A first Linux harness attempt failed before model execution because the dynamic-library search
  path was absent. The bounded harness repair supplied the frozen runtime directory; it did not
  change the runtime, model, policy, thresholds or input.

Every successful run returned exactly one face, 478 finite landmarks, bounded X/Y coordinates,
finite Z coordinates and one finite 4x4 transformation matrix. Same-platform landmark and matrix
spans were zero for all four inputs. Occupancy ranged from approximately `0.21878` to `0.27315`, and
all matrix-derived absolute X/Y/Z rotations remained below the frozen 10-degree limit.

Cross-platform maxima across the holdout were:

- landmark coordinate absolute difference: `0.00002999092`;
- transformation matrix value absolute difference: `0.0003167`;
- landmark bounding-box area absolute difference: `0.000007002890750729129`;
- matrix-derived rotation absolute difference: `0.001456678673668499` degrees.

All values are within policy digest
`5929f44a8383838e51b9b4e34eb4045748dd68c1f579f3ab5ffaa64eadb9fad6`; no threshold was changed
after holdout execution.

## Operator hard-gate review

The Principal visually reviewed the four checksum-bound normalized assets under the frozen review
rules. Each passed the forward adult-presentation v2 boundary, contained no child/student-minor
context, showed no visible text or watermark, used a suitable neutral background and had no
deliberate reference or obvious public-figure likeness. License review passes only for the approved
private synthetic research scope.

No biometric or external identity search was performed, so the likeness result is a bounded visual
and provenance review, not a claim that no real person could resemble a synthetic output. Model and
asset distribution, production Vision and real-user facial processing remain blocked.

## Decision

The source-built V03 candidate satisfies the preregistered synthetic-only Stage D holdout gates.
This closes calibration/holdout qualification but does not itself persist QA rows, register base
identities, complete T07/T08 or decide the P2-M3 Milestone Gate.

`P2_M3_V03_STAGE_D_HOLDOUT: PASS_PRIVATE_SYNTHETIC_ONLY`

`OFFICIAL_MEDIAPIPE_WHEELS: REJECTED_FOR_P2_M3_RUNTIME`

`MODEL_DISTRIBUTION: BLOCKED`

`PRODUCTION_VISION: BLOCKED`

`REAL_USER_FACIAL_PROCESSING: BLOCKED`
