# P2 Early-Young Adult Presentation Control v1

## Authority and scope

- Authority: ADR-028.
- Generation policy reference: `cn-early-young-adult-presentation-v1`.
- Review rubric reference: `adult-presentation-review-v1`.
- Coverage pack: `CN_EAST_ASIAN_PRESENTATION_V1` under ADR-024.
- Applies to: V-next and later internal synthetic female candidate generation/review.
- Does not modify: P2-M2-V01 Prompt, manifest, binaries, provenance or frozen evidence.
- Does not authorize: real-person input, real-user runtime generation, public release, age estimation,
  P2-M4 or QuestionBank release.

## Versioned generation policy

```text
primary_presentation_target = clearly-adult early-young woman, 18–25
secondary_coverage_range = clearly-adult woman, 26–30, only when morphology coverage needs it
de_emphasized_range = clearly-adult woman, 31–34
first_pack_selection_exclusion = visibly 35+ presentation
hard_reject = under-18 | minor ambiguity | schoolgirl framing | childlike presentation
```

The ranges describe visual presentation reviewed by an operator. They are not predicted biological
ages. No age-estimation score, classifier output or inferred age is persisted.

For an initial eight-image V-next pack, all requested items use a conservative 21–25 sub-band within
the approved primary range to preserve clear adult cues. Secondary spillover is not requested unless
the first cohort reveals a documented morphology coverage gap. Every Prompt keeps East-Asian-
presenting, synthetic-only, unique identity, frontal/neutral geometry, natural skin texture and
minimal styling. Item-specific morphology remains independent of the age-presentation axis.

## PromptTemplate controls

Every V-next private PromptTemplate version must include:

- `clearly adult`, `early-young adult woman` and `young woman`;
- the item-specific primary-range sub-band and explicit adult facial maturity;
- `East-Asian-presenting`, synthetic-only and no real-person/named-identity reference;
- no childlike proportions, juvenile styling, minor ambiguity, schoolgirl/campus framing or uniform;
- no beauty-template convergence, glamour retouching or influencer/celebrity imitation;
- one person, visible full facial contour, neutral closed mouth, direct gaze and bounded studio setup.

Prompt contents remain private. Committed evidence may contain only opaque Prompt references and
SHA-256 digests.

## Review rubric

Review order is fixed:

1. `ADULT_CLARITY`: the subject must unambiguously present as an adult. Unknown is reject.
2. `MINOR_SAFETY`: reject any minor ambiguity, childlike presentation or schoolgirl framing.
3. `PRIMARY_PACK_FIT`: classify the clearly-adult visual presentation as primary, secondary,
   de-emphasized or too mature for the first pack without claiming a biological age.
4. `MORPHOLOGY_FIDELITY`: confirm the requested coverage cell remains visible and is not replaced by
   an age stereotype or beauty template.
5. `IDENTITY_DIVERSITY`: compare the cohort for repeated face template, near-identical proportions,
   styling convergence or mode collapse.
6. Existing source, decode, checksum, text/watermark, background, likeness and rights gates remain
   mandatory and cannot be overridden by presentation fit.

Reason codes:

- `MINOR_AMBIGUOUS` — hard reject.
- `CHILDLIKE_PRESENTATION` — hard reject.
- `SCHOOLGIRL_FRAMING` — hard reject.
- `ADULT_PRESENTATION_PRIMARY_RANGE` — eligible for first-pack selection, subject to every other Gate.
- `ADULT_PRESENTATION_SECONDARY_RANGE` — eligible only with recorded coverage need.
- `ADULT_PRESENTATION_DEEMPHASIZED` — normally excluded from the first pack.
- `ADULT_PRESENTATION_TOO_MATURE_FOR_PRIMARY_PACK` — first-pack selection exclusion, not a global
  safety failure.
- `HOMOGENIZATION_RISK` — reject cohort admission until identity/morphology diversity is restored.

## V-next bounded generation contract

- Requested images: 8.
- Structure: 4 existing continuous morphology/lighting categories × 2 unique identities.
- Concurrency: 1.
- Maximum attempts: 12; maximum one retry per item.
- Source: ADR-026 Codex native offline generation only.
- Output: private ignored source directory; no image or Prompt enters Git.
- Admission: expected SHA-256 per item, bounded PNG, synthetic-only attestation and provenance level
  `PROVENANCE_ONLY`; unknown model/request/seed/usage/cost facts remain `NULL`.
- Stop immediately if any output is minor-ambiguous, childlike, schoolgirl-framed, derived from a
  real person, or if repeated outputs show template collapse. A rejected image is evidence, not a
  reason to relax the policy.

`AGE_PRESENTATION_CONTROL_STATUS: APPROVED`

`V01_MUTATED: NO`

`REAL_USER_RUNTIME_GENERATION_CALLS: 0`
