# P3–P7 D02 Change Control 05 — Recovered Legacy QA Snapshot Authority

## Decision status

```text
CHANGE_CONTROL_ID: P3_P7_D02_CC_05
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
STATUS: PRINCIPAL_ACCEPTED_FOR_BOUNDED_IMPLEMENTATION
BASE_SHA: 7f439661775c091143c98984492bd15c0b2f4a84
INDEPENDENT_SOL_REVIEW: PASS_FOR_EXACT_BLOB
IMPLEMENTATION_AUTHORIZED: YES
REVIEWED_CONTRACT_BLOB_SHA256: f2760c25f654843614a3aceb7ea9ae849216b4546cb2929db346eb3863bbe111
DISCOVERY: D02_PRIVATE_SOURCE_AUTHORITY_MAPPING
D02_PRIVATE_SCREENING: CLOSED_PENDING_CC05_IMPLEMENTATION_ACCEPTANCE
D02_TASK_ACCEPTED: NO
D03: BLOCKED
FORMAL_PHASE_AUTHORITY: FALSE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

The four D02 source assets and their accepted P2-M3 authority chains are recoverable, but the legacy authority database
is at `0011_offline_synth_source`. Its `synthetic_qa_runs` table predates the P2-M4 subject union and therefore has no
`subject_kind` or `transform_run_id` column. The current Demo function
`mirror_demo_formal_qa_snapshot_digest` requires both fields in the exact
`mirror.demo/FormalSyntheticQASnapshot/v1` preimage.

It is forbidden to fill the missing fields with `CANONICAL_BASE` and `null`, to alias the opaque P2 per-item
`authority_binding_digest`, or to use the executed-policy payload digest as the approved policy content digest. Those
choices would create a typed semantic collision or claim a replay that never occurred.

This change control defines a separate, replayable legacy snapshot authority. It preserves the existing
`DEMO_LOCAL_IMPORTED_COPY` design: formal SyntheticIdentity/QA columns remain null, no compatibility row is fabricated,
private QA payload remains outside Git, and PostgreSQL stores the domain-separated snapshot digest through the existing
facts → identity → source manifest → case → report authority graph.

## Frozen field mapping

| D02 field                   | Accepted authority                                                                                            |
| --------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `source_receipt_digest`     | Exact D00 private holdout input receipt content digest.                                                       |
| `source_authority_digest`   | The tracked P2-M3 per-item `authority_binding_digest`, treated only as an opaque source-local authority root. |
| `qa_policy_digest`          | The approved P2-M3 QA policy content digest; the executed-input payload digest is forbidden.                  |
| `source_qa_snapshot_digest` | Digest of `mirror.demo/RecoveredLegacySyntheticQASnapshot/v1` defined below.                                  |
| `source_provenance_digest`  | The matching legacy `offline_synthetic_source_admissions.admission_evidence_digest`.                          |
| `adult_synthetic_attested`  | Exact `true` from the joined legacy canonical identity and accepted QA authority.                             |

The batch-level P2 authority digest is not a per-source substitute. `source_authority_digest` is opaque and
non-recomputable from the tracked redacted document; it is not a QA snapshot digest and must never be relabelled as one.

## Recovered snapshot domain

```text
SCHEMA_VERSION: mirror.demo/RecoveredLegacySyntheticQASnapshot/v1
CANONICALIZATION: demo-canonical-json-v1
DIGEST: sha256(UTF8(SCHEMA_VERSION + LF + canonical_json(canonical_payload)))
```

The complete canonical payload has exactly these seven top-level keys:

```text
legacy_authority
source_binding
identity_authority
qa_run
qa_policy
measurements
reviews
```

### `legacy_authority`

Exact keys and values:

```text
alembic_head: 0011_offline_synth_source
source_schema_family: PRE_P2_M4_SUBJECT_UNION
subject_semantics: PRE_0012_SYNTHETIC_ASSET_RECORD_BOUND_CANONICAL_SOURCE
transform_semantics: NOT_REPRESENTED_PRE_0012
formal_snapshot_compatibility: DISTINCT_DOMAIN_NOT_FORMAL_SYNTHETIC_QA_SNAPSHOT_V1
canonicalization: demo-canonical-json-v1
```

`subject_semantics` and `transform_semantics` are explicit CC05 projection authority. They are not values inserted into
missing legacy columns and they do not alter, upgrade, or reinterpret the legacy database row.

### `source_binding`

Exact keys:

```text
source_output_id
source_asset_sha256
source_receipt_digest
source_authority_digest
source_provenance_digest
qa_policy_digest
authority_evidence_document_digest
holdout_evidence_document_digest
original_formal_identity_id_status
```

- `source_output_id` is the exact D00 registry output ID and must obey the accepted opaque-output grammar.
- `source_asset_sha256` is the exact normalized source Asset SHA-256.
- `authority_evidence_document_digest` is the verified document digest of the tracked P2-M3 authority evidence.
- `holdout_evidence_document_digest` is the verified document digest of the tracked P2-M3 holdout evidence.
- `original_formal_identity_id_status` remains exact `UNKNOWN_REDACTED_NOT_RECOVERED`; no recovered private row ID is
  promoted into the Demo formal-reference columns or tracked index.

### `identity_authority`

Exact keys:

```text
authority_kind
canonical_asset_sha256
accepted_qa_run_id
adult_synthetic_attested
synthetic_only
real_person_reference_used
```

Required values are `CANONICAL_QA`, the matching normalized Asset SHA, the private legacy accepted QA run reference,
`true`, `true`, and `false`, respectively. The QA run reference exists only in the Principal-custodied private payload;
it is not copied into `formal_accepted_qa_run_id` and is not emitted in tracked evidence or Agent handoffs.

### `qa_run`

The exact keys are the complete immutable fields available at legacy head `0011`:

```text
id
schema_version
synthetic_asset_record_id
normalized_asset_id
qa_policy_id
vision_provider_reference
vision_algorithm_reference
status
result_code
started_at
finalized_at
```

The run must be terminal `PASSED`; both authority timestamps use fixed-microsecond UTC. The ID fields remain private.
The payload deliberately has no `subject_kind` or `transform_run_id` key.

### `qa_policy`

Exact keys:

```text
id
schema_version
version
content_digest
approval_status
approved_at
```

The policy must be `APPROVED`, have a fixed-microsecond UTC approval time, and its `content_digest` must equal
`source_binding.qa_policy_digest`.

### `measurements`

Exactly nine records, ordered by `measurement_code` using C ordering. Every record has exactly:

```text
schema_version
measurement_kind
measurement_code
payload_digest
algorithm_reference
algorithm_version
confidence_scaled_1e7
hard_gate
threshold_outcome
reason_code
```

Every record must be a hard gate with `threshold_outcome=PASSED`. `confidence_scaled_1e7` is null or an integer; raw
numeric/float authority is forbidden. The ordered measurement codes must be exactly:

```text
bounded_coordinates
checksum_binding
complete_landmarks
exactly_one_face
face_occupancy
frontal_pose
platform_parity
repeatability
transformation_matrix
```

### `reviews`

Exactly six records, ordered by `review_kind` using C ordering. Every record has exactly:

```text
schema_version
review_kind
decision
reason_code
actor_reference
reviewed_at
```

All six decisions must be `PASSED`; review times use fixed-microsecond UTC. The exact review kinds are:

```text
adult_presentation
background_suitability
license_rights
license_scope
likeness_risk
text_watermark
```

The snapshot contains no image bytes, landmarks, raw measurement payload, source storage reference, locator, object key,
Prompt, provider credential, secret or real-user input.

## Recovery and replay procedure

For each of the four frozen normalized source SHA-256 values, the Principal performs one read-only legacy query and
requires exactly one complete chain:

```text
offline_synthetic_source_admission
→ source object
→ SyntheticAssetRecord
→ normalized Asset
→ PASSED SyntheticQARun
→ APPROVED QAPolicy
→ 9 PASSED hard-gate measurements
→ 6 PASSED reviews
→ CANONICAL_QA SyntheticIdentity with adult_synthetic_attested=true
```

### Exact legacy authority-chain selection and equality contract

Recovery is the intersection of three independently frozen bindings:

1. one D00 custody entry selected by exact `item_reference`;
2. one item from `P2_M3_V03_AUTHORITY_REDACTED_EVIDENCE.json` and one item from
   `P2_M3_V03_HOLDOUT_REDACTED_EVIDENCE.json`, each selected by that same `item_reference` and exact
   `normalized_sha256`;
3. one complete legacy PostgreSQL authority chain selected from `assets.sha256 = normalized_sha256`, with
   `admission.item_reference` equal to the exact `item_reference` selected in the first two bindings.

Selection by a caller-supplied private row ID is forbidden. The entire query runs in one read-only transaction against
one fixed database snapshot. For every source, each D00/tracked item and each authority node below must have cardinality
exactly one, and the final joined relation must have `COUNT(*) = 1`; no implied uniqueness of a SHA column is accepted.

The exact legacy nodes and relational equalities are:

| Authority node                                  | Mandatory condition                                                                                                                                                                                                                                                                                                           |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `offline_synthetic_source_admissions admission` | `admission.item_reference` equals the exact D00/tracked `item_reference`; `source_kind = 'CODEX_NATIVE_IMAGEGEN'`, `synthetic_only IS TRUE`, and `real_person_reference_used IS FALSE`.                                                                                                                                       |
| `synthetic_source_objects source`               | `source.schema_version = 'mirror.synthetic-dataset/SyntheticSourceObject/v2'`, `source.offline_admission_id = admission.id`, and both `source.generation_item_id` and `source.job_attempt_id` are null.                                                                                                                       |
| Raw-source byte binding                         | `source.storage_reference = admission.storage_reference`, `source.sha256 = admission.sha256`, `source.media_type = admission.media_type`, `source.byte_size = admission.byte_size`, `source.width = admission.width`, `source.height = admission.height`, and `source.retention_expires_at = admission.retention_expires_at`. |
| `synthetic_asset_records asset_record`          | `asset_record.source_object_id = source.id`, `asset_record.normalized_asset_id = normalized_asset.id`, and `asset_record.status = 'IDENTITY_REGISTERED'`.                                                                                                                                                                     |
| `assets normalized_asset`                       | `normalized_asset.sha256` equals the frozen normalized source SHA; `owner_user_id IS NULL`, `asset_role = 'synthetic'`, `internal_purpose = 'synthetic_dataset'`, `synthetic IS TRUE`, and `deleted_at IS NULL`.                                                                                                              |
| `synthetic_qa_runs qa_run`                      | `qa_run.synthetic_asset_record_id = asset_record.id`, `qa_run.normalized_asset_id = normalized_asset.id`, `qa_run.status = 'PASSED'`, `qa_run.result_code IS NULL`, and both authority timestamps are non-null.                                                                                                               |
| `synthetic_qa_policies qa_policy`               | `qa_run.qa_policy_id = qa_policy.id`, `qa_policy.approval_status = 'APPROVED'`, and `qa_policy.approved_at IS NOT NULL`.                                                                                                                                                                                                      |
| `synthetic_identities identity`                 | `identity.authority_kind = 'CANONICAL_QA'`, `identity.bank_version_id IS NULL`, `identity.canonical_asset_id = normalized_asset.id`, `identity.accepted_qa_run_id = qa_run.id`, and `identity.adult_synthetic_attested IS TRUE`.                                                                                              |
| Measurements                                    | Exactly nine rows, every `measurement.qa_run_id = qa_run.id`, one row per exact required code, every `hard_gate IS TRUE`, and every `threshold_outcome = 'PASSED'`.                                                                                                                                                           |
| Reviews                                         | Exactly six rows, every `review.qa_run_id = qa_run.id`, one row per exact required kind, and every `decision = 'PASSED'`.                                                                                                                                                                                                     |

The raw source and normalized source are different authority layers. `admission.sha256` and `source.sha256` must equal
each other, but they must not be asserted equal to `normalized_asset.sha256`; normalization is linked only by
`asset_record.normalized_asset_id = normalized_asset.id`.

The cross-document and database equalities are:

```text
source_binding.source_asset_sha256
  = identity_authority.canonical_asset_sha256
  = normalized_asset.sha256
  = authority_evidence.items[item_reference].normalized_sha256
  = holdout_evidence.items[item_reference].normalized_sha256
  = D00 custody entry normalized source SHA-256

