# ADR-021：合成数据集权威与生命周期

## Status

Accepted — 2026-08-16

## Context

现有 `SyntheticIdentity`、`QuestionAsset` 与 `QuestionBankVersion` 仅是 Phase 0 问卷骨架，且 `SyntheticIdentity` 仍直接关联题库版本。P2 需要以先生成和验证合成身份、再由发布版本引用的方式建立可追溯刺激资产，但不授权真实用户资料、SelfState、问卷运行或编辑。

## Decision

- `SyntheticIdentity` 是 bank-independent 的权威合成身份；只有 canonical normalized Asset 已通过适用 hard QA 时才可建立。QuestionBank 不拥有或改写 identity，后续只通过不可变 manifest entry 引用 identity、asset checksum 和版本化证据。
- raw Provider evidence、normalized synthetic Asset、deterministic variant 和 released manifest entry 是相互独立的生命周期/证据层。raw output 是不可信输入，永不直接成为 Asset、SyntheticIdentity 或 QuestionBank entry。
- migration 文件 `0008_synthetic_dataset_foundation.py` 使用 Alembic revision ID `0008_synth_dataset_foundation`，以满足既有 `alembic_version.version_num varchar(32)`；不得为长名称修改历史 migration 或版本表。该 migration 只前向建立 `SyntheticGenerationPolicy`、`SyntheticPromptTemplate`、`SyntheticQAPolicy` 与 `GeometryOntologyVersion` authority，解除 identity 对 QuestionBank 的 ownership，并固化 internal synthetic Asset 形状及不可变 blob metadata。历史 `0001`–`0007` 不得修改；batch、QA run、variant、manifest 与 revoke workflow 留给后续里程碑。
- versioned policy/template/ontology 使用与 exact authority kind 对应的固定 `schema_version`、JSON object content 与 canonical content digest；authority approval state 在 M1 只允许 `DRAFT → APPROVED`，`APPROVED` 是 terminal。schema version、content、version 和 digest 自创建起不可修改，禁止 update/delete；需要修订时创建新版本。项目状态继续使用 `PROVISIONAL → COMMITTED → EXECUTION_READY → EXECUTING → PASS → FROZEN`。
- 后续 release 必须是不可变 manifest；修正成员或证据创建新版本。revoke 追加 reason、actor、evidence 与 timestamp，立即停止新选择而不删除历史 provenance。
- P2 的控制面是 application service 与后续受控 CLI；M1 不建立用户公开 API、admin Web 或 internal HTTP API。

## Alternatives Considered

- 让 QuestionBankVersion 直接拥有 SyntheticIdentity。
- 将 Provider raw output 直接登记为 Asset。
- 将 P2 权威状态塞入通用 `Job.payload`。
- 在 M1 提前实现完整 batch/QA/release 表或公开管理接口。

## Consequences

M1 只建立前向 authority 基础与治理，不生成图片或正式题库。未来 P2 领域状态使用专门实体；`Job`/`JobAttempt` 只复用 lease、retry 与 recovery envelope。

## Security / Privacy Considerations

P2 synthetic object namespace 与 user quarantine/sanitized/export namespace 完全分离。所有 fixture、数据和未来 release candidate 必须具有 synthetic classification、source、license 和 checksum；真人或真实用户数据都不在 P2 范围。

## Testing Implications

`0007 → 0008 → 0007 → 0008`、`alembic check`、PostgreSQL immutability、unique、legacy compatibility 和 synthetic Asset shape 必须在真实 PostgreSQL 证明。M1 不改变 OpenAPI 或 generated TypeScript。
