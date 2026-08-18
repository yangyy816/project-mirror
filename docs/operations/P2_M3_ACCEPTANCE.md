# P2-M3 Acceptance Evidence

## Status

- Milestone: `P2-M3 — Synthetic Normalization and Base Identity QA`
- State: `EXECUTING`
- Frozen entry: `0b579ebdb1c2a63936225bc59a4b0ca780544df2`
- Migration head: `0011_offline_synth_source` after ADR-035 change control
- Public API change: none
- Vision candidate Gate: `PASS_PRIVATE_SYNTHETIC_ONLY`
- Real-user facial processing: prohibited

## Mandatory evidence matrix

| Gate                      | Required evidence                                                          | Status     |
| ------------------------- | -------------------------------------------------------------------------- | ---------- |
| M2 authority preservation | no GenerationItem/raw/generation evidence rewrite                          | T02 PASS   |
| Migration                 | `0010` evidence plus fresh and `0010→0011→0010→0011`, drift zero           | PASS       |
| Normalization             | bounded decode, sanitation, canonical encode, second decode, checksum      | T03 PASS   |
| Namespace                 | normalized private namespace separate from raw/user assets                 | T03 PASS   |
| Immutability              | Asset/record/measurement/review/identity lineage cannot mutate/delete      | T02 PASS   |
| QA                        | versioned run, typed measurements, reason codes and hard-gate evaluator    | T04 PASS   |
| Adult policy              | reject clear pre-16 or child/student-minor context; no age estimate        | T06 PASS   |
| Vision                    | approved exact package/model/data/license + controlled benchmark           | T06 PASS\* |
| Identity                  | one QA-passed canonical Asset creates at most one identity transactionally | T05 PASS   |
| Synthetic-only            | no User relation, real-person fixture, scraping or sensitive classifier    | T02 PASS   |
| Recovery                  | duplicate delivery, lease expiry, blob-before-commit and cleanup race      | T05 PASS   |
| Contracts                 | OpenAPI/generated TypeScript unchanged                                     | T02 PASS   |
| Supply chain              | Pillow unchanged; every new package/model separately approved              | T06 PASS\* |
| Full Gate                 | Python/TS/PG/Redis/Celery/Docker/Gitleaks/SBOM/same-SHA Actions            | T07 LOCAL  |
| Final review              | independent security and final reviewer acceptance                         | PENDING    |

`T06 PASS*` is limited to the source-built private synthetic M3 candidate. Official wheels,
distribution, production Vision and real-user facial processing remain blocked.

## Bounded native validation

The existing eight P2-M2-V01 source files may be reused from private storage after checksum and
source-evidence reconciliation. They are not regenerated merely to exercise M3. Requested
`1024×1024 PNG` and observed `1254×1254 PNG` remain distinct facts.

ADR-035 closes the discovered authority gap: V01 must not be represented by fabricated M2
Batch/Item/Provider records. A forward `0011` offline admission authority preserves all known-null
provenance, binds the private receipt digest and raw metadata, and then feeds the unchanged M3
normalizer through `SyntheticSourceObject`. This is a formal change control, not a Repair Task or a
production import API.

The M3 validation sequence is:

1. `P2-M3-V01`: normalize all eight admitted raw objects without resampling to the requested shape;
   verify sanitation, canonical output, second decode, namespace, checksum and no tracked binary.
2. `P2-M3-V02`: after Vision candidate approval, run face/pose/visibility/landmark measurement,
   repeatability and negative controls under a preregistered QAPolicy.
3. Explicit operator review records the applicable versioned adult-presentation rubric, obvious
   text/watermark/background, likeness risk and rights scope without overriding any automatic hard
   failure. Under ADR-030, a general non-sexual portrait fails the age-presentation review only for
   `CLEAR_PRE16_PRESENTATION` or `CHILD_OR_STUDENT_MINOR_CONTEXT`; adult-only style overlays remain
   stricter.
4. Register identities only for assets that satisfy every required gate. A rejected asset remains
   immutable evidence and is never silently replaced.

These eight assets validate the pipeline; they are not final coverage, diversity, transform,
QuestionBank or questionnaire evidence.

Future Codex-native cohorts whose built-in tool exposes no requested dimensions use the ADR-031 v2
admission contract. Their evidence must preserve observed dimensions while requested width/height and
the match fact remain `NULL`. This is not a dimensions-compliance claim and does not permit raw
resampling. All v1 evidence remains immutable; all image, source-root and resource-limit gates remain
mandatory.

## T03 deterministic normalization evidence

- `SyntheticNormalizationService` preserves M2 raw authority, verifies inspect metadata plus the
  streamed byte count/checksum, reuses the pinned `image-sanitizer-v1`, and creates an immutable
  internal synthetic `Asset` only after canonicalization and normalized storage admission.
- normalized storage uses `internal-synthetic/v1/normalized`; its opaque reference is derived from
  the immutable record ID and normalizer config digest. Raw, normalized and user namespaces remain
  disjoint.
