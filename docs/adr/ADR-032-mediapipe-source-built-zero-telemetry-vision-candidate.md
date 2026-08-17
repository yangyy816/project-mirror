# ADR-032：MediaPipe Source-built Zero-telemetry Vision Candidate

## Status

Accepted for isolated research — 2026-08-17

## Context

P2-M3 requires a synthetic-only Vision runtime that can expose multiple face observations, bounded
landmarks and pose evidence without network access. The exact upstream `mediapipe==0.10.35` Windows
wheel failed the preregistered runtime Gate because its native library attempted Google Clearcut
telemetry while outbound traffic was blocked. Linux success under `--network none` cannot waive the
Windows failure, and the rejected upstream wheels remain prohibited.

Replacing the whole landmark stack with an unrelated third-party model would add new model/data
rights, output-contract and calibration uncertainty. The least divergent research path is therefore
to determine whether the same exact MediaPipe source and already inventoried Face Landmarker bundle
can be built with the telemetry and network closure removed in a verifiable way.

## Decision

- Authorize an isolated source-feasibility study named
  `MEDIAPIPE_SOURCE_BUILD_ZERO_TELEMETRY_V1` at exact tag `v0.10.35`, commit
  `f8ef212d5c962c0e853db7e59d217056b187084b`.
- The upstream Windows/Linux wheels remain `REJECT_FOR_P2_M3_RUNTIME`. This ADR does not rehabilitate,
  patch in place, vendor or install either wheel in Project Mirror.
- Stage A may acquire the exact Git commit into private ignored storage and inspect its complete
  build dependency closure. It may not load the model, run inference or change project manifests.
- A candidate patch is admissible only if it removes the Clearcut uploader, telemetry/logging client,
  HTTP/network transport and CA-bundle plumbing from the Face Landmarker runtime closure. Merely
  blocking the destination, suppressing stderr, redirecting the endpoint or setting an undocumented
  environment variable is insufficient.
- The patch may change only build/runtime telemetry and network plumbing. It must not change model
  bytes, detector/landmark calculations, thresholds, graph semantics, output coordinates or the
  first-party `SyntheticVisionProvider` contract.
- Before any install or execution, the protocol must freeze the exact patch digest, Bazel/toolchain,
  dependency lock, Windows/Linux build artifacts, hashes, native inventory, license/NOTICE set and
  private SBOM. Unknown or dynamically fetched build inputs fail closed.
- Runtime approval requires both Windows AMD64 and Linux x86-64 to pass process-level egress denial
  and capture, negative native symbol/string scans, bounded synthetic inference and clean uninstall.
  Every target platform must pass; platform-local success is insufficient.
- The existing Face Landmarker bundle remains fixed at GCS generation `1683136941468629`, size
  `3758596`, SHA-256
  `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`. Its model/data/license
  disposition remains an independent Gate; a zero-telemetry build does not close incomplete data
  provenance or distribution evidence.
- If the Face Landmarker closure cannot be made demonstrably network-free without changing model
  semantics, or the build cannot be reproduced on both target platforms, this candidate returns
  `FAIL` and P2-M3 must evaluate a separately preregistered replacement. It cannot be repaired by
  weakening the zero-network Gate.
- No real-person input, real-user facial processing, public API, schema, migration, production
  Provider, project dependency or P2-M4 implementation is authorized.

## Alternatives Considered

- Accept the official wheel because outbound traffic was blocked.
- Suppress the Clearcut warning without removing its executable path.
- Approve Linux only and defer Windows parity.
- Adopt an OpenCV, InsightFace, dlib or community landmark model before its exact model/data rights
  and contract fit are frozen.
- Start V02 calibration before the replacement runtime and supply-chain Gates pass.

## Consequences

P2-M3 gains one bounded, architecture-preserving attempt to close the known telemetry defect while
retaining the existing first-party Vision contract and calibration design. It also adds meaningful
build-system and native supply-chain work. A successful source build is only a runtime candidate;
QAPolicy calibration, holdout, model/data approval and identity registration remain separate Gates.

## Security / Privacy Considerations

All source, toolchain caches, wheels, native libraries, model bytes, images and raw traces remain in
private ignored or disposable storage. Committed evidence may contain only exact identifiers,
digests, aggregate outcomes and reason codes. No paths, image bytes, landmarks, Prompt text, object
keys, URLs, credentials or raw process traces may be committed.

## Testing Implications

- Verify the acquired repository resolves exactly to the frozen commit.
- Prove the Face Landmarker build closure excludes Clearcut, HTTP/network and CA-bundle targets.
- Reject any candidate artifact containing prohibited network/telemetry symbols or endpoint strings.
- Run import/load/inference/shutdown/uninstall with egress denied and captured on Windows and Linux.
- Preserve the previous wheel telemetry failure as a negative control.
- Do not begin calibration or holdout unless the Principal records `POC_RUNTIME_APPROVED`.