identity_authority.accepted_qa_run_id = qa_run.id
qa_run.qa_policy_id = qa_policy.id

identity_authority.synthetic_only
  = admission.synthetic_only
  = true

identity_authority.real_person_reference_used
  = admission.real_person_reference_used
  = false

admission.item_reference
  = D00 custody entry item_reference
  = authority_evidence.items[item_reference].item_reference
  = holdout_evidence.items[item_reference].item_reference

source_binding.source_authority_digest
  = authority_evidence.items[item_reference].authority_binding_digest

source_binding.source_provenance_digest
  = admission.admission_evidence_digest

source_binding.qa_policy_digest
  = qa_policy.content_digest
  = authority_evidence.qa_policy_content_digest
  = holdout_evidence.qa_policy_content_digest
  = 8305cfaa25d084138fb67e93043a1e37842543a645085d19d3ef52ac8a6ce15f

source_binding.authority_evidence_document_digest
  = 69dc51045487ba65299785e4a1ee7780f8ae00c08684a033596f6ec7bd7b79e6

source_binding.holdout_evidence_document_digest
  = 759f651662068997933f900007b31ad0265255ee4b2654fb4e682f8059baa31c
```

All equalities, state predicates, exact measurement/review sets, and cardinalities must pass before the payload is
built. A chain assembled from nodes belonging to different QA runs or normalized Assets is invalid even when every
individual row is otherwise terminal and passed.

The Principal then:

```text
build exact canonical payload
→ compute domain-separated content digest
→ write canonical private envelope outside Git
→ compute private file SHA-256 and byte size
→ append verified Principal registry record
→ replay content digest from the registered bytes
→ publish only the redacted custody index
```

The private envelope has exactly `schema_version`, `canonical_payload`, and `content_digest`. The registry
`expected_digest` and `actual_digest` bind the envelope file bytes; they are distinct in meaning from the snapshot
`content_digest` and must not be substituted for it.

The stored private envelope and its two digest layers are exactly:

```text
snapshot_content_digest =
  sha256(UTF8(
    "mirror.demo/RecoveredLegacySyntheticQASnapshot/v1"
    + LF
    + canonical_json(canonical_payload)
  ))

