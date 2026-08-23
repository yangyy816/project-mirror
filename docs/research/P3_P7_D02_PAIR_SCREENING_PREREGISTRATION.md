# P3–P7 D02 Pair Screening Preregistration

## Status

```text
PREREGISTRATION_ID: P3_P7_D02_PAIR_SCREENING_V7
REVISION: 7
TRACK: DEMO_PROTOTYPE
SCHEMA: mirror.demo/D02PairScreeningPolicy/v6
STATUS: PENDING_INDEPENDENT_SOL_REVIEW
PRIOR_SOL_DECISION: REVISION_6_REVISE
REJECTED_REVISION_6_SHA: 8ab35f4e7d762069eb338c9e4a09a5d632c502c6
REJECTED_IMPLEMENTATION_SHA: cc56fc144d23d0b8109c1ef231b6afcfb7eb67c1
REJECTED_IMPLEMENTATION_DECISION: FAIL_REVISE_REQUIRED
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
screening_algorithm_version: demo-pair-screening-v6
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
record-pair set and Hamming distances. Revision 5 encoded the observation-only threshold as JSON null; Revision 6
replaces that representation with the exact string `OBSERVATION_ONLY_NO_THRESHOLD` and still forbids rejection,
ranking, selection or post-result threshold choice. An exact duplicate is a full-cardinality Gate failure after all 52
records exist; it does not truncate the 1,326 pHash observations.

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
PASSED -> full fixed cardinality, the exact-SHA report-global outcome Gate passes, at least two dimensions are eligible, exactly the first
          two eligible dimensions are selected, with 16 selected pairs and 32 selected result sides
FAILED -> full fixed cardinality, a report-global Gate fails or fewer than two dimensions are eligible, with zero
          selected dimensions/pairs/result sides and no import
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
`mirror.demo/DemoQuestionPair/v2` rows require the Revision 6 object-valued `qa_payload` with exactly:

```text
schema_version: mirror.demo/D02QuestionPairQAPayload/v2
screening_report_id
screening_report_digest
pair_screening_record_schema_version
pair_screening_record_digest
pair_screening_record_payload
```

There is no `qa_payload_digest` inside `qa_payload`; such a field would be cyclic and is forbidden. The immutable pair
row's shared `content_digest` covers the complete QA object. PostgreSQL recomputes the non-circular pair-record digest,
requires the embedded payload to equal the exact report record, then projects every pair/source/side/Asset/Variant fact
from that payload as specified by the Revision 6 section below.

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

Revision 5 was reviewed before the rejected implementation. Revision 6 of this preregistration and
`P3_P7_D02_CC_01` now requires a new independent Sol review before migration remediation, importer or private
execution. A review recommendation is evidence; Principal acceptance is still required.

## Revision 6 exact nested-evidence authority

This section is normative and supersedes every conflicting Revision 1–5 sentence. It responds to the independent
exact-SHA review of rejected implementation `cc56fc144d23d0b8109c1ef231b6afcfb7eb67c1`. That SHA remains negative
evidence and is not an accepted implementation baseline. Revision 6 freezes the element schemas, ordering identities,
cross-record linkage, Gate implications and non-circular digest preimages that Revision 5 left underspecified.

### Canonical record and digest rules

The top-level report schema remains `mirror.demo/D02PairScreeningReport/v1`. Its sixteen top-level groups remain the
same and are all mandatory. JSON objects are canonicalized by UTF-8 codepoint-ascending keys; every array below has the
explicit semantic order stated in this section. Canonical leaves are limited to JSON integers, booleans, allowlisted or
grammar-constrained strings, ordered arrays and exact-key objects. Raw binary float, JSON null, NaN, Infinity, exponent
decimal, negative zero, wall clock, path, locator, object key, Prompt, secret and private bytes are forbidden.

An inapplicable value uses an explicit discriminated record variant. It is never represented by null or by a fabricated
sentinel. Every stored evidence record follows this non-circular rule unless a more specific digest name is stated:

```text
stored_record = {
  schema_version,
  ...payload,
  record_digest
}

record_digest =
  mirror_demo_digest(schema_version, payload_without_schema_version_and_record_digest)
```

No digest preimage may contain its own digest, a parent report digest, an identifier derived from that digest or a wall
clock. Manifest and report digests are exactly:

```text
source_manifest_digest = mirror_demo_digest(
  "mirror.demo/D02SourceAuthorityManifest/v1",
  ordered_source_manifest
)

case_manifest_digest = mirror_demo_digest(
  "mirror.demo/D02GeometryCaseManifest/v1",
  ordered_case_manifest
)

selected_pair_manifest_digest = mirror_demo_digest(
  "mirror.demo/D02SelectedPairManifest/v2",
  selected_pair_manifest
)

