# P3–P7 D02 Change Control 01 — Recovered Identity Import Authority

## Decision status

```text
CHANGE_CONTROL_ID: P3_P7_D02_CC_01
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
DISCOVERED_BY: D02 independent authority review
REVISION: 7
STATUS: PENDING_INDEPENDENT_SOL_REVIEW
PRIOR_SOL_DECISION: REVISION_6_REVISE
REJECTED_REVISION_6_SHA: 8ab35f4e7d762069eb338c9e4a09a5d632c502c6
REJECTED_IMPLEMENTATION_SHA: cc56fc144d23d0b8109c1ef231b6afcfb7eb67c1
REJECTED_IMPLEMENTATION_DECISION: FAIL_REVISE_REQUIRED
D02_PRIVATE_SCREENING: CLOSED
D02_SCHEMA_IMPLEMENTATION: CLOSED
D03_D12: DEPENDENCY_GATED
FORMAL_PHASE_AUTHORITY: FALSE
PRODUCTION_RELEASE: NOT_AUTHORIZED
CURRENT_RESULT: NOT_VERIFIED
```

The D00 registry can recover the exact accepted private source bytes, Vision evidence and geometry runtime, but the
redacted handoff does not recover the original formal database row identifiers. Creating new compatibility rows in
`synthetic_identities` or `synthetic_qa_runs` would falsely present Demo-local copies as formal authority and would
violate the accepted `REFERENCE_ONLY_ADMISSION` disposition. Placeholder IDs, inferred provenance and reconstructed
attestations are forbidden.

This change control chooses a Demo-owned import snapshot instead. It preserves formal `Asset` and `AssetVariant` as the
byte and source/result-lineage authorities, while keeping recovered identity/QA/provenance facts in the existing
`demo_synthetic_identities` logical authority. No formal identity or QA row is fabricated.

## Frozen authority decision

`demo_synthetic_identities` supports exactly two mutually exclusive source modes:

```text
FORMAL_REFERENCE
DEMO_LOCAL_IMPORTED_COPY
```

### `FORMAL_REFERENCE`

- Existing exact formal `SyntheticIdentity`, canonical `Asset` and terminal accepted `SyntheticQARun` rows must already
  exist in the Demo database.
- The existing formal identity, QA run and canonical QA snapshot checks remain mandatory.
- This mode does not permit a local compatibility copy or a redacted/unknown original formal ID.

### `DEMO_LOCAL_IMPORTED_COPY`

- `formal_synthetic_identity_id`, `formal_accepted_qa_run_id` and
  `formal_accepted_qa_snapshot_digest` are null.
- `formal_canonical_asset_id` remains non-null because the imported source bytes are represented by the reused formal
  `Asset` byte authority. The field name continues to mean “formal Asset table”, not “formal SyntheticIdentity”.
- No row is inserted into `synthetic_identities`, `synthetic_qa_runs`, `synthetic_qa_measurements` or
  `synthetic_qa_review_decisions` for the recovered copy.
- The original formal row identity is exactly `UNKNOWN_REDACTED_NOT_RECOVERED`; it is never replaced with a new UUID.
- The row binds an opaque registry output ID and digests only. It never stores a locator, host path, object key, Prompt,
  private payload or secret.
- `adult_synthetic_attested` must be true and must be supported by the accepted recovered-fact snapshot. It may not be
  inferred from the image or filled with a placeholder.

The mode-specific fields added to `demo_synthetic_identities` are:

```text
source_authority_kind
source_authority_key
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
```

`source_fact_snapshot` uses `mirror.demo/RecoveredSyntheticIdentityFacts/v2`. Its canonical object contains only:

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
```

The measurement projection is the fixed ordered six-dimension projection defined below; a digest alone is not enough
for D04 rebuildability. All sizes and dimensions are positive integers. Every digest is lowercase SHA-256. The snapshot and row use
`demo-canonical-json-v1`; database wall clock, raw float and unordered collections are forbidden digest inputs.
`source_fact_snapshot_digest` is the SHA-256 of the canonical snapshot envelope and every duplicated typed value must
match the snapshot at insert time.

## Deterministic IDs, replay and collision handling

The importer version is `demo-d02-identity-importer-v2`. `DemoSyntheticIdentity.id` is an admission event ID, not a
stable source identity ID. Stable grouping is owned by the non-null generated `source_authority_key`. Both keys and IDs
use domain-separated canonical JSON envelopes; the earlier ambiguous newline concatenation is forbidden.

Replay with the same semantic payload returns the same rows. PostgreSQL unique constraints choose the only concurrent
winner. An existing derived ID with a different canonical payload or content digest is `DEMO_IMPORT_ID_COLLISION` and
fails closed; it is never overwritten or assigned an arbitrary fallback ID.

Identity import is one PostgreSQL transaction:

```text
verify task-scoped registry handoff and held source bytes
→ create-or-verify immutable source Asset
→ create-or-verify Demo-local identity authority
→ commit both or neither
```

The complete bank import is a separate all-or-nothing transaction after screening acceptance:

```text
verify accepted screening report and manual-review authority
→ require exactly two selected dimensions
→ create-or-verify only the 32 selected result Assets
→ create-or-verify only the 32 selected demo_p3_p7_geometry_v1 AssetVariants
→ create immutable DemoQuestionBank
→ create exactly 16 selected DemoQuestionPair rows
→ commit the full bank or none of it
```

All 48 canonical result bytes remain private screening evidence. The unselected third-dimension or failed-dimension
results never become formal Asset/AssetVariant rows. Fewer than two eligible dimensions creates no result Asset,
AssetVariant, bank or pair row.

No check-then-insert winner exists outside PostgreSQL. A replay validates every existing Asset SHA/size/dimensions,
AssetVariant source/result/type, Demo identity payload and pair payload before treating it as idempotent success.

## Asset and AssetVariant authority

Formal table reuse remains limited to stable byte and lineage facts:

- every source/result `Asset` is `asset_role=synthetic`, `owner_user_id=NULL`,
  `internal_purpose=synthetic_dataset`, `synthetic=true`, `deleted_at=NULL` and is bound to exact SHA-256, byte size,
  MIME type, width, height and private-object metadata;
- source Assets are `is_ai_generated=true`, `is_ai_modified=false`; selected geometry results follow the accepted M4
  derived-Asset semantics `is_ai_generated=false`, `is_ai_modified=true`;
- private bytes remain outside Git and ordinary CI artifacts; `storage_key` is never returned by Demo API;
- every selected result side has exactly one `AssetVariant` with exact type `demo_p3_p7_geometry_v1`;
- each variant binds the exact source Asset and corresponding result Asset; source and result are distinct;
- a pair's left/right `AssetVariant` references must resolve independently to the pair source and the matching left/right
  result; merely storing Asset IDs or an untyped lineage digest is insufficient.

The imported Assets and AssetVariants are reusable formal byte/lineage rows, but they do not create a formal synthetic
identity, a P2 READY dimension, a formal QuestionBank or production release authority.

## Forward prototype migration

The accepted migrations are not rewritten. Implementation, if this proposal is accepted, uses:

```text
MIGRATION_MODULE: demo_0003_d02_import_authority.py
REVISION: demo_0003_d02_import_auth
DOWN_REVISION: demo_0002_p3_p7_command_auth
PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
```

The migration changes only Demo tables/functions: it extends `demo_synthetic_identities`, adds immutable
`demo_pair_screening_reports`, and adds report bindings plus strict validation to `demo_question_banks` and
`demo_question_pairs`. It adds no column, trigger, constraint or index to a formal table. Populated downgrade fails
closed while any row uses `DEMO_LOCAL_IMPORTED_COPY`, any screening report exists, or any bank/pair uses the v2 report
contract; destructive test teardown uses an isolated disposable PostgreSQL database.

The Schema Reuse Matrix must advance to a new version that retains its historical reviewed digest and records the
identity extension, the new immutable report table, and the bank/pair report-binding extension. The five proofs must be
rerun; this proposal does not predeclare them PASS.

## API boundary

D02 implements only the already frozen `GET /api/v1/demo/identities` operation. Its semantics are:

```text
AUTHENTICATION: DemoBearerAuth required
DATA_SCOPE: global Demo corpus
ELIGIBILITY: latest row per source_authority_key is ADMIT and the source Asset is not tombstoned
ORDERING: source_authority_key ASC, identity_id ASC
IDENTITY_ID: DemoSyntheticIdentity.id
CANONICAL_ASSET_DIGEST: formal_canonical_asset_sha256
ADMISSION_STATUS: ADMITTED
PRIVATE_LOCATORS_OR_BYTES: never returned
```

The endpoint is not actor-owned corpus storage. Actor/session ownership remains mandatory for actor/session resources.
`POST /sessions` and all questionnaire run/next/response operations remain structured 501 until their owning tasks.
No OpenAPI route or response shape is added by this change control.

## Revision 3 exact authority contract

This section is normative and supersedes any conflicting earlier candidate sentence above. The prior `REVISE` remains
negative evidence; implementation is still closed.

### Stable source key and admission-event chain

`source_authority_kind` and `source_authority_key` are PostgreSQL `GENERATED ALWAYS ... STORED` values. They are not
caller authority and are immutable by construction. Neither generated expression may reference the other generated
column. `source_authority_kind` derives only from the nullable base mode columns:

```text
CASE
  WHEN formal_synthetic_identity_id IS NOT NULL THEN 'FORMAL_REFERENCE'
  ELSE 'DEMO_LOCAL_IMPORTED_COPY'
