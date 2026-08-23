# CC-P2-M5-04-B-E01 Fresh Calibration Execution Contract

## Status and authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: CC-P2-M5-04-B-E01`
- `TASK_NAME: Fresh Calibration Execution Contract`
- `BASELINE_SHA: fe1d66cb14446b0eabdf19d7a5afc7923c17ea43`
- `BASELINE_CI_RUN: 32627791730`
- `E01_CANDIDATE: THIS_COMMIT`
- `AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ARTIFACT_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`
- `PRE_CONDITION_CURRENT_STATE: CC04_B_E01=CONTRACT_CANDIDATE_PENDING_ACCEPTANCE;CC04_B_EXECUTION=CLOSED`

This candidate writes and accepts the execution contract only. It does not create or resolve a private registry, root,
locator, receipt, GenerationSpecification, Prompt, assignment ledger, request queue, counter, output, Asset, identity,
cohort, or holdout. It invokes no generation, Vision, measurement, transform, Provider, or private-input operation and
consumes zero requests, outputs, storage, Vision operations, transform operations, or cash.

## Bounded-task packet

- `OBJECTIVE`: after this exact contract is independently accepted, create one Principal-custodied private calibration
  capability and execute at most 32 serial Codex-native requests targeting exactly 24 independent cluster-adjusted
  QA-passed identities under the accepted T01, L01, repaired S01, P01, repaired Q01, O01, R16, and V01 authorities.
- `WHY_RETAINED_BY_PRINCIPAL`: Prompt custody, private capability creation, native generation calls, adult hard-fail,
  resource counters, runtime qualification, identity admission, and stop decisions are Principal security, privacy,
  license, and research-integrity authority.
- `SCOPE`: future 04-B private synthetic calibration acquisition and admission only. Contract writing changes only this
  document and the canonical/mirror true-EOF status tails.
- `EXPECTED_CHANGE`: an independently accepted execution contract. No runtime, model, dependency, code, schema,
  migration, API, Worker, workflow, data, private capability, or generated output is created by this candidate.
- `ALLOWED_FILES_OR_MODULES`: this contract, `docs/operations/P2_M5_ACCEPTANCE.md`, and
  `docs/operations/P2_M5_EXECUTION_PROTOCOL.md`.
- `FORBIDDEN_SCOPE`: a fourth changed path; generation before acceptance; private discovery; holdout; transform;
  04-C formula, tolerance, threshold, calibration, or diagnostic work; 04-D/04-E; MVR; M6; production; real-user
  processing; QuestionBank release; P2-M7; shared-summary sync; dependency/model/runtime adoption; or authority change.
- `DEPENDENCIES`: accepted T01 `827224a3` / run `32623064656`; L01 `885a6b24` / run `32623973304`; repaired S01/R15
  `126f96e2` / run `32624905183`; P01 `df50b479` / run `32625275234`; repaired Q01/R16 `c3faa387` / run
  `32626449663`; O01 `540dd23f` / run `32626876718`; V01 `fe1d66cb` / run `32627791730`; ADR-026, ADR-030,
  ADR-041, ADR-049, ADR-050, and the accepted fresh-evidence protocols.
- `INPUTS_AND_ASSUMPTIONS`: no private input is available or needed for contract writing. After acceptance the Principal
  must resolve only exact accepted task-scoped capabilities; unknown Provider fields remain `UNKNOWN_OR_NULL`.

## Inherited Owner envelope

