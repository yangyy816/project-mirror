# P2-M3-V03 Source Feasibility Report

## Result

`STAGE_A_DECISION: PASS`

`SOURCE_PATCH_APPROVED: YES`

`BUILD_OR_MODEL_EXECUTED: NO`

## Exact source evidence

- Source authority: MediaPipe tag `v0.10.35`.
- Verified Git commit: `f8ef212d5c962c0e853db7e59d217056b187084b`.
- Repository object connectivity check: PASS.
- Repository-declared Bazel version: `7.4.1`.
- Candidate patch: `docs/security/patches/mediapipe-v0.10.35-zero-telemetry-v1.patch`.
- Canonical LF-byte patch SHA-256:
  `cdde123e56bcd637726d7162171a75bed10de415cd323aa95952b1cba7e942eb`.
- Patch size: `5250` bytes.
- Patch applies as the exact reverse of the inspected private working tree: PASS.

The source was acquired only after ADR-032 and the V03 protocol were committed. The first direct
GitHub attempt was reset during transfer and produced no checkout. A second attempt used the
user-provided loopback proxy only on that command; no repository or global proxy setting was
written.

## Telemetry and runtime-closure findings

The public exact-tag source contains no `portable_clearcut_uploader`, Clearcut client or
`play.googleapis.com/log` implementation. Its `TaskRunner` links the public
`logging_factory.cc`, which constructs `TasksDummyLogger`; every logger method is a no-op. This
differs materially from the rejected upstream wheel's native inventory and explains why the wheel
cannot be treated as a reproducible build of the public source closure.

The public Python wrapper still imports `certifi` and passes a CA-bundle path through C/Python/C++
options even though the public dummy logger does not use it. The approved patch removes that field
from the minimal C and C++ Face Landmarker path.

The full upstream `libmediapipe` target also links audio, text, GenAI and unrelated vision tasks.
V03 therefore does not use the upstream Python wheel or full shared library. The patch adds a
minimal shared-library target containing only:

- common C error handling;
- Image C API;
- Face Landmarker C API and its required graph/model closure.

The intended Project Mirror adapter will use the stable C ABI from first-party Python `ctypes` and
the already-approved Pillow decoder. It will not import upstream `mediapipe`, `certifi`, NumPy,
OpenCV Python wheels or Provider SDK types.

Static prohibited-pattern scanning of the edited Face Landmarker, TaskRunner, logging factory,
base-options and minimal BUILD files found no Clearcut, telemetry endpoint, certifi, CA-bundle,
HTTP client, curl, socket or URL-loader reference after the patch.

## Stage B prerequisites

Stage A proves source feasibility, not an auditable build. Stage B remains closed until these facts
are frozen:

- exact Bazel 7.4.1 binary and checksum;
- Windows and Linux compiler/container toolchains;
- target-specific Bazel repository/download closure with hashes and licenses;
- confirmation that no unpinned repository declared elsewhere in `WORKSPACE` enters the minimal
  target closure;
- exact build commands and environment allowlist;
- Windows/Linux shared-library hashes, native dependency inventory and private SBOM;
- target export/symbol list needed by Image and Face Landmarker C APIs.

No QAPolicy calibration, holdout, identity registration, project dependency, model execution or
P2-M4 work is authorized by this report.

`SOURCE_BUILD_APPROVED_FOR_POC: NO`

`POC_RUNTIME_APPROVED: NO`

`PROJECT_DEPENDENCIES_ADDED: NONE`

`MODEL_ARTIFACTS_ADDED: NONE`