END
```

The mutually-exclusive base-column null-shape constraint remains the authority for that `CASE`. `source_authority_key`
is a 64-character lowercase SHA-256 selected by a base-column-only generated `CASE` between exactly two named scalar
helpers:

```text
mirror_demo_formal_source_authority_key(
  formal_synthetic_identity_id
)

mirror_demo_local_source_authority_key(
  source_output_id,
  formal_canonical_asset_id,
  formal_canonical_asset_sha256,
  source_receipt_digest
)
```

The migration creates both helpers before either generated column. Each helper is `LANGUAGE SQL`, `IMMUTABLE`, and
`STRICT`; each accepts only the listed scalar base columns and owns its fixed mode-specific canonical serialization.
The generated expression contains no JSON/JSONB constructor, does not call `jsonb_build_object`, and never references
`source_authority_kind` or any other generated column. The helpers serialize under `demo-canonical-json-v1` with schema
`mirror.demo/SourceAuthorityKey/v1`:

```text
FORMAL_REFERENCE payload:
  source_authority_kind
  formal_synthetic_identity_id

DEMO_LOCAL_IMPORTED_COPY payload:
  source_output_id
  formal_canonical_asset_id
  source_asset_sha256
  source_receipt_digest
```

`source_asset_sha256` above is the persisted `formal_canonical_asset_sha256` base column. Each helper includes its fixed
mode in the envelope, so formal and local sources cannot share a key. The key is classified
`INTERNAL_PSEUDONYMOUS_DERIVED_IDENTIFIER`; it is not a locator and is not returned by the API. `source_output_id` is
an opaque registry identifier with exact grammar `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`; `.`, `..`, whitespace,
newlines, slash, backslash, colon, URI schemes, drive prefixes and percent-encoding are forbidden.

The only grouping and lock key is `source_authority_key`:

```text
UNIQUE(source_authority_key, admission_sequence)
ADVISORY_LOCK_KEY: hashtextextended('mirror.demo.synthetic-admission-v2/' || source_authority_key, 0)
LATEST_ROW_PARTITION: source_authority_key
```

`DemoSyntheticIdentity.id` is the immutable admission event ID. New v2 IDs are the first 32 lowercase hex characters
of SHA-256 over `mirror.demo/DemoSyntheticIdentityAdmissionEventId/v2` and this canonical payload:

```text
source_authority_kind
source_authority_key
admission_sequence
admission_action
supersedes_id
admission_config_digest
canonical_payload_digest
```

Every other D02-created ID uses the same first-32-hex rule with a distinct schema and complete semantic payload:

```text
mirror.demo/D02ImportedAssetId/v1:
  asset_role, semantic_role(SOURCE|SELECTED_RESULT), sha256, byte_size, mime_type, width, height

mirror.demo/D02AssetVariantId/v1:
  exact variant_type, source_asset_id/sha256, result_asset_id/sha256, case_specification_digest

mirror.demo/D02PairScreeningReportId/v1:
  report_digest

mirror.demo/D02QuestionBankId/v1:
  screening_report_id/screening_report_digest, selected_pair_manifest_digest, algorithm_config_digest

mirror.demo/D02QuestionPairId/v1:
  question_bank_id, pair_screening_record_digest, source_admission_event_id, dimension_key, magnitude_ppm
