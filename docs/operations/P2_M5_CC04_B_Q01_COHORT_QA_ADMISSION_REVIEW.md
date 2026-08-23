# CC04-B-Q01 Cohort and QA Admission Review

## Status and authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: CC04-B-Q01`
- `TASK_NAME: Cohort and QA Admission Review`
- `PARENT_AUTHORITY: CC04-B-P01`
- `BASELINE_SHA: df50b479b5c2aceba17494d605a7ebbc66d53426`
- `REVIEW_CANDIDATE: THIS_COMMIT`
- `AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ARTIFACT_SECURITY_PRIVACY_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`
- `PRE_CONDITION_CURRENT_STATE: CC04_B_Q01=REVIEW_CANDIDATE_PENDING_ACCEPTANCE; CC04_B_EXECUTION=CLOSED`

This is a review-only checkpoint. It does not create a GenerationSpecification or Prompt, access private input, create or resolve custody, invoke generation or Vision, normalize an image, create an Asset or identity, form a cohort, compute a signature, consume quota, or authorize execution.

## Frozen generation-specification authority

- `GENERATION_SPECIFICATION_VERSION: p2-m5-cc04-b-calibration-generation-v1`
- `GENERATION_SPECIFICATION_SCOPE: FRESH_PRIVATE_SYNTHETIC_CALIBRATION_ONLY`
- `GENERATION_SPECIFICATION_DIGEST: COMPUTE_ONCE_FROM_CANONICAL_PRIVATE_SPEC_BEFORE_FIRST_E01_CALL`
- `CALIBRATION_ASSIGNMENT_AUTHORITY: PRECOMMITTED_REQUEST_ORDINAL_TO_MORPHOLOGY_AND_STYLE_CELL_MANIFEST`
- `HOLDOUT_ASSIGNMENT_OR_ACCESS: PROHIBITED`

The later execution contract must materialize one canonical private specification and compute its SHA-256 before the first call. The registry may retain its version and digest; Prompt plaintext remains outside Git, logs, CI, artifacts, MEMORY, and reviewer context. The canonical specification must bind:

1. `SOURCE_KIND: CODEX_NATIVE_IMAGEGEN` and private-internal-research-only purpose;
2. declared synthetic adult 18+, female-oriented, East-Asian-presenting first-coverage context, no real or named identity reference, and no age estimation;
3. general nonsexual ADR-030/v2 adult boundary and every repaired S01 hard control;
4. frontal or bounded pose, soft even lighting, plain neutral background, neutral or mild relaxed closed-mouth expression, one face, no text or watermark, and no sexualized context;
5. exactly one preassigned primary morphology-coverage cell and exactly one approved nonsexual style-context cell;
6. explicit identity distinctness, morphology diversity, anti-homogenization, and no hidden standard-face instruction;
7. exact request/output/resource bindings from the later O01 and execution contracts.

Each request ordinal is assigned before its call. The returned output inherits that immutable assignment even if it fails. A later request may not be relabeled using the observed image, transform performance, isolation result, threshold outcome, or MVR result. Any canonical-spec digest mismatch stops before use and cannot be repaired by an automatic retry.

## Frozen QA policy composition

- `QA_ADMISSION_OVERLAY_VERSION: p2-m5-cc04-b-calibration-qa-admission-v1`
- `NORMALIZED_SYNTHETIC_QA_BASELINE: p2-m3-v03-source-built-vision-qa-v1`
- `NORMALIZED_SYNTHETIC_QA_BASELINE_CONTENT_DIGEST: 8305cfaa25d084138fb67e93043a1e37842543a645085d19d3ef52ac8a6ce15f`
- `BASELINE_USE_SCOPE: NORMALIZATION_FACE_POSE_LANDMARK_RELIABILITY_ADMISSION_ONLY`
- `LEGACY_RESULT_OR_IDENTITY_AUTHORITY_INHERITED: NO`

The accepted M3 policy may be reused only as an immutable first-party synthetic normalization and admission baseline when the later execution manifest proves the exact approved algorithm, runtime, model digest, platform, zero-network, and policy binding. Mismatch, unavailable artifacts, unknown digest, hidden download, or network use returns `BLOCKED_ALGORITHM_RUNTIME_AUTHORITY_MISMATCH`; it does not install, substitute, or silently qualify a runtime.

