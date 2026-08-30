# P2-M5 CC07-G — Exact private Vision capability requalification contract

## Bounded-task authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-CC07-G`
- `CHANGE_CONTROL_ID: CC-P2-M5-07`
- `TASK_NAME: Exact Private Vision Capability Requalification and Task-Scoped Authority Bootstrap`
- `BASELINE_SHA: d4710a2df2a0623d10e7ff5c82f127467f529eab`
- `BASELINE_CI_RUN: 33335430920_ATTEMPT_1_ALL_MANDATORY_JOBS_PASS`
- `CURRENT_MILESTONE: P2-M5_EXECUTING`
- `CURRENT_CANARY: CAL-REQ-004_OUTPUT_REGISTERED_PRE_DECODE`
- `CHANGE_CLASS: FORWARD_ZERO_GENERATION_PRIVATE_CAPABILITY_CUSTODY_CHANGE_CONTROL`
- `STATUS: CONTRACT_CANDIDATE_PENDING_TRACKED_GATES`

## Root cause and objective

R57 is accepted and correctly refuses capability self-signing. The Principal
replayed the registered CAL-REQ-004 tip under the R55 quiescence lease and
retained an external registered-tip snapshot, but the exact task-scoped
registry contains no current two-platform runtime/model executor handles or
independently retained capability-authority map.

Tracked P2-M3 R25/R26 and CC04-B V01 evidence proves historical qualification,
exact digests and a reproducible build recipe. It does not materialize bytes,
an executable handle, a current zero-egress capability or a recoverable
locator. This is `PRIVATE_CAPABILITY_CUSTODY_LIFECYCLE_GAP`, not an R57 code
defect, and therefore cannot be packaged as R58.

CC07 creates the minimum forward path to reacquire official inputs, reproduce
the exact accepted artifacts, qualify fresh task-scoped executors and retain
an external authority map before any CAL-REQ-004 decode or M3 operation.

## Architecture disposition

ADR-049 and ADR-054 are sufficient and remain unchanged. ADR-049 already
defines Principal custody, recoverable opaque locators, non-propagation and
the private-output registry. ADR-054 already requires exact runtime/model,
zero-egress evidence, typed executor handles and an authority map retained
outside the payload being verified. CC07 only operationalizes those accepted
decisions.

No schema, migration, ORM, OpenAPI, public API, dependency, workflow,
generation policy, QA threshold, Provider, resource ceiling, M6 authority or
real-user processing boundary changes. The existing
`PrivateVisionOperationExecutor` and `PrivateVisionCapabilityBinding` remain
the typed boundary. If a tracked executor implementation becomes necessary,
the task must stop for a separately frozen implementation allowlist.

## Exact immutable qualification facts

- Linux runtime SHA-256:
  `6a5fb35175efc2f014fb61f7f4abb2c78c38156bd6abf2186d1549cbf3f006a7`.
- Windows runtime SHA-256:
  `1c67ae02b90a5b00b58018c3c04db411134d781c6f53b195e68a6ce6136615ef`.
- Face Landmarker model SHA-256:
  `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`.
- V01 manifest SHA-256:
  `a1d3698564c8ca0d0b6f01fa28b580d85135ccc8c502616527a140d80ba41cb3`.
- QA policy content digest:
  `8305cfaa25d084138fb67e93043a1e37842543a645085d19d3ef52ac8a6ce15f`.
- Approved scope:
  `PRIVATE_SYNTHETIC_P2_M5_CC04_B_NORMALIZATION_FACE_POSE_LANDMARK_RELIABILITY_AND_MORPHOLOGY_ADMISSION_ONLY`.

Any artifact digest, byte size, toolchain, patch, platform, policy or scope
mismatch stops. A near match must not be relabeled as the accepted version.
A new runtime/model version requires a new Principal decision and, where it
changes ADR-054, a superseding ADR.

## Frozen task DAG

1. `P2-M5-CC07-G_FREEZE_EXACT_CAPABILITY_REQUALIFICATION_CONTRACT`
   creates only this tracked contract, canonical/mirror authority tails and
   their governance test.
2. `P2-M5-CC07-A_REACQUIRE_EXACT_PUBLIC_BUILD_INPUTS_AND_MODEL` reacquires only
   the official/tagged inputs already referenced by V01/R25, verifies the
   effective build-input manifest and exact model digest, and regenerates
   private SBOM/license/vulnerability evidence. It performs no canary access,
   decode, Vision, Provider, imagegen or database operation.
3. `P2-M5-CC07-B_REPRODUCE_EXACT_TWO_PLATFORM_RUNTIME` runs serially Linux then
   Windows with two clean roots per platform and requires byte-identical exact
   outputs. It creates fresh private runtime/model objects under new opaque
   task IDs; it does not reuse D02 or an unproven legacy handle.
4. `P2-M5-CC07-C_QUALIFY_EXECUTOR_AND_EXTERNAL_AUTHORITY` creates one
   task-scoped executor handle per platform, runs three zero-egress
   load/invoke/free/close lifecycle probes per platform using procedural
   non-human negative-control bytes, and has an independent Principal verifier
   write the per-platform canonical capability payload digests to the private
   registry. The executor/controller may not derive that expected map from
   itself.