```

No raw concatenation, newline convention, UUID fallback or caller-selected collision suffix is allowed.

Sequence 1 is `ADMIT` with `supersedes_id=null`. Every later event has sequence `previous + 1`, supersedes exactly the
immediately previous event, keeps the same key and kind, and alternates `ADMIT -> REVOKE -> ADMIT`. PostgreSQL validates
the derived ID, one-winner uniqueness and the entire chain under the source-key advisory lock. A formal chain can never
supersede a local chain. For a local chain, `source_output_id`, `formal_canonical_asset_id`,
`formal_canonical_asset_sha256`, and `source_receipt_digest` are immutable across all events. A changed input derives a
new source-authority key and starts a new chain; it cannot supersede an event in the old chain. Local `REVOKE` copies the
complete prior recovered snapshot and measurement projection. Local re-admission may use a new config and recovered
snapshot only when the same source Asset is live and all Revision 5 admission checks pass.

### Mode-specific null and authority shape

`NN` means non-null; `NULL` means database-enforced null. The formal Asset columns remain named `formal_*` only because
they reference the formal Asset table; they do not imply a formal SyntheticIdentity for local mode.

| Column                                                       | `FORMAL_REFERENCE`                 | `DEMO_LOCAL_IMPORTED_COPY`             |
| ------------------------------------------------------------ | ---------------------------------- | -------------------------------------- |
| `source_authority_kind`                                      | generated exact kind               | generated exact kind                   |
| `source_authority_key`                                       | NN generated digest                | NN generated digest                    |
| `formal_synthetic_identity_id`                               | NN                                 | NULL                                   |
| `formal_canonical_asset_id` / SHA                            | NN / NN                            | NN / NN                                |
| `formal_accepted_qa_run_id`                                  | NN                                 | NULL                                   |
| `formal_accepted_qa_snapshot_digest`                         | NN                                 | NULL                                   |
| `source_output_id`                                           | NULL                               | NN                                     |
| receipt/authority/QA/landmark/measurement/provenance digests | all NULL                           | all NN                                 |
| `source_fact_snapshot` / digest                              | NULL / NULL                        | NN / NN                                |
| `source_measurement_projection` / digest                     | NULL / NULL                        | NN / NN                                |
| `original_formal_identity_id_status`                         | NULL                               | exact `UNKNOWN_REDACTED_NOT_RECOVERED` |
| `adult_synthetic_attested`                                   | NULL; verified from live formal QA | exact `true`                           |
| `importer_version` / `import_config_digest`                  | NULL / NULL                        | NN / NN                                |

Both modes keep the existing common admission sequence/action/config/supersedes, canonical payload and content digest
columns non-null. Formal `ADMIT` validates the live formal SyntheticIdentity, live canonical Asset and terminal accepted
formal QA chain. Local `ADMIT` validates the live source Asset, exact recovered-fact snapshots and adult attestation but
must not query, create or imply formal SyntheticIdentity/QA authority. A local `REVOKE` does not require the Asset to be
live, but it must copy the prior snapshot byte-for-byte.

Eligibility is fail closed:

```text
latest event per source_authority_key is ADMIT
AND referenced source Asset.deleted_at IS NULL
```

Asset tombstone therefore removes the source immediately. A tombstoned Asset cannot be re-admitted under the same key;
a different immutable Asset is a different local source authority. Revocation remains append-only audit evidence.

### Rebuildable morphology projection

`source_measurement_projection` uses `mirror.demo/D02MorphologyProjection/v1` and contains exactly six entries in this
order:

```text
cheekbone_width
chin_height
eye_spacing
jaw_width
mouth_width
nose_width
```

Each entry contains exactly:

```text
dimension_key
support_state: SUPPORTED | UNSUPPORTED
value_ppm: integer | null
unit: FACE_HEIGHT_PPM
confidence_ppm: integer
reliability_ppm: integer
unsupported_reason: null | MISSING_MEASUREMENT | LOW_CONFIDENCE | OUT_OF_BOUNDS | RUNTIME_UNSUPPORTED
```

Before quantization, every raw fixed18 Decimal is validated: each normalized morphology value, confidence and
reliability must be in `[0, 1]`. Source eligibility requires a `SUPPORTED` entry's `value_ppm`, confidence and
reliability to each be `1..1_000_000`, with a null reason. Zero geometry maps to `OUT_OF_BOUNDS`; zero confidence or
reliability maps to `LOW_CONFIDENCE`. For `UNSUPPORTED`, value is null, confidence and reliability are zero, and reason
is non-null. A raw
out-of-range value is never clamped into `SUPPORTED`: it persists (or is rejected according to the existing null-shape
contract) as `UNSUPPORTED` with `OUT_OF_BOUNDS`. Only after raw in-range validation may a defensive clamp absorb a
quantization tail before round-half-even ppm persistence; it cannot change support classification. Binary float is
forbidden. The projection envelope
also binds `measurement_version`, `measurement_projection_version`, `measurement_quantization_version`,
`source_p2_candidate_manifest_content_digest`, `dimension_authority_manifest_content_digest` and ordered entries.
PostgreSQL enforces count, order, allowlists, integer ranges,
uniqueness and digest equality.

The full 478 landmarks and other private runtime payload stay outside this projection; only their accepted digest is
stored. D04 can rebuild morphology-neighborhood ordering from PostgreSQL without private bytes, a population default or
a sensitive label. Missing confidence/reliability authority is a hard admission blocker, not a value to infer.

### Populated v1 formal-chain compatibility

Existing populated pre-`demo_0003` `FORMAL_REFERENCE` rows, banks and pairs remain valid historical authority:

- their `canonical_payload`, `content_digest`, event ID and timestamps are never rewritten;
- generated kind/key columns derive deterministically from the existing formal identity ID without firing an authority
  mutation;
- `demo_question_banks.screening_report_id`, `screening_report_digest`, and
  `demo_question_pairs.screening_report_id`, `screening_report_digest` are nullable only when the existing
  `schema_version` is respectively `mirror.demo/DemoQuestionBank/v1` or `mirror.demo/DemoQuestionPair/v1`; no backfill
  is permitted;
- existing v1 IDs, payloads and content digests remain byte-exact;
- the post-migration insert trigger rejects all new v1 bank/pair and identity payloads; every new bank/pair uses the
  explicit `schema_version` discriminator `mirror.demo/DemoQuestionBank/v2` or
  `mirror.demo/DemoQuestionPair/v2` and a non-null accepted report binding enforced by PostgreSQL;
- downgrade is permitted only when the database contains exclusively pre-`demo_0003` v1 rows and no v2 identity,
  report, bank or pair authority;
- a populated legacy fixture must prove `demo_0002 -> demo_0003 -> demo_0002 -> demo_0003` preserves every v1 bank/pair
  ID, canonical payload, content digest and legacy byte sequence exactly, while regenerating identical generated source
  keys;
- any local row, new v2 event, report, v2 bank or v2 pair makes downgrade fail before the first DDL change.

This is an explicit compatibility projection, not silent digest migration. Existing v1 formal rows remain grouped by
their formal identity-derived key; no placeholder or inferred recovered fact is added. Downgrade preflight runs before
DDL under the migration transaction and, only when it passes, drops dependencies in this order: v2 pair FK/validation,
v2 bank FK/validation, report anti-forgery validation and table, identity v2 chain triggers/indexes/constraints,
`source_authority_key`, `source_authority_kind`, then `mirror_demo_formal_source_authority_key`,
`mirror_demo_local_source_authority_key` and the remaining v2 columns. The generated-expression catalog test must prove
that both expressions reference only base columns, both helpers exist before the generated columns, and each helper has
`pg_proc.provolatile = 'i'` plus `pg_proc.proisstrict = true`; the lifecycle test must also prove the populated legacy
re-upgrade key equality above.

### Demo-local geometry specification

Formal `VariantSpecification.source_identity_id` and `source_qa_run_id` retain their formal semantics and are not used
for `DEMO_LOCAL_IMPORTED_COPY`. D02 uses immutable private authority
`mirror.demo/D02GeometryCaseSpecification/v1` with:

```text
case_id
source_authority_key
source_admission_event_id
source_asset_id / source_asset_sha256
source_qa_snapshot_digest
source_measurement_projection_digest
source_p2_candidate_manifest_content_digest
dimension_authority_manifest_content_digest
geometry_ontology_version_digest
target_dimension / direction / magnitude_ppm / ordered_control_dimensions
warp_plan_digest
geometry_algorithm_version
runtime_manifest_digest
runtime_config_digest
output_policy_version / output_width / output_height
determinism_level
specification_digest
```

The Principal runner invokes the already accepted first-party GeometryTransform port with this specification and binds
each private execution receipt to `case_id/specification_digest`. It creates no formal VariantSpecification,
TransformRun, SyntheticIdentity or SyntheticQARun row and never supplies a placeholder formal ID. Only the 32 selected
results later receive formal `Asset` and `AssetVariant` byte/lineage rows.

### Immutable screening report and DB binding

`demo_pair_screening_reports` is a new immutable Demo evidence table, not a new product capability. Its authority schema
is `mirror.demo/D02PairScreeningReport/v1`. The inherited `schema_version` is the exact
`report_schema_version`; no second version field exists. Required columns are:

```text
id
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
report_payload JSONB
report_digest UNIQUE
status: PASSED | FAILED
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
eligible_dimension_keys JSONB
selected_dimension_keys JSONB
selected_pair_manifest_digest nullable
canonical_payload JSONB
content_digest UNIQUE
created_at audit-only
```

`report_digest` is independently recomputed as SHA-256 of the canonical envelope containing exactly
`report_schema_version` (the `schema_version` column) and canonical `report_payload`; it is never a digest of a mutable
or wall-clock value. The canonical report payload binds all 48 case records, 12 source M3 repeats, 96 M4 executions,
144 result M3 repeats, 52 uniquely keyed image-authority records, 1,326 unordered record-pair pHash comparisons,
48 manual decisions, raw
canonical Decimal Gate inputs, quantized ppm, quality components, dimension eligibility and fixed-priority selection
trace. It contains no image, landmark array, storage key, locator, path, Prompt or secret.

`canonical_payload` is the exact canonical object rebuilt from every immutable non-audit report field: all ten
manifest/config/policy digest columns listed above, `report_payload`, `report_digest`, `status`, all eleven count
columns, `eligible_dimension_keys`, `selected_dimension_keys`, and `selected_pair_manifest_digest`. It excludes
surrogate `id`, the separately supplied `schema_version`, `canonical_payload` itself, `content_digest`, audit-only
`created_at`, and any terminal audit field. The table-specific verifier rebuilds this object from the structured columns
and requires equality, so direct SQL cannot supply a divergent payload.

The shared Demo content authority is not redefined for this table:

```text
content_digest = mirror_demo_digest(schema_version, canonical_payload)
```

`schema_version` remains the existing digest-envelope argument and is not duplicated as a field inside
`canonical_payload`. No second content-projection digest algorithm, raw float, wall clock or unordered value is
canonical authority.

PostgreSQL permits a report insert only after all fixed-cardinality evidence is present. For `PASSED`, the counts are
exactly `4, 48, 12, 96, 144, 48, 52, 1326, 24, 16, 32` in the column order above, all report-global Gates pass, at least
two dimensions are eligible, exactly the first two eligible dimensions are selected, and the selected manifest is
non-null. For `FAILED`, the first nine counts are still exactly `4, 48, 12, 96, 144, 48, 52, 1326, 24`; a report-global
Gate fails or fewer than two dimensions are eligible; selected-pair and selected-result-side counts are zero, selected
dimensions are empty, and no bank may bind it. Any early stop—including public
egress, runtime/model/digest mismatch, repeat disagreement or missing source—creates no database report and imports no
result, bank or pair; it is retained only as append-only Principal private-registry negative evidence/receipt.
After source/preflight admission, an ordinary case or dimension Gate failure is recorded but does not truncate the
fixed 48-case execution; it can therefore produce only a full `FAILED` report. Only the listed early-stop boundaries
produce registry-only negative evidence.

`DemoQuestionBank.dimension_manifest` must use
`mirror.demo/D02QuestionBankDimensionManifest/v1` and bind report ID/digest, ordered selected dimensions, priority,
16-side/eight-pair Gate digest per dimension, source manifest digest and selected pair-manifest digest.

`DemoQuestionPair.qa_payload` must use `mirror.demo/D02QuestionPairQAPayload/v2`, embed the non-circular exact
`mirror.demo/D02PairScreeningRecord/v2` payload and digest, and bind that payload field-for-field to the immutable report
record. Pair/source/Asset/Variant, dimension, magnitude, delta, Gate and quality facts are projections of that payload.

`demo_0003` adds the nullable-for-v1-only bank/pair report FK and digest columns above, then PostgreSQL functions and
deferred commit-time triggers enforce the version/null matrix, report-digest equality, `PASSED` status, exactly two
selected dimensions, exactly 16 pairs, exactly 32 selected sides, no duplicate side consumption and exact match to the
report's selected manifest. Each Asset/AssetVariant field is re-read and compared. The trigger rejects direct SQL that
inserts arbitrary JSONB, mismatched report digest, an unaccepted status, a v2 null binding, or a pair whose report is not
its bank's report. Only `PASSED` may bind a bank; `FAILED` is complete negative evidence and cannot own one.

## Mandatory validation before acceptance

```text
CURRENT_RESULT_FOR_EVERY_CHECK_BELOW: NOT_VERIFIED
LISTED_VALUES: REQUIRED_OUTCOMES_ONLY
```

```text
FRESH 0014 -> demo_0001 -> demo_0002 -> demo_0003
demo_0002 -> demo_0003 -> demo_0002 -> demo_0003
POPULATED DEMO_LOCAL_IMPORTED_COPY demo_0003 -> demo_0002: FAIL_CLOSED
POPULATED V2_REPORT_OR_BANK_OR_PAIR demo_0003 -> demo_0002: FAIL_CLOSED_BEFORE_DDL
ALEMBIC_CHECK: ZERO_DRIFT
SINGLE_HEAD: demo_0003_d02_import_auth
FORMAL_NON_DEMO_DDL_DIFF: ZERO
FORMAL_SYNTHETIC_IDENTITY_ROWS_CREATED_BY_IMPORTER: 0
FORMAL_SYNTHETIC_QA_ROWS_CREATED_BY_IMPORTER: 0
SOURCE_AUTHORITY_KEY_AND_SEQUENCE: PASS
FORMAL_LOCAL_MODE_NULL_MATRIX: PASS
MORPHOLOGY_PROJECTION_REBUILD: PASS
LEGACY_V1_BANK_PAIR_0002_0003_0002_0003: BYTE_EXACT
GENERATED_EXPRESSION_BASE_COLUMNS_ONLY: PASS
SOURCE_KEY_FORMAL_HELPER_IMMUTABLE_STRICT: PASS
SOURCE_KEY_LOCAL_HELPER_IMMUTABLE_STRICT: PASS
REUPGRADE_GENERATED_SOURCE_KEYS: IDENTICAL
SELECTED_RESULT_ASSETS_CREATED: 32
UNSELECTED_RESULT_ASSETS_CREATED: 0
ASSET_VARIANT_NAMESPACE_AND_LINEAGE: PASS
SCREENING_REPORT_DIRECT_SQL_FORGERY: REJECTED
EARLY_STOP_DATABASE_REPORT_OR_IMPORT: NONE
SAME_INPUT_REPLAY: SAME_AUTHORITY
ID_COLLISION_DIFFERENT_PAYLOAD: FAIL_CLOSED
TRANSACTION_FAILURE: NO_PARTIAL_IMPORT
DIRECT_SQL_MODE_SHAPE_AND_DIGEST_ATTACKS: REJECTED
PRIVATE_LOCATOR_OR_BYTES_IN_TRACKED_DIFF: 0
```

Revision 5 was reviewed before the rejected implementation. Revision 6 now requires a new independent Sol
schema/authority review before migration remediation, ORM or importer implementation. After implementation, real
PostgreSQL lifecycle/invariant tests and a second independent review are mandatory before D02 may be accepted.

## Revision 5 closure authority

This section is normative. It supersedes every conflicting Revision 1–4 sentence and closes the independent Sol
Revision 4 findings. Migration, ORM, importer, pair-bank and private execution remain closed until an independent Sol
review returns `ACCEPT` for the exact Revision 5 document and manifest digests.

### Content-addressed dimension authority

The sole D02 measurement and routing-dimension authority is:

```text
PATH: docs/research/P3_P7_D02_DIMENSION_AUTHORITY_MANIFEST.json
SCHEMA: mirror.demo/D02DimensionAuthorityManifest/v1
SOURCE_MANIFEST_PATH: docs/research/P2_M5_CC01C_CANDIDATE_MANIFEST.json
SOURCE_MANIFEST_SCHEMA: mirror.p2-m5/CC01CCandidateManifest/v1
SOURCE_MANIFEST_CONTENT_DIGEST: eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4
GEOMETRY_ONTOLOGY_VERSION_DIGEST: d902fe2cfdf69db9f62ccc2e5fa7c569227d652f1204aa683742fc3c592f38b9
DIMENSION_AUTHORITY_MANIFEST_DIGEST: d4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a
```

The manifest freezes all six ordered projection dimensions, each meaning, formula, anchor identity/order, normalizer,
coordinate system, unit/scale/range, screening tolerances, visibility, quality, unsupported/null shape, ontology,
canonical serialization and digest. It freezes all three candidates as the mandatory screening set, zero optional
screening candidates, and a result-derived mandatory routing set of the first two fully eligible candidates in fixed
priority. An empty pre-screening realized set is not a placeholder result and cannot bind a bank.

`geometry_ontology_version_digest` is `mirror_demo_digest` over schema
`mirror.demo/D02GeometryOntology/v1` and the `geometry_ontology` object excluding its `schema_version`.
`manifest_content_digest` is `mirror_demo_digest` over schema
`mirror.demo/D02DimensionAuthorityManifest/v1` and the root object excluding `schema_version` and
`manifest_content_digest`, with the computed ontology digest present. Reordering arrays changes authority.

### Raw measurement authority and v2 identity payload

`mirror.demo/RecoveredSyntheticIdentityFacts/v2` directly stores `raw_measurement_authority`; a digest-only assertion is
forbidden. It contains exactly six entries in the manifest projection order. Each entry contains:

```text
dimension_key
support_state
raw_value_fixed18: string | null
raw_confidence_fixed18: string | null
raw_reliability_fixed18: string | null
unsupported_reason: string | null
```

Supported values are canonical nonnegative fixed18 strings in
`[0.000001000000000000,1.000000000000000000]`; signs, exponent and negative zero are forbidden. Unsupported entries
have three null raw fields and one allowlisted reason. The recovered facts
also contain `raw_measurement_authority_digest`, the manifest content digest and the existing quantized projection plus
its digest. PostgreSQL parses the fixed18 strings as exact numeric, applies `ROUND_HALF_EVEN`, rebuilds all three ppm
values and requires exact equality with `mirror.demo/D02MorphologyProjection/v1`. Binary float and caller-supplied
unverified ppm are forbidden.

`raw_measurement_authority` uses the domain-separated schema
`mirror.demo/D02RawMeasurementAuthority/v1`. Its exact payload contains only:

```text
measurement_version
decimal_serialization_version
source_p2_candidate_manifest_content_digest
dimension_authority_manifest_content_digest
ordered_entries
```

Each ordered entry has exactly `dimension_key`, `support_state`, `raw_value_fixed18`,
`raw_confidence_fixed18`, `raw_reliability_fixed18` and `unsupported_reason`. A non-null decimal must match exactly
`^(0\.[0-9]{18}|1\.000000000000000000)$`; leading sign, alternate leading zero, exponent and negative zero are
forbidden. `raw_measurement_authority_digest` is:

```text
mirror_demo_digest(
  'mirror.demo/D02RawMeasurementAuthority/v1',
  raw_measurement_authority
)
```

The digest field is outside and excluded from that payload, so the digest is non-circular. The two manifest fields are
distinct and fixed respectively to
`eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4` and
`d4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a`; the ambiguous name
`candidate_manifest_digest` is forbidden in every new v2 payload.

Every identity event inserted after `demo_0003` uses `mirror.demo/DemoSyntheticIdentity/v2`; existing v1 rows remain
byte-exact and are never rewritten. The v2 `canonical_payload` is the exact non-audit projection of:

```text
source_authority_kind / source_authority_key
formal_synthetic_identity_id
formal_canonical_asset_id / formal_canonical_asset_sha256
formal_accepted_qa_run_id / formal_accepted_qa_snapshot_digest
admission_sequence / admission_action / admission_config_digest / supersedes_id
source_output_id
source_receipt_digest / source_authority_digest / source_qa_snapshot_digest
source_landmark_digest / source_measurement_digest / source_provenance_digest
source_fact_snapshot / source_fact_snapshot_digest
source_measurement_projection / source_measurement_projection_digest
original_formal_identity_id_status / adult_synthetic_attested
importer_version / import_config_digest
```

`id`, `schema_version`, `canonical_payload`, `content_digest` and `created_at` are excluded under the shared Demo
projection rule. No `closed_at` or `tombstoned_at` column is introduced for this authority. The event ID remains
separately derived from the canonical-payload digest and the admission-chain fields.

`demo_0003` replaces the v1-only schema constraint with an exact v1/v2 allowlist and version/null matrix. It makes
`formal_synthetic_identity_id`, `formal_accepted_qa_run_id` and `formal_accepted_qa_snapshot_digest` nullable; both
foreign keys remain and
`formal_canonical_asset_id` remains non-null. All new identity/bank/pair inserts must be v2. Downgrade preflight executes
before any DDL and rejects every local/v2/report-bound row. Only after that proof may downgrade remove v2 objects, set
all three existing v1 formal fields `NOT NULL`, and restore the exact v1-only constraints, indexes and foreign keys. A populated v1
round trip must preserve IDs, canonical payloads, content digests and generated source keys byte-exactly.

### Version-aware bank and pair JSON authority

Existing `mirror.demo/DemoQuestionBank/v1` rows retain an array-valued `dimension_manifest`. New
`mirror.demo/DemoQuestionBank/v2` rows require an object-valued `dimension_manifest` with exactly:

```text
schema_version: mirror.demo/D02QuestionBankDimensionManifest/v1
screening_report_id
screening_report_digest
source_manifest_digest
source_p2_candidate_manifest_content_digest
dimension_authority_manifest_content_digest
selected_pair_manifest_digest
selected_dimensions
```

`selected_dimensions` is an ordered array of exactly two objects, each containing exactly `dimension_key`,
`priority_index`, `sixteen_side_gate_digest` and `eight_pair_gate_digest`. No nested self-digest exists; the enclosing
bank `canonical_payload` and `content_digest` are the authority. PostgreSQL replaces the v1 array-only check with a
version-aware v1-array/v2-object check and an exact-key verifier. The ORM type becomes a deliberate union of the legacy
array and v2 object rather than pretending both have one shape.

New `mirror.demo/DemoQuestionPair/v2` rows require object-valued `qa_payload` with exactly:

```text
schema_version: mirror.demo/D02QuestionPairQAPayload/v2
screening_report_id
screening_report_digest
pair_screening_record_schema_version
pair_screening_record_digest
pair_screening_record_payload
```

There is no `qa_payload_digest` inside `qa_payload`; such a field would be cyclic and is forbidden. The immutable pair
row's shared `content_digest` covers the full QA object. PostgreSQL recomputes the non-circular record digest, requires
the embedded payload to equal the report record, and then validates every pair/source/side/Asset/Variant projection.
Downgrade is allowed only after the existing preflight proves no v2 bank or pair, then restores the exact v1
array/object checks and the original ORM-visible nullability.

### Exact source-key serialization and concurrency

The insert validator derives `source_authority_key` from the nullable base columns with the accepted immutable strict
helpers before it reads the chain. It then executes exactly:

```sql
PERFORM pg_advisory_xact_lock(
  hashtextextended(
    'mirror.demo.synthetic-admission-v2/' || derived_source_authority_key,
    0
  )
);
```

Only after the transaction-scoped lock is held may it read the latest row ordered by
`admission_sequence DESC, id DESC FOR UPDATE`, validate the next event and insert. The unique
`(source_authority_key, admission_sequence)` constraint is still the final canonical-winner authority. Direct SQL and
the application importer use the same database validator; a check-then-insert application lock is not accepted.

### Exact identities API projection

`GET /api/v1/demo/identities` returns only the latest event per `source_authority_key` when that event is `ADMIT` and the
source Asset is not tombstoned. Rows are sorted by `source_authority_key ASC, id ASC`. The existing response shape maps:

```text
identity_id = latest DemoSyntheticIdentity.id
canonical_asset_digest = formal_canonical_asset_sha256
admission_status = ADMITTED
```

Re-admission therefore exposes the new latest admission-event ID. A revoked chain is absent; the existing `REVOKED`
literal remains schema compatibility only and is not emitted by this eligible-corpus list. No key, locator, storage
metadata or private byte is returned. The OpenAPI and generated TypeScript shapes remain byte-identical.

### Exact-SHA and pHash record universe

The duplicate universe is exactly 52 uniquely keyed `mirror.demo/D02ImageAuthorityRecord/v1` records: four source
records and 48 result records. Each record has a unique domain-separated `image_record_id`, authority role, source key,
optional case ID and `sha256`. Equal SHA values are retained as distinct records for negative evidence; they are not
collapsed into a set.

The exact-SHA Gate passes only when all 52 SHA values are unique and source/result sets are disjoint. If it fails after
all bytes and receipts exist, the run remains a `FULL_CARDINALITY_GATE_FAILURE`. pHash still evaluates exactly
`52 choose 2 = 1,326` unordered record pairs, ordered first by `(sha256 ASC, image_record_id ASC)` and then by the two
record ordinals. Equal-byte records therefore produce an observed Hamming distance of zero without reducing the pair
count. pHash remains observation-only and cannot select, reject or rank a dimension.

### Mutually exclusive stop taxonomy

Every run outcome belongs to exactly one class:

```text
PREFLIGHT_AUTHORITY_STOP:
  missing/unauthorized handoff, digest or size mismatch, source mutation,
  proxy/public-egress presence, runtime/model/topology/config mismatch,
  insufficient source count, unsupported source projection, nonpositive normalizer.

