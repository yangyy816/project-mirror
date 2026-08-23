# P3–P7 D02 Pair Screening Preregistration

## Status

```text
PREREGISTRATION_ID: P3_P7_D02_PAIR_SCREENING_V5
REVISION: 5
TRACK: DEMO_PROTOTYPE
SCHEMA: mirror.demo/D02PairScreeningPolicy/v4
STATUS: PENDING_INDEPENDENT_SOL_REVIEW
PRIOR_SOL_DECISION: REVISION_4_REVISE
PRIVATE_EXECUTION: NOT_STARTED
D02_PRIVATE_SCREENING: CLOSED
D02_SCHEMA_IMPLEMENTATION: CLOSED
THRESHOLD_SELECTION_AFTER_RESULTS: FORBIDDEN
P2_DIMENSION_PROMOTION: FORBIDDEN
PRODUCTION_RELEASE: NOT_AUTHORIZED
CURRENT_RESULT: NOT_VERIFIED
```

This policy is a Demo-only screening hypothesis. It selects two directionally meaningful geometry dimensions for the
algorithmically faithful local prototype. It does not establish P2 READY status, production geometry tolerance, real
face validity or biometric identity preservation.

## Frozen versions and canonicalization

```text
screening_algorithm_version: demo-pair-screening-v4
measurement_version: demo-d02-face-height-normalized-measurement-v1
decimal_serialization_version: demo-d02-decimal-fixed18-v1
quantization_version: demo-d02-round-half-even-ppm-v1
pair_quality_version: demo-pair-quality-v1
manual_review_version: demo-d02-artifact-review-v1
duplicate_algorithm_version: exact-sha256-d02-52-record-scope-v2
phash_observation_version: phash-dct-nearest-v1
phash_bit_width: 64
phash_implementation_path: services/api/src/mirror_api/synthetic_dataset/similarity.py
phash_implementation_base_sha: 54b72a21f8493442be3fc1a1181a27d089085990
phash_implementation_sha256: 5679f6097eeb6f3a81ae805bd248d70edc70172f03a36f834794d6fc6b30c1a5
lock_policy_version: demo-neutral-bank-lock-policy-v1
digest_envelope_version: demo-canonical-json-v1
dimension_authority_schema: mirror.demo/D02DimensionAuthorityManifest/v1
dimension_authority_manifest_digest: d4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a
geometry_ontology_version_digest: d902fe2cfdf69db9f62ccc2e5fa7c569227d652f1204aa683742fc3c592f38b9
p2_candidate_manifest_content_digest: eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4
```

Canonical evidence uses integers, booleans, strings and ordered arrays only. Measurements are parsed into `Decimal`
from the accepted M3 authority and serialized by `demo-d02-decimal-fixed18-v1` as nonnegative canonical fixed-point
strings with exactly 18 fractional digits. A non-null raw decimal must match exactly
`^(0\.[0-9]{18}|1\.000000000000000000)$`; leading signs, alternate leading zeroes, exponent notation and negative zero
are forbidden. Arithmetic uses Decimal precision 50 and `ROUND_HALF_EVEN`. Each raw morphology value, confidence and
reliability is first validated in `[0, 1]`; source eligibility additionally requires each supported value to lie in
`[0.000001000000000000,1.000000000000000000]` and quantize to at least 1 ppm. A zero geometry value maps to
`OUT_OF_BOUNDS`; zero confidence or reliability maps to `LOW_CONFIDENCE`. An unsupported entry persists three null raw
fields plus one allowlisted reason; an out-of-range value is never clamped into support. Only after raw in-range and
nonzero eligibility proof may a defensive clamp absorb a quantization tail before round-half-even ppm persistence; it
cannot change support classification. Binary float, NaN, infinity, wall clock and unordered collections are forbidden
digest inputs. Thresholds are evaluated on the fixed18 Decimal authority before ppm quantization.

## Revision 5 dimension and source-measurement binding

The exact tracked authority is:

```text
PATH: docs/research/P3_P7_D02_DIMENSION_AUTHORITY_MANIFEST.json
SCHEMA: mirror.demo/D02DimensionAuthorityManifest/v1
MANIFEST_CONTENT_DIGEST: d4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a
GEOMETRY_ONTOLOGY_VERSION_DIGEST: d902fe2cfdf69db9f62ccc2e5fa7c569227d652f1204aa683742fc3c592f38b9
SOURCE_P2_MANIFEST_SCHEMA: mirror.p2-m5/CC01CCandidateManifest/v1
SOURCE_P2_MANIFEST_CONTENT_DIGEST: eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4
```

The D02 source-authority manifest binds those exact values, not an unvalued field name. Each recovered source stores
the six ordered raw fixed18 measurement, confidence and reliability values directly inside
`mirror.demo/RecoveredSyntheticIdentityFacts/v2`, plus the quantized `mirror.demo/D02MorphologyProjection/v1`.
PostgreSQL must rebuild the integer ppm projection from raw fixed18 authority. A projection-only payload or a digest
whose underlying raw values are unavailable is inadmissible.

The embedded raw authority uses `mirror.demo/D02RawMeasurementAuthority/v1`. Its payload contains exactly, in this
order:

```text
measurement_version
decimal_serialization_version
source_p2_candidate_manifest_content_digest
dimension_authority_manifest_content_digest
ordered_entries
```

Each of the six ordered entries contains exactly `dimension_key`, `support_state`, `raw_value_fixed18`,
`raw_confidence_fixed18`, `raw_reliability_fixed18` and `unsupported_reason`. The external
`raw_measurement_authority_digest` is
`mirror_demo_digest('mirror.demo/D02RawMeasurementAuthority/v1', raw_measurement_authority)` and is excluded from the
payload, so the digest is non-circular. The two manifest fields are distinct and fixed respectively to
`eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4` and
`d4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a`; the ambiguous field name
`candidate_manifest_digest` is forbidden in new v2 payloads.

For `DEMO_LOCAL_IMPORTED_COPY`, PostgreSQL enforces null for all three existing formal identity/QA fields:
`formal_synthetic_identity_id`, `formal_accepted_qa_run_id` and `formal_accepted_qa_snapshot_digest`.
`formal_canonical_asset_id` remains non-null. `demo_0003` makes exactly those three fields nullable for the v2
mode/version matrix; downgrade preflight rejects every local/v2/report-bound row before DDL and restores all three v1
`NOT NULL` properties only after that proof.

All three candidates are mandatory screening inputs. The realized mandatory routing set is empty before screening and
is populated only by a `PASSED` report with the first two fully eligible candidates in the frozen priority. This does
not predeclare `jaw_width`, `chin_height` or `eye_spacing` as passed or P2 READY.

## Frozen case matrix

```text
source_identities: 4
candidate_dimensions: jaw_width, chin_height, eye_spacing
directions: DECREASE, INCREASE
magnitudes_ppm: 15000, 30000
canonical_result_cases: 4 x 3 x 2 x 2 = 48
```

Before any private handle opens, the Principal freezes an ordered
`mirror.demo/D02SourceAuthorityManifest/v1` with exactly four entries. Each entry binds ordinal,
`source_authority_key`, admission event ID, opaque source output ID, source Asset ID/SHA/size/MIME/dimensions,
recovered QA/landmark/measurement/provenance digests, the raw-measurement authority and digest, the quantized
morphology projection and digest, and both distinctly named P2-source and D02-dimension manifest digests. Before the
48-case screening can start, each of the four ordered sources must have all six ordered morphology dimensions
`SUPPORTED`, each with a non-null canonical fixed18 value, confidence and reliability in the supported range; otherwise
that source is ineligible and the run stops before case execution. The source-manifest digest is an input to every case
specification and the final report. Changing order or any source fact is a new preregistration.

Candidate order is fixed:

```text
jaw_width -> chin_height -> eye_spacing
```

