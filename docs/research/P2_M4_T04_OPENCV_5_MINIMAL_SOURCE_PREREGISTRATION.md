# P2-M4-T04 OpenCV 5 minimal source-build preregistration

## Status and scope

- Status: `PREREGISTERED_NOT_BUILT`
- Frozen at: `2026-08-18T16:45:00+08:00`
- Candidate ID: `OPENCV_5_0_0_MINIMAL_CORE_IMGPROC_V1`
- Parent: ADR-036 and the P2-M4 geometry-variant research protocol
- Predecessor: wheel candidate `OPENCV_PYTHON_HEADLESS_5_0_0_93_V1` returned
  `FURTHER_RESEARCH`

This candidate tests whether a source-built closure can retain the wheel candidate's deterministic
`remap` behavior without its FFmpeg, video, model, GUI, codec and network-capable distribution
surface. It authorizes only private synthetic M4 research.

## Exact sources and toolchains

- OpenCV tag: `5.0.0`.
- Official tag archive SHA-256:
  `b0528f5a1d379d59d4701cb28c36e22214cc51cf64594e5b56f2d3e6c0233095`.
- `SOURCE_DATE_EPOCH`: `1780743154`, the official release publication timestamp.
- Windows: Visual Studio Build Tools `17.14.37531.7`, MSVC `14.44.35207`, CMake `4.3.3`, Ninja
  `1.13.2`, x64 Release.
- Linux: existing private builder image
  `project-mirror-p2-m3-v03-builder@sha256:4589fe916d1ff9c116fc45a70aace15102aef27576b0666dd8d7bf144cf8655f`
  with GCC/G++ `14.2.0`, CMake `3.31.6`, Ninja `1.12.1` and Python `3.13.15`.

Using the already-audited builder toolchain does not reuse M3's OpenCV 3.4.11 source, artifact,
runtime or adoption decision. Every OpenCV 5 build starts from the exact archive above in a new
task-owned root.

## Frozen build closure

The OpenCV configure contract is:

```text
BUILD_LIST=core,imgproc
BUILD_SHARED_LIBS=ON
BUILD_TESTS=OFF
BUILD_PERF_TESTS=OFF
BUILD_EXAMPLES=OFF
BUILD_opencv_apps=OFF
BUILD_opencv_python3=OFF
BUILD_JAVA=OFF
BUILD_PROTOBUF=OFF
BUILD_ZLIB=OFF
WITH_1394=OFF
WITH_ADE=OFF
WITH_CUDA=OFF
WITH_DIRECTX=OFF
WITH_DSHOW=OFF
WITH_EIGEN=OFF
WITH_FFMPEG=OFF
WITH_GDAL=OFF
WITH_GSTREAMER=OFF
WITH_GTK=OFF
WITH_IMGCODEC_HDR=OFF
WITH_IMGCODEC_PFM=OFF
WITH_IMGCODEC_PXM=OFF
WITH_IMGCODEC_SUNRASTER=OFF
WITH_IPP=OFF
WITH_ITT=OFF
WITH_JASPER=OFF
WITH_JPEG=OFF
WITH_LAPACK=OFF
WITH_MSMF=OFF
WITH_OPENCL=OFF
WITH_OPENCLAMDBLAS=OFF
WITH_OPENCLAMDFFT=OFF
WITH_OPENEXR=OFF
WITH_OPENGL=OFF
WITH_OPENJPEG=OFF
WITH_OPENMP=OFF
WITH_PNG=OFF
WITH_PROTOBUF=OFF
WITH_QT=OFF
WITH_TBB=OFF
WITH_TIFF=OFF
WITH_V4L=OFF
WITH_VA=OFF
WITH_VA_INTEL=OFF
WITH_VTK=OFF
WITH_WEBP=OFF
CV_ENABLE_INTRINSICS=OFF
CPU_DISPATCH=
ENABLE_LTO=OFF
OPENCV_ENABLE_NONFREE=OFF
OPENCV_GENERATE_PKGCONFIG=OFF
```

An option that OpenCV ignores, silently forces on or replaces with a bundled/system dependency must
be reported from `CMakeCache.txt` and the configure summary. It cannot be treated as disabled merely
because it appeared on the command line.

The only Project Mirror-facing binary is a first-party C ABI shared library that exposes bounded RGB
`uint8` remap over explicit contiguous `float32` maps. It links only OpenCV `core` and `imgproc`, sets
one thread and disables optimized dispatch before execution. It exposes no file, URL, codec, model,
video, GUI, detector or allocator ownership API. The wrapper source and build contract must be
committed and hashed before the first build.

## Evaluation order and immutable gates

1. Commit and hash the wrapper and build contract.
2. Configure two new Windows roots and two new Linux `--network none` roots.
3. Inspect actual configured dependencies before compiling; unexpected codec/network/model closure
   is a hard stop.
4. Build and install each root without fetching additional source.
5. Compare same-platform artifacts and scan paths, timestamps, exports, imports, RPATH and network
   symbols.
6. Generate exact component/license inventory, CycloneDX SBOM and vulnerability disposition.
7. Execute the same preregistered 256/1024 non-human fixtures and negative controls twice per
   platform under process-level zero-egress evidence.
8. Compare Windows/Linux pixels, numeric facts, performance and footprint.

The runtime gates remain those of the wheel V1 protocol: same-platform bit exactness, cross-platform
maximum channel delta `1`, mean delta `0.01`, changed-pixel fraction `0.001`, normalized coordinate
delta `0.000001`, 1024 p95 `100 ms` and installed closure `350 MiB`. This candidate additionally
requires:

- byte-identical same-platform wrapper and OpenCV libraries across the two clean roots;
- zero embedded private build paths after explicit deterministic path normalization;
- Windows import table and Linux dynamic-symbol/dependency scans with no Winsock, WinHTTP, libcurl,
  FFmpeg, GStreamer or socket/connect closure;
- only relative runtime lookup (`$ORIGIN` on Linux; application directory on Windows);
- no critical/high unresolved vulnerability in the configured closure;
- complete Apache-2.0 and actually linked third-party notice inventory;
- Linux runtime succeeds with `--network none`; Windows uses process-scoped outbound deny/capture.

Any reproducibility repair must receive `P2-M4-Rxx`, preserve failed roots and keep these thresholds.
If OpenCV core/imgproc itself cannot meet the closure, license or reproducibility gates, classify the
candidate `REJECTED` or `FURTHER_RESEARCH`; do not restore the full wheel.

## Boundaries

No project dependency, lockfile, production image, User Asset, real face, model, weight, public API or
QuestionBank release changes in T04. A passing result can only unlock Principal consideration of T05
for private synthetic M4.
