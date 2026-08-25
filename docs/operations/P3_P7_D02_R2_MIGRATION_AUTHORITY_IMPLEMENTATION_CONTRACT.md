# P3–P7 D02-R2 Migration and ORM Authority Implementation Contract

```text
CONTRACT_ID: P3_P7_D02_R2_MIGRATION_AUTHORITY_IMPLEMENTATION_CONTRACT_01
CHANGE_CONTROL_ID: P3_P7_D02_CC_08
TRACK: DEMO_PROTOTYPE
STATUS: PRINCIPAL_FROZEN_CANDIDATE_PENDING_EXACT_SHA_REVIEW
BASE_SHA: 00f1f111d01b4076e4af2e65e2d36e480c544a15
PRIVATE_INPUT_HANDOFF: NONE
SOURCE_GENERATION_CALLS_AUTHORIZED: 0
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
```

## Purpose

This contract opens only the D02-R2 PostgreSQL migration, ORM parity, pure admission validators and their tests. It does
not authorize source generation, private runtime execution, PostgreSQL admission of real D02-R2 evidence, D02-R2 task
acceptance, D03, D04-B, D07-B, formal authority or production release.

CC07 remains immutable as `EVIDENCE_LOCATION_LOST` and `NO_GO_CRITICAL_DEPENDENCY_UNAVAILABLE`; old D00 recovery stays
`CLOSED_NO_NEW_LEAD`. This task implements the separate CC08 forward authority only.

## Principal authority-boundary disposition

The complete private `G → A → Q → P` anti-splice replay is owned by the pure Python admission validator. `G` is the
generation receipt, `A` the accepted source authority, `Q` the QA snapshot and `P` the public PostgreSQL supporting-row
projection. The validator must consume exact typed payloads and prove all CC08 equality, digest, ID, task, dispatch,
policy, decode and review bindings before any database transaction is allowed.

PostgreSQL independently enforces every fact that can be replayed from `P` and the existing database graph:

- canonical payload, content digest and deterministic record ID;
- execution contract, evidence-root and root-name-receipt digests;
- source ordinal, output/receipt/provenance authority and uniqueness;
- immutable Asset checksum, byte size, MIME, dimensions, owner/type/deletion state and lineage;
- synthetic/adult/no-real-person attestations and accepted authority state;
- Identity v4 copy equality, version chain, admission/revocation and concurrency;
- Report v3 counts and state rules;
- bank/pair v3 version graph, 16-pair atomicity, idempotent replay and mixed-version rejection;
- append-only behavior and populated-downgrade fail-closed semantics.

PostgreSQL is not authorized to persist private locator, Prompt, raw generation payload, full QA payload, private
runtime path or image bytes merely to duplicate Python replay. A caller that bypasses the pure validator is outside the
accepted application path; direct SQL still fails all database-projectable invariants. Any future requirement for
PostgreSQL to re-sign the complete private `G/Q` payload requires a new change control and new authority tables.

This disposition preserves the existing CC08 physical column set. It is not delegated to the implementation worker.

## Single designated evidence root

All new D02-R2 runtime, source, QA, screening, report, bank-import and redacted runtime-log evidence must remain below the
single Git-external evidence root identified by:

```text
EVIDENCE_ROOT_ID: P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT
ROOT_NAME_RECEIPT_DIGEST: c3ae43887d51d15347153e392ca092866dff890bdcda959572cc1dd07e6195c4
NEW_OUTPUT_POLICY: PRINCIPAL_PREALLOCATED_OUTPUT_ID_AND_NAME_RECEIPT_REQUIRED
```

The absolute locator is intentionally absent from Git, CI and this contract. Tracked code, migrations, tests and
governance records are repository artifacts, not private execution evidence. Synthetic structural test fixtures may be
tracked only when they contain no private bytes, locator, Prompt, object key or runtime path.

## Exact migration

```text
FILE: services/api/migrations/versions/demo_0008_d02_r2_source_authority.py
REVISION: demo_0008_d02_r2_source_auth
DOWN_REVISION: demo_0007_d02_recovered_qa
PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
```

The migration adds `demo_d02_r2_source_authorities`, nullable R2 bindings on `demo_synthetic_identities`, nullable Report
v3 counts on `demo_pair_screening_reports`, and v3 schema acceptance for the existing question-bank/pair tables. It must
not alter any historical migration.

Because the existing identity guard canonicalizes `to_jsonb(NEW)`, `demo_0008` must `CREATE OR REPLACE` the guard in the
new forward migration so v1–v3 projections explicitly exclude new nullable columns. Existing v1–v3 canonical JSON,
digests, IDs, constraints and behavior must remain byte-identical across `0007 ↔ 0008`.

## Physical authority

`demo_d02_r2_source_authorities` is append-only and contains the exact CC08 supporting-row fields from `id` through
`authority_state`, including unique output, provenance, name/seal/commit receipt and authority digests. It has a unique
constraint on `(execution_contract_digest, source_ordinal)` and a RESTRICT FK to the existing `assets` authority.

