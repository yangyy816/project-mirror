# ADR-013：Personalized Question Routing

## Status

Accepted — 2026-08-15。

## Context

固定或人口类别路由不能针对用户自己的改变方向，也可能引入敏感特征分类和不可复现刺激。

## Decision

路由必须连续、SelfState-conditioned、measurement-aware、uncertainty-aware、versioned、reproducible。QuestionTemplate 与用户特定 QuestionInstance 分离；邻域距离在排除目标维度后计算，并记录算法、数据、schema、feature mask 与 seed。敏感特征不得进入 routing metadata。

## Alternatives Considered

固定 72 题；round/square 等类别；人口/族群分类；仅保存 random seed。

## Consequences

QuestionnaireRun 必须绑定 BaselineFaceModel、SelfState 与全部版本元数据；测试需证明路由可以响应相关 baseline 变化且忽略无关维度。

## Security / Privacy Considerations

只使用连续必要几何与可靠性，禁止种族、民族、国籍等敏感标签。生产题库仍仅用成年合成人物。

## Testing Implications

增加 routing sensitivity、reproducibility、variable isolation、cross-identity 和 sensitive-field absence 评估。
