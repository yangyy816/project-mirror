# ADR-050：P3–P7 Algorithmically Faithful Prototype Platform Demo Track

## Status

Accepted — 2026-08-23

Track: `DEMO_PROTOTYPE`

Plan: `P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1`

Change control: `CC-P3-P7-DEMO-01`

## Context

Project Owner 授权在固定的正式祖先上建立与 P2-M5 formal track 隔离的本地原型平台，用真实 PostgreSQL、
Redis/Celery、FastAPI、Next.js、对象存储和 private synthetic runtime 运行 P3–P7 核心算法。原型用于证明算法、
持久化、evidence、编辑、重建和 next-session recall 确实工作，不用于宣布正式 P3–P7、真实用户有效性或生产资格。

Demo base 固定为 `d134517fa97132b180a82c69c617b8f65d3b282e`。创建 Demo worktree 时 formal track 已前进并带有其他
任务的未提交变更；这些 bytes 不能成为 Demo base。D00 已在 Git 外一次性 sandbox 中完成，并由独立 Sol High
只读审查建议 `GO`，Principal 仅据此开放 D01-A。

Owner 随后修订“禁网”语义：核心执行应禁止公网出站，而不是禁止 localhost 或 Docker internal network。
已接受 runtime/model/dependency artifact 真正缺失时，可在核心离线验证前从已批准来源执行一次有界 acquisition。

## Decision

### 1. 完整原型范围

- 保留计划中的全部 prototype persistence、`/api/v1/demo/*`、D01–D12、P3–P7 核心算法、Worker、Web、
  PostgreSQL、Redis/Celery、OpenAPI、generated TypeScript、Playwright 和 evidence chain。
- 不允许以单页、静态 Mock、预录输出、fixture 驱动核心算法、单一 geometry dimension 或 golden path 代替完整平台。
- 未实现能力返回结构化 `501 CAPABILITY_NOT_IMPLEMENTED`；Generative Provider 保持
  `CAPABILITY_UNAVAILABLE`，Makeup 保持 `DEFERRED_WITH_EXPLICIT_REASON`，入口和错误语义仍需存在。
- 所有 Demo P3–P7 Gate 必须标记 `TRACK=DEMO_PROTOTYPE`。Demo 不改变正式 milestone、migration head、
  schema authority、P3–P7 maturity 或 production authorization。

### 2. 分支、worktree 与 migration 隔离

- Demo branch 为 `codex/p3-p7-core-demo`，worktree 为 `D:\p-p3-p7-core-demo`，branch point 必须保持精确
  `d134517fa97132b180a82c69c617b8f65d3b282e`。
- 不复制 formal worktree 的 tracked/untracked 未提交内容，不读取受保护 `.tmp/`，不 cherry-pick 未接受 ADR。
- 唯一允许的 post-base 安全重放是从 `b179c193b3a719142139b6d42e5be0c22ef4b225` 单独重放
  `requirements.lock` 的 `pip==26.1.2` 到 `pip==26.2.1`；不带入该提交的日期行或 P2-M5 文档。
- prototype migration 固定为 `demo_0001_p3_p7_core`，down revision 为 `0014_m5_eval_authority`，并声明：

  ```text
  PROTOTYPE_MIGRATION: TRUE
  FORMAL_PHASE_AUTHORITY: FALSE
  DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
  ```

- 正式吸收必须从当时 formal migration head 新建 forward migration，并另写 promotion/conversion strategy。

### 3. D00-A controlled recovery

- D00-A 仅在已接受 runtime/model/dependency artifact 缺失时开放一次 bounded acquisition；来源、版本、
  expected checksum、最大 bytes、attempt、time 和 output scope 必须预注册。
- 只允许批准来源，不允许 arbitrary URL；下载后必须验证 digest/size/authority，保存到 Git 外 private custody。
- acquisition 阶段不得调用 production Provider，不得处理真实用户数据，不得把 bytes、locator 或凭据写入 Git、
  普通 CI artifact、Prompt 或日志。
- D00-A 完成后冻结 local runtime/assets，再进入 D00-B。本次 D00 没有发生 acquisition；计数为 `0`。

### 4. D00-B offline core execution

统一网络语义为：

```text
PUBLIC_INTERNET_EGRESS_DISABLED
NOT ALL_NETWORK_DISABLED
```

- 必须保留 localhost、Docker internal network、PostgreSQL、Redis、Celery、Web↔API 和 private object storage。
- M3 Vision、M4 GeometryTransform、PostgreSQL、Redis、Celery、FastAPI、Next.js 和 private object storage 的核心
  验证窗口必须在 `PUBLIC_INTERNET_EGRESS: DENIED` 下工作。
- 代理配置不得进入 D00-B core process/container environment。任何 P3–P7 core runtime 尝试公网依赖时立即记录
  `EXTERNAL_RUNTIME_DEPENDENCY_FOUND` 并 fail closed，不得静默联网。
- Generative Provider 不可用不阻塞 deterministic P3–P7 core；它不得被伪造为可用。

### 5. Authority、custody 与真实性

