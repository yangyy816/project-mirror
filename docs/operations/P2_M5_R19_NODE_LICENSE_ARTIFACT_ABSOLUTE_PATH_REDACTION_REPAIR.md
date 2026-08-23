# P2-M5-R19 Node-License Artifact Absolute-Path Redaction Repair

## Status and authority

- BOOTSTRAP_STATUS: OK
- TASK_ID: P2-M5-R19
- TASK_NAME: Node-License CI Artifact Absolute-Path Redaction Repair
- REPAIR_CLASS: MINIMAL_FORWARD_CI_ARTIFACT_REDACTION_REPAIR
- BASELINE_SHA: a3aae5d1923a6cbc373aebcbdef79e501e92d883
- BASELINE_CI_RUN: 32659115560
- BASELINE_CI_ATTEMPT: 1
- BASELINE_SECURITY_RESULT: FAILED
- BASELINE_STOP_OUTCOME: NODE_LICENSE_ARTIFACT_ABSOLUTE_PATH_DISCLOSURE
- REPAIR_CANDIDATE: THIS_COMMIT
- AUTHORITY_CONDITION:
  EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE

R19 is a forward repair of one ordinary-CI artifact redaction defect. It does not amend, reset, rebase, reinterpret,
or accept the failed baseline. It does not change the Owner decision, TS01 policy, dependency graph, lockfile, audit
commands, application code, schema, migration, OpenAPI, model, Provider, generation interface, private-custody model,
resource envelope, qualification outcome, or downstream Gate.

## Preserved failed evidence

Commit `a3aae5d1923a6cbc373aebcbdef79e501e92d883` and run `32659115560` remain immutable evidence:

- `quality-and-integration`: PASS;
- `docker-validation`: PASS;
- `secret-scan`: PASS;
- eight artifacts: present, unexpired, and bound to the exact SHA;
- TS01 canonical policy, authority tails, resource accounting, and zero state: PASS;
- exact-SHA Security/Privacy Gate: FAILED;
- failed artifact: `project-audit-evidence` / `node-licenses.json`;
- absolute path entries: 506;
- offending baseline file SHA-256:
  `d3775d3054f2a3d62f660c5f3fec82ee25365eb574c97115de321baf38fbf64a`.

The same file SHA-256 and 506 path entries were independently reproduced from the previously accepted baseline run
`32655228398`. That proves the defect was inherited from the existing artifact generator; it does not waive the
current Security Gate or retroactively change earlier acceptance evidence.

## Root cause

`pnpm licenses list --json` includes a `paths` array for package installations. The CI workflow uploaded the raw JSON
as an ordinary artifact. On GitHub-hosted runners, those values are absolute runner workspace paths. Package names,
versions, license classifications, authors, homepages, and descriptions are useful license evidence; install paths
are neither required license evidence nor permitted ordinary-artifact content.

## Exact repair

The dependency-and-license audit step continues to run the same commands and versions. Only the node-license artifact
serialization changes:

1. stream the exact `pnpm licenses list --json` result to the already installed Node runtime;
2. JSON-parse the report;
3. delete only each package record's `paths` field;
4. serialize the remaining object as deterministic indented JSON with one final LF;
5. write only that sanitized serialization to an exact non-uploaded candidate filename whose prior existence hard
   fails;
6. parse the exact serialized candidate again and require nonzero license-group and package-record counts;
7. recursively count any remaining `paths` property or absolute Unix, Windows-drive, UNC, or `file:` URI path string;
8. hard-fail the CI step unless both path counts are zero and both evidence counts are nonzero;
9. only after validation, create the final `node-licenses.json` upload path through an exclusive same-filesystem hard
   link, verify source/final byte size and SHA-256 equality, and remove the candidate; and
10. permit `project-audit-evidence` upload only when the dependency-and-license audit step succeeded.

The validator reports counts only. It never emits a discovered path value. The raw unsanitized JSON is streamed and
is not written to a file or uploaded. A sanitizer, validator, upstream-inventory, promotion, or audit failure cannot
place a candidate at the final upload path or authorize the project-audit upload step. On successful runs,
`python-licenses.json`, `python-sbom.cdx.json`, `celery.log`, the other seven artifacts, audit thresholds, artifact
name, content set, and upload retention remain unchanged.

## Frozen invariants

