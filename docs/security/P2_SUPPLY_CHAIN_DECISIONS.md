# P2 Synthetic Dataset Supply-Chain Decisions

## Scope

This record freezes the P2-M1 dependency, model and data boundary. It records research candidates without installing packages, downloading artifacts, accepting external terms or authorizing production use. Verification date: 2026-08-16.

## Evaluated components

| Component                                | Authoritative upstream evidence                                                                                                            | License and dependency evidence                                                                                                                                                                                     | P2 decision                                                                                        | Review trigger                                                                                                                                                                              |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pillow 12.3.0                            | PyPI release and exact Windows/Linux wheels already recorded in `PILLOW_ADOPTION.md`                                                       | MIT-CMU top-level plus complete bundled native notices; no core Python `Requires-Dist`; native parser attack surface remains                                                                                        | `APPROVE_FOR_P2`; reuse the existing pinned 12.3.0 runtime for future synthetic normalization only | Any version, wheel, platform, feature, native notice or vulnerability change                                                                                                                |
| MediaPipe candidate snapshot v0.10.35    | `google-ai-edge/mediapipe` release `v0.10.35`, published 2026-04-28; latest-tag discrepancy is recorded separately                         | Exact-tag source and component model cards state Apache-2.0; data/distribution evidence remains incomplete; Windows native runtime attempted Google Clearcut telemetry                                              | `REJECT_FOR_P2_M3_RUNTIME`; private PoC only; no project install                                   | Reopen only through Principal change control with a new exact candidate/build and preregistered zero-telemetry Windows/Linux proof                                                          |
| MediaPipe source-built zero-telemetry v1 | exact `v0.10.35` commit `f8ef212d5c962c0e853db7e59d217056b187084b`; ADR-032                                                                | Public source uses a dummy logger; minimal C ABI/CA-bundle patch; Windows clean reproduction and path/network surface audit pass after R17/R18; hardened Linux replay and model/data disposition remain independent | `STAGE_B_WINDOWS_REPRODUCIBILITY_PASS_AUDIT_IN_PROGRESS`; no runtime/model approval                | Replay R17 in two fresh no-network Linux roots, close license/SBOM/vulnerability dispositions, then execute both-platform Stage C                                                           |
| OpenCV 3.4.11 V03 build input            | MediaPipe `v0.10.35` declared source snapshot; archive SHA-256 `10898a0268d8f8cbaf0354ddd1d9de6abaac84e3d9a6c9754f56a0aa3383d73b`; ADR-033 | Exact-source 3-clause BSD; build-lock overlay limits the closure to `core,imgproc` and disables dynamic download/video/UI/codec surfaces; old-version vulnerability review remains mandatory                        | `ISOLATED_BUILD_LOCK_AUTHORIZED`; no project/runtime/production adoption                           | Any archive, patch, module, compiler, platform, dynamic dependency, vulnerability, numeric behavior or distribution change                                                                  |
| OpenCV 5.0.0 research reference          | `opencv/opencv` release `5.0.0`, published 2026-06-06                                                                                      | Exact-tag source LICENSE is Apache-2.0. No Python wheel, hash, native feature set, transitive dependency graph or distribution artifact is selected                                                                 | `POC_REQUIRED`; no runtime version frozen and no P2-M1 install                                     | Before M4: compare controlled candidates on CPython 3.13 Windows/Linux/Docker, wheel/hash, SBOM, vulnerabilities, footprint, performance, determinism, platform parity and replacement cost |
| imagededup v0.3.3.post2                  | `idealo/imagededup` release `v0.3.3.post2`, published 2025-08-15                                                                           | Apache-2.0 source; build requires setuptools/wheel/Cython; runtime declares torch, torchvision, Pillow, tqdm, scikit-learn, PyWavelets and matplotlib                                                               | `REJECT`; `REIMPLEMENT_SMALL_CORE`                                                                 | Reopen only if materially new evidence makes the dependency graph smaller than the bounded first-party requirement                                                                          |

