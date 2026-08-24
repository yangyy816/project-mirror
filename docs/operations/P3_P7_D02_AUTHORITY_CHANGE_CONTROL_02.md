# P3–P7 D02 Change Control 02 — Measurement Quality Authority

## Decision status

```text
CHANGE_CONTROL_ID: P3_P7_D02_CC_02
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
REVISION: 10
CANDIDATE: REVISION_10_CANDIDATE_3
STATUS: PRINCIPAL_ACCEPTED_FOR_BOUNDED_IMPLEMENTATION
DISCOVERED_BY: D02 implementation preflight and independent authority review
BASE_SHA: 5bdf969e532a72dc904397490c932ac7e7f99401
D02_SCHEMA_AUTHORITY_CHECKPOINT: TASK_ACCEPTED_AT_REVISION_9
D02_MEASUREMENT_QUALITY_AUTHORITY: TASK_ACCEPTED_FOR_BOUNDED_IMPLEMENTATION
D02_PRIVATE_SCREENING: CLOSED
D02_TASK_ACCEPTED: NO
D03: BLOCKED
FORMAL_M3_AUTHORITY_CHANGE: NONE
FORMAL_P2_QUALIFICATION_CHANGE: NONE
FORMAL_PHASE_AUTHORITY: FALSE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

The independent Sol High exact-blob review accepted Candidate 3 with no P0, P1 or P2 findings:

```text
INDEPENDENT_SOL_EXACT_BLOB_REVIEW: PASS
REVIEWED_CHANGE_CONTROL_GIT_BLOB: 88cd37ca1c317d19fce77b1688c24d877a805aaa
REVIEWED_CHANGE_CONTROL_FILE_SHA256: 8f3395648497eb28c408f59b124d85e39141fd5bdaf7e76b71107769ebb09246
REVIEWED_MANIFEST_GIT_BLOB: b6da5c601ba60c5f21aec3c8d0f945a9e0fab1d3
REVIEWED_MANIFEST_FILE_SHA256: df39975dfcef15260458343babb88f0142d7f0f5f08556b399719b47fada129d
REVIEWED_MANIFEST_CONTENT_DIGEST: ed11f53e8e75428c396fb2b6711bd17fa996d49f8c4f5c9cdfebcfb36b42ed74
REVIEW_FINDINGS_P0: 0
REVIEW_FINDINGS_P1: 0
REVIEW_FINDINGS_P2: 0
```

This acceptance opens only the pure measurement-quality algorithm, pure authority builder, forward prototype
migration, ORM parity and PostgreSQL validator work defined below. It does not open private runtime/assets, 48-case
screening, QuestionBank admission, D03 or any formal/production authority.

Revision 10 candidate 1 blobs `bb584aeecc9c1e0270c33f540e5c1edde112ffb5` and
`a35267ffe7026ff7c0aed6b8dfae2af7099baa73` are `SUPERSEDED_DO_NOT_ACCEPT`. Candidate 2 is also
`SUPERSEDED_DO_NOT_ACCEPT` because its source repeat certificate referenced `source_m3_record_id`, whose preimage
depended on the source manifest and admitted identity that already embedded that certificate. Candidate 2 exact bytes
remain negative evidence only:

```text
CANDIDATE_2_CHANGE_CONTROL_GIT_BLOB: 2f27b87c3a618a061aadf62d7a9e50a3efe28473
CANDIDATE_2_CHANGE_CONTROL_FILE_SHA256: 5daa646509008edba229c47e90f5896b1b4e3ab81191703d8a8f6dca9b76dc38
CANDIDATE_2_MANIFEST_GIT_BLOB: a6108049d93848c5e216a9a7e7b2ca871e82678c
CANDIDATE_2_MANIFEST_FILE_SHA256: 7f93c721ca0ab2093aff35c5decf3593959a60b7f87ea28f5e69b5873541cb1b
STATUS: SUPERSEDED_DO_NOT_ACCEPT
```

Candidate 3 retains the observability and exact-repeat formulas, removes every post-admission identifier from the
source certificate, constructs SourceM3 records only after identity admission and source-manifest authority exist,
and freezes the complete v2/v3/v4 envelope, digest and row-equality contracts. It does not open implementation or
private execution.

Revision 9 correctly made confidence and reliability mandatory, quantized and fail closed, but it did not define a
producer, formula, version or digest for either value. The accepted private M3 wrapper exposes exactly one face and 478
normalized XYZ landmarks; it does not expose per-landmark confidence, visibility or presence. Therefore none of the
following is admissible evidence:

```text
constant 1.0
schema fixture 0.9
M3 runtime admission threshold 0.5
source QA PASS renamed as confidence
coordinate presence renamed as model confidence
```

This change control adds a deterministic, non-sensitive Demo geometric-observability proxy and an exact-repeat
determinism certificate. Neither is a model confidence score, model accuracy estimate, biometric identity result,
real-user validity result or production qualification.

## Exact peer manifest binding

The sole peer manifest is:

```text
PATH: docs/research/P3_P7_D02_MEASUREMENT_QUALITY_AUTHORITY_MANIFEST.json
SCHEMA: mirror.demo/D02MeasurementQualityAuthorityManifest/v1
GIT_BLOB: b6da5c601ba60c5f21aec3c8d0f945a9e0fab1d3
FILE_SHA256: df39975dfcef15260458343babb88f0142d7f0f5f08556b399719b47fada129d
MANIFEST_CONTENT_DIGEST: ed11f53e8e75428c396fb2b6711bd17fa996d49f8c4f5c9cdfebcfb36b42ed74
MEASUREMENT_QUALITY_CONFIG_DIGEST: ed52feca45f18b976e34d419da117d777d540978b9552c3e423a0d0c543e8f47
MEASUREMENT_CONFIG_DIGEST: ab5f745641a6f4539a8010fe32dda82b6c1066a8cb97d36ae17de737b901e8d3
IMPORT_CONFIG_DIGEST: 3cb5043028bec1c25e95822432db69a84b1eae9af3788201fafffe53f40acec2
D02_EXECUTION_RUNTIME_SET_DIGEST: 6d739c2e269128ea7bc09358203aa7efe0714484b1a216a9f401353a243135ed
```

The Git blob and file SHA bind the exact review candidate. Any peer-manifest byte change invalidates this section and
requires a new Revision 10 candidate before implementation. The manifest content digest uses
`demo-canonical-json-v1`, domain separation and the exact exclusion rule written in the manifest.

## Principal-only runtime resolution

The Integration Principal resolved only the original D00 receipt/registry authorized for this Goal. No disk scan,
protected `.tmp/` read, locator output or private byte handoff occurred. Redacted digest-membership checks matched the
accepted tracked P2 authority for:

```text
M3 Windows wrapper SHA-256
M3 Windows main SHA-256
M3 Vision model SHA-256
M4 Windows runtime manifest digest
468-point / 852-triangle topology SHA-256
```

The peer manifest publishes those non-secret digests and the accepted candidate reference only. It contains no host
path, opaque locator, object key, signed URL, secret, raw landmark, image byte or Prompt.

## Frozen confidence authority

```text
CONFIDENCE_ALGORITHM_VERSION: demo-d02-landmark-frame-observability-v1
CONFIDENCE_KIND: DEMO_GEOMETRIC_OBSERVABILITY_PROXY_NOT_MODEL_CONFIDENCE
COORDINATE_SYSTEM: normalized_image_xy_v1
DECIMAL_PRECISION: 50
ROUNDING: ROUND_HALF_EVEN
BINARY_FLOAT_CANONICAL_AUTHORITY: FORBIDDEN
```

The producer parses the M3 runtime's original normalized `x` and `y` numeric tokens directly as `Decimal`. It does not
first convert through binary float. `z`, image-content classes, population priors, attractiveness, race, ethnicity,
nationality, ancestry and all other sensitive labels are excluded.

For dimension `d`, repeat `r` and every landmark `a` in the exact ordered `required_landmarks` array of the accepted
dimension manifest:

```text
anchor_margin(a,r) =
  min(x[a,r], 1-x[a,r], y[a,r], 1-y[a,r])

