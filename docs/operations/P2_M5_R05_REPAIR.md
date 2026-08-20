# P2-M5-R05 — CC02-B Builder Contract-Fidelity Repair

## Status

- `BOOTSTRAP_STATUS`: `OK`.
- `TASK_ID`: `P2-M5-R05`.
- `STATUS`: `REPAIR_ACCEPTED_AT_298420F_RUN_32299835326_ATTEMPT_1`.
- Authority: Principal review of the untracked CC02-B builder candidate at repository head `6c6447f`.
- This repair does not change ADR-047, the CC02 manifest schema, accepted evidence, thresholds, algorithms or any later
  Gate.

## Bounded-task contract

- `OBJECTIVE`: remove four implementation acceptance defects and resolve one wording conflict without weakening the
  exact-byte evidence binding, then close the independent reviews' malformed-input, output-containment and cleanup
  findings without pretending that two separate filesystem paths form one operating-system transaction.
- `WHY_DELEGATED`: not delegated; Principal found the defects while reviewing the worker candidate and owns the repair
  decision and integration.
- `SCOPE`:
  - keep production builder entry points fixed to the accepted Windows/Linux report and runtime digests;
  - retain a private synthetic-test seam for placeholder report digests without exposing an authority/root override on
    production entry points;
  - make the human preregistration repeat the complete count/resource summary;
  - require canonical manifest bytes and exact direction-binding ordering;
  - validate manifest collection keys and types before sorting so malformed input always reaches the allowlisted stop;
  - verify the repository root, `docs` and `docs/research` directory identities and reject symlink, junction, reparse or
    observed parent-identity changes before and during publication;
  - stage both complete documents under hidden, non-authoritative same-parent paths before create-once publication;
  - verify cleanup for open, write, `fsync`, close and publication failures, including a close failure before descriptor
    release and persistent staging-unlink failure;
  - clarify exact presented-byte behavior when otherwise equivalent JSON uses different key ordering.
- `ALLOWED_FILES_OR_MODULES`:
  - `scripts/research/build_p2_m5_cc02_manifest.py`;
  - `services/api/tests/test_p2_m5_cc02_manifest.py`;
  - this repair record and forward P2-M5 execution/acceptance/log status records.
- `FORBIDDEN_SCOPE`: private report access; real manifest/preregistration creation; CC02-C–E; replay; transform; Vision;
  generation; network; subprocess; schema/migration/API/workflow/dependency/model changes; threshold, eligibility,
  mechanism or READY decisions; edits to accepted CC01C/CC02-A evidence.
- `DEPENDENCIES`: accepted CC02-B contract `f69361e`, accepted content SHA-256 `e82e0b83...`, and the more specific
  exact-byte rules in its `platform_report_bindings` and canonical-digest sections.
- `INPUTS_AND_ASSUMPTIONS`: tests use only synthetic/numeric in-memory reports. Both private report environment variables
  and both future tracked outputs remain absent.

## Exact-byte correction

The accepted contract's sentence claiming deterministic output bytes across input key ordering conflicts with its more
specific requirement that `legacy_report_sha256` bind the exact presented byte stream. Reordering JSON keys changes that
byte stream, so it must change `legacy_report_sha256`, `manifest_content_digest` and preregistration bytes. The corrected
requirement is:

- identical presented input bytes produce identical manifest and preregistration bytes across repeated runs;
- semantically equivalent reports with different JSON key ordering retain identical safe case/repeat/resource projection;
- their exact report-byte bindings and therefore final output bytes must differ;
- the builder must never canonicalize a private report before computing `legacy_report_sha256`.

This is a contract-fidelity correction, not a schema or authority change. The historical accepted contract candidate and
its hash remain evidence; this forward repair governs builder acceptance.

## R3–R5 adversarial closure

- R3 bound staging and final identities/bytes, made marker and directory changes durable, added exact-type frozen-value
  validation and made anchor close post-commit best-effort.
- Principal reproduced and closed a Windows-only child reparse path: a matching-byte file symlink could pass when Windows
  ignored POSIX `O_NOFOLLOW`. Child verification now compares pre-open name identity/type/reparse state, held descriptor
  identity/content and post-read name identity/type/reparse state.
- Independent security review rejected both rollback and revalidation after successful marker unlink because either can
  create a new failed transaction with unmarked partial residue. R5 therefore makes the successful unlink the explicit
  logical commit and treats its following directory sync as best-effort only.
