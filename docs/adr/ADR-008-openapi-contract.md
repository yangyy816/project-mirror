# ADR-008：OpenAPI 单向生成 TypeScript Client

## Status

Accepted — 2026-08-15

## Context

Python 与 TypeScript 手写重复契约会无声漂移。

## Decision

FastAPI/Pydantic 是 HTTP schema 来源：生成 OpenAPI，再生成 `packages/contracts` 类型与 typed client。生成文件标记不可手改，CI 重生成后执行 `git diff --exit-code`。

## Alternatives

双写 interface；GraphQL；TypeScript 反向生成 Python。

## Consequences

契约变化集中且可审计；开发者必须同步生成文件，CI 需要 Python 与 Node 工具链。
