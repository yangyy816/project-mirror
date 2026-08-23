# CC-P2-M5-04-B-T01 Fresh Calibration Cohort Bounded-Task Contract

## Status and authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: CC-P2-M5-04-B-T01`
- `TASK_NAME: Fresh Calibration Cohort Bounded-Task Contract`
- `CC04_B_T01_CANDIDATE: THIS_COMMIT`
- `CC04_B_T01_AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ARTIFACT_SECURITY_SOL_AND_PRINCIPAL_ACCEPTANCE`
- `CC04_B_T01_PRE_CONDITION_CURRENT_STATE: CC04_B_CONTRACT=CANDIDATE_THIS_COMMIT_PENDING_ACCEPTANCE; CC04_B_EXECUTION=CLOSED`

This is a contract-writing-only governance candidate. It defines a future bounded calibration acquisition task, but does not call image generation, perform a review, access private input, create an output root, register an Asset or identity, create a cohort, consume quota, or create any evidence.

## Bounded-task packet

- `OBJECTIVE`: define the independently reviewable, finite, fail-closed contract for a future fresh synthetic calibration cohort of at most 32 raw outputs targeting exactly 24 independent QA-passed calibration identities.
- `WHY_RETAINED_BY_PRINCIPAL`: source admission, adult safety hard-fail rules, private custody, cohort isolation, quota stops, review DAG, and generation-precondition authority are security/privacy/license/research-governance decisions.
- `SCOPE`: contract text and current-state authority only. Future execution may acquire fresh calibration raw outputs, register private synthetic records, perform bounded hard QA, and admit an isolated calibration cohort only after every required pre-execution review and a separate accepted execution task.
- `EXPECTED_CHANGE`: one tracked Markdown contract and status-only canonical/mirror EOF tails. No runtime, data, source, Provider, image, binary, private evidence, or execution authority is created.
- `ALLOWED_FILES_OR_MODULES`: this contract plus status-only updates to `docs/operations/P2_M5_ACCEPTANCE.md` and `docs/operations/P2_M5_EXECUTION_PROTOCOL.md`.
- `FORBIDDEN_SCOPE`: generation; private-input access/discovery; output-root, custody-locator, Asset, identity, cohort, manifest, output, transform, Vision, measurement, threshold, formula, holdout, MVR, M6, production, QuestionBank, real-user processing, schema, migration, API/OpenAPI, Worker, workflow, dependency, model, ADR, P2-M7, or shared-collision-domain change.
- `DEPENDENCIES`: accepted R14 `95cbaca80aa07b7fc284fb007abb9b67300458fa` / run `32621828872`; `OD-P2-M5-CC04-001`; ADR-026, ADR-041, ADR-047, ADR-049, ADR-050; the Owner Decision Pack; the CC04 Decision Register; the Fresh Study Proposal; the Fresh Evidence Protocol; and the P2-M5 Evaluation Protocol. No private input, source artifact, model, Provider call, or execution output is a dependency.
- `INPUTS_AND_ASSUMPTIONS`: all Owner values below are inherited constraints, not reopened decisions; unknown model ID, snapshot, seed, request ID, usage, and monetary-cost facts remain `UNKNOWN` or `NULL`; no review result is presumed PASS; legacy CC01-C/CC02/M4 material is excluded; missing facts remain review-required or evidence-gated.

## OWNER_AUTHORITY_INHERITED

The future task must inherit these exact limits without transfer, expansion, or reinterpretation:

- `SOURCE_KIND: CODEX_NATIVE_IMAGEGEN`
- `SOURCE_SCOPE: PRIVATE_INTERNAL_RESEARCH_ONLY`
- `PROVENANCE_LEVEL: PROVENANCE_ONLY`
- `COST_ACCOUNTING_MODE: REQUEST_COUNT_ONLY`
- `EXTERNAL_CASH_BUDGET: 0`
- `PAID_EXTERNAL_PROVIDER_ALLOWED: false`
- `PRODUCTION_PROVIDER_APPROVAL: NOT_GRANTED`
- `PRODUCTION_GENERATION_STATUS: FAIL_CLOSED`
- `CALIBRATION_RAW_GENERATION_MAX: 32`
- `CALIBRATION_QA_PASSED_TARGET: 24 independent identities`
- `SEALED_HOLDOUT_RAW_GENERATION_MAX: 32`
- `SEALED_HOLDOUT_QA_PASSED_TARGET: 24 independent identities`
- `TOTAL_NATIVE_GENERATED_OUTPUT_MAX: 64`
- `GENERATION_CONCURRENCY: 1`
- `AUTOMATIC_RETRY_CEILING: 0`
- `TRANSFORM_OPERATION_GLOBAL_HARD_CEILING: 768`
- `VISION_OR_MEASUREMENT_GLOBAL_HARD_CEILING: 2500`
- `NEW_PRIVATE_OUTPUT_STORAGE_GLOBAL_HARD_CEILING: 8 GiB`
- `N_48_OR_N_96_EXPANSION: NOT_AUTHORIZED`

## RESOURCE_ENVELOPE

`04-B` may consume only the calibration allocation. Each raw output, including rejected output, counts against the 32-raw ceiling. It must stop immediately when 24 independent identities pass QA. If 32 raw outputs are consumed before that target, it must stop as `FURTHER_RESEARCH_RESOURCE_ENVELOPE_EXHAUSTED`. No loop, manual repetition, hidden retry, holdout allocation, or quota transfer may bypass those rules.

## PRE_EXECUTION_REVIEW_DAG

The reviews are serial preconditions. This task neither executes nor accepts any of them.

1. `CC04-B-L01 — Source rights and provenance review`
   - Freeze internal-research-only CODEX_NATIVE_IMAGEGEN scope, retention, and source-rights/provenance record.
   - Record unknown or null model ID, snapshot, seed, request ID, usage, and monetary cost honestly; do not claim complete Provider provenance or production approval.
   - Required disposition: `LICENSE_AND_PROVENANCE_REVIEW: PASS | FURTHER_RESEARCH | BLOCKED`.
2. `CC04-B-S01 — Adult safety and negative-control review`
   - Freeze clearly-adult hard-fail, no age estimation, no ambiguity bypass, no real/User/celebrity reference, malformed/multi-face/unsafe rejection, no beauty score, no sensitive inference, and the specified leakage/network/resource/production negative controls.
3. `CC04-B-P01 — Private custody review`
   - Freeze Principal-owned registry, create-once private output root, opaque recoverable locator, digest/type/bytes/scope/retention, cleanup evidence, no discovery, and no private binary, Prompt plaintext, object key, URL, credential, or private path in tracked evidence.
4. `CC04-B-Q01 — Cohort and QA admission review`
   - Freeze the GenerationSpecification version, calibration assignment, identity-ID policy, canonical Asset and normalized-SHA isolation, duplicate-cluster rules, legacy/M4 exclusion, hard QA, reliability boundary, coverage requirements, rejection taxonomy, and no downstream-performance selection.
5. `CC04-B-O01 — Operational envelope review`
   - Freeze auditable finite operator actions for 32 maximum raw, 24 target, concurrency one, retry zero, request-count accounting, storage accounting, stop-on-target, stop-on-exhaustion, no holdout use, and no hidden quota transfer.

All five reviews require independent acceptance. Only then may a separate `CC04-B-EXECUTION` bounded task be written and accepted before its first generation call.

## GENERATION_SPECIFICATION_REQUIREMENTS

Any future approved specification must be synthetic-only, clearly adult-presenting, female-oriented, East-Asian-presenting in the first coverage context, nonsexual, protocol-approved frontal or bounded pose, and standardized in lighting, background, and expression. It must demand explicit morphology and style-context diversity without creating a hidden standard face.

