# Phase 0 Milestones

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
