# P3–P7 D02 Change Control 10 — Windows Read-Only Host Projection

## Decision status

```text
CHANGE_CONTROL_ID: P3_P7_D02_CC_10
TRACK: DEMO_PROTOTYPE
STATUS: CANDIDATE_REVISION_4_PENDING_INDEPENDENT_SOL_EXACT_PLAN_REVIEW
BASE_SHA: eacec651518ce84b0a94db28b4fefcb867c2ecff
TASK_ID: P3_P7_D02_CC10_WINDOWS_HOST_PROJECTION_IMPLEMENTATION_01
REVISION_1_NEGATIVE_REVIEW_SHA: 543fd14ee4d9c87785d713a47f2d8398084cc30b
REVISION_1_NEGATIVE_REVIEW_TREE: d8cd73a682443865d22cd79115f0f0e998d3cf11
REVISION_1_DISPOSITION: REPAIR_REQUIRED_P0_0
REVISION_2_NEGATIVE_REVIEW_SHA: c74978442e4ca38f794d05fdbaae9d1acf2b79c5
REVISION_2_NEGATIVE_REVIEW_TREE: 8b4062b1a0e15a10d3e6d8ebef4752d65a871ffe
REVISION_2_DISPOSITION: REPAIR_REQUIRED_P0_0_P1_3_P2_2_P3_0
REVISION_3_NEGATIVE_REVIEW_SHA: 60422fa8a7abcb129c862583dad7677c29621a00
REVISION_3_NEGATIVE_REVIEW_TREE: d153329da7f67d265a8946a8a8ff481d12b3ff33
REVISION_3_DISPOSITION: REPAIR_REQUIRED_P0_0_P1_1_P2_0_P3_0
PREDECESSOR_CHANGE_CONTROL: P3_P7_D02_CC_09
PREDECESSOR_IMPLEMENTATION_SHA: dd16624ed5ff679b03fefc61994f4ea9fd85e71e
PREDECESSOR_IMPLEMENTATION_ACCEPTANCE_DIGEST: 9421b293f88c6015f1f2f42d449d54bf93bd806fedcf73cb7a76ec4c3bef4f2c
PREDECESSOR_ACCEPTANCE_STATE_SHA: 889bb6fa2379d3369c1e72d32b4af8cca03387aa
PREDECESSOR_EXECUTION_STATE_SHA: eacec651518ce84b0a94db28b4fefcb867c2ecff
PLAN_AUTHORIZED_SCOPE: IMPLEMENT_AND_VALIDATE_EXACT_TWO_FILE_WINDOWS_READ_ONLY_HOST_PROJECTION_ONLY
PRODUCTION_ENTRYPOINT_ARGUMENTS: NONE
PRODUCTION_ENTRYPOINT_RESULT: CANONICAL_HOST_CANDIDATE_BYTES_ONLY
HOST_DIRECTORY_MUTATION_AUTHORIZED: NO
PROOF_TEMPORARY_KERNEL_TOKEN_PROCESS_STATE_AUTHORIZED_AFTER_S10_CI: YES_BOUNDED_EXACT
PERSISTENT_FILESYSTEM_REGISTRY_ACL_WFP_MUTATION_AUTHORIZED: NO
PRIVATE_OUTPUT_CREATED: NO
RAW_ETW_RETENTION: NONE
SOURCE_GENERATION_CALLS_AUTHORIZED: 0
M3_M4_EXECUTION_AUTHORIZED: NO
POSTGRESQL_ADMISSION_AUTHORIZED: NO
D02_R2_TASK_ACCEPTED: NO
D03: BLOCKED
D04_B: BLOCKED
D07_B: BLOCKED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

CC10 is forward-only. It does not rewrite or withdraw CC09. CC09 correctly accepted validators and an injected
read-only projection seam; repository inspection proved that those bytes contain no real Windows collector,
canonical candidate builder, production emitter or native no-write proof harness. Those capabilities exceed the CC09
implementation acceptance and therefore require this new change control rather than a Repair Task.

Revisions 1 through 3 are preserved at the SHAs above as negative review evidence. Revision 4 is a normal forward
commit and does not amend, force-rewrite or relabel those bytes. It retains revision 3's closure and additionally
freezes the sole three-component OS-build authority, its pre/post replay, prohibited alternate sources and fail-closed
negative controls; it still authorizes no execution.

## Accepted predecessor Gate

```text
CC09_IMPLEMENTATION_TREE: 632a1e7a334f33c9ca1b070bfe06228f80c1ae33
CC09_ACCEPTANCE_RECORD: docs/operations/P3_P7_D02_R2_LOCATOR_CUSTODY_IMPLEMENTATION_ACCEPTANCE.json
CC09_SOURCE_BLOB: 8a2a63f5338733f57aaaa0dc4898cedd08919d4a
CC09_TEST_BLOB: 5577e760c77a02175e5a32e12b4dccecd3ccaf99
CC09_IMPLEMENTATION_CI: PASS_33156860094
CC09_ACCEPTANCE_STATE_CI: PASS_33161517249
EXECUTION_STATE_CI: PASS_33164251848
```

Run `33164251848` passed `quality-and-integration`, `secret-scan` and `docker-validation` at exact head
`eacec651518ce84b0a94db28b4fefcb867c2ecff`; five artifacts were present, unexpired and SHA-bound. This opens CC10
governance only. It does not authorize a collector call or host write.

## Scope and ownership

After a separately tracked plan acceptance, one Terra High implementation owner may modify exactly:

```text
services/api/src/mirror_api/demo_d02_r2_locator_custody.py
services/api/tests/test_demo_d02_r2_locator_custody.py
```

The accepted CC09 validators, wire schemas, host-candidate key set, synthetic custody behavior and historical anchors
remain intact. No migration, ORM, router, OpenAPI, generated client, Celery registration, dependency, CI workflow or
public API may change. The Integration Principal alone owns future acceptance/candidate/proof files,
`.prettierignore`, execution state, MEMORY and every commit or push.

```text
NO_CC09_HISTORY_REWRITE
NO_OLD_D00_OR_CC07_RECOVERY
NO_HOST_DIRECTORY_CREATION_OR_MUTATION
NO_PROJECT_MIRROR_CONTAINER_OR_CODE_CACHE_CREATION
NO_PRIVATE_HOME_CREATION_OR_BINDING
NO_LOCATOR_NAMESPACE_OR_EVENT
NO_CC08_EVIDENCE_ROOT
NO_PRIVATE_TRACE_FILE_OR_ETL
NO_PROCMON_OR_THIRD_PARTY_DRIVER
NO_WFP_INSTALLATION
NO_IMAGEGEN_OR_M3_M4
NO_POSTGRESQL_ADMISSION
NO_D02_R2_TASK_ACCEPTANCE
NO_D03_D04_B_D07_B_OPENING
NO_FORMAL_P3_P7_AUTHORITY
NO_PRODUCTION_RELEASE
```

## Non-circular authority chain

Let:

```text
B10 = eacec651518ce84b0a94db28b4fefcb867c2ecff
G10 = final reviewed CC10 governance commit
P10 = commit containing CC10 plan acceptance
I10 = exact two-file implementation commit
S10 = commit containing CC10 implementation acceptance
A   = S10:docs/operations/P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_IMPLEMENTATION_ACCEPTANCE.json
SC  = candidate-only commit relative to S10
C   = SC:docs/operations/P3_P7_D02_R2_WINDOWS_HOST_BINDING_CANDIDATE.json
SH  = native-proof plus host-acceptance commit relative to SC
```

The only legal order is:

```text
B10 CI PASS
-> G10 exact-plan review and CI PASS
-> P10 plan acceptance and CI PASS
-> I10 implementation review and CI PASS
-> S10 implementation acceptance and CI PASS
-> native proof plus in-memory candidate bytes
-> SC candidate review and CI PASS
-> SH proof/host-acceptance review and CI PASS
-> next separately authorized code-cache/private-home stage
```

Implementation source may freeze the preceding plan-acceptance digest, but must not contain its future
implementation-acceptance digest, S10, candidate digest, SC, native-proof digest or host acceptance. The candidate
retains the frozen CC09 schema and literals, including `change_control_id=P3_P7_D02_CC_09`. CC10 externally defines:

```text
candidate.locator_custody_implementation_sha = A.implementation_sha = I10
candidate.locator_custody_implementation_acceptance_record_digest = A.record_digest
A.record_digest = TD(A.schema_version, A excluding record_digest)
A.governed_paths exactly bind source/test paths, blobs and SHA-256 values at I10
A.runtime_dependencies exactly bind the measurement-quality path, blob and SHA-256 value at I10
SC:<CC10 acceptance path> byte-equals S10:<CC10 acceptance path>
SC source/test blobs equal A.governed_paths
SC measurement-quality blob equals A.runtime_dependencies
diff(S10, SC) contains only the fixed host candidate path
C.record_digest = TD(C.schema_version, C excluding record_digest)
```

A caller mapping, fully re-signed candidate, mixed-SHA evidence or future-digest cycle never becomes authority.

## Exact plan and implementation acceptance authority

All acceptance JSON uses `demo-canonical-json-v1`: UTF-8, no BOM, no duplicate keys, no insignificant whitespace,
lexicographically sorted object keys, array order preserved, JSON booleans/integers/strings/null only and exactly one
terminal LF forbidden. `TD(domain, payload)` is SHA-256 of `UTF8(domain) || 0x0A || canonical_json(payload)`. A record
digest is `TD(record.schema_version, record excluding only record_digest)`. SHA/tree/blob values are 40 lowercase hex;
content digests are 64 lowercase hex; findings and CI `run_id` are non-boolean integers; timestamps are normalized UTC
`YYYY-MM-DDTHH:MM:SS.ffffffZ`.

The plan-acceptance path and schema are:

```text
PATH: docs/operations/P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_PLAN_ACCEPTANCE.json
SCHEMA: mirror.demo/D02R2WindowsHostProjectionPlanAcceptance/v1
AUTHORITY_ID: P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_PLAN_ACCEPTANCE_01
```

It has exactly these top-level keys; no extension key is allowed:

```text
schema_version, authority_id, change_control_id,
reviewed_plan_file_sha256, reviewed_plan_git_blob_oid,
reviewed_risk_register_file_sha256, reviewed_risk_register_git_blob_oid,
accepted_governance_sha, accepted_governance_tree, base_sha,
predecessor_implementation_sha, predecessor_implementation_acceptance_record_digest,
predecessor_acceptance_state_sha, predecessor_execution_state_sha,
schema_contract_digest, host_projection_contract_digest,
independent_review, same_sha_ci, principal_acceptance,
authorized_implementation_paths, runtime_dependency_paths, authorized_validation_actions,
authorized_scope, prohibited_scope, record_created_at_utc, record_digest
```

Its ordered literals are exactly:

```text
authorized_implementation_paths =
  [
    services/api/src/mirror_api/demo_d02_r2_locator_custody.py,
    services/api/tests/test_demo_d02_r2_locator_custody.py
  ]

runtime_dependency_paths =
  [
    services/api/src/mirror_api/demo_measurement_quality.py
  ]

authorized_validation_actions =
  [
    RUFF_FORMAT_AND_CHECK_AUTHORIZED_PATHS_ONLY,
    STRICT_MYPY_AUTHORIZED_IMPLEMENTATION_ONLY,
    TARGETED_PYTEST_SYNTHETIC_BACKENDS_ONLY,
    STATIC_CALL_GRAPH_AND_ACCESS_MASK_AUDIT,
    NATIVE_HARNESS_CONTRACT_TESTS_WITHOUT_STARTING_ETW_OR_TARGET,
    PRIVATE_PREIMAGE_DISCLOSURE_SCAN,
    GIT_DIFF_CHECK,
    INDEPENDENT_EXACT_SHA_IMPLEMENTATION_REVIEW,
    SAME_SHA_CI
  ]

authorized_scope = IMPLEMENT_AND_VALIDATE_EXACT_TWO_FILE_WINDOWS_READ_ONLY_HOST_PROJECTION_ONLY

prohibited_scope =
  [
    ANY_TRACKED_PATH_OUTSIDE_AUTHORIZED_IMPLEMENTATION_PATHS,
    NATIVE_ETW_OR_TARGET_EXECUTION_BEFORE_S10_CI,
    HOST_PERSISTENT_FILESYSTEM_REGISTRY_ACL_OR_WFP_MUTATION,
    WORKER_CANDIDATE_WRITE,
    PRIVATE_ROOT_HOME_LOCATOR_OR_TRACE_CREATION,
    RAW_ETW_OR_PRIVATE_PREIMAGE_RETENTION,
    SOURCE_GENERATION,
    M3_M4_EXECUTION,
    MIGRATION_OR_ORM,
    POSTGRESQL_ADMISSION,
    PUBLIC_API_OR_ROUTER_CHANGE,
    DEPENDENCY_OR_CI_CHANGE,
    D02_R2_TASK_ACCEPTANCE,
    D03_D04_B_D07_B_OPENING,
    FORMAL_PHASE_AUTHORITY,
    PRODUCTION_RELEASE
  ]
