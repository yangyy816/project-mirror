# ADR-038：不可变 Landmark Warp Plan 权威

## Status

Accepted — 2026-08-18

## Context

P2-M4-T06 的只读入口核验发现，`GeometryTransformRequest` 必须包含严格的
`LandmarkWarpPlan`，但 `0012_geometry_variant_authority` 只保存 requested
`VariantSpecification` 与 execution `TransformRun`，没有保存 plan、plan digest 或确定性 plan
reference。仓库中 plan 仅由 T05 isolated tests 构造。把 plan 放入 Celery/Job payload，或在 retry 时从
任意 QA JSON 临时推导，都会破坏 reference-only task、空 Job envelope、可重放性和 M5 provenance。

这是冻结 authority 的前向缺口，不是可包装为 `P2-M4-Rxx` 的实现缺陷。T06 在写入前停止。

## Decision

- 通过 `CC-P2-M4-03` 新增独立 `landmark_warp_plans` PostgreSQL authority，与
  `VariantSpecification` 严格 1:1。plan 必须在首个 `TransformRun` 前创建；已有 specification 在合法
  plan admission 前不可执行。
- authority 固定 schema `mirror.synthetic-dataset/LandmarkWarpPlanAuthority/v1`，保存：
  specification FK、现有 `LandmarkWarpPlan/v1` compact ASCII canonical payload、
  `warp_plan_digest`、`authority_digest`、bounded origin reference/digest、固定 builder version 与
  builder manifest digest、created timestamp。
- M4 唯一允许的 origin 是 `PREREGISTERED_M4_RESEARCH_PLAN`。Admission 只接受已经通过第一方 typed
  `LandmarkWarpPlan` 验证的对象；不接受 dict、任意 JSON、QA payload、URL、object key 或路径。它只负责
  验证、排序、canonicalization 与 digest，不构成通用 facial plan generator。
- canonical payload 必须精确匹配现有 plan grammar：3–512 个唯一且排序的 control points、1–1024 个
  canonical/唯一 triangles、所有点被引用、至少一个点移动、有限 `[0,1]` 坐标和
  `[500000,1000000]` integer confidence。未知字段、NaN、越界、重复、未引用或 spec digest mismatch
  全部拒绝。
- `warp_plan_digest = SHA256(plan_schema_version + "\n" + canonical_payload)`。
  `authority_digest` 绑定 authority schema、spec digest、origin kind/reference/digest、builder
  version/manifest 和 plan digest。相同 specification + 相同 authority 幂等；不同 authority hard
  conflict，变更必须创建新的 algorithm/specification version。
- PostgreSQL trigger 复验 closed grammar、spec binding、canonical payload、两个 digest，并拒绝 plan
  UPDATE/DELETE。`TransformRun` INSERT 必须锁定 specification 后锁定唯一 plan；没有 plan 时拒绝。
  ORM 同样拒绝 mutation/delete。
- T06 reference-only task 只携带 opaque `transform_run_id`、`job_id` 与 `request_id`，并按
  `run → specification → plan → source Asset` 重建 `GeometryTransformRequest`。Job payload 保持 `{}`。
- 统一锁序为 `VariantSpecification → LandmarkWarpPlanAuthority → TransformRun → source Asset →
result Asset → SyntheticQARun → Job → JobAttempt`。外部 transform/storage I/O 不持有数据库锁。
- variant output 使用独立 private namespace
  `internal-synthetic/v1/variants/<digest>` 与 create-if-absent receipt，绑定 output checksum/dimensions、
  spec/plan/runtime/output-policy facts。storage 后 crash 通过相同 deterministic receipt 接管；不同 checksum
  hard conflict。
- `SPECIFIED/RUNNING` 且 result 未提交时可取消；Asset promotion 后进入不可撤销 evidence completion。
  retry exhaustion 原子终结 run/job；reconciler 覆盖 expired lease、storage-before-DB、缺失 QA、QA terminal
  未同步和 cancelled orphan cleanup。
- 不修改历史 `0012`、public API、M5 isolation、QuestionBank、User Asset、真人处理或生产能力。

## Migration and Compatibility

- 新增前向 migration file `0013_landmark_warp_plan_authority.py`；其真实 Alembic revision/head 是
  `0013_warp_plan_authority`。Upgrade 若发现已有任何 `TransformRun` 必须 fail closed，
  因为不能猜测 backfill plan；已有无 run 的 specification 可保留。
- 无 plan/M4 execution data 时支持 `0012 → 0013 → 0012 → 0013`。存在 plan 或依赖 execution evidence
  时 downgrade 拒绝；有数据环境只允许 forward repair 或关闭功能。
- migration 不改变 OpenAPI、generated TypeScript、M1–M3 或现有 QA base authority。

## Alternatives Considered

- 把 plan 写入 Job/task payload。
- 把 plan JSON 复制到每个 TransformRun。
- 把 execution plan 混入既有 VariantSpecification digest。
- Worker 从可变代码和任意 QA JSON 临时重算。
- 只把 plan 放入 object storage。
- 一个 specification 允许多个 plan。
- 为 points/triangles 建立多表 draft/seal 生命周期。

## Consequences

T06 在 `0013` 及其领域/数据库 Gate 被 Principal 接受前保持 blocked。完成后，at-least-once Worker 可从
PostgreSQL authority 重建同一 transform request，而不把 plan、像素或 policy 放入消息。T07 仍必须提供
预注册 typed research plan；本 ADR 不产生或批准通用 planner。

## Security / Privacy Considerations

仅处理 private synthetic geometry evidence。canonical payload、对象键、图片与路径不得进入日志、公开响应或
CI artifact。无新依赖、模型、网络、真人数据、敏感分类、生产或分发授权。

## Testing Implications

必须覆盖 canonical round-trip/digest/closed grammar、direct-SQL mutation、1:1 concurrency、无 plan run
拒绝、migration lifecycle/downgrade、reference-only/empty payload、锁序、duplicate/lease/crash/cancel/retry/
reconcile、exactly-one result Asset/QA、zero-network、OpenAPI zero drift 和完整 PostgreSQL/Worker/CI Gate。
