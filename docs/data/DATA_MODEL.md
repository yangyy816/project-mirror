# 数据模型与不变量

## 领域分组

- 身份与授权：User、InviteCode、InviteRedemption、PhoneVerificationChallenge、UserSession、AgeAssuranceRecord、PolicyAcceptanceRecord、Consent。
- 资产与审计：Asset、AssetVariant、AssetAccessAudit、append-only AssetIngestionRecord。
- 上传控制：UploadIntent、append-only UploadIntentEvent；quarantine intent/object 不是 Asset，M4 验证晋升前不得作为 Original 引用。
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

P7 未来将研究 `AcceptedVisualEpisode`、Visual Memory Bundle、Memory Card、temporal/procedural views 与 retrieval indexes。它们当前不是 Phase 1 schema：不得提前建表或冻结字段。权威关系必须保持“用户确认的 durable evidence → 可重建派生视图/Profile”，图片二进制仍只进入私有对象存储，关系数据只引用 opaque asset ID。方向见 `docs/architecture/VISUAL_MEMORY_OS.md`。

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
- InviteRedemption、AgeAssuranceRecord 和 PolicyAcceptanceRecord 是 append-only 审计事实；邀请码只在 OTP 成功消费、新用户创建与兑换的同一事务中增加使用量。`User.age_confirmed_at` 如存在只是投影，不是年龄证据权威来源。
- PhoneVerificationChallenge、UserSession、IdempotencyRecord 和 session family 只保存用途隔离的 HMAC 或不可枚举引用，绝不保存手机号、OTP、邀请码、refresh token 或年龄凭证原文。refresh token 重用会撤销其 family；pending 用户在有效年龄与政策记录齐备前不能成为 active。
- Consent grant/withdrawal 与 UploadIntentEvent 只追加；withdrawal 精确引用有效 grant。UploadIntent 可更新受限 operational state，但每次 transition 必须有 event，owner、consent、opaque quarantine key、声明 metadata 与状态时间由 PostgreSQL 约束。`uploaded_unverified` 不等于安全图片或 Original Asset。
- 一个 UploadIntent 最多有一个 authoritative ingestion Job。实际开始过 attempt 的 Job 最多有一个 final AssetIngestionRecord：promoted record 必须精确引用同 owner 的 immutable Original Asset，rejected record 不得引用 Asset。若 intent 在首次 claim 前已 tombstone，Job 可在 `attempt_count=0` 时 terminal-cancelled，且不得伪造 JobAttempt 或 AssetIngestionRecord；Job 的 cancelled 结果、UploadIntentEvent 与 AuditLog 共同形成取消证据。Job/JobAttempt 是可恢复的 operational state，AssetIngestionRecord 与 UploadIntentEvent 是不可覆盖的业务证据。
- Original Asset 只记录 canonical sanitized output 的 opaque storage key、实际 MIME、摘要、大小和方向校正后尺寸。客户端声明与 raw quarantine key 不能复制成 Asset metadata；raw object 永远不是 Asset。
- 未来 P7 中，未保存/确认的 AI 输出不得成为持久审美证据；AestheticProfile 与所有视觉/语义/时序/程序索引必须能由仍获授权的 evidence 重建，源证据删除必须使所有依赖派生表示删除或失效。

## 版本策略

Consent、题库、Profile、Prompt、模型调用和 Reference Set 都必须带版本或不可变外键。任何重新计算产生新版本，不能改写历史解释。

Question route 的复现至少依赖 routing algorithm、question bank、SelfState、baseline analyzer、normalization、morphology descriptor、neighborhood metric、stimulus generator 与 seed 的共同版本，而不是 seed alone。

## 删除与恢复

账户删除先冻结会话与外部调用，写入审计事件，标记资产进入删除队列，再按保留政策删除对象与可识别数据。不可变财务/安全记录在法定保留期内去标识化保存。恢复只允许在对象尚未物理删除且用户撤销删除请求的窗口内执行。
