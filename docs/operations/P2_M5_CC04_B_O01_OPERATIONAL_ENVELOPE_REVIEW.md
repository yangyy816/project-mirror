# CC04-B-O01 Operational Envelope Review

## Status and authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: CC04-B-O01`
- `TASK_NAME: Operational Envelope, Quota, Accounting, and Stop Review`
- `PARENT_AUTHORITY: P2-M5-R16_AND_REPAIRED_CC04-B-Q01`
- `BASELINE_SHA: c3faa387677de55f565e8e63eeac14d89132f7cd`
- `REVIEW_CANDIDATE: THIS_COMMIT`
- `AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ARTIFACT_SECURITY_PRIVACY_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`
- `PRE_CONDITION_CURRENT_STATE: CC04_B_O01=REVIEW_CANDIDATE_PENDING_ACCEPTANCE; CC04_B_EXECUTION=CLOSED`

This is a review-only checkpoint. It does not create a request queue, counter, ledger, GenerationSpecification, assignment manifest, Prompt, private registry, root, locator, receipt, output, Asset, identity, cohort, holdout, runtime approval, or execution authority. It invokes no generation, Vision, measurement, transform, Provider, or private-input operation.

## Frozen Owner envelope

- `CALIBRATION_REQUEST_CALL_MAX: 32`
- `CALIBRATION_RAW_OUTPUT_MAX: 32`
- `CALIBRATION_ADMITTED_IDENTITY_TARGET: 24 independent cluster-adjusted identities`
- `REQUESTED_OUTPUTS_PER_CALL: 1`
- `GENERATION_CONCURRENCY: 1`
- `AUTOMATIC_RETRY_CEILING: 0`
- `TRANCHE_MAXIMUM_CALLS: 4`
- `SEALED_HOLDOUT_REQUEST_OR_OUTPUT_USE: 0`
- `SEALED_HOLDOUT_RAW_OUTPUT_MAX_RESERVED: 32`
- `SEALED_HOLDOUT_ADMITTED_IDENTITY_TARGET_RESERVED: 24 independent identities`
- `TOTAL_NATIVE_GENERATED_OUTPUT_MAX: 64`
- `TRANSFORM_OPERATION_GLOBAL_HARD_CEILING: 768`
- `TRANSFORM_OPERATION_ALLOWED_IN_04_B: 0`
- `VISION_OR_MEASUREMENT_GLOBAL_HARD_CEILING: 2500`
- `NEW_PRIVATE_OUTPUT_STORAGE_GLOBAL_HARD_CEILING: 8 GiB`
- `EXTERNAL_CASH_BUDGET: 0`
- `PAID_EXTERNAL_PROVIDER_ALLOWED: false`
- `N_48_OR_N_96_EXPANSION: NOT_AUTHORIZED`

The calibration request-call ceiling is deliberately no greater than the raw-output ceiling. A failed or zero-output call consumes its unique request ordinal and is not replaced. An unexpected multi-output response counts every returned output immediately, cannot be partially ignored, and hard-stops before any admission. These stricter operator bounds do not transfer unused calls or outputs to holdout and do not create a new budget.

## Fixed operator-action plan

The later accepted E01 contract may materialize exactly 32 immutable call ordinals, `CAL-REQ-001` through `CAL-REQ-032`. Each ordinal must bind one precommitted Q01 morphology cell, one approved nonsexual style cell, one requested output, the accepted private GenerationSpecification version and digest, the accepted O01/V01/E01 versions, and a unique operator-action ID before its call.

Calls execute in ordinal order in at most eight tranches of at most four calls. A tranche can end early for target, hard stop, request failure, output cardinality mismatch, custody or storage uncertainty, QA blocking evidence, or Owner-envelope exhaustion. Starting a later tranche requires a Principal checkpoint over all append-only counters, storage, custody, rejection, cluster-adjusted N, and coverage evidence from every earlier action.

Exactly one call may be active. The operator must observe a terminal tool response, register the request and every returned output, and reconcile all counters and custody facts before another call starts. No background invocation, parallel tab, sibling Agent, scheduled task, manual duplicate call, alternative Prompt, repeated tool action, or hidden Provider path may overlap or replace an ordinal.

An invocation begins only after the request-attempt entry is durably prepared. Once dispatch starts, its request count is one and can never be decremented. A transport, tool, policy, timeout, operator, zero-output, or unknown failure is final for that ordinal. `retry=0` prohibits automatic retry, manual retry, same-Prompt replay, changed-Prompt replay for the same assignment, SDK/tool retry, and a second call disguised as cleanup or recovery. Proceeding to the next never-used ordinal is allowed only if no hard stop applies.

## Append-only accounting

The later execution ledger must keep request and output accounting separate and append-only:

1. `request_call_count` increments exactly once when a unique ordinal dispatch begins, including failed and zero-output calls;
2. `requested_output_count` increments by one for every dispatched ordinal;
3. `returned_output_count` increments once for every actual output returned before decode, custody, safety, QA, or duplicate review;
4. `raw_output_count` equals all returned calibration outputs, including malformed, unsafe, duplicate, rejected, quarantined, or cleanup-eligible bytes;
5. `failed_call_count` records calls without a conforming terminal output and does not reduce another counter;
6. `rejected_output_count` records completed content dispositions and remains distinct from execution failure;
7. `admitted_identity_count` includes only atomic Q01 admissions that pass every Gate;
8. `effective_cluster_adjusted_identity_count` counts at most one admitted identity per confirmed duplicate cluster and is the only N used for the target;
9. morphology and style occupancy counts derive only from effective cluster-adjusted admissions and the accepted deterministic Q01/R16 measurement authority;
10. every entry binds ordinal, action ID, timestamp, task/spec/policy versions, status, reason code, and previous-entry digest without Prompt, image bytes, private locator, path, key, URL, credential, or free-text facial judgment.

