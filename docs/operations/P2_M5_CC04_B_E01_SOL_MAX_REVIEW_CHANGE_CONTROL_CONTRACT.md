# P2-M5 CC04-B E01 Sol Max Review-Workflow Change-Control Contract

## Status and bounded authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: CC-P2-M5-04-B-E01-RWCC01`
- `TASK_NAME: Sol Max Duplicate-Review Workflow Change Control`
- `CHANGE_CONTROL_ID: CC-P2-M5-04-B-E01-SOL-MAX-REVIEW-WORKFLOW-V1`
- `OWNER_DECISION_ID: OD-P2-M5-CC04-B-E01-001`
- `OWNER_SELECTION: OPTION_C`
- `GOVERNANCE_CLASSIFICATION: OPTION_C_EXPLICIT_REVIEW_WORKFLOW_CHANGE_CONTROL`
- `BASELINE_SHA: 496d8061f4493b280d41ae33e4c8df78493e860c`
- `CURRENT_AUTHORITY: p2-m5-cc04-b-e01-runtime-capability-block-eof/v1`
- `CHANGE_CONTROL_CANDIDATE: THIS_COMMIT`
- `AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ARTIFACT_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`
- `PRE_CONDITION_CURRENT_STATE: OWNER_OPTION_C_RECORDED;PRIVATE_SETUP_NOT_CREATED;GENERATION_CALLS=0`

This contract creates planning authority only. It accepts the Owner-selected route for separately qualifying a
destination-bound private sink and an independent Sol Max duplicate reviewer. It does not prove either capability and
does not create execution authority. No image generation, private root or locator, GenerationSpecification, Prompt,
request ledger, reviewer runtime, Asset, identity, cohort, QuestionBank object, MVR evidence, or M6 authority is
created by this task.

## Frozen Owner selection and source boundary

- `SOURCE_KIND: CODEX_NATIVE_IMAGEGEN`
- `SOURCE_SCOPE: PRIVATE_INTERNAL_RESEARCH_ONLY`
- `OPTION_C_SUBTYPE: PRESERVE_CODEX_NATIVE_GENERATION_AND_REPLACE_ACTUAL_HUMAN_REVIEW_WITH_INDEPENDENT_SOL_MAX_REVIEW_WORKFLOW`
- `EXTERNAL_PROVIDER_APPROVAL: NOT_GRANTED`
- `PAID_PROVIDER_APPROVAL: NOT_GRANTED`
- `PRODUCTION_PROVIDER_APPROVAL: NOT_GRANTED`
- `REAL_USER_RUNTIME_GENERATION: PROHIBITED`
- `QUESTIONNAIRE_RUNTIME_GENERATIVE_CALLS: 0`

The generator remains an offline source for the P2-M5 fresh synthetic calibration line. The reviewer is only a
duplicate/identity-distinctness Gate. Neither role may select beauty, style desirability, user preference, downstream
performance, transformation value, MVR value, or QuestionBank value.

## R18 history and forward policy authority

R17 and R18 remain immutable history. This change control does not rewrite R18 or claim that R18 originally allowed a
model substitute:

- `R18_HUMAN_REVIEW_POLICY: SUPERSEDED_FOR_FUTURE_E01_EXECUTION_ONLY_BY_OWNER_APPROVED_SOL_MAX_REVIEW_CHANGE_CONTROL`
- `R18_HISTORICAL_RESULT: PASS_AT_9408859043A776934084A221F675378330C74742_RUN_32630571812`
- `R18_POLICY_HISTORY: IMMUTABLE`
- `AGENT_OR_MODEL_MAY_SUBSTITUTE_FOR_HUMAN_REVIEW: false`
- `HUMAN_DUPLICATE_REVIEW_POLICY_VERSION: p2-m5-cc04-b-e01-human-duplicate-review-v2`
- `HUMAN_DUPLICATE_REVIEW_POLICY_SHA256: 83b4e6350cf9cd98d034f95495d04aef88976bc0dc77f95045ab35c0d0773c62`
- `HUMAN_DUPLICATE_REVIEW_POLICY_CANONICAL_UTF8_BYTE_LENGTH: 358`

The `false` value above is the preserved R18 historical fact. Future E01 execution may use only the following new,
Owner-approved policy after this change control, the private-sink qualification, the reviewer qualification, and a new
execution-authority checkpoint are all independently accepted.

