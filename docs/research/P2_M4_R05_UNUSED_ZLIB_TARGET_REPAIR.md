# P2-M4-R05 Unused Global Zlib Target Repair

## Status

- Task: `P2-M4-R05`
- Parent: `P2-M4-R04`
- Candidate: `OPENCV_5_0_0_MINIMAL_CORE_IMGPROC_V1`
- Scope: private synthetic and non-human geometry research only
- State: `PREREGISTERED`

## Trigger evidence

R04 configured two new Linux roots under `--network none`. Both proved that the actual OpenCV module
closure was reduced to `opencv_core;opencv_imgproc`; `geometry`, `flann` and all zlib link edges were
absent. OpenCV's top-level configuration nevertheless included `OpenCVFindLibsGrfmt.cmake`, which
treated zlib as globally required and added `3rdparty/zlib/all` to the default `all` target. Because
`install` depends on `all`, an ordinary build/install would still compile an unused bundled zlib.

The R04 roots remain configure-attempt evidence and must not be compiled.

## Bounded repair

The stacked overlay
`scripts/research/opencv_minimal/opencv-5.0.0-r05-skip-unused-grfmt.patch` removes only the top-level
image-format dependency discovery include. R04 has already removed all zlib consumers from the
private `core,imgproc` closure, and every image codec is disabled by the frozen configure contract.
The patch does not remove or alter `remap`, pixel storage, the first-party C ABI, or any selected
module source.

- frozen patch SHA-256:
  `8f10a176c78b70d5a1ee91f8c2f6630ef9a4340d18669ec69e78bfcd26270f80`.

R05 is applied after the frozen R04 patch to fresh exact OpenCV 5.0.0 source roots. All earlier flags,
thresholds, platform requirements and stop rules remain unchanged.

## Pre-build gates

Before compilation, each new root must prove:

- only `opencv_core` and `opencv_imgproc` are present in `OPENCV_MODULES_BUILD` and
  `opencv_modules`;
- `all` and `install` have no zlib, geometry, flann, downloader, codec, model or network-capable
  dependency;
- no R04/R05 patch fuzz or offset is required;
- configuration completes under `--network none` with no download attempt.

Any new missing dependency or broader source change stops the candidate as `FURTHER_RESEARCH`.

## Boundaries

This remains an isolated private research build. It does not create a general OpenCV distribution,
project dependency, production approval, public API, model, weight, User Asset or real-face path.
