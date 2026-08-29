# Project Mirror Memory

## 基本信息

- 项目名：Project Mirror（内部名，正式品牌待定）
- 建立日期：2026-08-15
- 当前目录：`D:\p`
- 当前阶段：Phase 2 — Synthetic Dataset Engine（COMMITTED）
- 当前 Milestone：P2-M5 — Variable Isolation, Duplicate and Diversity QA（EXECUTING）
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
- Project Mirror 使用项目级 `.codex` 定义专属 subagents：规划与最终审查使用 Sol High；安全审查和 `pm_terra_high_worker` 的已冻结困难实现使用 Terra High；普通 backend/data/frontend/infra/test 与未指定 subagent 默认 Terra Medium；规则明确的机械批处理使用 Luna Medium；原子即时微改使用 Spark Medium。并发硬上限为 4，但默认单 Agent。项目配置不设置顶层 `model`、主线程 reasoning 或 plan-mode model，不覆盖对话页面的 Principal 模型选择，也不修改全局 Codex 配置。
- `pm_fast_worker` 精确使用 `gpt-5.3-codex-spark` + `medium`，仅路由通过 Small/Precise/Atomic/Reversible/Known-validation 全部条件的 micro task；`pm_luna_worker` 使用 `gpt-5.6-luna` + `medium` 处理确定性批量、转换、同步、提取与模板化任务。Spark 不是批处理省成本层，Luna 不处理歧义业务逻辑；两者不确定时回退 Terra Medium。
- 执行状态统一为 `PROVISIONAL → COMMITTED → EXECUTION_READY → EXECUTING → PASS → FROZEN`；Phase 0、Phase 1 与 P1-M1–M6 均已 FROZEN；未经新的 rolling-wave planning 和明确授权不得进入 P2。
- Terra 只能实现 Principal 已批准的架构；新架构决策必须停止并上报。计划外实现缺陷使用 `P1-M1-Rxx` 最小 Repair Task，架构变化不得包装成 Repair Task。
- OSS 复用原则为“复用通用基础设施，保留个性化智能”：重大第三方组件必须分别审查代码、模型/权重、数据与传递依赖许可证，并通过 Principal change control；Terra 只能报告候选，不得自行安装、下载权重或接受条款。
- Identity-Preserving Makeup Transfer 已提升为 P6 Hybrid Editor 的一级高优先级研究轨道和能力子系统，与 Deterministic、Geometry、Generative Editor 和 Agent Tool Layer 并列，不得降格为单一 `makeup_transfer()` 工具；其未来链路为 Reference Makeup Understanding → MakeupStyleRepresentation → StyleProfile personalization → Structured MakeupPlan → region execution → identity/geometry verification → user correction → PreferenceEvent。
- Stable-Makeup 是高优先级研究参考，生产采用需完整依赖许可证审查；FLUX-Makeup 具有高算法/评估价值，但其被报告的受限 foundation-model 依赖在权威复核和商业清除前使直接生产路径保持 `PRODUCTION_BLOCKED`。
- 当前 P1-M2 不因 OSS/Makeup 研究增补发生变化：不新增依赖、模型资产或未来 bounded tasks；P6 到达 rolling-wave planning 时再确定独立研究 Milestone 与 GO/NO-GO/FURTHER_RESEARCH Gate。
- P1-M2-T06 经 Principal change control 允许 `@playwright/test@1.62.1` 作为 pinned test-only dev dependency；npm 元数据与包内 LICENSE 均为 Apache-2.0，Node 要求 `>=20`，不得进入生产 runtime 或调用真实 Provider。完整记录见 `docs/security/PLAYWRIGHT_ADOPTION.md`。
- P7 的前向方向已升级为 `Visual Memory OS & Persistent Preference Learning`，状态保持 PROVISIONAL。用户确认的 Visual/Behavioral/Explicit Truth 是权威证据；AestheticProfile、图、向量/视觉索引、Memory Card 与 semantic/temporal/procedural views 均为可重建 materialized state。未保存的 AI 输出无长期权威，当前指令优先，删除必须传播到全部派生表示；不新增当前依赖、模型资产、schema、ADR 或 P7 tasks。完整方向见 `docs/architecture/VISUAL_MEMORY_OS.md`。
- P1-M3 采用 ADR-018：政策接受与用途 Consent 分离；grant/withdrawal 和 UploadIntentEvent append-only；浏览器 ingress 先进入 owner-bound quarantine UploadIntent，绝不直接成为 Asset/Original。只有 active 且持精确有效用途授权的用户可获得一次性短时 upload grant；complete 仅形成 `uploaded_unverified`，M4 才负责解码、重编码、EXIF 清理和 Original 晋升。Local write-only ingress 只用于非生产合成 fixture，生产真实上传继续 fail closed。
- P1-M4 采用 ADR-019：`complete` 保持 M3 的 `uploaded_unverified` 语义，另由显式 owner-bound ingestion Job 启动摄入；PostgreSQL Job 是权威，Celery/Local runner 只作 at-least-once Adapter。raw quarantine 永不成为 Asset；首版只接受单帧 JPEG/PNG/WebP，经 magic/decode/byte/边长/像素 Gate、EXIF orientation、metadata 清除、RGB/白底和版本化 canonical JPEG 重编码及二次解码后，才可在单一事务中创建一个 immutable Original Asset。Worker 在读取前和晋升前重复检查 active/Consent/TTL；固定输出 key、唯一 final evidence 和幂等 cleanup 处理重复 delivery 与对象/数据库双写故障。Pillow 只是 decoder 候选，必须先过独立供应链 Gate 和 Principal `THIRD_PARTY_APPROVED`。
- P1-M4-T02 经 Principal 供应链 Gate 批准 `pillow==12.3.0` 仅作为 strict JPEG/PNG/WebP decoder 与 canonical JPEG encoder。PyPI 与 Windows/Linux cp313 wheel SHA-256 一致，核心无必需 Python 传递依赖，顶层 MIT-CMU 与 bundled native notices 已检查，Windows 及无网络 Linux feature inventory 通过，隔离 path audit 无已知漏洞。应用必须显式 format allowlist、保留完整 notices、禁用 truncated input/外部工具/任意插件/网络，并维持生产 real-image fail closed；版本变化需重新审查。完整记录见 `docs/security/PILLOW_ADOPTION.md`。
- P1-M4 `CC-P1-M4-01` 冻结 pre-claim tombstone 语义：ingestion Job 创建后若 intent 在首次 claim 前被 M3 取消，Job 以 zero-attempt terminal `cancelled` 结束，不读取 quarantine bytes、不伪造 JobAttempt 或 AssetIngestionRecord；若撤回发生在 attempt 已开始后，仍完成为 rejected evidence。该 change control 只补足安全终止表达，不改变 promoted/rejected 摄入证据或生产 fail-closed。

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

- 2026-08-18：P2-M4-T05 首版 first-party dense map、canonical JPEG/RGB boundary、exact-hash native
  loader 与 OpenCV adapter 已通过 45 项 targeted tests、完整 API/Worker Ruff/mypy/pytest 和双平台
  private smoke；Windows 与合格 Linux builder 的 canonical result SHA-256 同为 `5f7868d5...`。
  但 accepted Linux runtime 需要 `GLIBC_2.38`/`CXXABI_1.3.15`，仓库实际 Debian 12 API 镜像只有
  glibc 2.36，标准镜像在处理 bytes 前正确 fail closed。Principal 通过 `CC-P2-M4-02` 只重开
  Debian 12-compatible Linux candidate identity；不得升级 base image 掩盖缺口，T05 尚未接受，
  T06 保持关闭。

- 2026-08-18：P2-M4 T04 acceptance checkpoint `c919e0b95cbea6cdfbe8fbcc47e1e58c1f2ec4c5`
  的 run `32126635267` 三 jobs 全绿；该 run 只确认 T04 acceptance 文档与既有冻结回归，不替代
  T05 adapter 或标准 Docker runtime compatibility Gate。

- 2026-08-18：`CC-P2-M4-02` 与 `P2-M4-R10` 关闭 T05 的 Debian 12 ABI 兼容缺口。首两个 V3
  root 虽位级一致但 OpenCV build-info 泄露 `/work/...`，已保留为 attempt evidence；R10 只改为
  固定 `/usr/src/...` 构建根。两个新 root 的五项 runtime 逐字节一致、private-path/network-symbol
  扫描为零，最高要求为 `GLIBC_2.35`/`GLIBCXX_3.4.30`/`CXXABI_1.3.13`。标准 API 镜像在
  `--network none` 下得到与 Windows 相同的 T05 输出 `5f7868d5...`；private SBOM `641a93ad...` 与
  Grype 0.117.0/database v6.1.9 零 matches。该结论只关闭 Linux runtime identity；T05 仍待完整
  tracked validation 和 Principal acceptance，T06 继续关闭。

- 2026-08-18：T05 candidate `75c0ccbaeab5ae4e1a8e66054f2225f701e221eb` 的 same-SHA run
  `32131383622` 三 jobs 全绿，七项预期 audit/frozen-regression/Docker/Gitleaks artifacts 均存在且
  未过期。Principal 在复核实际 diff、双根 runtime、标准镜像 smoke、SBOM/Grype、本地 full matrix
  与远端结果后接受 T05 及 R09/R10，并只开放 T06。P2-M4 仍为 EXECUTING；T07/T08 与 Milestone
  Gate 未完成。

- 2026-08-18：P2-M4-T05 acceptance checkpoint `2afc084d8dade07d28da3c3d68d87006d4a94f49`
  的 run `32131954633` 三 jobs 全绿；七项 exact-SHA audit/frozen-regression/Docker/Gitleaks
  artifacts 均存在且未过期。该 closure 只确认 T05 治理 checkpoint，T06 已开始执行，T07/T08 与
  P2-M4 Gate 仍未完成。

- 2026-08-18：T06 入口只读核验发现 `0012` 无法持久化并重建 `GeometryTransformRequest` 所需的
  immutable LandmarkWarpPlan；继续把 plan 放入 Job/message 或从任意 QA JSON 临时推导会破坏
  reference-only 与 provenance。Principal 通过 ADR-038 / `CC-P2-M4-03` 接受前向 1:1
  `landmark_warp_plans` authority，origin 仅为 `PREREGISTERED_M4_RESEARCH_PLAN`，不批准通用 facial
  plan generator。T06 在 `CC-P2-M4-03-A` 的 domain/ORM/`0013`/PostgreSQL Gate 被接受前保持 blocked。

- 2026-08-18：P2-M4-T04 tracked evidence `28e5ae8ab9350fe44fa1e14aa1ae9c15436717fa` 的 run
  `32125987000` 三 jobs 全绿；下载 artifact `9320466783` 精确绑定该 SHA、migration head `0012`、
  46 M3 tests/0 skip 与既有 private-synthetic boundaries。Principal 接受 T04 并只开放 T05；
  P2-M4 仍为 EXECUTING，T05–T08 与 Milestone Gate 未完成。

- 2026-08-18：P2-M4-T04 候选 `OPENCV_5_0_0_BOUNDED_TRANSITIVE_SOURCE_V2` 完成本地 Gate，Principal
  处置为 `APPROVED_FOR_PRIVATE_SYNTHETIC_M4`，但须待 tracked evidence 的 same-SHA CI 通过后才开放
  T05。exact OpenCV 5.0.0 source + R08 conditional no-PDB overlay 构建的实际闭包仅为
  `core,flann,geometry,imgproc`、bundled static zlib 1.3.2 与第一方 `ctypes-c-v1` wrapper；两个
  Linux `--network none` 和两个 Windows clean roots 均逐平台 byte-identical，跨平台 fixture
  pixels 完全一致，全部负向控制通过。Windows/Linux static network closure 为零，Windows
  process-specific outbound deny + WFP capture 为零 attempted egress。private CycloneDX SBOM 为
  `2345cba1...`，Grype 0.117.0 / DB v6.1.9 为零 matches。该批准不等于项目 binary/package、
  distribution、production、真人 facial processing 或 QuestionBank release 授权。

- 2026-08-18：P2-M4-T04 首个候选 `opencv-python-headless==5.0.0.93` 结论为
  `FURTHER_RESEARCH`。Exact OpenCV/NumPy artifacts 均匹配官方 SHA-256；两个 Windows 与两个
  Linux `--network none` 有效运行的 deterministic digest 均为 `5833e2cf...`，跨平台 256/1024
  输出像素差为零，负向控制、性能与体积 Gate 通过。R02 修复 NumPy 2.5 二维 `np.cross` harness
  兼容问题；R03 保留四个 noexec tmpfs import failure 后改用一次性容器层。完整 wheel 含 M4 不需要的
  FFmpeg/OpenSSL/codec closure，Windows FFmpeg DLL 导入 Winsock socket/connect；Grype native DB
  两次 TLS timeout，native vulnerability 为 NOT VERIFIED。因此不批准 T05 或项目 dependency，下一
  候选必须独立预注册 OpenCV 5.0.0 minimal source-built `core,imgproc` closure。

- 2026-08-18：P2-M4-T03 与 `P2-M4-R01` 经 Principal 验收。前向
  `0012_geometry_variant_authority` 建立 immutable `VariantSpecification`、monotonic
  `TransformRun`、canonical QA-passed source、distinct result Asset、唯一成功 lineage 与
  ADR-037 `CANONICAL_BASE | GEOMETRY_VARIANT` QA subject union；variant 不伪造 raw source 或
  `SyntheticAssetRecord`。Fresh/round-trip migration、Alembic zero drift、六项 PostgreSQL、完整
  API/Worker、Ruff、113-source strict mypy 与 contracts drift 通过。候选 CI 只因冻结 M3 evidence
  的 `0011` 与当前 repository head `0012` 被错误要求相等而失败；R01 保留两者独立 authority，
  修复 SHA `e36ec5073e9fa5b1750642ff676dc102191b2c3f` 的 run `32113760284` 三 jobs 全绿。
  T03/R01 已接受，P2-M4 仍 EXECUTING，下一步为 T04 isolated candidate PoC。

- 2026-08-18：P2-M4-T03 schema review 发现 M3 `SyntheticQARun` 强制绑定 raw-normalized `SyntheticAssetRecord`，不能合法表示无 raw source 的 geometry variant result。ADR-037 前向批准 `CANONICAL_BASE | GEOMETRY_VARIANT` QA subject union：既有 M3 row/语义不变；variant QARun 不伪造 raw record，而唯一反向绑定 output-stored `TransformRun` 并复用同一 QAPolicy/measurement/review/hard-gate authority。保留 `normalized_asset_id` 冻结列名作为共同 subject Asset reference，不建立第二套 measurement 表；仅限 private synthetic M4，不扩大真人、生产或 release 权限。

