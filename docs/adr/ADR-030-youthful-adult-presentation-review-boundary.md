# ADR-030：年轻脸成年合成人物的视觉呈现审查边界

## Status

Accepted — 2026-08-17

## Context

ADR-028 将任何 `minor ambiguity` 作为 hard reject，以保护首包 18+ 与 clearly-adult 边界。实际
人工审查发现，该规则会把圆脸、babyface、较柔和五官或其他年轻脸特征本身误当成未成年证据，
从而排除声明为成年、没有儿童语境的 synthetic identities，并可能损害 morphology/identity
diversity。Project Owner 因此要求放宽一般非性感题库肖像的视觉呈现阻断条件。

该修订不能把视觉年龄判断伪装成生物年龄估计，也不能允许儿童呈现、学生未成年语境，或把可能
未满 18 岁的呈现用于性感、诱惑或性化 style context。

## Decision

- 所有候选继续必须是 synthetic-only、声明为 18+ adult identity、无真人 reference；本修订不
  引入真实未成年人、真实人物或自动年龄估计。
- 对一般非性感内部题库肖像，圆脸、babyface、柔和五官、较小骨架或 youthful appearance 本身不
  构成拒绝。人工 review 只在整体视觉明确呈现为未满 16 岁，或包含儿童/学生未成年语境时 hard
  reject。
- 新 reason codes 为 `CLEAR_PRE16_PRESENTATION` 与 `CHILD_OR_STUDENT_MINOR_CONTEXT`。后者包括
  儿童化 styling、中小学/高中学生语境、校服、未成年校园 framing 或明确儿童道具/场景。
- `YOUTHFUL_ADULT_PRESENTATION_ALLOWED` 是非失败 categorical evidence。它不声称预测年龄，也
  不改变声明的 synthetic adult provenance。
- `minor ambiguity` 不再是未来一般非性感 cohort 的独立 hard reject reason。ADR-028 与 v1 rubric
  产生的历史 evidence 不删除、不改名、不重解释；新规则只通过 v2 policy/Prompt/rubric 前向生效。
- `ADULT_SAFE_SEXY`、`CHARMING_ALLURING` 以及任何带性感、诱惑、亲密或性化语义的 context 仍要求
  `UNAMBIGUOUS_18_PLUS_PRESENTATION`。不能明确满足时以
  `ADULT_ONLY_STYLE_AGE_AMBIGUOUS` hard reject；不得把 16–17 岁视觉呈现用于这些 context。
- `PURE_CLEAN_NATURAL`、`GENTLE_SWEET_APPROACHABLE` 等非性感 context 也不得使用儿童/学生语境，
  但不能只因脸型年轻或 babyface 而拒绝。
- 年龄呈现 review 继续是人工 categorical judgment，不保存数值预测、置信分、estimated age、
  percentile 或 ranking。
- Codex native `image_gen` 仍是 ADR-026 operator-assisted offline source，不是 production
  `ImageGenerationProvider`；真实用户 runtime generation 调用保持 0。

## Alternatives Considered

- 继续把任何 youthful/babyface 特征视为 `minor ambiguity` hard reject。
- 仅使用数值年龄估计模型判定 16 岁阈值。
- 对所有 style context 无差别放宽到 16 岁视觉呈现。
- 覆盖 ADR-028、age-v1、style-v1 Prompt 或既有 attempt evidence。

## Consequences

一般非性感题库可以保留更多年轻脸成年合成人物和 morphology diversity，同时明确儿童呈现与
学生未成年语境仍 fail closed。带性感/诱惑语义的 style context 保留更严格的 18+ presentation
Gate，避免把放宽规则传播到不安全组合。

该决定不修改 schema、migration、公开 API、Vision port、自动 QAPolicy threshold、P2-M6 release
authority 或生产 Provider 状态。历史 v1 evidence 保持不可变；所有后续生成必须绑定 v2 authority。

## Security / Privacy Considerations

禁止真人、真实未成年人、名人/网红 imitation、社交媒体/搜索结果肖像、年龄估计模型、学生身份
推断和敏感属性分类。人工 review 只保存 policy/rubric version、categorical reason code、actor、
timestamp 与 outcome，不保存自由文本面部评价、图片、Prompt、private path 或 object key。

## Testing Implications

- 证明 ADR-028、age-v1、style-v1、V01、age-only V-next 与已生成 style-v1 evidence 均未被覆盖。
- v2 Prompt 必须禁止明确未满 16 岁呈现以及儿童/学生未成年语境，但不得把 `babyface` 本身列为
  hard reject。
- adult-only style Prompt 必须额外包含 unambiguous 18+ 与 no 16–17 presentation guard。
- policy/rubric scan 必须证明不存在自动年龄估计、数值阈值输出、beauty score 或 ranking。
