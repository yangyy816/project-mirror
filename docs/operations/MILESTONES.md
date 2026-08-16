# Project Mirror Milestones

## 当前执行状态

| Scope   | State     | Evidence / Boundary                                              |
| ------- | --------- | ---------------------------------------------------------------- |
| Phase 0 | FROZEN    | `phase0-baseline` → `f9398304b1a313540d80db701806d845f046bbb8`   |
| Phase 1 | COMMITTED | Application Foundation；P1-M1/M2/M3/M4 frozen；P1-M5 Gate PASS   |
| P1-M1   | FROZEN    | closure `1276a74`；run `31886590832` 三个 jobs 与 artifacts 全绿 |
| P1-M2   | FROZEN    | closure `0614ccf`；run `31892788852` 三个 jobs 与 artifacts 全绿 |
| P1-M3   | FROZEN    | closure `05c9f00`；run `31897780247` 三 jobs 与 artifacts 全绿   |
| P1-M4   | FROZEN    | closure `fd910f2`；run `31903994976` 三 jobs 与 artifacts 全绿   |
| P1-M5   | PASS      | candidate `6d46b4b`；run `31921199397` 三 jobs 与 artifacts 全绿 |

状态机与 Repair Task 规则见 `P1_M1_EXECUTION_PROTOCOL.md`。

P1-M1 的逐项证据与 deferred production Gates 见 `P1_M1_ACCEPTANCE.md`。

P1-M2 的浏览器、Linux CI、repairs 与 deferred production Gates 见 `P1_M2_ACCEPTANCE.md`。

P1-M3 的用途授权、quarantine upload control 与 M4 边界见 `ADR-018-purpose-consent-and-quarantine-upload.md` 和 `P1_M3_EXECUTION_PROTOCOL.md`。

P1-M3 的本地/远端 Gate、repairs 与 deferred production Gates 见 `P1_M3_ACCEPTANCE.md`。

P1-M4 的安全解码、canonical re-encode、Job/recovery、晋升和 M5 边界见 `ADR-019-safe-image-ingestion-and-promotion.md` 与 `P1_M4_EXECUTION_PROTOCOL.md`。

P1-M4 的本地/远端 Gate、repairs 与 deferred production Gates 见 `P1_M4_ACCEPTANCE.md`。

P1-M5 的私有 Asset 访问、异步删除、数据导出、账户删除传播和 P1-M6 边界见 `ADR-020-user-data-rights-and-asset-lifecycle.md` 与 `P1_M5_EXECUTION_PROTOCOL.md`。

P1-M5 的本地/远端 Gate、repairs 与 deferred production Gates 见 `P1_M5_ACCEPTANCE.md`；当前等待 acceptance closure CI，尚未标记 `FROZEN`，不得进入 P1-M6。

## Future rolling-wave positioning

- P6 — Hybrid Non-Destructive Editor & Agent Runtime 保持 `PROVISIONAL`，其一级能力子系统为 Deterministic Editor、Geometry Editor、Generative Editor、Identity-Preserving Makeup Transfer 与 Agent Tool Layer。
- Identity-Preserving Makeup Transfer 是 P6 的高优先级研究轨道和一级能力边界，不得降格为 Generative Editor 内的单个 `makeup_transfer()` 工具。它可向前影响 P5 Reference Profile refinement，并向后为 P7 PreferenceEvent 提供用户确认/纠正证据。
- 该轨道的目标链为：Reference Makeup Understanding → MakeupStyleRepresentation → StyleProfile personalization → Structured MakeupPlan → Region-level execution → Identity/geometry verification → User correction → PreferenceEvent。
- P6 成为当前 Phase 前不得冻结最终 schema、选择生产引擎或创建 bounded Terra tasks；届时由 Principal 确定 `P6-Mx` 编号，并以 `GO | NO-GO | FURTHER_RESEARCH` 结束研究 Gate。
- P7 的前向名称升级为 `Visual Memory OS & Persistent Preference Learning`，状态保持 `PROVISIONAL`。其权威层是用户确认的视觉、行为和明确证据；AestheticProfile、图、索引、Memory Card 与 semantic/temporal/procedural views 均为可重建派生状态。
- P7 未来高层 deliverables 包括 AcceptedVisualEpisode、EditTrajectory evidence、Admission/Write/Memory Gate、hierarchical memory、Active Visual Exemplars、temporal/procedural memory、Memory Consolidation、Context Compiler、删除/重编译和 MirrorMemoryBench；这些不得直接转换为当前 Milestones 或 bounded tasks。
- P6 必须保留 Final Save 到 source/result asset、ImageVersion、EditPlan、operations/manual corrections、Profile、context、Agent/provider version 与明确指令的 provenance，供 P7 使用；P7 不得重新发明 P6 的编辑证据语义。
- 此定位不改变当前 P1-M2 DAG、任务依赖或 Gate：`CURRENT_MILESTONE_IMPACT: NONE`。

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