- 2026-08-18：P2-M4-T02 经 Principal 验收。新增纯领域 `VariantSpecification`、`TransformRunState`、source-relative ppm magnitude、determinism level 与 `require_researchable_dimension`；只允许 READY/EXPERIMENTAL 进入 M4 研究，unknown/UNSUPPORTED/REQUIRES_3D/STYLE_ONLY fail closed，且 M4 不提升 dimension READY。60 个 targeted tests、全 API Ruff（153 files）、strict mypy（100 sources）与 contracts drift 通过；无 ORM/migration、算法/图片依赖、模型、网络、public API 或真人 fixture。Candidate `c173a46e43312c93b73c11462ee1adb115328fb2` 的 run `32110263179` 三 jobs 全绿。P2-M4 进入 EXECUTING，T03/T04 ready。

- 2026-08-18：P2-M4 rolling-wave refinement 已由 Principal 接受。ADR-036 冻结 source-relative `VariantSpecification`、append-only `TransformRun`、新 immutable variant Asset、第一方 `GeometryTransform` port、determinism 分级和 M5 isolation 分界；M4 研究只允许 `EXPERIMENTAL`/`READY` dimension，且 M4 不能单独把 dimension 提升为 READY。M3 的 OpenCV 3.4.11 closure 不构成 M4 采用；M4 candidate 必须重新完成 exact-version、license/SBOM/vulnerability、Windows/Linux/Docker、zero-network、determinism 与 replacement-cost Gate。P2-M4 状态为 EXECUTION_READY，M5 entry 继续关闭。

