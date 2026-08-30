# P2-M5 CC08-G — Recoverable private Vision runtime V2 contract

## Bounded-task authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-CC08-G`
- `CHANGE_CONTROL_ID: CC-P2-M5-08`
- `TASK_NAME: Recoverable Private Vision Runtime V2 Qualification and CAL-REQ-004 Rebinding`
- `BASELINE_SHA: 359eb10961d2acc32603a136194270c9b1596b77`
- `BASELINE_CI_RUN: 33339583295_ATTEMPT_1_ALL_MANDATORY_JOBS_PASS`
- `CURRENT_MILESTONE: P2-M5_EXECUTING`
- `CURRENT_CANARY: CAL-REQ-004_OUTPUT_REGISTERED_PRE_DECODE`
- `CHANGE_CLASS: FORWARD_SUPERSEDING_RUNTIME_VERSION_CHANGE_CONTROL`
- `STATUS: CONTRACT_CANDIDATE_PENDING_TRACKED_GATES`

## Objective and non-retry rule

CC07-A's accepted stop remains immutable. CC08 creates a new runtime version
whose builder, inputs, output manifests, executors and registry authorities are
fully recoverable. It is not a retry, replacement or relabel of V01. The same
official source/model/patch inputs may be transferred only through exact
registry bindings; every new runtime byte receives a new identity.

## Frozen version names

- `BUILD_RECIPE_VERSION: p2-m5-cc08-source-built-vision-recipe-v1`
- `RUNTIME_MANIFEST_VERSION: p2-m5-cc08-private-vision-runtime-v1`
- `QA_POLICY_VERSION: p2-m5-cc08-private-vision-qa-v1`
- `CAPABILITY_PROFILE_VERSION: p2-m5-cc08-post-registration-capability-v1`
- model SHA-256 remains
  `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`.

Linux/Windows runtime and OpenCV digests are intentionally unknown until two
clean roots per platform produce byte-identical pairs. Those digests are frozen
once, before runtime/QA qualification.

## Serial task DAG

1. `P2-M5-CC08-G_FREEZE_SUPERSEDING_RUNTIME_DECISION_AND_ADR` creates only
   ADR-055, this contract, canonical/mirror tails and governance assertions.
2. `P2-M5-CC08-A_FREEZE_RECOVERABLE_BUILDER_RECIPE_AND_INPUT_LOCK` creates a
   tracked deterministic builder algorithm, exact public input lock and
   verifier, plus private registry-backed repository-cache and builder handles.
   CC07-A objects transfer only by exact digest/authority.
3. `P2-M5-CC08-B_BUILD_AND_FREEZE_NEW_TWO_PLATFORM_RUNTIME_MANIFEST` builds
   serial Linux then Windows in two clean roots each and freezes only
   byte-identical output pairs under the new runtime manifest.
4. `P2-M5-CC08-C_SUPPLY_CHAIN_AND_ZERO_EGRESS_QUALIFICATION` refreshes SBOM,
   license, model/data, vulnerability and native-surface evidence; performs
   three zero-egress lifecycle probes per platform; and creates immutable
   runtime/model/executor handles without canary access.
5. `P2-M5-CC08-D_PREREGISTER_AND_EXECUTE_FRESH_QA_REQUALIFICATION` freezes a
   synthetic-only calibration manifest, identity-disjoint sealed holdout,
   hypotheses and operation budget before reading a qualification image. It
   executes calibration first, then the unchanged sealed holdout, never
   CAL-REQ-004 or D02.
6. `P2-M5-CC08-E_REBIND_POST_REGISTRATION_CONTROLLER` updates only the tracked
   post-registration manifest/policy/runtime constants after B-D acceptance and
   reruns the complete CC06/R56/R57 negative matrix.
7. `P2-M5-CC08-F_CREATE_TASK_SCOPED_CAPABILITY_MAP_AND_CANARY_READINESS` has an
   independent verifier create the per-platform payload/map, binds executor
   handles and the exact registered tip, and prepares a write-once terminal-tip
   slot with decode/executor calls zero.

Every task is separately accepted; local-only evidence cannot open its
successor.

## Builder and private-output contract

The tracked builder recipe must specify source commit, 12 patch digests/order,
toolchains, environment, command, flags, public input URLs/checksums, repository
inventory, manifest algorithm, file ordering, exclusions, output paths,
resource bounds and reconstruction verification. Hidden downloads and
PATH-based fallback are prohibited.

The Principal registry retains create-once entries for transferred CC07-A
official inputs, the complete new input lock, repository cache, builder
spec/executable, two clean roots per platform, new runtime/OpenCV objects, the
same exact model, supply-chain evidence, calibration/holdout fixtures,
executor/zero-egress handles, canonical capability payloads, external map,
registered-tip binding and empty terminal-tip slot.

