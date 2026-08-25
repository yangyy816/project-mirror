# P3–P7 D02-R2 Migration Dispatch Addendum 01

```text
ADDENDUM_ID: P3_P7_D02_R2_MIGRATION_DISPATCH_ADDENDUM_01
CHANGE_CONTROL_ID: P3_P7_D02_CC_08
CONTRACT_ID: P3_P7_D02_R2_MIGRATION_AUTHORITY_IMPLEMENTATION_CONTRACT_01
TRACK: DEMO_PROTOTYPE
STATUS: PRINCIPAL_FROZEN_CANDIDATE_PENDING_EXACT_SHA_REVIEW
BASE_SHA: 214efee32a8a498a1b960d4e8cf4db767bf94966
CC08_GIT_BLOB_OID: afd7a92e7f87fedb597268e7f92317a6cd1a4a84
CC08_GIT_BLOB_SHA256: d8702231045af9c705b9bccd2e26cce8d791823e9717574b317c91fbbef9da47
MIGRATION_CONTRACT_SHA256: c472e9e5f7475f49e8a98f2b477997bfb761db9acd5f4d650b01923094d9d800
PRIVATE_INPUT_HANDOFF: NONE
SOURCE_GENERATION_CALLS_AUTHORIZED: 0
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
```

## Purpose and authority boundary

This Principal addendum resolves only the implementation-dispatch ambiguity identified while implementing
`demo_0008_d02_r2_source_auth`. It does not change the product or data semantics frozen by CC08 revision 5, add a table
or column, authorize private evidence admission, authorize generation, accept D02-R2, open D03/D04-B/D07-B, or create
formal or production authority.

The historical CC07 disposition remains immutable:

```text
EVIDENCE_LOCATION_LOST
NO_GO_CRITICAL_DEPENDENCY_UNAVAILABLE
OLD_D00_RECOVERY: CLOSED_NO_NEW_LEAD
```

The authoritative CC08 clauses are lines 617–846, 1653–1680 and 1713–1734 of the Git blob identified above. The
accepted migration contract remains authoritative. If this addendum conflicts with either source, the stricter
fail-closed interpretation applies and implementation stops for Principal review.

## Designated evidence-root boundary

This addendum produces no private execution evidence. Every future D02-R2 non-control evidence output must remain under
the one Git-external root identified publicly as `P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT`. Before any such output bytes are
created, the Principal must preallocate its `output_id` and immutable `OUTPUT_NAME_RECEIPT`; the output may then be
sealed and registered through the accepted two-copy registry lifecycle. Tracked code, migration, tests, contracts and
acceptance records are repository artifacts, not private execution evidence. No absolute locator, Prompt, private
runtime path, object key or private byte may enter Git, CI, coordination files or `MEMORY.md`.

## Narrow legacy-dispatch exception

CC08's byte-compatibility protection applies to canonical authority bytes, digests, IDs, accepted/rejected outcomes and
all old-version semantics. It permits `demo_0008` to use `CREATE OR REPLACE` only for the seven compatibility/dispatch
functions below, because the physical rows gain nullable columns and the shared wrappers must explicitly select the
unchanged legacy validator or the new R2 validator:

1. `mirror_demo_authority_projection(jsonb,text)`
2. `mirror_demo_guard_authority()`
3. `mirror_demo_validate_d02_synthetic_identity_v10()`
4. `mirror_demo_validate_d02_write_version_v10()`
5. `mirror_demo_validate_d02_question_bank_insert()`
6. `mirror_demo_validate_d02_question_pair_insert()`
7. `mirror_demo_validate_d02_complete_bank()`

The exact exception is:

- Identity v1–v3 authority projections exclude `r2_source_authority_record_id`; Identity v4 includes and validates it.
- Report v1/v2 authority projections exclude `measurement_gate_count` and `decode_structure_record_count`; Report v3
  includes and validates both.
- `mirror_demo_guard_authority()` adds only the Identity v4 R2 source-key derivation path.
- `mirror_demo_validate_d02_synthetic_identity_v10()` changes the old v3 `to_jsonb(NEW)` exclusion only enough to ignore
  the new nullable R2 FK; every other v3 check is unchanged.
- The write-version, bank, pair and complete-bank functions become schema-version dispatch wrappers. Each wrapper calls
  one legacy helper with unchanged old behavior or one R2 helper; an old validator is never broadened to accept an R2
  payload, source kind, key set or digest domain.
- Existing bank, pair, deferred complete-bank and write-version trigger names and DDL remain. The held partial's
  redundant unconditional R2 write triggers must be removed.
- Downgrade restores the exact `demo_0007` function definitions.

At minimum, `demo_0008` adds dedicated helpers for the R2 source-authority key/row, Identity v4, Report v3, Bank v3,
Pair v3 and complete-bank v3 paths, plus separate legacy and R2 row validators where a shared wrapper dispatches.

## Exact version graph

New current-write graphs are exactly:

```text
LEGACY: Report v2 -> Bank v2 -> Pair v2 -> Identity v3 -> SourceEntry v3
R2:     Report v3 -> Bank v3 -> Pair v3 -> Identity v4 -> SourceEntry v4
```

Historical v1 rows remain readable but cannot become new current-write rows. Every cross-combination between these
graphs rejects, including mixed Report/Bank/Pair versions and mixed Identity/SourceEntry versions.

## Report v3 authority

The Report v3 payload contains exactly these 16 top-level groups and required member schemas:

| Group                                    | Required schema                             |
| ---------------------------------------- | ------------------------------------------- |
| `schema_and_policy`                      | `D02SchemaAndPolicyBinding/v3`              |
| `ordered_source_manifest`                | `D02SourceAuthorityManifestEntry/v4[]`      |
| `ordered_case_manifest`                  | `D02GeometryCaseManifestEntry/v4[]`         |
| `source_m3_repeat_evidence`              | `D02SourceM3RepeatRecord/v3[]`              |
| `m4_repeat_evidence`                     | `D02M4ExecutionRecord/v2[]`                 |
| `result_m3_repeat_evidence`              | `D02ResultM3RepeatRecord/v3[]`              |
| `measurement_gate_evidence`              | `D02MeasurementGateRecord/v5[]`             |
| `decode_structure_immutability_evidence` | `D02DecodeStructureImmutabilityRecord/v2[]` |
| `manual_review_evidence`                 | `D02ManualArtifactDecision/v1[]`            |
| `exact_duplicate_evidence`               | `D02ExactDuplicateEvidence/v2`              |
| `phash_observation_evidence`             | `D02PHashObservationEvidence/v2`            |
| `pair_quality_evidence`                  | `D02PairScreeningRecord/v4[]`               |
| `dimension_eligibility`                  | `D02DimensionEligibilityRecord/v4[]`        |
| `fixed_priority_selection_trace`         | `D02SelectionTraceRecord/v3[]`              |
| `selected_pair_manifest`                 | `D02SelectedPairManifest/v3`                |
| `network_and_runtime_boundary`           | `D02NetworkRuntimeBoundary/v2`              |

The row retains all existing structured Report fields and adds
`measurement_gate_count=48` and `decode_structure_record_count=48`. Both columns are NULL for v1/v2. The canonical
payload and all count/state rules are those frozen by CC08. For a complete FAILED Report,
`selected_pair_manifest_digest` follows the inherited nullable projection and no Bank/Pair row may exist.

```text
REPORT_DIGEST_DOMAIN: mirror.demo/D02PairScreeningReport/v3
REPORT_CONTENT_DIGEST_DOMAIN: mirror.demo/D02PairScreeningReport/v3
REPORT_ID_DOMAIN: mirror.demo/D02PairScreeningReportId/v2
REPORT_ID_PREIMAGE: {report_digest, source_manifest_digest, case_manifest_digest}
REPORT_ID_RESULT: first 32 lowercase hexadecimal characters
```

`report_digest` and row `content_digest` use distinct canonical preimages even though their typed domain is the same.

## QuestionBank v3 authority

The Bank v3 canonical payload contains exactly these nine fields:

```text
version
algorithm_config_digest
routing_version
stopping_version
neighborhood_version
pair_manifest_digest
dimension_manifest
screening_report_id
screening_report_digest
```

`dimension_manifest` is exactly `mirror.demo/D02QuestionBankDimensionManifest/v2` with:

```text
schema_version
screening_report_id
screening_report_digest
source_manifest_digest
source_p2_candidate_manifest_content_digest
dimension_authority_manifest_content_digest
selected_pair_manifest_digest
selected_dimensions
```

`selected_dimensions` contains exactly two objects in frozen priority order. Each object has exactly
`dimension_key`, `priority_index`, `sixteen_side_gate_digest`, `eight_pair_gate_digest` and
`ordered_selected_pair_entry_digests`. The final array contains exactly eight `SelectedPairManifestEntry/v3` digests in
source-then-magnitude order. The dimension manifest has no nested self-digest.

```text
BANK_ROW_AND_CONTENT_DOMAIN: mirror.demo/DemoQuestionBank/v3
BANK_ID_DOMAIN: mirror.demo/D02QuestionBankId/v2
BANK_ID_PREIMAGE:
  algorithm_config_digest
  screening_report_digest
  screening_report_id
  selected_pair_manifest_digest
  source_manifest_digest
BANK_ID_RESULT: first 32 lowercase hexadecimal characters
```

## QuestionPair v3 authority

The Pair v3 canonical payload contains exactly these 18 structured fields:

```text
question_bank_id
demo_synthetic_identity_id
source_asset_id
source_asset_sha256
left_asset_id
left_asset_sha256
right_asset_id
right_asset_sha256
left_asset_variant_id
right_asset_variant_id
dimension_key
magnitude_ppm
left_delta_ppm
right_delta_ppm
pair_quality_ppm
qa_payload
screening_report_id
screening_report_digest
```

