# P2-M5 CC02-A Diagnostic Harness Bounded-Task Contract

## Status and authority

- Status: `IMPLEMENTATION_ACCEPTED`.
- Task: `CC-P2-M5-02-A`.
- Change-control authority: ADR-047 and `P2_M5_CC02_FAILURE_MECHANISM_PROTOCOL.md`.
- Governance acceptance: `137157c41e7b1436ae47fe7dfcf34a7127789166`, run `32267510703`, attempt 1.
- Governance closure: `24079b48b301ec38e07c02d4e1ff0b423a7ad6e7`, run `32268767796`, attempt 1;
  all three jobs passed and eight exact-SHA artifacts were inspected.
- Contract acceptance: `d8659ae88fb32c99220d522fc6dbf94a8fc588ac`, run `32271571196`, attempt 1;
  all three jobs passed, eight exact-SHA artifacts were inspected, and independent security and final reviews passed.
- Implementation acceptance: implementation commit `5159c3f28ab8dcbb7db07c5bead3780a409ace25` plus R04 commit
  `ee19ad6efe49decfa3a0c8f0dbf3f130b5c59460`, run `32282614608`, attempt 1.
- Acceptance closure: `470849f0f42f151d1ec939e3b0d81ef4369ea86c`, run `32284285946`; all three jobs,
  Browser Integration 5/5 and eight exact-SHA artifacts passed.
- Current milestone: P2-M5 remains `EXECUTING`.
- Current authorization: CC02-A is complete. Only a separate CC02-B tracked contract candidate may be prepared.
  Execution against private input remains prohibited and requires CC02-B tracked contract acceptance.
- Private-input access: prohibited.

This contract does not reopen the accepted Stage C result. `CC-P2-M5-01-C` remains `FURTHER_RESEARCH`, its complete-case
eligible count remains 0/4, and all old runner outputs and reports remain immutable.

## Bounded-task packet

- `BOOTSTRAP_STATUS`: `OK`.
- `TASK_ID`: `CC-P2-M5-02-A`.
- `OBJECTIVE`: implement a new versioned, diagnosis-only harness that classifies failures at the eight frozen execution
  boundaries, preserves allowlisted typed reason codes losslessly, enforces the CC02 resource/redaction envelope, and is
  proven only with deterministic synthetic/numeric golden tests.
- `WHY_DELEGATED`: after tracked contract acceptance, delegate the difficult but frozen failure-path implementation to a
  single Terra High worker. The task has deep staged control flow and fail-closed exception handling, but no remaining
  architecture, schema, API, dependency or research-threshold choice.
- `SCOPE`: one new CC02 research harness, its targeted tests and a non-image golden taxonomy fixture. CC02-A may build
  and test the machinery needed by a later replay, but it must not read or execute against private Stage C inputs.
- `ALLOWED_FILES_OR_MODULES`:
  - new `scripts/research/run_p2_m5_cc02_diagnostic.py`;
  - new `services/api/tests/test_p2_m5_cc02_diagnostic.py`;
  - optional new `services/api/tests/fixtures/p2_m5_cc02_failure_taxonomy.json` containing only synthetic/numeric safe
    cases and no image, landmark, path, object key, Prompt or private identifier;
  - read-only imports from `scripts/research/run_p2_m5_cc01c_calibration.py` and existing first-party domain/provider
    modules.
