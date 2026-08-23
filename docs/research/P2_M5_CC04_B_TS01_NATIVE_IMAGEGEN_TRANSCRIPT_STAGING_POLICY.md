# P2-M5 CC04-B TS01 Native ImageGen Transcript-Staging Research Policy

## Research status and non-execution boundary

- BOOTSTRAP_STATUS: OK
- TASK_ID: CC04-B-TS01-T01-RESEARCH
- PARENT_TASK_ID: CC04-B-TS01-T01
- OWNER_DECISION_ID: OD-P2-M5-CC04-B-DS01-003
- OWNER_SELECTION: OPTION_C
- CHANGE_CONTROL_CLASS: PROSPECTIVE_SYNTHETIC_OUTPUT_CUSTODY_POLICY_CHANGE
- QUALIFICATION_TIER: CANDIDATE
- CURRENT_STATUS: CHANGE_CONTROL_PLANNING_CANDIDATE_NOT_QUALIFIED
- APPROVED_SCOPE: NONE
- PROHIBITED_SCOPE: ALL_GENERATION_PRIVATE_SETUP_MR01_E01_EXECUTION_PRODUCTION_REAL_USER_AND_QUESTIONBANK_USE

This document preregisters the TS01 research question and qualification outcomes. It creates no fixture, output,
staging target, custody root, Prompt, ledger, reviewer, or runtime authority. The operational contract and Acceptance
true-EOF tail are canonical for current status.

## Frozen hypothesis and decision boundary

The primary hypothesis is that Codex Desktop native image generation may expose an exact generated-artifact or
attachment handle after one output is created, and that the handle may allow automatic export of the exact original
bytes to a pre-authorized Git-external staging target without disk discovery, overwrite, substitution, or retry.

The hypothesis is unproven. Owner permission to investigate it is not proof that the current session exposes a handle,
that the handle is one-to-one, that original bytes are readable, that export is lossless, or that retention, deletion,
model, usage, cost, and platform-copy facts are known.

If the hypothesis is not proven, the legal workflow falls back to Owner-mediated manual export for a later formal
ordinal. That outcome does not revive DS01's destination-bound direct-write requirement and does not make the
platform transcript copy part of Project Mirror custody.

## Frozen policy authority

- NATIVE_TRANSCRIPT_STAGING_POLICY_VERSION: p2-m5-cc04-b-e01-native-transcript-staging-v1
- NATIVE_TRANSCRIPT_STAGING_POLICY_CANONICAL_UTF8_BYTE_LENGTH: 882
- NATIVE_TRANSCRIPT_STAGING_POLICY_SHA256:
  c5b2a15f3d8801e1eba28d5a4eabb4f35b06ffb7aa3abb9747890e504ecc753a
- NATIVE_IMAGEGEN_POST_GENERATION_EXPORT_POLICY:
  AUTOMATIC_IF_EXACT_ARTIFACT_IDENTITY_CAN_BE_PROVEN
- EXPORT_MODE_PRIORITY:
  EXACT_NATIVE_GENERATED_ARTIFACT_AUTO_EXPORT_THEN_EXACT_NATIVE_ATTACHMENT_HANDLE_AUTO_EXPORT_THEN_OWNER_MEDIATED_MANUAL_EXPORT_FALLBACK
- OUTPUT_CONFIDENTIALITY_CLASS: NON_USER_SYNTHETIC_RESEARCH
- SOURCE_DELIVERY_CLASS: CODEX_DESKTOP_NATIVE_TRANSCRIPT_OR_GENERATION_RESULT
- POST_DELIVERY_CUSTODY_PROMOTION_REQUIRED: YES

The exact canonical payload and hash procedure live only in the operational contract. TS01-Q01 must verify version,
byte length, and digest before any qualification output or staging operation.

## Preregistered research questions

TS01-Q01 must answer prospectively:

1. Does the active native tool expose a platform-issued exact generated-artifact handle after a call?
2. If not, does it expose an exact attachment handle for one returned output?
3. Can the handle be proven one-to-one with both the exact call and exact output without a recent-file guess?
4. Can the handle resolve original bytes rather than a preview, screenshot, re-render, or alternative upload?
5. Can source SHA-256, media type, magic-byte class, byte size, and dimensions be obtained without directory
   enumeration, globbing, parent listing, cache/clipboard recovery, or broad discovery?
6. Can the bytes be copied automatically to a pre-authorized absent target with an ordinal-derived filename and no
   overwrite?
7. Does the staging digest exactly equal the source digest?
8. Can export failure stop without retry, replacement generation, fallback recovery, or counter refund?
9. Can all tracked evidence remain redacted while private paths, locators, Prompt, and image bytes remain outside Git,
   ordinary CI, MEMORY, reviewer packets, and ordinary status?
10. Can the capability be qualified with one explicitly non-chargeable, non-production fixture call outside formal
    E01 accounting, or is a new Owner decision required before any generation?

No answer may be inferred from tool naming, generic documentation, model reputation, a rendered chat image, an Agent
claim, a successful download, or the mere existence of an image-generation result.

## Fixture and accounting boundary

The preferred qualification input is a platform-provided exact non-production fixture facility or a separately
identified no-cost qualification output. It must be synthetic-only, contain no real person or user data, be disjoint
from calibration and holdout, use qualification ordinal TS01-FIX-001, and never be admitted as an Asset, identity,
cohort member, threshold sample, MVR evidence, or QuestionBank entry.

TS01-Q01 may dispatch at most one fixture generation only after it proves before dispatch that the call is explicitly
non-chargeable and outside formal E01. The call and any returned output count in a separate qualification ledger; no
failure is retried. Immediately before dispatch, TS01 irrevocably reserves one unit inside the frozen 64-output global
ceiling. The reservation is not refunded if no output returns or export later fails. A dispatched fixture leaves at
most 63 aggregate outputs for later calibration plus holdout; their individual maxima remain unchanged but cannot
exceed that remaining aggregate capacity. Formal E01 remains:

- formal generation calls: 0;
- formal raw outputs: 0;
- formal request ordinal: NONE;
- CAL-REQ-001: not consumed;
- calibration request-call impact: 0;
- calibration raw-output impact: 0.

Before any dispatch, the TS01 global native-output reservation consumed is 0 and remaining global capacity is 64.
Any fixture staging, promoted, retained, or temporary bytes count inside the frozen 8 GiB global private-storage hard
ceiling; there is no separate qualification storage envelope. Retained bytes remain charged until verified cleanup.

If the platform cannot prove a no-cost fixture path, TS01-Q01 stops before generation with
OWNER_DECISION_REQUIRED_FOR_SINGLE_AUTO_EXPORT_QUALIFICATION_CALL. The stop report must state that the proposed call
does not use the formal 32-call/32-raw/CAL-REQ envelope, that no global reservation has yet been consumed, and that its
platform-credit treatment requires an explicit Owner decision. If later authorized and dispatched, it consumes one
unit inside the frozen 64-output ceiling and its bytes remain inside the frozen 8 GiB ceiling; neither envelope grows.
It must not silently spend a credit, create an output, or borrow CAL-REQ-001 to see what happens.

## Auto-export evidence matrix

