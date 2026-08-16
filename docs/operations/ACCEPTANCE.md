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

## Phase 1 — Application Foundation Gate

- P1-M1–M5 各自具有同一 SHA 的本地/远端 Gate、acceptance closure 与冻结证据。
- 新用户邀请认证、现有用户登录、pending onboarding、年龄/政策激活、刷新轮换/reuse 撤销和 logout 在真实 PostgreSQL/Redis 上闭环。
- 用途 Consent 与政策接受分离；未激活、未授权、撤回、过期和账户冻结状态均不能签发新上传或下载能力。
- quarantine upload 不等于 Asset；只有经过 magic/MIME/decode/大小/像素/单帧/EXIF/metadata/canonical re-encode Gate 的 synthetic/non-face 对象可晋升为 immutable Original。
- Asset 访问始终 owner-bound、私有、短时且一次性；删除立即阻止新访问/处理，并由可重试的对象与 PostgreSQL evidence 证明完成。
- 数据导出仅包含允许的当前用户数据，排除 raw quarantine、secret、内部风险/审计、prompt 和其他用户；短期归档按证据链清理。
- 账户删除原子冻结账号并撤销 session，传播 Consent/upload/ingestion/Asset/export 状态，等待旧 grant 到期屏障并最终去关联手机号散列。
- Web access token 只驻留内存；refresh Cookie 不可被 JavaScript 读取；download grant 不进入 URL、analytics 或持久浏览器存储。
- Phase 1 垂直生命周期、故障恢复、日志/审计脱敏、生产 fail-closed、迁移、契约、浏览器、供应链和容器必须在同一候选 SHA 零 mandatory skip。
- Candidate、acceptance closure 与最终冻结状态提交均需完整远端三个 jobs 全绿，且审计、Docker 与 Gitleaks artifacts 可下载、可读、未过期。

真实手机号/年龄 Provider、COS、真实 facial data、生产告警后端、备案/PIPIA/法律批准、支付、AI、公开注册和部署均不是 Phase 1 PASS；这些 Gate 未解除时继续 fail closed。

`PHASE_1_GATE: NOT_YET_EVALUATED`
