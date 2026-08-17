# P2-M3-V03 Frozen Build Closure Report

## Decision

`LINUX_CONFIGURED_CLOSURE: PASS`

`SOURCE_BUILD_AUTHORIZED: YES`

`SOURCE_BUILD_APPROVED_FOR_POC: NO`

`BUILD_EXECUTED: YES`

`LINUX_OFFLINE_BUILD: PASS`

`LINUX_BIT_REPRODUCIBILITY: PASS`

`LINUX_ARTIFACT_AUDIT: IN_PROGRESS`

`LINUX_DISTRIBUTION_LICENSE_GATE: BLOCKED`

`WINDOWS_OFFLINE_BUILD: PASS`

`WINDOWS_BIT_REPRODUCIBILITY: PASS`

`WINDOWS_ARTIFACT_PATH_AND_NETWORK_SURFACE_AUDIT: PASS`

The exact frozen Linux closure builds reproducibly with Docker networking disabled, and the hardened
Windows closure now builds reproducibly in two fresh roots. This does not yet authorize model loading
or inference: Linux must be replayed with the cross-platform R17 closure, the remaining license/SBOM/
vulnerability review must close, and both-platform Stage C runtime qualification remains open.

## Frozen source and patches

- MediaPipe source: tag `v0.10.35`, commit
  `f8ef212d5c962c0e853db7e59d217056b187084b`.
- Runtime/network-removal patch SHA-256:
  `cdde123e56bcd637726d7162171a75bed10de415cd323aa95952b1cba7e942eb`.
- Build-lock overlay SHA-256:
  `6b0d8771c1d1660abb6ee4cfca7a88b04ebb787faa36c8fd9cd15ecdbd3ecafa`.
- Cross-platform version-stamp repair overlay SHA-256:
  `a59578edba3a6c350ef78850b26e6cbf5f5929a32048c5199f92b4c526a27823`.
- `P2-M3-R05` OpenCV reproducibility overlay SHA-256:
  `192056a6ad29362442fe440bf24ea4f998b09172ab0807f91bc9c24a96d41c68`.
  It normalizes foreign-build paths, disables OpenCV RPATH and omits the OpenCV build-report
  wall-clock timestamp. It does not change modules, algorithms, dependencies or runtime behavior.
- `P2-M3-R17` Windows reproducibility/unused-audio closure patch SHA-256:
  `7099bdb0ed223d71110a18148880090f15311220f75e20cb1af6eb9619cca5dc`. It disables the
  toolchain-implied FASTLINK/PDB feature for the minimal Windows DLL and removes unused
  AudioSpectrogram/MFCC/RFFT2D registrations and the resulting Ooura closure.
- `P2-M3-R18` Windows OpenCV build-report path repair SHA-256:
  `b57ed5b0643d830cc9d66ad063eea211cbbab2b50c98df70d2b22f00b102775d`. It replaces only
  absolute Windows compiler/build-tool paths in the OpenCV report with `cl.exe`/`nmake.exe`; Linux
  behavior, modules and algorithms are unchanged.
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

## Windows clean reproduction evidence

The first R17 candidate root, `bw25`, proved that `/DEBUG:NONE` alone was insufficient: Bazel's
Windows `fastbuild` feature appended `/DEBUG:FASTLINK` later in the link action and generated an
RSDS/PDB path. The minimal target now disables that feature while retaining `/DEBUG:NONE`.
Configured `somepath` from the target to `@fft2d//:fft2d` is empty after removal of the unused audio
registrations and sources.

Fresh roots `bw26` and `bw27` each completed 4,549 actions, but a strict scan then found the frozen
MSVC/NMake installation path in `opencv_core3411.dll`'s compiled build report. R18 retained the tool
identity while canonicalizing those three report fields. Fresh roots `bw28` and `bw29` then each
completed the same 4,549-action command with exit code zero. Corresponding artifacts are byte-identical:

- Face Landmarker C ABI DLL: 30,324,736 bytes; SHA-256
  `f99ba0a489d673ff58a1870a9e16037260913dca02912cf304173993e7e5e199`.
- OpenCV core 3.4.11 DLL: 2,302,464 bytes; SHA-256
  `19b1b9bad3c7ad402858f97ccdc0299defbfe1d18f3a3b83bc786d7c3e443c91`.
- OpenCV imgproc 3.4.11 DLL: 2,385,408 bytes; SHA-256
  `1aa54040e263be7685f2b8a379cf1f34a275b0718cc8b3a823a1f935c28592b4`.

All six final DLLs have zero actual private-root, `bw28`/`bw29`, PDB/RSDS, Ooura, Clearcut,
certifi/CA-bundle and Windows network-API matches. Imports are limited to OpenCV, MSVC/CRT,
`dbghelp.dll`, `ADVAPI32.dll` and `KERNEL32.dll`; the main DLL exports 203 symbols and contains all
seven required Face Landmarker lifecycle/detection entries. PE debug directories contain only
deterministic `coffgrp` and `repro` records, not a PDB reference. Exact exports remain inventory
evidence rather than a newly invented Windows export allowlist.

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

Final reproducible artifact facts:

- Face Landmarker C ABI shared library: 68,714,008 bytes; SHA-256
  `a892ba0976fcd557a9ff2056ae170f765ab68aca99f70607eee0c6989fb94e7b`.
- OpenCV core 3.4.11: 4,707,400 bytes; SHA-256
  `048df8097a7c444769e5c56708041aa0c60a48a5a442f2ebad2c60a03097653a`.
