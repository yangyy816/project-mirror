# P2 Formal QuestionBank Generation and Admission Policy v3

## Authority and versions

- Authority: ADR-052, subordinate to the synthetic-only and no-sensitive-routing invariants in ADR-024.
- Machine-readable authority: `docs/research/P2_QUESTIONBANK_GENERATION_POLICY_V3.json`.
- Generation policy reference: `cn-formal-questionbank-adult-18-25-v3`.
- Prompt semantic reference: `cn-formal-questionbank-prompt-semantics-v3`.
- Admission rubric reference: `formal-questionbank-admission-review-v3`.
- Pair contract reference: `formal-pairwise-stimulus-v1`.
- Demo selection reference: `local-synthetic-demo-selection-v1`.
- Historical age/style v1/v2, V01 and existing generation evidence remain immutable.

Within the new formal QuestionBank, pairwise-stimulus, AestheticProfile synthetic-input and local
Demo scope, V3 is the narrower forward overlay. ADR-029 style descriptors are usable only when they
meet V3 adult/nonsexual restrictions, and ADR-030's broader nonsexual research-cohort presentation
boundary cannot replace V3 formal 18+ admission. Historical evidence under either ADR is unchanged.

This policy applies forward to every new formal QuestionBank candidate, pairwise stimulus,
AestheticProfile synthetic input and local Web Demo face case. It does not authorize questionnaire
runs, QuestionBank release, a public API, production generation or real-user facial processing.

## Adult-only age policy

```text
MAIN_QUESTION_BANK_AGE_POLICY = ADULT_ONLY_18_TO_25
allowed_declared_age_bands = ADULT_18_19 | ADULT_20_25
default_target = ADULT_20_25 about 70% | ADULT_18_19 about 20%
adult_only_flex = about 10%, assignable only to the two allowed adult bands
hard_reject = suspected minor | under-18 declaration | child/student-minor context | band mismatch
age_estimation = prohibited
```

The contradictory source line `18 -16: 10%` is not an allowed band. Its only safe interpretation is
an unallocated adult-only cohort flex; it never admits 16–17 or any other under-18 sample.

`VERIFIED_SYNTHETIC_ADULT` means verified synthetic provenance, an adult declaration and a passed
versioned human presentation review. It is not a biological-age claim. New formal admission requires
`suspected_minor=false`. Review remains categorical and must not persist estimated age, probability,
confidence, score, percentile or ranking.

`ADULT_18_19` permits only nonsexual presentation such as clean-natural, gentle, sweet, restrained,
cool or similarly age-appropriate styling. Light-mature or alluring-but-nonsexual presentation is
restricted to `ADULT_20_25`; sexy, intimate, fetishized or sexually suggestive presentation is
prohibited for the entire formal pack.

## Synthetic presentation and diversity

- First-wave market scope: `CN_MAINLAND`.
- First-wave presentation context: `EAST_ASIAN_PRESENTING_FIRST_WAVE`.
- The presentation context describes synthetic generation/coverage, not race, ethnicity, ancestry,
  nationality, a real-user label or a routing classifier.
- East-Asian-presenting faces are the first-wave priority; broader Asian-presenting variation may be
  used for morphology coverage without becoming a sensitive identity field.
- Continuous morphology, identity distinctness and non-sensitive style coverage remain independent.
  A single Korean-influencer template, celebrity resemblance or repeated ideal face fails admission.

The style presentation families include clean natural, restrained Korean-clear, gentle sweet,
refined cool, light-mature alluring-but-nonsexual, relaxed polished, cold reserved, heroic sharp and
strong individual distinctiveness. These are replaceable presentation descriptors, not a hierarchy
or user identity. Current M5 E01 retains its six pre-registered nonsexual style cells; V3 cannot
reassign a request after seeing the output.

## Fixed capture grammar

Unless the measured dimension explicitly requires otherwise, both single candidates and pair sides
must use:

- front-facing head orientation and direct eye contact;
- neutral or mildly natural expression and stable shoulder/neck posture;
- equivalent head occupancy, camera/framing and focal-length impression;
- stable soft lighting and clean neutral low-distraction background;
- consistent close portrait composition, natural light makeup and simple low-distraction clothing;
- no dramatic jewelry, filter, retouching, occluding hair, strong pose or camera-angle variation.

Any unplanned pose, expression, lighting, background, hair, makeup, clothing, accessory or framing
difference is a potential confound and must be rejected unless the versioned pair specification names
it as the target.

## Pair contracts

### GEOMETRY_PAIR

- Prefer one QA-passed canonical synthetic base identity and one seed family when the source actually
  supports a seed; unsupported seed facts remain `NULL`.
- Preserve declared age band, pose, expression, background, lighting, camera/framing, hair, makeup,
  clothing and all unrelated facial attributes.