- `EXPECTED_CHANGE`:
  - declare harness version `p2-m5-cc02-diagnostic-harness-v1`, taxonomy version
    `p2-m5-cc02-terminal-taxonomy-v1` and private report schema
    `mirror.p2-m5/CC02-private-platform-diagnostic-report/v1`;
  - place an explicit exception boundary around each frozen stage: `SOURCE_ADMISSION`, `SPECIFICATION`,
    `CONTROL_POINT_BUILD`, `WARP_PLAN_AUTHORITY`, `TRANSFORM`, `RESULT_VISION_QA`, `MEASUREMENT_DIRECTION` and
    `RESULT_SIGNATURE`;
  - preserve an allowed `DomainValidationError.reason_code` or `SimilarityValidationError.reason_code` only at the
    stage/code pairs frozen by the protocol; convert an allowed generic `ValueError`/`RuntimeError` at its exact
    boundary to the corresponding safe generic reason;
  - hard-stop any unknown stage, unknown reason, wrong stage/code pair or unexpected exception as
    `UNCLASSIFIED_TERMINAL_FAILURE` without serializing the exception type, message or traceback;
  - expose deterministic canonical-digest, safe-record, resource-counter and redaction validation helpers for later
    CC02-B/C use;
  - validate the complete frozen resource envelope before any operation: exactly 12 identities, six candidate
    dimensions, 288 logical cases, 576 platform cases, at most 576 single-repeat transforms, at most 604 Vision
    executions, zero generation, zero retry, concurrency 1, Windows/Linux serial execution, at most 120 minutes per
    platform and 240 minutes total, at most 4 GiB private output per platform, and zero dependency/model/runtime
    download;
  - make all output roots create-once and separate from CC01C roots, while leaving their concrete private locations to
    the future accepted CC02-B manifest;
  - emit a top-level private platform report with exactly these keys and reject missing or additional keys: `schema`,
    `harness_version`, `taxonomy_version`, `platform`, `diagnostic_manifest_digest`, `candidate_manifest_digest`,
    `legacy_report_sha256`, `legacy_report_digest`, `cohort_digest`, `case_set_digest`, `runtime_manifest_digest`,
    `model_sha256`, `topology_sha256`, `algorithm_version`, `resource_usage`, `resource_outcome`,
    `terminal_failure_cases`, `legacy_success_repeats`, `direction_measurements` and `report_digest`;
  - `resource_outcome` is the exact scalar `WITHIN_ENVELOPE` for a complete accepted report. A resource breach hard-stops
    without an accepted report. `resource_usage` has exactly these integer/string keys: `identity_count=12`,
    `candidate_count=6`, `logical_case_count=288`, `platform_case_count=288`, `transform_execution_count` in `0..288`,
    `vision_execution_count` in `0..(288 + 2 * direction_case_count)`, `generation_attempt_count=0`, `retry_count=0`,
    `download_count=0`, `max_concurrency=1`, `execution_mode=SERIAL`, `wall_clock_seconds` in `0..7200`, and
    `private_output_bytes` in `0..4294967296`, plus `started_at_utc` and `ended_at_utc` as strict second-precision RFC
    3339 UTC strings. `wall_clock_seconds` must equal the non-negative timestamp difference. Booleans are not accepted as
    integers;
  - each `terminal_failure_cases` entry has exactly: `case_digest`, `candidate`, `direction`, `magnitude_ppm`, `platform`,
    `terminal_stage`, `diagnostic_reason`, `source_reason_family`, `source_reason_code`, `source_sha256`, `result_sha256`,
    `runtime_manifest_digest`, `model_sha256`, `topology_sha256`, `plan_digest`, `algorithm_version`, `harness_version`,
    `taxonomy_version` and nullable `signed_target_delta`;
  - each `legacy_success_repeats` entry has exactly: `case_digest`, `candidate`, `direction`, `magnitude_ppm`, `platform`,
    `repeat_index`, `source_sha256`, `accepted_result_sha256`, `recomputed_result_sha256`, `legacy_row_digest`,
    `runtime_manifest_digest`, `model_sha256`, `topology_sha256`, `plan_digest` and `algorithm_version`. It has no
    terminal stage/reason and may not carry a target delta or a positive legacy-success drift claim. For each success
    case all three accepted result SHA values and the one recomputed result SHA must be identical; any mismatch hard-stops
    the report as `TECHNICAL_FAIL_DIAGNOSTIC_REPLAY_DRIFT`;
  - each `direction_measurements` entry has exactly: `case_digest`, `candidate`, `direction`, `magnitude_ppm`, `platform`,
    `measurement_index`, `source_sha256`, `plan_digest`, `recomputed_result_sha256`, `signed_target_delta`,
    `runtime_manifest_digest`, `model_sha256`, `topology_sha256`, `algorithm_version`, `harness_version` and
    `taxonomy_version`;
  - all digests are lowercase 64-hex strings; candidate/direction/magnitude/platform values belong to the frozen CC01C
    sets; all counts/indices are non-boolean integers; every target delta is finite. In a terminal record,
    `source_reason_family` and `source_reason_code` are both null or both non-null, `source_sha256` may be null only at
    `SOURCE_ADMISSION`, `plan_digest` may be null only through `WARP_PLAN_AUTHORITY`, `result_sha256` may be null only
    through a `TRANSFORM` failure, and `signed_target_delta` is null because the three individual values live only in
    `direction_measurements`;
  - `source_reason_family` is exactly `DOMAIN`, `SIMILARITY` or null. `DOMAIN` is valid only for an observed
    `DomainValidationError` whose `ReasonCode` is allowed at that terminal stage; `SIMILARITY` is valid only for an
    observed `SimilarityValidationError` at `RESULT_SIGNATURE` with one of its five frozen allowed reason codes. The
    family and safe code are both null for generic/legacy reasons and both non-null for typed reasons. Exception class
    names are checked in memory but never serialized;
  - enforce one cross-authority Gate before report construction: every row platform equals the top-level platform; every
    row runtime/model/topology/algorithm/harness/taxonomy value it carries equals the corresponding top-level and future
    CC02-B accepted authority; top-level `diagnostic_manifest_digest` equals the tracked CC02-B manifest content digest;
    candidate/direction/magnitude belongs to the exact bound candidate manifest; and any repeated case digest has
    identical case/candidate/direction/magnitude/platform authority across all three collections;
  - resolve every `legacy_row_digest` to exactly one actual row inside the exact accepted report bytes bound by
    `legacy_report_sha256` and `legacy_report_digest`. Its case digest, candidate, direction, magnitude, repeat index,
    source SHA, accepted result SHA and plan digest must equal the projected binding record; its report-level platform,
    runtime/model/topology and candidate-manifest authorities must equal the new report authorities, and algorithm
    authority must equal the version resolved from that accepted candidate manifest. Zero or multiple matches, or any
    projection mismatch, hard-stops before output;
  - for each direction case, all three measurements have identical non-null source SHA, plan digest and recomputed result
    SHA; those values equal the corresponding terminal failure's source SHA, plan digest and result SHA. The terminal
    stage is `MEASUREMENT_DIRECTION`, and its reason equals the deterministic classifier output from the exact three
    signed deltas and requested direction. The harness invokes transform exactly once for that case;
  - sort `terminal_failure_cases` by `case_digest`, `legacy_success_repeats` by `(case_digest, repeat_index)` and
    `direction_measurements` by `(case_digest, measurement_index)`. No sort key is nullable;
  - compute every canonical digest with the existing `_canonical_digest(schema, document, omitted)` semantics: omit
    only `report_digest`, serialize with `allow_nan=False`, `ensure_ascii=True`, `separators=(",", ":")` and
    `sort_keys=True`, prefix the canonical JSON with the exact schema identifier plus `\n`, encode UTF-8 and emit the
    lowercase SHA-256. `legacy_row_digest` separately binds the complete accepted legacy row as lowercase SHA-256 over
    `mirror.p2-m5/CC01C-private-platform-report/v2#row\n` plus that row's canonical JSON using the same JSON options and
    UTF-8 encoding. Additional/missing keys or a digest mismatch fail before output write;
  - no raw exception/private field is permitted in any exact key set. Signed target deltas exist only in the frozen
    direction measurement collection; thresholds, eligibility and READY classification are absent.