report_digest = mirror_demo_digest(
  "mirror.demo/D02PairScreeningReport/v1",
  report_payload
)
```

The report table's `canonical_payload` is status-discriminated. Common fields are always present. `PASSED` adds
`selected_pair_manifest_digest`; `FAILED` omits that key entirely while the structured database column is SQL NULL.
`content_digest = mirror_demo_digest(schema_version, canonical_payload)`. No JSON null is accepted in either status.

### Exact group schemas

#### `schema_and_policy`

Schema `mirror.demo/D02SchemaAndPolicyBinding/v1`, exact keys:

```text
schema_version
source_manifest_digest
case_manifest_digest
screening_policy_digest
runtime_manifest_digest
vision_model_manifest_digest
topology_digest
measurement_config_digest
manual_review_policy_digest
duplicate_policy_digest
phash_implementation_digest
```

Every digest must equal its structured report column.

#### `ordered_source_manifest`

Exactly four `mirror.demo/D02SourceAuthorityManifestEntry/v2` records. Exact keys:

```text
schema_version
source_ordinal
source_authority_kind
source_authority_key
source_admission_event_id
source_admission_content_digest
source_output_id
source_asset_id
source_asset_sha256
source_asset_byte_size
source_asset_mime_type
source_asset_width
source_asset_height
source_receipt_digest
source_authority_digest
source_qa_snapshot_digest
source_landmark_digest
source_measurement_digest
source_provenance_digest
source_fact_snapshot_digest
raw_measurement_authority_digest
source_measurement_projection_digest
adult_synthetic_attested
original_formal_identity_id_status
source_p2_candidate_manifest_content_digest
dimension_authority_manifest_content_digest
ordered_supported_measurements
record_digest
```

`ordered_supported_measurements` contains exactly six `mirror.demo/D02SupportedSourceMeasurement/v1` objects, in this
order: `cheekbone_width`, `chin_height`, `eye_spacing`, `jaw_width`, `mouth_width`, `nose_width`. Each has exactly:

```text
schema_version
dimension_key
raw_value_fixed18
raw_confidence_fixed18
raw_reliability_fixed18
value_ppm
confidence_ppm
reliability_ppm
unit
```

For report v1, all four sources must be `DEMO_LOCAL_IMPORTED_COPY`, `adult_synthetic_attested=true`,
`original_formal_identity_id_status=UNKNOWN_REDACTED_NOT_RECOVERED`, and `unit=FACE_HEIGHT_PPM`. A
`FORMAL_REFERENCE` lacks the required recovered six-dimensional raw authority and is rejected rather than completed by
digest-only evidence or inferred values. PostgreSQL must re-read the latest local `ADMIT`, live Asset, recovered facts,
raw authority and projection and compare every field. The order is
`source_authority_key ASC, source_admission_event_id ASC`, with `source_ordinal=1..4`.

#### `ordered_case_manifest`

Exactly 48 `mirror.demo/D02GeometryCaseManifestEntry/v2` records. Exact keys:

```text
schema_version
case_ordinal
case_id
source_ordinal
source_authority_key
source_admission_event_id
source_asset_id
source_asset_sha256
source_manifest_digest
source_qa_snapshot_digest
source_measurement_projection_digest
source_p2_candidate_manifest_content_digest
dimension_authority_manifest_content_digest
geometry_ontology_version_digest
dimension_key
priority_index
direction
direction_index
magnitude_ppm
magnitude_index
ordered_control_dimensions
warp_plan_digest
geometry_algorithm_version
runtime_manifest_digest
runtime_config_digest
output_policy_version
output_width
output_height
determinism_level
case_specification_digest
record_digest
```

Order is source ordinal; priority `jaw_width=1`, `chin_height=2`, `eye_spacing=3`; direction
`DECREASE=1`, `INCREASE=2`; magnitude `15000=1`, `30000=2`. PostgreSQL recomputes both `case_id` and
`case_specification_digest` from the complete semantic payload.

#### `source_m3_repeat_evidence`

Exactly 12 `mirror.demo/D02SourceM3RepeatRecord/v1` records, ordered by source ordinal then `repeat_index=1..3`:

```text
schema_version
source_m3_record_id
source_ordinal
source_authority_key
source_admission_event_id
source_asset_id
source_asset_sha256
repeat_index
execution_receipt_digest
vision_model_manifest_digest
runtime_manifest_digest
topology_digest
canonical_output_digest
landmark_digest
measurement_digest
face_count
landmark_count
coordinates_finite
coordinates_in_bounds
repeat_gate_passed
record_digest
```

Each source's three canonical-output, landmark and measurement digests must be identical and each repeat must pass.

#### `m4_repeat_evidence`

Exactly 96 `mirror.demo/D02M4ExecutionRecord/v1` records, in case-manifest order then `replay_index=1,2`:

```text
schema_version
m4_execution_record_id
case_id
case_specification_digest
replay_index
source_output_id
source_asset_id
source_asset_sha256
result_output_id
result_sha256
result_byte_size
result_mime_type
result_width
result_height
changed_pixel_count
warp_plan_digest
geometry_algorithm_version
runtime_manifest_digest
runtime_config_digest
determinism_level
execution_receipt_digest
execution_succeeded
record_digest
```

The two records for each case must agree on result SHA, size, MIME, dimensions and changed-pixel count. Failure or a
missing record is an execution-cardinality stop and cannot produce a database report.

#### `result_m3_repeat_evidence`

Exactly 144 `mirror.demo/D02ResultM3RepeatRecord/v1` records, in case-manifest order then `repeat_index=1..3`:

```text
schema_version
result_m3_record_id
case_id
case_specification_digest
result_output_id
result_sha256
repeat_index
execution_receipt_digest
vision_model_manifest_digest
runtime_manifest_digest
topology_digest
canonical_output_digest
landmark_digest
measurement_observation_digest
face_count
landmark_count
coordinates_finite
coordinates_in_bounds
observation_state
repeat_gate_passed
record_digest
```

`observation_state` is `SUPPORTED` or `UNSUPPORTED_EXPLICIT`. Missing receipts/records or decode failure are cardinality
stops. An explicit unsupported measurement may enter a full-cardinality `FAILED` report.

#### `measurement_gate_evidence`

Exactly 48 `mirror.demo/D02MeasurementGateRecord/v2` records in case-manifest order. Exact keys:

```text
schema_version
case_id
case_specification_digest
dimension_key
requested_direction
requested_magnitude_ppm
monotonicity_peer_case_id
source_target_measurement
ordered_source_control_measurements
ordered_result_repeat_measurements
direction_gate_passed
target_min_gate_passed
target_max_gate_passed
control_drift_gate_passed
magnitude_monotonicity_gate_passed
measurement_gate_passed
record_digest
```

The source target and five ordered controls use the supported source-measurement schema. Each of the three result items
is exactly one discriminated variant:

```text
mirror.demo/D02SupportedResultMeasurement/v1:
  schema_version
  repeat_index
  result_m3_record_digest
  raw_result_target_fixed18
  raw_signed_target_delta_fixed18
  raw_target_absolute_delta_fixed18
  ordered_control_deltas
  max_control_dimension_key
  raw_max_control_drift_fixed18
  measured_signed_delta_ppm
  target_absolute_delta_ppm
  drift_ppm
  direction_gate_passed
  target_min_gate_passed
  target_max_gate_passed
  control_drift_gate_passed

mirror.demo/D02UnsupportedResultMeasurement/v1:
  schema_version
  repeat_index
  result_m3_record_digest
  unsupported_dimension_key
  unsupported_reason
  measurement_gate_passed
```

The unsupported variant must have `measurement_gate_passed=false`. PostgreSQL derives every delta, maximum control,
ppm and Gate boolean from the fixed18 authority and linked result-M3 records.

#### `decode_structure_immutability_evidence`

Exactly 48 `mirror.demo/D02DecodeStructureImmutabilityRecord/v1` records in case-manifest order. Exact keys:

```text
schema_version
case_id
case_specification_digest
source_asset_id
source_asset_sha256
m4_execution_record_digests
result_output_id
result_sha256
result_byte_size
result_mime_type
result_width
result_height
result_image_record_id
source_decode_valid
result_decode_valid
bounded_dimensions_passed
source_checksum_unchanged
m4_replay_bytes_equal
m4_replay_dimensions_equal
changed_pixel_count_equal
changed_pixel_count_positive
immutable_result_binding_passed
exact_lineage_passed
target_and_controls_complete
structure_gate_passed
record_digest
```

`m4_execution_record_digests` contains replay 1 then replay 2. PostgreSQL derives the booleans from linked records.

#### `manual_review_evidence`

Exactly 48 records ordered by `case_id ASC`, `decision_sequence=1..48`. The stored
`mirror.demo/D02ManualArtifactDecision/v1` shape is:

```text
schema_version
case_id
result_sha256
manual_review_version
manual_review_policy_digest
decision_sequence
background_seam
disconnected_contour
duplicated_feature
warp_tear
verdict
review_authority_digest
manual_decision_digest
```

`manual_decision_digest` excludes `schema_version` and itself. `verdict=PASS` if and only if all four criteria are false.

#### `exact_duplicate_evidence`

Schema `mirror.demo/D02ExactDuplicateEvidence/v2`, exact keys:

```text
schema_version
image_records
all_record_sha_unique
source_sha_unique
result_sha_unique
source_result_sha_disjoint
exact_sha_gate_passed
```

`image_records` contains exactly 52 discriminated records, ordered by `sha256 ASC, image_record_id ASC`, with
`image_record_ordinal=1..52`:

```text
mirror.demo/D02SourceImageAuthorityRecord/v2:
  schema_version
  image_record_ordinal
  image_record_id
  authority_role
  source_ordinal
  source_authority_key
  source_admission_event_id
  source_asset_id
  sha256
  byte_size
  mime_type
  width
  height
  image_record_digest