repeat_observability(d,r) =
  clamp(2 * min(anchor_margin(a,r) for a in required_landmarks[d]), 0, 1)

group_observability(d) =
  min(repeat_observability(d,r) for r in ordered repeats 1,2,3)

raw_confidence_fixed18 =
  fixed18_round_half_even(group_observability(d))

confidence_ppm =
  round_half_even(raw_confidence_fixed18 * 1_000_000)
```

The same group formula applies separately to each source M3 three-repeat group and each result M3 three-repeat group.
It measures only whether the required continuous landmarks remain observable away from the normalized frame boundary.
It does not detect occlusion and does not estimate model correctness.

A dimension is supported only when every required landmark exists, all XY values are finite and in closed interval
`[0,1]`, the accepted face-height normalizer is strictly positive, every runtime/model/topology/config digest matches,
unquantized observability is at least `0.000001` and the fixed quantization yields at least one ppm. Unsupported values
retain the Revision 9 union shape. Reason precedence is:

```text
RUNTIME_UNSUPPORTED
MISSING_MEASUREMENT
OUT_OF_BOUNDS
LOW_CONFIDENCE
```

`LOW_CONFIDENCE` now means only that the explicitly named geometric-observability proxy is below the support floor.
It is not a model confidence statement. Missing or invalid inputs cannot be clamped, imputed or replaced with a
constant.

## Frozen measurement observation authority

The private runner computes observability from raw normalized XY. Raw 478-landmark arrays remain outside Git and
ordinary PostgreSQL. PostgreSQL does not pretend to recompute XY geometry; it validates the persisted canonical
observation, its runtime/model/topology/config bindings, its digest, its repeat equality and its downstream
raw/projection/report mappings. Exact algorithm reference tests plus the Principal private execution receipt prove the
XY calculation boundary.

`mirror.demo/D02MeasurementObservation/v1` has exactly:

```text
schema_version
observation_role
subject
canonical_output_digest
landmark_digest
runtime_manifest_digest
vision_model_manifest_digest
topology_digest
measurement_config_digest
measurement_quality_config_digest
measurement_quality_manifest_content_digest
confidence_kind
ordered_measurements
measurement_observation_digest
```

`observation_role` is `SOURCE | RESULT`. A SOURCE subject is
`mirror.demo/D02SourceObservationSubject/v1` with exact keys `schema_version`, `source_output_id`, `source_asset_id`
and `source_asset_sha256`. A RESULT subject is `mirror.demo/D02ResultObservationSubject/v1` with exact keys
`schema_version`, `case_id`, `case_specification_digest`, `result_output_id` and `result_sha256`.

`ordered_measurements` contains exactly six `mirror.demo/D02MeasurementObservationEntry/v1` records in
`cheekbone_width, chin_height, eye_spacing, jaw_width, mouth_width, nose_width` order. Each entry has exactly:

```text
schema_version
dimension_key
support_state
raw_value_fixed18
observability_state
raw_observability_fixed18
unsupported_reason
```

The only valid entry unions are:

```text
SUPPORTED:
  raw_value_fixed18 = canonical fixed18
  observability_state = COMPUTED
  raw_observability_fixed18 >= 0.000001000000000000
  unsupported_reason = null

UNSUPPORTED + LOW_CONFIDENCE:
  raw_value_fixed18 = null
  observability_state = COMPUTED
  0 <= raw_observability_fixed18 < 0.000001000000000000
  unsupported_reason = LOW_CONFIDENCE

UNSUPPORTED + RUNTIME_UNSUPPORTED | MISSING_MEASUREMENT | OUT_OF_BOUNDS:
  raw_value_fixed18 = null
  observability_state = NOT_COMPUTABLE
  raw_observability_fixed18 = null
  unsupported_reason = the selected allowlisted reason
```

The digest is non-circular:

```text
measurement_observation_digest =
  mirror_demo_digest(
    "mirror.demo/D02MeasurementObservation/v1",
    observation excluding schema_version and measurement_observation_digest
  )
```

`repeat_index`, execution receipt, M3 record ID, wall clock and group reliability are forbidden inside this digest;
otherwise exact equality across three repeats would be structurally impossible.

`mirror.demo/D02SourceM3RepeatRecord/v2` replaces the v1 `measurement_digest` key with the two exact keys
`measurement_observation` and `measurement_observation_digest`. Its full exact key set is:

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
measurement_observation
measurement_observation_digest
face_count
landmark_count
coordinates_finite
coordinates_in_bounds
repeat_gate_passed
record_digest
```

