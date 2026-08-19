# P2-M5 CC02-B Immutable Diagnostic Manifest Bounded-Task Contract

## Status and authority

- Status: `CONTRACT_ACCEPTED_BUILDER_EXECUTION_READY`.
- Task: `CC-P2-M5-02-B`.
- Change-control authority: ADR-047 and `P2_M5_CC02_FAILURE_MECHANISM_PROTOCOL.md`.
- CC02-A implementation acceptance: implementation commit
  `5159c3f28ab8dcbb7db07c5bead3780a409ace25` plus R04 commit
  `ee19ad6efe49decfa3a0c8f0dbf3f130b5c59460`, run `32282614608`, attempt 1.
- CC02-A acceptance closure: `470849f0f42f151d1ec939e3b0d81ef4369ea86c`, run `32284285946`; all three jobs,
  Browser Integration 5/5 and eight exact-SHA artifacts passed.
- CC02-B contract acceptance: candidate `f69361e8d855fa6262b2d79560c456c8862df2f7`, run `32287419743`, attempt 1;
  all three jobs, Browser Integration 5/5 and eight exact-SHA artifacts passed. The accepted contract content SHA-256 is
  `e82e0b83bd5ded0932dd547d2f46f0d229cf63c430637fedc736548ad9ccdc35`.
- Current milestone: P2-M5 remains `EXECUTING`.
- Current authorization: implement the frozen first-party builder and synthetic/numeric tests only. No private input may
  be read and no real manifest may be created before tracked builder acceptance and the separate Principal pre-read Gate.
- Private-input access: `PROHIBITED_PENDING_CC02_B_BUILDER_PRE_READ_GATE`.

This contract does not reopen the accepted Stage C result. `CC-P2-M5-01-C` remains `FURTHER_RESEARCH`, its complete-case
eligible count remains 0/4, and every old runner output, report and digest remains immutable. Contract acceptance first
authorizes only a versioned first-party builder plus synthetic tests. Private report locations/bytes remain prohibited
until that implementation passes tracked review and Principal records the separate pre-read Gate. Nothing in CC02-B
authorizes CC02-C replay.

## Bounded-task packet

- `BOOTSTRAP_STATUS`: `OK`.
- `TASK_ID`: `CC-P2-M5-02-B`.
- `OBJECTIVE`: after this contract receives tracked acceptance, implement and validate a deterministic first-party
  manifest builder using synthetic inputs only. After Principal separately accepts that builder and records
  `CC02_B_BUILDER_PRE_READ_GATE: PASS`, use it to read only the two CC01C private platform reports whose canonical
  content digests were previously accepted, first-bind the presented byte streams, and create an immutable tracked
  diagnostic manifest plus human preregistration.
- `WHY_DELEGATED`: the future task is a bounded evidence-reconstruction operation with a frozen schema, but exact
  cross-report row membership, canonical digests and privacy redaction require one isolated high-rigor worker. It has no
  authority to choose an algorithm, threshold, candidate, schema, API or product behavior.
- `SCOPE`: first create one versioned first-party builder and targeted synthetic tests without private input. After the
  pre-read Gate, use the accepted builder to create exactly one machine-readable manifest and one matching human
  preregistration from existing accepted evidence. Validate the entire document in memory before the first tracked
  evidence write. Do not transform, measure, replay, generate or alter any source/evidence bytes.
- `ALLOWED_FILES_OR_MODULES`:
  - new `scripts/research/build_p2_m5_cc02_manifest.py`;
  - new `services/api/tests/test_p2_m5_cc02_manifest.py`;
  - new `docs/research/P2_M5_CC02_DIAGNOSTIC_MANIFEST.json`;
  - new `docs/research/P2_M5_CC02_DIAGNOSTIC_PREREGISTRATION.md`;
  - read-only use of ADR-047, the CC02 protocol, this accepted contract, the accepted CC01C candidate manifest and
    redacted aggregate and the CC02-A harness;
  - only after `CC02_B_BUILDER_PRE_READ_GATE: PASS`, read-only use of the two private platform report byte streams whose
    canonical content digests were previously accepted, through the accepted builder. No ephemeral tool may become
    construction or verification authority.