- `SOURCE_KIND: CODEX_NATIVE_IMAGEGEN`
- `SOURCE_SCOPE: PRIVATE_INTERNAL_RESEARCH_ONLY`
- `PROVENANCE_LEVEL: PROVENANCE_ONLY`
- `COST_ACCOUNTING_MODE: REQUEST_COUNT_ONLY`
- `EXTERNAL_CASH_BUDGET: 0`
- `PAID_EXTERNAL_PROVIDER_ALLOWED: false`
- `PRODUCTION_PROVIDER_APPROVAL: NOT_GRANTED`
- `PRODUCTION_GENERATION_STATUS: FAIL_CLOSED`
- `CALIBRATION_REQUEST_CALL_MAX: 32`
- `CALIBRATION_RAW_OUTPUT_MAX: 32`
- `CALIBRATION_ADMITTED_IDENTITY_TARGET: 24 independent cluster-adjusted identities`
- `REQUESTED_OUTPUTS_PER_CALL: 1`
- `GENERATION_CONCURRENCY: 1`
- `AUTOMATIC_RETRY_CEILING: 0`
- `TRANCHE_MAXIMUM_CALLS: 4`
- `SEALED_HOLDOUT_REQUEST_OR_OUTPUT_USE: 0`
- `TOTAL_NATIVE_GENERATED_OUTPUT_MAX: 64`
- `TRANSFORM_OPERATION_ALLOWED_IN_04_B: 0`
- `VISION_OR_MEASUREMENT_GLOBAL_HARD_CEILING: 2500`
- `NEW_PRIVATE_OUTPUT_STORAGE_GLOBAL_HARD_CEILING: 8 GiB`
- `N_48_OR_N_96_EXPANSION: NOT_AUTHORIZED`

## Exact post-acceptance creation sequence

Only after every E01 acceptance Gate passes, the Principal must perform these operations serially and stop on any
uncertainty:

1. Resolve the exact accepted task receipt without parent enumeration, globbing, disk search, sibling lookup, or legacy
   registry reuse.
2. Create exactly one Git-external, task-scoped calibration root and one `PRINCIPAL_PRIVATE_OUTPUT_REGISTRY` authority;
   reject a pre-existing, reparse, escaped, shared, P2-M7, or second root.
3. Register the root through one opaque recoverable locator before use. Never print or disclose its locator or path.
4. Materialize one canonical private GenerationSpecification and Prompt template, compute their SHA-256 digests, and
   bind them to this E01, the accepted V01 manifest, and all 32 immutable request assignments before any call.
5. Materialize append-only request, output, storage, Vision/measurement, rejection, admission, cluster, coverage, and
   cleanup ledgers with a genesis digest. Initial counts are all zero.
6. Verify runtime/model availability only through the exact accepted P01 capability. Missing, lost, mismatched, or
   unresolved bytes stop; no download, installation, reconstruction, broad search, fallback, or substitution is allowed.
7. Execute at most four never-used ordinals in tranche 1. Reconcile every ledger and Gate before any later tranche.

Root, registry, specification, assignment, and ledger creation are execution operations, not contract-writing
operations. If creation cannot complete before the first call, the result is `BLOCKED_SECURITY_PRIVACY_LICENSE` with
zero generation calls.

## Canonical private GenerationSpecification

- `GENERATION_SPECIFICATION_VERSION: p2-m5-cc04-b-calibration-generation-v1`
- `GENERATION_SPECIFICATION_SCOPE: FRESH_PRIVATE_SYNTHETIC_CALIBRATION_ONLY`
- `PROMPT_TEMPLATE_VERSION: p2-m5-cc04-b-calibration-prompt-v1`
- `GENERATION_SPECIFICATION_DIGEST: COMPUTE_ONCE_PRIVATE_BEFORE_FIRST_CALL`
- `PROMPT_TEMPLATE_DIGEST: COMPUTE_ONCE_PRIVATE_BEFORE_FIRST_CALL`
- `REQUESTED_IMAGE_COUNT: 1`
- `REQUESTED_IMAGE_SIZE: 1024x1024`
- `RETURNED_IMAGE_MAXIMUM_DIMENSION: 2048`
- `RETURNED_IMAGE_MAXIMUM_BYTES: 16 MiB`

The private specification must declare a synthetic adult age 18+, female-oriented, East-Asian-presenting first-coverage
context; exactly one face; nonsexual presentation; frontal or bounded pose; soft even lighting; plain neutral
background; neutral or mild relaxed closed-mouth expression; no text or watermark; and the ordinal's one morphology
and one approved style assignment. It must require distinct identity, continuous morphology diversity,
anti-homogenization, and no hidden standard face.

It must prohibit a real person, User Asset, celebrity, influencer, scraped image, named identity, one-to-one likeness,
child or student-minor context, sexualization, age estimation, sensitive trait, race/ethnicity/ancestry/nationality
classification, beauty or attractiveness score, and legacy identity or Asset reuse. Prompt plaintext and Provider
payloads remain private and never enter Git, logs, CI, artifacts, MEMORY, reviewer packets, or status text.

