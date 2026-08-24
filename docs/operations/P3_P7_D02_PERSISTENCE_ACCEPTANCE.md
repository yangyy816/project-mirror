# P3–P7 D02 Measurement-Quality Persistence Acceptance

## Decision

```text
TASK: D02 — synthetic identities / mini bank / pair QA
CHECKPOINT: D02_MEASUREMENT_QUALITY_PERSISTENCE
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
ACCEPTED_BASE_SHA: 1aaccb83430db987af87d2cc23552adf0a73111d
NEGATIVE_CANDIDATE_SHA: 68545daeaf9543ff700c5cff2883639ebb28f04b
FINAL_REPAIR_SHA: f245441f23f42aaf923995ca6c7d4a490b72b429
FINAL_REPAIR_PARENT: 68545daeaf9543ff700c5cff2883639ebb28f04b
FINAL_TREE: 09535b02941ed0d34a45b57d7aa6aac4b39d621b
INDEPENDENT_SOL_EXACT_SHA_REVIEW: PASS
INDEPENDENT_SOL_FINDINGS_P0_P1_P2_P3: 0/0/0/0
SAME_SHA_CI_RUN: 32770366896
D02_MEASUREMENT_QUALITY_PERSISTENCE: TASK_ACCEPTED
D02_PRIVATE_SCREENING: EXECUTION_READY_AFTER_ACCEPTANCE_CHECKPOINT_CI
D02_TASK_ACCEPTED: NO
D03: BLOCKED
R_DEMO_03: OPEN
FORMAL_P3_P7_STATUS: UNCHANGED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

This checkpoint accepts the branch-local PostgreSQL and ORM authority required to persist the already accepted D02
measurement-quality graph. It does not accept private screening results, the real 4-source/48-case execution, the
selected 16-pair bank, D02 as a whole, D03, a formal P3–P7 Gate, real-face processing or production use.

The first implementation candidate remains immutable negative evidence. Green targeted tests on that candidate did
not override the independent review findings. The final tree is accepted only after the forward repair, exact-SHA
review, exact-archive PostgreSQL validation and same-SHA CI described below.

## Accepted file boundary

The complete implementation from the accepted base to the repaired SHA contains these ten tracked paths:

```text
.github/workflows/ci.yml
services/api/migrations/versions/demo_0005_d02_measurement_quality_authority.py
services/api/src/mirror_api/demo_models.py
services/api/tests/test_demo_d02_authority.py
services/api/tests/test_demo_d02_schema_authority.py
services/api/tests/test_demo_schema_authority_invariants.py
services/api/tests/test_geometry_variant_authority_invariants.py
services/api/tests/test_offline_synthetic_source_authority_invariants.py
services/api/tests/test_synthetic_asset_qa_invariants.py
services/api/tests/test_variable_isolation_authority_invariants.py
```

The repair itself changes only the migration, Demo ORM and three D02 test files. The CI and four formal-authority test
changes only advance the expected branch-local Demo head; they do not change a formal table, formal migration,
production setting, public API, router, OpenAPI, generated client, Celery registration, dependency or provider.

## Accepted persistence authority

```text
REVISION: demo_0005_d02_quality_auth
DOWN_REVISION: demo_0004_d09_episode_prov
PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
```

The accepted persistence layer provides:

- v3 Demo synthetic-identity admission and immutable local source authority;
- complete Report v2, QuestionBank v2 and QuestionPair v2 graph validation without adding a competing formal Asset
  authority;
- exact PostgreSQL validation of fixed-18/ppm measurement authority, three-repeat SourceM3 and ResultM3 evidence,
  48 measurement Gates, image/variant lineage, pHash, pair QA, eligibility and selected-bank authority;
- explicit equality between each ResultM3 observation and its Gate target raw value, five control raw values,
  repeat-record digest and unsupported reason;
- exact binding of source-P2, dimension-authority and geometry-ontology roots to the accepted peer/config values;
- ORM/PostgreSQL parity for the formal-v3 exclusion in the same named source-mode CHECK;
- advisory-serialized v3 admission, append-only evidence, legacy byte preservation and populated downgrade
  fail-closed behavior; and
- single-head lifecycle recovery to the frozen D09 migration without changing the D09 AcceptedVisualEpisode function.

The accepted roots are:

```text
SOURCE_P2_CANDIDATE_MANIFEST:
  eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4
