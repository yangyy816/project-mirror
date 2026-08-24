# P3–P7 D07-A Acceptance Evidence

## Candidate status

```text
TASK: D07-A — P6 Operation Graph domain
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
FINAL_REPAIR_HANDOFF_SHA: a6776f5536e40559c2aed81a071a6904bd3f7923
FINAL_REPAIR_HANDOFF_BASE_SHA: dbf45e55418278394c8a34eca10bf776a026abf7
INTEGRATED_SHA: 38d152f969d1235b2fc6ae39076adc79d4e72683
INTEGRATED_PARENT: dbf45e55418278394c8a34eca10bf776a026abf7
INTEGRATED_TREE: 70ca0dc8a72a7dcf01d53ee7397bb82856b0b5c2
BRANCH: codex/p3-p7-core-demo
CURRENT_STATUS: TASK_ACCEPTED
PRINCIPAL_TASK_ACCEPTANCE: TASK_ACCEPTED
INDEPENDENT_INITIAL_REVIEW: REPAIR_REQUIRED
INDEPENDENT_FINAL_REPAIR_REVIEW: PASS
D07_B: CLOSED_PENDING_D02_AND_D03_TASK_ACCEPTED
FORMAL_P3_P7_STATUS: UNCHANGED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

This acceptance covers only the pure deterministic D07-A typed Operation Graph authority. It does not accept an editor
runtime, Tool registry, planner, ToolRun, verifier, ImageVersion persistence, raster or geometry execution, restore UI,
D07-B, D08, Web, a formal P6 Gate or production use.

## Accepted file boundary

The final integrated tree binds exactly:

```text
services/api/src/mirror_api/demo_operation_graph.py
  blob: b530f99cec6a3614f02ee2b28ffb239dc95c7d05

services/api/tests/test_demo_operation_graph.py
  blob: abdfe2e62104aec850e081025ad28b8d10205f5f

services/api/tests/fixtures/demo_operation_graph_v2_golden.json
  blob: d28be5ac3888ed484cf8ce7b86ad5eb0ad1f6165
