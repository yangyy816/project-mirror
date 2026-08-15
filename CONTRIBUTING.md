# Contributing

1. 修改前完整读取 `AGENTS.md` 与 `MEMORY.md`。
2. 架构或数据边界变化先提交 ADR/文档，再修改代码。
3. 不引入真实人脸或凭据作为 fixture。
4. 数据库变更必须使用 Alembic，验证 upgrade 与 downgrade。
5. OpenAPI 变化后重新生成 `packages/contracts` 并通过漂移测试。
6. 提交前运行 Python 与 TypeScript 的格式、lint、类型、测试和构建检查。

Commit 建议使用 Conventional Commits，如 `feat(api): add consent boundary`。