Selection never reorders candidates by observed quality, pHash, visual appeal, identity, demographics or result
preference. All candidates remain `DEMO_EXPERIMENTAL_DIMENSION`.

Every target binds all five other measurements from the accepted six-dimension candidate manifest as controls:

| Target        | Required controls                                                            |
| ------------- | ---------------------------------------------------------------------------- |
| `jaw_width`   | `cheekbone_width`, `chin_height`, `eye_spacing`, `mouth_width`, `nose_width` |
| `chin_height` | `cheekbone_width`, `eye_spacing`, `jaw_width`, `mouth_width`, `nose_width`   |
| `eye_spacing` | `cheekbone_width`, `chin_height`, `jaw_width`, `mouth_width`, `nose_width`   |

No race, ethnicity, nationality, ancestry, sensitive label, beauty score or attractiveness score exists in the policy,
runner, report or selection logic.

## Repeat and runtime gates

Before any private handle is opened, the Principal must establish the task-scoped public-egress deny, remove all proxy
variables from the runner environment and verify the exact M3/M4 runtime/model/topology/algorithm/config digests.
Localhost and Docker internal PostgreSQL/object-storage traffic remain allowed.

Mandatory executions are:

```text
M3 source observations: 4 identities x 3 = 12
M4 transforms: 48 cases x 2 = 96
M3 result observations: 48 canonical results x 3 = 144
production Provider calls: 0
runtime generation calls: 0
```

Each M3 group of three must have exactly one face, exactly 478 landmarks, finite in-bounds coordinates and identical
canonical output, landmark and measurement digests. All three repeats must independently pass; selecting one successful
repeat is forbidden.

Each M4 pair of replays must produce identical result bytes, SHA-256, dimensions and changed-pixel count. A missing,
failed or inconsistent replay is an early-stop boundary because it makes fixed cardinality incomplete. No retry beyond
the two preregistered replays is allowed.

Any public egress attempt or runtime need for a public service is `EXTERNAL_RUNTIME_DEPENDENCY_FOUND` and stops the
screening run. Generative Provider remains `CAPABILITY_UNAVAILABLE` and is not a D02 dependency.

## Measurement and direction gates

For each repeated result:

```text
signed_target_delta =
  result_face_height_normalized_target
  - source_face_height_normalized_target

target_abs_delta = abs(signed_target_delta)

non_target_drift =
  max(
    abs(result_face_height_normalized_control[k]
        - source_face_height_normalized_control[k])
  )
```

The existing calibration aggregate `(result-source)/source` relative-delta formula is explicitly forbidden here.

Every result repeat must satisfy:

```text
requested INCREASE -> signed_target_delta > 0
requested DECREASE -> signed_target_delta < 0
target_abs_delta >= Decimal("0.00001")
target_abs_delta <= Decimal("0.06")
non_target_drift <= Decimal("0.02")
```

`0.00001`, `0.06` and `0.02` are `DEMO_ONLY_SCREENING_HYPOTHESIS` thresholds. The upper target bound is a
fail-closed runaway-warp bound equal to twice the largest requested magnitude. They must not be copied into P2 tolerance,
P2 READY or production identity-preservation evidence. Threshold comparison uses raw Decimal values before rounding.

Within the same identity, dimension and direction:

```text
target_abs_delta(30000 ppm) >= target_abs_delta(15000 ppm)
```

This proves only non-decreasing measured magnitude. It does not claim strict dose response or magnitude
discriminability.

## Structural, decode, immutability and artifact gates

Every canonical result must pass:

- source/result decode validity and bounded dimensions;
- source Asset checksum unchanged before and after both M4 runs and all M3 observations;
- result checksum bound to its immutable private object and future formal `Asset` row;
- changed-pixel count greater than zero and identical across M4 replays;
- exact source/result/transform/runtime/config lineage;
- target and five control measurement completeness;
- manual decisions for all four criteria: `background_seam`, `disconnected_contour`, `duplicated_feature`, `warp_tear`.