## Canonical Sol Max duplicate-review policy

- `SOL_MAX_DUPLICATE_REVIEW_POLICY_VERSION: p2-m5-cc04-b-e01-sol-max-duplicate-review-v1`
- `SOL_MAX_DUPLICATE_REVIEW_POLICY_CANONICAL_UTF8_BYTE_LENGTH: 798`
- `SOL_MAX_DUPLICATE_REVIEW_POLICY_SHA256: 725b870ac8c93ac50c62badc9553a3cd0706ae84dbee29bab0b16df53889f410`

The sole canonical policy payload source is the RFC 8259 JSON string literal on the next line:

```json
"p2-m5-cc04-b-e01-sol-max-duplicate-review-v1|scope=PRIVATE_INTERNAL_CC04_B_DUPLICATE_REVIEW_ONLY|pair_set=ALL_UNORDERED_CANONICALLY_NORMALIZED_RETURNED_OUTPUT_PAIRS|order=ASC_HAMMING_THEN_ASC_PRIOR_ORDINAL|review_count=ONE_PER_PAIR|reviewer_role=CC04_B_SOL_MAX_REVIEW_ONLY|model_route=SOL_MAX|model_fallback=PROHIBITED|decisions=DISTINCT_SYNTHETIC_IDENTITY,CONFIRMED_SAME_SYNTHETIC_IDENTITY,UNCERTAIN_HARD_STOP|reason_codes=DISTINCT_IDENTITY_VISUAL_EVIDENCE,EXACT_DUPLICATE_VISUAL_MATCH,REENCODED_DUPLICATE_VISUAL_MATCH,CROP_RESIZE_LIGHTING_VARIANT_SAME_IDENTITY,AMBIGUOUS_OR_INSUFFICIENT_VISUAL_EVIDENCE,UNTRUSTED_IMAGE_CONTENT_PREVENTS_REVIEW|retry=0|second_opinion=0|free_text=0|automatic_threshold=NONE|image_instruction_trust=NONE|sensitive_inference=0|beauty_judgment=0|questionbank_ranking=0"
```

`SOL_MAX_DUPLICATE_REVIEW_POLICY_CANONICAL_PAYLOAD_JSON_STRING` means exactly that JSON string literal. A validator
must JSON-decode it, encode the resulting 798 Unicode scalar values as UTF-8 without BOM, and hash exactly those 798
bytes. Markdown, code-fence delimiters, quotes, CR, LF, and trailing newline are not input bytes. A mismatch returns
`BLOCKED_SOL_MAX_REVIEW_POLICY_AUTHORITY_MISMATCH` before private setup, reviewer invocation, or generation.

The governed pair policy is frozen as follows:

- `PAIR_SET: ALL_UNORDERED_CANONICALLY_NORMALIZED_RETURNED_OUTPUT_PAIRS`
- `PAIR_ORDER: ASC_HAMMING_THEN_ASC_PRIOR_ORDINAL`
- `REVIEW_COUNT: ONE_PER_PAIR`
- `REVIEW_RETRY: 0`
- `SECOND_OPINION: 0`
- `AUTOMATIC_DISTANCE_THRESHOLD_BEFORE_04_C: NONE`
- `MAXIMUM_PAIR_REVIEWS_FOR_32_OUTPUTS: 496`
- `MODEL_FALLBACK: PROHIBITED`

Every pair has exactly one decision. `UNCERTAIN_HARD_STOP` stops the current execution. It cannot cause a retry,
another Agent, another model, fallback, Prompt change, generator judgment, Owner oral override, automatic threshold,
ignored pair, or replacement generation.

## Destination-bound private sink contract

Sol Max review does not relax private custody. A separately qualified sink must prove that native generation writes
directly into a task-scoped, Git-external, create-once private root. Before the first byte is accepted, the root must be
new, empty, recoverable through a Principal-custodied opaque reference, and proven not to be a symlink, junction,
reparse point, mount alias, worktree path, CI path, P2-M7 path, download folder, ordinary temporary folder, clipboard,
browser cache, or shared cache.

