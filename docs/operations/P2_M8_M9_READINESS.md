# P2-M8 / P2-M9 Pre-Entry Readiness Matrix

## Status and authority

- `TASK_ID: P2-CROSS-MILESTONE-READINESS-01`
- `DOCUMENT_KIND: READINESS_MATRIX_ONLY`
- `BASELINE_COMMIT: 04b0b21fedf2a7897f77b0eef8357b00371b599f`
- `BASELINE_CI_RUN: 32644954065`
- `BASELINE_MIGRATION_HEAD: 0014_m5_eval_authority`
- `P2_M8_STATE: COMMITTED`
- `P2_M8_ENTRY: CLOSED_PENDING_P2_M5_AND_P2_M6_FROZEN`
- `P2_M9_STATE: COMMITTED`
- `P2_M9_ENTRY: CLOSED_PENDING_P2_M1_THROUGH_P2_M8_GATES`
- `READINESS_MATRIX_RESULT: WAITING_FOR_P2_M5_AND_P2_M6_FROZEN`

This document maps the accepted Project Mirror Phase 2 master-plan requirements to
tracked repository evidence and explicit gaps. It is not an execution protocol,
acceptance record, change control, Milestone Gate, or permission to start P2-M8 or
P2-M9 implementation.

The repository remains authoritative. Dynamic P2-M5 and P2-M6 facts recorded here
are only a baseline snapshot and must be replaced by their later frozen authorities
before P2-M8 refinement.

## Readiness task candidate evidence

The bounded readiness matrix candidate was independently exercised without opening
either downstream Milestone:

- `READINESS_CANDIDATE_COMMIT: 21d2896816c0ac02f46c126a40a5b84dd5b98c60`
- `READINESS_CANDIDATE_CI_RUN: 32647106032`
- `READINESS_CANDIDATE_CI_ATTEMPT: 1`
- `READINESS_CANDIDATE_VERIFICATION: PASS`
- `READINESS_CANDIDATE_ARTIFACT_COUNT: 8`
- `READINESS_CANDIDATE_ARTIFACT_MEMBER_MANIFEST_SHA256: f55ab548b41e76ffa471925738001e688c0f672652a883c2011e6d794d30d3a3`
- `READINESS_CANDIDATE_MIGRATION_HEAD: 0014_m5_eval_authority`
- `READINESS_CANDIDATE_OPENAPI_SHA256: a9ee1e0ad3b942e5be5790b4fc7ff8c0deab744a84d3383a7a8856a8f97b4841`

The exact-SHA run completed `quality-and-integration`, `secret-scan`, and
`docker-validation` successfully. Inspection covered all eight non-expired
artifacts: project audit, P2-M3, P2-M2, P2-M1, Phase 1, Playwright, Docker, and
Gitleaks. Structured evidence was bound to the candidate SHA and the migration
head above. The run reported 814 Python tests passed with one pre-existing optional
M4 private-runtime skip, 54 Node tests passed, five browser tests passed, five
Docker services running and healthy, and six Celery tasks received and succeeded.
Ruff, mypy, contract drift, build, PostgreSQL migration lifecycle, Python and Node
dependency audits, and the three mandatory jobs completed successfully.

Artifact inspection found no Gitleaks results, image bytes, credential assignment,
private path, signed URL, Prompt/object-key/provider-raw field, path escape, or
reparse-point evidence. Playwright 1.62.1 installed system dependencies and Chromium
on their first bounded attempts. The Gitleaks artifact recorded version 8.24.3,
one scanned commit, and zero leaks. CycloneDX 1.6 evidence contained 105 components.

This is acceptance evidence for the docs-only readiness task, not acceptance or
entry authority for P2-M8, P2-M9, or Phase 2. The closure commit that records this
evidence requires its own exact-SHA CI verification; that verification does not
change the dependency states in this document.

## Purpose and boundary

The immediate purpose is to preserve useful cross-Milestone planning work while an
independent line completes P2-M5 and P2-M6. This matrix may identify evidence that
can later be reused, but it cannot:

- modify P2-M5 or P2-M6 policy, threshold, schema, evidence, acceptance, or state;
- preselect a P2-M5 technical or P2-MVR result;
- define the future P2-M6 manifest, release, or revocation contract;
- introduce a migration, public or internal API, dependency, model artifact, image,
  storage authority, CI workflow, or production capability;
- treat the accepted M5/M7 integration checkpoint as an M5, M6, M8, M9, or Phase 2
  Gate; or
