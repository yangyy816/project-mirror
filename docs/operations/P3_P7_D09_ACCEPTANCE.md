# P3–P7 D09 Acceptance Evidence

## Candidate status

```text
TASK: D09 — P7 event ledger authority
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
CHANGE_CONTROL: CC-P3-P7-DEMO-D09-02
IMPLEMENTATION_SHA: 17b790de6393434430d8462195a87c548c1fa15a
IMPLEMENTATION_PARENT: cacf86cfebb1a32598228c0dec0cff711514a92d
IMPLEMENTATION_TREE: 9b22612a9a27590d9497ef6151c95f0196f41525
BRANCH: codex/p3-p7-core-demo
CURRENT_STATUS: TASK_ACCEPTED
PRINCIPAL_TASK_ACCEPTANCE: TASK_ACCEPTED
INDEPENDENT_INITIAL_REVIEW: REPAIR_REQUIRED
INDEPENDENT_REPAIRED_SNAPSHOT_REVIEW: PASS
INDEPENDENT_EXACT_COMMIT_REVIEW: PASS
SAME_SHA_CI_RUN: 32701906246
D10: BLOCKED_PENDING_D05_AND_D06_TASK_ACCEPTED
FORMAL_P3_P7_STATUS: UNCHANGED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

This acceptance covers only the Demo P7 digest-chained PreferenceEvent ledger, atomic Final Save application service,
AcceptedVisualEpisode admission authority and the branch-local PostgreSQL provenance hardening migration. It does not
accept the D10 AestheticProfile or Context Compiler, rebuild/reset materialization, delete propagation, next-session
recall, Web, a formal P7 Gate, real-user validity or production use.

## Accepted file boundary

The implementation commit changes exactly nine files:

```text
.github/workflows/ci.yml
  blob: a9f2ff683188efa9c5ee9f98bc4d521d89ec3bd7

services/api/migrations/versions/demo_0004_d09_episode_provenance.py
  blob: 21af0829e5cd2b816b23312b5562c3fb0275fede

services/api/src/mirror_api/demo_preference_ledger.py
  blob: d1ab62fc540b4e317058d100a69a42c7882d761e

services/api/tests/test_demo_preference_ledger.py
  blob: 3ff46d2df36b2270ba51547e33104c6fe7d7471c

services/api/tests/test_demo_schema_authority_invariants.py
  blob: 49dc306e7d30e32d7a437eeef0f0c53aff937a69

services/api/tests/test_geometry_variant_authority_invariants.py
  blob: ede79574ec79bd634561d0ad47030aaf6ab82942

services/api/tests/test_offline_synthetic_source_authority_invariants.py
  blob: e734055bbe88110cbbcf408d8cc633f4bd46eca8

services/api/tests/test_synthetic_asset_qa_invariants.py
  blob: 89e0c862c197f8ea9b3c6cde47e58777d48c3b65

services/api/tests/test_variable_isolation_authority_invariants.py
  blob: f6f76ee8e9312f57ba0aa095a05abdeb322a6e34