5. `P2-M5-CC07-D_CANARY_REGISTRY_READINESS_CHECKPOINT` performs no decode, M3
   or imagegen. It re-verifies the externally retained registered-tip triad,
   binds both executor handles/map to CAL-REQ-004 and prepares a create-once
   terminal-tip registry slot. Only after its tracked Gates and Principal
   acceptance may the canary execute.

Tasks are serial. A later task cannot start from a local-only predecessor.

## Private output contract

The Principal private-output registry must retain create-once entries for:

- the official acquisition manifest;
- exact Linux and Windows runtime objects;
- the exact model object;
- one executor handle and zero-egress evidence ID/digest per platform;
- one canonical capability payload per platform and an independently verified
  authority map;
- the existing external registered-tip binding; and
- an empty write-once terminal-tip checkpoint capability.

Every entry records the creating task, opaque locator, exact digest/bytes,
platform/scope, authority, retention, custody, cleanup and allowed future task
`EXECUTE_CAL_REQ_004_POST_REGISTRATION_CANARY`. Locators, paths, Prompt,
runtime/model/image bytes, Provider payloads and credentials remain outside
Git, ordinary logs, CI artifacts, MEMORY and reviewer context.

The registered tip is read-only and cannot be regenerated. The terminal slot
must be ready before decode. After a terminal transition, the exact returned
receipt/state/event triad must be checkpointed immediately. Checkpoint failure
preserves terminal evidence but closes fresh recovery and successor creation;
the ordinal is never retried.

## Validation gates

- official-source allowlist, exact commit/tag/patch/toolchain/input-manifest
  and model SHA verification;
- two clean byte-identical roots per platform and every V01 runtime/OpenCV
  digest and byte size exact;
- private-path/debug/Clearcut/CA/network-import/export/RUNPATH scans;
- refreshed 51-component SBOM, license and vulnerability closure without scope
  promotion;
- three Linux `--network none` and three Windows process-specific outbound-deny
  lifecycle probes with zero observed egress and clean close;
- provider-neutral typed executor values, serial concurrency one, no hidden
  download, URL, SDK object or arbitrary path crossing the boundary;
- independent capability payload/map verification and missing, substituted or
  self-signed map negative controls;
- registry create-new/read-back/task binding/replay/cross-task/cross-platform/
  locator-loss/terminal-slot atomicity tests;
- exact registered-tip triad check and procedural R57 preflight with decode and
  executor call counts zero;
- exact changed-path allowlist, canonical/mirror equality, private-leak and
  Gitleaks scans, relevant Ruff/mypy/regression evidence, same-SHA three-job CI,
  eight artifact families, independent Security/Privacy/License/Research and
  Sol High review, then Principal acceptance.

## Stop rules

- missing official input:
  `BLOCKED_EXACT_BUILD_INPUT_AUTHORITY_UNAVAILABLE`;
- any runtime output digest or byte-size mismatch:
  `FURTHER_RESEARCH_EXACT_RUNTIME_REPRODUCTION_FAILED`;
- model mismatch, egress event, scope/platform mismatch, unresolved handle,
  authority-map self-signing or registered-tip mismatch:
  `BLOCKED_ALGORITHM_RUNTIME_AUTHORITY_MISMATCH` before decode;
- terminal-slot readiness failure: do not start the canary;
- post-terminal checkpoint failure: no successor, no fresh recovery and no
  retry.

Never change digests, policy, threshold, Provider, resource ledger or
CAL-REQ-005 authority to force progress. D02 handles, D02 negative handoff and
legacy private discovery are outside scope.

`PERSISTED_CAPABILITY_SELF_SIGNING: PROHIBITED`.

## Tracked scope for CC07-G

Only these four paths are allowed:

- this contract;
- `docs/operations/P2_M5_ACCEPTANCE.md` append-only current-authority tail;
- `docs/operations/P2_M5_EXECUTION_PROTOCOL.md` exact mirror tail; and
- `services/api/tests/test_questionbank_generation_policy_v3.py` governance
  assertions required because CC07 becomes the new true EOF.

CC07-G creates no private runtime/model object, executor, Prompt, image, Asset,
identity, schema row or external call.

## Acceptance and successor

After CC07-G local validation, normal non-force candidate push, exact-SHA CI,
eight artifact-family content checks, independent reviews and Principal
acceptance, its only successor is:

`P2-M5-CC07-A_REACQUIRE_EXACT_PUBLIC_BUILD_INPUTS_AND_MODEL`.

CC07-A uses the Owner's existing official-artifact acquisition authorization;
it is not a production, distribution, real-user or paid-service approval.
CAL-REQ-004 remains `OUTPUT_REGISTERED_PRE_DECODE`; CAL-REQ-005 and all M5/MVR/
M6 downstream Gates remain closed. CC07-D acceptance, not CC07-G alone, is the
precondition for `EXECUTE_CAL_REQ_004_POST_REGISTRATION_CANARY`.