mirror.demo/D02ResultImageAuthorityRecord/v2:
  schema_version
  image_record_ordinal
  image_record_id
  authority_role
  source_ordinal
  source_authority_key
  source_admission_event_id
  case_id
  case_specification_digest
  result_output_id
  deterministic_result_asset_id
  sha256
  byte_size
  mime_type
  width
  height
  image_record_digest
```

`exact_sha_gate_passed` is exactly the conjunction of the four preceding booleans. A `PASSED` report requires it to be
true; `PASSED + false` is invalid even when cardinality and digest syntax are otherwise correct.

#### `phash_observation_evidence`

Schema `mirror.demo/D02PHashObservationEvidence/v2`, exact keys:

```text
schema_version
implementation_digest
bit_width
threshold_policy
ordered_record_signatures
comparisons
```

`bit_width=64` and `threshold_policy=OBSERVATION_ONLY_NO_THRESHOLD`; Revision 5's JSON-null threshold is forbidden.
There are exactly 52 `mirror.demo/D02PHashSignatureRecord/v1` items:

```text
schema_version
image_record_ordinal
image_record_id
image_record_digest
image_sha256
phash_hex
signature_digest
```

There are exactly 1,326 `mirror.demo/D02PHashComparisonRecord/v1` items:

```text
schema_version
comparison_ordinal
left_image_record_ordinal
left_image_record_id
left_signature_digest
right_image_record_ordinal
right_image_record_id
right_signature_digest
hamming_distance
comparison_digest
```

Each comparison has `left ordinal < right ordinal`; order is `(left ordinal, right ordinal)`. PostgreSQL validates the
complete `52 choose 2` universe and recomputes Hamming distance from both 64-bit hexadecimal signatures.

#### `pair_quality_evidence`

Exactly 24 `mirror.demo/D02PairScreeningRecord/v2` wrappers, ordered by source ordinal, priority index and magnitude
ascending. Wrapper exact keys:

```text
schema_version
pair_screening_record_payload
pair_screening_record_digest
```

The digest is non-circular:

```text
pair_screening_record_digest = mirror_demo_digest(
  "mirror.demo/D02PairScreeningRecord/v2",
  pair_screening_record_payload
)
```

Payload exact keys:

```text
pair_record_id
source_ordinal
source_authority_key
source_admission_event_id
source_asset_id
source_asset_sha256
dimension_key
priority_index
magnitude_ppm
left
right
same_source_gate_passed
opposed_direction_gate_passed
equal_magnitude_gate_passed
pair_side_gates_passed
pair_quality_state
pair_quality_ppm
lock_conclusion
lock_policy_digest
pair_gate_passed
```

Both `left` and `right` have exactly:

```text
case_id
case_specification_digest
requested_direction
requested_magnitude_ppm
result_output_id
result_asset_id
result_asset_sha256
result_asset_byte_size
result_asset_mime_type
result_asset_width
result_asset_height
asset_variant_id
asset_variant_type
lineage_digest
image_record_id
image_record_digest
result_m3_record_digests
measurement_gate_record_digest
decode_structure_record_digest
manual_decision_digest
raw_signed_target_delta_fixed18
raw_target_absolute_delta_fixed18
raw_max_control_drift_fixed18
measured_signed_delta_ppm
drift_ppm
automated_gate_digest
automated_gate_passed
manual_gate_passed
side_gate_passed
side_quality_state
side_quality_component_ppm
```

Left is `DECREASE`, right is `INCREASE`. A failed side uses
`side_quality_state=NOT_COMPUTED_GATE_FAILED` and component zero; a passing side uses `COMPUTED` and a component in
`1..1_000_000`. Pair quality uses the same explicit computed/not-computed state and never uses null.

#### `dimension_eligibility`

Exactly three `mirror.demo/D02DimensionEligibilityRecord/v2` items in fixed jaw/chin/eye order:

```text
schema_version
dimension_key
priority_index
ordered_pair_screening_record_digests
ordered_side_automated_gate_digests
sixteen_side_gate_digest
eight_pair_gate_digest
all_sixteen_side_gates_passed
all_eight_pair_gates_passed
all_manual_gates_passed
global_exact_sha_gate_passed
empty_lock_policy_gate_passed
eligible
failure_reasons
record_digest
```

Each dimension binds exactly eight pair records and sixteen sides. `eligible` is the conjunction of the five booleans.
`failure_reasons` is duplicate-free, follows a frozen enumeration order and exactly explains the false booleans.

#### `fixed_priority_selection_trace`

Exactly three `mirror.demo/D02SelectionTraceRecord/v1` items:

```text
schema_version
selection_step
dimension_key
priority_index
dimension_eligibility_record_digest
eligible
eligible_rank
selection_decision
selection_slot
selected
record_digest
```

Zero for rank or slot explicitly means not applicable. `selection_decision` is one of `SELECTED_SLOT_1`,
`SELECTED_SLOT_2`, `ELIGIBLE_NOT_SELECTED`, `INELIGIBLE`. PostgreSQL recomputes the first two eligible dimensions by
frozen priority; technical quality cannot reorder them.

#### `selected_pair_manifest`

For `PASSED`, exactly 16 `mirror.demo/D02SelectedPairManifestEntry/v2` records; for `FAILED`, an empty array. Exact keys:

```text
schema_version
selected_pair_ordinal
selected_dimension_slot
dimension_key
priority_index
source_ordinal
source_authority_key
source_admission_event_id
magnitude_ppm
pair_record_id
pair_screening_record_digest
left_case_id
left_result_asset_id
left_result_asset_sha256
left_asset_variant_id
right_case_id
right_result_asset_id
right_result_asset_sha256
right_asset_variant_id
entry_digest
```

Order is selected dimension slot, source ordinal, magnitude ascending. Every field is an exact projection of one
`pair_gate_passed=true` record in a selected dimension; digest-format or membership-only validation is insufficient.

#### `network_and_runtime_boundary`

Schema `mirror.demo/D02NetworkRuntimeBoundary/v2`, exact keys and required values:

```text
schema_version
public_internet_egress = DENIED
localhost_and_docker_internal_network = true
proxy_environment_present = false
production_provider_calls = 0
runtime_generation_calls = 0
boundary_receipt_digest
```

If this boundary is not established, the run stops before report insertion.

### Report status and Gate derivation

All reports require the complete universe:

```text
4 sources
48 cases
12 source M3 records
96 M4 records
144 result M3 records
48 measurement records
48 decode/structure records
48 manual decisions
52 image records
52 pHash signatures
1326 pHash comparisons
24 pair records
3 dimension records
3 selection records
```

Status is exactly:

```text
PASSED iff
  the full fixed universe exists
  AND the exact-SHA report-global outcome Gate passes
  AND exact_sha_gate_passed = true
  AND at least two dimensions are eligible
  AND selected dimensions are the first two eligible by frozen priority
  AND selected manifest is the exact 16-record projection of those dimensions.

FAILED iff
  the full fixed universe exists
  AND (a report-global full-cardinality Gate fails OR fewer than two dimensions are eligible)
  AND selected dimensions, pairs and sides are empty
  AND selected_pair_manifest_digest is SQL NULL and absent from canonical_payload.