- 2026-08-16：落实项目级多 Agent 成本/能力路由升级：默认与普通实现角色从 Terra High 调整为 Terra Medium，保留安全审查 Terra High 与规划/最终 Gate Sol High，新增 `pm_terra_high_worker` 困难实现层、`pm_luna_worker` 机械批处理层并保留 `pm_fast_worker` Spark 原子微改层；`.codex/config.toml` 只约束 subagents 与 4 线程硬上限，明确不设置 Principal 模型或 reasoning，保留对话页面自由选模能力，且不修改全局 Codex 配置。
- 2026-08-16：Phase 2 rolling-wave plan 及 consolidated planning amendment 已接受；Phase 2 Milestones 为 COMMITTED，P2-M1 为 EXECUTING。T01 只编码 Principal 已批准决定；Principal 通过 `P2-M1-PR1`，并以 `P2-M1-R01` 修正四个 `0008` 实体精确名称、GenerationItem/Variant 生命周期和 unresolved isolation hard-gate 文档保真缺陷，现已解锁 T02–T05。M1 authority content/version/digest 自创建起 immutable，approval state 只允许 terminal `DRAFT → APPROVED`，修订必须新建版本。migration 文件保持 `0008_synthetic_dataset_foundation.py`，revision ID 使用 32 字符以内的 `0008_synth_dataset_foundation`，不修改历史 migration 或 Alembic 版本表。P2 仅建设 synthetic-only、可追溯的成年合成人物数据集引擎；`SyntheticIdentity` 为 bank-independent authority，raw Provider output、normalized Asset、variant 与 released manifest entry 分层且不可互相覆盖。P2-MVR-v1 的 4 dimensions / 3 regions / N=24 只是技术可行性研究下限，须按证据在 24→48→96 cohort 升级，不能当作科学充分性或产品 invariant。Pillow 12.3.0 批准扩展至后续 P2 normalization；MediaPipe/OpenCV/imagededup 分别保持 LICENSE_REVIEW_REQUIRED/POC_REQUIRED/REJECT。MediaPipe 的 `v0.10.35` 是指定 candidate snapshot；上游 latest 的 `v1.0.0` notes 报告内部 `0.10.36`，后续 PoC 必须分别审查 source tag、runtime 与 artifact/terms。

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
- 2026-08-16：P1-M3 acceptance closure `05c9f00d88d3b647060ef60012c284d710252bb3` 的远端 run `31897780247` 三个 jobs 全绿，并生成 `project-audit-evidence`、`project-docker-evidence` 与零结果 Gitleaks SARIF；Principal 将 P1-M3 前向更新为 FROZEN，下一步只对 P1-M4 做 rolling-wave refinement。
- 2026-08-16：P1-M3 最终冻结状态提交 `f6da0101aa7ac87479380b1dae9b4f0361a6b406` 的 run `31898073537` 三个 jobs 全绿，并产出三项未过期 artifacts；从该 SHA 创建 `codex/phase1-m4-safe-ingestion`。P1-M4 rolling-wave refinement 通过 ADR-019 与执行协议冻结显式 Job、decoder/sanitizer、双重授权检查、幂等晋升、crash recovery、quarantine/orphan cleanup 与 M5 边界；实现前先执行 decoder 供应链 Gate。
- 2026-08-16：P1-M4-T03/T04 经 Principal 本地验收。前向 `0004_safe_image_ingestion` 以复合 owner FK、唯一约束、状态检查和 deferred/append-only trigger 固化 one intent/one Job/one final record、lease/attempt、promoted/rejected shape 与最长 24 小时 quarantine retention；真实 PostgreSQL migration/invariant suite 22 PASS，`alembic check` 零漂移。ObjectStorageProvider 新增 bounded quarantine stream 与 canonical sanitized object 原子 create-if-absent/inspect/delete；`image-sanitizer-v1` 对 synthetic/non-face JPEG/PNG/WebP 执行 magic/MIME/decoder 一致性、单帧/大小/像素 Gate、EXIF orientation、metadata/ICC 丢弃、白底 alpha、deterministic JPEG 和二次解码验证。定向 53 项、全 API Ruff 与 strict mypy 通过；现有 M3 complete 写入 retention deadline 的兼容接入明确归入 T05。
- 2026-08-16：P1-M4-T05 经 Principal 本地验收。R01–R04 分别补强 promoted Asset 分类/metadata 防改写、Job↔current JobAttempt commit-time 一致性、provider-neutral sanitized-object conflict 分类及 terminal-cancelled 重复 claim 幂等；`CC-P1-M4-01` 解决 Job 创建后首次 claim 前 intent tombstone 的 zero-attempt cancelled 语义。Ingestion application 现覆盖 owner/Consent/TTL 双重重检、并发 one Job、用户域幂等、lease/stale reclaim、deterministic reject vs transient retry、sanitized create-if-absent、单事务 one Original/evidence/event/audit、pre/in-flight withdrawal、reconcile 与对象先写/DB commit fault recovery；M3 complete 同事务写入 1 小时默认、24 小时上限 retention deadline。Principal 独立 fresh PostgreSQL 39 PASS，Ruff 与 47 source strict mypy PASS；未进入 HTTP/Celery，真实图片/Provider 仍关闭。
- 2026-08-16：P1-M4-T06 经 Principal 本地验收。新增独立 reference-only `ingestion-task-v1` 消息（仅 `job_id/request_id/schema_version`）、Celery ingestion/maintenance 专用队列、late ack、worker-lost retry、有界 backoff、LocalTaskRunner、PostgreSQL pending/stale reconciler，以及 terminal quarantine/sanitized orphan 和无 Job retention-expired cleanup；API/Worker 通过同一私有 Compose volume 共享 Local storage。真实 Linux Worker 注册/队列/Redis round-trip 与 PostgreSQL cleanup suite 14 PASS，宿主非集成单元 10 PASS，Ruff 与 56 source strict mypy PASS；测试发现并修正无 Job retention tombstone 必须使用冻结的 `expired/expired_at` 语义，未修改 migration、HTTP 或 OpenAPI。
- 2026-08-16：P1-M4-T07 经 Principal 本地验收。R05 将 `ingestion-task-v1` 从 Worker 私有模块前移为 API/domain shared contract，关闭 API 反向依赖 Worker 或双写消息 schema 的集成缺陷；API 新增 `POST /api/v1/assets/upload-intents/{intent_id}/ingestion-jobs` 与 owner-bound `GET /api/v1/jobs/{job_id}`，只返回 job/status/result_code/asset_id/finalized_at。新 Job 通过 Celery reference-only dispatcher 投递；broker 故障保持 PostgreSQL pending 并由 reconciler 恢复，development pending dispatcher 不伪造完成。定向 HTTP/dispatch 5 PASS、真实 Compose PostgreSQL/Redis 完整 API 产品回归通过，OpenAPI→generated TypeScript 零漂移、contracts typecheck/Vitest PASS；已知 API 镜像缺少仓库级 contract fixture 将以独立 Repair 在 T08 前收口。
- 2026-08-16：P1-M4-R06 关闭 T08 Gate 前置缺陷。API/Worker 镜像显式复制权威 `packages/contracts/openapi.json`，CI Celery 启动显式监听 default/ingestion/maintenance 三队列并在 Docker job 运行完整 Worker suite；对 7 个既有 Python 文件仅执行 Ruff 机械格式化，不改变 migration 或领域语义。重建后的 Worker 容器对完整 API+Worker suite 在真实 PostgreSQL/Redis/Celery 上零 skip 全绿，93 文件 Ruff format、lint、61 source strict mypy、Prettier 与 Compose model 均 PASS。
- 2026-08-16：P1-M4-R07/R08 关闭远端 secret-scan 的历史 fixture 误报。R07 将当前测试中的旧协调器幂等测试值改为等价的确定性非凭据值；因 CI 使用 `fetch-depth: 0`，旧提交 `192610b` 仍会被完整历史扫描命中，R08 因此新增同时锁定 exact commit、exact path 与 exact match 的最窄 allowlist，并显式 `extend.useDefault = true` 保留 Gitleaks 默认规则。Gitleaks 8.28.0 对 44 个 commits 和精确 index 快照均无泄漏；同一模式置于其他路径的负向控制仍被 `generic-api-key` 拦截，证明未放宽当前或无关扫描。
- 2026-08-16：P1-M4 candidate `b28f0e6b547df94ded12ce6323efb06ae269a11e` 经 Principal Gate PASS。远端 run `31903655766` 的 `quality-and-integration`、`secret-scan`、`docker-validation` 全绿，PostgreSQL migration、Redis/Celery、完整 Python/TypeScript、浏览器、契约、供应链、Docker 和 Gitleaks 均实际执行，三项 artifacts 存在且未过期；P1-M4 当前为 PASS，等待 acceptance closure CI 后才能 FROZEN。
- 2026-08-16：P1-M4 acceptance closure `fd910f203a61a6aea2f2fa6fb9412216ddd0aa05` 的远端 run `31903994976` 三个 jobs 全绿，并生成 `project-audit-evidence`、`project-docker-evidence` 与零结果 Gitleaks SARIF；Principal 将 P1-M4 前向更新为 FROZEN，下一步只允许对 P1-M5 做 rolling-wave refinement，不在本次冻结提交中进入 M5。
- 2026-08-16：P1-M4 最终冻结状态提交 `79f50bdcf2192a7df4a511de82fcb221d194a6da` 的 run `31904693236` 三个 jobs 全绿，并产出三项未过期 artifacts；从该 SHA 创建 `codex/phase1-m5-data-rights`。P1-M5 rolling-wave refinement 通过 ADR-020 与执行协议冻结 owner-bound 私有下载、立即访问 tombstone、异步物理删除证据、短期私有导出、账户冻结/session revoke 与当前 Phase 1 删除传播；仍只允许合成非人脸 fixture，生产真实图片访问保持 fail closed。
- 2026-08-16：P1-M5-T02 经 Principal 本地验收。前向 `0005_data_rights_lifecycle` 新增 owner-bound Asset 删除、数据导出、账户删除 request/event 与物理对象删除证据；deferred trigger 强制 Asset tombstone 和账户立即冻结，request authority 不可改写/删除且状态只能单向推进，事件、访问审计和物理删除证据 append-only。真实 PostgreSQL `0001→…→0005→0004→0005`、5 项 migration、23 项 invariant 与 `alembic check` 零漂移通过；Ruff、strict mypy 和 diff check 全绿，隔离测试库均已删除，尚未进入 T03 私有下载实现。
- 2026-08-16：P1-M5-T03 经 Principal 本地验收。ObjectStorageProvider 新增 exact-key 私有下载 grant；Local Adapter 仅允许 loopback synthetic/non-face sanitized object，使用 CSPRNG handle + 独立 HMAC proof、一次性/短时兑换、路径与 symlink 防护，并在访问日志前同时清除 upload/download handle。Asset access application 的 list/detail/grant/redeem 查询把 active owner 与未删除状态写入 SQL predicate；授权和兑换均核对不可变 Asset 与存储对象 MIME/size/SHA-256，删除后的既有 grant 在 streaming 前失效，grant 创建/兑换写入 append-only audit 且不记录 URL、token、key 或 bytes。Tencent COS download 仍显式 fail closed；47 项存储/Provider/config 定向、16 项 access/revocation、完整 API regression、Ruff 与 strict mypy 通过，仅使用合成非人脸 bytes，T06 之前不暴露公共 Asset API。
- 2026-08-16：P1-M5-R01/T04 经 Principal 本地验收。R01 以前向 `0006_deletion_evidence_targets` 将物理删除证据扩展为 authority + owner-bound target，支持根 Asset 与任意深度派生 Asset 各自追加证据，并由 PostgreSQL 拒绝未 tombstone、跨 owner 或 dependency graph 外目标；`0006→0005→0006` 与 Alembic drift 通过。T04 实现同事务依赖 DAG tombstone、reference-only `asset-deletion-task-v1`、Celery maintenance queue/LocalTaskRunner、broker outage reconciler、children-first 对象删除、逐目标幂等 evidence、transient retry、missing-object 稳定成功和完整证据后才完成；处理期新发现的依赖先补 tombstone 再删除。最终隔离 PostgreSQL T04/migration/invariant 33 PASS、完整 API 187 PASS、Worker 16 PASS、Ruff 111 files、strict mypy 73 source files、五服务健康及真实 Redis/Celery roundtrip 均通过，仅使用合成非人脸 fixture。
- 2026-08-16：P1-M5-R02 与 `CC-P1-M5-01` 经 Principal 接受。前向 `0007_account_quarantine_evidence` 为账户删除增加 owner-bound UploadIntent quarantine 物理删除证据，且只允许 terminal intent、匹配 owner 与 account-deletion authority；不修改 `0001`–`0006`。账户删除必须等待冻结前签发的 upload grant 到期，再执行 post-expiry 幂等删除并记录证据，防止旧 grant 在“已删除”后发布对象。真实 PostgreSQL `0007→0006→0007`、29 项 migration/invariant 与 Alembic drift 通过；首次失败仅为测试 SHA-256 fixture 使用非十六进制字符，修正 fixture 后全绿。
- 2026-08-16：P1-M5-T05 经 Principal 本地验收。确定性私有 ZIP 仅导出 account、精确政策接受、用途 Consent 与已清洗 synthetic Asset，固定路径/顺序/时间戳并校验 MIME/size/SHA-256，明确排除认证材料、raw quarantine、内部风险/审计、prompt 和其他用户；短期 exact-key archive 具备 owner-bound 下载、到期清理与物理删除证据。账户删除 admission 在单事务内冻结 User 并撤销全部 session，随后追加 Consent withdrawal、取消 pending upload/ingestion、tombstone Asset、清理全部 export/quarantine，并在 grant-expiry barrier 与逐目标证据齐全后去关联 phone hash、标记 deleted。`R03` 将 export publication + ready commit 放入与账户删除共用的 User 行锁窗口，并统一 User→Job/Export 锁顺序，关闭已写对象晚于删除完成发布的 orphan race 与反向锁死风险；deterministic key 使对象已写而 DB commit 失败时仍可由账户删除恢复。隔离 PostgreSQL 完整 API 198 PASS、Worker 16 PASS + Linux Celery/Redis roundtrip 2 PASS、`0007→0006→0007` 与 Alembic drift、128-file Ruff、85-source strict mypy、52 Web tests、契约零漂移、Next production build及五服务/Celery health 均通过；仅使用合成非人脸 fixture，公共 HTTP/UI 仍留给 T06/T07。
- 2026-08-16：P1-M5-T06 经 Principal 本地验收。ADR-020 的 Asset list/detail/download grant/delete、data-export create/status/download grant、account-deletion create/current 九个 `/api/v1` 操作已接入真实 application/coordinator，严格 response schema 不暴露 object key、hash、Provider payload 或内部 evidence；Local synthetic export 使用独立隐藏下载路由，运行时 OpenAPI 不暴露 `_local` Adapter。OpenAPI→generated TypeScript 已同步，旧 M3“Assets 路由尚不存在”断言已按阶段前向更新。`CC-P1-M5-02` 关闭账户删除立即撤销 session 后 current-status 端点不可达的问题：普通 auth/refresh 仍拒绝被撤销 family，仅该只读端点可在原 access JWT 未过期、revocation reason 为 `account_deletion` 且用户已进入 deletion 状态时读取最小状态，不恢复 session 或授权其他资源。隔离 PostgreSQL 定向 6 PASS、完整 API 204 PASS、131-file Ruff、86-source strict mypy、完整 `pnpm check`（52 Web tests、contracts、Next build）及五服务健康通过；仅使用合成非人脸 fixture。
- 2026-08-16：P1-M5-T07 经 Principal 本地验收。`/account` 现通过生成客户端提供 owner-bound Asset 列表/详情/瞬时下载/删除、真实异步数据导出状态与短期 ZIP 下载，以及输入固定确认短语后的账户删除状态页；access JWT 仍只驻留 `BrowserAuthSession` 内存，download grant URL/headers 只在客户端 Adapter 内瞬时兑换，不进入组件状态、URL、analytics、localStorage 或 sessionStorage。账户删除提交后普通内容立即隐藏，保留原 5 分钟 JWT 仅轮询 `CC-P1-M5-02` 只读端点，不 refresh 已撤销 family，并在完成或 4 分钟窗口结束后清除本地会话。确定性 Fake API 与 Playwright 覆盖资产读取失败重试、详情、下载、删除、export requested→processing→ready→download、二次确认、删除状态完成及存储零敏感值；`pnpm check`、54 Web tests、5 Edge E2E、Next build、Web 镜像重建、五服务 health 与 `/account` HTTP 200 全绿，仅使用 synthetic/non-face fixture。
- 2026-08-16：P1-M5 candidate `6d46b4be2368870252905b472915e5a5b1f7cd1a` 经 Principal Gate PASS。远端 run `31921199397` 的 `quality-and-integration`、`secret-scan`、`docker-validation` 全绿，PostgreSQL migration、Redis/Celery、完整 Python/TypeScript、5 项浏览器流程、契约、供应链、Docker 和 Gitleaks 均实际执行；三项 artifacts 已下载核验，Compose/Celery 证据可读且 Gitleaks SARIF 为零结果。P1-M5 当前为 PASS，等待 acceptance closure CI 后才能 FROZEN，不得进入 P1-M6。
- 2026-08-16：P1-M5 acceptance closure `ccbd136a42e7d3a702acd2050265ba0e8a211d3e` 的远端 run `31921591091` 三个 jobs 全绿，并生成可读的 `project-audit-evidence`、`project-docker-evidence` 与零结果 Gitleaks SARIF；Principal 将 P1-M5 前向更新为 FROZEN。下一步只允许对 P1-M6 Application Foundation Integration Gate 做 rolling-wave refinement，不在本次冻结提交中进入 M6 实现。
- 2026-08-16：P1-M5 最终冻结状态提交 `d8c39ae95829e6401cc4379656f210362352e717` 的远端 run `31921975223` 三个 jobs 全绿，并产出未过期的 `project-audit-evidence`（`9256671007`）、`project-docker-evidence`（`9256643152`）与 Gitleaks SARIF（`9256614646`）；从该 SHA 创建 `codex/phase1-m6-integration-gate`。
- 2026-08-16：P1-M6 rolling-wave refinement 冻结为只做 Phase 1 集成验收：统一证据矩阵、跨 M1–M5 合成非人脸垂直生命周期与恢复演练、标准库结构化 operational events/脱敏、机器可读 CI 证据、同一 SHA candidate Gate、acceptance closure 与 Phase 1 freeze；不新增 migration、产品 API、第三方依赖、真实数据/Provider、部署或 P2 实现。
- 2026-08-16：P1-M6-T02/T03/T04 经 Principal 本地验收。隔离 PostgreSQL/Redis 垂直测试贯通邀请认证、年龄/政策激活、刷新、用途 Consent、synthetic/non-face PNG quarantine、safe ingestion、私有下载、数据导出、Asset 删除与账户删除，并实证旧 upload grant expiry barrier、幂等重试、session revoke、访问拒绝和敏感数据不落审计；完整 API/Worker 在独立 Celery 上零 skip 全绿。标准库 `OperationalEvent` 只接受固定字段，HTTP 仅记录 route template/status/duration/request correlation，异步 dispatch 仅记录 operation/job/request/outcome，本地 grant handle 不进入日志；生产 collector/alert 仍明确 `NOT_DEPLOYED`。CI 新增 fail-closed `mirror.phase1.ci-evidence/v1`，绑定完整 commit SHA、真实唯一 Alembic head `0007_account_quarantine_evidence`、OpenAPI SHA-256 与指定垂直测试的零 failure/error/skip JUnit 摘要，不上传原始 JUnit、环境或业务数据。P1-M6 仍为 EXECUTING，等待 T05 同一 candidate SHA 的完整远端 Gate。
- 2026-08-16：P1-M6 candidate `ed24b3d856e22bc1d0779a9eace254200041fb81` 经 Principal Gate PASS。远端 run `31924258547` 的 `quality-and-integration`、`secret-scan`、`docker-validation` 全绿，新增 Phase 1 vertical/recovery 与 machine-readable evidence steps 实际执行；四项 artifacts 可读且未过期，其中 `phase1-ci-evidence`（`9257370449`）精确绑定 candidate SHA、`0007_account_quarantine_evidence`、OpenAPI LF-byte SHA-256 和一项零 failure/error/skip 垂直测试，Gitleaks SARIF 为零结果。P1-M6 当前为 PASS，等待 acceptance closure CI 后才能与 Phase 1 一起 FROZEN；不得进入 P2。
- 2026-08-16：P1-M6 acceptance closure `cc926ceb49c7978cb7b57df778ec2f1c7f4cc878` 的远端 run `31924651458` 三个 jobs 全绿；四项 artifacts 可读且未过期，其中 `phase1-ci-evidence`（`9257491150`）精确绑定 closure SHA、`0007_account_quarantine_evidence`、OpenAPI LF-byte SHA-256 `a9ee1e0ad3b942e5be5790b4fc7ff8c0deab744a84d3383a7a8856a8f97b4841` 和一项零 failure/error/skip 垂直测试，Gitleaks SARIF（`9257448027`）为零结果。Principal 将 P1-M6 与 Phase 1 前向更新为 FROZEN；不得进入 P2。
- 2026-08-16：Phase 1 freeze-state run `31925010676` 的 secret-scan 与 Docker 全绿，但 Web onboarding 可访问性测试在 Linux CI 中于 React `useEffect` 聚焦完成前立即断言 focus，形成一次非确定性失败。`P1-M6-R01` 仅将断言改为 Testing Library bounded `waitFor` 等待既有 focus postcondition，不改生产代码、超时、可访问性语义或 Gate；修复提交必须重新通过完整远端 CI。
- 2026-08-16：P2-M1-T04 将合成 generation、Vision 与 internal synthetic storage 收敛为第一方 typed ports：请求和 payload 只接受 bounded synthetic bytes 与 opaque first-party references，结果固定携带 safety/cost/provenance facts，未知 retention、URL、user asset 与非 synthetic subject 均 fail closed。Mock 固定 bytes/metadata/cost/safety 且零网络；Tencent synthetic candidates fail closed；`internal-synthetic/v1` 与 user quarantine/sanitized/export 命名空间隔离；production 额外拒绝 mock synthetic storage provider。
- 2026-08-16：P2-M1-R03 补齐 generation contract fidelity：请求明确 output media type/width/height/max bytes、有限 scalar parameter tuple、optional bounded seed 与 pricing-snapshot budget；结果记录 provider-actual seed/parameters、model-version provenance 与 BIT_EXACT/SEED_REPLAYABLE/PROVENANCE_ONLY。Mock 仅声明真实支持的 1x1 grayscale non-human PNG、无 seed/parameter 支持与 BIT_EXACT，避免 MIME 或成人安全 metadata 误述。
- 2026-08-16：P2-M1-T06 经 Principal 本地验收。新增 checksum-bound 的 `mirror.p2-m1.fixture-manifest/v1`，只接纳带来源、许可、分类与 SHA-256 的 JSON 数值非人类 fixture；独立安全测试覆盖 `0008` schema guards、authority/domain digest、typed Provider zero-network、production fail-closed、OpenAPI 不变，以及依赖、模型、真人图片、URL、Prompt、secret、SDK import 和敏感日志路径负向扫描。Principal 重跑 74 项组合测试、140-file Ruff、89-source strict mypy、契约和格式检查全绿；Docker 隔离 PostgreSQL 证据为 97 PASS / 0 skip，临时库在零连接确认后删除。未新增依赖、模型、真人素材或外部调用。
- 2026-08-16：P2-M1-T07 本地 Gate PASS，远端 same-SHA Gate 待 Principal commit/push。CI 保留 Phase 1 evidence 并新增 `mirror.p2-m1.ci-evidence/v1`：只包含完整候选 SHA、唯一 migration head `0008_synth_dataset_foundation`、OpenAPI SHA-256、M1 JUnit 零 failure/error/skip 汇总和五类 synthetic/security boundary aggregate，不上传原始 JUnit、路径、Prompt、对象 key、图片、Provider payload、环境值或 DB rows。R04 仅为 Worker production Settings 测试夹具显式补 `synthetic_storage_provider=disabled`，避免 CI 的 mock 环境覆盖使测试在到达既有 LocalTaskRunner 生产拒绝断言前失败；不改生产 fail-closed。最终本地证据为 Ruff 142 files、strict mypy 90 sources、API 275、Worker 19、P2 evidence 87、隔离 PostgreSQL fresh→0007→0008→0007→0008 与 drift、完整 pnpm/Docker/供应链及 Gitleaks 8.28.0 candidate snapshot + 63 commits 全绿；两座隔离测试库在零连接核验后删除。
- 2026-08-16：P2-M1 candidate `6d9d97f3aa7f0aba5b7a3ea3f7eaf1c2a15a5440` 的 run `31929764395` 中 secret-scan、Docker 及 quality 的代码、迁移、Python、P2 boundary、TypeScript、浏览器和契约步骤均通过，但冻结时代的 Phase 1 evidence 调用仍要求当前唯一 head 为 `0007_account_quarantine_evidence`，在合法前向 `0008_synth_dataset_foundation` 后必然失败。`P2-M1-R05` 只更新该 current-head expectation；Phase 1 vertical JUnit、OpenAPI digest、完整 SHA 和零 skip 要求不变，不伪造旧 head 或弱化回归 Gate。
- 2026-08-16：`P2-M1-R06` 经 Principal 接受。R05 candidate `f2fec9ece18c54f3952cc877ad18d2b70ec54e32` 的 run `31930089028` 在完整 Python suite 暴露既有 Asset 删除并发死锁：evidence insert 的 PostgreSQL trigger 先锁 Asset，而完成事务先锁 deletion request 再更新 Asset。R06 统一为 evidence transaction 先按 request+owner `FOR UPDATE` 锁定 `AssetDeletionRequest`，再插入 append-only evidence 并由原 trigger 校验 Asset；missing/owner mismatch 在插入前 fail closed，不改 migration、trigger、状态机或删除语义。Agent 在真实 PostgreSQL 上并发 20/20、Asset deletion 6/6、fresh PostgreSQL/Redis 完整 API 零 skip通过；Principal 独立隔离 Compose 复验 6/6，Ruff、strict mypy 与 diff check 全绿。等待 R06 same-SHA 三 job 远端 Gate。
- 2026-08-16：P2-M1 candidate `a901337ca8e0ef1fc93e64638ef72abb56bc1d28` 的 run `31930761620` 三个 jobs 全绿且 same-SHA artifacts 可读，但独立 T08 仍发现两个 mandatory authority 缺陷。`P2-M1-R07` 以前向 `0008` PostgreSQL check + ORM guard 强制所有新 `SyntheticIdentity` 永远 bank-independent，并使四类 authority 的 `id`/`created_at` 与 content/version/digest 同样不可变；`P2-M1-R08` 使 `CanonicalPolicy` 的正常直接构造统一校验 kind、version、canonical object JSON 与 digest envelope。Principal 独立复验 domain 32 PASS、真实隔离 PostgreSQL migration/invariant 10 PASS、Ruff、strict mypy 和 diff check；仍需新 repair SHA 的完整远端 Gate 后才能冻结 M1。
- 2026-08-16：接受 P2–P7 benchmark-gated 前向治理增补，不改变 P1 frozen implementation 或当前 P2-M1 Gate。高影响算法、Provider、Agent runtime、Tool、编辑和视觉记忆候选统一遵循 `Candidate → isolated PoC → MirrorBench → ablation → license/privacy/security/cost review → ADR → APPROVED`；第三方只能作为 Adapter/Provider/baseline/reference，不能成为 Mirror domain authority。P3–P7 保持 PROVISIONAL，future PoC backlog 不等于执行授权；本次未新增 dependency 或 model artifact。
- 2026-08-16：P3–P7 research governance 在 P2-M2 T05 稳定提交后经 Principal 重新采集 manifest 并接受。P3–P7 maturity 统一保持 `DIRECTIONAL`；任何 PoC 必须预注册 baseline commit、versioned data/split/provenance/privacy、negative control、ablation、预算、stop/failure/rollback、reproduction command、seed、owner 和 result status，缺失字段为 `NOT_PRE_REGISTERED_BLOCKING`。外部论文、README、模型卡和用户报告必须严格区分 `UPSTREAM_CLAIM`/`UNVERIFIED` 与绑定 Project Mirror artifact 的 `PROJECT_MIRROR_REPRODUCED`；研究路线不改变当前 P2-M2 Gate，也未新增 dependency、model artifact、真人图片、公共 API 或 ADR。
- 2026-08-16：通过 `CC-P2-09` 与 ADR-024 接受 China-first synthetic coverage 前向决定。首个 internal pack 以 `CN_MAINLAND` market scope 和候选 `CN_EAST_ASIAN_PRESENTATION_V1` synthetic presentation scope 服务中国大陆，但底层 coverage/QuestionBank matching 仍以连续 morphology cells、reliability、uncertainty 和 Local Morphological Neighborhood 为主；presentation scope 不能成为真实用户 race/ethnicity/ancestry/nationality 推断或路由。`SyntheticCoveragePack`、`MorphologyCoverageCell`、`StyleContextPack` 在 M1 只冻结治理合同，不新增表/API，后续 rolling-wave 决定持久化。网络研究默认只提取抽象 descriptors；真人 reference 默认禁止用于 dataset generation，未来 restricted path 必须单独证明 copyright、adult model/portrait release、AI/derivative/commercial/storage/retention/territory/revocation rights 并通过 likeness/legal/privacy/security Gate。本次无 dependency、model artifact 或真人图片，DAG 与 `0008` 不变。
- 2026-08-16：P2-M1 repair candidate `9f3ca343223478f60a8eb0aed1b6d2342235f497` 经 Principal Gate PASS。远端 run `31932052115` 的 `quality-and-integration`、`secret-scan`、`docker-validation` 全绿；P2 artifact `9259615693` 精确绑定 candidate SHA、`0008_synth_dataset_foundation`、OpenAPI digest `a9ee1e0ad3b942e5be5790b4fc7ff8c0deab744a84d3383a7a8856a8f97b4841`、94 tests 零 failure/error/skip 与五类 boundary PASS，Phase 1 evidence `9259615509` 同 SHA，Docker evidence `9259595719` 可读，audit artifact `9259618402` 存在，Gitleaks artifact `9259575389` 为零 SARIF results。R07/R08 与 T08 最终接受，P2-M1 前向进入 PASS；只有 acceptance closure CI 全绿后才能 FROZEN。
- 2026-08-16：P2-M1 acceptance closure `27cede889f0e3cfd875b022b25af3d62165616f1` 的远端 run `31932349425` 三个 jobs 全绿。P2 evidence artifact `9259697255` 精确绑定 closure SHA、`0008_synth_dataset_foundation`、既定 OpenAPI digest、94 tests 零 failure/error/skip 与五类 boundary PASS；Phase 1 evidence `9259697020` 同 SHA，Docker evidence `9259677272` 可读，audit artifact `9259700154` 存在，Gitleaks artifact `9259654997` 为一项 SARIF run、零 results。Principal 将 P2-M1 前向更新为 FROZEN；下一步只能先对 P2-M2 做 rolling-wave refinement，不得直接进入 P3 或把未批准 Provider/模型引入 runtime。
- 2026-08-16：P2-M1 freeze-state `4a69f93f0d092afa0b520bbfb6e7d192e0f3dff1` 的 run `31932688424` 三个 jobs 全绿；P2 evidence `9259790978` 绑定 exact SHA、`0008`、既定 OpenAPI digest、94 tests 零 failure/error/skip 与五类 boundary PASS，Phase 1 evidence `9259790718` 同 SHA，Docker `9259768902`、audit `9259793616` 可读，Gitleaks `9259747842` 为零 results。P2-M1 完整 FROZEN，并从该 SHA 创建 `codex/phase2-m2-generation-pipeline`。
- 2026-08-16：P2-M2 rolling-wave refinement 通过 ADR-025 冻结 batch/item/budget/raw evidence 权威。M2 item 新增 `GENERATION_FAILED` 与 `CANCELLED` 终态，不能冒充 M3 QA `REJECTED`；Prompt 只在 leased Worker 内按引用解析为 bounded/redacted/不可序列化的短生命周期材料；raw metadata 永久不可变，物理清理追加 deletion evidence。Job/Attempt 只作执行 envelope，预算/dispatch 由 PostgreSQL batch row lock 保证，task reference-only，默认 CI Mock/zero-network。计划 migration 为 `0009_generation_batch_pipeline`，无公开 API、新 dependency/model/真实图片或 live call；真实候选 Provider benchmark 仍是 M2 PASS/FROZEN 的外部 Gate。
- 2026-08-16：P2-M2-T02 经 Principal 本地验收。前向 `0009_generation_batch_pipeline` 建立 GenerationBatch/Item、raw source、generation evidence、Provider cost 与 raw deletion evidence 六类权威；PostgreSQL 强制 approved policy/prompt admission、完整 item set 才能 queue、终态 aggregate 一致、`RAW_STORED` 必须绑定同一成功 JobAttempt 的 source/evidence/cost 链、batch 行锁预算与并发 cost ceiling、opaque storage reference、operator actor attribution 及全部 evidence append-only。真实隔离 PostgreSQL 完成 fresh upgrade、`0008→0009→0008→0009`、Alembic 零 drift、14 项 migration/invariant/concurrency 测试和带数据 downgrade fail-closed；Ruff、strict mypy、diff check 全绿。未新增依赖、模型、真人图片、Provider 调用或公共 API，T03 application service 已解锁。
- 2026-08-16：P2-M2-T03 经 Principal 本地验收。typed application/repository service 完成 batch 并发幂等创建、精确 Job/item、queue/status/cancel、并发 reservation、retry/remaining-budget、safe failure、cost 幂等和 atomic raw source/evidence/cost completion；Prompt 仅在匹配未过期 JobAttempt lease 时可物化，value object 有界、表示脱敏且不可序列化。`P2-M2-R01` 统一 evidence/cost 与应用事务锁顺序为 batch→item，并以真实 PostgreSQL 阻塞写者回归证明终态事务无反向死锁；`P2-M2-R02` 保真接受 Provider 已批准的 hyphen/underscore safety reason code。Ruff、strict mypy、19 项 migration/invariant/concurrency/service 测试与 Alembic 零 drift 全绿；无 dependency、model、真人图片、live call 或 public API，T04 raw storage 已解锁。
- 2026-08-16：P2-M2-T04 经 Principal 本地验收。synthetic raw storage port 增加 immutable create-if-absent、inspect、stream 与 exact-reference delete；Local development/test adapter 只在 `internal-synthetic/v1/raw` 中以单向 digest 映射 opaque reference，使用 atomic object directory，拒绝 traversal、symlink、unexpected member、metadata/size/checksum tamper 与 conflict，Mock 保持 deterministic/zero-network，Tencent candidate 继续 fail closed。TTL cleanup 保留 source authority 并追加唯一 deletion evidence，delete-before-commit 以 `not_found` 重试恢复；orphan cleanup 仅允许匹配的 failed/quiescent attempt，active 或 referenced object 不删除。raw completion/orphan cleanup 统一 batch→item→job/attempt→advisory 锁序。Ruff、strict mypy 与 51 项 Linux Provider/config/PostgreSQL/storage/reconciliation/crash tests 零 skip通过；无 dependency、model、真人图、live call、public API 或 migration，T05 Worker pipeline 已解锁。
- 2026-08-16：P2-M2-T05 经 Principal 本地验收并提交为 `be4a75fdc3b142fc8cd0fed8cef14b3fed9cff9b`。reference-only task 只含 item/Job/request/schema references；Celery-independent executor 在 exact lease 内物化脱敏 Prompt，执行 Provider→cost→private raw→immutable evidence，支持 duplicate no-op、retry/cancel/stale-lease reconciliation、TTL cleanup 与 Local/Celery dispatcher。CI/development Celery 显式使用共享私有卷上的 Local synthetic storage，避免 task-local Mock bytes 与 PostgreSQL `RAW_STORED` authority 分裂；production 继续只允许 disabled。`P2-M2-R03` 修正 cancelled single-item batch 聚合优先级，`P2-M2-R04` 修正数据库 ID 到 first-party policy/template reference 的映射并安全拒绝不可物化 Prompt。最终 22 项 Linux/PostgreSQL/Redis/Celery/跨进程 blob 验证零 skip，Ruff/strict mypy/Prettier 全绿，五个 Compose 服务 healthy；无 dependency、model、真人图片、live Provider 或 public API，T06 已解锁。
- 2026-08-16：P2-M2-T06 经 Principal 本地验收。独立安全测试固定 reference-only task exact shape，扫描 M2 application/Worker 的网络或 Provider SDK、URL、Prompt/object-key/secret logging、M3/public API 越界及 production fail-closed；`P2-M2-R05` 去除 generic Celery retry 对原始 Provider/storage exception chain 的暴露。Fresh Linux 容器在隔离 PostgreSQL、Redis 与真实 Celery Worker 上完成 API 307 + Worker 27 项零 skip，Ruff 156 files、strict mypy 98 sources、完整 `pnpm check`/contracts/Next build 与 diff check 全绿；临时数据库、Redis DB 和 Worker 已精确清理，五服务恢复 healthy。Windows host pytest 因运行时对默认及新 basetemp 的 ACL 拒绝不计入证据，未触碰既有 `.tmp/p1m6-unit` 或 `.tmp/pytest-worker`。无 dependency、model、真人图片、live Provider、public API 或 migration；T07 仍为 `EXTERNAL_VALIDATION_REQUIRED: IMAGE_GENERATION_PROVIDER`。
- 2026-08-16：P2-M2-T07 外部 Provider Gate 为 BLOCKED。仓库 Provider 与模型/数据登记仍将真实 image-generation Adapter 标为 candidate/fail-closed/`PRODUCTION_BLOCKED`，model/data terms、地域、留存、公共训练、分包商、删除、输出权利、安全和成本均未验证；不得用 Mock 或未批准 live call 伪造 benchmark。T08 可继续生成确定性 same-SHA evidence，但 M2 最多 CONDITIONAL，不能 PASS/FROZEN 或进入 M3。T08 新增 `mirror.p2-m2.ci-evidence/v1`，明确写入 `external_validation_required`/`production_approved=false`，并补齐 Linux CI Celery 的 `mirror.synthetic` queue；隔离 Linux 本地 37 项 evidence tests 零 skip通过，远端 CI 尚待执行。
- 2026-08-16：Principal 接受 P7 Visual Memory OS deep-research 治理 checkpoint，P3–P7 仍全部 `DIRECTIONAL`。P7 权威链固定为 User Truth → Evidence Ledger → versioned idempotent incremental compiler → rebuildable views → retrieval router → deterministic task-conditioned Gate → bounded context；Profile/vector/graph/Memory Card/LLM summary 均为可重建派生层。首轮研究必须先做 Profile/SQL structured baseline，再决定 visual/vector/graph；同 session/source/burst 相关证据不得自动计作独立确认，偏好研究区分 valid time 与 system/learned time，completed deletion 要求 derived orphan 为零。所有 Mem0/Graphiti/GBrain/PMMC/MemEye/MemLens/LangGraph/LangMem/Letta/MemGate/MemMachine/V-Mem/SAGE 主张仍为 `UPSTREAM_CLAIM`/`UNVERIFIED`，无 Project Mirror reproduction、dependency、model artifact、真人图片、runtime/API/schema/migration 或当前 M2 Gate 变化。
- 2026-08-16：P2-M2 独立本地最终审查结论为 `CONDITIONAL`。相对 M1 frozen baseline 仅新增前向 `0009_generation_batch_pipeline`，OpenAPI/generated TypeScript、依赖、lockfile、模型和真人图片资产无变化；M2 source 无外部 URL/网络 SDK 或 public generation route，deterministic security/integration evidence 全绿。当前分支未获本次 payload 的显式 push 授权，因此 same-SHA GitHub Actions 为 `NOT_VERIFIED`；真实 image-generation Provider 仍缺模型/数据条款、留存、训练、地域、删除、输出权利、安全与成本 Gate。M2 保持 EXECUTING，不能 PASS/FROZEN，M3 与整个 Phase 2 completion 继续关闭。
- 2026-08-16：Project Owner 通过 ADR-026 前向批准 `CODEX_NATIVE_IMAGEGEN` 作为 P2 synthetic-only 的 operator-assisted offline development source，不是 runtime `ImageGenerationProvider`。原 programmatic Provider exit Gate 改为 `DEFERRED_EXTERNAL_PRODUCTION_DEPENDENCY`；生产 Provider 仍 `NOT_CONFIGURED`、production generation 仍 `FAIL_CLOSED`，`PRODUCTION-BLOCKER-IMAGEGEN-PROVIDER` 必须在任何依赖 runtime generation 的生产发布前关闭。Native provenance 仅为 Principal/operator attestation 与 `PROVENANCE_ONLY`；model/version/request/seed/usage/cost 不可获得时必须保持 `NULL`，不得推导为强可复现或 production approval。
- 2026-08-16：P2-M2-V01 在 4 个 versioned categories × 2 images 上完成受控验证：8 requested、8 admitted、8/12 attempts、serial concurrency、expected SHA 全匹配；native 实际输出为 `1254×1254 PNG`，requested `1024×1024` 事实保留并记录 `dimensions_match_requested=false`，M2 不做 resample/normalization。Binaries、Prompt、paths、storage references 与 object keys 仅在 ignored private storage；Git 只保留 redacted checksum manifest。`P2-M2-R06` 强制 private source root、UNC/traversal/symlink/reparse 拒绝、per-item expected SHA、retry/attempt ceilings 与 path-free OS errors；`P2-M2-R07` 运行时强制 unknown provenance facts 为 `NULL`。独立安全审查无剩余 defect；修复后 full API/Worker/PostgreSQL/Redis/Celery 353 PASS/0 skip、Ruff 161 files、strict mypy 101 sources、`pnpm check`、fresh Alembic lifecycle 与 Docker health/smoke 全绿。最终 M2 Gate 仅待最终 candidate same-SHA GitHub Actions；此前 c24b03b baseline run `31954658786` 三 jobs 已通过。
- 2026-08-17：P2-M2 final candidate `1e1e70e116c893be400a1766758ede76ab565ea0` 的 run `31957815455` 三个 jobs 全绿。P2-M2 evidence `9266469638` 精确绑定 candidate SHA、`0009_generation_batch_pipeline`、既定 OpenAPI digest、48 tests 零 failure/error/skip 与 8 类 deterministic checks PASS，并保持 programmatic Provider deferred、`production_approved=false`、Codex native offline source 为 `PROVENANCE_ONLY`；Phase 1/P2-M1 regression artifacts 同 SHA，Docker/audit artifacts 可读，Gitleaks `9266417306` 为一项 SARIF run、零 results。Principal 将 P2-M2 前向更新为 PASS；只有 acceptance closure same-SHA CI 全绿后才能 FROZEN 并开放 P2-M3 rolling-wave refinement，`PRODUCTION-BLOCKER-IMAGEGEN-PROVIDER` 继续 OPEN。
- 2026-08-17：P2-M2 acceptance closure `e211adb54da2c24e517e2ae3e49ab92746e0d7b2` 的 run `31958454155` 三个 jobs 全绿。P2-M2 evidence `9266632362` 精确绑定 closure SHA、`0009`、既定 OpenAPI digest、48 tests 零 failure/error/skip 与 8 类 checks PASS；Phase 1/P2-M1 evidence 同 SHA，Docker `9266606944`、audit `9266635276` 可读，Gitleaks `9266585013` 为零 results。Principal 将 P2-M2 前向更新为 FROZEN；仅开放 P2-M3 rolling-wave refinement，M3 implementation 仍需接受后的 refinement 与显式授权。生产 Provider 继续 `NOT_CONFIGURED`/fail closed，`PRODUCTION-BLOCKER-IMAGEGEN-PROVIDER` 继续 OPEN。
- 2026-08-17：P2-M2 freeze-state `0b579ebdb1c2a63936225bc59a4b0ca780544df2` 的 run `31958786882` 三个 jobs 全绿。P2-M2 evidence `9266721317` 精确绑定 freeze SHA、`0009_generation_batch_pipeline`、OpenAPI digest `a9ee1e0ad3b942e5be5790b4fc7ff8c0deab744a84d3383a7a8856a8f97b4841`、48 tests 零 failure/error/skip与 8 类 deterministic checks PASS；programmatic Provider 继续 deferred、`production_approved=false`，Codex native source 继续为 offline `PROVENANCE_ONLY`，Gitleaks artifact `9266670445` 为零 results。P2-M2 完整 FROZEN，并从该 SHA 创建 `codex/phase2-m3-normalization-base-qa`。
- 2026-08-17：P2-M3 rolling-wave refinement 通过 ADR-027 冻结合成规范化、base QA 与 identity registration 权威。M2 `GenerationItem.RAW_STORED` 保持不可变终态，M3 以独立 `SyntheticAssetRecord` 表达 normalization/QA lifecycle；raw、normalized Asset、QA evidence 与 bank-independent identity 分层。规范化复用 Pillow 12.3.0，输出进入 `internal-synthetic/v1/normalized`、second-decode 并记录 checksum；Vision 只消费 normalized synthetic input。clearly-adult presentation 必须显式人工复核且不能覆盖 automatic hard failure，不做年龄估计或敏感分类。计划 migration 为 `0010_synthetic_asset_qa`；无 public/internal HTTP API、新依赖、模型、权重、真人图片或 M4 实现。MediaPipe 仍 `LICENSE_REVIEW_REQUIRED`；缺少获批 synthetic-only Vision candidate 与受控 benchmark 时 M3 不得 PASS/FROZEN。规划 checkpoint `963869273355d2fc14db4c4178ec63d3acb48ecb` 的 run `31959813830` 三个 jobs 全绿，P2-M3 已前向进入 `EXECUTING`。
- 2026-08-17：P2-M3-T02 经 Principal 本地验收。前向 `0010_synthetic_asset_qa` 新增 `SyntheticAssetRecord`、versioned `SyntheticQARun`、append-only measurement/review evidence，并把新 `SyntheticIdentity` 收紧为唯一 canonical Asset + accepted passed QA authority，同时无损保留 `LEGACY_SKELETON` rows。PostgreSQL trigger/constraint 强制 raw-stored source、approved QAPolicy、单向状态与时间戳/结果码形状、hard failure 不可绕过、三类 mandatory human review、原子 identity registration、lineage/evidence immutable 与有 M3 数据时 downgrade fail closed；fresh/`0009→0010→0009→0010`、legacy compatibility、`alembic check`、14 项 targeted PostgreSQL tests、完整 Linux API/Worker 回归、Ruff、strict mypy 与 contracts drift 均通过。未新增 public API、dependency、模型/权重、真人图片或 external call；M3 继续 EXECUTING，T03–T08 与 Vision candidate Gate 未完成。
- 2026-08-17：P2-M3-T02 repair candidate `4e8a72abd684da26549a7ebaf2debc74c010f228` 的 run `31962045245` 三个 jobs 全绿；Phase 1/P2-M1/P2-M2 evidence 均绑定该 SHA、migration head `0010_synthetic_asset_qa` 和既定 OpenAPI digest。P2-M3-T03 经 Principal 本地验收：新增独立 `internal-synthetic/v1/normalized` storage port/Local adapter、deterministic config digest、raw inspect + streamed checksum/size verification、canonical synthetic Asset 事务完成与 blob-before-commit recovery。数据库锁序统一为 source object→synthetic record，修复并发 ensure/claim 反向锁导致的真实 PostgreSQL deadlock；row-lock query 强制 refresh，避免并发完成读取 stale ORM state 并重复创建 Asset。确定性 decode/tamper/conflict 失败终止，transient store failure 保留 `NORMALIZING` 可重试。Linux targeted 25 PASS/0 skip，完整 API/Worker 366 tests 为 0 failure/0 error（3 个未启动外部 Celery worker 的既有 round-trip skip），完整 Ruff/strict mypy 与 contracts drift 通过；Windows/Linux canonical JPEG SHA-256 均为 `f55764d4e734d3d465707df1327826395f3ca3972c40601c1477f3cb8c52a495`。无 dependency、model/weight、public API、真实人脸或 V01 binary 进入 Git；M3 继续 EXECUTING，T04–T08、V01/V02 和 Vision candidate Gate 未完成。
- 2026-08-17：P2-M3-T03 checkpoint `9856c235432fb580836480cfaee56c21e8c58c1b` 的 run `31965014695` 三个 jobs 全绿；Python quality/tests、`0010` migration lifecycle、Redis/Celery、TypeScript/build、browser、contract drift、dependency/license、SBOM、Docker 与 Gitleaks 均通过。Phase 1/P2-M1/P2-M2 regression、Docker、audit 与 Gitleaks artifacts 均绑定 exact SHA。该证据只接受 T03 checkpoint，不替代 T07 最终 `mirror.p2-m3.ci-evidence/v1`；M3 保持 EXECUTING。
- 2026-08-17：P2-M3-T04 经 Principal 本地验收，`P2-M3-R01` 关闭 caller-supplied requirements 绕过：QA finalization 只信任 QARun 绑定、已批准且 canonical digest 匹配的 `QAPolicyDefinition/v1`；required measurement 必须匹配 hard-gate classification 与 algorithm/version，缺失、未知、unsupported、`NOT_APPLICABLE`、malformed 或 mismatch 均 fail closed，automatic hard failure 不可由 human review 覆盖。Vision port 仅接受 checksum-bound canonical JPEG normalized synthetic payload，Mock zero-network，candidate 继续 fail closed。Ruff、strict mypy 96 sources、12 focused tests、contracts drift 通过；fresh `0010` 隔离 PostgreSQL 的 async service test 在 Linux 连续两次 PASS，临时容器已删除，五个 Compose 服务保持 healthy。T04 不批准真实 Vision candidate、不完成 V01/V02 review 或 identity registration；M3 仍 EXECUTING。
- 2026-08-17：`P2-M3-R02` 修正冻结 M2 phase-boundary regression 的路径分类滞后：M2 forbidden-symbol scan 只读取实际 M2 generation/prompt/raw-storage/Worker 模块，并显式证明 M3 normalization/QA 文件与该集合互斥；原有跨 synthetic pipeline 的 zero-network 与日志脱敏扫描保持不变。Run `31966322329` 的失败因此分类为测试范围缺陷而非 M2 业务越界；修复提交 `d37f61b253c2240478d72aacedd167ede6d96eaa` 的 run `31966877634` 三 jobs 全绿，原 M2 evidence step 与 Phase 1/P2-M1/P2-M2/Docker/audit/Gitleaks artifacts 均存在，R02 已由 Principal 接受。
- 2026-08-17：P2-M3-T05 与 `P2-M3-R03` 经 Principal 验收。M3 normalization/QA 只经 reference-only task 和空 payload Job/Attempt envelope 执行，Celery 使用 `mirror.synthetic`，reconcile 使用 `mirror.maintenance`；canonical identity 注册在 PostgreSQL 中重新验证 approved policy 与全部 hard-gate evidence，并保持单 Asset/QA authority。Principal 发现并修复 reserve 的 `Job→record/run` 与 completion 的 `record/run→Job` 反向锁序、QA finalize 后 crash 无法恢复 identity、以及 retry exhaustion 只终结 Job 的缺陷；现统一 domain authority→Job/Attempt 锁序，`QA_PASSED` 可重入注册，第四次失败原子进入 `NORMALIZATION_FAILED`/`QA_FAILED`，第五次 delivery no-op。fresh Linux 5 项 PostgreSQL + 1 项 Redis/Celery + 2 项 Worker targeted tests、完整 API/Worker suite、Ruff 178 files、mypy 110 sources、Alembic 零 drift 与 contracts drift 全绿；候选 `5a726fc6348ab253b98e945348cfeac4b835a832` 的 run `31968433284` 三 jobs 全绿，Phase 1/P2-M1/P2-M2/Docker/audit/Gitleaks artifacts 均存在。T05 不批准 Vision candidate，M3 仍 EXECUTING。
- 2026-08-17：P2-M3-T06 MediaPipe Gate 为 `BLOCKED`。三份 Google 官方 BlazeFace Short Range、Face Mesh V2 与 Blendshape V2 model cards 已完整读取/渲染并均明确标注 Apache-2.0；其训练/评估数据只提供 consented mobile-AR、real-world smartphone 或 controlled lab/GHUM-derived 的高层描述，未闭合逐项权利、地域、删除与再分发链。Face Landmarker bundle 可固定到 GCS generation `1683136941468629`，size `3758596`、MD5 `b0e7274907a1644404fef66b28dd6d85`，但 upstream 无 SHA-256。未获明确 artifact-download authorization，未下载或安装 wheel/`.task`；bundle SHA-256、package notices/native SBOM、Python 3.13、zero-network、Windows/Linux repeatability 与 V02 calibration 均未验证。M3 保持 EXECUTING，T07/T08 与 M4 entry 关闭。
- 2026-08-17：P2-M3-V02 在不下载 artifact 的前提下完成预注册。MediaPipe `0.10.35` 继续作为 exact candidate；PyPI `1.0.1` 因同样缺少 `Requires-Python`/license expression、保持相同 unpinned dependency families、wheel 显著增大且 GitHub/PyPI version mapping 更模糊而不采用。授权后固定执行顺序为 exact artifact admission → wheel/native/license/SBOM audit → CPython 3.13 Windows/Linux zero-network runtime qualification → V01 `*-01` calibration → immutable QAPolicy/digest freeze → `*-02` holdout；no-face/multi-face/small-face/roll/tamper controls 不得注册 identity。该预注册不授权下载、安装、模型运行、依赖变更或阈值猜测。
- 2026-08-17：MediaPipe `v0.10.35` exact-tag 静态源码显示 Face Landmarker Python module 使用本地 model path/buffer 且无显式 HTTP/socket client，但 `BaseOptions.to_ctypes()` 会把 `certifi` CA-bundle path 传入 native layer，因此源码扫描不能证明 zero-network，必须保留 native inventory 与进程级 egress deny/capture。V02 冻结 still-image CPU、`num_faces=2`、三个 upstream `0.5` confidence baseline、blendshapes disabled、transformation matrices enabled；这些是候选运行参数，不是 Project Mirror QA 阈值。
- 2026-08-17：经 Project Owner 授权，P2-M3-T06 对 exact `mediapipe==0.10.35` 与 GCS generation `1683136941468629` 执行 private/disposable PoC；wheel hashes 匹配，bundle SHA-256 为 `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`，未进入 Git 或项目依赖。Windows bounded synthetic inference 在出站阻断下仍由 native `portable_clearcut_uploader` 尝试 Google Clearcut telemetry；Linux `--network none` 单次推理虽成功，也不能覆盖 Windows hard failure。按预注册协议 exact candidate 为 `FAIL`，不得进入 V02 calibration、QAPolicy freeze、holdout 或 identity registration；replacement candidate/build 需要新的 Principal change control 与预注册协议，M3 保持 EXECUTING。
- 2026-08-17：Project Owner 通过 ADR-028 批准首包合成年轻成年女性年龄呈现 change control：primary 18–25，secondary 26–30 仅用于 coverage，31–34 de-emphasized，明显 35+ 只作为首包 selection exclusion；minor ambiguity、childlike presentation 与 schoolgirl framing 是 hard reject。年龄区间只用于 synthetic Prompt、人工视觉呈现 review 与首包选择，不是自动年龄估计或真实用户属性；不得以幼态化、同质化或牺牲 morphology/identity diversity 实现年轻化。V01 不修改，V-next 使用新 private Prompt/policy version；Codex native 仍仅为 offline source，真实用户 runtime generation 调用保持 0。
- 2026-08-17：Project Owner 通过 ADR-029 批准首包多峰风格吸引力 change control：`visually aspirational`、女性向问卷适配与 stylistic distinctiveness 只能作为非数值、可解释的 soft curation 目标，禁止 beauty/attractiveness score、percentile、ranking 或统一理想脸。八个批准的 style context 是可替换 presentation descriptor，不是 identity、敏感分类、morphology 或路由 authority；adult/minor safety 保持 hard gate，product/style mismatch 只作首包 exclusion。V01 与 age-only V-next 不重写、不追溯重标，新的 style-aware cohort 必须使用独立 private policy/Prompt/version 并继续保持真实用户 runtime generation 调用为 0。
- 2026-08-17：Project Owner 通过 ADR-030 前向修订年轻脸成年合成人物的人工呈现边界：未来一般非性感 cohort 不得仅因 round face、babyface、soft features 或 youthful adult appearance 拒绝；只有明确呈现为未满 16 岁或存在儿童/学生未成年语境时 hard reject，且不得引入自动年龄估计。`ADULT_SAFE_SEXY`、`CHARMING_ALLURING` 及任何 intimate/sexualized context 仍要求 unambiguous 18+，不能使用可能呈现为 16–17 岁的主体。ADR-028/029、age/style v1 与全部既有 Prompt、图片、attempt、manifest、provenance 不覆盖、不追溯重标；新生成必须绑定 v2 policy/rubric。
- 2026-08-17：ADR-031 为 Codex built-in imagegen 未暴露 requested dimensions 的未来 cohort 增加前向 native admission v2；v1 manifest/evidence 完全不改。v2 以 cohort-level requested/attempt/retry/concurrency constraints 和 bounded MIME/byte/edge/pixel constraints 为权威，未知 requested width/height 与 `dimensions_match_requested` 必须保持 `NULL`，不得从 observed output 反推或在 raw admission 前裁切。P2-M3 style-v2 cohort 已完成 8 requested/8 admitted、10/12 attempts、8 项 categorical hard-gate PASS、2 项 adult-only overlay PASS；committed redacted evidence 不含 Prompt、路径、object key、storage reference 或图片。该结果不替代仍被 replacement candidate 阻断的 Vision QA、morphology measurement、identity registration 或 QuestionBank release。
- 2026-08-17：ADR-032 前向批准 `MEDIAPIPE_SOURCE_BUILD_ZERO_TELEMETRY_V1` 的 isolated Stage A source-feasibility study，冻结 exact `v0.10.35` commit `f8ef212d5c962c0e853db7e59d217056b187084b`。官方 `0.10.35` wheels 继续 `REJECT_FOR_P2_M3_RUNTIME`；新候选必须从 Face Landmarker closure 中实际移除 Clearcut、telemetry、HTTP/network 与 CA-bundle plumbing，不能只屏蔽连接或隐藏警告。Stage A 只允许私有源码检查；patch/toolchain/dependency/build artifacts/SBOM 未冻结前禁止 build/install/model execution，Windows/Linux 零 egress、model/data disposition、V02 calibration/holdout 仍是独立 Gate；无 project dependency、model artifact、schema/API 或 M4 authority 变化。
- 2026-08-17：P2-M3-V03 Stage A PASS。exact public `v0.10.35` source 使用 `TasksDummyLogger` 且不含 rejected wheel 中的 Clearcut client/endpoint，证明 upstream wheel 的 native closure 不能视为公开源码的可复现构建。批准 patch SHA-256 `cdde123e56bcd637726d7162171a75bed10de415cd323aa95952b1cba7e942eb`：新增只含 Image + Face Landmarker C API 的 minimal shared-library target，并从该 C/C++ closure 移除 CA-bundle field；不使用 upstream Python package、certifi 或完整多任务 library。Stage B 仍须冻结 Bazel 7.4.1、target-specific repository inputs、Windows/Linux toolchain、artifact hashes、native/license/SBOM；本轮未 build/install/import/model execution，V02 calibration 与 identity registration 继续关闭。
- 2026-08-17：ADR-033 前向批准 V03 私有 Stage B 的最小 OpenCV build lock，不构成 Project Mirror runtime/production 或 M4 OpenCV 采用。configured CPU closure 证明 Face Landmarker 只经 image-to-tensor preprocessing 使用 OpenCV `core,imgproc`；禁止未固定的 `linux_opencv=/usr`。OpenCV `3.4.11` archive 固定 SHA-256 `10898a0268d8f8cbaf0354ddd1d9de6abaac84e3d9a6c9754f56a0aa3383d73b`，exact-source 为 3-clause BSD；build-lock overlay SHA-256 `6b0d8771c1d1660abb6ee4cfca7a88b04ebb787faa36c8fd9cd15ecdbd3ecafa`，只构建 `core,imgproc` 并关闭 IPP、视频/UI/codec、外部加速和二次下载面。Linux builder 与 39-repository configured closure 已冻结，离线 build 获授权但尚未执行；Windows toolchain、artifact/SBOM/vulnerability、zero-network runtime、model/data、calibration/holdout 仍未批准。
- 2026-08-17：P2-M3-V03 Linux 离线源码构建在 `--network none` 下完成。首次构建因 Windows CRLF 使上游 metadata version stamp 生成非法 C++ 字符串而失败；`P2-M3-R04` repair overlay SHA-256 `a59578edba3a6c350ef78850b26e6cbf5f5929a32048c5199f92b4c526a27823` 仅剥离 CR，未改变 graph/dependency/runtime。重试 4,610 actions PASS；主库 SHA-256 `a892ba0976fcd557a9ff2056ae170f765ab68aca99f70607eee0c6989fb94e7b`，只动态依赖冻结的 OpenCV core/imgproc 与 Linux runtime，九项 versioned exports，无动态网络导入或 Clearcut/CA-bundle 字符串。TFLite 本地 telemetry/profiler 类型仍存在，不能把字符串扫描当作 zero-egress 证明；Linux license/SBOM/vulnerability、clean reproduction、Windows build/runtime、model/data、V02 calibration/holdout 继续关闭。
- 2026-08-17：`P2-M3-R05` 关闭 V03 Linux artifact 位级可复现缺陷。最终 outer patch SHA-256 `192056a6ad29362442fe440bf24ea4f998b09172ab0807f91bc9c24a96d41c68` 依次消除 foreign-build 私有路径、generated OpenCV build/install path、OpenCV RPATH 与编译壁钟 timestamp；两个全新、无网络、4,610-action build 的 main/core/imgproc 三项均 byte-identical，SHA-256 分别为 `a892ba0976fcd557a9ff2056ae170f765ab68aca99f70607eee0c6989fb94e7b`、`048df8097a7c444769e5c56708041aa0c60a48a5a442f2ebad2c60a03097653a`、`765ebf6c659e523d9d7e9557e63f004a041a9327fcba95e6d4ac0670485241f5`；三项私有路径扫描为零，OpenCV 无 RPATH/RUNPATH，主库仅相对 `$ORIGIN`。Ninja `1.12.1-1` 许可证据已闭合；Grype source/SBOM 扫描仍需对 `CVE-2019-14493` 做有来源的处置。OouraFFT entry points 存在且 modified/binary redistribution 权利不明确，因此只允许内部隔离研究，distribution/production Gate 保持 BLOCKED；Windows build/runtime、model/data、V02 calibration/holdout 继续关闭。
- 2026-08-18：Project Owner 明确授权后续 Project Mirror 工作自主下载完成任务所需依赖，并特别授权 MediaPipe `0.10.35` exact Windows/Linux wheels 与 exact Face Landmarker model bundle。所有下载仍必须进入 ignored private evidence、固定来源/version/checksum 并分别完成许可、SBOM、安全与运行 Gate；下载授权不等同于项目 dependency adoption、模型/数据权利批准、production Provider/runtime approval 或真实用户 facial processing 授权。
- 2026-08-18：ADR-035 / `0011_offline_synthetic_source_authority` 已完成权威验证：24 项 focused PostgreSQL tests、fresh upgrade、`0011→0010→0011` 与 `alembic check` 均通过。冻结的 P2-M2-V01 八项 receipt 未重生成或伪造 Provider facts，而是幂等导入为 8 immutable offline admissions + 8 sources，并经 `image-sanitizer-v1` 形成 8 normalized records + 8 synthetic Assets；全部 second-decode 与 replay 通过，零 tracked binary。该证据只关闭 V01 offline authority/normalization，不批准 Vision QA、identity registration、QuestionBank release、production Vision 或真实用户 facial processing。
- 2026-08-18：P2-M3-V03 Windows source-build clean reproduction 已通过静态构建 Gate。R17 从固定 Face Landmarker closure 移除未使用的 AudioSpectrogram/MFCC/RFFT2D 与 Ooura，并禁用会覆盖 `/DEBUG:NONE` 的 Bazel FASTLINK/PDB feature；R18 仅规范化 OpenCV build report 中的私有 MSVC/NMake 路径。`bw28`/`bw29` 各完成 4,549 actions，main/core/imgproc 三对 byte-identical，六项 artifact 的实际私有路径、PDB/RSDS、Ooura、Clearcut/CA 和 Windows network API 扫描为零。规范化后的 R17 patch SHA-256 为 `7099bdb0ed223d71110a18148880090f15311220f75e20cb1af6eb9619cca5dc`。该结论不批准模型或 production Vision；R17 hardened Linux 双根复现、license/SBOM/vulnerability audit、Stage C zero-egress、V02 calibration/holdout 仍是强制 Gate。
- 2026-08-18：P2-M3-R17 hardened Linux clean reproduction 已通过静态构建 Gate。首个因容器工作目录错误失败的 output root 仅保留为 attempt evidence；两个全新 `--network none` roots 均完成 4,597 actions。main/core/imgproc 三对产物逐字节一致，SHA-256 分别为 `19e90273dc9d370563ba48b2b9a0752a677c429f80b971dd3a6c814c223c1f29`、`116c2db3b7e149390631af309f910eabeb73bd18281e4174f131ced2a8de4408`、`765ebf6c659e523d9d7e9557e63f004a041a9327fcba95e6d4ac0670485241f5`；ELF 仅相对 `$ORIGIN` RUNPATH，private path/Ooura/Clearcut/CA/network scans 为零。跨平台 build reproducibility 已有证据，但更新 SBOM/license/vulnerability、exact model disposition、Stage C、V02、T07/T08 仍未通过。
- 2026-08-18：P2-M3-V03 Stage B audit 对 R17 权威 graph 重建：22,719 labels 中零 `fft2d`/Ooura，51-component SBOM SHA-256 为 `902088a0e70d3ce005885c01f7ee472fba19458ae803e09700df52949d152dda`，38-repository/124-file license inventory SHA-256 为 `e1e77546b0a2a8148cc2f6ef6b3dc700305edad16311b09d9a836caa3c2742d3`。Grype direct closure 为零；OpenCV 四项 CPE findings 通过 exact persistence backport/no-crash negative controls 或未构建 affected modules 独立 disposition。固定 model bundle 仅 `PRIVATE_RESEARCH_ONLY`，distribution/production 仍 blocked；Stage B 只批准 isolated synthetic Stage C。
- 2026-08-18：`P2-M3-R20` 识别并修复 data-rights HTTP integration 的固定时间炸弹：fixture session 固定在 `2026-08-17T23:30:00Z` 过期，导致稍后 CI 按正确的 fail-closed 逻辑返回 401。修复只把测试 session expiry 绑定到 live test clock，不改变 token、scope、revocation 或产品认证逻辑；fresh PostgreSQL `0011` 上目标测试连续 5 次与完整 API suite 通过，same-SHA run `32081539232` 的 `quality-and-integration`、`secret-scan`、`docker-validation` 全部 PASS。
- 2026-08-18：`P2-M3-R21` 与 V03 Stage C 经 Principal 验证通过。Windows `bw34`/`bw35` 各完成 4,549 actions，main/core/imgproc 三对 byte-identical，SHA-256 分别为 `5a904100bf197e8b4755f503aa4d1d8a8892107a9940e2f848eeb302ff24dd8d`、`353c960dbc233d6d412dc1015b702321f3a7f8a80494a7142c7e9c3670d61f68`、`1aa54040e263be7685f2b8a379cf1f34a275b0718cc8b3a823a1f935c28592b4`；所需 Face Landmarker 与 image create/free exports 存在，private-path/PDB/RSDS/Ooura/Clearcut/certifi-CA/telemetry endpoint/network import 扫描为零。固定 GCS generation `1683136941468629` model SHA-256 仍为 `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`；Windows 在 process-specific outbound block + Filtering Platform failure capture 下三次 create/detect/free/close 均 one-face PASS 且 zero outbound attempts，Linux 先前三次 `--network none` 同样 PASS。V03 runtime 只批准 private synthetic V02 Stage D；官方 wheel 仍 rejected、model 仍 `PRIVATE_RESEARCH_ONLY`，distribution/production Vision/real-user facial processing/T07/T08/M3 Gate 仍关闭。Windows cleanup 曾因递归跟随 Bazel reparse point 损坏 private toolchain，已按原始 workload 恢复 VS 17.14.38/MSVC 14.44.35207/SDK 10.0.26100.0；后续禁止递归删除 Bazel roots。
- 2026-08-18：`P2-M3-R25` 移除 Windows reproduction patch 中提交的私有绝对 NMake 路径，改为由 Bazel action environment fail-closed 注入 `MIRROR_NMAKE_EXE`；missing-variable negative control 无 PATH fallback，patch apply/reverse、Windows `bw37`/`bw38` 与两个 Linux `--network none` clean roots 均通过。R25 Linux main/core/imgproc SHA-256 为 `6a5fb35175efc2f014fb61f7f4abb2c78c38156bd6abf2186d1549cbf3f006a7`、`116c2db3b7e149390631af309f910eabeb73bd18281e4174f131ced2a8de4408`、`765ebf6c659e523d9d7e9557e63f004a041a9327fcba95e6d4ac0670485241f5`，三次 Stage C one-face/close PASS 且零网络调用；`19e90273...` 保留为 R17 历史 checkpoint，`6a5fb351...` 是 R19/R21/Stage D/current qualified Linux runtime。R25 只改变 NMake 注入表达，既有 51-component SBOM、38-repository/124-file license inventory 与漏洞处置继续适用；官方 wheel、模型分发、production Vision、真实用户处理和 M3 Gate 仍关闭。
- 2026-08-18：`P2-M3-R26` 以前向 correction evidence 关闭历史 V01 文档把 descriptive migration name 当作 `migration_head` 的治理缺陷；原文件 SHA-256 `621ccb7444ae2e678cdad7e290cf0bf362b8d7779b291c9a89ce4f19a774b245` 保持不变，correction digest 为 `c3d6751e97383d9cd3332e9450dc60d3427586a2aafa25496ebf09c0daaa894d`，真实 Alembic head 为 `0011_offline_synth_source`。Candidate `c31ca44627843c04455bbe333b6e1dcfc515d096` 的 run `32106647901` 三 jobs 全绿，artifact `9313484471` 记录 46 tests/0 skip；独立安全与最终审查均 PASS。Principal 将 P2-M3 前向更新为 PASS；只有 acceptance closure same-SHA CI 全绿后才能 FROZEN 并开放 P2-M4 rolling-wave refinement。官方 wheel 仍 rejected，model 仍 `PRIVATE_RESEARCH_ONLY`，distribution/production/real-user/QuestionBank release 继续 blocked。
- 2026-08-18：P2-M3 acceptance closure `abbf6c95e33ed39c34674c881d30b6cb578d17b0` 的 run `32107844716` 三 jobs 全绿。P2-M3 evidence `9313887640` 精确绑定 closure SHA、真实 `0011` head、46 tests/0 skip 与 R26 correction digest；Docker/audit artifacts 可读，Gitleaks `9313780235` 为零 results。Principal 将 P2-M3 前向更新为 FROZEN；只开放 P2-M4 rolling-wave refinement，implementation 仍需 refinement 被接受后另行授权。官方 wheel、model distribution、production Vision、真实用户 facial processing 与 QuestionBank release 继续 blocked。
- 2026-08-18：`CC-P2-M4-03-A` 已实现 immutable 1:1 LandmarkWarpPlan authority；migration 文件名为 `0013_landmark_warp_plan_authority.py`，真实 Alembic revision/head 为 `0013_warp_plan_authority`。Principal 负向复核发现初版 PostgreSQL trigger 在攻击者同步重算 digest 时会接受 duplicate JSON key 或整数化坐标，已在提交前收紧为 raw JSON 顺序/重复、escape 与 Python-compatible canonical float 校验；4 个 direct-SQL adversarial cases、共 22 项 focused tests、Ruff、116-source strict mypy、contracts drift、fresh `→0013→0012→0013`、zero-drift Alembic check 与完整 Linux API/Worker suite 均通过。该项仍待 tracked same-SHA CI/artifact 验收，T06 继续 blocked，T07/T08 与 M4 Gate 关闭。
- 2026-08-18：CC03-A candidate `4af3a8a3ff3264887ac8752a581180049cb6d240` 的 run `32137671571` 中 `secret-scan`、`docker-validation` 及 quality job 的 migration/Python/TS/browser 步骤通过，但 Phase 1 evidence generator 因 workflow 仍硬编码旧 `0012` head 而失败并跳过后续 evidence/audit。`P2-M4-R11` 只把四个 evidence 调用及回归断言更新为真实 `0013_warp_plan_authority`，不移除或弱化 Gate；须待新 exact-SHA 三 jobs 与 artifacts 全绿后才能接受 CC03-A 并恢复 T06。
- 2026-08-18：CC03-A/R11 repair candidate `741752d82bf22434aed2ffe37d6310452db2e51c` 的 run `32138493874` 三 jobs 全绿；七项 project-audit/P2-M1–M3/Phase1/Docker/Gitleaks artifacts 均存在、可读、未过期并绑定 exact SHA。四份 evidence 均记录真实 head `0013_warp_plan_authority`，P2-M3 为 46 tests/0 failure/0 error/0 skip，Gitleaks 为 0 results。Principal 接受 `CC-P2-M4-03-A` 与 `P2-M4-R11`；acceptance checkpoint CI 通过后恢复 T06，T07/T08 与 M4 Gate 继续关闭。
- 2026-08-18：CC03-A acceptance checkpoint `d9cff323db6218e6b9d7755464fc0bf9c96c53c2` 的 run `32139187461` 三 jobs 全绿。T06 随后只读核验发现新的 runtime-composition 架构缺口：已接受的 OpenCV transform 只能从 exact-hash private runtime root 加载，但 Settings/Worker 没有 typed provider/root composition。Principal 通过 ADR-039 / `CC-P2-M4-04` 冻结最小 `disabled | private_opencv` 配置、绝对私有 root、单一 manifest-verifying factory 与 production fail-closed；不新增 schema、依赖、binary、公开 API、生产 geometry 或真人处理。T06 在 CC04 实现与验收前暂停。
- 2026-08-18：CC-P2-M4-04 本地候选完成。Windows targeted config/factory/adapter 40 tests、全量 Ruff、117-source strict mypy、332 个无基础设施测试与完整 `pnpm check` 全绿；独立 fresh Linux PostgreSQL/Redis/四队列 Celery/可写 ignored storage harness 的 API+Worker 468 tests 零 skip，`alembic check` 零漂移。前两个 Linux full-run failure 均由 harness 复用 durable DB、缺 repository-only files、Celery 队列和 `LOCAL_STORAGE_ROOT` 造成，纠正 harness 后无需产品代码修补。候选状态为 `READY_FOR_TRACKED_EVIDENCE`；T06 仍待 exact-SHA 三 jobs 与 artifacts 后恢复。
- 2026-08-18：CC04 candidate `38e4755e87718ccddc5be81d45177fc37c5caae6` 的 run `32142005006` 三 jobs 全绿；project audit `9326412825`、P2-M3 `9326404299`、P2-M2 `9326403612`、P2-M1 `9326402997`、Phase 1 `9326402268`、Docker `9326312899` 与 Gitleaks `9326243254` 均存在、可读、未过期。四份 evidence 绑定 exact SHA、`0013_warp_plan_authority` 与 unchanged OpenAPI digest；M1 98、M2 52、M3 46 tests 零 skip，Gitleaks 0 results。Principal 接受 `CC-P2-M4-04`；acceptance checkpoint CI 后恢复 T06，T07/T08 与 M4 Gate 继续关闭。
- 2026-08-18：P2-M4-T06 本地候选建立 reference-only transform task、空 Job payload、private variant create-if-absent receipt、权威 transform service、M3 variant-QA handoff 与 Local/Celery composition。真实 Linux Redis/Celery 使用 accepted exact-hash Debian 12 OpenCV runtime 完成一项 reference-only `variant_qa_pending` round trip；fresh `→0013` PostgreSQL、独立 Redis 与 private storage 下 481 项 API/Worker tests 零 skip，Ruff、122-source strict mypy、Alembic zero drift、完整 pnpm/contracts 全绿。T06 仅为 `READY_FOR_TRACKED_EVIDENCE`，须待 candidate same-SHA 三 jobs/artifacts 后 Principal 才能接受；T07/T08 与 M4 Gate 继续关闭，且无新 migration、dependency、模型、公开 API、production geometry 或真人处理授权。

