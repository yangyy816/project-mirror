# ADR-007：严格 Provider Adapter

## Status

Accepted — 2026-08-15

## Context

短信、存储、视觉、图像和 Agent 的供应商能力、数据条款与地域会变化。

## Decision

Domain/Application 只依赖供应商中立 Protocol。SDK 只能位于 infrastructure adapter。Mock 必须 deterministic 并被 production schema 拒绝；腾讯混元仅是 `BENCHMARK_REQUIRED` 候选。

## Alternatives

业务直接调用 SDK；单一供应商抽象；在 Domain 保存原始 SDK metadata。

## Consequences

可替换且利于测试；需维护内部稳定类型和 benchmark evidence。
