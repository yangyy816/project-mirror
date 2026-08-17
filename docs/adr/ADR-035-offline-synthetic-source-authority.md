# ADR-035：离线 Codex-native Source Authority 前向接入

## Status

Accepted — 2026-08-18

## Context

ADR-026 已接受 `CODEX_NATIVE_IMAGEGEN` 作为 operator-assisted、offline、synthetic-only 的 P2
研究来源，并要求未暴露的 model、model version、provider request、seed、usage 与 cost 保持
`NULL`。P2-M2-V01 的八个对象已通过私有 raw admission，但未进入 PostgreSQL generation pipeline。

冻结的 `0009` 将 `SyntheticSourceObject` 强制绑定 `GenerationItem + JobAttempt`，而 Batch 和
`SyntheticGenerationEvidence` 又要求非空 Provider/model facts。`0010` 的 normalizer 正确地只接受
PostgreSQL source authority。因此，给 V01 创建占位 Batch/Item/Evidence 会伪造 provenance；绕过
`SyntheticSourceObject` 直接创建 Asset 又会破坏 M3 authority。

## Decision

- This forward architecture change is `CC-P2-M3-03`; implementation defects use subsequent
  `P2-M3-Rxx` tasks and may not alter the authority union.
- 新增前向 migration `0011_offline_synthetic_source_authority`；不修改 `0001`–`0010`，不改变
  P2-M2 frozen evidence。
- 新增 immutable `OfflineSyntheticSourceAdmission`，只表达已通过 ADR-026 private admission 的
  `CODEX_NATIVE_IMAGEGEN` receipt。它固定：
  - `source_kind=CODEX_NATIVE_IMAGEGEN`；
  - `provenance_level=PROVENANCE_ONLY`；
  - `cost_accounting_mode=REQUEST_COUNT_ONLY`；
  - `synthetic_only=true`、`real_person_reference_used=false`；
  - model/version/request/seed/usage/cost 均为 `NULL`，不得使用占位值；
  - specification、policy、PromptTemplate digest reference、item/attempt、时间、raw checksum、MIME、
    bytes、observed/requested dimensions、dimension-match fact、opaque storage reference、retention 与
    canonical admission-evidence digest。
- `SyntheticSourceObject` 继续是 normalizer 的唯一 source FK，但增加版本化 authority union：
  - `M2_GENERATION`：保持 v1，`generation_item_id` 与 `job_attempt_id` 均非空，offline admission 为空；
  - `OFFLINE_CODEX_NATIVE`：使用 v2，两个 M2 FK 均为空，`offline_admission_id` 唯一且非空。
    PostgreSQL XOR constraints 和 trigger 强制该形状。
- `0009` source-link validation 的 M2 分支语义原样保留；新增 offline 分支只接受 immutable admission，
  并要求 storage reference、checksum、MIME、bytes 与 dimensions 精确一致。
- `0010` 的 `SyntheticAssetRecord` initial-source trigger 前向接受：未删除的 M2 `RAW_STORED`
  authority，或仍有效且未删除的 offline authority。其余 normalization、Asset、QA、review 与 identity
  规则不变。
- offline authority 不创建 `GenerationBatch`、`GenerationItem`、`JobAttempt`、
  `SyntheticGenerationEvidence` 或 `ProviderCostEvent`。
- 新增无 HTTP/CLI/Worker 暴露的 internal typed import service。它只接收已经准入的 typed receipt，
  复验 canonical receipt digest 与 private raw storage 的 checksum/MIME/bytes/dimensions，并原子、
  幂等创建 admission + source；现有 `SyntheticNormalizationService` 保持 source-neutral。
- P2-M3-V01 使用该 authority 导入已有 8 项 evidence，再执行现有 normalizer。Prompt text、private
  path、object key、图片 bytes 与 Provider raw payload不得进入数据库、日志或 committed artifact。

## Alternatives Considered

- 用 `unknown`、`codex-native` 或其他占位字符串伪造 Provider/model facts。
- 在测试中绕过 FK/trigger，直接创建 Asset 或 `SyntheticAssetRecord`。
- 修改历史 `0009`/`0010`。
- 把 Codex native 包装成 runtime `ImageGenerationProvider`。
- 只保存文件系统输出而不建立 PostgreSQL authority。

## Consequences

M3 可如实把已准入 offline source 接入同一 normalized/QA/identity 链，同时不污染 M2 programmatic
Provider 语义。`0011` downgrade 仅在无 offline admission、offline source 或下游 M3 evidence 时允许；
存在数据时必须 fail closed，生产恢复采用前向修复。

该决定不批准 production generation、真实用户 facial processing、QuestionBank release、模型/数据
权利或公共 API，也不把 Codex native 提升为 runtime Provider。

## Security / Privacy Considerations

Import 必须复验 private storage metadata 和流式 SHA-256；只接受 synthetic-only、无真人 reference 的
receipt。禁止路径、Prompt、object key、图片、signed URL、secret 和未知 Provider fields 泄漏。
offline admission、source lineage 与 normalized Asset 均不可更新或删除。

## Testing Implications

- 真实 PostgreSQL fresh upgrade、`0010→0011→0010→0011`、`alembic check`；有 offline 数据时
  downgrade fail closed。
- 回归证明 M2 source-link 规则不变。
- 验证 XOR、known-null、receipt immutability、metadata mismatch、重复 item/attempt、伪造 linkage、
  retention/deletion 与并发幂等。
- P2-M3-V01 必须逐项证明 8/8 raw checksum 和 requested/observed dimensions 保真、deterministic
  normalization、second decode、private normalized namespace、immutable Asset/record 与零 tracked binary。

## Validation Evidence

- `0011` 已在隔离 PostgreSQL 17.6 完成 fresh upgrade、`0010→0011→0010→0011`、
  `alembic check` 零 drift，并以 24 项 focused tests 证明 authority XOR、known-null、immutability、
  downgrade-with-data fail closed 和 import 幂等。
- P2-M3-V01 已把冻结的八项 receipt 逐项复验并导入为 8 admission + 8 offline source，再经未修改的
  `image-sanitizer-v1` 形成 8 record + 8 normalized Asset。全部 second decode 和幂等 replay 通过，未
  resample 至 requested shape，也未创建占位 Provider/Batch/Item/Attempt evidence。
- 可提交的逐项 checksum、byte count、dimensions、normalizer authority 与限制记录在
  `docs/operations/P2_M3_V01_NORMALIZATION_REDACTED_EVIDENCE.json`；Prompt、private path、storage
  reference、图片 bytes 和未知 Provider facts 均未提交。
