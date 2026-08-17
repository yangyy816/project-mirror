# ADR-034：V03 最小 Runtime Closure 加固

## Status

Accepted

## Context

ADR-032 与 ADR-033 冻结的 `MEDIAPIPE_SOURCE_BUILD_ZERO_TELEMETRY_V1` 已在 Linux 产生可复现的
Face Landmarker C ABI artifact，并正在执行 Windows 可复现构建。Stage B 供应链审计仍有两个不能靠
声明绕过的阻断项：

- OpenCV `3.4.11` 的已构建 `core` module 包含 `CVE-2019-14493` 所在的 persistence parser。NVD 将
  问题定位为 `cv::XMLParser::parse` 空指针解引用；OpenCV upstream commit
  `5691d998ead1d9b0542bcfced36c2dceb3a59023` 为 XML、JSON 与 YAML persistence parser 增加
  null-pointer checks。Face Landmarker 当前不消费 XML/YAML/JSON FileStorage input，但已编译 surface
  不能仅凭未观察到调用而宣告安全。
- TensorFlow Lite 通用 `BuiltinOpResolver` 注册 `RFFT2D`，使 OouraFFT `fftsg.c` 进入最终 main
  binary。OouraFFT notice 明确允许 use/copy/modify，但只明确允许分发 `ORIGINAL package`，不足以批准
  Project Mirror 修改后 binary 的再分发。已固定 Face Landmarker bundle SHA-256
  `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`；使用冻结 TFLite schema
  解码其三个内嵌模型后，`RFFT2D` 与 `IRFFT2D` operator count 均为零。

## Decision

- 新增前向 change control `CC-P2-M3-02`；其已冻结实现缺陷使用 `P2-M3-R08...` Repair Task，
  不把架构或许可证变化包装成 Repair。在不改变 Face Landmarker graph、model bytes、threshold、
  result shape 或第一方 `SyntheticVisionRequest` / `SyntheticVisionResult` contract 的前提下加固 V03
  closure。
- 对 OpenCV `3.4.11` source overlay 回移植 upstream
  `5691d998ead1d9b0542bcfced36c2dceb3a59023` 中适用于当前 snapshot 的 persistence parser null
  checks。不得通过隐藏 Grype finding、仅写不可达结论或放宽 malformed-input Gate 关闭
  `CVE-2019-14493`。该 upstream commit 使用较新的 C++ parser layout；当前锁定的 `3.4.11`
  snapshot 使用 legacy C parser layout，因此回移植必须保持等价检查语义并以 exact archive
  apply test 与 malformed-input negative control 证明，不得直接复用不匹配的 hunk context。
- 从 V03 专用 TensorFlow Lite resolver closure 中删除 `RFFT2D` registration、`rfft2d.cc`、
  `@fft2d` 与对应 header dependency。不得增加替代 FFT dependency。该裁剪只适用于 Face
  Landmarker 专用 candidate，不成为通用 TensorFlow Lite runtime policy。
- model operator inventory 必须继续证明三个内嵌 TFLite model 不引用 `RFFT2D` / `IRFFT2D`。Stage C
  必须以同一 bundle 完成 import/load、one-face、multi-face negative control 和 shutdown；任何 missing
  operator 或结果语义失败都使该裁剪 `FAIL`。
- Linux 与 Windows 必须从相同 source commit 和完整 patch sequence 重新执行 fresh clean build。
  每个平台两个独立 clean roots 的 main/OpenCV artifacts 必须 byte-identical，且不得包含私有 root、
  OouraFFT function symbols 或新增 network surface。
- 既有失败与 pre-hardening build 都保留为 attempt evidence，不覆盖、不删除、不充当最终 artifact。

## Alternatives Considered

- 仅以 Face Landmarker 不调用 FileStorage 为由接受 vulnerable OpenCV core。
- 依赖漏洞扫描器的 source-version finding，而不核对 upstream location 与 fix。
- 在 OouraFFT notice 含糊时自行推定 modified-binary redistribution 获准。
- 保留 OouraFFT，等待外部法律结论后再继续 Stage B。
- 引入新的 FFT implementation 或升级 OpenCV/TensorFlow Lite，从而扩大当前 candidate scope。

## Consequences

V03 的 final artifact closure 会更小，并能用 source patch、operator inventory、symbol scan 与 runtime
negative control 闭合两个现有阻断项。代价是当前 Windows build 只能作为 pre-hardening toolchain/
reproducibility attempt；R08 后必须重跑 Linux 与 Windows clean reproduction。该决定不批准 model/data
rights，不批准 production/runtime adoption，也不授权 V02 calibration 或 identity registration。

## Security / Privacy Considerations

- parser hardening 不允许新增文件格式、codec、网络、动态下载或任意路径输入。
- RFFT closure removal 不得把 model operator inventory、model bytes、private path 或 raw inference
  result 写入 Git、日志或公开 artifact。
- 所有 runtime 检查继续使用 synthetic-only private fixtures，并在 Windows/Linux process-level egress
  deny/capture 下执行。
- upstream wheel 的 Clearcut failure 仍是 negative control；source build 不得复用 rejected wheel。

## Testing Implications

- 验证 upstream fix provenance、patch apply/reverse-apply 与 patch SHA-256。
- 对 OpenCV persistence parser 添加 malformed XML/JSON/YAML negative tests，证明错误返回而非 crash。
- 对固定 Face Landmarker bundle生成 operator inventory，断言 `RFFT2D`/`IRFFT2D` 为零。
- 两个平台分别执行 two-root clean build、SHA-256/cmp、private-path、PE/ELF、imports/exports、network
  symbol 与 OouraFFT symbol scan。
- Stage C 在零出站环境下执行同一 frozen bundle 的完整 capability 与 negative controls。