- `FORBIDDEN_SCOPE`:
  - any modification to `run_p2_m5_cc01c_calibration.py`, CC01C manifest/aggregate/report evidence or old private
    outputs;
  - copying or changing plan construction, measurement formula, transform, Vision, similarity or domain behavior;
  - any private Stage C report, source asset, image, landmark log, result artifact, runtime/model binary or private path
    read;
  - creating the real CC02-B manifest, selecting its opaque case digests, executing Windows/Linux replay or producing a
    mechanism aggregate;
  - schema/migration, ORM, public API/OpenAPI, Worker, dependency, lockfile, model artifact, workflow or production
    configuration changes;
  - threshold selection, tolerance changes, candidate-v2/formula-v2/plan-v2, dimension disposition, identity/cohort
    expansion, generation, Stage D/E, T06–T08, MVR, M6 or QuestionBank release;
  - network access, package/model download, retry, concurrency greater than 1, real-person or User-linked data.
- `DEPENDENCIES`:
  - ADR-047 and the accepted CC02-G protocol;
  - immutable CC01C candidate/aggregate/cohort/case/runtime/model/topology authorities listed in that protocol;
  - existing `DomainValidationError`, `ReasonCode`, `SimilarityValidationError` and `SimilarityReasonCode` contracts;
  - existing CC01C plan/measurement helpers and approved private runtime adapters, used read-only.
