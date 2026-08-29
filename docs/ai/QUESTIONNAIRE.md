# Aesthetic Questionnaire Research Spec v1

> **RESEARCH HYPOTHESIS**：本文件中的统计模型、题目数量、覆盖率和几何构造方法都可被实验替换，不是产品永久 Invariant。

## 测量目标

问卷测量用户自己表达的审美偏好，不评价用户或合成人物的“美丑”，不推断敏感身份。

## Self-conditioned routing

QuestionnaireRun 必须绑定 BaselineFaceModel 与 SelfState。路由使用连续 morphology、measurement reliability、coverage 和 uncertainty，不使用 round/square、族群或其他敏感类别。QuestionTemplate 只描述测量意图；QuestionInstance 保存用户特定 stimulus、局部形态邻域距离、排除目标维度的 feature mask 和完整复现版本。

## 当前 72 个 Canonical Slots

- Q01–Q18：相对于 SelfState 的方向搜索。
- Q19–Q32：期望幅度估计。
- Q33–Q44：邻近合成身份上的跨身份泛化。
- Q45–Q54：特征交互与 Harmony。
- Q55–Q64：皮肤、妆容、摄影风格与修图偏好。
- Q65–Q72：一致性、侧偏与可靠性验证。

当前假设典型 58–64、约 50 最小、72 最大。Adaptive 选择不得绕过版本化覆盖要求。这些数字均可由研究替换。

## 统计模型

方向和幅度必须分别估计，且区分 measurement、preference、generalization、transfer 与 profile confidence。Bradley–Terry、staircase、Bayesian refinement 都只是候选研究算法，必须版本化、可替换和实证验证。

Synthetic questionnaire evidence 只生成 provisional DesiredDelta；重要维度后续通过用户自身 baseline 的 identity-preserving candidates 做 self-transfer validation。有效冲突时 self-transfer evidence 优先。

## 题库资产

**OPERATIONAL TARGET**：初始目标约 200 个成年合成身份，规模可依据 QA 成本、覆盖与稳定性调整。当前假设几何题通过同一 Base Identity 的 canonical normalization + deterministic warp 构成，只改变目标维度；风格题可使用生成式编辑，但必须通过 landmark comparison 防止几何混杂。

正式题库的新候选适用 ADR-052 / `P2_QUESTIONBANK_GENERATION_POLICY_V3`：只允许
`ADULT_18_19` 与 `ADULT_20_25`，20–25 为多数，且每项都必须是 synthetic-only、
`VERIFIED_SYNTHETIC_ADULT`、`suspected_minor=false`。18–19 只允许非性化表达；全正式 pack 禁止
sexualized/fetishized framing。China-first、East-Asian-presenting 是合成 presentation scope，不是
真实用户的 race/ethnicity/ancestry/nationality 标签或路由字段，也不得通过真人、名人或社交平台肖像
构造刺激。

`GEOMETRY_PAIR` 与 `STYLE_PAIR` 使用不同的验证逻辑：前者只改变一个主要 geometry dimension，
最多包含一个预注册的必要相关变量；后者保持主要 facial geometry，只改变一个版本化 style direction。
两者都必须固定拍摄语法，分别验证 pair 两侧的 source、adult、quality、likeness、duplicate 与
anti-homogenization hard gates，再验证 pair comparability 和 variable isolation。不得用一侧明显更差、
大幅妆容/发型/服饰/姿态/背景差异或多个同时变化的变量制造选择。

产品 curation 只保存 natural anatomy、visual finish、individual distinctiveness、questionnaire suitability
和 fair comparability 等 categorical evidence；禁止 beauty/attractiveness score、rating、ranking、
percentile 或统一理想脸。Web Demo 只能使用预生成且通过同等 Gate 的 synthetic assets，并维持真实用户
运行时 generation 调用为 0。

QA 流程：生成 → 解码 → 标准化 → 单脸检测 → 姿态/遮挡/清晰度/曝光 → landmark → 目标 delta → confound → pair consistency → PASS。只有 PASS 资产能进入已发布题库。

每个资产只记录实际可得的生成 Provider/模型事实、Prompt policy 版本与 digest、合成来源、目标与实测 delta、姿态、QA 版本和状态；未暴露的 Provider/model/request/seed/usage/cost 保持 `NULL`。完整 Prompt、seed value、图片或 private locator 不进入 tracked authority、普通日志或 UI。未经正式 QA 的 Mock fixture 不得展示给真实用户。