- `EXPECTED_CHANGE`:
  1. add builder version `p2-m5-cc02-manifest-builder-v1` and targeted synthetic tests. Reuse only the applicable CC02-A
     `canonical_digest` and `legacy_row_digest` primitives, and use the non-circular legacy validator frozen below; do
     not create a second CC02 diagnostic-report authority or copy private input into fixtures;
  2. prove deterministic projection, ordering, digest, redaction, create-once/no-partial behavior and zero
     network/subprocess/replay/transform/Vision using synthetic/numeric in-memory reports only;
  3. obtain tracked builder/test acceptance and explicit Principal
     `CC02_B_BUILDER_PRE_READ_GATE: PASS` before private report locations or bytes are released;
  4. create the manifest and preregistration once with the accepted builder, with no edits to earlier evidence or
     implementation;
  5. verify the previously accepted Windows and Linux canonical report digests, then first-bind each presented byte
     stream SHA-256 with the explicit basis `FIRST_BOUND_AFTER_ACCEPTED_CANONICAL_VALIDATION`, together with its platform
     runtime authority;
  6. bind exactly 288 logical cases represented as 576 platform-case records, including the exact opaque case digest,
     frozen candidate/direction/magnitude tuple, legacy outcome and direction-diagnostic membership;
  7. bind all 344 legacy-success platform cases to exactly three accepted repeat rows each, for 1,032 opaque repeat
     bindings, and bind the exact 14 direction-diagnostic platform cases that will require 42 measurements in CC02-C;
  8. bind the frozen candidate/cohort/case/runtime/model/topology/algorithm/harness/taxonomy authorities and complete
     resource envelope without adding a threshold, eligibility result or mechanism conclusion;
  9. compute the canonical manifest content digest and repeat it exactly in the human preregistration;
  10. leave CC02-C–E, Stage D/E, T06–T08, MVR, production geometry, real-user processing, M6 and QuestionBank release
      closed.
- `FORBIDDEN_SCOPE`:
  - reading any private input while this contract itself is only a candidate;
  - reading a source image, result image, raw landmark, Vision log, private runtime binary, model binary or private
    object; only the two JSON report byte streams with previously accepted canonical content digests may be read by the
    later manifest worker;
  - enumerating, recording or committing any private path, output root, source/report filename, object key, signed URL,
    Prompt, Provider payload, credential, raw exception, image or landmark;
  - creating a real manifest, selecting opaque case digests or receiving private report locations/bytes before the
    builder implementation has tracked acceptance and Principal records `CC02_B_BUILDER_PRE_READ_GATE: PASS`;
  - using an untracked/ephemeral builder or verifier as evidence authority, adding private report material to tests, or
    allowing the builder to invoke network, subprocess, replay, transform or Vision;
  - modifying the old runner, old manifests/reports/aggregates, CC02-A harness/tests, transform/domain/similarity logic,
    schema/migration, ORM, public API/OpenAPI, Worker, workflow, dependency/lockfile, model registry or runtime artifact;
  - running CC02-C, transform, Vision, replay, generation, network access, download, retry or concurrent platform work;
  - selecting a target/control/cross-platform/pHash/near-duplicate threshold, changing a formula or candidate family,
    classifying a dimension, altering 0/4 eligibility, entering holdout, or opening any later Gate;
  - real-person or User-linked input, sensitive classification, beauty scoring/ranking or age estimation.
- `DEPENDENCIES`:
  - ADR-047 and the accepted CC02-G protocol;
  - CC02-A implementation accepted at `ee19ad6efe49decfa3a0c8f0dbf3f130b5c59460`, run `32282614608`, attempt 1,
    and closure at `470849f0f42f151d1ec939e3b0d81ef4369ea86c`, run `32284285946`;
  - existing CC02-A `canonical_digest` and `legacy_row_digest` primitives, reused without change by
    `p2-m5-cc02-manifest-builder-v1`; CC02-A `validate_report_pair` and `validate_legacy_report_bytes` validate future
    CC02 diagnostic reports against an already-created manifest and therefore are explicitly not CC02-B input
    validators;
  - tracked builder/test implementation acceptance and explicit Principal
    `CC02_B_BUILDER_PRE_READ_GATE: PASS` before any private report location/byte access;
  - immutable CC01C candidate manifest content digest
    `eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4`;
  - Stage B redacted evidence SHA-256
    `a71206d99a08a1372694175ec537282bae1f662b6a77ac35dfe097ae8e8e3908`;
  - calibration cohort digest `618b993f81f282367719173119ff109fbbb8131d26cb41f5c803805a92c52358`;
  - case-set digest `79cbaf4ad14f8b0ee3aa2fb2360e507740c2bf0737242356b601df5f23f7093f`;
  - redacted aggregate SHA-256 `272e473b16b8af346a3e8b516aef1de13f2359583694e6db0bff79b1b472e3bb`;
  - accepted Windows canonical report digest
    `0eac3ef8f7fa10fc4c1b13c685e5d7534716fe011dce702402266987fc947861` and Linux canonical report digest
    `916ff02cf47d9677b62b57f66aff68364e7aa15f53018941545621d15e453884`;
  - Windows runtime manifest digest `27b33d646d8587f76d5ca317ac9d6aec95bc04fd87d413bb3dd6394f9694bb7a`
    and Linux runtime manifest digest `5d0e9ee323d7daea78e8baaeec63917c7a1867301ec5f7c71685fa9cbed311d8`;
  - Vision model SHA-256 `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`,
    topology SHA-256 `85eea84eef15dd963e06382d6e61f7357029d9901acc935731ecaa7eab856b63`, and
    algorithm `opencv-piecewise-affine-v1`.
