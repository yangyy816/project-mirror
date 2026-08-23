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
STATUS: READY_FOR_INDEPENDENT_REVIEW
PRINCIPAL_TASK_ACCEPTANCE: PENDING
INDEPENDENT_SOL_IMPLEMENTATION_REVIEW: PENDING
D01_C: CLOSED
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
NO_CAPABILITY_LOSS: PASS
NO_EVIDENCE_LOSS: PASS
NO_API_LOSS_FROM_PHYSICAL_MAPPING: PASS
NO_REBUILDABILITY_LOSS: PASS
NO_FORMAL_AUTHORITY_POLLUTION: PASS
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
- AcceptedVisualEpisode validation proves a complete, same-owner trajectory through editing session, image version,
  plan, operations, ToolRun and Verifier authority.

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
to the D00 `internal=true` runtime network. All proxy variables were empty and an outbound connection probe to a public
TEST-NET address was denied while Docker-internal PostgreSQL remained reachable:

```text
fresh -> demo_0001_p3_p7_core: PASS
demo_0001_p3_p7_core -> 0014_m5_eval_authority: PASS
0014_m5_eval_authority -> demo_0001_p3_p7_core: PASS
demo_0001_p3_p7_core -> 0014_m5_eval_authority: PASS
0014_m5_eval_authority -> demo_0001_p3_p7_core: PASS
ALEMBIC_HEADS: exactly demo_0001_p3_p7_core
ALEMBIC_CURRENT: demo_0001_p3_p7_core
ALEMBIC_CHECK: No new upgrade operations detected
SCHEMA_DRIFT: 0
```

Populated downgrade tests prove that Demo authority rows, `demo_p3_p7.*` Jobs/JobAttempts and
`demo_p3_p7_` AssetVariants prevent object removal before any destructive DDL. Existing M3/M4/M5 durable-authority
downgrade tests still fail closed and now correctly assert that the failed transaction restores the branch-local Demo
head.

Future formal absorption must create a new forward migration from the then-current formal head and an explicit
promotion/conversion strategy. This migration cannot become the formal production revision.

## Validation evidence

The final D01-B targeted and migration-lifecycle Gates ran in the D00 Docker-internal topology with every proxy
variable unset:

```text
PUBLIC_INTERNET_EGRESS_POLICY: DENIED_FOR_D01_B_TARGETED_AND_MIGRATION_GATES
DOCKER_RUNTIME_NETWORK_INTERNAL: TRUE
PUBLIC_TEST_NET_EGRESS_PROBE: DENIED
DOCKER_INTERNAL_POSTGRESQL: AVAILABLE
D00_A_ACQUISITION_DURING_D01_B: 0
PRODUCTION_PROVIDER_CALLS: 0

D01_B_TARGETED_POSTGRESQL_SUITE: 24 PASS, 0 SKIP
FULL_API_COLLECTION: 722
FULL_API_RESULT: 718 PASS, 4 ENVIRONMENT-SCOPED SKIP
RUFF_FORMAT_CHECK: 222 files formatted
RUFF_CHECK: PASS
STRICT_MYPY: PASS, 125 source files
GIT_DIFF_CHECK: PASS
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

The 722-item full API regression used the existing D00 API container with all proxy variables unset. That container is
also attached to the host-facing ingress network, so the full-suite result is regression evidence, not the egress
containment proof. The internal-only targeted and migration runs above are the D01-B containment evidence.

## Repair evidence retained

The first LF-normalized complete regression exposed five old migration tests that still expected
`0014_m5_eval_authority` after `upgrade head` or a failed downgrade. All five failures had an actual current revision
of `demo_0001_p3_p7_core`; the migration transaction and authority rows were intact. The repair only updates those
branch-local expected-head assertions, after which all five and the complete suite pass.

A manual focused replay intentionally left a durable M5 authority row in its database. Reusing that database for a
subsequent deep legacy downgrade correctly failed with `0014 downgrade would discard durable M5 evaluation authority`.
The final full regression therefore uses a fresh isolated database and passes. This is fail-closed evidence, not a
flaky retry or migration bypass.

Ruff also detected mixed Windows line endings introduced by the five-line assertion repair. The four affected files
were formatted with the repository Ruff and the complete format/check Gate then passed.

The first internal-only read-only-container attempt denied public egress as required but stopped during application
import because the default local object-storage root pointed inside the read-only source mount. The accepted retry set
`LOCAL_STORAGE_ROOT` to an ephemeral container `/tmp` directory; source remained read-only, the network boundary did
not change, no acquisition occurred and all 24 tests passed.

## Risk disposition

```text
R-DEMO-05 migration conflict: MITIGATED_MONITORED
R-DEMO-06 competing authority: MITIGATED_MONITORED
R-DEMO-08 raw-float digest drift: SCHEMA_LAYER_MITIGATED; D04/D10 remain OPEN
R-DEMO-09 implicit rebuild time: SCHEMA_LAYER_MITIGATED; D10 remains OPEN
R-DEMO-16 Job ownership bridge: PARTIALLY_MITIGATED; D01-C/D03-D10 remain OPEN
R-DEMO-19 hidden public runtime dependency: MITIGATED_MONITORED; core runtime Gates remain mandatory
```

## Formal boundary and remaining Gate

```text
FORMAL_SCHEMA_CHANGE_ATTRIBUTABLE_TO_D01_B: NONE
FORMAL_MIGRATION_HEAD_CHANGE_ATTRIBUTABLE_TO_D01_B: NONE
FORMAL_P3_P7_STATUS: UNCHANGED
REAL_USER_VALIDITY: NOT_EVALUATED
PRODUCTION_SECURITY: DEFERRED_FOR_FORMAL_PHASE
PRODUCTION_RELEASE: NOT_AUTHORIZED

D01_B_INDEPENDENT_REVIEW: PENDING
D01_B_PRINCIPAL_ACCEPTANCE: PENDING
D01_C: CLOSED
D02_D12: NOT_VERIFIED
```

Only an independent Sol High review of the actual candidate diff and the bound PostgreSQL evidence can recommend
acceptance. Principal acceptance then opens D01-C; it does not open D02 or upgrade any formal P3–P7 Gate.