```

The four formal-authority test changes only advance their expected Demo migration head; they do not change formal
tables, constraints or evidence semantics. No ORM model, router, OpenAPI, generated client, Celery registration, Web
file, dependency, lockfile, private byte or formal migration is part of the commit.

## Accepted ledger and Final Save authority

The accepted domain provides:

- actor-scoped PostgreSQL advisory serialization and contiguous `event_sequence` allocation;
- digest-chained, append-only PreferenceEvent authority with explicit UTC `occurred_at` and independent audit time;
- canonical payload parity between application and PostgreSQL with no raw float authority;
- caller-owned atomic Final Save, creating exactly one `IMAGE_ACCEPTED` event and one AcceptedVisualEpisode;
- complete actor/session/editing-session, image trajectory, terminal RESULT plan, operation, ToolRun, verifier and Asset
  lineage validation;
- exact Final Save profile/context/instruction provenance and terminal-plan tool-registry equality;
- one canonical winner for concurrent Final Saves of the same accepted image;
- rollback of event, episode and sequence allocation on validation failure or cancellation after event flush;
- strict-earlier RESET watermark validation without destructive history mutation; and
- explicit negative evidence showing event-only acceptance, rejection, learning-disabled and lock/unlock events do not
  materialize or reinforce stable Profile or Context authority inside D09.

An `IMAGE_ACCEPTED` event by itself remains acceptance feedback, not Final Save. Only a valid
`DemoAcceptedVisualEpisode` is the Demo Final Save provenance authority. D09 does not compile a stable profile and does
not claim that reset/delete propagation or next-session recall is complete.

## PostgreSQL provenance hardening

The branch-local migration is:

```text
REVISION: demo_0004_d09_episode_prov
DOWN_REVISION: demo_0003_d02_import_auth
PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
TABLE_OR_COLUMN_CHANGE: NONE
ORM_MODEL_CHANGE: NONE
PUBLIC_API_CHANGE: NONE
```

It strengthens `mirror_demo_validate_accepted_episode()` so PostgreSQL proves:

```text
episode.profile_digest
  = editing_session.desired_delta_profile_digest
  = terminal_result_plan.desired_delta_profile_digest

episode.context_digest
  = editing_session.context_digest

episode.instruction_digest
  = editing_session.instruction_digest
  = terminal_result_plan.instruction_digest
```

Upgrade and downgrade both acquire `ACCESS EXCLUSIVE` on `demo_accepted_visual_episodes` until transaction commit.
Upgrade audits existing rows without rewriting evidence. Populated downgrade fails closed. Empty downgrade restores the
frozen legacy function; the regression reconstructs an independent `demo_0003` baseline from formal `0014`, compares
`pg_get_functiondef` after downgrade, and then re-upgrades to the exact hardened definition.

## Preserved negative evidence and bounded repair

The initial implementation review did not find a production-code or migration correctness defect, but rejected the
snapshot because two mandatory PostgreSQL regressions were not mutation-proof:

1. terminal-plan profile/instruction equality was covered only through application behavior; and
2. the downgrade function comparison reused a value produced by the same downgrade instead of an independently rebuilt
   `demo_0003` baseline.

The Principal kept migration and production bytes frozen, added isolated direct-SQL profile and instruction drift
tests, and rebuilt the legacy baseline through `0014 -> demo_0003`. The repaired snapshot review returned
`PASS_FOR_COMMIT: YES`; the exact commit-bound review then confirmed parent, tree, nine paths, nine blobs and semantic
equivalence with no P0, P1 or P2 finding.

## Local integration validation

The real PostgreSQL validation used the task-scoped `mirror_p3p7_principal_d09_e1` namespace. Its Docker network was
`internal=true`; the repository was mounted read-only into Linux/Python 3.13 test containers. Localhost/Docker-internal
PostgreSQL remained available while public internet egress was absent.

```text
REPAIRED_TARGETED_REGRESSIONS: 3/3 PASS
COMPLETE_DEMO_SCHEMA_SUITE: 77/77 PASS, 0 SKIP
D09_LEDGER_SUITE: 27/27 PASS, 0 SKIP
AFFECTED_FORMAL_AUTHORITY_REGRESSIONS: 34/34 PASS, 0 SKIP
D02_SCHEMA_REGRESSIONS: 30/30 PASS, 0 SKIP
RUFF_FORMAT: PASS
RUFF_CHECK: PASS
STRICT_MYPY: 133 source files PASS
ALEMBIC_HEADS: demo_0004_d09_episode_prov, SINGLE_HEAD
ALEMBIC_CHECK: NO_NEW_UPGRADE_OPERATIONS
FORMAL_NON_DEMO_DDL_DRIFT: 0
GIT_DIFF_CHECK: PASS
SCOPED_GITLEAKS_8_28_0: PASS, 0 findings across 9 files
PUBLIC_INTERNET_EGRESS: DENIED_FOR_CORE_POSTGRESQL_VALIDATION
PRIVATE_INPUT: NONE
PRODUCTION_PROVIDER_CALLS: 0
```

The first database test command used an unsupported `asyncpg` URL and was rejected by the repository configuration
Gate before test execution. All accepted results above use the configured `postgresql+psycopg` authority. Two later
container attempts also stopped before collection because of a malformed Windows mount argument and a correctly
rejected CI/local-runner mismatch; neither was counted as test evidence and no assertion or threshold was changed.

## Exact-SHA CI evidence

GitHub Actions run [32701906246](https://github.com/yangyy816/project-mirror/actions/runs/32701906246) completed
successfully for exact implementation SHA `17b790de6393434430d8462195a87c548c1fa15a`.

```text
secret-scan: PASS
docker-validation: PASS
quality-and-integration: PASS

