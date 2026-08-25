# P3–P7 Demo Risk Register

## Register authority

```text
REGISTER_VERSION: p3-p7-demo-risk-register-v1.1-d02-r2-revision5-candidate
TRACK: DEMO_PROTOTYPE
OWNER: TERRA_HIGH_PRINCIPAL
REVIEW_CADENCE: every D checkpoint and immediately after a trigger
ALLOWED_STATUS: OPEN | MITIGATED_MONITORED | TRIGGERED | RECOVERING | CLOSED | ACCEPTED_RESIDUAL
```

This is a continuous register. `CLOSED` requires evidence; a D00 mitigation does not erase the risk. Each entry records
the required description, probability, impact, early signal, mitigation, contingency, owner, status and blocked tasks.
P/D/R/S mean Prevention, Detection, Recovery and Stop Rule.

## R-DEMO-01 — Legacy D00 M3 runtime/asset custody locator unavailable

- **Probability / impact:** Medium / Critical
- **Description:** the original accepted D00 per-item registry/receipt binding cannot be resolved. This is the immutable
  CC07 legacy-custody incident; it is not a claim that newly created, independently registered R2 authority is missing.
- **Early signal:** registry miss, stale custody, missing byte size, digest mismatch or a request to scan storage.
- **P:** append-only registry, exact receipt/digest/size/authority, downstream retention check before cleanup.
- **D:** only a new exact original D00 task-scoped lead may re-open legacy recovery. R2 independently resolves its new
  opaque IDs from the new root and two-copy registry before every use.
- **R:** the one pre-registered receipt/task-owned-root recovery was exhausted on 2026-08-25. Reopen only if the original
  accepted D00 task-scoped registry/receipt becomes available; a new authority ID cannot replace the lost historical
  binding.
- **S:** `NO_GO_CRITICAL_DEPENDENCY_UNAVAILABLE` permanently stops `OLD_D00_RECOVERY` and the legacy D02 source chain.
  It does not stop the separately accepted forward-only R2 path; R2 still fails closed on any new custody miss. Never ask
  Owner to recreate Principal-owned output or broad-scan disks.
- **Incident evidence:** the bounded audit covered 239 known prior receipt files and 9,922 actual tool outputs. Five
  outputs named all four targets, but zero contained the required per-item digest/byte-size/authority/custody binding or
  a resolvable registry reference. Three known standard custody namespaces also had zero exact registry matches.
- **Owner / status / blocked:** Principal / `ACCEPTED_RESIDUAL` / `OLD_D00_RECOVERY`, legacy D02 source chain. Forward R2
  and downstream nodes remain dependency-blocked until D02-R2 acceptance, but not by this legacy locator risk.

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
- **Description:** fewer than two of jaw width, chin height and eye spacing survive the complete R2 24-candidate-pair
  screening universe and permit the frozen 16-pair selected bank.
- **Early signal:** wrong measured direction, excessive non-target drift, lock conflict, checksum instability or systematic artifact.
- **P:** D02-R2 preregisters all three candidate dimensions and same-source/opposite-direction pair QA before any
  QuestionBank admission; no old D00 screening result substitutes for R2 execution.
- **D:** screen `4 identities × 3 dimensions × 2 magnitudes = 24` candidate pairs with every required QA field, then
  select exactly two eligible dimensions and `4 × 2 × 2 = 16` pairs by frozen priority with deterministic replay.
- **R:** bounded dimension recovery/redesign using the remaining candidate; preserve failed evidence and the two-dimension target.
- **S:** mark `P4_MULTI_DIMENSION_ACTIVE_ROUTING: BLOCKED` and platform `FAIL`; continue only independent P3/P5/P6/P7 work.
- **Owner / status / blocked:** Principal + P4/P6 owners / `OPEN` / D02-R2 acceptance, D04-B, D12.

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
  acceptance closure. It was reverified as the same `PUBLIC` repository before D01-C repair push; the exact candidate
  had no private locator/bytes, the local Gitleaks 8.28.0 scan reported zero findings and exact-SHA CI secret-scan passed.
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
- **Description:** parallel D03–D10 route/schema changes repeatedly invalidate OpenAPI, generated client and D11, or a
  pure domain `TASK_ACCEPTED` is mistaken for completed route/application integration and truthful capability support.