- `INPUTS_AND_ASSUMPTIONS`:
  - builder implementation and tests receive no private location or bytes; tests construct only synthetic/numeric
    in-memory CC01C report doubles with opaque placeholder digests;
  - private report locations are supplied out of band only after the pre-read Gate and are never written to Git, stdout,
    logs, shell evidence or the manifest;
  - the future worker reads the Windows and Linux reports through a capped held file descriptor, verifies each canonical
    internal report digest against the accepted value, then computes the first tracked byte SHA-256 binding; no
    pre-CC02-B byte-level acceptance is claimed, and no filename, directory or caller-supplied count is trusted;
  - case and repeat membership is derived only from the validated report collections and the frozen CC01C authorities,
    never from the redacted aggregate alone;
  - no accepted legacy result bytes exist for the 14 direction-mismatch platform cases; their manifest binding contains
    no fabricated result SHA or drift claim;
  - Windows child-process-inclusive outbound deny is a CC02-C pre-read Gate. CC02-B performs no replay and must not
    claim that network containment has been established.

## Frozen first-party builder contract

- Builder path: `scripts/research/build_p2_m5_cc02_manifest.py`.
- Test path: `services/api/tests/test_p2_m5_cc02_manifest.py`.
- Builder version: `p2-m5-cc02-manifest-builder-v1`.
- The builder imports and reuses only the applicable CC02-A `canonical_digest` and `legacy_row_digest` primitives.
  Existing CC02-A `validate_report_pair` and `validate_legacy_report_bytes` are intentionally not called because both
  require the future diagnostic manifest/case authority and would make CC02-B construction circular.
- The builder adds the contract-frozen, non-circular `validate_cc01c_report_pair_for_manifest` input validator, the
  manifest projection and the create-once writer. That validator is not a second CC02 diagnostic-report authority: it
  admits only the legacy CC01C v2 report shape below, proves its previously accepted canonical content digest, and emits
  only the safe projection required to create the first CC02-B authority.
- A pure deterministic construction function accepts two bounded report byte strings plus the frozen public authority
  document and returns the complete manifest/preregistration bytes. It does not accept or return a path, image,
  landmark, Prompt, object key, Provider payload, credential, raw exception or source/result artifact bytes.
- The CLI adapter obtains the two private report locations only from the fixed environment variable names
  `CC02_WINDOWS_LEGACY_REPORT_PATH` and `CC02_LINUX_LEGACY_REPORT_PATH` after the pre-read Gate. It never prints,
  serializes or includes their values in an exception. It writes only the two fixed tracked output paths.
- Builder errors expose only an allowlisted stop outcome and safe aggregate/digest context. Raw JSON rows, parser
  exceptions, tracebacks and filesystem details are not evidence and must not enter stdout/stderr or tracked output.
- The builder uses only the Python standard library and existing repository code. It imports no network client and
  invokes no subprocess, transform, Vision, replay, generation or download. It performs zero retry and uses no
  concurrency.
- Each report input is limited to `67108864` bytes (64 MiB) and JSON nesting depth `16`; the 4 GiB CC02-C private-output
  ceiling is not a safe parser-input limit and must not be reused as one. The CLI must reject an empty, oversized,
  non-regular, symlink/reparse-point or changing file before projection.
- The CLI performs `lstat`/reparse-point rejection, opens once with no-follow semantics where supported, verifies the
  held descriptor with `fstat`, reads it in bounded chunks, rejects an extra byte, and verifies stable device/inode,
  size and modification facts after the read. It pre-scans UTF-8 JSON nesting while honoring quoted strings/escapes,
  rejects BOM, duplicate object keys and non-standard numeric constants, and converts every parser/resource failure to
  an allowlisted stop outcome without printing a path, parser exception or row.
- Both output documents are built and fully validated in memory before either write.
- Output creation is exclusive/create-once. If either fixed target exists, any validation fails, or either exclusive
  create cannot complete, the task leaves no newly created partial output. It never overwrites or repairs a file.
- Targeted tests generate the full 288-logical/576-platform, 232-failure/344-success, 1,032-repeat and
  14-direction/42-measurement authority shape entirely in memory. They prove deterministic bytes across repeat runs and
  input key ordering; exact sort/count/cross-platform/row projection; canonical digest; report/schema/digest mismatch;
  duplicate, missing and ambiguous row rejection; private-field and raw-exception redaction; no-partial/create-once
  failure; and zero network/subprocess/replay/transform/Vision.
- CI executes only those synthetic builder tests. It never receives a private location/report and never constructs the
  real manifest.

### Non-circular legacy CC01C input authority