- authorize real-user facial processing, runtime image generation, production
  deployment, or public QuestionBank use.

## Repository baseline

The baseline is the accepted M5/M7 controlled integration final state. GitHub Actions
run `32644954065` completed `quality-and-integration`, `secret-scan`, and
`docker-validation` successfully on the exact baseline commit, with eight inspected
artifacts. That evidence proves the combined baseline described by
`P2_M5_M7_INTEGRATION_CHECKPOINT.md`; it does not close the dependencies below.

| Milestone | Baseline state | Reusable tracked authority                              | Readiness effect                                                                                 |
| --------- | -------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| P2-M1     | `FROZEN`       | `P2_M1_ACCEPTANCE.md` and frozen CI evidence            | Policy, ontology, typed provider, and synthetic-only boundaries are available.                   |
| P2-M2     | `FROZEN`       | `P2_M2_ACCEPTANCE.md` and frozen CI evidence            | Generation batch, raw-source, budget, retry, and provenance foundations are available.           |
| P2-M3     | `FROZEN`       | `P2_M3_ACCEPTANCE.md` and frozen CI evidence            | Normalization, QA, canonical measurement, and bank-independent identity authority are available. |
| P2-M4     | `FROZEN`       | `P2_M4_ACCEPTANCE.md` and frozen evaluation evidence    | Deterministic variant lineage and bounded cross-platform research evidence are available.        |
| P2-M5     | `EXECUTING`    | `P2_M5_EXECUTION_PROTOCOL.md` and `P2_M5_ACCEPTANCE.md` | Isolation, duplicate, diversity, coverage, technical Gate, and MVR authority are not frozen.     |
| P2-M6     | `COMMITTED`    | Milestone definition only                               | Manifest release/revoke authority is not implemented or frozen.                                  |
| P2-M7     | `FROZEN`       | `P2_M7_ACCEPTANCE.md` and final-state CI evidence       | Internal operations, cost, observability, recovery, and redaction boundaries are available.      |
| P2-M8     | `COMMITTED`    | Master-plan objective only                              | Refinement remains dependency-gated.                                                             |
| P2-M9     | `COMMITTED`    | Master-plan objective only                              | Refinement remains dependency-gated.                                                             |

At this baseline, P2-M5 still records `P2_MVR_V1_RESULT: NOT_EVALUATED`.
P2-M6 entry remains closed pending the P2-M5 technical Gate and P2-MVR decision.
Those facts must not be inferred from later branch names, untracked outputs, or
partial work in another task.

## P2-M8 requirement-to-evidence matrix

Readiness statuses in this table have deliberately narrow meanings:

- `AVAILABLE_BASELINE`: accepted upstream evidence exists, but still requires M8
  binding and replay;
- `PARTIAL_WAITING`: some accepted evidence exists, while mandatory downstream
  evidence is missing;
- `WAITING_FOR_FROZEN_AUTHORITY`: the required source Milestone has not frozen;
- `NOT_VERIFIED`: no evidence has been accepted for the requirement.