- OpenCV imgproc 3.4.11: 7,297,752 bytes; SHA-256
  `765ebf6c659e523d9d7e9557e63f004a041a9327fcba95e6d4ac0670485241f5`.
- The main library exports nine versioned entries: the eight required MediaPipe C API/free
  functions plus the `VERS_1.0` version node.
- Dynamic dependencies are limited to the two frozen OpenCV libraries and Linux C/C++ runtime
  libraries. There are no undefined socket, connect, DNS, curl, SSL or HTTP imports.
- No Clearcut, portable Clearcut, certifi or CA-bundle string remains. Generic protobuf type URLs
  and TensorFlow Lite local telemetry/profiler type names remain and must not be misreported as a
  network uploader; runtime egress capture is still mandatory.

All binaries, command logs, symbol listings and private paths remain in ignored private evidence.
No artifact was added to Git or a Project Mirror dependency manifest.

## P2-M3-R05 clean reproduction evidence

The first repair builds exposed three separate non-reproducible OpenCV inputs: foreign-build source
paths in compiled file names, generated `OPENCV_BUILD_DIR`/`OPENCV_INSTALL_PREFIX` macros, and the
OpenCV configuration wall-clock timestamp. Each defect was retained as failed attempt evidence and
fixed in the single R05 overlay above.

Two new, empty output volumes then executed the same frozen 4,610-action command with the same
builder, source, read-only repository cache, four-job limit and `--network none`. Both completed with
exit code zero. `cmp` returned zero for the main, core and imgproc libraries; all three SHA-256 values
match the final facts above.

All six binaries across the two runs had zero matches for the private output root, workspace,
sandbox, sandbox stash, execroot and action-root patterns. OpenCV core/imgproc have no RPATH or
RUNPATH. The main library retains only the same relative `$ORIGIN` RUNPATH in both runs. The OpenCV
build report contains no wall-clock `Timestamp` field; MediaPipe `Timestamp::*` protocol strings in
the main library are semantic API constants, not build dates.

## Linux supply-chain audit status

- Debian `ninja-build 1.12.1-1` is the exact builder package. Its retained copyright/license file
  SHA-256 is `c6dd93071b285c591075669795794cc31ee34af7d4ed3cdf8c98a3c0bc7c5c01`;
  upstream is Apache-2.0 and bundled `src/getopt.*` carries a public-domain grant.
- Offline Grype `0.117.0` used database schema `v6.1.9`, built `2026-08-16T06:14:30Z`. The focused
  OpenCV source scan reported `CVE-2019-14493`, `CVE-2019-15939`, `CVE-2019-19624` and
  `CVE-2025-53644`. The built closure contains only `core,imgproc`; objdetect/HOG, video/DIS and
  imgcodecs/JPEG findings are outside that module closure. `CVE-2019-14493` still requires a sourced
  reachability/false-positive disposition before approval.
- The previously reproduced Linux main binary contains OouraFFT entry points `cdft`, `rdft`, `ddct`,
  `ddst`, `dfct` and `dfst`.
  The retained notice clearly permits use/copy/modify and distribution of the "ORIGINAL package",
  but modified/binary redistribution is not sufficiently clear for this Gate. Internal isolated
  research may continue; distribution and production remain blocked pending independent license
  judgment or removal of OouraFFT from the closure.

  R17 removes that unused closure on Windows, but the same hardened source must be replayed in two
  fresh Linux roots before the Linux distribution blocker can be closed.

Grype coverage is source/SBOM focused and cannot prove reachability or absence of vulnerabilities by
itself. These findings do not convert the source build into a runtime, model or production approval.

## Next Gate

The R17 hardened closure was replayed in fresh no-network Linux output roots
`pm-p2-m3-v03-r17-clean-output-3` and `pm-p2-m3-v03-r17-clean-output-4`. The earlier
`clean-output-1` root is retained only as failed-attempt evidence because the container started
outside `/workspace`; it is not acceptance evidence. Both accepted roots completed 4,597 actions
with exit code zero.

The accepted Linux artifacts are byte-identical across both roots:

- Face Landmarker C ABI shared library SHA-256:
  `19e90273dc9d370563ba48b2b9a0752a677c429f80b971dd3a6c814c223c1f29`.
- OpenCV core SHA-256:
  `116c2db3b7e149390631af309f910eabeb73bd18281e4174f131ced2a8de4408`.
- OpenCV imgproc SHA-256:
  `765ebf6c659e523d9d7e9557e63f004a041a9327fcba95e6d4ac0670485241f5`.

The main artifact is ELF64 x86-64 and exports the required versioned create, image/video/async
detection, result-free and close functions. Dynamic dependencies are limited to the two frozen
OpenCV libraries and Linux runtime libraries; RUNPATH is relative to `$ORIGIN`. Scans across the
main/core/imgproc closure found zero actual private-host paths, Ooura strings, Clearcut/certifi/CA
bundle strings or known HTTP/Windows network API strings.

This closes hardened Linux build reproducibility and the prior Ooura distribution blocker for this
exact closure. Updated SBOM/license/vulnerability dispositions and both-platform Stage C zero-egress
runtime qualification remain mandatory. Windows and Linux clean reproduction are complete, but
`SOURCE_BUILD_APPROVED_FOR_POC` remains `NO` until the whole Stage B contract and both-platform Stage C
runtime qualification pass. No model execution, calibration, holdout or identity registration is
authorized by this report.

`PROJECT_DEPENDENCIES_ADDED: NONE`

`MODEL_ARTIFACTS_ADDED: NONE`
