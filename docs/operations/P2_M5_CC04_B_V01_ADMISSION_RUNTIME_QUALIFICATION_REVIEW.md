# CC04-B-V01 Admission Runtime Qualification Review

## Status and authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: CC04-B-V01`
- `TASK_NAME: 04-B Admission Runtime Qualification Review`
- `BASELINE_SHA: 540dd23f2eee9ec4817ae48bc768681d3a4382f3`
- `BASELINE_CI_RUN: 32626876718`
- `PARENT_AUTHORITY: P2-M5-R16_AND_CC04-B-O01`
- `REVIEW_CANDIDATE: THIS_COMMIT`
- `AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ARTIFACT_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`
- `PRE_CONDITION_CURRENT_STATE: CC04_B_V01=REVIEW_CANDIDATE_PENDING_ACCEPTANCE;CC04_B_EXECUTION=CLOSED`

This is a fresh 04-B scope disposition, not inherited M3 approval. It reuses frozen, tracked, or recoverable M3
evidence only as evidence. It creates or resolves no private runtime locator, installs no dependency or model, invokes
no generation or Vision, accesses no image or private input, and creates no specification, assignment, registry, root,
counter, output, Asset, identity, cohort, holdout, or execution authority.

## ADR-043 qualification disposition

- `QUALIFICATION_TIER: APPROVED_FOR_INTERNAL_ENGINE`
- `CURRENT_STATUS: APPROVED_FOR_INTERNAL_ENGINE`
- `APPROVED_SCOPE: PRIVATE_SYNTHETIC_P2_M5_CC04_B_NORMALIZATION_FACE_POSE_LANDMARK_RELIABILITY_AND_MORPHOLOGY_ADMISSION_ONLY`
- `PROHIBITED_SCOPE: 04_C_TRANSFORM_OR_DIAGNOSTIC_AUTHORITY;HOLDOUT_ACCESS_OR_EVALUATION;PRODUCTION;DISTRIBUTION;REAL_USER_PROCESSING;PUBLIC_API;QUESTION_BANK_RELEASE;SENSITIVE_INFERENCE;BEAUTY_OR_AGE_SCORING`
- `CANONICAL_PLATFORM: linux_x86_64_network_none`
- `SUPPORTED_PLATFORMS: linux_x86_64_network_none;windows_amd64_process_specific_outbound_deny`
- `REAL_USER_DATA_ALLOWED: false`
- `PRODUCTION_ALLOWED: false`
- `NETWORK_POLICY: ZERO_EGRESS_RUNTIME`
- `LICENSE_STATUS: PASS_PRIVATE_SYNTHETIC_INTERNAL_ONLY_DISTRIBUTION_BLOCKED`
- `MODEL_STATUS: PRIVATE_RESEARCH_ONLY`
- `DISTRIBUTION_STATUS: BLOCKED`
- `REPRODUCIBILITY_LEVEL: TWO_CLEAN_BYTE_IDENTICAL_ROOTS_PER_PLATFORM_PLUS_THREE_ZERO_EGRESS_LIFECYCLE_RUNS_PER_PLATFORM`
- `SBOM_STATUS: PASS_51_COMPONENT_PRIVATE_CYCLONEDX`
- `VULNERABILITY_STATUS: PASS_FOR_EXACT_PRIVATE_SYNTHETIC_CLOSURE_WITH_FOCUSED_OPENCV_DISPOSITIONS`
- `NEXT_PROMOTION_GATE: NONE_NO_SCOPE_PROMOTION_AUTHORIZED`

The first-party `SyntheticVisionRequest` / `SyntheticVisionResult` boundary remains authoritative. The source-built
runtime is an isolated private operator implementation behind that boundary and cannot become domain, identity,
coverage, PostgreSQL, or release authority. No binary is added to Git, a project package, production image, public
endpoint, or normal application dependency.

## Exact manifest and source closure

- `MANIFEST_VERSION: p2-m5-cc04-b-v01-admission-runtime-v1`
- `MANIFEST_PATH: docs/research/P2_M5_CC04_B_V01_ADMISSION_RUNTIME_MANIFEST.json`
- `MANIFEST_SHA256: a1d3698564c8ca0d0b6f01fa28b580d85135ccc8c502616527a140d80ba41cb3`
- `SOURCE: MediaPipe v0.10.35`
- `SOURCE_COMMIT: f8ef212d5c962c0e853db7e59d217056b187084b`
- `EFFECTIVE_BUILD_INPUT_MANIFEST_SHA256: 5c4f74bc4dd661582d397e5d1c66d22548d103e70d75cd7a2062cc6f0958a224`
- `MODEL_SHA256: 64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`
- `QA_POLICY_VERSION: p2-m3-v03-source-built-vision-qa-v1`
- `QA_POLICY_FILE_SHA256: 6328eb82ce4c3477618432fe5911d05e8d10ecef11672e6c308b31acd38c987d`
- `QA_POLICY_CONTENT_DIGEST: 8305cfaa25d084138fb67e93043a1e37842543a645085d19d3ef52ac8a6ce15f`

