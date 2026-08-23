# P2-M5 CC04-B TS01 Native ImageGen Transcript-Staging Change-Control Contract

## Status and bounded authority

- BOOTSTRAP_STATUS: OK
- TASK_ID: CC04-B-TS01-T01
- TASK_NAME: Codex Desktop Native ImageGen Transcript-Staging Change-Control Contract
- OWNER_DECISION_ID: OD-P2-M5-CC04-B-DS01-003
- PARENT_DECISION_ID: OD-P2-M5-CC04-B-E01-001
- OWNER_SELECTION: OPTION_C
- OWNER_DECISION:
  APPROVE_CODEX_DESKTOP_NATIVE_IMAGEGEN_TRANSCRIPT_STAGING_AND_SOL_MAX_REVIEW_WORKFLOW
- CHANGE_CONTROL_CLASS: PROSPECTIVE_SYNTHETIC_OUTPUT_CUSTODY_POLICY_CHANGE
- BASELINE_SHA: 218df1619dedfdb5f7f3a095334b241e2d46c37d
- BASELINE_CI_RUN: 32655228398
- BASELINE_MIGRATION_HEAD: 0014_m5_eval_authority
- CURRENT_AUTHORITY: p2-m5-cc04-b-ds01-post-q01-owner-decision-pack-eof/v1
- CHANGE_CONTROL_CANDIDATE: THIS_COMMIT
- AUTHORITY_CONDITION:
  EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE
- PRE_CONDITION_CURRENT_STATE:
  DS01_Q01_ACCEPTED_BLOCKED;POST_Q01_DECISION_PACK_ACCEPTED;PRIVATE_SETUP_NOT_CREATED;GENERATION_CALLS=0;RAW_OUTPUTS=0;REQUEST_ORDINAL=NONE

This task creates prospective governance and qualification authority only. It does not invoke native image generation,
run a capability qualification, create a transcript-export staging target or private custody root, export an image,
create a Prompt, GenerationSpecification, assignment or request ledger, start MR01, consume CAL-REQ-001, create an
Asset, identity, cohort, or QuestionBank object, or open 04-C, MVR, M6, production, real-user processing, or P2-M7.

## Immutable DS01-Q01 history and prospective supersession

- DS01_Q01_RESULT: BLOCKED_PRIVATE_SINK_CAPABILITY
- DS01_Q01_ATTEMPT: 1_OF_1_EXHAUSTED
- DS01_Q01_RETRY: PROHIBITED
- PRIVATE_SINK_Q01_FAILURE: PRESERVED_AS_ACCURATE_HISTORICAL_RESULT
- DIRECT_TO_SINK_REQUIREMENT:
  SUPERSEDED_PROSPECTIVELY_FOR_NON_USER_SYNTHETIC_NATIVE_IMAGEGEN_OUTPUTS_ONLY
- DS01_PRIVATE_OUTPUT_SINK_CAPABILITY: NOT_PROVEN
- DS01_TRANSCRIPT_SUPPRESSION_PROOF: NOT_PROVEN
- DS01_CUSTODY_RECEIPT_PROOF: NOT_PROVEN

The accepted Q01 result, its four metadata-only operations, its zero-generation evidence, and every earlier failed or
accepted record remain immutable. This change is not a Q01 retry, repair, reinterpretation, destination-bound
capability proof, or retrospective custody claim. It changes only the prospective custody model for
Codex Desktop native outputs that contain no real person, User Asset, user data, secret, credential, or sensitive
identity information.

The strict direct/private custody rules remain unchanged for real persons, user uploads, User Assets, SelfState,
DesiredDelta, real-user questionnaires, production generation, and every private user-data flow.

## Canonical native transcript-staging policy

