# ADR-006：腾讯云作为中国大陆 Beta 部署目标

## Status

Accepted — 2026-08-15

## Context

首发市场在中国大陆，需要匹配备案、网络、短信、对象存储和数据驻留需求。

## Decision

Beta 目标为腾讯云 CVM/容器、RDS PostgreSQL、Redis、私有 COS、CLB/WAF 和日志服务；服务无状态并保留迁移 TKE 能力。

## Alternatives

阿里云；境外云；立即使用 TKE。

## Consequences

降低大陆接入摩擦；仍需备案、地域、PIPIA 和供应商条款审核。AI 模型选择不因云厂商品牌而锁定。