This narrow admission reuse imports no M3 identity, Asset, output, measurement result, coverage result, or M4/CC01-C/CC02 authority. Algorithm/runtime requalification for 04-C transform and diagnostic evidence remains a separate later task.

The Q01 overlay binds the accepted L01 source/rights, repaired S01 adult and negative controls, P01 custody, this cohort/split policy, duplicate rules, coverage rules, reason taxonomy, and immutable evidence ordering. Its canonical digest must be computed and registered before execution.

## Hard QA order

Every returned output is untrusted and consumes raw quota. The later execution must evaluate and preserve evidence in this order:

1. verify request/output count binding, source authority, custody record, byte count, SHA-256, type, and scope;
2. apply bounded MIME/magic-byte, single-frame, decode, sanitizer, pixel/decompression, canonical metadata removal, canonical JPEG write, second-decode, and normalized SHA-256 checks;
3. run only the exactly bound zero-network normalized-synthetic baseline for checksum binding, exactly one face, complete and bounded landmarks, finite transformation matrix, face occupancy, frontal/bounded pose, repeatability, and required platform reliability;
4. apply repaired S01 source, adult-presentation, nonsexual, unsafe-content, likeness, sensitive-inference, beauty-score, and no-override controls;
5. apply versioned human categorical review for text/watermark absence, plain-background suitability, standardized expression, visibility/occlusion, style-context match, and morphology-cell match where no approved automatic measurement exists;
6. perform exact raw and normalized duplicate checks, then pHash candidate-pair review and append-only duplicate-cluster decisions;
7. verify legacy/M4/CC01-C/CC02 and split exclusion by fresh IDs, Asset linkage, source digest, normalized digest, and confirmed cluster;
8. admit only a candidate satisfying every hard gate, assignment, duplicate, coverage, evidence, and reliability rule;
9. create the canonical Asset, QA-passed record, and one bank-independent SyntheticIdentity atomically under existing PostgreSQL authority only after all prior checks pass.

An execution failure is `FAILED`; a completed content rejection is `REJECTED`. Neither may be rewritten as the other. A human decision cannot erase or override an automatic hard failure, missing measurement, missing review, digest mismatch, or duplicate decision.

## Identity and Asset policy

- `IDENTITY_ID_POLICY: FRESH_OPAQUE_UUID4_CREATED_ONLY_AT_FINAL_QA_ADMISSION`
- `IDENTITY_ID_SEMANTICS: NO_TRAIT_STYLE_COVERAGE_PROMPT_OR_SEQUENCE_ENCODING`
- `CANONICAL_ASSET_POLICY: FRESH_NORMALIZED_SYNTHETIC_ASSET_ONLY`
- `RAW_OUTPUT_AS_CANONICAL_ASSET: PROHIBITED`
- `ONE_CANONICAL_ASSET_TO_ONE_IDENTITY: REQUIRED`
- `IDENTITY_CREATION_TRANSACTION: QA_PASSED_ASSET_AND_IDENTITY_ATOMIC`

Raw and normalized bytes remain separate immutable private objects. A canonical Asset binds the normalized SHA-256, media type, byte size, dimensions, normalizer version, source linkage, QA policy/overlay versions, accepted QA run, and custody authority. It is never overwritten or relinked. The identity ID is created only after admission and cannot be recycled after rejection, cleanup, failure, or cluster consolidation.

No real/User/celebrity/scraped identity, prior SyntheticIdentity, legacy Asset, prior output, private locator, or historical result may be used as a source, reference, comparison target, assignment input, or replacement.

## Duplicate and cluster policy

