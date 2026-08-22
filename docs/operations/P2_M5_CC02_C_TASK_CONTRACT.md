# P2-M5 CC02-C Serial Private Replay Bounded-Task Contract

## Status and authority

- Status: `READY_FOR_TRACKED_CONTRACT_EVIDENCE`.
- Task: `CC-P2-M5-02-C`.
- Change-control authority: ADR-047, ADR-048, ADR-049 and
  `P2_M5_CC02_FAILURE_MECHANISM_PROTOCOL.md`.
- Accepted CC02-B manifest: candidate `96ca439c727e0d9b54b1e6acdaf92be045ff40ab`, run
  `32332408245`, attempt 1.
- Accepted closure checkpoint: `3338b263eb3bdcd507ed6007c20b35d8f2070685`, run
  `32333890093`; all three jobs and eight artifacts passed.
- Diagnostic manifest digest:
  `5a0479a21556498d259572a050d659a0e3617429f83e5fd313c842a35591e0a3`.
- Current milestone: P2-M5 remains `EXECUTING`.
- Current authorization: this contract candidate is governance-only. It does not authorize replay, private-input read,
  transform, Vision, output creation or network activity.

The accepted Stage C outcome remains `FURTHER_RESEARCH` with 0/4 complete-case eligibility. CC02-C diagnoses the
frozen cases; it does not rerun that Gate, select a threshold, change an algorithm or promote a dimension. Contract
acceptance may open only a tracked, synthetic-only replay-driver implementation. Private replay remains closed until
that driver passes its own same-SHA acceptance and Principal records the separate pre-read/custody Gate.

## Bounded-task packet

- `BOOTSTRAP_STATUS`: `OK`.
- `TASK_ID`: `CC-P2-M5-02-C`.
- `OBJECTIVE`: after this contract receives tracked acceptance, implement a versioned first-party private-replay
  driver using synthetic/numeric tests only. After that driver receives separate tracked acceptance, execute exactly
  one Linux and one Windows replay, serially in the manifest platform order, under the accepted resource, custody,
  containment and fail-closed boundaries. Preserve private reports outside Git and publish only a redacted replay
  receipt. Do not aggregate mechanisms or decide a redesign in CC02-C.
- `WHY_DELEGATED`: the non-private driver implementation has frozen contracts but difficult multi-stage failure,
  resource and recovery control flow, so one Terra High worker may implement it without private input. Principal alone
  retains private-input custody, containment verification, real replay execution, tracked receipt publication and Gate
  authority.
- `SCOPE`:
  1. implement and test a deterministic driver that composes the accepted CC02-A validators with the existing frozen
     CC01C read-only computation helpers and approved private runtime adapters;
  2. obtain tracked driver acceptance before releasing any private locator or bytes;
  3. Principal recovers only the registered Stage C inputs/outputs from their original task receipts or private-output
     registry, validates every frozen authority and establishes the required platform containment;
  4. execute `linux_x86_64_network_none` and then `windows_x86_64` with no overlap, retry or generation;
  5. validate both complete private reports together and create one redacted tracked receipt only after every integrity
     Gate passes;
  6. leave CC02-D/E and every downstream Milestone Gate closed.
- `ALLOWED_FILES_OR_MODULES`:
  - future new `scripts/research/run_p2_m5_cc02_private_replay.py`;
  - future new `services/api/tests/test_p2_m5_cc02_private_replay.py`;
  - future new `docs/research/P2_M5_CC02_C_REPLAY_RECEIPT.json`;
  - future new `docs/operations/P2_M5_CC02_C_EXECUTION_REPORT.md`;
  - future status-only updates to this contract, the M5 execution protocol, CC02 research protocol, M5 acceptance,
    autonomous log and MEMORY by Principal;
  - read-only use of the accepted diagnostic manifest/preregistration, CC02-A harness, CC01C runner helpers, accepted
    domain/similarity contracts and private runtime adapters;
  - only after `CC02_C_RUNNER_PRE_READ_GATE: PASS`, Principal-only read access to exact registered source assets,
    normalized evidence, landmark/Vision evidence, accepted legacy reports, accepted result artifacts, model,
    topology and exact-manifest runtime roots required by the immutable manifest.