```

The implementation-acceptance path and schema are:

```text
PATH: docs/operations/P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_IMPLEMENTATION_ACCEPTANCE.json
SCHEMA: mirror.demo/D02R2WindowsHostProjectionImplementationAcceptance/v1
AUTHORITY_ID: P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_IMPLEMENTATION_ACCEPTANCE_01
```

It has exactly:

```text
schema_version, authority_id, change_control_id,
accepted_plan_sha, accepted_plan_tree, accepted_plan_acceptance_record_digest,
predecessor_implementation_sha, predecessor_implementation_acceptance_record_digest,
implementation_sha, implementation_tree, governed_paths, runtime_dependencies,
schema_contract_digest, host_projection_contract_digest,
independent_review, same_sha_ci, principal_acceptance,
authorized_scope, prohibited_scope, record_created_at_utc, record_digest
```

`governed_paths` is the ordered source/test list. `runtime_dependencies` is the ordered one-row measurement-quality
list. Every row has exactly `path`, `sha256`, `git_blob_oid`; implementation rows bind I10 bytes, while the dependency
row binds the unmodified I10 dependency bytes and is supplied to the isolated target through a verified read handle.
The implementation acceptance literals are exactly:

```text
authorized_scope = EXECUTE_READ_ONLY_WINDOWS_HOST_PROJECTION_AND_EMIT_CANONICAL_HOST_CANDIDATE_BYTES_ONLY

prohibited_scope =
  [
    ANY_IMPLEMENTATION_OR_TEST_PATH_CHANGE,
    PERSISTENT_FILESYSTEM_REGISTRY_ACL_OR_WFP_MUTATION,
    RAW_ETW_OR_PRIVATE_PREIMAGE_RETENTION,
    PRIVATE_ROOT_HOME_OR_LOCATOR_CREATION,
    WORKER_CANDIDATE_WRITE,
    SOURCE_GENERATION,
    M3_M4_EXECUTION,
    MIGRATION_OR_ORM,
    POSTGRESQL_ADMISSION,
    PUBLIC_API_OR_ROUTER_CHANGE,
    DEPENDENCY_OR_CI_CHANGE,
    D02_R2_TASK_ACCEPTANCE,
    D03_D04_B_D07_B_OPENING,
    FORMAL_PHASE_AUTHORITY,
    PRODUCTION_RELEASE
  ]
```

### Frozen nested objects and SHA equations

Plan `independent_review` has exactly:

```text
evidence_digest, findings_p0, findings_p1, findings_p2, findings_p3,
result, review_task_id, reviewed_governance_sha
```

Implementation `independent_review` has the same first seven keys and `reviewed_implementation_sha`. Both require
`result=PASS` and all four findings equal integer zero. Their evidence digests are respectively:

```text
TD(mirror.demo/D02R2WindowsHostProjectionPlanReviewEvidence/v1,
   {review_task_id, reviewed_governance_sha, reviewed_governance_tree,
    reviewed_plan_file_sha256, reviewed_risk_register_file_sha256,
    findings_p0, findings_p1, findings_p2, findings_p3, result})

TD(mirror.demo/D02R2WindowsHostProjectionImplementationReviewEvidence/v1,
   {review_task_id, reviewed_implementation_sha, reviewed_implementation_tree,
    governed_paths, runtime_dependencies,
    findings_p0, findings_p1, findings_p2, findings_p3, result})
```

Both `same_sha_ci` objects have exactly:

```text
artifact_manifest_digest, head_sha, provider, repository,
required_jobs, result, run_id, workflow_identity
```

with the ordered literal `required_jobs=[quality-and-integration,secret-scan,docker-validation]`,
`provider=GITHUB_ACTIONS`, `repository=yangyy816/project-mirror`, `result=PASS` and
`workflow_identity=.github/workflows/ci.yml`. The artifact manifest digest is an external exact-run authority and is
not synthesized by the acceptance record.

Plan `principal_acceptance` has exactly
`acceptance_authority_digest,accepted_at_utc,accepted_governance_sha,status`; implementation
`principal_acceptance` substitutes `accepted_implementation_sha`. `status=PRINCIPAL_ACCEPTED`, and each
`accepted_at_utc` equals its enclosing `record_created_at_utc`. The authority digests are:

```text
TD(mirror.demo/D02R2WindowsHostProjectionPlanPrincipalAcceptance/v1,
   {status, accepted_governance_sha, accepted_at_utc,
    independent_review_evidence_digest, same_sha_ci_artifact_manifest_digest})

TD(mirror.demo/D02R2WindowsHostProjectionImplementationPrincipalAcceptance/v1,
   {status, accepted_implementation_sha, accepted_at_utc,
    independent_review_evidence_digest, same_sha_ci_artifact_manifest_digest})
```

The exact equations are:

```text
plan.accepted_governance_sha = G10
plan.accepted_governance_tree = tree(G10)
plan.independent_review.reviewed_governance_sha = G10
plan.same_sha_ci.head_sha = G10
plan.principal_acceptance.accepted_governance_sha = G10

implementation.accepted_plan_sha = G10
implementation.accepted_plan_tree = tree(G10)
implementation.implementation_sha = I10
implementation.implementation_tree = tree(I10)
implementation.independent_review.reviewed_implementation_sha = I10
implementation.same_sha_ci.head_sha = I10
implementation.principal_acceptance.accepted_implementation_sha = I10
implementation.accepted_plan_acceptance_record_digest = plan.record_digest
implementation.schema_contract_digest = plan.schema_contract_digest
implementation.host_projection_contract_digest = plan.host_projection_contract_digest
```

P10 and S10 are commits containing the acceptance records; their own later CI is external progression evidence. P10
does not pretend its embedded CI ran at P10, and S10 does not pretend its embedded CI ran at S10. S10 must pass all
three jobs before any native session or target starts.

### Acceptance schema-contract digest preimage

`schema_contract_digest` is exactly
`TD(mirror.demo/D02R2WindowsHostProjectionAcceptanceSchemaContract/v1,
ACCEPTANCE_SCHEMA_CONTRACT_PREIMAGE)` where the named preimage is the following JSON object. Arrays are ordered
authorities; object key serialization remains canonical-json sorted.

```json
{
  "canonicalization": "demo-canonical-json-v1",
  "change_control_id": "P3_P7_D02_CC_10",
  "equations": [
    "PLAN_ACCEPTED_GOVERNANCE_SHA_EQ_G10",
    "PLAN_ACCEPTED_GOVERNANCE_TREE_EQ_TREE_G10",
    "PLAN_REVIEWED_GOVERNANCE_SHA_EQ_G10",
    "PLAN_CI_HEAD_SHA_EQ_G10",
    "PLAN_PRINCIPAL_SHA_EQ_G10",
    "IMPLEMENTATION_ACCEPTED_PLAN_SHA_EQ_G10",
    "IMPLEMENTATION_ACCEPTED_PLAN_TREE_EQ_TREE_G10",
    "IMPLEMENTATION_SHA_EQ_I10",
    "IMPLEMENTATION_TREE_EQ_TREE_I10",
    "IMPLEMENTATION_REVIEWED_SHA_EQ_I10",
    "IMPLEMENTATION_CI_HEAD_SHA_EQ_I10",
    "IMPLEMENTATION_PRINCIPAL_SHA_EQ_I10",
    "IMPLEMENTATION_PLAN_RECORD_DIGEST_EQ_PLAN_RECORD_DIGEST",
    "IMPLEMENTATION_SCHEMA_CONTRACT_DIGEST_EQ_PLAN",
    "IMPLEMENTATION_HOST_CONTRACT_DIGEST_EQ_PLAN"
  ],
  "implementation_acceptance": {
    "authority_id": "P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_IMPLEMENTATION_ACCEPTANCE_01",
    "authorized_scope": "EXECUTE_READ_ONLY_WINDOWS_HOST_PROJECTION_AND_EMIT_CANONICAL_HOST_CANDIDATE_BYTES_ONLY",
    "field_keys": [
      "schema_version",
      "authority_id",
      "change_control_id",
      "accepted_plan_sha",
      "accepted_plan_tree",
      "accepted_plan_acceptance_record_digest",
      "predecessor_implementation_sha",
      "predecessor_implementation_acceptance_record_digest",
      "implementation_sha",
      "implementation_tree",
      "governed_paths",
      "runtime_dependencies",
      "schema_contract_digest",
      "host_projection_contract_digest",
      "independent_review",
      "same_sha_ci",
      "principal_acceptance",
      "authorized_scope",
      "prohibited_scope",
      "record_created_at_utc",
      "record_digest"
    ],
    "governed_path_row_keys": ["path", "sha256", "git_blob_oid"],
    "independent_review_keys": [
      "evidence_digest",
      "findings_p0",
      "findings_p1",
      "findings_p2",
      "findings_p3",
      "result",
      "review_task_id",
      "reviewed_implementation_sha"
    ],
    "principal_acceptance_keys": [
      "acceptance_authority_digest",
      "accepted_at_utc",
      "accepted_implementation_sha",
      "status"
    ],
    "predecessor_implementation_acceptance_record_digest": "9421b293f88c6015f1f2f42d449d54bf93bd806fedcf73cb7a76ec4c3bef4f2c",
    "predecessor_implementation_sha": "dd16624ed5ff679b03fefc61994f4ea9fd85e71e",
    "prohibited_scope": [
      "ANY_IMPLEMENTATION_OR_TEST_PATH_CHANGE",
      "PERSISTENT_FILESYSTEM_REGISTRY_ACL_OR_WFP_MUTATION",
      "RAW_ETW_OR_PRIVATE_PREIMAGE_RETENTION",
      "PRIVATE_ROOT_HOME_OR_LOCATOR_CREATION",
      "WORKER_CANDIDATE_WRITE",
      "SOURCE_GENERATION",
      "M3_M4_EXECUTION",
      "MIGRATION_OR_ORM",
      "POSTGRESQL_ADMISSION",
      "PUBLIC_API_OR_ROUTER_CHANGE",
      "DEPENDENCY_OR_CI_CHANGE",
      "D02_R2_TASK_ACCEPTANCE",
      "D03_D04_B_D07_B_OPENING",
      "FORMAL_PHASE_AUTHORITY",
      "PRODUCTION_RELEASE"
    ],
    "runtime_dependency_row_keys": ["path", "sha256", "git_blob_oid"],
    "schema_version": "mirror.demo/D02R2WindowsHostProjectionImplementationAcceptance/v1"
  },
  "nested": {
    "implementation_principal_acceptance_domain": "mirror.demo/D02R2WindowsHostProjectionImplementationPrincipalAcceptance/v1",
    "implementation_review_evidence_domain": "mirror.demo/D02R2WindowsHostProjectionImplementationReviewEvidence/v1",
    "plan_principal_acceptance_domain": "mirror.demo/D02R2WindowsHostProjectionPlanPrincipalAcceptance/v1",
    "plan_review_evidence_domain": "mirror.demo/D02R2WindowsHostProjectionPlanReviewEvidence/v1",
    "required_jobs": [
      "quality-and-integration",
      "secret-scan",
      "docker-validation"
    ],
    "same_sha_ci_keys": [
      "artifact_manifest_digest",
      "head_sha",
      "provider",
      "repository",
      "required_jobs",
      "result",
      "run_id",
      "workflow_identity"
    ],
    "same_sha_ci_literals": {
      "provider": "GITHUB_ACTIONS",
      "repository": "yangyy816/project-mirror",
      "result": "PASS",
      "workflow_identity": ".github/workflows/ci.yml"
    }
  },
  "plan_acceptance": {
    "authority_id": "P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_PLAN_ACCEPTANCE_01",
    "authorized_implementation_paths": [
      "services/api/src/mirror_api/demo_d02_r2_locator_custody.py",
      "services/api/tests/test_demo_d02_r2_locator_custody.py"
    ],
    "authorized_scope": "IMPLEMENT_AND_VALIDATE_EXACT_TWO_FILE_WINDOWS_READ_ONLY_HOST_PROJECTION_ONLY",
    "authorized_validation_actions": [
      "RUFF_FORMAT_AND_CHECK_AUTHORIZED_PATHS_ONLY",
      "STRICT_MYPY_AUTHORIZED_IMPLEMENTATION_ONLY",
      "TARGETED_PYTEST_SYNTHETIC_BACKENDS_ONLY",
      "STATIC_CALL_GRAPH_AND_ACCESS_MASK_AUDIT",
      "NATIVE_HARNESS_CONTRACT_TESTS_WITHOUT_STARTING_ETW_OR_TARGET",
      "PRIVATE_PREIMAGE_DISCLOSURE_SCAN",
      "GIT_DIFF_CHECK",
      "INDEPENDENT_EXACT_SHA_IMPLEMENTATION_REVIEW",
      "SAME_SHA_CI"
    ],
    "base_sha": "eacec651518ce84b0a94db28b4fefcb867c2ecff",
    "field_keys": [
      "schema_version",
      "authority_id",
      "change_control_id",
      "reviewed_plan_file_sha256",
      "reviewed_plan_git_blob_oid",
      "reviewed_risk_register_file_sha256",
      "reviewed_risk_register_git_blob_oid",
      "accepted_governance_sha",
      "accepted_governance_tree",
      "base_sha",
      "predecessor_implementation_sha",
      "predecessor_implementation_acceptance_record_digest",
      "predecessor_acceptance_state_sha",
      "predecessor_execution_state_sha",
      "schema_contract_digest",
      "host_projection_contract_digest",
      "independent_review",
      "same_sha_ci",
      "principal_acceptance",
      "authorized_implementation_paths",
      "runtime_dependency_paths",
      "authorized_validation_actions",
      "authorized_scope",
      "prohibited_scope",
      "record_created_at_utc",
      "record_digest"
    ],
    "independent_review_keys": [
      "evidence_digest",
      "findings_p0",
      "findings_p1",
      "findings_p2",
      "findings_p3",
      "result",
      "review_task_id",
      "reviewed_governance_sha"
    ],
    "principal_acceptance_keys": [
      "acceptance_authority_digest",
      "accepted_at_utc",
      "accepted_governance_sha",
      "status"
    ],
    "predecessor_acceptance_state_sha": "889bb6fa2379d3369c1e72d32b4af8cca03387aa",
    "predecessor_execution_state_sha": "eacec651518ce84b0a94db28b4fefcb867c2ecff",
    "predecessor_implementation_acceptance_record_digest": "9421b293f88c6015f1f2f42d449d54bf93bd806fedcf73cb7a76ec4c3bef4f2c",
    "predecessor_implementation_sha": "dd16624ed5ff679b03fefc61994f4ea9fd85e71e",
    "prohibited_scope": [
      "ANY_TRACKED_PATH_OUTSIDE_AUTHORIZED_IMPLEMENTATION_PATHS",
      "NATIVE_ETW_OR_TARGET_EXECUTION_BEFORE_S10_CI",
      "HOST_PERSISTENT_FILESYSTEM_REGISTRY_ACL_OR_WFP_MUTATION",
      "WORKER_CANDIDATE_WRITE",
      "PRIVATE_ROOT_HOME_LOCATOR_OR_TRACE_CREATION",
      "RAW_ETW_OR_PRIVATE_PREIMAGE_RETENTION",
      "SOURCE_GENERATION",
      "M3_M4_EXECUTION",
      "MIGRATION_OR_ORM",
      "POSTGRESQL_ADMISSION",
      "PUBLIC_API_OR_ROUTER_CHANGE",
      "DEPENDENCY_OR_CI_CHANGE",
      "D02_R2_TASK_ACCEPTANCE",
      "D03_D04_B_D07_B_OPENING",
      "FORMAL_PHASE_AUTHORITY",
      "PRODUCTION_RELEASE"
    ],
    "runtime_dependency_paths": [
      "services/api/src/mirror_api/demo_measurement_quality.py"
    ],
    "schema_version": "mirror.demo/D02R2WindowsHostProjectionPlanAcceptance/v1"
  }
}
```

```text
FROZEN_ACCEPTANCE_SCHEMA_CONTRACT_DIGEST: e8d9b8c2fcae83b17e01528dde28eb020a76275d48e4b72d3d148cabe378baa0
```

Any key, type, array order, domain, literal, equality or preimage drift is
`CC10_ACCEPTANCE_SCHEMA_CONTRACT_MISMATCH_STOP`. The Principal-owned launcher, not I10 or candidate bytes, opens the
fixed implementation acceptance path from exact S10 and independently proves the S10/I10/Git equations.

## Production collector and emitter

The implementation adds these minimum boundaries:

```text
WindowsHostProjectionBackend
WindowsHostObservation
_collect_windows_host_observation()
_build_windows_host_binding_candidate()
emit_windows_host_binding_candidate_bytes()
collect_and_emit_windows_host_binding_candidate()
```

`collect_and_emit_windows_host_binding_candidate()` is the sole production entry point. It accepts no arguments and
returns canonical candidate bytes only. It accepts no path, backend, candidate mapping, timestamp, environment
override, fallback or output destination, and never writes a file. Tests may use private synthetic backend and frozen
clock seams; those seams are not production trust roots.

`WindowsHostObservation` carries typed digests, bounded public version tokens and the private preimages required for
final in-memory replay. Raw SID, absolute path, volume serial, file ID, PE bytes, OneDrive values and ETW paths are
excluded from repr and exceptions. Errors expose only fixed stop codes. Same observation and timestamp must produce
byte-identical candidate bytes.

### Principal-owned S10 loader and isolated target

I10 cannot attest its future S10 acceptance. A Principal-owned proof launcher at the exact accepted S10 checkout is
therefore the external trust root. It opens and same-handle verifies the fixed acceptance path, both governed I10
files and the ordered runtime dependency. It validates canonical acceptance bytes, duplicate-key rejection, every
plan/predecessor/schema/contract binding, `A.implementation_sha=I10`, ordered source/test/dependency rows, exact
blob/SHA values and `A.record_digest`. The test row is verified by the launcher but is not loaded into the production
target. The launcher supplies only verified read handles and anonymous pipes; it never supplies a repository path.

The fixed acceptance path is:

```text
docs/operations/P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_IMPLEMENTATION_ACCEPTANCE.json
```

The target creates in-memory modules named `mirror_api.demo_measurement_quality` and
`mirror_api.demo_d02_r2_locator_custody` from the inherited verified bytes, then calls the zero-argument entry point.
It may import only Python standard-library modules. Import from cwd, `sys.path`, site packages, zip files,
`PYTHONPATH`, `PYTHONHOME`, `sitecustomize`, `usercustomize` or caller paths is a stop.

The exact `CreateProcessW` contract is:

```text
lpApplicationName = normalized validated parent sys.executable path; never NULL
lpCommandLine =
  "<python>" -I -S -B -X utf8 -c "<fixed ASCII bootstrap literal>" --
  <source-handle-16hex> <measurement-handle-16hex> <acceptance-handle-16hex>