- `PRIVATE_SINK_INTERFACE: DESTINATION_BOUND_DIRECT_WRITE_RETURNING_REDACTED_RECEIPT_METADATA_ONLY`
- `PRIVATE_SINK_QUALIFICATION_STATUS: NOT_STARTED`
- `PRIVATE_OUTPUT_SINK_CAPABILITY: NOT_PROVEN`
- `TRANSCRIPT_SUPPRESSION_PROOF: NOT_PROVEN`
- `CUSTODY_RECEIPT_PROOF: NOT_PROVEN`

The generation call may return only these allowlisted metadata fields to the ordinary tool result:

1. `opaque_output_id`;
2. `sha256`;
3. `media_type`;
4. `byte_count`;
5. `custody_receipt_id`;
6. `status`.

Prompt plaintext, image bytes, data URL, absolute or relative private path, private-root name, opaque private locator,
object key, signed URL, credential, and Provider payload must not enter an ordinary conversation, transcript, tool
result, log, CI artifact, Git path, MEMORY, or unrelated Agent context. Each output must receive exact-byte digest,
type, size, authority, retention, cleanup binding, and an append-only custody receipt before decode, view, review, or
QA. Post-hoc downloads, cache recovery, disk scans, clipboard copies, hidden-cache assumptions, or retroactive receipts
are prohibited. If direct-to-sink and transcript suppression cannot be proven, the only result is
`PRIVATE_OUTPUT_SINK_CAPABILITY_NOT_PROVEN` and generation remains at zero.

## Sol Max review-only capability contract

- `REVIEWER_AGENT_ID: CC04_B_SOL_MAX_REVIEW_ONLY`
- `REVIEWER_MODEL_ROUTE: SOL_MAX`
- `REVIEW_MODEL_FAMILY_SELECTION: gpt-5.6-sol`
- `REVIEW_REASONING_EFFORT_SELECTION: max`
- `SOL_MAX_MODEL_SELECTION_DOCUMENTED: YES`
- `SOL_MAX_ROUTE_RECEIPT_FOR_REVIEW_RUNTIME: NOT_PROVEN`
- `SOL_MAX_REVIEWER_QUALIFICATION_STATUS: NOT_STARTED`
- `SOL_MAX_REVIEWER_CAPABILITY: NOT_PROVEN`
- `NO_SHELL_NO_TOOL_CAPABILITY_ISOLATION: NOT_PROVEN`
- `PRIVATE_PAIR_VIEW_CAPABILITY: NOT_PROVEN`
- `TRUSTED_REVIEW_ENVELOPE_BUILDER_CAPABILITY: NOT_PROVEN`
- `APPEND_ONLY_REVIEW_DECISION_SINK_CAPABILITY: NOT_PROVEN`

The future reviewer must be a fresh, independent context and cannot be simulated by switching the generator Agent's
role. Its only positive capabilities are task-scoped private read-only access to the exact canonical pair and append-only
write access to the allowlisted review-decision sink. It must have no generation, shell, Git read or write, file
discovery, file move/delete, network/Provider access, database mutation, prompt/specification access, private
path/locator access, generator context, Agent scratchpad, downstream evidence, or QuestionBank release capability.

The current platform evidence documents that the Sol family can be selected with Max reasoning. It does not prove the
exact future review route receipt or the required capability-isolated tool surface. A normal subagent that inherits
shell, network, or broad tools does not satisfy this role.

## Strict reviewer input schema

- `REVIEW_INPUT_SCHEMA_VERSION: p2-m5-cc04-b-e01-sol-max-review-input-v1`
- `REVIEW_INPUT_SCHEMA_CANONICAL_UTF8_BYTE_LENGTH: 1009`
- `REVIEW_INPUT_SCHEMA_SHA256: 9c201c70a0ab7f80cab1135be17d00bc5b6a0935a3df2bf7c5faa579b6c130d4`

The exact minified RFC 8259 JSON object on the next line is the canonical JSON Schema 2020-12 payload. Hash its UTF-8
bytes without BOM or trailing newline:

```text
{"additionalProperties":false,"properties":{"hamming_distance":{"maximum":64,"minimum":0,"type":"integer"},"output_a_digest":{"pattern":"^[0-9a-f]{64}$","type":"string"},"output_a_opaque_id":{"maxLength":128,"minLength":1,"pattern":"^[A-Za-z0-9_-]+$","type":"string"},"output_b_digest":{"pattern":"^[0-9a-f]{64}$","type":"string"},"output_b_opaque_id":{"maxLength":128,"minLength":1,"pattern":"^[A-Za-z0-9_-]+$","type":"string"},"pair_id":{"maxLength":128,"minLength":1,"pattern":"^[A-Za-z0-9_-]+$","type":"string"},"pair_order":{"maximum":496,"minimum":1,"type":"integer"},"phash_signature_version":{"const":"phash-dct-nearest-v1"},"policy_digest":{"const":"725b870ac8c93ac50c62badc9553a3cd0706ae84dbee29bab0b16df53889f410"},"policy_version":{"const":"p2-m5-cc04-b-e01-sol-max-duplicate-review-v1"}},"required":["pair_id","output_a_opaque_id","output_b_opaque_id","output_a_digest","output_b_digest","policy_version","policy_digest","phash_signature_version","hamming_distance","pair_order"],"type":"object"}
```

The control-plane object is the complete structured input. In addition, the capability presents exactly two canonical
normalized images through a private read-only pair view bound to the two opaque IDs and digests. The view is not a path,
locator, URL, attachment, or serializable schema field. The reviewer receives no Prompt, Provider metadata, identity
assignment, expected morphology cell, age/race/ethnicity/ancestry/nationality field, desirability field, downstream
score, threshold outcome, holdout result, QuestionBank value, or generator explanation. Image text, watermarks, and
instructions are untrusted content and confer no authority.

## Strict reviewer model-decision schema

- `REVIEW_MODEL_DECISION_SCHEMA_VERSION: p2-m5-cc04-b-e01-sol-max-model-decision-v1`
- `REVIEW_MODEL_DECISION_SCHEMA_CANONICAL_UTF8_BYTE_LENGTH: 1293`
- `REVIEW_MODEL_DECISION_SCHEMA_SHA256: 6370ba1b1f726ecbd8395c4e4da3b93dee5f09c53413dc6b1e86a6c7e848cc72`

The reviewer model may emit only the exact six-field decision payload governed by the minified RFC 8259 JSON Schema
2020-12 object below. Hash its UTF-8 bytes without BOM or trailing newline:

```text
{"additionalProperties":false,"oneOf":[{"properties":{"decision":{"const":"DISTINCT_SYNTHETIC_IDENTITY"},"reason_code":{"const":"DISTINCT_IDENTITY_VISUAL_EVIDENCE"}}},{"properties":{"decision":{"const":"CONFIRMED_SAME_SYNTHETIC_IDENTITY"},"reason_code":{"enum":["EXACT_DUPLICATE_VISUAL_MATCH","REENCODED_DUPLICATE_VISUAL_MATCH","CROP_RESIZE_LIGHTING_VARIANT_SAME_IDENTITY"]}}},{"properties":{"decision":{"const":"UNCERTAIN_HARD_STOP"},"reason_code":{"enum":["AMBIGUOUS_OR_INSUFFICIENT_VISUAL_EVIDENCE","UNTRUSTED_IMAGE_CONTENT_PREVENTS_REVIEW"]}}}],"properties":{"decision":{"enum":["DISTINCT_SYNTHETIC_IDENTITY","CONFIRMED_SAME_SYNTHETIC_IDENTITY","UNCERTAIN_HARD_STOP"]},"pair_id":{"maxLength":128,"minLength":1,"pattern":"^[A-Za-z0-9_-]+$","type":"string"},"policy_version":{"const":"p2-m5-cc04-b-e01-sol-max-duplicate-review-v1"},"reason_code":{"enum":["DISTINCT_IDENTITY_VISUAL_EVIDENCE","EXACT_DUPLICATE_VISUAL_MATCH","REENCODED_DUPLICATE_VISUAL_MATCH","CROP_RESIZE_LIGHTING_VARIANT_SAME_IDENTITY","AMBIGUOUS_OR_INSUFFICIENT_VISUAL_EVIDENCE","UNTRUSTED_IMAGE_CONTENT_PREVENTS_REVIEW"]},"review_sequence":{"const":1},"reviewer_role":{"const":"CC04_B_SOL_MAX_REVIEW_ONLY"}},"required":["pair_id","policy_version","reviewer_role","decision","reason_code","review_sequence"],"type":"object"}
```