- `INPUTS_AND_ASSUMPTIONS`:
  - tests use only in-memory synthetic/numeric doubles and the optional non-image golden fixture;
  - the future CC02-B manifest, private reports and opaque legacy case list do not yet exist as accepted inputs and must
    not be guessed, reconstructed from the redacted aggregate or embedded in this task;
  - Windows child-process-inclusive outbound deny and Linux `--network none` remain future CC02-C execution
    prerequisites; CC02-A tests neither simulate their success nor claim containment evidence;
  - no accepted legacy result bytes exist for the 14 direction-mismatch platform cases.
- `ACCEPTANCE_CRITERIA`:
  1. all eight terminal stages and every permitted generic/typed stage-code pair have deterministic golden PASS cases;
  2. every wrong stage/code pair, unknown stage/reason, raw generic exception outside its exact boundary and malformed
     record fails closed as `UNCLASSIFIED_TERMINAL_FAILURE`;
  3. serialized safe records never contain raw exception text, traceback, image/landmark content, Prompt, credential,
     path, object key, Provider payload, private identifier or unbounded numeric payload;
  4. canonical output and digest are stable across repeated runs and key ordering;
  5. deterministic validators accept exactly 12 identities, six candidates, 288 logical cases and 576 platform cases;
     reject 11/13 identities, 5/7 candidates, 287/289 logical cases and 575/577 platform cases; and perform no I/O on
     rejection;
  6. transform/Vision counters reject before invocation at 577/605; non-zero generation/download/retry, concurrency
     other than 1, parallel or interleaved platforms, elapsed time over 120 minutes per platform or 240 minutes total,
     and private output over 4 GiB per platform all fail closed under fake-clock/numeric golden tests;
  7. direction-sign classification accepts exactly three finite measurements over identical recomputed result bytes.
     Three non-zero deltas with the same wrong sign yield `TARGET_DIRECTION_STABLE_MISMATCH`; any sign change or exact
     zero yields `MEASUREMENT_SIGN_UNSTABLE`; three non-zero deltas with the same correct sign are outside the frozen
     mismatch taxonomy and hard-stop as `UNCLASSIFIED_TERMINAL_FAILURE`. No outcome can claim legacy-success drift;
  8. tests prove no source/private report read, subprocess, transform, Vision call, network call or output-root creation
     occurs before all non-private admission and resource checks pass;
  9. each report contains exactly 288 unique `(platform, case_digest)` values across the disjoint union of terminal
     failures and distinct legacy-success cases. The two-report validator derives exactly 576 platform cases and 288
     logical case digests, each logical digest appearing once on each platform;
  10. the two-report validator derives exactly 232 terminal failure cases with valid stage/reason pairs and exactly 344
      distinct legacy-success platform cases. Every success case has repeat indices `{1,2,3}` and three accepted result
      SHA bindings, for exactly 1,032 repeat records. Its single recomputed result SHA equals all three accepted values;
      any drift hard-stops without a complete report. Supplied top-level counts cannot substitute for these collections;
  11. exactly 14 distinct direction platform cases are a subset of the terminal failures at
      `MEASUREMENT_DIRECTION`. Each has exactly one recomputed result SHA and measurement indices `{1,2,3}`, all three
      rows bind that identical SHA plus one source SHA and plan digest, all equal the linked terminal record. The
      terminal reason equals the classifier output, transform is invoked once per direction case, and the two reports
      contain exactly 42 finite signed deltas. None may be represented in `legacy_success_repeats` or compared as
      legacy-success drift;
  12. all resource values are derived from the validated collections and operation counters. Across both reports,
      transforms are at most 576, Vision calls are at most 604, wall clock is at most 14,400 seconds and platforms do not
      overlap according to strict start/end timestamps; per-report bounds remain independently enforced;
  13. top-level, resource and all three collection key sets, nullability, enum/digest/numeric bounds, ordering and
      canonical digest have golden PASS cases; every missing/additional field, invalid nullability, duplicate/missing
      record or supplied/derived count mismatch fails closed before output write;
  14. golden negative cases prove row/top-level/manifest authority equality, cross-collection case equality, exact legacy
      report membership/projection equality, `DOMAIN|SIMILARITY|null` family/code/class consistency and direction
      measurement-to-terminal result/classification equality;
  15. the old runner and evidence, transform/domain modules, database schema, OpenAPI, dependency manifests, lockfile
      and model registry have zero diff;
  16. no task output selects a threshold, alters 0/4 eligibility or opens any later CC02 or Milestone Gate.
