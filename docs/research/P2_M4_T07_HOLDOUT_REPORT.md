# P2-M4 T07 Holdout Report

## Result

The preregistered two-identity, bidirectional holdout completed on Windows and Linux after commit
`1d2a2732a7ad3d0898663b542dd6f0fa308a59e0`. Every final attempt used the unchanged ADR-040
measurement formula, 3% narrow local field, fixed identity split, fixed model and exact private runtimes.

`P2_M4_T07_EVALUATION: PASS_EVALUATION_COMPLETE`

`P2_M4_T07_RESEARCH_HANDOFF: FURTHER_RESEARCH_FOR_M5_ISOLATION`

These two statements are intentionally separate. T07 proves deterministic execution and actual measurement; it does
not claim that control drift is acceptable or that `jaw_width` is `READY`.

## Determinism and measurement evidence

- Two holdout identities × two directions × three transform/Vision repeats × two platforms completed.
- All same-platform output repeats were byte-identical.
- All four Windows outputs were byte-identical to the corresponding Linux outputs.
- Every Vision measurement repeated exactly within each platform.
- The maximum Windows/Linux measurement absolute difference was
  `0.000011863707220088893`.
- Both identities produced a positive measured jaw-width delta for `INCREASE` and a negative delta for `DECREASE` on
  both platforms.
- The largest absolute `nose_width` or `eye_spacing` relative delta was
  `0.011420225249709091`. It remains visible evidence, not an isolation PASS.

Machine-readable aggregates and source/output/runtime/model/report digests are in
`P2_M4_T07_EVALUATION_EVIDENCE.json`. Images, raw landmarks, private paths, object keys and executable logs are not
committed.

## Preserved attempts and repairs

- Early calibration exhausted the nearly full D volume while writing a reconstructable RGB intermediate. Only that
  task-owned temporary RGB was removed; JPEG, log and calibration facts were retained. The final harness uses a fresh
  temporary directory and does not retain RGB intermediates.
- An initial topology reconstruction from an unordered edge-set produced two extra cliques. Calibration exposed an
  overlap rejection; ADR-040 now requires the upstream ordered list grouped into exactly 852 triangles.
- The first Linux holdout container used the Debian 12 API image and failed before Vision execution because the
  qualified M3 binary requires glibc 2.38. Its one already-produced output and attempt fact remain private evidence.
  The corrected run used the previously qualified Ubuntu 24.04 builder image, the same `--network none` boundary and
  a task-owned read-only volume containing the repository's already locked Python dependencies.
- `P2-M4-R12` added the missing calibration-split digest and overlap rejection to the evaluation harness. All pre-R12
  final outputs were retained; the unchanged holdout was rerun in fresh output roots and produced identical hashes.

No failed asset was silently replaced, no threshold changed after holdout and no new dependency or model was adopted.

## Boundaries

- Cohort size is two holdout identities, not the P2-M5 24-identity MVR.
- Only `jaw_width` was evaluated; it remains `EXPERIMENTAL`.
- Control drift requires later calibration and a new preregistered M5 holdout.
- No production geometry, User Asset, real-person image, real-user facial processing, QuestionBank release, public API
  or M5 tolerance was enabled.