The 48 canonical result SHA-256 values each receive one
`mirror.demo/D02ManualArtifactDecision/v1` with case ID, result SHA, policy/version, fixed decision sequence, four
explicit booleans, verdict and review-authority digest. Decision sequence is canonical authority; wall-clock review time
is audit-only in the private registry and never changes the report digest. Every criterion must be false for a PASS. A
missing decision is not PASS. Review sheets and full-resolution result images remain private and are registered through
Principal custody; tracked evidence contains only schema/version/digests and aggregates.

## Duplicate and pHash scope

The comparison universe is exactly 52 uniquely keyed `mirror.demo/D02ImageAuthorityRecord/v1` records: four canonical
source records plus 48 canonical result records. Each record has a unique domain-separated `image_record_id`, authority
role, source key, optional case ID and SHA-256. Equal SHA values remain distinct records for negative evidence; they are
never collapsed into a set. Intentional M4 replay bytes and M3 repeat observations are not additional records. The
exact-SHA Gate passes only when:

```text
all 52 record SHA values are unique
the four source-record SHA values are mutually unique
the 48 result-record SHA values are mutually unique
the source-record SHA set intersect result-record SHA set is empty
```

Intentional M4 replay bytes and M3 repeat observations of one canonical result are excluded from duplicate counts.

pHash is observation-only. It computes exactly `52 choose 2 = 1,326` unordered comparisons over the 52 record universe,
ordered first by `(sha256 ASC, image_record_id ASC)` and then by the two record ordinals. Equal-byte records therefore
produce a Hamming distance of zero without reducing cardinality. The frozen implementation decodes checksum-bound
canonical JPEG to RGB, samples a 32x32 center-nearest grid,
uses integer luma `(77R + 150G + 29B + 128) >> 8`, a fixed-point 8x8 DCT table scaled by 1,000,000, the upper median of
the 63 non-DC coefficients, strict `coefficient > median`, vertical-frequency then horizontal-frequency ordering, first
coefficient as the most-significant bit, and 16 lowercase hexadecimal characters. The exact tracked implementation
digest is listed above. The report records bit width, implementation digest, ordered record universe, exact unordered
record-pair set and Hamming distances. Its threshold is exactly `null`; it cannot reject, rank, select or trigger a
threshold chosen after results. An exact duplicate is a full-cardinality Gate failure after all 52 records exist; it
does not truncate the 1,326 pHash observations.

## Empty neutral lock policy

The bank screening lock set is exactly empty. The only permitted conclusion is:

```text
LOCK_COMPATIBILITY: PASS_FOR_FROZEN_EMPTY_NEUTRAL_POLICY_ONLY
```

This does not prove compatibility with future user locks or session overrides. D04/D05 must still execute actual
constraint filtering and lock-conflict semantics.

## Pair quality

Quality is computed only after every boolean and threshold Gate above passes:

```text
side_component_ppm =
  clamp(
    ROUND_HALF_EVEN((1 - drift / Decimal("0.02")) * 1000000),
    1,
    1000000
  )

pair_quality_ppm = min(left_component_ppm, right_component_ppm)
```

`drift` is the raw maximum five-control Decimal drift for the side. The evidence stores the raw canonical decimal
input, quantized drift ppm, rounding mode, precision, left/right component and final integer pair quality. Quality never
compensates for a failed Gate and is not used for dimension eligibility or selection. It is technical routing evidence,
not a person, identity or aesthetic score.

## Dimension eligibility and final bank

A dimension is eligible only if all 16 result sides, all eight A/B pairs, every repeat Gate, every automated Gate and
every manual criterion pass. The first two eligible dimensions in the fixed priority are selected.

Each final pair has the same source identity and Asset, dimension and magnitude; left is `-magnitude`, right is
`+magnitude`. Its source, left and right Assets are distinct, and each result has an independently verified
`demo_p3_p7_*` AssetVariant pointing from the exact source to that result.

Only after the immutable database report is accepted, the final bank is exactly:

