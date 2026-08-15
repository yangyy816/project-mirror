# ADR-010：分环境配置与生产 Fail-closed

## Status

Accepted — 2026-08-15

## Context

开发 Fake 很有用，但 accidental production misconfiguration 会暴露数据或伪造能力。

## Decision

环境固定为 development/test/ci/production，并由集中 schema 验证。Production 拒绝 Mock/Local、Debug、开发 CORS、不安全或空 Secret、公开存储、testing config 和未通过 legal/benchmark gate 的真实敏感处理。

## Alternatives

启动后按需报错；只靠部署文档；所有环境要求生产凭据。

## Consequences

错误配置在启动时失败；配置 schema 需随能力 Gate 演进并有负向测试。