Before projecting any safe binding, `validate_cc01c_report_pair_for_manifest` must prove the following exact legacy
shape and authority directly from each held byte stream:

- top-level keys are exactly `schema`, `platform`, `runtime_manifest_digest`, `candidate_manifest_digest`,
  `model_sha256`, `topology_sha256`, `triangle_count`, `stage_b_evidence_sha256`, `cohort_digest`,
  `input_manifest_digest`, `case_set_digest`, `cases`, `rows` and `report_digest`;
- `schema` is exactly `mirror.p2-m5/CC01C-private-platform-report/v2`; `platform` is one of the two frozen platforms;
  `report_digest` recomputes with the unchanged CC02-A `canonical_digest` primitive and equals that platform's accepted
  canonical digest; candidate/cohort/case/runtime/model/topology/stage-B authority equals the frozen values; and
  `triangle_count=852`;
- a success case has exactly `case_digest`, `identity_reference`, `candidate`, `direction`, `magnitude_ppm`, `status` and
  `executed_repeat_count`; a failed case has those exact keys plus `failure_stage` and `failure_code`;
- each row has exactly `case_digest`, `identity_reference`, `candidate`, `direction`, `magnitude_ppm`, `repeat`, `status`,
  `source_sha256`, `result_sha256`, `result_artifact`, `plan_digest`, `source_measurements`, `result_measurements`,
  `vision_log_sha256`, `vision_log_artifact`, `phash_hex` and `changed_pixel_count`;
- case status is exactly `PASSED_PENDING_MANUAL_ARTIFACT_REVIEW` or `FAILED`; row status is exactly `PASSED`; success
  cases have repeats `{1,2,3}` and failed cases have the exact executed prefix allowed by their accepted case record;
- all candidate/direction/magnitude/digest/repeat types and values match the frozen sets; each platform has 288 unique
  cases; the two case-digest/descriptor/outcome sets are identical; all accepted rows resolve uniquely; and the derived
  pair totals are exactly 232 failed platform cases, 344 successful platform cases and 1,032 successful repeat rows;
- rows already emitted before a later failed case remain validated private input under that case's exact executed-repeat
  prefix, but they never enter `legacy_success_repeat_bindings`; only the three rows of each complete legacy-success case
  are projected;
- a direction binding is derived only from an accepted failed case whose exact legacy pair is
  `failure_stage=MEASUREMENT` and `failure_code=TARGET_DIRECTION_MISMATCH`; the pair total is exactly 14;
- private `identity_reference`, artifact filenames and measurement dictionaries may exist only inside the admitted
  legacy report in memory. They are used only to prove exact row/case membership and are never copied into a safe
  projection, digest context, log, exception or tracked output.

The accepted canonical report digests, not a previously nonexistent byte hash, are the trust anchors for this input
validation. Only after all rules above pass does the builder compute `legacy_report_sha256` over the held bytes and mark
its basis `FIRST_BOUND_AFTER_ACCEPTED_CANONICAL_VALIDATION`. That new byte binding becomes mandatory authority for later
CC02-C; it must never be described as a byte hash accepted before CC02-B.

Tracked acceptance of builder/tests is mandatory but insufficient for private access. Principal must inspect their
exact diff and targeted/full same-SHA evidence, complete independent security/research-integrity review, and then record
the exact marker `CC02_B_BUILDER_PRE_READ_GATE: PASS_AT_<COMMIT>_RUN_<RUN>_ATTEMPT_<N>`. Until that marker exists, the
environment variables above must be absent and private input remains prohibited.

## Frozen tracked manifest contract

### Filenames, schema and exact top-level keys

The future machine-readable authority is exactly `docs/research/P2_M5_CC02_DIAGNOSTIC_MANIFEST.json`. Its
`schema_version` is exactly `mirror.p2-m5/CC02DiagnosticManifest/v1`; its `status` is exactly
`PREREGISTERED_NOT_EXECUTED`. It has exactly these top-level keys:

```text
schema_version
status
change_control
task_id
authority
platform_report_bindings
platform_case_bindings
legacy_success_repeat_bindings
direction_diagnostic_bindings
resource_envelope
boundaries
stop_rules
manifest_content_digest
```

`change_control` is `CC-P2-M5-02`; `task_id` is `CC-P2-M5-02-B`. Additional or missing keys fail closed.

The matching human authority is exactly `docs/research/P2_M5_CC02_DIAGNOSTIC_PREREGISTRATION.md`. It states the two
filenames/schema/status, the complete count/resource summary, all closed Gates and the exact lowercase
`manifest_content_digest`. It contains no information that is absent from the safe manifest except explanatory text.

### `authority`

`authority` has exactly these keys and values:

- `accepted_stage_c_commit`: `042f77e4b6708be827f2033a9740e348ae778f69`;
- `accepted_stage_c_run`: integer `32237678569`;
- `accepted_stage_c_attempt`: integer `2`;
- `candidate_manifest_digest`: `eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4`;
- `stage_b_redacted_evidence_sha256`:
  `a71206d99a08a1372694175ec537282bae1f662b6a77ac35dfe097ae8e8e3908`;
- `cohort_digest`: `618b993f81f282367719173119ff109fbbb8131d26cb41f5c803805a92c52358`;
- `case_set_digest`: `79cbaf4ad14f8b0ee3aa2fb2360e507740c2bf0737242356b601df5f23f7093f`;
- `redacted_aggregate_sha256`: `272e473b16b8af346a3e8b516aef1de13f2359583694e6db0bff79b1b472e3bb`;
- `builder_version`: `p2-m5-cc02-manifest-builder-v1`;
- `harness_version`: `p2-m5-cc02-diagnostic-harness-v1`;
- `taxonomy_version`: `p2-m5-cc02-terminal-taxonomy-v1`;
- `private_report_schema`: `mirror.p2-m5/CC02-private-platform-diagnostic-report/v1`;
- `legacy_report_schema`: `mirror.p2-m5/CC01C-private-platform-report/v2`;
- `vision_model_sha256`: `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`;
- `topology_sha256`: `85eea84eef15dd963e06382d6e61f7357029d9901acc935731ecaa7eab856b63`;
- `algorithm_version`: `opencv-piecewise-affine-v1`;
- `platforms`: exactly `linux_x86_64_network_none`, `windows_x86_64` in lexical order;
- `candidates`: exactly `cheekbone_width`, `chin_height`, `eye_spacing`, `jaw_width`, `mouth_width`, `nose_width` in
  lexical order;
- `directions`: exactly `DECREASE`, `INCREASE` in lexical order;
- `magnitudes_ppm`: exactly integers `15000`, `30000` in ascending order;
- `terminal_stages`: exactly `SOURCE_ADMISSION`, `SPECIFICATION`, `CONTROL_POINT_BUILD`, `WARP_PLAN_AUTHORITY`,
  `TRANSFORM`, `RESULT_VISION_QA`, `MEASUREMENT_DIRECTION`, `RESULT_SIGNATURE` in execution order.

All digest fields are lowercase 64-hex strings. Run/attempt/count/magnitude fields are non-boolean integers.

### `platform_report_bindings`

This array contains exactly two objects, sorted by `platform`. Every object has exactly:

```text
platform
legacy_report_sha256
legacy_report_sha256_basis
legacy_report_digest
runtime_manifest_digest
```

- `legacy_report_sha256` is SHA-256 over the exact presented byte stream and is derived only after the accepted
  canonical content digest and complete legacy authority validate.
- `legacy_report_sha256_basis` is exactly `FIRST_BOUND_AFTER_ACCEPTED_CANONICAL_VALIDATION`; it records that CC02-B
  establishes the first byte-level binding and does not rewrite history as though that byte SHA was accepted earlier.
- `legacy_report_digest` is the report's validated canonical internal digest and must equal the accepted Windows/Linux
  digest listed in `DEPENDENCIES`.
- `runtime_manifest_digest` must equal the accepted platform-specific runtime digest listed in `DEPENDENCIES`.
- The report's own platform, candidate-manifest, cohort, case-set, model, topology and runtime authority must match before
  any case binding is admitted. Algorithm authority is inherited only from the immutable accepted candidate manifest
  bound by `candidate_manifest_digest`; the legacy report has no standalone algorithm field.

If either report is unavailable, unbounded, not valid JSON, changes during the held-descriptor read, has a canonical
content digest mismatch, uses a different schema/authority or cannot resolve its complete row authority, stop as
`FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE`. Do not create either tracked output.

### `platform_case_bindings`

This array contains exactly 576 objects sorted by `(platform, case_digest)`. Every object has exactly:

```text
platform
case_digest
candidate
direction
magnitude_ppm
legacy_outcome
direction_diagnostic
```

- `case_digest` is an opaque lowercase 64-hex digest. It is never replaced by an identity, path or source reference.
- `candidate`, `direction`, `magnitude_ppm` and `platform` belong to the frozen sets above.
- `legacy_outcome` is exactly `TERMINAL_FAILURE` or `LEGACY_SUCCESS`.
- `direction_diagnostic` is a strict boolean. It may be true only for a `TERMINAL_FAILURE` that is proven from the
  accepted report to be a legacy direction mismatch.
- Exactly 288 unique `case_digest` values exist. Each appears exactly once on each platform with the same
  candidate/direction/magnitude tuple.
- Exactly 232 platform bindings are `TERMINAL_FAILURE`; exactly 344 are `LEGACY_SUCCESS`; exactly 14 are
  `direction_diagnostic=true`.