```

The third dimension may fail while a report is `PASSED` if all global Gates pass and the first two eligible dimensions
can be selected. This is the intended three-candidate/two-selection contract. A false `FAILED` report when every global
Gate passes and at least two dimensions are eligible is rejected. `PREFLIGHT_AUTHORITY_STOP` and
`EXECUTION_CARDINALITY_STOP` still create no database report.

### Pair QA exact-content binding

`DemoQuestionPair` remains row schema v2, but its QA schema becomes
`mirror.demo/D02QuestionPairQAPayload/v2` with exactly:

```text
schema_version
screening_report_id
screening_report_digest
pair_screening_record_schema_version
pair_screening_record_digest
pair_screening_record_payload
```

At insert, PostgreSQL resolves the unique report record by digest and requires schema equality, digest equality,
JSONB structural equality via `IS NOT DISTINCT FROM` and successful canonical digest recomputation. It then derives and compares every pair
column, source admission and Asset, left/right result Asset and AssetVariant, lineage, dimension, magnitude, delta and
quality field from that embedded exact payload. The report record must have `pair_gate_passed=true` and must appear in
the selected manifest. Swapping two valid digests, changing one embedded field, or swapping both digest and payload
while leaving the pair row inconsistent must all be rejected.

### Private authority and tracked redaction

The complete report payload is local private database authority. It contains source/result identifiers, per-image
digests, raw fixed18 measurements and pHash observations and must not enter Git, ordinary CI artifacts, API responses or
MEMORY. Tracked acceptance evidence is limited to report schema/status/report/content digests, ten policy/config/manifest
digests, fixed counts, eligible and selected dimension names, aggregate dimension Gate digests, selected-pair manifest
digest and the explicit non-production boundary. PostgreSQL proves structure, current database authority, mathematics,
linkage and digest consistency; Principal-controlled runtime receipts and review authority prove private M3/M4 execution
and human visual review. Revision 6 does not invent a new signing or production-attestation authority.

### Revision 6 implementation gate

```text
D02_SCHEMA_IMPLEMENTATION: CLOSED_PENDING_REVISION_6_SOL_ACCEPT
D02_PRIVATE_SCREENING: CLOSED
D02_RESULT: NOT_VERIFIED
D03_D12: DEPENDENCY_GATED
FORMAL_PHASE_AUTHORITY: FALSE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

An independent Sol architecture/schema review must accept the exact Revision 6 change-control and preregistration
digests before migration, ORM or PostgreSQL tests may be revised. Review evidence is not `D02 TASK_ACCEPTED`.

## Revision 7 unique implementation contract

This section is normative and supersedes every conflicting Revision 1–6 sentence. Exact-SHA document commit
`8ab35f4e7d762069eb338c9e4a09a5d632c502c6` remains `REVISE_REQUIRED` negative evidence. Revision 7 retains the
accepted direction of Revision 6 and closes its remaining type, order, digest/ID preimage and Gate-state ambiguity.

The top-level report schema remains `mirror.demo/D02PairScreeningReport/v1`. The following nested schemas advance:

```text
mirror.demo/D02GeometryCaseManifestEntry/v2 -> v3
mirror.demo/D02MeasurementGateRecord/v2 -> v3
mirror.demo/D02PairScreeningRecord/v2 -> v3
mirror.demo/D02DimensionEligibilityRecord/v2 -> v3
mirror.demo/D02SelectionTraceRecord/v1 -> v2
```

All other Revision 6 schemas retain their version but acquire the scalar, ID, digest and array semantics below.

### Canonical JSON type system

PostgreSQL must inspect `jsonb_typeof` before extraction or cast. Integer fields never accept JSON strings; booleans
never accept strings or integers; decimal authority is always a JSON string and never a JSON number; digest and ID
fields are always strings; objects and arrays are compared as JSONB without text coercion.

```text
Bool:
  JSON boolean

Digest64 | Sha256 | SourceAuthorityKey:
  JSON string matching ^[0-9a-f]{64}$

Id32:
  JSON string matching ^[0-9a-f]{32}$

PHash64:
  JSON string matching ^[0-9a-f]{16}$

OpaqueOutputId:
  JSON string matching ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$
  and not '.', '..', slash, backslash, colon, whitespace, percent encoding,
  URI scheme or drive prefix

SchemaLiteral:
  JSON string equal to the one exact schema declared for that record

BoundVersionToken:
  JSON string matching ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$
  and equal to the report-bound policy/config/manifest or receipt authority

Fixed18:
  JSON string matching ^(0\.[0-9]{18}|1\.000000000000000000)$

SignedFixed18:
  JSON string matching ^-?(0\.[0-9]{18}|1\.000000000000000000)$
  numeric value in [-1,1]
  exact -0.000000000000000000 forbidden

Ppm:
  JSON integer 0..1_000_000

SupportedPpm:
  JSON integer 1..1_000_000

SignedPpm:
  JSON integer -1_000_000..1_000_000

PositiveInt32:
  JSON integer 1..2_147_483_647

NonnegativeInt32:
  JSON integer 0..2_147_483_647

PositiveInt64:
  JSON integer 1..9_223_372_036_854_775_807
```

Field-name defaults are exact: every `schema_version` is `SchemaLiteral`; every `*_digest`, `*_sha256` and
`source_authority_key` is `Digest64`; every `*_id` is `Id32` except `*_output_id`, which is `OpaqueOutputId`; every
`*_passed`, `*_finite`, `*_in_bounds`, `*_valid`, `*_equal`, `*_positive`, `selected` and
`adult_synthetic_attested` field is `Bool`. Every `*_version`, `*_algorithm_version`, `determinism_level` and
`variant_type` is a bound token; `variant_type` is additionally exact `demo_p3_p7_geometry_v1`.

Every source/result/image `*_mime_type` is `ImageMime`. Fields named `dimension_key` or
`unsupported_dimension_key` use `DimensionKey`; report candidate, case, pair, eligibility and trace dimensions are
restricted further to `CandidateDimension`. Fields named `direction` or `requested_direction` use `Direction`; `side`
uses `SideName`; `support_state`, `observation_state`, `measurement_evaluation_state`, `unsupported_reason`,
`*_quality_state`, `authority_role`, `verdict`, `threshold_policy`, `lock_conclusion`, `public_internet_egress` and
`selection_decision` use their exact enums below. No unlisted string value is accepted.

```text
source_authority_kind = DEMO_LOCAL_IMPORTED_COPY
original_formal_identity_id_status = UNKNOWN_REDACTED_NOT_RECOVERED
unit = FACE_HEIGHT_PPM
ImageMime = image/jpeg
authority_role = SOURCE | RESULT
SupportState = SUPPORTED | UNSUPPORTED
ObservationState = SUPPORTED | UNSUPPORTED_EXPLICIT
MeasurementEvaluationState = SUPPORTED_EVALUATED | UNSUPPORTED_EXPLICIT
Direction = DECREASE | INCREASE
SideName = LEFT | RIGHT
UnsupportedReason =
  MISSING_MEASUREMENT | LOW_CONFIDENCE | OUT_OF_BOUNDS | RUNTIME_UNSUPPORTED
QualityState = COMPUTED | NOT_COMPUTED_GATE_FAILED
manual verdict = PASS | FAIL
threshold_policy = OBSERVATION_ONLY_NO_THRESHOLD
lock_conclusion = PASS_FOR_FROZEN_EMPTY_NEUTRAL_POLICY_ONLY
public_internet_egress = DENIED
selection_decision =
  SELECTED_SLOT_1 |
  SELECTED_SLOT_2 |
  ELIGIBLE_NOT_SELECTED_CAPACITY |
  ELIGIBLE_NOT_SELECTED_INSUFFICIENT_SET |
  INELIGIBLE
```