- `EXPECTED_CHANGE`:
  1. add replay-driver version `p2-m5-cc02-private-replay-v1` without modifying the accepted CC02-A harness, CC01C
     runner, geometry algorithm, measurement formula, Vision implementation or similarity/domain behavior;
  2. validate the tracked manifest digest and all report/case/repeat/direction bindings before any private asset read;
  3. recover private inputs only through the Principal registry/task receipt. No disk enumeration, filename guessing,
     broad private-root handoff or Owner re-upload is allowed;
  4. verify all input bytes, runtime/model/topology/plan authorities immediately before their first permitted use;
  5. execute at most 576 transforms and 604 Vision calls across both platforms, with zero generation/download/retry,
     global concurrency one, at most 7,200 seconds and 4 GiB new private output per platform, and at most 14,400
     seconds total;
  6. for every legacy-success platform case, recompute one result and require it to equal each of the three accepted
     result SHA bindings. Any drift stops as `TECHNICAL_FAIL_DIAGNOSTIC_REPLAY_DRIFT`;
  7. for each of the 14 direction-diagnostic platform cases, transform once and run exactly three Vision measurements
     over identical recomputed bytes. Classify only `TARGET_DIRECTION_STABLE_MISMATCH` or
     `MEASUREMENT_SIGN_UNSTABLE` under the accepted taxonomy;
  8. preserve every other terminal case at the first exact safe terminal stage with only an allowlisted generic or
     typed source reason. Any unknown stage/reason/pair or unexpected exception hard-stops as
     `UNCLASSIFIED_TERMINAL_FAILURE` without serializing exception details;
  9. create separate create-once private report/output roots for each platform. Existing CC01C roots and reports remain
     read-only;
  10. validate the two private reports with the accepted `validate_report_pair` authority before publishing a tracked
      receipt;
  11. publish no mechanism matrix in CC02-C. The receipt records only allowlisted authority digests, platform report
      digests, resource usage/outcome, containment outcome and an allowed CC02-C stop/completion status;
  12. leave the old 0/4 eligibility, all thresholds and every later Gate unchanged.
- `FORBIDDEN_SCOPE`:
  - private input access, replay or output creation while this contract is only a candidate;
  - private input access by the implementation worker, reviewer, ordinary CI or any Agent lacking a Principal-issued
    task-scoped packet;
  - modifying `run_p2_m5_cc01c_calibration.py`, `run_p2_m5_cc02_diagnostic.py`, accepted manifests, CC01C/CC02
    evidence, transform/domain/similarity/Vision code, schema/migration, ORM, API/OpenAPI, Worker, workflow,
    dependency/lockfile or model registry;
  - copying private input into tests, Git, logs, ordinary CI artifacts or Agent packets;
  - arbitrary path discovery, symlink/reparse traversal, unregistered input substitution or reconstructing missing
    evidence from the redacted aggregate;
  - parallel platform execution, retry, generation, download, live Provider call or network access;
  - threshold/tolerance selection, eligibility computation, READY promotion, candidate-v2/formula-v2/plan-v2,
    mechanism aggregate, redesign decision, Stage D/E, T06-T08, MVR, M6 or QuestionBank release;
  - real-person data, User-linked data, sensitive classification, beauty/attractiveness scoring or real-user facial
    processing.
- `DEPENDENCIES`:
  - accepted ADR-047/048/049 and the CC02 protocol;
  - accepted CC02-A harness at `ee19ad6...` and closure `470849f...`;
  - accepted CC02-B manifest digest `5a0479a2...`, its 288 logical/576 platform cases, 1,032 legacy-success repeat
    bindings and 14 direction-diagnostic bindings;
  - immutable accepted model/topology/algorithm and platform runtime manifest digests;
  - recoverable Principal private-output registry/task receipts for the existing synthetic-only private inputs;
  - existing private synthetic research approvals only. No production or real-user approval is inherited.