- Exactly 172 unique case digests are `LEGACY_SUCCESS` on both platforms and the remaining 116 are
  `TERMINAL_FAILURE` on both platforms. A cross-platform outcome mismatch fails closed.
- Supplied totals are not authority; all totals are derived from this collection.

### `legacy_success_repeat_bindings`

This array contains exactly 1,032 objects sorted by `(platform, case_digest, repeat_index)`. Every object has exactly:

```text
platform
case_digest
repeat_index
legacy_row_digest
source_sha256
accepted_result_sha256
plan_digest
```

- Each record resolves to exactly one complete row in the validated presented report bytes. `legacy_row_digest` is lowercase
  SHA-256 over `mirror.p2-m5/CC01C-private-platform-report/v2#row\n` plus that complete row's canonical JSON using
  `allow_nan=False`, `ensure_ascii=True`, `separators=(",", ":")`, `sort_keys=True` and UTF-8.
- `source_sha256`, `accepted_result_sha256` and `plan_digest` are lowercase 64-hex opaque bindings taken from that exact
  validated row. They do not authorize reading or committing the referenced bytes.
- Every binding refers to one `LEGACY_SUCCESS` platform case. Each of the 344 success platform cases has exactly repeat
  indices `{1,2,3}`; no terminal-failure case appears here.
- The containing report platform and each row's case/candidate/direction/magnitude, repeat, source/result/plan authority
  must match the corresponding case and report/manifest authority. Zero or multiple row matches, missing fields or any
  projection mismatch stop without tracked output.

### `direction_diagnostic_bindings`

This array contains exactly 14 objects sorted by `(platform, case_digest)`. Every object has exactly:

```text
platform
case_digest
measurement_count
```

- Each entry refers to one and only one `platform_case_bindings` entry with `legacy_outcome=TERMINAL_FAILURE` and
  `direction_diagnostic=true`.
- `measurement_count` is the non-boolean integer `3`. The total is therefore exactly 42 future measurements.
- No result SHA, signed delta, mechanism label or synthetic legacy-success comparison appears in this collection. Those
  values do not exist before CC02-C replay.

### `resource_envelope`

This object has exactly the following keys and values:

```text
identity_count = 12
candidate_count = 6
logical_case_count = 288
platform_case_count = 576
legacy_terminal_failure_platform_case_count = 232
legacy_success_platform_case_count = 344
legacy_success_repeat_binding_count = 1032
direction_diagnostic_platform_case_count = 14
direction_measurement_count = 42
maximum_transform_executions = 576
maximum_vision_executions = 604
generation_attempt_count = 0
retry_count = 0
download_count = 0
maximum_concurrency = 1
execution_mode = WINDOWS_AND_LINUX_SERIAL
maximum_wall_clock_seconds_per_platform = 7200
maximum_wall_clock_seconds_total = 14400
maximum_private_output_bytes_per_platform = 4294967296
maximum_legacy_report_bytes_per_platform = 67108864
maximum_legacy_report_json_depth = 16
```

Every numeric field is a non-boolean integer. The two legacy-report limits govern CC02-B construction; the remaining
execution values are future CC02-C ceilings, not claims that replay happened.

### `boundaries` and `stop_rules`

`boundaries` has exactly these strict boolean keys:

```text
synthetic_only = true
private_reports_remain_untracked = true
source_and_result_assets_remain_untracked = true
real_user_processing = false
production_geometry = false
public_api_change = false
schema_or_migration_change = false
dependency_or_model_change = false
network_during_manifest_construction = false
replay_during_manifest_construction = false
generation = false
question_bank_release = false
```

`stop_rules` is exactly this ordered enum list:

```text
FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE
DIGEST_MISMATCH
SCHEMA_OR_AUTHORITY_MISMATCH
CASE_MEMBERSHIP_NOT_EXACT
LEGACY_ROW_AUTHORITY_NOT_EXACT
PRIVATE_FIELD_REDACTION_FAILED
RESOURCE_ENVELOPE_MISMATCH
CANONICAL_DIGEST_MISMATCH
```

Any stop rule prevents both tracked outputs. The worker must not weaken a rule, emit a partial manifest or infer missing
authority from the redacted aggregate.

### Canonical digest and create-once rules

- Build and validate the complete manifest in memory before writing either tracked file.
- Compute `manifest_content_digest` with the accepted CC02-A `canonical_digest` semantics: omit only
  `manifest_content_digest`; serialize the remaining document with `allow_nan=False`, `ensure_ascii=True`,
  `separators=(",", ":")`, `sort_keys=True`; prefix the canonical JSON with the exact `schema_version` plus `\n`;
  encode UTF-8; emit lowercase SHA-256.
- Recompute the digest after parsing the final JSON bytes. It must match both the JSON field and the human
  preregistration.
- Both target paths must be absent before the task. Creation is exclusive/create-once; an existing file, partial prior
  output or write collision hard-stops. Do not overwrite, merge, append or repair in place.