lpCurrentDirectory = validated Windows-directory path; never NULL or inherited
dwCreationFlags =
  CREATE_SUSPENDED(0x00000004) |
  CREATE_UNICODE_ENVIRONMENT(0x00000400) |
  EXTENDED_STARTUPINFO_PRESENT(0x00080000) |
  CREATE_NO_WINDOW(0x08000000)
bInheritHandles = TRUE only with PROC_THREAD_ATTRIBUTE_HANDLE_LIST
STARTF_USESTDHANDLES = TRUE
```

The explicit sorted target environment contains exactly `COMSPEC`, `SystemRoot` and `windir`, all derived from held
validated authorities. `PATH`, `PATHEXT`, drive pseudo-variables, proxy/credential keys, `HOME`, `USERPROFILE`,
`APPDATA`, `LOCALAPPDATA`, `TEMP`, `TMP`, every `PYTHON*` and every `MIRROR_*` key are absent. Exact inherited handles
are source, measurement dependency, acceptance, stdout-write, stderr-write and an EOF stdin-read handle. Every other
handle is non-inheritable. Before `ResumeThread`, the observer is active and the target is assigned to a non-breakaway
Job with `ActiveProcessLimit=2` and `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.

The fixed bootstrap reads length-framed bytes from the three input handles, enforces their maxima, hashes them,
validates A, compiles and executes the two modules in memory and emits exactly one transport frame. It accepts no
code, path, environment or output argument. The frame is:

```text
magic = PMD02CC10HOSTCANDIDATEV1\0
magic hex = 504d44303243433130484f535443414e444944415445563100
length = one unsigned 32-bit big-endian payload length
payload = exact canonical candidate bytes
MAX_CANDIDATE_BYTES = 65536
MAX_STDERR_BYTES = 256
success stderr = empty
success EOF = immediately after payload
failure stdout = empty
failure stderr = exactly one fixed ASCII stop code plus LF
```

Extra bytes, missing EOF, multiple frames, malformed length, oversized output or mixed success/failure channels stop.
The outer frame is transport only and never enters candidate authority.

`CreateProcessW` has no preopened-image-handle entry point. CC10 therefore freezes a lock-before-launch and
post-launch mapped-image identity proof: the original Python executable handle remains open with read sharing only
and without write/delete sharing; every parent directory is held and non-reparse; `lpApplicationName` is the exact
normalized path; before resume, `QueryFullProcessImageNameW` must return that mapped image path; a second read-only
handle to that mapped path must have the same volume/file identity, size and SHA-256 while the original lock remains
held. The same mechanism applies to the PowerShell child before it runs. Any unavailable API, path/identity/hash drift,
IFEO/debugger substitution or inability to prove the equality is `CC10_EXECUTED_IMAGE_IDENTITY_UNPROVEN_STOP`.
Rehashing an unlocked pathname before/after launch is never sufficient.

## Principal and filesystem projection

The current process token is the sole principal authority:

```text
GetCurrentProcess
-> OpenProcessToken(TOKEN_QUERY)
-> GetTokenInformation(TokenUser)
-> canonical SID string
-> TD(mirror.governance/WindowsPrincipalSid/v1, {sid_string})
```

User name, environment text and caller-supplied SID are forbidden. The collector resolves exactly
`FOLDERID_LocalAppData`, `FOLDERID_Profile`, `GetWindowsDirectoryW()` and `GetSystemDirectoryW()`. It opens existing
directories with read/attribute/`READ_CONTROL`/`SYNCHRONIZE` access, no-follow semantics and no write/delete share.
Identity, attributes, ACL and parent relationships come from still-open handles.

It proves the handle-relative Profile/AppData/Local relationship, fixed-local volume, no reparse/cloud state, the
accepted CC09 OneDrive boundary, sufficient free space and exact Windows/System/PowerShell-module-root roles. ACL
collection uses `GetSecurityInfo`, complete ACE parsing, `MapGenericMask` and `AccessCheck`; no setter is reachable.

Absence probes for `ProjectMirror` and `ProjectMirror-code-cache-v1` are handle-relative under the accepted
LocalAppData handle. Only exact not-found status is accepted. Existing, inaccessible, reparse, unknown or ambiguous
state stops. Nothing is created, adopted, deleted or repaired.

## Git and executable authority

Python authority is current `sys.executable`. Windows, System32, PowerShell, cmd and the four accepted system DLLs are
derived only from handle-validated Windows/System-directory authorities. PATH, cwd, `SearchPathW`, `where.exe` and
`Get-Command` are never executable authority.

Git has one resolver:

```text
ROOT: HKEY_LOCAL_MACHINE
VIEW: 64_BIT_ONLY
KEY: SOFTWARE\GitForWindows
VALUE: InstallPath
TYPE: REG_SZ_ONLY
SUFFIX: cmd\git.exe
ACCESS: KEY_QUERY_VALUE|KEY_WOW64_64KEY
FALLBACK: NONE
```

HKCU, 32-bit view, PATH, PATHEXT, cwd and second-candidate fallback are forbidden. A missing key, wrong type,
nonlocal/reparse path, missing executable or identity drift stops.

Every executable, DLL, manifest and script is opened `OPEN_EXISTING` with read-only access and no write/delete share.
The same handle supplies file identity, size and SHA-256. PE machine type and version-resource ProductName/
ProductVersion are parsed from those exact bytes; path-based version lookup, WinTrust and replacement between hash and
metadata are forbidden. Final identity/size/hash replay occurs before timestamp capture.

PE metadata parsing is exact and fail closed. From the still-open bytes, parse checked DOS/NT headers, section-table
RVA mapping and the `RT_VERSION` resource tree. Require exactly one unambiguous version-resource leaf and one valid
`VS_FIXEDFILEINFO`; duplicate resource ID/language, malformed offset/alignment/UTF-16 or bounds overflow stops.
`VarFileInfo\\Translation` must be nonempty and contain unique language/codepage pairs. Every `StringFileInfo` table
key is exactly eight ASCII hex digits naming one declared pair and contains exactly one `ProductName` and one
`ProductVersion`; duplicate keys/tables stop even when their text matches. Values must be nonempty, correctly
NUL-terminated printable UTF-16 without embedded NUL or malformed surrogate. All declared translations are evaluated:
different ProductName/ProductVersion text across valid tables is `PE_VERSION_TRANSLATION_CONFLICT_STOP`; identical
text selects the smallest `(language_id,codepage)` only as a deterministic audit selector. File identity, size, hash,
machine and version values are replayed from the same held bytes before the sole timestamp read.

## PowerShell and timestamp

PowerShell is the fixed System32 Windows PowerShell executable and uses exactly:

```text
lpApplicationName = exact validated System32 Windows PowerShell executable path; never NULL
lpCommandLine =
  "<powershell>" -NoLogo -NoProfile -NonInteractive -EncodedCommand <fixed UTF-16LE script>
lpCurrentDirectory = validated Windows-directory path; never NULL or inherited
dwCreationFlags =
  CREATE_SUSPENDED(0x00000004) |
  CREATE_UNICODE_ENVIRONMENT(0x00000400) |
  EXTENDED_STARTUPINFO_PRESENT(0x00080000) |
  CREATE_NO_WINDOW(0x08000000)
bInheritHandles = TRUE only with PROC_THREAD_ATTRIBUTE_HANDLE_LIST
STARTF_USESTDHANDLES = TRUE
inherited handles = stdin EOF-read, stdout-write and stderr-write only
source, measurement-dependency and acceptance handles = MUST_NOT_BE_INHERITED
```

`-ExecutionPolicy`, `-File`, arbitrary command/script/path input, shell and cmd launch are forbidden. Its sorted
environment contains exactly:

```text
SystemRoot=<validated Windows directory>
windir=<same value>
COMSPEC=<validated System32 cmd.exe>
PSModulePath=<validated system PowerShell module root only>
PSModuleAnalysisCachePath=NUL
```