Unknown model ID, snapshot, seed, Provider request ID, usage, monetary cost, and complete Provider provenance remain
`UNKNOWN_OR_NULL`. The known request ordinal, timestamps, output cardinality, source kind, specification/template IDs
and digests, and request/output counts are recorded without inventing missing Provider facts.

## Immutable 32-ordinal assignment manifest

- `ASSIGNMENT_MANIFEST_VERSION: p2-m5-cc04-b-calibration-assignment-v1`
- `ASSIGNMENT_MANIFEST_DIGEST: COMPUTE_ONCE_FROM_THIS_EXACT_TABLE_AND_PRIVATE_SPEC_BINDING_BEFORE_FIRST_CALL`

Morphology codes are `UL`/`UH` for upper-face lower/upper, `ML`/`MH` for midface lower/upper, and `LL`/`LH` for
lower-face lower/upper. Style codes are `PCN`, `GSA`, `RE`, `SU`, `GS`, and `IELM` in the Q01-approved order. The
immutable pairings are:

| Ordinal | Morphology | Style | Ordinal | Morphology | Style |
| ------: | ---------- | ----- | ------: | ---------- | ----- |
|     001 | UL         | PCN   |     017 | LL         | PCN   |
|     002 | UH         | GSA   |     018 | LH         | GSA   |
|     003 | ML         | RE    |     019 | UL         | SU    |
|     004 | MH         | SU    |     020 | UH         | GS    |
|     005 | LL         | GS    |     021 | ML         | IELM  |
|     006 | LH         | IELM  |     022 | MH         | PCN   |
|     007 | UL         | GSA   |     023 | LL         | GSA   |
|     008 | UH         | RE    |     024 | LH         | RE    |
|     009 | ML         | SU    |     025 | UL         | GS    |
|     010 | MH         | GS    |     026 | UH         | IELM  |
|     011 | LL         | IELM  |     027 | ML         | PCN   |
|     012 | LH         | PCN   |     028 | MH         | GSA   |
|     013 | UL         | RE    |     029 | LL         | RE    |
|     014 | UH         | SU    |     030 | LH         | SU    |
|     015 | ML         | GS    |     031 | UL         | IELM  |
|     016 | MH         | IELM  |     032 | UH         | PCN   |

The first 24 ordinals contain four assignments for every morphology and style cell. Across all 32, `UL`, `UH`, `PCN`,
and `IELM` have six assignments and every other cell has five. This balancing is fixed before output and gives no
permission to relabel, reorder, skip ahead, choose by appearance, issue replacements, or relax the three-to-six
cluster-adjusted admission requirement. Returned content inherits its ordinal assignment even when rejected.

## Exact runtime, policy, and morphology binding

- `V01_MANIFEST_VERSION: p2-m5-cc04-b-v01-admission-runtime-v1`
- `V01_MANIFEST_SHA256: a1d3698564c8ca0d0b6f01fa28b580d85135ccc8c502616527a140d80ba41cb3`
- `QA_POLICY_VERSION: p2-m3-v03-source-built-vision-qa-v1`
- `QA_POLICY_CONTENT_DIGEST: 8305cfaa25d084138fb67e93043a1e37842543a645085d19d3ef52ac8a6ce15f`
- `QA_ADMISSION_OVERLAY_VERSION: p2-m5-cc04-b-calibration-qa-admission-v1`
- `MORPHOLOGY_MANIFEST_VERSION: p2-m5-cc04-b-morphology-admission-v1`
- `MORPHOLOGY_MANIFEST_SHA256: a1d3698564c8ca0d0b6f01fa28b580d85135ccc8c502616527a140d80ba41cb3`
- `DUPLICATE_SIGNATURE_VERSION: phash-dct-nearest-v1`

E01 must verify the exact source-built runtime, model, policy, supported platform, zero-egress, formula, normalizer,
bounds, equality, repeat, and failure values from V01 before the first call and before each tranche. Only the descriptor
for the ordinal's preassigned region determines its primary morphology cell; all three continuous descriptors remain
preserved. Human morphology assignment, repair, override, inference, or relabeling is prohibited.

## Exact private-storage reservation