- The two files must enter the same tracked candidate. Once accepted, neither may be modified or deleted. A correction
  requires a new forward schema/version, new filenames and Principal change control.
- The accepted `manifest_content_digest` becomes the exact `diagnostic_manifest_digest` required by every CC02-C
  private platform report.

## Acceptance, validation and handoff

- `ACCEPTANCE_CRITERIA`:
  1. the contract candidate changes only authorized governance files and remains
     `READY_FOR_TRACKED_CONTRACT_EVIDENCE`;
  2. after contract acceptance, the versioned first-party builder and targeted tests are implemented with no private
     input, no new dependency and no second canonical/report authority;
  3. targeted tests prove deterministic full-cardinality projection, exact authority validation, canonical digest,
     redaction, create-once/no-partial behavior and zero network/subprocess/replay/transform/Vision;
  4. Principal accepts exact-SHA builder/test evidence and records `CC02_B_BUILDER_PRE_READ_GATE: PASS` before any
     private report location/byte access;
  5. after that Gate, the accepted builder proves both previously accepted canonical report digests and all frozen
     authorities, then first-binds the two presented byte streams before creating output;
  6. the final manifest has exact key sets, enums, types, ordering and lowercase digest shapes, with no missing or
     additional field;
  7. collections derive exactly 288 logical/576 platform cases, 232 failures, 344 successes, 1,032 success-repeat
     bindings, 14 direction platform cases and 42 future measurements; the 344 successes are exactly 172 logical cases
     represented once on each platform, and the 232 failures are the remaining 116 logical cases on both platforms;
  8. every success repeat resolves to exactly one complete accepted legacy row and every direction binding resolves to
     exactly one accepted legacy mismatch case;
  9. the manifest binds both first-bound report byte SHA values and their explicit basis, both previously accepted
     report content digests, both runtime digests, and shared candidate/cohort/case/model/topology/algorithm/builder/
     harness/taxonomy authority;
  10. canonical digest recomputation is stable and the human preregistration repeats the exact digest/counts/boundaries;
  11. a missing report, digest/schema/authority mismatch, ambiguous row, wrong count, duplicate/missing case, private
      field, pre-existing output or inability to reconstruct evidence produces no tracked output and the exact stop
      outcome `FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE` where applicable;
  12. committed output contains only allowlisted enums, versions, booleans, bounded counts and opaque digests. Apart
      from the two fixed tracked output filenames required above, it contains no private/source/report path or filename,
      image, landmark, Prompt, object key, URL, Provider payload, credential, raw exception, threshold, target delta,
      mechanism result, eligibility or READY classification;
  13. no source/result bytes, transform, Vision, network, subprocess, download, generation, retry or CC02-C operation
      occurs;
  14. old CC01C evidence, CC02-A implementation, schema/API, dependencies/models and acceptance thresholds have zero
      diff;
  15. tracked manifest acceptance may open only a separate CC02-C bounded-task contract. It never opens replay directly
      and does not change P2-M5 or MVR status.
- `VALIDATION_COMMANDS`:
  - contract candidate only: `pnpm.cmd format:check`;
  - contract candidate only: `git diff --check`;
  - contract candidate only: bounded field/status/reproducibility scan proving no private-input, threshold,
    schema/API/dependency or later-Gate authorization drift and proving the four future paths are absent;
  - future builder candidate: `python -m ruff format --check
scripts/research/build_p2_m5_cc02_manifest.py services/api/tests/test_p2_m5_cc02_manifest.py`;
  - future builder candidate: `python -m ruff check scripts/research/build_p2_m5_cc02_manifest.py
services/api/tests/test_p2_m5_cc02_manifest.py`;
  - future builder candidate: strict mypy for `scripts/research/build_p2_m5_cc02_manifest.py` with
    `MYPYPATH=services/api/src` or the Windows equivalent;
  - future builder candidate: `python -m pytest services/api/tests/test_p2_m5_cc02_manifest.py -q` using only
    synthetic/numeric in-memory doubles, followed by bounded source scans for network/subprocess/private-field/replay/
    transform/Vision access;
  - future builder candidate: complete local Gates, same-SHA three-job Actions, artifact inspection and independent
    security/research-integrity/final review before Principal may record the pre-read Gate;
  - future manifest task after the pre-read Gate: run only the accepted first-party builder. It must parse both exact
    report byte streams without printing their locations or rows; recompute byte/content/row/manifest digests; validate
    all exact key sets, authority projections, counts, sort order and cross-platform membership; and print only PASS/FAIL
    plus allowlisted aggregate counts/digests;
  - future manifest candidate: `pnpm.cmd format:check`, `git diff --check`, exact four-path cumulative allowlist diff,
    private-field negative scan, dependency/model/schema/API drift scan, then same-SHA three-job Actions and artifact
    inspection;
  - no product, Browser, transform or Vision test is required for this contract-only candidate. Existing CI remains the
    later tracked evidence and must not be weakened.