```text
4 identities x 2 selected dimensions x 2 magnitudes = 16 A/B pairs
32 selected result Assets and 32 exact demo_p3_p7_geometry_v1 AssetVariants
```

If fewer than two dimensions are eligible:

```text
P4_MULTI_DIMENSION_ACTIVE_ROUTING: BLOCKED
ALGORITHMIC_PROTOTYPE_PLATFORM: FAIL
BOUNDED_DIMENSION_RECOVERY_OR_REDESIGN: REQUIRED
```

P3/P5/P6/P7 work may continue, but no second dimension is fabricated and no threshold is relaxed after observation.
No result Asset, AssetVariant, bank or pair is imported when fewer than two dimensions are eligible. Unselected or
failed third-dimension results remain only in the Principal private registry.

## Revision 5 case, review and report authority

This section is normative and supersedes any conflicting Revision 1–4 wording above.

### Case specification and identifiers

Each of the 48 cases has a domain-separated 32-hex `case_id` derived from
`mirror.demo/D02GeometryCaseId/v1` and the source manifest digest, source authority key, admission event ID, source
Asset SHA, dimension, direction, magnitude, the distinctly named
`source_p2_candidate_manifest_content_digest`, `dimension_authority_manifest_content_digest` and execution-config
digest. Its immutable
`mirror.demo/D02GeometryCaseSpecification/v1` additionally binds source QA and morphology-projection digests, the five
ordered controls, warp-plan digest, geometry ontology, M4 algorithm/runtime/config/output/determinism versions and
specification digest.

The local specification maps real recovered authority as follows:

```text
source identity reference -> Demo source_authority_key + admission event ID
source QA reference       -> recovered source_qa_snapshot_digest
source measurements       -> recovered source_measurement_projection_digest
```

It does not create or populate formal `VariantSpecification.source_identity_id`, formal `source_qa_run_id`,
`TransformRun`, `SyntheticIdentity` or `SyntheticQARun`. Placeholder formal IDs are forbidden.

### Source morphology authority

Every source entry carries the ordered `mirror.demo/D02RawMeasurementAuthority/v1` and derived six-dimension
`mirror.demo/D02MorphologyProjection/v1` defined by `P3_P7_D02_CC_01` Revision 5. The raw payload and its non-circular
digest bind the two unambiguous manifest digests. Every fixed18 morphology value, confidence and reliability is
range-validated in
`[0, 1]` before any quantization. An out-of-range raw value must become `UNSUPPORTED` with `OUT_OF_BOUNDS` and null
value/zero confidence/zero reliability under the existing null-shape contract; it cannot be clamped into `SUPPORTED`.
Only an already in-range raw value may receive defensive post-validation clamping for quantization-tail absorption.
All six raw entries, raw-authority digest, measurement/config/quantization versions, support state, integer face-height
ppm value, confidence, reliability and reason are report inputs. PostgreSQL parses the strings as exact numeric,
applies `ROUND_HALF_EVEN`, and requires the rebuilt projection to equal the persisted integer authority. A four-source
manifest is valid only when every entry is `SUPPORTED` with non-null in-range raw value, confidence and reliability.
Raw 478 landmarks remain private; their digest is bound separately. A source without that complete valid raw and
derived projection cannot enter the four-source manifest or begin 48-case screening.

### Manual review authority

Manual decisions are ordered by `case_id ASC` and assigned `decision_sequence=1..48`. Each decision is:

```text
schema_version: mirror.demo/D02ManualArtifactDecision/v1
case_id
result_sha256
manual_review_version
manual_review_policy_digest
decision_sequence
background_seam: boolean
disconnected_contour: boolean
duplicated_feature: boolean
warp_tear: boolean
verdict: PASS | FAIL
review_authority_digest
```

`verdict=PASS` if and only if all four criteria are false. The Principal is the review authority; no user preference,
beauty, demographic or identity score exists. Wall-clock time is private audit evidence only and is excluded from
selection and canonical report digests.

### Exact report schema

