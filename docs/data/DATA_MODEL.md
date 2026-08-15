# 数据模型与不变量

## 领域分组

- 身份与授权：User、InviteCode、PhoneVerificationChallenge、UserSession、Consent。
- 资产与审计：Asset、AssetVariant、AssetAccessAudit。
- 题库资产：QuestionBankVersion、SyntheticIdentity、QuestionAsset。
- 个人审美：AestheticProfile、AestheticProfileVersion、ReferenceSet、PreferenceEvent。
- 自身状态：BaselineFaceModel、BaselineMeasurement、SelfState、BaselineMorphologyDescriptor。
- 期望变化：DesiredDeltaProfileVersion、DesiredDeltaDimension、StyleProfileVersion、IdentityConstraintVersion。
- 个性化问卷：QuestionTemplate、QuestionInstance、QuestionnaireRoute、QuestionResponse，以及绑定 baseline/SelfState 的 QuestionnaireRun；旧的通用 Question/QuestionPair 占位实体已由 v0.2 取代。
- Self-transfer：SelfTransferValidationRun、SelfTransferValidationResponse。
- 编辑：EditingSession、Message、ImageVersion、EditOperation。
- 模型与任务：ModelRun、Job、JobAttempt。
- 权益账务：Plan、Subscription、Entitlement、CreditAccount、CreditLedger、PaymentEvent。
- 治理：AuditLog。

## 强不变量

- ProfileVersion 和 CreditLedger 只可追加，不可更新或删除。
- BaselineFaceModel、BaselineMeasurement、SelfState、MorphologyDescriptor、DesiredDelta/Style/IdentityConstraint 版本与 self-transfer evidence 只追加，不覆盖历史。
- Original Asset 的 blob 地址、摘要、大小、尺寸和 MIME 不可改变；删除采用状态与异步清理。
- QuestionRun 永久锁定一个 QuestionBankVersion。
- Canonical Slot 范围是 1–72；回答为五级序数 `-2..2`。
- PreferenceEvent 必须来自明确用户行为，模型自产结果不得写入长期学习事件。
- DesiredDelta 表示相对于 SelfState 的方向和幅度；各类 confidence 分开；显式 preserve lock 不等于零 delta。
- Synthetic evidence 是 provisional；有效 self-transfer 冲突证据优先。任何人口先验都不得成为 target geometry。
- Credit 通过 Ledger 求和得到，用户表和账户表不保存可直接覆盖的余额。
- PaymentEvent 以 provider + provider_event_id 去重，浏览器成功页不是支付依据。

## 版本策略

Consent、题库、Profile、Prompt、模型调用和 Reference Set 都必须带版本或不可变外键。任何重新计算产生新版本，不能改写历史解释。

Question route 的复现至少依赖 routing algorithm、question bank、SelfState、baseline analyzer、normalization、morphology descriptor、neighborhood metric、stimulus generator 与 seed 的共同版本，而不是 seed alone。

## 删除与恢复

账户删除先冻结会话与外部调用，写入审计事件，标记资产进入删除队列，再按保留政策删除对象与可识别数据。不可变财务/安全记录在法定保留期内去标识化保存。恢复只允许在对象尚未物理删除且用户撤销删除请求的窗口内执行。
