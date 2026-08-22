# P2-M5 CC04-A Fresh Study Proposal Bounded-Task Contract

## Status and authority

- Status: `ACCEPTED_PROPOSAL_WRITING_EXECUTION_READY`.
- Task: `CC-P2-M5-04-A`.
- Change-control authority: ADR-041, ADR-047, ADR-049, ADR-050,
  `P2_M5_CC04_FRESH_EVIDENCE_PROTOCOL.md`, and the active P2-M5 execution and acceptance records.
- Predecessor: `CC_P2_M5_04_G: GOVERNANCE_ACCEPTED_AT_3AC41C3_RUN_32582621932_ATTEMPT_1`.
- Current milestone: P2-M5 remains `EXECUTING`; `P2_MVR_V1_RESULT: NOT_EVALUATED`.

This is an accepted proposal-only contract. It does not select an actual source, Asset, identity, resource count,
candidate family, algorithm, model/runtime, policy, ontology, split, threshold, budget, provider, or private input/output
locator. It does not authorize any execution under `04-A`, and it does not open `04-B` through `04-E`.

The accepted CC02-C recovery stop remains immutable. No legacy CC01-C/CC02 report, case, Asset, identity, digest,
aggregate, output root, runtime, model, or private locator is a permissible input, comparison baseline, replacement, or
selection source for this task or a future fresh study.

## Bounded-task packet

- `BOOTSTRAP_STATUS`: `OK`.
- `TASK_ID`: `CC-P2-M5-04-A`.
- `OBJECTIVE`: after this contract receives tracked acceptance, prepare one versioned, reviewable fresh-study proposal
  or return an explicit `FURTHER_RESEARCH` / `OWNER_DECISION_REQUIRED` stop. The proposal must enumerate the decisions
  and admission evidence required before any future fresh calibration task, while keeping every actual candidate,
  quantity, algorithm, runtime, policy, ontology, budget, custody arrangement and execution authority undecided until
  its own independently accepted decision task.
- `WHY_DELEGATED`: `NONE`. This is Principal-owned planning because the later proposal may surface architecture,
  resource-envelope, license, security, privacy, data-custody, or research-design decisions. It must not be delegated
  as implementation.
- `SCOPE`:
  1. create a tracked proposal template and decision register for a genuinely fresh synthetic-only line;
  2. state the required future evidence for source/origin, rights, adult boundary, candidate-family admission,
     resource ceiling, runtime qualification, policy/ontology, calibration/holdout split, negative controls, custody,
     reproducibility, diversity and M5 disposition separation;
  3. record explicit stop and escalation conditions when any decision lacks accepted authority; and
  4. preserve the sequencing `04-A proposal → 04-B calibration → 04-C evidence → 04-D preregistration → 04-E sealed
holdout/review → separate M5 disposition` without opening a later stage.
- `EXPECTED_CHANGE`: future proposal documents and status records only. They may enumerate required decision categories,
  evidence fields and stop conditions, but they must not decide a concrete resource, candidate, algorithm, runtime,
  policy, ontology, threshold, split, budget, custody locator or execution date.
- `ALLOWED_FILES_OR_MODULES`:
  - future new `docs/research/P2_M5_CC04_FRESH_STUDY_PROPOSAL.md`;
  - future new `docs/research/P2_M5_CC04_DECISION_REGISTER.md`;
  - status-only updates to this contract, ADR-050, the CC04 protocol, P2-M5 execution/acceptance records,
    `AUTONOMOUS_EXECUTION_LOG.md`, `MILESTONES.md`, and `MEMORY.md` by Principal;
  - read-only use of the accepted ADRs, M5 protocols, qualification records and supply-chain dispositions.
