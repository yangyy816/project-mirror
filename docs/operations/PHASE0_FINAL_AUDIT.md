# Phase 0 Final Audit Evidence

日期：2026-08-15。所有本地结果均来自当前工作树；未执行项不计为 PASS。

## 本地通过

- Python：Ruff format/check、strict mypy、41 tests PASS。
- TypeScript：Prettier、ESLint、strict typecheck、3 test files PASS、Next.js production build PASS。
- API：Windows 原生启动；live/version 返回 200；本机无 PostgreSQL/Redis 时 ready 返回 503 + `limited`，未伪造 ready。
- Web：Windows production server 启动并返回 HTTP 200；首页服务端读取真实 API live 状态。
- Contract：FastAPI OpenAPI 与提交 JSON 一致；generated TypeScript in-process drift check PASS。
- Supply chain：Python 与 Node 漏洞审计均为 no known vulnerabilities；许可证摘要与 Python CycloneDX SBOM 可生成。
- Hygiene：源码扫描未发现凭据、真实人脸图片、真实用户数据、公开桶配置或生产 Provider 调用。
- v0.2：纯数值 fixture 验证 relative-delta anchoring、no-response restraint、explicit lock、evidence precedence、SelfState-conditioned routing 与 variable isolation。

## 本轮权威基础设施执行

- Docker：Desktop/Engine 29.7.2、Compose 5.3.1、Linux/WSL2；Compose config 与 API/Worker/Web 全镜像 build PASS。
- Compose：PostgreSQL 17.6、Redis 8.2.1、API、Web、Linux Celery Worker 全部通过 `up --wait`；API live/ready 与 Web 返回 200，ready 真实报告 database/redis `available`。
- PostgreSQL：初始 migration downgrade/upgrade/downgrade/re-upgrade 与 `alembic check` PASS；完整 Linux 容器 Python suite `50 passed`，8 个数据库 invariant 无 skip。
- Redis/Celery：Worker inspect `pong`；真实 Redis broker/backend round trip PASS，最终 Worker suite `5 passed`。
- Gitleaks：固定容器 `zricethezav/gitleaks:v8.28.0` 对 Git 可提交文件快照执行 `--no-git --redact`，扫描 528432 bytes，`no leaks found`。被忽略的 `.venv`/`.next` 不属于提交扫描范围。
- Image hygiene：最终镜像 Config.Env 未发现项目凭据；源码媒体文件计数为 0；未发现真实人脸或用户数据。

## Authoritative Acceptance Closure Recheck

2026-08-15 复核发现 Docker Desktop 29.7.2、Linux Engine 与 Compose 5.3.1 已可用，原“本机没有 Docker”证据已过期。Compose 静态配置解析通过；镜像构建、容器启动、PostgreSQL/Redis/Celery 集成仍须以本轮实际执行结果更新。现有 CI 覆盖数据库、Redis、Celery 与 Gitleaks，但缺少 Docker image/Compose validation；在补齐并实际执行前不得声称 CI 已覆盖该 Gate。

首次完整镜像构建因 Docker Hub OAuth 连接被远端重置而失败，分类为 `EXTERNAL_SERVICE_FAILURE`；未改版本重试后 API、Worker、Web 三个镜像均成功构建。首次 Compose 启动发现 Web standalone trace 中 `@swc/helpers` 只包含 CJS 文件但 Next.js 服务端需要 ESM helper，分类为 `DOCKER_DEFECT`；该缺陷必须最小修复并重新执行 Compose 后才能计为通过。

Web 镜像最小补齐被 trace 遗漏的 ESM helper 后，完整 Compose 五服务均启动并通过 health wait；live/ready/version/Web 均返回 200，ready 真实报告 PostgreSQL 与 Redis `available`，Celery inspect 返回单节点 `pong`。随后 migration lifecycle 在首次 downgrade 后重升级时报 `DuplicateFunction`：初始 migration 的 downgrade 未删除三个 trigger function，分类为 `MIGRATION_DEFECT`；需补齐清理并从头重跑 migration 与数据库 invariant 测试。