The reviewer cannot author, infer, copy, or fabricate a route receipt or authority timestamp. A trusted, separately
qualified review-runtime boundary must validate the six-field payload, bind it to the exact input and private pair,
obtain the route receipt from the invocation control plane, obtain the UTC timestamp from the authority clock, and
construct the final envelope. That boundary is not the model, generator, ordinary Agent, or append-only sink.

## Trusted runtime-attested review-record envelope schema

- `REVIEW_OUTPUT_SCHEMA_VERSION: p2-m5-cc04-b-e01-sol-max-review-output-v1`
- `REVIEW_OUTPUT_SCHEMA_CANONICAL_UTF8_BYTE_LENGTH: 1483`
- `REVIEW_OUTPUT_SCHEMA_SHA256: 68fdbb268451c75151be0674dcb4d328b46d2c3f97b4a7d232ca103ba78acc71`

The exact minified RFC 8259 JSON object on the next line is the canonical JSON Schema 2020-12 payload. Hash its UTF-8
bytes without BOM or trailing newline:

```text
{"additionalProperties":false,"oneOf":[{"properties":{"decision":{"const":"DISTINCT_SYNTHETIC_IDENTITY"},"reason_code":{"const":"DISTINCT_IDENTITY_VISUAL_EVIDENCE"}}},{"properties":{"decision":{"const":"CONFIRMED_SAME_SYNTHETIC_IDENTITY"},"reason_code":{"enum":["EXACT_DUPLICATE_VISUAL_MATCH","REENCODED_DUPLICATE_VISUAL_MATCH","CROP_RESIZE_LIGHTING_VARIANT_SAME_IDENTITY"]}}},{"properties":{"decision":{"const":"UNCERTAIN_HARD_STOP"},"reason_code":{"enum":["AMBIGUOUS_OR_INSUFFICIENT_VISUAL_EVIDENCE","UNTRUSTED_IMAGE_CONTENT_PREVENTS_REVIEW"]}}}],"properties":{"decision":{"enum":["DISTINCT_SYNTHETIC_IDENTITY","CONFIRMED_SAME_SYNTHETIC_IDENTITY","UNCERTAIN_HARD_STOP"]},"model_route_receipt":{"pattern":"^route-receipt:[A-Za-z0-9_-]{16,192}$","type":"string"},"pair_id":{"maxLength":128,"minLength":1,"pattern":"^[A-Za-z0-9_-]+$","type":"string"},"policy_version":{"const":"p2-m5-cc04-b-e01-sol-max-duplicate-review-v1"},"reason_code":{"enum":["DISTINCT_IDENTITY_VISUAL_EVIDENCE","EXACT_DUPLICATE_VISUAL_MATCH","REENCODED_DUPLICATE_VISUAL_MATCH","CROP_RESIZE_LIGHTING_VARIANT_SAME_IDENTITY","AMBIGUOUS_OR_INSUFFICIENT_VISUAL_EVIDENCE","UNTRUSTED_IMAGE_CONTENT_PREVENTS_REVIEW"]},"review_sequence":{"const":1},"reviewer_role":{"const":"CC04_B_SOL_MAX_REVIEW_ONLY"},"timestamp":{"format":"date-time","pattern":"Z$","type":"string"}},"required":["pair_id","policy_version","reviewer_role","decision","reason_code","review_sequence","model_route_receipt","timestamp"],"type":"object"}
```

The schema's `oneOf` clauses make every decision/reason mapping machine-enforced rather than prose-only. The final
governed review record must be one JSON object and nothing else. `pair_id` must exactly echo the input; the
timestamp must be injected from an authority-issued UTC clock; and the route receipt must be injected from verified
runtime evidence, never supplied by the reviewer. The envelope builder must reject any model payload that already
contains either field. Decision/reason pairs are restricted to:

- `DISTINCT_SYNTHETIC_IDENTITY` with `DISTINCT_IDENTITY_VISUAL_EVIDENCE`;
- `CONFIRMED_SAME_SYNTHETIC_IDENTITY` with `EXACT_DUPLICATE_VISUAL_MATCH`,
  `REENCODED_DUPLICATE_VISUAL_MATCH`, or `CROP_RESIZE_LIGHTING_VARIANT_SAME_IDENTITY`;
