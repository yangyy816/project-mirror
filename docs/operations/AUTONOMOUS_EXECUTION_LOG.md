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

## 2026-08-18T10:55:00+08:00 — R21 and V03 Stage C closure

- Existing build session completed `bw35` without restart: 4,549/4,549 actions PASS. `bw34`/`bw35`
  main/core/imgproc pairs are byte-identical with SHA-256 values
  `5a904100bf197e8b4755f503aa4d1d8a8892107a9940e2f848eeb302ff24dd8d`,
  `353c960dbc233d6d412dc1015b702321f3a7f8a80494a7142c7e9c3670d61f68` and
  `1aa54040e263be7685f2b8a379cf1f34a275b0718cc8b3a823a1f935c28592b4`.
- Export/import and string scans confirm the image create/free ABI and zero private-path, PDB/RSDS,
  Ooura, Clearcut, certifi/CA-bundle, telemetry-endpoint or Windows network-API matches.
- The exact official GCS model generation was reacquired with size `3758596` and unchanged SHA-256
  `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`.
- Windows Stage C completed three fixed synthetic runs under process-specific outbound denial and
  Filtering Platform failure capture: three detect PASS, three one-face results, three close PASS and
  zero outbound attempts. Firewall and audit-policy changes were fully reverted. Together with the
  earlier three Linux `--network none` runs, V03 Stage C is PASS for private synthetic use only.
- A disk-pressure cleanup incident followed Bazel reparse points and damaged the private toolchain.
  The exact VS Build Tools workload was restored and verified before both accepted builds. Future
  cleanup must not recurse through Bazel reparse points; failed roots remain evidence.
- Official wheels remain rejected; the model remains `PRIVATE_RESEARCH_ONLY`; project dependency,
  distribution, production Vision and real-user facial processing remain blocked. Next action is
  V02 Stage D calibration, policy freeze and unchanged holdout.

## 2026-08-18T18:10:00+08:00 — P2-M3-R25 portable NMake injection closure

- R25 removes the committed private absolute `nmake.exe` path from the Windows reproduction patch.
  The tracked patch now requires `MIRROR_NMAKE_EXE` through Bazel's fail-closed action environment;
  its SHA-256 is `02264c696b85af0637724afc880604c6a3e8bee846d298d39595c2ec0a410cb3`.
- Exact-preimage apply/reverse replay passed. A fresh negative-control root failed before OpenCV
  configuration with `MIRROR_NMAKE_EXE: parameter not set`, proving that no PATH fallback occurs.
- Fresh Windows roots `bw37` and `bw38` each completed 4,549 actions. Main/core/imgproc pairs are
  byte-identical with SHA-256 values
  `1c67ae02b90a5b00b58018c3c04db411134d781c6f53b195e68a6ce6136615ef`,
  `e0415de8bd7dd97f1c2bcccfba627fe6efe4da9441c9b4c9772f3f4faa8f4343` and
  `1aa54040e263be7685f2b8a379cf1f34a275b0718cc8b3a823a1f935c28592b4`. Private-path,
  PDB/RSDS, Ooura, Clearcut/CA, telemetry-endpoint and Windows network-import scans remained zero;
  three Stage C lifecycle runs returned one face and zero outbound events.
- Fresh Linux output volumes each completed 4,597 actions under `--network none`. Their
  main/core/imgproc pairs are byte-identical with SHA-256 values
  `6a5fb35175efc2f014fb61f7f4abb2c78c38156bd6abf2186d1549cbf3f006a7`,
  `116c2db3b7e149390631af309f910eabeb73bd18281e4174f131ced2a8de4408` and
  `765ebf6c659e523d9d7e9557e63f004a041a9327fcba95e6d4ac0670485241f5`. A fresh compact Stage C
  capture recorded `RUN_OK_COUNT=3`, `DETECT_OK_COUNT=3`, `FACE_ONE_COUNT=3`,
  `CLOSE_OK_COUNT=3` and `NETWORK_CALL_COUNT=0`.
- The R25 effective build-input manifest contains 4,737 files and has SHA-256
  `5c4f74bc4dd661582d397e5d1c66d22548d103e70d75cd7a2062cc6f0958a224`. Relative to R17 only
  `third_party/BUILD` changes; the extra private `BUILD.orig` is replay evidence and is not a build
  input. Dependency labels, repositories and versions are unchanged, so the existing 51-component
  SBOM, 38-repository/124-file license inventory and vulnerability dispositions remain applicable.
