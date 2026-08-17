# P2-M3-V03 Frozen Build Closure Report

## Decision

`LINUX_CONFIGURED_CLOSURE: PASS`

`SOURCE_BUILD_AUTHORIZED: YES`

`SOURCE_BUILD_APPROVED_FOR_POC: NO`

`BUILD_EXECUTED: NO`

This report authorizes the next bounded Stage B action only: an offline Linux build from the exact
frozen source, runtime patch and build-lock overlay. It does not authorize model loading or inference.

## Frozen source and patches

- MediaPipe source: tag `v0.10.35`, commit
  `f8ef212d5c962c0e853db7e59d217056b187084b`.
- Runtime/network-removal patch SHA-256:
  `cdde123e56bcd637726d7162171a75bed10de415cd323aa95952b1cba7e942eb`.
- Build-lock overlay SHA-256:
  `6b0d8771c1d1660abb6ee4cfca7a88b04ebb787faa36c8fd9cd15ecdbd3ecafa`.
- Both patches pass reverse-apply validation against the inspected private working tree.

## Linux toolchain

- Builder image ID and repository digest:
  `sha256:4589fe916d1ff9c116fc45a70aace15102aef27576b0666dd8d7bf144cf8655f`.
- Base image:
  `python@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a`.
- Bazel: `7.4.1`; Linux binary SHA-256:
  `c97f02133adce63f0c28678ac1f21d65fa8255c80429b588aeeba8a1fac6202b`.
- Compiler: Debian GCC `14.2.0-19`; Python: `3.13.15`; CMake: `3.31.6`; Ninja: `1.12.1`.
- Bazel hermetic Python repository: CPython `3.12.8`, archive SHA-256
  `b9d6ee5ddac1198e72d53112698773fc8bb597de095592eb849ca794306699ba`.

The private builder inventory contains 183 Debian package records and has SHA-256
`3e1b20f7a0da2a214f204e94fc9f4fc26aa9432058d2693ffd8016483084a405`. It must be retained
with the final SBOM evidence. No builder image or compiler is adopted into Project Mirror runtime
images.

## Configured dependency evidence

Unconfigured `bazel query deps(...)` was rejected as evidence because it expands every `select()`
branch, including unused WebGPU targets. The authoritative command is configured `cquery` with:

```text
--config=linux
--define=MEDIAPIPE_DISABLE_GPU=1
--define=OPENCV=source
HERMETIC_PYTHON_VERSION=3.12
```

The locked configured closure contains 22,738 labels and 39 external/generated repositories.
Dependency-label evidence SHA-256 is
`7c01ef95691f87718d9de1e0f66a6363955ee70cdc323ff91a66b3c08a7f1e38`.
Resolved-repository evidence SHA-256 is
`2052599174df6f78ea2db8d667959fdd9c13653fbaac9aa606e84fecfcb72aee`.
All 39 target repositories were resolved; unresolved target repositories: zero.

## OpenCV closure

The CPU graph reaches OpenCV only through:

```text
Face Landmarker graph
→ image preprocessing graph
→ image-to-tensor calculator
→ OpenCV converter
→ OpenCV core + imgproc
```

The upstream `/usr` local repository path is prohibited. ADR-033 selects MediaPipe's source snapshot
OpenCV `3.4.11`, adds archive SHA-256
`10898a0268d8f8cbaf0354ddd1d9de6abaac84e3d9a6c9754f56a0aa3383d73b`, reduces the module
set to `core,imgproc`, and disables secondary download/system-video/UI/codec surfaces. The exact
source license is 3-clause BSD. This is an isolated build input, not general OpenCV adoption.

## Next Gate

The Linux build must run with Docker network disabled and the frozen repository cache mounted
read-only. Failure due to a missing repository, CMake download or system dependency is a closure
failure and must not be repaired by opening network. On success, record artifact hashes, exported
symbols, dynamic dependencies, prohibited strings, notices, package inventory, SBOM and vulnerability
results before changing `SOURCE_BUILD_APPROVED_FOR_POC`.

Windows toolchain and build remain mandatory and pending. No model execution, calibration, holdout or
identity registration is authorized by this report.

`PROJECT_DEPENDENCIES_ADDED: NONE`

`MODEL_ARTIFACTS_ADDED: NONE`
