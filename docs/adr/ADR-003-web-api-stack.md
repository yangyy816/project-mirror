# ADR-003：Next.js Web 与 FastAPI API

## Status

Accepted — 2026-08-15

## Context

产品需要 Web 首发、Python CV/AI 生态和未来 iOS 复用的稳定 API。

## Decision

Web 使用 Next.js App Router + strict TypeScript；API 使用 FastAPI + Pydantic + SQLAlchemy + Alembic。Web 不直接访问数据库或供应商。

## Alternatives

全栈 Next.js；Django；Node API。

## Consequences

前后端边界清晰并适合 CV Worker；需要单向契约生成避免类型漂移。