- `SECURITY_NOTES`: builder/tests must receive tracked acceptance and the Principal pre-read Gate before out-of-band
  private locations are released. Those locations are capability data and never tracked. Report bytes are untrusted
  bounded input: the accepted builder parses them in a zero-network/no-subprocess process, validates exact schema/digests
  before projecting safe fields, and never serializes an exception, row payload or non-allowlisted key. Manifest
  creation grants no access to source/result assets. CC02-C still requires independently verified Windows
  runner-and-child outbound deny before its first replay input read and Linux `--network none`.
- `PRIVACY_NOTES`: all input remains synthetic-only and private. Opaque digest does not make the underlying asset public.
  No User relation, real-person input, image, landmark, Prompt, path, object/storage reference or Provider payload may
  enter Git, logs, artifacts or human preregistration.
- `DATA_NOTES`: CC02-B records only existing evidence authority. It creates no report, result asset, transform, Vision
  measurement, mechanism aggregate, threshold or eligibility evidence. The accepted CC01C canonical report content and
  0/4 outcome remain unchanged; CC02-B adds only the first explicit byte-stream binding after validation.
- `LICENSE_NOTES`: no dependency, runtime, model or data artifact is added, downloaded, redistributed or requalified.
  Existing OpenCV/Vision artifacts retain their private research-only scope and are not executed in CC02-B.
- `ROLLBACK`: before tracked acceptance, revert only this forward contract candidate. Before the pre-read Gate, reject or
  revert only the builder/test candidate; no private input or manifest exists. After a manifest candidate exists, reject
  the whole candidate rather than editing accepted prior evidence. After manifest acceptance, corrections require a new
  forward version; never delete or rewrite CC01C/CC02 evidence.
- `RECOMMENDED_AGENT`: `pm_terra_high_worker`, with exclusive ownership of the four future paths after this contract is
  accepted. Principal owns builder acceptance, private input release, diff inspection, commit/push, same-SHA acceptance
  and Gate decisions.
- `RECOMMENDED_MODEL_TIER`: Terra High. Architecture and schema are frozen, while exact private evidence reconstruction,
  row projection, canonical digesting and fail-closed redaction require deep cross-authority validation.
- `ESCALATION_CONDITION`: stop before writing if an exact report is unavailable, a digest/schema/row authority cannot be
  reconstructed, a private field is required, an accepted count conflicts, or completion would require changing an
  algorithm, schema, API, threshold, dependency/model, resource/network rule or later Gate. Return
  `FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE` or the exact conflict to Principal; do not guess or emit a partial
  manifest.
- `OUTPUT_FORMAT`: `STATUS: PASS|BLOCKED|FAILED; SUMMARY; CHANGED_FILES; VALIDATION_RUN; VALIDATION_RESULT;
BUILDER_VERSION; PRE_READ_GATE; MANIFEST_SCHEMA_AND_DIGEST; DERIVED_COUNTS; AUTHORITY_MATCHES;
SECURITY_PRIVACY_BOUNDARY; STOP_OUTCOME; RISKS_OR_OPEN_QUESTIONS; MEMORY_CANDIDATES; ESCALATION_REASON`.

## Execution and acceptance order

```text
this tracked contract candidate
→ same-SHA CI and artifact inspection
→ independent security/research-integrity and final review
→ Principal CC02-B contract acceptance
→ one bounded worker implements first-party builder + synthetic tests with no private input
→ Principal diff review, targeted/full validation and builder candidate commit
→ same-SHA CI, artifacts and independent security/research-integrity/final review
→ Principal records CC02_B_BUILDER_PRE_READ_GATE: PASS
→ only now release out-of-band exact report locations to the accepted builder
→ deterministic in-memory authority/reconstruction/redaction validation
→ create-once manifest + preregistration candidate
→ Principal diff and canonical-digest review
→ same-SHA CI and artifact inspection
→ independent security/research-integrity and final review
→ Principal CC02-B manifest acceptance
→ separate CC02-C bounded-task contract
```

`CC_P2_M5_02_B_CONTRACT: PASS_AT_F69361E_RUN_32287419743_ATTEMPT_1`

`CC_P2_M5_02_B_BUILDER: EXECUTION_READY`

`CC02_B_BUILDER_PRE_READ_GATE: CLOSED_PENDING_TRACKED_BUILDER_ACCEPTANCE`

`CC_P2_M5_02_B_MANIFEST: NOT_CREATED`

`CC_P2_M5_02_PRIVATE_INPUT: PROHIBITED_PENDING_CC02_B_BUILDER_PRE_READ_GATE`

`CC_P2_M5_02_C_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`
