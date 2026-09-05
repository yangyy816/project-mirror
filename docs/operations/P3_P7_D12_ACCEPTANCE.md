# P3–P7 Demo Epoch 02 — D12 acceptance

Date: 2026-09-05. Decision owner: Integration Principal.

```text
STATUS: PASS
TRACK: DEMO_PROTOTYPE
ACCEPTED_PRODUCT_CODE: 75ffda3c3f782f762ffa1db0479c0647c4a67808
PRODUCT_CODE_CI: 33953264614 PASS
MIGRATION_HEAD: demo_0019_d06_stepped_transfer
D06_CONTROLLED_RUNTIME: TASK_ACCEPTED
D11_REAL_RUNTIME_E2E: TASK_ACCEPTED
D12_COMPLETE_RUNTIME_E2E: TASK_ACCEPTED
ALGORITHMIC_PROTOTYPE_PLATFORM: PASS
LOCAL_WEB_AGENT: PASS
```

The [exact product-code CI](https://github.com/yangyy816/project-mirror/actions/runs/33953264614)
completed at `2026-09-05T09:41:01Z`. All three jobs and their applicable mandatory
steps succeeded. The five audit, Demo boundary, Docker, Playwright installation and
Gitleaks artifacts were downloaded, were unexpired, and identified the same code SHA.
The boundary artifact records one Demo migration head and the separate formal baseline
`0014_m5_eval_authority`. The Gitleaks SARIF contains zero results; the Python SBOM
contains 105 components. Conditional skips for the already-closed bootstrap and
formal evidence generators are the accepted Demo workflow routing, not omitted tests.
The run reports 2,986 Python tests passed and one skipped, strict mypy over 247
sources, 133 Web unit tests and 11 browser contract tests passed. The real runtime
Gates below are separate from deterministic CI fixtures; no zero-skip claim is made.

## Acceptance evidence

| Requirement                    | Actual evidence and result                                                                                                                                                                                                                                                                                                                                                                             |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| D06 controlled geometry        | Two preserved real Jobs: standard geometry and the accepted targeted Case 25. Real source/result M3, M4 and independent verification passed. Missing capability rejected before claim; locks, restraints and no-compatible cases remained fail-closed. Completed redelivery did not republish results.                                                                                                 |
| D11 real browser               | Session `9d64ea4b6edb4024815beb44faf97f21`: supported analysis, 12 responses with both actual question JPEGs loaded before each response, Profile READY, real Geometry preview, INPUT and RESULT HTTP 200 and browser decode at 1254×1254. Exactly one Final Save returned 202, followed by Reference Profile READY. One accepted visual episode and one completed Reference Profile were confirmed.   |
| D12 rebuild and Context        | Actual API/Worker rebuild and two Context Jobs completed. Same-key replay returned the same Job; different payload and same immutable input under another key were rejected with 409. Context and Trace agreed at the same explicit recall time. Current-time recall after Session expiry failed closed; a valid historical explicit time replayed correctly without changing expiry.                  |
| Persistent next-session recall | Main-actor Context selected the real saved D11 visual episode and reported `next_session_recall=true`. The isolated actor's old temporary override was excluded from learning and selected evidence with `SESSION_SCOPE_MISMATCH`.                                                                                                                                                                     |
| P6 restore                     | Job `8db758dea1274606b531ec6e4ddc4519` completed as `IMAGE_VERSION_RESTORED`. New version `e6e6c109eb8efdba84b3cd3eab99910c`, sequence 2, names saved version `339549e59da325f8b3b86ab32ceaa76a` as parent and the original as restore target. Original and saved versions remain unchanged. This is distinct from P7 rollback.                                                                        |
| P7 lifecycle                   | An isolated `AUTOMATED_TEST` actor completed real RESET, ROLLBACK, DELETE and TOMBSTONE application/PG/Worker validation with six append-only events. Deleted/tombstoned derived authority was not recalled; historical authority remained intact. These are not claims about nonexistent Web lifecycle buttons or production data erasure.                                                            |
| Cancellation and redelivery    | An isolated Job was cancelled before dispatch: zero attempts and zero partial Context/result rows. A real broker duplicate delivery of a completed Context produced no additional attempt or result. Terminal Jobs were absent from reconciliation candidates.                                                                                                                                         |
| Safe shutdown                  | Two abandoned, expired diagnostic questionnaires were verified separate from the completed D11 flow and cancelled through `DemoJobService.cancel`, preserving history. No pending/running Jobs remained. The original task-owned consumer exited by warm shutdown, removing its D03/Geometry factories; no force kill or replacement Worker occurred. API operator and browser driver closed normally. |
| Privacy and scope              | No new ImageGen or other Provider calls. No historical D02 generation, screening or admission was repeated. D02 private execution remained custodian-owned; the Principal consumed public/redacted facts. Browser Authorization-header observations were zero. Local/session storage observations were zero; IndexedDB exclusion is static/BFF evidence, not a runtime counter.                        |

The explicit Job-binding creation window begins at `2026-09-05T04:00:00Z`:
41 Jobs, 40 actual JobAttempt rows, 36 new product M3 executions, 3 new M4 executions,
and 0 new Provider calls. Attempt groups are main actor 24, controlled D06 standard
actor 3, controlled D06 targeted actor 3 and isolated D12 actor 10. Earlier 20/30
attempt summaries used incomplete/different windows and are not final totals.

The protected main-flow snapshot covers preference events, accepted visual episodes,
Reference Profiles and ImageVersions. It is not a claim that every actor-owned table
was exhaustively compared.

## Preserved failures and bounded recovery

The isolated lifecycle driver first reached a rejected rebuild because its new actor
lacked a legal D05 source. That rejected Job and zero-profile result remain unchanged.
A forward execution created one real Analysis (three M3 executions), 12 explicitly
automated test responses and a real D05 Profile. A subsequent driver assertion wrongly
expected a positive cross-session trace flag without selected cross-session persistent
evidence. Its failure was preserved; the assertion was corrected to the existing
product predicate while retaining all override-exclusion checks.

Recovery read the completed PostgreSQL checkpoints; it did not repeat Analysis,
Profile or Context compilation. A new isolated Session supported remaining lifecycle
operations when the original TTL became short; no old expiry was extended. Recoverable
public helpers and the detailed runtime checkpoint are in commit
`ea45f124bd9f5b1848145c256bfcbe3f7cd129ad`.

One independent Sol High final review found no new product-correctness/privacy blocker.
Its sole acceptance prerequisite was this exact code CI, now satisfied. The Principal
also corrected the stale continuing-dispatch projection. There was no second runtime
wave or repeated review cycle.

## Original goal delivery audit

- D02 bootstrap remains a normal forward integration of candidate `6bea8374…`.
  Merge `49d2b825…` retains the specified product and D02 parents. The successful
  forward integration CI is `33408104901`; common base `012ee5ac…` and the D02 ACK
  remain recorded. The migration lease returned to the Integration Principal.
- The accepted D11 synthetic version-history shell remains in source and component
  tests, including comparison slider, history, restore/rollback states and accessibility.
  Its UI-only scope and CI `33419815815`/`33436654662` remain historical evidence.
  Accepted `P3_P7_D11_REAL_FLOW_CONTRACT_05` explicitly removed obsolete fixture panels
  from the rendered real page. They are not counted as real D12 execution.
- D06 queued orchestration was accepted with migration `demo_0016_d06_ref_profile_queue`
  and CI `33436654662`; D10 queued Context/rebuild followed serially with
  `demo_0017_d10_context_queue` and CI `33455652850`. Their typed requests, ownership,
  transactional publication, cancellation, reconciliation and lifecycle contracts
  remain covered by the integrated code tests and the fresh runtime evidence above.
- D02 final admission is already accepted: 7/50 historical calls, four sources,
  accepted screening and atomic admission. E3/E4 remain permanently FAILED_CLOSED.
  Subsequent source/model work in this wave is new product execution, not D02 replay.
- The formal worktree independently advanced to `codex/phase2-m7-internal-operations`
  at `376d26d7…`; its existing tracked edits were observed and left untouched. This
  does not turn the Demo branch's formal baseline into a claim about current formal
  milestone acceptance. Final metadata/helper descendants contain no changes to
  product source, public contracts, migrations or workflow relative to the passing code.

## Final boundaries

The authoritative accepted product code is `75ffda3…`, not the later metadata tip.
Helper/static checks and actual runtime validation cover the execution checkpoint;
no complete CI for a metadata SHA is claimed. Closure follows the Owner's metadata-only
efficiency policy and does not trigger another full test wave.

```text
REAL_USER_VALIDITY: NOT_EVALUATED
PREFERENCE_MODEL_GENERALIZATION: NOT_EVALUATED
REAL_FACE_MEASUREMENT_VALIDITY: NOT_EVALUATED
REAL_USER_IDENTITY_PRESERVATION: NOT_EVALUATED
PRODUCT_MARKET_VALIDATION: NOT_EVALUATED
PRODUCTION_SECURITY: DEFERRED_FOR_FORMAL_PHASE
PRODUCTION_RELEASE: NOT_AUTHORIZED
TEMPORARY_RUNTIME_CAPABILITY: REVOKED
POST_ACCEPTANCE_MODE: READ_ONLY_DEMO_DISPLAY
PROJECT_MAINLINE: ACTIVE
CURRENT_DEMO_GOAL: COMPLETE
NEXT_PRODUCT_ACTION: NONE_REQUIRED_FOR_THIS_ACCEPTED_DEMO_EPOCH
```

Further product runtime requires its controlled task-scoped startup; acceptance does
not leave a permanent private execution capability installed or authorize production.