- 2026-08-18：P2-M4-T06 candidate `0ac4269399fdf45b486a7be4bce93f01292e0572` 的 run
  `32149168567` 三 jobs 全绿；project audit、P2-M1–M3、Phase 1、Docker 与 Gitleaks 七项
  artifacts 均存在、可读、未过期并绑定 exact SHA。四份 JSON evidence 记录真实 head
  `0013_warp_plan_authority` 与 unchanged OpenAPI digest，M1/M2/M3 为 98/52/46 tests 且零
  failure/error/skip，Gitleaks 为零 results。Principal 接受 T06 并只开放 T07；T08 与 P2-M4
  Milestone Gate 仍关闭。用户前向授权按需下载 MediaPipe 0.10.35 精确 Windows/Linux wheels、
  Face Landmarker 精确模型包及必要依赖，但下载授权不等于依赖采用、许可证批准、分发、生产启用
  或真实用户 facial processing 授权。

- 2026-08-18：P2-M4-T07/R12 candidate `9d6984435ad29a4a17635194aeba10783e22bbe7`
  的 run `32155084991` 三 jobs 全绿；七项 artifacts 绑定 exact SHA、真实 head
  `0013_warp_plan_authority` 与 unchanged OpenAPI，Gitleaks 为零 results。固定两 identity、双向、
  Windows/Linux、三次 transform/Vision holdout 的同平台与跨平台输出 bytes 全部一致，target 方向全部
  正确，最大跨平台 measurement 差为 `0.000011863707220088893`；最大 control relative drift
  `0.011420225249709091` 继续作为 M5 研究证据。Principal 接受 T07/R12 为
  `PASS_EVALUATION_COMPLETE`，但结论保持 `FURTHER_RESEARCH_FOR_M5_ISOLATION`：N=2 不满足 M5
  MVR，`jaw_width` 仍为 `EXPERIMENTAL`，未批准 M5 tolerance、production geometry、真人处理或
  QuestionBank release。T08 已开放，P2-M4 Milestone Gate 尚未决定。