- all database paths use source-object then synthetic-record lock order. A concurrent duplicate is
  idempotent; a blob stored before database commit is reused; deterministic content/tamper/conflict
  failures are terminal; a transient store failure leaves `NORMALIZING` recoverable.
- Linux targeted evidence: 25 sanitizer/raw/normalized/0010/concurrency/recovery tests passed with
  zero skip. Full API/Worker regression: 366 tests, zero failures, zero errors and three pre-existing
  Celery round-trip skips because the isolated run did not start an external worker; these skips are
  not T03 mandatory evidence and remain covered by the later full CI Gate.
- Windows and Linux produced the same canonical JPEG checksum
  `f55764d4e734d3d465707df1327826395f3ca3972c40601c1477f3cb8c52a495`, byte size `694`,
  dimensions `64×64`, and config digest
  `5ebe5ea3e9b0e5c8ad86b93166e38f11da7bdcd76a7a2801aadd0f30e32f81de`. Input PNG bytes differed
  by platform compression, while canonical output remained exact.
- complete Linux Ruff format/lint and strict mypy passed; `pnpm.cmd contracts:check` passed; no
  dependency, model/weight, public API, OpenAPI/generated TypeScript or real-person fixture changed.

## P2-M3-V01 offline authority and normalization evidence

- The frozen P2-M2-V01 manifest was not regenerated or rewritten. Its eight raw checksums,
  byte counts and observed `1254×1254` dimensions were reconciled against private storage before
  each immutable admission and source row was created.
- The isolated `p2m3_v01_authority` PostgreSQL run completed with exactly 8 offline admissions,
  8 offline sources, 8 normalized records and 8 normalized synthetic Assets. A second complete run
  returned the same authority and result for every item, proving import and normalization replay
  idempotency.
- All eight normalized objects passed streamed byte/checksum verification and second JPEG decode.
  The frozen normalizer was `image-sanitizer-v1` with config digest
  `5ebe5ea3e9b0e5c8ad86b93166e38f11da7bdcd76a7a2801aadd0f30e32f81de`; requested dimensions
  remained a distinct source fact and no resampling was performed.
- The committed redacted evidence is
  `docs/operations/P2_M3_V01_NORMALIZATION_REDACTED_EVIDENCE.json`; its canonical item evidence
  digest is `eabea6fe4159cc8932d2ebd4d1797e0ed3aa3e982dcbc15b052f6136e294f299`.
  It contains no Prompt, private path, storage reference, image bytes or fabricated Provider facts,
  and records zero tracked binaries.
- This closes V01 normalization only. Vision QA, the versioned adult review, morphology measurement,
  identity registration and QuestionBank release remain blocked or not authorized until their own
  gates pass.

## T03 same-SHA remote evidence

- Checkpoint `9856c235432fb580836480cfaee56c21e8c58c1b` was pushed to
  `codex/phase2-m3-normalization-base-qa` and run `31965014695` completed successfully.
- `quality-and-integration`, `secret-scan` and `docker-validation` all passed on that exact SHA.
  Python quality/tests, the PostgreSQL migration lifecycle, Redis/Celery integration, TypeScript
  quality/build, browser integration, contract drift, dependency/license audit and SBOM steps all
  succeeded.
- Phase 1, P2-M1 and P2-M2 regression evidence artifacts, Docker evidence, project audit evidence
  and Gitleaks SARIF were present and exact-SHA bound. This checkpoint proves T03 regression safety;
  it is not the final `mirror.p2-m3.ci-evidence/v1` required by T07.

## T04 QA contract and R01 evidence

- The Vision port accepts only bounded canonical-JPEG `NormalizedSyntheticImagePayload` with an
  opaque normalized Asset reference and content-matching SHA-256. Raw generation payloads, User
  Assets, URLs, object keys, SDK types and network locations are not representable on this path;
  the Mock remains deterministic and zero-network, while unverified candidates remain fail closed.
- `SyntheticQAService` persists typed measurements and explicit operator reviews into the existing
  append-only `0010` authority. Execution `FAILED` remains distinct from content `REJECTED`.
- `P2-M3-R01` removed caller-supplied finalization requirements. Finalization now loads the exact
  QARun-bound `APPROVED` QAPolicy, validates its canonical digest and closed
  `QAPolicyDefinition/v1` grammar, and matches hard-gate classification plus algorithm/version.
  Missing, unknown, unsupported, malformed, `NOT_APPLICABLE` or mismatched required evidence fails
  closed; human review cannot erase an automatic hard failure.
- Principal verification: Ruff format/lint passed; strict mypy passed for 96 sources; 12 focused
  unit/provider tests passed; contract drift remained zero. A fresh isolated PostgreSQL 17.6 was
  migrated through `0010`; the migration-backed async service test passed twice consecutively in
  Linux, proving deterministic replay. The temporary database was removed and the original five
  Compose services remained healthy.
- T04 does not approve a real Vision candidate, perform adult/likeness/license review on V01 assets,
  register an identity or satisfy T06/T07. Those gates remain pending.

## P2-M3-R02 frozen M2 boundary regression repair