- `UNCERTAIN_HARD_STOP` with `AMBIGUOUS_OR_INSUFFICIENT_VISUAL_EVIDENCE` or
  `UNTRUSTED_IMAGE_CONTENT_PREVENTS_REVIEW`.

Free text, confidence prose or score, face description, age judgment, race/ethnicity/ancestry/nationality judgment,
beauty judgment, style preference, personality judgment, identity name, celebrity similarity, recommendation,
QuestionBank ranking, and every additional property are prohibited in both the model payload and final envelope. A
missing or invalid payload, missing runtime attestation, or invalid envelope is not repaired or reinterpreted; it
returns `SOL_MAX_REVIEW_DECISION_SCHEMA_MISMATCH` and hard-stops execution.

Before exactly-once append, the trusted boundary must hash the canonical input object, raw six-field model payload, and
final eight-field envelope; verify the pair ID, both output digests, policy version/digest, pHash version/distance, and
pair order against the scheduler; and bind those hashes plus the route receipt and authority timestamp into the
append-only sink's internal custody record. These binding fields are not reviewer output and do not expand the Owner's
eight-field final envelope. MR01 must hard-stop on missing, forged, model-authored, mismatched, replayed, or duplicate
attestation/binding evidence.

## Threat model and fail-closed controls

The separate qualifications must test and close at least these threats:

1. transcript, ordinary attachment, tool-result, log, CI, MEMORY, or Git leakage of Prompt or private bytes;
2. Downloads, Desktop, temporary folder, browser/cache/clipboard, shared-cache, or post-hoc custody fallback;
3. symlink, junction, reparse, mount-alias, cross-task, sibling-Agent, or P2-M7 private-root confusion;
4. path, locator, object-key, URL, credential, Provider-payload, or private receipt overexposure;
5. generator/reviewer context contamination and reviewer access to specification or downstream evidence;
6. route fallback, exact-route ambiguity, hidden tool inheritance, shell/network availability, or review-role simulation;
7. image prompt injection, text/watermark instructions, sensitive inference, beauty selection, or free-text output;
8. malformed model payload or envelope, extra fields, model-authored attestation, missing pair, replay, duplicate
   append, retry, second opinion, or order effect;
9. mutable decision records, incorrect pair binding, forged or missing authority timestamp/route receipt, or
   incomplete operation accounting;
10. qualification fixtures leaking into E01, post-hoc threshold changes, QuestionBank escalation, or M6 boundary drift;
11. unknown model/provider terms, telemetry, retention, provenance, exact model ID, snapshot, runtime, cost, or usage.

An unclosed threat cannot be accepted by oral explanation. It yields `BLOCKED_PRIVATE_SINK_CAPABILITY`,
`BLOCKED_SOL_MAX_REVIEWER_QUALIFICATION`, `BLOCKED_SECURITY_PRIVACY_LICENSE`, `FURTHER_RESEARCH`, or `FAILED` as
applicable.

## Qualification DAG and execution-authority checkpoint

The only authorized forward sequence is:

1. accept this change control with same-SHA CI, all eight artifacts, independent Security/Privacy/License/Research
   Integrity review, independent Sol High review, and Principal acceptance;
2. create and accept only `CC04-B-DS01 DESTINATION_BOUND_PRIVATE_SINK_QUALIFICATION`;
3. after DS01 acceptance, create and accept only `CC04-B-MR01 SOL_MAX_DUPLICATE_REVIEWER_QUALIFICATION`;
4. after both capabilities are proven, create and accept a new E01 execution-authority checkpoint;
5. confirm all generation, output, private-state, and ordinal counters still equal zero;
6. only then create private custody state and allow tranche 1 with at most four generation calls.

The reviewer qualification must preregister its fixture manifest digest and success/failure rules before showing any
formal E01 output. It must include exact route binding, fallback negative control, fresh-context isolation, absence of
generator context, private pair view, no exfiltration, no path exposure, strict schema, prompt-injection/text/watermark
tests, exact and re-encoded duplicates, crop/resize/lighting variants, similar morphology but distinct identity,
clearly distinct identities, ambiguous cases, repeat determinism, order independence, failure/timeout, append-only
integrity, zero retry, operation accounting, and all required independent reviews.

