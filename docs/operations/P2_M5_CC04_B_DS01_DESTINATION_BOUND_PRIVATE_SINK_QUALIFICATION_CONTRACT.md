# P2-M5 CC04-B DS01 Destination-Bound Private Sink Qualification Contract

## Status and bounded authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: CC04-B-DS01-C01`
- `PARENT_QUALIFICATION_ID: CC04-B-DS01`
- `TASK_NAME: Destination-Bound Private Sink Qualification Contract Only`
- `OWNER_DECISION_ID: OD-P2-M5-CC04-B-E01-001`
- `OWNER_SELECTION: OPTION_C`
- `GOVERNANCE_CLASSIFICATION: OPTION_C_EXPLICIT_REVIEW_WORKFLOW_CHANGE_CONTROL`
- `BASELINE_SHA: 94cbc5e4c4338cfe809de7ddd4bfdc879ca4643a`
- `CURRENT_AUTHORITY: p2-m5-cc04-b-e01-option-c-sol-max-review-change-control-eof/v1`
- `CONTRACT_CANDIDATE: THIS_COMMIT`
- `AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`
- `PRE_CONDITION_CURRENT_STATE: RWCC01_ACCEPTED;PRIVATE_SETUP_NOT_CREATED;GENERATION_CALLS=0;RAW_OUTPUTS=0;REQUEST_ORDINAL=NONE`

This is a capability-qualification contract only. It freezes how a later `CC04-B-DS01-Q01` task may determine
whether Codex native image generation can write directly into a destination-bound private sink without exposing image
bytes or private references to an ordinary conversation, transcript, attachment, tool result, download path, cache,
Git, CI, MEMORY, or unrelated Agent context. It does not qualify a sink, invoke image generation, create a private
root or locator, create a Prompt or GenerationSpecification, consume an ordinal, or open E01 execution.

## Inherited source, custody, and execution boundary

- `SOURCE_KIND: CODEX_NATIVE_IMAGEGEN`
- `SOURCE_SCOPE: PRIVATE_INTERNAL_RESEARCH_ONLY`
- `PROVENANCE_LEVEL: PROVENANCE_ONLY`
- `PRIVATE_INPUT_CUSTODIAN: PRINCIPAL`
- `PRIVATE_OUTPUT_CUSTODIAN: PRINCIPAL`
- `PRIVATE_REGISTRY_AUTHORITY: PRINCIPAL_PRIVATE_OUTPUT_REGISTRY`
- `PRIVATE_SINK_INTERFACE: DESTINATION_BOUND_DIRECT_WRITE_RETURNING_REDACTED_RECEIPT_METADATA_ONLY`
- `PRODUCTION_PROVIDER_APPROVAL: NOT_GRANTED`
- `PRODUCTION_GENERATION_STATUS: FAIL_CLOSED`
- `QUESTIONNAIRE_RUNTIME_GENERATIVE_CALLS: 0`

ADR-026, ADR-049, the Principal-Managed Private Input Delegation Protocol, P01, O01, the E01 execution contract, and
the accepted Option C review-workflow change control remain binding. This contract does not convert Codex into a
programmatic runtime Provider, approve an API credential, select a paid service, relax retention, or authorize real
user, production, M6, QuestionBank, holdout, transform, or measurement work.

## Contract-stage zero-state

- `DS01_CONTRACT_GENERATION_CALL_BUDGET: 0`
- `DS01_CONTRACT_RAW_OUTPUT_BUDGET: 0`
- `DS01_CONTRACT_PRIVATE_STORAGE_BUDGET: 0_BYTES`
- `DS01_CONTRACT_PRIVATE_ROOT_CREATION: PROHIBITED`
- `DS01_CONTRACT_PRIVATE_LOCATOR_CREATION: PROHIBITED`
- `DS01_CONTRACT_PROMPT_CREATION: PROHIBITED`
- `DS01_CONTRACT_GENERATION_SPECIFICATION_CREATION: PROHIBITED`
- `DS01_CONTRACT_REQUEST_ORDINAL_CONSUMPTION: PROHIBITED`
- `DS01_CONTRACT_REVIEWER_RUNTIME_CREATION: PROHIBITED`
- `DS01_QUALIFICATION_EXECUTION: NOT_STARTED`

