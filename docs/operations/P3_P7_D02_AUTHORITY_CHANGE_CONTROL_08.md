# P3–P7 D02 Change Control 08 — Forward-Only R2 Synthetic Source and Evidence Authority

## Decision status

```text
CHANGE_CONTROL_ID: P3_P7_D02_CC_08
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
STATUS: CANDIDATE_REVISION_5_PENDING_INDEPENDENT_SOL_EXACT_PLAN_REVIEW
PLAN_BASE_SHA: 17f8f1edd84ab39925441b596152c1ff973ed03a
D02_R2_TASK_ID: P3_P7_D02_R2_EXECUTION_01
D02_R2_SOURCE_PRODUCER_TASK_ID: P3_P7_D02_R2_SOURCE_COHORT_01
D02_R2_DISPATCH_EPOCH: 1
D02_R2_PRIVATE_NAMESPACE_ID: pm-p3p7-d02-r2-cc08-e1
D02_R2_EVIDENCE_ROOT_ID: P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT
D02_R2_EVIDENCE_ROOT_BASENAME: p3-p7-d02-r2-cc08-e1-evidence
OLD_D00_RECOVERY: CLOSED_NO_NEW_LEAD
CC07_HISTORICAL_RESULT: EVIDENCE_LOCATION_LOST
CC07_CURRENT_RESULT: NO_GO_CRITICAL_DEPENDENCY_UNAVAILABLE
D02_R2_PRIVATE_PREFLIGHT: CLOSED_PENDING_THIS_PLAN_ACCEPTANCE
D02_R2_CORE_EXECUTION: CLOSED_PENDING_ROOT_GENERATION_AND_RUNTIME_GATES
MIGRATION_IMPLEMENTATION: CLOSED_PENDING_SEPARATE_BOUNDED_TASK_AND_PRINCIPAL_ACCEPTANCE
POSTGRESQL_ADMISSION: CLOSED_PENDING_ACCEPTED_MIGRATION_IMPLEMENTATION
D02_TASK_ACCEPTED: NO
D03: BLOCKED
D04_B: BLOCKED
D07_B: BLOCKED
FORMAL_PHASE_AUTHORITY: FALSE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

This change control establishes a new forward Demo execution. It does not reopen, replace, reinterpret or repair the
lost D00 custody chain recorded by `P3_P7_D02_CC_07`. New evidence is new authority with new output IDs, receipts,
digests, custody and source rows. Historical D00 and CC05/CC06 identifiers never alias the R2 chain.

## CURRENT_REPOSITORY_TRUTH

The exact clean plan base is `17f8f1edd84ab39925441b596152c1ff973ed03a` on
`codex/p3-p7-core-demo`; local and remote are equal. The integration branch already contains accepted D01-C, D04-A,
D07-A, D09, the D02 schema/domain/persistence checkpoints and the API application-integration governance checkpoint.
The current branch-local migration chain ends at `demo_0007_d02_recovered_qa`.

The formal worktree remains separate and protected. This plan reads no protected `.tmp/`, imports no formal dirty byte,
changes no formal migration head and does not consume a concurrent formal source-generation result.

## OLD_D00_RECOVERY_FINAL_STATE

The following history is immutable:

```text
EVIDENCE_LOCATION_LOST
NO_GO_CRITICAL_DEPENDENCY_UNAVAILABLE
OLD_D00_RECOVERY: CLOSED_NO_NEW_LEAD
```

Old recovery may reopen only if a new exact task-scoped locator directly resolves an original accepted D00 receipt,
registry, task-owned root, batch-receipt bytes or a handoff containing all four complete original registry rows. This R2
plan is not such a lead. It performs no disk scan, output-ID derivation, database custody reconstruction, fixture
substitution or new-file impersonation of historical authority.

## D02_R2_CHANGE_CONTROL_ID

`P3_P7_D02_CC_08` is the next free D02 authority change-control identifier. It is distinct from the already accepted
API governance identifier `CC-P3-P7-DEMO-API-08`; neither may be abbreviated to an ambiguous `CC08` in evidence.

## REUSABLE_ACCEPTED_COMPONENTS

| Accepted component                                         | R2 reuse boundary                                                                                                                                            |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Revision 9 D02 report/bank schema and PostgreSQL admission | Reuse exact cardinality, typed JSON, lineage, selection and transactional bank rules. Historical fixture values are not execution evidence.                  |
| Packet A measurement quality                               | Reuse Decimal/fixed-18/ppm, six-measurement, three-repeat, unsupported-state and quality certificate algorithms from current HEAD.                           |
| Packet B authority builder                                 | Reuse current builders/validators for the `4/48/96/144/48/52/1326/24/16` graph after supplying new typed R2 source authority.                                |
| `demo_0005` persistence authority                          | Reuse root binding, projection equality, append-only protection, report/bank/pair validation and populated downgrade protection.                             |
| `demo_0006` opaque-ID and execution authority              | Reuse typed opaque output IDs, private-execution bindings and execution-config validation; old recovered source IDs are forbidden inputs.                    |
| `demo_0007` recovered-QA validators                        | Reuse pure typed-digest and envelope/index techniques only. `RecoveredLegacySyntheticQASnapshot/v1` is not an R2 source schema.                              |
| Measurement and dimension manifests                        | Reuse formulas and contract roots only after actual runtime/config compatibility is reverified. `PREREGISTERED_NOT_EXECUTED` remains non-execution evidence. |
| Pair-screening preregistration Revision 9                  | Reuse frozen pair design, no threshold retuning, manual review, pHash observation-only and exact selection state table.                                      |
| M3 and M4 accepted runtimes                                | Reuse only exact accepted runtime/model/config bytes whose task-scoped handles, digests and offline execution are verified for R2.                           |
| D04-A, D07-A and D09                                       | Preserve their accepted results unchanged; R2 neither rewrites nor prematurely opens their downstream tasks.                                                 |

Historical implementation or handoff SHAs are evidence, not cherry-pick sources. All reused source code is taken from
the current integration HEAD.

## NEW_SOURCE_COHORT_STRATEGY

R2 creates exactly four new clearly-adult, synthetic-only source identities. They use no real-person reference, real
user input, celebrity or social-media source, sensitive label, beauty score or hidden cohort classifier.

The cohort source chain is:

```text
P3_P7_D02_CC_08 accepted plan
-> immutable evidence-root name receipt
-> accepted D02-R2 generation-capability authority
-> D02R2SourceGenerationPreregistrationAuthority/v1
-> four source-candidate plus four provenance name receipts
-> D02R2SourceAllocationManifest/v1
-> D02R2SourceProducerDispatchReceipt/v1
-> four D02R2SourceGenerationReceipt/v1 records
-> four D02R2SourceAuthority/v1 records
-> four D02R2SourceQASnapshot/v1 records
-> D02R2SourceCohortReceipt/v1
-> 12 SourceM3 observations
-> 48 geometry cases
-> 96 M4 executions
-> 144 ResultM3 observations
-> 48 automated measurement Gates
-> 48 decode/structure/immutability records
-> 48 manual reviews
-> 52-image SHA Gate and 1,326 pHash observations
-> 24 screened pairs
-> immutable Report
-> optional 16-pair QuestionBank only after PASSED
```

### Controlled source generation

Source generation is a pre-runtime, bounded Demo asset-production step, not the Generative Editor and not a production
Provider call. Tracked repository authority does **not** currently contain an exact D02-R2 generation capability. The
nearest accepted decision, ADR-026, is scoped to P2 operator-assisted offline source production, exposes no exact
model/version and does not authorize a D02-R2 runtime Provider. It cannot be inherited or broadened by this change
control.

```text
SOURCE_PRODUCER_DISPATCH: BLOCKED_PENDING_SEPARATE_GENERATION_CAPABILITY_AUTHORITY
GENERATION_CALLS_AUTHORIZED_BY_CC08: 0
GENERATION_EGRESS_AUTHORIZED_BY_CC08: NONE
GENERATION_CREDENTIAL_USE_AUTHORIZED_BY_CC08: NONE
```

A separate Principal authority decision must bind an exact tool/capability, provider/model/version disclosure state,
qualification tier and D02-R2 scope, approved endpoint allowlist, credential process boundary, call/output/byte/cost
ceilings, license/privacy/retention terms, Prompt-policy digest, direct create-new sink behavior and stop rules. If exact
model/version is inherently unavailable, that decision must state the limitation and obtain explicit Owner acceptance;
CC08 cannot silently substitute a generic capability claim.

Only after that authority is accepted may a new dispatch freeze call count, retry, concurrency, ordinals and egress.
R2 execution 01 then freezes exactly four calls, zero retry, concurrency one and the four Principal-preallocated
allocations. A failed or unregistered output consumes its ordinal and fails this source cohort; replacement requires a
new forward change control and cannot reuse the output ID/name. The core M3/M4/screening
phase always runs with `PUBLIC_INTERNET_EGRESS: DENIED`; localhost and Docker-internal PostgreSQL, Redis, Celery and
private storage remain available.

### Source acceptance

The producer creates candidates only. The Principal independently rehashes registered bytes, verifies synthetic-only
provenance and clearly-adult presentation, performs decode/QA/M3/M4/manual review and decides source admission. The
producer cannot declare source QA, dimension eligibility, Report, QuestionBank or D02 acceptance.

## OTHER_QUESTIONBANK_WORK_REDISPATCH

The existing P2-M5 E01 generation work is not transplanted into R2. Its `CAL-REQ-002` result remains a consumed,
unregistered, fail-closed P2 result and supplies no R2 byte, receipt, ordinal, resource credit or authority.

The existing Codex task titled `完成 CC04-A Owner Decision` is eligible for a new forward dispatch only after this plan
is Principal-accepted, the R2 evidence root/registry Gate passes **and** a separate exact generation-capability authority
is accepted. Until all three conditions hold, it remains on read-only HOLD. The future role is:

```text
ROLE: D02_R2_SOURCE_COHORT_PRODUCER
NEW_TASK_ID: P3_P7_D02_R2_SOURCE_COHORT_01
NEW_DISPATCH_EPOCH: 1
NEW_BASE_SHA: exact accepted P3_P7_D02_CC_08 SHA
NEW_PRIVATE_NAMESPACE: pm-p3p7-d02-r2-cc08-e1
NEW_BATCH_RECEIPT: REQUIRED
NEW_PER_ITEM_REGISTRY_ROWS: REQUIRED
NEW_GENERATION_PREREGISTRATION: REQUIRED
NEW_SOURCE_ALLOCATION_MANIFEST: REQUIRED
NEW_SOURCE_PRODUCER_DISPATCH_RECEIPT: REQUIRED
DISPATCH_STATUS: BLOCKED_PENDING_SEPARATE_GENERATION_CAPABILITY_AUTHORITY
LOCAL_COMMIT_ONLY: TRUE
NO_DIRECT_POSTGRESQL_ADMISSION: TRUE
NO_DIRECT_INTEGRATION_BRANCH_WRITE: TRUE
NO_OLD_D00_OR_P2_E01_RESOURCE_REUSE: TRUE
```

The producer may write only candidate source bytes and provider-returned provenance into Principal-preallocated,
create-new staging destinations inside its root-scoped writable subtree. The producer does **not** allocate output IDs,
create name receipts, seal outputs or commit registry events. Those are Principal duties: the Principal preallocates the
name receipt, verifies the returned bytes/provenance, computes the seal receipt and commits the same semantic event to
both registry copies. The producer may not access other R2 subtrees, old D00/CC07 inputs, database authority, M3/M4,
manual review, report/bank creation, central registry implementation, migration, ORM, router, OpenAPI, Celery
registration, MEMORY or acceptance state.

## FORWARD_SOURCE_AUTHORITY_AND_MIGRATION_DECISION

The accepted `DemoSyntheticIdentity/v3` and `D02LocalSyntheticAdmissionConfiguration/v1` explicitly model recovered
local imported copies. A newly generated R2 source is not semantically equivalent. It is forbidden to store R2 sources
as `DEMO_LOCAL_IMPORTED_COPY` or to reuse the recovered-legacy snapshot/index domains.

Before PostgreSQL admission, a central Principal-owned forward prototype migration is required:

```text
REVISION: demo_0008_d02_r2_source_auth
DOWN_REVISION: demo_0007_d02_recovered_qa
PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
NEW_SOURCE_AUTHORITY_SCHEMA: mirror.demo/D02R2SourceAuthority/v1
NEW_SOURCE_QA_SCHEMA: mirror.demo/D02R2SourceQASnapshot/v1
NEW_COHORT_SCHEMA: mirror.demo/D02R2SourceCohortReceipt/v1
DEMO_IDENTITY_SCHEMA: mirror.demo/DemoSyntheticIdentity/v4
SOURCE_AUTHORITY_KIND: DEMO_R2_GENERATED_SOURCE
```

The physical design adds one prototype-only supporting authority table, `demo_d02_r2_source_authorities`, and extends
`demo_synthetic_identities` with a nullable R2 authority reference and a third exact source-mode matrix. The supporting
row owns R2 generation/receipt/provenance/QA digests and the neutral reused Asset binding; the
`demo_synthetic_identities` row remains the single Demo identity admission authority. No locator or private byte enters
PostgreSQL.

`demo_d02_r2_source_authorities` has exactly these columns:

```text
id                              char(32) primary key
schema_version                  text not null
canonical_payload               jsonb not null
content_digest                  char(64) not null unique
created_at                      timestamptz not null audit-only
execution_contract_digest       char(64) not null
evidence_root_id                text not null
root_name_receipt_digest        char(64) not null
generation_preregistration_digest char(64) not null
source_allocation_manifest_digest char(64) not null
source_producer_dispatch_digest char(64) not null
source_ordinal                  smallint not null
source_output_id                varchar(128) not null unique
source_asset_id                 varchar(32) not null FK assets(id) on delete restrict
source_asset_sha256             char(64) not null
source_asset_byte_size          bigint not null
source_asset_mime_type          varchar(64) not null
source_asset_width              integer not null
source_asset_height             integer not null
source_generation_receipt_digest char(64) not null unique
output_name_receipt_digest      char(64) not null unique
output_seal_receipt_digest      char(64) not null unique
registry_commit_receipt_digest  char(64) not null unique
generation_capability_authority_digest char(64) not null
generation_request_policy_digest char(64) not null
source_provenance_digest        char(64) not null
source_provenance_output_id     varchar(128) not null unique
source_provenance_name_receipt_digest char(64) not null unique
source_provenance_seal_receipt_digest char(64) not null unique
source_provenance_registry_commit_receipt_digest char(64) not null unique
source_authority_digest         char(64) not null unique
source_authority_key            char(64) not null unique
source_qa_snapshot_digest       char(64) not null unique
adult_synthetic_attested        boolean not null
synthetic_only_attested         boolean not null
real_person_reference_used      boolean not null
authority_state                 varchar(32) not null
```

It has unique `(execution_contract_digest, source_ordinal)`, `source_ordinal between 1 and 4`, exact schema
`mirror.demo/D02R2SourceAuthorityRecord/v1`, all digest-shape checks, all three attestations fixed to
`true/true/false`, positive byte size and dimensions, a decoded-image MIME allowlist inherited from D02, and
`authority_state=PRINCIPAL_ACCEPTED`. Its canonical payload is exactly every structured column
from `execution_contract_digest` through `authority_state`; it excludes `id`, `schema_version`, `canonical_payload`,
`content_digest` and audit-only `created_at`. `content_digest` uses the row schema domain. `id` uses
`mirror.demo/D02R2SourceAuthorityRecordId/v1` over exactly
`{execution_contract_digest, evidence_root_id, root_name_receipt_digest, generation_preregistration_digest,
source_allocation_manifest_digest, source_producer_dispatch_digest, source_ordinal, source_output_id,
source_authority_key, source_authority_digest,
source_qa_snapshot_digest, content_digest}` and takes the first 32 lowercase hex characters. Here `content_digest` is
exactly the row's domain-separated digest of `canonical_payload`; no second digest alias exists. Python and PostgreSQL
must derive the same ID from that exact value and reject either substituted input.

`demo_synthetic_identities.r2_source_authority_record_id` is nullable and has a RESTRICT FK to that exact PK. It is
null for v1/v2/v3 rows and non-null for every v4 row. It is not globally unique because an append-only ADMIT/REVOKE
chain legitimately repeats the same supporting authority; uniqueness remains `(source_authority_key,
admission_sequence)` plus the existing one-successor constraint. For v4, the identity row's
`r2_source_authority_record_id`, source output/Asset/receipt/authority/QA/provenance digests and attestation must equal
the referenced supporting row; its computed source key must equal `D02R2SourceAuthorityKey/v1`. The supporting table
has no reverse identity FK, so the graph remains acyclic.

The migration must update report admission to accept the new source kind without weakening old v3 rules. Existing
formal-reference and recovered-import rows remain byte/semantics unchanged. A populated downgrade fails closed. All
new objects require real PostgreSQL lifecycle, schema-drift, append-only, concurrent-winner and old-to-R2 contamination
tests before database admission opens.

Plan acceptance authorizes only evidence-root/name-receipt/registry implementation and private preflight. It does not
authorize `demo_0008`, ORM or PostgreSQL changes. Those require a separate bounded central migration/models task,
independent review, real-PostgreSQL lifecycle evidence and Principal `TASK_ACCEPTED`. Source production may occur
before that task only after its separate generation-capability authority is accepted because it writes no database.
Report or QuestionBank insertion remains closed until the migration implementation is accepted.

## R2_SCHEMA_VERSION_COMPATIBILITY_MATRIX

R2 is a parallel forward authority, not a validator flag added to an old schema. Every existing v3/v2 constant,
canonical key set, digest domain, ID preimage, helper and PostgreSQL trigger remains byte- and semantics-identical.
Implementation adds parallel R2 builders/validators and explicit mode dispatch; an old helper may be reused only where
the table below says `REUSE_UNCHANGED` and no accepted input or output meaning changes.

| Chain node               | Existing frozen authority                                     | R2 authority                                                          | Disposition                                   |
| ------------------------ | ------------------------------------------------------------- | --------------------------------------------------------------------- | --------------------------------------------- |
| generation allocation    | none                                                          | preregistration v1, allocation manifest v1, producer dispatch v1      | new non-circular Principal authority          |
| generation receipt       | digest scalar only                                            | `D02R2SourceGenerationReceipt/v1`                                     | new exact receipt                             |
| source authority         | `SourceAuthorityKey/v1` for recovered import                  | `D02R2SourceAuthority/v1` + `D02R2SourceAuthorityKey/v1`              | new domain/helper                             |
| source authority row     | none                                                          | `D02R2SourceAuthorityRecord/v1`, record ID v1                         | new supporting PostgreSQL authority           |
| source QA                | `RecoveredLegacySyntheticQASnapshot/v1`                       | `D02R2SourceQASnapshot/v1`                                            | new; no legacy envelope/index                 |
| facts                    | `RecoveredSyntheticIdentityFacts/v3`                          | `D02R2SyntheticIdentityFacts/v1`                                      | new domain; same measurement algorithms       |
| raw/projection           | `D02RawMeasurementAuthority/v2`, `D02MorphologyProjection/v2` | same exact schemas                                                    | `REUSE_UNCHANGED`                             |
| identity                 | `DemoSyntheticIdentity/v3`, admission ID v2                   | `DemoSyntheticIdentity/v4`, admission ID v3                           | new mode/config/ID                            |
| source entry/manifest    | `D02SourceAuthorityManifestEntry/v3`, manifest v1             | entry v4, manifest v2                                                 | new domains                                   |
| SourceM3                 | `D02SourceM3RepeatRecord/v2`, ID v1                           | record v3, ID v2                                                      | new manifest/source binding                   |
| case/config              | case entry v3, case manifest v1, execution config v1          | entry v4, manifest v2, config v2, case/spec IDs v2                    | new domains                                   |
| M4/ResultM3/gate         | M4 v1, ResultM3 v2, gate v4                                   | M4 v2, ResultM3 v3, gate v5; respective record IDs v2                 | new case/execution binding                    |
| structure                | `D02DecodeStructureImmutabilityRecord/v1`                     | v2                                                                    | new case/execution binding                    |
| manual review            | `D02ManualArtifactDecision/v1`                                | same exact schema                                                     | `REUSE_UNCHANGED`; binds result SHA/case only |
| image/exact/pHash        | source/result image v2, exact v2, pHash v2                    | source/result image v3; exact v2 and pHash v2 unchanged               | image source binding versioned                |
| pair/dimension/selection | pair v3, dimension v3, selection v2, selected manifest v2     | pair v4, dimension v4, selection v3, selected manifest v3; pair ID v2 | new source/case domains                       |
| schema/policy            | `D02SchemaAndPolicyBinding/v2`                                | v3                                                                    | new schema-set binding                        |
| Report                   | `D02PairScreeningReport/v2`, Report ID v1                     | Report v3, Report ID v2                                               | new exact 16-group payload                    |
| bank/pair                | `DemoQuestionBank/v2`, `DemoQuestionPair/v2`                  | bank/pair v3, dimension manifest v2, QA payload v3, row IDs v2        | new Report/identity linkage                   |

### Exact new upstream contracts

All payloads use `demo-canonical-json-v1`, lowercase SHA-256, exact key sets, ordered arrays and domain-separated
`mirror_demo_digest(domain, canonical_payload)`. Unknown keys, raw locators, Prompt text, wall-clock-derived defaults,
raw floats and old D00/CC05 identifiers fail closed.

`mirror.demo/D02R2SourceGenerationPreregistrationAuthority/v1` is created by the Principal only after the separate
generation-capability authority is accepted and before any source-candidate name receipt. It has exactly:

```text
schema_version
execution_contract_digest
evidence_root_id
root_name_receipt_digest
generation_capability_authority_digest
cohort_policy_digest
producer_task_id
dispatch_epoch
source_count
ordered_candidate_ordinals
generation_preregistration_digest
```

`source_count=4`, ordinals are exactly `[1,2,3,4]`, and the digest excludes only itself. It intentionally contains no
output ID, name receipt or allocation manifest, so four later candidate name receipts can bind it through
`expected_parent_authority` without a digest cycle.

`mirror.demo/D02R2SourceAllocationManifest/v1` has exactly:

```text
schema_version
execution_contract_digest
evidence_root_id
root_name_receipt_digest
generation_preregistration_digest
producer_task_id
dispatch_epoch
source_count
ordered_allocations
source_allocation_manifest_digest
```

`ordered_allocations` contains exactly four entries ordered by `candidate_ordinal`; each entry has exactly
`{candidate_ordinal, source_output_id, output_name_receipt_digest, source_provenance_output_id,
source_provenance_name_receipt_digest, generation_request_policy_digest, producer_task_id, dispatch_epoch,
source_maximum_bytes, source_expected_media_type, provenance_maximum_bytes, provenance_expected_media_type}`. Both name
receipts must already be durable and resolve under the root manifest; each binds the preregistration digest as
`expected_parent_authority`. Registration events occur only after the corresponding bytes are sealed, so the allocation
manifest never claims that an unwritten output is already registered. The manifest digest excludes only itself.

`mirror.demo/D02R2SourceProducerDispatchReceipt/v1` has exactly:

```text
schema_version
execution_contract_digest
evidence_root_id
root_name_receipt_digest
generation_capability_authority_digest
generation_preregistration_digest
source_allocation_manifest_digest
producer_task_id
dispatch_epoch
call_ceiling
retry_ceiling
concurrency
approved_endpoint_policy_digest
credential_process_boundary_digest
provider_retention_policy_digest
producer_writable_classes
dispatch_state
source_producer_dispatch_digest
```

It fixes `call_ceiling=4`, `retry_ceiling=0`, `concurrency=1`,
`producer_writable_classes=[DATA_SOURCE_CANDIDATES, DATA_SOURCE_PROVENANCE]` and
`dispatch_state=AUTHORIZED_EXACT_ALLOCATIONS_ONLY`; all variable
policy digests must equal the separately accepted generation-capability authority. The dispatch digest excludes only
itself. A new attempt, fifth candidate, changed request policy or replacement output requires a new forward change
control; it cannot re-sign this allocation.

The three singleton authority files are themselves registered outputs. Their name-receipt parent chain is exact and
non-circular: preregistration's parent is the accepted generation-capability authority digest; allocation manifest's
parent is the preregistration digest; producer dispatch's parent is the allocation-manifest digest. None of the three
payloads contains its own name/seal/registry-commit digest. Both registry copies enforce one committed event for each
singleton semantic role before any generation receipt is valid.

`mirror.demo/D02R2SourceGenerationReceipt/v1` has exactly:

```text
schema_version
candidate_ordinal
producer_task_id
dispatch_epoch
execution_contract_digest
evidence_root_id
root_name_receipt_digest
generation_preregistration_digest
source_allocation_manifest_digest
source_producer_dispatch_digest
source_output_id
output_name_receipt_digest
output_seal_receipt_digest
registry_commit_receipt_digest
generation_capability_authority_digest
generation_request_policy_digest
generation_result_provenance_digest
source_provenance_output_id
source_provenance_name_receipt_digest
source_provenance_seal_receipt_digest
source_provenance_registry_commit_receipt_digest
source_asset_sha256
source_asset_byte_size
source_asset_mime_type
source_asset_width
source_asset_height
synthetic_only_attested
real_person_reference_used
receipt_digest
```

`receipt_digest` excludes only itself and uses that schema as its domain. `source_output_id` is a Principal-allocated,
unguessable registry identifier; it is not derived from a path, ordinal or asset digest. The receipt is valid only when
its name, seal and registry-commit digests resolve inside the one evidence root and the separate generation-capability
authority digest equals the accepted dispatch. Its ordinal/output/name/request-policy/task/epoch tuple must be the exact
member of the immutable allocation manifest; its preregistration/allocation/dispatch digests must resolve through the
same two-copy registry. The four provenance-control fields must resolve one distinct registered provenance output whose
sealed authority digest equals `generation_result_provenance_digest`; a digest scalar without recoverable provenance
custody is invalid.

`mirror.demo/D02R2SourceAuthority/v1` has exactly:

```text
schema_version
source_ordinal
execution_contract_digest
evidence_root_id
root_name_receipt_digest
generation_preregistration_digest
source_allocation_manifest_digest
source_producer_dispatch_digest
source_output_id
source_asset_id
source_asset_sha256
source_asset_byte_size
source_asset_mime_type
source_asset_width
source_asset_height
source_generation_receipt_digest
output_name_receipt_digest
output_seal_receipt_digest
registry_commit_receipt_digest
generation_capability_authority_digest
generation_request_policy_digest
source_provenance_digest
source_provenance_output_id
source_provenance_name_receipt_digest
source_provenance_seal_receipt_digest
source_provenance_registry_commit_receipt_digest
synthetic_only_attested
real_person_reference_used
authority_kind
authority_digest
```

`authority_kind` is exactly `DEMO_R2_GENERATED_SOURCE`; `synthetic_only_attested=true` and
`real_person_reference_used=false`. `source_asset_id` retains the accepted `D02ImportedAssetId/v1` preimage because its
byte/lineage meaning does not change. `authority_digest` excludes only itself. The R2 authority key uses
`mirror.demo/D02R2SourceAuthorityKey/v1` over exactly
`{authority_kind, source_output_id, source_asset_id, source_asset_sha256, source_generation_receipt_digest,
authority_digest}` and retains the full 64 lowercase hex digest. The supporting record's `source_authority_key` must
equal this value; `r2_source_authority_record_id` is the separate 32-character deterministic row ID defined above.

`mirror.demo/D02R2SourceQASnapshot/v1` has exactly:

```text
schema_version
source_ordinal
execution_contract_digest
evidence_root_id
root_name_receipt_digest
generation_preregistration_digest
source_allocation_manifest_digest
source_producer_dispatch_digest
source_authority_key
source_authority_digest
source_output_id
source_asset_id
source_asset_sha256
source_asset_byte_size
source_asset_mime_type
source_asset_width
source_asset_height
source_generation_receipt_digest
output_name_receipt_digest
output_seal_receipt_digest
registry_commit_receipt_digest
generation_capability_authority_digest
generation_request_policy_digest
source_provenance_digest
source_provenance_output_id
source_provenance_name_receipt_digest
source_provenance_seal_receipt_digest
source_provenance_registry_commit_receipt_digest
qa_policy_digest
decode_record_digest
ordered_review_decision_digests
adult_synthetic_attested
synthetic_only_attested
real_person_reference_used
qa_state
source_qa_snapshot_digest
```

The ordered review roles are exactly `adult_presentation`, `synthetic_only_provenance`, `real_person_reference_absent`,
`license_rights`, `background_suitability`, `likeness_and_text_watermark`. All six must exist and pass before
`qa_state=PASSED`; the Principal owns the decisions. The snapshot digest excludes only itself. It is not compatible
with `RecoveredLegacySyntheticQASnapshot/v1` and creates no recovered index entry.

`mirror.demo/D02R2SourceCohortReceipt/v1` has exactly:

```text
schema_version
change_control_id
task_id
dispatch_epoch
private_namespace_id
evidence_root_id
root_name_receipt_digest
execution_contract_digest
generation_capability_authority_digest
generation_preregistration_digest
source_allocation_manifest_digest
source_producer_dispatch_digest
cohort_policy_digest
ordered_source_authority_digests
ordered_source_qa_snapshot_digests
registry_copy_a_head_digest
registry_copy_b_head_digest
registry_snapshot_digest
source_count
cohort_state
cohort_receipt_digest
```

It requires exactly four sources ordered by `source_ordinal`, `source_count=4`, equal registry heads/snapshots and
`cohort_state=PRINCIPAL_ACCEPTED`. The cohort digest excludes only itself.

`D02R2SyntheticIdentityFacts/v1` uses the exact 27-key set of `RecoveredSyntheticIdentityFacts/v3` without renaming or
adding a field; every field is populated from the R2 source/QA authority rather than legacy recovery. The new digest
domain is `mirror.demo/D02R2SyntheticIdentityFacts/v1`. Its `source_receipt_digest`, `source_authority_digest` and
`source_qa_snapshot_digest` equal the three R2 digests above; `original_formal_identity_id_status` is exactly
`NOT_APPLICABLE_DEMO_R2_GENERATED_SOURCE`. Raw measurement and morphology projection remain the accepted v2 payloads.

`mirror.demo/D02R2SyntheticAdmissionConfiguration/v1` has exactly:

```text
track
source_mode
identity_schema_version
source_authority_record_schema_version
generation_preregistration_schema_version
source_allocation_manifest_schema_version
source_producer_dispatch_schema_version
source_generation_receipt_schema_version
source_authority_key_domain
source_facts_schema_version
source_qa_schema_version
source_manifest_entry_schema_version
source_manifest_schema_version
source_output_id_contract
source_receipt_binding_required
root_name_receipt_binding_required
registry_commit_binding_required
adult_synthetic_attestation_required
synthetic_only_attestation_required
real_person_reference_forbidden
original_formal_identity_id_status
public_internet_egress_during_core_execution
production_release
```

Its fixed values bind this exact R2 schema matrix, `OPAQUE_PRIVATE_OUTPUT_REGISTRY_ID_V1`, all six
binding/attestation/prohibition booleans to `true`, `NOT_APPLICABLE_DEMO_R2_GENERATED_SOURCE`, core egress `DENIED`, and production
`NOT_AUTHORIZED`. The domain-separated digest of that exact payload is the only v4 `import_config_digest`.

`DemoSyntheticIdentity/v4` uses the exact v3 canonical row key set plus one required
`r2_source_authority_record_id`. Formal identity/QA fields remain null. Its exact fixed values are
`importer_version=demo-d02-r2-identity-importer-v1`, `source_authority_kind=DEMO_R2_GENERATED_SOURCE` and
`import_config_digest=mirror_demo_digest("mirror.demo/D02R2SyntheticAdmissionConfiguration/v1", the exact payload
above)`. Content digest uses `DemoSyntheticIdentity/v4`. Admission event ID uses
`mirror.demo/DemoSyntheticIdentityAdmissionEventId/v3` over exactly
`{source_authority_kind, source_authority_key, r2_source_authority_record_id, admission_sequence, admission_action,
supersedes_id, admission_config_digest, canonical_payload_digest}` and takes the first 32 lowercase hex characters.

`D02SourceAuthorityManifestEntry/v4` uses the exact v3 key set plus required
`r2_source_authority_record_id`; `record_digest` uses the v4 domain excluding `schema_version` and `record_digest`.
`D02SourceAuthorityManifest/v2` is the ordered four-entry sequence digest, ordered by
`(source_ordinal, source_authority_key, source_admission_event_id)` with ordinals exactly 1..4.

### Downstream parallel-version rules

Each R2 execution schema from SourceM3 through Report keeps the predecessor's exact key set unless this paragraph names
an addition. Its digest domain and deterministic ID domain advance to the version in the matrix; the ID preimage keeps
all predecessor fields and replaces predecessor source/manifest/case/report digests with the R2 equivalents.
`SourceM3/v3` additionally binds `source_authority_digest`; case entry v4 additionally binds
`r2_source_authority_record_id`; Report v3 adds exact row counts `measurement_gate_count` and
`decode_structure_record_count`. No other SourceM3-through-Report keys or semantics change. Bank/pair contracts are
separately and completely frozen below.

Report v3 retains exactly the existing 16 top-level group names. Their required schema sequence is:

```text
D02SchemaAndPolicyBinding/v3
D02SourceAuthorityManifestEntry/v4[]
D02GeometryCaseManifestEntry/v4[]
D02SourceM3RepeatRecord/v3[]
D02M4ExecutionRecord/v2[]
D02ResultM3RepeatRecord/v3[]
D02MeasurementGateRecord/v5[]
D02DecodeStructureImmutabilityRecord/v2[]
D02ManualArtifactDecision/v1[]
D02ExactDuplicateEvidence/v2
D02PHashObservationEvidence/v2
D02PairScreeningRecord/v4[]
D02DimensionEligibilityRecord/v4[]
D02SelectionTraceRecord/v3[]
D02SelectedPairManifest/v3
D02NetworkRuntimeBoundary/v2
```

`report_digest` and row `content_digest` use `D02PairScreeningReport/v3` but retain distinct canonical preimages.
Report ID v2 is the first 32 lowercase hex characters of the digest over exactly `{report_digest,
source_manifest_digest, case_manifest_digest}`. A complete FAILED Report retains all 24 candidate screening records,
48 measurement gates, 48 decode/structure records and 48 manual reviews; only selected dimensions/pairs and
QuestionBank/QuestionPair rows are zero.

`mirror.demo/D02QuestionBankDimensionManifest/v2` has exactly:

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

`selected_dimensions` is exactly two objects in frozen priority order. Each object has exactly
`{dimension_key, priority_index, sixteen_side_gate_digest, eight_pair_gate_digest,
ordered_selected_pair_entry_digests}`; the last array contains exactly eight v3 selected-entry digests in source then
magnitude order. There is no nested manifest self-digest.

`mirror.demo/DemoQuestionBank/v3` uses exactly the existing v2 physical/canonical row fields:

```text
id
schema_version
canonical_payload
content_digest
created_at
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

