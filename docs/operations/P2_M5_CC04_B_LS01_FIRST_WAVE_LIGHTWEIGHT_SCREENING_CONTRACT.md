# P2-M5 CC04-B LS01 First-Wave Lightweight Synthetic Image Screening Contract

## Status, authority, and scope

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: CC04-B-LS01`
- `TASK_NAME: First-Wave Lightweight Synthetic Image Screening Contract`
- `OWNER_DECISION_ID: OD-P2-M5-CC04-B-MR01-002`
- `BASELINE_SHA: 8d204caa87a1ee5e1ddb5d1d4da2ff7ed9b973c4`
- `BASELINE_CI_RUN: 32717363183`
- `BASELINE_AUTHORITY: p2-m5-cc04-b-mr01-stage2a-runtime-capability-inventory-eof/v1`
- `LIGHTWEIGHT_REVIEW_POLICY_VERSION: p2-m5-cc04-b-first-wave-lite-screening-v1`
- `AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`

This is a prospective, document-only reduced-assurance change control for synthetic-only, non-user,
non-production, offline first-wave screening. It creates no image, private root, registry, locator, generation
specification, Prompt, ledger, reviewer input/output, model call, image-generation call, Asset, identity, cohort,
QuestionBank entry, revocation, or human-review queue. All LS01, MR01, and formal-E01 execution counters remain zero.
Historical TS01 qualification accounting is not LS01 execution and remains preserved as prior evidence.

## Historical strict assurance disposition

The accepted Stage-2A result remains historical fail-closed evidence:

- `MR01_STAGE2A_STRICT_RUNTIME_INVENTORY: BLOCKED_AT_8D204CAA87A1EE5E1DDB5D1D4DA2FF7ED9B973C4_RUN_32717363183`
- `STRICT_SOL_MAX_REVIEWER_CAPABILITY: NOT_PROVEN`
- `STRICT_ROUTE_LEVEL_PROVENANCE: BLOCKED`
- `STRICT_RUNTIME_ASSURANCE_MODEL: HISTORICAL_FAIL_CLOSED_EVIDENCE`

For first-wave synthetic Beta preliminary screening only, the Owner prospectively supersedes the strict MR01
assurance model. This does not claim route receipts, snapshots, tool isolation, private pair views, trusted envelopes,
authority clocks, or exactly-once reviewer sinks are proven. It does not authorize their use or rewrite their result.
Deferred strict MR01 fixture/runtime qualification is not a prerequisite for LS01 or its separate E01 checkpoint.

## Permitted assurance model and independence

- `REVIEW_MODEL_PREFERENCE: gpt-5.6-sol / max when available`
- `ALLOWED_SOL_FALLBACK: gpt-5.6-sol / high`
- `OUTSIDE_SOL_FAMILY_FALLBACK: PROHIBITED`
- `REVIEW_ASSURANCE: PRELIMINARY_ADVISORY_ONLY`
- `INDEPENDENCE_CONTROL: PROMPT_AND_CONTEXT_SEPARATION`

Each group review must use a fresh, independent review-only Sol context. The reviewer must not read generator
scratchpad, generate or modify an image, select user preferences, decide production eligibility, or self-review its
own generation. A result is advisory screening evidence only; it cannot establish duplicate or identity authority,
M5 technical PASS, MVR PASS, production approval, public release, or permanent QuestionBank value.

## Source, custody, and non-execution boundary

Formal source remains `CODEX_NATIVE_IMAGEGEN` through the Codex Desktop native image-generation tool. Accepted TS01
authority permits only its exact returned generated-artifact path to be copied create-new into authorized Git-external
staging, verified by SHA-256/type/size/dimensions, and promoted into Principal custody. Export failure is a hard stop
and must not retry generation.

No image byte, Prompt, local absolute path, locator, object key, signed URL, credential, raw tool payload, or reviewer
report may enter Git, commit messages, normal CI artifacts, MEMORY, or ordinary status. Tracked evidence may contain
only opaque receipts, group/image IDs, digests, counters, model actions, and human-review status. Exact storage paths
may be disclosed only in direct Owner output after a real group exists; this contract creates none.

## Future group protocol

After a separately accepted E01 lightweight execution-authority checkpoint, one serial tranche contains at most four
calls and becomes one `CAL-GRP-###` group. Each result is untrusted until deterministic hard QA completes. Per new
image, pHash may rank at most three nearest candidates from the new group or retained first-party images; pHash is
ranking only, never identity authority. No all-pairs model review is authorized.

| Deterministic hard gate                                                              | Required result                                          |
| ------------------------------------------------------------------------------------ | -------------------------------------------------------- |
| Raw SHA-256 equal                                                                    | `REJECT_EXACT_DUPLICATE`                                 |
| Normalized SHA-256 equal                                                             | `REJECT_NORMALIZED_DUPLICATE`                            |
| Decode failure                                                                       | `REJECT_MALFORMED`                                       |
| Face count is not exactly one                                                        | `REJECT_FACE_COUNT`                                      |
| Clearly-adult presentation cannot be confirmed                                       | `FLAG_HUMAN_PRIORITY_AND_EXCLUDE_FROM_BETA_UNTIL_REVIEW` |
| Obvious text, watermark, brand, abnormal background, severe crop, or prohibited pose | `REJECT_OR_FLAG`                                         |