EXECUTION_CARDINALITY_STOP:
  missing execution receipt, fewer than prescribed executions,
  M4 replay byte/digest disagreement, no unique canonical result,
  decode failure that prevents mandatory M3/pHash evidence,
  incomplete mandatory manual review.

FULL_CARDINALITY_GATE_FAILURE:
  all prescribed evidence objects and counts exist, but a direction, magnitude,
  measurement-support, drift, result-QA, artifact, exact-duplicate or lock Gate fails.
```

The first two classes create only append-only Principal private-registry negative evidence and no database report or
import. The third class continues the fixed 48 cases and creates one immutable `FAILED` report with zero selected
dimensions/pairs/sides. A structured result observation that explicitly reports an unsupported target/control is a
full-cardinality Gate failure; a missing receipt or undecodable result preventing the fixed evidence universe is a
cardinality stop. pHash remains observation-only and never causes a Gate failure.

### Revision 5 implementation gate

```text
D02_SCHEMA_IMPLEMENTATION: CLOSED_PENDING_SOL_ACCEPT
D02_IMPORTER_IMPLEMENTATION: CLOSED_PENDING_SOL_ACCEPT
D02_PAIR_BANK_IMPLEMENTATION: CLOSED_PENDING_SOL_ACCEPT
D02_PRIVATE_SCREENING: CLOSED_PENDING_SCHEMA_AND_POSTGRES_REVIEW
```

## Network, privacy and formal boundary

```text
NETWORK_SEMANTICS: PUBLIC_INTERNET_EGRESS_DISABLED
ALL_NETWORK_DISABLED: FALSE
LOCALHOST_AND_DOCKER_INTERNAL_NETWORK: REQUIRED
D00_A_ACQUISITION_FOR_THIS_CHANGE: NOT_AUTHORIZED
PRODUCTION_PROVIDER_CALLS: 0
REAL_USER_DATA: 0
FORMAL_P3_P7_STATUS: UNCHANGED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