补齐 trigger function 清理后，两轮 downgrade/upgrade 成功；`alembic check` 继续发现 4 个 check constraint 名超过 PostgreSQL 63 字节后被服务端截断，导致 metadata 与数据库名称不一致，分类为 `MIGRATION_DEFECT`。修复要求是同时缩短模型与初始 migration 的约束名，不改变约束表达式或数据语义。

约束名统一后 migration downgrade/upgrade/downgrade/re-upgrade 与 `alembic check` 实际通过。首次 PostgreSQL invariant suite 暴露测试夹具将仅以原始 FK 关联、没有 ORM relationship 的父子对象同批 flush，插入顺序未被 ORM 保证，PostgreSQL 正确返回 FK violation，分类为 `CODE_DEFECT`（test fixture）；修复只将夹具按父到子分阶段提交，不弱化任何数据库约束。生产 API 镜像不包含仓库级契约文件，因此完整 Linux 测试使用只读挂载当前工作树的测试容器执行，不把测试资产加入运行镜像。

## 权威 CI 路径与远端收口

`.github/workflows/ci.yml` 使用 PostgreSQL 17.6 与 Redis 8.2.1，执行 migration upgrade/downgrade/re-upgrade/check、直接 SQL invariant tests、Linux Celery round trip、Python/TypeScript gates、contract drift、dependency/license/SBOM、Docker/Compose smoke 与 Gitleaks。私有远端为 `yangyy816/project-mirror`，分支为 `main`；所有结论均来自实际 push 触发的 GitHub Actions，而不是静态配置推断。

首次远端 baseline run `31871452535`（commit `39b14c68a05438b302f0f5b9471d8a0a1bef06e0`）中，`quality-and-integration` 与 `secret-scan` PASS；`docker-validation` 的镜像构建与 Compose 启动 PASS，但第一条 API curl 返回 `Recv failure: Connection reset by peer`。根因为 API、Worker、Web 缺少 Compose healthcheck，`up --wait` 只能等待容器进入 running，不能证明服务已接受请求，分类为 `CI_CONFIGURATION_DEFECT`。修复必须加入真实服务健康检查并让 Web 依赖 API healthy，再执行本地 Compose 与完整远端 CI。

修复提交 `796ab552fb3a92af5eddac5ef23086a4037323e7` 为 API、Worker、Web 增加真实 healthcheck，并令 Web 等待 API `service_healthy`。本地五服务 `up --wait` 后首次 API live/ready 与 Web 请求均返回 200；精确提交内容的 Gitleaks v8.28.0 扫描无发现。

该修复提交触发 run [`31871724239`](https://github.com/yangyy816/project-mirror/actions/runs/31871724239)，于 2026-08-15 完整通过：

- `quality-and-integration`（job `94981306215`）：Python quality/tests、PostgreSQL migration lifecycle、database invariants、Linux Celery、TypeScript checks/build、contract drift、dependency/license audit 与 SBOM 全部 PASS。
- `secret-scan`（job `94981306125`）：Gitleaks PASS。
- `docker-validation`（job `94981306139`）：Docker build、Compose start/wait、行为 smoke 与 cleanup 全部 PASS。
- Artifacts：`phase-0-audit-evidence`（ID `9243633315`）、`phase-0-docker-evidence`（ID `9243625550`）、`gitleaks-results.sarif`（ID `9243603254`）均由该 run 产出。

部分 GitHub Actions 输出 Node 20 弃用 annotation，但 workflow runner 已强制 Node 24，三个 job 结论均为 success；该提示记录为非阻断的上游 Action 维护事项。

## 结论

`PHASE 0: PASS`。本地权威 Gate 与修复提交的完整远端 GitHub Actions 均已通过；本审计提交和 `phase0-baseline` 标签仍须分别通过其 push-triggered workflow，完成后冻结 Phase 0，不进入 Phase 1。
