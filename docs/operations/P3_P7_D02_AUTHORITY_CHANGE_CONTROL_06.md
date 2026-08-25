# P3–P7 D02 Change Control 06 — Shared Batch Receipt Digest Cardinality

## Decision status

```text
CHANGE_CONTROL_ID: P3_P7_D02_CC_06
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
STATUS: PRINCIPAL_ACCEPTED
BASE_SHA: b985d29232e07c962530f4ce85675e61b591b72f
DISCOVERY: CC05_BATCH_RECEIPT_CARDINALITY_CONTRADICTION
SUPERSEDES: CC05_INDEX_SOURCE_RECEIPT_DIGEST_UNIQUENESS_ONLY
CC05_IMPLEMENTATION_CHECKPOINT: REMAINS_TASK_ACCEPTED
INDEPENDENT_SOL_CONTRACT_REVIEW: PASS
INDEPENDENT_SOL_FINDINGS_P0_P1_P2_P3: 0/0/0/0
REVIEWED_CONTRACT_BLOB_SHA256: 61a98c58baf7db69772345d185086e531471aaa5030956f2a57e77a75de95eb9
IMPLEMENTATION_AUTHORIZED: YES
IMPLEMENTATION_STATUS: TASK_ACCEPTED
IMPLEMENTATION_SHA: e8dea452837410e2322cb9145e2178ec26a3b026
IMPLEMENTATION_PARENT: b985d29232e07c962530f4ce85675e61b591b72f
IMPLEMENTATION_TREE: 192f3ddd744452c0315d32da15e87be9161308ae
INDEPENDENT_SOL_EXACT_SHA_REVIEW: PASS
INDEPENDENT_SOL_EXACT_SHA_FINDINGS_P0_P1_P2_P3: 0/0/0/0
CANDIDATE_SAME_SHA_CI_RUN: 32819929887
CANDIDATE_SAME_SHA_CI_JOBS: 3_PASS
CC06_IMPLEMENTATION_CHECKPOINT: TASK_ACCEPTED
PRIVATE_SNAPSHOT_RECOVERY: PAUSED_PENDING_ACCEPTANCE_CHECKPOINT_CI
D02_PRIVATE_SCREENING: BLOCKED
D02_TASK_ACCEPTED: NO
D03: BLOCKED
FORMAL_PHASE_AUTHORITY: FALSE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

CC05 correctly freezes `source_receipt_digest` as the exact D00 private holdout input receipt content digest. The
accepted recovery authority is one canonical batch receipt document containing four source entries and one replayable
content digest. The four sources do not have four separately frozen per-entry receipt content digests.

CC05 also requires `source_receipt_digest` to be unique across the four redacted index entries. That requirement
contradicts the frozen batch-receipt mapping and rejects the only recovered receipt authority. Creating, deriving or
guessing four per-entry receipt digests would invent evidence and is forbidden.

This forward change control corrects only that cardinality rule before any private snapshot, registry record or tracked
redacted index has been created. It does not rewrite CC05 history, reduce evidence, change a payload key, change a digest
preimage, create a migration or promote any formal authority.

## Frozen authority correction

For all four recovered source snapshots:

```text
source_receipt_digest = exact D00 holdout batch receipt content digest
cardinality({entry.source_receipt_digest for entry in index.entries}) = 1
```

The one shared value must replay from the single accepted batch receipt document resolved through the Principal-owned
D00 receipt/registry chain. It is not:

- the receipt file SHA-256;
- an individual registry-record digest;
- a source output digest;
- a per-entry projection digest;
- a database row digest; or
- a value derived from an item reference, asset SHA or source-local authority.

The actual digest value remains Git-external unless an already accepted tracked authority explicitly publishes it.
The Principal passes it to the pure builder as verified task-scoped input; the builder does not resolve a locator,
inspect a filesystem or query a database.

## Redacted index cardinality

The CC05 index schemas and digest formulas remain exact and unchanged:

```text
ENTRY_SCHEMA: mirror.demo/RecoveredLegacySyntheticQASnapshotIndexEntry/v1
INDEX_SCHEMA: mirror.demo/RecoveredLegacySyntheticQASnapshotIndex/v1
SNAPSHOT_SCHEMA: mirror.demo/RecoveredLegacySyntheticQASnapshot/v1
CANONICALIZATION: demo-canonical-json-v1
```

The four index entries must remain unique for each of these fields:

```text
item_reference
source_output_id
source_asset_sha256
source_authority_digest
source_provenance_digest
private_snapshot_output_id
private_snapshot_file_sha256
source_qa_snapshot_digest
```

`source_receipt_digest` is removed from that uniqueness set and placed in this exact shared-authority set:

```text
SHARED_BATCH_AUTHORITY_FIELDS:
- source_receipt_digest

