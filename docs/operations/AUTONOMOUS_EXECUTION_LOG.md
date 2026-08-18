# Project Mirror Autonomous Execution Log

This append-only operational summary records bounded autonomous checkpoints. It intentionally excludes
credentials, Prompt plaintext, image bytes, private object keys, signed URLs and raw Provider responses.

## 2026-08-18T01:45:05+08:00 — P2-M3 recovery and V01 authority closure

- Phase/Milestone: Phase 2 / P2-M3 (`EXECUTING`)
- Branch: `codex/phase2-m3-normalization-base-qa`
- Starting local SHA: `66016914a936728e73145a23930cc050cf229f38`
- Remote checkpoint: `ccf687dae205105fb2b0f12b047d32cf29478d28`; run `31970114413` succeeded.
- Repository truth: local branch was nine commits ahead; migration head was
  `0010_synthetic_asset_qa`; five Compose services were healthy; protected `.tmp` remained untouched.
- Recovery: stopped the stale `bw16` batch prompt and the exact orphaned `bw14` CMake/Ninja processes;
  preserved both roots as failed-attempt evidence.
- V01 finding: ADR-026 known-null provenance cannot be represented by the frozen M2 non-null
  Batch/Provider schema. Placeholder facts are forbidden. ADR-035 therefore authorizes a forward
  offline source authority and `0011`; V01 generation is not repeated.
- Windows repair evidence: `bw16` proved double-escaped MSVC date/time macro flags and missing
  `CMAKE_MT`; bounded patches remove only the three invalid foreign-CMake flags and pin the frozen SDK
  `mt.exe`. `bw18` then failed early because the RFFT2D patch context did not match the exact TensorFlow
  BUILD ordering; the context was corrected and apply-checked before a new clean attempt.
- Closure: `0011` schema/application integration passed 24 focused PostgreSQL tests plus fresh and
  `0011→0010→0011` lifecycle with zero Alembic drift. V01 then completed 8/8 immutable admission,
  offline-source import, canonical normalization, second decode and idempotent replay; redacted
  evidence is committed without Prompt, path, storage reference or image bytes.
- Remaining blockers: Windows/Linux R08 reproduction, Stage C, V02, T07 and T08 remain pending.
- Next action: finish the already-running clean Windows `bw20` build and reproduce it in fresh `bw21`.

## 2026-08-18T02:20:00+08:00 — P2-M3-R11 exact OpenCV backport correction

- `bw19` failed before compilation because upstream `5691d998...` hunk context targets a newer C++
  persistence parser, while locked OpenCV 3.4.11 uses the legacy C parser layout.
- R11 preserves ADR-034's frozen security outcome and applies equivalent entry-point/post-skip null
  checks to the exact JSON/XML/YAML functions. After R12 canonical whitespace normalization, the
  inner patch SHA-256 is `a1037142e804aeb74d072d159b36f03289bdfc1be223199c06b7543301ddba62`
  and the outer patch SHA-256 is
  `9c7f6c9032f1ffa050044123e29cc596ca255332e78d5af7fb77cf5f20f65e60`.
- `bw19` remains failed-attempt evidence. Fresh Windows roots advance to `bw20` and `bw21`.

## 2026-08-18T03:05:00+08:00 — P2-M3-R12 canonical patch whitespace

- The pre-commit `git diff --check` found trailing spaces only on added blank lines inside five
  tracked patch artifacts. R12 removes that non-semantic whitespace; it does not change a source
  token, build flag, dependency, runtime graph or security outcome.
- New tracked patch SHA-256 values are: LLVM overlay
  `9c4524600297eda5f7df81b2aa7ed2b82b90907f33f441725710a3a7a56431ff`, runtime closure
  `9c7f6c9032f1ffa050044123e29cc596ca255332e78d5af7fb77cf5f20f65e60`, Windows build
  `9bec126ea037a8a9d72417ba798252e5b32fdb2c94b0081c5de55cf89f6c5c9a`, rules_foreign_cc
  BusyBox `7a586cbe76741e1c620b11495ccbb5bf879d0cddfe4d2a186a5a8d0190140424`, and CMake flags
  `c401de5d81a420ecdaa30f9c711b9b45d2bafdecbc7a5e7b71a0003845d02146`.