- Historical R17 SHA-256 `19e90273...` remains checkpoint evidence. R19/R21 retained the image ABI,
  and `6a5fb351...` is the later frozen and currently reproduced Linux runtime. R25 does not rewrite
  the R21 policy/holdout evidence or approve official wheels, distribution, production Vision or
  real-user facial processing.

## 2026-08-18T14:36:51+08:00 — P2-M3-R26 final candidate acceptance

- R26 preserves the historical V01 evidence byte-for-byte and adds a forward correction binding its
  SHA-256, item evidence digest, actual Alembic head `0011_offline_synth_source` and descriptive
  migration name. The correction canonical digest is
  `c3d6751e97383d9cd3332e9450dc60d3427586a2aafa25496ebf09c0daaa894d`.
- Candidate `c31ca44627843c04455bbe333b6e1dcfc515d096` completed run `32106647901`; all three jobs passed.
  Downloaded artifact `9313484471` records 46 M3 tests with zero failures/errors/skips and has JSON
  SHA-256 `2edb8f76afee534fdc407c35abbbe96e6bb967520edd425068f4517e7f4d59c8`.
- Independent security and final reviews both returned PASS with no required repair. Principal
  accepts the P2-M3 Gate as PASS. Acceptance closure CI remains mandatory before FROZEN; P2-M4
  refinement remains closed until then.

## 2026-08-18T14:45:00+08:00 — P2-M3 acceptance closure and freeze readiness

- Acceptance closure `abbf6c95e33ed39c34674c881d30b6cb578d17b0` completed run `32107844716` with all three jobs
  passing. Artifact `9313887640` binds the exact SHA, migration head, 46 zero-skip M3 tests and R26
  correction digest; its downloaded JSON SHA-256 is
  `eaf8e90f334c61cc3eb41c28b225e84833880fad4a5c2895352d5a287abd326d`.
- Docker and audit artifacts are readable and Gitleaks SARIF has zero results. The evidence retains
  every official-wheel, model, distribution, production, real-user and QuestionBank boundary.
- P2-M3 advances to FROZEN through a separate freeze-state commit. P2-M4 only opens for rolling-wave
  refinement; implementation remains unauthorized until that refinement is accepted.

## 2026-08-18T15:06:00+08:00 — P2-M4 refinement and T02 domain contracts

- Repository truth: P2-M3 freeze-state `6b86a665e845e113bbfa2820f906d3b78506b753` and run
  `32108427849` were verified before M4 work. Branch `codex/phase2-m4-geometry-variants` was created
  from that exact SHA; protected `.tmp/` remained untouched.
- Refinement checkpoint `6c566c78e30bd0269a2691950c9107e84a6ddaa9` added ADR-036, the execution and
  research protocols, acceptance skeleton and Principal review. Run `32109417346` passed all three
  jobs on the exact SHA.
- T02 candidate `c173a46e43312c93b73c11462ee1adb115328fb2` added pure source-relative variant
  contracts and monotonic transform state. Local evidence: 60 targeted tests, Ruff across 153 files,
  strict mypy across 100 sources and contract drift PASS. Run `32110263179` passed all three jobs.
- No migration, dependency, model/image artifact, external download, public API or real-person data was
  added. M3 OpenCV 3.4.11 remains unavailable as the M4 runtime. Next ready work is T03 PostgreSQL
  authority or T04 isolated candidate PoC.

## 2026-08-18T16:05:00+08:00 — P2-M4-T03 and R01 acceptance

- T03 candidate `e6f45279b72258143a32bd131f5e91aecdaeedd4` added forward migration
  `0012_geometry_variant_authority`, immutable specification/run lineage and ADR-037 variant QA
  subject binding. Fresh and round-trip migration lifecycle, zero Alembic drift, six final PostgreSQL
  tests, full API/Worker regression, Ruff, strict mypy and contract drift passed locally.
