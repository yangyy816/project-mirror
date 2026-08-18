# P2-M4-R08 OpenCV MSVC PDB Repair

## Status

- Task: `P2-M4-R08`
- Candidate: `OPENCV_5_0_0_BOUNDED_TRANSITIVE_SOURCE_V2`
- Scope: Windows build metadata only
- State: `PREREGISTERED`

## Trigger evidence

R07 removed actual private tool paths, ambient Git identity and the accidental pthread closure. Two
clean roots produced byte-identical DLLs and the frozen cross-platform deterministic output. OpenCV
5.0.0 nevertheless unconditionally applies `/NODEFAULTLIB:libc /DEBUG` to every MSVC module target in
`cmake/OpenCVModule.cmake`. Because target `LINK_FLAGS` follow the configured global
`/DEBUG:NONE`, all four OpenCV DLLs retained RSDS records and canonical PDB paths. This fails the
frozen zero-PDB Gate; the R07 binaries remain attempt evidence and are not post-processed.

## Bounded repair

The exact R08 source overlay changes only the hard-coded MSVC target linker metadata. When the new
private PoC flag `MIRROR_DISABLE_MSVC_PDB=ON` is present, `/DEBUG:NONE` replaces `/DEBUG`; without the
flag, upstream behavior is unchanged. No C++, algorithm, module graph, ABI, transform, fixture,
threshold, license source or runtime behavior changes.

The patch applies and reverses cleanly against the exact OpenCV 5.0.0 archive. Its frozen SHA-256 is
`e42a75d9b42584197ba444eda90b001da1120e72e68327e573dd77d8fc802da3`. Every R08 source root is
extracted fresh, checksum-admitted and receives only this overlay. The overlay is private M4 research
evidence, not an upstream or production patch.

## Validation gates

- patch apply/reverse/apply succeeds exactly;
- two new Windows roots produce byte-identical OpenCV and wrapper DLLs;
- no DLL contains RSDS, `.pdb`, actual private path or attempt-root path;
- imports remain the admitted OpenCV and standard Windows/MSVC closure with zero network-capable DLL;
- `pthread` remains absent and module closure remains `core;flann;geometry;imgproc` plus bundled zlib;
- both harness runs match Linux fixture hashes and all negative controls;
- process-scoped outbound deny and Filtering Platform capture show zero attempted egress.

Failure remains `FURTHER_RESEARCH`. R08 does not approve T05, a project dependency, distribution,
production, real-user processing or QuestionBank release.