- The failed `quality-and-integration` job in run `31966322329` was caused by the frozen M2
  regression test recursively scanning every later `synthetic_dataset` module. The new M3
  normalization and QA modules therefore supplied `SyntheticQARun` to an M2-only forbidden-symbol
  assertion even though no M2 implementation crossed into M3.
- `P2-M3-R02` keeps the existing broad zero-network and redacted-logging scan intact, but fixes the
  M2 phase-boundary scan to the concrete M2 generation, prompt, raw-storage and Worker module set.
  A regression assertion proves that present M3 normalization/QA modules are non-empty and disjoint
  from that frozen M2 source set.
- The four focused M2 security-boundary tests pass locally; Ruff format/lint and `git diff --check`
  also pass. The wider evidence tests require Linux CI because the known Windows pytest temporary
  directory ACL fault recurred.
- Repair commit `d37f61b253c2240478d72aacedd167ede6d96eaa` completed same-SHA run `31966877634`.
  `quality-and-integration`, `secret-scan` and `docker-validation` all passed, including the original
  P2-M2 deterministic integration and boundary evidence step. Phase 1, P2-M1, P2-M2, Docker,
  project-audit and zero-result Gitleaks artifacts were present. `P2-M3-R02` is accepted.

## T05 Worker orchestration and P2-M3-R03 evidence

- Normalization and QA task messages are closed, reference-only schemas containing only the
  record/run ID, deterministic Job ID, request ID and schema version. `Job`/`JobAttempt` remain an
  empty-payload execution envelope; no image bytes, Prompt, policy payload, storage location, URL or
  Provider SDK type enters Celery.
- The Celery-independent application service schedules, leases, retries and reconciles M3 work;
  Celery routes normalization/QA to `mirror.synthetic` and reconciliation to
  `mirror.maintenance`. Production still rejects local synthetic storage and no public API or CLI
  was added.
- Canonical identity registration revalidates the approved policy and all append-only hard-gate
  evidence under PostgreSQL locks. Concurrent registration creates one identity, and the existing
  `0010` trigger atomically advances the record to `IDENTITY_REGISTERED`.
- Principal review rejected the initial Worker PASS and opened `P2-M3-R03`: reserve used
  `Job → record/run` while completion used `record/run → Job`; a crash after QA finalization also
  left `QA_PASSED` permanently unreconciled, and retry exhaustion terminalized only the Job.
  R03 now uses domain-authority-before-envelope lock order, reconciles `QA_PASSED` records until
  identity registration, and atomically moves exhausted normalization/QA work to
  `NORMALIZATION_FAILED`/`QA_FAILED` with a failed final attempt. A fifth delivery is a no-op.
- Fresh Linux targeted evidence passed: five PostgreSQL normalization/QA/concurrency/recovery tests,
  one real Redis/Celery queue test and two Worker adapter tests. A fresh full API/Worker suite with
  PostgreSQL 17.6, Redis 8.2.1 and an external Celery Worker passed with zero failures.
  `alembic check` reported no operations; Ruff covered 178 files, strict mypy covered 110 sources,
  contract drift and `git diff --check` passed. All exact T05/R03 temporary containers and private
  test directories were removed.
- T05 and R03 do not approve a Vision candidate, provide V02 calibration or satisfy T06–T08. M3
  remains `EXECUTING` and M4 entry remains closed.
- Candidate `5a726fc6348ab253b98e945348cfeac4b835a832` completed same-SHA run `31968433284`.
  `quality-and-integration`, `secret-scan` and `docker-validation` all passed. Phase 1, P2-M1,
  P2-M2, Docker, project-audit and zero-result Gitleaks artifacts were present. Principal accepts
  T05 and R03; this is not the final T07 M3 evidence Gate.

## T06 Vision candidate supply-chain and runtime Gate

- Exact MediaPipe source candidate was `v0.10.35` at commit
  `f8ef212d5c962c0e853db7e59d217056b187084b`; Windows and Linux wheel SHA-256 values are recorded,
  and the authorized private wheel and bundle acquisitions matched the frozen manifest.
- The Principal read and rendered all pages of the official BlazeFace Short Range, Face Mesh V2 and
  Blendshape V2 model cards. Each model card explicitly states Apache-2.0. Their training/evaluation
  data descriptions are high level and do not close per-dataset rights, territory, deletion or
  redistribution evidence.
- GCS metadata fixes the Face Landmarker bundle at generation `1683136941468629`, size `3758596`,
  MD5 `b0e7274907a1644404fef66b28dd6d85` and CRC32C `2FSEdQ==`; upstream publishes no SHA-256.
- The bundle SHA-256 was independently computed as
  `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`; an exact CPython 3.13 package
  set and private SBOM were produced without changing project manifests or adding tracked artifacts.
- Stage C produced a protocol-defined hard failure. A bounded Windows inference completed while
  outbound egress was blocked, but the native runtime still attempted to upload to Google Clearcut.
  Native static evidence includes the portable Clearcut uploader, HTTP client and
  `https://play.googleapis.com/log`. Linux `--network none` completed without the same message, which
  does not waive a Windows platform failure.