| Master-plan requirement                               | Current tracked evidence                                                                                            | Missing evidence required by P2-M8                                                                                                                                             | Status                         |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------ |
| Generation to normalization continuity                | M2 generation/raw provenance and M3 normalization authorities are independently frozen.                             | One exact, reference-bound replay must prove raw source, normalization, checksums, and immutable evidence continuity without private data leakage.                             | `AVAILABLE_BASELINE`           |
| Normalization to QA and identity continuity           | M3 freezes deterministic normalization, QA evidence, and bank-independent canonical identity registration.          | M8 must bind the selected golden source and all policy, algorithm, measurement, review, and identity references in one replayable manifest.                                    | `AVAILABLE_BASELINE`           |
| Identity to deterministic variant continuity          | M4 freezes source-relative variant specification, transform lineage, result QA, and bounded deterministic evidence. | The future golden chain must bind only M5-qualified dimensions and the final accepted transform/QA versions.                                                                   | `PARTIAL_WAITING`              |
| Variable isolation, duplicate, and diversity evidence | M5 domain/schema foundations exist.                                                                                 | P2-M5 technical Gate, P2-MVR result, accepted thresholds, holdout evidence, coverage, failure interpretation, and frozen authority are all required.                           | `WAITING_FOR_FROZEN_AUTHORITY` |
| Immutable release and revocation                      | Phase 0 skeleton entities exist, but they are not P2-M6 release authority.                                          | Immutable manifest membership, digest, release transaction, append-only revocation, selection exclusion, and reproducibility evidence must be implemented and frozen by P2-M6. | `WAITING_FOR_FROZEN_AUTHORITY` |
| Full generation-to-release/revoke replay              | Individual M2-M4 layers and M7 operations evidence exist.                                                           | One accepted chain from generation through release and revoke does not yet exist; it cannot be designed around provisional M5/M6 contracts.                                    | `WAITING_FOR_FROZEN_AUTHORITY` |
| Golden fixtures and admission manifest                | M1 contains a bounded non-human numeric fixture manifest; later Milestones retain synthetic evidence.               | A P2-M8 golden manifest, fixture admission rules, exact provenance, checksums, versions, expected outcomes, negative controls, and no-private-byte policy remain undefined.    | `NOT_VERIFIED`                 |
| Reproducibility and artifact re-creation              | M3 and M4 retain bounded reproducibility evidence; current CI replays deterministic tests.                          | M8 must preregister clean-root recreation inputs, commands, expected digests, allowed variance, failure classification, and artifact comparison across the complete chain.     | `PARTIAL_WAITING`              |
| Cross-platform variance                               | M4 has accepted Windows/Linux transform and measurement research evidence.                                          | M8 must define which full-chain layers require bit parity, bounded numeric parity, or platform-specific evidence and test them on the final frozen chain.                      | `PARTIAL_WAITING`              |
| Coverage and failure interpretation                   | M5 research protocols distinguish technical Gate, MVR, missingness, and `FURTHER_RESEARCH`.                         | Final frozen M5 coverage and failure authority is required; M8 must not invent or relax thresholds after seeing results.                                                       | `WAITING_FOR_FROZEN_AUTHORITY` |
| Release/revoke consistency under replay               | No P2-M6 release/revoke implementation is accepted.                                                                 | M8 must verify immutable history, concurrent release/revoke behavior, selection exclusion, manifest reconstruction, and unchanged historical provenance.                       | `WAITING_FOR_FROZEN_AUTHORITY` |
| Integrated cost and operational evidence              | M7 freezes allowlisted operations, cost categories, recovery, audit, and redaction boundaries.                      | M8 must bind actual integrated operations without exposing Prompt, object key, URL, image bytes, Provider payload, credential, or private path.                                | `AVAILABLE_BASELINE`           |

## P2-M9 requirement-to-evidence matrix

P2-M9 cannot refine until every P2-M1 through P2-M8 Milestone Gate has completed
and the required frozen authorities exist.

| Master-plan requirement                    | Entry evidence required                                                                                                                             | Current status                               |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| All P2 Milestones complete                 | P2-M1 through P2-M8 acceptance closure and frozen-state evidence                                                                                    | M1-M4/M7 frozen; M5/M6/M8 incomplete         |
| Cross-Milestone integration                | Accepted integrated descendant containing all frozen Milestone histories without authority loss                                                     | `WAITING_FOR_FROZEN_AUTHORITY`               |
| Full migration lifecycle                   | Final Phase 2 head: fresh upgrade, previous-to-head, downgrade/re-upgrade, `alembic check`, invariants, concurrency, and irreversible-data handling | Final head is unknown until M6/M8 refinement |
| Full regression                            | Python, PostgreSQL, Redis/Celery, TypeScript, Browser, Docker, contracts, and zero mandatory skip at the final candidate                            | `NOT_VERIFIED`                               |
| Security, privacy, data, and license audit | Exact final diff, dependencies, models, fixtures, private-data boundaries, supply-chain evidence, and production fail-closed review                 | `NOT_VERIFIED`                               |
| Exact-SHA remote evidence                  | Three mandatory jobs, readable exact-SHA artifacts, evidence digests, and negative scans                                                            | `NOT_VERIFIED`                               |
| Independent reviews                        | Independent security/privacy/data/license review and Sol High final audit                                                                           | `NOT_VERIFIED`                               |
| Phase closure and freeze                   | Principal acceptance closure CI followed by independent freeze-state CI                                                                             | `NOT_VERIFIED`                               |

## Dependency graph

```text
P2-M1--M4 FROZEN -------------------------------+
P2-M5 technical Gate + P2-MVR decision
  -> P2-M5 acceptance / closure / FROZEN
  -> P2-M6 refinement / implementation / Gate / FROZEN
P2-M7 FROZEN -----------------------------------+
                                                  -> P2-M8 refinement
                                                  -> full-chain golden evaluation
                                                  -> M8 Gate / closure / FROZEN
                                                  -> P2-M9 refinement
                                                  -> Phase-wide audit / closure / FROZEN
```