The formal E01 counters remain `GENERATION_CALLS_EXECUTED=0`, `RAW_OUTPUTS_CREATED=0`, and
`REQUEST_ORDINAL_CONSUMED=NONE`. No qualification output may be hidden in a calibration or holdout budget. No private
state exists merely because this contract describes its future shape.

## Canonical destination-bound policy

- `PRIVATE_SINK_POLICY_VERSION: p2-m5-cc04-b-ds01-destination-bound-private-sink-v1`
- `PRIVATE_SINK_POLICY_CANONICAL_UTF8_BYTE_LENGTH: 563`
- `PRIVATE_SINK_POLICY_SHA256: e1501ac8c3c05010d211aeed7b407c3642e414ff98ed2cc7d619158ee39b9b7d`

The sole canonical policy payload source is the RFC 8259 JSON string literal on the next line:

```json
"p2-m5-cc04-b-ds01-destination-bound-private-sink-v1|source=CODEX_NATIVE_IMAGEGEN|scope=PRIVATE_INTERNAL_RESEARCH_ONLY|delivery=DIRECT_TO_TASK_SCOPED_CREATE_ONCE_GIT_EXTERNAL_ROOT|ordinary_result=REDACTED_RECEIPT_METADATA_ONLY|prompt_plaintext=0|image_bytes=0|data_url=0|private_path=0|root_name=0|locator=0|object_key=0|signed_url=0|credential=0|provider_payload=0|receipt_before_decode=1|receipt_before_result=1|intermediate_landing=NONE|posthoc_custody=0|generation_calls_during_qualification=0|raw_outputs_during_qualification=0|root_creation_during_contract=0"
```

A validator must JSON-decode that literal, encode the resulting 563 Unicode scalar values as UTF-8 without BOM, and
hash exactly those bytes. Markdown, fence delimiters, quotes, CR, LF, and trailing newline are excluded. A mismatch
returns `BLOCKED_PRIVATE_SINK_POLICY_AUTHORITY_MISMATCH` before any private or generation operation.

## Current runtime-interface observation

The current Codex session exposes a read-only tool schema observation, not a capability PASS:

- `CURRENT_SESSION_IMAGEGEN_TOOL_NAME: image_gen__imagegen`
- `CURRENT_SESSION_IMAGEGEN_SCHEMA_SNAPSHOT_VERSION: p2-m5-cc04-b-ds01-current-session-imagegen-interface-v1`
- `CURRENT_SESSION_IMAGEGEN_SCHEMA_SNAPSHOT_CANONICAL_UTF8_BYTE_LENGTH: 226`
- `CURRENT_SESSION_IMAGEGEN_SCHEMA_SNAPSHOT_SHA256: 4c4f20ba9db866a9646d48ca4019af888a0f286c9af29094d4235e2775817df1`
- `CURRENT_SESSION_IMAGEGEN_DESTINATION_PARAMETER: ABSENT_IN_OBSERVED_SCHEMA`
- `CURRENT_SESSION_IMAGEGEN_DELIVERY_INSTRUCTION: RETURN_IMAGE_WITH_GENERATED_IMAGE_RESULT`
- `CURRENT_SESSION_IMAGEGEN_INTERFACE_CAPABILITY: NOT_PROVEN`
- `IMAGEGEN_CALL_EXECUTED_FOR_SCHEMA_OBSERVATION: NO`

The canonical observation payload is:

```text
{"arguments":["num_last_images_to_include","prompt","referenced_image_paths"],"delivery_instruction":"RETURN_IMAGE_WITH_GENERATED_IMAGE_RESULT","destination_parameter":null,"name":"image_gen__imagegen","return_type":"unknown"}
```

