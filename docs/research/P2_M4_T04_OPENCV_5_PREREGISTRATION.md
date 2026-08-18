# P2-M4-T04 OpenCV 5 isolated PoC preregistration

## Status and authority

- Status: `PREREGISTERED_NOT_EXECUTED`
- Frozen at: `2026-08-18T16:10:00+08:00`
- Scope: private synthetic and non-human geometry research only
- Parent authority: ADR-036 and `P2_M4_GEOMETRY_VARIANT_PROTOCOL.md`
- Candidate ID: `OPENCV_PYTHON_HEADLESS_5_0_0_93_V1`

This document freezes the candidate and acceptance rules before artifact download, installation or
benchmark execution. A passing PoC can approve only a private synthetic M4 adapter candidate. It is
not project-manifest adoption, distribution approval, production approval or real-user facial
processing authorization.

## Exact candidate lock

| Layer            | Exact authority                                                                            | Expected SHA-256 / evidence                                        |
| ---------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| OpenCV upstream  | GitHub release/tag `5.0.0`, published 2026-06-06                                           | tag and release metadata must be retained                          |
| Python packaging | PyPI `opencv-python-headless==5.0.0.93`, uploaded 2026-07-02                               | PyPI JSON snapshot must be retained                                |
| Windows artifact | `opencv_python_headless-5.0.0.93-cp37-abi3-win_amd64.whl`                                  | `829717b6a95554f273e49e357cee3b3a2a26b6f4842fbc1bed2b45bdd8f87e0e` |
| Linux artifact   | `opencv_python_headless-5.0.0.93-cp37-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl` | `09a872a157c1376ab922a69bbf22f9a95bcc7b658a9d8b436a60212b02b2eeb4` |

Only official GitHub and PyPI sources are permitted. Artifacts, extracted wheels, virtual
environments, reports with private paths and benchmark outputs stay in ignored private storage.
Every acquired byte receives a locally recomputed SHA-256. Any mismatch is a hard stop.

The wheel metadata is untrusted until inspected. Exact transitive runtime dependencies and hashes
must be frozen from wheel metadata and official indices before import. The project manifests and
lockfiles remain unchanged throughout T04.

### Dependency resolution lock before first import

Artifact admission confirmed that the Python 3.13 branch requires only `numpy>=2`. Before importing
the candidate, T04 freezes `numpy==2.5.2` with these official PyPI artifacts:

| Platform | Exact artifact                                                            | Expected SHA-256                                                   |
| -------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Windows  | `numpy-2.5.2-cp313-cp313-win_amd64.whl`                                   | `85aaccb24182c25df891ad0ec333585967e115269d5f1b17f2c9ae005bc96657` |
| Linux    | `numpy-2.5.2-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl` | `29b86ff8a6cc556b47ec6b64b194815cc80e6bf5eedcc6cddfd65318cb0b4eee` |

This lock was derived only from wheel metadata and official index metadata; no OpenCV or NumPy code
had been imported. Any additional runtime requirement discovered later is an unexpected-closure stop.

## Intended adapter surface

The candidate may provide only bounded numeric image primitives behind the first-party
`GeometryTransform` port:

- explicit `float32` displacement maps;
- `cv2.remap` or an equivalently bounded OpenCV primitive;
- fixed interpolation and border modes;
- fixed thread and optimization settings when required for determinism;
- no detector, classifier, model, codec discovery, GUI, video, network or file-URL behavior.

Landmark selection, source-relative displacement, target/control semantics, bounds, foldover checks,
canonical encode, second decode and domain reason codes remain first-party authority. OpenCV must not
receive an absolute target face, population prior, sensitive label or User Asset.

The V1 runtime configuration is frozen before benchmark execution: `cv2.setNumThreads(1)`,
`cv2.setUseOptimized(False)`, `cv2.INTER_LINEAR`, `cv2.BORDER_REFLECT_101`, explicit `float32`
destination-to-source maps and contiguous RGB `uint8` input. Changing any setting creates a new
candidate ID.

## Fixtures and execution order

The PoC executes in this immutable order:

1. artifact checksum, wheel metadata and archive admission;
2. license/notices/native-library inventory, SBOM and vulnerability review;
3. import and build-information capture in clean Python 3.13 environments;
4. numeric coordinate fixtures without image data;
5. bounded 256x256 and 1024x1024 non-human grid/shape fixtures;
6. malformed, mismatch, bounds and foldover negative controls;
7. two clean Windows runs and two clean Linux/Docker `--network none` runs;
8. cross-platform comparison, footprint, latency and replacement-cost report;
9. disposition: `APPROVED_FOR_PRIVATE_SYNTHETIC_M4`, `REJECTED` or `FURTHER_RESEARCH`.

No P2 identity image is used in this candidate qualification. If the candidate passes, later T05/T07
may use the already governed private synthetic calibration/holdout assets under separate evidence.

## Frozen determinism and safety gates

The candidate claims:

- `BIT_EXACT_SAME_PLATFORM` for decoded result pixels and serialized numeric measurement output;
- `MEASUREMENT_EQUIVALENT` across Windows and Linux, not cross-platform bit-exact encoding.

PASS requires all of the following:

- two fresh runs per platform produce identical decoded pixel SHA-256 and identical numeric JSON;
- cross-platform maximum absolute channel delta is at most `1`, mean absolute channel delta is at
  most `0.01`, and changed-pixel fraction above zero is at most `0.001`;
- mapped control-point coordinates differ by at most `0.000001` normalized image units;
- expected target direction is correct for every numeric/grid fixture;
- source/result differ for every non-zero valid request;
- all output pixels are finite and inside the fixed output extent;
- foldover, self-intersection, out-of-bounds maps, checksum mismatch, unsupported dimension,
  malformed input and algorithm/runtime digest mismatch fail before result admission;
- output dimensions, channel count and colorspace match the frozen specification;
- no network attempt occurs; Linux runs with `--network none`, and Windows evidence combines native
  import scanning with process-scoped connection capture or deny evidence;
- wheel compressed size is at most `70 MiB`, isolated installed runtime is at most `350 MiB`, and
  1024x1024 warm-transform p95 is at most `100 ms` on the recorded local host/CI class;
- no critical/high unresolved vulnerability applies to the configured runtime closure;
- all code and bundled binary notices required for private research use are retained.

The performance and footprint limits are operational PoC stop rules, not permanent product
invariants. They cannot be relaxed after results are observed for this candidate ID.

## Mandatory negative controls

- unknown, `UNSUPPORTED`, `REQUIRES_3D` and `STYLE_ONLY` dimensions;
- source checksum mismatch and algorithm/runtime digest mismatch;
- NaN/Infinity coordinate or displacement;
- negative/out-of-range coordinate and excessive displacement;
- a triangle whose mapped signed area is zero or reverses sign;
- malformed/empty/incorrect-channel image input;
- non-zero request producing source-identical output;
- implicit file/URL input, GUI/video/model API use or any network attempt.

Failure remains evidence. Do not replace a failed fixture, change interpolation/border mode or lower a
threshold under the same candidate ID after observing results.

## Supply-chain and privacy stop rules

Stop as `REJECTED` for checksum mismatch, unexpected network/telemetry, license incompatibility,
unbounded codec/plugin loading or a mandatory native dependency outside the admitted closure. Use
`FURTHER_RESEARCH` for platform variance, performance, footprint or a repairable deterministic-build
gap that requires a new candidate version.

No real face, user record, Prompt, image bytes, private path, object key, landmark array or Provider
payload may enter committed evidence. Downloads are authorized but do not change the existing
`POC_REQUIRED` registry status until Principal accepts the complete T04 evidence.