- Change exactly one primary geometry dimension. At most one necessary correlated variable may move,
  and it must be declared before generation/transform.
- Bind requested and measured delta, transform/measurement versions and isolation evidence. Every
  control dimension must pass its frozen tolerance.

### STYLE_PAIR

- Preserve base identity and primary facial geometry.
- Change one versioned style direction such as natural/refined, warm/cool, soft/sharp,
  innocent-natural/mature-refined, sweet/cold or relaxed/polished.
- Do not create the choice through large makeup, hairstyle, clothing, pose, expression, lighting or
  background differences. Remeasure geometry after any generative style change.

### Shared pair admission

Both sides must independently pass identical hard gates and the pair must pass `PAIR_COMPARABILITY`.
The selection cannot be driven by a visibly broken, low-finish, distorted or obviously inferior side.
Reject the complete pair for target ambiguity, non-target contamination, one-sided failure, large
finish imbalance, template collapse or manifest mismatch.

## Non-scoring product curation

No per-face attractiveness or beauty score, rating, percentile or ranking exists. Review records only
categorical evidence: natural anatomy, acceptable visual finish, individual distinctiveness,
questionnaire suitability and fair pair comparability.

Pack-level operational distribution:

- about 70–80% coordinated, clean and higher-finish accepted candidates;
- about 15–25% strongly distinctive but still product-acceptable candidates;
- no more than about 10% neutral boundary candidates used to test preference limits.

These are cohort curation targets, not user-facing labels or scalar face attributes. Severe imbalance,
plastic/template appearance, low completion, untidiness, lack of any distinguishing feature and
obvious error-answer pairs are rejected rather than balanced by lowering QA thresholds.

## Minimum record and admission contract

Each candidate or pair-side record contains at least:

```text
synthetic_identity_id, declared_age_band, adult_status, suspected_minor,
visual_context, style_family, sexualized_presentation, age_style_compatibility,
pair_type, geometry_dimensions,
controlled_variables, preserved_variables, generation_source_kind,
generation_provider, generation_version, prompt_policy_version,
source_digest, qa_result, rejection_reason, pair_id, pair_side,
base_identity_family, real_person_reference, celebrity_resemblance,
source_rights, decode_qa, likeness_review, duplicate_status,
pair_comparability, variable_isolation, visual_quality, anti_homogenization
```

`generation_provider` is present but nullable when the offline source does not expose that fact.
`CODEX_NATIVE_IMAGEGEN` is recorded as an offline source kind with `runtime_provider=false`, never as
a production Provider. Provider, model, model version, request reference, seed, usage and cost remain
`NULL` when unavailable; no fallback string may imply a fact that the source did not expose.

Formal QuestionBank or Demo admission requires:

```text
adult_status = VERIFIED_SYNTHETIC_ADULT
declared_age_band in {ADULT_18_19, ADULT_20_25}
suspected_minor = false
sexualized_presentation = false
age_style_compatibility = PASS
real_person_reference = false
celebrity_resemblance = false
source_rights = PASS
decode_qa = PASS
likeness_review = PASS
duplicate_status = PASS
pair_comparability = PASS
variable_isolation = PASS
visual_quality = PASS
anti_homogenization = PASS
```

Hard rejects are append-only evidence and cannot be converted to PASS by a soft product review.

## Provider Prompt semantic contract

Private PromptTemplates must bind required semantics for clearly-adult, 18–25, synthetic non-real
person, East-Asian-presenting first-wave context, frontal direct gaze, neutral natural expression,
stable soft lighting, neutral background, consistent framing, natural facial anatomy and no celebrity
or public-figure resemblance. Geometry pairs additionally bind same base identity and preservation of
all unrelated attributes.

The full Prompt, seed value, image bytes, private locator, object key, signed URL and Provider raw
payload stay outside Git, MEMORY, ordinary logs, artifacts and UI. Git may contain only this semantic
contract, opaque references, digests, checksums and allowlisted aggregate outcomes.

## Demo boundary

The local Web Demo selects only pre-generated synthetic assets that pass the same adult, source,
quality, pair, isolation and anti-homogenization gates. It performs zero real-user runtime generation,
uses no real-person examples, and labels the material as internal/research demonstration rather than
production validation or training data.

## Active M5 transition

`CAL-REQ-002` remains unconsumed. Before dispatch, `CC-P2-M5-05-A` must materialize a new private
generation-policy/Prompt/rubric version bound to this V3 digest and prove custody, assignment,
register-before-decode and zero-leakage. This policy itself generates no image.

`QUESTIONBANK_GENERATION_POLICY_V3_STATUS: APPROVED_FORWARD_ONLY`

`UNDER_18_FORMAL_ADMISSION: PROHIBITED`

`BEAUTY_SCORE_USED: NO`

`REAL_USER_RUNTIME_GENERATION_CALLS: 0`