- PostgreSQL 是 Demo authority；原始 Asset immutable，派生状态必须可从 append-only/versioned evidence 重建。
- 所有 private runtime、model、synthetic image、landmark、measurement、report 和 receipt 由 Principal 的 Git 外
  `PRINCIPAL_PRIVATE_OUTPUT_REGISTRY` 托管。tracked evidence 只记录 opaque ID、digest、authority 和状态。
- sub-agent 不得发现或枚举 private storage；每次只消费 task-scoped read-only handle。无法证明 least privilege
  时执行 `PRINCIPAL_EXECUTES_SENSITIVE_STEP`。
- Demo synthetic verifier 的 identity 结论只表示结构约束和 non-target drift；不得称为真实 biometric identity
  preservation。

### 6. D01 checkpoint 和任务所有权

- D01-A、D01-B、D01-C 分别独立接受。D01-A 接受前不得创建 migration、ORM、公共 Demo API 或 Web。
- migration、models、OpenAPI/generated client、Worker registration、Web、private registry、MEMORY 和 acceptance
  state 均保持单一所有者。
- 本 Track 的逻辑 Principal 为 task-scoped `TERRA_HIGH_PRINCIPAL`；项目配置不写顶层 Principal model 键，保留
  Owner 在 Codex UI 的选择权。每次证据区分 `REQUESTED_MODEL`、`STATIC_CONFIG` 与 `RUNTIME_VERIFIED`；当前线程
  model metadata 未暴露时必须写 `NOT_EXPOSED`。
- 默认最多一个 active sub-agent，硬上限两个；OpenAI 官方配置参考明确
  `agents.max_concurrent_threads_per_session` 不含 primary thread，因此本 Track 将该值设为 `2`。
- 每个 bounded task packet 固定 `CAN_DELEGATE=false`；这是一项授权和审查约束，不冒充底层工具已被物理移除。

### 7. Security 和发布边界

本 Track 只要求 ADR-050、Demo Fast Track Contract、持续风险登记、Gitleaks、localhost-only ingress、synthetic-only、
no production secret、no arbitrary public network、immutable original、private bytes outside Git、scoped diff 和
D12 lightweight Principal boundary review。

production PIPIA、production threat model、完整 supply-chain qualification、cloud hardening、真实用户批准、
public deployment、production Provider/credential、penetration test 和完整 production platform qualification 均为
`DEFERRED_FOR_FORMAL_PHASE`，不得写成 PASS。

## D00 disposition

```text
D00_STATUS: GO
D00_REVIEW_PACKET_SHA256: a987dcec3580e2baa02cc8c783dd15a94804651e81d76b8081de6777b28539be
D00_PRINCIPAL_DECISION_SHA256: 5f7734a51ae1f761b36b7375578e16fb6c26c5fd6d274ef3aff708d43b3797ac
D00_ACQUISITION_COUNT: 0
D01_A: AUTHORIZED
D01_B_D12: NOT_AUTHORIZED_UNTIL_PREDECESSOR_ACCEPTANCE
```

D00 只证明关键依赖与执行可行性。它不证明 D02 的 16-pair QA、API/Worker 端到端算法集成、D01–D12 完成、
formal P3–P7 PASS、P2 READY、真实用户有效性或 production readiness。

## Alternatives Considered

- `ALL_NETWORK_DISABLED`：拒绝，它会破坏本地 Web/API、Docker data plane 和 Worker 拓扑，且不对应风险目标。
- 运行时按需下载：拒绝，会引入隐藏公网依赖和不可重放 core execution。
- 直接使用 formal worktree dirty bytes：拒绝，会污染固定 base 并破坏 evidence attribution。
- 直接将 `demo_0001` 晋级 formal migration：拒绝，会造成 revision 和 authority 冲突。
- 缩减为最小 happy path：拒绝，不满足 algorithmically faithful prototype platform 目标。

## Consequences

- D01–D12 可以在明确非生产边界内实现完整本地原型，但每个 checkpoint 必须绑定实际 diff、验证和独立审查。
- 日程是 operational target；未达性能目标必须记录实际数据，不得通过删除算法或 Mock 掩盖。
- 任何 mandatory Gate 未运行时为 `NOT_VERIFIED`；不得用计划、D00 或 reviewer 文本替代执行证据。
- 正式 worktree 和 formal migration authority 预期不发生变化；D01-A 与 D12 分别重新核验。

## Validation

- D00 在精确 base sandbox 中验证 M3 三次 1 face / 478 landmarks deterministic replay、M4 deterministic
  transform、三项 geometry candidate directionality、五服务本地拓扑与公网出站拒绝；独立 Sol High review 为 PASS。
- D01-A 必须验证 Demo clean/base/formal isolation、official-worktree private runtime load、TOML schema、Agent role
  discovery、Gitleaks、format/diff 和风险/合同一致性，并由新的独立 Sol High reviewer 接受。
- 后续数据库、OpenAPI、Worker、Web、算法和 Playwright 证据只能在其各自 checkpoint 产生。
