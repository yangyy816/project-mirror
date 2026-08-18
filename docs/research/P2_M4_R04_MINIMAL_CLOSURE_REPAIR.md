# P2-M4-R04 Minimal OpenCV Closure Repair

## Status

- Task: `P2-M4-R04`
- Parent candidate: `OPENCV_5_0_0_MINIMAL_CORE_IMGPROC_V1`
- Scope: private synthetic and non-human geometry research only
- State: `PREREGISTERED`

## Trigger evidence

Two fresh Linux configurations completed under the frozen builder image and `--network none`, but
their generated Ninja graphs did not match the intended minimal closure:

- OpenCV 5.0.0 made `imgproc` depend on `geometry`, which made `geometry` depend on `flann`;
- `core` and the new TrueType text implementation linked bundled `zlib` even though
  `BUILD_ZLIB=OFF` was supplied;
- `WITH_UNIFONT=ON` attempted the upstream font download and failed only because the container had
  no network;
- the cache retained unrelated default-on candidate flags including AVIF, FlatBuffers, OBSensor,
  Unifont, IPP IW and ITT even where they were not reachable from the selected target graph.

The two configured roots are attempt evidence and must not be reused as passing builds.

## Bounded repair

The exact forward overlay is
`scripts/research/opencv_minimal/opencv-5.0.0-r04-minimal-closure.patch`. It is applied only to fresh
copies of the exact OpenCV 5.0.0 source archive and does all of the following:

- frozen patch SHA-256:
  `b2d727df65468f7cac7bbbc07bdfefad2a9ea8d1e604726833316b72083e3ee7`;

- removes `geometry` from `imgproc`'s build dependency, which also removes `flann`;
- disables gzip-backed `FileStorage` support in `core` and removes its zlib include/link edge;
- excludes the unused TrueType `drawing_text.cpp` implementation and its compressed-font/zlib
  closure;
- removes the Unifont download path entirely.

The Project Mirror wrapper uses only bounded in-memory RGB `uint8` `remap`; it does not expose
OpenCV `FileStorage`, font, file, URL, codec, geometry, FLANN or allocator APIs. Removing those
unexposed facilities is therefore within the frozen private adapter boundary. This overlay does not
claim to produce a general-purpose OpenCV distribution.

All new configurations must additionally set these default-on flags explicitly to `OFF`:

```text
BUILD_IPP_IW=OFF
BUILD_ITT=OFF
WITH_AVIF=OFF
WITH_FLATBUFFERS=OFF
WITH_OBSENSOR=OFF
WITH_UNIFONT=OFF
```

The original frozen flags and all numerical, platform, reproducibility, footprint, vulnerability,
license and zero-egress thresholds remain unchanged.

## Pre-build gates

Before compilation, each fresh configured graph must prove:

- the patch applies cleanly to the exact admitted source;
- `opencv_modules` contains only `opencv_core` and `opencv_imgproc`;
- `opencv_imgproc` has no `opencv_geometry`, `opencv_flann` or zlib edge;
- `opencv_core` has no zlib edge;
- no download, Unifont, AVIF, FlatBuffers, OBSensor, IPP IW or ITT target is reachable from the build
  or install targets;
- configuration still occurs under `--network none`.

If the overlay does not compile cleanly, introduces unresolved symbols, or requires broader API
removal, stop this candidate as `FURTHER_RESEARCH`; do not expand the patch after observing runtime
results and do not restore the full wheel.

## Boundaries

No project dependency, lockfile, production image, public API, model, weight, User Asset, real face
or QuestionBank release changes are authorized. A successful repair can only resume the already
preregistered T04 private synthetic PoC.