- **Early signal:** multiple router/generated-client writers, unexplained OpenAPI drift, D11 works against unpublished
  local types, a provider-owned route remains 501 after its domain task is accepted, or capability availability changes
  without owner-bound application and Worker evidence.
- **P:** D01-C complete skeleton, source-only provider edits, a single Principal router/codegen integrator and the
  explicit non-D-task `DEMO_API_APPLICATION_INTEGRATION` checkpoint before contract freeze.
- **D:** the 23-operation provider/central/state matrix, route-501 inventory, capability-cohort truth check, OpenAPI
  diff/drift and generated-client freshness at every API acceptance boundary.
- **R:** apply `CC-P3-P7-DEMO-API-08` forward-only, keep historical domain acceptance scoped, serialize central wiring
  and regeneration, repair callers, then independently review application integration and exact contract bytes.
- **S:** no capability may leave `NOT_IMPLEMENTED` from domain acceptance alone; D11 cannot start until
  `DEMO_API_APPLICATION_INTEGRATION: TASK_ACCEPTED` and `DEMO_API_CONTRACT_FREEZE` both pass.
- **Current evidence:** D01-C freezes the complete 23-operation skeleton at `3523d61`, with one OpenAPI/codegen
  integrator, zero regeneration drift, generated TypeScript freshness/typecheck and exact-SHA CI PASS. D09 is accepted
  for ledger/Final Save domain only while its two public adapters remain 501; generic Job GET/cancel also remains a
  D01-C contract skeleton. `CC-P3-P7-DEMO-API-08` inserts central application integration before freeze without
  reopening either historical acceptance or D02.
- **Owner / status / blocked:** Principal + Web owner / `MITIGATED_MONITORED` /
  `DEMO_API_APPLICATION_INTEGRATION` and D11; D02 transitive blocker remains independently active.

## R-DEMO-19 — Hidden public runtime dependency in deterministic core

- **Probability / impact:** Medium / Critical
- **Description:** P3–P7 core or its dependency silently requires public DNS/HTTP/model/service access at runtime.
- **Early signal:** socket/DNS attempt, proxy variable consumption, public default route use, retry waiting on external host or success only when proxy is enabled.
- **P:** separate D00-A acquisition from frozen D00-B runtime; no proxy in core environment; frozen artifacts and local service topology.
- **D:** process/container public-egress denial with localhost/Docker services still healthy; network-attempt logging and offline replay.
- **R:** classify `EXTERNAL_RUNTIME_DEPENDENCY_FOUND`, remove or vendor only through approved bounded acquisition/change control, then rerun offline Gate.
- **S:** stop the affected core Gate immediately; never silently enable egress. Generative Provider remains unavailable without blocking deterministic core.
- **Owner / status / blocked:** Principal + infra/runtime owners / `MITIGATED_MONITORED` / D03–D12 affected core path.

## R-DEMO-20 — Synchronous semantic idempotency authority missing

- **Probability / impact:** High / High
- **Description:** a synchronous creating API uses transient formal coordination, memory state, JSONB-only keys or a
  fake asynchronous Job, so replay/concurrency can create multiple durable responses or lose owner/session authority.
- **Early signal:** a creating POST has no immutable target binding, `DemoJobBinding.job_id` is proposed as nullable,
  an expiring `idempotency_records` row is called permanent authority, or concurrent retries create two targets.
- **P:** separate immutable `demo_command_bindings` from asynchronous `demo_job_bindings`; freeze six operation/typed
  response mappings, actor/session ownership, request digest and response status in `CC-P3-P7-DEMO-D01B-02`.
- **D:** real PostgreSQL same-key concurrency, same/different digest replay, wrong owner/session/type/status/target,
  immutable update/delete, typed response uniqueness and migration lifecycle tests.
