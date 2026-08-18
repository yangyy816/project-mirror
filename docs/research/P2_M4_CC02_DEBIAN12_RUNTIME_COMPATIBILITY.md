# P2-M4 CC02 — Debian 12 Runtime Compatibility Gate

## Status

- Change control: `CC-P2-M4-02`
- State: `EXECUTING`
- Triggered: 2026-08-18
- Candidate under test: `OPENCV_5_0_0_DEBIAN12_COMPAT_V3`
- Scope: private synthetic P2-M4 only

## Trigger evidence

The accepted T04 source/runtime candidate passed Windows and Linux builder tests, but T05 integration
tested the exact Linux artifacts against the repository's actual API base image for the first time.
The image is `python:3.13.1-slim` on Debian 12 with glibc 2.36. The accepted Linux binary requires
`GLIBC_2.38` and `CXXABI_1.3.15`; the dynamic loader therefore rejects it before any image bytes are
processed. This is an honest fail-closed compatibility result, not an adapter or fixture failure.

The exact Windows runtime loads and the T05 adapter produces deterministic output. The exact Linux
runtime loads in its qualified newer builder image and produces the same canonical output SHA-256,
but that does not satisfy the standard Project Mirror Docker boundary.

## Forward decision

T05 must not be accepted and T06 must not begin with the incompatible artifact. The standard API
base image will not be upgraded as a shortcut because that would expand T05 into deployment and
supply-chain scope. Instead, T04 is reopened only for a deployment-compatible Linux rebuild while
the already-qualified source, R08 conditional patch, module closure, C ABI, algorithm, fixtures,
limits and Windows runtime remain frozen.

The V3 Linux candidate must:

1. build from exact OpenCV 5.0.0 source SHA-256
   `b0528f5a1d379d59d4701cb28c36e22214cc51cf64594e5b56f2d3e6c0233095`;
2. retain R08 patch SHA-256
   `e42a75d9b42584197ba444eda90b001da1120e72e68327e573dd77d8fc802da3`;
3. retain the exact first-party `ctypes-c-v1` wrapper and bounded RGB/remap contract;
4. build in an exact Debian 12-compatible toolchain and record compiler, linker, libc and image
   identity;
5. produce two clean-root byte-identical Linux builds;
6. preserve the admitted `core,flann,geometry,imgproc` plus static zlib closure and relative
   `$ORIGIN` loading;
7. pass the original deterministic, negative, resource, network, license, SBOM and vulnerability
   Gates without changing thresholds;
8. load and execute the T05 adapter in the actual `project-mirror-foundation-api` image with
   `--network none` and produce the same non-human fixture output as Windows.

Any source, algorithm, ABI, module, fixture or threshold change requires a separate decision. V3
approval would replace only the private Linux runtime identity; it would not approve a package,
production/distribution use, User Assets, real-user facial processing or QuestionBank release.

## Stop rule

If two clean Debian 12 builds are not byte-identical, the closure expands, the current API image
cannot load the result, deterministic output changes, or a security/license Gate regresses, classify
V3 as `FURTHER_RESEARCH` or `FAIL`. Do not weaken the standard image compatibility check and do not
advance T05.
