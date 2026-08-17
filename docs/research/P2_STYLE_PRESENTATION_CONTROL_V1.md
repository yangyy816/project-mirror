# P2 Multi-Peak Style Presentation Control v1

## Authority and scope

- Authority: ADR-029, subordinate to ADR-024 and ADR-028.
- Generation policy reference: `cn-female-style-presentation-v1`.
- Review rubric reference: `style-product-curation-review-v1`.
- Applies to: a new style-aware internal synthetic cohort and later candidate curation.
- Does not modify or reclassify: P2-M2-V01 or the age-only V-next cohort.
- Does not authorize: a beauty score, public release, real-person input, real-user runtime generation,
  P2-M4, P2-M6 release or production Provider approval.

## Product language

```text
objective = visually aspirational and product-appropriate for a female-oriented preference questionnaire
selection_mode = categorical, non-numeric, multi-peak curation
forbidden_authority = beauty score | attractiveness score | percentile | ranking | universal ideal face
required_independent_axes = adult safety | age presentation | morphology | identity | style context
```

`Product-aligned attractiveness` means questionnaire suitability and stylistic distinctiveness in a
specified context. It never measures a person's worth, predicts user preference, or establishes a
global aesthetic hierarchy.

## Approved style contexts

| Reference                           | Presentation intent                                       | Adult-safety boundary                                            |
| ----------------------------------- | --------------------------------------------------------- | ---------------------------------------------------------------- |
| `PURE_CLEAN_NATURAL`                | clean, natural, fresh, restrained styling                 | explicit adult facial maturity; no juvenile/campus coding        |
| `GENTLE_SWEET_APPROACHABLE`         | warm, gentle, approachable and polished                   | sweetness cannot use childlike proportions or schoolgirl framing |
| `REFINED_ELEGANT`                   | precise, graceful, composed and understated               | no template-face or luxury-status inference                      |
| `SOPHISTICATED_URBAN`               | contemporary urban polish and confidence                  | no sensitive socioeconomic inference                             |
| `GLAMOROUS_STRIKING`                | vivid, high-impact styling with clear identity            | no celebrity imitation or excessive beauty-template retouching   |
| `CHARMING_ALLURING`                 | expressive adult charm and controlled allure              | no nudity, explicit sexualization or vulgar framing              |
| `ADULT_SAFE_SEXY`                   | confident adult sensuality through styling and expression | fully clothed, non-explicit, non-fetishized, clearly adult       |
| `INTELLECTUAL_ELEGANT_LIGHT_MATURE` | thoughtful, elegant, lightly mature styling               | cannot move the first-pack age center outside ADR-028            |

Style references are non-exclusive descriptors. Each generated item binds one primary context for
coverage accounting, but a reviewer may record secondary context matches without converting them
into identity labels.

## PromptTemplate controls

Every new private style-aware PromptTemplate must bind:

- ADR-028 clearly-adult, 21–25 initial-sub-band and minor-safety language;
- `CN_EAST_ASIAN_PRESENTATION_V1`, synthetic-only and no real-person reference;
- one primary style-context reference and its adult-safe presentation intent;
- a morphology coverage-cell reference independent of styling;
- natural skin texture, individual facial structure and no template/celebrity/influencer imitation;
- one person, visible full facial contour, direct gaze, neutral or mildly warm closed-mouth expression
  and bounded portrait framing;
- no score, percentile, ranking, universal ideal, minor coding or explicit sexual content.

Prompt contents remain private. Committed evidence may contain only opaque references and SHA-256
digests.

## Review order and categorical outcomes

1. Apply every source, rights, decode and automatic QA gate.
2. Apply ADR-028 `ADULT_CLARITY` and `MINOR_SAFETY`; unknown is hard reject.
3. Record `STYLE_CONTEXT_MATCH` or `STYLE_CONTEXT_MISMATCH` against the bound context.
4. Record `QUESTIONNAIRE_SUITABLE` or `PRODUCT_CONTEXT_MISMATCH` without a score.
5. Record `STYLISTICALLY_DISTINCT` or `WEAK_STYLISTIC_DISTINCTIVENESS`.
6. At cohort level, record context occupancy, morphology occupancy, identity distinctness,
   `FIRST_PACK_STYLE_REDUNDANCY` and `HOMOGENIZATION_RISK`.

Only the existing automatic/adult-safety failures are hard rejects. Product/style outcomes are soft
first-pack curation evidence and cannot override hard failures. No outcome may be converted to a
numeric attractiveness value or ranking.

## Initial style-aware cohort contract

- Requested images: 8, one per approved primary style context.
- Age presentation: ADR-028 primary range, using the conservative 21–25 requested sub-band.
- Morphology: distribute the eight items across the four existing age-only coverage cells; style may
  not replace or redefine the cell.
- Identities: eight new synthetic identities; no identity or Prompt is reused from V01 or age-only
  V-next.
- Concurrency: 1.
- Maximum attempts: 12; maximum one retry per item.
- Source: ADR-026 Codex native offline generation only.
- Storage: a new ignored private root; no Prompt or image enters Git.
- Provenance: `PROVENANCE_ONLY`; unavailable model/request/seed/usage/cost facts remain `NULL`.
- Stop on any minor ambiguity, childlike/schoolgirl framing, real-person likeness, explicit sexual
  presentation, repeated-template collapse or inability to preserve morphology diversity.

`STYLE_PRESENTATION_CONTROL_STATUS: APPROVED`

`ATTRACTIVENESS_SCORE_USED: NO`

`EXISTING_COHORTS_MUTATED: NO`

`REAL_USER_RUNTIME_GENERATION_CALLS: 0`
