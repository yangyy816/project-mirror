# ADR-002：PostgreSQL 是唯一权威关系数据库

## Status

Accepted — 2026-08-15

## Context

Profile、Consent、资产 lineage 和账务依赖事务、约束与 PostgreSQL-specific 不可变保护；SQLite 会产生错误通过。

## Decision

所有环境的权威关系数据库均为 PostgreSQL。无 PostgreSQL 的本地 API 进入有限能力模式；migration、constraint、transaction 与 invariant 只在真实 PostgreSQL 验收。

## Alternatives

开发 SQLite、生产 PostgreSQL；Mock DB；双数据库兼容。

## Consequences

本地起步成本提高，但消除方言漂移。Linux CI 必须启动 PostgreSQL；本机缺服务时标记 `NOT VERIFIED LOCALLY`。
