# P2-M3-V02 Vision Candidate and Calibration Protocol

## Status and authority

- Milestone: `P2-M3 — Synthetic Normalization and Base Identity QA`.
- Protocol status: `PREREGISTERED_BLOCKED_PENDING_ARTIFACT_AUTHORIZATION`.
- Candidate: MediaPipe `0.10.35`, synthetic-only, internal evaluation only.
- This document does not authorize artifact download, package installation, model execution,
  dependency changes, production Vision, real-user facial processing or threshold selection.
- Only the Principal may authorize acquisition, approve the exact package/model/data chain, freeze
  the QAPolicy and decide `PASS | FAIL | FURTHER_RESEARCH`.

## Candidate freeze and negative comparison

The T06 candidate remains `mediapipe==0.10.35`. Its exact source tag resolves to commit
`f8ef212d5c962c0e853db7e59d217056b187084b`, and exact Windows/Linux wheel SHA-256 values are
already published by PyPI. PyPI `1.0.1` is not adopted for this PoC:

- both versions omit `Requires-Python` and a machine-readable license expression;
- both declare the same unpinned direct dependency families: `absl-py`, `certifi`, `numpy`,
  `sounddevice`, `flatbuffers`, `opencv-contrib-python` and `matplotlib`;
- `1.0.1` Windows/Linux x86-64 wheels are approximately 20.1/37.9 MB, compared with approximately
  10.9/12.4 MB for `0.10.35`;
- GitHub release tag `v1.0.0` reports an internal version bump to `0.10.36`, while PyPI publishes
  `1.0.1`; selecting it would add version-mapping ambiguity without closing Python 3.13, license,
  artifact or runtime evidence.

Any candidate change requires a new Principal decision and a new protocol version. It must not be
introduced as a Repair Task.

## Authoritative sources

Accessed read-only on 2026-08-17:

- `https://github.com/google-ai-edge/mediapipe/releases/tag/v0.10.35`
- `https://pypi.org/project/mediapipe/0.10.35/`
- `https://pypi.org/project/mediapipe/1.0.1/`
- `https://storage.googleapis.com/storage/v1/b/mediapipe-models/o/face_landmarker%2Fface_landmarker%2Ffloat16%2Flatest%2Fface_landmarker.task`
- `https://storage.googleapis.com/mediapipe-assets/MediaPipe%20BlazeFace%20Model%20Card%20%28Short%20Range%29.pdf`
- `https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Blendshape%20V2.pdf`
- `https://storage.googleapis.com/mediapipe-assets/Model%20Card%20MediaPipe%20Face%20Mesh%20V2.pdf`

## Exact acquisition manifest

Acquisition is prohibited until the Project Owner explicitly authorizes these exact artifacts.
After authorization, all downloads must go to a fresh private directory outside the Git worktree.
No URL, path, image, model byte or raw package payload may enter logs or committed evidence.

| Artifact               | Immutable reference                                    | Upstream size | Upstream integrity                                                                                               |
| ---------------------- | ------------------------------------------------------ | ------------: | ---------------------------------------------------------------------------------------------------------------- |
| Windows AMD64 wheel    | `mediapipe-0.10.35-py3-none-win_amd64.whl`             |    `10905503` | SHA-256 `b08f001cf3c3cd0d88d9ed68f3368dc8a4913f568281a93117f083115aa672ba`                                       |
| Linux x86-64 wheel     | `mediapipe-0.10.35-py3-none-manylinux_2_28_x86_64.whl` |    `12400490` | SHA-256 `db9a579df48cffe9570cd3e93f6a5d2dd089a1103b846c60c5b5de8a21c38db0`                                       |
| Face Landmarker bundle | GCS generation `1683136941468629`                      |     `3758596` | MD5 `b0e7274907a1644404fef66b28dd6d85`; CRC32C `2FSEdQ==`; SHA-256 must be computed after authorized acquisition |

The three official component model cards are evidence inputs, not runtime artifacts. Their recorded
PDF SHA-256 values are:

- BlazeFace Short Range:
  `cd335c06fc0de7807cd815a0777a697932598bcdb28fa98adaaabf847485f758`.
- Blendshape V2:
  `c8e9cf60a39998f4b341740623917590e050d1c97004e2de4568d84e026445ae`.
- Face Mesh V2:
  `c6add060f4ebfb37b2690136b6c711c7e5fcb7038baa2649ae3338b83979565a`.

## Four-stage execution Gate

### Exact-tag static source evidence

The `v0.10.35` Python `face_landmarker.py` module imports local MediaPipe bindings and NumPy and
exposes model creation through local `model_asset_path`/buffer. No explicit HTTP, URL or socket
client appears in that module. This is static source evidence only.

`base_options.py` passes the `certifi` CA-bundle path into the native `BaseOptionsC` structure.
Therefore the absence of a Python network import does not prove that the native runtime is
zero-network. Stage C must retain process-level egress denial and capture; the CA-bundle field and
all native libraries are explicit audit targets.

### A. Non-executing artifact admission