- `VALIDATION_COMMANDS`:
  - Windows local:
    `.\.venv\Scripts\python.exe -m ruff format --check scripts/research/run_p2_m5_cc02_diagnostic.py services/api/tests/test_p2_m5_cc02_diagnostic.py`;
  - Windows local:
    `.\.venv\Scripts\python.exe -m ruff check scripts/research/run_p2_m5_cc02_diagnostic.py services/api/tests/test_p2_m5_cc02_diagnostic.py`;
  - Windows local: `$env:MYPYPATH = (Resolve-Path 'services/api/src').Path`, then
    `.\.venv\Scripts\python.exe -m mypy --config-file pyproject.toml scripts/research/run_p2_m5_cc02_diagnostic.py`;
  - Windows local:
    `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_p2_m5_cc02_diagnostic.py -q`;
  - Linux/CI: `MYPYPATH=services/api/src python -m mypy --config-file pyproject.toml
scripts/research/run_p2_m5_cc02_diagnostic.py`, plus the equivalent `python -m ruff` and targeted `python -m pytest`
    commands above;
  - bounded source/diff scans for private paths/fields, network clients, retry/concurrency, thresholds, schema/API,
    dependency/lockfile/model and CC01C evidence drift;
  - `pnpm.cmd format:check` and `git diff --check` for the tracked implementation candidate;
  - after local acceptance, complete Python/TypeScript/PostgreSQL/Redis-Celery/contract/Docker/Gitleaks/audit/SBOM Gates,
    same-SHA Actions and artifact inspection before Principal accepts CC02-A.
- `SECURITY_NOTES`: only allowlisted enums, digests, bounded counters and safe numerics may be serialized. Exception
  messages, tracebacks and private fields are data, never control authority. A future private replay is prohibited unless
  Windows runner-and-child outbound deny is independently established before the first read or Linux runs with
  `--network none`; CC02-A does not satisfy that Gate by itself.