- Candidate run `32113196395` passed secret and Docker jobs but failed only because the frozen P2-M3
  evidence generator incorrectly compared its historical `0011` head with the current repository
  `0012` head. `P2-M4-R01` preserves those as separate authorities and changes no historical evidence,
  schema or Gate.
- Repair `e36ec5073e9fa5b1750642ff676dc102191b2c3f` completed run `32113760284`; all three jobs passed.
  The run exercised the `0012` lifecycle, full Python/TypeScript/browser regression, frozen evidence
  generators, dependency/license audits, SBOM, Gitleaks and Docker. Expected artifacts are present and
  unexpired. Principal accepts T03 and R01; P2-M4 remains EXECUTING.
- The next bounded action is T04 candidate preregistration and isolated PoC. Download authorization
  remains distinct from dependency adoption, model distribution, production Vision and real-user
  facial-processing approval.

## 2026-08-18T16:10:00+08:00 — P2-M4-T04 candidate preregistration

- T03 governance checkpoint `75b95eb20ea47b8633c30ee6b72ce5191ce25094` completed run
  `32114265582`; all three jobs passed before T04 execution began.
- Candidate `OPENCV_PYTHON_HEADLESS_5_0_0_93_V1` freezes upstream OpenCV `5.0.0`, PyPI package
  `opencv-python-headless==5.0.0.93`, exact Windows/Linux wheel names and PyPI SHA-256 values.
- Determinism, numeric/pixel variance, bounds/foldover, zero-network, footprint, performance,
  license/SBOM/vulnerability and replacement-cost gates were frozen before artifact acquisition.
- No dependency, wheel, model or fixture was added to Git or project manifests. The next action is
  exact artifact admission into ignored private storage followed by the ordered isolated PoC.
- Artifact admission matched all three preregistered OpenCV/PyPI hashes. Before first import, wheel
  metadata exposed the Python 3.13 requirement `numpy>=2`; the resolution was frozen to
  `numpy==2.5.2` with exact official Windows/Linux wheel names and PyPI SHA-256 values. Runtime
  execution remains pending this dependency-lock checkpoint.

## 2026-08-18T16:20:00+08:00 — P2-M4-R02 PoC harness NumPy 2.5 compatibility

- The first two independent Windows roots installed the exact locked wheels, then both stopped in the
  harness negative-control helper before producing a candidate report. NumPy 2.5 rejects two-element
  vectors in `np.cross`; the OpenCV remap result itself did not determine candidate disposition.
- R02 replaces only that helper with the equivalent explicit two-dimensional determinant. It changes
  no candidate, fixture, interpolation, threshold, runtime setting or domain behavior. Both failed
  roots remain private attempt evidence; qualification restarts in new roots.

## 2026-08-18T16:35:00+08:00 — P2-M4-T04 OpenCV wheel disposition

- Two Windows and two Linux valid runs produced identical deterministic digest `5833e2cf...`; both
  cross-platform arrays were byte-identical, all negative controls passed, worst 1024 p95 was 7.2457
  ms and installed runtime was about 163 MiB. R03 preserves four Linux tmpfs import failures before
  the two successful ephemeral `--network none` runs.
- Python package audit found no known NumPy/OpenCV vulnerability and two SBOMs were generated. The
  general-purpose wheel nevertheless includes unnecessary FFmpeg/OpenSSL/codec closure; its Windows
  FFmpeg DLL imports Winsock socket/connect. Grype native DB update failed twice with TLS timeout, so
  native vulnerability review remains NOT VERIFIED.
- Candidate disposition is `FURTHER_RESEARCH`, not approval. T05 remains blocked. The next bounded
  work is a separately preregistered minimal OpenCV 5.0.0 source-built `core,imgproc` candidate.

## 2026-08-18T16:45:00+08:00 — P2-M4-T04 minimal OpenCV 5 source candidate

- Wheel-report SHA `51968c1680287542324c78573c46341ddea79aad` completed run `32116663250` with
  all three jobs passing, closing the prior candidate as `FURTHER_RESEARCH`.
- New candidate `OPENCV_5_0_0_MINIMAL_CORE_IMGPROC_V1` freezes the official 5.0.0 source archive,
  Windows/Linux toolchains, core/imgproc-only CMake closure, narrow C ABI, deterministic-build rules,
  supply-chain gates and the existing pixel/numeric/performance thresholds before any build.
