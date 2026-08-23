# P3–P7 D01-B Acceptance Evidence

## Candidate status

```text
TASK: D01-B — Schema authority
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
BASE_SHA: d134517fa97132b180a82c69c617b8f65d3b282e
BRANCH: codex/p3-p7-core-demo
REVISION: demo_0001_p3_p7_core
DOWN_REVISION: 0014_m5_eval_authority
REMEDIATION_CANDIDATE: dd39b37f5cf9286be0153dd034737865ebf3e0cd
REMEDIATION_CANDIDATE_TREE: 13b2b09aa507194fa4a5da15cb1c81213dfb0f60
STATUS: TASK_ACCEPTED
PRINCIPAL_TASK_ACCEPTANCE: TASK_ACCEPTED
INDEPENDENT_SOL_IMPLEMENTATION_REVIEW: PASS
D01_C: EXECUTION_READY
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

This checkpoint implements only the frozen Demo persistence authority. It does not implement or accept the D01-C API
skeleton, any P3–P7 runtime/domain algorithm, Worker registration, Web, OpenAPI generation or D02–D12 behavior.

## Candidate scope

Schema implementation:

```text
services/api/migrations/env.py
services/api/migrations/versions/demo_0001_p3_p7_core.py
services/api/src/mirror_api/demo_models.py
```

Schema and regression tests:

```text
services/api/tests/test_demo_schema_authority_invariants.py
services/api/tests/test_geometry_variant_authority_invariants.py
services/api/tests/test_offline_synthetic_source_authority_invariants.py
services/api/tests/test_synthetic_asset_qa_invariants.py
services/api/tests/test_variable_isolation_authority_invariants.py
```

Governance evidence:

```text
docs/operations/P3_P7_DEMO_SCHEMA_REUSE_MATRIX.md
docs/operations/P3_P7_DEMO_RISK_REGISTER.md
docs/operations/P3_P7_D01_B_CHANGE_CONTROL_01.md
docs/operations/P3_P7_D01_B_ACCEPTANCE.md
```

The four existing formal authority test files only update post-`upgrade head` and failed-downgrade revision assertions
from the old formal head to the branch-local Demo head. Their formal migration behavior, fixtures and fail-closed
expectations are unchanged.

## Physical authority result

Real PostgreSQL metadata at the final Demo head reports:

```text
REVISION: demo_0001_p3_p7_core
DEMO_TABLE_COUNT: 27
AUTHORITY_TRIGGER_COUNT: 27
TERMINAL_BINDING_CONSTRAINT_TRIGGER_COUNT: 4
FORMAL_TABLE_DDL_CHANGE: NONE
```

The 27 tables preserve all 26 planned logical entities and add the cross-cutting `demo_job_bindings` authority:

```text
Session/identity: demo_actors, demo_sessions, demo_synthetic_identities
P3: demo_face_observations, demo_face_observation_repeats,
    demo_baseline_face_models, demo_self_states
P4: demo_question_banks, demo_question_pairs, demo_questionnaire_runs,
    demo_questionnaire_steps
P5: demo_desired_delta_profiles, demo_style_profiles, demo_identity_constraints,
    demo_self_transfer_runs, demo_reference_profiles
P6: demo_editing_sessions, demo_image_versions, demo_edit_plans,
    demo_edit_operations, demo_tool_runs, demo_verification_results
P7: demo_preference_events, demo_accepted_visual_episodes,
    demo_aesthetic_profiles, demo_context_compilations