`mirror.demo/D02ResultM3RepeatRecord/v2` retains the v1 `measurement_observation_digest`, adds the embedded
`measurement_observation`, and has exactly:

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
measurement_observation
measurement_observation_digest
face_count
landmark_count
coordinates_finite
coordinates_in_bounds
observation_state
repeat_gate_passed
record_digest
```

Each record digest covers the embedded observation and its digest. The observation subject must match every repeated
record field. `RecoveredSyntheticIdentityFacts/v3` is the v2 exact key set plus
`source_measurement_observation`, `source_measurement_observation_digest`, `source_repeat_certification` and
`source_repeat_certification_digest`. It stores one canonical source observation because the certificate proves all
three repeat observations equal. Existing `source_measurement_digest` is retained with the single v3 meaning
`source_measurement_digest == source_measurement_observation_digest`; no second measurement authority exists.

## Frozen reliability authority

```text
RELIABILITY_ALGORITHM_VERSION: demo-d02-three-repeat-digest-certification-v1
RELIABILITY_KIND: EXACT_REPEAT_DETERMINISM_CERTIFICATION_NOT_MODEL_RELIABILITY
REPEAT_COUNT: 3
```

Each ordered M3 repeat must independently bind one face, 478 landmarks, finite in-bounds coordinates and the exact
runtime/model/topology/config authority. A source or result group is certified only when all three values are equal for
each of:

```text
canonical_output_digest
landmark_digest
measurement_observation_digest
```

Only exact equality derives:

```text
raw_reliability_fixed18: "1.000000000000000000"
reliability_ppm: 1000000
```

This `1.0` is a derived deterministic replay certificate, not a default and not a claim about accuracy, identity,
cross-device reliability or real users. Source mismatch is `PREFLIGHT_AUTHORITY_STOP`: no identity import, M4 handle,
48-case execution or database report may follow. Result mismatch is `CASE_EXECUTION_CARDINALITY_STOP`: the case result,
report and QuestionBank cannot be admitted.

`mirror.demo/D02SourceRepeatDeterminismCertification/v1` has exactly:

```text
schema_version
subject
runtime_manifest_digest
vision_model_manifest_digest
topology_digest
measurement_config_digest
measurement_quality_config_digest
measurement_quality_manifest_content_digest
reliability_kind
repeat_count
ordered_repeat_bindings
certification_state
certified_raw_reliability_fixed18
certified_reliability_ppm
source_repeat_certification_digest
```

Its subject is the exact SOURCE observation subject. `ordered_repeat_bindings` has exactly three records in repeat
order, each with exactly:

```text
repeat_index
execution_receipt_digest
canonical_output_digest
landmark_digest
measurement_observation_digest
face_count
landmark_count
coordinates_finite
coordinates_in_bounds
repeat_gate_passed
```

The source certificate is a pre-admission authority. Its root, subject, bindings and digest preimage must not contain
any of the following post-admission fields or aliases:

```text
source_m3_record_id
source_m3_record_digest
source_manifest_digest
source_admission_event_id
source_admission_content_digest
identity_content_digest
source_fact_snapshot_digest
source_authority_manifest_entry_digest
report_digest
source_authority_key
any placeholder post-admission identifier
```

The allowed receipt, canonical-output, landmark and observation digests bind already-produced execution evidence;
they are not SourceM3 record digests. This exact pre-admission tuple is the only bridge later used to compare a
post-admission SourceM3 record.

The only persisted state is `CERTIFIED_EXACT_REPEAT`; all structural preconditions pass, all three digest families are
equal, `repeat_count=3`, raw reliability is `1.000000000000000000` and ppm reliability is `1000000`. The digest is
`mirror_demo_digest("mirror.demo/D02SourceRepeatDeterminismCertification/v1", certification excluding schema_version
and source_repeat_certification_digest)`. The certificate and digest are embedded in
`RecoveredSyntheticIdentityFacts/v3`. Only after the v3 identity content digest, admission event, v3 source-manifest
entry and aggregate source-manifest digest exist may `D02SourceM3RecordId/v1` and `D02SourceM3RepeatRecord/v2` be
constructed. Each later record must match its certificate binding, field by field, for `repeat_index`, receipt,
canonical output, landmark, observation digest, face/landmark counts, finite/in-bounds flags and repeat Gate, and must
embed the same observation stored in the facts snapshot. Comparing only one aggregate digest is forbidden.

`mirror.demo/D02ResultRepeatDeterminismCertification/v1` has the same root fields, replacing the digest field with
`result_repeat_certification_digest`, uses the RESULT subject and its own domain separator. Its ordered bindings have
exactly:

```text
repeat_index
result_m3_record_id
execution_receipt_digest
canonical_output_digest
landmark_digest
measurement_observation_digest
face_count
landmark_count
coordinates_finite
coordinates_in_bounds
observation_state
repeat_gate_passed
```

The result certificate and digest are embedded in `mirror.demo/D02MeasurementGateRecord/v4`. That record is the v3
exact key set plus the two certificate keys and therefore has exactly:

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
result_repeat_certification
result_repeat_certification_digest
record_digest
```

The three ordered result measurements must cross-link the corresponding ResultM3RepeatRecord v2 observation digest.
PostgreSQL validates each observation, then the certificate, then the measurement Gate and enclosing report.

The total failure and persistence semantics are:

| Role   | Structural preconditions | Three digest families | Dimension state         | Certificate                       | Persistence and outcome                                                                 |
| ------ | ------------------------ | --------------------- | ----------------------- | --------------------------------- | --------------------------------------------------------------------------------------- |
| Source | PASS                     | equal                 | all six supported       | group `1.0`                       | v3 identity import allowed; M4 may open after all other Gates                           |
| Source | PASS                     | equal                 | one or more unsupported | private-evidence group `1.0` only | per-dimension reliability remains null/0; no identity row; `PREFLIGHT_AUTHORITY_STOP`   |
| Source | PASS                     | mismatch              | any                     | not created                       | registry-only negative evidence; no identity/M4; `PREFLIGHT_AUTHORITY_STOP`             |
| Source | FAIL                     | N/A                   | any                     | not created                       | no observation authority or identity; `PREFLIGHT_AUTHORITY_STOP`                        |
| Result | PASS                     | equal                 | all supported           | group `1.0`                       | persist v2/v4 records and continue case                                                 |
| Result | PASS                     | equal                 | one or more unsupported | group `1.0`                       | per-dimension reliability remains null/0; preserve cardinality; Report outcome `FAILED` |
| Result | PASS                     | mismatch              | any                     | not created                       | no Report; `CASE_EXECUTION_CARDINALITY_STOP`                                            |
| Result | FAIL                     | N/A                   | any                     | not created                       | no observation authority or Report; `CASE_EXECUTION_CARDINALITY_STOP`                   |

The certificate's `1.0` is group-level exact replay determinism. The unsupported union's null/raw reliability and zero
ppm are dimension-level usability. Neither overwrites the other. A mismatch never means reliability zero; it means no
valid certificate exists. `RUNTIME_UNSUPPORTED` is admissible only for a successful, structured and exactly repeatable
dimension-level unsupported observation. Runtime failure, missing receipt or digest mismatch is a structural
precondition failure, never `UNSUPPORTED_EXPLICIT`.