The absence of a destination parameter and the ordinary generated-image delivery instruction mean the observed
interface cannot be treated as destination-bound evidence. The observation does not prove that no future platform
capability can exist; Q01 must snapshot the actual interface again and fail closed if no separately scoped mechanism
or authoritative platform attestation is available.

## Official OpenAI documentation observation

- `OFFICIAL_OPENAI_DOCUMENTATION_URL: https://developers.openai.com/api/docs/guides/image-generation`
- `OFFICIAL_OPENAI_DOCUMENTATION_RETRIEVED_AT_UTC: 2026-08-23T16:05:20Z`
- `OFFICIAL_OPENAI_DOCUMENTATION_HTTP_STATUS: 200`
- `OFFICIAL_OPENAI_DOCUMENTATION_CONTENT_BYTES: 1220386`
- `OFFICIAL_OPENAI_DOCUMENTATION_CONTENT_SHA256: 41d168c0e5696c7ac7c36e9515f676ba22e08a6b64233d2fc5090e84fa4cc5dc`
- `OFFICIAL_OPENAI_DOCUMENTATION_ETAG: 84adb81f98017af7c02ffc4d1d34c3a5`
- `OFFICIAL_OPENAI_DOCUMENTATION_LAST_MODIFIED_UTC: 2026-08-23T03:14:15Z`
- `DOCUMENTED_IMAGE_API_DELIVERY: B64_JSON_IN_API_RESPONSE`
- `DOCUMENTED_RESPONSES_API_DELIVERY: IMAGE_GENERATION_CALL_RESULT_BASE64_IN_RESPONSE`
- `DOCUMENTED_DESTINATION_BOUND_PRIVATE_SINK: NOT_ESTABLISHED_BY_FETCHED_PAGE`
- `DOCUMENTATION_EVIDENCE_CLASS: DOCUMENTATION_ONLY_NOT_RUNTIME_CAPABILITY_PROOF`

The fetched official page shows client-side Base64 result decoding for both the Image API and Responses image
generation tool. That delivery path is not eligible for DS01 because bytes first enter an ordinary API response. The
page is useful negative documentation evidence only: it neither proves the Codex desktop tool's internal custody nor
establishes transcript suppression, direct write, a task-scoped handle, receipt-before-result, or create-once root
semantics. Q01 may refresh official documentation but must retain the retrieved page identity and must not infer a
private capability from silence or marketing language.

## Admissible and rejected mechanism classes

Q01 may examine only an already available mechanism that requires no generation call, output creation, credential,
new dependency, new model, new Provider, or network relaxation:

1. a platform-native destination-bound private attachment or sink handle;
2. a platform-provided private sink callback whose bytes never enter the ordinary result channel;
3. a pre-existing, separately isolatable local secure-capture bridge that receives bytes before any ordinary result;
4. another explicitly documented direct-write mechanism with equivalent task, custody, and transcript guarantees.

The following are categorically ineligible:

- the observed ordinary `generatedImage(result)` path;
- Image API or Responses API Base64 result decoding;
- a new API key, SDK, programmatic Provider, browser automation, unofficial endpoint, or paid service;
- post-hoc download, ordinary attachment, browser cache, clipboard, Downloads, Desktop, ordinary temp, shared cache,
  object URL, signed URL, data URL, or filesystem search;
- decoding a result and then copying it into a private root;
- retroactive digest, locator, or custody-receipt registration;
- a hidden cache whose location, authority, retention, cleanup, or access boundary is assumed rather than proved.

A candidate that changes the source from Codex native image generation, adds a dependency/model/SDK/credential, uses
a paid or external Provider, relaxes network or transcript boundaries, or requires a generation probe returns to the
Owner before execution. It cannot be accepted as a DS01 implementation detail.

## Required destination-bound interface semantics

A positive qualification requires all of these properties from the exact future invocation interface:

1. Principal supplies an opaque task-scoped sink capability out of band; the generator never receives or returns a
   private path, root name, locator, object key, URL, credential, or parent capability.
2. The interface writes the exact returned bytes directly and atomically into one create-once, Git-external root;
   there is no ordinary attachment, transcript, result-payload, download, cache, clipboard, or fallback landing.
3. The custody boundary computes exact-byte SHA-256, media type, byte count, authority, retention, and cleanup binding
   and appends one immutable receipt before decode, image view, review, QA, or ordinary result emission.
4. The ordinary result contains exactly the six redacted receipt fields defined below and no image bytes, Base64,
   data URL, path, root name, locator, key, URL, credential, Provider payload, Prompt, or free text.
5. Partial output, cancellation, timeout, process crash, duplicate delivery, and receipt-append failure never expose
   bytes, fabricate success, reuse an ordinal, create a second root, or silently fall back. Uncommitted bytes are
   removed through the same exact capability with retained redacted failure evidence.
6. One invocation can create at most one registered output. Duplicate callbacks are idempotently rejected or mapped
   to the same exact receipt; they never create a second output or erase request/output accounting.
7. Recovery begins only from the exact Principal registry receipt or task-scoped handle. Disk scanning, parent
   enumeration, sibling lookup, legacy-root reuse, and Owner re-upload substitution are prohibited.
8. The capability is unavailable to sibling or recursive Agents, and no ordinary subagent inherits the root, handle,
   locator, shell path, or byte stream.

Configuration text, a tool name, a successful generic generation, a screenshot, an undocumented cache, a normal file
write after result delivery, or an Agent's statement is not sufficient evidence.

## Redacted receipt metadata schema

- `PRIVATE_SINK_RECEIPT_SCHEMA_VERSION: p2-m5-cc04-b-ds01-redacted-receipt-v1`
- `PRIVATE_SINK_RECEIPT_SCHEMA_CANONICAL_UTF8_BYTE_LENGTH: 595`
- `PRIVATE_SINK_RECEIPT_SCHEMA_SHA256: 57e6ba038f4f5e0fb838a777a2c5761085688085cc04aa560773ba42a8882d33`

The exact minified RFC 8259 JSON Schema 2020-12 payload is:

```text
{"additionalProperties":false,"properties":{"byte_count":{"maximum":134217728,"minimum":1,"type":"integer"},"custody_receipt_id":{"maxLength":128,"minLength":1,"pattern":"^[A-Za-z0-9_-]+$","type":"string"},"media_type":{"enum":["image/jpeg","image/png","image/webp"]},"opaque_output_id":{"maxLength":128,"minLength":1,"pattern":"^[A-Za-z0-9_-]+$","type":"string"},"sha256":{"pattern":"^[0-9a-f]{64}$","type":"string"},"status":{"const":"CUSTODY_REGISTERED_BEFORE_ORDINARY_RESULT"}},"required":["opaque_output_id","sha256","media_type","byte_count","custody_receipt_id","status"],"type":"object"}
```

Hash the UTF-8 payload without BOM or trailing newline. This schema describes the only future ordinary result shape;
it does not create a receipt or prove that a runtime can produce one. Receipt IDs and output IDs are opaque public
identifiers, not private locators. The receipt's internal registry record retains the private locator and full custody
binding outside Git and ordinary Agent context.

## Q01 qualification scope and zero-generation metadata-only budget

The separately accepted Q01 task may perform only:

- read-only current runtime schema and capability inventory;
- read-only official documentation refresh;
- inspection of a platform-issued interface contract or capability attestation;
- a zero-output handshake only if authoritative runtime evidence proves it cannot call a model, create bytes, allocate
  storage, create a private root/locator, or consume an ordinal;
- deterministic first-party validator tests using inline non-image metadata fixtures, which can validate the policy
  and receipt schema but cannot prove the native generation path.

Q01 has these hard budgets:

- `QUALIFICATION_OPERATION_BUDGET_AUTHORITY: CREATED_FOR_DS01_Q01_ZERO_MODEL_ZERO_IMAGE_METADATA_ONLY`
- `DS01_Q01_QUALIFICATION_ATTEMPT_MAX: 1`
- `DS01_Q01_TOTAL_CHARGEABLE_OPERATION_MAX: 8`
- `DS01_Q01_CURRENT_RUNTIME_SCHEMA_INVENTORY_READ_MAX: 1`
- `DS01_Q01_OFFICIAL_DOCUMENTATION_REQUEST_MAX: 1`
- `DS01_Q01_PLATFORM_CAPABILITY_METADATA_REQUEST_MAX: 1`
- `DS01_Q01_ZERO_OUTPUT_HANDSHAKE_MAX: 1`
- `DS01_Q01_VALIDATOR_INVOCATION_MAX: 4`
- `DS01_Q01_PER_OPERATION_ATTEMPT_MAX: 1`
- `DS01_Q01_RETRY_MAX: 0`
- `DS01_Q01_CONCURRENCY_MAX: 1`
- `DS01_Q01_NETWORK_OR_PLATFORM_REQUEST_TIMEOUT_SECONDS_MAX: 30`
- `DS01_Q01_VALIDATOR_TIMEOUT_SECONDS_PER_INVOCATION_MAX: 60`
- `DS01_Q01_VALIDATOR_CUMULATIVE_RUNTIME_SECONDS_MAX: 240`
- `DS01_Q01_TOTAL_WALL_CLOCK_SECONDS_MAX: 1800`
- `DS01_Q01_OFFICIAL_DOCUMENTATION_RESPONSE_BYTE_MAX: 2097152`
- `DS01_Q01_PLATFORM_METADATA_RESPONSE_BYTE_MAX: 262144`
- `DS01_Q01_ZERO_OUTPUT_HANDSHAKE_RESPONSE_BYTE_MAX: 262144`
- `DS01_Q01_TOTAL_TRANSIENT_RESPONSE_BYTE_MAX: 2621440`
- `DS01_Q01_INLINE_NON_IMAGE_METADATA_FIXTURE_COUNT_MAX: 32`
- `DS01_Q01_INLINE_NON_IMAGE_METADATA_FIXTURE_BYTE_MAX_EACH: 4096`
- `DS01_Q01_INLINE_NON_IMAGE_METADATA_FIXTURE_TOTAL_BYTE_MAX: 131072`
- `DS01_Q01_IMAGE_OR_BINARY_FIXTURE_BYTE_MAX: 0`
- `DS01_Q01_TRACKED_REDACTED_EVIDENCE_FILE_MAX: 3`
- `DS01_Q01_TRACKED_REDACTED_EVIDENCE_STORAGE_BYTE_MAX: 262144`
- `DS01_Q01_UNTRACKED_PRIVATE_OR_TEMPORARY_STORAGE_BYTE_MAX: 0`
- `DS01_Q01_DOCUMENTATION_OR_PLATFORM_RESPONSE_PERSISTENCE_BYTE_MAX: 0`
- `DS01_Q01_MODEL_OR_PROVIDER_REQUEST_MAX: 0`
- `DS01_Q01_PROMPT_OR_CREDENTIAL_BYTE_MAX: 0`
- `DS01_Q01_GENERATION_CALL_MAX: 0`
- `DS01_Q01_RAW_OUTPUT_MAX: 0`
- `DS01_Q01_PRIVATE_ROOT_MAX: 0`
- `DS01_Q01_PRIVATE_LOCATOR_MAX: 0`
- `DS01_Q01_IMAGE_BYTE_MAX: 0`
- `DS01_Q01_REQUEST_ORDINAL_MAX: 0`
- `DS01_Q01_TRANSFORM_OPERATION_MAX: 0`
- `DS01_Q01_VISION_OR_MEASUREMENT_OPERATION_MAX: 0`
- `DS01_Q01_NETWORK_SCOPE: OFFICIAL_OPENAI_DOCUMENTATION_READ_ONLY_OR_PLATFORM_CAPABILITY_METADATA_ONLY`