- `INPUTS_AND_ASSUMPTIONS`:
  - driver tests use only bounded in-memory synthetic/numeric doubles and non-image fixtures;
  - the private reports, source/result assets, landmarks, runtime roots, model and topology remain outside Git and are
    not available to the implementation worker or ordinary CI;
  - report/output locators are capability data and remain in the Git-external registry;
  - the accepted manifest is complete authority. A missing binding cannot be inferred;
  - Linux execution uses an isolated environment with `--network none` and a verified empty egress path;
  - Windows execution cannot read its first private input until a process-specific outbound deny is proven to cover
    the Principal runner and every spawned Vision/runtime child. Capture without deny is insufficient;
  - ADR-048 exclusive write/delete custody applies to each create-once private output root and to tracked receipt
    publication; Principal executes the sensitive step and takes the immediate snapshot.
- `ACCEPTANCE_CRITERIA`:
  1. this contract candidate changes governance only, passes formatting/diff/status scans and remains
     `READY_FOR_TRACKED_CONTRACT_EVIDENCE`;
  2. after contract acceptance, the new driver/test candidate has no private input and changes only its two authorized
     implementation paths plus status evidence;
  3. synthetic tests prove exact manifest/case admission, per-stage exception boundaries, resource accounting,
     serial-platform ordering, no retry, create-once/no-partial output and complete redaction;
  4. synthetic tests prove no source/report/runtime/model read, transform, Vision or output creation before manifest,
     custody and containment admission succeeds;
  5. driver candidate passes Ruff, strict mypy, targeted tests, complete local Gates, same-SHA three-job Actions,
     eight-artifact inspection and independent security/research-integrity/final review;
  6. Principal records `CC02_C_RUNNER_PRE_READ_GATE: PASS` only after confirming the accepted driver/test blobs and
     the exact tracked manifest digest;
  7. immediately before each platform run, Principal proves registered input authority, regular/non-reparse nodes,
     create-once output absence, exclusive custody and platform containment without printing locators;
  8. Linux completes before Windows starts. Their private time windows do not overlap, and every operation counter is
     derived rather than supplied;
  9. the complete pair covers exactly 576 platform cases, 232 terminal failures, 344 legacy-success cases, 1,032
     accepted repeat bindings, 14 direction cases and 42 direction measurements with zero unknown/unclassified row;
  10. all legacy-success recomputed result bytes equal all accepted result SHA bindings. Any mismatch produces no
      accepted report pair or tracked PASS receipt;
  11. every direction case binds one recomputed result SHA and three finite measurements over identical bytes, with an
      exact accepted taxonomy result and no legacy-success drift claim;
  12. `validate_report_pair` accepts both private reports, all authority/digest/cardinality/resource checks and
      non-overlapping serial windows before receipt construction;
  13. the tracked receipt and human report contain no private path, filename, image, landmark, Prompt, object key,
      Provider payload, credential, raw exception, signed URL, threshold, eligibility, READY class or per-case
      mechanism data;
  14. private reports and outputs are registered with recoverable opaque locators, digest, bytes, authority, retention,
      allowed future task `CC-P2-M5-02-D`, custody and cleanup state, but the locator never enters Git or MEMORY;
  15. exact-SHA receipt candidate CI/artifacts and independent reviews pass before Principal accepts CC02-C;
  16. CC02-C acceptance opens only a separate CC02-D bounded-task contract. It never opens CC02-D execution directly
      or changes Stage D/E, T06-T08, MVR, M6, production geometry or real-user processing.