- NODE_LICENSE_ARTIFACT_PATH_FIELDS_ALLOWED: 0
- NODE_LICENSE_ARTIFACT_ABSOLUTE_PATH_STRINGS_ALLOWED: 0
- NODE_LICENSE_ARTIFACT_LICENSE_GROUPS_REQUIRED: NONZERO
- NODE_LICENSE_ARTIFACT_PACKAGE_RECORDS_REQUIRED: NONZERO
- NODE_LICENSE_ARTIFACT_OTHER_FIELDS: PRESERVED_EXCEPT_PATHS
- NODE_LICENSE_ARTIFACT_CANDIDATE_UPLOAD: PROHIBITED
- NODE_LICENSE_ARTIFACT_FINAL_PROMOTION: ONLY_AFTER_VALIDATION_WITH_EXCLUSIVE_TARGET_AND_DIGEST_EQUALITY
- NODE_LICENSE_ARTIFACT_FAILED_STEP_UPLOAD: PROHIBITED
- NODE_LICENSE_INVENTORY_PIPELINE_FAILURE_PROPAGATION: REQUIRED
- RAW_NODE_LICENSE_REPORT_PERSISTENCE: PROHIBITED
- RAW_NODE_LICENSE_REPORT_UPLOAD: PROHIBITED
- VALIDATOR_PATH_VALUE_LOGGING: PROHIBITED
- DEPENDENCY_CHANGE: NONE
- LOCKFILE_CHANGE: NONE
- AUDIT_THRESHOLD_CHANGE: NONE
- CI_JOB_SET_CHANGE: NONE
- EXPECTED_ARTIFACT_COUNT: 8
- EXPECTED_MIGRATION_HEAD: 0014_m5_eval_authority

The repair must preserve the TS01 policy at 882 UTF-8 bytes and SHA-256
`c5b2a15f3d8801e1eba28d5a4eabb4f35b06ffb7aa3abb9747890e504ecc753a`. DS01-Q01 remains
`1_OF_1_EXHAUSTED`, retry remains prohibited, and the accepted post-Q01 Owner Decision Pack remains the current
authority until this candidate completes every Gate.

## Allowed paths

R19 may change exactly:

1. `.github/workflows/ci.yml`;
2. `docs/operations/P2_M5_R19_NODE_LICENSE_ARTIFACT_ABSOLUTE_PATH_REDACTION_REPAIR.md`;
3. `docs/operations/P2_M5_ACCEPTANCE.md`;
4. `docs/operations/P2_M5_EXECUTION_PROTOCOL.md`.

It may not modify the TS01 contract or research policy, application code, tests, package manifests, lockfiles,
dependencies, schema, migration, OpenAPI, models, Providers, private state, MEMORY, MILESTONES, shared summaries, or
P2-M7.

## Validation and acceptance

Local validation requires:

- exact changed-path allowlist;
- scoped Prettier and `git diff --check`;
- YAML parse;
- an exact raw-to-sanitized fixture proving all non-`paths` JSON content is preserved;
- zero `paths` fields and zero absolute path strings in the sanitized fixture;
- canonical TS01 policy byte/digest verification;
- Acceptance/Execution key order and value equality, no duplicate current-tail keys, last occurrence in the new tail,
  and physical true EOF;
- zero generation, raw output, ordinal, private-root, fixture reservation, and fixture-storage state.

Tracked acceptance additionally requires a normal forward commit, fast-forward non-force push, same-SHA attempt-1
`quality-and-integration`, `docker-validation`, and `secret-scan`, exactly eight unexpired exact-SHA artifacts, and
actual content inspection proving:

- `node-licenses.json` is valid and nonempty;
- it contains zero `paths` fields and zero absolute path strings;
- package/license evidence remains present;
- the other seven artifact contents retain their existing Gate semantics;
- independent Security/Privacy/License/Research Integrity PASS;
- independent Sol High PASS; and
- Principal acceptance.

No post-acceptance status commit is allowed.

## Current zero state and result

- P2_M5_R19_STATUS: READY_FOR_SAME_SHA_ACCEPTANCE
- CC04_B_TS01_CHANGE_CONTROL: NOT_ACCEPTED_AT_FAILED_BASELINE
- TS01_QUALIFICATION_STATUS: NOT_STARTED
- NATIVE_AUTO_EXPORT_CAPABILITY: NOT_PROVEN
- GENERATION_CALLS_EXECUTED: 0
- RAW_OUTPUTS_CREATED: 0
- REQUEST_ORDINAL_CONSUMED: NONE
- CAL_REQ_001_STATUS: NOT_CONSUMED
- TS01_FIXTURE_GLOBAL_NATIVE_OUTPUT_RESERVATION_CONSUMED: 0
- TS01_FIXTURE_PRIVATE_STORAGE_BYTES_CONSUMED: 0
- PRIVATE_ROOT_OR_LOCATOR_CREATED: NO
- GENERATION_SPECIFICATION_CREATED: NO
- CALIBRATION_COHORT_STATUS: NOT_CREATED
- CC04_B_EXECUTION: CLOSED_PENDING_TS01_CHANGE_CONTROL_R19_ACCEPTANCE
- P2_M5_STATE: EXECUTING
- P2_MVR_V1_RESULT: NOT_EVALUATED
- P2_M6_ENTRY: CLOSED_PENDING_TECHNICAL_AND_MVR_PASS
- STOP_OUTCOME: READY_FOR_TRACKED_EVIDENCE

R19 acceptance accepts the repaired TS01-T01 change-control tree and opens only the separately bounded TS01-Q01
qualification. It does not execute qualification, call image generation, create private state, start MR01, or
authorize formal E01 execution.