- All five normalized artifacts reverse-apply-check against their exact prepared source/override
  snapshots; the runtime closure also apply-checks against the pre-Windows baseline. `git diff
--check` is clean after normalization.

## 2026-08-18T04:35:00+08:00 — P2-M3-R15 build success and R16 closure defects

- `bw23` completed the exact Windows build with exit code zero after R15 pinned the frozen NMake,
  resource compiler and manifest-tool paths. The 4,561-action build produced the main Face
  Landmarker DLL and both OpenCV DLLs; this proves the toolchain path works but does not satisfy
  reproducibility acceptance.
- PE inspection found an absolute private output-root PDB path in the main DLL. The same class of
  path is present in the OpenCV DLLs, so the artifacts fail the mandatory private-path scan before
  any two-root equality claim.
- The second fresh root `bw24` independently reached the compile phase, then visibly compiled
  `fftsg2d.c` and `fftsg.c`. An exact configured Bazel `somepath` query identified the remaining
  closure as Face Landmarker -> TFLite builtin kernels -> internal audio utilities -> `@fft2d`.
  This contradicts ADR-034's no-Ooura closure outcome.
- `bw24` was stopped normally at 1,842/4,561 actions once both mandatory failures were proven; its
  root is retained and is not reused. No successful or reproducible claim is made for `bw24`.
- A two-root MSVC probe proved `/Brepro /DEBUG:NONE` removes the RSDS/PDB path and yields
  byte-identical DLLs with the same basename. R16 is therefore bounded to removing unused
  AudioSpectrogram/MFCC/RFFT registrations and dependencies from the fixed-model V03 closure and
  suppressing debug-path metadata in the Windows candidate DLLs. Model operator inventory and
  Stage C remain mandatory regression evidence.

## 2026-08-18T06:45:00+08:00 — P2-M3-R17/R18 Windows clean reproduction

- R17 removed unused AudioSpectrogram/MFCC/RFFT2D registrations and dependencies. Configured
  `somepath` from the minimal target to `@fft2d//:fft2d` is empty, and the 4,549-action graph no
  longer compiles Ooura sources. The target also disables Bazel's `fastbuild` feature because
  configured action evidence proved its later `/DEBUG:FASTLINK` overrode `/DEBUG:NONE`.
- R17 patch SHA-256 is
  `7099bdb0ed223d71110a18148880090f15311220f75e20cb1af6eb9619cca5dc`. Fresh roots `bw26` and
  `bw27` completed successfully and produced byte-identical artifacts, but strict review found the
  private MSVC/NMake installation path in OpenCV core's compiled build report.
- R18 changes only that Windows report normalization; patch SHA-256 is
  `b57ed5b0643d830cc9d66ad063eea211cbbab2b50c98df70d2b22f00b102775d`. The generated report now
  records only `cl.exe` and `nmake.exe`.
- Fresh roots `bw28` and `bw29` each completed 4,549 actions. Main/core/imgproc pairs are
  byte-identical with SHA-256 values
  `f99ba0a489d673ff58a1870a9e16037260913dca02912cf304173993e7e5e199`,
  `19b1b9bad3c7ad402858f97ccdc0299defbfe1d18f3a3b83bc786d7c3e443c91` and
  `1aa54040e263be7685f2b8a379cf1f34a275b0718cc8b3a823a1f935c28592b4`.
- Six-artifact scans found zero actual private path, PDB/RSDS, Ooura, Clearcut, certifi/CA-bundle or
  Windows network API. PE debug records are deterministic `coffgrp`/`repro`, not PDB references.
  Windows static reproduction passes; hardened Linux reproduction, audit and Stage C remain next.

## 2026-08-18T08:35:00+08:00 — P2-M3-R17 hardened Linux clean reproduction

