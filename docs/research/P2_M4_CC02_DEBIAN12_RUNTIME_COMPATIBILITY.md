# P2-M4 CC02 — Debian 12 Runtime Compatibility Gate

## Status

- Change control: `CC-P2-M4-02`
- State: `PASS`
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

## Qualification evidence

- Builder image: `project-mirror-p2m4-opencv5-debian12-builder:cc02`, manifest-list digest
  `sha256:2ed1ff4589d34f74df0dd9e8440d5ff712b625e3b984a9937e4ec5446efee223`.
- Exact base: `python:3.13.1-slim@sha256:031ebf3cde9f3719d2db385233bcb18df5162038e9cda20e64e08f49f4b47a2f`.
- Toolchain: GCC/G++ `12.2.0`, binutils `2.40`, glibc `2.36`; direct builder packages are pinned in
  `Dockerfile.debian12`.
- Direct builder copyright-file SHA-256 values are binutils
  `a81bdd422c2c015deca84bf6ad249bf0d7d19885fc01d1894463291b0b7313e1`, build-essential
  `5ac244848c8571fcd7044b0c3778cde9e068ce169227b0354a1be519b695358f`, CMake
  `b70ca2018b7fd516ac9b9953678c1a9733eb9e15f3cfbe9b26c137ef0dbd5782`, Ninja
  `1134fe05b5a52ce2a81fb233e421655bb45e5fdb74164478ea85343baf52b86` and patch
  `8c70d7b0af209abe627c97cd21883931b891c820d0a4affcc10b789a23538a0d`; these builder tools are not
  copied into the private runtime.
- R10 preserves the first two private build roots as failed-attempt evidence after their OpenCV
  build-info string exposed `/work/...`. It rebuilds from fixed `/usr/src/...` roots only; source,
  R08 patch, modules, zlib, ABI, algorithm, fixtures and thresholds are unchanged.
- The two R10 clean roots are byte-identical for all five runtime files:
  - wrapper `1fca403721b0ea2adb5a7529aa41d3a8f65813635378ea1a7c69973764f99e49`;
  - core `00f6f16794afeafd06fe6ed596c75e6173199a344242b0eb1d5bdb3197eda8eb`;
  - flann `50f7b0d5883b49b6d114f58d1c74560f780603dedc7c876039db3991bb788f79`;
  - geometry `e021428b8080794899bb36c7be7d8bc3ea4187cda47c3cd8d989d5b3768f9d36`;
  - imgproc `d8ee4b5211369ffbe5f27b68587ae34c5bb75979c41b08b83495dd8869efd6c9`.
- Both reports retain deterministic digest `ebfee6e904e75b1cf147a4259904ab53145568d1940f6f272b9e1a595f95b62c`,
  the original fixture hashes and every preregistered negative-control result. Runtime private-path
  and network-symbol scans are zero; all libraries use relative `$ORIGIN`.
- Maximum required symbols are `GLIBC_2.35`, `GLIBCXX_3.4.30` and `CXXABI_1.3.13`, compatible with
  the standard Debian 12 image.
- The exact standard API image `sha256:9171d0d497fb48ad8381a81e77146e700634c20d113a78715291eb7b6ab0b660`
  ran the real T05 adapter under `--network none`. It produced `changed_pixel_count=1895`, result
  SHA-256 `5f7868d5538134c3a85fdb91a02c02a0bcfbb009e8fd717298447e2c5bf8e0bb` and runtime manifest
  digest `5d0e9ee323d7daea78e8baaeec63917c7a1867301ec5f7c71685fa9cbed311d8`.
- Deterministic CycloneDX 1.6 runtime SBOM SHA-256 is
  `641a93add13ba87dcc61480a3756ef9f6d2c0605f8c5ee02c29e96329bbd0390`. Offline Grype `0.117.0`
  with valid database schema `v6.1.9`, built `2026-08-16T06:14:30Z`, reports zero matches; result
  SHA-256 is `1c28957b3aa6cc18287b20c35f043d1a56f07008191f36718c8145d699b67057`.

`CC_P2_M4_02: PASS`

This closes only the Linux deployment-compatibility repair. It does not itself accept T05 or open
T06; those transitions still require the complete T05 tracked validation and Principal acceptance.