stored_private_envelope = {
  "schema_version": "mirror.demo/RecoveredLegacySyntheticQASnapshot/v1",
  "canonical_payload": canonical_payload,
  "content_digest": snapshot_content_digest
}

private_snapshot_file_bytes =
  UTF8(canonical_json(stored_private_envelope))

private_snapshot_file_sha256 = sha256(private_snapshot_file_bytes)
```

`schema_version` and `content_digest` are excluded from the snapshot content-digest preimage because the schema is the
domain separator and the digest is the self field. Private file bytes use `demo-canonical-json-v1`, UTF-8 without BOM,
and no trailing LF; the file SHA-256 covers the complete stored envelope bytes.

## Redacted custody index

Git may contain one generated `mirror.demo/RecoveredLegacySyntheticQASnapshotIndex/v1` document after the four private
snapshots have been created. It has exact top-level keys:

```text
schema_version
snapshot_schema_version
legacy_authority_head
canonicalization
entries
content_digest
```

There are exactly four entries ordered by `item_reference` using C ordering. Each entry has exactly:

```text
item_reference
source_output_id
source_asset_sha256
source_receipt_digest
source_authority_digest
source_provenance_digest
qa_policy_digest
private_snapshot_output_id
private_snapshot_file_sha256
source_qa_snapshot_digest
adult_synthetic_attested
recovery_status
record_digest
```

The entry preimage is exact and has no implicit `schema_version` field:

```text
ENTRY_DOMAIN = mirror.demo/RecoveredLegacySyntheticQASnapshotIndexEntry/v1

