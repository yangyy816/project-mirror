# ADR-037：几何变体结果的 QA Subject Union

## Status

Accepted — 2026-08-18

## Context

ADR-027 将 `SyntheticQARun` 冻结为 canonical normalized base Asset 的 QA authority，并要求每个 run
绑定一个 raw-source-derived `SyntheticAssetRecord`。ADR-036 要求 M4 的新 immutable variant Asset 重新使用
同一 measurement/QA pipeline，但 variant 是 transform result，不具有也不得伪造 Provider raw source 或
`SyntheticAssetRecord`。

如果为 variant 伪造 raw source/normalization record，会重写 M2/M3 authority；如果建立第二套 QA measurement
表，则会产生双重权威并增加 M5 isolation drift。

## Decision

- 前向扩展 `SyntheticQARun` 为明确的 subject union：`CANONICAL_BASE | GEOMETRY_VARIANT`。
- 既有行全部为 `CANONICAL_BASE`，继续要求非空 `SyntheticAssetRecord`，且原有 normalized Asset、policy、
  measurement/review、hard-gate 和 identity registration 语义不变。
- `GEOMETRY_VARIANT` run 不得引用 `SyntheticAssetRecord`；它必须唯一引用已进入 output-stored 阶段的
  `TransformRun`，且被测 Asset 必须等于该 run 的 immutable result Asset。
- `SyntheticQARun.normalized_asset_id` 在 `0012` 保留为冻结列名和共同 subject Asset reference；不做历史
  rename。对 variant，它表示经过 canonical source 变换、bounded encode 和 second decode 的 subject Asset，
  不声称存在新的 raw normalization record。
- `TransformRun` 不重复保存 result QA ID。variant `SyntheticQARun.transform_run_id` 是唯一反向绑定；
  TransformRun 进入 `MEASURING` 必须存在对应 RUNNING run，进入 `COMPLETED` 必须存在对应 PASSED run。
- measurement/review append-only、hard-gate non-bypass、approved QAPolicy、provider-neutral schema 与 production
  fail-closed 全部复用 M3 authority。M4 不新增第二套 measurement table。
- 该 union 只允许 private synthetic geometry variant；不授权 User Asset、real-user facial processing、M5
  isolation PASS、QuestionBank release 或 public API。

## Alternatives Considered

- 为 variant 伪造 `SyntheticSourceObject` / `SyntheticAssetRecord`。
- 在 `TransformRun` JSON 中复制 measurement payload。
- 新增平行 `TransformMeasurement` authority。
- 破坏性 rename 或重写既有 M3 QARun rows。

## Consequences

M3 authority保持可重建且 byte/schema history 不被重写，M4 result 可使用同一 QAPolicy、measurement、review
和 hard-gate evaluator。应用层后续必须显式分支 subject kind；未知或混合 shape fail closed。

## Security / Privacy Considerations

union 仅扩大 synthetic subject provenance，不扩大数据类别、存储可见性或处理授权。PostgreSQL trigger 必须
验证 base/variant XOR、result Asset linkage、approved policy、run state 和 immutable references。

## Testing Implications

`0012` 必须证明 existing M3 row backfill、base behavior regression、variant insert/transition、mixed/forged
subject rejection、immutability、concurrency、downgrade fail-closed、re-upgrade和 Alembic zero drift。