- NATIVE_TRANSCRIPT_STAGING_POLICY_VERSION: p2-m5-cc04-b-e01-native-transcript-staging-v1
- NATIVE_TRANSCRIPT_STAGING_POLICY_CANONICAL_UTF8_BYTE_LENGTH: 882
- NATIVE_TRANSCRIPT_STAGING_POLICY_SHA256:
  c5b2a15f3d8801e1eba28d5a4eabb4f35b06ffb7aa3abb9747890e504ecc753a
- OUTPUT_CONFIDENTIALITY_CLASS: NON_USER_SYNTHETIC_RESEARCH
- SOURCE_KIND: CODEX_NATIVE_IMAGEGEN
- GENERATION_INTERFACE: CODEX_DESKTOP_NATIVE_IMAGE_GEN_TOOL
- SOURCE_SCOPE: PRIVATE_INTERNAL_SYNTHETIC_RESEARCH_ONLY
- SOURCE_DELIVERY_CLASS: CODEX_DESKTOP_NATIVE_TRANSCRIPT_OR_GENERATION_RESULT
- TRANSCRIPT_EXPOSURE_ACCEPTED_BY_OWNER: YES_FOR_SYNTHETIC_ONLY_OUTPUTS
- DIRECT_TO_SINK_REQUIRED: NO_FOR_THIS_EXACT_SYNTHETIC_SOURCE_AND_SCOPE
- POST_DELIVERY_CUSTODY_PROMOTION_REQUIRED: YES
- PLATFORM_TRANSCRIPT_COPY_WITHIN_PROJECT_CUSTODY: NO
- PLATFORM_TRANSCRIPT_COPY_DELETION_PROOF_REQUIRED: NO
- PLATFORM_TRANSCRIPT_COPY_MUST_NOT_BE_DESCRIBED_AS_PRIVATE_REGISTRY_OBJECT: REQUIRED

The sole canonical policy payload source is the RFC 8259 JSON string literal below:

```json
"p2-m5-cc04-b-e01-native-transcript-staging-v1|scope=NON_USER_SYNTHETIC_RESEARCH_ONLY|source=CODEX_DESKTOP_NATIVE_IMAGE_GEN_TOOL|delivery=CODEX_DESKTOP_NATIVE_TRANSCRIPT_OR_GENERATION_RESULT|direct_to_sink=0|transcript_exposure=OWNER_ACCEPTED|post_delivery_custody_promotion=1|auto_export=IF_EXACT_ARTIFACT_IDENTITY_PROVEN|priority=EXACT_NATIVE_GENERATED_ARTIFACT_AUTO_EXPORT,EXACT_NATIVE_ATTACHMENT_HANDLE_AUTO_EXPORT,OWNER_MEDIATED_MANUAL_EXPORT_FALLBACK|exact_call_binding=1|exact_output_binding=1|original_bytes=1|sha256=1|media_type=1|byte_size=1|no_enumeration=1|no_glob=1|no_scan=1|no_clipboard=1|no_screenshot=1|no_overwrite=1|source_staging_digest_equal=1|ordinal_filename=1|export_retry=0|formal_cal_req_qualification_use=0|qualification_fixture_global_reservation=1|global_native_output_max=64|qualification_fixture_storage_counts_global=1|global_private_storage_max_gib=8"
```

A validator must JSON-decode that literal, encode the resulting 882 Unicode scalar values as UTF-8 without BOM, and
hash exactly those bytes. Markdown, fence delimiters, quotes, CR, LF, and trailing newline are excluded. A version,
length, or digest mismatch stops before qualification or private setup.

## Post-generation export policy and priority

- NATIVE_IMAGEGEN_POST_GENERATION_EXPORT_POLICY:
  AUTOMATIC_IF_EXACT_ARTIFACT_IDENTITY_CAN_BE_PROVEN
