# P2-M4-T04 OpenCV 5 Bounded Source V2 Report

## Disposition

- Candidate: `OPENCV_5_0_0_BOUNDED_TRANSITIVE_SOURCE_V2`
- Scope: private synthetic and non-human M4 geometry research only
- Result: `APPROVED_FOR_PRIVATE_SYNTHETIC_M4`
- Project dependency or production approval: no
- Distribution approval: no

The candidate satisfies the preregistered source, closure, reproducibility, deterministic behavior,
resource, zero-network, license, SBOM and vulnerability Gates. This disposition permits Principal
consideration of P2-M4-T05 behind the first-party `GeometryTransform` port after the tracked evidence
checkpoint passes same-SHA CI. It does not authorize a public API, real-user facial processing,
QuestionBank release or M5 isolation conclusions.

## Exact inputs and closure

- OpenCV source archive SHA-256:
  `b0528f5a1d379d59d4701cb28c36e22214cc51cf64594e5b56f2d3e6c0233095`.
- R08 conditional MSVC no-PDB overlay SHA-256:
  `e42a75d9b42584197ba444eda90b001da1120e72e68327e573dd77d8fc802da3`.
- Built modules are exactly `core;flann;geometry;imgproc`.
- Bundled zlib `1.3.2` is the only built third-party target and is statically linked.
- The first-party wrapper retains the frozen `ctypes-c-v1` ABI and in-memory RGB/map boundary.
- No Python OpenCV/NumPy package, model, codec, video, UI, DNN, camera, downloader or Provider SDK
  enters the project manifest or runtime closure.

R08 changes only an upstream hard-coded MSVC `/DEBUG` target flag to `/DEBUG:NONE` when the private
`MIRROR_DISABLE_MSVC_PDB=ON` build flag is present. Upstream behavior is unchanged without that flag;
the algorithm, ABI, module graph, fixtures and thresholds are unchanged.

## Reproducibility and artifact identity

Two fresh Linux `--network none` roots and two fresh Windows roots completed independently. Every
same-platform runtime pair is byte-identical.

| Runtime artifact    | Linux SHA-256                                                      | Windows SHA-256                                                    |
| ------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| first-party wrapper | `9ce503f8e5e1186269c8ef37d00a26ab04c40c9681d4a043d2ea94e2e4a861dd` | `2d7a2722d386ad3796045d0992da5cf7edc7ce4c4c07cc10ae6b3e44972829a3` |
| OpenCV core         | `1984bb9695ffb5b628809f23d0026fd49c30a8e3ed6093040e6fc7c54e5bd9ab` | `ef313484c24614ab9b3b263a46ecb930ae621b0e969d001c2583dcada483905f` |
| OpenCV flann        | `b3afa2bc31b96fec8bcab48e8f47ff9a9618a236e9fcf3a5298ee8124f8f3fff` | `1c7e087b02cd541a3205e58c800e9edf61483f49fda193ad1d90fee703923232` |
| OpenCV geometry     | `31095c77a09445c2a876dc2ea17db87c1edca051213261f3a6443274b3198e39` | `a91f8ecc0f1f22d3c60e72e1c875beb242a17357d121f18497f2c4b00ce01144` |
| OpenCV imgproc      | `5eb430711d7883602d694c8cfbd021edb9ce345ad311e65531aa13d1e31cbb89` | `6baf90843b20fa07b8e9b95c38ccbcc4c0f83d44191de1cc29febd27c17dc2d3` |

Linux libraries use only relative `$ORIGIN` RUNPATH. All five Windows DLLs contain deterministic
`coffgrp`/`repro` debug records but no CodeView, RSDS or PDB reference. ASCII and UTF-16 scans found
zero private repository, user, tool-cache or attempt-root path and zero `pthread` match.

## Deterministic and safety evidence

All four clean-root reports produced deterministic digest
`ebfee6e904e75b1cf147a4259904ab53145568d1940f6f272b9e1a595f95b62c`.

- 256 output SHA-256:
  `74ed45fbd6ec5b34a8cde0e805040e650c80c966be685492e9f6a69ecfc0b10a`.
- 1024 output SHA-256:
  `94abe99966d2d409f6383343340dc1c8150e1155de7ec4af2138712872cbe6aa`.
- Cross-platform maximum and mean pixel delta: `0`.
- Null source, zero edge, short stride, NaN/range map, collapsed/foldover triangle and positive
  triangle controls all returned the preregistered result.
- Worst observed 1024 p95: `15.10869 ms`, below the `100 ms` Gate.
- Installed footprint: Linux `16,292,903` bytes by `du -sb`; Windows `14,171,908` regular-file bytes,
  both below the `350 MiB` Gate.

## Network and runtime boundary

- Linux ELF imports are limited to the admitted OpenCV chain and standard C/C++ runtime libraries;
  exact network undefined-symbol scans are zero. Both Linux harness roots ran under
  `--network none`.
- Windows PE imports are limited to the admitted OpenCV chain and standard Windows/MSVC runtime
  libraries. Winsock, WinHTTP, WinINet, URLMon, libcurl and network-function scans are zero.
- A final Windows harness run used an enabled process-specific outbound block and Filtering Platform
  failure capture. It completed with the frozen deterministic digest and recorded zero blocked
  connection events. The temporary firewall rule was removed and the audit policy was restored.

## License, SBOM and vulnerability evidence

- OpenCV root license SHA-256:
  `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`;
  Apache-2.0 plus retained legacy BSD-3-Clause file notices apply to the built modules.
- Bundled zlib license SHA-256:
  `e32ff4e00d9d94930537635291da39e7e612703334bf6fde8c7f1686fe8a45a2`;
  license expression `Zlib`.
- Private three-component CycloneDX 1.6 SBOM SHA-256:
  `2345cba1a2b397f13d36d754cc83e0ba3cdd182658d48e87e84210e7ea1fa38d`.
- Offline Grype `0.117.0`, database schema `v6.1.9` built `2026-08-16T06:14:30Z`, reported zero
  matches for exact OpenCV `5.0.0`, zlib `1.3.2` and the first-party wrapper. Result SHA-256:
  `4749ee252c4d5f112399cffd05321d0d79b26740c2b3c21a4a42edafaca83e1f`.

The SBOM and scanner output remain in ignored private evidence storage. No binary, source archive,
model, image or private path is committed.

## Preserved failures and remaining boundaries

Earlier wheel, two-module closure, R04/R05, R06 and R07 outcomes remain visible as attempt evidence.
R08 fixes only the final Windows PDB metadata failure and does not rewrite those results.

T05 may use only this exact source/patch/toolchain/runtime contract and must fail closed on any digest,
module, dependency or platform mismatch. Any source, patch, compiler, linker, module, zlib, ABI or
runtime change reopens T04. Production, distribution, real-user processing and QuestionBank release
remain blocked.