## Authority envelopes and digest chain

New envelopes:

```text
mirror.demo/D02MeasurementQualityConfig/v1
mirror.demo/D02MeasurementQualityAuthorityManifest/v1
mirror.demo/D02MeasurementExecutionConfig/v1
mirror.demo/D02IdentityImportConfiguration/v3
mirror.demo/D02MeasurementObservation/v1
mirror.demo/D02MeasurementObservationEntry/v1
mirror.demo/D02SourceObservationSubject/v1
mirror.demo/D02ResultObservationSubject/v1
mirror.demo/D02SourceRepeatDeterminismCertification/v1
mirror.demo/D02ResultRepeatDeterminismCertification/v1
```

Upgraded envelopes:

```text
mirror.demo/D02RawMeasurementAuthority/v1      -> v2
mirror.demo/D02MorphologyProjection/v1         -> v2
mirror.demo/RecoveredSyntheticIdentityFacts/v2 -> v3
mirror.demo/DemoSyntheticIdentity/v2           -> v3
mirror.demo/D02SourceAuthorityManifestEntry/v2 -> v3
mirror.demo/D02SourceM3RepeatRecord/v1          -> v2
mirror.demo/D02ResultM3RepeatRecord/v1          -> v2
mirror.demo/D02MeasurementGateRecord/v3         -> v4
mirror.demo/D02SchemaAndPolicyBinding/v1        -> v2
mirror.demo/D02PairScreeningReport/v1           -> v2
demo-d02-identity-importer-v2                   -> v3
```

Unchanged envelopes:

```text
mirror.demo/DemoQuestionBank/v2
mirror.demo/DemoQuestionPair/v2
mirror.demo/D02QuestionBankDimensionManifest/v1
mirror.demo/D02QuestionPairQAPayload/v2
```

### Complete upgraded envelope contracts

All objects below use exact-key validation: a missing, renamed or extra key fails closed. Objects described without an
internal `schema_version` rely on their digest domain for version authority. Arrays retain the declared order.

`D02RawMeasurementAuthority/v2` has exactly:

```text
measurement_version
decimal_serialization_version
source_p2_candidate_manifest_content_digest
dimension_authority_manifest_content_digest
measurement_config_digest
measurement_quality_config_digest
measurement_quality_manifest_content_digest
confidence_kind
reliability_kind
runtime_manifest_digest
vision_model_manifest_digest
topology_digest
source_repeat_certification_digest
ordered_entries
```

Each Raw entry has exactly:

```text
dimension_key
support_state
raw_value_fixed18
raw_confidence_fixed18
raw_reliability_fixed18
unsupported_reason
```

The six entries are ordered `cheekbone_width, chin_height, eye_spacing, jaw_width, mouth_width, nose_width`.

```text
raw_measurement_authority_digest =
  mirror_demo_digest(
    "mirror.demo/D02RawMeasurementAuthority/v2",
    complete RawMeasurementAuthority object
  )
```

`D02MorphologyProjection/v2` has exactly:

```text
measurement_version
measurement_projection_version
measurement_quantization_version
source_p2_candidate_manifest_content_digest
dimension_authority_manifest_content_digest
measurement_config_digest
measurement_quality_config_digest
measurement_quality_manifest_content_digest
confidence_kind
reliability_kind
runtime_manifest_digest
vision_model_manifest_digest
topology_digest
source_repeat_certification_digest
ordered_entries
```

Each projection entry has exactly:

```text
dimension_key
support_state
value_ppm
unit
confidence_ppm
reliability_ppm
unsupported_reason
```

`value_ppm`, `confidence_ppm` and `reliability_ppm` are the `ROUND_HALF_EVEN` projections of the corresponding Raw v2
fixed18 values; `unit` is `FACE_HEIGHT_PPM`.

```text
source_measurement_projection_digest =
  mirror_demo_digest(
    "mirror.demo/D02MorphologyProjection/v2",
    complete MorphologyProjection object
  )
```

`RecoveredSyntheticIdentityFacts/v3` has exactly the 23 v2 keys plus four new observation/certificate keys, for 27
keys total:

```text
source_output_id
source_asset_sha256
source_asset_byte_size
source_asset_mime_type
source_asset_width
source_asset_height
source_receipt_digest
source_authority_digest
qa_policy_digest
source_qa_snapshot_digest
source_landmark_digest
source_measurement_digest
source_provenance_digest
source_measurement_projection
source_measurement_projection_digest
raw_measurement_authority
raw_measurement_authority_digest
adult_synthetic_attested
original_formal_identity_id_status
measurement_projection_version
measurement_quantization_version
source_p2_candidate_manifest_content_digest
dimension_authority_manifest_content_digest
source_measurement_observation
source_measurement_observation_digest
source_repeat_certification
source_repeat_certification_digest
```

The only v3 meaning of `source_measurement_digest` is
`source_measurement_digest == source_measurement_observation_digest`. It must not equal or alias
`raw_measurement_authority_digest`.

```text
source_fact_snapshot_digest =
  mirror_demo_digest(
    "mirror.demo/RecoveredSyntheticIdentityFacts/v3",
    complete facts object
  )
```

`DemoSyntheticIdentity/v3` retains the existing physical columns and the existing 26-key canonical projection. Its
physical row has exactly:

```text
id
schema_version
canonical_payload
content_digest
created_at
formal_synthetic_identity_id
formal_canonical_asset_id
formal_canonical_asset_sha256
formal_accepted_qa_run_id
formal_accepted_qa_snapshot_digest
admission_sequence
admission_action
admission_config_digest
supersedes_id
source_output_id
source_receipt_digest
source_authority_digest
source_qa_snapshot_digest
source_landmark_digest
source_measurement_digest
source_provenance_digest
source_fact_snapshot
source_fact_snapshot_digest
source_measurement_projection
source_measurement_projection_digest
original_formal_identity_id_status
adult_synthetic_attested
importer_version
import_config_digest
source_authority_kind
source_authority_key
```

Its canonical payload is the same list excluding `id`, `schema_version`, `canonical_payload`, `content_digest` and
`created_at`.

```text
content_digest =
  mirror_demo_digest(
    "mirror.demo/DemoSyntheticIdentity/v3",
    canonical_payload
  )

id = first_32_hex(
  mirror_demo_digest(
    "mirror.demo/DemoSyntheticIdentityAdmissionEventId/v2",
    {
      source_authority_kind,
      source_authority_key,
      admission_sequence,
      admission_action,
      supersedes_id,
      admission_config_digest,
      canonical_payload_digest: content_digest
    }
  )
)
```