Only a fully completed run produces one canonical `mirror.demo/D02PairScreeningReport/v1`. Its payload has exactly these
top-level groups:

```text
schema_and_policy
ordered_source_manifest
ordered_case_manifest
source_m3_repeat_evidence
m4_repeat_evidence
result_m3_repeat_evidence
measurement_gate_evidence
decode_structure_immutability_evidence
manual_review_evidence
exact_duplicate_evidence
phash_observation_evidence
pair_quality_evidence
dimension_eligibility
fixed_priority_selection_trace
selected_pair_manifest
network_and_runtime_boundary
```

Cardinalities are fixed: four sources, 48 cases, 12 source M3 repeats, 96 M4 executions, 144 result M3 repeats, 48
manual decisions, 52 exact-SHA image records, 1,326 pHash comparisons, 24 candidate pairs, and either 16 selected pairs
with 32 selected result sides or zero of both. Each case record binds its case/specification/result/repeat/manual/gate
digests. Raw threshold inputs are canonical Decimal strings with normalized zero and no exponent ambiguity; persisted
routing values are round-half-even integer ppm. Both representations and the comparison outcome enter the case digest.

The report status is:

```text
PASSED -> full fixed cardinality, exactly two selected dimensions, 16 selected pairs and 32 selected result sides
FAILED -> full fixed cardinality, at least one Gate failed, zero selected dimensions/pairs/result sides and no import
```

The inherited `schema_version` column is the exact report schema version. `report_digest` is SHA-256 of the canonical
envelope containing exactly that `schema_version` and the canonical `report_payload`. `canonical_payload` is the exact
immutable structured report projection: every source/case/policy/runtime/model/topology/measurement/manual/duplicate/
pHash manifest or config digest column; `report_payload`; `report_digest`; `status`; all eleven fixed count columns;
eligible and selected dimension arrays; and selected-pair manifest digest. It excludes surrogate `id`, the separately
supplied `schema_version`, `canonical_payload` itself, `content_digest`, audit-only `created_at`, and any terminal audit
field. PostgreSQL rebuilds that object from the structured columns and requires equality.

`content_digest` uses the already accepted shared authority without defining a second projection algorithm:

```text
content_digest = mirror_demo_digest(schema_version, canonical_payload)
```

No raw float, wall clock or unordered value enters either digest.

The report is inserted into immutable `demo_pair_screening_reports` only after fixed-cardinality completion. PostgreSQL
recomputes both digests, validates every cardinality, fixed order, Gate implication and selection rule, and rejects
arbitrary JSONB. A `PASSED` report is the only report that can bind a bank; a `FAILED` report is complete negative
evidence and cannot bind one. A stop before fixed-cardinality completion—public egress, runtime/model/digest mismatch,
repeat disagreement, missing source or any comparable boundary failure—creates no database report and imports no result
Asset, AssetVariant, bank or pair. It is append-only Principal private-registry negative evidence/receipt only.

After source/preflight admission succeeds, an ordinary case or dimension Gate failure is recorded and the runner still
completes the full fixed 48-case cardinality so it can produce `FAILED` evidence. Only an early-stop boundary above
aborts cardinality and produces registry-only negative evidence.

### Bank and pair payloads

Existing `mirror.demo/DemoQuestionBank/v1` rows preserve their array-valued `dimension_manifest` byte-for-byte. New
`mirror.demo/DemoQuestionBank/v2` rows require an object-valued `dimension_manifest` with exactly:

```text
schema_version: mirror.demo/D02QuestionBankDimensionManifest/v1
screening_report_id
screening_report_digest
source_manifest_digest
source_p2_candidate_manifest_content_digest
dimension_authority_manifest_content_digest
selected_pair_manifest_digest
selected_dimensions: exactly two objects ordered by frozen priority, each containing exactly
  dimension_key / priority_index / sixteen_side_gate_digest / eight_pair_gate_digest
```