- No calibration, negative-control run, QAPolicy threshold freeze, holdout or identity registration
  followed. T07/T08 and M4 entry remain closed pending an independently approved replacement Vision
  candidate.
- `docs/research/P2_M3_V02_VISION_CALIBRATION_PROTOCOL.md` now freezes the exact `0.10.35` candidate,
  artifact manifest, four-stage audit, V01 calibration/holdout split, negative controls and
  policy-freeze-before-holdout rule. This removes planning ambiguity but does not authorize a
  download, install, model run or threshold.
- PyPI `1.0.1` was rejected for this PoC because it retains the same unpinned dependency families and
  missing Python/license metadata, substantially enlarges both target wheels and introduces a
  GitHub/PyPI version mapping mismatch without closing any T06 blocker.
- Exact-tag static review found local model path/buffer APIs and no explicit Python HTTP/socket
  client in `face_landmarker.py`, but `BaseOptions` passes a `certifi` CA-bundle path to native code.
  This prediction was confirmed unsafe by the Windows runtime result. V02 had frozen
  `num_faces=2`, CPU/image mode, upstream `0.5` confidence baselines, blendshapes disabled and
  transformation matrices enabled before calibration.

`P2_M3_T06_STATUS: CANDIDATE_FAIL`

`P2_M3_VISION_REPLACEMENT_REQUIRED: YES`

## V03 source-built replacement candidate

- ADR-032 and `P2_M3_V03_SOURCE_BUILT_VISION_PROTOCOL.md` authorize only an exact-source Stage A
  feasibility study at MediaPipe commit `f8ef212d5c962c0e853db7e59d217056b187084b`.
- The upstream `0.10.35` wheels remain rejected; a blocked destination or hidden warning is not a
  telemetry fix.
- Before build or execution, the patch, toolchain, dependency lock, artifact hashes, native
  inventory, license/NOTICE set and private SBOM must be frozen.
- Both Windows and Linux must prove the runtime closure has no Clearcut, telemetry, HTTP/network or
  CA-bundle path and makes zero egress attempts. Calibration and holdout remain closed.

Stage A verified the exact source commit and public dummy-logger closure, froze patch SHA-256
`cdde123e56bcd637726d7162171a75bed10de415cd323aa95952b1cba7e942eb`, and selected a minimal C ABI
shared-library target instead of the upstream Python wheel/full task library. No build, install,
model execution or calibration occurred. ADR-033 then froze the Linux toolchain, 39-repository
configured closure and OpenCV 3.4.11 `core,imgproc` build-lock overlay. The offline Linux build
completed after `P2-M3-R04` stripped a Windows CR from the upstream metadata version stamp. The
minimal C ABI library and two OpenCV libraries have frozen hashes, bounded exports and no dynamic
network imports or Clearcut/CA-bundle strings. R05 clean reproduction is recorded below. OouraFFT
distribution rights, remaining vulnerability dispositions, Windows toolchain/build and all
runtime/model stages remain pending.

`P2_M3_V03_STATUS: STAGE_B_WINDOWS_REPRODUCIBILITY_PASS_HARDENED_LINUX_REPLAY_PENDING`

`P2-M3-R05` closed the Linux bit-reproducibility defect. Two fresh no-network 4,610-action builds
produced byte-identical main, OpenCV core and OpenCV imgproc libraries. All private path scans were
zero; OpenCV has no RPATH/RUNPATH and the main library has only a relative `$ORIGIN` RUNPATH. This
does not close the independent OouraFFT distribution-license blocker, remaining vulnerability
dispositions, Windows build/runtime, model/data or V02 calibration Gates.

ADR-034 / `CC-P2-M3-02` freezes the OpenCV persistence-parser backport and unused RFFT2D removal;
`P2-M3-R08` implements that already-frozen closure. After the exact OpenCV 3.4.11 backport correction
described in R11 and R12 canonical whitespace normalization, the current outer runtime-closure patch
SHA-256 is `9c7f6c9032f1ffa050044123e29cc596ca255332e78d5af7fb77cf5f20f65e60`; it apply/reverse-applies
against the prepared exact source. This remains candidate evidence until both platforms, model
operator inventory and Stage C pass.

`P2-M3-R09` addresses the Windows foreign-CMake compiler-detection defect without changing the
runtime graph. After R12 canonical whitespace normalization, the rules_foreign_cc patch SHA-256 is
`c401de5d81a420ecdaa30f9c711b9b45d2bafdecbc7a5e7b71a0003845d02146`; it removes only the
double-escaped MSVC `__DATE__`/`__TIME__`/`__TIMESTAMP__` flags at the CMake boundary. The MediaPipe
toolchain patch SHA-256 is `38db262542d155dab30f55b43041ec4e56283f6fc6be6a4118ba938ccd545db1` and pins the frozen
Windows SDK `mt.exe` (local SHA-256
`1b8a272d586a9ab53ac2ccd457a88bd0210d7d7ac3daea5b34743cc2afe73b26`). `bw16` is preserved as
failed evidence; no success claim is made yet.

