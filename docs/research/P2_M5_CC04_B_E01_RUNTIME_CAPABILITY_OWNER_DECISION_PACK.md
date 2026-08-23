# P2-M5 CC04-B E01 Runtime Capability Owner Decision Pack

## Authority and observed blocker

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: CC-P2-M5-04-B-E01-CAPABILITY-GATE`
- `DECISION_ID: OD-P2-M5-CC04-B-E01-001`
- `DECISION_STATUS: OWNER_DECISION_REQUIRED`
- `OBSERVED_AT_SHA: 9408859043a776934084a221f675378330c74742`
- `R18_ACCEPTED_CI_RUN: 32630571812`
- `R18_PRINCIPAL_ACCEPTANCE: GRANTED`
- `CURRENT_EXECUTION_RESULT: BLOCKED_SECURITY_PRIVACY_LICENSE`
- `SPECIFIC_STOP_REASON: PRIVATE_OUTPUT_SINK_AND_ACTUAL_HUMAN_REVIEW_CAPABILITY_NOT_PROVEN`

R18 and the E01 execution contract remain accepted documentation authority. This pack records a runtime capability
failure discovered before private setup and before request ordinal `CAL-REQ-001`. It does not retract R18, alter the
duplicate-review policy, consume a request or output, create a private root or locator, or authorize a replacement
Provider, runtime, dependency, reviewer, threshold, or workflow.

## Facts

1. The accepted source remains `CODEX_NATIVE_IMAGEGEN` for private internal synthetic research only.
2. E01 requires generated output to enter one Principal-custodied, Git-external, recoverable private registry/root with
   digest, type, byte count, authority, scope, retention, and cleanup evidence.
3. Prompt plaintext, Provider payload, image bytes, private path, locator, object key, URL, credential, and secret must
   not enter Git, ordinary logs, CI artifacts, MEMORY, ordinary reviewer packets, or tracked evidence.
4. R17/R18 requires exactly one Project Owner or Owner-designated actual-human review for every unordered pair of
   canonically normalized returned outputs. An Agent or model cannot substitute.
5. The human channel must privately present only the two canonical outputs and allowlisted pair evidence, then record an
   append-only decision with pseudonymous human actor, policy digest, pair IDs/digests, reason code, and timestamp.
6. The exposed native image-generation tool accepts a Prompt and reference selectors but exposes no destination-root,
   private-sink handle, registry callback, transcript-suppression contract, or custody receipt parameter.
7. The exposed local image-view tool returns a data URL to the Agent. The UI-open capability opens a file/browser tab
   but does not authenticate the human reviewer or capture an append-only allowlisted decision.
8. Shell access cannot intercept or redirect native image-generation output and cannot turn an Agent/model decision into
   actual-human evidence.
9. Two independent read-only reviews, Security and Sol High, therefore returned `BLOCKED` before private setup or the
   first generation call.
10. Current counters remain zero and no private execution state exists.

## Frozen non-decisions

This pack does not reopen or change:

- the 32 calibration raw / 24 admitted target;
- the 32 sealed-holdout raw / 24 admitted target;
- 64 total outputs, concurrency one, retry zero, external cash budget zero;
- the 768 transform, 2500 inclusive Vision/measurement/governed-human-review, or 8 GiB storage ceilings;
- the all-pairs actual-human duplicate-review policy or its RFC 8259 binding;
- adult/safety, synthetic-only, no-real-person, no-sensitive-inference, no-beauty-score, custody, holdout, 04-C through
  04-E, MVR, M6, production, real-user, QuestionBank, or P2-M7 boundaries.

Agent/model substitution, an automatic duplicate threshold, transcript attachments, copying native output from a
conversation/cache, broad private discovery, or retroactive custody registration are not selectable options.

## Option A — provision the two missing native capabilities

`OPTION_A: PROVISION_DESTINATION_BOUND_PRIVATE_SINK_AND_AUTHENTICATED_ACTUAL_HUMAN_REVIEW_CHANNEL`

The Owner or platform provides a Codex-native capability with both:

1. destination-bound output directly into a task-scoped recoverable Principal private registry/root, returning only
   redacted metadata and a custody receipt while suppressing Prompt, bytes, path, locator, URL, and Provider payload from
   ordinary thread/tool output; and
2. a private authenticated actual-human pair-review interface that records the exact append-only allowlisted evidence
   required by R17/R18.

Before E01 resumes, the capability itself must receive a separate bounded contract, exact interface and threat model,
local evidence, Security/Privacy/License/Research review, Sol High review, and Principal acceptance. The first call may
occur only after a new execution-authority checkpoint proves both capabilities and preserves all existing counters.

- Cost: platform or engineering work; time and credits currently `UNKNOWN`; external cash remains `0` only if the
  accepted native platform supplies the capability without a paid external Provider.
- Security/privacy: strongest continuity with accepted custody and least privilege, but only if transcript suppression,
  recoverability, actor authentication, append-only decisions, and cleanup are proven rather than inferred.
- License/source: no new Provider or model is approved by selecting this option.
- Recommendation: `RECOMMENDED`, because it preserves the accepted source, reviewer, budget, and research design.

## Option B — suspend E01 and retain the fail-closed state

`OPTION_B: SUSPEND_CC04_B_E01_WITH_ZERO_CALLS`

Do not provision a new runtime and do not execute calibration acquisition. P2-M5 remains `EXECUTING` but blocked at
04-B; MVR stays unevaluated and M6 remains closed.

- Cost: no additional generation, storage, Provider, or implementation cost.
- Security/privacy/license: lowest immediate risk; all private and production boundaries remain closed.
- Research impact: the fresh-evidence line cannot produce a calibration cohort, so 04-C through 04-E, technical Gate,
  MVR, and M6 cannot proceed.
- Default: `FAIL_CLOSED_DEFAULT_IF_OWNER_DOES_NOT_SELECT_AND_PROVISION_OPTION_A_OR_C`.

## Option C — open explicit runtime/provider change control

`OPTION_C: NEW_RUNTIME_PROVIDER_OR_REVIEW_WORKFLOW_CHANGE_CONTROL`

Consider a different API, CLI, browser workflow, storage mechanism, Provider, dependency, or review system only through
new Owner-approved change control. The proposal must identify exact Provider/runtime/model/dependency, data flow,
network boundary, telemetry, terms, provenance, cost, credentials, private storage, reviewer authentication, retention,
cleanup, and reproducibility. It must be separately qualified and accepted before any output or private state exists.

- Cost: `UNKNOWN`; may violate the accepted zero-cash or native-source decision and therefore may require a revised
  Owner resource/provider decision.
- Security/privacy/license: highest review burden and largest change surface.
- Research impact: may restore execution only after requalification and prospective contract acceptance.
- Recommendation: `NOT_RECOMMENDED_WHILE_OPTION_A_IS_FEASIBLE`; never use as an implicit fallback.

## Required Owner response

The Owner must choose exactly one of `OPTION_A`, `OPTION_B`, or `OPTION_C`. Silence preserves Option B. A response that
only says “continue” does not prove the missing capability and cannot consume `CAL-REQ-001`. Selecting Option A must be
accompanied by an externally provisioned capability or explicit authorization and evidence sufficient to define its
separate bounded qualification task. Selecting Option C must identify the proposed changed mechanism and accepts that
new provider/runtime/dependency, budget, license, privacy, and security review may be required.

## Current fail-closed evidence

- `PRIVATE_OUTPUT_SINK_CAPABILITY: NOT_PROVEN`
- `ACTUAL_HUMAN_DUPLICATE_REVIEW_CAPABILITY: NOT_PROVEN`
- `PRIVATE_ROOT_OR_LOCATOR_CREATED: NO`
- `GENERATION_SPECIFICATION_CREATED: NO`
- `GENERATION_CALLS_EXECUTED: 0`
- `RAW_OUTPUTS_CREATED: 0`
- `ASSET_IDENTITY_OR_COHORT_CREATED: NO`
- `REQUEST_ORDINAL_CONSUMED: NONE`
- `NEXT_ACTION: WAIT_FOR_OWNER_SELECTION_AND_REQUIRED_EXTERNAL_CAPABILITY_OR_CHANGE_CONTROL`

No post-hoc explanation, Agent review, model judgment, ordinary chat attachment, hidden tool assumption, or successful
R18 CI can substitute for the two missing execution capabilities.
