# Project Mirror Memory

## 基本信息

- 项目名：Project Mirror（内部名，正式品牌待定）
- 建立日期：2026-08-15
- 当前目录：`D:\p`
- 当前阶段：Phase 1 — Application Foundation（COMMITTED）
- 当前 Milestone：P1-M3 — Purpose Consent, Authorization and Private Upload Control Plane（EXECUTING）
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
- Project Mirror 使用项目级 `.codex` 定义专属 subagents：规划与最终审查使用 Sol High，边界明确的执行/测试/安全角色使用 Terra High；未指定 subagent 默认 Terra High，不覆盖主交互模型、不固定并发数、不修改全局 Codex 配置。
- 新增第三层 `pm_fast_worker`，精确使用 `gpt-5.3-codex-spark` + `medium`，仅路由通过 Small/Precise/Atomic/Reversible/Known-validation 全部条件的 micro task；Spark 不是默认模型，不得决定架构、安全/数据库语义或 Project Mirror 敏感领域 invariant，不确定时回退 Terra。
- 执行状态统一为 `PROVISIONAL → COMMITTED → EXECUTION_READY → EXECUTING → PASS → FROZEN`；Phase 0 与 P1-M1 已 FROZEN，Phase 1 COMMITTED，P1-M2 已完成 rolling-wave refinement 并进入 EXECUTING。
- Terra 只能实现 Principal 已批准的架构；新架构决策必须停止并上报。计划外实现缺陷使用 `P1-M1-Rxx` 最小 Repair Task，架构变化不得包装成 Repair Task。
- OSS 复用原则为“复用通用基础设施，保留个性化智能”：重大第三方组件必须分别审查代码、模型/权重、数据与传递依赖许可证，并通过 Principal change control；Terra 只能报告候选，不得自行安装、下载权重或接受条款。
- Identity-Preserving Makeup Transfer 已提升为 P6 Hybrid Editor 的一级高优先级研究轨道和能力子系统，与 Deterministic、Geometry、Generative Editor 和 Agent Tool Layer 并列，不得降格为单一 `makeup_transfer()` 工具；其未来链路为 Reference Makeup Understanding → MakeupStyleRepresentation → StyleProfile personalization → Structured MakeupPlan → region execution → identity/geometry verification → user correction → PreferenceEvent。
- Stable-Makeup 是高优先级研究参考，生产采用需完整依赖许可证审查；FLUX-Makeup 具有高算法/评估价值，但其被报告的受限 foundation-model 依赖在权威复核和商业清除前使直接生产路径保持 `PRODUCTION_BLOCKED`。
- 当前 P1-M2 不因 OSS/Makeup 研究增补发生变化：不新增依赖、模型资产或未来 bounded tasks；P6 到达 rolling-wave planning 时再确定独立研究 Milestone 与 GO/NO-GO/FURTHER_RESEARCH Gate。
- P1-M2-T06 经 Principal change control 允许 `@playwright/test@1.62.1` 作为 pinned test-only dev dependency；npm 元数据与包内 LICENSE 均为 Apache-2.0，Node 要求 `>=20`，不得进入生产 runtime 或调用真实 Provider。完整记录见 `docs/security/PLAYWRIGHT_ADOPTION.md`。
- P7 的前向方向已升级为 `Visual Memory OS & Persistent Preference Learning`，状态保持 PROVISIONAL。用户确认的 Visual/Behavioral/Explicit Truth 是权威证据；AestheticProfile、图、向量/视觉索引、Memory Card 与 semantic/temporal/procedural views 均为可重建 materialized state。未保存的 AI 输出无长期权威，当前指令优先，删除必须传播到全部派生表示；不新增当前依赖、模型资产、schema、ADR 或 P7 tasks。完整方向见 `docs/architecture/VISUAL_MEMORY_OS.md`。
- P1-M3 采用 ADR-018：政策接受与用途 Consent 分离；grant/withdrawal 和 UploadIntentEvent append-only；浏览器 ingress 先进入 owner-bound quarantine UploadIntent，绝不直接成为 Asset/Original。只有 active 且持精确有效用途授权的用户可获得一次性短时 upload grant；complete 仅形成 `uploaded_unverified`，M4 才负责解码、重编码、EXIF 清理和 Original 晋升。Local write-only ingress 只用于非生产合成 fixture，生产真实上传继续 fail closed。

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
- pnpm 内容寻址 store 位于 `D:\.pnpm-store`；受限沙箱无法访问 workspace 外 store 时会误触发 node_modules 重建，pnpm install/check/audit 应在获准的外部环境执行，局部静态检查可直接调用 workspace 内 `.bin`。

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
- 2026-08-15：审计提交 `f9398304b1a313540d80db701806d845f046bbb8` 的 run `31872379668` 与 annotated tag `phase0-baseline` 的 run `31872550234` 均三 jobs 全绿；tag 指向该审计提交，Phase 0 已冻结。
- 2026-08-15：为后续开发新增 8 个项目级 Codex 角色与 Terra High 默认 subagent；Codex CLI 0.148.0-alpha.9 严格解析和三角色只读 smoke 通过，未进入 Phase 1。
- 2026-08-15：P1-M1 获正式执行授权；不重跑 Master Planning，只追加统一状态机、Terra 架构权限边界和 `P1-M1-Rxx` Repair Task 协议，并明确不得进入 P1-M2。
- 2026-08-15：通过 Principal change control 登记 OSS/AI 供应链治理，并将 Identity-Preserving Makeup Transfer 提升为未来 P6 一级研究轨道；未改变 P1-M1 DAG，未添加依赖、权重或模型资产。
- 2026-08-15：P1-M1 T05/T07 经 Principal 接受。R13 阻止已消费、撤销或过期 session 的登录/刷新幂等重放重新签发访问令牌，并补齐 refresh reuse、logout family revoke、邀请码并发上限、OTP 失败持久化/过期、Provider 失败重试、年龄非通过状态与幂等冲突场景；Compose PostgreSQL 17/Redis 8 定向 23 项、容器 API 其余 85 项、宿主契约 11 项、Ruff 与 strict mypy 均通过。API 镜像未复制仓库级 `packages/contracts`，因此容器内契约文件读取不作为通过证据，完整仓库契约仍由宿主与 CI 验证。
- 2026-08-15：P1-M1 T06 经 Principal 接受。七个 `/api/v1` 认证/用户接口、Bearer 当前会话校验、真实 onboarding 缺口、精确政策配置、refresh/logout Origin + 双提交 CSRF、HttpOnly 轮换 Cookie、SecretStr 错误脱敏、CORS DELETE 与 OpenAPI → generated TypeScript 已闭环。R14 补充真实 session 撤销后的 access 拒绝及浏览器预检；安全复核发现直接账号枚举后，Principal 以 ADR-016 冻结通用 challenge 受理语义，R15 使用幂等 decoy 202 关闭枚举且不发送短信或创建真实 challenge。最终 Compose PostgreSQL 17/Redis 8 完整 API suite 96 PASS，无 skip；Ruff、strict mypy、Prettier、契约生成/漂移/typecheck/Vitest 均通过。真实 SMS Provider 的响应时间侧信道须在 P9 启用前重新 Gate。
- 2026-08-15：P1-M1 T08 candidate `99c4fcc7e1fea5e240da09b45e532b9d9c793088` 经 Principal 验收。R16 修复 SMS 成功后 finalize 失败使幂等 claim 永久停留 `in_progress`；真实 PostgreSQL 回归和完整 Compose API suite `98 passed`、零 skip。迁移 `0001→0002→0001→0002`、Ruff、strict mypy、`pnpm check`、契约漂移、Python/Node 漏洞审计和精确 index Gitleaks 均通过。远端 run `31886292870` 的三个 jobs 与三项 artifacts 全部成功；P1-M1 Gate 为 PASS，等待 closure CI 后 FROZEN。
- 2026-08-15：P1-M1 acceptance closure `1276a7466b7f4e9b0cd9fddaefcd13d5af3a05b0` 的远端 run `31886590832` 三个 jobs 全绿，并生成 `project-audit-evidence`、`project-docker-evidence` 与 `gitleaks-results.sarif`；Principal 将 P1-M1 状态前向更新为 FROZEN，下一步仅对 P1-M2 做 rolling-wave refinement。
- 2026-08-15：P1-M2 rolling-wave refinement 通过 ADR-017 与执行协议冻结浏览器会话、内存 access token、HttpOnly refresh + CSRF、single-flight refresh、外部年龄 popup bridge、精确政策 manifest、受限页面和 E2E Gate；P1-M2 进入 EXECUTING，未改变冻结的 M1 API。
- 2026-08-15：前向修订 P6 定位：Identity-Preserving Makeup Transfer 是一级能力子系统而非单工具，与 SelfState、StyleProfile、DesiredDeltaProfile、IdentityConstraints 和 PreferenceEvent 形成端到端链路；当前 P1-M2 无任务、依赖或 Gate 变化。
- 2026-08-15：接受精细模型路由政策；在保留 Sol High / Terra High 架构和 Terra 默认的前提下新增 `pm_fast_worker` Spark micro-task tier。官方文档与动态模型目录确认精确标识及 `low/medium/high/xhigh`；Codex CLI `0.148.0-alpha.9` 已以 strict-config、read-only、`medium` 完成直接 Spark 和按名 `pm_fast_worker` 委派 smoke。WindowsApps 原始可执行文件受 ACL 保护，验证使用 app-managed `.codex/.sandbox-bin/codex.exe`；ephemeral 会话无法建立子线程，普通 read-only 委派已通过。
- 2026-08-15：P1-M2 T03–T05 经 Principal 本地接受：可访问手机号/邀请码/OTP 流、严格外部年龄 popup、精确政策逐项接受、内存会话 Provider、`/join`、无受保护内容闪现的 `/account`、刷新恢复与可确认 logout 已实现。R01 修复测试类型边界；R02 阻止退出网络失败伪装成功；真实 Web unit suite 当前 52 PASS，production build 通过。
- 2026-08-15：P1-M2 T06 本地候选 Gate 建立 Playwright + deterministic Fake API/age provider；真实 Microsoft Edge + Next standalone 的 3 个端到端场景通过。R03 将 bootstrap 缺少 CSRF 安全降级为 anonymous 并要求重认证；R04 分离 Vitest 与 Playwright 收集边界。完整 `pnpm check`、Docker build/五服务 health、容器 PostgreSQL/Redis 97 PASS、Worker/Celery 5 PASS、隔离数据库 migration lifecycle、OpenAPI 零漂移和 Python/Node 漏洞审计均通过；等待 candidate SHA 的远端 CI。
- 2026-08-15：P1-M2 远端候选经 R05/R06 收口。R05 以 `vitest.config.ts` 关闭 Linux Bash glob 展开导致的测试命令故障；R06 补齐 Linux Next standalone 缺失的 `@swc/helpers/esm` 并处理 Windows junction realpath。最终 candidate `f4dd6f0a58635e0d8505a5fa0ce0c2ed366982aa` 的 run `31892402898` 三个 jobs 全绿，Chromium 安装与 Browser integration 实际执行，三项 artifacts 可下载且 Gitleaks SARIF 零结果；P1-M2 Gate 为 PASS，等待 acceptance closure CI 后 FROZEN。
- 2026-08-15：接受 P7 Visual Memory OS 方向补充；新增 MEM-01–MEM-12、AcceptedVisualEpisode、分层/时序/程序记忆、Admission/Write/Memory Gate、Active Visual Exemplars、Context Compiler、删除重编译与 MirrorMemoryBench 研究边界。P6 只承担 final-save provenance 前向兼容，不提前实现 P7。
- 2026-08-15：P1-M2 acceptance closure `0614ccf8fe526c6bfecc53da7117722247788ce7` 的 run `31892788852` 三个 jobs 全绿；Chromium browser Gate、契约、迁移、供应链、Gitleaks、Docker 与三项 artifacts 均实际通过。Principal 将 P1-M2 前向更新为 FROZEN；下一步只对 P1-M3 做 rolling-wave refinement。
- 2026-08-15：P1-M2 最终冻结状态提交 `aef81b1ec862b20138cf974da320640c7168b8b1` 的 run `31893106522` 三个 jobs 全绿，并产出 `project-audit-evidence`、`project-docker-evidence` 和零结果 Gitleaks SARIF；从该 SHA 创建 `codex/phase1-m3-upload-control`。
- 2026-08-15：P1-M3 rolling-wave refinement 通过 ADR-018 与执行协议冻结 purpose Consent、quarantine UploadIntent、一次性短时签名、owner-bound authorization、withdrawal tombstone、Local ingress 与 M4 promotion 边界；M3 进入 EXECUTING，不创建 Original Asset、不解码图片、不调用真实 COS 或处理真人 fixture。
- 2026-08-16：P1-M3-T02 经 Principal 验收。`0003_upload_control` 以前向列扩展、Consent 精确 supersession、owner-bound UploadIntent、20 MiB/声明 MIME/SHA-256/期限边界、append-only event 与并发 opaque key 唯一性建立 PostgreSQL 控制面；R01 避免对受不可变触发器保护的历史 Consent 执行回填 UPDATE，R02 清理测试 settings cache 以确保 Alembic 只操作隔离库。真实 PostgreSQL `0001→0002→0003→0002→0003`、18 项迁移/不变量和完整 106 项 API PostgreSQL/Redis/契约测试通过；未创建 Asset/Original，未处理图片 bytes。
- 2026-08-16：P1-M3-T03 经 Principal 验收。ObjectStorageProvider 扩展为 provider-neutral PUT grant、quarantine metadata inspection 与幂等 delete；Local adapter 使用 CSPRNG grant handle + 仅存 HMAC proof、固定 opaque key、loopback-only ingress、一次性/TTL、声明 MIME/长度/SHA-256、20 MiB bounded streaming、symlink/containment 防护和无覆盖原子发布，Tencent COS 边界继续 fail closed。`/_local/private-upload/{grant_id}` 仅非生产写入且从 OpenAPI 隐藏，无 GET；访问日志 scope、错误和状态不暴露 proof、object key 或 bytes。Linux 定向 36 项、完整 API PostgreSQL/Redis/契约 120 项与五服务健康通过，只使用合成非人脸 bytes。
- 2026-08-16：P1-M3-T04 经 Principal 本地验收。Purpose Consent application 以独立配置和事务服务实现 active-user grant、非 active 仍可 withdrawal、精确 purpose/policy/scope、HMAC 幂等、current-state 推导、并发 grant/withdrawal、owner-bound 撤回，以及同事务 tombstone `awaiting_upload`/`uploaded_unverified` intents 和白名单审计；production 拒绝零 policy digest。R03 修复完整套件复用 PostgreSQL 时 Consent 与 QuestionBank fixture 残留；全新隔离库 migration lifecycle/`alembic check`、T04 定向 31 项及完整 API 128 项通过，未创建 Original Asset 或处理图片内容。
- 2026-08-16：P1-M3-T05 经 Principal 本地验收。UploadIntent application 在同一用户锁/事务中校验 active actor、精确有效 Consent、HMAC 幂等与并发/累计声明配额；服务端生成 opaque key，每个 intent 只签发一次，查询/complete/cancel 均以 owner SQL predicate 绑定。complete 只比对 Provider metadata 并进入 `uploaded_unverified`，撤回、过期或 mismatch 先持久 tombstone 再删除 quarantine，cleanup 失败仍保持 fail-closed；不创建 Asset/Job。R04 修正 PostgreSQL `JSON` scope 不可直接相等比较，显式转为 `JSONB` 保持精确语义；8 项定向测试和完整 API 136 项通过，仅使用合成非人脸 bytes。
- 2026-08-16：P1-M3-T06 经 Principal 本地验收。ADR-018 七个 `/api/v1` Consent/UploadIntent 接口已接入真实 application services，响应不暴露 object key，grant URL/headers 仅出现在 create 响应，本地 PUT ingress 继续隐藏于 OpenAPI；旧 `/api/v1/assets` 501 stub 已移除。Auth/DB/Redis/storage 通过共享 infrastructure 注入，上传频率、并发 intent 与累计 bytes 可配置；OpenAPI 单向生成 TypeScript 零漂移。R05 补齐浏览器私有上传所需 PUT 与完整性/授权 CORS headers；HTTP 定向 23 项、完整 API 139 项、contracts Vitest/typecheck、52 个 Web tests 与 Next production build 通过。
- 2026-08-16：P1-M3 candidate `26fe43213519cebd4eda157b46035cc0beb43cc5` 经 Principal Gate PASS。全新 PostgreSQL migration lifecycle、145 项 Python/Redis/Celery、`pnpm check`、3 项 Playwright、全镜像/五服务、供应链和精确 index Gitleaks 均通过；R06 仅补齐 Worker 生产 fixture 的非零 purpose policy digest。远端 run `31897237022` 的 `quality-and-integration`、`secret-scan`、`docker-validation` 与三项 artifacts 全绿；P1-M3 状态为 PASS，等待 acceptance closure CI 后 FROZEN。
