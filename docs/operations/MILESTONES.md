# Project Mirror Milestones

## 当前执行状态

| Scope   | State     | Evidence / Boundary                                              |
| ------- | --------- | ---------------------------------------------------------------- |
| Phase 0 | FROZEN    | `phase0-baseline` → `f9398304b1a313540d80db701806d845f046bbb8`   |
| Phase 1 | COMMITTED | Application Foundation；仅 P1-M1 已通过 Gate，Phase 1 尚未 PASS  |
| P1-M1   | FROZEN    | closure `1276a74`；run `31886590832` 三个 jobs 与 artifacts 全绿 |
| P1-M2   | COMMITTED | Web Authentication and Onboarding；等待 rolling-wave refinement  |

状态机与 Repair Task 规则见 `P1_M1_EXECUTION_PROTOCOL.md`。

P1-M1 的逐项证据与 deferred production Gates 见 `P1_M1_ACCEPTANCE.md`。

## Future rolling-wave positioning

- P6 — Hybrid Non-Destructive Editor & Agent Runtime 保持 `PROVISIONAL`，其一级能力轨道为 Deterministic Editor、Geometry Editor、Generative Editor、Identity-Preserving Makeup Transfer 与 Agent Tool Layer。
- Identity-Preserving Makeup Transfer 是 P6 的高优先级研究轨道，并可向前影响 P5 Reference Profile refinement、向后为 P7 PreferenceEvent 提供用户确认/纠正证据。
- 该轨道的目标链为：Reference Makeup Understanding → MakeupStyleRepresentation → StyleProfile personalization → Structured MakeupPlan → Region-level execution → Identity/geometry verification → User correction → PreferenceEvent。
- P6 成为当前 Phase 前不得冻结最终 schema、选择生产引擎或创建 bounded Terra tasks；届时由 Principal 确定 `P6-Mx` 编号，并以 `GO | NO-GO | FURTHER_RESEARCH` 结束研究 Gate。
- 此定位不改变 P1-M1 DAG、任务依赖或 Gate：`CURRENT_MILESTONE_IMPACT: NONE`。

## Phase 0 Milestones

每个 Milestone 的 Evidence 由 P0.14 审计更新；Known Limitations 不得伪装为通过。

| Milestone          | Acceptance Criteria                             | Validation                   | Evidence / Limitation                                           |
| ------------------ | ----------------------------------------------- | ---------------------------- | --------------------------------------------------------------- |
| P0.1 Repository    | Git、pnpm workspace、Turbo、ignore              | `git status`; `pnpm install` | Local PASS：pnpm 11.19.0、Turbo 2.9.14、lockfile                |
| P0.2 Documentation | PRD、安全、数据、AI、部署、合规、ADR            | docs-code audit              | Local PASS：required docs/ADR present；v0.2 conflict scan clean |
| P0.3 Web           | Windows start/build/typecheck、真实 health      | web build + smoke            | Local PASS：production build + HTTP 200 smoke                   |
| P0.4 API           | Windows start、error/request id/501             | pytest + smoke               | Local PASS：live/version 200；缺依赖 ready 503 limited          |
| P0.5 Domain        | Consent/provenance/profile/lineage/ledger       | PostgreSQL tests             | Docker Linux + PostgreSQL PASS：8 个 invariant 无 skip          |
| P0.6 PostgreSQL    | upgrade/down/upgrade/check                      | Linux CI PostgreSQL          | Docker Linux PASS：两轮 lifecycle + schema consistency          |
| P0.7 Providers     | strict Adapter、deterministic Mock、prod reject | unit + architecture scan     | Local PASS：unit/security/source scan                           |
| P0.8 Worker        | App logic 独立；Linux Celery integration        | unit + CI Redis              | Docker Linux + Redis PASS：inspect pong、round trip、5 tests    |
| P0.9 Contracts     | OpenAPI → generated TS client                   | generation + drift check     | Local PASS：in-process drift check + API equality test          |
| P0.10 Security     | config/storage/upload/auth/log tests            | security suite               | Local tests PASS；Gitleaks Docker source snapshot PASS          |
| P0.11 Tests        | unit + PostgreSQL integration                   | local + CI                   | Docker Linux full Python suite PASS：50 tests                   |
| P0.12 Supply Chain | lock/audit/secret/license/SBOM                  | CI jobs                      | Remote PASS：run 31871724239；audit、SBOM、Gitleaks artifacts   |
| P0.13 Local DX     | Windows Web/API instructions                    | clean-start smoke            | Local PASS：Web/API independently started；README corrected     |
| P0.14 Final Audit  | 只审计、修 defect、同步证据                     | full matrix                  | PASS：fix SHA 796ab55；run 31871724239 三个 jobs 全绿           |
