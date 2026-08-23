# P3–P7 Demo Risk Register

## Register authority

```text
REGISTER_VERSION: p3-p7-demo-risk-register-v1.1-network-amended
TRACK: DEMO_PROTOTYPE
OWNER: TERRA_HIGH_PRINCIPAL
REVIEW_CADENCE: every D checkpoint and immediately after a trigger
ALLOWED_STATUS: OPEN | MITIGATED_MONITORED | TRIGGERED | RECOVERING | CLOSED | ACCEPTED_RESIDUAL
```

This is a continuous register. `CLOSED` requires evidence; a D00 mitigation does not erase the risk. Each entry records
the required description, probability, impact, early signal, mitigation, contingency, owner, status and blocked tasks.
P/D/R/S mean Prevention, Detection, Recovery and Stop Rule.

## R-DEMO-01 — M3 private runtime/asset locator unavailable

- **Probability / impact:** Medium / Critical
- **Description:** accepted Vision runtime, model, asset or receipt cannot be resolved from Principal registry/task receipt.
- **Early signal:** registry miss, stale custody, missing byte size, digest mismatch or a request to scan storage.
- **P:** append-only registry, exact receipt/digest/size/authority, downstream retention check before cleanup.
- **D:** D00 and each consuming task resolve opaque IDs and reverify digest before execution.
- **R:** one pre-registered bounded recovery from accepted receipt/recipe; nondeterministic bytes receive a new authority ID.
- **S:** D00 cannot GO; D03/D04/D05 stop. Never ask Owner to recreate Principal-owned output or broad-scan disks.
- **Owner / status / blocked:** Principal / `MITIGATED_MONITORED` / D03, D04, D05.

## R-DEMO-02 — M4 private geometry runtime cannot load

- **Probability / impact:** Medium / Critical
- **Description:** exact OpenCV/geometry manifest is unavailable, mismatched or not loadable by the standard Demo runtime.
- **Early signal:** manifest digest mismatch, missing closure file, DLL load error or adapter smoke failure.
- **P:** freeze exact runtime manifest and loader contract; keep task-scoped read-only custody.
- **D:** D00 smoke and D01-A official-worktree adapter replay; D07 preflight before pair/editor work.
- **R:** one exact bounded reconstruction from accepted recipe/digests, then full D00 rerun.
- **S:** stop D02 geometry, D07 and D06; no hard-coded after image or landmark substitution.
- **Owner / status / blocked:** Principal / `MITIGATED_MONITORED` / D02, D07, D06.

## R-DEMO-03 — Fewer than two geometry dimensions pass pair screening

- **Probability / impact:** High / High
- **Description:** fewer than two of jaw width, chin height and eye spacing pass all 16-pair lineage/direction/drift/artifact checks.
- **Early signal:** wrong measured direction, excessive non-target drift, lock conflict, checksum instability or systematic artifact.
- **P:** D00 screens three candidates; D02 freezes same-source opposite-direction design and pair-level QA before QuestionBank admission.
- **D:** `4 identities × 2 dimensions × 2 magnitudes` matrix with every required QA field and deterministic replay.
- **R:** bounded dimension recovery/redesign using the remaining candidate; preserve failed evidence and the two-dimension target.
- **S:** mark `P4_MULTI_DIMENSION_ACTIVE_ROUTING: BLOCKED` and platform `FAIL`; continue only independent P3/P5/P6/P7 work.
- **Owner / status / blocked:** Principal + P4/P6 owners / `OPEN` / D04, D12.

## R-DEMO-04 — Formal worktree contamination or base drift

- **Probability / impact:** Medium / Critical
- **Description:** formal uncommitted bytes or later HEAD are copied into the fixed Demo base without explicit accepted replay.
- **Early signal:** unexpected file at worktree creation, branch-point mismatch, formal status hash change attributable to Demo or cherry-pick evidence.
- **P:** Git-object checkout from exact base, redacted before/after manifest, separate branch/worktree and scoped diff.
- **D:** `BASE_SHA_EXACT`, Demo status, formal before/after and changed-path attribution at D01-A/D12.
- **R:** discard only the verified Demo worktree and recreate from exact base; never reset formal work.
- **S:** stop all integration on any unattributed cross-track byte.
- **Owner / status / blocked:** Principal / `OPEN` / D01, D12.

