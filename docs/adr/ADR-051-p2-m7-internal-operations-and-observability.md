# ADR-051：P2-M7 内部操作、成本与可观测性控制面

## Status

Accepted — 2026-08-23

## Context

P2-M2 已冻结可审计的 `GenerationBatch`、`GenerationItem`、`ProviderCostEvent`、`Job` / `JobAttempt`
和 reference-only Worker 边界；P2-M3 与 P2-M4 已冻结其各自的 synthetic-only authority。P2-M5 仍在
研究状态，CC04-A 的任何 fresh-study execution 需要单独 Owner decision，P2-M6 release/revoke 也保持关闭。

现有 Phase 1 structured operational event 与 runbook 只覆盖用户域和通用 Job 事件。P2 仍缺少一个最小、可
审计且不会把对象 key、Prompt、图像、Provider payload 或凭据暴露给操作人员的控制面。将操作逻辑直接放进
shell SQL、临时脚本、admin HTTP 或 Celery task payload 会绕过 PostgreSQL authority、actor attribution 与
redaction boundary。

## Decision

- P2-M7 采用 `mirror-dataset` **内部 CLI + application service** 边界；不创建 admin HTTP、Web console 或
  public OpenAPI contract。CLI 不得直接写表、拼接 SQL、读取 private object 或绕过 repository / service 事务。
- 所有 mutation command 必须使用显式 database environment、authenticated system/operator actor、reason、
  request correlation 和预期 immutable reference / status。缺少任一项时 fail closed；结果必须经既有
  `AuditLog` 或对应 P2 append-only authority 留痕。
- 初始可实现范围仅限已冻结 application authority 的 batch/status/cancel、provenance status、QA status、
  cost summary 与 redacted operational evidence。P2-M6 前不得实现或暴露 QuestionBank release/revoke command；
  P2-M5 closed research paths 不得由 CLI 重新打开、重放或生成研究输入。
- 成本只投影 `ProviderCostEvent` 和已版本化 pricing facts：actual、estimated、unknown / unavailable 必须保持
  区分，禁止从 native offline source、缺失 usage 或 request count 推导货币成本。CLI 输出只允许 aggregate
  count / currency / amount / outcome / duration bucket / opaque authority ID；禁止 Prompt、object key、URL、
  image bytes、raw Provider response、secret、private path 与用户资料。
- 可观测性复用 Phase 1 的 payload-free allowlist 原则，并为 P2 固定 operation、outcome、reason code、
  request correlation、opaque batch/item/job/policy/version reference、duration bucket 和 cost aggregate。
  事件是辅助投影；PostgreSQL authoritative rows、append-only evidence 与 audit log 才是事实来源。collector、
  dashboard、alerting 和 Tencent Cloud routing 继续是 P9 工作，必须标记 `NOT_DEPLOYED`。
- 默认 CI 使用 deterministic Mock / numeric or JSON fixtures 且零网络。production 配置仍拒绝 Mock、Local
  synthetic storage、未批准 Provider、未知 model artifact、公开 bucket 与未授权 CLI execution。M7 不新增
  runtime dependency、model artifact、real-person fixture、real-user facial processing 或迁移；若实施发现
  新 authority table、public contract、role model 或 schema 是必要条件，停止并通过独立 change control 决定。

## Consequences

- P2-M7 可以在 M5 的 research blocker 存在时独立推进其已冻结的 operations foundation，但不能以“运维”为由
  实现 M6 release/revoke、M5 holdout/fresh study 或 production generation。
- 命令的可用性是 capability-specific：只有目标 application service 已经 accepted 且其 preconditions 通过时
  才可启用；其余子命令必须返回 stable fail-closed status，不能伪造操作完成。
- 每项后续 M7 bounded task 必须同时证明 operator authorization、redaction、at-least-once / concurrent safety
  和 PostgreSQL authority precedence。只通过 CLI parsing test 不足以证明 mutation 正确。

## Alternatives considered

1. 直接提供 admin HTTP / Web console：拒绝；会扩张公开或内部网络认证面，且当前 Phase 未授权。
2. 使用 SQL 或临时 operator script：拒绝；无法强制 application invariants、审计与脱敏。
3. 等待 M5/M6 完成才建设 M7：拒绝；MILESTONES 已明确 M7 在 M2 contracts 后可 refinement，且其基础能力不
   依赖 M5 fresh-study decision。