Integer fields use these exact ranges or literals:

```text
source_ordinal: 1..4
priority_index: jaw_width=1, chin_height=2, eye_spacing=3
direction_index: DECREASE=1, INCREASE=2
magnitude_ppm: 15000 | 30000
magnitude_index: 15000=1, 30000=2
case_ordinal: 1..48
source/result M3 repeat_index: 1..3
M4 replay_index: 1..2
image_record_ordinal: 1..52
comparison_ordinal: 1..1326
decision_sequence: 1..48
selection_step: 1..3
eligible_rank: 0..3
selection_slot: 0..2
selected_pair_ordinal: 1..16
selected_dimension_slot: 1..2
face_count / landmark_count: NonnegativeInt32
source/result byte_size: PositiveInt64
width / height / output_width / output_height: PositiveInt32
changed_pixel_count: 0..result_width*result_height
hamming_distance: 0..64
bit_width: 64
production_provider_calls: 0
runtime_generation_calls: 0
```

Raw morphology/source/result/control absolute values use `Fixed18`; only `raw_signed_target_delta_fixed18` uses
`SignedFixed18`. `value_ppm`, confidence, reliability, target absolute delta, drift and computed quality use `Ppm`, with
source-supported values using `SupportedPpm`. `measured_signed_delta_ppm` uses `SignedPpm`. A computed quality is
`1..1_000_000`; a not-computed quality is exactly zero. Width, height, size and MIME must also equal every linked Asset,
M4 result, image record and case output policy; satisfying the scalar range alone is insufficient.

### Complete array order and cardinality

| Array                                   | Element                            |            Cardinality | Exact order                                        |
| --------------------------------------- | ---------------------------------- | ---------------------: | -------------------------------------------------- |
| `ordered_source_manifest`               | source entry v2                    |                      4 | source key, admission ID ascending                 |
| `ordered_supported_measurements`        | supported source measurement v1    |                      6 | cheekbone, chin, eye, jaw, mouth, nose             |
| `ordered_case_manifest`                 | case entry v3                      |                     48 | source, priority, direction index, magnitude index |
| `ordered_control_dimensions`            | `DimensionKey` string              |                      5 | exact target control order in dimension manifest   |
| `source_m3_repeat_evidence`             | source M3 record                   |                     12 | source, repeat 1..3                                |
| `m4_repeat_evidence`                    | M4 record                          |                     96 | case ordinal, replay 1..2                          |
| `result_m3_repeat_evidence`             | result M3 record                   |                    144 | case ordinal, repeat 1..3                          |
| `ordered_source_control_measurements`   | supported source measurement       |                      5 | exact case control order                           |
| `ordered_result_repeat_measurements`    | supported/unsupported result union |                      3 | repeat 1..3                                        |
| `ordered_control_deltas`                | `D02ControlDelta/v1`               |                      5 | exact case control order                           |
| `m4_execution_record_digests`           | `Digest64`                         |                      2 | replay 1 then 2                                    |
| `manual_review_evidence`                | manual decision                    |                     48 | case ID ascending; sequence 1..48                  |
| `image_records`                         | source/result image union          |                     52 | SHA then image ID ascending; ordinal 1..52         |
| `ordered_record_signatures`             | pHash signature                    |                     52 | identical ordinal/identity order as image records  |
| `comparisons`                           | pHash comparison                   |                   1326 | every `1 <= left < right <= 52` lexicographically  |
| `result_m3_record_digests`              | `Digest64`                         |                      3 | repeat 1, 2, 3                                     |
| `result_m3_repeat_gate_results`         | `Bool`                             |                      3 | repeat 1, 2, 3                                     |
| `pair_quality_evidence`                 | pair wrapper v3                    |                     24 | source, priority, magnitude 15000 then 30000       |
| `ordered_pair_screening_record_digests` | `Digest64`                         |        8 per dimension | source 1..4, magnitude 15000 then 30000            |
| `ordered_side_automated_gate_digests`   | `Digest64`                         |       16 per dimension | source, magnitude, LEFT then RIGHT                 |
| `failure_reasons`                       | frozen reason string               |                   0..5 | frozen reason order below                          |
| `fixed_priority_selection_trace`        | selection record v2                |                      3 | jaw, chin, eye; step 1..3                          |
| `eligible_dimension_keys`               | `CandidateDimension`               |                   0..3 | fixed-priority projection of eligible records      |
| `selected_dimension_keys`               | `CandidateDimension`               |     PASSED 2; FAILED 0 | selection-slot order from the state table          |
| `selected_pair_manifest`                | selected entry v2                  |    PASSED 16; FAILED 0 | slot, source, magnitude ascending                  |
| `unsupported_repeat_indexes`            | JSON integer                       |                   1..3 | strictly ascending                                 |
| `ordered_unsupported_reasons`           | `UnsupportedReason`                | same length as indexes | corresponding repeat order                         |

`mirror.demo/D02ControlDelta/v1` has exactly:

```text
schema_version: SchemaLiteral
control_ordinal: JSON integer 1..5
dimension_key: DimensionKey
raw_source_value_fixed18: Fixed18
raw_result_value_fixed18: Fixed18
raw_absolute_delta_fixed18: Fixed18
drift_ppm: Ppm
```

The dimension equals `ordered_control_dimensions[control_ordinal]`; absolute delta equals
`abs(raw_result - raw_source)`; ppm equals round-half-even of that delta times 1,000,000.

`failure_reasons` contains each applicable item exactly once in this order and no other token:

```text
ONE_OR_MORE_SIDE_GATES_FAILED
ONE_OR_MORE_PAIR_GATES_FAILED
ONE_OR_MORE_MANUAL_GATES_FAILED
GLOBAL_EXACT_SHA_GATE_FAILED
EMPTY_LOCK_POLICY_GATE_FAILED
```

### Replaced nested schema shapes

`mirror.demo/D02GeometryCaseManifestEntry/v3` is Revision 6's v2 exact key set plus one required
`execution_config_digest: Digest64`; its record digest uses the generic rule under the v3 domain.

`mirror.demo/D02MeasurementGateRecord/v3` has exactly:

```text
schema_version
case_id
case_specification_digest
dimension_key
requested_direction
requested_magnitude_ppm
monotonicity_peer_case_id
source_target_measurement
ordered_source_control_measurements
ordered_result_repeat_measurements
measurement_evaluation_state
gate_evaluation
record_digest
```

`gate_evaluation` is exactly one variant:

```text
mirror.demo/D02SupportedMeasurementGateEvaluation/v1:
  schema_version
  direction_gate_passed
  target_min_gate_passed
  target_max_gate_passed
  control_drift_gate_passed
  magnitude_monotonicity_gate_passed
  measurement_gate_passed

mirror.demo/D02UnsupportedMeasurementGateEvaluation/v1:
  schema_version
  unsupported_repeat_indexes
  ordered_unsupported_reasons
  measurement_gate_passed
```

The supported evaluation is allowed only when all three result variants are supported. The unsupported evaluation has
`measurement_gate_passed=false` and may not carry direction/min/max/drift/monotonicity booleans.

`mirror.demo/D02PairScreeningRecord/v3` wrapper remains exactly:

```text
schema_version
pair_screening_record_payload
pair_screening_record_digest
```

