# P2-M5 CC02 Failure-Mechanism Isolation Protocol

## Authority and current state

- Change control: `CC-P2-M5-02` / ADR-047.
- Baseline: `aa695c2f81ca8ec0762fb521d77dd705c8fdeee5`.
- Accepted Stage C evidence: `042f77e4b6708be827f2033a9740e348ae778f69` / run `32237678569`, attempt 2.
- Governance acceptance: `137157c41e7b1436ae47fe7dfcf34a7127789166` / run `32267510703`, attempt 1.
- CC02-A implementation acceptance: `ee19ad6efe49decfa3a0c8f0dbf3f130b5c59460` / run `32282614608`, attempt 1.
- CC02-A acceptance closure: `470849f0f42f151d1ec939e3b0d81ef4369ea86c` / run `32284285946`.
- CC02-B contract acceptance: `f69361e8d855fa6262b2d79560c456c8862df2f7` / run `32287419743`, attempt 1.
- Current status: `CC02_B_CONTRACT_ACCEPTED_BUILDER_EXECUTION_READY`.
- Execution authorization: `CC02_B_BUILDER_SYNTHETIC_IMPLEMENTATION_ONLY`; private-input access remains closed.
- Threshold selection: `FORBIDDEN`.
- Stage D/E, T06–T08, MVR and M6: `CLOSED`.

This protocol diagnoses why the immutable Stage C candidate family failed complete-case admission. It does not rerun the
old Gate, change an algorithm, select a threshold, promote a dimension or authorize a holdout.

## Immutable input authority

| Evidence                  | Exact authority                                                                    |
| ------------------------- | ---------------------------------------------------------------------------------- |
| CC01C manifest            | content digest `eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4`  |
| Stage B redacted evidence | SHA-256 `a71206d99a08a1372694175ec537282bae1f662b6a77ac35dfe097ae8e8e3908`         |
| calibration cohort        | digest `618b993f81f282367719173119ff109fbbb8131d26cb41f5c803805a92c52358`          |
| case set                  | digest `79cbaf4ad14f8b0ee3aa2fb2360e507740c2bf0737242356b601df5f23f7093f`          |
| redacted aggregate        | SHA-256 `272e473b16b8af346a3e8b516aef1de13f2359583694e6db0bff79b1b472e3bb`         |
| qualified Windows report  | digest `0eac3ef8f7fa10fc4c1b13c685e5d7534716fe011dce702402266987fc947861`          |
| qualified Linux report    | digest `916ff02cf47d9677b62b57f66aff68364e7aa15f53018941545621d15e453884`          |
| Vision model              | SHA-256 `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`         |
| topology                  | SHA-256 `85eea84eef15dd963e06382d6e61f7357029d9901acc935731ecaa7eab856b63`         |
| transform algorithm       | `opencv-piecewise-affine-v1`                                                       |
| Windows runtime           | manifest digest `27b33d646d8587f76d5ca317ac9d6aec95bc04fd87d413bb3dd6394f9694bb7a` |
| Linux runtime             | manifest digest `5d0e9ee323d7daea78e8baaeec63917c7a1867301ec5f7c71685fa9cbed311d8` |

The future CC02-B manifest must first validate each previously accepted canonical private-report digest, then establish
the first explicit SHA-256 binding for the presented byte stream and bind opaque legacy case digests before the harness
reads source assets or Vision logs. It must not claim that a byte SHA was accepted before CC02-B. A canonical digest
mismatch, unstable read or unavailable report stops the change control.

## Frozen diagnostic question

For every legacy terminal case, determine the first safe terminal stage and losslessly preserve the underlying domain
reason without changing any computation:

```text
SOURCE_ADMISSION
→ SPECIFICATION
→ CONTROL_POINT_BUILD
→ WARP_PLAN_AUTHORITY
→ TRANSFORM
→ RESULT_VISION_QA
→ MEASUREMENT_DIRECTION
→ RESULT_SIGNATURE
```

Every diagnostic row contains only:

- opaque case digest, candidate, direction and magnitude;
- platform and repeat index where applicable;
- allowlisted terminal stage;
- allowlisted diagnostic reason;
- nullable safe source reason family and existing `DomainValidationError.reason_code` or
  `SimilarityValidationError.reason_code`;