The canonical payload is exactly the structured fields from `version` through `screening_report_digest`; it excludes
`id`, `schema_version`, `canonical_payload`, `content_digest` and audit-only `created_at`. Content digest uses the v3
row domain. `dimension_manifest` must be the exact v2 object above; `pair_manifest_digest` equals its
`selected_pair_manifest_digest`, and Report/source/selected-manifest digests equal Report v3. Bank ID v2 preserves every
predecessor identity input and adds the new source authority:

```text
mirror.demo/D02QuestionBankId/v2
{
  algorithm_config_digest,
  screening_report_digest,
  screening_report_id,
  selected_pair_manifest_digest,
  source_manifest_digest
}
```

The first 32 lowercase hex characters are used. Keeping `algorithm_config_digest` and `screening_report_id` prevents
different algorithms or Report rows over the same manifest from colliding.

`mirror.demo/D02QuestionPairQAPayload/v3` has exactly:

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

There is no nested QA self-digest. `source_manifest_entry_schema_version` is v4, pair schema is v4 and selected-entry
schema is v3. The entry payloads must be exact members of the Report's ordered source/pair/selected groups; their
digests replay under their typed domains.

`mirror.demo/DemoQuestionPair/v3` uses exactly the existing v2 physical/canonical row fields:

```text
id
schema_version
canonical_payload
content_digest
created_at
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

Its canonical payload contains exactly the structured fields from `question_bank_id` through
`screening_report_digest` and excludes the same five authority/audit fields as the bank. Content digest uses the v3 row
domain. Pair ID v2 preserves every predecessor preimage field and adds the two new member authorities:

```text
mirror.demo/D02QuestionPairId/v2
{
  dimension_key,
  magnitude_ppm,
  pair_screening_record_digest,
  question_bank_id,
  source_admission_event_id,
  source_manifest_entry_digest,
  selected_pair_entry_digest
}
```

PostgreSQL requires bank/Report/source-manifest/selected-manifest equality; pair Report equality with its bank; identity
v4 ID/content/source key equality with the source entry; exact source/left/right Asset SHA and AssetVariant lineage;
dimension/magnitude/deltas/quality equality with the pair record; and exact selected-entry equality with both sides.
All 16 pair rows must be the selected manifest projection. Mixed v2/v3 Report-bank-pair or v3/v4 identity/source-entry
chains are rejected.

### Mandatory cross-layer equalities

The implementation checkpoint must prove all equalities below without a compatibility fallback. For compactness, `R`
is the root receipt, `N` the output name receipt, `S` the seal, `E` the registry event, `I` the transaction intent, `C`
the registry commit receipt, `G` the source-generation receipt, `A` the source authority, `Q` the source QA snapshot
and `P` the supporting PostgreSQL row.

1. **Root/control equality.** `N.evidence_root_id=R.evidence_root_id` and
   `N.root_name_receipt_digest=digest(R)`. `N.producer_task_id`, dispatch epoch, semantic role, maximum bytes and expected
   parent authority equal the accepted dispatch. `S` repeats the same root/output/name/role/task values; its actual SHA,
   size and media type equal a fresh rehash/decode of the immutable output. `E` repeats the root/output/role/task/name/seal
   values; its opaque locator resolves to that exact byte under the root; `EXPECTED_DIGEST=ACTUAL_DIGEST=S.actual_sha256`,
   `BYTE_SIZE=S.byte_size`, `MEDIA_TYPE=S.media_type` and `AUTHORITY=S.authority_digest`. `I` repeats the derived
   transaction/sequence/heads and `E.EVENT_DIGEST`; `C` repeats `I.intent_digest`, output, event and the equal A/B
   counts/heads/snapshots. Every digest replays under its exact typed domain.
2. **Generation equality.** `G.execution_contract_digest=R.contract_digest`, `G.evidence_root_id=R.evidence_root_id`,
   `G.root_name_receipt_digest=digest(R)`, `G.producer_task_id=N.producer_task_id=S.producer_task_id=E.CREATING_TASK`,
   `G.dispatch_epoch=N.dispatch_epoch`, and G's output/name/seal/commit fields resolve exactly through `N/S/E/I/C`. Its
   preregistration, allocation-manifest and producer-dispatch digests resolve and the exact
   ordinal/source-output/source-name/provenance-output/provenance-name/request-policy/task/epoch/ceiling/media tuple
   equals its precommitted allocation entry. Both name receipts' expected parent equals the preregistration digest.
   Its
   generation-capability digest equals the separately accepted capability authority and dispatch; its request-policy
   digest equals the dispatched canonical request policy; its result-provenance digest equals the sealed provenance
   authority, and all four provenance output/name/seal/commit fields resolve that exact registered authority. G's source
   SHA/size/media type equal `S` and the decoded Asset authority; width/height equal the decoded
   Asset authority because the generic seal carries no dimensions. The receipt digest must replay before any source
   authority is built.
3. **Source-authority equality.** `A.source_ordinal=G.candidate_ordinal`; A's root/contract, preregistration/allocation/
   dispatch, output/name/seal/commit, capability and request-policy fields equal G.
   `A.source_generation_receipt_digest=G.receipt_digest`; A's provenance digest and four provenance-control fields equal
   G. A's Asset ID is derived from, and its
   SHA/size/media type/width/height equal, G/S/decoded Asset authority. A's synthetic-only and real-person-reference
   attestations equal G. `A.authority_kind=DEMO_R2_GENERATED_SOURCE`; its authority digest and R2 source key replay.
4. **QA equality.** Q's ordinal/root/contract/preregistration/allocation/dispatch/source key/source authority
   digest/output ID, all source and provenance control-receipt digests, capability/request-policy/provenance digests and
   all Asset descriptors equal A and G. Q's synthetic-only
   and real-person-reference attestations equal A/G; `adult_synthetic_attested=true` comes only from the six required
   Principal review decisions. Decode and ordered review digests must resolve under the same root and policy before
   `qa_state=PASSED`.
5. **Supporting-row equality.** P's root/contract/preregistration/allocation/dispatch/ordinal/output ID,
   generation/name/seal/commit receipts, all provenance output/control fields,
   capability/request-policy/provenance, Asset ID/SHA/size/media type/width/height, source authority digest/key and QA
   digest equal G/A/Q. `P.adult_synthetic_attested=Q.adult_synthetic_attested`, while P's other two attestations equal
   A/G/Q. P's canonical payload, content digest and deterministic ID replay exactly; no copied scalar may merely be
   shape-valid.
6. **Identity/manifest equality.** Facts receipt/authority/QA/Asset values equal G/A/Q/P. Identity v4's R2 FK, key,
   facts, Asset, content and attestations equal P+Facts. Source entry v4's R2 FK/key/admission/content and every copied
   scalar equal Identity+Facts+A+Q+P. A field-by-field full-resign substitution using another valid R2 source must fail.
7. **Execution equality.** SourceM3 source key/admission/Asset/SHA/authority equals its source entry; each case entry's
   source manifest/key/admission/Asset/QA/projection equals that manifest; M4 case/spec/source/geometry/runtime equals
   its case; ResultM3, measurement/structure/image evidence equals the case and canonical M4 result.
8. **Screening/import equality.** Pair sides equal passed measurement/structure/manual/image/AssetVariant lineage; Report
   bindings/counts/groups equal the complete R2 graph; selected manifest is only the frozen passed-pair projection;
   QuestionBank/QuestionPair Report, identity, selection, pair-entry and Asset lineage equal those exact R2 authorities.

Mandatory negative tests splice each duplicated field class independently: root/contract, output/control receipt,
capability/request policy, provenance, Asset descriptor, attestation, source/QA and Report/selection. A validator that
only verifies digest shape or allows all fields to be re-signed as one substituted chain does not pass.
An additional execution-level test attempts to register a second internally valid preregistration, allocation manifest
and dispatch in all permutations; the first conflicting singleton insert must roll back both deferred rows in both
copies, and no downstream validator may consume the unregistered replacement.

Any helper that must accept both generations uses explicit schema dispatch and calls one unchanged old validator or one
new R2 validator. It must never broaden an old validator's allowed source kind, key set or digest domain.

## EVIDENCE_ROOT_AND_NAME_RECEIPT

All new R2 evidence is confined to one Principal-designated Git-external folder. No R2 evidence may be written to a
worktree, `.tmp/`, ordinary CI artifact, cache, coordination mailbox, Downloads/Desktop, cloud-synced folder or any
second root.

Tracked evidence records only the public root ID, policy digest and state. It never records the absolute root locator,
private subpaths, Prompt, object key, private bytes or registry locator.

### Root preflight

Before any generation or runtime call, the Principal verifies:

```text
RESOLVED_ROOT_EQUALS_AUTHORIZED_ROOT
ROOT_OUTSIDE_ALL_GIT_WORKTREES
ROOT_NOT_REPARSE_SYMLINK_OR_JUNCTION
ROOT_LOCAL_NOT_NETWORK_OR_CLOUD_SYNC
PRINCIPAL_ONLY_OR_OWNER_CONTROLLED_RESTRICTED_ACL
FREE_SPACE_AND_MAX_BYTES_SUFFICIENT
ROOT_EMPTY_OR_EXACT_SAME_RECEIPT_REPLAY
```

The root basename is fixed as `p3-p7-d02-r2-cc08-e1-evidence`. Its absolute locator exists only in Principal/private
handoff context.

### Root name receipt

The first immutable file in the new folder is exactly:

```text
D02_R2_EVIDENCE_ROOT_NAME_RECEIPT.json
SCHEMA: mirror.demo/D02R2EvidenceRootNameReceipt/v1
```

It binds:

```text
schema_version
evidence_root_id
root_basename
purpose
change_control_id
task_id
dispatch_epoch
accepted_plan_sha
accepted_plan_tree
private_namespace_id
contract_digest
cohort_policy_digest
network_policy
allowed_roles
allowed_output_classes
maximum_bytes
registry_copy_a_id
registry_copy_b_id
registry_schema_contract_digest
registry_normalized_ddl_sha256
registry_implementation_sha
relative_subtree_manifest
created_at_utc
retention_policy
cleanup_dependency_scan_policy
canonicalization_version
receipt_digest
```

The fixed scalar values are:

```text
evidence_root_id: P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT
root_basename: p3-p7-d02-r2-cc08-e1-evidence
purpose: D02_R2_FORWARD_ONLY_SYNTHETIC_SOURCE_AND_PAIR_SCREENING_EVIDENCE
change_control_id: P3_P7_D02_CC_08
task_id: P3_P7_D02_R2_EXECUTION_01
dispatch_epoch: 1
private_namespace_id: pm-p3p7-d02-r2-cc08-e1
maximum_bytes: 42949672960
registry_copy_a_id: P3_P7_D02_R2_CC08_E1_REGISTRY_A
registry_copy_b_id: P3_P7_D02_R2_CC08_E1_REGISTRY_B
retention_policy: RETAIN_UNTIL_D02_R2_AND_ALL_REFERENCING_DOWNSTREAM_TASKS_RELEASE_CUSTODY
cleanup_dependency_scan_policy: PRINCIPAL_EXACT_OUTPUT_ID_DEPENDENCY_SCAN_REQUIRED_BEFORE_ANY_CLEANUP
canonicalization_version: demo-canonical-json-v1
```

`accepted_plan_sha` and `accepted_plan_tree` are the exact accepted tracked governance commit and tree; neither may be
the dirty working-tree hash. `created_at_utc` is selected once by the Principal at the exclusive create-new operation,
normalized as `YYYY-MM-DDTHH:MM:SS.ffffffZ`, and is never recomputed from filesystem metadata. `network_policy` is the
fixed core policy below. `registry_schema_contract_digest`, `registry_normalized_ddl_sha256` and
`registry_implementation_sha` equal the independently accepted registry implementation authorities defined below and
are verified before directory creation. `allowed_roles` is the ordered array
`[INTEGRATION_PRINCIPAL, D02_R2_SOURCE_COHORT_PRODUCER, D02_R2_RUNTIME_EXECUTOR,
D02_R2_REVIEWER_READ_ONLY]`. `allowed_output_classes` is the ordered array
`[SOURCE_GENERATION_PREREGISTRATION, SOURCE_PRODUCER_DISPATCH_RECEIPT, SOURCE_ALLOCATION_MANIFEST, SOURCE_CANDIDATE, SOURCE_PROVENANCE,
SOURCE_GENERATION_RECEIPT, SOURCE_AUTHORITY, SOURCE_QA, SOURCE_COHORT_RECEIPT, SOURCE_MANIFEST, SOURCE_M3,
GEOMETRY_CASE, CASE_MANIFEST, M4_EXECUTION, RESULT_M3, MEASUREMENT_GATE, STRUCTURE_GATE, MANUAL_REVIEW,
IMAGE_AUTHORITY, PHASH, PAIR_SCREENING, REPORT, BANK_IMPORT_EVIDENCE, NEGATIVE_RECEIPT,
RUNTIME_LOG_REDACTED]`. Role presence in this policy does not open dispatch;
the generation-capability and task dependency Gates still apply.

`contract_digest` is
`mirror_demo_digest("mirror.demo/D02R2ExecutionContract/v1", payload)` over exactly:

```text
change_control_id
task_id
dispatch_epoch
accepted_plan_sha
accepted_plan_tree
private_namespace_id
evidence_root_id
root_basename
root_receipt_schema_version
output_name_receipt_schema_version
output_seal_receipt_schema_version
registry_metadata_schema_version
registry_event_schema_version
registry_intent_schema_version
registry_commit_receipt_schema_version
registry_recovery_receipt_schema_version
registry_schema_contract_digest
registry_normalized_ddl_sha256
registry_implementation_sha
source_generation_preregistration_schema_version
source_allocation_manifest_schema_version
source_producer_dispatch_schema_version
source_generation_receipt_schema_version
r2_schema_matrix_version
generation_dispatch_state
core_network_policy
maximum_bytes
```

The fixed schema-matrix token is `P3_P7_D02_R2_SCHEMA_MATRIX_V1`; generation state is
`BLOCKED_PENDING_SEPARATE_GENERATION_CAPABILITY_AUTHORITY`; core network policy is
`LOCALHOST_AND_DOCKER_INTERNAL_ALLOWED_PUBLIC_INTERNET_EGRESS_DENIED`. The four generation schema-version fields equal
the exact v1 domains defined in the upstream-contract section.

`cohort_policy_digest` is
`mirror_demo_digest("mirror.demo/D02R2SourceCohortPolicy/v1", payload)` over exactly:

```text
source_count: 4
source_m3_count: 12
geometry_case_count: 48
m4_execution_count: 96
result_m3_count: 144
measurement_gate_count: 48
decode_structure_record_count: 48
manual_review_count: 48
image_authority_count: 52
phash_comparison_count: 1326
candidate_pair_count: 24
selected_dimension_count_on_pass: 2
selected_pair_count_on_pass: 16
ordered_candidate_dimensions: [jaw_width, chin_height, eye_spacing]
ordered_directions: [DECREASE, INCREASE]
ordered_magnitudes_ppm: [15000, 30000]
synthetic_only_required: true
clearly_adult_required: true
real_person_reference_forbidden: true
```

`network_policy`, `retention_policy` and `cleanup_dependency_scan_policy` are respectively the fixed core policy above,
`RETAIN_UNTIL_D02_R2_AND_ALL_REFERENCING_DOWNSTREAM_TASKS_RELEASE_CUSTODY`, and
`PRINCIPAL_EXACT_OUTPUT_ID_DEPENDENCY_SCAN_REQUIRED_BEFORE_ANY_CLEANUP`.

`receipt_digest` is `mirror_demo_digest("mirror.demo/D02R2EvidenceRootNameReceipt/v1", exact payload excluding only
receipt_digest)`. The timestamp is canonical UTC. The receipt is written directly with exclusive create-new semantics
as the directory's first file, then file and parent-directory durability are checked before any subdirectory or second
file is created. A partial, pre-existing or mismatched receipt is
`EVIDENCE_ROOT_NAME_COLLISION_STOP`; it is never overwritten or automatically suffixed.

`relative_subtree_manifest` is exactly the following ordered eight-entry canonical JSON array. Every
`logical_name_pattern` is an anchored ASCII regular expression; `maximum_bytes` is a per-matched-object ceiling.

```json
[
  {
    "control_class": "ROOT_NAME_RECEIPT",
    "logical_name_pattern": "^D02_R2_EVIDENCE_ROOT_NAME_RECEIPT[.]json$",
    "relative_destination_class": "CONTROL_ROOT",
    "mutability": "CREATE_NEW_IMMUTABLE",
    "maximum_bytes": 262144
  },
  {
    "control_class": "OUTPUT_NAME_RECEIPT",
    "logical_name_pattern": "^D02_R2_OUTPUT_NAME_RECEIPT__[0-9]{8}__[A-Za-z0-9][A-Za-z0-9._-]{0,127}[.]json$",
    "relative_destination_class": "CONTROL_NAME_RECEIPTS",
    "mutability": "CREATE_NEW_IMMUTABLE",
    "maximum_bytes": 262144
  },
  {
    "control_class": "OUTPUT_SEAL_RECEIPT",
    "logical_name_pattern": "^D02_R2_OUTPUT_SEAL_RECEIPT__[0-9]{8}__[A-Za-z0-9][A-Za-z0-9._-]{0,127}[.]json$",
    "relative_destination_class": "CONTROL_SEAL_RECEIPTS",
    "mutability": "CREATE_NEW_IMMUTABLE",
    "maximum_bytes": 262144
  },
  {
    "control_class": "REGISTRY_DATABASE_A",
    "logical_name_pattern": "^D02_R2_PRIVATE_OUTPUT_REGISTRY_A[.]sqlite3(?:-journal)?$",
    "relative_destination_class": "CONTROL_REGISTRY_A",
    "mutability": "APPEND_ONLY_SQLITE_WITH_TRANSIENT_DELETE_JOURNAL",
    "maximum_bytes": 2147483648
  },
  {
    "control_class": "REGISTRY_DATABASE_B",
    "logical_name_pattern": "^D02_R2_PRIVATE_OUTPUT_REGISTRY_B[.]sqlite3(?:-journal)?$",
    "relative_destination_class": "CONTROL_REGISTRY_B",
    "mutability": "APPEND_ONLY_SQLITE_WITH_TRANSIENT_DELETE_JOURNAL",
    "maximum_bytes": 2147483648
  },
  {
    "control_class": "REGISTRY_TRANSACTION_INTENT",
    "logical_name_pattern": "^D02_R2_REGISTRY_TRANSACTION_INTENT__[0-9a-f]{64}[.]json$",
    "relative_destination_class": "CONTROL_REGISTRY_INTENTS",
    "mutability": "CREATE_NEW_IMMUTABLE",
    "maximum_bytes": 262144
  },
  {
    "control_class": "REGISTRY_COMMIT_RECEIPT",
    "logical_name_pattern": "^D02_R2_REGISTRY_COMMIT_RECEIPT__[0-9a-f]{64}[.]json$",
    "relative_destination_class": "CONTROL_REGISTRY_COMMITS",
    "mutability": "CREATE_NEW_IMMUTABLE",
    "maximum_bytes": 262144
  },
  {
    "control_class": "REGISTRY_RECOVERY_RECEIPT",
    "logical_name_pattern": "^D02_R2_REGISTRY_RECOVERY_RECEIPT__[0-9a-f]{64}__[0-9]{4}[.]json$",
    "relative_destination_class": "CONTROL_REGISTRY_RECOVERY",
    "mutability": "CREATE_NEW_IMMUTABLE",
    "maximum_bytes": 262144
  }
]
```

The control destination-class mapping is exact:

```text
CONTROL_ROOT              -> .
CONTROL_NAME_RECEIPTS      -> control/name-receipts
CONTROL_SEAL_RECEIPTS      -> control/seal-receipts
CONTROL_REGISTRY_A         -> control/registry-a
CONTROL_REGISTRY_B         -> control/registry-b
CONTROL_REGISTRY_INTENTS   -> control/registry-intents
CONTROL_REGISTRY_COMMITS   -> control/registry-commits
CONTROL_REGISTRY_RECOVERY  -> control/registry-recovery
```

The non-control `semantic_role -> relative_destination_class -> root-relative directory` mapping is exact:

```text
SOURCE_GENERATION_PREREGISTRATION -> DATA_GENERATION_PREREG    -> authority/generation-preregistration
SOURCE_PRODUCER_DISPATCH_RECEIPT -> DATA_SOURCE_DISPATCH      -> authority/source-dispatch
SOURCE_ALLOCATION_MANIFEST       -> DATA_SOURCE_ALLOCATION    -> authority/source-allocation
SOURCE_CANDIDATE                 -> DATA_SOURCE_CANDIDATES     -> bytes/source-candidates
SOURCE_PROVENANCE                -> DATA_SOURCE_PROVENANCE     -> authority/source-provenance
SOURCE_GENERATION_RECEIPT         -> DATA_GENERATION_RECEIPTS   -> authority/generation-receipts
SOURCE_AUTHORITY                  -> DATA_SOURCE_AUTHORITY      -> authority/sources
SOURCE_QA                         -> DATA_SOURCE_QA             -> evidence/source-qa
SOURCE_COHORT_RECEIPT             -> DATA_SOURCE_COHORT         -> authority/source-cohort
SOURCE_MANIFEST                   -> DATA_SOURCE_MANIFEST       -> authority/manifests/sources
SOURCE_M3                         -> DATA_SOURCE_M3             -> evidence/source-m3
GEOMETRY_CASE                     -> DATA_GEOMETRY_CASES        -> authority/geometry-cases
CASE_MANIFEST                     -> DATA_CASE_MANIFEST         -> authority/manifests/cases
M4_EXECUTION                      -> DATA_M4_EXECUTION          -> evidence/m4
RESULT_M3                         -> DATA_RESULT_M3             -> evidence/result-m3
MEASUREMENT_GATE                  -> DATA_MEASUREMENT_GATES     -> evidence/gates/measurement
STRUCTURE_GATE                    -> DATA_STRUCTURE_GATES       -> evidence/gates/structure
MANUAL_REVIEW                     -> DATA_MANUAL_REVIEWS        -> evidence/manual-review
IMAGE_AUTHORITY                   -> DATA_IMAGE_AUTHORITY       -> authority/images
PHASH                             -> DATA_PHASH                 -> evidence/phash
PAIR_SCREENING                    -> DATA_PAIR_SCREENING        -> evidence/pair-screening
REPORT                            -> DATA_REPORT                -> authority/report
BANK_IMPORT_EVIDENCE              -> DATA_BANK_IMPORT           -> evidence/bank-import
NEGATIVE_RECEIPT                  -> DATA_NEGATIVE_RECEIPTS     -> evidence/negative
RUNTIME_LOG_REDACTED              -> DATA_REDACTED_LOGS         -> logs/redacted
```

The resolver accepts only the listed class token, joins that fixed relative directory with a separator-free ASCII
`logical_name`, canonicalizes the result and requires it to remain under the authorized root. A path, drive prefix,
UNC prefix, `.`/`..`, alternate stream, symlink, junction or reparse point in `logical_name` fails closed. Directories
may be created only after the root receipt is durable; no file may precede that receipt. Before every create/open, the
Principal walks the root and every existing ancestor using no-follow handles, revalidates the authorized volume/file ID
and rejects any reparse point; the final canonical resolved path must remain a strict descendant of the same root.

Each entry has exactly `{control_class, logical_name_pattern, relative_destination_class, mutability, maximum_bytes}`.
The array contains neither `receipt_digest` nor a parent/root digest. The root receipt therefore commits the allowed
namespace without referring to its own not-yet-computed digest. Once the root receipt exists, every later control object
binds both `evidence_root_id` and the already-computed `root_name_receipt_digest` in its own exact payload. Registry
connections must use `journal_mode=DELETE`; `-wal` and `-shm` files are forbidden, and no journal may remain after a
successful durability boundary.

The root receipt preallocates the fixed control-file namespace, so creating its own file and the per-output name-receipt
files is not recursive.

### Non-recursive control-file taxonomy

The root receipt's `relative_subtree_manifest` preallocates exactly these control classes:

```text
ROOT_NAME_RECEIPT              immutable JSON; must be the first root object
OUTPUT_NAME_RECEIPT            immutable JSON; Principal-created before an output
OUTPUT_SEAL_RECEIPT            immutable JSON; Principal-created after byte rehash
REGISTRY_DATABASE_A            live append-only SQLite control store
REGISTRY_DATABASE_B            live append-only SQLite control store
REGISTRY_TRANSACTION_INTENT    immutable JSON; Principal-created before copy A
REGISTRY_COMMIT_RECEIPT        immutable JSON; Principal-created after equal A+B commits
REGISTRY_RECOVERY_RECEIPT      immutable JSON; only for an explicit crash-recovery transition
```

These eight classes are control-plane authority and are exempt from requesting their own output name/seal receipt;
otherwise the receipt graph would recurse. Their exact logical-name patterns, maximum sizes and post-root binding-field
requirements are preallocated by the root receipt; their own payloads later carry the actual root-receipt digest.
Every control JSON is create-new and immutable. Registry A/B are the only mutable files; mutation is restricted to
append-only SQLite transactions, with update/delete denial triggers. Their semantic heads are sealed by immutable
commit receipts rather than by attempting to seal the database file bytes.

Every non-control evidence output requires an immutable name receipt before bytes are created:

```text
SCHEMA: mirror.demo/D02R2OutputNameReceipt/v1
schema_version
evidence_root_id
root_name_receipt_digest
execution_contract_digest
output_id
allocation_sequence
semantic_role
logical_name
producer_task_id
dispatch_epoch
allowed_tasks
expected_parent_authority
expected_media_type
maximum_bytes
relative_destination_class
allocated_at_utc
name_receipt_digest
```

The name digest excludes only itself. `allowed_tasks` is immutable and ordered. For source/provenance allocations it is
exactly `[P3_P7_D02_R2_EXECUTION_01, P3_P7_D02_R2_SOURCE_COHORT_01, P3_P7_D02_R2_EVIDENCE_REVIEW_01]`; for all other
R2 outputs it is exactly `[P3_P7_D02_R2_EXECUTION_01, P3_P7_D02_R2_EVIDENCE_REVIEW_01]`. Later downstream access requires
a new Principal custody change control and cannot be inferred here. `relative_destination_class` is a class token, not
a path; the private registry alone resolves the root-relative locator. Bytes are written create-new/exclusive. After durability and an independent
Principal rehash, `mirror.demo/D02R2OutputSealReceipt/v1` has exactly:

```text
schema_version
evidence_root_id
root_name_receipt_digest
execution_contract_digest
output_id
name_receipt_digest
semantic_role
producer_task_id
actual_sha256
byte_size
media_type
authority_digest
retention
custody
sealed_at_utc
seal_digest
```

The seal digest excludes only itself. It deliberately does **not** bind a registry transaction; the subsequent registry
event binds the already-durable seal receipt, removing the circular dependency identified during review. No overwrite,
automatic suffix, latest-file lookup, after-the-fact move or same ordinal retry is allowed.

For a canonical structured authority, `authority_digest` equals that payload's typed domain-separated digest. For raw
binary evidence it equals
`mirror_demo_digest("mirror.demo/D02R2SealedBinaryAuthority/v1", {semantic_role, actual_sha256, byte_size, media_type,
name_receipt_digest})`. The registry event and transaction project the same semantic role and authority digest under
unique constraints, so a typed authority digest has one recoverable output within this root.

### Principal/producer RACI

| Action                                   | Principal                             | Source producer              |
| ---------------------------------------- | ------------------------------------- | ---------------------------- |
| choose/resolve evidence root             | accountable + executes                | forbidden                    |
| create root/name receipt and output ID   | accountable + executes                | read-only handoff            |
| invoke an accepted generation capability | dispatch/accountable                  | executes only exact dispatch |
| write candidate bytes/provenance         | preallocates destination              | executes create-new write    |
| rehash/decode/admit candidate            | executes                              | forbidden                    |
| create seal receipt                      | executes                              | forbidden                    |
| append registry A/B and commit receipt   | executes                              | forbidden                    |
| QA/M3/M4/manual/Report/bank              | executes/dispatches bounded core work | forbidden                    |

If the producer cannot write directly to the preallocated root-scoped handle without seeing a host locator, generation
does not start and the Principal executes the sensitive step instead.

## PRIVATE_REGISTRY_DESIGN

The single root contains two separate registry-copy subtrees. They provide logical corruption detection inside one
common filesystem root; this plan does not claim independent-device disaster recovery.

Before the root is created, the Principal-owned registry implementation must be independently accepted at one exact
tracked `registry_implementation_sha`. Its semantic schema authority is:

```text
registry_schema_contract_digest =
mirror_demo_digest("mirror.demo/D02R2RegistrySchemaContract/v1", {
  schema_version: "mirror.demo/D02R2RegistrySchemaContract/v1",
  sqlite_application_id: 1297232466,
  sqlite_user_version: 1,
  required_pragmas: [
    "application_id=1297232466",
    "user_version=1",
    "journal_mode=DELETE",
    "synchronous=FULL",
    "foreign_keys=ON",
    "temp_store=MEMORY",
    "trusted_schema=OFF"
  ],
  ordered_table_contracts: [
    "registry_metadata|singleton:INTEGER:PK:CHECK_EQ_1|schema_version:TEXT:NOT_NULL|evidence_root_id:TEXT:NOT_NULL|root_name_receipt_digest:CHAR64:NOT_NULL|execution_contract_digest:CHAR64:NOT_NULL|registry_schema_contract_digest:CHAR64:NOT_NULL|registry_normalized_ddl_sha256:CHAR64:NOT_NULL|registry_implementation_sha:CHAR40:NOT_NULL|registry_copy_id:TEXT:NOT_NULL:UNIQUE|common_genesis_digest:CHAR64:NOT_NULL|created_at_utc:TEXT:NOT_NULL|metadata_digest:CHAR64:NOT_NULL:UNIQUE",
    "registry_events|sequence:INTEGER:PK:CHECK_GE_1|transaction_id:CHAR64:NOT_NULL:UNIQUE:FK_registry_transactions.transaction_id_DEFERRED|output_id:VARCHAR128:NOT_NULL:UNIQUE|semantic_role:TEXT:NOT_NULL|authority_digest:CHAR64:NOT_NULL:UNIQUE|name_receipt_digest:CHAR64:NOT_NULL:UNIQUE|seal_receipt_digest:CHAR64:NOT_NULL:UNIQUE|previous_event_digest:CHAR64:NOT_NULL|event_digest:CHAR64:NOT_NULL:UNIQUE|canonical_event_json:BLOB:NOT_NULL:UNIQUE",
    "registry_transactions|transaction_id:CHAR64:PK|output_id:VARCHAR128:NOT_NULL:UNIQUE|semantic_role:TEXT:NOT_NULL|authority_digest:CHAR64:NOT_NULL:UNIQUE|intent_digest:CHAR64:NOT_NULL:UNIQUE|expected_sequence:INTEGER:NOT_NULL:UNIQUE:CHECK_GE_1|canonical_event_digest:CHAR64:NOT_NULL:UNIQUE:FK_registry_events.event_digest_DEFERRED|transaction_state:TEXT:NOT_NULL:CHECK_COPY_PREPARED|intent_created_at_utc:TEXT:NOT_NULL"
  ],
  ordered_index_contracts: [
    "uq_registry_execution_singleton_roles|UNIQUE|registry_events(semantic_role)|WHERE semantic_role IN ('SOURCE_GENERATION_PREREGISTRATION','SOURCE_ALLOCATION_MANIFEST','SOURCE_PRODUCER_DISPATCH_RECEIPT')"
  ],
  ordered_trigger_contracts: [
    "trg_registry_metadata_no_update|BEFORE_UPDATE|RAISE_REGISTRY_APPEND_ONLY",
    "trg_registry_metadata_no_delete|BEFORE_DELETE|RAISE_REGISTRY_APPEND_ONLY",
    "trg_registry_events_no_update|BEFORE_UPDATE|RAISE_REGISTRY_APPEND_ONLY",
    "trg_registry_events_no_delete|BEFORE_DELETE|RAISE_REGISTRY_APPEND_ONLY",
    "trg_registry_transactions_no_update|BEFORE_UPDATE|RAISE_REGISTRY_APPEND_ONLY",
    "trg_registry_transactions_no_delete|BEFORE_DELETE|RAISE_REGISTRY_APPEND_ONLY",
    "trg_registry_transactions_sequence_guard|BEFORE_INSERT|EXPECTED_SEQUENCE_EQUALS_EVENT_COUNT_PLUS_ONE_AND_OUTPUT_UNIQUE",
    "trg_registry_events_pair_guard|BEFORE_INSERT|MATCH_TRANSACTION_OUTPUT_SEQUENCE_ROLE_AUTHORITY_EVENT_DIGEST_AND_CURRENT_HEAD"
  ],
  canonical_event_projection: [
    "SCHEMA_VERSION", "EVIDENCE_ROOT_ID", "ROOT_NAME_RECEIPT_DIGEST", "EXECUTION_CONTRACT_DIGEST", "OUTPUT_ID", "SEMANTIC_ROLE",
    "CREATING_TASK", "OPAQUE_LOCATOR", "EXPECTED_DIGEST", "ACTUAL_DIGEST", "BYTE_SIZE", "MEDIA_TYPE",
    "AUTHORITY", "ALLOWED_TASKS", "RETENTION", "CUSTODY", "RECOVERY_STATUS", "BACKUP_STATUS", "CLEANUP_STATUS",
    "NAME_RECEIPT_DIGEST", "SEAL_RECEIPT_DIGEST", "TRANSACTION_ID", "SEQUENCE", "PREVIOUS_EVENT_DIGEST",
    "EVENT_DIGEST"
  ],
  semantic_snapshot_preimage: [
    "schema_version", "evidence_root_id", "root_name_receipt_digest", "execution_contract_digest",
    "registry_schema_contract_digest", "common_genesis_digest", "event_count", "head_event_digest", "ordered_events"
  ],
  semantic_snapshot_ordered_event_projection: ["sequence", "transaction_id", "output_id", "semantic_role", "authority_digest", "event_digest"],
  unknown_application_objects_forbidden: true
})
```

The exact implementation also emits one normalized LF/UTF-8 DDL stream containing its ordered application
`CREATE TABLE`, explicit index and `CREATE TRIGGER` statements; its plain SHA-256 is
`registry_normalized_ddl_sha256`. The root receipt and execution contract bind the schema-contract digest, normalized
DDL digest and accepted implementation SHA. Fresh-process replay recomputes all three from the checked-out accepted
implementation and `sqlite_master`; a semantically similar but byte-different DDL, missing trigger or unknown
application object fails closed. Plan acceptance alone therefore opens registry implementation, but the designated
evidence root is not created until that bounded implementation has independent review, same-SHA validation and
Principal acceptance.

Registry mutation is Principal-only and serialized by one non-persistent OS mutex keyed by `evidence_root_id`; no lock
file is created. Each copy is a Python-standard-library SQLite database opened with `journal_mode=DELETE`,
`synchronous=FULL`, `foreign_keys=ON`, `temp_store=MEMORY` and `user_version=1`. A successful boundary fsyncs the file
and containing directory and leaves no journal. The registry schema has exactly three application tables:

```text
registry_metadata
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1)
  schema_version TEXT NOT NULL
  evidence_root_id TEXT NOT NULL
  root_name_receipt_digest CHAR(64) NOT NULL
  execution_contract_digest CHAR(64) NOT NULL
  registry_schema_contract_digest CHAR(64) NOT NULL
  registry_normalized_ddl_sha256 CHAR(64) NOT NULL
  registry_implementation_sha CHAR(40) NOT NULL
  registry_copy_id TEXT NOT NULL UNIQUE
  common_genesis_digest CHAR(64) NOT NULL
  created_at_utc TEXT NOT NULL
  metadata_digest CHAR(64) NOT NULL UNIQUE