- **R:** keep D01-C closed, add only the branch-local forward prototype migration, repair target/application
  transaction integration and rerun D01-B from the new exact Demo head.
- **S:** no synchronous creating Demo route may return success or be included in contract freeze until CC02 is
  Principal-accepted; no fake Job or in-memory fallback is permitted.
- **Current evidence:** D01-C stopped before implementation; CC02 now has a forward prototype migration, immutable
  typed-response authority, 63 focused schema tests, full API/Worker replay, migration lifecycle, concurrency, zero
  formal-DDL drift and independent Sol High `PASS / ACCEPT` for exact candidate `6981a88`. D01-C exact repair
  `3523d61` adds PostgreSQL replay-first coordination, stateful questionnaire/cancelled-Job replay tests, single-winner
  concurrency and typed target/digest contracts; the LF-faithful full suite passed `816`, exact-SHA CI passed all three
  jobs and Sol High reported no new mandatory finding.
- **Owner / status / blocked:** Principal + data/backend owners / `MITIGATED_MONITORED` / D01-C accepted; later route
  implementations must reuse this authority and may not introduce in-memory or fake-Job fallbacks.

## R-DEMO-21 — Formal CI evidence generator rejects prototype migration head

- **Probability / impact:** High / High
- **Description:** shared CI asks a formal Phase 1/P2 evidence generator to accept the branch-local Demo migration head,
  either failing every Demo run after valid tests or tempting implementation to weaken the formal `0014` authority.
- **Early signal:** executable Python/PostgreSQL/Celery/Web/contract Gates pass, then evidence generation reports that
  migration head evidence does not contain the single expected formal head.
- **P:** keep formal evidence generators and their `0014_m5_eval_authority` threshold unchanged; route only the fixed
  Demo branch/head PR to a separate prototype-boundary witness.
- **D:** same-SHA CI asserts the exact single Demo head, both formal-to-demo ancestry edges, a separately named artifact
  and continued execution of dependency/SBOM/Docker/Gitleaks Gates.
- **R:** add branch-local CI conditionals and rerun the exact repair SHA; never relabel Demo migration evidence as
  Phase 1/P2 evidence.
- **S:** any condition that suppresses formal evidence on main/formal branches, accepts a Demo head as formal, or skips
  executable quality/integration Gates is rejected.
- **Current evidence:** run `32631450833` failed only at `Generate Phase 1 CI evidence`; the generator correctly expected
  `0014_m5_eval_authority` while Alembic correctly reported `demo_0002_p3_p7_command_auth` on the Demo branch. The
  branch-local repair then produced exact-SHA run `32636591101`: all three jobs passed, executable quality/integration,
  Docker, browser, dependency and secret Gates remained active, and artifact `9492531462` bound the Demo head while
  preserving `FORMAL_HEAD_AUTHORITY: 0014_m5_eval_authority` and `PRODUCTION_RELEASE: NOT_AUTHORIZED`.
- **Owner / status / blocked:** Principal + CI owner / `MITIGATED_MONITORED` / no D01-C blocker; the conditional remains
  forbidden on main/formal branches.

## R-DEMO-22 — R2 evidence escapes the designated root

- **Probability / impact:** Medium / Critical
- **Description:** an R2 source, receipt, M3/M4 result, QA record or registry is written to a worktree, cache, OS temp,
  ordinary CI artifact, coordination mailbox or a second private root.
- **Early signal:** output has no root-relative name receipt, an absolute locator appears in tracked evidence, or a tool
  returns bytes without a preallocated destination.
- **P:** one exact Git-external root, immutable root name receipt, preallocated per-output name receipts and root-scoped
  producer handles.
- **D:** resolved-path containment before every write; tracked/private-field scans; registry output-to-name reconciliation.
- **R:** mark the outside output unregistered negative evidence, consume its ordinal and quarantine without promotion;
  execution 01 stops, and any replacement requires a new forward change control and allocation.