- EXPORT_MODE_PRIORITY_1: EXACT_NATIVE_GENERATED_ARTIFACT_AUTO_EXPORT
- EXPORT_MODE_PRIORITY_2: EXACT_NATIVE_ATTACHMENT_HANDLE_AUTO_EXPORT
- EXPORT_MODE_PRIORITY_3: OWNER_MEDIATED_MANUAL_EXPORT_FALLBACK
- NATIVE_POST_GENERATION_AUTO_EXPORT_CAPABILITY: PRIMARY_TS01_QUALIFICATION_OBJECTIVE
- NATIVE_AUTO_EXPORT_CAPABILITY: NOT_PROVEN
- OWNER_MANUAL_EXPORT_REQUIRED_BY_DEFAULT: NOT_EVALUATED_UNTIL_TS01_QUALIFICATION

TS01 must investigate the two native automatic modes in that order. It may use a mode only when the platform exposes
an exact generated-artifact or attachment handle that is bound one-to-one to one native generation call and one
returned output. An ordinary conversation image, inline Base64 or data URL, screenshot, inferred recent file, generic
download, or unbound attachment is not an eligible handle.

NATIVE_AUTO_EXPORT_CAPABILITY may become PASS only if one prospective qualification proves every property below:

1. one exact platform-issued handle binds one exact call and one exact returned output;
2. the handle resolves the original generated bytes, not a screenshot, preview, re-render, or substitute;
3. no directory enumeration, parent listing, glob, Downloads/Desktop/temp/cache scan, clipboard recovery, recent-file
   guess, message-history byte inference, or alternate upload occurs;
4. the source bytes yield an exact SHA-256, media type, magic-byte class, byte size, and dimensions;
5. the exact bytes can be copied automatically to one pre-authorized Git-external staging target;
6. the destination filename is determined by the exact qualification or formal request ordinal;
7. a pre-existing target is a hard stop and is never overwritten, replaced, renamed, or used as success evidence;
8. the source digest and staging digest are byte-for-byte equal;
9. private path, root name, locator, object key, URL, signed URL, credential, Prompt, and image bytes stay out of Git,
   ordinary CI, MEMORY, logs, reviewer packets, and user-facing status;
10. export failure hard-stops without generation retry, replacement output, count refund, cache recovery, or fallback
    to another automatic mechanism for the same output.

Partial proof, tool-schema prose, an Agent statement, a successful generic generation, or a handle that cannot expose
the exact original bytes yields NATIVE_AUTO_EXPORT_CAPABILITY: NOT_PROVEN. That result is not failure of the overall
TS01 workflow and must not revive the destination-bound private-sink requirement.

## Qualification budget and CAL-REQ isolation

- TS01_QUALIFICATION_STATUS: NOT_STARTED
- TS01_QUALIFICATION_FORMAL_CALIBRATION_REQUEST_CALL_MAX: 0
- TS01_QUALIFICATION_FORMAL_CALIBRATION_RAW_OUTPUT_MAX: 0
- TS01_QUALIFICATION_FORMAL_REQUEST_ORDINAL_MAX: 0
- TS01_NO_COST_NON_PRODUCTION_FIXTURE_GENERATION_CALL_MAX: 1
- TS01_NO_COST_NON_PRODUCTION_FIXTURE_RAW_OUTPUT_MAX: 1
- TS01_FIXTURE_GLOBAL_NATIVE_OUTPUT_RESERVATION_MAX: 1
- TS01_FIXTURE_GLOBAL_NATIVE_OUTPUT_RESERVATION_CONSUMED: 0
- TS01_FIXTURE_GLOBAL_NATIVE_OUTPUT_RESERVATION_TRIGGER: NATIVE_FIXTURE_DISPATCH
- TS01_FIXTURE_GLOBAL_NATIVE_OUTPUT_RESERVATION_REFUND: PROHIBITED_AFTER_DISPATCH
- GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING_BEFORE_TS01_QUALIFICATION: 64
- GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING_AFTER_ONE_TS01_FIXTURE_DISPATCH: 63
- DOWNSTREAM_CALIBRATION_AND_HOLDOUT_AGGREGATE_OUTPUT_CAPACITY_AFTER_ONE_TS01_FIXTURE: 63
- TS01_FIXTURE_PRIVATE_STORAGE_ACCOUNTING:
  ALL_STAGING_PROMOTED_AND_TEMPORARY_BYTES_COUNT_WITHIN_EXISTING_8_GIB_GLOBAL_HARD_CEILING_NO_ADDITIVE_ENVELOPE
