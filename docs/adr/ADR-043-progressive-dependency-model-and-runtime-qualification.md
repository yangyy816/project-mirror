# ADR-043：依赖、模型与原生运行时的渐进式资格治理

## Status

Accepted — 2026-08-19

Change control: `CC-GOV-QUAL-01`

## Context

Project Mirror 过去对重要 dependency、model、weight、native runtime、research algorithm、Provider SDK、
视觉/编辑引擎和 Agent runtime 候选采用了严格的逐项 Gate。该做法保护了来源、许可、隐私、安全、
可复现性和 production fail-closed，但容易让仅用于 isolated synthetic PoC 的候选过早承担完整生产资格成本。

这项变更不是降低质量，也不追溯改写已冻结证据。资格强度应由当前用途、数据敏感度、runtime/分发范围、
网络与 telemetry、不可逆影响和生产风险决定；Research 结论不得自动提升为 Internal Engine 或 Production
批准。

## Decision

- 所有重要候选必须同时声明 `QUALIFICATION_TIER`、`CURRENT_STATUS` 和 `APPROVED_SCOPE`。禁止只写含糊的
  `approved`。
- 采用三层用途模型和六个主状态：

  ```text
  CANDIDATE
  → RESEARCH_QUALIFIED
  → INTERNAL_ENGINE_CANDIDATE
  → APPROVED_FOR_INTERNAL_ENGINE
  → PRODUCTION_CANDIDATE
  → PRODUCTION_APPROVED
  ```

- 任一阶段可前向进入 `REJECTED`、`FURTHER_RESEARCH`、`DEFERRED_EXTERNAL_DEPENDENCY`、
  `LICENSE_REVIEW_REQUIRED`、`SECURITY_REVIEW_REQUIRED`、`PRIVACY_REVIEW_REQUIRED` 或
  `PRODUCTION_BLOCKED`。失败证据保留；不允许把 Research 直接提升为 Production。
- `RESEARCH_QUALIFIED` 只授权受控 isolated research。最低证据包括 exact source/version/URL、SHA-256、
  code/model/weight/data 条款分离、基础 license/security/privacy review、synthetic-only 或 non-sensitive
  fixtures、bounded Linux isolated runtime、resource/time budget、network deny/capture 或显式 allowlist、
  no telemetry/credentials/real-user data/public endpoint/production config，以及成功和失败 attempt evidence。
  它默认不要求 production image、全部平台 byte identity、production SLA 或真实用户处理资格。
- `APPROVED_FOR_INTERNAL_ENGINE` 只授权明示的 private、synthetic-only、non-production、non-real-user、
  phase/milestone scope。除 Research Gate 外，还要求第一方 port/adapter、无第三方 domain authority、exact
  runtime/artifact hashes、Linux/Docker clean reproduction、declared determinism、same-platform reproducibility、
  适用时 Windows functional compatibility、private SBOM、dependency/license/vulnerability disposition、
  negative controls、bounded/zero-network proof、resource/retry/recovery/integration tests 和 production
  fail-closed。若某 Milestone 已冻结更严格跨平台标准，则不得用本 ADR 放宽。
- `PRODUCTION_CANDIDATE` 只表示候选进入完整生产资格审查。它还需要 production runtime/image、全部声明支持
  平台、完整 transitive SBOM/license/notices、code/model/weight/data/commercial terms 分离、漏洞处置、
  security/privacy/telemetry/region/retention/training/deletion/subprocessor review、secret/network controls、
  performance/concurrency/cost/failure/failover/rollback/observability/incident/backup/recovery、production-like
  staging、same-SHA CI/artifacts 和独立审查。
- `PRODUCTION_CANDIDATE` 不等于启用。只有对应 Phase 的 Principal final Gate 明确记录
  `PRODUCTION_APPROVAL: GRANTED`，候选才可进入 `PRODUCTION_APPROVED`；真实 facial data 还必须独立满足
  Legal/Consent/PIPIA/Security Gate。
- exact provenance、unknown facts remain `NULL`、synthetic-only、no sensitive inference、no beauty score、
  Provider/Adapter boundary、PostgreSQL authority、no arbitrary URL、no unbounded network、no hidden telemetry、
  no credential、no unapproved model weight、no silent dependency adoption、no threshold relaxation after
  holdout、no fake PASS 与 production fail-closed 对所有层永久适用。
- 既有证据可复用，但批准范围必须按新用途重新声明。任何 source、version、artifact、patch、toolchain、
  dependency closure、model、data、network、license、privacy class、distribution 或用途变化，都按既有 trigger
  重新评估。

## Grandfathering

- P2-M3 已冻结的 Windows/Linux reproduction、SBOM、license、vulnerability、zero-egress 和 private model
  evidence 保持完整有效；不重开、不降级、不改写。它归类为 `LEGACY_STRICT_QUALIFICATION`，并且
  `EXCEEDS_CURRENT_RESEARCH_MINIMUM`。
- P2-M4 OpenCV 5.0.0 bounded source closure 保持 scope-specific
  `APPROVED_FOR_PRIVATE_SYNTHETIC_M4`。该结论满足其已记录的 internal-engine 用途，不扩展到 production、
  distribution、真实用户处理或其他 Phase。
- 当前 P2-M5 的 manifest、complete-case、threshold、holdout、MVR 和 stop rules 均不变。ADR-043 不把 Stage C
  的 `FURTHER_RESEARCH` 改写为 PASS，也不打开 Stage D/E、T06–T08 或 M6。

## Alternatives Considered

- 所有 PoC 一开始都执行完整 production qualification：拒绝，会让早期淘汰候选承担与用途不相称的成本。
- 仅记录 `approved/rejected`：拒绝，无法表达用途、数据和部署范围。
- Research PASS 自动进入 internal 或 production：拒绝，会绕过供应链、隐私、安全与部署 Gate。
- 追溯性降低 M3/M4 证据或当前 M5 Gate：拒绝，违反 forward-only change control。

## Consequences

- 新候选报告、PoC contract、Milestone protocol 和 acceptance evidence 必须使用本 ADR 的层级与 mandatory
  fields；已有历史文档无需批量重写。
- 早期 isolated PoC 可以在不声称生产就绪的前提下更快停止、替换或晋级；越接近 internal/production，
  资格强度和独立审查随风险增加。
- 本变更只修改治理文档，不新增 dependency、model、binary、schema、migration、OpenAPI、network path、
  production runtime 或真实用户数据处理。

## Security / Privacy / Supply Chain

Research tier 仍禁止真实用户数据、production credentials、未知权重、未知许可证、隐藏 telemetry、任意或
无界网络和不可信二进制。Internal Engine approval 仍限定为 private synthetic scope；Production Candidate
仍不能替代法律、隐私、商业条款和 Principal production approval。

## Testing Implications

治理变更必须通过 Markdown formatting、link/status/conflict scan、dependency/model manifest negative scan、
`git diff --check` 和现有 same-SHA CI。未来候选验收必须证明层级、范围、禁止范围和 promotion Gate 均明确。