- T05 remains closed. The next action is to commit and hash the wrapper/build contract, then configure
  four new task-owned roots and inspect the actual dependency graph before compilation.
- The frozen CMake and C++ wrapper digests are `1ba75ad0...` and `2bfe68ce...`. The wrapper accepts
  only bounded in-memory RGB bytes and float32 maps, exports version/remap functions, fixes one thread
  and disables optimized dispatch. No configure or build was run before these digests were recorded.

## 2026-08-18T18:40:00+08:00 — P2-M4-T04 bounded OpenCV 5 V2 local disposition

- Candidate `OPENCV_5_0_0_BOUNDED_TRANSITIVE_SOURCE_V2` completed two clean Linux `--network none`
  roots and two clean Windows roots. All five runtime pairs are byte-identical per platform; all four
  harness reports share deterministic digest `ebfee6e9...`, byte-identical cross-platform fixture
  outputs and passing negative controls.
- R08's conditional linker overlay removed the last Windows PDB metadata without changing the module
  graph or algorithm. All Windows binaries have zero RSDS/PDB, private-path, pthread and network-import
  matches. Linux retains only relative `$ORIGIN` and zero network undefined symbols.
- A final Windows run under process-specific outbound denial and Filtering Platform failure capture
  completed with zero attempted egress. The temporary rule was removed and audit policy restored.
- The exact closure is `core,flann,geometry,imgproc` plus bundled static zlib `1.3.2`. License notices
  are closed; private CycloneDX SBOM SHA-256 is `2345cba1...`; offline Grype 0.117.0/database v6.1.9
  reports zero matches.
- Principal local disposition is `APPROVED_FOR_PRIVATE_SYNTHETIC_M4`. T05 remains closed until this
  tracked evidence passes same-SHA GitHub Actions. No binary, project dependency, model, image,
  production, distribution, real-user or QuestionBank authority is added.

## 2026-08-18T18:50:00+08:00 — P2-M4-T04 tracked evidence acceptance

- Commit `28e5ae8ab9350fe44fa1e14aa1ae9c15436717fa` was pushed normally using the user's local proxy
  only for the command; no persistent Git proxy configuration changed.
- Same-SHA run `32125987000` passed `quality-and-integration`, `secret-scan` and
  `docker-validation`. The existing Node 20 action-runtime deprecation annotations are non-blocking.
- Downloaded artifact `9320466783` records migration head `0012`, 46 M3 tests with zero
  failures/errors/skips and unchanged private-synthetic boundaries. Project audit, Docker and
  Gitleaks artifacts are present and readable.
- Principal accepts T04 and opens T05. P2-M4 remains `EXECUTING`; T05–T08 and the Milestone Gate are
  not complete.

## 2026-08-18T19:10:00+08:00 — P2-M4 CC02 Debian 12 compatibility qualification

- R09 commit `8332d9341ac06776008755f282fb0814c3cdca9f` completed same-SHA run `32128839492`; all three
  GitHub Actions jobs passed, closing the Linux-mypy portability defect only.
- The first two Debian 12 V3 roots were byte-identical and behaviorally correct but retained
  `/work/...` inside OpenCV build-info. R10 preserved those roots as attempt evidence and rebuilt in
  fixed `/usr/src/...` roots without changing source, R08, modules, zlib, ABI, algorithm or fixtures.
- The two R10 roots are byte-identical for all five runtime files. Private-path and network-symbol
  scans are zero; maximum requirements are glibc 2.35, GLIBCXX 3.4.30 and CXXABI 1.3.13.
- The standard Debian 12 API image ran the real adapter under `--network none` and produced the same
  canonical result SHA-256 `5f7868d5...` as Windows. Updated private SBOM SHA-256 is `641a93ad...`;
  offline Grype 0.117.0/database v6.1.9 reports zero matches.
- `CC-P2-M4-02` is PASS. T05 still requires its complete tracked regression and same-SHA candidate
  evidence before Principal acceptance; T06 remains closed.

## 2026-08-18T19:21:00+08:00 — P2-M4-T05 local candidate validation

- Ruff, dual-platform strict mypy, focused transform tests, full Linux API/Worker tests on a fresh
  PostgreSQL `0012` schema, pnpm check/build/contracts and Compose health/behavior all pass.