| Gate                 | Required positive evidence                                     | Mandatory negative control                                           | Failure disposition              |
| -------------------- | -------------------------------------------------------------- | -------------------------------------------------------------------- | -------------------------------- |
| exact call binding   | platform receipt binds one call to one handle                  | stale, recent, or cross-call handle rejected                         | NOT_PROVEN                       |
| exact output binding | one returned output maps to one handle                         | multi-output ambiguity and substitute rejected                       | NOT_PROVEN                       |
| original bytes       | handle resolves exact original bytes                           | preview, screenshot, re-render, inline data copy rejected            | NOT_PROVEN                       |
| bounded access       | exact handle access only                                       | listing, glob, scan, cache, clipboard, and history recovery rejected | FAILED if attempted              |
| source identity      | SHA-256, type, magic, size, and dimensions computed            | missing or inconsistent fact rejected                                | NOT_PROVEN                       |
| absent target        | exact staging target proven absent before copy                 | pre-existing target and overwrite rejected                           | FAILED if attempted              |
| deterministic name   | filename derives from TS01-FIX-001 or later CAL-REQ ordinal    | appearance- or timestamp-derived name rejected                       | NOT_PROVEN                       |
| lossless copy        | staging SHA-256 equals source SHA-256                          | mismatch and normalization-before-promotion rejected                 | NOT_PROVEN                       |
| redaction            | private fields and bytes absent from tracked/ordinary channels | path, locator, Prompt, data, or byte leak rejected                   | BLOCKED_SECURITY_PRIVACY_LICENSE |
| failure atomicity    | no retry, replacement, refund, or fallback recovery            | repeated generation and cache recovery rejected                      | FAILED if attempted              |

Every row must pass for NATIVE_AUTO_EXPORT_CAPABILITY: PASS. There is no weighted average, oral override, or
post-hoc explanation.

## Legal qualification results

TS01-Q01 may end with:

1. NATIVE_AUTO_EXPORT_CAPABILITY: PASS
   - OWNER_MANUAL_EXPORT_REQUIRED_BY_DEFAULT: NO
   - the exact proven generated-artifact or attachment-handle mode becomes the default for this source/scope only;
2. NATIVE_AUTO_EXPORT_CAPABILITY: NOT_PROVEN
   - OWNER_MEDIATED_MANUAL_EXPORT: ALLOWED_FALLBACK
   - this is not overall TS01 failure and does not require a destination-bound sink;
3. STATUS: OWNER_DECISION_REQUIRED_FOR_SINGLE_AUTO_EXPORT_QUALIFICATION_CALL
   - no generation or global reservation consumption occurred, formal E01 counters remain zero, and the Owner must
     decide separate platform-credit/call authority;
4. BLOCKED_SECURITY_PRIVACY_LICENSE
   - a data-flow, terms, retention, private-reference, or safety question prevents qualification;
5. FAILED
   - authority, tamper, accounting, scope, retry, overwrite, discovery, or zero-state integrity fails.

If automatic capability is not proven, the future formal workflow may continue through manual fallback after all
remaining Gates. Only when a specific formal ordinal needs export does Codex return OWNER_EXPORT_REQUIRED and stop for
the Owner's exact save action.

## Manual-fallback experiment boundary

Manual export is not requalified through a formal calibration call in TS01-Q01. Its contract is validated using
non-image metadata fixtures and negative controls: exact ordinal, exact expected filename, target-absent proof,
single-file exact read, digest/type/size binding, no parent listing, no alternate upload, and no retry.

At formal execution time, the Owner saves only the exact displayed result for the named ordinal and replies only
EXPORTED CAL-REQ-xxx. A missing, mismatched, substituted, or late file consumes the already-used ordinal and hard-stops.
It cannot be repaired by saving a different image or by asking Codex to generate another one.

## Staging and promotion experiment

The qualified data flow must be:

```text
native generation
  -> exact generated result in Codex Desktop
  -> exact auto-export handle OR Owner-mediated exact manual export
  -> absent task-scoped TRANSCRIPT_EXPORT_STAGING target
  -> source/staging digest equality and integrity receipt
  -> atomic promotion to PRINCIPAL_RESEARCH_CUSTODY_ROOT
  -> custody receipt
  -> canonical normalization and QA
  -> opaque duplicate-pair scheduler
  -> independently qualified Sol Max review
```

The platform transcript copy stays outside Project Mirror registry authority. Promotion governs only the local copy.
No QA, pHash, pair review, Asset, identity, or cohort use occurs before successful promotion.

## Threat model and negative controls

TS01-Q01 must retain redacted evidence for:

- wrong/stale/cross-call handle;
- handle bound to multiple outputs or output bound to multiple handles;
- preview/screenshot/re-encoded bytes instead of original bytes;
- inline data URL or message-history copy masquerading as a handle;
- directory listing, glob, Downloads/Desktop/temp/cache scan, clipboard recovery, recent-file inference, or parent
  enumeration;
