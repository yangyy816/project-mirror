# AI 与外部 Provider 策略

## 接口

- `SmsProvider`：发送验证消息；日志只保留散列引用和 Provider message id。
- `ObjectStorageProvider`：私有上传/下载、短时签名和删除。
- `VisionProvider`：质量、姿态、单脸与可测量 landmark，不做身份识别或敏感推断。
- `ImageGenerationProvider`：合成人物与复杂局部编辑。
- `AgentProvider`：结构化理解和 EditPlan，不直接持久化或扣费。

## 当前实现状态

Local/Mock Provider 可重复、无网络、无真实用户数据。腾讯云与腾讯混元类只保留显式候选边界，调用时必须失败，不得误认为已接通。

## 生产准入基准

候选 Provider 使用合成测试集评估：身份保持、局部控制、几何泄漏、图像质量、内容安全、P50/P95 延迟、失败率、人民币成本、并发限制、地域、日志保留、公共训练、分包商和删除条款。任何一项未达安全门不得接收真实用户数据。

Provider 名称、模型、Prompt、输入资产引用、状态、成本与验证结果记录为 ModelRun；业务只依赖内部稳定类型。