entry_payload = {
  item_reference,
  source_output_id,
  source_asset_sha256,
  source_receipt_digest,
  source_authority_digest,
  source_provenance_digest,
  qa_policy_digest,
  private_snapshot_output_id,
  private_snapshot_file_sha256,
  source_qa_snapshot_digest,
  adult_synthetic_attested,
  recovery_status
}

record_digest =
  sha256(UTF8(ENTRY_DOMAIN + LF + canonical_json(entry_payload)))

stored_entry = entry_payload + {"record_digest": record_digest}
```

`record_digest` excludes only itself. The document preimage is separately domain-separated and exact:

```text
INDEX_DOMAIN = mirror.demo/RecoveredLegacySyntheticQASnapshotIndex/v1

document_payload = {
  snapshot_schema_version,
  legacy_authority_head,
  canonicalization,
  entries
}

content_digest =
  sha256(UTF8(INDEX_DOMAIN + LF + canonical_json(document_payload)))

stored_document = {
  "schema_version": INDEX_DOMAIN,
  ...document_payload,
  "content_digest": content_digest
}
```

The document digest excludes its stored `schema_version` because that exact value is already the domain separator, and
excludes its self field `content_digest`; it includes all four complete `stored_entry` objects, including every
`record_digest`. Entries are strictly ascending by `item_reference` using C ordering. `recovery_status` must be
`CREATED_AND_VERIFIED`.

Across the four entries, each of `item_reference`, `source_output_id`, `source_asset_sha256`,
`source_receipt_digest`, `source_authority_digest`, `source_provenance_digest`, `private_snapshot_output_id`,
`private_snapshot_file_sha256`, and `source_qa_snapshot_digest` must be unique. `qa_policy_digest` and
`adult_synthetic_attested` are intentionally not unique. Every entry must equal the corresponding private envelope's
`canonical_payload.source_binding` fields; its `source_qa_snapshot_digest` must equal that envelope's
`content_digest`; and its private output ID and file SHA-256 must equal the verified Principal registry record.

The index never contains a locator, absolute path, database row ID, actor reference, measurement/review payload, object
key, Prompt, storage reference, secret or private byte. A registry output ID is a custody reference, not a locator.

## Typed-digest separation

For a local v3 identity, `source_qa_snapshot_digest` must not equal any differently typed source authority in the same
facts graph:

```text
source_asset_sha256
source_receipt_digest
source_authority_digest
qa_policy_digest
source_landmark_digest
source_measurement_digest
source_provenance_digest
source_measurement_projection_digest
raw_measurement_authority_digest
source_measurement_observation_digest
source_repeat_certification_digest
source_p2_candidate_manifest_content_digest
dimension_authority_manifest_content_digest
source_fact_snapshot_digest
```

The exact PostgreSQL representation of that authority set is:

| Typed authority              | PostgreSQL representation                                                                                                                                                    |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Source Asset SHA             | column `formal_canonical_asset_sha256`; JSON path `source_fact_snapshot ->> 'source_asset_sha256'`                                                                           |
| Source receipt               | column `source_receipt_digest`; JSON path `source_fact_snapshot ->> 'source_receipt_digest'`                                                                                 |
| Opaque source authority      | column `source_authority_digest`; JSON path `source_fact_snapshot ->> 'source_authority_digest'`                                                                             |
| QA policy                    | JSON path `source_fact_snapshot ->> 'qa_policy_digest'`                                                                                                                      |
| Landmark                     | column `source_landmark_digest`; JSON path `source_fact_snapshot ->> 'source_landmark_digest'`                                                                               |
| Measurement observation      | column `source_measurement_digest`; JSON paths `source_fact_snapshot ->> 'source_measurement_digest'` and `source_fact_snapshot ->> 'source_measurement_observation_digest'` |
| Source provenance            | column `source_provenance_digest`; JSON path `source_fact_snapshot ->> 'source_provenance_digest'`                                                                           |
| Morphology projection        | column `source_measurement_projection_digest`; JSON path `source_fact_snapshot ->> 'source_measurement_projection_digest'`                                                   |
| Raw measurement authority    | JSON path `source_fact_snapshot ->> 'raw_measurement_authority_digest'`                                                                                                      |
| Repeat certificate           | JSON path `source_fact_snapshot ->> 'source_repeat_certification_digest'`                                                                                                    |
| P2 candidate manifest        | JSON path `source_fact_snapshot ->> 'source_p2_candidate_manifest_content_digest'`                                                                                           |
| Dimension authority manifest | JSON path `source_fact_snapshot ->> 'dimension_authority_manifest_content_digest'`                                                                                           |
| Facts snapshot               | column `source_fact_snapshot_digest`                                                                                                                                         |

Applicability is exactly a `mirror.demo/DemoSyntheticIdentity/v3` row whose generated
`source_authority_kind = 'DEMO_LOCAL_IMPORTED_COPY'`. The migration and ORM constraint name is
`ck_demo_synthetic_identities_d02_local_qa_digest_separation`, and its exact CHECK expression is:

```sql
schema_version <> 'mirror.demo/DemoSyntheticIdentity/v3'
OR source_authority_kind <> 'DEMO_LOCAL_IMPORTED_COPY'
OR (
    source_qa_snapshot_digest IS NOT NULL
    AND jsonb_typeof(source_fact_snapshot) IS NOT DISTINCT FROM 'object'
    AND (source_fact_snapshot ->> 'source_qa_snapshot_digest')
        IS NOT DISTINCT FROM source_qa_snapshot_digest

    AND source_qa_snapshot_digest
        IS DISTINCT FROM formal_canonical_asset_sha256
    AND source_qa_snapshot_digest
        IS DISTINCT FROM source_receipt_digest
    AND source_qa_snapshot_digest
        IS DISTINCT FROM source_authority_digest
    AND source_qa_snapshot_digest
        IS DISTINCT FROM source_landmark_digest
    AND source_qa_snapshot_digest
        IS DISTINCT FROM source_measurement_digest
    AND source_qa_snapshot_digest
        IS DISTINCT FROM source_provenance_digest
    AND source_qa_snapshot_digest
        IS DISTINCT FROM source_fact_snapshot_digest
    AND source_qa_snapshot_digest
        IS DISTINCT FROM source_measurement_projection_digest

    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_asset_sha256')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_receipt_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_authority_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'qa_policy_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_landmark_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_measurement_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_provenance_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (
            source_fact_snapshot ->> 'source_measurement_projection_digest'
        )
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (
            source_fact_snapshot ->> 'raw_measurement_authority_digest'
        )
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (
            source_fact_snapshot ->> 'source_measurement_observation_digest'
        )
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (
            source_fact_snapshot ->> 'source_repeat_certification_digest'
        )
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (
            source_fact_snapshot ->> 'source_p2_candidate_manifest_content_digest'
        )
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (
            source_fact_snapshot ->> 'dimension_authority_manifest_content_digest'
        )
)
```

Every inequality is NULL-safe `IS DISTINCT FROM`; `<>` and `NOT IN` are forbidden. Upgrade obtains its exclusive lock,
then runs an audit equivalent to:

```sql
SELECT 1
FROM demo_synthetic_identities
WHERE schema_version = 'mirror.demo/DemoSyntheticIdentity/v3'
  AND source_authority_kind = 'DEMO_LOCAL_IMPORTED_COPY'
  AND NOT (<the exact inner parenthesized predicate above>)