## R-DEMO-05 — Demo migration conflicts with formal revisions

- **Probability / impact:** Medium / High
- **Description:** prototype revision is mistaken for formal sequence or produces multiple heads/drift.
- **Early signal:** revision named `0015_*`, down revision not `0014`, multiple heads, Alembic drift or direct promotion proposal.
- **P:** branch-local `demo_0001_p3_p7_core` metadata and direct-cherry-pick prohibition.
- **D:** fresh/upgrade/downgrade/re-upgrade, single-head, `alembic check`, zero-drift and populated-downgrade tests.
- **R:** repair the prototype revision before D01-B acceptance; formal absorption uses a new forward migration.
- **S:** stop D01-B/C and all database consumers while lifecycle or authority is ambiguous.
- **Owner / status / blocked:** Principal + data owner / `MITIGATED_MONITORED` / no current task; formal promotion and D12 remain monitored.

## R-DEMO-06 — Formal and Demo entities become competing authorities

- **Probability / impact:** Medium / High
- **Description:** reuse creates two sources that both claim authority or silently forks v0.2 semantics.
- **Early signal:** duplicate owner fields, stale admission remains eligible, external authority facts are not snapshotted,
  unresolved lineage digests, missing promotion plan or unexplained physical substitution.
- **P:** accepted `DEMO_SCHEMA_REUSE_MATRIX`, `P3_P7_D01_B_CC_01`, exactly one Demo authoritative source per logical
  entity, frozen formal QA snapshot and bidirectional image-execution binding.
- **D:** revoked-admission, snapshot mismatch, arbitrary/missing/cross-owner lineage, half-edge, AcceptedEpisode and
  concurrency tests prove no capability/evidence/API/rebuildability/formal-authority loss.
- **R:** the bounded forward repair is implemented on top of the rejected candidate; isolated PostgreSQL, migration,
  full regression and formal-DDL checks are rerun and bound to the remediation candidate.
- **S:** reopen and stop the affected checkpoint on any future authority-parity, stale-admission or unresolved-lineage
  regression.
- **Owner / status / blocked:** Principal + data owner / `MITIGATED_MONITORED` / no current task; D01-C and every
  downstream database consumer retain regression checks.

## R-DEMO-07 — Bayesian Newton solver is unstable or non-convergent

- **Probability / impact:** Medium / High
- **Description:** invalid Hessian, false boundary failure, overflow, iteration exhaustion or disagreement with the reference posterior.
- **Early signal:** non-finite intermediate, positive Hessian, KKT violation, grid error above 2 ppm or derivative mismatch.
- **P:** frozen one-dimensional formula, stable logistic math, bounds, iteration/tolerance and projected KKT rules.
- **D:** grid, finite-difference gradient/Hessian, symmetry, reversal, monotonicity, contradiction and replay suites.
- **R:** bounded algorithm repair with unchanged preregistered reference/threshold; rerun the complete numerical suite.
- **S:** fail closed without posterior success; stop D04-B and downstream DesiredDelta compilation.
- **Owner / status / blocked:** P4 owner / `OPEN` / D04, D05.

## R-DEMO-08 — Raw floating point causes posterior/profile digest drift

- **Probability / impact:** Medium / High
- **Description:** platform/DB/runtime float representation changes canonical payload or digest.
- **Early signal:** same answers/watermark produce different bytes, negative zero, unordered collection or raw float in stored authority.
- **P:** clamp and round-half-even fixed integers; persist posterior/Profile confidence and consistency in ppm only.
- **D:** byte-identical cross-replay, schema scan and canonical digest tests.
- **R:** repair canonicalization before authority promotion and explicitly version any already-written conversion.
- **S:** stop D04/D10 acceptance on any digest divergence or raw-float authority.
- **Owner / status / blocked:** P4 + P7 owners / `OPEN` / D04, D10, D12.

## R-DEMO-09 — Context recency breaks deterministic Profile rebuild

- **Probability / impact:** Medium / High
- **Description:** implicit wall clock changes Profile digest or context without an authoritative input change.
- **Early signal:** same watermark rebuild differs; compiler calls `now()` for digest input; context omits explicit as-of time.
- **P:** Profile uses event sequence/watermark/compiler version; Context receives normalized `context_as_of_time`.
- **D:** same-input/same-watermark digest tests plus reset/tombstone/rollback propagation tests.
- **R:** repair compiler inputs, invalidate affected derived views and rebuild from authoritative evidence.
- **S:** stop D10/D12 while deterministic reconstruction is not proven.
- **Owner / status / blocked:** P7 owner / `OPEN` / D10, D12.