No competing Asset, private receipt, cohort receipt, generation receipt, QA snapshot or registry-locator table is
created. Assets and AssetVariants remain the byte/lineage authority.

`demo_synthetic_identities.r2_source_authority_record_id` is nullable and RESTRICT-bound to the supporting table. It is
null for v1–v3 and required for v4. It is deliberately not unique so an ADMIT/REVOKE chain can reference the same source
authority. Formal and local modes must reject the R2 FK.

`demo_pair_screening_reports.measurement_gate_count` and `decode_structure_record_count` are null for v1/v2 and exactly
48 for v3. Bank/pair v3 adds no physical columns and must bind only Report v3 and Identity v4.

## Digest and version invariants

- Supporting-row canonical payload is exactly all structural fields from `execution_contract_digest` through
  `authority_state`; authority/audit headers are excluded.
- `content_digest` uses `mirror.demo/D02R2SourceAuthorityRecord/v1`.
- Record ID uses the frozen CC08 12-field preimage and the first 32 lowercase hexadecimal characters.
- Source authority/key, Identity v4, Report v3 and bank/pair v3 domains are exactly those frozen by CC08 revision 5.
- PostgreSQL and Python must produce identical canonical bytes, content digest and ID.
- `source_ordinal` is 1–4; sizes and dimensions are positive; output identifiers match the opaque-ID contract.
- Attestations are exactly `true / true / false`; authority state is `PRINCIPAL_ACCEPTED`.
- Supporting rows reject UPDATE and DELETE.
- Downgrade fails closed if any supporting row, Identity v4, Report v3, bank v3 or pair v3 exists.

## File ownership

One writer owns the entire collision domain.

Allowed:

```text
services/api/migrations/versions/demo_0008_d02_r2_source_authority.py
services/api/src/mirror_api/demo_models.py
services/api/src/mirror_api/demo_d02_r2_authority.py
services/api/tests/test_demo_d02_r2_authority.py
services/api/tests/test_demo_d02_r2_schema_authority.py
services/api/tests/test_demo_schema_authority_invariants.py
services/api/tests/test_demo_d02_schema_authority.py
services/api/tests/test_geometry_variant_authority_invariants.py
services/api/tests/test_offline_synthetic_source_authority_invariants.py
services/api/tests/test_synthetic_asset_qa_invariants.py
services/api/tests/test_variable_isolation_authority_invariants.py
.github/workflows/ci.yml
```

The final six invariant files and CI may change only for Demo head/history/boundary parity. They may not weaken formal
authority or unrelated gates.

Forbidden:

```text
services/api/migrations/versions/demo_0001* through demo_0007*
services/api/src/mirror_api/demo_d02_authority.py
router, OpenAPI, generated client, Celery and Provider code
dependencies and formal migrations/models
private registry implementation and all private evidence
ADR, acceptance records and MEMORY.md
```

The worker may not commit, push, create a PR, modify the integration branch outside these files or delegate further.

## Required validation

Pure tests must prove exact keys/order/domains/digests/IDs, complete `G→A→Q→P→Facts→Identity→manifest` equality,
explicit old-schema dispatch, old D00/recovered marker rejection, every independent splice class, cross-source full-field
re-sign rejection and deterministic replay.

An isolated real PostgreSQL 17 environment must prove:

```text
fresh base → demo_0008
demo_0007 → demo_0008
empty demo_0008 → demo_0007 → demo_0008
single head = demo_0008_d02_r2_source_auth
alembic check = no upgrade operations
metadata/schema drift = 0
v1/v2/v3 canonical bytes, digests and IDs unchanged
populated downgrade = fail closed
append-only and FK/Asset invariants
Identity v4 and Report/bank/pair v3 rules
concurrent source ordinal winner = 1
concurrent first ADMIT winner = 1
16-pair transaction, idempotent replay and failure rollback
```

SQLite, Mock DB and metadata-only checks cannot establish PostgreSQL PASS. Required quality gates are Ruff format/check,
strict mypy, targeted tests, full API tests, migration history/heads/check and `git diff --check`.

## Handoff and acceptance

The implementation worker returns only changed files, validation evidence and risks. The Integration Principal reviews
the actual diff, ensures historical migrations and formal DDL are untouched, creates the candidate commit, obtains an
independent Sol exact-SHA schema/security/compatibility review, reruns exact-archive PostgreSQL validation, pushes the
integration branch and requires same-SHA CI before creating a separate acceptance record.

Until that acceptance exists:

```text
D02_R2_POSTGRESQL_ADMISSION: CLOSED
D02_R2_MIGRATION_AUTHORITY: NOT_TASK_ACCEPTED
D02_R2_SOURCE_GENERATION: BLOCKED
D02_R2: NOT_TASK_ACCEPTED
D03: CLOSED
D04_B: CLOSED
D07_B: CLOSED
```