PostgreSQL and private object storage may use localhost/Docker internal networking. No proxy enters the importer or
screening environment. Any attempted public runtime dependency is `EXTERNAL_RUNTIME_DEPENDENCY_FOUND` and fails closed.

## Revision 6 closure contract

This section is normative and supersedes every conflicting Revision 1–5 sentence. It closes the authority gaps found by
the independent exact-SHA review of rejected implementation
`cc56fc144d23d0b8109c1ef231b6afcfb7eb67c1`. That SHA remains negative evidence; it must not be amended, integrated or
reported as accepted.

The exact nested-evidence contract is jointly owned by this change control and:

```text
PATH: docs/research/P3_P7_D02_PAIR_SCREENING_PREREGISTRATION.md
PREREGISTRATION_ID: P3_P7_D02_PAIR_SCREENING_V6
POLICY_SCHEMA: mirror.demo/D02PairScreeningPolicy/v5
TRACKED_FILE_SHA256: 2a1681ba9eedefe1a3a69be6e63bdbe76a387ab57cf4b1ce92fa9e273a337231
```

The preregistration's Revision 6 section freezes all sixteen group schemas, exact key sets, array order, cardinalities,
non-circular record and manifest digest preimages, cross-record foreign linkage, Gate derivations, selection semantics,
pair-QA content binding and private/tracked evidence boundary. A regex-valid digest or cardinality-only array is never
sufficient authority.