Cross-cutting: demo_job_bindings
```

Formal `Asset`, `AssetVariant`, `Job` and `JobAttempt` remain the byte/lineage/execution authorities and are referenced
through foreign keys and namespace checks. No Demo column, trigger, constraint, index or current pointer is added to a
formal table.

The five physical-reuse proofs are:

```text
NO_CAPABILITY_LOSS: PASS_FOR_REMEDIATION_CANDIDATE
NO_EVIDENCE_LOSS: PASS_FOR_REMEDIATION_CANDIDATE
NO_API_LOSS_FROM_PHYSICAL_MAPPING: PASS_FOR_REMEDIATION_CANDIDATE
NO_REBUILDABILITY_LOSS: PASS_FOR_REMEDIATION_CANDIDATE
NO_FORMAL_AUTHORITY_POLLUTION: PASS_FOR_REMEDIATION_CANDIDATE
```

`NO_API_LOSS_FROM_PHYSICAL_MAPPING` means the schema can represent the frozen API authority. It does not claim that
D01-C routes, OpenAPI or generated TypeScript exist.

## Canonical digest and JSON authority

The migration installs `demo-canonical-json-v1` PostgreSQL authority. Every Demo table has a digest guard that:

- requires a canonical object payload;
- accepts only integer numeric leaves in digest authority;
- canonicalizes object key ordering and preserves semantic array order;
- rejects non-finite/fractional/raw-float authority and mismatched structured columns;
- computes SHA-256 from schema version plus canonical UTF-8 payload;
- rejects direct update/delete according to the frozen mutation class.

ORM payload columns use PostgreSQL `JSONB`. The three optional semantic JSONB fields use `none_as_null=True`, so Python
`None` persists as SQL `NULL`; explicit JSON `null` remains a distinct invalid JSON value and fails the database shape
checks:

```text
demo_questionnaire_steps.response_snapshot
demo_self_transfer_runs.measured_delta
demo_self_transfer_runs.non_target_drift
```

Digest-authoritative posterior/profile quantities are integer fields such as ppm; raw Python or PostgreSQL float is
not a canonical authority.

## Ownership, evidence and lifecycle authority

- Composite actor/session foreign keys prevent opaque IDs from substituting for authorization.
- `mirror_demo_evidence_owned_by()` requires every persisted profile/context evidence digest to resolve to an actual
  Demo authority owned by the same actor. Same-actor historical sessions remain eligible for next-session recall;
  unknown and cross-actor evidence fail closed.
- Typed Job bindings validate actor, optional session, endpoint operation, request digest, formal Job namespace and
  target ownership. PostgreSQL uniqueness selects one concurrent canonical idempotency winner.
- Preference events use actor-scoped sequence and previous-digest chaining with PostgreSQL advisory transaction locks.
- Synthetic admission freezes the formal canonical Asset and deterministic QA snapshot, serializes successor selection,
  rejects stale ADMIT rows and permits evidence-preserving post-tombstone REVOKE.
- ImageVersion resolves exact plan/operation/ToolRun/AssetVariant/verifier authority, freezes source/result SHA values
  and requires a commit-time bidirectional VerificationResult edge. AcceptedVisualEpisode traverses the complete
  root-to-leaf execution graph.

Actor/session/editing-session terminal headers are materialized only with matching append-only lifecycle events in the
same transaction. Four `DEFERRABLE INITIALLY DEFERRED` constraint triggers validate both directions at commit:

```text
header without event: rejected
event without header: rejected
actor/session/editing target mismatch: rejected
timestamp mismatch: rejected
matching header + event transaction: accepted
```

The implementation preserves the matrix's frozen PreferenceEvent target allowlist. Session and editing-session
lifecycle targets use their exact, schema-validated `signal` forms rather than silently widening the derived-target
`target_type` contract.

## Migration lifecycle

```text
PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
```

Executed on an empty isolated PostgreSQL database from a read-only source mount in a temporary container attached only
to `mirror-d01b-remediation-01`, a Docker `internal=true` network with no published PostgreSQL port. All proxy variables
were empty; Docker-internal PostgreSQL remained reachable while public egress was unavailable by topology:

```text
fresh -> demo_0001_p3_p7_core: PASS
demo_0001_p3_p7_core -> 0014_m5_eval_authority: PASS
0014_m5_eval_authority -> demo_0001_p3_p7_core: PASS
demo_0001_p3_p7_core -> 0014_m5_eval_authority: PASS
0014_m5_eval_authority -> demo_0001_p3_p7_core: PASS
ALEMBIC_HEADS: exactly demo_0001_p3_p7_core
ALEMBIC_CURRENT: demo_0001_p3_p7_core
ALEMBIC_CHECK: No new upgrade operations detected
ALEMBIC_CYCLE_WARNING: five deferred execution tables cannot be topologically sorted
SUPPLEMENTARY_ORM_DATABASE_FK_PARITY: PASS, 27 tables / 85 foreign keys
SCHEMA_DRIFT: 0, including explicit cycle-FK parity
FORMAL_NON_DEMO_TABLE_DDL_SHA256_AT_0014: 3a24974137509a6b81be483f667d5060ca89749c70b7a46ac365285ca06927e7
FORMAL_NON_DEMO_TABLE_DDL_SHA256_AT_DEMO_HEAD: 3a24974137509a6b81be483f667d5060ca89749c70b7a46ac365285ca06927e7
FORMAL_TABLE_DDL_DIFF: 0
```

Populated downgrade tests prove that Demo authority rows, `demo_p3_p7.*` Jobs/JobAttempts and
`demo_p3_p7_` AssetVariants prevent object removal before any destructive DDL. Existing M3/M4/M5 durable-authority
downgrade tests still fail closed and now correctly assert that the failed transaction restores the branch-local Demo
head.

Future formal absorption must create a new forward migration from the then-current formal head and an explicit
promotion/conversion strategy. This migration cannot become the formal production revision.

## Validation evidence

All remediation validation used a byte-faithful source snapshot created with `git -c core.autocrlf=false archive HEAD`
plus the filtered current diff. Source was mounted read-only; writable caches and local object storage were confined to
ephemeral container `/tmp`. Core validation used Docker internal or `--network none` and explicitly empty proxy values.

```text
PUBLIC_INTERNET_EGRESS_POLICY: DENIED_FOR_D01_B_TARGETED_AND_MIGRATION_GATES
DOCKER_RUNTIME_NETWORK_INTERNAL: TRUE
PUBLIC_TEST_NET_EGRESS_PROBE: DENIED
DOCKER_INTERNAL_POSTGRESQL: AVAILABLE
D00_A_ACQUISITION_DURING_D01_B: Gitleaks v8.28.0 only
D00_A_GITLEAKS_EXPECTED_SHA256: da6458e8864af553807de1c46a7a8eac0880bd6b99ba56288e87e86a45af884f
D00_A_GITLEAKS_ACTUAL_SHA256: da6458e8864af553807de1c46a7a8eac0880bd6b99ba56288e87e86a45af884f
D00_A_PROXY_SCOPE: ACQUISITION_ONLY
PRODUCTION_PROVIDER_CALLS: 0