`qa_payload` is exactly `mirror.demo/D02QuestionPairQAPayload/v3` with:

```text
schema_version
screening_report_id
screening_report_digest
source_manifest_digest
source_manifest_entry_schema_version
source_manifest_entry_digest
pair_screening_record_schema_version
pair_screening_record_digest
pair_screening_record_payload
selected_pair_manifest_digest
selected_pair_entry_schema_version
selected_pair_entry_digest
selected_pair_entry_payload
```

The source entry is v4, pair-screening record is v4 and selected entry is v3. There is no QA self-digest. Each payload
and digest must be an exact typed member of the Report's ordered groups.

```text
PAIR_ROW_AND_CONTENT_DOMAIN: mirror.demo/DemoQuestionPair/v3
PAIR_ID_DOMAIN: mirror.demo/D02QuestionPairId/v2
PAIR_ID_PREIMAGE:
  dimension_key
  magnitude_ppm
  pair_screening_record_digest
  question_bank_id
  source_admission_event_id
  source_manifest_entry_digest
  selected_pair_entry_digest
PAIR_ID_RESULT: first 32 lowercase hexadecimal characters
```

## Deferred complete-bank transaction

A PASSED Report v3 admits its Bank v3 and Pair v3 graph only under the inherited
`DEFERRABLE INITIALLY DEFERRED` complete-bank invariant:

1. The PASSED Report v3 exists before the Bank insert.
2. The Bank and all Pair rows are written in one PostgreSQL transaction.
3. The Bank precedes its Pair rows because of the FK.
4. At deferred validation the graph has exactly 16 pairs, 32 distinct result sides, 4 identities/sources, 2 selected
   dimensions, 2 magnitudes and 8 pairs per selected dimension.
5. The 16 rows are an exact one-to-one projection of all ordered selected-manifest entries. No missing, extra,
   duplicated, swapped or substituted entry is allowed.
6. A 15-pair, 17-pair, duplicate-side, missing-entry, swapped-entry, mixed-version or lineage-mismatch graph rolls back
   the entire transaction and leaves zero new Bank/Pair rows.
7. A FAILED Report v3 always has zero Bank and zero Pair rows.
8. `SET CONSTRAINTS ... IMMEDIATE` fails closed if the graph is incomplete.

The implementation may not weaken this into an empty Bank followed by later transactions.

## Idempotency and concurrency

`IDEMPOTENT_FIELD_SET` is every non-audit authority field, including deterministic ID, schema version,
`canonical_payload`, `content_digest` and every structured physical field. Audit-only `created_at` is excluded from the
comparison and is never overwritten.

- A sequential field-identical replay is a successful no-op. It preserves row counts, all stored digests and the
  original winner's `created_at`.
- A replay that differs in any compared field rejects, including conflicts on primary key, bank version or pair natural
  key. Blind `ON CONFLICT DO NOTHING` is forbidden.
- For concurrent exact imports, one transaction is the insert winner. A uniqueness/serialization loser retries the
  entire transaction; after re-read, an exact graph resolves as the same field-identical no-op.
- No partial loser state may remain. The implementation is not required to make both concurrent first attempts report
  success without a whole-transaction retry.

## Validation ordering

The accepted semantic validation order is:

```text
version/mode
-> exact key/type/count shape
-> typed digest/ID replay
-> database graph/lineage equality
-> outcome/selection
-> row digest/ID/canonical equality
-> deferred complete-bank projection
```

This order is authority. Exact PostgreSQL trigger/constraint error-message ordering is not authority and is not frozen.
All invalid inputs must still fail closed with no partial authority.

## Required implementation and validation disposition

The held partial implementation must be resumed only after this addendum receives independent Sol exact-SHA review,
normal push, same-SHA CI and a separate Principal acceptance record. The resumed task must prove:

- exact Report v3, Bank v3 and Pair v3 schemas, domains, digests and IDs;
- the full legacy/R2 version matrix and unchanged v1/v2/v3 canonical bytes and outcomes;
- deferred 16-pair completeness and all rollback negatives;
- sequential exact replay, conflicting replay and concurrent whole-transaction retry;
- append-only and populated-downgrade fail-closed behavior for every new authority class;
- fresh/upgrade/downgrade/re-upgrade, single head, Alembic check, schema drift, Ruff, strict mypy, targeted and full API
  regression on real PostgreSQL 17.

Until the separate acceptance record is accepted:

```text
MIGRATION_ADDENDUM_01: NOT_TASK_ACCEPTED
D02_R2_MIGRATION_IMPLEMENTATION: HOLD
D02_R2_POSTGRESQL_ADMISSION: CLOSED
D02_R2_SOURCE_GENERATION: BLOCKED
D02_R2: NOT_TASK_ACCEPTED
D03: CLOSED
D04_B: CLOSED
D07_B: CLOSED
```