Its payload has exactly:

```text
pair_record_id
source_ordinal
source_authority_key
source_admission_event_id
source_asset_id
source_asset_sha256
dimension_key
priority_index
magnitude_ppm
screening_policy_digest
left
right
same_source_gate_passed
opposed_direction_gate_passed
equal_magnitude_gate_passed
pair_side_gates_passed
empty_lock_policy_gate_passed
pair_quality_state
pair_quality_ppm
lock_conclusion
lock_policy_digest
pair_gate_passed
```

`left` and `right` are discriminated by their exact schema. `mirror.demo/D02EvaluatedPairSide/v3` has exactly:

```text
schema_version
measurement_evaluation_state
case_id
case_specification_digest
requested_direction
requested_magnitude_ppm
result_output_id
result_asset_id
result_asset_sha256
result_asset_byte_size
result_asset_mime_type
result_asset_width
result_asset_height
asset_variant_id
asset_variant_type
lineage_digest
image_record_id
image_record_digest
result_m3_record_digests
measurement_gate_record_digest
decode_structure_record_digest
manual_decision_digest
raw_signed_target_delta_fixed18
raw_target_absolute_delta_fixed18
raw_max_control_drift_fixed18
measured_signed_delta_ppm
drift_ppm
automated_gate_digest
automated_gate_passed
manual_gate_passed
side_gate_passed
side_quality_state
side_quality_component_ppm
```

`measurement_evaluation_state=SUPPORTED_EVALUATED`. `mirror.demo/D02UnsupportedPairSide/v3` has exactly:

```text
schema_version
measurement_evaluation_state
case_id
case_specification_digest
requested_direction
requested_magnitude_ppm
result_output_id
result_asset_id
result_asset_sha256
result_asset_byte_size
result_asset_mime_type
result_asset_width
result_asset_height
asset_variant_id
asset_variant_type
lineage_digest
image_record_id
image_record_digest
result_m3_record_digests
measurement_gate_record_digest
decode_structure_record_digest
manual_decision_digest
unsupported_repeat_indexes
ordered_unsupported_reasons
automated_gate_digest
automated_gate_passed
manual_gate_passed
side_gate_passed
side_quality_state
side_quality_component_ppm
```

It fixes `measurement_evaluation_state=UNSUPPORTED_EXPLICIT`, automated/side Gates false, quality state
`NOT_COMPUTED_GATE_FAILED` and component zero. Raw delta, measured ppm and drift fields are forbidden in this variant.

`mirror.demo/D02DimensionEligibilityRecord/v3` retains the Revision 6 exact key set. Its two ordered digest arrays,
five booleans, failure reasons and record digest use the exact array and Gate rules below.

`mirror.demo/D02SelectionTraceRecord/v2` retains the Revision 6 exact key set, uses the Revision 7 selection enum and
must equal one row of the complete state table below.

### Derived configuration, ID and specification preimages

All deterministic IDs are the lowercase first 32 hexadecimal characters of
`mirror_demo_digest(domain_schema, exact_payload)`. No ID, its record digest, report digest or wall clock appears in its
own preimage. An identical semantic slot with different observation content is a collision and fails closed.

`execution_config_digest` is:

```text
mirror_demo_digest(
  "mirror.demo/D02ExecutionConfiguration/v1",
  {
    screening_policy_digest,
    runtime_manifest_digest,
    vision_model_manifest_digest,
    topology_digest,
    measurement_config_digest,
    manual_review_policy_digest,
    duplicate_policy_digest,
    phash_implementation_digest,
    geometry_algorithm_version,
    runtime_config_digest,
    output_policy_version,
    output_width,
    output_height,
    determinism_level
  }
)
```

`case_id` uses domain `mirror.demo/D02GeometryCaseId/v1` and exact payload:

```text
source_manifest_digest
source_authority_key
source_admission_event_id
source_asset_sha256
source_p2_candidate_manifest_content_digest
dimension_authority_manifest_content_digest
dimension_key
direction
magnitude_ppm
execution_config_digest
```

`case_specification_digest` uses domain `mirror.demo/D02GeometryCaseSpecification/v1` and exact payload:

```text
source_manifest_digest
source_ordinal
source_authority_key
source_admission_event_id
source_asset_id
source_asset_sha256
source_qa_snapshot_digest
source_measurement_projection_digest
source_p2_candidate_manifest_content_digest
dimension_authority_manifest_content_digest
geometry_ontology_version_digest
dimension_key
priority_index
direction
direction_index
magnitude_ppm
magnitude_index
ordered_control_dimensions
warp_plan_digest
geometry_algorithm_version
runtime_manifest_digest
runtime_config_digest
output_policy_version
output_width
output_height
determinism_level
execution_config_digest
```

The remaining ID domains and exact payloads are:

```text
mirror.demo/D02SourceM3RecordId/v1:
  source_manifest_digest
  source_authority_key
  source_admission_event_id
  source_asset_id
  source_asset_sha256
  repeat_index
  vision_model_manifest_digest
  runtime_manifest_digest
  topology_digest

mirror.demo/D02M4ExecutionRecordId/v1:
  case_id
  case_specification_digest
  replay_index
  geometry_algorithm_version
  runtime_manifest_digest
  runtime_config_digest
  determinism_level

mirror.demo/D02ResultM3RecordId/v1:
  case_id
  case_specification_digest
  result_output_id
  result_sha256
  repeat_index
  vision_model_manifest_digest
  runtime_manifest_digest
  topology_digest

mirror.demo/D02SourceImageAuthorityRecordId/v1:
  authority_role = SOURCE
  source_authority_key
  source_admission_event_id
  source_asset_id
  sha256

mirror.demo/D02ResultImageAuthorityRecordId/v1:
  authority_role = RESULT
  source_authority_key
  source_admission_event_id
  case_id
  case_specification_digest
  result_output_id
  deterministic_result_asset_id
  sha256

mirror.demo/D02PairScreeningRecordId/v1:
  source_authority_key
  source_admission_event_id
  source_asset_sha256
  dimension_key
  priority_index
  magnitude_ppm
  left_case_id
  right_case_id
  screening_policy_digest
  lock_policy_digest
```

### Named digest preimages

The generic record rule remains:

```text
record_digest = mirror_demo_digest(
  record.schema_version,
  record excluding schema_version and record_digest
)
```

Named nested digests use their exact record domains and exclude the schema/digest pair:

```text
manual_decision_digest = mirror_demo_digest(
  "mirror.demo/D02ManualArtifactDecision/v1",
  decision excluding schema_version and manual_decision_digest
)

image_record_digest = mirror_demo_digest(
  exact source-or-result image schema,
  record excluding schema_version and image_record_digest
)

signature_digest = mirror_demo_digest(
  "mirror.demo/D02PHashSignatureRecord/v1",
  signature excluding schema_version and signature_digest
)

comparison_digest = mirror_demo_digest(
  "mirror.demo/D02PHashComparisonRecord/v1",
  comparison excluding schema_version and comparison_digest
)

entry_digest = mirror_demo_digest(
  "mirror.demo/D02SelectedPairManifestEntry/v2",
  entry excluding schema_version and entry_digest
)
```

`automated_gate_digest` is:

```text
mirror_demo_digest(
  "mirror.demo/D02AutomatedSideGate/v1",
  {
    case_id,
    case_specification_digest,
    result_m3_record_digests,
    result_m3_repeat_gate_results,
    measurement_gate_record_digest,
    measurement_evaluation_state,
    measurement_gate_passed,
    decode_structure_record_digest,
    structure_gate_passed,
    automated_gate_passed
  }
)
```

The three repeat booleans are derived from the three linked result-M3 records in repeat order. Unsupported measurement
still produces this digest with `measurement_gate_passed=false` and therefore `automated_gate_passed=false`.

`sixteen_side_gate_digest` is:

```text
mirror_demo_digest(
  "mirror.demo/D02SixteenSideGate/v1",
  {
    dimension_key,
    priority_index,
    ordered_side_gate_entries
  }
)
```

`ordered_side_gate_entries` contains exactly 16 `mirror.demo/D02DimensionSideGateEntry/v1` objects, ordered by source,
magnitude, then LEFT/RIGHT, with exactly:

```text
schema_version
source_ordinal
magnitude_ppm
side
case_id
automated_gate_digest
manual_decision_digest
automated_gate_passed
manual_gate_passed
side_gate_passed
```

`eight_pair_gate_digest` is:

```text
mirror_demo_digest(
  "mirror.demo/D02EightPairGate/v1",
  {
    dimension_key,
    priority_index,
    ordered_pair_gate_entries
  }
)
```

`ordered_pair_gate_entries` contains exactly eight `mirror.demo/D02DimensionPairGateEntry/v1` objects, ordered by
source and magnitude, with exactly:

```text
schema_version
source_ordinal
magnitude_ppm
pair_record_id
pair_screening_record_digest
pair_gate_passed
```

The v3 pair wrapper digest is non-circular:

```text
pair_screening_record_digest = mirror_demo_digest(
  "mirror.demo/D02PairScreeningRecord/v3",
  pair_screening_record_payload
)
```

Its payload cannot contain the wrapper schema, its digest, report ID or report digest. Dimension aggregate digests must
be recomputed from these exact entries before their values can be copied into a bank.

### Gate-layer separation and exact formulas

The following are report-admission preconditions, not false-valued outcome Gates. A failure rejects report insertion or
belongs to the existing preflight/cardinality stop taxonomy; it cannot be converted into a `FAILED` report:

```text
the current four-source local authority is valid
network/runtime preflight is exact
all fixed arrays, cardinalities and Cartesian combinations exist
all record/ID/digest preimages validate
all cross-record references validate
all 12 source-M3 repeats pass and agree
all 96 M4 executions succeed
each M4 replay pair is deterministic and complete
52 pHash signatures and 1326 comparisons are complete
report, canonical and content digests validate
```

The sole report-global outcome Gate is:

```text
REPORT_GLOBAL_OUTCOME_GATES = [EXACT_SHA_UNIQUENESS]

report_global_outcome_gate_passed =
  exact_duplicate_evidence.exact_sha_gate_passed
```

pHash remains observation-only. Network, source-M3 and M4 determinism remain admission preconditions.

For every result-M3 repeat:

```text
repeat_gate_passed iff
  face_count = 1
  AND landmark_count = 478
  AND coordinates_finite
  AND coordinates_in_bounds
  AND observation_state = SUPPORTED
```

`UNSUPPORTED_EXPLICIT` fixes `repeat_gate_passed=false`.

For a supported measurement Gate record:

```text
direction_gate_passed =
  all three repeat signed deltas have the requested strict sign

target_min_gate_passed =
  all three target absolute deltas >= 0.000010000000000000

target_max_gate_passed =
  all three target absolute deltas <= 0.060000000000000000

control_drift_gate_passed =
  all three maximum control drifts <= 0.020000000000000000

magnitude_monotonicity_gate_passed =
  for the same source, dimension and direction, each repeat-index
  absolute delta at 30000 >= the same repeat-index absolute delta at 15000

measurement_gate_passed =
  direction_gate_passed
  AND target_min_gate_passed
  AND target_max_gate_passed
  AND control_drift_gate_passed
  AND magnitude_monotonicity_gate_passed
```

An unsupported measurement Gate record contains no direction/min/max/drift/monotonicity values and fixes
`measurement_gate_passed=false`.

The structure Gate is:

```text
structure_gate_passed =
  source_decode_valid
  AND result_decode_valid
  AND bounded_dimensions_passed
  AND source_checksum_unchanged
  AND m4_replay_bytes_equal
  AND m4_replay_dimensions_equal
  AND changed_pixel_count_equal
  AND changed_pixel_count_positive
  AND immutable_result_binding_passed
  AND exact_lineage_passed
  AND target_and_controls_complete
```

For an evaluated pair side:

```text
automated_gate_passed =
  all three result-M3 repeat Gates pass
  AND measurement_gate_passed
  AND structure_gate_passed

manual_gate_passed = linked manual verdict is PASS

side_gate_passed = automated_gate_passed AND manual_gate_passed
```

For an unsupported pair side, `automated_gate_passed=false` and `side_gate_passed=false`; the manual Gate still reflects
the linked decision. Side quality is uniquely derived:

```text
side_gate_passed=true:
  side_quality_state = COMPUTED
  side_quality_component_ppm = clamp(
    ROUND_HALF_EVEN(
      (1 - raw_max_control_drift_fixed18 / 0.020000000000000000) * 1000000
    ),
    1,
    1000000
  )

side_gate_passed=false:
  side_quality_state = NOT_COMPUTED_GATE_FAILED
  side_quality_component_ppm = 0
```

For a pair:

```text
same_source_gate_passed =
  both sides' source authority, admission and source Asset equal the parent pair source

opposed_direction_gate_passed =
  left requested direction = DECREASE
  AND right requested direction = INCREASE

equal_magnitude_gate_passed =
  left requested magnitude = right requested magnitude = pair magnitude

pair_side_gates_passed =
  left.side_gate_passed AND right.side_gate_passed

empty_lock_policy_gate_passed =
  lock_policy_digest equals the frozen empty-policy digest
  AND lock_conclusion = PASS_FOR_FROZEN_EMPTY_NEUTRAL_POLICY_ONLY

pair_gate_passed =
  same_source_gate_passed
  AND opposed_direction_gate_passed
  AND equal_magnitude_gate_passed
  AND pair_side_gates_passed
  AND empty_lock_policy_gate_passed
```

Pair quality is uniquely derived:

```text
pair_gate_passed=true:
  pair_quality_state = COMPUTED
  pair_quality_ppm = min(left component, right component)

pair_gate_passed=false:
  pair_quality_state = NOT_COMPUTED_GATE_FAILED
  pair_quality_ppm = 0
```

For each dimension:

```text
all_sixteen_side_gates_passed = AND of its exact 16 side Gate values
all_eight_pair_gates_passed = AND of its exact 8 pair Gate values
all_manual_gates_passed = AND of its exact 16 manual Gate values
global_exact_sha_gate_passed = report exact-SHA Gate
empty_lock_policy_gate_passed = AND of its exact 8 pair empty-lock Gates

eligible =
  all_sixteen_side_gates_passed
  AND all_eight_pair_gates_passed
  AND all_manual_gates_passed
  AND global_exact_sha_gate_passed
  AND empty_lock_policy_gate_passed
```

Each failure reason appears if and only if its corresponding dimension boolean is false, using the frozen order above.

### Complete selection-trace state table

Trace order is always `jaw_width`, `chin_height`, `eye_spacing`, and `selection_step=priority_index`. Each cell is:

```text
(eligible, eligible_rank, selection_decision, selection_slot, selected)
```

| Eligibility JCE | Status | Jaw                                                | Chin                                               | Eye                                                | `selected_dimension_keys`   |
| --------------- | ------ | -------------------------------------------------- | -------------------------------------------------- | -------------------------------------------------- | --------------------------- |
| `000`           | FAILED | `(F,0,INELIGIBLE,0,F)`                             | same                                               | same                                               | `[]`                        |
| `100`           | FAILED | `(T,1,ELIGIBLE_NOT_SELECTED_INSUFFICIENT_SET,0,F)` | `(F,0,INELIGIBLE,0,F)`                             | `(F,0,INELIGIBLE,0,F)`                             | `[]`                        |
| `010`           | FAILED | `(F,0,INELIGIBLE,0,F)`                             | `(T,1,ELIGIBLE_NOT_SELECTED_INSUFFICIENT_SET,0,F)` | `(F,0,INELIGIBLE,0,F)`                             | `[]`                        |
| `001`           | FAILED | `(F,0,INELIGIBLE,0,F)`                             | `(F,0,INELIGIBLE,0,F)`                             | `(T,1,ELIGIBLE_NOT_SELECTED_INSUFFICIENT_SET,0,F)` | `[]`                        |
| `110`           | PASSED | `(T,1,SELECTED_SLOT_1,1,T)`                        | `(T,2,SELECTED_SLOT_2,2,T)`                        | `(F,0,INELIGIBLE,0,F)`                             | `[jaw_width,chin_height]`   |
| `101`           | PASSED | `(T,1,SELECTED_SLOT_1,1,T)`                        | `(F,0,INELIGIBLE,0,F)`                             | `(T,2,SELECTED_SLOT_2,2,T)`                        | `[jaw_width,eye_spacing]`   |
| `011`           | PASSED | `(F,0,INELIGIBLE,0,F)`                             | `(T,1,SELECTED_SLOT_1,1,T)`                        | `(T,2,SELECTED_SLOT_2,2,T)`                        | `[chin_height,eye_spacing]` |
| `111`           | PASSED | `(T,1,SELECTED_SLOT_1,1,T)`                        | `(T,2,SELECTED_SLOT_2,2,T)`                        | `(T,3,ELIGIBLE_NOT_SELECTED_CAPACITY,0,F)`         | `[jaw_width,chin_height]`   |

There is no legal `FAILED` state with two or three eligible dimensions. A false exact-SHA Gate makes every dimension's
global exact-SHA conjunct false and therefore maps to `000`.

Report status is exactly:

```text
PASSED iff
  all report-admission preconditions validate
  AND exact_sha_gate_passed
  AND eligible count >= 2
  AND trace equals the unique state-table projection
  AND selected dimensions equal trace slots 1 and 2
  AND selected manifest is the exact 16-record projection

FAILED iff
  all report-admission preconditions validate
  AND (NOT exact_sha_gate_passed OR eligible count < 2)
  AND trace equals the unique FAILED projection
  AND selected_dimension_keys = []
  AND selected_pair_manifest = []
  AND selected pair/side counts = 0
  AND the SQL selected-pair-manifest digest is NULL
  AND canonical_payload omits that key
```

### Pair QA structural equality

PostgreSQL resolves exactly one report pair record by digest, requires:

```sql
qa.pair_screening_record_payload IS NOT DISTINCT FROM
  report_record.pair_screening_record_payload
```

then recomputes the canonical digest from that structural JSONB value and derives every pair column and
Asset/AssetVariant binding from it. JSONB does not preserve input byte spelling; the obsolete phrase “byte-equivalent
JSONB” is forbidden. Canonical digest equality separately proves canonical serialization, and array order remains
authoritative. `pair_screening_record_schema_version` is the exact literal
`mirror.demo/D02PairScreeningRecord/v3`; the embedded wrapper payload may not declare any other version.

### Revision 7 mandatory negative-test additions

In addition to every Revision 6 attack, PostgreSQL tests must re-canonicalize enclosing authority and prove:

1. an integer field encoded as JSON string is rejected;
2. a boolean field encoded as string or integer is rejected;
3. a decimal encoded as JSON number, exponent, leading plus or alternate zero is rejected;
4. `SignedFixed18=-0.000000000000000000` or a value outside `[-1,1]` is rejected;
5. `ordered_control_deltas` with missing/extra keys/items or wrong control order is rejected;
6. a control absolute delta or ppm inconsistent with its raw values is rejected;
7. `result_m3_record_digests` with other than three repeat-ordered items is rejected;
8. a dimension pair-digest array with other than eight unique source/magnitude slots is rejected;
9. a side-digest array with other than sixteen source/magnitude/LEFT-RIGHT slots is rejected;
10. failure reasons with missing/extra/duplicate/wrong-order items or boolean mismatch are rejected;
11. pHash signatures not matching all 52 image records by ordinal, ID, digest and SHA are rejected;
12. a comparison set other than every exact `left < right` pair is rejected;
13. any source-M3, M4, result-M3, image or pair ID with wrong domain or missing preimage field is rejected;
14. a case ID that uses the specification digest, a derived ID or omits execution config is rejected;
15. a case-specification digest containing itself or omitting a control/output/runtime field is rejected;
16. an automated Gate digest omitting a repeat, measurement or structure binding is rejected;
17. a sixteen-side aggregate omitting a manual Gate or using wrong side order is rejected;
18. an eight-pair aggregate using the right digest in the wrong source/magnitude slot is rejected;
19. a supported measurement outer record containing unsupported keys is rejected;
20. an unsupported outer record containing direction/min/max/drift/monotonicity keys is rejected;
21. an unsupported pair side carrying raw delta, ppm or drift fields is rejected;
22. an automated Gate true while a repeat, measurement or structure Gate is false is rejected;
23. a side Gate true while its manual Gate is false is rejected;
24. a pair Gate true while any of its five conjuncts is false is rejected;
25. any quality state/ppm shape inconsistent with its Gate is rejected;
26. exact-SHA false while any dimension remains eligible is rejected;
27. each of the eight eligibility patterns rejects altered rank, decision, slot or selected state;
28. a one-eligible `FAILED` trace marked `SELECTED_SLOT_1` is rejected;
29. a two-eligible trace marked `FAILED` is rejected;
30. a three-eligible third item using the obsolete `ELIGIBLE_NOT_SELECTED` token is rejected;
31. a network, source-M3 or M4 precondition failure submitted as a `FAILED` report is rejected;
32. a pHash observation change cannot alter status or selection without changing its canonical evidence digest;
33. QA objects with different input key spelling/order but equal JSONB structure and canonical digest are accepted;
34. QA array-order changes are rejected;
35. a structurally different QA payload referencing a valid pair digest is rejected;
36. a bound token inconsistent with the execution configuration or Principal receipt is rejected.

### Revision 7 implementation gate

```text
D02_SCHEMA_IMPLEMENTATION: CLOSED_PENDING_REVISION_7_SOL_ACCEPT
D02_PRIVATE_SCREENING: CLOSED
D02_RESULT: NOT_VERIFIED
D03_D12: DEPENDENCY_GATED
FORMAL_PHASE_AUTHORITY: FALSE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

Only a new independent Sol acceptance of the exact Revision 7 document blobs can reopen bounded migration remediation.