MediaPipe upstream version labels are not collapsed: the v0.10.35 release is the plan's candidate snapshot, while the 2026-08-16 `releases/latest` response is tag v1.0.0 and its notes mention internal version 0.10.36. A later PoC must lock the exact source tag, package/runtime and Face Landmarker artifact independently.

## P2-M3-T06 MediaPipe evidence update

On 2026-08-17 the Principal independently read and visually verified all pages of the official
BlazeFace Short Range, Face Mesh V2 and Blendshape V2 model cards. Each card explicitly licenses its
model under Apache-2.0. The cards provide only high-level training/evaluation descriptions: consented
mobile-AR images, real-world smartphone images, or controlled multi-view lab subjects and GHUM-derived
samples. They do not provide a complete per-dataset rights, territory, deletion or redistribution
chain.

The public Face Landmarker object has immutable GCS generation `1683136941468629`, size `3758596`,
MD5 `b0e7274907a1644404fef66b28dd6d85` and CRC32C `2FSEdQ==`. Upstream does not publish SHA-256.
That was the pre-authorization checkpoint. The Project Owner later authorized the exact private
artifacts and isolated PoC. Both wheels matched the preregistered hashes, and the bundle SHA-256 was
computed as `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`. The exact CPython 3.13
package set and an SBOM remained private and did not change any project manifest.

The Windows runtime then failed the mandatory zero-telemetry Gate: with outbound egress blocked, a
bounded synthetic inference emitted an attempted Google Clearcut upload. Static inspection found the
portable uploader, HTTP client and `https://play.googleapis.com/log` in the native binary. Linux
`--network none` inference completed without the same message, but the protocol requires every target
platform to pass. Calibration and holdout were therefore never started.

`P2_M3_T06_DECISION: CANDIDATE_FAIL`

`MEDIAPIPE_PROJECT_INSTALL: NO`

`MEDIAPIPE_PRIVATE_POC_INSTALL: EXECUTED_DISPOSABLE`

`MODEL_ARTIFACTS_ADDED: NONE`

## P2-M3-R05 Linux reproducibility and audit update

The final R05 outer patch SHA-256 is
`192056a6ad29362442fe440bf24ea4f998b09172ab0807f91bc9c24a96d41c68`. Two new empty output
volumes executed the same frozen, no-network 4,610-action build. Both produced:

- main C ABI SHA-256 `a892ba0976fcd557a9ff2056ae170f765ab68aca99f70607eee0c6989fb94e7b`;
- OpenCV core SHA-256 `048df8097a7c444769e5c56708041aa0c60a48a5a442f2ebad2c60a03097653a`;
- OpenCV imgproc SHA-256 `765ebf6c659e523d9d7e9557e63f004a041a9327fcba95e6d4ac0670485241f5`.

All three pairs are byte-identical. Private build-path scans are zero; OpenCV has no RPATH/RUNPATH;
the main library uses the same relative `$ORIGIN` RUNPATH in both builds. This is
`PROJECT_MIRROR_REPRODUCED` Linux artifact evidence, not runtime/model/production approval.

Exact Ninja evidence is Debian `ninja-build 1.12.1-1`, Apache-2.0 with public-domain bundled
`getopt` files; retained license evidence SHA-256 is
`c6dd93071b285c591075669795794cc31ee34af7d4ed3cdf8c98a3c0bc7c5c01`. Offline Grype
`0.117.0` with DB schema `v6.1.9` identified four OpenCV source-version findings. Findings outside
the built `core,imgproc` module closure do not establish reachability; `CVE-2019-14493` still needs
a sourced disposition.

OouraFFT functions are present in the previously reproduced Linux main binary. Its notice does not
clearly close modified/binary redistribution rights, so internal isolated research may continue but
distribution and production remain blocked pending independent license judgment or removal from the
closure.

## P2-M3-R17/R18 Windows reproduction update

R17 patch SHA-256
`7099bdb0ed223d71110a18148880090f15311220f75e20cb1af6eb9619cca5dc` removes the unused
AudioSpectrogram/MFCC/RFFT2D registrations and Ooura dependency, and disables Bazel's target-level
FASTLINK/PDB feature while retaining `/DEBUG:NONE`. R18 patch SHA-256
`b57ed5b0643d830cc9d66ad063eea211cbbab2b50c98df70d2b22f00b102775d` canonicalizes only the
absolute MSVC/NMake paths compiled into the OpenCV Windows build report.

