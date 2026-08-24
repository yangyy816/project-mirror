# P3–P7 D02 Change Control 04 — Private Execution Identifier and Admission Authority

## Decision status

```text
CHANGE_CONTROL_ID: P3_P7_D02_CC_04
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
STATUS: PRINCIPAL_IMPLEMENTATION_CANDIDATE
BASE_SHA: dc43bc1acc793b6a9c74942147414d744662f70f
DISCOVERY: D02_PRIVATE_SCREENING_CUSTODY_PREFLIGHT
D02_PERSISTENCE: TASK_ACCEPTED_AT_BASE
D02_PRIVATE_SCREENING: PAUSED_PENDING_CC04_ACCEPTANCE
D02_TASK_ACCEPTED: NO
D03: BLOCKED
FORMAL_PHASE_AUTHORITY: FALSE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

The Principal's first real M3 smoke recovered the D00 registry authority and produced one face with 478 landmarks,
but the complete source graph could not begin safely. The accepted SQL/domain contract defines `source_output_id` and
`result_output_id` as opaque private-output registry identifiers, while the pure measurement module accidentally
restricted both to a 32-character hexadecimal entity-ID grammar. The same preflight also found that local v3 identity
admission persisted a generic SHA-256 without a frozen configuration preimage.

These are authority gaps, not private-runtime failures. This change control closes only those gaps before any D02
Report, selected result Asset, AssetVariant, QuestionBank or QuestionPair is inserted.

## Opaque output identifier parity

The sole output-ID grammar is:

```text
^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$
```

It applies identically to source observation subjects, result observation subjects, ResultM3 ID preimages, D02 pure
authority validators and PostgreSQL nested-evidence validators. Entity IDs such as Asset, case and ResultM3 record IDs
remain 32-character lowercase hexadecimal values.

The Principal must use the exact D00 registry output ID for each recovered source. A 32-hex alias, truncated hash,
caller-generated UUID, path, URI or locator is forbidden. This preserves the accepted chain:

```text
D00 registry output ID
-> source observation subject
-> facts
-> DemoSyntheticIdentity/v3
-> SourceAuthorityManifestEntry/v3
-> SourceM3RepeatRecord/v2
```

No private locator, path or byte enters a canonical payload, Git, CI artifact, log, Agent handoff or public API.

## Frozen local admission configuration

Schema:

```text
mirror.demo/D02LocalSyntheticAdmissionConfiguration/v1
```

Canonical payload:

```json
{
  "adult_synthetic_attestation_required": true,
  "identity_schema_version": "mirror.demo/DemoSyntheticIdentity/v3",
  "import_config_digest": "3cb5043028bec1c25e95822432db69a84b1eae9af3788201fafffe53f40acec2",
  "original_formal_identity_id_status": "UNKNOWN_REDACTED_NOT_RECOVERED",
  "production_release": "NOT_AUTHORIZED",
  "public_internet_egress": "DENIED_DURING_CORE_EXECUTION",
  "source_mode": "DEMO_LOCAL_IMPORTED_COPY",
  "source_output_id_contract": "OPAQUE_PRIVATE_OUTPUT_REGISTRY_ID_V1",
  "source_receipt_binding_required": true,
  "track": "DEMO_PROTOTYPE"
}
```

Using `demo-canonical-json-v1` and `sha256(schema_version + LF + canonical_json(payload))`:

```text
LOCAL_ADMISSION_CONFIG_DIGEST:
ef87c397af7db78211a6d2440f0cb3eef4214080f5117ff7be89b6400b663b21
```

This digest is deliberately distinct from `IMPORT_CONFIG_DIGEST`. The import digest identifies the v3 importer and
measurement/config bindings; the admission digest identifies the Demo-only decision to admit a registry-bound,
adult-attested local synthetic source under offline-core and non-production boundaries.

Every new local `DemoSyntheticIdentity/v3` ADMIT/REVOKE event must use this exact digest. Formal-reference rows and
legacy v1/v2 rows keep their historical admission authority byte-identical.

## Forward prototype migration

```text
MODULE: demo_0006_d02_private_execution_authority.py
REVISION: demo_0006_d02_private_exec
DOWN_REVISION: demo_0005_d02_quality_auth
PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
```

The migration adds one exact local-v3 admission check after an exclusive-lock audit. It does not modify formal tables,
accepted payload columns, API/OpenAPI, Worker registration, runtime/model assets or the D02 algorithm. Upgrade fails
closed if a pre-existing local v3 row uses another config. Downgrade fails closed while any local v3 authority exists;
an empty database may round-trip to `demo_0005` and re-upgrade.

## Required validation

```text
PYTHON_OPAQUE_OUTPUT_ID_PARITY
LOCAL_ADMISSION_CONFIG_DIGEST_REPLAY
PYTHON_WRONG_CONFIG_FAIL_CLOSED
POSTGRESQL_WRONG_CONFIG_DIRECT_SQL_REJECTED
ORM_MIGRATION_CHECK_PARITY
fresh -> demo_0006
demo_0005 -> demo_0006
demo_0006 -> demo_0005 -> demo_0006 when empty
populated local v3 downgrade -> FAIL_CLOSED
alembic heads: single head demo_0006_d02_private_exec
alembic check: schema drift 0
Ruff
strict mypy
focused and relevant complete regression
Gitleaks
scoped diff/private-byte-path scan
independent exact-SHA review
same-SHA CI
```

## Exit rule

Only the Integration Principal may accept this checkpoint. Until local validation, independent review and same-SHA CI
all pass, real source-graph construction remains paused and no private Report/import is permitted. Acceptance opens
the previously authorized Principal-only private screening; it does not accept D02, open D03, change formal P3–P7
status or authorize production use.