### Principal decisions

The following decisions are accepted for independent Sol review:

1. The complete report payload is local private PostgreSQL authority. Tracked acceptance evidence contains only the
   redacted aggregate projection listed in the preregistration.
2. `PASSED` requires all report-global Gates plus at least two eligible dimensions. A third candidate may fail without
   invalidating the first-two-eligible selection. `FAILED` is not valid when all global Gates pass and at least two
   dimensions are eligible.
3. PostgreSQL validates structure, current database facts, linkage, mathematics and digests. Principal-controlled
   receipts and manual-review custody validate that private M3/M4 execution and visual review actually occurred. No new
   signature, production attestation or formal authority is invented.
4. `mirror.demo/D02PairScreeningReport/v1` accepts only `DEMO_LOCAL_IMPORTED_COPY` sources in Revision 6. A
   `FORMAL_REFERENCE` without the same six-dimensional raw authority fails closed.

### PostgreSQL implementation authority

The `demo_0003_d02_import_authority.py` revision identifier and prototype-only table scope remain unchanged because the
rejected revision has never entered the integration branch. Remediation is a new child commit, not a history rewrite.
The migration and tests must implement the accepted Revision 6 contract before private screening can open.

The migration must use bounded validator helpers instead of treating `report_payload` as opaque JSONB. At minimum the
validation graph separately checks source entries, case entries, M3 records, M4 records, measurement records, image and
pHash records, pair records, dimension records and fixed-priority selection before the enclosing report validator
accepts a row. Every helper must:

- require the exact key set and exact `schema_version`;
- check `jsonb_typeof` before every cast;
- accept only canonical integer and fixed18 grammars, never coercing JSON strings such as `"0"` or `"true"` into typed
  authority;
- validate array ordinality, continuous indexes, natural-key uniqueness and the complete Cartesian universe;
- recompute every record, manifest, report and content digest from its frozen non-circular preimage;
- re-read the current local admission, Asset, recovered facts, pair Assets and AssetVariants where database authority
  exists;
- recompute deterministic IDs, fixed18-to-ppm values, deltas, maximum drift, quality, exact-SHA booleans, pHash Hamming
  distance, dimension eligibility, first-two selection and selected-manifest projection;
- reject raw float, JSON null, exponent, negative zero, wall clock, locator-like key or value, arbitrary nested key and
  any private path/object key/Prompt/secret field.

`PASSED + exact_sha_gate_passed=false` is always rejected. The report must validate all 52 image records, all 52 pHash
signatures and all 1,326 comparisons rather than accepting the expected count alone. A report item digest must match its
recomputed payload and every parent projection.

### Bank and pair repair requirements

For each selected dimension, `DemoQuestionBank.dimension_manifest` must copy `sixteen_side_gate_digest` and
`eight_pair_gate_digest` exactly from the same ordered `dimension_eligibility` record in its immutable report. SHA-256
syntax alone is not authority.

New pair rows continue to use `mirror.demo/DemoQuestionPair/v2`, but `qa_payload` advances to
`mirror.demo/D02QuestionPairQAPayload/v2` and contains only:

```text
schema_version
screening_report_id
screening_report_digest
pair_screening_record_schema_version
pair_screening_record_digest
pair_screening_record_payload
```

The pair-screening wrapper uses `mirror.demo/D02PairScreeningRecord/v2` with the non-circular preimage frozen by the
preregistration. PostgreSQL must find exactly one matching report wrapper, recompute its digest and require the embedded
payload to equal the report payload field-for-field. Pair columns and all source/result Asset, AssetVariant, lineage,
dimension, magnitude, delta, Gate and quality facts are derived from and compared with that payload. Digest membership
without payload equality, swapped valid digests, or a consistent digest/payload pair that disagrees with the pair row
must all fail.

### Report status and canonical payload

The report's fixed full-cardinality universe is exactly:

```text
4 sources / 48 cases / 12 source M3 / 96 M4 / 144 result M3
48 measurement / 48 decode-structure / 48 manual
52 image / 52 pHash signature / 1326 pHash comparison
24 pair / 3 dimension / 3 selection records
```

`PASSED` has exactly two selected dimensions, 16 selected pairs and 32 selected sides. `FAILED` has zero selected
dimensions/pairs/sides. For `PASSED`, `selected_pair_manifest_digest` is included in `canonical_payload`; for `FAILED`,
that key is absent and the structured column is SQL NULL. JSON null is forbidden in both variants. The shared
`content_digest` rule remains unchanged.

### Mandatory negative test matrix

The implementation is not reviewable without PostgreSQL tests that re-canonicalize every mutated fixture and prove the
database—not a stale digest—rejects all of the following:

1. a typed evidence record replaced by a 64-hex string;
2. missing/extra keys or wrong nested schema;
3. array order changed with cardinality retained;
4. broken/duplicate ordinals or one Cartesian item duplicated to hide an omission;
5. raw float, JSON null, exponent, negative zero, wall clock or locator-like key/value;
6. a wrong record digest or self-referential preimage attempt;
7. a source entry not equal to the current latest local `ADMIT`, Asset or recovered fact authority;
8. a `FORMAL_REFERENCE` source in report v1;
9. `PASSED + exact_sha_gate_passed=false`;
10. duplicate image SHA with submitted exact-SHA booleans set true;
11. missing, duplicate, reversed or mathematically wrong pHash comparisons;
12. tampered measurement delta or maximum drift with all enclosing digests recomputed;
13. manual verdict inconsistent with its four boolean criteria;
14. a valid pair digest whose embedded payload changes one field;
15. two pair digests swapped without their full payloads;
16. digest and payload swapped together while pair row/source/Assets remain inconsistent;
17. selected manifest references a failed pair, unselected dimension or wrong side Asset/Variant;
18. selection differs from the frozen first-two eligible result;
19. `PASSED` exposes fewer than two eligible dimensions, 16 pairs or 32 unique sides;
20. `FAILED` exposes a selected dimension, pair, side or manifest digest;
21. `FAILED` when global Gates pass and at least two dimensions are eligible;
22. a v2 bank or pair bound to a `FAILED` report;
23. direct report `UPDATE` or `DELETE`;
24. JSON strings substituted for integer or boolean authority in recovered identity facts or unsupported ppm fields.

One complete legal graph must pass and prove deterministic replay, populated downgrade fail-closed, lifecycle
round-trip, single head, zero Alembic drift and byte-identical non-Demo formal DDL.

### Revision 6 review and execution gate