- **S:** no decode, QA, runtime, database admission or after-the-fact move/rename for an outside-root output.
- **Owner / status / blocked:** Principal / `OPEN` / D02-R2 and every dependent task.

## R-DEMO-23 — R2 name or output-ID collision

- **Probability / impact:** Medium / High
- **Description:** overwrite, automatic suffixing, reused ordinal or an output ID bound to different semantics/bytes
  makes custody ambiguous.
- **Early signal:** destination exists, name receipt mismatch, duplicate allocation sequence or same ID with a different
  canonical payload/digest.
- **P:** create-new exclusive writes, immutable allocation receipts, typed domain-separated IDs and no retry per ordinal.
- **D:** registry unique constraints, file-existence preflight and full semantic/digest collision tests.
- **R:** preserve both facts as negative evidence under different failure receipts; allocate no fallback ID in execution
  01 for a deterministic collision, and require a new forward change control for replacement.
- **S:** `OUTPUT_NAME_OR_ID_COLLISION_STOP`, `OUTPUT_NAME_RECEIPT_PARTIAL_OR_CORRUPT_STOP` or
  `OUTPUT_SEAL_RECEIPT_PARTIAL_OR_CORRUPT_STOP`; no overwrite, suffix, deletion or bank admission.
- **Owner / status / blocked:** Principal + producer / `OPEN` / D02-R2 source and runtime execution.

## R-DEMO-24 — Two private registry copies diverge

- **Probability / impact:** Medium / Critical
- **Description:** registry copies differ in sequence, head event digest, semantic snapshot or resolvable output state.
- **Early signal:** one-sided commit, missing event, SQLite integrity failure, digest mismatch or locator rehash failure.
- **P:** transaction IDs, previous-event chains, durable two-copy writes and immutable commit receipts.
- **D:** compare event count/head/snapshot after every transaction and during fresh-process recovery; inject one-side
  failure before execution.
- **R:** stop; validate the complete surviving chain and every output under a new Principal change control before
  rebuilding the damaged copy. No automatic overwrite.
- **S:** `REGISTRY_INCONSISTENT_STOP`; affected evidence cannot enter M3/M4, PostgreSQL, Report or QuestionBank.
- **Owner / status / blocked:** Principal / `OPEN` / all D02-R2 execution. Both copies share one root, so no media-level
  disaster-recovery claim is made.

## R-DEMO-25 — Legacy D00/CC05 authority contaminates R2

- **Probability / impact:** Medium / Critical
- **Description:** an old output ID, receipt digest, legacy QA snapshot, PostgreSQL row, item reference or reconstructed
  custody value is mapped into the new R2 chain.
- **Early signal:** `RecoveredLegacySyntheticQASnapshot/v1`, old P2/D00 ordinal or CC07 identifier appears in an R2
  source preimage or registry event.
- **P:** new task/epoch/private namespace, new typed schemas and explicit no-alias validation.
- **D:** exact old-marker scan, typed digest separation and PostgreSQL contamination negatives.
- **R:** roll back the R2 transaction, preserve CC07 unchanged and regenerate only under a clean new R2 authority.
- **S:** `HISTORICAL_AUTHORITY_CONTAMINATION_STOP`; never reinterpret or resign the mixed chain.
- **Owner / status / blocked:** Principal / `OPEN` / D02-R2 acceptance and all downstream tasks.

## R-DEMO-26 — New source is forced into recovered-import schema

- **Probability / impact:** High / High
- **Description:** the accepted v3 local-import config is reused for a newly generated R2 source, creating a semantically
  false `DEMO_LOCAL_IMPORTED_COPY` row.
- **Early signal:** a new source proposes `DemoSyntheticIdentity/v3`, old import-config digest or recovered snapshot
  schema; no distinct R2 authority row exists.
- **P:** freeze `D02R2SourceAuthority/v1`, `DemoSyntheticIdentity/v4`, `DEMO_R2_GENERATED_SOURCE` and forward
  `demo_0008_d02_r2_source_auth` before database admission.
