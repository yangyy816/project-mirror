# P2-M5 Acceptance Evidence

## Status

- Milestone: `P2-M5 — Variable Isolation, Duplicate and Diversity QA`
- State: `EXECUTION_READY`
- Entry baseline: `5f2680e4d0724b409e13ac9cbe318b144cb0375f`
- Entry migration head: `0013_warp_plan_authority`
- Public API change: none
- M6 entry: closed pending technical Gate and P2-MVR-v1 PASS

This is an acceptance skeleton. `PENDING` is not PASS evidence.

## Entry evidence

- Local and remote P2-M4 freeze-state are `5f2680e4d0724b409e13ac9cbe318b144cb0375f`.
- GitHub Actions run `32171351357`, attempt 2, passed `quality-and-integration`, `secret-scan` and
  `docker-validation` on that exact SHA.
- Seven artifacts are present, readable, unexpired and exact-SHA bound. The frozen regression JSON reports migration
  head `0013_warp_plan_authority`, unchanged OpenAPI digest and zero M1/M2/M3 failures/errors/skips. Gitleaks SARIF
  contains zero results.
- Attempt 1 was cancelled after a 35-minute Playwright Chromium download stall; attempt 2 completed the same step in
  68 seconds without repository changes. This is bounded external-download evidence, not a product repair.
- P2-M4 remains `FROZEN`; `jaw_width` remains `EXPERIMENTAL` and N=2 remains
  `FURTHER_RESEARCH_FOR_M5_ISOLATION`.
- The tracked worktree was clean at branch creation except protected existing `.tmp/`, which remains outside scope.

## Mandatory evidence matrix

| Gate                | Required evidence                                                  | Status   |
| ------------------- | ------------------------------------------------------------------ | -------- |
| Architecture        | ADR-041 and rolling-wave contracts accepted                        | T01 PASS |
| Domain              | policy/isolation/cohort/result types deterministic and fail closed | PENDING  |
| Ontology            | new immutable version binds non-sensitive region groups            | PENDING  |
| Database            | forward `0014`, lifecycle, invariants, concurrency, zero drift     | PENDING  |
| Isolation           | actual target error and every non-target delta retained            | PENDING  |
| Similarity          | exact SHA and first-party pHash/Hamming golden evidence            | PENDING  |
| Threshold           | calibration distribution and pre-holdout version freeze            | PENDING  |
| Split               | calibration/M4-seen/holdout/cluster leakage rejected               | PENDING  |
| Duplicate           | append-only cluster membership and review decision                 | PENDING  |
| Diversity           | continuous coverage, occupancy, NN/yield/mode-collapse evidence    | PENDING  |
| Anti-homogenization | no single-template, beauty or sensitive-trait optimization         | PENDING  |
| Recovery            | retry/cancel/duplicate/reconcile and lock-order evidence           | PENDING  |
| Synthetic-only      | no User relation, real-person fixture or live AI CI                | PENDING  |
| Contracts           | public OpenAPI/generated TypeScript unchanged                      | PENDING  |
| Full Gate           | Python/TS/PG/Redis/Celery/Docker/Gitleaks/SBOM/same-SHA CI         | PENDING  |
| Review              | independent security and final review                              | PENDING  |

## Separate outcome ledger

| Outcome                | Current value   | Evidence                                                      |
| ---------------------- | --------------- | ------------------------------------------------------------- |
| `P2_M5_TECHNICAL_GATE` | `PENDING`       | T02–T08 not executed                                          |
| `P2_MVR_V1_RESULT`     | `NOT_EVALUATED` | only four canonical identities and one N=2 M4 dimension exist |
| M6 release entry       | `CLOSED`        | requires both outcomes to PASS                                |

## T01 acceptance

- ADR-041 freezes separate technical/MVR results, immutable `SyntheticEvaluationPolicy`, new ontology-version
  `region_group`, per-dimension cluster-adjusted holdout N, 24→48→96 stop rules, first-party SHA/pHash/Hamming and
  append-only isolation/duplicate/diversity authority.
- `P2_M5_EVALUATION_PROTOCOL.md` freezes the evaluation order and mandatory negative controls without fabricating
  missing cohort or thresholds.
- `P2_M5_EXECUTION_PROTOCOL.md` defines T01–T08, collision domains, validation, Repair protocol and closure sequence.
- No code, migration, dependency, model/image artifact, public API or holdout result is added by T01.
- Owner download authorization is retained as permission for task-required private acquisition only; it is not
  adoption, license, distribution, production or real-user processing approval.

`P2_M5_T01: PASS`

`P2_M5_STATE: EXECUTION_READY`

`P2_M5_TECHNICAL_GATE: PENDING`

`P2_MVR_V1_RESULT: NOT_EVALUATED`

`P2_M6_ENTRY: CLOSED`