- TS01_FIXTURE_PRIVATE_STORAGE_BYTES_CONSUMED: 0
- TS01_QUALIFICATION_RETRY_MAX: 0
- TS01_QUALIFICATION_CONCURRENCY_MAX: 1
- TS01_QUALIFICATION_OUTPUT_ADMISSION: PROHIBITED
- TS01_QUALIFICATION_AND_FORMAL_E01_BUDGET_COMMINGLING: PROHIBITED
- CAL_REQ_001_STATUS: NOT_CONSUMED_AND_PROHIBITED_FOR_TS01_QUALIFICATION

After this change control is accepted, a separate TS01 qualification may first use read-only interface metadata,
platform attestation, or an explicitly non-production, non-chargeable native fixture facility. At most one fixture
generation call and one returned fixture output are allowed, only when the platform can prove before dispatch that
the operation is non-chargeable, non-production, independent of formal E01, uses no CAL-REQ ordinal, and one unit is
available inside the frozen 64-output global ceiling. Immediately before dispatch, TS01 must irrevocably reserve one
global native-output unit. The reservation remains consumed even if the call returns no output or later export fails;
there is no refund or retry. One dispatched fixture therefore reduces the aggregate capacity later available to
calibration plus holdout from 64 to 63, while their individual maxima remain unchanged and subject to that aggregate
remaining capacity. The fixture uses a separate TS01-FIX-001 accounting record, cannot enter calibration or holdout,
and cannot create an Asset, identity, or cohort.

Any fixture staging, promoted, retained, or temporary bytes also count inside the existing 8 GiB global private-
storage hard ceiling. TS01 creates no separate or additive storage envelope. Retained bytes remain charged until
verified cleanup; formal E01 cannot start until qualification storage and the global ceiling are reconciled.

If exact auto-export proof requires a native generation call whose non-chargeable status is unavailable, ambiguous,
or false, no call is authorized. The qualification must return:

```text
STATUS: OWNER_DECISION_REQUIRED_FOR_SINGLE_AUTO_EXPORT_QUALIFICATION_CALL
FORMAL_CALIBRATION_GENERATION_BUDGET_IMPACT: 0
FORMAL_CALIBRATION_RAW_OUTPUT_BUDGET_IMPACT: 0
FORMAL_REQUEST_ORDINAL_IMPACT: NONE
CAL_REQ_001_STATUS: NOT_CONSUMED
PLATFORM_CREDIT_OR_OTHER_RESOURCE_IMPACT: EXPLICIT_OWNER_DECISION_REQUIRED_BEFORE_CALL
GLOBAL_NATIVE_OUTPUT_RESERVATION_IMPACT_IF_LATER_AUTHORIZED_AND_DISPATCHED: 1_WITHIN_FROZEN_64_NOT_ADDITIVE
CURRENT_GLOBAL_NATIVE_OUTPUT_RESERVATION_CONSUMED: 0
```

Any later Owner-authorized qualification call must remain separately accounted and must not use or reduce the 32-call,
32-raw, or CAL-REQ-001 formal calibration envelope. The Owner must explicitly decide its platform-credit treatment
before dispatch; if dispatched, the call still consumes the one frozen global-output reservation and all private bytes
remain within the existing 8 GiB ceiling. T01 itself authorizes no qualification call.

## Manual-export fallback

If the exact native handle cannot be proven, TS01 records:

- NATIVE_AUTO_EXPORT_CAPABILITY: NOT_PROVEN
- OWNER_MEDIATED_MANUAL_EXPORT: ALLOWED_FALLBACK
- DESTINATION_BOUND_DIRECT_WRITE_REQUALIFICATION: NOT_REQUIRED

This is a legal qualification disposition, not a TS01 failure. A later formal ordinal may use manual export only after
TS01, MR01, and a new E01 execution-authority checkpoint are all accepted and staging/custody/specification/ledger
preconditions are ready. When manual action is actually needed, Codex must stop with:

```text
STATUS: OWNER_EXPORT_REQUIRED
REQUEST_ORDINAL: CAL-REQ-xxx
EXPECTED_EXPORT_FILENAME: <opaque task-approved filename>
```

The Owner uses the normal save/download action on that exact native result, saves it to the pre-authorized exact
staging target under the ordinal-derived filename, and replies only EXPORTED CAL-REQ-xxx. Codex then reads only that
exact expected file. It does not list the parent, use a glob, search another directory, inspect Downloads/Desktop/temp/
cache, recover from clipboard, accept a screenshot, accept a different upload, or substitute another image.

The native dispatch has already consumed its ordinal whether export succeeds or fails. Manual omission, wrong binding,
file mismatch, export failure, or staging failure never triggers generation retry, Prompt change, replacement output,
count refund, or another ordinal masquerading as the same request.

## Staging, integrity, and custody promotion

The later accepted workflow has two distinct Git-external areas:

1. TRANSCRIPT_EXPORT_STAGING;
2. PRINCIPAL_RESEARCH_CUSTODY_ROOT.

Neither is created by T01. The later task must resolve a pre-authorized task-scoped capability without disk discovery,
prove each exact target absent before export, reject reparse/symlink/alias/shared/P2-M7 targets, and never disclose the
path or locator. Staging accepts only the exact current ordinal's file.

Before promotion, the immutable staging-integrity record must bind:

```text
OUTPUT_OPAQUE_ID
REQUEST_OR_QUALIFICATION_ORDINAL
SOURCE_KIND
SOURCE_DELIVERY_CLASS
SOURCE_ARTIFACT_OR_ATTACHMENT_HANDLE_REDACTED_RECEIPT
SOURCE_OUTPUT_DIGEST
STAGING_DIGEST
MEDIA_TYPE
MAGIC_BYTES_CLASS
BYTE_SIZE
DIMENSIONS
EXPORT_TIMESTAMP
EXPORT_MODE
STAGING_INTEGRITY_STATUS
```

Only digest-equal, type/size/dimension-valid staging evidence may be atomically copied or moved to the Principal
research-custody root. The promotion record additionally binds GenerationSpecification and assignment-manifest
digests for formal E01 output, custody authority, retention class, and cleanup status. Decode, normalization, QA,
pHash, Sol Max pair review, Asset admission, and SyntheticIdentity admission are prohibited before promotion.

Every output must accurately record:

- TRANSCRIPT_COPY_EXISTS: YES_OR_PLATFORM_UNKNOWN
- TRANSCRIPT_COPY_UNDER_PROJECT_REGISTRY: NO
- TRANSCRIPT_COPY_DELETION_VERIFIED: NO
- LOCAL_PROMOTED_COPY_UNDER_PROJECT_REGISTRY: YES_AFTER_PROMOTION_ONLY

Staging or promotion does not retroactively make the platform transcript copy private, prove its deletion, establish
Project Mirror as sole custodian, or prove destination-bound delivery from the first generated byte.

## Prompt, image, privacy, and license boundary

Because the Prompt and native result may enter a Codex Desktop conversation, both must be synthetic-only and contain
no real-person name or reference, User Asset, user feature, user data, secret, credential, private path, locator,
internal private payload, sensitive identity category, age estimation, beauty score, celebrity imitation, or
minor-boundary bypass. The existing clearly-adult, nonsexual, anti-homogenization, no-sensitive-inference, no-beauty-
ranking, no-hidden-standard-face, and private-internal-research controls remain binding.