`P2-M3-R10` corrects only the exact TensorFlow `kernels/BUILD` ordering context in the RFFT2D removal
patch. `bw18` failed during repository patching before compilation; the corrected inner patch then
passed `git apply --check` against the exact snapshot. Fresh build roots must be used for acceptance.

`P2-M3-R11` corrects the OpenCV persistence hardening patch target without changing ADR-034's frozen
security outcome. `bw19` proved that upstream commit `5691d998...` targets the newer C++ parser layout,
while the locked OpenCV 3.4.11 archive contains the legacy C parser layout. The backport now applies the
same entry-point and post-skip null checks to the exact legacy JSON/XML/YAML parser functions. After
R12 canonical whitespace normalization, the inner patch SHA-256 is
`a1037142e804aeb74d072d159b36f03289bdfc1be223199c06b7543301ddba62`.
`bw19` remains failed evidence; only fresh `bw20`/`bw21` roots may support reproducibility acceptance.

`P2-M3-R12` removes trailing spaces only from added blank lines in five tracked patch artifacts after
the pre-commit Gate found them. No source token, build flag, dependency or runtime graph changed. The
normalized LLVM, runtime-closure, Windows-build, BusyBox and CMake-flags patch SHA-256 values are,
respectively, `9c4524600297eda5f7df81b2aa7ed2b82b90907f33f441725710a3a7a56431ff`,
`9c7f6c9032f1ffa050044123e29cc596ca255332e78d5af7fb77cf5f20f65e60`,
`9bec126ea037a8a9d72417ba798252e5b32fdb2c94b0081c5de55cf89f6c5c9a`,
`7a586cbe76741e1c620b11495ccbb5bf879d0cddfe4d2a186a5a8d0190140424` and
`c401de5d81a420ecdaa30f9c711b9b45d2bafdecbc7a5e7b71a0003845d02146`. Each reverse-apply-checks
against its prepared exact snapshot; the runtime closure also apply-checks against the pre-Windows
baseline, and repository `git diff --check` is clean.

`P2-M3-R17` closes two Windows closure defects. The exact configured graph no longer has a path from
the minimal Face Landmarker target to `@fft2d`; unused AudioSpectrogram/MFCC/RFFT2D registrations and
sources are absent. Bazel's target-level `fastbuild` feature is disabled so its later
`/DEBUG:FASTLINK` cannot override `/DEBUG:NONE` and create an RSDS/PDB reference. The tracked patch
SHA-256 is `7099bdb0ed223d71110a18148880090f15311220f75e20cb1af6eb9619cca5dc`.

`bw26` and `bw27` proved byte reproducibility for the resulting 4,549-action graph, but a stricter
scan found the frozen MSVC/NMake installation path in the OpenCV core build report. `P2-M3-R18`
canonicalizes only those report fields to `cl.exe`/`nmake.exe`; its patch SHA-256 is
`b57ed5b0643d830cc9d66ad063eea211cbbab2b50c98df70d2b22f00b102775d`.

Fresh roots `bw28` and `bw29` each completed all 4,549 actions with exit code zero. The corresponding
main, OpenCV core and OpenCV imgproc DLLs are byte-identical. Their final size/SHA-256 pairs are:

- 30,324,736 / `f99ba0a489d673ff58a1870a9e16037260913dca02912cf304173993e7e5e199`;
- 2,302,464 / `19b1b9bad3c7ad402858f97ccdc0299defbfe1d18f3a3b83bc786d7c3e443c91`;
- 2,385,408 / `1aa54040e263be7685f2b8a379cf1f34a275b0718cc8b3a823a1f935c28592b4`.

All six final DLLs have zero actual private-root, PDB/RSDS, Ooura, Clearcut, certifi/CA-bundle and
Windows network-API matches. Imports remain bounded to OpenCV, MSVC/CRT and Windows runtime support;
all seven required Face Landmarker lifecycle/detection exports are present. Deterministic
`coffgrp`/`repro` PE records remain and are not PDB references. Windows static build/reproduction
evidence passes, but the hardened R17 graph still requires two fresh Linux reproductions, updated
license/SBOM/vulnerability evidence and Stage C zero-egress runtime qualification before V02.

## Deferred production boundary

`PRODUCTION-BLOCKER-IMAGEGEN-PROVIDER` remains `OPEN`. M3 synthetic research does not approve a
runtime image-generation Provider, real-user Vision processing, production QuestionBank or public
release. Codex native provenance remains `PROVENANCE_ONLY` and unknown facts remain `NULL`.

## Approved age-presentation change control

- ADR-028 and `P2_AGE_PRESENTATION_CONTROL_V1.md` were accepted by the Principal as the original
  forward-only v1 control. V01 remains immutable, while ADR-030 supersedes its universal
  `minor ambiguity` rule only for future general non-sexual cohorts.