- `PER_OUTPUT_CUMULATIVE_PRIVATE_RESERVATION: 128 MiB`
- `PER_CALL_TRANSIENT_PRIVATE_RESERVATION: 128 MiB`
- `PER_CALL_WORST_CASE_PEAK_INCREMENT: 256 MiB`
- `FULL_32_OUTPUT_CUMULATIVE_RESERVATION: 4096 MiB`
- `FULL_32_OUTPUT_WORST_CASE_PEAK_LIVE: 4224 MiB`
- `GLOBAL_PRIVATE_STORAGE_CEILING: 8192 MiB`

The per-output reservation covers the returned encoded bytes, immutable raw object, canonical normalized object,
bounded platform working derivatives, digest/signature material, and custody metadata. The transient reservation covers
bounded response encoding, decode, sanitizer, second-decode, and platform work copies for one active call. Actual
cumulative and peak-live bytes are recorded separately. Deletion may reduce live bytes only after exact cleanup
verification and never reduces cumulative accounting or output facts.

A call cannot start unless both its 128-MiB cumulative output reservation and 128-MiB transient reservation fit. An
output above 16 MiB, a dimension above 2048, unknown size, unregistered bytes, projection above either exact reservation,
or any cumulative/peak projection at or above 8192 MiB hard-stops. No compression, deletion, missing output, rejected
output, or cleanup refunds quota or creates extra storage authority.

## Exact Vision and measurement reservation

For each returned output, reserve exactly:

- 10 accepted-runtime reliability runs on Linux and 10 on Windows: 20 operations;
- one deterministic three-descriptor morphology vector: 1 operation;
- one bounded pHash signature: 1 operation;
- one categorical adult/safety/style/background/expression/visibility review: 1 operation;
- one Hamming candidate-pair comparison against each prior returned output: ordinal minus one operations, at most 31.

The maximum for ordinal 032 is 54 operations. Across 32 outputs the exact maximum is `32 * 23 + 496 = 1232` Vision
or measurement operations. The counter increments before each operation; failed or missing results count. No extra run,
retry, alternate platform, pair comparison, hidden review, or transform is allowed. The 04-B transform count remains
zero, and the 768 transform ceiling cannot substitute for Vision budget.

## Request, output, and tranche transaction

Ordinals execute from `CAL-REQ-001` upward in at most eight tranches of at most four calls. Before each dispatch the
Principal verifies: all accepted authorities and digests; root/registry recoverability; zero active calls; exact next
unused ordinal; counter reconciliation; remaining request/output/storage/Vision capacity; no target or hard stop; and no
holdout, downstream, paid, or external-provider state.

The append-only request-attempt entry is durably prepared before dispatch. Dispatch increments `request_call_count` and
`requested_output_count` exactly once. A timeout, transport, tool, policy, operator, zero-output, or unknown failure is
final for that ordinal. There is no automatic or manual retry, same/changed-Prompt replay, SDK retry, alternative tab,
sibling Agent, background call, scheduled call, or disguised replacement. The next never-used ordinal may run only if no
hard stop applies.

Every returned output increments `returned_output_count` and `raw_output_count` before inspection. Unexpected zero or
multiple output cardinality is an execution failure and hard stop; every actual returned output still counts. Exact
returned bytes must be registered, hashed, typed, sized, and bound to source/specification/assignment evidence before
decode or admission use. Raw output is always untrusted.

After at most four calls, the tranche stops. A later tranche requires a Principal checkpoint over every request, output,
failure, rejection, storage, Vision, custody, duplicate cluster, effective N, and morphology/style occupancy fact.

## Hard QA and atomic admission

Apply the Q01 order without substitution: custody and source binding; bounded MIME/magic/single-frame decode and
sanitizing normalization; exact V01 face/landmark/pose/reliability checks; repaired S01 adult, nonsexual, likeness,
sensitive-inference, and beauty-score controls; allowed categorical presentation review; raw and normalized SHA-256
duplicate checks; pHash candidate review and append-only cluster decision; fresh/legacy/holdout split exclusion;
deterministic morphology assignment; coverage; then atomic PostgreSQL Asset, QA-passed record, and one fresh opaque
SyntheticIdentity creation.