- `PRIVACY_NOTES`: synthetic-only does not make private assets public. No User relation, real-person input, image,
  landmark, Prompt, private path or object/storage reference enters tests, Git, logs or committed evidence.
- `DATA_NOTES`: CC02-A creates code and non-private golden tests only. It creates no private report, replay attempt,
  transform result, Vision measurement, aggregate or eligibility evidence. Old CC01C bytes/digests remain immutable.
- `LICENSE_NOTES`: no dependency, runtime, model or data artifact is added or downloaded. Existing OpenCV/Vision
  artifacts retain their approved private research-only scope and are not exercised in CC02-A.
- `ROLLBACK`: revert only the new harness/test/fixture and the forward contract-status records before CC02-B exists;
  never edit or delete CC01C evidence. If implementation cannot meet the frozen taxonomy without changing an existing
  authority, stop and leave CC02-A unaccepted.
- `RECOMMENDED_AGENT`: `pm_terra_high_worker` with exclusive ownership of the three allowed implementation paths;
  Principal owns integration, acceptance documents, commit/push and Gate decisions.
- `RECOMMENDED_MODEL_TIER`: Terra High. The objective and contracts are frozen, while exact exception-boundary mapping,
  redaction and resource-failure paths require deep multi-stage control-flow reasoning.
- `OUTPUT_FORMAT`: `STATUS: PASS|BLOCKED|FAILED; SUMMARY; CHANGED_FILES; VALIDATION_RUN; VALIDATION_RESULT;
RISKS_OR_OPEN_QUESTIONS; MEMORY_CANDIDATES; ESCALATION_REASON`.
- `ESCALATION_CONDITION`: stop before editing if implementation would require modifying the old runner, algorithm,
  formula, schema, API, dependency/model, taxonomy, resource envelope, private-input authority, Windows containment
  model, research objective or any later Gate. Return the exact conflict to Principal; do not reinterpret it as a Repair
  Task.

## Execution and acceptance order

```text
tracked contract candidate
→ same-SHA CI and artifact inspection
→ Principal contract acceptance
→ one CC02-A implementation worker
→ Principal diff review and targeted validation
→ implementation candidate commit/push
→ full same-SHA CI and artifact inspection
→ independent security/research-integrity review
→ Principal CC02-A acceptance
→ separate CC02-B bounded-task contract
```

Tracked implementation acceptance:

- Implementation commit `5159c3f28ab8dcbb7db07c5bead3780a409ace25` and the bounded R04 repair at
  `ee19ad6efe49decfa3a0c8f0dbf3f130b5c59460` passed exact-SHA run `32282614608` attempt 1. All three jobs and eight
  artifacts passed; the full Python suite was 642 PASS with one existing optional skip, Browser Integration was 5/5,
  and the targeted harness contract matrix was 58 PASS.
- Independent contract, security and final reviews found no mandatory issue. Principal accepts only the frozen CC02-A
  implementation. This opens a separate CC02-B bounded-task contract and does not permit private input or replay.

`CC_P2_M5_02_A_CONTRACT: PASS_AT_D8659AE_RUN_32271571196_ATTEMPT_1`

`CC_P2_M5_02_A_IMPLEMENTATION: PASS_AT_EE19AD6_RUN_32282614608_ATTEMPT_1`

`CC_P2_M5_02_A_CLOSURE: PASS_AT_470849F_RUN_32284285946`

`CC_P2_M5_02_B_CONTRACT: READY_FOR_TRACKED_CONTRACT_EVIDENCE`

`CC_P2_M5_02_B_MANIFEST: NOT_CREATED`

`CC_P2_M5_02_PRIVATE_INPUT: PROHIBITED_PENDING_CC02_B_TRACKED_CONTRACT_ACCEPTANCE`

`CC_P2_M5_02_C_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`
