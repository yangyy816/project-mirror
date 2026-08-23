# CC04-B-L01 Source Rights, Provenance, and Retention Review

## Status and authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: CC04-B-L01`
- `TASK_NAME: Source Rights and Provenance Review`
- `PARENT_AUTHORITY: CC-P2-M5-04-B-T01`
- `BASELINE_SHA: 827224a3f8c331d6c7774c4d6f8ca6e38d92ff72`
- `REVIEW_CANDIDATE: THIS_COMMIT`
- `AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ARTIFACT_LICENSE_SECURITY_SOL_AND_PRINCIPAL_ACCEPTANCE`
- `PRE_CONDITION_CURRENT_STATE: CC04_B_L01=REVIEW_CANDIDATE_PENDING_ACCEPTANCE; CC04_B_EXECUTION=CLOSED`

This is a review-only checkpoint. It does not invoke image generation, access private input, create a private root or locator, create an Asset or identity, form a cohort, consume quota, or authorize `CC04-B-EXECUTION`.

## Review question

Can the already Owner-selected `CODEX_NATIVE_IMAGEGEN` source proceed to the remaining 04-B pre-execution reviews under a narrow private-internal-research boundary without inventing provenance, rights, retention, model, request, usage, or cost facts?

## Inputs reviewed

- ADR-026, ADR-041, ADR-049, and ADR-050;
- the accepted CC04 Owner Decision Pack and Decision Register;
- the Fresh Study Proposal and Fresh Evidence Protocol;
- the accepted T01 bounded-task contract at `827224a3f8c331d6c7774c4d6f8ca6e38d92ff72` / run `32623064656`;
- official OpenAI image-generation documentation retrieved from `https://developers.openai.com/api/docs/guides/image-generation` on 2026-08-23.

The official API documentation describes image-generation and moderation behavior, but it does not establish a stable model ID, model snapshot, seed, request ID, usage record, monetary cost, output-rights grant, or retention commitment for the Codex desktop native generation capability used by this research line. No such fact is inferred from API documentation or product similarity.

## Source and rights disposition

- `SOURCE_KIND: CODEX_NATIVE_IMAGEGEN`
- `SOURCE_SCOPE: PRIVATE_INTERNAL_RESEARCH_ONLY`
- `SOURCE_RIGHTS_BASIS: OWNER_AUTHORIZED_INTERNAL_RESEARCH_UNDER_ADR_026`
- `SOURCE_RIGHTS_ASSERTION: NO_CLAIM_BEYOND_THE_ACCEPTED_INTERNAL_RESEARCH_SCOPE`
- `PUBLIC_DISTRIBUTION_RIGHTS: NOT_REVIEWED_NOT_GRANTED`
- `PRODUCTION_PROVIDER_APPROVAL: NOT_GRANTED`
- `PRODUCTION_GENERATION_STATUS: FAIL_CLOSED`
- `PROGRAMMATIC_PROVIDER_ADOPTION: NOT_CREATED`

This PASS is scope-specific. It means the accepted Project authority permits bounded internal research use while all unproved external rights remain unclaimed. Any source-rights conflict, distribution request, paid Provider use, production use, public release, real-person reference, User Asset, scraped image, celebrity reference, or new source requires a new Owner decision and a separate legal/license review.

## Provenance disposition

- `PROVENANCE_LEVEL: PROVENANCE_ONLY`
- `COST_ACCOUNTING_MODE: REQUEST_COUNT_ONLY`
- `MODEL_ID: UNKNOWN_OR_NULL`
- `MODEL_SNAPSHOT: UNKNOWN_OR_NULL`
- `SEED: UNKNOWN_OR_NULL`
- `PROVIDER_REQUEST_ID: UNKNOWN_OR_NULL`
- `USAGE: UNKNOWN_OR_NULL`
- `MONETARY_COST: UNKNOWN_OR_NULL`
- `COMPLETE_PROVIDER_PROVENANCE_CLAIMED: false`

Future known-fact evidence may record only source classification, the accepted GenerationSpecification version and digest, policy and coverage assignment, request count, output count, actual output digest, actual timestamps, and allowlisted disposition facts. Prompt plaintext, private path, object key, signed URL, credential, Provider payload, image bytes, and fabricated identifiers remain prohibited from Git, logs, CI artifacts, and MEMORY.