1. Download only the exact manifest entries into the fresh private directory.
2. Verify wheel size and SHA-256 before opening either archive.
3. Verify bundle size, MD5 and CRC32C, then compute and record its SHA-256.
4. Inspect bundle members without loading a model. Reconcile the component inventory against the
   three reviewed model cards; an unknown component is a hard stop.
5. Preserve only an allowlisted manifest containing identifiers, versions, hashes, sizes and review
   outcomes. Delete the private acquisition directory after the evidence and rollback drill.

### B. Package, native and license audit

1. Unpack both wheels without importing or executing them.
2. Inventory package metadata, licenses/notices, native libraries and dynamic dependencies.
3. Resolve an exact Windows/Linux CPython 3.13 dependency lock with hashes. No unpinned dependency
   may enter the PoC environment.
4. Produce package SBOM, native inventory, vulnerability results and license disposition for every
   direct and transitive dependency, including OpenCV-contrib and NumPy.
5. Any unknown license, unexpected executable, unsupported platform tag, unresolved vulnerability
   or dependency divergence returns `BLOCKED`; it is not waived for an internal PoC.

### C. Isolated runtime qualification

1. Create disposable CPython 3.13 environments for Windows AMD64 and Linux x86-64/Docker. Do not
   modify project dependency manifests, lockfiles, images or the normal project virtualenv.
2. Install only the frozen, hash-verified lock. Load the exact bundle by local path with outbound
   network denied.
3. Prove import, model load, one bounded synthetic inference, clean shutdown and complete uninstall.
4. Capture process-level network evidence. Any DNS, HTTP, telemetry, update or artifact request is a
   hard failure.
5. Record runtime, CPU architecture, thread settings and first-party adapter version. Provider SDK
   objects, raw responses and filesystem paths must not cross the `VisionProvider` boundary.

### D. V02 calibration and holdout

V02 may start only after A-C pass and the Principal records `POC_RUNTIME_APPROVED`. It uses the
existing private P2-M2-V01 assets after all eight source SHA-256 values reconcile and P2-M3-V01
normalization completes.

- Calibration set: `v01-category-a-01` through `v01-category-d-01`.
- Holdout set: `v01-category-a-02` through `v01-category-d-02`.
- The holdout is never opened or executed before the calibration report and exact QAPolicy content,
  version and digest are committed.
- All eight source and normalized binaries remain private. Committed evidence contains only opaque
  item references, checksums, aggregate measurements and reason codes.

Private deterministic negative controls are created from calibration inputs only and are never
eligible for identity registration or release:

1. `no_face_v1`: canonical non-human geometric image; expected observation count `0`.
2. `multi_face_v1`: checksum-bound side-by-side composite of two calibration assets; expected
   observation count at least `2`.
3. `small_face_v1`: padded derived image; expected face-occupancy hard gate failure.
4. `roll_v1`: deterministically rotated derived image; expected frontal-pose hard gate failure.
5. checksum and media-type tamper controls must fail before model execution.

## Measurement and threshold freeze

- Runtime mode is still-image CPU inference with `num_faces=2`,
  `min_face_detection_confidence=0.5`, `min_face_presence_confidence=0.5`,
  `min_tracking_confidence=0.5`, `output_face_blendshapes=false` and
  `output_facial_transformation_matrixes=true`. These are the exact-tag upstream baseline values
  except that face count is raised from `1` to `2` to make multi-face rejection observable and the
  transformation matrix is enabled for pose evidence. They are frozen before calibration and are
  not Project Mirror quality thresholds.
- Canonical output must use first-party `FaceObservation`, `FaceLandmarkSet`, `PoseEstimate` and
  `GeometryMeasurement`; raw MediaPipe types and blendshape categories are not persisted.
- Exactly one observation, complete bounded landmark output, finite normalized coordinates,
  checksum binding and required pose evidence are hard gates.
- Adult presentation, likeness risk, license scope, text/watermark and background suitability remain
  explicit operator reviews. No model output may estimate age or replace these reviews.
- Run each calibration input and negative control ten times per platform with fixed CPU/thread
  settings. Record observation-count stability, landmark coordinate variance, pose variance,
  latency and failure reason distributions.
- Numeric confidence, occupancy, pose and repeatability thresholds are not guessed in this document.
  The calibration report must derive them from the calibration distribution and documented numeric
  precision, then commit a new immutable approved QAPolicy version/digest before any holdout run.
- The same QAPolicy and adapter/model hashes must be used unchanged on Windows, Linux and holdout.
  A holdout failure cannot be repaired by relaxing that policy version.

## Decision rules

Return `PASS` only if the exact supply chain passes, runtime is zero-network on both platforms, every
negative control fails at the intended boundary, all holdout assets produce complete evidence under
the frozen QAPolicy, and no mandatory result is skipped.

Return `FAIL` for an integrity, license, privacy, network or hard-gate bypass. Return
`FURTHER_RESEARCH` for Python/platform incompatibility, unstable measurements, insufficient face
count behavior, negative-control ambiguity or holdout failure. Do not substitute a Mock result,
change the candidate, expand the dataset or regenerate V01 assets to force a pass.

`P2_M3_V02_EXECUTED: NO`

`MODEL_ARTIFACTS_ADDED: NONE`

`DEPENDENCIES_ADDED: NONE`