D01_B_TARGETED_POSTGRESQL_SUITE: 56 PASS, 0 SKIP
FULL_API_COLLECTION: 754
FULL_API_RESULT: 750 PASS, 4 ENVIRONMENT-SCOPED SKIP
WORKER_COLLECTION: 34
WORKER_RESULT: 28 PASS, 6 ENVIRONMENT-SCOPED SKIP
RUFF_FORMAT_CHECK: 222 files formatted
RUFF_CHECK: PASS
STRICT_MYPY: PASS, 125 source files
ALEMBIC_LIFECYCLE_AND_CHECK: PASS
ORM_DATABASE_FK_PARITY: PASS, 85/85
FORMAL_TABLE_DDL_DIFF: 0
GITLEAKS_WORKTREE_SCAN: PASS, 6.16 MB, 0 findings
GITLEAKS_EXACT_COMMIT_SCAN: PASS, dd39b37 only, 1 commit / 0 findings
PRIVATE_LOCATOR_AND_BYTE_SCAN: PASS, 7 scoped text files, 0 absolute-path or NUL/binary hits
GIT_DIFF_CHECK: PASS
REMOTE_REPOSITORY: yangyy816/project-mirror
REMOTE_VISIBILITY: PUBLIC, VERIFIED_READ_ONLY_BEFORE_CANDIDATE_COMMIT
```

The four full-suite skips are retained as negative evidence and are outside this schema checkpoint:

```text
auth HTTP integration: TEST_REDIS_URL not supplied to this PostgreSQL-only run
rate limit integration: TEST_REDIS_URL not supplied to this PostgreSQL-only run
P2-M3 Celery orchestration: RUN_CELERY_INTEGRATION not enabled
P2-M4 orchestration: private M4 Celery runtime not injected into this test process
```

D00 separately established the real local Redis/Celery/runtime topology. These skips are not reclassified as PASS and
do not verify D01-C, Worker or runtime integration.

The API and Worker tests reuse the accepted local API image only as a frozen dependency runtime. Test processes run on
the D01-B internal network or with `--network none`; they are not attached to the D00 ingress network.

## Negative and excluded validation evidence

- The rejected `4c84f255...` result remains `FAIL`; its historical `24 PASS / 718 PASS` cannot support this candidate.
- The first remediation full replay found one real Alembic drift defect: four redundant ORM-only digest indexes and one
  overlong QA constraint name. Both were repaired, then `alembic check` passed.
- Five checksum-bound legacy tests failed on the Windows CRLF checkout. A first attempted normalization was invalid
  because it also altered the PNG magic literal; that run produced 29 image-chain failures and is excluded. A second
  `git archive` snapshot inherited global `core.autocrlf=true` and is also excluded.
- The accepted snapshot construction disables checkout conversion before archive and verifies zero CR bytes in the
  three checksum authorities and `image_sanitizer.py`. Checksum/private-replay plus sanitizer tests then passed 56/56.
- A read-only container import initially failed because local object storage targeted the source mount. The accepted
  retry uses ephemeral `/tmp`; it does not widen network or filesystem authority.
- The PostgreSQL container's persisted local-test password differed from its current image environment metadata. The
  task-scoped accepted local credential was verified without logging it and no production credential was used.

## Risk disposition

```text
R-DEMO-05 migration conflict: MITIGATED_MONITORED
R-DEMO-06 competing authority: MITIGATED_MONITORED
R-DEMO-10 private bytes in Git/CI: MITIGATED_MONITORED for this candidate
R-DEMO-08 raw-float digest drift: SCHEMA_LAYER_MITIGATED; D04/D10 remain OPEN
R-DEMO-09 implicit rebuild time: SCHEMA_LAYER_MITIGATED; D10 remains OPEN
R-DEMO-16 Job ownership bridge: PARTIALLY_MITIGATED; D01-C/D03-D10 remain OPEN
R-DEMO-19 hidden public runtime dependency: MITIGATED_MONITORED; Gitleaks acquisition was D00-A-only
```

## Formal boundary and remaining Gate

```text
FORMAL_SCHEMA_CHANGE_ATTRIBUTABLE_TO_D01_B: NONE
FORMAL_MIGRATION_HEAD_CHANGE_ATTRIBUTABLE_TO_D01_B: NONE
FORMAL_P3_P7_STATUS: UNCHANGED
REAL_USER_VALIDITY: NOT_EVALUATED
PRODUCTION_SECURITY: DEFERRED_FOR_FORMAL_PHASE
PRODUCTION_RELEASE: NOT_AUTHORIZED

D01_B_REJECTED_CANDIDATE_REVIEW: FAIL_FOR_4c84f255
D01_B_REMEDIATION_CANDIDATE_REVIEW: PASS_FOR_dd39b37
D01_B_REVIEW_BLOCKING_FINDINGS: 0
D01_B_REVIEW_NON_BLOCKING_FINDINGS: 0
D01_B_PRINCIPAL_ACCEPTANCE: TASK_ACCEPTED
D01_C: EXECUTION_READY
D02_D12: NOT_VERIFIED
```

Independent Sol High reviewed exact SHA, parent, tree, seven-file scope, migration, ORM, tests and governance evidence
and recommended `ACCEPT` with no finding. Principal accepts D01-B and opens only D01-C implementation. This does not open
D02 or upgrade any formal P3–P7 Gate.
