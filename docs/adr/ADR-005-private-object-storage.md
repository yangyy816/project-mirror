# ADR-005：私有对象存储

## Status

Accepted — 2026-08-15

## Context

人脸与派生图是高度敏感数据，公共 URL 会绕过授权与删除控制。

## Decision

生产使用私有腾讯云 COS；访问必须经服务端授权与短时签名 URL。开发 Local storage 只在非生产启用。

## Alternatives

公开桶随机 key；数据库存 blob；永久 CDN URL。

## Consequences

每次访问可授权和审计；增加签名、缓存与过期处理复杂度。
