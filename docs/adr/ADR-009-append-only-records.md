# ADR-009：Profile、Consent 与 Credit Ledger Append-only

## Status

Accepted — 2026-08-15

## Context

审美变化、授权历史与额度账务必须可解释、可审计，ORM 约定不足以阻止直接 SQL 修改。

## Decision

AestheticProfileVersion、ConsentRecord 和 CreditLedger 采用 append-only 表；PostgreSQL trigger 拒绝 UPDATE/DELETE。当前 Profile 指针可以事务更新，但历史值不能覆盖；余额从 Ledger 聚合或受验证快照计算。

## Alternatives

应用层约定；JSON 覆盖；用户表 balance 字段。

## Consequences

历史可靠且便于审计；纠错需追加补偿记录，新迁移必须维护 trigger。