## Future input slots

These slots are placeholders for later _frozen_ authorities. Their presence is not
evidence that the input exists.

| Input slot           | Required authority                                                                                                        | Current value                  |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| M5 frozen baseline   | Exact freeze commit, CI run, artifacts, technical Gate, MVR result, accepted policy/ontology/threshold/holdout references | `WAITING_FOR_FROZEN_AUTHORITY` |
| M6 frozen baseline   | Exact freeze commit, migration head, CI run, artifacts, manifest/release/revoke contracts and consistency evidence        | `WAITING_FOR_FROZEN_AUTHORITY` |
| M8 planning baseline | Accepted integrated descendant of frozen M5, M6, and M7 histories                                                         | `NOT_AVAILABLE`                |
| M9 planning baseline | P2-M1 through P2-M8 frozen authorities                                                                                    | `NOT_AVAILABLE`                |

## Work that must wait

Until both P2-M5 and P2-M6 are frozen, do not create or modify:

- a P2-M8 execution protocol, acceptance document, task graph, implementation, or
  CI evidence generator;
- a golden image corpus, full-chain manifest, storage object, migration, database
  authority, application service, Worker task, or CLI command;
- M8 cross-platform runner requirements or final numeric tolerances;
- P2-M9 execution or acceptance documents; or
- any Phase 2 PASS, closure, or freeze-state record.

## Entry procedure after dependencies freeze

After P2-M5 and P2-M6 both provide accepted frozen authorities, the Principal must:

1. fetch and verify the exact remote branches, freeze commits, same-SHA runs, and
   required artifacts;
2. construct or identify an accepted integrated descendant that preserves M5, M6,
   and M7 histories;
3. re-read the final migration head, public contract digest, frozen policies,
   manifest/revocation authority, supply-chain decisions, and private-data boundary;
4. run P2-M8 rolling-wave refinement from that actual baseline;
5. preregister fixture provenance, negative controls, deterministic and bounded
   variance rules, failure interpretation, replay/recreation commands, budgets, and
   stop conditions before executing holdout or golden evaluation; and
6. keep P2-M9 closed until P2-M8 has completed its own Gate, closure, and frozen-state
   evidence.

The expected future M8 task shape remains directional only:

```text
M8-T01 refinement and acceptance contract
-> M8-T02 golden manifest and fixture admission
-> M8-T03 deterministic full-chain replay
-> M8-T04 cross-platform recreation and coverage evidence
-> M8-T05 independent evaluation and CI evidence
-> M8-T06 security/final review, closure, and freeze
-> M9 rolling-wave refinement
```

Task identifiers, collision domains, migrations, schemas, thresholds, and file
ownership must be derived from the later repository truth and are intentionally not
frozen by this document.

## Security, privacy, data, and supply-chain notes

- This readiness matrix contains no image bytes, Prompt plaintext, private object
  key, signed URL, Provider payload, credential, private absolute path, real-person
  fixture, model artifact, or user data.
- `synthetic-only`, production fail-closed, no-sensitive-inference, no-beauty-score,
  Identity First, source-relative geometry, immutable provenance, and
  anti-homogenization remain unchanged.
- Existing research approval never becomes production or real-user processing
  approval through inclusion in a golden evaluation.
- Later golden fixtures require exact source, license, synthetic classification,
  checksum, version, admission, retention, and deletion/revocation scope.
- No dependency, model, dataset, Provider, runtime, or license disposition is changed
  by this document.

## Validation contract

This bounded readiness task is acceptable only if:

- the diff contains this new file and no other path;
- `git diff --check` passes;
- repository formatting checks pass for this file;
- no migration, dependency manifest, lockfile, workflow, OpenAPI, generated contract,
  source, test, acceptance authority, or existing Milestone document changes;
- no token claims P2-M8 or P2-M9 is executing, passed, or frozen; and
- the protected primary, M5/M6, and P3-P7 worktrees remain untouched.

## Next bounded action

```text
wait for stable, accepted P2-M5 and P2-M6 frozen authorities
-> refresh repository and remote truth
-> integrate only after collision review
-> perform P2-M8 rolling-wave refinement
```

This is a deliberate dependency wait, not a Phase 2 failure and not permission to
weaken either upstream Gate.
