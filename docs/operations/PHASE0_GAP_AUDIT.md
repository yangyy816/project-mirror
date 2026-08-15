# Phase 0 补充规格差距审计

日期：2026-08-15

| 要求                                  | 审计时状态                               | 修正动作                                                                 |
| ------------------------------------- | ---------------------------------------- | ------------------------------------------------------------------------ |
| PostgreSQL 唯一权威数据库             | FAIL：默认及 invariant tests 使用 SQLite | 改为 PostgreSQL-only；本机有限能力；Linux CI 服务验收                    |
| Worker 与 Celery 解耦                 | FAIL：业务函数定义在 Celery task 中      | 引入 Application Service、TaskDispatcher、LocalTaskRunner、CeleryAdapter |
| development/test/ci/production schema | PARTIAL                                  | 增加 ci、Secret/CORS/Debug/Provider/Gate fail-closed                     |
| Versioned Consent history             | PARTIAL：缺 purpose/scope/source         | 升级模型并增加数据库 append-only trigger/test                            |
| PIPIA                                 | MISSING                                  | 增加 compliance 模板和 `LEGAL_REVIEW_REQUIRED` Gate                      |
| AI content provenance                 | MISSING                                  | 增加供应商中立模型、Asset flags 与 ImageVersion 关联                     |
| Research/operation 分类               | PARTIAL                                  | 从 AGENTS invariant 移出并在 research spec 标记                          |
| OpenAPI generated client              | PARTIAL：只有 generated types            | 增加 typed client、生成与 git diff Gate                                  |
| Idempotency policy                    | PARTIAL                                  | 增加 scope/fingerprint/expiry/replay/conflict 规格和模型                 |
| PostgreSQL database invariants        | MISSING：只有 ORM event                  | migration triggers + direct SQL integration tests                        |
| Dependency-aware readiness            | MISSING                                  | DB/Redis probe，有限能力 503 与 Web 真实展示                             |
| Security tests                        | PARTIAL                                  | 增加 auth、redaction、production mock/CORS/debug/secret tests            |
| Supply-chain gate                     | MISSING                                  | 版本文件、lockfile、audit/license/SBOM/secret scan CI                    |
| ADR                                   | MISSING                                  | 为已接受架构决策建立标准 ADR                                             |
| Git repository                        | MISSING                                  | 初始化 Git 并执行 hygiene audit                                          |

无法在当前 Windows 主机权威验证的 PostgreSQL、Redis 和 Celery 项目必须标记 `NOT VERIFIED LOCALLY`，不得写成 PASS。