- `FORBIDDEN_SCOPE`:
  - selecting, acquiring, generating, importing, normalizing, measuring, transforming, clustering, releasing or
    revoking any source, image, Asset, identity, report, fixture or private evidence;
  - reusing, discovering, copying, inferring from, comparing against, reconstructing, reclassifying or replacing any
    CC01-C/CC02 evidence, private output or locator;
  - choosing an actual candidate, source count, cohort size, dimension, region group, algorithm, formula, model,
    runtime, provider, policy/ontology version, threshold/tolerance, split, budget or implementation schedule;
  - private-input access, output-root creation, registry write, network call, dependency/model download, install,
    qualification promotion, paid service, live Provider or native-image generation;
  - schema/migration, ORM, domain implementation, Worker, API/OpenAPI, CLI, workflow, dependency/lockfile, model
    registry, public contract, production configuration or downstream-Milestone change;
  - real-person/User data, sensitive classification, age estimation, minor-ambiguity bypass, beauty/attractiveness
    score/rank, celebrity similarity, production geometry, M6, real-user facial processing or QuestionBank release.
- `DEPENDENCIES`:
  - accepted CC04-G at `3ac41c3c54de34b6386aebb1ba79b6fa1790dfe1` and its same-SHA run `32582621932`;
  - ADR-041/047/049/050, the CC04 fresh-evidence protocol, active M5 execution/acceptance protocol, and current
    dependency/model/provider/Pillow/OpenCV/Vision dispositions;
  - no private input, source asset, candidate manifest, model artifact, runtime root or execution environment.
- `INPUTS_AND_ASSUMPTIONS`:
  - legacy recovery evidence is historical context only and cannot be transformed into fresh-study selection data;
  - every future source, identity, Asset, measurement, transform, signature, policy, split, runtime/model manifest,
    private output and report must have fresh authority, version/digest and ADR-049 recoverable custody;
  - a future proposal may identify unresolved decision categories, but it cannot silently resolve them from prior
    evidence, upstream claims, a successful import, a planned download or a convenient existing runtime;
  - a future task must separately determine whether a candidate is legally/security/privacy qualified and whether a
    bounded resource envelope is justified; qualification or cost assumptions are never inherited from CC02;
  - no `04-A` document is execution authorization. Missing authority results in an explicit stop, never placeholder
    values masquerading as a frozen decision.
- `ACCEPTANCE_CRITERIA`:
  1. the contract candidate is governance-only and contains every required bounded-task field;
  2. it gives no actual source/candidate/model/runtime/policy/ontology/threshold/resource/budget/custody decision and
     no execution command;
  3. it explicitly requires independent future decisions for fresh source/candidate admission, resource ceiling,
     algorithm/runtime qualification, policy/ontology, calibration/holdout split, negative controls, budget and
     ADR-049 custody before any `04-B` work;
  4. it preserves legacy exclusion, synthetic-only, adult boundary, no-sensitive-inference, anti-homogenization,
     no-beauty-score, production fail-closed and no-real-user-processing invariants;
  5. it preserves `04-E` as sealed identity-disjoint holdout plus independent review only, with any M5 technical/MVR
     disposition remaining a later separate decision;
  6. it names `OWNER_DECISION_REQUIRED`, `LICENSE_REVIEW_REQUIRED`, `SECURITY_REVIEW_REQUIRED`,
     `PRIVACY_REVIEW_REQUIRED`, `DEFERRED_EXTERNAL_DEPENDENCY` and `FURTHER_RESEARCH` as possible honest stops;
  7. scoped formatting, diff and negative scans pass; schema, OpenAPI, workflow, dependency/lockfile and model-artifact
     paths remain unchanged; and
  8. only after same-SHA CI, eight-artifact inspection and independent security/final review may Principal accept this
     contract. Acceptance opens only the separately bounded proposal-writing task, never proposal execution or `04-B`.
- `VALIDATION_COMMANDS`:
  - `pnpm.cmd format:check`;
  - `git diff --check`;
  - scoped source/diff scans proving no legacy CC01/CC02 selection/reference, private locator/path, Prompt, image,
    object key, credential, source acquisition, generation, model/download/install, threshold, resource decision,
    schema/API/workflow/dependency/model change or downstream Gate authorization;
  - inspect the exact changed-path allowlist and confirm OpenAPI, migration head, dependency manifests, lockfiles and
    workflows have zero diff;
  - after candidate commit: full existing local Gate, normal non-force push, same-SHA three-job Actions, eight-artifact
    inspection and independent security/final review.
