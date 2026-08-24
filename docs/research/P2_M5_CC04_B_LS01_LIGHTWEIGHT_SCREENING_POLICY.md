# P2-M5 CC04-B LS01 Lightweight Screening Policy

## Policy identity

- `POLICY_VERSION: p2-m5-cc04-b-first-wave-lite-screening-v1`
- `OWNER_DECISION_ID: OD-P2-M5-CC04-B-MR01-002`
- `ASSURANCE_CLASS: REDUCED_ASSURANCE_PRELIMINARY_MODEL_SCREENING_FOR_SYNTHETIC_ONLY_BETA`
- `REVIEW_RESULT_CLASS: PRELIMINARY_ADVISORY_ONLY`
- `HUMAN_SECOND_ROUND_POLICY: DEFERRED_TO_FIRST_WAVE_INVITE_ONLY_BETA_TESTING`

This policy governs an independent Sol-family preliminary review of private, offline, first-party synthetic images only. It does not prove strict runtime capability, provider provenance, a model snapshot, or production eligibility.

## Scope and exclusions

Included scope is fresh P2-M5 calibration images and P2-M6 invite-only-Beta candidates that are synthetic-only, non-user, non-production, and offline. Excluded scope is a real person, User Asset, user upload, SelfState, DesiredDelta, real-user photograph, sensitive data, production, public release, general availability, and permanent QuestionBank release.

The historical strict result remains `STRICT_SOL_MAX_RUNTIME_CAPABILITY: NOT_PROVEN_HISTORICAL_NON_BLOCKING_FOR_FIRST_WAVE`. Strict MR01 fixtures, private pair-view runtime, route receipts, envelope/clock/sink qualification, and their operation budgets are `DEFERRED_POST_FIRST_WAVE`; they are neither silently passed nor required for this policy.

## Reviewer input and output

An independent fresh-context Sol reviewer receives only an approved redacted group packet and bounded nearest-candidate comparisons. It receives no generator scratchpad, private locator, Prompt, credential, user data, or authority to generate, mutate, select user preferences, or make final release decisions.

Allowed actions are `KEEP_FOR_BETA_CANDIDATE`, `REJECT_HARD`, `FLAG_FOR_HUMAN_SECOND_ROUND`, and `DUPLICATE_SUSPECT`.

Allowed reasons concern duplicate/same-identity suspicion, severe artifact, face/protocol conformance, text/watermark/composite/abnormal-content signal, and human-review priority. Comments are brief, factual, and non-sensitive. Prohibited output includes beauty, style preference, numeric age, race/ethnicity/nationality/ancestry, personality, identity naming, celebrity similarity, sensitive attributes, production readiness, or final QuestionBank value.

## Deterministic precedence and group record

Deterministic hard QA precedes the model. Exact or normalized digest duplicates, malformed decode, and invalid face count reject. Adult ambiguity is flagged and excluded from Beta until human review. Obvious text/watermark/branding, abnormal background, severe crop, or prohibited pose rejects or flags under the accepted deterministic QA policy.

For each `CAL-GRP-###`, private reports record opaque IDs, owner-visible filename, SHA-256, deterministic QA, model action/reason codes, limited pHash-ranked duplicate suspects, group decision, and `HUMAN_REVIEW_STATUS: PENDING_SECOND_ROUND`. The exact storage directory is Owner-visible only and outside tracked evidence. Model decisions never override deterministic hard QA or later human judgment.

## Human override and Beta boundary

Every retained candidate awaits a real human second round during first invite-only Beta. Human results are append-only and take precedence. `HUMAN_REVOKE` or `HUMAN_NEEDS_REPLACEMENT` immediately excludes future selection and display while retaining historical testing and audit references. Flagged and duplicate-suspect images have zero pre-human exposure. Kept items may have a future-contract exposure cap between one and twenty and require human review within seven calendar days after first exposure.

This policy alone does not open E01, M5/MVR, M6, production, public release, or runtime generative calls. It requires `QUESTIONNAIRE_RUNTIME_GENERATIVE_CALLS: 0` and keeps production generation fail-closed.
