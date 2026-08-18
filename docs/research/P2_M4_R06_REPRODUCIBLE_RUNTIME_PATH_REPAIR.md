# P2-M4-R06 Reproducible Runtime Path Repair

## Status

- Task: `P2-M4-R06`
- Candidate: `OPENCV_5_0_0_BOUNDED_TRANSITIVE_SOURCE_V2`
- Scope: private synthetic and non-human geometry research only
- State: `PREREGISTERED`

## Trigger evidence

Two exact-source Linux V2 roots configured and built under `--network none`. Their four OpenCV
libraries and bundled zlib archive were byte-identical across roots:

| Artifact                      | SHA-256                                                            |
| ----------------------------- | ------------------------------------------------------------------ |
| `libopencv_core.so.5.0.0`     | `93367f96dea02a5e7f00ca9bf8a2d832b66ae7154b3b30c1e6c2fa4b89ae947d` |
| `libopencv_flann.so.5.0.0`    | `80f4294b4b81cb59fcc1c4ec02e6367886016a2566b5b0c5dc16770ec1184024` |
| `libopencv_geometry.so.5.0.0` | `a970c6e005cdf1bea162871daf68d0c0562d265afbe1efb59338dc67d7260d58` |
| `libopencv_imgproc.so.5.0.0`  | `4c765c4ad62272024aeac5f96d10aba982fe6a653e5ad1d1c719bb8924e9fe41` |
| `libzlib.a`                   | `c51147bce3c8a34faa34469aab4f2c3bd195c4bf753992b2793770430d445727` |

The installed tree was 16,265,425 bytes, and the four shared libraries had no socket, connect,
getaddrinfo, curl, TLS or HTTP dynamic symbols. They nevertheless embedded source/build paths and an
absolute `/work/install/lib` RUNPATH. This fails the frozen private-path and relative-runtime-lookup
gates even though same-root reproduction was bit exact.

## Bounded repair

Fresh V2 configurations must add:

```text
CMAKE_INSTALL_PREFIX=/opt/project-mirror-opencv5
CMAKE_BUILD_RPATH_USE_ORIGIN=ON
CMAKE_INSTALL_RPATH=$ORIGIN
CMAKE_INSTALL_RPATH_USE_LINK_PATH=OFF
CMAKE_C_FLAGS=-ffile-prefix-map=/work/opencv-5.0.0=/usr/src/opencv-5.0.0 -ffile-prefix-map=/work/build=/usr/src/opencv-build -fdebug-prefix-map=/work/opencv-5.0.0=/usr/src/opencv-5.0.0 -fdebug-prefix-map=/work/build=/usr/src/opencv-build
CMAKE_CXX_FLAGS=<same prefix maps>
```

Installation uses `DESTDIR=/work/stage`; the runtime closure is then
`/work/stage/opt/project-mirror-opencv5`. The normalized `/usr/src/...` labels are reproducible
source identities, not host-private paths.

Windows clean roots use the same logical install prefix and explicit MSVC path normalization:

```text
BUILD_INFO_SKIP_TIMESTAMP=ON
CMAKE_INSTALL_PREFIX=C:/project-mirror-opencv5
CMAKE_C_FLAGS=/experimental:deterministic /pathmap:<absolute-source-root>=C:\mirror-opencv-source /pathmap:<absolute-build-root>=C:\mirror-opencv-build
CMAKE_CXX_FLAGS=<same deterministic and pathmap flags>
CMAKE_SHARED_LINKER_FLAGS=/Brepro /DEBUG:NONE /INCREMENTAL:NO
```

Each clean root substitutes only its own resolved source/build paths on the left side of `/pathmap`;
the canonical right sides are identical. Installed OpenCV DLLs and the wrapper DLL are copied into one
private runtime `bin` directory and loaded through the harness's process-scoped DLL directory. Windows
has no RPATH assertion, but all DLL imports must remain in the admitted OpenCV/system closure. A scan
must prove zero original drive/user/build-root strings, PDB/RSDS paths and absolute dependency lookup.
`BUILD_INFO_SKIP_TIMESTAMP` and `/pathmap` do not by themselves prove that generated CMake literals are
normalized: if any private path remains, execution stops for a separately preregistered repair rather
than post-processing the binary or silently changing the candidate.

The first-party wrapper CMake contract now sets both build and install RPATH to `$ORIGIN`. The new
stdlib-only `run_minimal_remap_poc.py` harness binds only the frozen C ABI, regenerates the exact
non-human V1 fixtures and maps without NumPy, saves raw private arrays, checks C ABI negative return
codes, measures the unchanged 256/1024 workloads and emits canonical JSON.

The wrapper CMake change and harness must be committed and hashed before their first build or
execution.

Frozen first-party inputs for this repair are:

| Input                    | SHA-256                                                            |
| ------------------------ | ------------------------------------------------------------------ |
| wrapper `CMakeLists.txt` | `e33c7041c9ced8f4766284d92121c198b3ca54455c8de8a8474b72510b3590b2` |
| unchanged wrapper C++    | `2bfe68ce626a0b2fc8f3d720a37f069cd0b9d03f4d53c5a6e7853e0aa18c1dfd` |
| stdlib ctypes harness    | `2502b4a4fedd7cdb71d382bf01645539cfc0c161053111d68cb1268081336ffb` |

## Validation gates

- two fresh Linux OpenCV and wrapper builds remain byte-identical;
- no binary contains `/work`, a Windows drive/user path, or another private root;
- all OpenCV and wrapper runtime lookup is exactly `$ORIGIN`;
- actual dependencies remain only the admitted OpenCV/system closure;
- no network symbol appears;
- two Linux harness runs under `--network none` match the earlier V1 fixture result hashes and all
  C ABI negative controls pass;
- no threshold, fixture, map, interpolation or border mode changes.

Any failure requires a new bounded repair or `FURTHER_RESEARCH`; existing successful build evidence
must not be overwritten.

## Boundaries

No project dependency, lockfile, production image, public API, model, weight, User Asset, real face
or QuestionBank release change is authorized. R06 changes only private research build metadata,
relative runtime lookup and deterministic harness evidence.