```

The final repair commit changes only the source and targeted test; the tracked golden fixture is byte-identical. The
handoff and integrated commit have the same stable patch ID. No migration, ORM, schema, router, OpenAPI, generated
client, Celery registration, Web file, dependency, D07-B module or private byte is part of the repair.

## Accepted Operation Graph authority

```text
GRAPH_SCHEMA_VERSION: mirror.demo/OperationGraph/v2
GRAPH_ALGORITHM_VERSION: demo-operation-graph-linear-v1
MAX_OPERATIONS: 64
GOLDEN_GRAPH_DIGEST: 22e06819de362dac62ffc244b2945ced614858331102a70902c8fa74a22cacb5
CANONICAL_JSON: UTF8_KEY_ORDER_INTEGER_ONLY_NO_FLOAT
```

The accepted domain provides:

- typed operation specs for crop, rotate, exposure, contrast, saturation, temperature, restore, rollback, geometry,
  makeup and generative entries;
- deterministic engine/type compatibility, parameter bounds, derived expected effects and preserve constraints;
- canonical, linear graph-local node identity and dependency validation with explicit cycle, orphan, duplicate,
  disconnected and non-linear failures;
- deep defensive freezing of operation parameters, effects, preserve tuples and graph-node containers;
- transition intents for append-only restore and rollback lineage, with current/ancestor/quarantine checks;
- explicit execution-unavailable behavior for registry-gated capabilities without deleting their typed graph entry.

MAKEUP and GENERATIVE being structurally representable does not make either capability available. D07-A contains no
runtime callback implementation and does not claim that an operation has executed.

## Preserved negative evidence and bounded repair

The initial exact integrated SHA `dbf45e55418278394c8a34eca10bf776a026abf7` had green CI run `32675441689`, but an
independent Sol review reproduced a mandatory immutability defect: `OperationGraph.nodes` could retain a caller-owned
mutable list and the same accepted object could later produce a different digest. That SHA was correctly classified
`REPAIR_REQUIRED`; green CI was not treated as authority acceptance.

Epoch 4 repair handoff `a6776f5536e40559c2aed81a071a6904bd3f7923` defensively copies tuple/list input to a tuple,
rejects every non-`OperationNode` member and makes post-construction non-tuple state fail closed at validation. The
repair changes neither graph schema/algorithm nor canonical golden bytes.

## Standalone and integrated validation

The Principal transplanted only the final repair from exact base `dbf45e5` into detached standalone SHA
`724a00f3845b9716a5b7ed0a1ffb5ce743937160`. The handoff, transplant and integrated code/test blobs are identical.
Standalone and integrated validation used Linux/Python 3.13.1, `--network none`, a read-only source mount and a
task-scoped `/tmp` storage/cache root.

```text
TARGETED_PYTEST: 39/39 PASS, 0 SKIP
RUFF_FORMAT: PASS
RUFF_CHECK: PASS
STRICT_MYPY: PASS
GIT_DIFF_CHECK: PASS
STANDALONE_TRANSPLANT: PASS
EXACT_COMMIT_GITLEAKS_8_28_0: PASS, 0 findings
PUBLIC_INTERNET_EGRESS: DENIED
PRIVATE_INPUT: NONE
```

The first Principal read-only container attempt reached test collection before failing because the default local
storage path was read-only. Re-running with the test-only storage root under `/tmp` passed completely; no source,
assertion, threshold or authority changed.

## Independent final repair review

An independent Sol reviewer verified exact handoff SHA `a6776f5`, its base, two-file scope, patch-equivalent standalone
transplant and unchanged golden fixture. It reproduced all relevant mutation boundaries:

```text
EXTERNAL_LIST_DEFENSIVELY_FROZEN: PASS
EXTERNAL_LIST_MUTATION_DIGEST_STABLE: PASS
NON_OPERATION_NODE_REJECTED: PASS
POST_CONSTRUCTION_NON_TUPLE_FAILS_CLOSED: PASS
MUTABLE_DEPENDS_ON_CANNOT_BECOME_VALID_AUTHORITY: PASS
NESTED_OPERATION_SPEC_IMMUTABILITY: PASS
FINDINGS: NONE
GATE_VERDICT: PASS
```

The reviewer recommended integration but did not claim `TASK_ACCEPTED`; that decision remains the Principal's.

## Exact-SHA CI evidence

GitHub Actions run [32677991401](https://github.com/yangyy816/project-mirror/actions/runs/32677991401) completed
successfully for exact implementation SHA `38d152f969d1235b2fc6ae39076adc79d4e72683`.

```text
secret-scan: PASS
quality-and-integration: PASS
docker-validation: PASS
```

The exact job evidence records:

```text
PYTHON_FORMAT: 238 files
RUFF: PASS
MYPY: 132 source files PASS
PYTHON_TESTS: 942 passed, 1 existing optional skip
PHASE_1: 1 passed
P2_M1: 98 passed
P2_M2: 52 passed
P2_M3: 46 passed
TYPESCRIPT_TESTS: 54 passed
PLAYWRIGHT: 5 passed
POSTGRESQL_MIGRATION_LIFECYCLE: PASS
OPENAPI_CONTRACT_DRIFT: PASS
DEMO_BOUNDARY: PASS
DEPENDENCY_AUDITS: NO KNOWN VULNERABILITIES
DOCKER_TOPOLOGY: PASS
```

The downloaded boundary artifact binds the exact SHA, Demo migration head `demo_0003_d02_import_auth`, unchanged
formal head `0014_m5_eval_authority` and `PRODUCTION_RELEASE: NOT_AUTHORIZED`. Five artifacts are present and unexpired:

| Artifact                      |         ID | Result                                |
| ----------------------------- | ---------: | ------------------------------------- |
| `gitleaks-results.sarif`      | 9503270945 | one run, zero results                 |
| `project-docker-evidence`     | 9503300726 | topology evidence present             |
| `playwright-install-evidence` | 9503369734 | install evidence present              |
| `demo-prototype-ci-boundary`  | 9503374468 | exact SHA/head/boundary matched       |
| `project-audit-evidence`      | 9503378111 | licenses/SBOM/Celery evidence present |

The only workflow annotations are GitHub's Node 20 action-deprecation notices under a Node 24 forced runtime; no D07-A
product or execution step failed.

## Repository and concurrent-work preservation

Before the authorized normal non-force push, the remote repository was reverified as `PUBLIC`; the exact repair commit
had no private locator/path token and Gitleaks v8.28.0 found zero results. Remote and local integration refs both reached
`38d152f...`.

The two Principal-owned untracked D02 authority candidates remained excluded from the D07-A commit. The protected P6
topic draft remained untracked, unmodified and excluded at 7,317 bytes with SHA-256
`5b7843e6c38d27dc5a1b89dd5cff248566a41e5e806438481aa04f8fee60a76b`. No formal worktree change was absorbed.

## Principal decision

```text
D07_A: TASK_ACCEPTED
D07_B: CLOSED_PENDING_D02_AND_D03_TASK_ACCEPTED
P6_OPERATION_GRAPH: DEMO_PROTOTYPE_DOMAIN_ACCEPTED
P6_DETERMINISTIC_EDITOR: NOT_VERIFIED
P6_GEOMETRY_EDITOR: NOT_VERIFIED
P6_AGENT_EDIT_PLAN: NOT_VERIFIED
P6_TOOL_VERIFIER: NOT_VERIFIED
P6_RESTORE_ROLLBACK_RUNTIME: NOT_VERIFIED
P6_MAKEUP_BASELINE: DEFERRED_WITH_EXPLICIT_REASON
P6_GENERATIVE_EDITOR: CAPABILITY_UNAVAILABLE
ALGORITHMIC_PROTOTYPE_PLATFORM: NOT_VERIFIED
LOCAL_WEB_AGENT: NOT_VERIFIED
FORMAL_P3_P7_STATUS: UNCHANGED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

D07-A acceptance opens no new DAG node by itself. D07-B remains gated until D02, D03 and D07-A are all
`TASK_ACCEPTED`, D00 M4 runtime remains valid and the Principal publishes the applicable next-wave base.
