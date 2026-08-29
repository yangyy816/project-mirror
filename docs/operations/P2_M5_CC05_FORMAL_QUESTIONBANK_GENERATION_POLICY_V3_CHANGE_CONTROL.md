# CC-P2-M5-05 — Formal QuestionBank Generation Policy v3 Binding

- `BOOTSTRAP_STATUS: OK`
- `CHANGE_CONTROL_ID: CC-P2-M5-05`
- `OWNER_AUTHORITY_DATE: 2026-08-29`
- `BASELINE_COMMIT: 5eda4cf19ca2c8f3f5b66dd4e7e2f5cbd0d51950`
- `BASELINE_R39_STATUS: PRINCIPAL_ACCEPTED_AFTER_RUN_32830012131_AND_INDEPENDENT_REVIEWS`
- `CHANGE_CLASS: FORWARD_PRODUCT_AND_GENERATION_GOVERNANCE`
- `POLICY_AUTHORITY: ADR-052`
- `POLICY_DOCUMENT: docs/research/P2_QUESTIONBANK_GENERATION_POLICY_V3.md`
- `MACHINE_READABLE_POLICY: docs/research/P2_QUESTIONBANK_GENERATION_POLICY_V3.json`

## Objective

Bind every future formal synthetic face, QuestionBank candidate, pairwise comparison and local Demo
face case to an adult-only 18–25, China-first, controlled-variable and non-scoring admission policy.
Preserve all historical policy, Prompt, attempt, image, manifest and provenance evidence.

## Conflict resolution

The Owner input contains both `ADULT_ONLY_18_TO_25` and an apparent `18 -16: 10%` allocation. Under
the repository's 18+ product boundary and explicit formal-admission bands, the latter cannot create a
16–17 band. V3 records 70% `ADULT_20_25`, 20% `ADULT_18_19` and 10% adult-only flex assignable only
to those two bands.

## Current M5 effect

- R39 remains accepted historical/current baseline evidence.
- `CAL-REQ-002` remains `NOT_CONSUMED`; no generation or decode occurs in CC05.
- The R39 next action to execute `CAL-REQ-002` is suspended for forward execution until
  `CC-P2-M5-05-A_PRIVATE_POLICY_MATERIALIZATION` completes.
- CC05-A must create a new private policy/Prompt/rubric version, bind the V3 content digest and the
  existing immutable assignment ledger, and prove custody, register-before-decode, Prompt/seed/
  locator non-propagation, age/style/pair semantics and zero output before dispatch.
- No existing private Prompt or generation specification is overwritten. If the exact current private
  root cannot be recovered from its task-scoped receipt, the task must stop with
  `PRIVATE_INPUT_SCOPE_EXPANSION_REQUIRED` or create a separately authorized forward epoch; it must
  not search or guess paths.
- Within the new formal QuestionBank/pair/AestheticProfile synthetic-input/Demo scope, V3 is the
  narrower forward overlay over ADR-029/030. Their historical evidence and broader research-only
  scopes remain intact, but they cannot weaken V3 formal adult/nonsexual admission.

## Allowed scope

- ADR-052 and V3 first-party policy/rubric contracts.
- Architecture, Provider and questionnaire/Demo guidance references.
- Deterministic policy contract tests.
- Current M5 acceptance/protocol policy overlay only.

## Forbidden scope

- Image generation, Prompt materialization, image/seed/private-locator access or `CAL-REQ-002`
  consumption.
- Schema, migration, OpenAPI, generated TypeScript, dependency, model or production Provider change.
- M5 threshold, READY promotion, holdout/MVR evaluation, M6 release, QuestionBank membership,
  production geometry or real-user facial processing.
- Rewriting ADR-024/028/029/030, age/style v1/v2, V01 or any prior M5 evidence.

## Acceptance criteria

1. V3 machine-readable canonical digest is correct and the adult-only allocation totals 100% without
   an under-18 band.
2. Formal admission requires both allowed age band and `suspected_minor=false`; 18–19 remains
   nonsexual-only. Required records explicitly carry source-rights, decode/QA, likeness, duplicate,
   visual-quality, comparability, isolation and anti-homogenization outcomes consumed by admission.
3. `GEOMETRY_PAIR` and `STYLE_PAIR` have separate control-variable rules, while both sides pass the
   same quality and comparability gates.
4. Product acceptance remains categorical with no per-face score, rating, percentile or ranking.
5. Prompt semantics are versioned but full Prompt, seed, bytes, locator, object key and Provider raw
   payload remain outside Git/MEMORY/log/artifact/UI.
6. Demo uses only pre-generated admitted synthetic assets with zero runtime generation.
7. OpenAPI, migration head, dependencies, models and historical evidence remain unchanged.
8. Exact-SHA CI and all eight current artifact families pass before CC05 becomes current:
   `project-audit-evidence`, `p2-m3-ci-evidence`, `p2-m2-ci-evidence`, `p2-m1-ci-evidence`,
   `phase1-ci-evidence`, `playwright-install-evidence`, `project-docker-evidence` and
   `gitleaks-results.sarif`; each artifact is inspected before independent security review, Sol High
   final review and Principal acceptance.

## Next bounded action

```text
TASK_ID: CC-P2-M5-05-A_PRIVATE_POLICY_MATERIALIZATION
IMAGEGEN_CALLS_ALLOWED: 0
PRIVATE_INPUT_DISCOVERY: PROHIBITED
CAL_REQ_002_CONSUMPTION: PROHIBITED
OUTPUT: task-scoped private V3 policy/Prompt/rubric envelope, digest receipt and zero-leakage evidence
STOP: before generation dispatch
```

`CC_P2_M5_05_STATUS: CANDIDATE_PENDING_SAME_SHA_GATES`

`P2_M5_STATE: EXECUTING`

`P2_M5_TECHNICAL_GATE: NOT_EVALUATED`

`P2_MVR_V1_RESULT: NOT_EVALUATED`

`P2_M6_ENTRY: CLOSED`