- The incomplete marker is itself bound to exact bytes and a stable file identity before each final publication, after
  staging cleanup and immediately before commit. A matching-byte marker replacement is not accepted.
- Stable targeted evidence: Windows 46 PASS; standard Linux API image with `--network none` 46 PASS; complete local Python
  regression 527 passed / 162 skipped; Ruff format/check, strict mypy, `pnpm.cmd check` and scoped `git diff --check`
  PASS. Fresh independent security/privacy and Sol final reviews under ADR-048: `PASS`. The builder entry point was not
  run, private inputs were not read and neither future tracked output was created. Tracked same-SHA Actions and eight
  readable artifacts remain pending.

## CC-P2-M5-03 threat-boundary disposition

Final review then reproduced a final-child replacement after the last exact validation but before marker unlink. Sol
architecture review proved that two ordinary files plus a marker cannot portably exclude an active same-UID/same-permission
writer: another validation only moves the race, POSIX held descriptors and advisory locks do not deny owner mutation, and
Windows deny-share handles have no cross-platform equivalent.

ADR-048 therefore freezes the required `LOCAL_PUBLICATION_TRUST_BOUNDARY`: builder invocation and immediate Principal
snapshot handoff require trusted exclusive write/delete custody of `docs/research`. R05 remains a create-once correctness
and crash/error recovery repair; it does not claim hostile-local-writer tamper resistance. The reproduced counterexample
is retained as boundary evidence rather than falsely labelled fixed. Builder acceptance now requires a fresh security and
final review against ADR-048 plus a cooperative concurrent-invocation test.

## Filesystem publication and recovery boundary

- The two fixed tracked paths are not an operating-system-level multi-file transaction. The implementation must not
  claim otherwise.
- Both documents are fully validated, written, `fsync`ed and closed under hidden same-parent staging names before either
  fixed path is published. Hidden staging files have no authority and are never accepted evidence.
- Before the first fixed path is published, the writer exclusively creates and durably writes the hidden
  `.p2-m5-cc02-publication-incomplete` marker. The marker is removed only after both fixed paths and their directory
  entries are durable, staging cleanup is durable, both exact final bytes/identities are reverified and the held
  directory anchor remains valid; its presence always means `NON_AUTHORITATIVE_RECOVERY_REQUIRED`.
- Successful marker unlink is the logical commit transition. The writer immediately attempts one final directory sync.
  If that sync succeeds, marker absence is also durably recorded. If it reports failure after the unlink succeeded, the
  writer must not attempt rollback, marker recreation or a second transactional validation phase: both final links,
  staging cleanup, held-anchor validation and exact final identity/byte checks completed before commit. A crash before
  the marker unlink becomes durable can only restore the already-durable incomplete marker, which conservatively makes
  the exact finals non-authoritative until recovery.
- Same-permission mutation after logical commit is outside the bounded writer transaction, just as mutation immediately
  after the function returns is outside it. The writer cannot make two ordinary repository files immutable against their
  owner. Tracked diff/hash review and same-SHA CI bind the later acceptance snapshot; this boundary must not be disguised
  as a portable multi-file filesystem transaction.
- Root, `docs` and `docs/research` must be real directories, not symlinks, junctions or reparse points. Their device/inode
  identity is captured before staging and rechecked around publication; any observed change stops the task. POSIX child
  operations are relative to a held `dir_fd` chain. Windows holds `CreateFileW` directory handles without delete sharing,
  so the chain cannot be renamed or replaced while path-based child operations run.
- Create-once publication uses exclusive hard-link creation. An ordinary first/second publication failure rolls back any
  fixed path created by that invocation. Cleanup errors are never ignored.
- No portable filesystem can guarantee rollback after an arbitrary persistent close/unlink/I/O failure across two
  independent fixed paths. If cleanup cannot complete, the builder returns only the allowlisted stop, emits no PASS, and
  any residue remains non-authoritative and blocks the next create-once invocation. Principal/operator recovery must
  inspect and remove only the exact failed invocation's residue before a new attempt; it may never be repaired, accepted
  or overwritten in place. A fixed-path residue after a persistent rollback failure is valid only together with the
  incomplete marker and a failed builder outcome; it is not a manifest candidate.
- Synthetic tests must distinguish this recovery stop from success: pre-publication cleanup failure may leave only hidden
  staging, never either fixed authority path; the normal second-publication rollback path must leave neither fixed path.

