# P2-M5 CC06 — batched native imagegen post-registration contract

## Bounded-task authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-CC06`
- `OWNER_DECISION_ID: OD-P2-M5-IMAGEGEN-BATCH-EXECUTION-001`
- `CHANGE_CLASS: FORWARD_BATCH_LEVEL_EXECUTION_CHANGE_CONTROL`
- `BASELINE_SHA: b0de4d85c4ba65be86d2d2795d15a1de9fea0add`
- `CURRENT_MILESTONE: P2-M5_EXECUTING`
- `CURRENT_CANARY: CAL-REQ-004_OUTPUT_REGISTERED_PRE_DECODE`
- `D02_CONTRACT_STATUS: OWNER_WITHDRAWN_MISROUTED_AND_OUT_OF_SCOPE`
- `STATUS: EXECUTION_READY_PENDING_IMPLEMENTATION_AND_TRACKED_GATES`

## Objective

Close the one remaining canary gap after successful native output registration: bounded normalization, exact V01/V03
technical M3 qualification, append-only terminal disposition, fresh-process recovery and a safe sequential successor.
The same accepted controller may then execute later ordinals in bounded tranches without per-output governance commits.

## Allowed scope

- one independent private post-registration controller and focused tests;
- one accepted ADR and append-only P2-M5 authority mirrors;
- exact registration/state/controller verification;
- private raw-to-canonical normalization and second decode;
- injected task-scoped private-synthetic M3 capabilities;
- versioned technical QA, operation receipts and terminal checkpoints;
- success/content-rejection successor rollover within the standing tranche rules; and
- redacted tranche or hard-incident evidence.

## Forbidden scope

No modification of the live `private_execution_overlay.py` or capture runner; no Provider call during implementation;
no imagegen call before candidate acceptance; no same-ordinal retry; no hidden download or runtime discovery; no private
locator, Prompt, data URL, image/model byte or credential in Git/logs/errors; no PostgreSQL/Asset/Job/QA/identity/admission
mutation; no schema, migration, OpenAPI, public API, dependency, CI workflow or M6 change; no production, distribution,
real-user data, holdout or QuestionBank release authority.

## Verified precondition

The Principal reread the exact private current tip instead of relying on the compressed handoff. The registered canary
has sequence 6, phase `OUTPUT_REGISTERED_PRE_DECODE`, `active_calls=0`, `request_call_count=4`,
`returned_output_count=4`, `raw_output_count=4`, `formal_calls_remaining=28`,
`formal_raw_capacity_remaining=28`, `global_native_output_capacity_remaining=59` and
`global_native_output_consumed=5`. The earlier handoff value `formal_raw_capacity_remaining=29` was a stale pre-return
summary, not ledger corruption.

Tracked evidence must not reproduce the private root, receipt locator, raw bytes, normalized bytes or Prompt. The
registered output remains unadmitted and has not yet been decoded.

## Exact controller contract

The controller must:

1. require expected overlay receipt, state, event and original controller SHA-256 values;
2. verify the supplied receipt is the current tip and no next receipt exists;
3. acquire the R55 quiescence lease and repeat the same checks under that lease;
4. rerun `verify_registration_before_decode()` including capture-sidecar, registration record, source/staging digest,
   byte-size, MIME and magic binding;
5. bind its own tracked module SHA-256 without replacing the original controller pin;
6. persist a create-new-or-verify-exact post-registration attempt before reading the registered raw object;
7. use the registered opaque output ID to derive the single bounded staging object; arbitrary paths are not accepted;
8. sanitize to canonical JPEG, write the immutable normalized object, second-decode it and persist exact digest,
   dimensions, byte-size, MIME, sanitizer version and configuration digest;
9. verify exact injected runtime/model/policy/manifest/platform/scope/zero-egress capability before every operation;
   the expected capability-authority digest map must be supplied from the independently verified task-scoped registry
   authority and must not be derived from the capability object during execution;
10. persist each operation plan before invocation and each typed result immediately after return;
11. aggregate only after all preregistered results are durable; and
12. commit exactly one terminal checkpoint and overlay transition.

## Frozen V01/V03 technical Gate

