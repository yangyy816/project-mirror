# P2-M5 CC04-A D01 Owner Decision Closure Contract

## Status and authority

- Status: `ACCEPTED_HISTORICAL_CONTRACT_RECORD`.
- Task: `CC-P2-M5-04-A-D01`.
- Owner decision: `OD-P2-M5-CC04-001` / `PROCEED_WITH_FRESH_EVIDENCE_LINE` dated `2026-08-23`.
- Retained by: Principal / Sol High.
- Authority: ADR-041, ADR-047, ADR-049, ADR-050, the accepted CC04-A proposal-only contract, the CC04 fresh-evidence protocol, and the active P2-M5 acceptance/execution records.

This is a governance-only contract for recording the supplied Owner decision in a later decision pack. It is not a study specification, source acquisition, generation, calibration, qualification, preregistration, holdout, or `04-B` contract. It does not alter the immutable historical CC01-C/CC02 recovery-stop evidence or convert fresh results into replay, repair, recovery, drift comparison, or legacy-Gate evidence.

## Bounded-task packet

- `BOOTSTRAP_STATUS`: `OK`.
- `TASK_ID`: `CC-P2-M5-04-A-D01`.
- `OBJECTIVE`: create a reviewable, tracked Owner-decision closure pack that records only the concrete authority in `OD-P2-M5-CC04-001`, keeps license/security/privacy and fresh-evidence questions explicitly open, and establishes the maximum subsequent eligibility boundary without authorizing study execution.
- `WHY_RETAINED_BY_PRINCIPAL`: the task records Owner authority for source scope, adult boundary, candidate-family constraints, resource ceilings, policy/ontology versioning, split isolation, negative controls, custody, and M5 disposition separation. These are governance, security/privacy/license, research-design, and downstream-Gate boundaries, not routine implementation decisions.
- `SCOPE`:
  1. create one versioned Owner Decision Pack and update the CC04 proposal, decision register, fresh-evidence protocol, and P2-M5 status records only as required to make the supplied Owner decision unambiguous;
  2. record the new fresh-line boundary, without changing CC01-C/CC02 historical evidence or attempting its recovery;
  3. distinguish Owner-accepted constraints from `LICENSE_REVIEW_REQUIRED`, `SECURITY_REVIEW_REQUIRED`, `PRIVACY_REVIEW_REQUIRED`, and `EVIDENCE_GATED_NOT_PREAPPROVED` outcomes; and
  4. leave `04-B` contract writing merely eligible after closure, never executed or created by this task.
- `EXPECTED_CHANGE`: tracked Markdown governance records only. The pack may record the explicitly supplied source scope, adult hard-fail rule, family constraints, resource-envelope ceilings, versioning and split rules, negative-control requirements, custody requirements, and separate technical/MVR disposition boundary. It must not create any runtime, source, Asset, identity, image, cohort, manifest instance, private output, threshold, formula, algorithm result, holdout evidence, or execution authorization.
- `ALLOWED_FILES_OR_MODULES`:
  - new `docs/research/P2_M5_CC04_OWNER_DECISION_PACK.md`;
  - updates to `docs/research/P2_M5_CC04_DECISION_REGISTER.md`, `docs/research/P2_M5_CC04_FRESH_STUDY_PROPOSAL.md`, and `docs/research/P2_M5_CC04_FRESH_EVIDENCE_PROTOCOL.md`;
  - status-only updates to `docs/operations/P2_M5_ACCEPTANCE.md` and `docs/operations/P2_M5_EXECUTION_PROTOCOL.md`; and
  - this contract's Principal acceptance record after exact-SHA evidence is available.
- `FORBIDDEN_SCOPE`:
  - any image generation, source acquisition, Provider call, paid service, model/dependency download or installation;
  - private-input access, locator discovery, output-root creation, asset/identity/cohort creation, normalization, Vision, measurement, transform, pHash review, threshold calculation, holdout access, or MVR evaluation;
  - CC01-C/CC02 report/case/Asset/identity/measurement/transform/output/aggregate/locator reuse, inference, replacement, reconstruction, comparison, or historical-Gate repair;
  - any schema, migration, ORM, API/OpenAPI, Worker, workflow, dependency/lockfile, model registry, production configuration, test binary, or `04-B` contract change;
  - opening T06/T07, P2-M6, production generation/geometry, QuestionBank release, or real-user facial processing; and
  - modifications to the shared collision domain: `AGENTS.md`, `MEMORY.md`, model-routing/milestone/autonomous-execution records, all P2-M7 records, or ADR-051.