- 2026-08-19：P2-M4 T08 forward repairs R13–R16 已关闭 split authority、exact Vision/topology binding、
  current-state drift 与 persisted ontology researchability 缺口。Fresh Windows/Linux replay 与原 T07
  outputs/measurements 完全一致；candidate `734148c38c591f1514d17a7a4fcb967dd680fd79` 的 run
  `32165030127` 三 jobs 与七项 exact-SHA artifacts 全绿，独立安全和最终审查均 PASS。Principal 将
  P2-M4 technical Gate 更新为 PASS；仍须 acceptance closure 与独立 freeze-state CI 后才能 FROZEN。
  `jaw_width` 保持 `EXPERIMENTAL`，结论仍为 `FURTHER_RESEARCH_FOR_M5_ISOLATION`，P2-M5、production
  geometry、真人处理与 QuestionBank release 继续关闭。

- 2026-08-19：P2-M4 acceptance closure `75c59ed39be34102d2e6e042a248801c17861cfb` 的 run
  `32166922750` 暴露 Phase 1 data-rights 潜在死锁；Docker 与 secret scan 通过，但 quality job 不得按
  flaky 重跑掩盖。`P2-M4-R17` 前向统一 account-deletion request、data-export Job/request 与 evidence 的
  锁序，不改 schema、trigger、授权、公开 API 或删除语义。修复前 live Compose/Celery 在有界第 2 次复现，
  修复后 focused 9 项与同一 vertical flow 20/20 通过，fresh PostgreSQL/isolated Redis/Celery 全套、质量、
  migration 和 Docker Gate 通过；当前仅 `READY_FOR_TRACKED_EVIDENCE`，P2-M4 仍未 FROZEN，P2-M5 关闭。

