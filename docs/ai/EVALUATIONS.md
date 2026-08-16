# Self-conditioned Evaluation Specifications

所有 Phase 0 评估只使用确定性数值、几何 placeholder 或非人类 fixture。真实人脸评估受 `CONSENT_REQUIRED`、`PRIVACY_REVIEW_REQUIRED`、`SECURITY_REVIEW_REQUIRED`、`LEGAL_REVIEW_REQUIRED`、`PROVIDER_VALIDATION_REQUIRED`、`PRODUCTION_READINESS_REQUIRED` 阻断。

P2–P7 的统一 benchmark authority、预注册/holdout/ablation 合同、MirrorBench family 与 future PoC backlog 见 `MIRROR_BENCH.md`。候选不得从“设计合理”直接进入生产架构；PoC 或单一指标成功不等于批准。

## Baseline Routing Sensitivity

输入两个只在相关可靠维度变化的 SelfState，以及一个只在无关/低可靠维度变化的 control。记录 routing algorithm、normalization、descriptor、metric、bank、stimulus 与 seed 版本；期望相关变化能改变 priority/stimulus neighborhood，无关变化保持稳定。

## Cross-Identity Generalization

对同一 target dimension 在多个局部 morphology 邻居重复 evidence。输出方向一致性、幅度 variance、generalization confidence degradation 与失败 identity；单 stimulus 不得直接获得高 generalization confidence。

## Synthetic-to-Self Transfer Error

Metric contract 比较 provisional synthetic DesiredDelta 与未来 self-transfer validated delta，按 dimension 输出 signed error、absolute error、transfer confidence 和 correction source。Phase 0 只验证 mock contract 与 evidence precedence。

## Question Variable Isolation

确定性向量 fixture 只修改 target dimension。输出 target_delta、non_target_max_error、isolation_threshold、pose validity、artifact status 与 validation status；任一非目标误差超限即 FAIL。

## Questionnaire Test-Retest Consistency

输出 direction stability、magnitude stability、response consistency、posterior stability 和 route stability；允许 adaptive run 展示不同实例，但完整版本元数据必须可解释差异。

## Identity Preservation

未来组合 geometry constraints、用户验证、图像 similarity 和经独立审查的 specialized metrics。Phase 0 不选择 face-recognition embedding；任何 biometric metric 重新触发隐私/安全/法律评估。

## Anti-Homogenization

长期 Gate 至少覆盖：不同 baseline + 相同 delta 保持不同绝对 target；相同问卷回答不坍缩；无 evidence 时 delta≈0/high uncertainty；cross-user target diversity；人口先验无法写入 target geometry；identity anchor 保持。

## Identity-Preserving Makeup Transfer（P6 future Gate）

P6 必须在同一套成年合成身份 benchmark 上比较确定性区域/颜色迁移、经典方法、Stable-Makeup-inspired、许可允许的 FLUX-Makeup research baseline、通用图像编辑模型、商业许可候选以及 hybrid pipeline。早期研究不得使用私有真实用户照片。

最低评估维度为：身份保持、非请求几何保持、参考妆容忠实度、区域准确性、皮肤纹理保持、伪影率、姿态鲁棒性、光照鲁棒性、强度单调可控性和用户偏好对齐。身份保持与显式约束是硬约束，优先级高于参考妆容忠实度；任何静默几何漂移、feature-lock 违反或非目标区域变化都必须使候选结果失败。

自动指标不能替代用户证据。用户对结果的接受、拒绝和区域级纠正可在 P7 形成 `PreferenceEvent`；模型生成结果本身不得进入长期学习。阈值、指标与最终 `MakeupPlan` schema 在 P6 研究获得证据前保持未冻结。

## Tool and memory evaluation direction

P6 的 `MirrorToolBench` 必须覆盖 tool/parameter/target-region correctness、forbidden-effect violation、rollback、idempotency、region leakage、cost、latency 及 EffectVerifier false-positive/negative。P7 的 `MirrorMemoryBench` 必须覆盖 visual/explicit/procedural recall、错上下文/陈旧/未授权记忆、时序冲突与漂移、相关证据降权、删除传播、Profile rebuild、context bound、延迟和成本。精确 ablation matrix 见 `MIRROR_BENCH.md`。
