# ADR-011：Self-conditioned Aesthetic Modeling

## Status

Accepted — 2026-08-15；supersedes v0.1 中以 generic face preference 为主要目标的冲突部分。

## Context

通用脸型偏好回答“用户通常喜欢什么脸”，不能可靠回答“用户希望自己的外观如何改变”，并可能把不同用户拉向隐藏的全局理想脸。

## Decision

Project Mirror 改为 self-conditioned desired-self modeling。用户自己的版本化 `SelfState` 是几何参考坐标；`BaselineFaceModel` 是测量证据。Target 概念上为 IdentityAnchor + DesiredDelta，受身份约束、显式锁、可靠性、偏好置信度和编辑强度限制。任何全局理想脸都不得定义编辑目标。

## Alternatives Considered

通用绝对 PreferenceVector；人口平均脸；人口分群审美模板；只依赖文本 Prompt。

## Consequences

问卷必须先绑定 baseline/SelfState，Profile 和 EditPlan 必须保存相对证据；跨用户同答案不再意味着相同绝对目标。

## Security / Privacy Considerations

SelfState 和派生测量是高度敏感数据，遵循 Consent、删除和 `LEGAL_REVIEW_REQUIRED`；不得推断敏感身份或锁定生物识别 embedding。

## Testing Implications

必须验证相对 delta、不同 baseline 锚定、无证据不收敛、敏感字段缺失和 anti-homogenization。
