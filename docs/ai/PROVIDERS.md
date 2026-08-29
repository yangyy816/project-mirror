# AI 与外部 Provider 策略

## 接口

- `SmsProvider`：发送验证消息；日志只保留散列引用和 Provider message id。
- `ObjectStorageProvider`：私有上传/下载、短时签名和删除。
- `VisionProvider`：质量、姿态、单脸与可测量 landmark，不做身份识别或敏感推断。
- `ImageGenerationProvider`：合成人物与复杂局部编辑。
- `AgentProvider`：结构化理解和 EditPlan，不直接持久化或扣费。

## 当前实现状态

Local/Mock Provider 可重复、无网络、无真实用户数据。腾讯云与腾讯混元类只保留显式候选边界，调用时必须失败，不得误认为已接通。

ADR-026 另行批准 `CODEX_NATIVE_IMAGEGEN` 作为 P2 synthetic-only 的 operator-assisted offline
development source。它通过受控 admission 把已生成文件写入 private synthetic raw namespace，
不是 runtime `ImageGenerationProvider`，不进入 application/Worker production config，也不代表
模型、条款或生产 Provider 已获批准。未知 model、request、seed、usage 与 cost 字段必须保持
`NULL`。

ADR-052 的正式 QuestionBank policy v3 进一步要求新 private PromptTemplate 绑定 allowlisted semantic
contract：clearly adult、18–25、East-Asian-presenting first-wave、front-facing、direct gaze、neutral
natural expression、stable soft lighting、clean neutral background、consistent framing、natural facial
anatomy、synthetic non-real person，以及 no celebrity/public-figure resemblance。Geometry pair 还必须
绑定 same synthetic base identity、同等 pose/camera/lighting/hair/makeup/background、只改变命名的
facial dimension 并保留所有非目标属性。完整 Prompt、seed value、图片、private locator、object key、
signed URL 与 Provider raw payload 不得进入 Git、MEMORY、普通日志、artifact 或 UI；只有版本引用、
semantic contract、digest、checksum 和 allowlisted aggregate evidence 可进入 tracked authority。

V3 不改变 Provider 事实保真规则：`CODEX_NATIVE_IMAGEGEN` 继续只是 offline source kind，
`runtime_provider=false`；未暴露的 provider/model/request/seed/usage/cost 继续为 `NULL`。本地 Demo 只
消费预生成且已准入的 synthetic assets，真实用户运行时 generation 调用为 0。

## 生产准入基准

候选 Provider 使用合成测试集评估：身份保持、局部控制、几何泄漏、图像质量、内容安全、P50/P95 延迟、失败率、人民币成本、并发限制、地域、日志保留、公共训练、分包商和删除条款。任何一项未达安全门不得接收真实用户数据。

Provider 名称、模型、Prompt、输入资产引用、状态、成本与验证结果记录为 ModelRun；业务只依赖内部稳定类型。

生产 runtime image generation 当前为 `NOT_CONFIGURED` / `FAIL_CLOSED`，closure 条件登记于
`docs/operations/PRODUCTION_BLOCKERS.md`。

P2-M3 的 Vision 边界只消费 normalized synthetic Asset，不消费 Provider raw output、User Asset、URL、
object key 或 SDK type。deterministic Mock 只用于 CI。exact `v0.10.35` official wheels 因 Clearcut
telemetry 已拒绝；从同一 exact source 构建的最小 Face Landmarker C ABI 已完成 Windows/Linux
可复现、zero-egress 与 frozen synthetic holdout，只批准用于 private synthetic M3。固定 model bundle
保持 `PRIVATE_RESEARCH_ONLY`；distribution、production Vision 与 real-user facial processing 继续
fail closed。