registry_events
  sequence INTEGER PRIMARY KEY CHECK (sequence >= 1)
  transaction_id CHAR(64) NOT NULL UNIQUE REFERENCES registry_transactions(transaction_id) DEFERRABLE INITIALLY DEFERRED
  output_id VARCHAR(128) NOT NULL UNIQUE
  semantic_role TEXT NOT NULL
  authority_digest CHAR(64) NOT NULL UNIQUE
  name_receipt_digest CHAR(64) NOT NULL UNIQUE
  seal_receipt_digest CHAR(64) NOT NULL UNIQUE
  previous_event_digest CHAR(64) NOT NULL
  event_digest CHAR(64) NOT NULL UNIQUE
  canonical_event_json BLOB NOT NULL UNIQUE

registry_transactions
  transaction_id CHAR(64) PRIMARY KEY
  output_id VARCHAR(128) NOT NULL UNIQUE
  semantic_role TEXT NOT NULL
  authority_digest CHAR(64) NOT NULL UNIQUE
  intent_digest CHAR(64) NOT NULL UNIQUE
  expected_sequence INTEGER NOT NULL UNIQUE CHECK (expected_sequence >= 1)
  canonical_event_digest CHAR(64) NOT NULL UNIQUE REFERENCES registry_events(event_digest) DEFERRABLE INITIALLY DEFERRED
  transaction_state TEXT NOT NULL CHECK (transaction_state = 'COPY_PREPARED')
  intent_created_at_utc TEXT NOT NULL
