# P2-M4-T04 OpenCV 5 Minimal Source Candidate Report

## Disposition

- Candidate: `OPENCV_5_0_0_MINIMAL_CORE_IMGPROC_V1`
- Scope: private synthetic and non-human geometry research only
- Result: `FURTHER_RESEARCH`
- T05 unlock: `NO`

The candidate cannot satisfy its frozen two-module source closure without a broader OpenCV 5 source
fork. It is not approved as a Project Mirror dependency or runtime.

## Evidence sequence

1. `linux-build1` and `linux-build2` configured the unmodified exact source under `--network none`.
   The actual graph included `opencv_geometry`, `opencv_flann`, bundled zlib and a failed Unifont
   download attempt. No compilation was started.
2. `P2-M4-R04` froze patch SHA-256
   `b2d727df65468f7cac7bbbc07bdfefad2a9ea8d1e604726833316b72083e3ee7`. It removed the
   transitive geometry/flann and linked zlib edges and disabled the font downloader.
3. `linux-build3` and `linux-build4` proved the module closure was only `core,imgproc`, but OpenCV's
   default `all/install` graph still compiled an unused global bundled zlib target. No compilation
   was started.
4. `P2-M4-R05` froze patch SHA-256
   `8f10a176c78b70d5a1ee91f8c2f6630ef9a4340d18669ec69e78bfcd26270f80`. It removed only
   the now-unused global image-format discovery path.
5. `linux-build5` and `linux-build6` configured under `--network none` with identical results:
   `OPENCV_MODULES_BUILD=opencv_core;opencv_imgproc`, no zlib/geometry/flann/downloader build target
   and no download attempt.
6. Both clean builds then failed deterministically while compiling `imgproc`: its shared
   `src/precomp.hpp` includes `opencv2/geometry.hpp`, which is absent from the admitted two-module
   closure. Neither root produced an install.

The relevant compiler result was:

```text
modules/imgproc/src/precomp.hpp:47:10: fatal error:
opencv2/geometry.hpp: No such file or directory
```

## Interpretation

OpenCV 5.0.0's source architecture treats geometry as an imgproc compile-time dependency, and
geometry in turn requires flann. Removing only CMake dependency edges is therefore insufficient.
Continuing would require editing shared imgproc headers or partitioning many sources and public APIs,
which exceeds the frozen R04 repair boundary and materially increases replacement and maintenance
cost.

This failure does not invalidate the earlier full-wheel determinism evidence. It proves only that
the exact `core,imgproc` two-module source candidate is not viable under its preregistered closure.
No threshold was relaxed and the full wheel was not restored.

## Boundaries retained

- no project manifest, dependency, lockfile or production image changed;
- no public API, schema, model, weight, User Asset or real face was introduced;
- all private configuration and build attempts used exact source and `--network none`;
- the failed roots remain ignored attempt evidence;
- T05 remains blocked pending a separately preregistered passing candidate and Principal approval.
