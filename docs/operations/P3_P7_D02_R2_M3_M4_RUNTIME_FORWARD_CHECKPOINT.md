# D02-R2 Demo M3/M4 Runtime Forward Checkpoint

```text
TASK_ID: P3_P7_D02_R2_DEMO_M3_M4_RUNTIME_FORWARD_IMPLEMENTATION
TRACK: DEMO_PROTOTYPE
BASE_SHA: 5323f853838f9b48a0bf9a9d037ca9048e7cb2c7
STATUS: EXECUTING
OWNER_DECISION: APPROVE_DEMO_ONLY_M3_RUNTIME_FORWARD_IMPLEMENTATION
D02_R2_TASK_ACCEPTED: NO
PRODUCTION_RELEASE: NOT_AUTHORIZED
REAL_E2_SOURCE_ACCESS: FORBIDDEN_IN_THIS_TASK
PUBLIC_INTERNET_EGRESS: DENIED
```

## Gap map

| STAGE | EXISTING_IMPLEMENTATION | EXISTING_PATHS | MISSING_COMPONENT | WHY_BLOCKING | IMPLEMENTATION_OWNER | VALIDATION | FINAL_REAL_EXECUTOR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E2 source authority | Epoch 02 normalization, source authority, QA and packet validators | `demo_d02_r2_epoch2_admission.py` | none | not blocking | existing | packet replay tests | Integration Principal |
| M3 domain | normalization/QA orchestration and frozen measurement schemas | `synthetic_dataset/normalization_service.py`, `synthetic_dataset/orchestration_service.py`, `demo_measurement_quality.py` | reconstructable runtime/model handles and screening adapter | task-scoped runtime objects are not durable | this task | unit + bridge tests | injected qualified private Vision runtime |
| M4 domain | deterministic warp domain, OpenCV adapter and manifest-verifying loader | `synthetic_dataset/geometry_transform.py`, `providers/opencv_geometry.py` | reconstructable runtime handle and screening adapter | current D02 runner only accepts a Protocol | this task | unit + deterministic replay tests | injected qualified private OpenCV runtime |
| screening | complete fail-closed 4-source/48-case graph builder | `demo_d02_r2_screening_execution.py` | concrete runtime evidence bridge | tests currently replay fixture mappings | this task | targeted integration | existing runner |
| QuestionBank | R2 report/bank/pair builders and 16-pair authority | `demo_d02_r2_authority.py` | admission-ready bundle projection | production helper is not composed with runtime result | this task | cardinality tests | existing builders |
| PostgreSQL admission | single-transaction, idempotent/concurrent Epoch 02 coordinator | `demo_d02_r2_epoch2_admission.py` | none | not blocking | existing | real PostgreSQL tests | Integration Principal |

## Frozen internal boundary

- A durable source descriptor contains only public scalar authority: source ID, ordinal, SHA-256, MIME type,
  dimensions, byte length, generation identity, provenance identity and schema version.
- Runtime and model recipes are canonical typed values with deterministic digests. They bind the existing D02
  runtime/model/topology/measurement authority and remain Demo-only, synthetic-only and offline-only.
- Runtime/model handles are derived from the ordered four-source descriptor manifest plus recipe/model identities.
  They contain no path, Prompt, raw bytes, locator, secret or task-scoped object.
- A factory reconstructs an executor only when an injected backend advertises the exact runtime/model identity.
  Backend injection is the Principal-owned runtime-material boundary; no discovery, fallback or download exists.
- Executors validate bytes against the durable descriptor before exactly one algorithm call. They reject count,
  order, digest, media envelope, recipe/model identity and output-schema drift.
- The screening bridge adapts validated algorithm fields into the existing `run_offline_screening` Protocols.
  The existing runner remains the sole full-graph validator; no partial report is admission-ready.
- No migration, ORM, public API, central router, OpenAPI, generated client or production capability changes.

## Completion guard

Synthetic fixtures may prove the code path but never count as real E2 execution. This task must stop after a local
candidate commit and one independent exact-SHA review. The Integration Principal alone may bind the four real E2
sources, construct private runtime material, execute the final graph, perform PostgreSQL admission and decide D02.

## Candidate identity

```text
RUNTIME_RECIPE_VERSION: demo-m3-m4-runtime-recipe-v1
RUNTIME_RECIPE_DIGEST: be8ed45430d4cc1d50cbba5baab8510fa48694dfd0093c182578a313af506243
MODEL_IDENTITY_DIGEST: adcc9e9a215ef65332db915509851f7beedfa88273823b49e8471f69813b28c4
MODEL_CONFIG_DIGEST: 0bd8fc187095130fc830f73a8ecc0b91f8784b3683f77d247ff5416d02e3c86e
WEIGHTS_DIGEST: 64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff
RUNTIME_MANIFEST_DIGEST: 6d739c2e269128ea7bc09358203aa7efe0714484b1a216a9f401353a243135ed
TOPOLOGY_DIGEST: 85eea84eef15dd963e06382d6e61f7357029d9901acc935731ecaa7eab856b63
MEASUREMENT_CONFIG_DIGEST: ab5f745641a6f4539a8010fe32dda82b6c1066a8cb97d36ae17de737b901e8d3
THRESHOLD_CONFIG_DIGEST: 4b18fd2543abd8e2a86c2dfc339aefbd9ed0e9d53d5a8e18b49ba21252e9488e
M3_RUNTIME_HANDLE_SCHEMA: mirror.demo/D02R2M3RuntimeHandle/v1
M3_MODEL_HANDLE_SCHEMA: mirror.demo/D02R2M3ModelHandle/v1
```

## Validation snapshot

```text
RUFF_LINT: PASS (2 task Python files)
RUFF_FORMAT: PASS (2 task Python files)
STRICT_MYPY: PASS (runtime-forward source)
RUNTIME_FORWARD_AND_SCREENING: PASS (34 tests, offline container)
POSTGRESQL_EPOCH2_ADMISSION: PASS (6 tests, PostgreSQL 17.6)
TRANSACTION_ROLLBACK: PASS (zero partial rows)
IDEMPOTENCY_AND_COLLISION: PASS
CONCURRENT_ADMISSION: PASS
NO_NETWORK: PASS (--pull=never plus no-network/internal-only containers)
ALEMBIC_HEAD: demo_0009_d02_r2_e2_adm
PRIVATE_PATH_OR_CREDENTIAL_SCAN: PASS (0 matches in task files)
PUBLIC_CONTRACT_CHANGE: NO
MIGRATION_OR_ORM_CHANGE: NO
REAL_E2_SOURCE_ACCESSED: NO
NEW_IMAGEGEN_CALLS: 0
REAL_E2_M3_M4_EXECUTED: NO
REAL_POSTGRESQL_ADMISSION: NO
MEMORY_UPDATED: NO
PUSHED: NO
```

## Remaining gate

Create one local candidate commit, then run exactly one independent exact-SHA review limited to the Owner-approved
blocking categories. Do not execute real E2 sources, write real admission rows, update durable state, push, or accept
D02 in this task.
