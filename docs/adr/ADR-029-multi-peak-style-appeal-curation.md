# ADR-029：首包多峰风格吸引力与非打分式遴选

## Status

Accepted — 2026-08-17

## Context

ADR-028 已冻结 clearly-adult early-young 女性年龄呈现，但首轮 V-next 只验证年龄控制、成人安全与
morphology/identity diversity，没有把女性向偏好问卷所需的视觉吸引力方向、多个风格峰值或首包
curation 语言版本化。把“更吸引人”实现为 beauty/attractiveness score、percentile、ranking 或统一
标准美女脸，会违反 No Beauty Score 与 anti-homogenization；仅在 Prompt 中加入一个“beautiful”
形容词也无法形成可审计、可复现或多样化的产品方向。

## Decision

- The internal synthetic female question-bank should present clearly-adult early-young women in
  multiple visually aspirational and product-appropriate style contexts for a female-oriented
  preference questionnaire.
- Attractiveness is a non-numeric curation objective, not a beauty score, ranking, percentile or
  universal aesthetic standard. No automatic or human-authored scalar attractiveness value may be
  persisted or used for release selection.
- Approved non-exclusive style contexts are `PURE_CLEAN_NATURAL`, `GENTLE_SWEET_APPROACHABLE`,
  `REFINED_ELEGANT`, `SOPHISTICATED_URBAN`, `GLAMOROUS_STRIKING`, `CHARMING_ALLURING`,
  `ADULT_SAFE_SEXY` and `INTELLECTUAL_ELEGANT_LIGHT_MATURE`.
- Style contexts describe replaceable presentation, styling, lighting and product fit. They are not
  identity labels, sensitive-trait classes, morphology authorities or user-routing attributes.
- `PRODUCT_CONTEXT_MISMATCH`, `WEAK_STYLISTIC_DISTINCTIVENESS` and
  `FIRST_PACK_STYLE_REDUNDANCY` are first-pack soft curation exclusions. They are not automatic QA
  hard failures and cannot erase source, provenance, normalization or QA evidence.
- Minor ambiguity, childlike presentation and schoolgirl framing remain ADR-028 hard rejects.
  `PURE_CLEAN_NATURAL` must remain unmistakably adult. `ADULT_SAFE_SEXY` and
  `CHARMING_ALLURING` prohibit nudity, fetishized framing, explicit sexualization and vulgar or
  exploitative presentation.
- A style-aware cohort must preserve morphology and identity coverage independently of style.
  Review records style-context occupancy, repeated-template risk and cross-style identity collapse;
  it never ranks identities or treats a style context as inherently superior.
- Existing P2-M2-V01 and age-only V-next Prompt, image, attempt, manifest and provenance evidence
  remain immutable. They are not retroactively relabeled as style-evaluated. A separate private
  policy/Prompt/cohort version is required.
- Codex native `image_gen` remains the ADR-026 operator-assisted offline synthetic source with
  `PROVENANCE_ONLY`; it is not a production `ImageGenerationProvider`. Real-user runtime generation
  calls remain zero.

## Alternatives Considered

- Add `beautiful` or `high attractiveness` to every Prompt without a style distribution.
- Introduce a beauty score, reviewer rating, percentile or ranking.
- Reject all visually ordinary outputs as automatic QA failures.
- Use one preferred template face and vary only styling.
- Reinterpret or overwrite the existing age-only V-next cohort.

## Consequences

Generation and curation gain a product-aligned multi-peak direction without creating a universal
beauty authority. The change is forward-only content governance: no schema, migration, public API,
Vision threshold, M3 lifecycle or P2-M6 release authority changes. Future P2-M6 refinement must bind
the selected style-policy/rubric version and distinguish safety hard rejects from soft first-pack
curation exclusions.

Prompt contents and images remain in ignored private storage. Git may contain only first-party
policy/rubric text, opaque references, digests, checksums and allowlisted aggregate evidence.

## Security / Privacy Considerations

No real-person reference, celebrity/influencer imitation, social-media/search-result portrait,
sensitive-trait inference or real-user facial input is authorized. Styling must not introduce
minor-coded clothing, campus/school framing, explicit sexual content or identity reproduction.
Review evidence stores only versioned categorical outcomes and reason codes, never free-text facial
judgments, attractiveness scores, Prompt text, image bytes, private paths or object keys.

## Testing Implications

- Prove V01 and the age-only V-next cohort are unchanged.
- Require every style-aware private Prompt to bind exactly one primary style-context reference while
  retaining the ADR-028 adult/minor controls and independent morphology reference.
- Scan policy, Prompt and review evidence for score, percentile, ranking and universal-template
  semantics.
- Review adult/minor safety before style/product curation; a soft curation decision cannot override
  any automatic or adult-safety hard failure.
- Cohort evidence must report style occupancy, morphology-cell occupancy, identity distinctness and
  homogenization risk without scalar attractiveness values.
