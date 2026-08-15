# ADR-012：Relative DesiredDelta Preference Model

## Status

Accepted — 2026-08-15。

## Context

绝对几何偏好向量无法区分方向、幅度、各类置信度、显式 preserve lock、上下文和证据来源，也会诱发跨用户同质化。

## Decision

主要几何意图表示为 `IdentityAnchor + DesiredDelta`。每个维度独立记录 direction、magnitude、measurement/preference/generalization/transfer confidence、bounds、context、evidence 和 user lock。delta≈0 不等于 preserve lock。StyleProfile 与几何分离。

## Alternatives Considered

绝对 target vector；二元“喜欢大/小”标签；单个 embedding；只在 Profile JSON 保存不可查询数据。

## Consequences

编辑目标按 SelfState 计算；问卷需分别估计方向与幅度；历史 Profile 链接版本化 delta/style/constraints；数据模型更规范化。

## Security / Privacy Considerations

人口先验不能提供目标几何。显式锁与用户证据优先，证据不足时 delta 收缩而不是回退到审美模板。

## Testing Implications

验证 preserve lock、bounds、证据优先级、不同 baseline 相同 delta、no-response convergence 和 Profile append-only。
