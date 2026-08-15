# 阶段验收门

## Phase 0 + 骨架 PASS

- Web/API 可在 Windows 本机启动，首页读取真实 live/readiness/dependency 状态。
- Worker Application Service 可脱离 Celery 测试；Celery + Redis 只在 Linux CI/Docker 做权威集成验证，Windows solo 仅为 `DEVELOPMENT ONLY`。
- Python lint、类型、测试，TypeScript lint、类型、测试、构建均通过。
- Alembic 在真实 PostgreSQL 中从空库 upgrade 到 head、downgrade 到 base、再次 upgrade；SQLite/Mock 结果不得计入 PASS。
- OpenAPI 与生成 TypeScript 类型无漂移。
- 生产配置拒绝公开存储、Local Provider 和缺失腾讯云凭据。
- 安全测试覆盖路径穿越、危险 MIME、大小/像素限制、未授权边界和日志禁止项。
- 仓库无 Secret、真实手机号、真实人脸、公开桶或已启用真实支付。
- 所有未实施能力返回 `501`；文档、ADR、代码和 MEMORY 一致。
- SelfState 引用版本化 baseline；DesiredDelta 是相对变化且不会回退到全局 target；显式锁与 self-transfer 证据优先级由纯数值 fixture 验证。
- QuestionnaireRun/Route/Instance 保存完整复现版本且无敏感特征路由字段；anti-homogenization evaluation 已定义。
- 若本机缺 PostgreSQL/Redis/Docker，对应项必须写为 `NOT VERIFIED LOCALLY`；只有 Linux CI 证据可解除条件状态。

## FAIL 条件

任何 Fake 被生产配置接受、迁移不可回滚、原图/Profile/Ledger 可覆盖、契约漂移、Secret 扫描失败、外部调用在测试中发生或真实业务入口伪造成功，都必须阻止进入下一 Phase。
