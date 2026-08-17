# P2 Youthful Adult Presentation Control v2

## Authority and supersession

- Authority: ADR-030.
- Supersedes for future cohorts: the general `minor ambiguity` hard-reject rule in
  `P2_AGE_PRESENTATION_CONTROL_V1.md`.
- Generation policy reference: `cn-youthful-adult-presentation-v2`.
- Review rubric reference: `youthful-adult-presentation-review-v2`.
- Historical v1 Prompt, image, attempt, manifest and review evidence remain immutable.
- Applies only to new synthetic-only internal cohorts; it does not authorize real-person input,
  age-estimation models, public release or real-user runtime generation.

## Versioned review boundary

```text
declared_identity = synthetic adult, 18+
allowed_general_presentation = youthful adult appearance, including round face or babyface traits
general_hard_reject = clearly under-16 presentation | child/minor-student context
adult_only_style_hard_reject = not unambiguously 18+ in sexy/alluring/intimate/sexualized context
age_estimation = prohibited
```

The under-16 boundary is an operator-reviewed presentation category, not a predicted biological age.
No numerical age, probability, confidence, score or model output is persisted.

## General non-sexual Prompt controls

New private PromptTemplates must state that the identity is a synthetic adult and may have youthful,
round-faced or babyface features. They must prohibit:

- a clearly pre-16 child presentation;
- childlike body/facial proportions deliberately used to depict a child;
- primary/secondary/high-school student framing, school uniform or minor-coded campus context;
- real-person/named-identity reference, celebrity/influencer imitation or face swap;
- automatic age estimation, beauty scoring, ranking or universal-template convergence.

`babyface`, a round face, soft features or a small adult face alone are not rejection reasons.

## Adult-only style overlay

For `ADULT_SAFE_SEXY`, `CHARMING_ALLURING` or any future sexy, alluring, intimate or sexualized
context, the Prompt and review must additionally require:

- unambiguous 18+ adult presentation;
- no 16–17 presentation ambiguity;
- fully clothed, non-explicit and non-fetishized styling;
- no child/student/minor-coded context.

Failure is `ADULT_ONLY_STYLE_AGE_AMBIGUOUS` and is a hard reject.

## Review reason codes

- `CLEAR_PRE16_PRESENTATION` — general hard reject.
- `CHILD_OR_STUDENT_MINOR_CONTEXT` — general hard reject.
- `ADULT_ONLY_STYLE_AGE_AMBIGUOUS` — adult-only style hard reject.
- `YOUTHFUL_ADULT_PRESENTATION_ALLOWED` — accepted categorical evidence, not an age prediction.
- ADR-028 first-pack primary/secondary/de-emphasized/too-mature categories remain soft selection
  evidence where applicable; they are not reinterpreted as biological ages.

`AGE_PRESENTATION_CONTROL_V2_STATUS: APPROVED`

`AUTOMATIC_AGE_ESTIMATION_USED: NO`

`HISTORICAL_V1_MUTATED: NO`

`REAL_USER_RUNTIME_GENERATION_CALLS: 0`