Prompt plaintext never enters Git, commit text, ordinary logs, CI artifacts, MEMORY, status tails, or reviewer packets.
Its exposure as necessary native tool input is the exact Owner-accepted transcript/tool-transport exposure and grants
no further propagation authority.

This change adds no dependency, SDK, model, weight, Provider, credential, network relaxation, paid service, production
approval, or output-rights conclusion. Unknown native model/version/request/usage/cost/retention/telemetry facts remain
UNKNOWN_OR_NULL and require explicit scope-appropriate review.

## Request failure and no-retry semantics

Formal E01 retains 32 calls, 32 raw outputs, 24 independent cluster-adjusted admitted identities, one output per call,
concurrency one, retry zero, and at most four calls per tranche. Every native dispatch consumes its unique ordinal
immediately. Every returned output counts before export, inspection, QA, or admission.

Legal export/custody failures include:

- NATIVE_EXPORT_FAILED_HARD_STOP
- OWNER_EXPORT_NOT_COMPLETED_HARD_STOP
- STAGING_INTEGRITY_FAILED
- PROMOTION_CUSTODY_FAILED

No failure permits another generation for the same ordinal, Prompt mutation, automatic/manual retry, cached recovery,
substitute bytes, ignored output, quota refund, or hidden Provider route.

## Sol Max reviewer and downstream boundaries

The accepted Sol Max duplicate-review policy remains unchanged:

- SOL_MAX_DUPLICATE_REVIEW_POLICY_VERSION: p2-m5-cc04-b-e01-sol-max-duplicate-review-v1
- SOL_MAX_DUPLICATE_REVIEW_POLICY_SHA256:
  725b870ac8c93ac50c62badc9553a3cd0706ae84dbee29bab0b16df53889f410
- REVIEWER_MODEL_ROUTE: SOL_MAX
- MODEL_FALLBACK: PROHIBITED
- REVIEW_RETRY: 0
- SECOND_OPINION: 0
- PAIR_SET: ALL_UNORDERED_CANONICALLY_NORMALIZED_RETURNED_OUTPUT_PAIRS
- PAIR_ORDER: ASC_HAMMING_THEN_ASC_PRIOR_ORDINAL
- MAXIMUM_PAIR_REVIEWS_FOR_32_OUTPUTS: 496

MR01 begins only after TS01 qualification is independently accepted. The reviewer receives only promoted, canonical,
capability-bound pairs and strict allowlisted control data. It receives no Prompt, transcript, path, locator, staging
fact, generator context, downstream evidence, shell, network, generation, Provider, or release capability. Free-text
face description, beauty/style preference, age or sensitive-trait judgment, identity name, celebrity similarity, and
QuestionBank recommendation remain prohibited.

Native outputs can enter only the fresh M5 calibration cohort after every admission Gate. They cannot enter
QuestionBank until M5 technical PASS, P2-MVR-v1 PASS, and a separate M6 release authority. Questionnaire runtime
generation remains zero.

## Qualification DAG and stop boundary

The only forward sequence is:

```text
TS01-T01 change-control acceptance
  -> TS01-Q01 auto-export-first capability qualification
  -> MR01 Sol Max reviewer qualification
  -> new E01 execution-authority checkpoint
  -> zero-counter recheck
  -> staging, custody root, specification, assignments, and ledgers
  -> tranche 1, maximum four formal calls
```

TS01-Q01 must prefer exact generated-artifact auto export, then exact attachment-handle auto export, then record
manual export fallback. It may not retry DS01-Q01 or require destination-bound direct write. Each node needs its own
same-SHA CI, eight artifact content checks, Security, Privacy, License, Research Integrity, Sol High, and Principal
acceptance before the next node starts.

## Changed paths and validation

T01 may change exactly:

1. docs/operations/P2_M5_CC04_B_TS01_NATIVE_IMAGEGEN_TRANSCRIPT_STAGING_CHANGE_CONTROL_CONTRACT.md;
2. docs/research/P2_M5_CC04_B_TS01_NATIVE_IMAGEGEN_TRANSCRIPT_STAGING_POLICY.md;
3. docs/operations/P2_M5_ACCEPTANCE.md;
4. docs/operations/P2_M5_EXECUTION_PROTOCOL.md.

It may not change code, schema, migration, OpenAPI, Worker, dependency, lockfile, model, Provider, CI, MILESTONES,
MEMORY, P2-M7, shared summaries, or private state. Acceptance requires scoped Prettier, git diff --check, exact
changed-path and no-private/no-binary scans, canonical policy byte-length/digest verification, immutable DS01 history,
zero formal and qualification counters, resource and downstream boundary scans, canonical/mirror exact key order and
value equality, no duplicate current-tail keys, every governed key's last occurrence in the new true-EOF tail, exact-
SHA CI, all eight artifact content checks, independent Security/Privacy/License/Research Integrity, independent Sol
High, and Principal acceptance.

Only normal forward commits and fast-forward non-force push are allowed. Never amend, reset, rebase, merge,
force-push, rewrite history, or create a post-acceptance status commit.

## Candidate result and next task

- TS01_CHANGE_CONTROL_RESULT: PASS_AT_THIS_COMMIT_AFTER_ALL_GATES
- TS01_QUALIFICATION_STATUS: NOT_STARTED
- NATIVE_AUTO_EXPORT_CAPABILITY: NOT_PROVEN
- NATIVE_GENERATED_ARTIFACT_EXPORT_STATUS: NOT_PROVEN
- NATIVE_ATTACHMENT_EXPORT_STATUS: NOT_PROVEN
- OWNER_MANUAL_EXPORT_STATUS: NOT_STARTED
- TRANSCRIPT_EXPORT_STAGING_CREATED: NO
- STAGING_INTEGRITY_STATUS: NOT_STARTED
- PRINCIPAL_RESEARCH_CUSTODY_ROOT_CREATED: NO
- CUSTODY_PROMOTION_STATUS: NOT_STARTED
- TS01_QUALIFICATION_GENERATION_CALLS_EXECUTED: 0
- TS01_QUALIFICATION_OUTPUTS_CREATED: 0
- TS01_FIXTURE_GLOBAL_NATIVE_OUTPUT_RESERVATION_CONSUMED: 0
- GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING: 64
- TS01_FIXTURE_PRIVATE_STORAGE_BYTES_CONSUMED: 0
- FORMAL_E01_GENERATION_CALLS_EXECUTED: 0
- GENERATION_CALLS_EXECUTED: 0
- RAW_OUTPUTS_CREATED: 0
- REQUEST_ORDINAL_CONSUMED: NONE
- PRIVATE_ROOT_OR_LOCATOR_CREATED: NO
- GENERATION_SPECIFICATION_CREATED: NO
- CALIBRATION_COHORT_STATUS: NOT_CREATED
- CC04_B_EXECUTION: CLOSED_PENDING_TS01_MR01_AND_NEW_E01_AUTHORITY
- P2_M5_STATE: EXECUTING
- P2_MVR_V1_RESULT: NOT_EVALUATED
- P2_M6_ENTRY: CLOSED_PENDING_TECHNICAL_AND_MVR_PASS
- NEXT_READY_TASK: CC04-B-TS01-Q01_NATIVE_POST_GENERATION_AUTO_EXPORT_CAPABILITY_QUALIFICATION
- STOP_OUTCOME: TS01_CHANGE_CONTROL_ACCEPTED_AFTER_ALL_GATES

Acceptance opens only the separately bounded TS01-Q01 qualification. It does not itself call image generation, create
staging or custody state, start MR01, or authorize formal E01 execution.