- `OPTION_C_QUALIFICATION_DAG: CHANGE_CONTROL_THEN_DS01_THEN_MR01_THEN_EXECUTION_AUTHORITY_CHECKPOINT`
- `NEXT_READY_TASK: CC04-B-DS01_DESTINATION_BOUND_PRIVATE_SINK_QUALIFICATION_CONTRACT_ONLY`
- `REVIEWER_RUNTIME_CREATION: PROHIBITED_IN_THIS_TASK`
- `EXECUTION_AUTHORITY_CHECKPOINT: NOT_CREATED`
- `CC04_B_EXECUTION: CLOSED_PENDING_OPTION_C_CAPABILITY_QUALIFICATIONS_AND_NEW_EXECUTION_AUTHORITY`

## Model provenance and qualification state

The planning selection is not runtime proof:

- `REVIEW_MODEL_ROUTE: SOL_MAX`
- `REVIEW_MODEL_FAMILY: gpt-5.6-sol`
- `REVIEW_MODEL_EXACT_ID: UNKNOWN_OR_NULL`
- `REVIEW_MODEL_SNAPSHOT: UNKNOWN_OR_NULL`
- `REVIEW_RUNTIME_VERSION: UNKNOWN_OR_NULL`
- `REVIEW_POLICY_VERSION: p2-m5-cc04-b-e01-sol-max-duplicate-review-v1`
- `REVIEW_POLICY_DIGEST: 725b870ac8c93ac50c62badc9553a3cd0706ae84dbee29bab0b16df53889f410`
- `REVIEW_INPUT_SCHEMA_DIGEST: 9c201c70a0ab7f80cab1135be17d00bc5b6a0935a3df2bf7c5faa579b6c130d4`
- `REVIEW_MODEL_DECISION_SCHEMA_DIGEST: 6370ba1b1f726ecbd8395c4e4da3b93dee5f09c53413dc6b1e86a6c7e848cc72`
- `REVIEW_OUTPUT_SCHEMA_DIGEST: 68fdbb268451c75151be0674dcb4d328b46d2c3f97b4a7d232ca103ba78acc71`
- `ROUTE_RECEIPT: NOT_PROVEN`
- `ROUTE_LEVEL_PROVENANCE_SUFFICIENT_FOR_PRIVATE_INTERNAL_RESEARCH: PENDING_MR01_QUALIFICATION`
- `MODEL_PROVIDER_TERMS_AND_RETENTION_EVIDENCE: UNKNOWN_OR_NULL`

MR01 must decide `PASS`, `FURTHER_RESEARCH`, or `BLOCKED` for route-level provenance sufficiency. Unknown fields remain
unknown; no exact model snapshot, runtime receipt, usage, cost, retention, telemetry, license, or output-rights fact may
be invented.

## Resource accounting and budget separation

Formal E01 accounting remains frozen:

- `BASE_VISION_AND_MEASUREMENT: 736`
- `PHASH_HAMMING_COMPARISONS: 496`
- `SOL_MAX_GOVERNED_PAIR_REVIEWS: 496`
- `INCLUSIVE_MAXIMUM: 1728`
- `GLOBAL_CEILING: 2500`
- `REMAINING_HEADROOM: 772`
- `TRANSFORM_OPERATION_ALLOWED_IN_04_B: 0`

The arithmetic is `736 + 496 + 496 = 1728 < 2500`. Sol Max pair review remains a governed review operation and cannot
be omitted because it runs in a subagent. Qualification fixtures and formal E01 outputs are disjoint. This task
authorizes zero qualification or E01 operations. DS01 and MR01 must preregister their own operation, storage, runtime,
and fixture budgets. Qualification counts may not be charged to formal E01, charged twice, hidden in another category,
or implicitly use the 772 headroom; any required allocation from the global ceiling needs explicit prospective
authority before the operation.

- `QUALIFICATION_OPERATION_BUDGET_AUTHORITY: NOT_CREATED`
- `QUALIFICATION_OPERATIONS_CONSUMED: 0`
- `FORMAL_E01_OPERATIONS_CONSUMED: 0`
- `QUALIFICATION_AND_E01_BUDGET_COMMINGLING: PROHIBITED`

The Owner envelope otherwise remains 32 calibration calls, 32 raw outputs, a target of 24 independent
cluster-adjusted identities, one output per call, concurrency one, automatic retries zero, four calls per tranche, 64
total native outputs across calibration and holdout, 8 GiB private storage, and zero transforms in 04-B.

