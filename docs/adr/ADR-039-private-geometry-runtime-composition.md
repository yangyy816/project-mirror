# ADR-039：私有 Geometry Runtime 组合边界

## Status

Accepted — 2026-08-18

## Context

P2-M4-T05 已接受的 `OpenCvGeometryTransform` 只能通过 exact-hash manifest loader 从私有 native
runtime root 构建。T06 入口核验发现，现有 typed `Settings` 和 provider factory 没有表达该 root 或
transform provider 的能力。若 Worker 硬编码路径、直接读取 raw environment，或绕过 loader 注入 native
library，会破坏 Provider Adapter、typed configuration、可替换边界和 production fail-closed。

这是 T06 runtime composition 的前向架构缺口，不是实现 Repair Task。

## Decision

- `Settings` 新增 `geometry_transform_provider`，只允许 `disabled` 或 `private_opencv`，默认
  `disabled`；新增可选 `geometry_runtime_root`，只接受绝对路径。
- `private_opencv` 必须同时配置 root；`disabled` 不接受悬空 root。配置错误只返回 allowlisted 原因，
  不回显路径。
- 单一第一方 factory 根据 typed settings 调用 `load_private_opencv_runtime(Path)`，再构造
  `OpenCvGeometryTransform`。业务、application、Job 和 task adapter 不直接读取环境变量、加载 DLL/SO
  或接收 native/SDK 类型。
- loader 继续是 runtime identity authority：平台文件集合、SHA-256、symlink、ABI、candidate/version 和
  manifest digest 必须全部通过后才返回。factory 不提供 fallback、PATH search、自动下载或联网。
- `private_opencv` 只可用于 development/test/CI 中的 private synthetic M4 execution。production 必须
  保持 `disabled` 且 root 未配置；该 change control 不批准 production geometry 或真人处理。
- T06 的 Worker runtime 必须通过 factory 注入 `GeometryTransform` port。task message、Job payload、日志、
  API 响应和 CI artifact 不得包含 runtime root。
- 不修改 schema、migration、public API、dependency manifest、runtime binaries 或 M3 frozen authority。

## Alternatives Considered

- 在 Worker 中硬编码私有 runtime 路径。
- 由 application service 读取环境变量并直接加载 native library。
- 将 runtime root 写入 Job/task payload。
- 依赖系统 PATH 或项目级 OpenCV package。
- 在 provider disabled 时静默回退到 fake transform。

## Consequences

T06 可以通过一个 typed、可替换且 fail-closed 的 composition root 使用已接受的 private runtime。部署或
测试 harness 负责显式挂载并配置 ignored runtime root；仓库和消息不持久化该路径。缺失、相对、额外文件、
hash mismatch、ABI mismatch 或 production enablement 均在读取 source image bytes 前失败。

## Security / Privacy Considerations

仅处理 private synthetic M4 assets。无下载、网络、真实人物、User Asset、敏感分类或生产能力。下载授权与
T05 private runtime approval不改变 production、distribution、license 或 real-user Gate。

## Testing Implications

覆盖 provider/root 组合、绝对路径、production rejection、disabled fail-closed、factory 单一路径、loader
错误传播、无 fallback/网络/import side effect 和错误消息不泄露 root。T06 另验证真实 Worker/Celery 注入、
zero-network、lease/retry/cancel/reconcile 和 exactly-one result authority。