REQUIRED_DISTINCT_VALUE_COUNT:
- source_receipt_digest: 1
```

`qa_policy_digest` and `adult_synthetic_attested` retain their CC05 shared-value semantics. No other uniqueness,
cardinality, ordering, equality or replay rule changes.

## Per-entry and private-envelope equality

For each index entry, all CC05 equality checks remain mandatory. In particular:

```text
entry.source_receipt_digest
  = matching_private_envelope.canonical_payload.source_binding.source_receipt_digest
  = accepted_D00_batch_receipt.content_digest
```

Each matching private envelope remains source-specific. Its content digest and file SHA-256 therefore remain unique
because its source output, source asset, source authority, provenance, measurements and reviews remain source-specific.
Sharing the batch receipt digest does not allow any source-local authority, snapshot or private file to be shared.

The index remains redacted and must not contain the receipt document, receipt locator, registry locator, absolute path,
database row ID, private payload, object key, Prompt, secret or private byte.

## Fail-closed validator rule

After validating all four entries individually and validating the exact item ordering, the index validator must enforce:

```python
unique_fields = (
    "source_output_id",
    "source_asset_sha256",
    "source_authority_digest",
    "source_provenance_digest",
    "private_snapshot_output_id",
    "private_snapshot_file_sha256",
    "source_qa_snapshot_digest",
)

for field in unique_fields:
    require(len({entry[field] for entry in entries}) == 4)