Fresh roots `bw28` and `bw29` independently completed 4,549 actions. The main, OpenCV core and OpenCV
imgproc pairs are byte-identical with SHA-256 values
`f99ba0a489d673ff58a1870a9e16037260913dca02912cf304173993e7e5e199`,
`19b1b9bad3c7ad402858f97ccdc0299defbfe1d18f3a3b83bc786d7c3e443c91` and
`1aa54040e263be7685f2b8a379cf1f34a275b0718cc8b3a823a1f935c28592b4`. Six-artifact scans have
zero actual private path, PDB/RSDS, Ooura, Clearcut, certifi/CA-bundle and Windows network-API
matches. PE debug records are deterministic `coffgrp`/`repro`, not PDB references.

This closes Windows build reproducibility and static path/network-surface evidence only. The older
Linux reproducible artifact still contains the now-removed Ooura closure, so two fresh hardened Linux
builds, updated SBOM/license/vulnerability review, exact model disposition and Stage C zero-egress
runtime qualification remain mandatory. No project dependency, model artifact or production Vision
approval is created.

The preregistered acquisition and audit contract is
`docs/research/P2_M3_V02_VISION_CALIBRATION_PROTOCOL.md`. PyPI `1.0.1` was compared and rejected for
this PoC: it retains the same unpinned dependency families and absent `Requires-Python`/license
expression while materially increasing the Windows/Linux wheel sizes. The exact `0.10.35` candidate
therefore remains frozen; this is not package or model approval.

Exact-tag static source review found no explicit network client in the Python Face Landmarker module
and confirmed local model path/buffer input. However `BaseOptions.to_ctypes()` passes a `certifi`
CA-bundle path into native code. Static Python review therefore cannot prove no telemetry or egress;
native inventory plus process-level network denial/capture remain mandatory before any runtime
approval.

## Frozen implementation boundary

- P2-M1 adds no MediaPipe, OpenCV, imagededup, PyMC, ASAP, React-Konva, OpenAI Agents SDK, makeup-transfer, memory-graph or 3D-face dependency.
- No source repository, wheel, native binary, model, weight, dataset, cache or Provider SDK is vendored or added to Project Mirror runtime manifests. Authorized private PoC artifacts are not adoption.
- A permissive code license never proves a model artifact, data source, hosted Provider or commercial usage term is approved.
- Future fixture admission requires source, license, checksum and synthetic/non-human classification.
- Future model/data assets require identifier, exact version, checksum, source, storage location, purpose, approval, security review, license evidence, dataset provenance and reproduction notes.

## Codex native offline source addendum

Project Owner change control and ADR-026 approve the currently exposed Codex native `image_gen`
capability only as an operator-assisted P2 synthetic research source. It adds no package, SDK,
runtime Provider, model artifact or network path to Project Mirror. The capability does not expose
an exact model identifier/version, request identifier, seed, usage or Provider cost, so these facts
remain `NULL` and provenance is classified as `PROVENANCE_ONLY`.

This research approval does not establish model/weight redistribution rights or production hosted
Provider approval. Generated binaries stay in private ignored storage; the committed V01 artifact
contains checksums and bounded facts only. Runtime production generation remains blocked by
`PRODUCTION-BLOCKER-IMAGEGEN-PROVIDER`.

## Future first-party duplicate core

The later P2-M5 component is deliberately limited to exact SHA-256 comparison, perceptual hashing, Hamming distance, similarity candidate generation, deterministic threshold evaluation and duplicate-cluster evidence. It will not recreate the imagededup package. Thresholds require measured distributions and deterministic fixtures covering identical, re-encoded, brightness, resize, crop, geometry variant, clearly different identity, boundary and Hamming determinism cases.

`DEPENDENCIES_ADDED: NONE`

`MODEL_ARTIFACTS_ADDED: NONE`

`PROVIDER_SDKS_ADDED: NONE`