- **D:** Python/PostgreSQL mode-matrix, old/new row parity, no-alias and full-resign negative tests.
- **R:** keep producer evidence private, repair the forward prototype schema and rerun lifecycle before any import.
- **S:** `SOURCE_AUTHORITY_SCHEMA_MISMATCH_STOP`; no database Report or QuestionBank write.
- **Owner / status / blocked:** Principal + central data owner / `OPEN` / R2 PostgreSQL admission.

## R-DEMO-27 — Producer output cannot be registered before decode

- **Probability / impact:** High / High
- **Description:** source generation succeeds but lacks a declared sink, immutable name, recoverable locator or both-copy
  registry commit, repeating the prior unregistered-output failure.
- **Early signal:** provider output exists while root/name receipt is absent, or registration cannot seal digest/size
  before decode.
- **P:** root and registry Gate before dispatch; Principal-preallocated exact writable destination and name receipt;
  producer cannot seal or commit registry events.
- **D:** pre-call bootstrap replay, immediate non-decoding magic/SHA/size registration and fresh-process recovery.
- **R:** consume the ordinal and budget, record `SOURCE_OUTPUT_REGISTRATION_FAILED`, do not decode or reuse; execution 01
  stops and any replacement requires a new forward change control with new task/epoch/allocation.
- **S:** no after-the-fact promotion, path guessing, retry under the same ordinal or PostgreSQL admission.
- **Owner / status / blocked:** Principal + source producer / `OPEN` / four-source cohort completion.

## R-DEMO-28 — D02-R2 source generation has no exact accepted capability authority

- **Probability / impact:** High / Critical
- **Description:** a generic native image capability, ADR-026's P2-only offline authorization, local proxy or Owner's
  forward-execution direction is treated as approval of an unspecified D02-R2 tool/provider/model/network/cost contract.
- **Early signal:** dispatch contains generation calls or public egress without an accepted capability-authority digest,
  exact qualification scope, endpoint allowlist, credential boundary, ceilings, terms and create-new sink contract.
- **P:** CC08 authorizes zero generation calls/egress; require a separate Principal authority decision before producer
  dispatch, bind it into the non-circular preregistration/allocation/dispatch chain, and bind it directly in every
  generation receipt.
- **D:** tracked-authority scan, dispatch schema validation, process egress observation and registry equality against the
  accepted capability-authority digest.
- **R:** keep the producer on read-only HOLD; complete a bounded authority decision using an exact candidate or choose a
  separately Owner-approved source-production mechanism. Do not inherit or relabel P2 evidence.
- **S:** `GENERATION_CAPABILITY_AUTHORITY_MISSING`; no provider/tool call, candidate byte, source admission or budget is
  permitted. Core M3/M4 remains public-egress denied.
- **Owner / status / blocked:** Principal / `OPEN` / D02-R2 source production and all downstream D02 execution.

## R-DEMO-29 — CC08 plan acceptance is mistaken for migration implementation authority

- **Probability / impact:** Medium / Critical
- **Description:** acceptance of the forward architecture plan is treated as permission to modify `demo_0008`, central
  ORM or PostgreSQL before a bounded migration/models task, exact review and real-PostgreSQL evidence exist.
- **Early signal:** a migration/model diff, new Alembic head or database admission appears while the only accepted state
  is the CC08 plan/root preflight.
- **P:** freeze `MIGRATION_IMPLEMENTATION=CLOSED_PENDING_SEPARATE_BOUNDED_TASK_AND_PRINCIPAL_ACCEPTANCE` in CC08,
  Routing and Fast Track; keep migration/models under the central single owner.
- **D:** branch diff ownership check, Alembic-head check, PostgreSQL write audit and acceptance-state matrix before every
  D02-R2 dispatch.
- **R:** stop integration, preserve the unauthorized diff as non-accepted evidence, discard/recreate only through an
  approved bounded task without rewriting accepted history.
- **S:** no migration/ORM implementation, database Report or QuestionBank admission until the dedicated task and
  Principal acceptance pass.