`PATH`, `PATHEXT`, `HOME`, `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `TEMP`, `TMP`, every proxy/credential key,
`PSExecutionPolicyPreference`, every `PYTHON*`, every `MIRROR_*` and inherited drive variables are absent. The fixed
script sets `ErrorActionPreference=Stop`, Warning/Information/Verbose/Progress preferences to `SilentlyContinue` and
`PSModuleAutoloadingPreference=None`; it explicitly imports only the two held/validated manifest authorities and
projects exactly the frozen rows. Failure in this environment stops; user profile, cache, temp, PATH or inherited
environment is never added as fallback. `PSModuleAnalysisCachePath=NUL` is prevention only; any observed persistent
profile/module/cache write is `POWERSHELL_ENVIRONMENT_OR_CACHE_WRITE_STOP`.

The PowerShell executable is held without write/delete sharing. Before `ResumeThread`, the mapped-image identity is
replayed through `QueryFullProcessImageNameW` plus a second read-only mapped-path handle while the original lock is
still held, using the same volume/file identity, size and SHA-256 equality as the Python target. The suspended child
must already be in the same non-breakaway Job, and `IsProcessInJob` plus Job accounting must prove membership before
resume. `CREATE_BREAKAWAY_FROM_JOB`, an inherited source/dependency/acceptance handle, an inherited caller handle or
an unverified mapped image is `CC10_EXECUTED_IMAGE_IDENTITY_UNPROVEN_STOP`.

The collector reproduces the accepted two manifests, three nested members, three cmdlet rows, four script rows,
four-part PowerShell version and runtime closure. stdout contains one bounded canonical projection; stderr, an extra
object/module root/child or network attempt stops. `cmd.exe` is identified but not launched.

The Principal-owned S10 proof launcher is the sole OS-build authority. While it still holds and has replayed the exact
normalized `sys.executable` file identity, size and SHA-256, it calls the real built-in `sys.getwindowsversion()` once
before creating the calibration/target process and once after target/PowerShell termination, native-observer cleanup
and privilege restoration. Both calls must return non-boolean integer `major`, `minor` and `build` fields in
`[0,4294967295]`, and the ordered triples must be identical. `os_build` is exactly the canonical no-leading-zero decimal
serialization `major.minor.build` (with the single character `0` allowed for zero).

`sys.getwindowsversion().platform_version`, registry UBR, kernel32 or other PE ProductVersion/revision, an appended
zero, caller/environment text and components combined from different sources are forbidden. There is no fallback,
retry-selected value or normalization from a four-component token. A missing field, wrong type/range/count, alternate
source, mixed source or pre/post mismatch is `WINDOWS_HOST_PROJECTION_OS_BUILD_AUTHORITY_STOP` and produces no proof or
candidate.

Production time comes from exactly one `GetSystemTimePreciseAsFileTime` call after all handles, hashes, ACLs,
PowerShell rows and cross-equalities replay and while identity handles remain open. FILETIME ticks subtract
`116444736000000000`; Unix microseconds use integer floor by ten. The UTC form has six fractional digits and `Z`.
There is no caller timestamp, `datetime.now()` fallback, retry or rollback tolerance.

## Static no-write contract

The reachable production graph is allowlisted to token, Known Folder, registry query/enumeration, existing-handle
metadata/security, access check, file read/hash/PE parse, time, anonymous-pipe, fixed PowerShell process and Job APIs.
All file opens are existing/read-only; all registry opens are query/enumerate-only. The graph contains no create,
overwrite, persistent `WriteFile`, truncate, delete, rename, file/security setter, registry setter/deleter, writable
mapping, WFP mutation, WinTrust, arbitrary shell, network or DNS API.

The only permitted proof-time mutation is temporary kernel/token/process state: anonymous pipes, suspended process and
thread handles, one non-breakaway Job Object, one real-time memory-only ETW session, proof-owned loopback sockets and
exact enable/restore of `SeSystemProfilePrivilege`. No persistent filesystem, registry, ACL, WFP, AutoLogger, service,
task, profile, cache or environment mutation is authorized. Cleanup failure can terminate the Job, close proof-owned
handles and stop the proof; it cannot delete, repair, rename or adopt host bytes.

## Native PID-tree proof

The observer starts before calibration or target creation. The proof request identity is fixed:

```text
proof_task_id = P3_P7_D02_CC10_NATIVE_PROOF_01
proof_run_id = first_32_hex(
  TD(mirror.demo/D02R2WindowsHostProjectionProofRun/v1,
     {implementation_acceptance_record_digest, proof_task_id})
)
session_name = ProjectMirror.CC10.NativeNoWrite.<proof_run_id>
attempt_limit = 1
```

The exact session name is queried before start. Only `ERROR_WMI_INSTANCE_NOT_FOUND` means absent; present, ambiguous or
any other result is `ETW_SESSION_COLLISION_STOP`. A later process never stops a pre-existing session by name: only the
creating proof process holding the returned TRACEHANDLE owns cleanup. Crash residue therefore requires forward
Principal recovery/change control or host restart evidence; it is never silently adopted or removed. `StartTraceW`
uses `EVENT_TRACE_PROPERTIES_V2` with:

```text
Wnode.Flags = WNODE_FLAG_TRACED_GUID | WNODE_FLAG_VERSIONED_PROPERTIES
Wnode.ClientContext = 1
Wnode.Guid = GUID_NULL
Wnode.BufferSize = aligned sizeof(EVENT_TRACE_PROPERTIES_V2) plus exact inline session-name bytes
LogFileMode = EVENT_TRACE_REAL_TIME_MODE | EVENT_TRACE_NO_PER_PROCESSOR_BUFFERING
BufferSize = 64 KiB
MinimumBuffers = 64
MaximumBuffers = 64
FlushTimer = 1 second
LogFileNameOffset = 0
V2Options = 0
VersionNumber = 2
FilterDescCount = 0
LoggerNameOffset = exact inline UTF-16 session-name offset
all other input-only/reserved fields = 0
```

The proof retains the returned `TRACEHANDLE`; ownership is `(TRACEHANDLE,exact session_name,proof_run_id)`. It never
stops an unowned name-only session. `OpenTraceW` uses
`PROCESS_TRACE_MODE_REAL_TIME|PROCESS_TRACE_MODE_EVENT_RECORD`. Each `EnableTraceEx2` uses
`EVENT_CONTROL_CODE_ENABLE_PROVIDER`, timeout zero, `ENABLE_TRACE_PARAMETERS.Version=2`, no filters,
`EnableProperty=0` and the exact matrix:

| Provider               | GUID                                   |             Level | MatchAnyKeyword | MatchAllKeyword |
| ---------------------- | -------------------------------------- | ----------------: | --------------: | --------------: |
| Kernel-Process         | `22FB2CD6-0E7B-422B-A0C7-2FAD1FD0E716` | Informational `4` |          `0x10` |             `0` |
| Kernel-File            | `EDD08927-9CC4-4E65-B970-C2560FB5C289` | Informational `4` |        `0x1EF0` |             `0` |
| Kernel-Registry        | `70EB4F03-C1DE-4F73-A051-33D13D5413BD` | Informational `4` |        `0x5344` |             `0` |
| Winsock-AFD            | `E53C6823-7BB8-44BB-90DC-3F86090D48A6` |       Verbose `5` |           `0x4` |             `0` |
| Winsock-NameResolution | `55404E71-4DB9-4DEB-A5F5-8F86E46DDE56` | Informational `4` |             `0` |             `0` |

### Privilege authority

The proof opens the current-process token with `TOKEN_QUERY|TOKEN_ADJUST_PRIVILEGES`, resolves exactly
`SeSystemProfilePrivilege`, sets last error to `ERROR_SUCCESS`, enables only that LUID with
`AdjustTokenPrivileges` and captures the exact prior attributes. API failure, `ERROR_NOT_ALL_ASSIGNED`, absent or
malformed prior state, LUID mismatch or unverifiable state is `ETW_PRIVILEGE_ENABLE_STOP`. In `finally`, it restores
the exact captured attributes, again rejects API failure/`ERROR_NOT_ALL_ASSIGNED`, rereads `TokenPrivileges`, requires
the original LUID attributes and closes the token. Failure is `ETW_PRIVILEGE_RESTORE_STOP`. An already-enabled
privilege is still restored to its exact original enabled state; `RtlAdjustPrivilege` and blanket enable are forbidden.

### Event identity, calibration and mutation matrix

Process authority is Kernel-Process event ID `1`, version exactly `3` or `4`, task `ProcessStart`, opcode `Start`.
The stable key is `(ProcessID,ProcessSequenceNumber)` and parent key is
`(ParentProcessID,ParentProcessSequenceNumber)`; versions 0–2 and PID-only identity stop. Target and fixed PowerShell
image identities must also match the pre-resume mapped-image proof. Job membership, ProcessStart rows and terminal
wait/Job accounting must agree; missing start, unexpected child, breakaway, PID reuse ambiguity or incomplete closure
is `ETW_PID_TREE_INCOMPLETE_STOP`.

Before the production target, the same memory-only observer runs one proof-owned calibration process in the Job. It
may use only temporary process/kernel/token state, one proof-owned IPv4/IPv6 loopback listener, an existing held
read-only file, and a query-only HKLM registry handle. It must establish all of the following without persistent
mutation:

```text
Kernel-File EVENT_HEADER.ProcessId attribution to ProcessSequenceNumber
Kernel-File ID=12 CreateOptions decoding with create_disposition=(CreateOptions >> 24) & 0xff
Kernel-File ID=15 read Irp -> ID=24 OperationEnd correlation and Status semantics
Kernel-Registry ID=7 opcode=38 QueryValueKey EVENT_HEADER.ProcessId attribution and direct Status semantics
Winsock-AFD target attribution using only the proof-owned loopback endpoint
Winsock-NameResolution target attribution using only literal localhost
```

Calibration performs at least one successful read against the held existing file and at least one successful
`QueryValueKey` against the query-only registry handle. It performs no file or registry mutator intent. It also
performs at least one attributable loopback AFD event and one attributable localhost NameResolution event; any
non-loopback event or any mutator intent stops. Missing, failed, extra or unattributable calibration evidence is one of
`ETW_FILE_PID_ATTRIBUTION_UNAVAILABLE_STOP`, `ETW_FILE_CREATE_SEMANTICS_UNAVAILABLE_STOP`,
`ETW_REGISTRY_PID_ATTRIBUTION_UNAVAILABLE_STOP` or `ETW_NETWORK_ATTRIBUTION_UNAVAILABLE_STOP`. Calibration identities
are excluded from collector counts but are retained as aggregate path-free proof fields.

The collector file matrix is exact:

```text
Create/open: ID=12, versions {0,1}, correlation key Irp
  create_disposition must equal FILE_OPEN(1); any other value is a mutating intent and STOP
Read calibration: ID=15, versions {0,1}, correlation key Irp
OperationEnd: ID=24, version 0, fields Irp, ExtraInformation, Status
Mutator intent IDs and versions:
  16 Write {0,1}
  17 SetInformation {0,1}
  18 SetDelete {0,1}
  19 Rename {0,1}
  21 Flush {0,1}
  23 FSCTL {0,1}
  26 DeletePath {0,1}
  27 RenamePath {0,1}
  28 SetLinkPath {0,1}
  29 Rename {0,1}
  30 CreateNewFile {0,1}
  31 SetSecurity {1}
  33 SetEA {1}