- The initial `clean-output-1` attempt failed before workspace analysis because Docker started in
  `/`; the root is retained as failed-attempt evidence and was not reused.
- Fresh `clean-output-3` and `clean-output-4` each completed the exact 4,597-action build with
  `--workdir /workspace`, read-only repository cache, four-job limit and `--network none`.
- Main/core/imgproc pairs are byte-identical. SHA-256 values are
  `19e90273dc9d370563ba48b2b9a0752a677c429f80b971dd3a6c814c223c1f29`,
  `116c2db3b7e149390631af309f910eabeb73bd18281e4174f131ced2a8de4408` and
  `765ebf6c659e523d9d7e9557e63f004a041a9327fcba95e6d4ac0670485241f5`.
- ELF inspection confirms relative `$ORIGIN` RUNPATH and the required versioned Face Landmarker C
  lifecycle/detection exports. Private-path, Ooura, Clearcut/certifi/CA-bundle and known network
  surface scans are zero.
- Cross-platform build reproducibility is now evidence-complete. Updated SBOM/license/vulnerability
  disposition, exact model disposition and Stage C remain the next Gate; P2-M3 stays `EXECUTING`.

## 2026-08-18T09:20:00+08:00 — P2-M3-V03 Stage B audit disposition

- A fresh R17 `cquery deps(...)` export contains 22,719 configured labels and zero `fft2d`/Ooura
  matches. The old R05 dependency list was rejected as stale for current closure evidence.
- The regenerated private 51-component CycloneDX SBOM SHA-256 is
  `902088a0e70d3ce005885c01f7ee472fba19458ae803e09700df52949d152dda`; the 38-repository,
  124-file license inventory SHA-256 is
  `e1e77546b0a2a8148cc2f6ef6b3dc700305edad16311b09d9a836caa3c2742d3`.
- Offline Grype 0.117.0/database v6.1.9 reports zero direct closure matches. The focused OpenCV CPE
  findings were independently dispositioned through exact-backport malformed-input tests or absent
  affected modules/symbols; none was silently suppressed.
- The fixed model is private-research-only because redistribution/data provenance remains incomplete.
  Stage B passes for isolated synthetic Stage C only; no production/model/dependency approval exists.

## 2026-08-18T07:40:00+08:00 — P2-M3-R20 data-rights CI time-boundary repair

- Same-SHA run `32080603204` failed only the deletion-status step in
  `test_data_rights_http_vertical_flow_is_owner_bound_and_idempotent`; the other 390 tests and the
  secret/Docker jobs passed.
- The fixture's database session expired at the fixed instant `2026-08-17T23:30:00Z`, one minute
  before the failing CI step. The access token remained current, so production authentication
  correctly rejected the expired backing session with HTTP 401.
- R20 changes only the fixture session expiry to one day after the test's live clock. It does not
  weaken token verification, revocation reason checks, deletion-status scope or product code.
- On a fresh PostgreSQL database at migration head `0011_offline_synth_source`, the exact test passed
  five consecutive runs and the complete API suite passed.
- Same-SHA GitHub Actions run `32081539232` passed `quality-and-integration`, `secret-scan` and
  `docker-validation`. This closes R20 only; it does not advance Stage C, V02, T07, T08 or the M3
  Gate.

## 2026-08-18T10:20:00+08:00 — P2-M3-R21 Windows Stage C image ABI retention

- R19's fresh Windows roots `bw30` and `bw31` each completed all 4,549 actions, but static export
  inspection proved that both DLLs omitted `MpImageCreateFromUint8Data` and `MpImageFree`.
- The Face Landmarker lifecycle API alone cannot execute the preregistered create-image, detect and
  free sequence. Windows Stage C therefore remains fail closed.
- R21 adds only the two MSVC `/INCLUDE:` linker-retention directives analogous to R19's Linux `-u`
  directives. It does not change algorithms, model inputs, dependency versions, public product API or
  production approval.
- Two new clean roots, byte comparison, export/import/private-path scans and Windows zero-egress Stage
  C remain mandatory before acceptance.