1. Raw-byte SHA-256 equality is an immediate duplicate hard reject for the later arrival.
2. Canonical normalized SHA-256 equality is an immediate exact-duplicate hard reject for the later arrival.
3. `DUPLICATE_SIGNATURE_VERSION: phash-dct-nearest-v1`; this accepted first-party 64-bit pHash bitstring is computed only from bounded canonical pixels, and deterministic Hamming distance produces candidate pairs.
4. Before the 04-C calibration distance distribution and threshold are accepted, pHash distance cannot automatically reject or admit an output. It may only order candidate pairs for a versioned human same-identity review.
5. Candidate-pair evidence and retain/cluster decisions are append-only and bind signature version, bit length, Hamming distance, actor, reason, timestamp, and member digests without image bytes or free-text facial judgments.
6. A confirmed same-identity duplicate cluster contributes at most one admitted calibration identity. A later member is rejected as `CONFIRMED_DUPLICATE_CLUSTER`; if two previously provisional admissions collapse into one cluster, effective accepted N is reduced and the preserved earlier admission is marked non-counting without deleting evidence.
7. Morphological similarity, style similarity, youthful features, continuous descriptor proximity, or questionnaire desirability alone never proves same identity.
8. No pair/cluster decision may use transform, isolation, candidate-dimension, threshold-performance, holdout, MVR, or release evidence.

Every raw output remains counted even when exact-duplicate or cluster-rejected. There is no replacement retry, quota refund, or holdout transfer.

## Calibration and split isolation

All 04-B records use new task, specification, assignment, output, Asset, QA, identity, and cluster IDs. Calibration membership is fixed at admission and cannot later be relabeled as holdout. The execution must prove non-membership and non-linkage to CC01-C, CC02, M3/M4-seen, User, real-person, and any sealed-holdout identity through the available fresh IDs, source/normalized digests, canonical Asset linkage, and confirmed duplicate-cluster authority.

The 04-B task must not create, enumerate, access, hash, sign, inspect, or reserve holdout bytes, identities, assignments, manifests, roots, locators, pHash results, or performance evidence. A future 04-D/04-E split must independently prove holdout isolation; Q01 does not pre-create it.

## Morphology and style coverage

Coverage is a preregistered acquisition constraint, not a score or ranking. The assignment manifest uses six primary non-sensitive morphology cells: lower and upper predeclared continuous descriptor bands for each of `UPPER_FACE_GEOMETRY`, `MIDFACE_GEOMETRY`, and `LOWER_FACE_GEOMETRY`. Band bounds, measurement formula, units, and policy digest must be fixed before the first call. They describe source-relative geometry coverage and never race, ethnicity, ancestry, nationality, age, beauty, or a target ideal face.

The six approved nonsexual primary style cells are:

- `PURE_CLEAN_NATURAL`
- `GENTLE_SWEET_APPROACHABLE`
- `REFINED_ELEGANT`
- `SOPHISTICATED_URBAN`
- `GLAMOROUS_STRIKING`
- `INTELLECTUAL_ELEGANT_LIGHT_MATURE`

`CHARMING_ALLURING` and `ADULT_SAFE_SEXY` are excluded from 04-B. Every identity has exactly one primary morphology cell and one primary style cell for acquisition accounting, while the underlying continuous measurements remain preserved. Style is presentation context, not an identity, sensitive-trait, morphology, or routing label.

For the 24-identity cohort to be ready:

- every one of the six primary morphology cells must contain at least three admitted independent identities;
- every one of the six style cells must contain at least three admitted independent identities;
- no primary morphology or style cell may contribute more than six identities;
- all counts are adjusted to one identity per confirmed duplicate cluster;
- all 24 identities must still pass every safety, QA, reliability, custody, provenance, and isolation gate.

The 32 request ordinals must be preassigned across all six morphology and all six style cells before generation. Exact pairing may be balanced by the later execution contract, but no output-dependent reassignment is allowed. Failure to reach both 24 independent admissions and these occupancy bounds within 32 raw outputs stops as `FURTHER_RESEARCH_RESOURCE_ENVELOPE_EXHAUSTED`; it does not relax coverage, repeat a call, borrow holdout quota, score attractiveness, or prefer a hidden template.

## Admission taxonomy

At minimum, the versioned overlay must distinguish:

- source/custody: `SOURCE_OR_CUSTODY_INVALID`, `EVIDENCE_OR_DIGEST_MISSING`, `PRIVATE_FIELD_LEAKAGE_DETECTED`;
- decode/normalization: `MALFORMED_OR_UNSUPPORTED_IMAGE`, `SANITIZE_OR_SECOND_DECODE_FAILED`, `NORMALIZED_CHECKSUM_MISMATCH`;
- face/reliability: `FACE_COUNT_NOT_ONE`, `POSE_OR_VISIBILITY_OUT_OF_POLICY`, `LANDMARK_OR_MEASUREMENT_RELIABILITY_FAILED`;
- presentation: `CLEAR_PRE16_PRESENTATION`, `CHILD_OR_STUDENT_MINOR_CONTEXT`, `YOUTHFUL_ADULT_PRESENTATION_ALLOWED`, `UNEXPECTED_SEXUALIZED_CONTEXT`, `BACKGROUND_OR_EXPRESSION_OUT_OF_POLICY`, `TEXT_OR_WATERMARK_PRESENT`;
- prohibited inference/selection: `SENSITIVE_INFERENCE_PROHIBITED`, `BEAUTY_OR_AGE_SCORING_PROHIBITED`, `REAL_OR_USER_REFERENCE_PROHIBITED`, `CELEBRITY_OR_SCRAPED_REFERENCE_PROHIBITED`, `LEGACY_REUSE_PROHIBITED`;
- duplicate/split: `RAW_OR_NORMALIZED_EXACT_DUPLICATE`, `CONFIRMED_DUPLICATE_CLUSTER`, `DUPLICATE_CANDIDATE_REVIEW_MISSING`, `LEGACY_OR_SPLIT_OVERLAP`;
- assignment/coverage: `MORPHOLOGY_ASSIGNMENT_MISMATCH`, `STYLE_CONTEXT_ASSIGNMENT_MISMATCH`, `COVERAGE_REQUIREMENT_UNMET`;
- operation/evidence: `HIDDEN_NETWORK_DETECTED`, `RESOURCE_ENVELOPE_EXCEEDED`, `UNSUPPORTED_PASS_OR_MISSING_EVIDENCE`, `DOWNSTREAM_OR_PRODUCTION_BYPASS_ATTEMPTED`.

`YOUTHFUL_ADULT_PRESENTATION_ALLOWED` is non-failure categorical evidence. `COVERAGE_REQUIREMENT_UNMET` is a cohort stop, not permission to reject a safe identity for beauty or downstream performance. Every other disposition must declare whether it is hard reject, execution failure, hard stop, or soft non-admission; missing classification is fail-closed.

## No downstream-performance selection

Generation, admission, retention, duplicate clustering, coverage, and effective N may not use candidate transform results, target/control measurements, direction correctness, isolation score, tolerance, threshold, repeat/platform performance beyond the admitted QA reliability policy, holdout outcome, MVR result, QuestionBank desirability, user preference, beauty, or production value.

04-B produces only a fresh bounded calibration cohort and its admission/duplicate/diversity evidence. It does not choose a candidate formula, transform, threshold, READY dimension, 04-C result, 04-D preregistration, 04-E holdout, MVR, M6, or release outcome.

## Review result and validation

- `COHORT_AND_QA_ADMISSION_REVIEW: PASS`
- `PASS_SCOPE: FUTURE_FRESH_PRIVATE_SYNTHETIC_CALIBRATION_ONLY`
- `GENERATION_SPECIFICATION_CREATED: NO`
- `ASSET_OR_IDENTITY_CREATED: NO`
- `COHORT_CREATED: NO`
- `NEXT_REQUIRED_REVIEW: CC04-B-O01`

This result becomes effective only after this exact commit passes same-SHA CI, artifact inspection, independent Security/Privacy/Research Integrity review, independent Sol High review, and Principal acceptance. Until then Q01 remains a candidate, O01 remains closed, and generation and execution remain prohibited.

Acceptance requires exact parent and three-path allowlist; scoped Markdown formatting and `git diff --check`; specification, QA-order, identity, duplicate, cluster, split, legacy-exclusion, coverage, taxonomy, no-performance-selection, no-generation/private-mutation, binary/leakage, true-EOF, sentinel, last-occurrence, and canonical/mirror checks; then exact-SHA CI, all eight artifacts, independent reviews, and Principal acceptance.

After acceptance, stop Q01 and open only `CC04-B-O01`. Do not create a specification, assignment manifest, Asset, identity, cohort, holdout, private capability, execution contract, or generation call in this task.
