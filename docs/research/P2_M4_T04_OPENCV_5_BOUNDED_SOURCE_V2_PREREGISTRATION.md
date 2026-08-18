# P2-M4-T04 OpenCV 5 Bounded Source V2 Preregistration

## Candidate identity

- Candidate ID: `OPENCV_5_0_0_BOUNDED_TRANSITIVE_SOURCE_V2`
- Parent: ADR-036 and the P2-M4 geometry-variant research protocol
- Scope: private synthetic and non-human geometry research only
- State: `PREREGISTERED`

This candidate tests the smallest unmodified OpenCV 5.0.0 source closure that the upstream module
graph actually supports. It does not reuse the full Python wheel and does not carry forward the R04
or R05 source overlays.

## Frozen source and toolchains

- OpenCV source: exact `5.0.0` archive, SHA-256
  `b0528f5a1d379d59d4701cb28c36e22214cc51cf64594e5b56f2d3e6c0233095`.
- Linux builder:
  `project-mirror-p2-m3-v03-builder@sha256:4589fe916d1ff9c116fc45a70aace15102aef27576b0666dd8d7bf144cf8655f`.
- Windows: VS Build Tools `17.14.37531.7`, MSVC `14.44.35207`, CMake `4.3.3`, Ninja
  `1.13.2`.
- Linux: GCC/G++ `14.2.0`, CMake `3.31.6`, Ninja `1.12.1`, Python `3.13.15`.
- First-party wrapper and C ABI remain the exact committed sources from `e2c7f7e`; their frozen
  digests and interface do not change.

## Admitted build closure

The configure request remains `BUILD_LIST=core,imgproc`, but this V2 protocol explicitly admits the
actual upstream transitive module closure:

```text
opencv_core
→ opencv_flann
→ opencv_geometry
→ opencv_imgproc
```

It also admits the exact bundled zlib source already contained in the OpenCV archive because the
frozen Linux builder does not provide a matching development package and upstream OpenCV treats zlib
as required by core and imgproc. Zlib is statically linked into the OpenCV libraries and is not a
separate Project Mirror-facing API.

No other module or third-party library is admitted. In particular, FFmpeg, OpenSSL, GStreamer,
imgcodecs, videoio, highgui, DNN, protobuf, FlatBuffers, AVIF, JPEG, PNG, TIFF, WebP, OpenEXR,
OpenJPEG, IPP, ITT, OpenCL, TBB, OpenMP, GUI, camera and model support remain disabled.

`WITH_UNIFONT=OFF` is mandatory so configuration has no font download attempt. The remaining frozen
V1 flags and the explicit R04 default-off flags remain mandatory, except that V2 uses unmodified
source and therefore does not claim `BUILD_ZLIB=OFF` removes the bundled fallback.

## Pre-build gate

Two fresh roots per platform must prove before compilation:

- exact source checksum and zero patch/overlay;
- actual modules are exactly `core;flann;geometry;imgproc`;
- bundled zlib is the only third-party build target;
- no downloader, codec, video, GUI, DNN, model, telemetry or network-capable target is reachable;
- configuration completes with Linux `--network none` and no download attempt.

Any additional actual closure is a hard stop.

## Evaluation order

1. Commit this protocol before the first V2 build.
2. Configure two fresh Linux roots and inspect the generated graph.
3. Build/install both roots under `--network none`; require byte-identical same-platform OpenCV
   libraries after permitted deterministic path normalization.
4. Build the frozen first-party wrapper against each install and inspect dependencies, exports,
   private paths, RPATH and network symbols.
5. Repeat with two clean Windows roots and process-scoped outbound deny/capture.
6. Generate component/license inventory, CycloneDX SBOM and vulnerability disposition for OpenCV,
   FLANN, geometry and bundled zlib.
7. Run the unchanged 256/1024 non-human fixtures and negative controls twice per platform.
8. Compare cross-platform pixels, facts, performance and installed footprint.

## Unchanged gates

- same-platform output and accepted build artifacts must be bit exact;
- cross-platform maximum channel delta `1`, mean delta `0.01`, changed-pixel fraction `0.001` and
  normalized coordinate delta `0.000001`;
- 1024 p95 below `100 ms` and installed closure below `350 MiB`;
- no private build paths, absolute runtime lookup, Winsock, WinHTTP, libcurl, FFmpeg, GStreamer,
  socket/connect closure or unresolved critical/high vulnerability;
- complete Apache-2.0 and zlib notice inventory;
- Linux runtime under `--network none`; Windows process-scoped outbound deny/capture.

## Stop rules and boundaries

Stop as `REJECTED` for network-capable imports, license incompatibility, unresolved critical/high
vulnerability or checksum mismatch. Use `FURTHER_RESEARCH` for reproducibility, footprint,
performance or bounded-closure failure.

No project dependency, lockfile, production image, public API, model, weight, User Asset, real face
or QuestionBank release change is authorized. A passing V2 result can only unlock Principal
consideration of T05 for private synthetic M4.
