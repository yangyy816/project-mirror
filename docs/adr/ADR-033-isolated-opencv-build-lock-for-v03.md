# ADR-033：V03 隔离构建的最小 OpenCV Source Lock

## Status

Accepted for isolated build research — 2026-08-17

## Context

ADR-032 的最小 Face Landmarker C ABI target 在 Linux CPU configured closure 中仍通过
`image_to_tensor_converter_opencv` 依赖 OpenCV。上游默认路径把 `linux_opencv` 指向构建机
`/usr`，无法满足可复现供应链 Gate；切换 `OPENCV=source` 后，上游固定为 OpenCV 3.4.11，
但其 archive 未声明 SHA-256，且默认 CMake 配置会构建八个模块并允许 IPPICV、视频、UI、
系统库探测或额外下载。

该依赖不能被静默解释为 Project Mirror 对 OpenCV 的通用采用。Face Landmarker CPU
preprocessing 的 configured path 实际只需要 OpenCV `core` 与 `imgproc`，输入是已由 Pillow
规范化和校验的 synthetic pixel buffer，不由 OpenCV 解码不可信图片。

## Decision

- 仅为 `MEDIAPIPE_SOURCE_BUILD_ZERO_TELEMETRY_V1` 的私有、隔离 Stage B build，允许使用
  upstream MediaPipe `v0.10.35` 所声明的 OpenCV `3.4.11` source snapshot。
- Archive SHA-256 固定为
  `10898a0268d8f8cbaf0354ddd1d9de6abaac84e3d9a6c9754f56a0aa3383d73b`；Bazel cache
  实际 bytes 与该值一致。Exact-source `LICENSE` 为 3-clause BSD，SHA-256 为
  `a5a7cf90fe5ac9763baad852cf69cf9d9b89bff934a679fdc5c8fcecaeba9a25`。
- 新增独立 build-lock overlay
  `mediapipe-v0.10.35-build-lock-v1.patch`，SHA-256
  `6b0d8771c1d1660abb6ee4cfca7a88b04ebb787faa36c8fd9cd15ecdbd3ecafa`。它不修改
  Face Landmarker graph、model、threshold、coordinate 或 first-party Vision contract。
- Overlay 只构建 OpenCV `core,imgproc`，并显式关闭 IPP/TBB/OpenMP、FFmpeg/GStreamer、
  GTK/Qt、JPEG/PNG/TIFF/OpenEXR/WebP、OpenCL、Eigen/LAPACK、V4L/1394、Java、docs、apps、
  tests 与 examples。任何 build-time secondary download 或未声明系统库使 Stage B fail closed。
- Linux build 必须在 target repositories 已预取并冻结后以 `--network none` 执行；缺少输入时
  失败，不临时打开网络补齐。Windows 必须使用同一 source/runtime patch/build-lock overlay，
  另行冻结 exact compiler/toolchain。
- OpenCV 3.4.11 是旧 snapshot，不能成为 Project Mirror production/runtime dependency，不能
  进入 manifests、lockfiles、normal images、Git binaries 或 M4 的 OpenCV 选型。最终 artifact
  仍须经过漏洞、native dependency、license/NOTICE、symbol/string、zero-network 与平台一致性 Gate。
- OpenCV 3.4.11 build 成功不批准 MediaPipe runtime、Face Landmarker model/data、P2-M3 Gate
  或生产 facial processing。

## Alternatives Considered

- 继续使用构建机 `/usr` 中未固定的 `linux_opencv`。
- 允许 OpenCV CMake 在构建时下载 IPPICV 或自动发现视频/UI/system dependencies。
- 在 V03 中改用 OpenCV 5.0，从而同时改变 upstream build baseline 与 preprocessing behavior。
- 重写 image-to-tensor preprocessing，改变 ADR-032 禁止变化的模型输入语义。
- 因 OpenCV 依赖而接受官方 MediaPipe wheel 的 Clearcut telemetry。

## Consequences

V03 获得一个可审计、最小且可离线失败的 OpenCV build closure，同时保留 OpenCV 通用候选的
`POC_REQUIRED` 状态。代价是必须审计旧 snapshot 的漏洞与数值/platform behavior；任一结果
不合格时 V03 返回 `FAIL` 或 `FURTHER_RESEARCH`，不能通过放宽 Gate 继续。

## Security / Privacy Considerations

OpenCV 只接收 canonical synthetic pixels，不负责 JPEG/PNG/WebP decode，不接触真人或用户资产。
构建与产物保持在 ignored private storage；提交内容仅含版本、哈希、许可、aggregate outcome 和
patch。运行时仍必须零网络，且不得包含 telemetry、HTTP、socket、CA-bundle 或动态更新路径。

## Testing Implications

- configured cquery 必须证明 target 不再引用 `linux_opencv=/usr`；
- resolved evidence 必须覆盖全部 target repositories，且 OpenCV archive 在解析前已有 SHA-256；
- offline build 不能产生二次下载；
- artifact 必须只动态依赖 allowlisted platform/runtime libraries，并保留所需 notices；
- Windows/Linux calibration 和 holdout 使用相同 QAPolicy version，平台偏差超阈值即失败。
