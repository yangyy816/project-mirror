# Project Mirror

Project Mirror 是一个由长期个人审美记忆驱动的 AI Photo Editing Agent。Phase 0 工程基线已冻结，当前处于 **Phase 1 — Application Foundation**：P1-M1 邀请制身份认证后端已通过候选 Gate，仍不处理真实人脸、不接真实支付，也不开放生产注册。

## 当前可运行内容

- Next.js 中文首页，实时读取 API readiness。
- FastAPI 健康、版本与 `/api/v1` 能力边界。
- Celery Worker 的确定性基础任务。
- PostgreSQL 领域模型与 Alembic migration。
- OpenAPI → TypeScript 契约生成与漂移检查。
- 隐私、安全、问卷、Provider、部署与 ADR 文档。

## 本机启动（Windows，无 Docker）

```powershell
Copy-Item .env.example .env
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
pnpm.cmd install
.\.venv\Scripts\python.exe -m uvicorn mirror_api.main:app --host 127.0.0.1 --port 8000
```

另开一个终端：

```powershell
pnpm.cmd --filter @mirror/web dev
```

打开 `http://127.0.0.1:3000`。无 PostgreSQL/Redis 时 API 会明确进入 limited mode；不得用 SQLite 代替。Windows Worker 使用 `LocalTaskRunner`（`DEVELOPMENT ONLY`），Celery + Redis 的权威路径是 Linux CI 或 Compose。

若本机另行安装了 PostgreSQL，可再运行 Alembic；这一步不能在无 PostgreSQL 时伪造：

```powershell
.\.venv\Scripts\python.exe -m alembic -c services/api/alembic.ini upgrade head
```

## 验证

```powershell
.\.venv\Scripts\python.exe -m ruff check services
.\.venv\Scripts\python.exe -m mypy services/api/src services/worker/src
.\.venv\Scripts\python.exe -m pytest services/api/tests services/worker/tests
pnpm.cmd check
```

本机缺少 PostgreSQL、Redis 与 Docker 时，数据库迁移、不变约束和 Celery 集成测试会显式跳过并标记 `NOT VERIFIED LOCALLY`；Linux CI 是这些项目的权威验收路径。

## 安全边界

- 不要向本仓库加入真实人脸、手机号、验证码、令牌或云凭据。
- `.env.example` 只有键名和安全的本地默认值；真实值只能在未跟踪的 `.env` 或 Secret Manager 中。
- 腾讯云与国内 AI Adapter 当前是显式未验证边界，不会静默调用外部服务。

完整规格见 `docs/`，工程约束见 `AGENTS.md`，阶段决策见 `MEMORY.md`。