## Retention boundary

- `RETENTION_PURPOSE: AUTHORIZED_P2_M5_CALIBRATION_RESEARCH_AND_AUDIT_ONLY`
- `RETENTION_START: ONLY_AFTER_ACCEPTED_CC04_B_EXECUTION_AUTHORITY_CREATES_THE_OUTPUT`
- `RETENTION_END: M5_RESEARCH_STOP_OR_M5_CLOSURE_AFTER_REQUIRED_AUDIT_AND_CLEANUP_EVIDENCE`
- `EARLY_CLEANUP_TRIGGER: SECURITY_PRIVACY_LICENSE_SCOPE_OR_INTEGRITY_FAILURE`
- `RETENTION_EXTENSION: REQUIRES_EXPLICIT_ACTIVE_SECURITY_OR_RESEARCH_EVIDENCE_HOLD_AUTHORITY`
- `PRODUCTION_OR_PUBLIC_RETENTION: NOT_AUTHORIZED`

This review freezes the maximum purpose and lifecycle boundary, not a filesystem location. P01 must still freeze the Principal registry, create-once root, opaque locator, exact retention record, cleanup evidence, and no-discovery controls before any output is created. Rejected outputs continue to count in the raw ledger even if their private bytes are later cleaned; count and allowlisted audit facts are not erased.

## Negative controls

The remaining review and execution chain must fail closed on:

1. claiming complete Provider provenance;
2. filling unknown model, snapshot, seed, request, usage, or cost fields with placeholders;
3. using the source in production, a public API, questionnaire runtime, or a programmatic Provider Adapter;
4. using real-person, User, celebrity, influencer, internet-scraped, child, student-minor, or ambiguous-adult material;
5. logging or tracking Prompt plaintext, private paths, keys, URLs, credentials, Provider payloads, or image bytes;
6. hidden network or unreviewed source substitution;
7. retention beyond the authorized M5 purpose without explicit hold authority;
8. deleting request/output counts or rejection evidence during byte cleanup;
9. treating this review as S01, P01, Q01, O01, execution, MVR, M6, distribution, or production approval.

## Review result

- `LICENSE_AND_PROVENANCE_REVIEW: PASS`
- `PASS_SCOPE: CODEX_NATIVE_IMAGEGEN_PRIVATE_INTERNAL_RESEARCH_ONLY`
- `PASS_LIMITATION: PROVENANCE_ONLY_WITH_UNKNOWN_OR_NULL_UNEXPOSED_FIELDS`
- `NEXT_REQUIRED_REVIEW: CC04-B-S01`

The result is valid only after this exact commit passes same-SHA CI, artifact inspection, independent license/security review, independent Sol High review, and Principal acceptance. Until then L01 remains a candidate and generation remains prohibited.

## Acceptance criteria

1. All source, rights, provenance, retention, and unknown-field statements match the accepted Owner authority and ADR-026.
2. No statement claims production, distribution, complete Provider provenance, stable model identity, request identity, usage, or monetary cost.
3. The retention boundary is purpose-limited, ends at M5 stop/closure after audit, and delegates exact custody mechanics to P01.
4. No generation, private access, custody root, locator, Asset, identity, cohort, quota use, dependency, model, schema, API, workflow, MVR, M6, P2-M7, or shared-summary change occurs.
5. Acceptance and Execution Protocol contain an exact true-EOF current-authority mirror and keep 04-B execution closed.

## Validation

- scoped Markdown formatting and `git diff --check`;
- exact three-path allowlist;
- source/rights/provenance/retention and unknown-field scans;
- no generation, private input, quota, Provider, dependency, schema, API, workflow, MVR, M6, P2-M7, or binary diff;
- true-EOF, sentinel, last-occurrence, and canonical/mirror equality checks;
- same-SHA CI, all workflow artifacts, independent license/security and Sol High reviews, then Principal acceptance.

## Stop and sequencing

After L01 acceptance, stop L01 and open only `CC04-B-S01`. Do not start P01, Q01, O01, write an execution contract, create private custody, or invoke image generation in this task.