The manifest is the canonical digest-bearing V01 record. Its raw-file SHA-256 is recorded externally in this review
and the current-authority tail; it is not recursively embedded in itself. E01 must bind this exact hash before it can
be accepted and must verify every exact runtime, model, policy, platform, and morphology value before any first call.
Any byte, digest, toolchain, platform, policy, formula, or bound mismatch returns
`BLOCKED_ALGORITHM_RUNTIME_AUTHORITY_MISMATCH`; there is no download, install, PATH fallback, substitution, or retry.

## Reused evidence and non-inheritance

The preserved M3 R25/R26 chain provides the evidence facts used for this new scope judgment:

1. `P2_M3_V03_BUILD_CLOSURE_REPORT.md` and `P2_M3_ACCEPTANCE.md` bind the exact source, patches, Bazel 7.4.1,
   compilers, Python 3.13 boundary, dependency closure, model origin, and both-platform output hashes.
2. R25 reproduced two byte-identical clean Windows roots and two byte-identical clean Linux roots. The main runtime
   hashes are respectively `1c67ae02b90a5b00b58018c3c04db411134d781c6f53b195e68a6ce6136615ef` and
   `6a5fb35175efc2f014fb61f7f4abb2c78c38156bd6abf2186d1549cbf3f006a7`.
3. Three lifecycle runs per platform produced one-face results and clean close with zero observed network calls or
   outbound events. Private-path, debug-record, Ooura, Clearcut, CA-bundle, known network surface, import, export, and
   relative-RUNPATH checks passed for the declared platform scope.
4. The 51-component private CycloneDX SBOM digest is
   `902088a0e70d3ce005885c01f7ee472fba19458ae803e09700df52949d152dda`; the 38-repository,
   124-license-file inventory digest is `e1e77546b0a2a8148cc2f6ef6b3dc700305edad16311b09d9a836caa3c2742d3`.
5. Offline Grype recorded zero direct matches for the exact source closure. Focused OpenCV findings remain explicit:
   CVE-2019-14493 has the exact null-check backport and malformed-input negative controls; the affected HOG, DIS, and
   JPEG surfaces for CVE-2019-15939, CVE-2019-19624, and CVE-2025-53644 are not built and their symbols are absent.
6. R25 same-SHA CI passed at `f498c80b` in run `32104336955`; R26's migration-head correction passed at
   `c31ca44627843c04455bbe333b6e1dcfc515d096` in run `32106647901` without changing runtime evidence.

These facts do not import an M3 identity, Asset, output, raw byte, measurement row, cohort, coverage result, threshold,
holdout result, M4/CC01-C/CC02 result, or prior scope approval. The M3 policy document's historical Windows hash remains
historical; R25 changed only portable tool-path injection and reproduced unchanged policy behavior. V01 accessed no
legacy private bytes and creates no claim that those bytes are presently located. If E01 cannot resolve the exact
accepted runtime and model under P01 custody, it stops rather than reconstructing or searching for them.

## Code, model, weight, data, and license separation

The MediaPipe and bounded OpenCV source closure, Face Landmarker model bundle, build dependencies, and any fixture or
future generated data are separate authorities. The exact source and component model cards provide the recorded
Apache-2.0 code/model license evidence, but model training-data provenance is incomplete for distribution or production.
Therefore this review permits only private synthetic internal research, blocks redistribution and production, requires
no credential, and adds no model artifact or dependency to the repository. It does not approve Codex image generation
as a production Provider or change the Owner's provenance-only source disposition.

## Deterministic morphology admission authority

- `MORPHOLOGY_MANIFEST_VERSION: p2-m5-cc04-b-morphology-admission-v1`
- `MORPHOLOGY_MANIFEST_SHA256: a1d3698564c8ca0d0b6f01fa28b580d85135ccc8c502616527a140d80ba41cb3`
- `MEASUREMENT_COORDINATE_SPACE: NORMALIZED_XY`
- `MEASUREMENT_NORMALIZER: distance_xy(10,152)`
- `PRIMARY_CELL_AUTHORITY: IMMUTABLE_REQUEST_ASSIGNMENT_PLUS_BOUND_DETERMINISTIC_MEASUREMENT`
- `HUMAN_MORPHOLOGY_ASSIGNMENT_REPAIR_OR_OVERRIDE: PROHIBITED`

