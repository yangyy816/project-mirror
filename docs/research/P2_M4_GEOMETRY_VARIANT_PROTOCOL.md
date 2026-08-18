# P2-M4 Deterministic Geometry Variant Research Protocol

## Status and question

- Status: `PREREGISTERED`
- Scope: private synthetic, frontal 2D geometry research only
- Baseline: P2-M3 freeze-state `6b86a665e845e113bbfa2820f906d3b78506b753`
- Question: can a source-relative transform candidate reproducibly change a declared target
  measurement while preserving a bounded, auditable result suitable for later M5 isolation testing?

This protocol does not claim that any dimension is `READY`, that isolation has passed or that a
QuestionBank asset is releasable.

## Inputs and authority

Every research input must be a bank-independent identity whose canonical Asset has an accepted M3 QA
run. Source bytes are immutable canonical JPEG in the private normalized namespace. The transform
receives only first-party normalized pixels, landmarks, pose, geometry measurements and an immutable
specification.

No real-person reference, User Asset, Prompt-generated target face, population mean, sensitive label,
beauty score or absolute target coordinate is permitted.

## Specification grammar

A specification fixes before execution:

- source Asset, identity and source QA references;
- ontology and measurement-policy versions;
- one target dimension and `INCREASE | DECREASE` direction;
- dimensionless source-relative magnitude within the policy-declared bound;
- explicit control dimensions;
- algorithm candidate/version and runtime-manifest digest;
- output dimensions/colorspace/encode policy;
- claimed determinism level and tolerance-policy reference.

Unknown fields, zero/negative magnitude, missing controls, unknown ontology version or a dimension
classified `UNSUPPORTED`, `REQUIRES_3D` or `STYLE_ONLY` fail before result storage.

## Candidate evaluation sequence

1. Freeze exact candidate, source/license, dependency graph, toolchain/runtime and artifact hashes.
2. Run numeric displacement fixtures without image or identity data.
3. Run bounded non-human synthetic grid/shape fixtures for direction, bounds, foldover and replay.
4. Run calibration identities and estimate same-platform/cross-platform pixel and measurement variance.
5. Freeze candidate version, determinism claim and tolerance policy.
6. Run identity-disjoint holdout; do not alter the same version after viewing results.
7. Classify candidate as `APPROVED_FOR_PRIVATE_SYNTHETIC_M4`, `REJECTED` or `FURTHER_RESEARCH`.

Calibration and holdout manifests must be disjoint and checksum-bound. Failed outputs remain attempt
evidence and are not silently replaced.

## Measurements

For each completed transform retain:

```text
requested_delta(k)
source_measurement(k)
result_measurement(k)
measured_delta(k)
control_measurements(source, result)
pixel/runtime determinism evidence
pose/reliability evidence
artifact and bounds reason codes
```

M4 may summarize these facts but does not freeze M5 formulas or release tolerances. M5 will derive
target error and normalized non-target drift from the immutable evidence under a separately
preregistered QAPolicy.

## Negative controls and stop rules

Mandatory negatives include unknown/unsupported dimension, mismatched source checksum, insufficient
landmark confidence, out-of-bounds displacement, foldover/self-intersection, malformed output,
second-decode failure, source/result checksum equality for a non-zero request, algorithm/runtime
digest mismatch, cross-platform variance beyond preregistered bounds and any network attempt.

Stop and classify `FURTHER_RESEARCH` when no candidate meets bounded determinism and artifact safety.
Do not expand beyond the 24→48→96 cohort rule to force a result. M4 may use a smaller technical
cohort for engine qualification; the N=24 minimum and escalation belong to M5 isolation evidence.

## Privacy, safety and reporting

All images remain in ignored private storage. Committed evidence contains only opaque IDs, versions,
digests, aggregate measurements, reason codes and counts—never image bytes, private paths, object keys,
landmark arrays, Prompt text or Provider payloads. M4 authorizes no real-user processing, production
runtime, public API, QuestionBank release or dependency distribution.