- **Owner / status / blocked:** Principal + central data owner / `OPEN` / `demo_0008` and all R2 PostgreSQL admission.

## R-DEMO-30 — Seal-to-intent crash creates ambiguous registry transaction

- **Probability / impact:** Medium / Critical
- **Description:** source bytes and seal are durable, but no complete registry intent exists; recovery invents a
  transaction ID, timestamp, head or commit name, or overwrites a partial intent/commit receipt.
- **Early signal:** sealed output has no deterministic intent file, an intent is partial/corrupt, or A/B already contains
  the output/transaction while recovery claims intent-absent.
- **P:** non-recursive transaction-ID preimage, deterministic locator/name/task policy, intent-bound exact canonical
  event bytes, deterministic commit name, Principal single-writer mutex and create-new intent before copy A.
- **D:** explicit `SEAL_DURABLE_INTENT_ABSENT` and partial-intent fault injection; negative proof against both registry
  tables and exact control names before the sole legal new-intent creation.
- **R:** if truly absent, create the unique intent once after output/name/seal/head replay; if any partial or conflicting
  authority exists, preserve it and stop under a new change control.
- **S:** `REGISTRY_INTENT_PARTIAL_OR_CORRUPT_STOP` or `REGISTRY_COMMIT_RECEIPT_PARTIAL_OR_CORRUPT_STOP`; never
  overwrite, suffix or synthesize missing immutable control fields.
- **Owner / status / blocked:** Principal / `OPEN` / registry preflight and all D02-R2 outputs.

## R-DEMO-31 — Registry genesis or initialization is not reproducible

- **Probability / impact:** Medium / Critical
- **Description:** two SQLite copies use different genesis, metadata, schema/triggers or snapshot preimages, or a crash
  leaves one partially initialized file that is silently recreated.
- **Early signal:** copy metadata/root/contract/genesis differs, unknown tables/triggers exist, one populated copy lacks
  its peer, or zero-event semantic snapshot differs.
- **P:** accepted tracked registry implementation SHA, schema-contract and normalized-DDL digests, exact three-table
  schema with deferred pair FKs, common genesis, fixed copy IDs/metadata, DELETE journaling and closed initialization.
- **D:** fresh-process schema/trigger replay, partial-file and one-copy fault injection, integrity check and A/B
  zero-event/count/head/snapshot equality.
- **R:** only a valid empty single copy may cause exclusive creation of the missing empty copy; any partial, corrupt or
  populated unilateral state requires a new Principal change control.
- **S:** `REGISTRY_INITIALIZATION_CORRUPTION_STOP` or `REGISTRY_INCONSISTENT_STOP`; no automatic clone or database-byte
  overwrite.
- **Owner / status / blocked:** Principal / `OPEN` / root/registry preflight and D02-R2 execution.

## R-DEMO-32 — Valid-looking R2 authorities are spliced across different outputs

- **Probability / impact:** Medium / Critical
- **Description:** independently well-shaped generation, source, QA, supporting-row, identity or manifest payloads are
  mixed so control receipt, capability, provenance, Asset descriptors or attestations come from different candidates.
- **Early signal:** duplicated scalars are shape-valid but unequal, or a validator accepts a full-chain re-sign using a
  different valid source.
- **P:** non-circular preregistration→four immutable allocations→producer dispatch anchor, per-root registry singleton
  uniqueness, direct root→generation→source→QA→supporting-row equality and typed digest/ID domains; no compatibility
  fallback or alias.
- **D:** independent splice negatives for root/contract, output/control receipts, capability/request policy,
  provenance, Asset descriptors, attestations, source/QA and Report/selection.
- **R:** reject the entire mixed authority transaction, retain private bytes as unadmitted negative evidence and rebuild
  only from one registered output chain.
- **S:** `R2_AUTHORITY_SPLICE_DETECTED`; no Identity, Report, QuestionBank or downstream runtime admission.
- **Owner / status / blocked:** Principal + central data owner / `OPEN` / migration implementation, source admission and
  D02-R2 acceptance.