- `VALIDATION_COMMANDS`:
  - contract candidate: `pnpm.cmd format:check`;
  - contract candidate: `git diff --check`;
  - contract candidate: bounded status/field scan proving no implementation path, private path, replay result,
    threshold, schema/API/dependency or downstream-Gate authorization drift;
  - future driver candidate: `python -m ruff format --check
scripts/research/run_p2_m5_cc02_private_replay.py
services/api/tests/test_p2_m5_cc02_private_replay.py`;
  - future driver candidate: `python -m ruff check scripts/research/run_p2_m5_cc02_private_replay.py
services/api/tests/test_p2_m5_cc02_private_replay.py`;
  - future driver candidate: strict mypy for `scripts/research/run_p2_m5_cc02_private_replay.py` with
    `MYPYPATH=services/api/src` or the Windows equivalent;
  - future driver candidate: `python -m pytest services/api/tests/test_p2_m5_cc02_private_replay.py
services/api/tests/test_p2_m5_cc02_diagnostic.py -q` with synthetic/numeric doubles only;
  - future driver candidate: bounded source/diff scans for network client, retry/concurrency, private field/path,
    threshold, schema/API/dependency/model/workflow and accepted evidence drift;
  - future driver candidate: complete local Gates, same-SHA Actions, eight-artifact inspection and independent reviews
    before the pre-read Gate;
  - future real replay: execute only the accepted driver in a Principal-held task-scoped environment. Command lines,
    environment values and private locators are not copied into tracked evidence;
  - future replay validation: recompute manifest/report/row/result/resource digests and run the accepted pair validator;
    print only PASS/FAIL plus allowlisted aggregate counts/digests;
  - future receipt candidate: `pnpm.cmd format:check`, `git diff --check`, exact cumulative path allowlist, private-field
    scan, schema/API/dependency/model/workflow drift scan, full local regression, same-SHA Actions/eight artifacts and
    independent reviews.
- `SECURITY_NOTES`: private bytes and locators are capabilities. Principal releases none to the implementation worker,
  ordinary CI or reviewers. Windows deny must cover the runner and child processes before first read; Linux remains
  network-none. Any egress attempt, containment ambiguity, path/type/hash mismatch, resource breach, unexpected
  exception or taxonomy violation hard-stops without a PASS receipt. Raw exceptions are never serialized.
- `PRIVACY_NOTES`: all inputs remain private synthetic research evidence. Synthetic origin does not make them public.
  No User relation, real-person input, image, landmark, Prompt or object/storage reference enters Git, ordinary
  artifacts, MEMORY or unrelated Agent context.
- `DATA_NOTES`: CC02-C creates new private diagnostic reports and a redacted replay receipt only. It does not modify
  CC01C/CC02-B evidence or create a mechanism aggregate, threshold, eligibility result or ontology promotion. The old
  0/4 complete-case result remains immutable.
- `LICENSE_NOTES`: no dependency, model, runtime or data artifact is added, downloaded, redistributed or requalified.
  Existing OpenCV/Vision/model artifacts retain their private synthetic research-only scope; their use grants no
  distribution, production or real-user authorization.
- `ROLLBACK`: before contract acceptance, revert only this forward governance candidate. Before runner acceptance,
  reject only the new driver/test candidate. After a private run begins, preserve attempt evidence and never overwrite
  a private output root; a failed platform run requires a new forward task/version, not retry. After CC02-C acceptance,
  corrections require new forward evidence and must not rewrite CC01C, CC02-B or accepted private reports.
- `RECOMMENDED_AGENT`: `pm_terra_high_worker` for the future non-private driver/test implementation with exclusive
  ownership of those two paths. Principal is the sole sensitive replay executor and owns containment, private registry,
  receipt publication, commit/push and Gate decisions.
- `RECOMMENDED_MODEL_TIER`: Terra High. Architecture, taxonomy and resource contracts are frozen, while exact staged
  failure mapping, cross-platform serialization, resource accounting and fail-closed private execution require deep
  control-flow reasoning.
- `ESCALATION_CONDITION`: stop before writing or reading private input if any authority/locator/digest is missing, the
  accepted driver cannot express an exact stage without modifying old behavior, containment/custody cannot be proven,
  a retry or resource expansion is required, or completion would change algorithm/formula/taxonomy/schema/API/
  dependency/model/threshold/research objective/downstream Gate. Return the exact accepted stop outcome; do not guess,
  partially publish or recast the conflict as a Repair.
- `OUTPUT_FORMAT`: `STATUS: PASS|BLOCKED|FAILED; SUMMARY; CHANGED_FILES; VALIDATION_RUN; VALIDATION_RESULT;
DRIVER_VERSION_AND_BLOBS; PRE_READ_GATE; INPUT_AUTHORITY; PLATFORM_ORDER_AND_CONTAINMENT; PRIVATE_REPORT_DIGESTS;
RESOURCE_USAGE; REPORT_PAIR_VALIDATION; TRACKED_RECEIPT; STOP_OUTCOME; SECURITY_PRIVACY_BOUNDARY;
RISKS_OR_OPEN_QUESTIONS; MEMORY_CANDIDATES; ESCALATION_REASON`.