DIMENSION_AUTHORITY_MANIFEST:
  d4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a
GEOMETRY_ONTOLOGY:
  d902fe2cfdf69db9f62ccc2e5fa7c569227d652f1204aa683742fc3c592f38b9
```

## Preserved negative evidence and repair

Independent review of `68545da...` found three mandatory defects:

1. ResultM3 observations could be fully re-signed while a Gate retained different target/control/unsupported values.
2. source-P2, dimension and geometry roots could be replaced through a fully re-signed alternate-root graph.
3. the ORM source-mode CHECK omitted the migration's formal-v3 exclusion.

The repair adds PostgreSQL projection equality for every repeat, binds all three accepted roots across the nested graph,
synchronizes the ORM CHECK and adds seven real-PostgreSQL regressions. The three observation attacks re-sign the
observation, ResultM3 records, result-repeat certificate, Gate, pair wrappers, outcomes/selection and report authority.
The three root attacks rebuild a complete internally self-consistent alternate-root graph. Rejection therefore occurs
at the new authority equality, not at a stale enclosing digest.

The independent final reviewer verified exact SHA, parent, tree, merge-base, full/repair diff and frozen contracts and
returned:

```text
PASS_FINDINGS_NONE: YES
P0: 0
P1: 0
P2: 0
P3: 0
```

The reviewer did not claim `TASK_ACCEPTED`; that decision remains this Principal record.

## Local exact-SHA validation

`git archive` of the exact repaired SHA produced tree `09535b0...` and archive SHA-256
`53ce6c77b698a7491ea73c5fdda80320a3a53e5813585cb5f5b30923020c1971`. The archive was mounted read-only into
Linux/Python 3.13 containers. PostgreSQL used an internal-only Docker network with no published host port.

```text
D02_COMPLETE_MATRIX: 480/480 PASS, 0 SKIP
NEW_FULLY_RESIGNED_ATTACKS_AND_PARITY: 7/7 PASS
D09_MIGRATION_REGRESSION: 6/6 PASS
PYTHON_FORMAT: 244 files PASS
RUFF: PASS
STRICT_MYPY: 134 source files PASS
ALEMBIC_0004_TO_0005_TO_0004_TO_0005: PASS
ALEMBIC_CHECK: NO_NEW_UPGRADE_OPERATIONS
ALEMBIC_HEADS: demo_0005_d02_quality_auth, SINGLE_HEAD
EXACT_ARCHIVE_GITLEAKS_8_28_0: PASS, 0 findings over about 8.04 MB
SCOPED_PRIVATE_LOCATOR_SCAN: PASS
PUBLIC_INTERNET_EGRESS: DENIED_FOR_CORE_POSTGRESQL_VALIDATION
PRIVATE_INPUT: NONE
PRODUCTION_PROVIDER_CALLS: 0
```

## Exact-SHA CI evidence

GitHub Actions run [32770366896](https://github.com/yangyy816/project-mirror/actions/runs/32770366896) completed
successfully for exact repaired SHA `f245441f23f42aaf923995ca6c7d4a490b72b429`.

```text
secret-scan: PASS
docker-validation: PASS
quality-and-integration: PASS