The chargeable-operation arithmetic is exactly `1 + 1 + 1 + 1 + 4 = 8`: one current-runtime schema inventory,
one official-documentation request, one platform-capability metadata request, at most one zero-output handshake, and at
most four deterministic validator invocations. An attempt is charged when it starts, including a failed, timed-out, or
empty attempt. The overall qualification, every operation, and every target have one attempt only; no retry, parallel
attempt, alternate endpoint, redirect-based scope expansion, or second qualification run is authorized. The handshake
is optional and remains prohibited unless authority available before the attempt proves that it cannot call a model or
Provider, accept a Prompt or credential, allocate storage, create bytes/root/locator, or consume an ordinal.

The response-byte ceilings cover transient in-process receipt only and use the exact arithmetic
`2097152 + 262144 + 262144 = 2621440`; response bodies, caches, attachments, downloads, and temporary files may not be
persisted. Tracked evidence is limited to redacted digests, headers, schema/attestation metadata, counters, validator
results, and the three task-authorized Markdown files. Fixtures must be inline UTF-8 non-image metadata; their maximum
is `32 * 4096 = 131072` bytes, and they may contain neither image/binary bytes nor a real Prompt, credential, locator,
path, object key, signed URL, or Provider payload. Each validator invocation runs serially for at most 60 seconds; its
cumulative validator runtime is at most 240 seconds, and the whole Q01 attempt is at most 1800 wall-clock seconds.

These are ceilings, not a requirement to spend the allowance. Q01 must record every charged operation, byte count,
fixture count, file count, and runtime in tracked redacted evidence. Reaching any ceiling without complete positive
proof returns the applicable blocked, further-research, or failed outcome; Q01 cannot raise a ceiling, restart the
attempt, or silently reclassify an operation. Any prospective budget change requires a separate forward contract
change with the same full acceptance Gates before the changed operation occurs.

These operations do not consume or enlarge the formal E01 `1728` operation envelope, the 32 calibration outputs, the
future 32 holdout outputs, or the 64-output global ceiling. If positive qualification requires even one actual
generation, image byte, root, locator, Prompt, API credential, or provider request, Q01 must return
`BLOCKED_PRIVATE_SINK_CAPABILITY` or an Owner decision pack; it may not borrow a formal ordinal before the new E01
execution-authority checkpoint.

## Preregistered evidence matrix

Q01 must produce tracked, redacted evidence for every row without private values:

| Gate                   | Required positive evidence                                             | Mandatory negative control                                                        | Failure result                     |
| ---------------------- | ---------------------------------------------------------------------- | --------------------------------------------------------------------------------- | ---------------------------------- |
| exact interface        | versioned schema or platform attestation binds the future invocation   | ordinary imagegen and API Base64 paths are rejected                               | `BLOCKED_PRIVATE_SINK_CAPABILITY`  |
| direct write           | authoritative guarantee of no intermediate ordinary result or landing  | post-hoc copy and cache recovery are rejected                                     | `BLOCKED_PRIVATE_SINK_CAPABILITY`  |
| transcript suppression | all ordinary result fields are exactly the six-field schema            | bytes, Base64, data URL, Prompt, path, locator, key, URL and prose are rejected   | `BLOCKED_SECURITY_PRIVACY_LICENSE` |
| receipt ordering       | authority proves receipt append precedes decode, view and result       | retroactive receipt and receipt-after-result are rejected                         | `BLOCKED_PRIVATE_SINK_CAPABILITY`  |
| root semantics         | future root contract is create-once, empty, task-scoped and non-alias  | pre-existing, second, reparse, parent, shared and P2-M7 roots are rejected        | `BLOCKED_SECURITY_PRIVACY_LICENSE` |
| failure atomicity      | partial, cancel, timeout, crash and append failure remain fail closed  | fallback landing, second root and unregistered bytes are rejected                 | `BLOCKED_PRIVATE_SINK_CAPABILITY`  |
| exactly once           | callback/output/receipt binding is idempotent and replay-resistant     | duplicate callback and duplicate receipt append are rejected                      | `BLOCKED_SECURITY_PRIVACY_LICENSE` |
| custody recovery       | exact task receipt and opaque registry capability are sufficient       | disk search, parent listing, sibling lookup and Owner reconstruction are rejected | `BLOCKED_SECURITY_PRIVACY_LICENSE` |
| least privilege        | capability is unavailable to ordinary/sibling/reviewer contexts        | inherited shell path, locator, byte stream and broad handle are rejected          | `BLOCKED_SECURITY_PRIVACY_LICENSE` |
| zero-state             | generation, raw output, ordinal, root, locator and storage remain zero | any nonzero counter or private-state creation is rejected                         | `FAILED`                           |