```

For ID12 and every mutator intent, `(ProcessSequenceNumber,Irp)` must have exactly one later ID24 completion. A
completion without one live intent, two live intents with the same key, completion before intent, duplicate completion
or unresolved intent at drain stops. Attempt count increments on the intent event regardless of final Status; success
count increments only when `Status=0`. Any collector mutator intent count greater than zero fails closed even if every
completion failed. Anonymous-pipe operations are allowed only for the six inherited pipe/byte handles and are excluded
by exact handle identity, never by path text.

The collector registry matrix is version `0` with direct `Status`:

```text
event ID 1  opcode 32 CreateKey
event ID 3  opcode 34 DeleteKey
event ID 5  opcode 36 SetValueKey
event ID 6  opcode 37 DeleteValueKey
event ID 11 opcode 42 SetInformationKey
event ID 15 opcode 46 SetSecurityKey
```

Any attributable collector row in that matrix is an attempted mutation and fails regardless of Status; `Status=0`
also increments successful mutation. Any Winsock-AFD or NameResolution event attributable to the collector target or
PowerShell child fails. Unknown required version/schema, malformed TDH data, ambiguous PID/process-sequence mapping,
unresolved status or out-of-order evidence stops; no provider event is silently dropped.

After all target/child handles are signalled, the only terminal sequence is:

```text
ControlTraceW(owned TRACEHANDLE, exact name, STOP) returns final EVENT_TRACE_PROPERTIES_V2
-> ProcessTrace completes delivery and the consumer thread joins
-> final STOP-time EventsLost/LogBuffersLost/RealTimeBuffersLost are each validated as integer zero
-> CloseTrace closes the consumer handle
-> exact-name QUERY returns only ERROR_WMI_INSTANCE_NOT_FOUND
```

A pre-STOP QUERY is not final loss authority, and `CloseTrace` must not precede the owned STOP, complete drain/join or
final loss validation. The Job then has zero active processes; all process/thread/pipe/socket/token/session handles
are closed; privilege replay passes. Any missing versioned-properties flag, STOP output, drain/join, final loss value,
consumer close or absence replay is `NATIVE_NO_WRITE_PROOF_UNAVAILABLE_STOP`, `ETW_EVENT_LOSS_STOP` or
`ETW_CLEANUP_FAILED_STOP` and cannot produce a proof or candidate.

No `.etl`, AutoLogger, Procmon log, event dump or private trace exists. The combined claim is limited to zero collector
PID-tree persistent filesystem/registry mutation and zero attributable collector network events under a complete,
calibrated, lossless observation. It does not claim enforcement of public-egress denial or zero causal writes by
unrelated system services.

## Native proof summary

Raw ETW is never retained. After the authorized native Gate, the path-free canonical summary is tracked only at
`docs/operations/P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_NATIVE_PROOF.json` under
`mirror.demo/D02R2WindowsHostProjectionNativeProof/v1`. It contains exactly:

```text
schema_version, authority_id, change_control_id, proof_task_id, proof_run_id,
implementation_sha, implementation_tree, implementation_acceptance_record_digest,
implementation_acceptance_state_sha, implementation_acceptance_state_tree,
implementation_acceptance_path, implementation_acceptance_git_blob_oid,
implementation_acceptance_file_sha256,
plan_acceptance_record_digest, schema_contract_digest, host_projection_contract_digest,
candidate_sha, candidate_tree, candidate_path, candidate_git_blob_oid,
candidate_record_digest, candidate_file_sha256, candidate_byte_size,
os_build, os_architecture, python_version,
invocation_contract_digest, runtime_dependency_digest, synthetic_ledger_digest, etw_contract_digest,
process_tree, calibration, filesystem_observation, registry_observation, network_observation,
loss_counters, lifecycle, cleanup, private_retention, network_claim,
result, record_created_at_utc, record_digest
```

`authority_id=P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_NATIVE_PROOF_01`,
`change_control_id=P3_P7_D02_CC_10`, `proof_task_id=P3_P7_D02_CC10_NATIVE_PROOF_01`,
`os_architecture=AMD64`, `private_retention=RAW_ETW_NONE_PRIVATE_PREIMAGE_MEMORY_ONLY`,
`network_claim=ZERO_TARGET_ATTRIBUTED_NETWORK_EVENTS_OBSERVED_NOT_EGRESS_ENFORCEMENT` and `result=PASS`.
`candidate_byte_size` is an integer in `[1,65536]`; all other counters below are nonnegative non-boolean integers.
`os_build` is the three-component dotted decimal Windows version built only from the Principal launcher's two matching
`sys.getwindowsversion()` observations described below, and `python_version` is the bounded dotted decimal version
returned by the verified executable; neither accepts arbitrary host text.

Native-proof bytes use `demo-canonical-json-v1` exactly: UTF-8 without BOM, duplicate keys rejected, no insignificant
whitespace, lexicographically sorted object keys, preserved array order, only JSON booleans/integers/strings/null and
no terminal LF. The top-level key set above and every nested key set below are exact; extension keys are forbidden.
`record_digest = TD(schema_version, record excluding only record_digest)`. The fixed path is
`docs/operations/P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_NATIVE_PROOF.json`; the fixed candidate path is
`docs/operations/P3_P7_D02_R2_WINDOWS_HOST_BINDING_CANDIDATE.json`.

The scalar authority is fully typed:

```text
schema_version = literal mirror.demo/D02R2WindowsHostProjectionNativeProof/v1
authority_id = literal P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_NATIVE_PROOF_01
change_control_id = literal P3_P7_D02_CC_10
proof_task_id = literal P3_P7_D02_CC10_NATIVE_PROOF_01
proof_run_id = exactly 32 lowercase hex
all *_sha and *_tree values = exactly 40 lowercase hex
all *_git_blob_oid values = exactly 40 lowercase hex
all *_digest and *_sha256 values = exactly 64 lowercase hex
implementation_acceptance_path = fixed implementation-acceptance path above
candidate_path = fixed candidate path above
candidate_byte_size = non-boolean integer [1,65536]
os_build = three canonical unsigned decimal components, each [0,4294967295]
os_architecture = literal AMD64
python_version = three canonical unsigned decimal components, each [0,4294967295]
private_retention = literal RAW_ETW_NONE_PRIVATE_PREIMAGE_MEMORY_ONLY
network_claim = literal ZERO_TARGET_ATTRIBUTED_NETWORK_EVENTS_OBSERVED_NOT_EGRESS_ENFORCEMENT
result = literal PASS
record_created_at_utc = normalized YYYY-MM-DDTHH:MM:SS.ffffffZ
record_digest = exactly 64 lowercase hex
```

Every nested `PASS`, `NOT_PROVIDED_BY_CC10`, boolean and fixed count below is an exact literal. Every variable count is
a non-boolean integer within its stated range; no float, negative zero, implicit timestamp, path, unordered set or
extra key is authority. Duplicate, noncanonical, ill-typed or out-of-range proof bytes are
`CC10_HOST_PROJECTION_CONTRACT_MISMATCH_STOP`.

The final proof is constructed only after SC exists and obeys all of these equations:

```text
proof.implementation_sha = I10
proof.implementation_tree = tree(I10)
proof.implementation_acceptance_state_sha = S10
proof.implementation_acceptance_state_tree = tree(S10)
proof.implementation_acceptance_path = fixed implementation-acceptance path
proof.implementation_acceptance_git_blob_oid = blob(S10:implementation-acceptance path)
proof.implementation_acceptance_file_sha256 = SHA256(bytes(S10:implementation-acceptance path))
proof.implementation_acceptance_record_digest = A.record_digest
proof.plan_acceptance_record_digest = A.accepted_plan_acceptance_record_digest
proof.schema_contract_digest = A.schema_contract_digest
proof.host_projection_contract_digest = A.host_projection_contract_digest
proof.candidate_sha = SC
proof.candidate_tree = tree(SC)
proof.candidate_path = fixed candidate path
proof.candidate_git_blob_oid = blob(SC:candidate path)
proof.candidate_file_sha256 = SHA256(bytes(SC:candidate path))
proof.candidate_byte_size = byte_size(SC:candidate path)
proof.candidate_record_digest = C.record_digest
C = strict canonical record parsed from exact bytes(SC:candidate path)
SC:<implementation-acceptance path> byte-equals S10:<implementation-acceptance path>
```

The native observation necessarily precedes SC. It therefore produces only one path-free, non-authoritative,
untracked observation draft with no claimed SC SHA/tree/blob and no native-proof `record_digest` authority. After the
candidate-only SC commit has passed independent review and same-SHA CI, the Principal binds exact S10/A/I10 and SC/C
bytes to construct the final canonical proof record for SH. A draft may never be renamed, re-signed or cited as the
final proof, and SC fields may never be predicted before SC exists.

The four subordinate digests are exact:

```text
invocation_contract_digest =
  TD(mirror.demo/D02R2WindowsHostProjectionInvocationContract/v1,
     {acceptance_loader, bootstrap, output_frame, production_entrypoint}
     from HOST_PROJECTION_CONTRACT_PREIMAGE)

runtime_dependency_digest =
  TD(mirror.demo/D02R2WindowsHostProjectionRuntimeDependencies/v1,
     {runtime_dependencies: A.runtime_dependencies})

synthetic_ledger_digest =
  TD(mirror.demo/D02R2WindowsHostProjectionSyntheticCallLedger/v1,
     {rows: ordered rows each with exactly
       [sequence, role, api_family, requested_access, share_mask,
        disposition, output_class, result_class]})

etw_contract_digest =
  TD(mirror.demo/D02R2WindowsHostProjectionEtwContract/v1,
     HOST_PROJECTION_CONTRACT_PREIMAGE.etw)
```

Nested objects have exactly these keys and success values:

```text
process_tree = {
  identity_field: ProcessSequenceNumber,
  observer_before_calibration: true,
  observer_before_target: true,
  target_created_suspended: true,
  job_assigned_before_resume: true,
  job_breakaway_forbidden: true,
  job_active_process_limit: 2,
  calibration_process_count: 1,
  collector_process_count: 1,
  powershell_child_count: 1,
  unexpected_process_count: 0,
  all_processes_terminal: true,
  result: PASS
}

calibration = {
  file_event_header_pid_attribution: PASS,
  file_create_disposition_decode: PASS,
  file_irp_operation_end_correlation: PASS,
  registry_event_header_pid_attribution: PASS,
  afd_target_attribution: PASS,
  name_resolution_target_attribution: PASS,
  file_read_probe_count: integer >= 1,
  registry_query_probe_count: integer >= 1,
  file_mutator_intent_count: 0,
  registry_mutator_intent_count: 0,
  loopback_afd_event_count: integer >= 1,
  localhost_name_resolution_event_count: integer >= 1,
  non_loopback_network_event_count: 0,
  persistent_filesystem_mutation_count: 0,
  persistent_registry_mutation_count: 0,
  result: PASS
}

filesystem_observation = {
  open_existing_event_count: integer >= 1,
  mutator_intent_count: 0,
  mutator_success_count: 0,
  unresolved_irp_count: 0,
  unsupported_result_event_count: 0,
  result: PASS
}

registry_observation = {
  query_event_count: integer >= 1,
  mutator_intent_count: 0,
  mutator_success_count: 0,
  unsupported_result_event_count: 0,
  result: PASS
}

network_observation = {
  afd_target_event_count: 0,
  name_resolution_target_event_count: 0,
  unattributed_provider_event_count: 0,
  enforcement: NOT_PROVIDED_BY_CC10,
  result: PASS
}

loss_counters = {
  events_lost: 0,
  log_buffers_lost: 0,
  real_time_buffers_lost: 0
}

lifecycle = {
  session_preexisting: false,
  versioned_properties_flag_present: true,
  all_providers_enabled: true,
  mapped_python_identity_replayed: true,
  mapped_powershell_identity_replayed: true,
  output_frame_valid: true,
  candidate_replay_valid: true,
  result: PASS
}

cleanup = {
  control_trace_stop: PASS,
  stop_returned_final_properties: true,
  process_trace_drain_complete: true,
  consumer_thread_joined: true,
  final_loss_counters_validated: true,
  close_trace: PASS,
  session_absence_replay: PASS,
  terminal_sequence: CONTROL_TRACE_STOP_THEN_PROCESS_TRACE_DRAIN_JOIN_THEN_FINAL_LOSS_VALIDATION_THEN_CLOSE_TRACE_THEN_ABSENCE_REPLAY,
  job_active_processes: 0,
  job_closed: true,
  process_thread_pipe_socket_handles_closed: true,
  privilege_restored: true,
  result: PASS
}
```

The proof contains no path, SID, PID, process sequence number, file ID, volume serial, PE bytes, ETW event, endpoint,
registry value or raw preimage. Those values may exist only transiently in controlled process memory, are excluded
from repr/errors/stdout/stderr and are gone when handles/processes close. CC10 therefore means “not persisted,
tracked, logged or output”, not “private preimages never existed in memory”.

Immediately after the one native run, the Principal preserves the exact path-free observation as the explicitly
non-authoritative untracked draft defined above; no raw trace accompanies it. SC stages and commits only the candidate
path. After SC review/CI, the Principal reopens exact S10/A and SC/C Git bytes, verifies every frozen equation and
constructs the final canonical proof at the fixed future tracked path. SH stages that proof plus host acceptance. If
the observation draft is missing or changes before construction, the run is not reconstructed from prose and the
proof stops. These Principal Git-evidence writes occur outside the observed collector PID tree and do not authorize
the collector, PowerShell or worker to write any path.

The proof is committed with later host acceptance, not with SC. The unchanged CC09 host-acceptance schema binds it
through `independent_review.evidence_digest`, exactly:

```text
TD(mirror.demo/D02R2WindowsHostProjectionHostReviewEvidence/v1,
   {review_task_id, reviewed_candidate_sha, candidate_record_digest,
    native_proof_record_digest, cc10_implementation_acceptance_record_digest,
    findings_p0, findings_p1, findings_p2, findings_p3, result})
