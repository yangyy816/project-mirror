# Project Mirror Memory

## 基本信息

- 项目名：Project Mirror（内部名，正式品牌待定）
- 建立日期：2026-08-15
- 当前目录：`D:\p`
- 当前阶段：Phase 0 + 可运行工程骨架
- 首发策略：中国大陆、18+、手机号 + 邀请码、小规模私测 Beta
- UI：简体中文默认，预留国际化

## 已确认的架构决策

- 使用 pnpm + Turborepo Monorepo。
- Web 使用 Next.js App Router、React、TypeScript、Tailwind。
- API 使用 Python 3.13、FastAPI、Pydantic、SQLAlchemy 2、Alembic。
- PostgreSQL 是唯一权威关系数据库，SQLite/内存数据库不得用于 migration、constraint 或 invariant 验收。本机无 PostgreSQL 时 API 进入有限能力模式并明确报告 unavailable。
- Worker 业务逻辑经 Task Interface 运行；Windows 开发使用 `LocalTaskRunner`，Celery 是 Linux + Redis 的生产执行 Adapter，权威集成验证在 Linux CI。
- 生产基础设施目标为腾讯云：CVM/容器、RDS PostgreSQL、Redis、私有 COS、CLB/WAF、日志服务与短信；增长后可迁移 TKE。
- 登录首选手机号 + 邀请码；短信必须经过 `SmsProvider`。
- AI 采用国内 Provider 优先、多 Provider Adapter；腾讯混元只是首选评估候选，未经能力、成本和数据条款基准验证不得标记为生产默认。
- 支付首阶段只建立 Entitlement、CreditAccount、不可变 CreditLedger 与 Payment Adapter 边界，不接真实微信或支付宝支付。
- 环境分为 development、test、ci、production；生产配置必须 fail closed，拒绝 Mock/Local、开发 CORS、Debug、不安全 Secret 和未通过 Gate 的能力。
- OpenAPI 是 HTTP 契约权威来源，TypeScript client 由其生成并由 CI 检查漂移。
- 本阶段不生成正式题库、不处理真实人脸、不接真实支付、不公开上线。
- Master Specification Revision v0.2 已采用：核心架构改为 self-conditioned aesthetic modeling。
- `BaselineFaceModel` 表示版本化测量证据，`SelfState` 表示供路由和个性化使用的版本化当前状态；两者不得混为一体。
- `DesiredDeltaProfile` 成为主要几何编辑意图，表达相对于 SelfState 的方向、幅度、各类置信度、证据、上下文、边界与显式锁；不再以通用绝对 PreferenceVector 为主。
- 问卷路由必须由连续 SelfState、测量可靠性、覆盖与不确定性条件化，并保存完整算法/数据/seed 版本以便复现。
- 有效 self-transfer 证据高于冲突的合成问卷证据；显式指令、手动修正和 feature lock 具有更高语义优先级。
- Anti-homogenization 是显式架构要求：证据不足时 delta 接近 0 且不确定性升高，不允许回退到全局理想脸。
- Phase 0 仍严格禁止真实人脸处理、真实数据集、生产视觉/编辑调用和真实 self-transfer。
- v0.2 持久化已落为独立版本实体：BaselineFaceModel/Measurement、SelfState/MorphologyDescriptor、DesiredDeltaDimension、Style、IdentityConstraint、QuestionTemplate/Instance/Route 与 SelfTransfer evidence；运行态 Run 可更新状态，历史 evidence 由 PostgreSQL trigger 防覆盖。
- 未共享、未执行的 `0001_phase0_foundation` 已在首次权威 PostgreSQL 验收前按 v0.2 一次性重生成；从下一次 migration 起只允许前向追加。
- Phase 0 OpenAPI 暴露 inactive domain schemas 供生成契约使用，但没有新增成功型业务 endpoint；未实施业务仍为 501/401。

## 长期产品与数据边界