- Final Linux repository run is 444 passed with four existing optional skips. Earlier container
  attempts honestly preserve missing runtime-image repo files, read-only test storage and missing
  mirrored `DATABASE_URL` as harness failures; none required a production-code workaround.
- All five Compose services remain healthy. Temporary PostgreSQL test databases were removed;
  task-owned runtime/build/SBOM volumes remain preserved for evidence.
- Candidate is ready for tracked commit and same-SHA Actions evidence. T05 is not yet accepted and
  T06 remains closed.

## 2026-08-18T19:28:00+08:00 — P2-M4-T05 tracked acceptance

- Candidate `75c0ccbaeab5ae4e1a8e66054f2225f701e221eb` completed run `32131383622` with
  `quality-and-integration`, `secret-scan` and `docker-validation` all successful.
- Seven expected audit/frozen-regression/Docker/Gitleaks artifacts are present and unexpired. Only
  the existing non-blocking Node 20 action-runtime deprecation annotations remain.
- Principal accepts T05 plus R09/R10 and opens T06 only. P2-M4 remains `EXECUTING`; T07/T08 and the
  Milestone Gate are not complete.

## 2026-08-18T19:36:00+08:00 — P2-M4-T05 acceptance closure

- Forward checkpoint `2afc084d8dade07d28da3c3d68d87006d4a94f49` completed run `32131954633`;
  `quality-and-integration`, `secret-scan`, and `docker-validation` all passed.
- Seven exact-SHA audit/frozen-regression/Docker/Gitleaks artifacts are present and unexpired.
- T05 remains accepted and T06 is now executing. This closure does not advance T07/T08 or the
  P2-M4 Milestone Gate.

## 2026-08-18T19:44:00+08:00 — CC-P2-M4-03 warp-plan authority

- T06 entry review stopped before writes: `0012` does not persist the immutable LandmarkWarpPlan
  required to reconstruct `GeometryTransformRequest`; Job/message fallback would violate the
  reference-only contract.
- ADR-038 accepts one immutable plan per VariantSpecification, with origin restricted to
  `PREREGISTERED_M4_RESEARCH_PLAN`, and a forward `0013` migration. This is change control, not Rxx.
- T06 remains blocked until `CC-P2-M4-03-A` domain/ORM/migration/PostgreSQL evidence is accepted.

## 2026-08-18T21:05:00+08:00 — CC-P2-M4-03-A local candidate

- Implemented typed canonical plan serialization, immutable ORM authority and forward migration
  file `0013_landmark_warp_plan_authority.py`; the actual Alembic revision/head is
  `0013_warp_plan_authority`.
- Principal adversarial review demonstrated that recomputed digests could bypass the initial
  PostgreSQL canonical-text check with duplicate keys or integerized coordinates. The uncommitted
  trigger was corrected to inspect raw JSON ordering/duplicates, escapes and canonical float text;
  four direct-SQL negative cases now reject.
- Ruff format/lint, strict mypy (116 sources), 22 focused domain/PostgreSQL tests, contracts drift,
  fresh `→0013→0012→0013`, zero-drift Alembic check and the complete Linux API/Worker suite all
  pass. The full suite has seven existing optional skips and no executed failure; the complete pnpm
  format/lint/typecheck/test/contracts/build gate also passes.
- Candidate commit, same-SHA Actions and artifact inspection remain pending. T06 stays blocked until
  Principal accepts CC03-A; T07/T08 and the P2-M4 Gate remain closed.

## 2026-08-18T21:15:00+08:00 — P2-M4-R11 CI evidence-head repair

- Candidate `4af3a8a3ff3264887ac8752a581180049cb6d240` run `32137671571` passed
  `secret-scan`, `docker-validation`, all migration/tests and browser checks. Phase 1 evidence
  generation then failed because all four workflow evidence calls still expected the prior `0012`
  head; downstream evidence/audit steps were skipped by the failed job.
- R11 changes only those four expected-head arguments and their repository regression assertions to
  the real `0013_warp_plan_authority`. No evidence generator, check, artifact or frozen regression is
  removed or weakened.
- A new same-SHA run and all expected artifacts remain mandatory before CC03-A acceptance and T06
  resume.