- `SECURITY_NOTES`: no network, private input, binary, model, runtime root, object key, URL, secret or custody locator
  is admitted. A future fresh line cannot inherit CC02 authority, runtime or output locations. Any unknown candidate
  ownership, license, retention, telemetry, artifact or custody fact fails closed.
- `PRIVACY_NOTES`: this task has no User relation, real-person image, facial-data processing or private-input read.
  Future synthetic-only handling remains private under ADR-049; synthetic origin never authorizes broad access.
- `DATA_NOTES`: no corpus, image, fixture, Asset, identity, measurement, transform, report or threshold is created or
  changed. All future evidence must be newly versioned and recoverable; legacy IDs and aggregates remain immutable.
- `LICENSE_NOTES`: no dependency, wheel, model, weight, data artifact, Provider term or runtime is adopted, downloaded,
  installed, promoted or redistributed. Existing approved scopes remain unchanged and cannot substitute for future
  qualification evidence.
- `ROLLBACK`: before acceptance, reject only this forward governance candidate. After acceptance, a deficient proposal
  is superseded or stopped forward; neither ADR-050 nor legacy evidence is rewritten. No private output exists to clean
  up under this task.
- `RECOMMENDED_AGENT`: Principal / Sol High; no subagent write access. A future concrete research-proposal task must
  be reviewed by Principal before any implementation packet is issued.
- `RECOMMENDED_MODEL_TIER`: Sol High because fresh-study authority, resource boundaries and security/license/privacy
  escalation cannot be delegated as a routine implementation choice.
- `ESCALATION_CONDITION`: stop and return to Principal before writing a future proposal if it requires selecting or
  changing architecture, schema, public contract, Product Invariant, age/adult policy, source-rights position,
  license/model disposition, Provider scope, data class, private custody, algorithm/runtime, resource/budget ceiling,
  threshold/split or downstream-Gate state. Do not conceal such a choice in a template, placeholder or Repair Task.
- `OUTPUT_FORMAT`: `STATUS: PASS|BLOCKED|FAILED; SUMMARY; CHANGED_FILES; VALIDATION_RUN; VALIDATION_RESULT;
DECISIONS_RECORDED; DECISIONS_REMAINING; LEGACY_EXCLUSION_CHECK; SECURITY_PRIVACY_DATA_LICENSE_BOUNDARY;
RISKS_OR_OPEN_QUESTIONS; MEMORY_CANDIDATES; ESCALATION_REASON; NEXT_READY_TASK`.

## Execution and acceptance order

```text
this tracked contract candidate
→ same-SHA CI and eight-artifact inspection
→ independent security/final contract review
→ Principal contract acceptance
→ separate proposal-writing task with its own explicit decision authority
→ no execution unless a later bounded task is independently accepted
```

## Principal acceptance

R11 `10931438912410b235977bf79debde7d980a7e70` closed the independently found next-action ambiguity without modifying
this contract. Its exact-SHA run `32584548148` passed all three jobs and supplied eight readable, unexpired artifacts.
Principal artifact inspection confirmed the four committed evidence documents bind the same SHA and migration head
`0014_m5_eval_authority`, while Gitleaks reports zero results. Independent security and final reviews both passed.

Principal therefore accepts this contract only. The one next ready task is its proposal-writing scope: it may create the
versioned proposal and decision register described above, or return an explicit stop. It cannot select/execute a study,
acquire any resource, access private input, or open `04-B` through `04-E`.

`CC_P2_M5_04_A_CONTRACT: PASS_AT_1093143_RUN_32584548148_ATTEMPT_1`

`CC_P2_M5_04_A_PROPOSAL_WRITING: EXECUTION_READY_PROPOSAL_ONLY`

`CC_P2_M5_04_A_EXECUTION: CLOSED`

`CC_P2_M5_04_B_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`

`P2_MVR_V1_RESULT: NOT_EVALUATED`

`P2_M6_ENTRY: CLOSED_PENDING_TECHNICAL_AND_MVR_PASS`

`P2_M5_NEXT_ACTION: EXECUTE_CC04_A_PROPOSAL_WRITING_PER_ACCEPTED_CONTRACT_NO_STUDY_EXECUTION`