It must prohibit real-person, User Asset, celebrity/influencer, or internet-scraped reference; child or student-minor context; age estimation; ambiguity bypass; sensitive classification or race/ethnicity inference; beauty/attractiveness score or ranking; and any CC01-C, CC02, or M4 Asset or identity reuse. Adult presentation is controlled only by the specification and non-overridable hard-fail review; ambiguous output is rejected and cannot be overridden.

## QA_ADMISSION_RULES

Future 04-B execution may admit only fresh calibration outputs passing the frozen decode, single-face, adult-safety, pose, background, expression, normalization, duplicate, and reliability rules. Malformed, multi-face, unsafe, ambiguous-adult, duplicate, excluded, or unreliable outputs must be rejected with an allowlisted reason code. Admission must not select identities based on downstream transform, target/control performance, formula, threshold, dimension-readiness, holdout, MVR, or release outcome.

## IDENTITY_AND_SPLIT_ISOLATION

Future calibration identities require fresh identity IDs, canonical Assets, normalized SHA-256 evidence, and duplicate-cluster decisions. Every identity and Asset must be isolated from CC01-C, CC02, M4, and any future sealed holdout. Calibration is not a holdout and cannot consume, borrow, precreate, access, or influence the 32-raw/24-QA-passed holdout allocation. This task creates none of these records.

## PRIVATE_CUSTODY

Any later private output follows ADR-049: Principal-owned registry, create-once task-scoped root, opaque recoverable locator, digest, type, byte count, scope, retention, allowed future task, and cleanup evidence. No Agent may discover a path or registry by enumeration. Private bytes, Prompt plaintext, object keys, URLs, credentials, and private paths must remain outside Git, CI artifacts, logs, and MEMORY. This contract creates no root, locator, registry entry, or private data.

## NEGATIVE_CONTROLS

The future review/execution chain must fail closed for adult ambiguity, real/User/celebrity reference, malformed or multi-face output, unsafe output, exact/cluster duplicate, resource overflow, hidden network, unsupported PASS, Prompt/path/key/URL/credential leakage, production or M6 bypass, legacy reuse, holdout use, quota transfer, automatic retry, sensitive inference, and beauty scoring.

## STOP_CONDITIONS

- Stop before execution unless L01, S01, P01, Q01, and O01 all pass independently and a separate execution task is accepted.
- Stop after 24 independent QA-passed calibration identities; do not issue another request.
- Stop at 32 calibration raw outputs with fewer than 24 admissions as `FURTHER_RESEARCH_RESOURCE_ENVELOPE_EXHAUSTED`.
- Stop on any hard QA, custody, provenance, safety, duplicate, isolation, network, leakage, quota, or scope violation.
- Stop for any request to use holdout, choose a candidate formula or threshold, run transform/Vision/measurement evidence, judge dimension readiness, evaluate MVR, open M6, or enable production or QuestionBank release.

## ACCEPTANCE_CRITERIA

1. All required contract fields are present and this candidate defines no execution.
2. Every inherited Owner value above is exact and no new budget, retry, quota, or global ceiling is introduced.
3. The review DAG, hard adult boundary, private-custody prerequisites, QA/isolation, and finite stop rules are explicit.
4. `04-B` remains calibration-only; holdout, 04-C/04-D/04-E, T06/T07, MVR, M6, production, and QuestionBank remain closed.
5. Exactly three paths change; all current-state keys are unambiguous at true EOF in the canonical Acceptance tail and exact Execution mirror.
6. Scoped Markdown formatting, `git diff --check`, allowlist, authority, envelope, prohibition, leakage, binary, and zero-diff boundary checks pass; then the exact-SHA CI, artifact, Security, Sol High, and Principal Gates pass.

## VALIDATION_COMMANDS