Every private entry is digest/byte/platform/scope/task bound, recoverably
located and has retention/cleanup evidence. Locators, paths, Prompt,
runtime/model/image bytes, Provider payloads and credentials never enter Git,
ordinary logs, CI artifacts, MEMORY or reviewer context.

## QA requalification

The old V03 limits may be copied unchanged only as preregistered candidate
hypotheses. They are not approved for new runtime bytes. A new policy digest
must bind the new runtime manifest and require exactly 478 finite landmarks,
finite matrix/coordinates, same-platform repeatability, cross-platform parity,
occupancy and pose evidence.

Calibration and sealed holdout must be synthetic-only, provenance-bound and
identity-disjoint. Thresholds freeze before holdout. No post-holdout relaxation,
canary-first calibration, D02 input, real-person data or legacy sealed holdout
discovery is permitted. If no recoverable qualification fixture exists, stop
before Vision for a separate fixture authority.

## Validation gates

- tracked builder algorithm/input-lock completeness and reconstruction test;
- exact source/model/patch/toolchain/repository inventory with no hidden fetch;
- two clean byte-identical builds per platform;
- PE/ELF imports/exports, private-path/debug/Clearcut/CA/network/Ooura and
  OpenCV vulnerable-surface controls;
- refreshed SBOM/license/model-data/vulnerability review with distribution,
  production and real-user use blocked;
- three Linux network-none and three Windows process-specific outbound-deny
  lifecycle probes with zero egress and clean close;
- preregistered calibration and sealed holdout with zero post-holdout policy
  change;
- provider-neutral typed executor, serial execution and zero retry;
- controller exact constants/module pin and rejection of old/substituted
  capabilities;
- R57 registered-tip replay and terminal-slot atomicity with zero readiness
  decode/executor calls;
- same-SHA three-job CI, eight artifacts, independent Security/Privacy/License/
  Research, Sol High and Principal acceptance for every tracked checkpoint.

## Stop rules

- incomplete builder/input lock:
  `BLOCKED_CC08_REPRODUCIBLE_BUILDER_AUTHORITY_INCOMPLETE`;
- source/model/patch/toolchain mismatch:
  `BLOCKED_CC08_INPUT_AUTHORITY_MISMATCH`;
- nondeterministic or single-platform build:
  `FURTHER_RESEARCH_CC08_RUNTIME_NOT_REPRODUCIBLE`;
- egress/native security/license failure:
  `REJECTED_CC08_RUNTIME_QUALIFICATION_FAILED`;
- missing clean synthetic calibration/holdout authority:
  `BLOCKED_CC08_QA_FIXTURE_AUTHORITY_UNAVAILABLE`;
- QA/parity/holdout failure:
  `FURTHER_RESEARCH_CC08_QA_REQUALIFICATION_FAILED`;
- controller/manifest/map/registered-tip mismatch:
  `BLOCKED_ALGORITHM_RUNTIME_AUTHORITY_MISMATCH` before decode;
- terminal-slot failure: canary stays closed; post-terminal checkpoint failure
  closes recovery/successor without retry.

No old-hash relabel, D02/legacy reuse, holdout leakage, CAL-REQ-005, resource
expansion, schema/public/dependency change, production, distribution or
real-user scope.

## CC08-G tracked scope and acceptance

Only these five paths are allowed:

- `docs/adr/ADR-055-recoverable-private-vision-runtime-version-and-rebinding.md`;
- this contract;
- append-only `docs/operations/P2_M5_ACCEPTANCE.md`;
- the exact `docs/operations/P2_M5_EXECUTION_PROTOCOL.md` mirror; and
- `services/api/tests/test_questionbank_generation_policy_v3.py` governance
  assertions.

CC08-G creates no private object, build, model load, Vision/decode/M3/imagegen
call, database mutation or controller change. After all local/remote/review
Gates and Principal acceptance, its unique successor is:

`P2-M5-CC08-A_FREEZE_RECOVERABLE_BUILDER_RECIPE_AND_INPUT_LOCK`.

The final successor after CC08-F acceptance is
`EXECUTE_CAL_REQ_004_POST_REGISTRATION_CANARY_WITH_CC08_RUNTIME_V1`.

No additional Owner decision is required for CC08-G under the existing
synthetic-only/internal official-artifact authorization. Owner escalation is
required only for paid/restrictive-EULA acquisition, a new model/Provider/
project dependency, new generation budget, schema/public/resource changes,
production/distribution/real-user scope or irreversible external action.
