# P2-M3-V03 Frozen Build Closure Report

## Decision

`LINUX_CONFIGURED_CLOSURE: PASS`

`SOURCE_BUILD_AUTHORIZED: YES`

`SOURCE_BUILD_APPROVED_FOR_POC: NO`

`BUILD_EXECUTED: YES`

`LINUX_OFFLINE_BUILD: PASS`

`LINUX_ARTIFACT_AUDIT: IN_PROGRESS`

The exact frozen Linux closure now builds successfully with Docker networking disabled. This does
not yet authorize model loading or inference because the Linux license/SBOM/vulnerability review,
the Windows build and both-platform runtime qualification remain open.

## Frozen source and patches

- MediaPipe source: tag `v0.10.35`, commit
  `f8ef212d5c962c0e853db7e59d217056b187084b`.
- Runtime/network-removal patch SHA-256:
  `cdde123e56bcd637726d7162171a75bed10de415cd323aa95952b1cba7e942eb`.
- Build-lock overlay SHA-256:
  `6b0d8771c1d1660abb6ee4cfca7a88b04ebb787faa36c8fd9cd15ecdbd3ecafa`.
- Cross-platform version-stamp repair overlay SHA-256:
  `a59578edba3a6c350ef78850b26e6cbf5f5929a32048c5199f92b4c526a27823`.
- The runtime and build-lock patches pass reverse-apply validation against the inspected private
  working tree. The repair overlay passes apply-check against that frozen patched tree.

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

## Offline Linux build evidence

The first `--network none` build reached 4,125 of 4,610 actions and failed because upstream
`stamp_metadata_parser_version` preserved a carriage return from the Windows CRLF checkout. The
generated C++ header therefore split the `1.5.0` string literal. This was a deterministic source
portability defect, not a missing repository, secondary download or OpenCV failure.

`P2-M3-R04` adds only the version-stamp repair overlay above. It strips `CR` from the extracted
schema version and does not change the graph, model, dependency set, compiler flags or runtime
surface. The retry used the same builder digest, source/output volumes, read-only repository cache,
configured flags, four-job limit and `--network none`; it completed all 4,610 actions.

Initial artifact facts:

- Face Landmarker C ABI shared library: 68,714,008 bytes; SHA-256
  `a892ba0976fcd557a9ff2056ae170f765ab68aca99f70607eee0c6989fb94e7b`.
- OpenCV core 3.4.11: 4,715,592 bytes; SHA-256
  `8bd2b27ff69e5c2a17cf675ff5879f6ed69d5a8fcdf93389bd8dc1e3f1b5b17f`.
- OpenCV imgproc 3.4.11: 7,305,944 bytes; SHA-256
  `876c4451d5a70b38b2326db979e13df8dc2ef8d5a97d719632358c73bafadd9c`.
- The main library exports nine versioned entries: the eight required MediaPipe C API/free
  functions plus the `VERS_1.0` version node.
- Dynamic dependencies are limited to the two frozen OpenCV libraries and Linux C/C++ runtime
  libraries. There are no undefined socket, connect, DNS, curl, SSL or HTTP imports.
- No Clearcut, portable Clearcut, certifi or CA-bundle string remains. Generic protobuf type URLs
  and TensorFlow Lite local telemetry/profiler type names remain and must not be misreported as a
  network uploader; runtime egress capture is still mandatory.

All binaries, command logs, symbol listings and private paths remain in ignored private evidence.
No artifact was added to Git or a Project Mirror dependency manifest.

## Next Gate

Complete the Linux notice/license closure, private SBOM and vulnerability review, then freeze and
execute the Windows build with the same source and overlays. A clean-output Linux reproduction is
also required before changing `SOURCE_BUILD_APPROVED_FOR_POC`.

Windows toolchain and build remain mandatory and pending. No model execution, calibration, holdout or
identity registration is authorized by this report.

`PROJECT_DEPENDENCIES_ADDED: NONE`

`MODEL_ARTIFACTS_ADDED: NONE`