require(len({entry["source_receipt_digest"] for entry in entries}) == 1)
```

The shared-receipt check is not optional. Merely removing `source_receipt_digest` from the uniqueness loop without
requiring exactly one shared value is non-conforming because it would accept two, three or four unrelated receipt
authorities in one index.

All four entry `record_digest` values and the index `content_digest` must be revalidated after any mutation. A caller
cannot bypass the shared-receipt rule by re-signing entries or the index document.

## Compatibility and version disposition

No CC05 private snapshot or tracked index exists, so there is no persisted payload to migrate, rewrite or grandfather.
This correction changes only the admissible four-entry relationship and leaves every serialized key and digest preimage
unchanged. Therefore:

```text
SNAPSHOT_SCHEMA_VERSION_CHANGE: NONE
ENVELOPE_SCHEMA_VERSION_CHANGE: NONE
INDEX_ENTRY_SCHEMA_VERSION_CHANGE: NONE
INDEX_SCHEMA_VERSION_CHANGE: NONE
MIGRATION_REQUIRED: NO
ORM_CHANGE_REQUIRED: NO
OPENAPI_CHANGE_REQUIRED: NO
GENERATED_CLIENT_CHANGE_REQUIRED: NO
ROUTER_CHANGE_REQUIRED: NO
CELERY_REGISTRATION_CHANGE_REQUIRED: NO
```

Historical synthetic test fixtures that invented four receipt digests were implementation fixtures, not accepted D00
evidence. They must be replaced with one deterministic batch receipt digest shared by all four fixture sources.

## Mandatory implementation scope

Only these implementation files may change after this contract is independently accepted:

```text
services/api/src/mirror_api/demo_d02_authority.py
services/api/tests/test_demo_d02_authority.py
```

The implementation must:

1. remove `source_receipt_digest` from the index uniqueness loop;
2. add the exact-one shared receipt cardinality check;
3. update the four-source replay test to use one batch receipt digest;
4. prove the resulting four-envelope/index replay succeeds;
5. prove a fully re-signed index containing a second receipt digest fails closed;
6. preserve every other unique-field and typed-authority alias negative test; and
7. produce no filesystem, registry, database, network or private-input side effect.

## Mandatory validation

```text
SHARED_BATCH_RECEIPT_FOUR_SOURCE_REPLAY
SOURCE_RECEIPT_DISTINCT_VALUE_COUNT_1
SECOND_RECEIPT_AFTER_FULL_RESIGN_REJECTED
ALL_OTHER_INDEX_UNIQUENESS_PRESERVED
PRIVATE_SNAPSHOT_FILE_DIGEST_REPLAY
INDEX_ENTRY_RECORD_DIGEST_REPLAY
INDEX_CONTENT_DIGEST_REPLAY
TRACKED_INDEX_HAS_NO_PRIVATE_FIELD
CC05_TYPED_DIGEST_ALIAS_NEGATIVES_UNCHANGED
DETERMINISTIC_REPLAY
RUFF_FORMAT_CHECK
STRICT_MYPY
TARGETED_D02_AUTHORITY_TESTS
FULL_PYTHON_REGRESSION
GITLEAKS
SCOPED_DIFF
INDEPENDENT_SOL_EXACT_SHA_REVIEW
SAME_SHA_CI
```

## Acceptance sequence

```text
CC06 exact contract
→ independent Sol contract review
→ Principal implementation authorization
→ bounded two-file implementation
→ targeted and full local validation
→ independent Sol exact-SHA implementation review
→ Principal commit and normal push
→ same-SHA CI
→ Principal acceptance-state checkpoint
→ acceptance-state same-SHA CI
→ resume Principal-only private snapshot recovery
```

No private snapshot generation may overlap contract review, implementation or same-SHA acceptance.

## Acceptance evidence

The Integration Principal accepts exact implementation
`e8dea452837410e2322cb9145e2178ec26a3b026` only. The implementation changes the CC06 contract plus the two authorized
Python files; it creates no migration, ORM, API, router, generated client, Celery registration, private snapshot,
registry record, tracked redacted index, identity, Report, QuestionBank or QuestionPair.

- parent `b985d29232e07c962530f4ce85675e61b591b72f` and tree
  `192f3ddd744452c0315d32da15e87be9161308ae` replay exactly;
- exact Git-archive CC06 success and full-resign negative tests: `2 PASS`;
- exact Git-archive complete D02 authority tests: `322 PASS`;
- Ruff format/check, strict mypy for the two changed Python files, Prettier and `git diff --check`: `PASS`;
- exact Git-archive Gitleaks directory scan: approximately 8.18 MB scanned, zero leaks;
- independent Sol High exact-SHA review: `PASS`, findings `P0/P1/P2/P3 = 0/0/0/0`;
- same-SHA CI run `32819929887`: quality/integration, Docker validation and secret scan all `PASS`;
- CI Python result: `1389 passed, 1 skipped`; strict mypy: `134 source files` with no issue;
- CI focused Phase 1/P2-M1/P2-M2/P2-M3 results: `1/98/52/46 PASS`;
- CI TypeScript result: `54 PASS`; Playwright: `5 PASS`; dependency audits: no known vulnerabilities; and
- five unexpired artifacts bind exact candidate SHA, including project audit, Demo boundary, Docker, Playwright install
  and Gitleaks evidence.

One discarded local documentation-formatting harness omitted Docker `--pull=never`; the Docker daemon acquired the
official `node:24.18.0-bookworm-slim` image before the `--network none` container started, and the command then failed.
It did not execute a Demo algorithm, Provider, private input or accepted validation. It is explicitly excluded from
offline evidence. Subsequent exact artifact validation uses already present images with `--pull=never` where image
identity matters. CC06 does not independently claim the D00-B or D12 public-egress Gate.

The CC06 implementation checkpoint is `TASK_ACCEPTED`. Principal-only private snapshot recovery remains paused until
this acceptance-state commit passes its own same-SHA CI. This does not accept D02, open D03, create formal QA authority
or authorize production use.

## Stop rules

Private recovery, D02 import and private screening remain stopped if:

- the recovered receipt is not exactly one replayable batch document;
- its content digest cannot be verified through the accepted D00 receipt/registry chain;
- any code or fixture derives a per-entry receipt digest;
- the four index entries contain more than one `source_receipt_digest`;
- any source-local authority or private snapshot field loses its CC05 uniqueness requirement;
- an entry does not equal its matching private envelope and the shared accepted receipt digest;
- a mutation can pass after recomputing entry/index digests;
- a locator, private payload, row ID or private byte would enter Git, CI, a sub-agent handoff or a public API; or
- scoped validation, independent review or same-SHA CI fails.

If the single accepted batch receipt cannot be recovered and replayed, the result is
`NO_GO_CRITICAL_DEPENDENCY_UNAVAILABLE`. No substitute receipt, per-entry digest, identity, Report, QuestionBank or
QuestionPair authority may be created.

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