- V-next primary presentation is clearly-adult 18–25; 26–30 is secondary only for coverage, 31–34
  is de-emphasized, and visibly 35+ is a first-pack selection exclusion.
- Under the current v2 authority, a youthful or babyface appearance alone is allowed; general
  rejection requires `CLEAR_PRE16_PRESENTATION` or `CHILD_OR_STUDENT_MINOR_CONTEXT`. No
  age-estimation model or real-person reference is authorized.
- New images may be generated only with new private Prompt/policy versions and must pass adult
  clarity plus morphology/identity-diversity review before any admission claim.

## Approved multi-peak style-presentation change control

- ADR-029 and `P2_STYLE_PRESENTATION_CONTROL_V1.md` were accepted as a forward-only content and
  curation control for a separate style-aware cohort.
- The cohort uses eight non-exclusive style contexts and categorical questionnaire/style suitability
  evidence. It records no beauty/attractiveness score, percentile or ranking.
- Adult/minor safety remains a hard gate. `PRODUCT_CONTEXT_MISMATCH`,
  `WEAK_STYLISTIC_DISTINCTIVENESS` and `FIRST_PACK_STYLE_REDUNDANCY` are soft first-pack curation
  exclusions only.
- V01 and the age-only V-next cohort remain immutable and are not considered style-evaluated.
- Style-aware generation/admission evidence cannot satisfy the still-blocked Vision candidate,
  calibration, QAPolicy freeze, identity registration, QuestionBank release or production Provider
  Gates.

## Approved youthful-adult review boundary v2

- ADR-030, `P2_AGE_PRESENTATION_CONTROL_V2.md` and `P2_STYLE_PRESENTATION_CONTROL_V2.md` apply only
  to future cohorts. All v1 evidence remains immutable.
- General non-sexual portraits no longer fail solely for a round face, babyface or youthful adult
  appearance. `CLEAR_PRE16_PRESENTATION` and `CHILD_OR_STUDENT_MINOR_CONTEXT` are hard rejects.
- `ADULT_SAFE_SEXY`, `CHARMING_ALLURING` and other adult-only style contexts additionally require
  unambiguous 18+ presentation; `ADULT_ONLY_STYLE_AGE_AMBIGUOUS` is a hard reject.
- Review remains categorical and human. No automatic age estimation, numerical age, probability,
  beauty score, percentile or ranking is permitted.
- New generation/admission evidence must bind v2 policy/Prompt/rubric references and cannot be used
  to rewrite or reinterpret V01, age-v1 or style-v1 evidence.

## Approved native admission schema v2

- ADR-031 is a forward-only representation change for native tools without auditable requested
  dimensions; it does not rewrite ADR-026 v1 evidence.
- Unknown requested width/height and `dimensions_match_requested` must remain `NULL`; observed
  width/height are mandatory.
- Cohort requested quantity, global attempt ceiling, per-item retry ceiling and serial concurrency
  must be enforced independently of per-Prompt specifications.
- MIME/magic, checksum, bytes, edge, pixels, frame count, decode, private source-root and attempt
  ceilings remain hard gates. Known requested dimensions still require a matching aspect ratio.
- No public API, runtime Provider, production generation, dependency, model, weight or real-person
  processing is authorized.

## Style-v2 native cohort evidence

- `P2_M3_STYLE_V2_REDACTED_EVIDENCE.json` binds the v2 policy, plan, admission manifest, admission
  evidence and categorical review digests without Prompt text, private paths, object keys, storage
  references or image bytes.
- Eight source candidates were requested and admitted with 10 of 12 allowed attempts. Two rejected
  attempts remain immutable private evidence; neither was silently replaced or deleted.
- All eight passed the ADR-030 general/adult-only categorical hard gates and were recorded as
  questionnaire-suitable without age estimation, beauty/attractiveness scoring or ranking.
- Candidate selection is still soft and provisional. Vision QA, morphology measurement, identity
  registration and QuestionBank release remain blocked and are not implied by this evidence.

`P2_M3_LOCAL_GATE: PASS`

`P2_M3_T03_REMOTE_CI: PASS`

`P2_M3_REMOTE_CI: PENDING_FINAL_T07`

`P2_M3_STATE: EXECUTING`

`P2_M4_ENTRY: CLOSED`

## R17 hardened Linux clean reproduction checkpoint

- The first Linux retry root is retained as failed-attempt evidence because Docker started outside
  the Bazel workspace; it is not reused or counted as acceptance evidence.
- Fresh `clean-output-3` and `clean-output-4` roots each completed all 4,597 R17 actions under
  `--network none` with exit code zero.
- Main/core/imgproc artifacts are byte-identical across the two roots with SHA-256 values
  `19e90273dc9d370563ba48b2b9a0752a677c429f80b971dd3a6c814c223c1f29`,
  `116c2db3b7e149390631af309f910eabeb73bd18281e4174f131ced2a8de4408` and
  `765ebf6c659e523d9d7e9557e63f004a041a9327fcba95e6d4ac0670485241f5`.