- 产品是长期个人审美记忆驱动的 AI Photo Editing Agent，不是换脸、颜值评分或统一审美系统。
- Aesthetic Profile 保存结构化偏好、置信度、证据、约束和 Reference Set，并且只能创建新版本。
- 用户记忆分为稳定偏好、强约束、会话偏好和行为证据；只有用户行为可更新长期 Profile。
- 原始图片不可修改；ImageAsset、ImageVersion 与 EditOperation 形成非破坏式编辑图。
- 人脸图片、landmark、几何测量与参考图按高度敏感个人数据处理。
- Facial Data 的具体技术处理类型必须区分；未经法律判断不得一概称为法律意义上的“人脸识别”。真实敏感数据处理受 `LEGAL_REVIEW_REQUIRED` Gate 阻断。
- Consent 必须按用途、范围和政策版本追加记录，支持撤回、重新授权和历史审计，不能压成 Boolean。
- AI 生成或修改内容必须记录供应商中立的 provenance 与内容/元数据标识状态。

## Research Hypotheses（可替换）

- v0.2 当前研究方案：72 个 Canonical Slots，典型 58–64、约 50 最小、72 最大；self-relative direction、magnitude、cross-identity、interaction/style、reliability 分层；具体 inference/staircase/Bayesian 方法可替换。
- 这些不是产品 Invariant；可由实验替换为 Thurstone、Plackett-Luce、Bayesian Preference Model 或其他经验证方案。

## Operational Targets（可调整）

- 生产题库初始目标约 200 个可追溯成年合成身份，实际规模由 QA 成本、覆盖和稳定性实验决定。

## 本地环境基线

- Git 2.52.0.windows.1 可用。
- Node.js 24.18.0 可用。
- pnpm 11.19.0 可用。
- Python 通过 `py` 启动，版本 3.13.1。
- Docker Desktop/Engine 29.7.2 与 Compose 5.3.1 可用，运行 Linux/WSL2 engine；PostgreSQL 17.6 与 Redis 8.2.1 通过 Compose 提供测试基础设施，不要求在 Windows 主机单独安装。
- PowerShell 的脚本执行策略会阻止 `npm.ps1`；使用 `pnpm.cmd` 或可执行文件入口，不修改系统执行策略。
- Vitest/Vite 在受限 Windows 沙箱中会因 `net use`/esbuild 子进程产生 `spawn EPERM`；测试入口仅在 Windows 拦截无关的网络盘探测，实际编译子进程验收需允许正常创建。普通 Windows 与 Linux CI 不受该限制。

## Phase 0 当前验证状态

- 本地 Python：Ruff、strict mypy、41 个无基础设施测试 PASS；Docker Linux 全量 Python suite 50 PASS，PostgreSQL invariant 与 Celery/Redis integration 均无 skip。
- 本地 TypeScript：Prettier、ESLint、strict typecheck、3 个 test files、OpenAPI generated contract drift check 与 Next.js production build PASS。
- Windows smoke：FastAPI live/version 200；缺 PostgreSQL/Redis 时 ready 503 + limited；Next.js production server HTTP 200 并读取真实 API live。
- 供应链：Python 与 Node 漏洞审计在升级 pip 26.1.2、pytest 9.0.3、Vitest 3.2.6、PostCSS 8.5.23、Turbo 2.9.14 后均为 no known vulnerabilities；许可证摘要与 Python CycloneDX SBOM 可生成。
- Docker Compose 全镜像 build、五服务 health、API/Web smoke、PostgreSQL migration lifecycle/schema consistency、8 个数据库 invariant、Linux Celery+Redis round trip 均有实际 PASS 证据。
- Gitleaks v8.28.0 Docker 扫描 Git 可提交文件快照 PASS；`.venv` 与 `.next` 是被 Git 忽略的依赖/构建产物，不属于提交扫描范围。
- `.github/workflows/ci.yml` 已覆盖真实 PostgreSQL/Redis、migration lifecycle、Linux Celery、Gitleaks、供应链与 Docker Compose Gates；修复提交 `796ab552fb3a92af5eddac5ef23086a4037323e7` 的远端 run `31871724239` 三个 jobs 全部通过，Phase 0 Gate 更新为 `PASS`。
- GitHub 私有远端为 `yangyy816/project-mirror`，默认分支 `main`；初始 baseline commit 为 `39b14c68a05438b302f0f5b9471d8a0a1bef06e0`，首次远端 run `31871452535` 的 quality/Gitleaks PASS，Docker behavior 因 Compose 缺少应用 healthcheck 发生启动竞态而 FAIL。
- Compose 已为 API、Worker、Web 增加真实 healthcheck，Web 等待 API healthy；本地 `up --wait` 后首次 live/ready/Web 请求均为 200。该 `CI_CONFIGURATION_DEFECT` 已由修复提交的完整远端 run `31871724239` 关闭。
- Run `31871724239` 的 `quality-and-integration`、`secret-scan`、`docker-validation` 均 PASS，并产出 `phase-0-audit-evidence`、`phase-0-docker-evidence` 与 `gitleaks-results.sarif`；Node 20 弃用 annotation 非阻断，runner 已强制 Node 24。

