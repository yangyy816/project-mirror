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

QA 流程：生成 → 解码 → 标准化 → 单脸检测 → 姿态/遮挡/清晰度/曝光 → landmark → 目标 delta → confound → pair consistency → PASS。只有 PASS 资产能进入已发布题库。

每个资产记录生成 Provider/模型/Prompt 版本、合成来源、目标与实测 delta、姿态、QA 版本和状态。未经正式 QA 的 Mock fixture 不得展示给真实用户。