```

All digest columns require exactly 64 lowercase hexadecimal characters; output IDs require
`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`; timestamps require canonical UTC. Triggers reject every UPDATE or DELETE on all
three tables and any second metadata row. The two circular, deferred foreign keys require the transaction and event to
exist as a pair at commit; `BEGIN IMMEDIATE` inserts both and a commit of only one row fails. Insert triggers require
`expected_sequence=count(registry_events)+1`, the event sequence to equal it, matching output/transaction/event digests,
matching semantic role/authority projections, and `previous_event_digest` to equal the current head. Application validation before commit and after fresh-process
reopen recomputes every canonical payload and digest; SQLite shape checks do not substitute for digest replay.

Each copy also has the exact partial unique index `uq_registry_execution_singleton_roles` on
`registry_events(semantic_role)` for
`SOURCE_GENERATION_PREREGISTRATION`, `SOURCE_ALLOCATION_MANIFEST` and `SOURCE_PRODUCER_DISPATCH_RECEIPT`. Because one
registry pair is bound to one execution root, each role can have exactly one committed authority. Every generation,
source, QA, supporting-row and cohort validator must resolve the referenced singleton digest to that exact committed
event in both copies; an unregistered second chain is invalid even if all of its private JSON is internally re-signed.

The common previous-head authority is:

```text
mirror_demo_digest("mirror.demo/D02R2RegistryCommonGenesis/v1", {
  schema_version: "mirror.demo/D02R2RegistryCommonGenesis/v1",
  evidence_root_id,
  root_name_receipt_digest,
  execution_contract_digest,
  registry_schema_contract_digest,
  registry_normalized_ddl_sha256,
  registry_implementation_sha,
  registry_event_schema_version: "mirror.demo/D02R2PrivateRegistryEvent/v1",
  genesis_state: "EMPTY_TWO_COPY_REGISTRY"
})
```

Both copies use that identical digest as the zero-event head and first event's `PREVIOUS_EVENT_DIGEST`. Each database
has exactly one metadata payload with keys `{schema_version, evidence_root_id, root_name_receipt_digest,
execution_contract_digest, registry_schema_contract_digest, registry_normalized_ddl_sha256,
registry_implementation_sha, registry_copy_id, common_genesis_digest, created_at_utc, metadata_digest}`. The schema is
`mirror.demo/D02R2RegistryMetadata/v1`; `created_at_utc` equals the root receipt timestamp; copy IDs equal the two fixed
root-receipt IDs; `metadata_digest` excludes only itself and uses the metadata schema as its domain. Copy-specific
metadata digests may differ, but every other genesis input must be equal.

Every semantic event contains exactly:

```text
SCHEMA_VERSION
EVIDENCE_ROOT_ID
ROOT_NAME_RECEIPT_DIGEST
EXECUTION_CONTRACT_DIGEST
OUTPUT_ID
SEMANTIC_ROLE
CREATING_TASK
OPAQUE_LOCATOR
EXPECTED_DIGEST
ACTUAL_DIGEST
BYTE_SIZE
MEDIA_TYPE
AUTHORITY
ALLOWED_TASKS
RETENTION
CUSTODY
RECOVERY_STATUS
BACKUP_STATUS
CLEANUP_STATUS
NAME_RECEIPT_DIGEST
SEAL_RECEIPT_DIGEST
TRANSACTION_ID
SEQUENCE
PREVIOUS_EVENT_DIGEST
EVENT_DIGEST
```

The event schema is exactly `mirror.demo/D02R2PrivateRegistryEvent/v1`; the uppercase tokens above are its exact
canonical keys. `EVENT_DIGEST` excludes only itself. `OPAQUE_LOCATOR` is a registry-resolved root-relative opaque value,
must resolve under the authorized root, and is stored only in these private databases. It is never emitted to Git,
logs, CI artifacts or a sub-agent handoff. Initial semantic values are
`RECOVERY_STATUS=NOT_REQUIRED`, `BACKUP_STATUS=TWO_LOGICAL_COPIES_SAME_ROOT_REQUIRED` and
`CLEANUP_STATUS=RETAINED`; immutable recovery receipts, not event mutation, record later crash recovery.

The locator is uniquely derived as
`r2rel1:` plus unpadded RFC-4648 base64url of UTF-8
`{fixed relative directory from relative_destination_class}/{logical_name}` after separator normalization to `/`.
`ALLOWED_TASKS` equals the exact ordered `allowed_tasks` array in the name receipt. No current time, process ID, host
path, directory enumeration or caller default participates in either value.

For an equal current A/B head, the transaction ID is the full digest:

```text
mirror_demo_digest("mirror.demo/D02R2RegistryTransactionId/v1", {
  evidence_root_id,
  root_name_receipt_digest,
  execution_contract_digest,
  output_id,
  name_receipt_digest,
  seal_receipt_digest
})
```

This preimage contains neither mutable head/sequence nor the event digest, so the deterministic intent path remains
unique even after a crash and the event can bind the transaction ID without recursion. Under the Principal mutex, the
intent then freezes the current sequence and heads; `expected_copy_a_previous_head` and
`expected_copy_b_previous_head` must be equal. The canonical event is built next;
its `TRANSACTION_ID`, `SEQUENCE` and `PREVIOUS_EVENT_DIGEST` must equal the preimage above, and its `EVENT_DIGEST` becomes
`canonical_event_digest`.

Before intent creation, every other event field is a unique projection of the root receipt, name receipt, seal receipt,
fixed locator algorithm, fixed initial status tokens and the equal registry heads. No caller-supplied locator,
allowed-task default or recovery-time choice is permitted.

Before copy A is touched, a create-new immutable `mirror.demo/D02R2RegistryTransactionIntent/v1` freezes exactly
`{schema_version, evidence_root_id, root_name_receipt_digest, execution_contract_digest, transaction_id, output_id,
semantic_role, authority_digest, name_receipt_digest, seal_receipt_digest, canonical_event_digest,
canonical_event_json_b64, expected_copy_a_previous_head,
expected_copy_b_previous_head, expected_sequence, commit_receipt_logical_name, commit_receipt_created_at_utc,
intent_created_at_utc, intent_digest}`. The commit logical name is exactly
`D02_R2_REGISTRY_COMMIT_RECEIPT__{transaction_id}.json`; the two timestamps are identical and selected once at the
exclusive intent create. `intent_digest` excludes only itself. Once the intent is durable, every replay uses its exact
bytes; no recovery chooses a new event field, transaction ID, sequence, timestamp or commit name.

`canonical_event_json_b64` is padded RFC-4648 base64 of the exact `demo-canonical-json-v1` UTF-8 bytes, including
`EVENT_DIGEST`. Decoding must produce byte-identical `canonical_event_json`, whose parsed exact key set and recomputed
digest equal `canonical_event_digest`. The intent therefore durably freezes `OPAQUE_LOCATOR`, `ALLOWED_TASKS` and every
other event field rather than merely committing to a digest with no recoverable preimage.

Copy A then atomically inserts one `registry_transactions` row and the exact event, commits durably and is reopened for
replay; copy B performs the same step only after A passes. The transaction row projects the intent and event fields
exactly. The two event payloads/digests are byte-identical because both copies use the common genesis/head, not their
copy-specific metadata digest.

The semantic snapshot digest is:

```text
mirror_demo_digest("mirror.demo/D02R2PrivateRegistrySemanticSnapshot/v1", {
  schema_version: "mirror.demo/D02R2PrivateRegistrySemanticSnapshot/v1",
  evidence_root_id,
  root_name_receipt_digest,
  execution_contract_digest,
  registry_schema_contract_digest,
  common_genesis_digest,
  event_count,
  head_event_digest,
  ordered_events: [
    {sequence, transaction_id, output_id, semantic_role, authority_digest, event_digest}
  ]
})
```

`ordered_events` is strictly ascending by sequence with no gap. For zero events it is empty, `event_count=0`, and the
head is `common_genesis_digest`. The snapshot excludes SQLite filenames, copy ID, audit timestamps, page layout and
file-byte digest, so valid A/B snapshots are equal.

After both copies durably append the exact semantic event, `mirror.demo/D02R2RegistryCommitReceipt/v1` records exactly:

```text
schema_version
evidence_root_id
root_name_receipt_digest
execution_contract_digest
transaction_id
intent_digest
output_id
canonical_event_digest
copy_a_event_count
copy_a_head_event_digest
copy_a_semantic_snapshot_digest
copy_b_event_count
copy_b_head_event_digest
copy_b_semantic_snapshot_digest
commit_state
created_at_utc
commit_receipt_digest
```

The counts and three semantic digests must be equal across copies, `created_at_utc` must equal the preallocated intent
timestamp, `commit_state=COMMITTED_BOTH_COPIES`, and the digest
excludes only itself. SQLite file-byte digests are diagnostic only and may differ. An event is authoritative only when
both copies, the immutable intent and the immutable commit receipt all resolve and replay. Equal A+B rows without a
commit receipt are explicitly **not committed**.

Registry initialization itself has a closed state machine:

| Durable files at open                           | State                                       | Only legal action                                                                                                       |
| ----------------------------------------------- | ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| neither database exists                         | `REGISTRY_UNINITIALIZED`                    | create A exclusively, fsync/reopen/verify its empty metadata+genesis, then create and verify B                          |
| exactly one valid empty database exists         | `REGISTRY_INITIALIZATION_INTERRUPTED_EMPTY` | verify its copy ID/root/contract/genesis and zero rows, create only the missing copy, then compare zero-event snapshots |
| either file exists but is partial/corrupt       | `REGISTRY_INITIALIZATION_CORRUPTION_STOP`   | do not delete, overwrite or rename it; stop under a new Principal change control                                        |
| one copy has an event/transaction, other absent | `REGISTRY_INCONSISTENT_STOP`                | no initialization replay or automatic clone; complete evidence review under a new change control                        |
| both valid and empty                            | `REGISTRY_READY_EMPTY`                      | require equal common genesis and semantic snapshot before first output allocation                                       |
| both valid with committed history               | `REGISTRY_READY_REPLAYED`                   | replay metadata, transactions, events, intents and commit receipts from sequence 1; require equal count/head/snapshot   |

An unexpected `-wal`/`-shm`, a leftover journal after clean recovery, a copy-ID swap, duplicate metadata, unknown table,
trigger drift or schema drift is `REGISTRY_INITIALIZATION_CORRUPTION_STOP`. No registry operation starts until this
state machine and a fresh-process reopen both pass.

### Crash/recovery state machine

| Durable state at interruption                                        | Derived state                                     | Only legal recovery                                                                                                                                                                                                                                      |
| -------------------------------------------------------------------- | ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| deterministic name-receipt path exists but bytes are partial/corrupt | `OUTPUT_NAME_RECEIPT_PARTIAL_OR_CORRUPT_STOP`     | do not overwrite, delete, suffix or allocate the output; preserve the bytes and stop under a new Principal change control                                                                                                                                |
| valid name+output durable; deterministic seal path absent            | `OUTPUT_DURABLE_SEAL_ABSENT`                      | under the Principal mutex revalidate name/root/containment, rehash/decode the immutable output, then create the sole seal exclusively                                                                                                                    |
| deterministic seal path exists but bytes are partial/corrupt         | `OUTPUT_SEAL_RECEIPT_PARTIAL_OR_CORRUPT_STOP`     | do not overwrite, delete, suffix or infer a seal; preserve the bytes and stop under a new Principal change control                                                                                                                                       |
| seal durable; derived intent path absent; no A/B row for output/tx   | `SEAL_DURABLE_INTENT_ABSENT`                      | under the Principal mutex rehash output/name/seal, require equal current A/B heads, derive the unique transaction ID, verify the exact intent/commit names do not exist, then exclusively create the one new intent; this is intent creation, not replay |
| intent path exists but bytes are partial, corrupt or mismatched      | `REGISTRY_INTENT_PARTIAL_OR_CORRUPT_STOP`         | do not overwrite, delete, suffix or infer missing fields; preserve the object and stop under a new Principal change control                                                                                                                              |
| intent durable; neither copy has its transaction/event               | `INTENT_DURABLE_BOTH_COPIES_ABSENT`               | exact intent/event replay, require heads and sequence still equal the intent, append A then B and create the preallocated commit receipt                                                                                                                 |
| A committed only                                                     | `REGISTRY_ONE_COPY_PREPARED_STOP`                 | reconstruct the event only from immutable intent+name+seal, independently verify A and unchanged expected B head, append the exact event to B, then create the preallocated commit receipt; never copy A database bytes                                  |
| A+B equal, commit receipt absent                                     | `BOTH_COPIES_PREPARED_NOT_COMMITTED`              | fresh-process verify output, intent, both transactions/chains/counts/heads/snapshots; then create the exact preallocated receipt; no automatic committed inference                                                                                       |
| A+B equal; commit path exists but bytes are partial/corrupt          | `REGISTRY_COMMIT_RECEIPT_PARTIAL_OR_CORRUPT_STOP` | do not overwrite, delete, suffix or infer a committed state; preserve the bytes and stop under a new Principal change control                                                                                                                            |
| A+B differ                                                           | `REGISTRY_INCONSISTENT_STOP`                      | no in-place repair; new Principal change control and complete rehash                                                                                                                                                                                     |
| commit receipt durable but intent or seal absent/unresolvable        | `IMPOSSIBLE_ORDER_OR_CUSTODY_CORRUPTION_STOP`     | never synthesize either authority; quarantine the transaction under a new change control                                                                                                                                                                 |
| commit receipt durable but a copy/head does not replay               | `REGISTRY_INCONSISTENT_STOP`                      | no automatic copy restore; new change control                                                                                                                                                                                                            |
| all authorities replay                                               | `COMMITTED_BOTH_COPIES`                           | downstream use allowed                                                                                                                                                                                                                                   |

Every recovery attempt creates an immutable `mirror.demo/D02R2RegistryRecoveryReceipt/v1` in the preallocated control
namespace with exactly:

```text
schema_version
evidence_root_id
root_name_receipt_digest
execution_contract_digest
transaction_id
observed_intent_digest
resulting_intent_digest
observed_intent_bytes_sha256
recovery_attempt
observed_prior_state
output_rehash_digest
copy_a_head_event_digest
copy_b_head_event_digest
recovery_action
recovery_outcome
principal_authority_digest
created_at_utc
recovery_receipt_digest
```

`recovery_attempt` is a positive integer rendered as four digits in the logical name. `observed_intent_digest` is the
validated 64-hex digest or null when the deterministic intent path is absent/corrupt. `resulting_intent_digest` equals
the newly created digest for `SEAL_DURABLE_INTENT_ABSENT`, equals the observed digest for exact replay, and is null for a
failed corrupt-intent stop. `observed_intent_bytes_sha256` is null only when the deterministic intent path is absent and
otherwise hashes the exact observed bytes, including corrupt bytes. The recovery digest excludes only itself.
`SEAL_DURABLE_INTENT_ABSENT` is the sole state where a new intent may be
created, and only after negative proof against the deterministic intent/commit names and both registry tables. Once an
intent file exists, only exact-byte replay is legal. A recovery receipt is audit evidence, not permission to relax
equality. A failed recovery consumes its transaction and stops downstream use.

```text
COMMITTED_BOTH_COPIES
REGISTRY_INCONSISTENT_STOP
```

are respectively the sole success state and the sole state for semantic A/B divergence; the partial/corrupt control
states above are separate fail-closed terminal outcomes. One surviving copy never automatically overwrites the other.
Repair requires a new Principal change control, full chain validation and output rehash before rebuilding a copy. Recovery
starts only from the exact root name receipt and its two registry IDs; no other path may be searched.

Cleanup requires an exact downstream dependency scan. Any referenced output remains retained. The Principal owns all
sub-agent handoff and final custody updates.

## RESOURCE_COLLISION_MATRIX

| Resource            | R2 allocation                               | Collision rule                                                                                                |
| ------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Integration branch  | `codex/p3-p7-core-demo`                     | Principal-only central commits; producer cannot write it.                                                     |
| Producer Codex task | existing task retasked under new task/epoch | New dispatch cannot inherit P2-M5 ordinal, branch, resource or private namespace.                             |
| Evidence root       | `P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT`        | One exact Git-external root; mismatched pre-existing receipt stops.                                           |
| Private namespace   | `pm-p3p7-d02-r2-cc08-e1`                    | No sibling, old D00, P2-M5 E01 or formal namespace access.                                                    |
| Compose project     | `mirror_p3p7_d02_r2_e1`                     | Every compose command supplies the exact project name.                                                        |
| Test database       | `mirror_demo_d02_r2_e1`                     | Isolated database; no formal or other topic database writes.                                                  |
| Redis DB            | `14`                                        | Reserved for R2 only during execution; no FLUSHALL.                                                           |
| Celery queue        | `mirror.demo.d02.r2.e1`                     | Worker consumes only this queue.                                                                              |
| Local storage       | evidence-root storage subtree               | No second storage root or default local bucket.                                                               |
| Temporary output    | evidence-root staging subtree               | Create-new only; no OS temp for evidence bytes.                                                               |
| Host ports          | none by default                             | Localhost ports may be Principal-assigned only for an explicit integration smoke.                             |
| Heavy Docker        | maximum one R2 slot                         | Scheduler retains one spare slot; no unnamed volume teardown.                                                 |
| Private runtime     | one exclusive slot                          | M3/M4 and producer never share the slot concurrently.                                                         |
| Public egress       | none until separately authorized            | CC08 authorizes zero generation egress; any M3/M4/core egress attempt is `EXTERNAL_RUNTIME_DEPENDENCY_FOUND`. |

No task may run `docker compose down --volumes` without the exact R2 project name and a Principal-verified target set.

## REVISED_CRITICAL_PATH

```text
P3_P7_D02_CC_08 exact plan
-> independent Sol exact-plan review
-> Principal plan commit / same-SHA CI / acceptance
-> Principal-owned registry implementation / independent review / same-SHA acceptance
-> evidence root + root name receipt + two-copy registry preflight
-> separate exact generation-capability authority
-> D02_R2_SOURCE_COHORT_PRODUCER (4 accepted sources)
-> Principal source handoff admission
-> demo_0008 central migration/model authority
-> offline M3/M4 full execution and QA
-> Report and optional transactional QuestionBank import
-> independent exact-evidence review
-> Principal D02_R2_TASK_ACCEPTED decision
-> Principal D02 TASK_ACCEPTED decision
-> D03
-> D04-B + D07-B in parallel
```

D04-A, D07-A and D09 remain accepted. D02-R2 acceptance alone does not open D04-B or D07-B; both still require D03
`TASK_ACCEPTED`.

## COUNT_AND_FAILURE_INVARIANTS

| Authority                                  |                    Exact count |
| ------------------------------------------ | -----------------------------: |
| New source identities                      |                              4 |
| SourceM3 records                           |                             12 |
| Geometry cases                             |                             48 |
| M4 executions                              |                             96 |
| ResultM3 records                           |                            144 |
| Measurement-gate records                   |                             48 |
| Decode/structure/immutability records      |                             48 |
| Manual decisions                           |                             48 |
| Image authority records / pHash signatures |                        52 / 52 |
| pHash comparisons                          |                          1,326 |
| Candidate A/B pairs                        |                             24 |
| Selected dimensions                        |   PASSED: exactly 2; FAILED: 0 |
| Selected pairs / result sides              | PASSED: 16 / 32; FAILED: 0 / 0 |

The 52-image universe is four sources plus one canonical result for each geometry case. M4 replay and M3 repeats do not
add images. pHash is observation-only and cannot affect eligibility, selection or threshold tuning.

Incomplete cardinality is an early stop and creates only registry failure evidence; it cannot be submitted as a
database `FAILED` Report. After complete cardinality, ordinary measurement, manual or exact-SHA Gate failure may create
one immutable `FAILED` Report. That complete FAILED Report still contains all 24 candidate screening records, all 48
measurement gates, all 48 decode/structure/immutability records and all 48 manual reviews; it contains zero selected
dimensions, zero selected-pair manifest entries, zero `demo_question_banks` rows and zero `demo_question_pairs` rows.
`PASSED` requires the full exact-SHA Gate, at least two eligible dimensions, frozen-priority selection of exactly two
dimensions and the exact 16-pair manifest.

## RISK_REGISTER

The continuous register adds R-DEMO-22 through R-DEMO-32 for evidence-root escape, name collision, registry divergence,
legacy contamination, source-schema mismatch, producer registration failure, absent generation-capability authority,
premature migration implementation, seal-to-intent crash ambiguity, registry initialization/genesis drift and
cross-layer authority splicing. Existing R-DEMO-01, -03, -10 and -19 remain tracked and are not replaced.
R-DEMO-01 is explicitly scoped to the immutable legacy D00 custody loss and does not block the new independently
registered R2 path; R-DEMO-03 now evaluates 24 screened candidates and 16 selected pairs.

Mandatory stop outcomes include:

```text
EVIDENCE_ROOT_NOT_READY_STOP
EVIDENCE_ROOT_NAME_COLLISION_STOP
OUTPUT_NAME_OR_ID_COLLISION_STOP
OUTPUT_NAME_RECEIPT_PARTIAL_OR_CORRUPT_STOP
OUTPUT_SEAL_RECEIPT_PARTIAL_OR_CORRUPT_STOP
REGISTRY_INCONSISTENT_STOP
REGISTRY_INITIALIZATION_CORRUPTION_STOP
REGISTRY_INTENT_PARTIAL_OR_CORRUPT_STOP
REGISTRY_COMMIT_RECEIPT_PARTIAL_OR_CORRUPT_STOP
R2_AUTHORITY_SPLICE_DETECTED
HISTORICAL_AUTHORITY_CONTAMINATION_STOP
SOURCE_AUTHORITY_SCHEMA_MISMATCH_STOP
SOURCE_OUTPUT_REGISTRATION_FAILED
GENERATION_CAPABILITY_AUTHORITY_MISSING
MIGRATION_IMPLEMENTATION_AUTHORITY_MISSING
EXTERNAL_RUNTIME_DEPENDENCY_FOUND
INCOMPLETE_EXECUTION_UNIVERSE_STOP
```

## D02_R2_EXIT_GATE

R2 can be `TASK_ACCEPTED` only when all conditions are actually verified:

1. The exact CC08 plan, source/config authority and forward-migration decision pass independent Sol review, same-SHA CI
   and Principal acceptance.
2. CC07 blob and state are unchanged, and no old-to-R2 identifier, digest, receipt or row alias exists.
3. The accepted exact registry implementation/DDL authority, one evidence root, immutable root/name/seal receipt
   lifecycle and two-copy registry pass create-new,
   replay, corruption, divergence and fresh-process recovery tests.
4. A separate exact generation-capability authority is accepted before any generation dispatch. Four source candidates
   are then newly generated and registered; the Principal rehashes every byte and accepts exactly four synthetic-only,
   clearly-adult source authorities.
5. `demo_0008_d02_r2_source_auth`, ORM and validators pass real PostgreSQL fresh/upgrade/downgrade/re-upgrade,
   single-head, drift, append-only, concurrent-winner, populated-downgrade and Python/PostgreSQL
   `content_digest`→supporting-row-ID parity tests.
6. Under denied public egress, the exact `4/12/48/96/144/48-measurement/48-structure/48-manual/52/1326/24` evidence
   universe completes using the accepted M3/M4 runtimes and actual registered bytes.
7. The Report is exactly one legal result: `PASSED + >=2 eligible + 2 selected + 16 selected pairs + 32 sides`, or
   `FAILED + 24 candidate records + 0 selected dimensions/pairs + 0 QuestionBank/QuestionPair rows`.
8. A PASSED bank import is one PostgreSQL transaction; idempotent replay is field-identical and every failure fully
   rolls back.
9. Every private byte resolves and rehashes from the root receipt and both registry copies; tracked evidence contains no
   private field, locator, Prompt or byte.
10. Targeted/full tests, real PostgreSQL, network denial, Gitleaks, scoped diff, independent exact-evidence review and
    same-SHA CI pass.
11. Only the Integration Principal grants `D02_R2_TASK_ACCEPTED` and then separately decides full D02 acceptance.

Any mandatory item not executed is `NOT_VERIFIED`, never PASS. R2 does not create formal P2/P3-P7 authority, real-user
validity, production security or release authorization.

## NEXT_BOUNDED_ACTION

```text
1. Independently review the exact plan diff.
2. If accepted, commit and run same-SHA CI.
3. Principal publishes the CC08 acceptance checkpoint.
4. Implement and independently accept the exact Principal-owned registry/receipt module; bind its implementation SHA,
   schema-contract digest and normalized DDL digest.
5. Create the one Git-external evidence root; create and durability-check its first file,
   `D02_R2_EVIDENCE_ROOT_NAME_RECEIPT.json`.
6. Initialize and fault-test the two registry copies and non-recursive receipt lifecycle.
7. Complete a separate exact generation-capability authority decision; do not use old D00 evidence or broaden ADR-026.
8. Separately package `demo_0008`/ORM as a bounded central migration task; do not implement it under plan acceptance.
9. Only if the generation decision is accepted, create the preregistration, four candidate allocations and exact
   producer dispatch, then begin four-source forward
   production. PostgreSQL admission additionally waits for the migration task acceptance.
```

Until steps 1–6 pass, no R2 generation or M3/M4 execution begins. Steps 1–6 may proceed without waiting for old D00
evidence. Source generation remains blocked until step 7 separately passes. Migration/ORM implementation remains
closed until step 8 receives its own bounded dispatch; PostgreSQL admission remains closed until that implementation is
independently reviewed and Principal-accepted.