PYTHON_FORMAT: 244 files
RUFF: PASS
MYPY: 134 source files PASS
PYTHON_TESTS: 1348 passed, 1 existing optional skip
PHASE_1: 1 passed
P2_M1: 98 passed
P2_M2: 52 passed
P2_M3: 46 passed
TYPESCRIPT_TESTS: 54 passed
PLAYWRIGHT: 5 passed
POSTGRESQL_MIGRATION_LIFECYCLE: PASS
OPENAPI_CONTRACT_DRIFT: PASS
DEMO_BOUNDARY: PASS
DEPENDENCY_AUDITS: NO_KNOWN_VULNERABILITIES
SBOM: GENERATED
DOCKER_TOPOLOGY: PASS
```

The exact boundary artifact records:

```text
TRACK: DEMO_PROTOTYPE
COMMIT_SHA: f245441f23f42aaf923995ca6c7d4a490b72b429
DEMO_MIGRATION_HEAD: demo_0005_d02_quality_auth
FORMAL_EVIDENCE_GENERATORS: NOT_RUN_ON_PROTOTYPE_HEAD
FORMAL_HEAD_AUTHORITY: 0014_m5_eval_authority
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

Five same-SHA artifacts were present and unexpired when reviewed:

| Artifact                      |         ID | Result                          |
| ----------------------------- | ---------: | ------------------------------- |
| `gitleaks-results.sarif`      | 9535955296 | one run, zero findings          |
| `project-docker-evidence`     | 9536003874 | topology evidence present       |
| `playwright-install-evidence` | 9536575807 | bounded install evidence        |
| `demo-prototype-ci-boundary`  | 9536587617 | exact SHA/head/boundary matched |
| `project-audit-evidence`      | 9536596361 | licenses/SBOM/Celery present    |

The only workflow annotations are GitHub's Node 20 action-deprecation notices while actions are forced onto Node 24;
no D02, migration, browser, Docker, secret-scan or integration step failed.

## Repository, private and formal boundaries

Before the authorized normal non-force push, the remote was reverified as `yangyy816/project-mirror`, `PUBLIC`, and
the remote Demo branch still pointed to the accepted parent. The normal push advanced only
`codex/p3-p7-core-demo`; the formal worktree, formal migration head and production authorization were not changed.

The complete scoped diff and exact archive contain no private locator/path, private runtime byte, synthetic image,
landmark payload, secret or production credential. Private screening remains subject to Principal custody, exact
registry/digest verification and task-scoped read-only handoff. No sub-agent receives disk-discovery authority.

## Mandatory negative evidence

This checkpoint does not turn pure structural fixtures into real screening evidence. The following remain true:

```text
REAL_SOURCE_M3_12: NOT_VERIFIED
REAL_M4_EXECUTIONS_96: NOT_VERIFIED
REAL_RESULT_M3_144: NOT_VERIFIED
REAL_48_CASE_MEASUREMENT_GATES: NOT_VERIFIED
REAL_48_CASE_MANUAL_REVIEW: NOT_VERIFIED
REAL_52_IMAGE_EXACT_SHA_GATE: NOT_VERIFIED
REAL_1326_PHASH_OBSERVATIONS: NOT_VERIFIED
REAL_24_PAIR_SCREENING: NOT_VERIFIED
REAL_SELECTED_16_PAIR_BANK: NOT_VERIFIED
P4_MULTI_DIMENSION_ACTIVE_ROUTING: NOT_VERIFIED
ALGORITHMIC_PROTOTYPE_PLATFORM: NOT_VERIFIED
LOCAL_WEB_AGENT: NOT_VERIFIED
```

## Principal decision and next boundary

```text
D02_MEASUREMENT_QUALITY_PERSISTENCE: TASK_ACCEPTED
D02_PRIVATE_SCREENING: EXECUTION_READY_AFTER_ACCEPTANCE_CHECKPOINT_CI
D02_TASK_ACCEPTED: NO
D03: BLOCKED
D04_B: CLOSED_PENDING_D02_AND_D03_TASK_ACCEPTED
D07_B: CLOSED_PENDING_D02_AND_D03_TASK_ACCEPTED
R_DEMO_03: OPEN
FORMAL_P3_P7_STATUS: UNCHANGED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

After this acceptance record itself receives same-SHA CI, the next bounded D02 action is Principal-custodied offline
screening with the frozen 4-source/48-case authority and accepted M3/M4 handles. It may not scan for private inputs,
acquire a different runtime, change thresholds, fabricate Gate values, reuse structural fixtures as results or open
D03 before full D02 acceptance.
