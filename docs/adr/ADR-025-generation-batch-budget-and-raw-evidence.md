# ADR-025：生成批次、预算与 raw evidence 权威

## Status

Accepted — 2026-08-16

## Context

P2-M1 已冻结 Provider-neutral generation/storage ports 和 policy authority，但尚未定义批次、
生成 item、失败/取消、预算并发、raw object retention 或 Worker task 的持久化权威。现有 `Job` 与
`JobAttempt` 包含 ingestion 历史字段，只能作为执行 envelope，不能承载 P2 领域状态。已批准的
GenerationItem 长生命周期也没有表达 Provider 重试耗尽和取消终态，不能把这些结果误写成后续
QA 的 `REJECTED`。

## Decision

- P2-M2 新增 `GenerationBatch`、`GenerationItem`、`SyntheticSourceObject`、
  `SyntheticGenerationEvidence`、`ProviderCostEvent` 与
  `SyntheticSourceObjectDeletionEvidence`。这些实体不引用 `User`、真实 Asset 或真实 facial data。
- `GenerationBatch` 固定 approved GenerationPolicy/PromptTemplate、Provider/model/version、pricing
  snapshot、output specification、item count、hard budget、per-item ceiling、retry ceiling 和
  concurrency ceiling。配置自创建起不可变；跨 policy、prompt、Provider/model/version 或 pricing
  snapshot 的重试必须创建新 batch。
- batch 状态为
  `DRAFT → QUEUED → RUNNING → COMPLETED | PARTIAL | FAILED | CANCELLED`。取消请求先追加
  `cancel_requested_at` 并阻止新 dispatch；已取得 lease 的 attempt 到安全点后完成或保留失败/成本
  证据，全部 item quiescent 后 batch 才进入 `CANCELLED`。
- P2-M2 item 状态为
  `REQUESTED → GENERATING → RAW_STORED | GENERATION_FAILED | CANCELLED`。M3 才能从
  `RAW_STORED` 进入 normalization/QA 状态。`GENERATION_FAILED` 和 `CANCELLED` 是 M2 必需终态，
  不得伪装成表示内容/QA 决策的 `REJECTED`。这是 `CC-P2-10` 对概念生命周期的前向澄清。
- 一个 GenerationItem 绑定一个通用 `Job`；`Job`/`JobAttempt` 只保存 lease、attempt、retry 和
  recovery envelope。P2 task message 固定为 reference-only schema，只含 schema version、item ID、
  job ID 和 request ID。Prompt、policy content、bytes、URL、object key、Provider payload 和 credential
  不得进入 task payload。
- Worker 在取得 item/job lease 后从 PostgreSQL 读取冻结 authority，并在进程内解析 Prompt。实际
  Prompt 使用 bounded、redacted-representation、不可序列化的短生命周期 value object；只允许
  Provider Adapter 在调用边界读取，不进入日志、异常、task、evidence 或 CI artifact。M2 不新增
  Provider SDK，也不选择生产 Provider。
- 每次 Provider attempt 都追加 generation evidence 和 cost event。Provider/model/version/run
  reference、实际 seed/parameters、safety、rights/retention、reproducibility 和 cost 只记录 Provider
  实际事实；未知值为 `NULL` 或 fail closed，禁止猜测。`ModelRun` 与 `AIContentProvenance` 只是跨能力
  投影，不替代这些 P2 记录。
- budget admission 与 cost posting 在 PostgreSQL batch row lock 下执行。dispatch 前预留受 hard
  budget 和 per-item ceiling 约束的 item budget；每次 retry 只能消费该 item 剩余额度。追加 cost
  event 后的 item/batch 累计不得越界。达到 budget 或 retry ceiling 时 fail closed，不再 dispatch。
- Provider output 先写独立 `internal-synthetic-raw/v1` 私有 namespace，再在同一 item 完成事务中追加
  source/evidence metadata 并进入 `RAW_STORED`。storage reference 是第一方 opaque reference，不是
  object key。确定性 item/attempt reference 使“blob 已写但数据库事务失败”可由 reconciler 找回。
- `SyntheticSourceObject` 的 checksum、MIME、bytes、dimensions、storage reference、retention deadline
  和 generation linkage 自创建起不可变。TTL、取消、失败或 orphan cleanup 删除 blob 时，追加
  `SyntheticSourceObjectDeletionEvidence`；历史 metadata/provenance 不删除、不覆盖。
- CI 只运行 deterministic Mock 与 synthetic/non-human fixtures，零网络。受控 live Provider benchmark
  是独立外部 Gate；未完成一个批准候选的真实 benchmark 时，M2 Gate 至多 `CONDITIONAL`，不能
  `FROZEN`，也不能让该候选产生 release-eligible asset。

## Alternatives Considered

- 把 batch/item/cost 权威塞入 `Job.payload`。
- 把 Provider failure 当作 QA `REJECTED`。
- 把 Prompt 明文放进 Celery message 或日志。
- 删除 raw blob 时同时删除 provenance row。
- 只在应用内检查预算，不使用 PostgreSQL 行锁。
- 让 Mock 或未批准 Provider 满足 live benchmark Gate。

## Consequences

M2 可以独立证明 batch/retry/cancel/budget/raw evidence 与恢复语义，但不会执行 normalization、Vision
QA、SyntheticIdentity registration、variant 或 QuestionBank release。没有获批的真实 Provider 与凭据
时可以完成 deterministic implementation，Milestone 仍保持外部验证未满足，不能伪报 PASS/FROZEN。

## Security / Privacy Considerations

所有 M2 数据 synthetic-only；不得持久化 Prompt、Provider raw response、URL、object key、credential
或真实用户引用。raw bytes 始终是不可信输入，只能进入私有 raw namespace，不能成为 Asset。

## Testing Implications

必须在真实 PostgreSQL 验证 immutable configuration/evidence、状态单向、并发 dispatch、预算/重试
ceiling、cancel race、idempotent storage、orphan reconcile 与 append-only cleanup。默认 CI 必须零网络、
零 mandatory skip，并保留 P1/P2-M1 regression、OpenAPI drift、Docker、Gitleaks、license 与 SBOM Gate。
