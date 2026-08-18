# P2-M5 Variable Isolation, Duplicate and Diversity Evaluation Protocol

## Status and authority

- Status: `PREREGISTERED_FRAMEWORK`
- Entry baseline: P2-M4 freeze-state `5f2680e4d0724b409e13ac9cbe318b144cb0375f`
- Entry run: `32171351357`, attempt 2; all three jobs passed on the exact SHA
- Authority: ADR-021–041 and `P2_M5_EXECUTION_PROTOCOL.md`
- Scope: private synthetic evaluation only

This framework freezes evaluation ordering and stop rules. It does not invent missing dimensions, identities or
thresholds, and it is not the final cohort preregistration. T05 must commit the exact policy, split manifests,
thresholds and cohort digests before any final holdout is executed.

## Two-result contract

```text
P2_M5_TECHNICAL_GATE = PASS | FAIL
P2_MVR_V1_RESULT = PASS | FURTHER_RESEARCH | FAIL
```

The technical Gate evaluates implementation correctness, provenance, reproducibility and boundaries. The MVR result
evaluates research sufficiency. Technical PASS never implies MVR PASS.

## Required inputs

Each evaluated transform must bind:

- one bank-independent `SyntheticIdentity` and QA-passed canonical source Asset;
- one completed M4 `TransformRun`, result Asset and source/result measurement authority;
- immutable ontology, region group, algorithm/runtime and `SyntheticEvaluationPolicy` versions;
- a split assignment fixed by identity ID, source Asset ID/SHA-256 and duplicate-cluster identity;
- one target dimension/direction and all declared control dimensions.

No real person, User Asset, sensitive label, population prior, absolute target face or beauty score is permitted.

## Isolation formulas

For dimension `k`, the versioned policy defines normalization and tolerance before holdout:

```text
measured_delta(k) = result_measurement(k) - source_measurement(k)
target_error(k) = abs(measured_delta(k) - requested_delta(k))
normalized_control_delta(j) = abs(result(j) - source(j)) / policy_scale(j)
non_target_drift = max(normalized_control_delta(j)), j != k
```

The report stores actual source/result/requested values and every control delta, not only a Boolean. A pass requires
correct direction, target error within the frozen per-dimension tolerance, every control within its tolerance,
acceptable repeat/platform variance, valid QA/reliability and no artifact hard failure.

## Cohort and split rules

- Calibration, M4-seen and holdout identities are disjoint by identity, source Asset SHA-256 and duplicate cluster.
- N is counted per dimension after cluster adjustment; two variants/directions of one identity count once.
- Required progression is 24, then 48, then 96 holdout identities per dimension when evidence is unstable.
- Expansion must be justified by preregistered uncertainty/coverage evidence, not by a desire to force PASS.
- At N=96, an unstable dimension is reclassified `EXPERIMENTAL`, `UNSUPPORTED_IN_P2`,
  `REQUIRES_3D_RESEARCH` or another approved non-PASS result.
- P2-MVR-v1 requires at least four bidirectional dimensions across at least three non-sensitive region groups.

## Duplicate protocol

1. Compute canonical normalized SHA-256; equality is an exact duplicate hard rejection.
2. Compute the versioned first-party pHash bitstring from bounded canonical pixels.
3. Compute deterministic Hamming distance.
4. During calibration, retain the full allowlisted distance distribution and manually reviewed candidate labels.
5. Commit a new evaluation-policy version with the threshold before holdout.
6. During holdout, create candidates/clusters and append retain/reject decisions; never silently delete evidence.

Before step 5, pHash may rank candidate pairs but cannot automatically reject them.

## Diversity and anti-homogenization protocol

Reports may use continuous geometry measurements, nearest-neighbor distance, cluster occupancy, empty/underrepresented
coverage cells, exact/near duplicate rate, generation/QA/transform/isolation yield, style-context bandwidth and the
approved adult age-presentation distribution. They must not use protected-trait classifiers, ancestry/nationality
labels, celebrity similarity, beauty scores, rankings or a hidden standard face.

The first pack remains synthetic-only, China-market-first, East-Asian-presenting, female-oriented and 18+. Current
ADR-028–030 presentation rules remain authoritative. “Younger” or “appealing” cannot be implemented through
infantilization, homogenization or loss of morphology diversity.

## Mandatory negative controls

1. calibration/holdout/M4-seen overlap;
2. same duplicate cluster appearing twice in effective N;
3. unknown ontology/policy/region group or digest mismatch;
4. missing control measurement or non-finite value;
5. direction mismatch and target/control threshold failure;
6. exact checksum duplicate;
7. pHash input/bit-length/version mismatch and non-deterministic Hamming result;
8. threshold created or changed after holdout access;
9. report mutation, duplicate final authority and concurrent cluster conflict;
10. real-person/User/sensitive/beauty-score field or committed private payload;
11. any network attempt in deterministic CI;
12. public OpenAPI/generated-client drift.

## Current readiness and stop rule

Repository evidence currently proves four canonical identities and only `jaw_width` M4 evidence with N=2. Therefore
the exact MVR holdout cannot be preregistered at T01. T02–T04 may establish deterministic technical authority; T05
must either produce a valid cohort/policy preregistration or report `FURTHER_RESEARCH` with the missing evidence.

No result authorizes production geometry, real-user facial processing, public API, QuestionBank release or M6 entry.