## R-DEMO-10 — Private runtime/assets enter Git or ordinary CI

- **Probability / impact:** Low / Critical
- **Description:** image, landmark, model, runtime, locator, object key or private path leaks through tracked files/log/artifact.
- **Early signal:** binary/unexpected extension, Gitleaks finding, locator/path scan hit, cache/artifact includes private namespace.
- **P:** Git-external registry, task-scoped read-only mounts, ignored private namespace and redacted evidence only.
- **D:** staged/scoped diff scan, Gitleaks, artifact inventory and private-byte/path negative scan before commit/push.
- **R:** immediately isolate the candidate and stop processing; Principal handles repository/credential incident disposition.
- **S:** stop all private work and do not push while any leak or custody uncertainty exists.
- **Owner / status / blocked:** Principal / `MITIGATED_MONITORED` / this candidate has zero Gitleaks, locator/path and
  binary-byte findings; every later private task and push must rerun the same stop rule.

## R-DEMO-11 — Real runtime performance causes browser timeout

- **Probability / impact:** Medium / Medium
- **Description:** real M3/M4/Worker latency prevents a complete local browser flow or misses operational targets.
- **Early signal:** growing queue delay, P95 above target, Playwright wait timeout or Worker lease expiry.
- **P:** concurrency one for heavy runtime, pre-generated QuestionBank and explicit asynchronous progress/status.
- **D:** per-stage telemetry and P95 report from real runtime, never mocked timing.
- **R:** optimize batching, scheduling, caching of immutable artifacts or UI timeouts without deleting algorithms.
- **S:** target miss is a recorded performance risk; if E2E cannot complete, the corresponding Gate fails or remains NOT_VERIFIED.
- **Owner / status / blocked:** platform owner / `OPEN` / D11, D12.

## R-DEMO-12 — Worker and Web states diverge

- **Probability / impact:** Medium / High
- **Description:** UI displays a state not backed by PostgreSQL or duplicate Worker delivery publishes inconsistent authority.
- **Early signal:** terminal state regresses, missing JobAttempt, duplicate version/event or stale polling result.
- **P:** PostgreSQL state-machine authority, immutable job binding and idempotent completion transaction.
- **D:** replay, concurrency, illegal-transition, cancellation and browser polling tests.
- **R:** append reconciliation evidence and reload database authority; never edit terminal state in place.
- **S:** stop D11/D12 when UI cannot faithfully reproduce authoritative state.
- **Owner / status / blocked:** backend + Web owners / `OPEN` / D11, D12.

## R-DEMO-13 — Schedule produces infrastructure but no runnable vertical slice

- **Probability / impact:** High / High
- **Description:** broad scope consumes the Alpha window without a real Web→API→DB→Worker→algorithm flow.
- **Early signal:** day-10 has only schema/scaffolding, routes remain 501 across the primary flow, no real page is runnable.
- **P:** dependency-aware vertical integration and Runnable Alpha checkpoint without deleting final scope.
- **D:** day-10 to day-14 real-flow review with actual authority/runtime evidence.
- **R:** stop new non-blocking infrastructure and finish the ready vertical integration; reforecast bounded recovery honestly.
- **S:** do not cut tables/APIs/tools/rebuild or relabel incomplete work PASS to preserve a date.
- **Owner / status / blocked:** Principal / `OPEN` / schedule and Alpha.

## R-DEMO-14 — Prototype is mistaken for formal P3–P7 authority

- **Probability / impact:** Medium / Critical
- **Description:** docs/API/UI/migration or summary omits Demo-only status or claims production/real-user validity.
- **Early signal:** missing banner/`x-demo-only`, unqualified `PASS`, formal migration numbering or production wording.
- **P:** ADR/contract/banner/track labels and fixed final conclusion scope.
- **D:** static status/claim scan and independent review at each authority checkpoint.
- **R:** correct the claim and affected contract/evidence before integration or push; do not rewrite historical results silently.
- **S:** stop push and acceptance while a formal/production ambiguity remains.
- **Owner / status / blocked:** Principal / `OPEN` / all checkpoints and push.

