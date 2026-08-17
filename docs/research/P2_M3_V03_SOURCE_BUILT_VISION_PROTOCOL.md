# P2-M3-V03 Source-built Zero-telemetry Vision Protocol

## Status and authority

- Authority: ADR-032.
- Milestone: `P2-M3 — Synthetic Normalization and Base Identity QA` (`EXECUTING`).
- Candidate family: `MEDIAPIPE_SOURCE_BUILD_ZERO_TELEMETRY_V1`.
- Source: MediaPipe tag `v0.10.35`, commit
  `f8ef212d5c962c0e853db7e59d217056b187084b`.
- Current state: `STAGE_B_LINUX_REPRODUCIBLE_AUDIT_IN_PROGRESS`.
- Upstream `mediapipe==0.10.35` wheels remain rejected and are the telemetry negative control.
- Only the Principal may advance stages or record `PASS | FAIL | FURTHER_RESEARCH`.

## Fixed capability contract

The replacement must preserve the first-party `SyntheticVisionRequest` and
`SyntheticVisionResult` boundary. It must provide, from canonical synthetic JPEG input only:

- observable zero, one and multiple face counts with a configured maximum of two;
- a bounded, stable landmark set sufficient for occupancy, visibility, pose and later supported
  geometry measurements;
- finite normalized coordinates and a versioned pose derivation;
- no age estimate, identity match, beauty score, sensitive classification or Provider SDK type;
- deterministic failure for checksum/media-type tamper before model execution.

## Frozen artifacts and evidence separation

| Item                            | Frozen authority                                                                                                             | Current state                          |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| Source                          | Git commit `f8ef212d5c962c0e853db7e59d217056b187084b`                                                                        | acquisition authorized for Stage A     |
| Upstream wheel negative control | PyPI `mediapipe==0.10.35` exact Windows/Linux hashes from V02                                                                | rejected; no reinstall required        |
| Face Landmarker bundle          | GCS generation `1683136941468629`; SHA-256 `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`                | private research artifact only         |
| Patch                           | `mediapipe-v0.10.35-zero-telemetry-v1.patch`; SHA-256 `cdde123e56bcd637726d7162171a75bed10de415cd323aa95952b1cba7e942eb`     | frozen and Stage A approved            |
| Build-lock overlay              | `mediapipe-v0.10.35-build-lock-v1.patch`; SHA-256 `6b0d8771c1d1660abb6ee4cfca7a88b04ebb787faa36c8fd9cd15ecdbd3ecafa`         | frozen; ADR-033 isolated-build only    |
| CRLF build repair               | `mediapipe-v0.10.35-crlf-version-stamp-v1.patch`; SHA-256 `a59578edba3a6c350ef78850b26e6cbf5f5929a32048c5199f92b4c526a27823` | Linux build portability repair only    |
| Toolchain                       | exact Bazel/compiler/Python 3.13 inputs                                                                                      | Linux frozen; Windows compiler pending |
| Output artifacts                | minimal Windows AMD64 and Linux x86-64 C ABI shared libraries                                                                | Linux built; Windows pending           |

An expected fact may be `PENDING_STAGE_A`, but no pending fact may be silently guessed or carried
past the stage that requires it.

## Prohibited runtime closure

The candidate Face Landmarker closure must not contain or link executable paths for:

- `portable_clearcut_uploader`, Clearcut/Play logging clients or endpoint constants;
- HTTP clients, DNS/socket transports, remote artifact fetch or update checks;
- `certifi`/CA-bundle plumbing used by the native task runtime;
- environment-controlled endpoint redirection or opt-out logic that leaves telemetry compiled in.

Build-time source acquisition is distinct from runtime behavior. All build downloads must be
enumerated and frozen before producing a candidate artifact; runtime network access remains zero.

## Stage A — exact-source feasibility

1. Acquire the exact Git commit into a new private ignored directory; verify `HEAD` and object
   integrity before inspection.
2. Record the repository-declared Bazel/toolchain requirements without executing repository code.
3. Trace the Python Tasks Face Landmarker target through its C/C++ graph and list every telemetry,
   logging, HTTP, URL, socket and CA-bundle dependency in the transitive closure.
