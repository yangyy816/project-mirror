# ADR-004：Task Interface、LocalTaskRunner 与 Celery Adapter

## Status

Accepted — 2026-08-15

## Context

Celery 生产目标是 Linux + Redis；Windows 原生不是权威兼容环境。业务逻辑与 Celery task 绑定会降低可测试性。

## Decision

Application Service 实现任务逻辑，TaskDispatcher 是端口；development/test 可用同步 `LocalTaskRunner`，production/ci 使用 Celery Adapter。Celery 注册、序列化、retry 与幂等在 Linux CI 验证。

## Alternatives

所有环境直接 Celery；Windows solo 作为生产证明；自建队列。

## Consequences

业务可脱离 broker 单测；需要维护两个执行 Adapter，并禁止 Local runner 进入生产。