- `DEPENDENCIES`: current clean branch baseline `fd64a313c3f2da534e3e019991f1cdb8352f5a74`; migration head `0014_m5_eval_authority`; accepted CC04-A proposal-only output at `ae8abd30b7de11e27ba9b7af04c53b2f79afef2a`; the supplied Owner decision; and the listed ADR/protocol authorities. No private input or external source is a dependency.
- `INPUTS_AND_ASSUMPTIONS`:
  - the Owner decision is authority to record only the constraints stated in it; it does not make a review-required or evidence-gated result pass;
  - `CODEX_NATIVE_IMAGEGEN_FOR_PRIVATE_INTERNAL_RESEARCH_ONLY` is a future private synthetic research source scope, not a programmatic Project Mirror Provider, production approval, complete provenance claim, or authority to call image generation in this task;
  - unknown model ID, snapshot, seed, request ID, usage, and monetary cost remain `UNKNOWN` or `NULL` where applicable;
  - CC01-C/CC02 evidence remains immutable historical context and cannot inform fresh candidate selection;
  - a future task must create fresh versions/digests/manifests and maintain ADR-049 custody; this task creates none; and
  - any missing fact stays `UNKNOWN`, `REVIEW_REQUIRED`, or `FURTHER_RESEARCH` rather than becoming an implied decision.
- `ACCEPTANCE_CRITERIA`:
  1. the phase-2 pack records `OD-P2-M5-CC04-001` accurately and does not add or dilute its authority;
  2. decision-register rows `01`, `03`, `04`, `06`, `07`, and `12` record only their Owner-accepted constraints; rows `01`, `02`, `05`, `08`, and `09` preserve their named review gates; rows `10` and `11` remain evidence-gated, not pass;
  3. source scope stays private synthetic research only, production generation stays fail closed, and all unknown provenance/cost facts remain unknown;
  4. the hard adult boundary, synthetic-only/no-real-person rule, no-sensitive-inference, no-beauty-score, anti-homogenization, legacy exclusion, duplicate/split isolation, negative controls, and ADR-049 custody rules remain explicit;
  5. the envelope records only the Owner's maximum ceilings: 32 calibration raw, 24 calibration QA-passed, 32 sealed-holdout raw, 24 sealed-holdout QA-passed, 64 total outputs, concurrency one, zero automatic retry, 768 transforms, 2500 Vision/measurement operations, and 8 GiB private storage; it does not consume or transfer any allowance;
  6. `04-E` remains evidence only; later, separate P2-M5 technical and P2-MVR-v1 disposition tasks are required before M6 can be considered;
  7. `CC04_B_CONTRACT_WRITING` becomes at most `ELIGIBLE_NOT_EXECUTION_AUTHORIZATION`, while the `04-B` contract stays `NOT_CREATED` and execution stays closed;
  8. all changed paths are in the allowlist; shared collision, ADR-number, schema/migration, OpenAPI/generated-client, workflow, dependency/lockfile, model-artifact, image/binary, private-field, Prompt/path/key/URL/credential, and legacy-reuse negative scans pass; and
  9. each phase receives scoped local validation, non-force exact-branch push, same-SHA mandatory CI, artifact inspection, independent security review, independent Sol High final review, and Principal acceptance.
- `VALIDATION_COMMANDS`:
  - scoped Markdown formatting and `git diff --check`;
  - changed-path allowlist plus zero-diff checks for schema/migrations, OpenAPI/generated client, workflows, dependency manifests/lockfiles, model artifacts, and prohibited shared files;
  - negative scans for legacy CC01-C/CC02 reuse, source acquisition/generation/execution language, private fields, Prompt/path/object-key/URL/credential leakage, and image/binary additions;
  - the existing full local Gate without mutating product or private-research state;
  - normal non-force push only to `codex/phase2-m5-cc04-owner-decision`, exact-SHA Actions inspection, and review of all mandatory exact-SHA artifacts.
