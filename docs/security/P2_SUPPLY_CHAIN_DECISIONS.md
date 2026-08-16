# P2 Synthetic Dataset Supply-Chain Decisions

## Scope

This record freezes the P2-M1 dependency, model and data boundary. It records research candidates without installing packages, downloading artifacts, accepting external terms or authorizing production use. Verification date: 2026-08-16.

## Evaluated components

| Component                             | Authoritative upstream evidence                                                                                    | License and dependency evidence                                                                                                                                              | P2 decision                                                                                        | Review trigger                                                                                                                                                                              |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pillow 12.3.0                         | PyPI release and exact Windows/Linux wheels already recorded in `PILLOW_ADOPTION.md`                               | MIT-CMU top-level plus complete bundled native notices; no core Python `Requires-Dist`; native parser attack surface remains                                                 | `APPROVE_FOR_P2`; reuse the existing pinned 12.3.0 runtime for future synthetic normalization only | Any version, wheel, platform, feature, native notice or vulnerability change                                                                                                                |
| MediaPipe candidate snapshot v0.10.35 | `google-ai-edge/mediapipe` release `v0.10.35`, published 2026-04-28; latest-tag discrepancy is recorded separately | Exact-tag source LICENSE is Apache-2.0. Package/runtime, Face Landmarker artifact, training/evaluation data and model/data distribution terms remain separate and unapproved | `LICENSE_REVIEW_REQUIRED`; `MEDIAPIPE_INSTALLED: NO`                                               | Exact package and artifact selected; then source/package/artifact/data/terms review before isolated PoC                                                                                     |
| OpenCV 5.0.0 research reference       | `opencv/opencv` release `5.0.0`, published 2026-06-06                                                              | Exact-tag source LICENSE is Apache-2.0. No Python wheel, hash, native feature set, transitive dependency graph or distribution artifact is selected                          | `POC_REQUIRED`; no runtime version frozen and no P2-M1 install                                     | Before M4: compare controlled candidates on CPython 3.13 Windows/Linux/Docker, wheel/hash, SBOM, vulnerabilities, footprint, performance, determinism, platform parity and replacement cost |
| imagededup v0.3.3.post2               | `idealo/imagededup` release `v0.3.3.post2`, published 2025-08-15                                                   | Apache-2.0 source; build requires setuptools/wheel/Cython; runtime declares torch, torchvision, Pillow, tqdm, scikit-learn, PyWavelets and matplotlib                        | `REJECT`; `REIMPLEMENT_SMALL_CORE`                                                                 | Reopen only if materially new evidence makes the dependency graph smaller than the bounded first-party requirement                                                                          |

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
No wheel or `.task` bundle was downloaded or installed because explicit artifact-download authority
is still absent. Consequently package contents, bundle SHA-256, native/transitive SBOM and notices,
Python 3.13 compatibility, zero-network behavior and Windows/Linux repeatability remain unverified.

`P2_M3_T06_DECISION: POC_BLOCKED`

`MEDIAPIPE_INSTALLED: NO`

`MODEL_ARTIFACTS_ADDED: NONE`

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
- No source repository, wheel, native binary, model, weight, dataset, cache or Provider SDK is downloaded or vendored.
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
