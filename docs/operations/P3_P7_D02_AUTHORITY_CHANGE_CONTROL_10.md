# P3–P7 D02 Change Control 10 — Windows Read-Only Host Projection

## Decision status

```text
CHANGE_CONTROL_ID: P3_P7_D02_CC_10
TRACK: DEMO_PROTOTYPE
STATUS: CANDIDATE_REVISION_1_PENDING_INDEPENDENT_SOL_EXACT_PLAN_REVIEW
BASE_SHA: eacec651518ce84b0a94db28b4fefcb867c2ecff
TASK_ID: P3_P7_D02_CC10_WINDOWS_HOST_PROJECTION_IMPLEMENTATION_01
PREDECESSOR_CHANGE_CONTROL: P3_P7_D02_CC_09
PREDECESSOR_IMPLEMENTATION_SHA: dd16624ed5ff679b03fefc61994f4ea9fd85e71e
PREDECESSOR_IMPLEMENTATION_ACCEPTANCE_DIGEST: 9421b293f88c6015f1f2f42d449d54bf93bd806fedcf73cb7a76ec4c3bef4f2c
PREDECESSOR_ACCEPTANCE_STATE_SHA: 889bb6fa2379d3369c1e72d32b4af8cca03387aa
PREDECESSOR_EXECUTION_STATE_SHA: eacec651518ce84b0a94db28b4fefcb867c2ecff
PLAN_AUTHORIZED_SCOPE: IMPLEMENT_AND_VALIDATE_EXACT_TWO_FILE_WINDOWS_READ_ONLY_HOST_PROJECTION_ONLY
PRODUCTION_ENTRYPOINT_ARGUMENTS: NONE
PRODUCTION_ENTRYPOINT_RESULT: CANONICAL_HOST_CANDIDATE_BYTES_ONLY
HOST_DIRECTORY_MUTATION_AUTHORIZED: NO
PRIVATE_OUTPUT_CREATED: NO
RAW_ETW_RETENTION: NONE
SOURCE_GENERATION_CALLS_AUTHORIZED: 0
M3_M4_EXECUTION_AUTHORIZED: NO
POSTGRESQL_ADMISSION_AUTHORIZED: NO
D02_R2_TASK_ACCEPTED: NO
D03: BLOCKED
D04_B: BLOCKED
D07_B: BLOCKED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

CC10 is forward-only. It does not rewrite or withdraw CC09. CC09 correctly accepted validators and an injected
read-only projection seam; repository inspection proved that those bytes contain no real Windows collector,
canonical candidate builder, production emitter or native no-write proof harness. Those capabilities exceed the CC09
implementation acceptance and therefore require this new change control rather than a Repair Task.

## Accepted predecessor Gate

```text
CC09_IMPLEMENTATION_TREE: 632a1e7a334f33c9ca1b070bfe06228f80c1ae33
CC09_ACCEPTANCE_RECORD: docs/operations/P3_P7_D02_R2_LOCATOR_CUSTODY_IMPLEMENTATION_ACCEPTANCE.json
CC09_SOURCE_BLOB: 8a2a63f5338733f57aaaa0dc4898cedd08919d4a
CC09_TEST_BLOB: 5577e760c77a02175e5a32e12b4dccecd3ccaf99
CC09_IMPLEMENTATION_CI: PASS_33156860094
CC09_ACCEPTANCE_STATE_CI: PASS_33161517249
EXECUTION_STATE_CI: PASS_33164251848
```

Run `33164251848` passed `quality-and-integration`, `secret-scan` and `docker-validation` at exact head
`eacec651518ce84b0a94db28b4fefcb867c2ecff`; five artifacts were present, unexpired and SHA-bound. This opens CC10
governance only. It does not authorize a collector call or host write.

## Scope and ownership

After a separately tracked plan acceptance, one Terra High implementation owner may modify exactly:

```text
services/api/src/mirror_api/demo_d02_r2_locator_custody.py
services/api/tests/test_demo_d02_r2_locator_custody.py
```

The accepted CC09 validators, wire schemas, host-candidate key set, synthetic custody behavior and historical anchors
remain intact. No migration, ORM, router, OpenAPI, generated client, Celery registration, dependency, CI workflow or
public API may change. The Integration Principal alone owns future acceptance/candidate/proof files,
`.prettierignore`, execution state, MEMORY and every commit or push.

```text
NO_CC09_HISTORY_REWRITE
NO_OLD_D00_OR_CC07_RECOVERY
NO_HOST_DIRECTORY_CREATION_OR_MUTATION
NO_PROJECT_MIRROR_CONTAINER_OR_CODE_CACHE_CREATION
NO_PRIVATE_HOME_CREATION_OR_BINDING
NO_LOCATOR_NAMESPACE_OR_EVENT
NO_CC08_EVIDENCE_ROOT
NO_PRIVATE_TRACE_FILE_OR_ETL
NO_PROCMON_OR_THIRD_PARTY_DRIVER
NO_WFP_INSTALLATION
NO_IMAGEGEN_OR_M3_M4
NO_POSTGRESQL_ADMISSION
NO_D02_R2_TASK_ACCEPTANCE
NO_D03_D04_B_D07_B_OPENING
NO_FORMAL_P3_P7_AUTHORITY
NO_PRODUCTION_RELEASE
```

## Non-circular authority chain

Let:

```text
B10 = eacec651518ce84b0a94db28b4fefcb867c2ecff
G10 = final reviewed CC10 governance commit
P10 = commit containing CC10 plan acceptance
I10 = exact two-file implementation commit
S10 = commit containing CC10 implementation acceptance
A   = S10:docs/operations/P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_IMPLEMENTATION_ACCEPTANCE.json
SC  = candidate-only commit relative to S10
C   = SC:docs/operations/P3_P7_D02_R2_WINDOWS_HOST_BINDING_CANDIDATE.json
SH  = native-proof plus host-acceptance commit relative to SC
```

The only legal order is:

```text
B10 CI PASS
-> G10 exact-plan review and CI PASS
-> P10 plan acceptance and CI PASS
-> I10 implementation review and CI PASS
-> S10 implementation acceptance and CI PASS
-> native proof plus in-memory candidate bytes
-> SC candidate review and CI PASS
-> SH proof/host-acceptance review and CI PASS
-> next separately authorized code-cache/private-home stage
```

Implementation source may freeze the preceding plan-acceptance digest, but must not contain its future
implementation-acceptance digest, S10, candidate digest, SC, native-proof digest or host acceptance. The candidate
retains the frozen CC09 schema and literals, including `change_control_id=P3_P7_D02_CC_09`. CC10 externally defines:

```text
candidate.locator_custody_implementation_sha = A.implementation_sha = I10
candidate.locator_custody_implementation_acceptance_record_digest = A.record_digest
A.record_digest = TD(A.schema_version, A excluding record_digest)
A.governed_paths exactly bind source/test paths, blobs and SHA-256 values at I10
SC:<CC10 acceptance path> byte-equals S10:<CC10 acceptance path>
SC source/test blobs equal A.governed_paths
diff(S10, SC) contains only the fixed host candidate path
C.record_digest = TD(C.schema_version, C excluding record_digest)
```

A caller mapping, fully re-signed candidate, mixed-SHA evidence or future-digest cycle never becomes authority.

## Plan and implementation acceptance records

The plan-acceptance path and schema are:

```text
docs/operations/P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_PLAN_ACCEPTANCE.json
mirror.demo/D02R2WindowsHostProjectionPlanAcceptance/v1
```

It has exactly:

```text
schema_version, authority_id, change_control_id,
reviewed_plan_file_sha256, reviewed_plan_git_blob_oid,
reviewed_risk_register_file_sha256, reviewed_risk_register_git_blob_oid,
accepted_governance_sha, accepted_governance_tree, base_sha,
predecessor_implementation_sha, predecessor_implementation_acceptance_record_digest,
predecessor_acceptance_state_sha, predecessor_execution_state_sha,
schema_contract_digest, independent_review, same_sha_ci, principal_acceptance,
authorized_implementation_paths, authorized_validation_actions,
authorized_scope, prohibited_scope, record_created_at_utc, record_digest
```

`authority_id=P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_PLAN_ACCEPTANCE_01`. The authorized paths are the ordered
two-file list above. Validation actions are Ruff, strict mypy, targeted synthetic/native pytest, static call-graph and
access-mask audit, native PID-tree ETW proof, private-preimage scan, diff check, independent exact-SHA review and
same-SHA CI. Prohibited scope includes every path outside the two files, host mutation, worker candidate write,
private/root creation, generation, M3/M4, migration/ORM, PostgreSQL, API/dependency/CI change and downstream opening.

The implementation-acceptance path and schema are:

```text
docs/operations/P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_IMPLEMENTATION_ACCEPTANCE.json
mirror.demo/D02R2WindowsHostProjectionImplementationAcceptance/v1
```

It has exactly:

```text
schema_version, authority_id, change_control_id,
accepted_plan_sha, accepted_plan_tree, accepted_plan_acceptance_record_digest,
predecessor_implementation_sha, predecessor_implementation_acceptance_record_digest,
implementation_sha, implementation_tree, governed_paths,
schema_contract_digest, host_projection_contract_digest,
independent_review, same_sha_ci, principal_acceptance,
authorized_scope, prohibited_scope, record_created_at_utc, record_digest
```

`authority_id=P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_IMPLEMENTATION_ACCEPTANCE_01` and
`authorized_scope=EXECUTE_READ_ONLY_WINDOWS_HOST_PROJECTION_AND_EMIT_CANONICAL_HOST_CANDIDATE_BYTES_ONLY`.
The acceptance is created after I10 and is never embedded in I10. S10 must pass all three CI jobs before native
collection. Its production loader reads only this fixed path from the exact acceptance-state checkout, validates
canonical bytes and the predecessor/plan bindings, and rehashes both governed files. External S10/SC Git equations,
not a candidate-provided mapping, remain the final trust root.

## Production collector and emitter

The implementation adds these minimum boundaries:

```text
WindowsHostProjectionBackend
WindowsHostObservation
_collect_windows_host_observation()
_build_windows_host_binding_candidate()
emit_windows_host_binding_candidate_bytes()
collect_and_emit_windows_host_binding_candidate()
```

`collect_and_emit_windows_host_binding_candidate()` is the sole production entry point. It accepts no arguments and
returns canonical candidate bytes only. It accepts no path, backend, candidate mapping, timestamp, environment
override, fallback or output destination, and never writes a file. Tests may use private synthetic backend and frozen
clock seams; those seams are not production trust roots.

`WindowsHostObservation` carries typed digests, bounded public version tokens and the private preimages required for
final in-memory replay. Raw SID, absolute path, volume serial, file ID, PE bytes, OneDrive values and ETW paths are
excluded from repr and exceptions. Errors expose only fixed stop codes. Same observation and timestamp must produce
byte-identical candidate bytes.

## Principal and filesystem projection

The current process token is the sole principal authority:

```text
GetCurrentProcess
-> OpenProcessToken(TOKEN_QUERY)
-> GetTokenInformation(TokenUser)
-> canonical SID string
-> TD(mirror.governance/WindowsPrincipalSid/v1, {sid_string})
```

User name, environment text and caller-supplied SID are forbidden. The collector resolves exactly
`FOLDERID_LocalAppData`, `FOLDERID_Profile`, `GetWindowsDirectoryW()` and `GetSystemDirectoryW()`. It opens existing
directories with read/attribute/`READ_CONTROL`/`SYNCHRONIZE` access, no-follow semantics and no write/delete share.
Identity, attributes, ACL and parent relationships come from still-open handles.

It proves the handle-relative Profile/AppData/Local relationship, fixed-local volume, no reparse/cloud state, the
accepted CC09 OneDrive boundary, sufficient free space and exact Windows/System/PowerShell-module-root roles. ACL
collection uses `GetSecurityInfo`, complete ACE parsing, `MapGenericMask` and `AccessCheck`; no setter is reachable.

Absence probes for `ProjectMirror` and `ProjectMirror-code-cache-v1` are handle-relative under the accepted
LocalAppData handle. Only exact not-found status is accepted. Existing, inaccessible, reparse, unknown or ambiguous
state stops. Nothing is created, adopted, deleted or repaired.

## Git and executable authority

Python authority is current `sys.executable`. Windows, System32, PowerShell, cmd and the four accepted system DLLs are
derived only from handle-validated Windows/System-directory authorities. PATH, cwd, `SearchPathW`, `where.exe` and
`Get-Command` are never executable authority.

Git has one resolver:

```text
ROOT: HKEY_LOCAL_MACHINE
VIEW: 64_BIT_ONLY
KEY: SOFTWARE\GitForWindows
VALUE: InstallPath
TYPE: REG_SZ_ONLY
SUFFIX: cmd\git.exe
ACCESS: KEY_QUERY_VALUE|KEY_WOW64_64KEY
FALLBACK: NONE
```

HKCU, 32-bit view, PATH, PATHEXT, cwd and second-candidate fallback are forbidden. A missing key, wrong type,
nonlocal/reparse path, missing executable or identity drift stops.

Every executable, DLL, manifest and script is opened `OPEN_EXISTING` with read-only access and no write/delete share.
The same handle supplies file identity, size and SHA-256. PE machine type and version-resource ProductName/
ProductVersion are parsed from those exact bytes; path-based version lookup, WinTrust and replacement between hash and
metadata are forbidden. Final identity/size/hash replay occurs before timestamp capture.

## PowerShell and timestamp

PowerShell is the fixed System32 Windows PowerShell executable, invoked only with
`-NoProfile -NonInteractive -NoLogo`. Its environment is synthesized from validated Windows/System/module-root
authorities and contains no proxy, credential, Provider, `MIRROR_*`, Python startup or inherited profile/cache
authority. Any persistent module-analysis/profile/cache write stops.

The collector reproduces the accepted two manifests, three nested members, three cmdlet rows, four script rows,
four-part PowerShell version and runtime closure. stdout contains one bounded canonical projection; stderr, an extra
object/module root/child or network attempt stops. `cmd.exe` is identified but not launched.

Production time comes from exactly one `GetSystemTimePreciseAsFileTime` call after all handles, hashes, ACLs,
PowerShell rows and cross-equalities replay and while identity handles remain open. FILETIME ticks subtract
`116444736000000000`; Unix microseconds use integer floor by ten. The UTC form has six fractional digits and `Z`.
There is no caller timestamp, `datetime.now()` fallback, retry or rollback tolerance.

## Static no-write contract

The reachable production graph is allowlisted to token, Known Folder, registry query/enumeration, existing-handle
metadata/security, access check, file read/hash/PE parse, time, anonymous-pipe, fixed PowerShell process and Job APIs.
All file opens are existing/read-only; all registry opens are query/enumerate-only. The graph contains no create,
overwrite, persistent `WriteFile`, truncate, delete, rename, file/security setter, registry setter/deleter, writable
mapping, WFP mutation, WinTrust, arbitrary shell, network or DNS API.

Anonymous pipes, process handles, one Job Object and the proof observer's real-time ETW session are temporary kernel
state, not persistent output. They are bounded and cleaned in `finally`.

## Native PID-tree proof

The observer starts before target creation. It may enable `SeSystemProfilePrivilege` for this proof only, records the
prior state and restores it in `finally`. Target Python starts suspended, is assigned to a non-breakaway Job Object
with active-process limit two and kill-on-close, then resumes with `-I -S -B -X utf8`. Only fixed anonymous pipes are
inherited; the sole permitted child is fixed PowerShell. ProcessStartKey or equivalent stable identity is mandatory;
PID alone is insufficient.

The real-time memory-only session enables exactly:

```text
Microsoft-Windows-Kernel-Process          22FB2CD6-0E7B-422B-A0C7-2FAD1FD0E716
Microsoft-Windows-Kernel-File             EDD08927-9CC4-4E65-B970-C2560FB5C289
Microsoft-Windows-Kernel-Registry         70EB4F03-C1DE-4F73-A051-33D13D5413BD
Microsoft-Windows-Winsock-AFD             E53C6823-7BB8-44BB-90DC-3F86090D48A6
Microsoft-Windows-Winsock-NameResolution  55404E71-4DB9-4DEB-A5F5-8F86E46DDE56
```

Provider version/opcode decoding is exact; unknown schema or ambiguous status stops. File/Registry start and
completion events are correlated. Successful persistent create/write/truncate/delete/rename/security and registry
create/set/delete are mutations. Anonymous-pipe operations are allowed only for inherited pipe identities. Every
Winsock or NameResolution event in the target tree stops.

Proof succeeds only with complete process-tree closure; zero `EventsLost`, `LogBuffersLost` and
`RealTimeBuffersLost`; terminal target/child; successful `CloseTrace` and `ControlTrace(STOP)`; absent-session replay;
closed Job/handles; and restored privilege. No `.etl`, AutoLogger, Procmon log, event dump or private trace exists.
The claim is limited to zero successful persistent filesystem/registry mutation by the collector PID tree. It does not
claim zero causal writes by unrelated system services.

## Native proof summary

Raw ETW is never retained. A path-free canonical summary may later be tracked at
`docs/operations/P3_P7_D02_R2_WINDOWS_HOST_PROJECTION_NATIVE_PROOF.json` under
`mirror.demo/D02R2WindowsHostProjectionNativeProof/v1`. It binds S10/I10/implementation acceptance, candidate digest
and file SHA, OS build/architecture, fixed invocation and contract digests, synthetic ledger, ETW providers,
process-tree identity, counts/loss counters, lifecycle/cleanup booleans, denied egress, timestamp and record digest.

Frozen success values are zero persistent filesystem mutations, registry mutations, Winsock events, name-resolution
events and loss counters; observer-before-target, suspended-create, job-before-resume and privilege-restored are true;
cleanup/session-absence are PASS; `RAW_ETW_RETENTION=NONE`; result is PASS. It contains no path, SID, PID, file ID,
volume serial or raw event.

The proof is committed with later host acceptance, not with SC. The unchanged CC09 host-acceptance schema binds it
through `independent_review.evidence_digest`, defined as the typed digest of exact review task ID, SC, candidate record
digest, native-proof record digest, CC10 implementation-acceptance digest, four zero finding counts and PASS. Thus no
candidate-schema change or self-signature is introduced.

## Synthetic call ledger and evidence policy

Every backend operation records only role, API family, access, share mask, disposition and output class in an
in-memory ledger. Tests require its exact order and reject a write right, create disposition, path fallback, network
call, extra process or output destination. The digest, never raw paths/handles, enters the native proof.

```text
NETWORK_POLICY: PUBLIC_INTERNET_EGRESS_DISABLED
TARGET_NETWORK_SYSCALLS: 0
LOCALHOST_REQUIRED: NO
DOCKER_INTERNAL_NETWORK_REQUIRED: NO
ACQUISITION_AUTHORIZED: NO
RAW_ETW_RETENTION: NONE
PRIVATE_NATIVE_TRACE_FILE: FORBIDDEN
```

CC10 creates no private bytes before host acceptance, so it creates no private folder, private name receipt or CC08
root. The only retained proof is uploadable, path-free tracked JSON. If raw trace or private preimage persistence
becomes necessary, execution stops for a new private-output custody change control.

## Mandatory validation

Cross-platform tests must prove:

- Linux import and strict typing; the native production entry fails closed off Windows;
- all accepted CC09 tests and candidate keys/literals/digests remain unchanged;
- production entry has zero parameters and returns bytes only;
- caller path/backend/timestamp/candidate/environment/output injection is impossible;
- identical observation/timestamp produces byte-identical candidate bytes;
- missing/extra/wrong-role observation, acceptance drift and fully re-signed mapping fail closed;
- SID/path/volume/file-ID/PE/OneDrive/ETW preimages never enter repr, errors, output or canonical bytes;
- static calls, access masks, share modes and dispositions match the read-only allowlist;
- synthetic ledger rejects mutators, network, path fallback and extra processes;
- PATH/PATHEXT/cwd/SearchPath/where/Get-Command Git decoys cannot affect authority;
- missing/wrong-type/HKCU-only/32-bit-only Git registration and replacement fail closed;
- same text/different identity, changed hash/version/machine and mid-read replacement fail;
- every PowerShell manifest/member/cmdlet/script/runtime closure equality and ordering is attacked;
- clock injection, multiple reads, invalid FILETIME, rounding drift and malformed UTC fail;
- candidate collision preserves bytes and stops; no worker writes a candidate;
- Ruff, strict mypy, targeted pytest and `git diff --check` pass.

Native Windows tests must prove:

- current SID, LocalAppData/Profile and Windows/System relationships replay from handles;
- fixed-local volume, reparse/cloud/OneDrive/ACL/free-space boundaries pass;
- both Project Mirror candidates are truly absent and no directory is created;
- Python, registry Git, PowerShell, cmd, system DLLs, manifests and members pass same-handle replay;
- PowerShell cmdlet/script/runtime closure is real, bounded and path-free;
- two runs differ only in timestamp/record digest; saved observation plus timestamp rebuilds identical bytes;
- emitted bytes pass existing `validate_windows_host_candidate` with externally replayed S10 bindings;
- zero persistent filesystem/registry mutations, Winsock/DNS events and ETW loss counters;
- ETW session, Job, child, handles and temporary privilege are fully cleaned;
- candidate/proof contain no absolute path, SID, file ID, volume serial, PID or trace payload;
- public egress is denied and no Provider is called.

Linux CI is mandatory but cannot substitute for native Windows evidence.

## Stop rules

```text
CC10_PLAN_ACCEPTANCE_MISSING_STOP
CC10_IMPLEMENTATION_ACCEPTANCE_MISSING_STOP
CC10_IMPLEMENTATION_AUTHORITY_CYCLE_STOP
CC10_IMPLEMENTATION_BINDING_MISMATCH_STOP
WINDOWS_HOST_PROJECTION_NOT_WINDOWS_STOP
WINDOWS_HOST_PROJECTION_NATIVE_API_UNAVAILABLE_STOP
WINDOWS_HOST_PROJECTION_PRIVATE_PREIMAGE_DISCLOSURE_STOP
WINDOWS_HOST_PROJECTION_GIT_AUTHORITY_UNAVAILABLE_STOP
WINDOWS_HOST_PROJECTION_GIT_AUTHORITY_AMBIGUOUS_STOP
WINDOWS_HOST_PROJECTION_EXECUTABLE_IDENTITY_DRIFT_STOP
WINDOWS_HOST_PROJECTION_PE_METADATA_MISMATCH_STOP
WINDOWS_HOST_PROJECTION_POWERSHELL_CLOSURE_STOP
WINDOWS_HOST_PROJECTION_PRECONDITION_NOT_ABSENT_STOP
WINDOWS_HOST_PROJECTION_TIMESTAMP_AUTHORITY_STOP
WINDOWS_HOST_PROJECTION_MUTATION_DETECTED_STOP
WINDOWS_HOST_PROJECTION_NETWORK_EVENT_DETECTED_STOP
NATIVE_NO_WRITE_PROOF_UNAVAILABLE_STOP
ETW_EVENT_SCHEMA_UNSUPPORTED_STOP
ETW_EVENT_LOSS_STOP
ETW_PID_TREE_INCOMPLETE_STOP
ETW_CLEANUP_FAILED_STOP
WINDOWS_HOST_BINDING_CANDIDATE_COLLISION_STOP
```

A stop emits only its code, preserves all prior bytes and creates no candidate. It never authorizes deletion, unknown
state cleanup, fallback, suffix, alternate locator, relaxed proof or mock PASS.

## Review Gates

```text
G1: independent Sol exact-plan review of CC10 and R-DEMO-39..41
G2: governance same-SHA CI and Principal plan acceptance
G3: exact I10 two-file ownership/diff/preimage review
G4: independent Sol exact-implementation review
G5: I10 same-SHA CI and Principal implementation acceptance
G6: S10 acceptance-state same-SHA CI
G7: independent native no-write and candidate-byte review
G8: SC candidate-only same-SHA CI
G9: SH proof/host-acceptance review and same-SHA CI
G10: Principal host-binding acceptance and next-node publication
```

The same reviewer is not both sole plan author and sole final implementation reviewer. Worker PASS is evidence only;
Principal reviews actual bytes and decides every acceptance.

## State and critical path

```text
CURRENT:
  CC09_IMPLEMENTATION_ACCEPTED
  NEXT_READY_NODE=P3_P7_D02_CC_10_GOVERNANCE

