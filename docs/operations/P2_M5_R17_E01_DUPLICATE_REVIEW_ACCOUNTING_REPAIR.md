# P2-M5-R17 E01 Duplicate Review Accounting Repair

## Status and bounded authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R17`
- `TASK_NAME: CC04-B E01 Deterministic Human Duplicate Review and Accounting Repair`
- `FAILED_CANDIDATE_SHA: 1fd372cd690719d1cd4725d48a4cb4388b7480ec`
- `FAILED_CANDIDATE_RUN: 32628887252`
- `FAILED_CANDIDATE_GATE_EVIDENCE: SAME_SHA_CI_PASS;EIGHT_ARTIFACTS_PASS;SECURITY_PRIVACY_LICENSE_RESEARCH_PASS;SOL_HIGH_FAIL`
- `REPAIR_CANDIDATE: THIS_COMMIT`
- `AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ARTIFACT_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`
- `PRE_CONDITION_CURRENT_STATE: CC04_B_E01=FAILED_PENDING_FORWARD_DUPLICATE_REVIEW_ACCOUNTING_REPAIR;CC04_B_EXECUTION=CLOSED`

The failed E01 candidate remains immutable Git history. This forward Repair preserves every passing Gate and repairs
only the mandatory Q01 human same-identity review policy and its operation accounting. It creates no private receipt,
registry, root, locator, GenerationSpecification, Prompt, request, output, Asset, identity, cohort, or execution-side
state and invokes no generation, Vision, measurement, transform, Provider, or private-input operation.

## Preserved E01 authority

All non-conflicting E01 decisions remain unchanged: at most 32 serial request calls and 32 raw outputs; exactly one
requested output per call; target 24 independent cluster-adjusted admitted identities; concurrency one; retry zero;
tranches of at most four; immutable ordinal assignments; 4096-MiB cumulative and 4224-MiB peak-live storage maxima;
exact V01 runtime and morphology binding; automatic exact-duplicate hard rejection; pHash without a pre-04-C automatic
threshold; adult, safety, custody, Prompt-redaction, no-human-morphology-override, holdout, transform, downstream,
production, real-user, M6, and P2-M7 closures; and all legal stop outcomes.

R17 does not convert the failed candidate itself into PASS. After R17 acceptance, the E01 authority consists of the
preserved non-conflicting E01 contract plus this repair, with this repair controlling on conflict.

## Canonical duplicate-review policy

- `HUMAN_DUPLICATE_REVIEW_POLICY_VERSION: p2-m5-cc04-b-e01-human-duplicate-review-v1`
- `HUMAN_DUPLICATE_REVIEW_POLICY_CANONICAL_PAYLOAD: p2-m5-cc04-b-e01-human-duplicate-review-v1|pair_set=ALL_UNORDERED_CANONICALLY_NORMALIZED_RETURNED_OUTPUT_PAIRS|order=ASC_HAMMING_THEN_ASC_PRIOR_ORDINAL|review_count=ONE_PER_PAIR|actor_role=AUTHORIZED_ACTUAL_HUMAN_REVIEWER|decisions=DISTINCT_SYNTHETIC_IDENTITY,CONFIRMED_SAME_SYNTHETIC_IDENTITY,UNCERTAIN_HARD_STOP|retry=0|free_text=0|automatic_threshold=NONE`
- `HUMAN_DUPLICATE_REVIEW_POLICY_SHA256: 724a10d4886ec07a5fcb51ccce53e98caf2a6a936b1d9955ded8a00e97635e24`
- `HUMAN_DUPLICATE_REVIEW_ACTOR_ROLE: PROJECT_OWNER_OR_PROJECT_OWNER_DESIGNATED_ACTUAL_HUMAN_REVIEWER`
- `AGENT_OR_MODEL_MAY_SUBSTITUTE_FOR_HUMAN_REVIEW: false`
- `AUTOMATIC_DUPLICATE_DISTANCE_THRESHOLD_BEFORE_04_C: NONE`
- `HUMAN_DUPLICATE_REVIEW_RETRY_OR_SECOND_OPINION: 0`

The canonical payload is the exact UTF-8 byte sequence between the backticks, without a trailing newline. Its SHA-256
must be recomputed and matched before private setup and before every tranche. Any version, payload, digest, actor-role,
or policy mismatch returns `BLOCKED_DUPLICATE_REVIEW_AUTHORITY_MISMATCH` before another call.

## Deterministic all-pairs candidate set

For every returned output that reaches canonical normalization, pHash is computed once. For current ordinal `j`, the
candidate set is every unordered pair `(i,j)` where `i < j` and prior output `i` also reached canonical normalization,
without an automatic distance cutoff. The pair set cannot omit an output because it was rejected, provisionally
admitted, morphologically similar or dissimilar, stylistically similar or dissimilar, or inconvenient for occupancy.

All current-ordinal pairs are reviewed in ascending Hamming distance, breaking ties by ascending prior ordinal. pHash
therefore only orders review and never automatically rejects, admits, retains, or clusters. If normalization or pHash
is missing, failed, or uncertain, the reserved operation remains counted and the existing hard-stop outcome applies;
the pair set is not silently reduced and no later ordinal is dispatched.

## One governed actual-human decision per pair

Exactly one actual-human review operation is authorized for each deterministic candidate pair. It occurs only inside
the Principal-custodied private capability and may display only the two canonical normalized outputs, their opaque IDs,
member digests, and Hamming distance. The reviewer may decide only:

- `DISTINCT_SYNTHETIC_IDENTITY`;
- `CONFIRMED_SAME_SYNTHETIC_IDENTITY`; or
- `UNCERTAIN_HARD_STOP`.

The append-only decision binds the policy version and digest, signature version and bit length, both opaque output IDs
and member digests, Hamming distance, pseudonymous authorized-human actor ID, allowlisted decision and reason code, and
timestamp. Free-text facial judgments are prohibited. The reviewer may not infer or record age, race, ethnicity,
ancestry, nationality, beauty, attractiveness, sensitive traits, morphology cells, style quality, or downstream
performance. The decision cannot override an exact-duplicate, adult, safety, decode, runtime, reliability, custody, or
other automatic hard fail.

An Agent, model, automated similarity result, second reviewer, consensus pass, re-review, or changed presentation may
not substitute for the one authorized actual-human decision. Missing actual-human capability, uncertainty, timeout,
private-field leakage, or an invalid actor/decision/reason returns `UNSUPPORTED_PASS_OR_MISSING_EVIDENCE`, counts the
prepared review operation, and hard-stops without retry or replacement.

## Corrected exact operation accounting

For each returned output, reserve exactly the preserved E01 base operations:

- 20 accepted-runtime reliability runs;
- one morphology-vector operation;
- one pHash operation;
- one categorical adult/safety/style/background/expression/visibility review.

For ordinal `j`, additionally reserve exactly `j - 1` deterministic Hamming comparisons and exactly `j - 1` governed
actual-human same-identity review operations. The maximum for ordinal 032 is therefore
`23 + 31 + 31 = 85` operations. Across 32 outputs:

- base operations: `32 * 23 = 736`;
- Hamming comparisons: `32 * 31 / 2 = 496`;
- governed actual-human pair reviews: `32 * 31 / 2 = 496`;
- corrected total maximum: `736 + 496 + 496 = 1728`.

- `VISION_OR_MEASUREMENT_04_B_MAXIMUM: 1728`
- `VISION_OR_MEASUREMENT_OR_GOVERNED_HUMAN_REVIEW_04_B_MAXIMUM: 1728`
- `VISION_OR_MEASUREMENT_GLOBAL_HARD_CEILING: 2500`
- `REMAINING_GLOBAL_HEADROOM: 772`
- `TRANSFORM_OPERATION_ALLOWED_IN_04_B: 0`

The counter increments before each comparison or human review. Failed, missing, uncertain, or interrupted operations
count. No operation can be hidden in a categorical review, combined across pairs, refunded, repeated, delegated to a
model, or charged to transform budget. A call cannot start unless the worst-case remaining operations fit below the
2500 global ceiling. The preserved `VISION_OR_MEASUREMENT_04_B_MAXIMUM` governed key is corrected to 1728 and, for
this repaired E01 authority, inclusively covers the governed actual-human pair reviews as well as automated Vision and
measurement operations.

## Sequencing and closed boundaries

R17 acceptance is required before E01 can become effective. Until same-SHA CI, all eight artifacts, independent
Security/Privacy/License/Research Integrity, independent Sol High, and Principal acceptance pass for this repair,
`CC04_B_EXECUTION` remains closed and no private setup or generation may occur.

After acceptance, the sole next action is the preserved E01 Principal-custodied private setup followed by tranche 1 of
at most four serial calls. Before the first call, the Principal must bind the canonical duplicate-review policy payload
and digest into the private GenerationSpecification, assignment manifest, registry, and operation ledger. Missing
actual-human review capability is a fail-closed execution blocker; it does not authorize an Agent substitute, a hidden
automatic threshold, a call beyond the accepted tranche, or scope expansion.

This Repair does not create or access holdout, execute a transform, choose a 04-C threshold, alter any morphology split
or assignment, open 04-C through 04-E, evaluate MVR, enter M6, approve production or real-user processing, touch P2-M7,
or synchronize shared summaries.

- `PRIVATE_ROOT_OR_LOCATOR_CREATED: NO`
- `GENERATION_SPECIFICATION_CREATED: NO`
- `GENERATION_CALLS_EXECUTED: 0`
- `RAW_OUTPUTS_CREATED: 0`
- `ASSET_IDENTITY_OR_COHORT_CREATED: NO`

## Validation and result

Acceptance requires an exact three-path Markdown allowlist; scoped Prettier and `git diff --check`; failed-candidate
evidence preservation; canonical-payload digest verification; all-pairs set/order/decision semantics; actor and
no-Agent-substitution checks; `496 + 496` pair-operation and `1728 < 2500` arithmetic; no-threshold, no-retry,
adult/custody/holdout/downstream invariant scans; true-EOF last-occurrence, sentinel, and canonical/mirror equality;
exact-SHA CI and all eight artifacts; independent Security/Privacy/License/Research Integrity and Sol High reviews;
and Principal acceptance.

- `P2_M5_R17_RESULT: PASS`
- `CC04_B_E01_RESULT: PASS_AFTER_R17_ONLY`
- `CC04_B_EXECUTION: EXECUTION_READY_AFTER_R17_ACCEPTANCE`
- `NEXT_ACTION: EXECUTE_CC04_B_E01_PRIVATE_SETUP_AND_TRANCHE_1_MAX_4_CALLS`

These result markers are conditional and become current only after every R17 Gate passes. Reject or repair R17 only
with another normal forward commit; never amend, reset, rebase, force-push, rewrite the failed E01 candidate, or create a
post-acceptance status commit.