- 2026-08-19：P2-M4 repaired closure `11bda0ad1fed8d01298cc3be23ea461ff522cc91` 的 run
  `32169725374` 三 jobs 全绿，七项 exact-SHA artifacts 可读且未过期；Python 499 PASS/1 个既有 optional
  private-runtime skip，M1/M2/M3 为 98/52/46 且零 skip，Gitleaks 为零 results。独立安全与最终审查均
  PASS、无 mandatory finding，Principal 接受 R17/R18 并前向记录 P2-M4 `FROZEN`；P2-M5 仅开放
  rolling-wave refinement。`jaw_width` 仍为 `EXPERIMENTAL`，结论保持
  `FURTHER_RESEARCH_FOR_M5_ISOLATION`，N=2 不满足 M5 MVR，production geometry、真人处理与
  QuestionBank release 继续关闭。Project Owner 前向授权按任务需要下载依赖（含 MediaPipe 0.10.35
  exact Windows/Linux wheels 与 Face Landmarker exact bundle）到私有缓存；下载授权不等于 adoption、
  license、distribution、production 或 real-user processing 批准。

- 2026-08-19：P2-M4 freeze-state `5f2680e4d0724b409e13ac9cbe318b144cb0375f` 的 run
  `32171351357` attempt 2 三 jobs 全绿，七项 artifacts 精确绑定该 SHA 和
  `0013_warp_plan_authority`；M1/M2/M3 evidence 零 failure/error/skip，Gitleaks SARIF 零结果。
  attempt 1 的 Playwright 下载停滞是外部下载证据，不产生产品 Repair。Principal 从该冻结提交建立
  `codex/phase2-m5-variable-isolation` 并接受 ADR-041 与 M5 T01 rolling-wave protocol，M5 进入
  `EXECUTION_READY`。M5 technical Gate 与 P2-MVR-v1 result 必须分开；N 按每 dimension 的
  identity-disjoint、duplicate-cluster-adjusted holdout identity 计算，calibration/M4-seen 不计入，
  按 `24 → 48 → 96` 后仍不稳定就重新分类。当前只有 4 个 canonical identities、一个 experimental
  `jaw_width` 和 N=2 evidence，因此 MVR 仍 `NOT_EVALUATED`，M6 release 保持关闭。

