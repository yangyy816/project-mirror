# P2 Multi-Peak Style Presentation Control v2

## Authority and scope

- Authority: ADR-029 plus ADR-030.
- Supersedes for future generation: `P2_STYLE_PRESENTATION_CONTROL_V1.md` only where its age guard
  imports ADR-028 `minor ambiguity` as a universal hard reject.
- Generation policy reference: `cn-female-style-presentation-v2`.
- Review rubric reference: `style-product-curation-review-v2`.
- Style contexts, non-numeric curation, morphology/identity separation and anti-homogenization remain
  unchanged from v1.
- Existing style-v1 policy, Prompt, source and attempt evidence remain immutable and are not
  retroactively evaluated under v2.

## Age overlay by style context

| Style context                       | Age-presentation rule                                                       |
| ----------------------------------- | --------------------------------------------------------------------------- |
| `PURE_CLEAN_NATURAL`                | youthful adult traits allowed; reject clear pre-16 or child/student context |
| `GENTLE_SWEET_APPROACHABLE`         | youthful adult traits allowed; sweetness cannot use child/student context   |
| `REFINED_ELEGANT`                   | youthful adult traits allowed; reject clear pre-16 or child/student context |
| `SOPHISTICATED_URBAN`               | youthful adult traits allowed; reject clear pre-16 or child/student context |
| `GLAMOROUS_STRIKING`                | require clear adult styling; reject clear pre-16 or child/student context   |
| `INTELLECTUAL_ELEGANT_LIGHT_MATURE` | youthful adult traits allowed; no student framing                           |
| `CHARMING_ALLURING`                 | unambiguous 18+ required; no 16–17 ambiguity                                |
| `ADULT_SAFE_SEXY`                   | unambiguous 18+ required; no 16–17 ambiguity                                |

## Review order

1. Source, rights, decode and automatic QA gates.
2. Apply age-v2 general child/student hard gates.
3. Apply the unambiguous-18+ overlay for adult-only style contexts.
4. Record categorical style match, questionnaire suitability and stylistic distinctiveness.
5. Review morphology/identity/style occupancy and homogenization without scores or rankings.

`STYLE_PRESENTATION_CONTROL_V2_STATUS: APPROVED`

`HISTORICAL_STYLE_V1_MUTATED: NO`

`ATTRACTIVENESS_SCORE_USED: NO`