Every new local ADMIT/REVOKE uses `demo-d02-identity-importer-v3`, the accepted v3 import-config digest,
`RecoveredSyntheticIdentityFacts/v3` and `D02MorphologyProjection/v2`. The existing formal/local null matrices and
ADMIT/REVOKE copy-equality rules remain mandatory.

`D02SourceAuthorityManifestEntry/v3` has exactly 38 keys:

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
measurement_config_digest
measurement_quality_config_digest
measurement_quality_manifest_content_digest
confidence_kind
reliability_kind
runtime_manifest_digest
vision_model_manifest_digest
topology_digest
source_repeat_certification_digest
import_config_digest
ordered_supported_measurements
record_digest
```

No second `source_measurement_observation_digest` alias is added: the existing `source_measurement_digest` is the
observation digest. Each ordered supported measurement retains exactly:

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

```text
record_digest =
  mirror_demo_digest(
    "mirror.demo/D02SourceAuthorityManifestEntry/v3",
    entry excluding schema_version and record_digest
  )

source_manifest_digest =
  mirror_demo_digest(
    "mirror.demo/D02SourceAuthorityManifest/v1",
    four ordered v3 entries
  )
```

The source manifest contains no SourceM3 record ID or digest.

`D02SourceM3RepeatRecord/v2` and `D02ResultM3RepeatRecord/v2` have the exact key sets frozen earlier in this change
control. Their record digests are:

```text
record_digest =
  mirror_demo_digest(
    record.schema_version,
    record excluding schema_version and record_digest
  )
```

The unchanged SourceM3 ID is created only after `source_manifest_digest` exists:

```text
source_m3_record_id = first_32_hex(
  mirror_demo_digest(
    "mirror.demo/D02SourceM3RecordId/v1",
    {
      source_manifest_digest,
      source_authority_key,
      source_admission_event_id,
      source_asset_id,
      source_asset_sha256,
      repeat_index,
      vision_model_manifest_digest,
      runtime_manifest_digest,
      topology_digest
    }
  )
)
```

The unchanged ResultM3 ID is acyclic:

```text
result_m3_record_id = first_32_hex(
  mirror_demo_digest(
    "mirror.demo/D02ResultM3RecordId/v1",
    {
      case_id,
      case_specification_digest,
      result_output_id,
      result_sha256,
      repeat_index,
      vision_model_manifest_digest,
      runtime_manifest_digest,
      topology_digest
    }
  )
)
```

`D02MeasurementGateRecord/v4` has exactly:

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
result_repeat_certification
result_repeat_certification_digest
record_digest
```

Source target/control measurements retain exactly:

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

A supported result measurement retains exactly:

```text
schema_version
repeat_index
result_m3_record_digest
raw_result_target_fixed18
raw_signed_target_delta_fixed18
raw_target_absolute_delta_fixed18
ordered_control_deltas
winning_control_ordinal
max_control_dimension_key
raw_max_control_drift_fixed18
measured_signed_delta_ppm
target_absolute_delta_ppm
drift_ppm
direction_gate_passed
target_min_gate_passed
target_max_gate_passed
control_drift_gate_passed
```

An unsupported result measurement retains exactly:

```text
schema_version
repeat_index
result_m3_record_digest
unsupported_dimension_key
unsupported_reason
measurement_gate_passed
```

Each result measurement links its `result_m3_record_digest` to one v2 record. Its raw target/control values must be the
projection of that record's embedded observation, and the observation digest must equal both the record field and the
corresponding result-certificate binding. No second observation authority is permitted.

`D02PairScreeningReport/v2.report_payload` retains exactly 16 top-level groups:

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

The upgraded projections are `D02SchemaAndPolicyBinding/v2`, ordered
`D02SourceAuthorityManifestEntry/v3[]`, `D02SourceM3RepeatRecord/v2[]`,
`D02ResultM3RepeatRecord/v2[]` and `D02MeasurementGateRecord/v4[]`. All other Revision 9 nested schemas,
cardinalities and orderings remain unchanged. `report_payload` must not contain `report_digest` or `report_id`; both
are constructed only after the complete 16-group payload exists.

The report physical row has exactly:

```text
id
schema_version
canonical_payload
content_digest
created_at
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
report_payload
report_digest
status
source_count
case_count
source_m3_repeat_count
m4_execution_count
result_m3_repeat_count
manual_decision_count
exact_sha_record_count
phash_comparison_count
candidate_pair_count
selected_pair_count
selected_result_side_count
eligible_dimension_keys
selected_dimension_keys
selected_pair_manifest_digest
```

The canonical payload is this structured row excluding `id`, `schema_version`, `canonical_payload`, `content_digest`
and `created_at`; `FAILED` additionally excludes nullable `selected_pair_manifest_digest`, while `PASSED` must include
it.

```text
report_digest =
  mirror_demo_digest(
    "mirror.demo/D02PairScreeningReport/v2",
    complete report_payload
  )

id = first_32_hex(
  mirror_demo_digest(
    "mirror.demo/D02PairScreeningReportId/v1",
    {"report_digest": report_digest}
  )
)

content_digest =
  mirror_demo_digest(
    "mirror.demo/D02PairScreeningReport/v2",
    canonical_payload
  )
```

`report_digest` covers the 16-group evidence payload; `content_digest` covers the structured row projection. They are
distinct authorities.

### Configuration digests and constructive DAG

```text
measurement_config_digest =
  mirror_demo_digest(
    "mirror.demo/D02MeasurementExecutionConfig/v1",
    measurement_execution_config excluding schema_version
  )

import_config_digest =
  mirror_demo_digest(
    "mirror.demo/D02IdentityImportConfiguration/v3",
    identity_import_config excluding schema_version
  )
```

`measurement_execution_config` binds its exact measurement, Decimal, projection, quantization, confidence,
reliability, unsupported/stop-policy, source/dimension/ontology, runtime/model/topology and observation/certificate/M3
and Gate version fields. `identity_import_config` additionally binds importer v3 and the identity/facts/raw/projection
source-authority versions in its exact preimage. The peer manifest content digest binds the complete envelope matrix,
including SourceManifestEntry v3, SchemaAndPolicyBinding v2 and PairScreeningReport v2.
`DemoSyntheticIdentity/v3.import_config_digest` must equal the accepted peer-manifest `import_config_digest`.
`measurement_quality_manifest_content_digest` is absent from both config preimages to avoid a digest cycle; every
persisted observation, certificate, raw authority, projection, facts snapshot and Report binding carries it separately.

The source authority is constructible in exactly this order:

```text
runtime/model/topology/policy roots
-> D02MeasurementQualityConfig/v1
-> D02MeasurementExecutionConfig/v1 / measurement_config_digest
-> D02IdentityImportConfiguration/v3 / import_config_digest
-> D02MeasurementQualityAuthorityManifest/v1
-> three D02MeasurementObservation/v1 values
-> D02SourceRepeatDeterminismCertification/v1 over pre-admission semantic tuples
-> D02RawMeasurementAuthority/v2
-> D02MorphologyProjection/v2
-> RecoveredSyntheticIdentityFacts/v3
-> DemoSyntheticIdentity/v3 content_digest
-> admission event ID
-> D02SourceAuthorityManifestEntry/v3
-> source_manifest_digest
-> D02SourceM3RecordId/v1
-> D02SourceM3RepeatRecord/v2 record_digest
-> D02PairScreeningReport/v2
```

This graph is acyclic because the certificate contains no identity, manifest, SourceM3 or Report authority; the only
SourceM3 ID that depends on the source manifest is constructed after that manifest. The post-admission record is linked
back to the certificate only by exact semantic equality, never by a certificate dependency on the record ID.

The result/report graph is:

```text
source_manifest_digest + case specification
-> M4 result_output_id/result_sha256
-> three D02MeasurementObservation/v1 values
-> D02ResultM3RecordId/v1
-> D02ResultM3RepeatRecord/v2 record_digest
-> D02ResultRepeatDeterminismCertification/v1
-> D02MeasurementGateRecord/v4
-> D02PairScreeningReport/v2 report_digest
-> Report ID and canonical row content_digest
-> DemoQuestionBank/v2 and DemoQuestionPair/v2 screening_report_digest
```

ResultM3 IDs do not depend on the certificate, Gate or Report. Runtime, model, topology, algorithm, config, anchor
order or kind-token mutation must change the corresponding digest and be rejected by PostgreSQL. Locator, path, raw
landmark, image byte, wall clock, binary float and unordered set are never digest inputs.

### Version transition matrix

| Authority             | Legacy         | Candidate 3 new writes | Mixing                                       |
| --------------------- | -------------- | ---------------------- | -------------------------------------------- |
| Raw measurement       | v1             | v2                     | forbidden                                    |
| Morphology projection | v1             | v2                     | forbidden                                    |
| Recovered facts       | v2             | v3                     | forbidden                                    |
| Demo local identity   | v2/importer v2 | v3/importer v3         | new local ADMIT/REVOKE must be v3            |
| Source manifest entry | v2             | v3                     | forbidden inside one report graph            |
| Source M3 repeat      | v1             | v2                     | forbidden                                    |
| Result M3 repeat      | v1             | v2                     | forbidden                                    |
| Measurement Gate      | v3             | v4                     | forbidden                                    |
| Schema/policy binding | v1             | v2                     | forbidden                                    |
| Pair screening report | v1             | v2                     | v1 immutable; new writes v2 only             |
| Report ID             | Id/v1          | Id/v1                  | preimage remains the versioned report digest |

All legacy rows remain byte-identical and read-only. A new local import must contain one complete v3/v2/v4 graph;
partial upgrades and cross-version references fail closed. Populated new-version authority makes downgrade fail closed.

### Row and JSON equality matrix

| Layer                    | Mandatory equality                                                                                                    |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| Identity row ↔ Asset    | Asset ID equals source manifest; SHA/size/MIME/width/height equal facts and source manifest.                          |
| Identity row ↔ facts    | output, receipt, authority, QA, landmark, measurement, provenance, projection and digests equal field by field.       |
| Candidate 3 measurement  | `row.source_measurement_digest == facts.source_measurement_observation_digest`.                                       |
| Raw authority            | `facts.raw_measurement_authority_digest == digest(raw v2)` and does not equal the row measurement digest by alias.    |
| Projection               | row/facts projection objects and digests equal `digest(projection v2)`.                                               |
| Facts                    | `row.source_fact_snapshot_digest == digest(facts v3)`.                                                                |
| Observation              | subject Asset/output and landmark/config/runtime/model/topology fields equal the row and accepted manifest.           |
| Source certificate       | subject equals observation; all three pre-admission semantic tuples equal execution evidence.                         |
| Raw/projection           | config, manifest, kind, runtime/model/topology and certificate digest fields agree.                                   |
| Identity config          | row `import_config_digest` equals the accepted peer-manifest digest.                                                  |
| Source entry ↔ identity | event/content/authority/Asset/facts/raw/projection/certificate/config fields agree.                                   |
| Source entry measurement | existing `source_measurement_digest` equals the observation digest; raw digest remains separate.                      |
| Source M3                | post-admission ID preimage is valid; embedded observation and all shared fields equal the matching certificate tuple. |
| Result M3                | case/result subject, embedded observation and record digest agree.                                                    |
| Result certificate       | record ID and semantic tuple equal each corresponding ResultM3 v2 record.                                             |
| Measurement Gate         | result record digests, result certificate and observation-derived value projections agree.                            |
| Report binding           | v2 binding equals structured columns, accepted manifest and every nested authority.                                   |
| Report payload           | exact 16 groups, counts/status/dimension projections and `report_digest` agree.                                       |
| Report canonical row     | canonical projection and `content_digest` agree; FAILED excludes only nullable selected-manifest digest.              |
| Formal/local null matrix | Existing formal/local exclusivity remains exact; local v3 fields are all present and formal-only fields are null.     |
| ADMIT/REVOKE             | v3 facts, projection, config and authority fields are copied byte-identically.                                        |

## PostgreSQL and migration decision

```text
NO_SCHEMA_CHANGE: REJECTED
FORWARD_PROTOTYPE_MIGRATION_REQUIRED: YES
NEW_TABLE_REQUIRED: NO
NEW_COLUMN_REQUIRED: NO
FORMAL_TABLE_CHANGE: NO
PUBLIC_API_CHANGE: NO
```

Revision 9 JSONB payloads are exact-key authorities. Existing validators hard-code RawMeasurementAuthority v1,
MorphologyProjection v1, RecoveredSyntheticIdentityFacts v2, DemoSyntheticIdentity v2,
D02SchemaAndPolicyBinding v1, D02PairScreeningReport v1 and importer v2. `import_config_digest` proves only a lowercase
SHA-256 shape; PostgreSQL cannot recover its preimage or prove the quality producer. A tracked manifest plus that field
would be an application-only assertion and is rejected.

`mirror.demo/D02MeasurementExecutionConfig/v1` has exactly:

```text
schema_version
measurement_algorithm_version
decimal_serialization_version
measurement_projection_version
measurement_quantization_version
confidence_algorithm_version
confidence_kind
reliability_algorithm_version
reliability_kind
coordinate_system
decimal_precision
rounding
repeat_count
required_face_count
required_landmark_count
supported_raw_min_fixed18
supported_ppm_min
supported_ppm_max
unsupported_reason_precedence
unsupported_projection_policy_version
source_repeat_failure_policy_version
result_repeat_failure_policy_version
source_p2_candidate_manifest_content_digest
dimension_authority_manifest_content_digest
geometry_ontology_version_digest
measurement_quality_config_digest
d02_execution_runtime_set_digest
vision_model_manifest_digest
topology_digest
measurement_observation_schema_version
source_repeat_certification_schema_version
result_repeat_certification_schema_version
source_m3_repeat_record_schema_version
result_m3_repeat_record_schema_version
measurement_gate_record_schema_version
```

The peer-manifest object is the only accepted preimage for structured Report column `measurement_config_digest`.
`mirror.demo/D02IdentityImportConfiguration/v3` has exactly:

```text
schema_version
importer_version
identity_schema_version
source_fact_schema_version
raw_measurement_authority_schema_version
morphology_projection_schema_version
measurement_observation_schema_version
source_repeat_certification_schema_version
measurement_config_digest
measurement_quality_config_digest
d02_execution_runtime_set_digest
vision_model_manifest_digest
topology_digest
source_p2_candidate_manifest_content_digest
dimension_authority_manifest_content_digest
```

Its domain-separated digest is the sole accepted `DemoSyntheticIdentity/v3.import_config_digest`. Thus the row-level
producer/config authority cannot diverge from the inner facts, observation, certificate, raw authority or projection.

`mirror.demo/D02SchemaAndPolicyBinding/v2` has exactly:

```text
schema_version
source_manifest_digest
case_manifest_digest
screening_policy_digest
runtime_manifest_digest
vision_model_manifest_digest
topology_digest
measurement_execution_config
measurement_config_digest
measurement_quality_config_digest
measurement_quality_manifest_content_digest
confidence_kind
reliability_kind
manual_review_policy_digest
duplicate_policy_digest
phash_implementation_digest
```

PostgreSQL must recompute and prove all of:

```text
digest(binding.measurement_execution_config)
  = binding.measurement_config_digest
  = demo_pair_screening_reports.measurement_config_digest
  = accepted peer-manifest measurement_config_digest

binding.measurement_execution_config
  = accepted peer-manifest measurement_execution_config

binding.measurement_quality_config_digest
  = accepted peer-manifest measurement_quality_config_digest

binding.measurement_quality_manifest_content_digest
  = accepted peer-manifest manifest_content_digest

binding runtime/model/topology digests
  = measurement execution config values
  = structured report columns

binding confidence/reliability kinds
  = measurement execution config kinds
  = peer-manifest kinds
```

Observations, certificates, RawMeasurementAuthority v2, MorphologyProjection v2 and every enclosing facts/report digest
must carry the same values. PostgreSQL validation order is observation payload/digest, repeat record, certificate,
raw/projection or result measurement Gate, facts/report binding, enclosing canonical/content digest. It may not accept a
digest-only placeholder at any layer.

The Central Migration Owner shall allocate the next actual Demo revision after `demo_0003_d02_import_auth`. The
candidate name is:

```text
MODULE: demo_0004_d02_measurement_quality_authority.py
REVISION: demo_0004_d02_quality_auth
REVISION_LENGTH: 26
DOWN_REVISION: demo_0003_d02_import_auth
PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
```

No D03 migration reservation survives this forward change; D03 receives the next available Demo revision only after
D02 is accepted. The migration adds no table or column. It replaces only Demo validation functions, triggers and
constraints needed to accept the frozen v3/v2/v4 authority matrix and reject version/digest/kind mismatches. Legacy rows remain
byte-identical. After upgrade, every new Demo-local identity import must use v3 authority. Populated v3 authority makes
downgrade fail closed.

Migration validation must prove:

```text
fresh -> quality head
demo_0003 -> quality head
quality head -> demo_0003 on a database with no new-version authority
demo_0003 -> quality head
populated v3 downgrade -> FAIL_CLOSED
alembic check
schema drift = 0
single head
formal non-Demo DDL unchanged
```

## Mandatory implementation validation

Algorithm/canonical tests:

```text
GEOMETRIC_OBSERVABILITY_CENTER_REFERENCE
GEOMETRIC_OBSERVABILITY_BOUNDARY_MONOTONICITY
GEOMETRIC_OBSERVABILITY_REQUIRED_ANCHOR_SET
MISSING_NONFINITE_OUT_OF_RANGE_FAILS_CLOSED
FIXED18_HALF_EVEN_REFERENCE
PPM_HALF_EVEN_REFERENCE
NEGATIVE_ZERO_NORMALIZED
NO_BINARY_FLOAT_CANONICAL_AUTHORITY
DIFFERENT_GEOMETRY_CHANGES_CONFIDENCE
NO_MODEL_CONFIDENCE_CLAIM
NO_SENSITIVE_INPUT_FIELD
MEASUREMENT_OBSERVATION_EXACT_KEYS_AND_DIGEST
OBSERVATION_DIGEST_EXCLUDES_REPEAT_LOCAL_FIELDS
SUPPORTED_AND_UNSUPPORTED_OBSERVATION_UNIONS
MEASUREMENT_CONFIG_DIGEST_REPLAY
IMPORT_CONFIG_DIGEST_REPLAY
THREE_REPEAT_EXACT_DIGEST_CERTIFICATION
SOURCE_AND_RESULT_CERTIFICATE_PREIMAGE
GROUP_CERTIFICATE_VS_DIMENSION_UNSUPPORTED_SEMANTICS
ANY_SOURCE_REPEAT_DIGEST_MISMATCH_STOPS_BEFORE_M4
ANY_RESULT_REPEAT_DIGEST_MISMATCH_STOPS_REPORT
STRUCTURAL_PRECONDITION_FAILURE_CREATES_NO_CERTIFICATE
DETERMINISTIC_REPLAY_BYTE_IDENTICAL
```

PostgreSQL adversarial tests:

```text
VALID_V3_IDENTITY_AND_REPORT_V2_ACCEPTED
OBSERVATION_PAYLOAD_REQUIRED_NOT_DIGEST_ONLY
SOURCE_REPEAT_V2_REPLACES_AMBIGUOUS_MEASUREMENT_DIGEST
RESULT_REPEAT_V2_OBSERVATION_CROSS_LINK_ENFORCED
RESULT_CERTIFICATE_GATE_V4_CROSS_LINK_ENFORCED
MISSING_OR_WRONG_QUALITY_MANIFEST_DIGEST_REJECTED
MEASUREMENT_CONFIG_PREIMAGE_OR_COLUMN_MISMATCH_REJECTED
IMPORT_CONFIG_PREIMAGE_OR_ROW_MISMATCH_REJECTED
SCHEMA_AND_POLICY_BINDING_V2_EXACT_KEYS_ENFORCED
WRONG_CONFIDENCE_OR_RELIABILITY_KIND_REJECTED
RAW_PROJECTION_PPM_MISMATCH_REJECTED
RUNTIME_MODEL_TOPOLOGY_CONFIG_MUTATION_REJECTED
REPEAT_COUNT_ORDER_OR_DIGEST_MISMATCH_REJECTED
RELIABILITY_ONE_WITHOUT_EXACT_REPEAT_EQUALITY_REJECTED
SUPPORTED_CONFIDENCE_BELOW_FLOOR_REJECTED
UNSUPPORTED_NULL_ZERO_SHAPE_ENFORCED
UNSUPPORTED_CERTIFIED_RESULT_PRESERVES_CARDINALITY_AND_FAILS_REPORT
PRECONDITION_FAILURE_OR_REPEAT_MISMATCH_CREATES_NO_REPORT
REPORT_SOURCE_CERTIFICATION_CROSS_LINK_ENFORCED
LEGACY_ROWS_BYTE_IDENTICAL
NEW_IMPORT_REQUIRES_V3
CONCURRENT_SAME_PAYLOAD_ONE_CANONICAL_WINNER
POPULATED_V3_DOWNGRADE_FAILS_CLOSED
ALEMBIC_REVISION_ID_LENGTH_AT_MOST_32
```

Candidate 3 cycle, envelope and equality tests are additionally mandatory:

```text
SOURCE_CERTIFICATE_EXACT_KEYS_NO_POST_ADMISSION_ID
SOURCE_CERTIFICATE_FORBIDS_SOURCE_M3_RECORD_ID
SOURCE_CERTIFICATE_FORBIDS_RECORD_DIGEST
SOURCE_CERTIFICATE_FORBIDS_SOURCE_MANIFEST_DIGEST
SOURCE_CERTIFICATE_FORBIDS_ADMISSION_AND_FACT_DIGEST
SOURCE_CERTIFICATE_FORBIDS_SOURCE_AUTHORITY_KEY_AND_PLACEHOLDER_ID
SOURCE_DAG_CONSTRUCTIBLE_WITHOUT_PLACEHOLDER
SOURCE_M3_ID_ONLY_AFTER_SOURCE_MANIFEST
SOURCE_M3_CERTIFICATE_REPEAT_INDEX_CROSSLINK
SOURCE_M3_OBSERVATION_OBJECT_AND_DIGEST_CROSSLINK
RESULT_M3_ID_PREIMAGE_ACYCLIC
RESULT_CERTIFICATE_ONLY_REFERENCES_EXISTING_RESULT_RECORDS
RESULT_GATE_OBSERVATION_PROJECTION_CROSSLINK
RAW_V2_EXACT_KEYS_AND_DIGEST
PROJECTION_V2_EXACT_KEYS_AND_DIGEST
FACTS_V3_EXACT_KEYS_AND_DIGEST
SOURCE_MEASUREMENT_DIGEST_IS_OBSERVATION_DIGEST_NOT_RAW_DIGEST
IDENTITY_V3_CANONICAL_ROW_EQUALITY
SOURCE_MANIFEST_ENTRY_V3_EXACT_KEYS_AND_DIGEST
SOURCE_MANIFEST_ENTRY_HAS_NO_OBSERVATION_DIGEST_ALIAS
REPORT_V2_EXACT_16_GROUPS
REPORT_V2_STRUCTURED_ROW_EQUALITY
REPORT_DIGEST_VS_CONTENT_DIGEST_SEPARATION
REPORT_PAYLOAD_FORBIDS_REPORT_DIGEST_AND_REPORT_ID
NO_V1_V2_V3_V4_MIXED_GRAPH
LEGACY_ROWS_BYTE_IDENTICAL
FORMAL_LOCAL_NULL_MATRIX_UNCHANGED
ADMIT_REVOKE_V3_COPY_EQUALITY
EXACT_KEY_MISSING_EXTRA_RENAMED_FAILS_CLOSED
ORM_MIGRATION_CONTRACT_PARITY
NEW_LOCAL_IMPORT_REQUIRES_COMPLETE_V3_GRAPH
POPULATED_NEW_VERSION_DOWNGRADE_FAILS_CLOSED
```

Every negative payload must recompute all enclosing digests so the intended invariant, not a stale outer digest, causes
the rejection. Fixtures prove only structure and cannot be presented as private execution evidence.

## D03 and D04 consumption boundary

D03 SelfState may consume only explicit fields:

```text
measurement_confidence_ppm
measurement_confidence_kind
repeat_reliability_ppm
repeat_reliability_kind
self_state_reliability_ppm
```

The Demo-only composite is:

```text
self_state_reliability_ppm =
  round_half_even(measurement_confidence_ppm * repeat_reliability_ppm / 1_000_000)
```

D04 morphology-neighborhood routing may consume a value only when the quality-manifest digest and both kind tokens
match the accepted configuration and the dimension is supported. Unknown kind, missing digest or unsupported state is
not eligible. This proxy may downweight Demo routing only; it cannot become formal M3 confidence or real-face validity.

## Execution gate

Candidate 3 exact-blob review and Principal disposition are now accepted. The current bounded execution state is:

```text
PRIVATE_HANDLES: MUST_NOT_OPEN
D02_MEASUREMENT_QUALITY_PURE_ALGORITHM: OPEN_FOR_BOUNDED_IMPLEMENTATION
D02_PURE_AUTHORITY_BUILDER: OPEN_AFTER_PURE_ALGORITHM_ACCEPTANCE
D02_POSTGRESQL_MIGRATION: OPEN_AFTER_PURE_DOMAIN_ACCEPTANCE
D02_MIGRATION_REVISION: demo_0004_d02_quality_auth
D02_48_CASE_EXECUTION: NOT_STARTED
D02_PRIVATE_SCREENING: NOT_VERIFIED
D02_TASK_ACCEPTED: NO
D03: BLOCKED
```

Private execution remains closed until the pure implementations, migration lifecycle, same-SHA CI, independent
exact-SHA implementation review and exact runtime/model/topology digest preflight are accepted.

Final D02 acceptance still requires four real adult synthetic identities, 48 executed cases, complete manual QA,
two selected geometry dimensions, 16 A/B pairs, PostgreSQL import and all evidence/digest/lineage gates. This change
control does not make D02, D03, P3–P7 or production PASS.