- 2026-08-19：P2-M5-T01 candidate `a39d9763f3a907bc7824994cd92fbe5c319b3acc` 的 run
  `32176583182` 三 jobs 全绿。七项 artifacts 精确绑定 candidate、`0013_warp_plan_authority` 与既有
  OpenAPI digest；Phase 1/M1/M2/M3 evidence 为 1/98/52/46 tests 且零 failure/skip，Gitleaks 为零
  results。Principal 接受 T01，M5 前向进入 `EXECUTING` 并只开放 T02/T04 的无冲突实现；T03 仍等待
  两者 contract names 集成。technical Gate、MVR result 与 M6 entry 均未通过。

- 2026-08-19：P2-M5-T02 candidate `9fb09fbc922406d5881950f355629c3108656a24` 的 run
  `32178257563` 三 jobs 全绿；七项 artifacts 精确绑定 candidate、`0013_warp_plan_authority` 与既有
  OpenAPI digest，Phase 1/M1/M2/M3 为 1/98/52/46 tests 且零 failure/error/skip，Gitleaks 为零 results。
  Principal 接受 immutable evaluation policy、split authority、per-dimension cluster-adjusted N、isolation
  evidence 和 technical/MVR 分离契约。T04 仍需 tracked acceptance，T03 在两者 contract integration 前
  保持 dependency-gated；threshold、holdout、dimension promotion、MVR、production geometry、真人处理与
  QuestionBank release 均未获批准。

- 2026-08-19：P2-M5-T04 candidate `c80f32f6adb0c1ed17ac14e97b5552739abec57c` 的 run
  `32179065826` 三 jobs 全绿；七项 artifacts 精确绑定 candidate 与 `0013_warp_plan_authority`，既有
  Phase 1/M1/M2/M3 回归为 1/98/52/46 tests 且零 failure/error/skip，Gitleaks 为零 results。Principal
  接受第一方 exact SHA + `phash-dct-nearest-v1` 64-bit signature/Hamming core；它没有 near-duplicate
  threshold，threshold 预注册前不得自动拒绝候选。T02/T04 contract 已集成并只开放 T03 的冻结
  `0014_m5_eval_authority` PostgreSQL authority；T05–T08、MVR、production geometry、真人处理、M6 与
  QuestionBank release 继续关闭。