The reviewer may determine only obvious/suspected same synthetic identity, severe artifact, one permitted face,
protocol conformance, obvious text/watermark/composite/abnormal content, a keep recommendation, and human-review
priority. It must not judge beauty, preference, numeric age, race/ethnicity/nationality/ancestry, personality, named
identity, celebrity similarity, sensitive traits, production readiness, or final QuestionBank value.

## Private reports and operation limits

Each actual group creates one Git-external JSON and one Owner-readable Markdown report. Each binds the group ID, Sol
family/available reasoning, `PRELIMINARY_ADVISORY_ONLY`, owner-visible storage location, every opaque image ID,
filename, SHA-256, deterministic QA, model action, reason codes, brief non-sensitive comment, human status, bounded
duplicate-suspect list, group decision, and human-second-round requirement. Parser failure is
`FLAG_FOR_HUMAN_SECOND_ROUND`; it must not trigger another model call.

- `FORMAL_E01_LIGHTWEIGHT_GROUP_REVIEW_MAX: 8`
- `FORMAL_E01_TARGETED_DUPLICATE_FOLLOWUP_MAX: 8`
- `FORMAL_E01_TOTAL_MODEL_SCREENING_MAX: 16`
- `FORMAL_E01_LIGHTWEIGHT_GROUP_REVIEW_EXECUTED: 0`
- `FORMAL_E01_TARGETED_DUPLICATE_FOLLOWUP_EXECUTED: 0`
- `FORMAL_E01_TOTAL_MODEL_SCREENING_EXECUTED: 0`
- `GROUP_REVIEW_RETRY: 0`
- `DUPLICATE_FOLLOWUP_RETRY: 0`
- `SECOND_OPINION: 0`
- `SCREENING_GROUP_SIZE_MAX: 4`

Unused screening operations never transfer to generation. Calibration remains at most 32 calls/32 raw outputs, target
24 provisional independent identities, serial concurrency one, automatic retry zero, tranche maximum four, and each
`CAL-REQ` ordinal exactly once. This document consumes none of them.

## Human second round and downstream closure

`KEEP_FOR_BETA_CANDIDATE` may enter a provisional M5 cohort and, only after future M5/MVR Gates, an invite-only-Beta
candidate draft. `FLAG_FOR_HUMAN_SECOND_ROUND` and `DUPLICATE_SUSPECT` do not count as independent identities and have
exposure cap zero before human review. `REJECT_HARD` never enters a cohort or QuestionBank; audit facts persist while
bytes follow retention cleanup.

All retained items carry `HUMAN_REVIEW_STATUS: PENDING_SECOND_ROUND`. Later human results are append-only and override
the preliminary model through `HUMAN_KEEP`, `HUMAN_REVOKE`, or `HUMAN_NEEDS_REPLACEMENT`; revocation/exclusion stops
future selection without deleting historical testing references. Before that review, the maximum downstream scope is
`INVITE_ONLY_BETA_PENDING_HUMAN_SECOND_ROUND`, never production, public, general availability, or permanent release. A
future M6 release contract must set exposure cap 1--20, human review within seven calendar days of first exposure,
immediate revocation, and audit logging.

Formal E01, acquisition, 04-C/04-D/04-E, M5 disposition, MVR, M6 release, real/user data, and production remain
closed. Only a separate E01 checkpoint may create private execution state or make the first native call after LS01
acceptance.

## Validation and acceptance

This candidate may modify only this contract, its policy, and canonical/mirror tails. It may not modify code, schema,
migrations, dependencies, workflows, MODEL/MEMORY/shared summaries, P2-M7, custody, counters, or any source/output.
Required evidence is scoped Markdown formatting, diff check, changed-path allowlist, source/limits/zero-state scans,
private-leak scan, canonical/mirror true-EOF equality, normal push, same-SHA CI, all eight artifact checks,
independent Security/Privacy/License/Research Integrity review, independent Sol High review, and Principal acceptance.
Acceptance authorizes only the next E01 checkpoint, not image generation.

## P2-M5-R26 authority and counter repair

This forward repair preserves failed candidate `434bda62872a44b66923bab802ebdff3c50b3f55` and corrects only two
LS01 authority defects identified by independent Sol High review. The historical strict-runtime fact remains
`STRICT_RUNTIME_ASSURANCE_MODEL: HISTORICAL_FAIL_CLOSED_EVIDENCE`. The new, separate policy key is
`STRICT_MR01_ASSURANCE_MODEL: SUPERSEDED_PROSPECTIVELY_FOR_FIRST_WAVE_SYNTHETIC_BETA_ONLY`. The explicit three zero
screening execution counters above apply only to future LS01 operations; they neither erase nor relabel TS01 history.
No execution, byte, review call, generation, E01 action, or resource counter changes in this repair.