- `SECURITY_NOTES`: no network, generation, Provider, model, runtime, private input, binary, object key, signed URL, secret, or production capability is admitted. Review-required decisions remain open and must fail closed if their required evidence is absent.
- `PRIVACY_NOTES`: no real-person or User relation, facial-data processing, private byte, Prompt, locator, key, signed URL, or credential is accessed or tracked. Any later private output must use a Principal-owned ADR-049 registry with an opaque recoverable locator; this task creates no output root or registry entry.
- `DATA_NOTES`: no corpus, Asset, identity, cohort, measurement, transform, duplicate cluster, threshold, report, or holdout is created, read, or changed. Legacy evidence is excluded, and any future fresh object needs a new version/digest.
- `LICENSE_NOTES`: the Owner source selection does not pass license/source-rights/provenance review. No dependency, model, weight, Provider term, or runtime is adopted, downloaded, installed, promoted, distributed, or approved for production.
- `ROLLBACK`: before Principal acceptance, reject this tracked governance candidate without changing historical evidence. After acceptance, correct any defect with a new forward change-control record; do not rewrite ADR-050, historical CC01-C/CC02 evidence, or the Owner decision. No private output exists to clean up.
- `RECOMMENDED_AGENT`: Principal / Sol High; no subagent write access.
- `RECOMMENDED_MODEL_TIER`: Sol High, because this is Owner-decision encoding and controls security/privacy/license boundaries, research authority, resource ceilings, and downstream-Gate separation.
- `ESCALATION_CONDITIONS`: stop before writing the phase-2 pack if a change would select or adopt a dependency/model/runtime, alter architecture/schema/public contract, broaden Provider or production scope, create an adult-policy exception, expand the resource envelope, determine a threshold/formula/candidate set, access private data, create a `04-B` contract, open M6, or touch a shared collision-domain file. Return `REMOTE_BRANCH_CONCURRENCY_MISMATCH` if the remote target gains an unknown commit.
- `OUTPUT_FORMAT`: `STATUS; REPOSITORY_TRUTH; WORKTREE; BRANCH; BASELINE_HEAD; REMOTE_M5_HEAD; GIT_STATUS; MIGRATION_HEAD; OWNER_DECISION_ID; STAGE_1_CONTRACT_FILE; STAGE_1_CONTRACT_COMMIT; STAGE_1_CI_RUN; STAGE_1_ARTIFACT_INSPECTION; STAGE_1_SECURITY_REVIEW; STAGE_1_FINAL_REVIEW; STAGE_1_PRINCIPAL_ACCEPTANCE; OWNER_DECISION_PACK_FILE; DECISION_REGISTER_ROWS_UPDATED; OWNER_ACCEPTED_ROWS; LICENSE_REVIEW_REQUIRED_ROWS; SECURITY_REVIEW_REQUIRED_ROWS; PRIVACY_REVIEW_REQUIRED_ROWS; EVIDENCE_GATED_ROWS; RESOURCE_ENVELOPE; LEGACY_EXCLUSION_PROOF; CHANGED_FILES; SHARED_COLLISION_DOMAIN_CHECK; ADR_NUMBER_RESERVATION_CHECK; LOCAL_VALIDATION; FINAL_COMMIT_SHA; FINAL_REMOTE_CI_RUN; FINAL_ARTIFACT_INSPECTION; FINAL_SECURITY_REVIEW; FINAL_SOL_HIGH_REVIEW; P2_M5_STATE; P2_MVR_V1_RESULT; P2_M6_ENTRY; CC04_B_CONTRACT_STATUS; CC04_B_EXECUTION_STATUS; SHARED_SUMMARY_SYNC; NEXT_READY_TASK; STOP_OUTCOME; RISKS_OR_OPEN_QUESTIONS`.

## Exact sequencing

```text
1. Validate and accept this D01 contract on an exact SHA.
2. Only after that acceptance, create the Owner Decision Pack and the allowed status/register/protocol updates.
3. Validate and accept the phase-2 closure on a new exact SHA.
4. Stop with 04-B contract writing merely eligible; do not create or execute it.
```

## Principal acceptance

Candidate `7659eed48917b1491fd5fc8d18180c28f35944ec` completed exact-SHA run `32592430642`: all mandatory jobs succeeded; eight artifacts were readable, unexpired, and bound to that SHA and `0014_m5_eval_authority`; independent Security and Sol High reviews passed. Principal acceptance is `GRANTED` for this D01 contract only. This historical acceptance opened proposal writing, not study execution or `04-B`.

`CC_P2_M5_04_A_D01_CONTRACT: PASS_AT_7659EED_RUN_32592430642`