4. Determine the smallest source/build patch that removes those dependencies without changing the
   graph, model operators, thresholds or result structures.
5. Produce a patch file and SHA-256 plus an allowlisted source-feasibility report. Do not build,
   install, import or run a model in Stage A.

Stage A returns `FAIL` if a prohibited dependency is inseparable from the inference closure or if
the build requires unpinned executable downloads that cannot be frozen.

## Stage B — frozen build and supply-chain audit

Stage B starts only after Stage A evidence is committed and the Principal records
`SOURCE_PATCH_APPROVED`.

1. Freeze exact Bazel, compiler, Python 3.13, package and repository inputs with hashes.
2. Build Windows AMD64 and Linux x86-64 artifacts from the same source commit and patch.
3. Inventory native libraries, dynamic dependencies, license/NOTICE obligations, symbols and
   strings; generate private SBOM and vulnerability results.
4. Fail if prohibited runtime symbols/strings remain or an unexpected binary/dependency appears.
5. Record artifact hashes and deterministic reproduction commands without private paths.

No artifact may enter project manifests, containers, normal virtualenvs or Git.

## Stage C — isolated zero-network runtime qualification

Stage C starts only after the Principal records `SOURCE_BUILD_APPROVED_FOR_POC`.

1. Use disposable CPython 3.13 environments on Windows AMD64 and Linux x86-64.
2. Deny and capture process-level egress before import; load the exact local bundle.
3. Run bounded synthetic import/load, one-face inference, multi-face negative control, shutdown and
   uninstall. Preserve the official-wheel Clearcut failure as comparative evidence.
4. Fail on any DNS, HTTP, socket, telemetry, update or artifact request, even if blocked.
5. Record only allowlisted aggregates and hashes; raw images, landmarks, paths and traces stay
   private.

## Stage D — calibration and holdout

Stage D reuses the V02 calibration/holdout split and negative controls only after
`POC_RUNTIME_APPROVED`. The QAPolicy is derived from calibration evidence, frozen with an immutable
version/digest, then applied unchanged to holdout. A holdout failure cannot be repaired by relaxing
that policy version.

## Decision rules

- `PASS`: exact-source/build chain is auditable, both platforms are zero-network, capability and
  negative controls pass, model/data disposition is approved, and unchanged holdout passes.
- `FAIL`: telemetry/network remains, integrity/license/privacy fails, model semantics must change,
  or a hard gate is bypassed.
- `FURTHER_RESEARCH`: the source patch is sound but reproducible build, platform parity or landmark
  repeatability remains insufficient.

Stage A completed without build, install, import or model execution. The exact public source uses a
no-op `TasksDummyLogger` and contains none of the Clearcut implementation found in the rejected
upstream wheel. The approved patch adds a Face-Landmarker-only C shared-library target and removes
the unused CA-bundle field from that closure. Evidence is recorded in
`P2_M3_V03_SOURCE_FEASIBILITY_REPORT.md`.

`P2_M3_V03_EXECUTED: STAGE_B_LINUX_REPRODUCIBILITY_PASS_AUDIT_IN_PROGRESS`

ADR-033 and `P2_M3_V03_BUILD_CLOSURE_REPORT.md` subsequently froze the Linux builder, configured
repository closure and minimal OpenCV source overlay. The offline Linux build passed after the
bounded `P2-M3-R04` CRLF version-stamp repair. `P2-M3-R05` then removed foreign-build paths, OpenCV
RPATH and the compiled OpenCV build-report timestamp. Two fresh 4,610-action Linux builds produced
byte-identical main/core/imgproc artifacts with no private build paths. OouraFFT distribution rights,
the remaining sourced vulnerability dispositions, Windows toolchain/build and all runtime/model
stages remain closed.

`SOURCE_BUILD_AUTHORIZED: YES`

`SOURCE_PATCH_APPROVED: YES`

`SOURCE_BUILD_APPROVED_FOR_POC: NO`

`POC_RUNTIME_APPROVED: NO`

`PROJECT_DEPENDENCIES_ADDED: NONE`

`MODEL_ARTIFACTS_ADDED: NONE`
