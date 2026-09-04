# P3–P7 Demo D11 Real Flow Contract 07

## Decision status

```text
CONTRACT_ID: P3_P7_D11_REAL_FLOW_CONTRACT_07
TRACK: DEMO_PROTOTYPE
STATUS: PRINCIPAL_ACCEPTED_FOR_ISOLATED_IMPLEMENTATION
BASE_SHA: ec1f1ee9bef057931e3321c4f6a0678024a3d36e
INTEGRATION_GATE: CONTRACT_06_INTEGRATED_EXACT_SHA_CI_PASS
PUBLIC_API_SHAPE_CHANGE: ADDITIVE_EDIT_EXECUTION_RESULT_READ
PUBLIC_API_BEHAVIOR_CHANGE: PRESENT
MIGRATION_CHANGE: NONE
BROWSER_FLOW_CHANGE: NONE
PRODUCTION_AUTHORIZATION: NONE
REAL_USER_AUTHORIZATION: NONE
```

## Product slice

This slice exposes the immutable result of one exact accepted D08 execution
Job. It closes the server-side authority gap between an execution admission and
its published synthetic ImageVersion:

```text
edit_plan.execute Job
-> exact JobBinding
-> final JobAttempt
-> EditArtifact
-> ToolRun
-> PASS VerificationResult
-> PROMOTED event
-> published EDITED ImageVersion
```

It does not create an edit, select an operation, return image bytes, start D06,
write D09 feedback, expose a private object key, or change browser behavior.

## Exact read operation

Add this authenticated Demo-only read:

```text
GET /api/v1/demo/edit-plans/execution-jobs/{job_id}/result
operationId: demoGetEditExecutionResultByJob
authentication: DemoBearerAuth
request body: none
Idempotency-Key: not accepted
```

Only a fully published PASS result returns `200`:

```json
{
  "status": "IMAGE_VERSION_READY",
  "job_id": "<DemoId>",
  "session_id": "<DemoId>",
  "editing_session_id": "<DemoId>",
  "edit_plan_id": "<DemoId>",
  "job_binding_digest": "<DemoDigest>",
  "plan_digest": "<DemoDigest>",
  "tool_run_id": "<DemoId>",
  "tool_run_digest": "<DemoDigest>",
  "verification_result_id": "<DemoId>",
  "verifier_digest": "<DemoDigest>",
  "image_version_id": "<DemoId>",
  "image_version_digest": "<DemoDigest>",
  "version_kind": "EDITED",
  "sequence": 1,
  "parent_image_version_id": "<DemoId>",
  "result_asset_id": "<DemoId>",
  "result_asset_sha256": "<DemoDigest>"
}
```

The response is intended for trusted server-side orchestration. D11 must not
forward any identifier or digest from it to browser JSON, DOM, URL, storage or
logs.

## Replay requirements

The read service must perform zero persistent writes and must not call an
execution, verifier, publisher or Provider. Within one transaction it must:

1. read the exact Job and JobBinding by `job_id`;
2. hide missing and foreign-owner authority as unavailable;
3. replay the same-owner binding canonical payload/digest, operation
   `edit_plan.execute`, `EDIT_PLAN` target, Job type and empty Job payload;
4. report `PENDING` and `RUNNING` as not ready;
5. report `REJECTED`, `FAILED` and `CANCELLED` as terminal without fallback;
6. for `COMPLETED`, require result code `EDIT_EXECUTION_COMPLETED` and the exact
   completed JobAttempt used by the result graph;
7. require one RESULT EditPlan matching the binding target and owner/session;
8. replay the exact EditOperation, EditArtifact, ToolRun and VerificationResult
   ownership and digest links;
9. require verification outcome `PASS` with a published ImageVersion;
10. require one matching `PROMOTED` artifact event; and
11. replay the ImageVersion kind (`EDITED`, `RESTORED` or `ROLLED_BACK`),
    including parent, sequence, plan/tool/verifier digests and result Asset
    ID/SHA. The later D11 first-edit BFF must require `EDITED`.

Repeated and concurrent reads return the same projection and create zero rows.
The service must never use active/latest ImageVersion ordering, search by output
SHA, or require the caller to know a ToolRun ID.

## Failure contract

Errors retain the standard `code`, `message`, `request_id`, `details` shape and
do not reveal internal graph differences:

- missing Job/Binding or foreign owner: `404 DEMO_EDIT_RESULT_UNAVAILABLE`;
- `PENDING` or `RUNNING`: `409 DEMO_EDIT_RESULT_NOT_READY`;
- `REJECTED`, `FAILED` or `CANCELLED`: `409 DEMO_EDIT_RESULT_TERMINAL`;
- malformed same-owner envelope, missing result row, non-PASS verification,
  non-PROMOTED event or inconsistent lineage: `503
DEMO_EDIT_RESULT_AUTHORITY_CORRUPT`.

The existing editing create, plan, execute, generic Job and ToolRun operations
remain byte-compatible.

## Change boundary

Allowed changes are limited to the D08 read service/coordinator, Demo schema and
router, focused PostgreSQL/API tests, generated OpenAPI client, and this
contract.

Explicitly forbidden:

- migration or ORM changes;
- Worker, execution, verifier or publication changes;
- private object storage or image-byte reads;
- active/latest or digest-search fallback;
- browser/BFF/UI changes;
- D06, D09 or D10 changes;
- Provider or private-input access.

## Acceptance

Acceptance requires:

- real PostgreSQL tests for exact published replay, repeated-read zero writes,
  pending, all terminal states, missing/foreign authority and malformed
  same-owner authority;
- corruption tests for JobAttempt, plan, tool, verifier, event, ImageVersion
  and Asset lineage;
- API tests for the four safe failure classes and exact response shape;
- additive-only OpenAPI/generated-client validation;
- proof of no migration, ORM, Worker or private-storage change;
- Ruff, strict mypy, contract drift, diff check and changed-range Gitleaks;
- one integrated-SHA CI pass after the preceding D11 Gate is accepted.