- target pre-existence, overwrite, partial copy, digest mismatch, wrong ordinal name, symlink/reparse/alias escape, or
  P2-M7 crossover;
- private path, locator, object key, URL, signed URL, Prompt, credential, or image-byte leakage;
- automatic retry, manual retry, replacement generation, ordinal refund, or output substitution;
- calibration/holdout/QuestionBank contamination;
- transcript-copy deletion, exclusivity, or Project-registry custody misrepresentation;
- unknown terms, retention, telemetry, native model provenance, usage, or cost falsely reported as known.

An attempted prohibited discovery, overwrite, retry, private leak, or accounting bypass is FAILED or
BLOCKED_SECURITY_PRIVACY_LICENSE, not merely NOT_PROVEN.

## Security, privacy, license, and research integrity

Qualification content must be synthetic-only and non-user. No real-person reference, user data, secret, credential,
sensitive identity label, beauty or age score, celebrity similarity, Prompt plaintext in tracked evidence, or
production use is allowed. The fixture and its private bytes remain task-scoped, Git-external, and cleanup-bound.

The change adds no dependency, Provider, SDK, weight, credential, paid service, or production approval. Unknown
platform facts remain UNKNOWN_OR_NULL. A transcript-staging PASS is custody-transport evidence only; it does not
approve native model/data terms, production generation, real-user processing, QA admission, the Sol Max reviewer, MVR,
M6, or QuestionBank release.

## Sequential research DAG

```text
accepted TS01-T01
  -> accepted TS01-Q01 capability qualification
  -> accepted MR01 reviewer qualification
  -> accepted new E01 execution-authority checkpoint
  -> formal-E01-zero and TS01/global-envelope reconciliation
  -> formal private setup and tranche 1
```

No node may be skipped. An automatic-export NOT_PROVEN result can still satisfy TS01-Q01 only when manual fallback,
staging integrity, custody promotion, failure accounting, and all security/privacy/license/research controls are
independently accepted. First formal generation remains prohibited until TS01, MR01, the checkpoint, staging/custody
setup, GenerationSpecification, assignments, and ledgers all pass with zero counters.

## Planning result

- TS01_CHANGE_CONTROL_POLICY: READY_FOR_SAME_SHA_ACCEPTANCE
- TS01_QUALIFICATION_STATUS: NOT_STARTED
- NATIVE_AUTO_EXPORT_CAPABILITY: NOT_PROVEN
- NATIVE_GENERATED_ARTIFACT_EXPORT_STATUS: NOT_PROVEN
- NATIVE_ATTACHMENT_EXPORT_STATUS: NOT_PROVEN
- OWNER_MEDIATED_MANUAL_EXPORT: FALLBACK_PLANNED_NOT_EXECUTED
- STAGING_INTEGRITY_STATUS: NOT_STARTED
- CUSTODY_PROMOTION_STATUS: NOT_STARTED
- SOL_MAX_REVIEWER_QUALIFICATION_STATUS: NOT_STARTED
- GENERATION_CALLS_EXECUTED: 0
- RAW_OUTPUTS_CREATED: 0
- TS01_FIXTURE_GLOBAL_NATIVE_OUTPUT_RESERVATION_CONSUMED: 0
- GLOBAL_NATIVE_OUTPUT_CAPACITY_REMAINING: 64
- TS01_FIXTURE_PRIVATE_STORAGE_BYTES_CONSUMED: 0
- REQUEST_ORDINAL_CONSUMED: NONE
- CAL_REQ_001_STATUS: NOT_CONSUMED
- CC04_B_EXECUTION: CLOSED_PENDING_TS01_MR01_AND_NEW_E01_AUTHORITY
- NEXT_READY_TASK: CC04-B-TS01-Q01_NATIVE_POST_GENERATION_AUTO_EXPORT_CAPABILITY_QUALIFICATION

The successful result of T01 is an accepted planning authority only. It stops before qualification generation,
staging creation, MR01, or formal E01 execution.