## Admission, M5, M6, and QuestionBank boundary

The reviewer provides one evidence item only. Existing Q01, V01, P01, O01, and deterministic PostgreSQL Gates retain
admission authority. The reviewer cannot create or change an Asset, SyntheticIdentity, assignment, morphology cell,
cohort, or cluster. Only an atomic admission after every hard Gate passes may add a qualifying identity to the fresh
calibration cohort.

- `M5_SELECTION_DESTINATION: FRESH_CALIBRATION_COHORT_ONLY`
- `CALIBRATION_COHORT_STATUS: NOT_CREATED`
- `QUESTIONBANK_ENTRY: PROHIBITED_UNTIL_M5_TECHNICAL_GATE_AND_P2_MVR_V1_PASS_AND_M6_RELEASE_AUTHORITY`
- `FUTURE_INTERNAL_QUESTIONBANK_SYNTHETIC_SOURCE_PREFERENCE: CODEX_NATIVE_IMAGEGEN`
- `FUTURE_QUESTIONBANK_GENERATION_MODE: OFFLINE_ONLY`
- `FUTURE_QUESTIONBANK_REVIEWER_PREFERENCE: INDEPENDENT_QUALIFIED_SOL_MAX_REVIEW_ONLY_AGENT`
- `P2_MVR_V1_RESULT: NOT_EVALUATED`
- `P2_M6_ENTRY: CLOSED_PENDING_TECHNICAL_AND_MVR_PASS`

Future intent does not approve M6, QuestionBank release, production, public access, real-user processing, or runtime
generation. M5 output may remain only private raw output, normalized Asset, QA and duplicate evidence, calibration
SyntheticIdentity, and calibration cohort membership after their own Gates.

## Changed paths, validation, and stop conditions

This change-control candidate is limited to:

1. `docs/operations/P2_M5_CC04_B_E01_SOL_MAX_REVIEW_CHANGE_CONTROL_CONTRACT.md`;
2. `docs/research/P2_M5_CC04_B_E01_SOL_MAX_REVIEW_CHANGE_CONTROL.md`;
3. `docs/operations/P2_M5_ACCEPTANCE.md`;
4. `docs/operations/P2_M5_EXECUTION_PROTOCOL.md`.

It may not change implementation, schema, migration, OpenAPI, Worker, dependency, model, Provider, CI workflow,
MILESTONES, MEMORY, M6, P2-M7, or any private state. Acceptance requires the exact allowlist, scoped formatting,
`git diff --check`, exact policy and all three schema byte-length/digest checks, canonical/mirror equality, true-EOF last
occurrence and sentinel checks, `1728 < 2500` accounting, zero private leakage, zero generation markers, same-SHA CI,
all eight artifact content checks, independent Security/Privacy/License/Research Integrity and Sol High reviews, and
Principal acceptance.

Any new dependency, model, SDK, external Provider, paid service, public API, credential, network relaxation, private
data flow, or resource-envelope increase returns to the Owner. Reject or repair only with a normal forward commit;
never amend, reset, rebase, merge, force-push, or create a post-acceptance status commit.

## Candidate result and next task

- `SOL_MAX_REVIEW_CHANGE_CONTROL_RESULT: PASS_AT_THIS_COMMIT_AFTER_ALL_GATES`
- `GENERATION_CALLS_EXECUTED: 0`
- `RAW_OUTPUTS_CREATED: 0`
- `REQUEST_ORDINAL_CONSUMED: NONE`
- `PRIVATE_ROOT_OR_LOCATOR_CREATED: NO`
- `GENERATION_SPECIFICATION_CREATED: NO`
- `ASSET_IDENTITY_OR_COHORT_CREATED: NO`
- `P2_M5_STATE: EXECUTING`
- `NEXT_READY_TASK: CC04-B-DS01_DESTINATION_BOUND_PRIVATE_SINK_QUALIFICATION_CONTRACT_ONLY`
- `STOP_OUTCOME: SOL_MAX_REVIEW_CHANGE_CONTROL_ACCEPTED_AFTER_ALL_GATES`

Acceptance stops here. It does not start DS01, MR01, reviewer execution, private setup, generation, admission, MVR, M6,
or QuestionBank work.