```

`reviewed_candidate_sha=SC`, each finding is integer zero and `result=PASS`. No candidate-schema change,
self-signature or candidate-provided trust mapping is introduced.

### Host-projection contract digest preimage

`host_projection_contract_digest` is exactly
`TD(mirror.demo/D02R2WindowsHostProjectionContract/v1, HOST_PROJECTION_CONTRACT_PREIMAGE)` using this JSON object. The
implementation must expose the same payload as a pure constant builder; neither tests nor a caller may override it.

```json
{
  "acceptance_loader": {
    "acceptance_path": "docs/operations/P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_IMPLEMENTATION_ACCEPTANCE.json",
    "dependency_module": "mirror_api.demo_measurement_quality",
    "governed_paths": [
      "services/api/src/mirror_api/demo_d02_r2_locator_custody.py",
      "services/api/tests/test_demo_d02_r2_locator_custody.py"
    ],
    "runtime_dependencies": [
      "services/api/src/mirror_api/demo_measurement_quality.py"
    ],
    "source_module": "mirror_api.demo_d02_r2_locator_custody",
    "trust_root": "PRINCIPAL_S10_EXTERNAL_HANDLE_LOADER"
  },
  "bootstrap": {
    "application_name": "EXACT_VALIDATED_PARENT_SYS_EXECUTABLE",
    "arguments": [
      "-I",
      "-S",
      "-B",
      "-X",
      "utf8",
      "-c",
      "FIXED_ASCII_BOOTSTRAP",
      "--",
      "SOURCE_HANDLE_16HEX",
      "MEASUREMENT_HANDLE_16HEX",
      "ACCEPTANCE_HANDLE_16HEX"
    ],
    "creation_flags": [
      "CREATE_SUSPENDED",
      "CREATE_UNICODE_ENVIRONMENT",
      "EXTENDED_STARTUPINFO_PRESENT",
      "CREATE_NO_WINDOW"
    ],
    "cwd": "VALIDATED_WINDOWS_DIRECTORY",
    "environment_keys": ["COMSPEC", "SystemRoot", "windir"],
    "inherited_handle_roles": [
      "SOURCE_READ",
      "MEASUREMENT_READ",
      "ACCEPTANCE_READ",
      "STDOUT_WRITE",
      "STDERR_WRITE",
      "STDIN_EOF_READ"
    ],
    "job_active_process_limit": 2,
    "job_limits": ["NON_BREAKAWAY", "KILL_ON_CLOSE"],
    "mapped_image_identity": "HELD_NO_WRITE_DELETE_SHARE_PLUS_QUERY_FULL_PROCESS_IMAGE_NAME_PLUS_FILE_ID_SIZE_SHA_REPLAY",
    "module_loading": "IN_MEMORY_VERIFIED_BYTES_ONLY"
  },
  "etw": {
    "calibration": [
      "FILE_EVENT_HEADER_PID",
      "FILE_CREATE_DISPOSITION",
      "FILE_READ_IRP_OPERATION_END",
      "REGISTRY_QUERY_EVENT_HEADER_PID",
      "AFD_LOOPBACK_ATTRIBUTION",
      "NAME_RESOLUTION_LOCALHOST_ATTRIBUTION"
    ],
    "file_mutator_events": [
      [16, [0, 1]],
      [17, [0, 1]],
      [18, [0, 1]],
      [19, [0, 1]],
      [21, [0, 1]],
      [23, [0, 1]],
      [26, [0, 1]],
      [27, [0, 1]],
      [28, [0, 1]],
      [29, [0, 1]],
      [30, [0, 1]],
      [31, [1]],
      [33, [1]]
    ],
    "file_open_event": [12, [0, 1], "FILE_OPEN_1_ONLY"],
    "file_operation_end_event": [24, 0, "IRP_EXTRA_INFORMATION_STATUS"],
    "file_read_event": [15, [0, 1]],
    "loss_counters": ["EventsLost", "LogBuffersLost", "RealTimeBuffersLost"],
    "process_start_event": [
      1,
      [3, 4],
      "ProcessSequenceNumber",
      "ParentProcessSequenceNumber"
    ],
    "providers": [
      ["22FB2CD6-0E7B-422B-A0C7-2FAD1FD0E716", 4, 16, 0],
      ["EDD08927-9CC4-4E65-B970-C2560FB5C289", 4, 7920, 0],
      ["70EB4F03-C1DE-4F73-A051-33D13D5413BD", 4, 21316, 0],
      ["E53C6823-7BB8-44BB-90DC-3F86090D48A6", 5, 4, 0],
      ["55404E71-4DB9-4DEB-A5F5-8F86E46DDE56", 4, 0, 0]
    ],
    "registry_query_event": [7, 0, 38],
    "registry_mutator_events": [
      [1, 0, 32],
      [3, 0, 34],
      [5, 0, 36],
      [6, 0, 37],
      [11, 0, 42],
      [15, 0, 46]
    ],
    "session": {
      "buffer_size_kib": 64,
      "client_context": 1,
      "enable_property": 0,
      "filter_count": 0,
      "flush_timer_seconds": 1,
      "log_file_mode": [
        "EVENT_TRACE_REAL_TIME_MODE",
        "EVENT_TRACE_NO_PER_PROCESSOR_BUFFERING"
      ],
      "maximum_buffers": 64,
      "minimum_buffers": 64,
      "name_prefix": "ProjectMirror.CC10.NativeNoWrite.",
      "raw_retention": "NONE",
      "terminal_sequence": [
        "CONTROL_TRACE_STOP_OWNED_HANDLE_RETURNS_FINAL_PROPERTIES",
        "PROCESS_TRACE_COMPLETE_DRAIN",
        "CONSUMER_THREAD_JOIN",
        "VALIDATE_FINAL_STOP_TIME_LOSS_COUNTERS",
        "CLOSE_TRACE_CONSUMER_HANDLE",
        "EXACT_NAME_ABSENCE_REPLAY"
      ],
      "version_number": 2,
      "wnode_flags": [
        "WNODE_FLAG_TRACED_GUID",
        "WNODE_FLAG_VERSIONED_PROPERTIES"
      ],
      "wnode_guid": "GUID_NULL"
    }
  },
  "network_claim": "ZERO_TARGET_ATTRIBUTED_NETWORK_EVENTS_OBSERVED_NOT_EGRESS_ENFORCEMENT",
  "os_build_authority": {
    "call_count": 2,
    "caller": "PRINCIPAL_S10_EXTERNAL_HANDLE_LOADER_WITH_VERIFIED_SYS_EXECUTABLE",
    "components": ["major", "minor", "build"],
    "forbidden_sources": [
      "SYS_GETWINDOWSVERSION_PLATFORM_VERSION",
      "REGISTRY_UBR",
      "KERNEL32_OR_OTHER_PE_PRODUCTVERSION_OR_REVISION",
      "APPENDED_ZERO",
      "CALLER_OR_ENVIRONMENT_VALUE",
      "MIXED_SOURCE_COMPONENTS"
    ],
    "format": "CANONICAL_DOTTED_UINT32_X3",
    "replay": "IDENTICAL_PRE_TARGET_AND_POST_CLEANUP_SYS_GETWINDOWSVERSION",
    "source": "DIRECT_BUILTIN_SYS_GETWINDOWSVERSION"
  },
  "output_frame": {
    "failure_stderr": "ONE_FIXED_ASCII_STOP_CODE_PLUS_LF",
    "failure_stdout": "EMPTY",
    "length": "UINT32_BIG_ENDIAN",
    "magic_ascii_hex": "504d44303243433130484f535443414e444944415445563100",
    "max_candidate_bytes": 65536,
    "max_stderr_bytes": 256,
    "success_eof": "IMMEDIATE",
    "success_stderr": "EMPTY"
  },
  "pe_versioninfo": {
    "metadata_source": "STILL_OPEN_VERIFIED_BYTES_ONLY",
    "resource_leaf_count": 1,
    "translation_conflict": "STOP",
    "translation_selector": "SMALLEST_LANGUAGE_ID_CODEPAGE_AFTER_EQUALITY",
    "wintrust": "FORBIDDEN"
  },
  "powershell": {
    "application_name": "EXACT_VALIDATED_SYSTEM32_WINDOWS_POWERSHELL",
    "arguments": [
      "-NoLogo",
      "-NoProfile",
      "-NonInteractive",
      "-EncodedCommand",
      "FIXED_UTF16LE_SCRIPT"
    ],
    "command_line": "EXACT_QUOTED_APPLICATION_NAME_PLUS_FIXED_ARGUMENTS",
    "creation_flags": [
      "CREATE_SUSPENDED",
      "CREATE_UNICODE_ENVIRONMENT",
      "EXTENDED_STARTUPINFO_PRESENT",
      "CREATE_NO_WINDOW"
    ],
    "cwd": "VALIDATED_WINDOWS_DIRECTORY",
    "environment_keys": [
      "COMSPEC",
      "PSModuleAnalysisCachePath",
      "PSModulePath",
      "SystemRoot",
      "windir"
    ],
    "forbidden_inherited_handle_roles": [
      "SOURCE_READ",
      "MEASUREMENT_READ",
      "ACCEPTANCE_READ"
    ],
    "handle_inheritance": "TRUE_WITH_PROC_THREAD_ATTRIBUTE_HANDLE_LIST_ONLY",
    "inherited_handle_roles": [
      "STDIN_EOF_READ",
      "STDOUT_WRITE",
      "STDERR_WRITE"
    ],
    "job_membership": "SAME_NON_BREAKAWAY_JOB_VERIFIED_BEFORE_RESUME",
    "mapped_image_identity": "HELD_NO_WRITE_DELETE_SHARE_PLUS_QUERY_FULL_PROCESS_IMAGE_NAME_PLUS_FILE_ID_SIZE_SHA_REPLAY_BEFORE_RESUME",
    "module_analysis_cache": "NUL",
    "module_autoloading": "NONE",
    "persistent_write": "STOP",
    "startup_stdio": "STARTF_USESTDHANDLES_TRUE"
  },
  "privilege": {
    "name": "SeSystemProfilePrivilege",
    "restore": "EXACT_PRIOR_ATTRIBUTES_AND_REREAD",
    "token_access": ["TOKEN_QUERY", "TOKEN_ADJUST_PRIVILEGES"]
  },
  "production_entrypoint": {
    "arguments": 0,
    "name": "collect_and_emit_windows_host_binding_candidate",
    "result": "CANONICAL_HOST_CANDIDATE_BYTES_ONLY"
  },
  "proof_schema": {
    "authority_equations": [
      "PROOF_IMPLEMENTATION_SHA_EQ_I10",
      "PROOF_IMPLEMENTATION_TREE_EQ_TREE_I10",
      "PROOF_IMPLEMENTATION_ACCEPTANCE_STATE_SHA_EQ_S10",
      "PROOF_IMPLEMENTATION_ACCEPTANCE_STATE_TREE_EQ_TREE_S10",
      "PROOF_IMPLEMENTATION_ACCEPTANCE_PATH_EQ_FIXED",
      "PROOF_IMPLEMENTATION_ACCEPTANCE_BLOB_EQ_BLOB_S10_PATH",
      "PROOF_IMPLEMENTATION_ACCEPTANCE_FILE_SHA_EQ_SHA256_S10_PATH",
      "PROOF_IMPLEMENTATION_ACCEPTANCE_RECORD_DIGEST_EQ_A_RECORD_DIGEST",
      "PROOF_PLAN_ACCEPTANCE_RECORD_DIGEST_EQ_A_ACCEPTED_PLAN_RECORD_DIGEST",
      "PROOF_SCHEMA_CONTRACT_DIGEST_EQ_A_SCHEMA_CONTRACT_DIGEST",
      "PROOF_HOST_CONTRACT_DIGEST_EQ_A_HOST_CONTRACT_DIGEST",
      "PROOF_CANDIDATE_SHA_EQ_SC",
      "PROOF_CANDIDATE_TREE_EQ_TREE_SC",
      "PROOF_CANDIDATE_PATH_EQ_FIXED",
      "PROOF_CANDIDATE_BLOB_EQ_BLOB_SC_PATH",
      "PROOF_CANDIDATE_FILE_SHA_EQ_SHA256_SC_PATH",
      "PROOF_CANDIDATE_BYTE_SIZE_EQ_SIZE_SC_PATH",
      "PROOF_CANDIDATE_RECORD_DIGEST_EQ_C_RECORD_DIGEST",
      "CANDIDATE_STRICT_CANONICAL_BYTES_EQ_SC_C",
      "SC_IMPLEMENTATION_ACCEPTANCE_BYTES_EQ_S10"
    ],
    "calibration_keys": [
      "file_event_header_pid_attribution",
      "file_create_disposition_decode",
      "file_irp_operation_end_correlation",
      "registry_event_header_pid_attribution",
      "afd_target_attribution",
      "name_resolution_target_attribution",
      "file_read_probe_count",
      "registry_query_probe_count",
      "file_mutator_intent_count",
      "registry_mutator_intent_count",
      "loopback_afd_event_count",
      "localhost_name_resolution_event_count",
      "non_loopback_network_event_count",
      "persistent_filesystem_mutation_count",
      "persistent_registry_mutation_count",
      "result"
    ],
    "candidate_path": "docs/operations/P3_P7_D02_R2_WINDOWS_HOST_BINDING_CANDIDATE.json",
    "canonicalization": "demo-canonical-json-v1",
    "cleanup_keys": [
      "control_trace_stop",
      "stop_returned_final_properties",
      "process_trace_drain_complete",
      "consumer_thread_joined",
      "final_loss_counters_validated",
      "close_trace",
      "session_absence_replay",
      "terminal_sequence",
      "job_active_processes",
      "job_closed",
      "process_thread_pipe_socket_handles_closed",
      "privilege_restored",
      "result"
    ],
    "duplicate_keys": "REJECT",
    "field_type_rules": [
      "schema_version=LITERAL:mirror.demo/D02R2WindowsHostProjectionNativeProof/v1",
      "authority_id=LITERAL:P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_NATIVE_PROOF_01",
      "change_control_id=LITERAL:P3_P7_D02_CC_10",
      "proof_task_id=LITERAL:P3_P7_D02_CC10_NATIVE_PROOF_01",
      "proof_run_id=LOWER_HEX_32",
      "implementation_sha=LOWER_HEX_40",
      "implementation_tree=LOWER_HEX_40",
      "implementation_acceptance_record_digest=LOWER_HEX_64",
      "implementation_acceptance_state_sha=LOWER_HEX_40",
      "implementation_acceptance_state_tree=LOWER_HEX_40",
      "implementation_acceptance_path=LITERAL:docs/operations/P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_IMPLEMENTATION_ACCEPTANCE.json",
      "implementation_acceptance_git_blob_oid=LOWER_HEX_40",
      "implementation_acceptance_file_sha256=LOWER_HEX_64",
      "plan_acceptance_record_digest=LOWER_HEX_64",
      "schema_contract_digest=LOWER_HEX_64",
      "host_projection_contract_digest=LOWER_HEX_64",
      "candidate_sha=LOWER_HEX_40",
      "candidate_tree=LOWER_HEX_40",
      "candidate_path=LITERAL:docs/operations/P3_P7_D02_R2_WINDOWS_HOST_BINDING_CANDIDATE.json",
      "candidate_git_blob_oid=LOWER_HEX_40",
      "candidate_record_digest=LOWER_HEX_64",
      "candidate_file_sha256=LOWER_HEX_64",
      "candidate_byte_size=NONBOOLEAN_INTEGER_1_TO_65536",
      "os_build=CANONICAL_DOTTED_UINT32_X3",
      "os_architecture=LITERAL:AMD64",
      "python_version=CANONICAL_DOTTED_UINT32_X3",
      "invocation_contract_digest=LOWER_HEX_64",
      "runtime_dependency_digest=LOWER_HEX_64",
      "synthetic_ledger_digest=LOWER_HEX_64",
      "etw_contract_digest=LOWER_HEX_64",
      "process_tree=EXACT_OBJECT:process_tree_keys",
      "calibration=EXACT_OBJECT:calibration_keys",
      "filesystem_observation=EXACT_OBJECT:filesystem_observation_keys",
      "registry_observation=EXACT_OBJECT:registry_observation_keys",
      "network_observation=EXACT_OBJECT:network_observation_keys",
      "loss_counters=EXACT_OBJECT:loss_counter_keys",
      "lifecycle=EXACT_OBJECT:lifecycle_keys",
      "cleanup=EXACT_OBJECT:cleanup_keys",
      "private_retention=LITERAL:RAW_ETW_NONE_PRIVATE_PREIMAGE_MEMORY_ONLY",
      "network_claim=LITERAL:ZERO_TARGET_ATTRIBUTED_NETWORK_EVENTS_OBSERVED_NOT_EGRESS_ENFORCEMENT",
      "result=LITERAL:PASS",
      "record_created_at_utc=NORMALIZED_UTC_6_FRACTIONAL_DIGITS",
      "record_digest=LOWER_HEX_64"
    ],
    "field_keys": [
      "schema_version",
      "authority_id",
      "change_control_id",
      "proof_task_id",
      "proof_run_id",
      "implementation_sha",
      "implementation_tree",
      "implementation_acceptance_record_digest",
      "implementation_acceptance_state_sha",
      "implementation_acceptance_state_tree",
      "implementation_acceptance_path",
      "implementation_acceptance_git_blob_oid",
      "implementation_acceptance_file_sha256",
      "plan_acceptance_record_digest",
      "schema_contract_digest",
      "host_projection_contract_digest",
      "candidate_sha",
      "candidate_tree",
      "candidate_path",
      "candidate_git_blob_oid",
      "candidate_record_digest",
      "candidate_file_sha256",
      "candidate_byte_size",
      "os_build",
      "os_architecture",
      "python_version",
      "invocation_contract_digest",
      "runtime_dependency_digest",
      "synthetic_ledger_digest",
      "etw_contract_digest",
      "process_tree",
      "calibration",
      "filesystem_observation",
      "registry_observation",
      "network_observation",
      "loss_counters",
      "lifecycle",
      "cleanup",
      "private_retention",
      "network_claim",
      "result",
      "record_created_at_utc",
      "record_digest"
    ],
    "filesystem_observation_keys": [
      "open_existing_event_count",
      "mutator_intent_count",
      "mutator_success_count",
      "unresolved_irp_count",
      "unsupported_result_event_count",
      "result"
    ],
    "lifecycle_keys": [
      "session_preexisting",
      "versioned_properties_flag_present",
      "all_providers_enabled",
      "mapped_python_identity_replayed",
      "mapped_powershell_identity_replayed",
      "output_frame_valid",
      "candidate_replay_valid",
      "result"
    ],
    "loss_counter_keys": [
      "events_lost",
      "log_buffers_lost",
      "real_time_buffers_lost"
    ],
    "network_observation_keys": [
      "afd_target_event_count",
      "name_resolution_target_event_count",
      "unattributed_provider_event_count",
      "enforcement",
      "result"
    ],
    "nested_value_rules": {
      "calibration": [
        "file_event_header_pid_attribution=LITERAL:PASS",
        "file_create_disposition_decode=LITERAL:PASS",
        "file_irp_operation_end_correlation=LITERAL:PASS",
        "registry_event_header_pid_attribution=LITERAL:PASS",
        "afd_target_attribution=LITERAL:PASS",
        "name_resolution_target_attribution=LITERAL:PASS",
        "file_read_probe_count=NONBOOLEAN_INTEGER_GTE_1",
        "registry_query_probe_count=NONBOOLEAN_INTEGER_GTE_1",
        "file_mutator_intent_count=INTEGER_0",
        "registry_mutator_intent_count=INTEGER_0",
        "loopback_afd_event_count=NONBOOLEAN_INTEGER_GTE_1",
        "localhost_name_resolution_event_count=NONBOOLEAN_INTEGER_GTE_1",
        "non_loopback_network_event_count=INTEGER_0",
        "persistent_filesystem_mutation_count=INTEGER_0",
        "persistent_registry_mutation_count=INTEGER_0",
        "result=LITERAL:PASS"
      ],
      "cleanup": [
        "control_trace_stop=LITERAL:PASS",
        "stop_returned_final_properties=BOOLEAN_TRUE",
        "process_trace_drain_complete=BOOLEAN_TRUE",
        "consumer_thread_joined=BOOLEAN_TRUE",
        "final_loss_counters_validated=BOOLEAN_TRUE",
        "close_trace=LITERAL:PASS",
        "session_absence_replay=LITERAL:PASS",
        "terminal_sequence=LITERAL:CONTROL_TRACE_STOP_THEN_PROCESS_TRACE_DRAIN_JOIN_THEN_FINAL_LOSS_VALIDATION_THEN_CLOSE_TRACE_THEN_ABSENCE_REPLAY",
        "job_active_processes=INTEGER_0",
        "job_closed=BOOLEAN_TRUE",
        "process_thread_pipe_socket_handles_closed=BOOLEAN_TRUE",
        "privilege_restored=BOOLEAN_TRUE",
        "result=LITERAL:PASS"
      ],
      "filesystem_observation": [
        "open_existing_event_count=NONBOOLEAN_INTEGER_GTE_1",
        "mutator_intent_count=INTEGER_0",
        "mutator_success_count=INTEGER_0",
        "unresolved_irp_count=INTEGER_0",
        "unsupported_result_event_count=INTEGER_0",
        "result=LITERAL:PASS"
      ],
      "lifecycle": [
        "session_preexisting=BOOLEAN_FALSE",
        "versioned_properties_flag_present=BOOLEAN_TRUE",
        "all_providers_enabled=BOOLEAN_TRUE",
        "mapped_python_identity_replayed=BOOLEAN_TRUE",
        "mapped_powershell_identity_replayed=BOOLEAN_TRUE",
        "output_frame_valid=BOOLEAN_TRUE",
        "candidate_replay_valid=BOOLEAN_TRUE",
        "result=LITERAL:PASS"
      ],
      "loss_counters": [
        "events_lost=INTEGER_0",
        "log_buffers_lost=INTEGER_0",
        "real_time_buffers_lost=INTEGER_0"
      ],
      "network_observation": [
        "afd_target_event_count=INTEGER_0",
        "name_resolution_target_event_count=INTEGER_0",
        "unattributed_provider_event_count=INTEGER_0",
        "enforcement=LITERAL:NOT_PROVIDED_BY_CC10",
        "result=LITERAL:PASS"
      ],
      "process_tree": [
        "identity_field=LITERAL:ProcessSequenceNumber",
        "observer_before_calibration=BOOLEAN_TRUE",
        "observer_before_target=BOOLEAN_TRUE",
        "target_created_suspended=BOOLEAN_TRUE",
        "job_assigned_before_resume=BOOLEAN_TRUE",
        "job_breakaway_forbidden=BOOLEAN_TRUE",
        "job_active_process_limit=INTEGER_2",
        "calibration_process_count=INTEGER_1",
        "collector_process_count=INTEGER_1",
        "powershell_child_count=INTEGER_1",
        "unexpected_process_count=INTEGER_0",
        "all_processes_terminal=BOOLEAN_TRUE",
        "result=LITERAL:PASS"
      ],
      "registry_observation": [
        "query_event_count=NONBOOLEAN_INTEGER_GTE_1",
        "mutator_intent_count=INTEGER_0",
        "mutator_success_count=INTEGER_0",
        "unsupported_result_event_count=INTEGER_0",
        "result=LITERAL:PASS"
      ]
    },
    "observation_draft_authority": "NONE_NONAUTHORITY_UNTRACKED_UNTIL_SC",
    "process_tree_keys": [
      "identity_field",
      "observer_before_calibration",
      "observer_before_target",
      "target_created_suspended",
      "job_assigned_before_resume",
      "job_breakaway_forbidden",
      "job_active_process_limit",
      "calibration_process_count",
      "collector_process_count",
      "powershell_child_count",
      "unexpected_process_count",
      "all_processes_terminal",
      "result"
    ],
    "proof_path": "docs/operations/P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_NATIVE_PROOF.json",
    "record_digest_equation": "TD_SCHEMA_VERSION_RECORD_EXCLUDING_ONLY_RECORD_DIGEST",
    "registry_observation_keys": [
      "query_event_count",
      "mutator_intent_count",
      "mutator_success_count",
      "unsupported_result_event_count",
      "result"
    ],
    "schema_version": "mirror.demo/D02R2WindowsHostProjectionNativeProof/v1"
  },
  "stop_rules": [
    "CC10_PLAN_ACCEPTANCE_MISSING_STOP",
    "CC10_IMPLEMENTATION_ACCEPTANCE_MISSING_STOP",
    "CC10_ACCEPTANCE_SCHEMA_CONTRACT_MISMATCH_STOP",
    "CC10_HOST_PROJECTION_CONTRACT_MISMATCH_STOP",
    "CC10_IMPLEMENTATION_AUTHORITY_CYCLE_STOP",
    "CC10_IMPLEMENTATION_BINDING_MISMATCH_STOP",
    "CC10_ACCEPTANCE_LOADER_UNTRUSTED_STOP",
    "CC10_RUNTIME_DEPENDENCY_UNBOUND_STOP",
    "CC10_ISOLATED_BOOTSTRAP_IMPORT_STOP",
    "CC10_EXECUTED_IMAGE_IDENTITY_UNPROVEN_STOP",
    "CC10_OUTPUT_FRAME_INVALID_STOP",
    "WINDOWS_HOST_PROJECTION_NOT_WINDOWS_STOP",
    "WINDOWS_HOST_PROJECTION_NATIVE_API_UNAVAILABLE_STOP",
    "WINDOWS_HOST_PROJECTION_PRIVATE_PREIMAGE_DISCLOSURE_STOP",
    "WINDOWS_HOST_PROJECTION_GIT_AUTHORITY_UNAVAILABLE_STOP",
    "WINDOWS_HOST_PROJECTION_GIT_AUTHORITY_AMBIGUOUS_STOP",
    "WINDOWS_HOST_PROJECTION_EXECUTABLE_IDENTITY_DRIFT_STOP",
    "WINDOWS_HOST_PROJECTION_PE_METADATA_MISMATCH_STOP",
    "PE_VERSION_RESOURCE_AMBIGUOUS_STOP",
    "PE_VERSION_TRANSLATION_CONFLICT_STOP",
    "PE_SAME_HANDLE_REPLAY_STOP",
    "WINDOWS_HOST_PROJECTION_POWERSHELL_CLOSURE_STOP",
    "POWERSHELL_ENVIRONMENT_OR_CACHE_WRITE_STOP",
    "WINDOWS_HOST_PROJECTION_PRECONDITION_NOT_ABSENT_STOP",
    "WINDOWS_HOST_PROJECTION_OS_BUILD_AUTHORITY_STOP",
    "WINDOWS_HOST_PROJECTION_TIMESTAMP_AUTHORITY_STOP",
    "WINDOWS_HOST_PROJECTION_MUTATION_DETECTED_STOP",
    "WINDOWS_HOST_PROJECTION_NETWORK_EVENT_DETECTED_STOP",
    "NATIVE_NO_WRITE_PROOF_UNAVAILABLE_STOP",
    "ETW_SESSION_COLLISION_STOP",
    "ETW_PRIVILEGE_ENABLE_STOP",
    "ETW_PRIVILEGE_RESTORE_STOP",
    "ETW_EVENT_SCHEMA_UNSUPPORTED_STOP",
    "ETW_FILE_CREATE_SEMANTICS_UNAVAILABLE_STOP",
    "ETW_FILE_PID_ATTRIBUTION_UNAVAILABLE_STOP",
    "ETW_FILE_OPERATION_UNRESOLVED_STOP",
    "ETW_REGISTRY_PID_ATTRIBUTION_UNAVAILABLE_STOP",
    "ETW_NETWORK_ATTRIBUTION_UNAVAILABLE_STOP",
    "ETW_EVENT_LOSS_STOP",
    "ETW_PID_TREE_INCOMPLETE_STOP",
    "ETW_CLEANUP_FAILED_STOP",
    "WINDOWS_HOST_BINDING_CANDIDATE_COLLISION_STOP"
  ]
}
```

```text
FROZEN_HOST_PROJECTION_CONTRACT_DIGEST: 65cdc704b011cdda121d3815e345a2c5d36dc05e598811fd7f51dfe5151c3b65
```

The decimal provider keyword values above are exact encodings of `0x1EF0` and `0x5344`. Any implementation constant,
section domain, list order or digest preimage drift is `CC10_HOST_PROJECTION_CONTRACT_MISMATCH_STOP`.

## Synthetic call ledger and evidence policy

Every backend operation records only role, API family, access, share mask, disposition and output class in an
in-memory ledger. Tests require its exact order and reject any persistent-object write right, non-`OPEN_EXISTING`
disposition, path fallback, production network call, extra process or output destination. Write access is allowed only
for the exact anonymous stdout/stderr transport-pipe roles and never for a filesystem handle. The digest, never raw
paths/handles, enters the native proof.

```text
NETWORK_POLICY: PRODUCTION_GRAPH_MAKES_NO_NETWORK_OR_DNS_CALL
PUBLIC_INTERNET_EGRESS_ENFORCEMENT: NOT_PROVIDED_BY_CC10
NETWORK_PROOF_CLAIM: ZERO_TARGET_ATTRIBUTED_NETWORK_EVENTS_OBSERVED
TARGET_NETWORK_SYSCALLS: 0
PRODUCTION_LOCALHOST_REQUIRED: NO
PROOF_CALIBRATION_LOOPBACK_REQUIRED: YES_KERNEL_STATE_ONLY
DOCKER_INTERNAL_NETWORK_REQUIRED: NO
ACQUISITION_AUTHORIZED: NO
RAW_ETW_RETENTION: NONE
PRIVATE_NATIVE_TRACE_FILE: FORBIDDEN
```

CC10 creates no persisted private bytes before host acceptance, so it creates no private folder, private name receipt
or CC08 root. Raw SID/path/file-ID/PE/ETW preimages exist only transiently in controlled process memory. The only
retained proof is uploadable, path-free tracked JSON. If raw trace or private preimage persistence becomes necessary,
execution stops for a new private-output custody change control.

## Mandatory validation

Cross-platform tests must prove:

- Linux import and strict typing; the native production entry fails closed off Windows;
- all accepted CC09 tests and candidate keys/literals/digests remain unchanged;
- exact plan/implementation nested key sets, ordered literal arrays, G10/I10 SHA equations and both contract digest
  preimages replay;
- all three tree equations are present in the acceptance-schema preimage and fail when any tree differs;
- the external S10 loader rejects duplicate/noncanonical acceptance, unbound measurement dependency, wrong blob/SHA,
  path-based import and future-acceptance cycles;
- final native-proof bytes reject duplicate/noncanonical JSON, any wrong top-level or nested type/literal/range,
  `record_digest` drift, predicted SC fields, S10/A/I10 or SC/C Git-binding drift and observation-draft substitution;
- production entry has zero parameters and returns bytes only;
- caller path/backend/timestamp/candidate/environment/output injection is impossible;
- identical observation/timestamp produces byte-identical candidate bytes;
- missing/extra/wrong-role observation, acceptance drift and fully re-signed mapping fail closed;
- SID/path/volume/file-ID/PE/OneDrive/ETW preimages never enter repr, errors, output or canonical bytes;
- static calls, access masks, share modes and dispositions match the read-only allowlist;
- synthetic ledger rejects mutators, network, path fallback and extra processes;
- PATH/PATHEXT/cwd/SearchPath/where/Get-Command Git decoys cannot affect authority;
- missing/wrong-type/HKCU-only/32-bit-only Git registration and replacement fail closed;
- same text/different identity, changed hash/version/machine and mid-read replacement fail;
- PE duplicate resource, malformed bounds/UTF-16, missing translation and cross-translation text conflict fail;
- every PowerShell manifest/member/cmdlet/script/runtime closure equality and ordering is attacked;
- exact target/PowerShell application name, command line, cwd, creation flags, environment, handle allowlist,
  `STARTF_USESTDHANDLES`, mapped-image identity, same-Job pre-resume membership and privilege replay are attacked;
- PowerShell is rejected if it inherits source, measurement, acceptance or any caller handle;
- OS build comes only from matching pre-target/post-cleanup `sys.getwindowsversion().major/minor/build` triples;
  platform-version, UBR, PE revision, appended-zero, caller/environment, wrong-count, mixed-source and mismatch cases
  fail closed;
- clock injection, multiple reads, invalid FILETIME, rounding drift and malformed UTC fail;
- Ruff, strict mypy, targeted pytest and `git diff --check` pass.

Native Windows tests must prove:

- current SID, LocalAppData/Profile and Windows/System relationships replay from handles;
- fixed-local volume, reparse/cloud/OneDrive/ACL/free-space boundaries pass;
- both Project Mirror candidates are truly absent and no directory is created;
- Python, registry Git, PowerShell, cmd, system DLLs, manifests and members pass same-handle replay;
- PowerShell cmdlet/script/runtime closure is real, bounded and path-free;
- the verified Principal Python launcher replays an identical canonical three-component OS build before target launch
  and after native cleanup, and every prohibited alternate source/count/mix/mismatch negative control stops;
- saved observation plus its timestamp rebuilds byte-identical candidate bytes without a second native attempt;
- emitted bytes pass existing `validate_windows_host_candidate` with externally replayed S10 bindings;
- calibration proves File/Registry/AFD/NameResolution attribution and File Irp/status semantics without persistent
  mutation;
- collector attempted-mutator counts, successful mutations, target Winsock/DNS events and all ETW loss counters are
  zero;
- removing `WNODE_FLAG_VERSIONED_PROPERTIES`, using v1-sized properties, validating pre-STOP QUERY loss, closing the
  consumer before STOP/drain or skipping consumer join/final STOP-time counters is rejected;
- ETW session, Job, child, handles and temporary privilege are fully cleaned;
- candidate/proof contain no absolute path, SID, file ID, volume serial, PID or trace payload;
- no Provider is called; network conclusion is observational zero-event evidence, not egress enforcement.

Candidate collision is not a two-file worker responsibility. After S10 CI, the Principal alone performs the SC Gate:
if the fixed tracked candidate path already exists, bytes are preserved and
`WINDOWS_HOST_BINDING_CANDIDATE_COLLISION_STOP` is recorded; otherwise the Principal writes exactly the reviewed
in-memory bytes in a candidate-only commit. No worker receives an output path or writes the candidate.

Linux CI is mandatory but cannot substitute for native Windows evidence.

## Stop rules

```text
CC10_PLAN_ACCEPTANCE_MISSING_STOP
CC10_IMPLEMENTATION_ACCEPTANCE_MISSING_STOP
CC10_ACCEPTANCE_SCHEMA_CONTRACT_MISMATCH_STOP
CC10_HOST_PROJECTION_CONTRACT_MISMATCH_STOP
CC10_IMPLEMENTATION_AUTHORITY_CYCLE_STOP
CC10_IMPLEMENTATION_BINDING_MISMATCH_STOP
CC10_ACCEPTANCE_LOADER_UNTRUSTED_STOP
CC10_RUNTIME_DEPENDENCY_UNBOUND_STOP
CC10_ISOLATED_BOOTSTRAP_IMPORT_STOP
CC10_EXECUTED_IMAGE_IDENTITY_UNPROVEN_STOP
CC10_OUTPUT_FRAME_INVALID_STOP
WINDOWS_HOST_PROJECTION_NOT_WINDOWS_STOP
WINDOWS_HOST_PROJECTION_NATIVE_API_UNAVAILABLE_STOP
WINDOWS_HOST_PROJECTION_PRIVATE_PREIMAGE_DISCLOSURE_STOP
WINDOWS_HOST_PROJECTION_GIT_AUTHORITY_UNAVAILABLE_STOP
WINDOWS_HOST_PROJECTION_GIT_AUTHORITY_AMBIGUOUS_STOP
WINDOWS_HOST_PROJECTION_EXECUTABLE_IDENTITY_DRIFT_STOP
WINDOWS_HOST_PROJECTION_PE_METADATA_MISMATCH_STOP
PE_VERSION_RESOURCE_AMBIGUOUS_STOP
PE_VERSION_TRANSLATION_CONFLICT_STOP
PE_SAME_HANDLE_REPLAY_STOP
WINDOWS_HOST_PROJECTION_POWERSHELL_CLOSURE_STOP
POWERSHELL_ENVIRONMENT_OR_CACHE_WRITE_STOP
WINDOWS_HOST_PROJECTION_PRECONDITION_NOT_ABSENT_STOP
WINDOWS_HOST_PROJECTION_OS_BUILD_AUTHORITY_STOP
WINDOWS_HOST_PROJECTION_TIMESTAMP_AUTHORITY_STOP
WINDOWS_HOST_PROJECTION_MUTATION_DETECTED_STOP
WINDOWS_HOST_PROJECTION_NETWORK_EVENT_DETECTED_STOP
NATIVE_NO_WRITE_PROOF_UNAVAILABLE_STOP
ETW_SESSION_COLLISION_STOP
ETW_PRIVILEGE_ENABLE_STOP
ETW_PRIVILEGE_RESTORE_STOP
ETW_EVENT_SCHEMA_UNSUPPORTED_STOP
ETW_FILE_CREATE_SEMANTICS_UNAVAILABLE_STOP
ETW_FILE_PID_ATTRIBUTION_UNAVAILABLE_STOP
ETW_FILE_OPERATION_UNRESOLVED_STOP
ETW_REGISTRY_PID_ATTRIBUTION_UNAVAILABLE_STOP
ETW_NETWORK_ATTRIBUTION_UNAVAILABLE_STOP
ETW_EVENT_LOSS_STOP
ETW_PID_TREE_INCOMPLETE_STOP
ETW_CLEANUP_FAILED_STOP
WINDOWS_HOST_BINDING_CANDIDATE_COLLISION_STOP
```

A stop emits only its code, preserves all prior bytes and creates no candidate. It never authorizes deletion, unknown
state cleanup, fallback, suffix, alternate locator, relaxed proof or mock PASS.

## Review Gates

```text
G1: independent Sol exact-plan review of CC10 and R-DEMO-39..41
G2: governance same-SHA CI and Principal plan acceptance
G3: exact I10 two-file ownership/diff/preimage review
G4: independent Sol exact-implementation review
G5: I10 same-SHA CI and Principal implementation acceptance
G6: S10 acceptance-state same-SHA CI
G7: one Principal-owned calibrated native proof run; collision Gate; candidate bytes remain in memory until SC write
G8: independent SC candidate-only exact review and SC same-SHA CI
G9: SH native-proof/host-acceptance exact review and SH same-SHA CI
G10: Principal host-binding acceptance and next-node publication
```

The same reviewer is not both sole plan author and sole final implementation reviewer. Worker PASS is evidence only;
Principal reviews actual bytes and decides every acceptance.

## State and critical path

```text
CURRENT:
  CC09_IMPLEMENTATION_ACCEPTED
  CC10_REVISION_1=REPAIR_REQUIRED_PRESERVED
  CC10_REVISION_2=REPAIR_REQUIRED_PRESERVED
  CC10_REVISION_3=REPAIR_REQUIRED_PRESERVED
  CC10_REVISION_4=PENDING_INDEPENDENT_EXACT_PLAN_REVIEW
  NEXT_READY_NODE=P3_P7_D02_CC_10_GOVERNANCE