- ELF imports/exports and relative RUNPATH are bounded as designed. Private host paths, Ooura,
  Clearcut/certifi/CA-bundle and known network-surface strings are absent from the three-artifact
  closure.
- Cross-platform build reproducibility is accepted as evidence only. Updated SBOM/license/
  vulnerability disposition, exact model disposition, Stage C, V02, T07 and T08 remain mandatory.

`P2_M3_R17_LINUX_REPRODUCIBILITY: PASS`

## R17 Stage B audit checkpoint

- The authoritative R17 configured dependency graph contains 22,719 labels and zero `fft2d`/Ooura
  matches; the obsolete R05 graph was not reused as current evidence.
- Regenerated private evidence includes a 51-component CycloneDX SBOM
  (`902088a0e70d3ce005885c01f7ee472fba19458ae803e09700df52949d152dda`) and a
  38-repository/124-license-file inventory
  (`e1e77546b0a2a8148cc2f6ef6b3dc700305edad16311b09d9a836caa3c2742d3`).
- Offline Grype reports zero direct source-closure matches. Focused OpenCV CPE findings remain visible:
  the core persistence issue has the exact backport and no-crash negative controls; affected
  objdetect/HOG, video/DIS and imgcodecs/JPEG modules and symbols are absent.
- The model bundle is approved only for the already-authorized private synthetic PoC. Incomplete
  training-data/redistribution provenance keeps distribution and production blocked.

`P2_M3_V03_STAGE_B: PASS_FOR_ISOLATED_STAGE_C`

`P2_M3_V03_STAGE_C: PENDING`

## P2-M3-R20 data-rights CI time-boundary repair

- Run `32080603204` failed one unrelated Phase 1 data-rights integration assertion because its
  fixed database session expiry (`2026-08-17T23:30:00Z`) had elapsed before CI authentication.
- R20 derives only the fixture session expiry from the live test clock. Product authentication and
  deletion-status authorization remain unchanged and fail closed for expired sessions.
- Fresh PostgreSQL at `0011_offline_synth_source`: exact test 5/5 PASS; complete API suite PASS.
- Same-SHA GitHub Actions run `32081539232` passed `quality-and-integration`, `secret-scan` and
  `docker-validation`. R20 is accepted, but this does not advance Stage C, V02, T07, T08 or the M3
  Gate.

`P2_M3_R20_LOCAL: PASS`

`P2_M3_R20_REMOTE_CI: PASS`

## P2-M3-R21 Windows Stage C image ABI retention

- Fresh R19 Windows roots `bw30` and `bw31` both completed 4,549 actions, but neither DLL exported
  `MpImageCreateFromUint8Data` or `MpImageFree`. The preregistered Windows Stage C lifecycle therefore
  cannot run and remains fail closed.
- R21 adds only `/INCLUDE:MpImageCreateFromUint8Data` and `/INCLUDE:MpImageFree` to the existing
  Windows linker options. Linux options, algorithms, model inputs, dependency versions and product
  contracts are unchanged.
- Acceptance requires two new clean roots with byte-identical main/core/imgproc outputs, the required
  exports, bounded imports, no private/PDB/Ooura/Clearcut/CA/network surface, and three successful
  zero-egress synthetic runs.

Fresh roots `bw34` and `bw35` each completed 4,549 actions. Main/core/imgproc pairs are byte-identical
with SHA-256 values
`5a904100bf197e8b4755f503aa4d1d8a8892107a9940e2f848eeb302ff24dd8d`,
`353c960dbc233d6d412dc1015b702321f3a7f8a80494a7142c7e9c3670d61f68` and
`1aa54040e263be7685f2b8a379cf1f34a275b0718cc8b3a823a1f935c28592b4`. The main DLL exposes the
required Face Landmarker and image lifecycle functions. All three DLLs have zero private-path,
PDB/RSDS, Ooura, Clearcut, certifi/CA-bundle, fixed telemetry endpoint and Windows network-API
matches.

Windows Stage C ran the fixed model and synthetic RGB input three times under a process-specific
outbound block with Filtering Platform failure capture. Every run returned exit code zero,
`detect_status=ok`, `face_count=1` and `close_status=ok`; outbound block event count was zero. The
temporary firewall rule was removed and audit policy restored. Linux had already produced the same
three successful lifecycle runs under `--network none` with zero network calls.

`P2_M3_R21_STATUS: PASS`

`P2_M3_V03_STAGE_C: PASS_PRIVATE_SYNTHETIC_ONLY`

This acceptance opens Stage D V02 calibration/holdout only. T07, T08, M3 PASS/FROZEN, production
Vision, distribution and real-user processing remain closed.

## V03 Stage D holdout and PostgreSQL authority

- The frozen policy commit `f7b76b2` passed same-SHA run `32091490211` before holdout execution.
- Four private holdout assets completed 80 source-built Face Landmarker runs across Windows and
  Linux. All frozen automatic thresholds and five policy reviews passed; no holdout threshold,
  runtime, model or input changed after freeze.
- R22 corrected the policy digest envelope before any database row was admitted. Its same-SHA run
  `32092697747` passed all three jobs.