PYTHON_FORMAT: 241 files
RUFF: PASS
MYPY: 133 source files PASS
PYTHON_TESTS: 1033 passed, 1 existing optional skip
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
DOCKER_TOPOLOGY: PASS
```

The downloaded Demo boundary artifact binds the exact SHA, `demo_0004_d09_episode_prov`, unchanged formal authority
`0014_m5_eval_authority` and `PRODUCTION_RELEASE: NOT_AUTHORIZED`. Five artifacts are present and unexpired:

| Artifact                      |         ID | Result                          |
| ----------------------------- | ---------: | ------------------------------- |
| `gitleaks-results.sarif`      | 9510809854 | one run, zero findings          |
| `project-docker-evidence`     | 9510852134 | topology evidence present       |
| `playwright-install-evidence` | 9511012564 | install evidence present        |
| `demo-prototype-ci-boundary`  | 9511021406 | exact SHA/head/boundary matched |
| `project-audit-evidence`      | 9511028811 | licenses/SBOM/Celery present    |

The workflow's Phase 1/P2 formal evidence generators were intentionally skipped on the prototype head; their
deterministic regression tests still passed. The only annotation is GitHub's Node 20 action-deprecation notice under a
forced Node 24 runtime; no D09 product or validation step failed.

## Repository and concurrent-work preservation

Immediately before the authorized normal non-force push, the remote was reverified as
`yangyy816/project-mirror`, `PUBLIC`, matching the accepted D01 baseline, and the remote Demo branch still pointed to the
implementation parent. Remote and local refs then reached the same exact implementation SHA. No formal worktree change
was absorbed.

The D02 Packet B work remains isolated in its auxiliary worktree and was not staged or modified by D09. Superseded P4
`c9e2e9f...` and P6 `c6544c5...` handoffs were not cherry-picked. The protected P6 topic acceptance draft remained
outside the integration worktree and was not touched.

## Principal decision

```text
D09: TASK_ACCEPTED
P7_PREFERENCE_EVENT: DEMO_PROTOTYPE_DOMAIN_ACCEPTED
P7_EVENT_DIGEST_CHAIN: DEMO_PROTOTYPE_DOMAIN_ACCEPTED
P7_ACCEPTED_VISUAL_EPISODE: DEMO_PROTOTYPE_DOMAIN_ACCEPTED
P7_EVIDENCE_PRECEDENCE: PARTIAL_D09_ONLY
P7_PROFILE_COMPILER: NOT_VERIFIED
P7_CONTEXT_COMPILER: NOT_VERIFIED
P7_PROFILE_REBUILD: NOT_VERIFIED
P7_RESET_ROLLBACK: PARTIAL_EVENT_AUTHORITY_ONLY
P7_DELETE_PROPAGATION: NOT_VERIFIED
P7_NEXT_SESSION_RECALL: NOT_VERIFIED
D10: BLOCKED_PENDING_D05_AND_D06_TASK_ACCEPTED
ALGORITHMIC_PROTOTYPE_PLATFORM: NOT_VERIFIED
LOCAL_WEB_AGENT: NOT_VERIFIED
FORMAL_P3_P7_STATUS: UNCHANGED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

D09 acceptance satisfies one prerequisite for D06 and D10 but opens neither task by itself. D06 still requires D05 and
D07-B; D10 still requires D05 and D06. The next accepted integration base is published only after this acceptance
closure commit receives same-SHA CI.