## 阶段顺序

1. Phase 0 + 工程骨架
2. 账号与授权
3. 安全图片上传
4. 自适应审美问卷
5. Reference Set Agent
6. 非破坏式修图
7. 个性化学习
8. 额度与支付
9. 腾讯云私测部署
10. iOS

## 待验证外部事项

- 腾讯云具体产品地域、备案与数据驻留方案。
- 国内图像生成/编辑 Provider 的身份保持、局部控制、延迟、成本和数据条款。
- 微信/支付宝数字服务支付与退款的正式接入要求。
- 面向具体运营地区发布前的隐私、个人信息保护和人脸数据法律审核。
- PIPIA/个人信息保护影响评估审批，当前 Gate 为 `LEGAL_REVIEW_REQUIRED`。

## 凭据位置规则

- 本地凭据只允许放在未跟踪的 `.env` 文件或系统凭据存储中。
- CI/生产凭据只记录在对应平台 Secret Manager；本文件永不保存凭据值。

## 工作记录

- 2026-08-15：依据已确认方案建立项目基线；模板目录不存在，因此创建项目专用 `AGENTS.md` 与 `MEMORY.md`。
- 2026-08-15：接受 Phase 0 补充规格；移除 SQLite 权威验收，拆分 LocalTaskRunner/Celery，增加分环境 fail-closed、Consent history、AI provenance、PIPIA、供应链与架构漂移要求。
- 2026-08-15：采用 Master Specification Revision v0.2；引入 SelfState、BaselineFaceModel、DesiredDeltaProfile、SelfState-conditioned routing、self-transfer evidence precedence 与 anti-homogenization。初始 migration 尚未共享/执行，因此允许在首次权威 PostgreSQL 验收前随 schema 一次性重生成。
- 2026-08-15：完成 v0.2 schema、纯数值 domain/evaluation tests、初始 migration 重生成、inactive OpenAPI contracts、Linux CI、Docker/Compose、供应链锁定与 Windows Web/API smoke；本地可验证项通过，PostgreSQL/Redis/Celery/Docker/Gitleaks 保持待权威执行。
- 2026-08-15：Docker/Linux 权威验收修复 Web standalone 缺失 ESM helper、migration downgrade 遗漏 trigger function、超长 PostgreSQL constraint 名与无序父子测试夹具；最终 Compose build/start、50 个 Linux tests、migration lifecycle、PostgreSQL invariants、Celery+Redis 与本地 Gitleaks PASS。仅完整 GitHub Actions 因缺 remote/认证仍待执行。
- 2026-08-15：创建并推送 Phase 0 baseline `39b14c68a05438b302f0f5b9471d8a0a1bef06e0`；远端 run `31871452535` 暴露 Compose `up --wait` 未等待应用 ready，增加 API/Worker/Web healthcheck 并完成本地五服务复验，等待修复提交的远端 CI。
- 2026-08-15：推送 Compose healthcheck 修复 `796ab552fb3a92af5eddac5ef23086a4037323e7`；远端 run `31871724239` 的三个 jobs 与全部 mandatory steps 通过，生成三项审计 artifacts，Phase 0 Gate 更新为 `PASS`。