- scoped Prettier and `git diff --check`;
- exact three-file allowlist and no-untracked-extra-path check;
- contract-field, Owner-value, review-DAG, stop-rule, prohibition, downstream-boundary, and current-blocker scans;
- physical true-EOF, heading, sentinel, last-occurrence, and canonical/mirror equality validation;
- legacy/private/Prompt/path/key/URL/credential and image/binary scans;
- schema/migration/OpenAPI/workflow/dependency/model/shared-file zero-diff scans;
- existing full local Gate, reported without unrelated reformatting; normal non-force exact-branch push; same-SHA CI, eight-artifact inspection, independent Security and Sol High review, and Principal acceptance.

## SECURITY_NOTES

This candidate adds no network, Provider, generation, model, runtime, private input, binary, secret, production capability, or external cash spend. Review-required and evidence-gated facts remain fail-closed.

## PRIVACY_NOTES

No real-person or User relation, facial-data processing, private byte, Prompt, locator, key, signed URL, or credential is accessed or tracked. Future private handling remains Principal-owned under ADR-049.

## DATA_NOTES

No raw output, Asset, identity, cohort, duplicate cluster, measurement, transform, threshold, report, or holdout is created, read, or changed. Legacy material is historical context only and excluded from future selection.

## LICENSE_NOTES

This candidate does not pass source-rights or provenance review, adopt a dependency/model/runtime/Provider, download anything, or approve distribution or production.

## ROLLBACK

Reject this normal forward candidate before acceptance without creating execution-side effects. Correct any accepted-document defect only through a new forward change-control record; do not amend, reset, rebase, rewrite R14, or create a post-acceptance status commit.

## RECOMMENDED_AGENT

`Principal / Sol High`

## RECOMMENDED_MODEL_TIER

`Sol High`

## ESCALATION_CONDITIONS

Stop for any fourth changed path; Owner-value, envelope, adult-policy, review-Gate, authority-tail, or downstream-boundary drift; need for source/model/runtime adoption; private-input access; execution; or any shared-collision-domain change.

## OUTPUT_FORMAT

`STATUS; BASELINE_SHA; R14_AUTHORITY_VERIFICATION; CONTRACT_TASK_ID; CONTRACT_FILE; CONTRACT_COMPLETENESS; INHERITED_OWNER_AUTHORITY; RESOURCE_ENVELOPE; PRE_EXECUTION_REVIEW_DAG; GENERATION_PROHIBITION_CHECK; PRIVATE_INPUT_PROHIBITION_CHECK; HOLDOUT_AND_DOWNSTREAM_BOUNDARY_CHECK; CHANGED_PATHS; CANONICAL_AUTHORITY_VERSION; TRUE_EOF_VALIDATION; CANONICAL_MIRROR_EQUALITY; LOCAL_VALIDATION; FULL_LOCAL_PNPM_CHECK_STATUS; CONTRACT_CANDIDATE_SHA; PUSH_RESULT; SAME_SHA_CI_RUN; MANDATORY_JOB_RESULTS; ARTIFACT_COUNT; ARTIFACT_INSPECTION; SECURITY_REVIEW; SOL_HIGH_REVIEW; PRINCIPAL_ACCEPTANCE; CC04_A_OWNER_DECISION_CLOSURE; CC04_B_CONTRACT_WRITING; CC04_B_CONTRACT; CC04_B_EXECUTION; P2_M5_STATE; P2_MVR_V1_RESULT; P2_M6_ENTRY; P2_M5_NEXT_ACTION; SHARED_SUMMARY_SYNC; MEMORY_MD_STATUS; P2_M7_WORKTREE_UNTOUCHED; POST_ACCEPTANCE_COMMIT_CREATED; STOP_OUTCOME; RISKS_OR_OPEN_QUESTIONS`.

## EXACT_SEQUENCING

1. Validate and accept this contract candidate on its own exact SHA.
2. Stop. Do not write or execute L01, S01, P01, Q01, O01, or `CC04-B-EXECUTION` in this task.
3. The next task may execute the serial pre-execution review DAG only, with no generation.
4. Only after every review and a separate accepted execution authority may the first generation call occur.