No rejection, failure, cleanup, duplicate cluster, identity consolidation, or evidence correction refunds request, requested-output, returned-output, raw-output, Vision/measurement, or cumulative storage accounting. Corrections are new append-only facts; counters are never rewritten to manufacture remaining quota.

## Storage and operation ledgers

Before E01 acceptance, its contract must freeze an exact per-call and per-output maximum byte reservation covering returned bytes, canonical normalized bytes, required immutable private derivatives, custody metadata, and bounded transient copies. A call cannot start unless the worst-case reservation fits below 8 GiB.

The private storage ledger must track both cumulative newly materialized private bytes and peak live new private bytes. Each exact registered object records expected and actual bytes under P01 custody. Deletion or cleanup may reduce live bytes only after bounded verification; it never decreases cumulative bytes or erases the request/output/rejection audit facts. Either cumulative or peak live bytes reaching the 8-GiB ceiling stops further writes and calls. Unknown size, unregistered bytes, locator loss, path uncertainty, or a projected overflow hard-stops before the next operation.

Every admitted QA Vision or measurement operation increments a separate append-only global counter before execution. E01 must precompute the exact maximum per output and prove the worst case stays within the remaining 2500-operation ceiling. Failed, missing, repeated-for-reliability, platform, or negative-control operations count. No 04-B transform is allowed, so the transform counter remains zero and the 768 ceiling cannot be borrowed as Vision budget.

## Stop-on-target and stop-on-exhaustion

`CALIBRATION_COHORT_READY` occurs only when all of the following are simultaneously true:

- exactly 24 effective cluster-adjusted admitted identities exist;
- every Q01 morphology and nonsexual style cell contains at least three and at most six effective identities;
- all source, adult, safety, custody, runtime qualification, deterministic morphology, QA, duplicate, isolation, and evidence Gates pass;
- all request, output, operation, storage, and cluster counters reconcile.

The moment this condition is reached, the current action is reconciled and execution stops. No remaining ordinal may be called for replacement, aesthetic preference, balance improvement, additional diversity, reserve, comparison, or future holdout use.

`FURTHER_RESEARCH_RESOURCE_ENVELOPE_EXHAUSTED` is mandatory when either 32 unique request calls or 32 raw calibration outputs are exhausted before cohort readiness, or when the remaining legal ordinals cannot reach 24 and all occupancy minima. It does not authorize a 33rd call, retry, quota refund, holdout borrowing, 48/96 expansion, or relaxed QA/coverage rule.

Immediate hard stops also include: unaccepted V01 or E01; specification, assignment, runtime, model, digest, platform, policy, custody, locator, or counter mismatch; hidden network or telemetry; Prompt/private-field leakage; unexpected output cardinality; 8-GiB or 2500-operation projection/overflow; any attempt to transform, access holdout, use paid/external Provider, create a second root, reuse legacy input, override an adult/safety/duplicate/reliability failure, select by downstream performance, or open 04-C through 04-E, MVR, M6, production, real-user processing, or P2-M7.

## Quota isolation and no transfer

Calibration and sealed-holdout requests, outputs, identities, assignments, roots, locators, manifests, counters, storage facts, and duplicate evidence remain separate. O01 authorizes zero holdout calls and zero holdout bytes. Unused, failed, rejected, or cleaned calibration capacity cannot move to holdout, and the 32 holdout outputs cannot move to calibration. The 64 total-output ceiling is an additional hard ceiling, not a pool that relaxes either 32-output cohort ceiling.

No paid cash, Provider credit, retry budget, concurrency slot, storage deletion, transform operation, Vision operation, legacy output, previous identity, or later milestone budget may substitute for exhausted calibration quota.

## Review result and exact sequencing

- `OPERATIONAL_ENVELOPE_REVIEW: PASS`
- `PASS_SCOPE: FUTURE_04_B_PRIVATE_SYNTHETIC_CALIBRATION_OPERATOR_ACTIONS_ONLY`
- `REQUEST_QUEUE_CREATED: NO`
- `COUNTER_OR_LEDGER_CREATED: NO`
- `PRIVATE_ROOT_OR_LOCATOR_CREATED: NO`
- `GENERATION_OR_VISION_EXECUTED: NO`
- `CC04_B_PREEXECUTION_REVIEW_DAG: 5_OF_5_PASS_AFTER_THIS_COMMIT_ACCEPTANCE`
- `NEXT_REQUIRED_TASK: CC04-B-V01`

After this exact commit passes same-SHA CI, all eight artifacts, independent Security/Privacy/Research Integrity, independent Sol High, and Principal acceptance, the T01 five-review DAG is complete. Execution remains closed. The next task must be the separate R16-mandated V01 runtime qualification review; only after V01 acceptance may the separate E01 execution contract be created and accepted. No generation or private capability may be created in O01 or V01.

Acceptance requires exact parent and three-path allowlist; scoped Markdown formatting and `git diff --check`; exact Owner-value, request/output separation, ordinal, tranche, concurrency, zero-retry, no-refund, storage, Vision, transform-zero, holdout-isolation, target/exhaustion, hard-stop, and no-hidden-call scans; no generation/private mutation/binary/leakage; true-EOF sentinel, last-occurrence, and canonical/mirror equality; then all same-SHA remote and independent-review Gates.
