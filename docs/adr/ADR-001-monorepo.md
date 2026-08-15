# ADR-001：pnpm + Turborepo Monorepo

## Status

Accepted — 2026-08-15

## Context

Web、共享 UI/契约、Python API 与 Worker 需要统一版本、CI 和审查边界，同时 iOS 后续保持 API 复用。

## Decision

使用单仓库；JavaScript workspace 由 pnpm 管理，任务图由 Turborepo 管理，Python 服务保留独立 package metadata。

## Alternatives

多仓库；npm workspace；只用脚本编排。

## Consequences

跨模块契约变更可原子提交并统一检查；需维护 Node/Python 两套锁定与 CI 缓存。