No row may pass from prose inference, silence, generic documentation, a configuration flag, an unverified screenshot,
or a test that exercises only the metadata validator. All ten rows must pass; there is no weighted average or oral
override.

## Capability-attestation minimum fields

If Q01 relies on a platform-issued attestation, it must bind at least:

```text
ATTESTATION_AUTHORITY
ATTESTATION_VERSION
ATTESTATION_ISSUED_AT
RUNTIME_INTERFACE_VERSION
SOURCE_KIND
DESTINATION_BINDING_MODE
ORDINARY_RESULT_SCHEMA_DIGEST
DIRECT_WRITE_GUARANTEE
NO_INTERMEDIATE_LANDING_GUARANTEE
TRANSCRIPT_SUPPRESSION_GUARANTEE
RECEIPT_BEFORE_RESULT_GUARANTEE
FAILURE_ATOMICITY_GUARANTEE
TASK_ISOLATION_GUARANTEE
RETENTION_AND_CLEANUP_AUTHORITY
ATTESTATION_DIGEST_OR_SIGNATURE
```

Unknown, unsigned, self-authored, model-authored, unverifiable, scope-mismatched, expired, mutable, or marketing-only
attestation is not accepted. A local document written by this Agent cannot attest to the platform. If no authoritative
attestation or equivalent exact interface guarantee exists, the correct Q01 disposition is blocked.

## Security, privacy, license, and research integrity

- No real person, User Asset, face image, synthetic image, Prompt, Provider payload, private path, locator, object key,
  signed URL, secret, credential, or binary is read or created in C01 or Q01.
- The official documentation fetch is public read-only evidence. It does not approve API use, terms, retention,
  telemetry, model provenance, output rights, or a production Provider.
- No API/SDK is invoked, no API key is requested, and no live source/provider experiment is authorized.
- No result can weaken the clearly-adult, no-age-estimation, no-sensitive-inference, no-beauty-score,
  anti-homogenization, synthetic-only, private-internal, or production-fail-closed boundaries.
- A qualified sink would establish custody transport only. It would not qualify the Sol Max reviewer, generation
  policy, Prompt, source rights, model terms, adult/QA admission, Asset/identity creation, MVR, M6, or QuestionBank.

Independent Security, Privacy, License, Research Integrity, and Sol High reviews must separately confirm the evidence
classification and the zero-operation boundary. The same reviewer cannot substitute generic documentation for runtime
proof.

## Legal outcomes and stop rules

Q01 may end only as:

- `PRIVATE_SINK_QUALIFIED` — all evidence rows pass through an authoritative exact interface or attestation without a
  generation call, output, root, locator, Prompt, credential, or ordinal;
- `BLOCKED_PRIVATE_SINK_CAPABILITY` — the current runtime lacks or cannot prove the destination-bound interface;
- `BLOCKED_SECURITY_PRIVACY_LICENSE` — transcript, custody, terms, isolation, or review evidence is unsafe or
  insufficient;
