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

## R17 SBOM, license and vulnerability disposition

The authoritative R17 `cquery deps(...)` export contains 22,719 configured labels and zero `fft2d`
or Ooura matches. Regenerating from that graph, rather than the obsolete R05 dependency export,
produced a 51-component CycloneDX closure with SHA-256
`902088a0e70d3ce005885c01f7ee472fba19458ae803e09700df52949d152dda`. The 38-repository license
inventory contains 124 retained files across 32 external repositories; missing roots/files are only
generated local toolchain repositories or the separately reviewed Ninja toolchain. Inventory
SHA-256 is `e1e77546b0a2a8148cc2f6ef6b3dc700305edad16311b09d9a836caa3c2742d3`.

Offline Grype 0.117.0 with valid database schema v6.1.9 built 2026-08-16 reported zero direct matches
against the regenerated source closure. The focused OpenCV 3.4.11 CPE negative control still reports
four version findings, so each was dispositioned rather than hidden:

- `CVE-2019-14493`: the exact core persistence null-check backport is present. R17-linked malformed
  JSON/YAML fixtures reject with `cv::Exception`; the retained upstream XML crash fixture does not
  crash.
- `CVE-2019-15939`: `objdetect/HOG` is not built and `HOGDescriptor` symbols are absent.
- `CVE-2019-19624`: `video/DIS` is not built and `DISOpticalFlow` symbols are absent.
- `CVE-2025-53644`: `imgcodecs/JPEG` is not built; `imdecode` and JPEG decoder symbols are absent.

The exact Face Landmarker bundle remains `PRIVATE_RESEARCH_ONLY`: its three official component model
cards are Apache-2.0, but incomplete training-data and redistribution provenance keeps distribution
and production blocked. That bounded disposition permits the already-authorized isolated Stage C;
it does not create model adoption or commercial approval.

`STAGE_B_ARTIFACT_AUDIT: PASS_FOR_ISOLATED_STAGE_C`

`SOURCE_BUILD_APPROVED_FOR_POC: YES_PRIVATE_SYNTHETIC_ONLY`

Stage C Windows/Linux process-level zero-egress runtime qualification is now the next mandatory Gate.

`PROJECT_DEPENDENCIES_ADDED: NONE`

`MODEL_ARTIFACTS_ADDED: NONE`

## R21 image ABI retention and Stage C closure

R19 retained `MpImageCreateFromUint8Data` and `MpImageFree` on Linux, but the first two Windows
replays omitted both exports. R21 adds only the equivalent MSVC linker-retention directives. The
tracked Linux and Windows repair patches have SHA-256 values
`8838776b861579a9078868150de1475c9f624b032a67715748799bf04d987d31` and
`5bc80bdceea7e902e3af79c59ec1f121b01add2e660831c9aa85d11ac3c1bdb1` respectively.

Fresh Windows roots `bw34` and `bw35` each completed all 4,549 actions. Their three artifact pairs
are byte-identical:

- Face Landmarker DLL: size `30476288`, SHA-256
  `5a904100bf197e8b4755f503aa4d1d8a8892107a9940e2f848eeb302ff24dd8d`.
- OpenCV core DLL: size `2302464`, SHA-256
  `353c960dbc233d6d412dc1015b702321f3a7f8a80494a7142c7e9c3670d61f68`.
- OpenCV imgproc DLL: size `2385408`, SHA-256
  `1aa54040e263be7685f2b8a379cf1f34a275b0718cc8b3a823a1f935c28592b4`.

The main DLL exports the Face Landmarker create/detect/result-close/close functions and the required
image create/free functions. Its dynamic imports are limited to the frozen OpenCV DLLs and Windows
runtime libraries. Main/core/imgproc scans report zero private-build paths, PDB/RSDS references,
Ooura, Clearcut, certifi/CA-bundle, fixed telemetry endpoint or Windows network API imports. The PE
debug directory contains deterministic `coffgrp` and `repro` records, not a PDB reference.

The fixed GCS generation `1683136941468629` bundle was reacquired from the official object metadata:
size `3758596`, SHA-256
`64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`. A private Windows harness
executed the full create -> image-create -> detect -> result-free -> image-free -> close lifecycle
three times against the fixed synthetic RGB input. All three runs returned one face and clean close;
the process-specific outbound block plus Filtering Platform failure capture recorded zero outbound
attempts. The temporary firewall rule was removed and the prior audit-policy state was restored.

Linux Stage C had already executed the same model/input lifecycle three times under `--network none`
with `DETECT_OK_COUNT=3`, `FACE_ONE_COUNT=3`, `CLOSE_OK_COUNT=3` and `NETWORK_CALL_COUNT=0`. These
process-level results do not imply that all local TFLite telemetry/profiler types are absent; they
prove zero observed external network invocation for this exact Stage C closure.

During the Windows reproduction, unsafe cleanup of an old Bazel output root followed reparse points
and damaged the private toolchain. The same Visual Studio Build Tools workload contract was restored
and verified as VS `17.14.38`, MSVC `14.44.35207` / compiler `19.44.35228`, and Windows SDK
`10.0.26100.0` before `bw34`/`bw35`. Future cleanup must never recursively traverse Bazel reparse
points; failed roots are evidence, not cleanup targets.

`P2_M3_V03_STAGE_C: PASS_PRIVATE_SYNTHETIC_ONLY`

`POC_RUNTIME_APPROVED: YES_PRIVATE_SYNTHETIC_ONLY`

This closes Stage C for the exact source-built candidate only. The official `0.10.35` wheels remain
rejected, the model remains `PRIVATE_RESEARCH_ONLY`, and distribution, production Vision and
real-user facial processing remain blocked. Stage D calibration/holdout is the next Gate.