- 2026-08-19：P2-M5 T02/T04 contract acceptance checkpoint
  `8640879c586afcbf72c9ea1e67bef82992525bdd` 的 run `32179662032` 三 jobs 全绿，七项 artifacts 精确绑定
  checkpoint 与 `0013_warp_plan_authority`，既有回归零 failure/error/skip、Gitleaks 零 results。当前仅
  T03 的冻结 `0014_m5_eval_authority` schema/transaction 实现获授权；M5 technical Gate、MVR、T05–T08、
  production geometry、真人处理和 M6 继续关闭。

- 2026-08-19：P2-M5-T03/R01 本地候选建立前向 `0014_m5_eval_authority` PostgreSQL authority，并由
  PostgreSQL 重算 policy/signature/isolation digest 与派生结论，绑定 M4 transform/variant QA，序列化
  cluster membership/finalization/split races。Principal 复核还修复四个旧 migration-head 断言和
  exact-duplicate loser 在 trigger/unique constraint 两种合法 PostgreSQL 路径下的测试稳定性。Fresh
  14 项 authority tests、并发十连跑、566 项 Linux API/Worker collection 的完整执行、fresh/
  `0013→0014→0013→0014`、Alembic zero drift、Ruff、124-source strict mypy、pnpm/contracts/build 均通过。
  当前仅为 `READY_FOR_TRACKED_EVIDENCE`；same-SHA 三 jobs/七 artifacts 未核验前不得接受 T03 或开放 T05，
  threshold、holdout、MVR、production geometry、真人处理、M6 与 QuestionBank release 继续关闭。

- 2026-08-19：P2-M5-T03/R01 candidate `277c69aad491e31241142990d94b843fd7b18700` 的 run
  `32186155269` 三 jobs 全绿；七项 artifacts 可读、未过期并绑定 exact SHA、`0014_m5_eval_authority`
  与 unchanged OpenAPI。Phase 1/M1/M2/M3 为 1/98/52/46 tests 且零 failure/error/skip，Gitleaks 零
  results，Docker/Celery 无真实 error，license/SBOM 可读。Principal 接受 T03/R01 并只开放 T05
  calibration/cohort/preregistration；T06–T08、technical Gate、MVR、production geometry、真人处理、M6
  与 QuestionBank release 继续关闭。

- 2026-08-19：T03 acceptance checkpoint `6efd2dce4f4205d76af156c65b78f36f6910f52b` 的 run
  `32186910142` 三 jobs 与七 artifacts 全绿。T05 随后重建现有四项 canonical identity split：它们全部
  已被 M4 使用，因此在 M5 只能归入 `M4_SEEN`，M5 calibration/holdout effective N 均为 0；当前仅有
  一个 `EXPERIMENTAL jaw_width`，没有 READY dimensions、三 region groups、阈值分布或新 ontology/policy
  authority。T05 本地结论为 `FURTHER_RESEARCH`，全局 MVR 保持 `NOT_EVALUATED`；不得用 M4 N=2 重标
  M5 holdout，不创建阈值/最终 cohort，不开放 T06。补足数据与维度必须走前向 research change control，
  不能包装成 Repair。

- 2026-08-19：P2-M5-T05 candidate `e46d7a9d19eee536c2f57cac6de224cccf27f2be` 的 run
  `32187946640` 三 jobs 全绿；七项 artifacts 精确绑定该 SHA、`0014_m5_eval_authority` 与 unchanged
  OpenAPI，Phase 1/M1/M2/M3 为 1/98/52/46 tests 且零 failure/error/skip，Gitleaks 零 results。
  Principal 接受 T05 的 `FURTHER_RESEARCH` stop decision；P2-MVR-v1 保持 `NOT_EVALUATED`。全部四项
  canonical identities 均为 `M4_SEEN`，M5 calibration/holdout effective N 为 0，且不存在四个 READY
  dimensions、三个冻结 region groups 或 threshold calibration distributions。T06–T08、M6、production
  geometry、真人处理与 QuestionBank release 保持关闭；补足 evidence 必须走前向 research change
  control，不能包装成 Repair。

- 2026-08-19：ADR-042 / `CC-P2-M5-01` 为 T05 `FURTHER_RESEARCH` 建立唯一前向 evidence-expansion
  path，不修改旧 evidence、不包装为 Repair 或 T09/T10。Stage A candidate
  `9993e019ad4267dd2521c2988b881bfdf0ec1558` 的 run `32189725291` 三 jobs 与七 artifacts 全绿；
  Principal 只开放 Stage B 的 12 个 calibration-only accepted identities、18 次总 attempt、单项最多一次
  retry、concurrency 1。Stage C–E、final holdout、T06–T08、MVR、production geometry、真人处理、M6 与
  QuestionBank release 继续关闭。官方 MediaPipe wheels 仍 rejected；下载授权不改变 adoption、license、
  distribution、production 或 real-user-processing status。

- 2026-08-19：`P2-M5-R02` 关闭 Stage A acceptance checkpoint 的测试组合死锁：Phase 1 同步 HTTP vertical
  test 原先同时向 live Celery 投递 data-rights/asset-deletion 工作并直接执行相同服务，导致 teardown
  `TRUNCATE` 与后台 transaction 竞态。修复仅在该测试内使用既有 recoverable no-broker dispatchers；20/20
  live PostgreSQL/Redis/Celery replay 通过且 worker 收到零任务。Candidate
  `9946a43d771c2cb27d764243bda047e943ad5c99` 的 run `32192316257` 三 jobs 与七项 exact-SHA artifacts
  全绿，Python 为 567 PASS/1 个既有 optional skip，Gitleaks 零结果。Principal 接受 R02 并恢复 Stage B 为
  `EXECUTION_READY`；12 identities、18 attempts、单项一次 retry、concurrency 1 边界不变，Stage C–E、MVR、
  production geometry、真人处理、M6 与 QuestionBank release 继续关闭。

- 2026-08-19：Project Owner 前向授权后续任务按需下载依赖，包括 MediaPipe 0.10.35 exact Windows/Linux
  wheels 与 exact Face Landmarker bundle；下载必须进入 Git 忽略的 private cache/research namespace，且不等于
  adoption、license approval、distribution、production 或 real-user facial processing approval。当前 Stage B
  已有 accepted source-built Vision runtime，不因授权而无目的重复下载官方 wheels。
- 2026-08-19：`CC-P2-M5-01-B` 本地 calibration wave 在冻结的 12 identities / 18 attempts / 单项一次 retry /
  concurrency-one envelope 内，以 12 attempts、零 retry 获得 12 项 admitted、normalized、exactly-one-face、
  478-landmark、human categorical hard-gate PASS 的 synthetic-only identities；真实 PostgreSQL 幂等重放后仍为
  12 admissions / sources / passed QA runs / bank-independent identities。Exact duplicate 为 0；第一方 pHash 66
  pairs 的观测最小 Hamming distance 为 12，但未选择 near-duplicate threshold。`cal-b-06` 保留
  `REQUESTED_CELL_VISUAL_MATCH_WEAK` 诚实 evidence。当前只到 `LOCAL_PASS_PENDING_TRACKED_EVIDENCE`；Stage C–E、
  T06–T08、MVR、production geometry、真人处理、M6 与 QuestionBank release 继续关闭。

- 2026-08-19：`CC-P2-M5-01-B` candidate `7282094406b9754368709f543c4fda54b2e57490` 的 run
  `32197326163` 三 jobs 全绿；七项 artifacts 可读、未过期并绑定 exact SHA、`0014_m5_eval_authority` 与
  unchanged OpenAPI。Phase 1/M1/M2/M3 为 1/98/52/46 tests 且零 failure/error/skip，Gitleaks 零
  results。Principal 接受 Stage B，只开放 Stage C exact candidate-manifest 编写；在该 manifest tracked
  acceptance 前 measurement/transform/threshold calibration 仍关闭，Stage D–E、T06–T08、MVR、production
  geometry、真人处理、M6 与 QuestionBank release 继续关闭。

- 2026-08-19：Stage B acceptance checkpoint `0a46f0f6889b4fd0e05cec9b78f66a20c8c56ef1` 的 run
  `32197913261` 三 jobs 与七 artifacts 全绿，只开放 Stage C premeasurement candidate-manifest。本地
  manifest candidate digest 为 `eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4`，
  冻结 6 个 candidates、4 个 non-sensitive region groups、精确 landmark/formula、source-relative Gaussian
  plan、`15k/30k ppm`、双平台三次 repeat、全 control/missingness/artifact/negative-control 规则。
  尚未读取或执行 Stage C measurement/transform；tracked acceptance 前继续关闭。

- 2026-08-19：Stage C premeasurement manifest candidate `b0b60eb29336d74a0f4c7628c9d1d1458d11d3f9`
  的 run `32199176469` 三 jobs 与七 artifacts 全绿；证据绑定 exact SHA、`0014_m5_eval_authority`、
  unchanged OpenAPI，Phase 1/M1/M2/M3 为 `1/98/52/46` 且零 failure/error/skip，Gitleaks 零结果。
  Principal 接受 digest `eb202109...` 的不可变 manifest，并仅开放其精确 Stage C execution；threshold、
  READY、Stage D-E、T06-T08、MVR、production geometry、真人处理、M6 与 QuestionBank release 继续关闭。

- 2026-08-19：`CC-P2-M5-01-C` candidate `042f77e4b6708be827f2033a9740e348ae778f69` 的 run
  `32237678569` attempt 1 在此前产品/迁移/Python/TS 步骤通过后，因 Playwright Chromium 下载超过 60 分钟
  无 runner heartbeat 而取消；same-SHA attempt 2 在 4m53s 内三 jobs 全绿。七 artifacts 绑定 exact SHA、
  `0014_m5_eval_authority` 和 unchanged OpenAPI；Phase 1/M1/M2/M3 为 `1/98/52/46` 且零
  failure/error/skip，完整 Python 为 582 pass/1 个既有 optional private-runtime skip，浏览器 5/5，Gitleaks
  零结果，Docker/Celery 无 execution failure。Principal 接受 Stage C 的 `FURTHER_RESEARCH` stop：六个候选
  均有 failed/missing case，complete-case eligible 为 0/4；不得选 threshold、宣称 READY 或开放 Stage D/E、
  T06–T08、MVR、production geometry、真人处理、M6 或 QuestionBank release。继续研究必须走新的前向
  change control。

- 2026-08-19：`P2-M5-R03` 通过 exact job log 将 run `32237678569` attempt 1 的粗略“Chromium 下载停滞”
  修正为 `TRANSIENT_EXTERNAL_SYSTEM_DEPENDENCY_ACQUISITION_STALL`：组合 Playwright 步骤最后停在 Ubuntu
  repository fetch，未出现 Chromium binary download、checksum、launch 或 Browser Integration 失败。
  R03 将 `install-deps chromium` 与 `install chromium` 分离；系统依赖只执行一次且 hard timeout 600 秒，
  browser download 最多 3 次、每次 600 秒、30/60 秒退避、官方源、三次失败即 fail closed，并上传仅含版本、
  时间、耗时、状态和安装输出的 evidence。Candidate `d3f0597019bc0b4de37a058159a74a26ea1fc046` 的 run
  `32245119767` 三 jobs 全绿；依赖/下载/browser 为 20/17/20 秒，八 artifacts 可读且 exact-SHA bound，
  Gitleaks 零结果。该修复不改变 Browser Gate、依赖锁、Stage C `FURTHER_RESEARCH` 或任何后续 Gate。

- 2026-08-19：ADR-047 / `CC-P2-M5-02-G` diagnosis-only governance candidate
  `137157c41e7b1436ae47fe7dfcf34a7127789166` 的 run `32267510703` attempt 1 三 jobs 全绿，八 artifacts
  可读且 exact-SHA bound，独立安全与 Sol final review 均 PASS。Principal 接受冻结的八阶段
  `p2-m5-cc02-terminal-taxonomy-v1`、Windows runner/child-process pre-read outbound deny、576-transform/
  604-Vision ceiling、零 generation/retry/threshold 和 evidence-reconstruction stop。旧 Stage C
  `FURTHER_RESEARCH`、0/4 eligibility 与旧 evidence 保持不可变；当前只允许准备 CC02-A 的独立 bounded-task
  contract，不代表 harness 已实现或 private input、CC02-B–E、Stage D/E、T06–T08、MVR、M6 已开放。

- 2026-08-19：`CC-P2-M5-02-A` bounded-task contract candidate
  `d8659ae88fb32c99220d522fc6dbf94a8fc588ac` 的 run `32271571196` attempt 1 三 jobs 全绿，八 artifacts
  可读、未过期且 exact-SHA bound，独立安全与 Sol final review 均 PASS。Principal 接受 contract 并仅将冻结的
  新 diagnostic harness 实现设为 `EXECUTION_READY`；harness 尚未实现或执行，private input、CC02-B–E、Stage
  D/E、T06–T08、MVR、M6 继续关闭，旧 Stage C `FURTHER_RESEARCH` 与 0/4 eligibility 不变。

- 2026-08-29：P2-M5-R46 candidate `31f4ecdb598e0796c1939c6b17f5ce70c07b5793` 的 same-SHA run
  `33250016931` 三 jobs 全绿，八个 artifact families/十一项文件、冻结回归、Gitleaks、Browser Integration、
  独立 Security 与 Sol High final review 均通过，Principal 接受 R46。随后对 R43-Q01 所需 CC05-A exact
  task-scoped receipt/registry handle 的有界恢复得到 `NO_EXACT_TASK_SCOPED_HANDLE`；按 ADR-049 记录
  `EVIDENCE_LOCATION_LOST`，禁止重复搜索、重建 legacy evidence、创建替代 root 或要求 Owner 重新上传。
  `CAL-REQ-002` 保持未消费，31/31/62 资源账本不变；恢复只接受新的、显式且可恢复的 task-scoped authority。

- 2026-08-29：CC05-B candidate `40f7c6bee88196e8730f8df1a521c46775b77f5c` 的 same-SHA run
  `33251230684` 三 jobs、八个 artifact families/十一项文件、冻结回归、Gitleaks、Browser Integration、
  独立 Security 与 Sol High final review 均通过，Principal 接受其 `EVIDENCE_LOCATION_LOST` closure。
  `CC-P2-M5-05-C0` 以前向零生成 authority 授权仅在其自身全部 Gate 被接受后建立新的 epoch-4 私有状态；
  epoch-3 保持不可变历史且禁止搜索、复制、重建或复用，C0 不创建 private root/Prompt/ledger、不满足恢复
  predicate，也不消费 `CAL-REQ-002`。后续 CC05-C 必须创建全新版本/摘要及可恢复 exact task-scoped receipt，
  资源账本继续为 `31/31/62`，M5 technical Gate、MVR、M6、production 和真人处理继续关闭。