```text
D02_REVISION_6_DOCUMENTS: PENDING_INDEPENDENT_SOL_REVIEW
D02_SCHEMA_IMPLEMENTATION: CLOSED
D02_PRIVATE_SCREENING: CLOSED
D02_RESULT: NOT_VERIFIED
D03_D12: DEPENDENCY_GATED
FORMAL_PHASE_AUTHORITY: FALSE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

Only an independent Sol acceptance of the exact two Revision 6 document blobs may reopen the bounded schema remediation.
That review does not accept the rejected implementation and does not grant `D02 TASK_ACCEPTED`.

## Revision 7 closure contract

This section is normative and supersedes every conflicting Revision 1–6 sentence. Revision 6 exact-SHA
`8ab35f4e7d762069eb338c9e4a09a5d632c502c6` remains `REVISE_REQUIRED` negative evidence. It is not amended or
reinterpreted as an accepted contract.

The exact companion authority is:

```text
PATH: docs/research/P3_P7_D02_PAIR_SCREENING_PREREGISTRATION.md
PREREGISTRATION_ID: P3_P7_D02_PAIR_SCREENING_V7
POLICY_SCHEMA: mirror.demo/D02PairScreeningPolicy/v6
TRACKED_FILE_SHA256: 5887fd5085cb495f85e11d196cd4e257db4ab60daa7214451180088eed72e92b
```

Revision 7 retains the top-level `mirror.demo/D02PairScreeningReport/v1` schema and advances only the ambiguous nested
schemas:

```text
mirror.demo/D02GeometryCaseManifestEntry/v3
mirror.demo/D02MeasurementGateRecord/v3
mirror.demo/D02PairScreeningRecord/v3
mirror.demo/D02DimensionEligibilityRecord/v3
mirror.demo/D02SelectionTraceRecord/v2
```

The preregistration's Revision 7 section is incorporated into this change control. It is the exact authority for the
canonical JSON type system, integer ranges and enum allowlists; every array element, cardinality and order; all derived
configuration/deterministic-ID/specification/digest preimages; all Gate conjunctions; the eight-state selection trace;
and the mandatory negative tests. A migration implementation that omits any such rule is out of scope and cannot be
accepted as a partial closure.

### Type and coercion boundary

PostgreSQL must validate `jsonb_typeof` before every extraction or cast. JSON strings cannot stand in for integer or
boolean authority, and JSON numbers cannot stand in for fixed18 decimal strings. Signed fixed18 authority uses the
explicit `[-1,1]` grammar and rejects negative zero. JSONB object equality uses structural comparison:

```sql
left_jsonb IS NOT DISTINCT FROM right_jsonb
```

Canonical digest recomputation separately proves deterministic serialization. The obsolete phrase “byte-equivalent
JSONB” is not an implementation requirement because PostgreSQL JSONB does not retain original input byte spelling.

### Unique derived authority

The migration must recompute, using the exact Revision 7 domains and preimages:

- `execution_config_digest`, `case_id` and `case_specification_digest`;
- source-M3, M4, result-M3, source/result image and pair record IDs;
- every generic record digest, manual/image/signature/comparison/selected-entry digest;
- automated side, sixteen-side and eight-pair Gate digests;
- the v3 pair-screening-record digest;
- source, case and selected-pair manifest digests plus report/canonical/content digests.

Caller-chosen 32-hex IDs or 64-hex aggregate values are invalid even when every enclosing digest is recomputed. The
same semantic slot with different observed payload is a collision and fails closed.

### Exact outcome and selection semantics

The sole report-global outcome Gate is `EXACT_SHA_UNIQUENESS`. pHash is observation-only. Valid local source authority,
network/runtime preflight, all fixed evidence universes, all source-M3 repeats, all M4 executions, deterministic replays,
cross-record linkage and digest validity are report-admission preconditions; they cannot be represented as a `FAILED`
outcome to bypass execution requirements.

Result-repeat, measurement, structure, automated side, manual side, pair, empty-lock and dimension Gate formulas are the
exact conjunctions in the Revision 7 preregistration. Unsupported measurement and pair-side evidence use mutually
exclusive schemas and cannot carry fabricated raw deltas or evaluated Gate booleans.

The fixed trace covers all eight jaw/chin/eye eligibility patterns. Zero or one eligible dimension produces a unique
`FAILED` trace with no selected slot; two or three eligible dimensions produce a unique `PASSED` first-two selection;
the third eligible candidate uses `ELIGIBLE_NOT_SELECTED_CAPACITY`. A false exact-SHA Gate makes all three dimensions
ineligible and maps to `000`. No `FAILED` report with two or three eligible dimensions is legal.

### Bank and pair binding

Bank Gate values remain exact projections of their selected report dimension records, but those values now use the
domain-separated sixteen-side and eight-pair aggregate preimages rather than arbitrary SHA strings.

The pair row remains `mirror.demo/DemoQuestionPair/v2` with
`mirror.demo/D02QuestionPairQAPayload/v2`. The embedded report record is now
`mirror.demo/D02PairScreeningRecord/v3`. PostgreSQL resolves exactly one record by digest, requires:

```sql
qa.pair_screening_record_payload IS NOT DISTINCT FROM
  report_record.pair_screening_record_payload
```

recomputes the v3 canonical digest, and derives every pair column and Asset/AssetVariant binding from the structural
payload. Digest membership alone remains insufficient.

### Revision 7 mandatory validation additions

In addition to the Revision 6 matrix, real PostgreSQL tests must cover every Revision 7 negative case listed in the
preregistration. Mandatory categories are:

```text
JSON scalar type/coercion and signed-fixed18 grammar
all nested array cardinality/order/natural-key universes
control-delta arithmetic and ppm derivation
all deterministic ID domains and exact preimages
case specification and execution-config completeness
automated/sixteen-side/eight-pair digest preimages
supported-versus-unsupported union exclusivity
all repeat/measurement/structure/side/pair/dimension Gate conjunctions
quality-state and ppm implications
all eight selection patterns and forbidden status projections
report-admission-precondition bypass attempts
pHash observation-only semantics
QA JSONB structural equality versus authoritative array ordering
bound-version-token equality to execution configuration and receipt authority
```

Every mutation test must recompute all enclosing digests and IDs so rejection proves the database authority rather than
a stale checksum. One complete legal graph must continue to prove deterministic replay, lifecycle round-trip, populated
downgrade fail-closed, single head, zero Alembic drift and byte-identical non-Demo formal DDL.

### Revision 7 review and execution gate

```text
D02_REVISION_6_DOCUMENTS: REVISE_REQUIRED
D02_REVISION_7_DOCUMENTS: PENDING_INDEPENDENT_SOL_REVIEW
D02_SCHEMA_IMPLEMENTATION: CLOSED
D02_PRIVATE_SCREENING: CLOSED
D02_RESULT: NOT_VERIFIED
D03_D12: DEPENDENCY_GATED
FORMAL_PHASE_AUTHORITY: FALSE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

Only an independent Sol acceptance of the exact two Revision 7 document blobs may reopen bounded schema remediation.
That review does not accept `cc56fc1`, does not execute private screening and does not grant `D02 TASK_ACCEPTED`.