## Acceptance and validation

- `ACCEPTANCE_CRITERIA`:
  1. production entry points accept neither caller-supplied authority nor output root;
  2. all resource-envelope fields required by the accepted contract appear in the exact preregistration bytes;
  3. non-canonical manifest bytes, direction-order drift, resource drift and preregistration drift fail closed;
  4. malformed sort fields return only `ManifestBuildError`; output-parent reparse/identity changes fail closed;
  5. open/write/`fsync`/close-before-release and ordinary publication failure tests leave neither fixed authority path;
     persistent staging-cleanup failure is detected, leaves no fixed authority path and enters the recovery boundary;
     persistent fixed-path rollback failure before the logical commit retains the incomplete marker, returns no PASS and
     blocks a second attempt; a directory-sync error after successful marker unlink never starts rollback or converts the
     already committed exact outputs into a failed transaction;
  6. exact-byte versus semantic key-order behavior is tested explicitly;
  7. no private input/output path exists and no later Gate opens;
  8. targeted checks, same-SHA three-job Actions, eight artifacts, independent security and final review pass before the
     Principal may accept R05 or the builder.
- `VALIDATION_COMMANDS`:
  - `.\.venv\Scripts\python.exe -m ruff format --check scripts/research/build_p2_m5_cc02_manifest.py
services/api/tests/test_p2_m5_cc02_manifest.py`;
  - `.\.venv\Scripts\python.exe -m ruff check scripts/research/build_p2_m5_cc02_manifest.py
services/api/tests/test_p2_m5_cc02_manifest.py`;
  - strict mypy for the builder with `MYPYPATH=services/api/src`;
  - `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_p2_m5_cc02_manifest.py -q`;
  - `pnpm.cmd format:check`; `git diff --check`; bounded source/path/dependency/schema/API/network/private-field scans;
  - complete existing local Gate and same-SHA Actions before acceptance.
- `RECOMMENDED_AGENT`: Principal integration followed by `pm_security_reviewer` and `pm_final_reviewer` read-only review.
- `RECOMMENDED_MODEL_TIER`: Principal-selected model; bounded reviews retain their configured tiers.
- `OUTPUT_FORMAT`: existing Project Mirror task report format.
- `ESCALATION_CONDITION`: any need to change frozen manifest keys, digest semantics, report authority, schema/API,
  dependency/model, threshold, privacy boundary or later Gate.

`P2_M5_R05: REPAIR_ACCEPTED_AT_298420F_RUN_32299835326_ATTEMPT_1`

`CC_P2_M5_02_B_BUILDER: PASS_AT_298420F_RUN_32299835326_ATTEMPT_1`

`CC02_B_BUILDER_PRE_READ_GATE: PASS_AT_298420F_RUN_32299835326_ATTEMPT_1`

`HISTORICAL_CC_P2_M5_02_PRIVATE_INPUT: PRIVATE_INPUT_RELEASE_REQUIRED_SUPERSEDED_BY_RECOVERY_PASS`

`HISTORICAL_P2_M5_NEXT_ACTION: SECURE_FIXED_PRIVATE_INPUT_RELEASE_THEN_REPEAT_CUSTODY_PREFLIGHT`

## ADR-048 real invocation checkpoint

Principal recovered the two original reports from the prior Stage C task receipt, validated their frozen authority,
established exclusive custody and invoked the accepted builder exactly once. Immediate snapshot found both fixed
regular outputs, manifest digest `5a0479a21556498d259572a050d659a0e3617429f83e5fd313c842a35591e0a3`, zero
staging nodes and no incomplete marker. The environment handoff was cleared before custody release. This was local
candidate evidence at construction time; exact-SHA run `32332408245` and both independent reviews subsequently
accepted the manifest snapshot without changing R05 builder acceptance or opening CC02-C.

`ADR_048_REAL_INVOCATION: ACCEPTED_AT_96CA439_RUN_32332408245_ATTEMPT_1`

`CC_P2_M5_02_B_MANIFEST: PASS_AT_96CA439_RUN_32332408245_ATTEMPT_1`

`CC_P2_M5_02_C_ENTRY: CLOSED_PENDING_SEPARATE_BOUNDED_CONTRACT`

`P2_M5_NEXT_ACTION: PREPARE_SEPARATE_CC02_C_BOUNDED_CONTRACT_NO_EXECUTION`