PostgreSQL replaces the legacy array-only constraint with a version-aware v1-array/v2-object exact-key check; the ORM
type deliberately represents that union. The bank's enclosing canonical payload/content digest is the sole bank
payload digest, so no nested self-digest exists.

Existing `mirror.demo/DemoQuestionPair/v1` rows preserve their current object payload. New
`mirror.demo/DemoQuestionPair/v2` rows require object-valued `qa_payload` with exactly:

```text
schema_version: mirror.demo/D02QuestionPairQAPayload/v1
screening_report_id / screening_report_digest
pair_screening_record_digest
source_authority_key / source_admission_event_id
source_asset: id / sha256
dimension_key / magnitude_ppm
left and right:
  case_id / case_specification_digest
  result_asset_id / result_asset_sha256
  asset_variant_id / exact variant_type / lineage digest
  requested direction and magnitude
  raw signed target delta / target absolute delta / max control drift
  measured signed delta ppm / drift ppm
  automated Gate digest / manual decision digest / side quality component ppm
pair_quality_ppm
lock conclusion and lock policy digest
```

There is no `qa_payload_digest` inside `qa_payload`; such a field would be cyclic and is forbidden. The immutable pair
row's shared `content_digest` covers the complete QA object, while `pair_screening_record_digest` binds the exact record
inside the screening report. PostgreSQL enforces exact top-level and left/right object keys.

At commit, PostgreSQL resolves the bank and pair `screening_report_id`/`screening_report_digest`, requires they match
each other and the immutable `PASSED` report, resolves source admission, all Assets and all AssetVariants, requires exact
`demo_p3_p7_geometry_v1` lineage, and enforces exactly 16 pairs/32 unique selected sides matching the report manifest.
The added bindings are nullable only for existing `mirror.demo/DemoQuestionBank/v1` and
`mirror.demo/DemoQuestionPair/v1` rows; all post-`demo_0003` inserts must use the explicit v2 schema-version
discriminator and non-null accepted report binding. Application validation is not accepted as the sole authority.

## Output and stop rules

Private outputs for a fully completed run:

- 48 canonical result images and immutable object metadata;
- complete automated report with all repeat rows and measurements;
- 12 Principal review sheets grouped by identity/dimension;
- manual-review decisions;
- append-only private registry output/event rows.

Tracked outputs after acceptance contain only redacted policy, version/digest bindings, aggregate Gate outcomes,
selected dimensions and final pair manifest digests. They contain no private locator, storage key, image, landmark,
measurement payload, Prompt or secret.

The Revision 5 stop taxonomy is exclusive. `PREFLIGHT_AUTHORITY_STOP` covers missing/unauthorized handoff, digest/size
mismatch, source mutation, proxy/public-egress presence, runtime/model/topology/config mismatch, insufficient sources,
unsupported source projection or a nonpositive normalizer. `EXECUTION_CARDINALITY_STOP` covers a missing execution
receipt, fewer than the prescribed executions, M4 replay disagreement, absence of exactly one deterministic canonical
result for a case (not a cross-record duplicate), decode failure that prevents mandatory M3/pHash evidence, or
incomplete mandatory manual review. Those two classes create no
database report or import and are retained only as append-only Principal private-registry negative evidence.
`FULL_CARDINALITY_GATE_FAILURE` applies only when every prescribed evidence object and count exists but a direction,
magnitude, measurement-support, drift, result-QA, artifact, exact-duplicate or lock Gate fails; the runner completes all
48 cases, retains 52 uniquely keyed image records and all 1,326 record-pair pHash observations, and inserts one immutable
`FAILED` report with zero selected dimensions/pairs/sides. A structured observation
with an explicit unsupported measurement is a full-cardinality failure, while a missing receipt or undecodable result
that prevents the fixed evidence universe is a cardinality stop. Neither outcome is silently retried or re-thresholded.

Independent Sol review of Revision 5 of this preregistration, the dimension authority manifest and
`P3_P7_D02_CC_01` is mandatory before migration,
importer or private execution. A review recommendation is evidence; Principal acceptance is still required.