A human cannot override an automatic hard fail, assign or repair morphology, erase a duplicate, bypass adult/safety,
or choose by downstream performance. pHash cannot automatically reject before the later 04-C threshold freeze; it only
orders human same-identity review. A confirmed cluster contributes at most one effective identity. Rejection and
execution failure remain distinct, append-only, and non-refundable.

## Stop conditions and legal results

Stop immediately on any unaccepted authority; receipt/root/locator/runtime/model/specification/assignment/digest/policy/
platform/counter mismatch; hidden network or telemetry; private-field leakage; unexpected cardinality; storage or
Vision uncertainty/overflow; hard adult/safety/decode/reliability failure; second root; retry; transform; holdout access;
legacy reuse; downstream selection; paid/external Provider; or 04-C through 04-E, MVR, M6, production, real-user, or
P2-M7 bypass.

`CALIBRATION_COHORT_READY` requires exactly 24 effective cluster-adjusted admitted identities, every morphology and
style cell at three-to-six, all Gates passing, and all counters reconciled. Stop after the completing action; do not use
another ordinal. `FURTHER_RESEARCH_RESOURCE_ENVELOPE_EXHAUSTED` is mandatory when 32 requests or 32 raw outputs are
exhausted first, or remaining legal ordinals cannot satisfy target and occupancy.

The only 04-B execution dispositions are:

- `CALIBRATION_COHORT_READY`
- `FURTHER_RESEARCH_RESOURCE_ENVELOPE_EXHAUSTED`
- `BLOCKED_SECURITY_PRIVACY_LICENSE`
- `FAILED`

None authorizes a 33rd request, retry, quota transfer, 48/96 expansion, threshold change, holdout, transform, MVR, M6,
production, real-user processing, or QuestionBank release.

## Retention, cleanup, and tracked evidence

Retention is only `AUTHORIZED_P2_M5_CALIBRATION_RESEARCH_AND_AUDIT_ONLY`, ending at M5 research stop or closure after
required audit and cleanup evidence. Security, privacy, license, scope, or integrity failure triggers bounded early
cleanup unless an explicit active evidence hold applies. Cleanup uses only exact registered output IDs and locator
capabilities, verifies absence through the same capability, and preserves all count/digest/rejection/audit facts.

Tracked evidence may contain only opaque output IDs, content digests, byte counts, versions, assignments, counters,
allowlisted status/reason, cluster facts, retention class, and cleanup status. It must contain no private locator, path,
directory, object key, URL, signed URL, credential, secret, Prompt, Provider payload, image bytes, encoded image, free-text
facial judgment, or private registry/root identifier.

## Acceptance criteria and validation

1. Exact parent `fe1d66c`, three text paths, no fourth path, and no generation/private mutation.
2. All accepted review/runtime authorities and exact digests are preserved; E01 adds no dependency, model, runtime,
   Provider, budget, retry, concurrency, quota transfer, holdout, transform, or downstream authority.
3. All 32 ordinals are unique and balanced exactly as stated; first 24 have four assignments per cell; total counts are
   six/six/five/five/five/five for each dimension family.
4. Storage arithmetic is exact: 4096 MiB cumulative and 4224 MiB peak-live below 8192 MiB.
5. Vision arithmetic is exact: 1232 maximum below 2500; transform operations are zero.
6. Request/output accounting, tranche checkpoints, custody, Prompt redaction, hard QA, no-human-override, atomic
   admission, target/exhaustion, legal results, cleanup, and all downstream stops are explicit.
7. Scoped Prettier, `git diff --check`, allowlist, marker, arithmetic, ordinal, prohibition, leakage, binary, true-EOF,
   sentinel, last-occurrence, and canonical/mirror checks pass; then exact-SHA CI, eight artifacts, independent
   Security/Privacy/License/Research Integrity, independent Sol High, and Principal acceptance pass.

## Rollback and exact sequencing

Reject this candidate before acceptance with no execution-side effect. Repair an accepted defect only with a new normal
forward commit; never amend, reset, rebase, force-push, rewrite history, or create a post-acceptance status commit.

After acceptance, execute only the post-acceptance creation sequence and tranche 1 under Principal custody. Do not
delegate generation or private discovery. Do not create or access holdout, run transforms, calibrate thresholds, open
04-C, evaluate MVR, or enter M6. Complete and independently accept the whole 04-B execution disposition before any next
Wave.