- The isolated PostgreSQL research authority now contains one approved policy, four passed QA runs,
  36 measurements, 24 reviews and four canonical identities. Four calibration records remain
  `NORMALIZED`.
- R23 restored trigger-owned `NORMALIZED → QA_PENDING` ordering. R24 appends both the frozen policy's
  `license_scope` and the existing database invariant's `license_rights` decision for the same
  private-research-only rights conclusion. No row was deleted/reset and no terminal evidence was
  rewritten.
- A second execution produced the same policy/run/record/identity bindings, zero new identities and
  zero additional rows. The allowlisted evidence digest is
  `69dc51045487ba65299785e4a1ee7780f8ae00c08684a033596f6ec7bd7b79e6`.

`P2_M3_V03_STAGE_D_HOLDOUT: PASS_PRIVATE_SYNTHETIC_ONLY`

`P2_M3_V03_POSTGRESQL_AUTHORITY: PASS`

`P2_M3_R23_STATUS: PASS`

`P2_M3_R24_STATUS: PASS`

## T07 machine-readable evidence checkpoint

- `mirror.p2-m3.ci-evidence/v1` validates the single migration head, committed OpenAPI digest,
  zero-skip M3 JUnit results and the two digest-bound redacted V03 documents.
- It keeps the official MediaPipe wheels rejected, the model private-research-only, and distribution,
  production Vision, real-user facial processing and QuestionBank release false.
- Docker/Linux targeted validation passed 41 tests with zero skip, covering real PostgreSQL,
  normalization, storage tamper, hard-gate evaluation, zero-network Mock Vision, identity
  concurrency, reference-only Worker messages and reconciliation. A first local attempt on shared
  Redis DB 0 was retained as failed environment evidence after an existing worker consumed the
  message with a different task registry; isolated task-owned Redis DB 15 passed the exact test and
  the complete suite without restarting existing services.
- The full Docker/Linux regression passed 401 API/Worker tests with zero skip after mounting a
  task-owned shared raw-storage directory for the isolated Redis DB 14 Worker. Fresh migration,
  downgrade/re-upgrade and `alembic check`, Ruff, strict mypy, `pnpm check`, Compose validation and
  API/Worker/Web image builds all passed. The shared-container mount is only local topology evidence;
  it does not alter application storage configuration.

`P2_M3_T07_TARGETED_LOCAL: PASS`

`P2_M3_T07_FULL_LOCAL: PASS`

`P2_M3_T07_SAME_SHA_CI: PENDING`

## P2-M3-R25 portable Windows toolchain path closure

The committed Windows reproduction patch no longer contains a private absolute `nmake.exe` path.
It requires the exact checksum-locked tool through `MIRROR_NMAKE_EXE`; the patch SHA-256 is
`02264c696b85af0637724afc880604c6a3e8bee846d298d39595c2ec0a410cb3`. Exact-preimage replay and
reverse replay passed, while a fresh missing-variable negative control failed closed before OpenCV
configuration and did not fall back to PATH.

Fresh Windows roots `bw37`/`bw38` each completed 4,549 actions. Their byte-identical
main/core/imgproc SHA-256 values are
`1c67ae02b90a5b00b58018c3c04db411134d781c6f53b195e68a6ce6136615ef`,
`e0415de8bd7dd97f1c2bcccfba627fe6efe4da9441c9b4c9772f3f4faa8f4343` and
`1aa54040e263be7685f2b8a379cf1f34a275b0718cc8b3a823a1f935c28592b4`. All prior private-path,
debug-record, Ooura, telemetry/CA and network-import scans passed. Windows Stage C again completed
three one-face runs with zero outbound events.

Two fresh Linux output volumes each completed 4,597 actions under `--network none`; their three
artifact pairs are byte-identical at
`6a5fb35175efc2f014fb61f7f4abb2c78c38156bd6abf2186d1549cbf3f006a7`,
`116c2db3b7e149390631af309f910eabeb73bd18281e4174f131ced2a8de4408` and
`765ebf6c659e523d9d7e9557e63f004a041a9327fcba95e6d4ac0670485241f5`. Fresh R25 Stage C counts
are three successful runs, three successful detects, three one-face results, three clean closes and
zero intercepted network calls.

The effective 4,737-file build-input manifest SHA-256 is
`5c4f74bc4dd661582d397e5d1c66d22548d103e70d75cd7a2062cc6f0958a224`. Only the tool-path
injection expression changes relative to the R17 source volume, so the 51-component SBOM,
38-repository/124-file license inventory and existing vulnerability dispositions remain valid.
R17's historical `19e90273...` main-library hash is retained as checkpoint history;
`6a5fb351...` is the later R19/R21/current qualified Linux runtime reproduced by R25.

`P2_M3_R25_LOCAL_REPRODUCTION: PASS`

`P2_M3_R25_SAME_SHA_CI: PENDING`

R25 does not mutate the frozen Stage D policy/evidence and does not advance the M3 Gate. T08 and a
new same-SHA three-job CI run remain mandatory.