AFTER_CC10_PLAN_ACCEPTANCE:
  CC10_IMPLEMENTATION_AUTHORIZED

AFTER_CC10_IMPLEMENTATION_ACCEPTANCE_AND_S10_CI:
  READ_ONLY_WINDOWS_HOST_BINDING_CANDIDATE_EXECUTION_AUTHORIZED

AFTER_SC_CI:
  WINDOWS_HOST_BINDING_CANDIDATE_NON_AUTHORITY

AFTER_SH_ACCEPTANCE_AND_CI:
  WINDOWS_HOST_BINDING_ACCEPTED
  NEXT_READY_NODE=CODE_CACHE_AND_PRIVATE_HOME_CANDIDATE_RECEIPTS
```

Throughout CC10:

```text
D02_R2: BLOCKED
D03: BLOCKED
D04_B: BLOCKED
D07_B: BLOCKED
EVIDENCE_ROOT: NOT_CREATED
TWO_COPY_REGISTRY: NOT_INITIALIZED
IMAGEGEN_CALLS_EXECUTED: 0
```

Formal CC04 QuestionBank generation remains outside the Demo critical path and keeps its independent worktree,
namespace, registry, ordinal and low-priority resource schedule. CC10 does not release its generation slot.

## Risk and acceptance boundary

CC10 adds R-DEMO-39–41 while R-DEMO-33–38 remain active. An accepted plan authorizes implementation only. An
accepted implementation authorizes one read-only projection only. A candidate is not authority. Only later host
acceptance may open the exact code-cache/private-home candidate-and-receipt stage. None of these states proves formal
P3–P7, real-user validity, production security or production readiness.