## R-DEMO-15 — Repository visibility change creates asset/IP exposure

- **Probability / impact:** Low / Critical
- **Description:** remote becomes public/unknown or a push would expose prototype/private references unexpectedly.
- **Early signal:** visibility query unavailable, repository identity mismatch, remote URL changed or visibility differs from prior evidence.
- **P:** no private bytes in Git and read-only visibility verification immediately before first push.
- **D:** exact remote/repository identity and visibility response captured without credentials.
- **R:** keep work local and resolve repository authority/visibility with Owner; never work around an unknown state.
- **S:** unknown or changed visibility means no push.
- **Current evidence:** `yangyy816/project-mirror` was read-only verified as `PUBLIC` immediately before the D01-A
  acceptance closure; the reviewed candidate had no private locator/bytes and Gitleaks reported zero findings.
- **Owner / status / blocked:** Principal / `MITIGATED_MONITORED` / every later push requires the same recheck.

## R-DEMO-16 — Formal Job cannot express Demo ownership

- **Probability / impact:** Medium / High
- **Description:** nullable formal owner fields or unguessable IDs are incorrectly treated as Demo authorization.
- **Early signal:** actor/session absent from job lookup, cross-session ID succeeds or one job binds multiple Demo entities.
- **P:** unique immutable `demo_job_binding` with actor/session/entity and binding digest.
- **D:** owner-bound GET/cancel, cross-owner negative, concurrent binding and immutability tests.
- **R:** repair the bridge/schema before opening async routes; quarantine unbound job results.
- **S:** no asynchronous Demo API may open without owner-bound binding authority.
- **Owner / status / blocked:** backend + data owners / `PARTIALLY_MITIGATED` / D01-C and D03–D10 owner-bound API/state-machine integration.

## R-DEMO-17 — D00/worktree circular dependency

- **Probability / impact:** Medium / High
- **Description:** feasibility requires tracked Demo code, but creating that code would bypass the D00 entry Gate.
- **Early signal:** request to create migration/API/Web just to prove a D00 dependency or to load runtime only from a future worktree.
- **P:** Git-external `git archive` sandbox at exact base plus path-neutral runtime smoke.
- **D:** D00 isolation evidence and D01-A official-worktree replay from the same fixed base.
- **R:** repair handoff/loader within D01-A governance scope; rerun the exact smoke without product scaffolding.
- **S:** D00 cannot GO and D01-A cannot open if feasibility depends on future product code.
- **Owner / status / blocked:** Principal / `MITIGATED_MONITORED` / D01.

## R-DEMO-18 — API contract churn blocks Web integration

- **Probability / impact:** High / High
- **Description:** parallel D03–D10 route/schema changes repeatedly invalidate OpenAPI, generated client and D11.
- **Early signal:** multiple generated-client writers, unexplained OpenAPI drift, D11 works against unpublished local types.
- **P:** D01-C complete skeleton, source-only contract edits and a single Principal codegen integrator.
- **D:** OpenAPI diff/drift and generated-client freshness at every API task acceptance.
- **R:** serialize regeneration and repair callers; freeze only after D03–D10 contracts are Principal accepted.
- **S:** D11 cannot start before `DEMO_API_CONTRACT_FREEZE`.
- **Owner / status / blocked:** Principal + Web owner / `OPEN` / D11.

## R-DEMO-19 — Hidden public runtime dependency in deterministic core

- **Probability / impact:** Medium / Critical
- **Description:** P3–P7 core or its dependency silently requires public DNS/HTTP/model/service access at runtime.
- **Early signal:** socket/DNS attempt, proxy variable consumption, public default route use, retry waiting on external host or success only when proxy is enabled.
- **P:** separate D00-A acquisition from frozen D00-B runtime; no proxy in core environment; frozen artifacts and local service topology.
- **D:** process/container public-egress denial with localhost/Docker services still healthy; network-attempt logging and offline replay.
- **R:** classify `EXTERNAL_RUNTIME_DEPENDENCY_FOUND`, remove or vendor only through approved bounded acquisition/change control, then rerun offline Gate.
- **S:** stop the affected core Gate immediately; never silently enable egress. Generative Provider remains unavailable without blocking deterministic core.
- **Owner / status / blocked:** Principal + infra/runtime owners / `MITIGATED_MONITORED` / D03–D12 affected core path.