- manifest: `p2-m5-cc04-b-v01-admission-runtime-v1`;
- manifest file SHA-256: `a1d3698564c8ca0d0b6f01fa28b580d85135ccc8c502616527a140d80ba41cb3`;
- QA policy: `p2-m3-v03-source-built-vision-qa-v1`;
- QA policy content digest: `8305cfaa25d084138fb67e93043a1e37842543a645085d19d3ef52ac8a6ce15f`;
- model SHA-256: `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`;
- Linux runtime SHA-256: `6a5fb35175efc2f014fb61f7f4abb2c78c38156bd6abf2186d1549cbf3f006a7`;
- Windows runtime SHA-256: `1c67ae02b90a5b00b58018c3c04db411134d781c6f53b195e68a6ce6136615ef`;
- platforms: `linux_x86_64_network_none` and `windows_amd64_process_specific_outbound_deny`;
- executions: 10 per platform, serial, zero automatic retry;
- face count: exactly one;
- landmarks: exactly 478, unique, finite and in `[0,1]`;
- transformation matrix: exactly 16 finite values;
- same-platform maximum span: landmarks `0.000001`, matrix `0.000001`;
- cross-platform maximum absolute difference: landmarks `0.00005`, matrix `0.0005`, bounding-box area `0.00001`,
  rotation `0.01` degrees;
- face occupancy: at least `0.1`; and
- absolute yaw, pitch and roll: at most `10` degrees.

Any capability, digest, platform, scope or zero-egress mismatch is infrastructure failure. Face, landmark, matrix,
occupancy, pose, repeatability or parity failure after a complete result is content rejection. No threshold may be
changed after seeing this output.

## State and recovery

```text
OUTPUT_REGISTERED_PRE_DECODE
→ POST_REGISTRATION_ATTEMPT_BOUND
→ POST_REGISTRATION_TECHNICAL_QA_PASSED
 | POST_REGISTRATION_CONTENT_REJECTED
 | POST_REGISTRATION_INFRA_FAILURE
 | POST_REGISTRATION_UNKNOWN_M3_OUTCOME
```

- A complete existing file is replayed only after byte-for-byte canonical verification.
- A recoverable partial write resumes from the last complete durable step without another imagegen call.
- A durable terminal checkpoint or successor intent retains its original timestamp across recovery; a later caller
  must verify and reuse that persisted value rather than producing a second semantic record.
- A durable operation plan without its result means the M3 outcome is unknown; that operation is never invoked again.
- Digest loss, ordinal duplication, counter drift, accepted-byte loss or private leakage is a global integrity failure and
  stops all later calls.
- Terminal checkpoints set `active_calls=0`, `decode_authorized=false`, retain the truthful `decode_performed` fact and
  do not change generation/raw/global counters.

## Successor and tranche rules

The successor is a new project-local Git-ignored root. Its intent and `READY` state bind the exact terminal predecessor
receipt/state/event/checkpoint, post-controller digest, derived next ordinal and inherited counters. `staging` and
`records` must be empty at commit and verification. Create/recover, stale handles, concurrent writers, forks and replay
all fail closed under the R55 lease. The parent-scoped intent must be durable before the successor root is created, so
an interruption between intent and root creation is recoverable while an unbound pre-existing root remains rejected.

- Tranche 1 is only `CAL-REQ-004`; only technical QA PASS opens tranche 2. A canary content rejection is terminal and
  does not authorize `CAL-REQ-005`.
- Tranche 2 may contain at most four sequential calls.
- Later tranches may contain at most ten sequential calls.
- Within an already accepted tranche, technical PASS or completed content rejection may advance; infrastructure,
  unknown-outcome or global-integrity failure stops immediately.
- Reaching the accepted cohort target stops all unused calls.
- The 50-call standing Owner cap never enlarges the current execution ledger.

## Evidence and redaction

Every private output checkpoint binds opaque IDs; ordinal; original overlay receipt/state/event/controller digests;
registration/capture digests; source and normalized checksums, sizes, MIME and dimensions; sanitizer version/config;
manifest/policy/runtime/model digests; platform-labeled opaque capability IDs; operation plan/result digests; aggregate
QA; outcome/reason; recovery mode; and the explicit facts `db_mutations=0`, `provider_calls_added=0`, `admission=0`.

Tracked tranche evidence contains only redacted aggregate counts, digests, reason codes and resource counters. It must
not contain a path, locator, Prompt, data URL, image/model byte, raw Provider payload, object key, URL or credential.

## Acceptance

Implementation acceptance requires focused success/content/infra/unknown/recovery/concurrency/privacy/resource tests;
all R50-R55 focused regressions; Ruff format/check; strict mypy; canonical-LF complete API/Worker regression; scoped
Prettier/contracts checks; exact changed-path and private-leak checks; same-SHA three-job CI; all eight artifact-family
content checks; independent Security/Privacy/License/Research review; Sol High final review; and Principal inspection.

Until all Gates pass, no unaccepted local code may decode the private canary, no M3 operation may run and
`CAL-REQ-005` remains unauthorized.