- `FURTHER_RESEARCH` — a bounded, non-execution evidence question remains unresolved without claiming capability;
- `FAILED` — contract, zero-state, authority, tamper, or accounting integrity fails.

`BLOCKED_PRIVATE_SINK_CAPABILITY` is an expected honest result and does not authorize use of ordinary imagegen output,
API Base64, another Provider, a human download, a cache, or post-hoc custody. No result other than accepted
`PRIVATE_SINK_QUALIFIED` may open MR01.

## Changed paths and validation

C01 is limited to exactly three tracked Markdown paths:

1. `docs/operations/P2_M5_CC04_B_DS01_DESTINATION_BOUND_PRIVATE_SINK_QUALIFICATION_CONTRACT.md`;
2. `docs/operations/P2_M5_ACCEPTANCE.md`;
3. `docs/operations/P2_M5_EXECUTION_PROTOCOL.md`.

It may not modify schema, migration, OpenAPI, application/Worker code, dependency, lockfile, model, Provider, CI,
MILESTONES, MEMORY, M6, P2-M7, private storage, or another task's evidence. Acceptance requires scoped Prettier,
`git diff --check`, exact allowlist, policy/schema byte-length and digest checks, current-runtime snapshot digest,
official-document metadata verification, no-private/no-binary/no-Prompt scans, canonical/mirror exact key order and
value equality, no duplicate current keys, true-EOF sentinel checks, unchanged zero counters, exact-SHA CI, all eight
artifact content checks, independent Security/Privacy/License/Research Integrity review, independent Sol High review,
and Principal acceptance.

Reject or repair only with a normal forward child commit. Never amend, reset, rebase, merge, force-push, or create a
post-acceptance status commit.

## Candidate result and next task

- `CC04_B_DS01_CONTRACT: PASS_AT_THIS_COMMIT_AFTER_ALL_GATES`
- `CC04_B_DS01_QUALIFICATION: NOT_STARTED`
- `PRIVATE_SINK_QUALIFICATION_STATUS: CONTRACT_ACCEPTED_QUALIFICATION_NOT_STARTED_AFTER_ALL_GATES`
- `PRIVATE_OUTPUT_SINK_CAPABILITY: NOT_PROVEN`
- `TRANSCRIPT_SUPPRESSION_PROOF: NOT_PROVEN`
- `CUSTODY_RECEIPT_PROOF: NOT_PROVEN`
- `QUALIFICATION_OPERATION_BUDGET_AUTHORITY: CREATED_FOR_DS01_Q01_ZERO_MODEL_ZERO_IMAGE_METADATA_ONLY_AFTER_ALL_GATES`
- `GENERATION_CALLS_EXECUTED: 0`
- `RAW_OUTPUTS_CREATED: 0`
- `REQUEST_ORDINAL_CONSUMED: NONE`
- `PRIVATE_ROOT_OR_LOCATOR_CREATED: NO`
- `GENERATION_SPECIFICATION_CREATED: NO`
- `CC04_B_EXECUTION: CLOSED_PENDING_OPTION_C_CAPABILITY_QUALIFICATIONS_AND_NEW_EXECUTION_AUTHORITY`
- `P2_M5_STATE: EXECUTING`
- `P2_MVR_V1_RESULT: NOT_EVALUATED`
- `P2_M6_ENTRY: CLOSED_PENDING_TECHNICAL_AND_MVR_PASS`
- `NEXT_READY_TASK: CC04-B-DS01-Q01_DESTINATION_BOUND_PRIVATE_SINK_QUALIFICATION_EXECUTION_NO_GENERATION`
- `STOP_OUTCOME: DESTINATION_BOUND_PRIVATE_SINK_QUALIFICATION_CONTRACT_ACCEPTED_AFTER_ALL_GATES`

Acceptance stops C01. It opens only the separately bounded Q01 evidence task; it does not run Q01, create a private
capability, open MR01, invoke a reviewer, create private setup, generate an image, admit an Asset/identity/cohort, or
enter 04-C, MVR, M6, or QuestionBank work.