- source/result/runtime/model/topology/plan/version digests;
- signed target delta only for executable direction-diagnostic cases.

### Exhaustive terminal taxonomy

Taxonomy version: `p2-m5-cc02-terminal-taxonomy-v1`.

The following table is exhaustive. A safe typed exception retains its listed source reason code; a generic
`ValueError`/`RuntimeError` is converted at the exact call boundary to the listed generic diagnostic reason. No raw
exception string is retained.

| Terminal stage          | Permitted generic/legacy diagnostic reasons                                                                                | Permitted safe typed source reason codes                                                                                                                                                                                                                   |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SOURCE_ADMISSION`      | `SOURCE_CHECKSUM_MISMATCH`, `SOURCE_LANDMARK_EVIDENCE_MISMATCH`, `SOURCE_ADMISSION_REJECTED`                               | `CHECKSUM_MISMATCH`, `SYNTHETIC_ORIGIN_REQUIRED`, `TRANSFORM_OUTPUT_INVALID`, `OUT_OF_BOUNDS_DISPLACEMENT`, `INVALID_WARP_PLAN`                                                                                                                            |
| `SPECIFICATION`         | `SPECIFICATION_VALUE_REJECTED`                                                                                             | `UNKNOWN_GEOMETRY_DIMENSION`, `UNSUPPORTED_DIMENSION`, `REQUIRES_3D_RESEARCH`, `STYLE_ONLY_DIMENSION`, `INVALID_VARIANT_SPECIFICATION`, `INVALID_DETERMINISM_CLAIM`, `INVALID_RELATIVE_MAGNITUDE`, `CONTROL_DIMENSION_REQUIRED`, `TARGET_CONTROL_CONFLICT` |
| `CONTROL_POINT_BUILD`   | `CONTROL_POINT_VALUE_REJECTED`                                                                                             | `INVALID_WARP_PLAN`, `OUT_OF_BOUNDS_DISPLACEMENT`, `INSUFFICIENT_LANDMARK_CONFIDENCE`                                                                                                                                                                      |
| `WARP_PLAN_AUTHORITY`   | `WARP_PLAN_VALUE_REJECTED`                                                                                                 | `INVALID_WARP_PLAN`, `OUT_OF_BOUNDS_DISPLACEMENT`, `INSUFFICIENT_LANDMARK_CONFIDENCE`                                                                                                                                                                      |
| `TRANSFORM`             | `TRANSFORM_RUNTIME_REJECTED`, `SAME_PLATFORM_NONDETERMINISM`, `SOURCE_RESULT_IDENTICAL`                                    | `INVALID_WARP_PLAN`, `SYNTHETIC_ORIGIN_REQUIRED`, `CHECKSUM_MISMATCH`, `OUT_OF_BOUNDS_DISPLACEMENT`, `INSUFFICIENT_LANDMARK_CONFIDENCE`, `FOLDOVER_REJECTED`, `TRANSFORM_RUNTIME_MISMATCH`, `TRANSFORM_OUTPUT_INVALID`, `SOURCE_RESULT_IDENTICAL`          |
| `RESULT_VISION_QA`      | `RESULT_QA_FAILED`, `RESULT_VISION_QA_REJECTED`                                                                            | none                                                                                                                                                                                                                                                       |
| `MEASUREMENT_DIRECTION` | `MEASUREMENT_VALUE_REJECTED`, `TARGET_DIRECTION_MISMATCH`, `TARGET_DIRECTION_STABLE_MISMATCH`, `MEASUREMENT_SIGN_UNSTABLE` | none                                                                                                                                                                                                                                                       |
| `RESULT_SIGNATURE`      | `RESULT_SIGNATURE_VALUE_REJECTED`                                                                                          | `INVALID_CANONICAL_IMAGE`, `CHECKSUM_MISMATCH`, `INVALID_DIMENSIONS`, `INVALID_SIGNATURE`, `ALGORITHM_VERSION_MISMATCH`                                                                                                                                    |

`DomainValidationError` is accepted only at the stage/code pairs listed above.
`SimilarityValidationError` is accepted only at `RESULT_SIGNATURE` with the five listed similarity codes. Any other
stage, reason, exception class or stage/code pair becomes `UNCLASSIFIED_TERMINAL_FAILURE`, hard-stops the platform run
and makes the diagnostic incomplete. Changing this taxonomy requires a new forward governance version before reading
new diagnostic output.

## Direction-sign diagnostic

The exact 14 legacy direction-mismatch platform cases are selected only by opaque case digests committed in CC02-B.
The old runner performed its direction check before writing a result artifact, so these 14 cases have no accepted legacy
result SHA or bytes. During CC02-C, each case is recomputed once from the frozen input/runtime/plan authority. The new
result SHA is bound as diagnostic evidence, and the identical recomputed bytes are measured by three independent Vision
invocations:

- three non-zero deltas with the same wrong sign → `TARGET_DIRECTION_STABLE_MISMATCH`;
- any sign change or exact zero → `MEASUREMENT_SIGN_UNSTABLE`;
- any result-byte, runtime, model or input mismatch → technical hard stop.

No legacy-success drift comparison may be claimed for these 14 cases. This is a categorical mechanism label, not a
numeric tolerance. Neither outcome is eligible for Stage D.

## Resource envelope

- identities: existing 12 Stage B calibration identities only;
- candidate family: unchanged six dimensions;
- logical cases: unchanged 288;
- platform cases: exactly 576;
- transform executions: at most 576 single-repeat diagnostic transforms;
- Vision executions: at most 604, including two additional repeats for each of the 14 legacy direction mismatches;
- generation attempts: 0;
- retries: 0;
- concurrency: global 1; Windows and Linux execute serially;
- wall clock: at most 120 minutes per platform, 240 minutes total;
- private output: at most 4 GiB per platform in new create-once roots;
- network: before reading private input, Windows must establish and verify an outbound deny that covers the runner and
  every spawned child Vision/runtime process; capture is evidence, not containment. Linux uses `--network none`;
- dependency/model/runtime downloads: 0.

No M4-seen or future holdout identity may enter the diagnostic. Existing private reports and CC01C outputs remain
read-only.

Failure to establish or verify the Windows outbound deny prevents replay. Any attempted egress hard-stops the run.
Windows network evidence remains private/redacted and must not expose process paths, private roots or payloads in Git.

## Integrity Gates

All are mandatory:

1. accepted manifest, cohort, case-set, aggregate, report, runtime, model and topology digests match;
2. 576/576 platform cases are represented exactly once;
3. all 232 legacy failed platform cases map to one lossless terminal stage/reason;
4. all 344 legacy successful platform cases retain each of their three accepted repeat artifacts/rows and result
   SHA-256 values (1,032 accepted repeat artifacts/rows total);
5. zero omitted candidate, unknown terminal stage, retry or unclassified domain reason;
6. the 14 direction mismatch cases are recomputed once from frozen authority, bind the new diagnostic result SHA and
   receive exactly three sign measurements on those identical recomputed bytes, without a legacy-success drift claim;
7. no raw exception, Prompt, image, landmark, path, object key, Provider payload or credential enters committed output;
8. no threshold, eligible count, READY classification, ontology promotion or Stage D decision is produced.

If the accepted private reports do not expose enough authority to prove items 3–4, stop as
`FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE`; do not weaken these Gates.

## Bounded stage DAG

```text
CC02-G governance tracked acceptance
→ CC02-A diagnostic harness + golden failure taxonomy
→ CC02-B immutable private-input/case manifest tracked acceptance
→ CC02-C serial Windows/Linux private replay
→ CC02-D redacted mechanism aggregate + decision
→ CC02-E security/research-integrity/final review
→ separate redesign change control or FURTHER_RESEARCH
```

### CC02-A — Diagnostic harness

- Allowed: new versioned CC02 research script and targeted tests.
- Forbidden: old runner/evidence edits, transform/domain behavior, private input access, schema, API and dependency.
- Validation: Ruff, strict mypy, targeted pytest, safe-reason golden cases, redaction and resource-bound tests.

### CC02-B — Diagnostic manifest

- Allowed: machine-readable opaque digests and a human-readable preregistration.
- Forbidden: image, landmark, path, Prompt, object key, threshold or new candidate formula.
- Entry: CC02-A tracked acceptance and exact private reports available read-only.
- Exit: Principal accepts exact input/case/resource digest before replay.

### CC02-C/D/E — Replay, aggregate and review

- Private replay is serial and zero-retry; any integrity failure stops the run.
- Windows replay cannot read private input until child-process-inclusive outbound deny is established and verified;
  Linux replay remains `--network none`.
- Committed aggregate retains every candidate and failure; no success-only filtering.
- Independent security and research-integrity reviewers verify zero evidence rewriting and zero Gate promotion.

## Stop rules and allowed outcomes

- evidence unavailable/digest mismatch → `FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE`;
- legacy-success output drift → `TECHNICAL_FAIL_DIAGNOSTIC_REPLAY_DRIFT`;
- unknown/coarse terminal stage remains → `FURTHER_RESEARCH_INSTRUMENTATION_INSUFFICIENT`;
- resource, network or privacy violation → hard stop;
- complete diagnostic → `DIAGNOSIS_COMPLETE_READY_FOR_SEPARATE_REDESIGN_DECISION`.

No outcome from this protocol opens Stage D/E, T06–T08, MVR or M6. A later redesign requires a new immutable algorithm/
formula/manifest version, a complete new calibration run and its own same-SHA evidence.

`CC_P2_M5_02_G: PASS_AT_137157C_RUN_32267510703_ATTEMPT_1`

`CC_P2_M5_02_A: IMPLEMENTATION_ACCEPTED_AT_EE19AD6_RUN_32282614608_ATTEMPT_1`

`CC_P2_M5_02_A_CLOSURE: PASS_AT_470849F_RUN_32284285946`

`CC_P2_M5_02_B_CONTRACT: PASS_AT_F69361E_RUN_32287419743_ATTEMPT_1`

`CC_P2_M5_02_B_BUILDER: PASS_AT_298420F_RUN_32299835326_ATTEMPT_1`

`P2_M5_R05: REPAIR_ACCEPTED_AT_298420F_RUN_32299835326_ATTEMPT_1`

`CC_P2_M5_03_LOCAL_PUBLICATION_TRUST_BOUNDARY: ACCEPTED_AT_298420F_RUN_32299835326_ATTEMPT_1`

`LOCAL_PUBLICATION_CUSTODY_GATE: REQUIRED_FOR_REAL_BUILDER_INVOCATION`

`CC02_B_BUILDER_PRE_READ_GATE: PASS_AT_298420F_RUN_32299835326_ATTEMPT_1`

`HISTORICAL_CC_P2_M5_02_B_MANIFEST: NOT_CREATED_SUPERSEDED_BY_LOCAL_PASS`

`HISTORICAL_CC_P2_M5_02_PRIVATE_INPUT: PRIVATE_INPUT_RELEASE_REQUIRED_SUPERSEDED_BY_RECOVERY_PASS`

`HISTORICAL_CC02_B_REAL_BUILDER_INVOCATION: NOT_RUN_FAIL_CLOSED_SUPERSEDED_BY_PASS_EXACTLY_ONCE`

`CC_P2_M5_02_C_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`

## Prior Principal output recovery and local manifest candidate

The two qualified CC01C reports were recovered only from the original Principal task receipt and its proven task-owned
root. They were not Owner uploads, filename guesses, regenerated evidence or redacted-aggregate substitutes. Held-file
validation matched all frozen authority and no private locator entered tracked evidence.

Principal then held the ADR-048 exclusive window, ran the accepted builder exactly once and completed the immediate
snapshot. The resulting manifest digest is
`5a0479a21556498d259572a050d659a0e3617429f83e5fd313c842a35591e0a3`. It contains the exact frozen
288/576 cases, 1,032 success-repeat bindings and 14 direction cases. Exact-SHA run `32332408245` and both independent
reviews accepted the CC02-B tracked evidence; CC02-C–E, T06, MVR and M6 remain closed.

`PRIOR_PRINCIPAL_OUTPUT_RECOVERY: PASS`

`CC02_B_REAL_BUILDER_INVOCATION: PASS_EXACTLY_ONCE`

`CC_P2_M5_02_B_MANIFEST: PASS_AT_96CA439_RUN_32332408245_ATTEMPT_1`

`P2_MVR_V1_RESULT: NOT_EVALUATED`

`CC_P2_M5_02_C_ENTRY: CLOSED_PENDING_SEPARATE_BOUNDED_CONTRACT`

`P2_M5_NEXT_ACTION: PREPARE_SEPARATE_CC02_C_BOUNDED_CONTRACT_NO_EXECUTION`