AFTER_CC10_PLAN_ACCEPTANCE:
  CC10_IMPLEMENTATION_AUTHORIZED

AFTER_CC10_IMPLEMENTATION_ACCEPTANCE_AND_S10_CI:
  READ_ONLY_WINDOWS_HOST_BINDING_CANDIDATE_EXECUTION_AUTHORIZED

AFTER_SC_CI:
  WINDOWS_HOST_BINDING_CANDIDATE_NON_AUTHORITY

AFTER_SH_ACCEPTANCE_AND_CI:
  WINDOWS_HOST_BINDING_ACCEPTED
  NEXT_READY_NODE=CODE_CACHE_AND_PRIVATE_HOME_CANDIDATE_RECEIPTS
```

Throughout CC10:

```text
D02_R2: BLOCKED
D03: BLOCKED
D04_B: BLOCKED
D07_B: BLOCKED
EVIDENCE_ROOT: NOT_CREATED
TWO_COPY_REGISTRY: NOT_INITIALIZED
IMAGEGEN_CALLS_EXECUTED: 0
```

Formal CC04 QuestionBank generation remains outside the Demo critical path and keeps its independent worktree,
namespace, registry, ordinal and low-priority resource schedule. CC10 does not release its generation slot.

## Risk and acceptance boundary

CC10 adds R-DEMO-39–41 while R-DEMO-33–38 remain active. An accepted plan authorizes implementation only. An
accepted implementation authorizes one read-only projection only. A candidate is not authority. Only later host
acceptance may open the exact code-cache/private-home candidate-and-receipt stage. None of these states proves formal
P3–P7, real-user validity, production security or production readiness.