One runtime result computes all three continuous non-sensitive descriptors, but only the descriptor for the request's
immutably preassigned region determines its one primary morphology cell:

- `UPPER_FACE_GEOMETRY`: `distance_xy(133,362)/distance_xy(10,152)`; lower is finite `0 < value < 0.25`, upper is
  finite `value >= 0.25`.
- `MIDFACE_GEOMETRY`: `distance_xy(98,327)/distance_xy(10,152)`; lower is finite `0 < value < 0.18`, upper is finite
  `value >= 0.18`.
- `LOWER_FACE_GEOMETRY`: `distance_xy(234,454)/distance_xy(10,152)`; lower is finite `0 < value < 0.75`, upper is finite
  `value >= 0.75`.

These split points are Principal-selected, pre-data operational research hypotheses fixed before any 04-B generation
or measurement. They were not selected from a legacy result, holdout, transform score, downstream performance, user
data, population category, or beauty/age authority. They claim only a deterministic coverage partition—not a median,
norm, scientific threshold, sensitive trait, validated user-routing rule, or ideal face. Equality belongs to the upper
cell. All three continuous measurements are preserved even though only one is primary.

The split points, formulas, bounds, and manifest hash become immutable from the first accepted E01 call through 04-B
disposition. A later change requires forward change control and a new cohort; it cannot relabel this cohort. If the
precommitted 32-call envelope cannot achieve the required 24 identities and three-to-six occupancy under these fixed
rules, the honest result is `FURTHER_RESEARCH_RESOURCE_ENVELOPE_EXHAUSTED`, not a threshold change or human reassignment.

## Reliability, resources, and fail-closed controls

Before one accepted landmark result is used, each output requires ten runs on each supported platform to satisfy the
manifest's landmark-count, finite-matrix, same-platform span, cross-platform difference, occupancy, and pose bounds.
One measurement operation then computes all three descriptors. E01 must precompute and reserve every run under the
2500 Vision-or-measurement ceiling and the 8-GiB storage ceiling. Failed or repeated operations count; 04-B transform
operations remain zero; concurrency remains one and automatic retry remains zero.

Exact failure outcomes are preserved:

- missing or unaccepted manifest: `BLOCKED_MORPHOLOGY_MEASUREMENT_AUTHORITY_MISSING`;
- runtime, model, digest, platform, policy, formula, or bound mismatch: `BLOCKED_ALGORITHM_RUNTIME_AUTHORITY_MISMATCH`;
- unavailable, non-finite, non-positive-normalizer, or unreliable measurement:
  `LANDMARK_OR_MEASUREMENT_RELIABILITY_FAILED`;
- deterministic primary band not matching immutable assignment: `MORPHOLOGY_ASSIGNMENT_MISMATCH`;
- missing review or uncertain evidence: `UNSUPPORTED_PASS_OR_MISSING_EVIDENCE`.

Every returned output remains counted. No human may assign, repair, override, infer, or relabel a morphology cell. Human
review remains limited to the categorical presentation controls already allowed by repaired Q01. Hidden network,
telemetry, download, runtime substitution, private-field leakage, adult/safety bypass, unknown evidence, resource
overflow, downstream selection, holdout access, or production/M6 bypass is an immediate hard stop.

## Result and sequencing

- `ADMISSION_RUNTIME_QUALIFICATION_REVIEW: PASS`
- `V01_MANIFEST_CREATED: YES_TRACKED_JSON_ONLY`
- `RUNTIME_OR_MODEL_BYTES_CREATED_OR_ACCESSED: NO`
- `PRIVATE_ROOT_OR_LOCATOR_CREATED: NO`
- `GENERATION_SPECIFICATION_CREATED: NO`
- `GENERATION_OR_VISION_EXECUTED: NO`
- `ASSET_IDENTITY_OR_COHORT_CREATED: NO`
- `CC04_B_EXECUTION: CLOSED`
- `NEXT_REQUIRED_TASK: PREPARE_SEPARATE_CC04_B_E01_EXECUTION_CONTRACT_NO_GENERATION`

This PASS becomes effective only after this exact commit passes scoped local validation, same-SHA CI, all eight
artifacts, independent Security/Privacy/License/Research Integrity review, independent Sol High review, and Principal
acceptance. Until then the O01 tail remains current and V01 remains a candidate. After acceptance, only the separate
E01 contract may be prepared and independently accepted. Neither V01 nor E01 contract preparation authorizes a
generation call or private capability creation.