LIMIT 1;
```

Any returned row aborts before DDL; no digest is rewritten or re-signed. The audit and final CHECK must import/use one
literal predicate definition, not independently maintained lists. Python `validate_facts` must apply the same semantic
authority set, while identity validation continues to prove the column/JSON duplicated values equal. ORM metadata,
migration DDL, Python validation and direct-SQL adversarial tests must have explicit parity. All four layers fail closed
on any alias even when every downstream canonical payload, digest and ID is recomputed.

## Forward prototype migration

```text
MODULE: demo_0007_d02_recovered_qa_authority.py
REVISION: demo_0007_d02_recovered_qa
DOWN_REVISION: demo_0006_d02_private_exec
PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
```

The migration adds no column and changes no accepted v1/v2/v3 payload schema. It adds a PostgreSQL check that enforces
the typed-digest separation above for every local v3 identity and mirrors it in ORM metadata. Upgrade obtains an
exclusive table lock and audits existing rows before DDL; any populated alias row fails before the constraint is added.
Downgrade fails closed while any local v3 identity exists. Historical formal-reference and legacy rows remain
byte-identical.

`RecoveredSyntheticIdentityFacts/v3`, `DemoSyntheticIdentity/v3`, source-manifest v3, case-manifest v3 and Report v2 do
not change because they already bind `source_qa_snapshot_digest` throughout their canonical digest DAG. CC05 closes the
previously underspecified digest preimage; it does not add a field. The existing import-config digest remains unchanged
because the recovered snapshot schema is self-versioning and its content digest is already an immutable identity input.

## Implementation boundary

- Add a pure, filesystem-free recovered-snapshot builder/validator/digest helper.
- Add a pure redacted-index builder/validator.
- Add typed-digest separation to `validate_facts`.
- Add the forward migration and ORM-equivalent check.
- Update fixtures so a typed QA snapshot digest is never a generic metadata hash.
- Generate private snapshot bytes and registry records only after the implementation is accepted.
- Generate the tracked redacted index only from registered, byte-verified private envelopes.
- Do not add a public route, OpenAPI field, generated client type or Celery registration.
- Do not modify legacy formal tables or create synthetic identity/QA compatibility rows.

## Mandatory validation

```text
RECOVERED_QA_EXACT_KEYS
RECOVERED_QA_DETERMINISTIC_REPLAY
RECOVERED_QA_LEGACY_SEMANTICS_EXPLICIT
RECOVERED_QA_FORMAL_DOMAIN_SEPARATION
RECOVERED_QA_POLICY_CONTENT_DIGEST_EXACT
RECOVERED_QA_NINE_MEASUREMENTS_ORDERED
RECOVERED_QA_SIX_REVIEWS_ORDERED
RECOVERED_QA_FAILS_ON_MISSING_OR_EXTRA_FIELD
RECOVERED_QA_FAILS_ON_SUBJECT_OR_TRANSFORM_DEFAULT
RECOVERED_QA_FAILS_ON_NONTERMINAL_OR_FAILED_GATE
RECOVERED_QA_FAILS_ON_OPAQUE_AUTHORITY_ALIAS
RECOVERED_QA_FAILS_ON_EXECUTED_POLICY_DIGEST
RECOVERED_QA_PRIVATE_FIELD_EXCLUSION
RECOVERED_QA_REDACTED_INDEX_REPLAY
PYTHON_POSTGRESQL_TYPED_DIGEST_PARITY
DIRECT_SQL_TYPED_DIGEST_ALIAS_REJECTED
P2_CANDIDATE_MANIFEST_QA_DIGEST_ALIAS_REJECTED_AFTER_FULL_RESIGN
DIMENSION_AUTHORITY_MANIFEST_QA_DIGEST_ALIAS_REJECTED_AFTER_FULL_RESIGN
UPGRADE_ALIAS_AUDIT_FAILS_CLOSED
EMPTY_DEMO_0006_TO_0007_TO_0006_TO_0007
POPULATED_LOCAL_V3_DOWNGRADE_FAILS_CLOSED
ALEMBIC_SINGLE_HEAD_DEMO_0007
ALEMBIC_CHECK
SCHEMA_DRIFT_0
PRIVATE_SNAPSHOT_FILE_DIGEST_VERIFIED
PRIVATE_REGISTRY_RECORD_VERIFIED
TRACKED_INDEX_HAS_NO_PRIVATE_FIELD
```

## Stop rules

D02 import and private pair screening remain closed when any of the following is true:

- the legacy authority head or column set differs from the frozen pre-0012 schema;
- a source SHA resolves to zero, multiple, or incomplete authority chains;
- a tracked source authority binding or provenance digest does not match;
- the approved policy content digest is not exact;
- any QA run, measurement, review, identity attestation or synthetic-only fact is ineligible;
- any missing legacy field is defaulted into the formal snapshot domain;
- any snapshot, envelope, registry byte or redacted-index digest fails replay;
- `source_qa_snapshot_digest` aliases another typed authority;
- a private locator, row ID, payload or byte would enter Git, a normal CI artifact, a sub-agent handoff or public API;
- migration audit, downgrade protection, ORM parity, real PostgreSQL validation or independent Sol review fails.

If the exact private payload cannot be recovered or replayed, the result is
`NO_GO_CRITICAL_DEPENDENCY_UNAVAILABLE`; no identity, Report, QuestionBank or QuestionPair row may be inserted.

## Formal boundary

```text
TRACK: DEMO_PROTOTYPE
QUALIFICATION_SCOPE: LOCAL_SYNTHETIC_PROTOTYPE_DEMO
FORMAL_QA_AUTHORITY_CREATED: NO
FORMAL_SYNTHETIC_IDENTITY_CREATED: NO
FORMAL_P2_READY_DIMENSION_CREATED: NO
REAL_USER_VALIDITY: NOT_EVALUATED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```