## Execution and acceptance order

```text
this tracked contract candidate
→ same-SHA CI and eight-artifact inspection
→ independent contract/security/final review
→ Principal CC02-C contract acceptance
→ one Terra High worker implements the driver/tests with synthetic input only
→ Principal diff, targeted and full validation
→ driver candidate same-SHA CI/artifacts and independent reviews
→ Principal records CC02_C_RUNNER_PRE_READ_GATE: PASS
→ Principal recovers exact registered inputs and establishes ADR-048 custody
→ Linux --network none replay and immediate private snapshot
→ Windows child-inclusive outbound-deny replay and immediate private snapshot
→ accepted pair validation and private-output registry update
→ redacted receipt candidate/full local Gate
→ same-SHA CI/eight artifacts and independent reviews
→ Principal CC02-C acceptance
→ separate CC02-D bounded-task contract
```

`CC_P2_M5_02_C_CONTRACT: READY_FOR_TRACKED_CONTRACT_EVIDENCE`

`CC_P2_M5_02_C_DRIVER: CLOSED_PENDING_CONTRACT_ACCEPTANCE`

`CC02_C_RUNNER_PRE_READ_GATE: CLOSED_PENDING_TRACKED_DRIVER_ACCEPTANCE`

`CC_P2_M5_02_C_REPLAY: NOT_EXECUTED`

`CC_P2_M5_02_D_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`

`P2_MVR_V1_RESULT: NOT_EVALUATED`

`P2_M6_ENTRY: CLOSED_PENDING_TECHNICAL_AND_MVR_PASS`

## Principal pre-read acceptance and bounded recovery stop

- Pre-read checkpoint `d134517fa97132b180a82c69c617b8f65d3b282e` passed exact-SHA run `32345071728`, all
  three jobs, eight readable artifacts and both independent reviews. Principal accepts the exact tracked driver/test
  blobs and records the governance pre-read Gate as passed.
- Recovery then used only the original Codex task receipt and its exact task-owned capabilities. It recovered the
  Stage B private authority root, all 12 normalized-source nodes, all 12 Vision/landmark-log nodes, the accepted
  Windows Vision/model nodes and the Windows legacy-report node. No locator is recorded here.
- The exact qualified Linux legacy-report capability was not present in the recovered receipt/registry state. The
  prior environment references were absent, and the accepted Debian 13 execution image was no longer present.
  PostgreSQL contained zero surviving Asset rows and therefore could not serve as replacement authority.
- Broad disk, parent-directory or Docker-volume enumeration is prohibited by ADR-049 and was not used. Rebuilding the
  Linux legacy report, rerunning Stage C or substituting an aggregate is also prohibited. Recovery therefore stops at
  the contract's accepted outcome `FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE` with operational classification
  `EVIDENCE_LOCATION_LOST`.
- No legacy-report bytes, normalized image bytes, landmark bytes or model bytes were consumed by a platform replay.
  No transform, Vision call, output root, private diagnostic report, report pair or tracked receipt was created.

`CC_P2_M5_02_C_CONTRACT: PASS_AT_8213B40_RUN_32336519837_ATTEMPT_1`

`CC_P2_M5_02_C_DRIVER: PASS_AT_410DCB9_RUN_32343563224_ATTEMPT_1`

`CC02_C_RUNNER_PRE_READ_GATE: PASS_AT_D134517_RUN_32345071728_ATTEMPT_1`

`CC02_C_INPUT_RECOVERY: EVIDENCE_LOCATION_LOST`

`CC_P2_M5_02_C_REPLAY: NOT_EXECUTED_FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE`

`CC02_C_REPORT_PAIR_VALIDATION: NOT_RUN`

`CC02_C_TRACKED_RECEIPT: NOT_CREATED`

`CC_P2_M5_02_D_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`

`P2_MVR_V1_RESULT: NOT_EVALUATED`

`P2_M6_ENTRY: CLOSED_PENDING_TECHNICAL_AND_MVR_PASS`

`P2_M5_NEXT_ACTION: PREPARE_FORWARD_RECOVERY_FAILURE_CHANGE_CONTROL_NO_REGENERATION`
