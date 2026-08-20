# ADR-049：Principal 管理的私有输入委派

## Status

Accepted — 2026-08-20

Change control: `CC-PROJECT-PRIVATE-INPUT-01`

## Context

Project Mirror 的 bounded task 可能需要 Git 外的模型、报告、fixture、合成图片或其他受控输入。此前各任务
分别描述 private path、digest、redaction 和 cleanup，但没有统一规定 Owner 是否需要向每个 sub-agent 重复
交接，也没有冻结跨 task、跨 Agent 的 non-propagation 语义。CC02 又要求 ADR-048 的 single trusted writer、
exclusive custody、exactly one builder invocation 和 Principal immediate snapshot，不能为了形式上的委派而放宽。

## Decision

- 接受 `OWNER -> PRINCIPAL -> SUB-AGENT` 作为长期 private-input authority flow。Owner 对未变化的授权用途只向
  Principal 交接一次；Principal 成为 `PRIVATE_INPUT_CUSTODIAN`，负责分类、authority/digest/type/scope 验证、
  custody、最小 handoff、cleanup 和最终 Gate 判断。
- 冻结四项 invariant：`PRIVATE_INPUT_OWNER_HANDOFF_ONCE`、`SUBAGENT_NO_PRIVATE_DISCOVERY`、
  `PRIVATE_INPUT_NON_PROPAGATION`、`PRINCIPAL_RETAINS_AUTHORITY`。
- 输入按最严格适用级别分类为 `PUBLIC_REPOSITORY_INPUT`、`TRACKED_INTERNAL_INPUT`、
  `PRIVATE_NONSENSITIVE_INPUT`、`PRIVATE_SENSITIVE_INPUT`、`SECRET_CREDENTIAL` 或
  `REAL_USER_SENSITIVE_INPUT`。Secret value 不得以文本或文件交给 sub-agent；real-user sensitive input 继续受
  Legal/Consent/Privacy/Security Gate，本文不授予新用途。
- Private registry 只存在于内存或 Git 外；durable evidence 只记录 opaque input ID、digest、authority 和状态，
  不记录绝对 private path、Prompt 或 secret。
- 每次委派必须有 task/agent/input/purpose/digest/max-bytes/operation/output/network/cleanup 的显式 packet。
  授权不跨 sibling、task 或递归 Agent 传播。缺少 packet 内输入时返回
  `PRIVATE_INPUT_SCOPE_EXPANSION_REQUIRED`，不得枚举父目录、扫描磁盘或猜路径。
- Handoff 优先使用 runtime 提供的 task-scoped handle；其次为 exact read-only reference、scoped environment、
  byte-identical temporary copy；若无法证明 least privilege，由 Principal 执行敏感步骤并只交付 redacted output。
- 临时 copy 必须位于 repository 外或明确 ignored 的 `.private-handoff/`，使用不可预测 task directory、复制后
  复核 SHA-256、尽可能 read-only，并在 task 结束后确认删除。Shared-workspace ignore 不是 OS sandbox；不能把
  它描述为对恶意同凭据进程的防御。
- Delegation 不委派 architecture、Gate、consent、production approval 或 scope-expansion authority。Worker PASS
  仍只是证据。
- Principal 或 sub-agent 创建的 private evidence 必须登记到 Git 外的 `PRINCIPAL_PRIVATE_OUTPUT_REGISTRY`，至少
  包含 input/output ID、creating task/agent、opaque locator、expected/actual digest、bytes、authority、retention、
  allowed future tasks、custody 和 cleanup status。Sub-agent 结束前必须把 authority 与可恢复 locator 交回
  Principal；Principal 不得把自己或 worker 创建的 private output 重新归类为 Owner upload obligation。
- 冻结 `PRIVATE_OUTPUT_LOCATION_MUST_BE_RECOVERABLE`、`SUBAGENT_HANDOFF_IS_PRINCIPAL_RESPONSIBILITY` 和
  `PRIVATE_BYTES_STAY_OUT_OF_GIT`。Locator 留在 registry，不进入 tracked docs；tracked evidence 只记录 opaque
  ID、digest、authority、retention 和状态。

## Current CC02 application

ADR-048 保持原样。CC02 两份 legacy report 是 prior Principal Stage C task-owned private outputs，不是新的 Owner
upload。Principal 必须从原 task receipt/registry 恢复 locator，在不打印路径的情况下验证 presence/authority，
建立 ADR-048 custody，并选择唯一 executor。当前 shared-workspace sub-agent boundary 不能证明 ADR-048 的即时
Principal snapshot，因此默认 `PRINCIPAL_EXECUTES_SENSITIVE_STEP`。Security/final reviewers只能收到 tracked
manifest、tracked preregistration 和 redacted status。只有 bounded task-state recovery 失败时才可报告
`EVIDENCE_LOCATION_LOST`；不得搜索磁盘、重跑 Stage C 或要求 Owner 重建 Principal 自己的输出。

## Alternatives Considered

- Owner 向每个 Agent 重复路径：拒绝，扩大 capability 传播和人为泄漏面。
- 给所有 Agent 一个 private root：拒绝，违反 least privilege、no discovery 和 non-propagation。
- 只靠 `.gitignore`：拒绝，它只防止普通 Git discovery，不是访问控制或 cleanup 证明。
- 强制所有敏感步骤由 sub-agent 执行：拒绝，可能破坏更严格的 task-specific custody contract。

## Consequences

- 新增通用 protocol、routing 规则和一个仅用于 synthetic policy/recovery 验证的第一方 reference state machine。
- Reference state machine 不创造 Codex runtime sandbox，也不授权真实 private input。具体 handoff 仍需 Principal
  根据 runtime 能力和 task-specific ADR 建立。
- 不新增 dependency、schema/migration、OpenAPI、Provider、模型、真实数据处理或 public API。

## Security / Privacy / Data / License

Private bytes、路径、Prompt、secret、object key 和 Provider payload 不进入 Git、普通 CI artifact、MEMORY 或
无关 Agent context。任何 digest/type/scope/custody mismatch 都 fail closed。没有新增 OSS、模型、数据或许可
结论。

## Validation

- Synthetic tests覆盖 Owner→Principal→Terra、unauthorized sibling、cross-task reuse、missing input、digest
  mismatch、cleanup 和 secret/real-user fail-closed。
- `.private-handoff/` 必须被 Git ignore；workflow 不得引用该 namespace；ADR-048 blob 必须保持不变。
- Ruff、strict mypy、targeted pytest、format/diff/source scan 和 same-SHA CI 仍为 acceptance evidence。
