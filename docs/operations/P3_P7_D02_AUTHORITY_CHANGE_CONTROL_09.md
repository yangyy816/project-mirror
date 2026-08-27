# P3–P7 D02 Change Control 09 — Principal Locator Custody for the Single CC08 Root

## Decision status

```text
CHANGE_CONTROL_ID: P3_P7_D02_CC_09
TRACK: DEMO_PROTOTYPE
STATUS: CANDIDATE_REVISION_8_PENDING_INDEPENDENT_SOL_EXACT_PLAN_REVIEW
BASE_SHA: fd25ae5b0e16178e3556f22492dc449b8765635c
AUTHORITY_ID: P3_P7_D02_R2_LOCATOR_CUSTODY_AUTHORITY_01
ALLOCATION_ID: P3_P7_D02_R2_CC08_E1_ROOT_LOCATOR_ALLOCATION
PRIVATE_HOME_HANDLE_ID: PM_PROJECT_MIRROR_PRIVATE_HOME_V1
CUSTODY_NAMESPACE_ID: pm-project-mirror-principal-private-output-registry-v1
CUSTODY_COPY_A_ID: P3_P7_D02_R2_LOCATOR_CUSTODY_A
CUSTODY_COPY_B_ID: P3_P7_D02_R2_LOCATOR_CUSTODY_B
EVIDENCE_ROOT_ID: P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT
EVIDENCE_ROOT_BASENAME: p3-p7-d02-r2-cc08-e1-evidence
EVIDENCE_ROOT_FIRST_FILE: D02_R2_EVIDENCE_ROOT_NAME_RECEIPT.json
CC07: UNCHANGED
CC08: UNCHANGED
SOURCE_GENERATION_CALLS_AUTHORIZED: 0
PUBLIC_INTERNET_EGRESS_AUTHORIZED: NONE
PLAN_AUTHORIZED_SCOPE: IMPLEMENT_AND_VALIDATE_EXACT_TWO_FILE_CC09_LOCATOR_CUSTODY_ONLY
PRIVATE_HOME_CREATED: NO
LOCATOR_NAMESPACE_CREATED: NO
D02_R2_TASK_ACCEPTED: NO
D03: BLOCKED
D04_B: BLOCKED
D07_B: BLOCKED
FORMAL_PHASE_AUTHORITY: FALSE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

## Purpose and corrected evidence statement

CC09 creates a forward-only locator-custody control plane for the one fixed CC08 evidence-root identity. It does not
recover old D00 custody, reinterpret an unbound directory, or claim that a root already exists.

The value below occurs in accepted migration planning records and in the local R05 evidence-set metadata, but no exact
CC08 root receipt bytes and no accepted locator mapping have been replayed for it:

```text
PRE_ROOT_EXPECTATION_DIGEST: c3ae43887d51d15347153e392ca092866dff890bdcda959572cc1dd07e6195c4
ROOT_DURABILITY_EVIDENCE: NOT_PROVEN
LOCATOR_AUTHORITY: NOT_PROVEN
MAY_AUTHORIZE_ROOT_RECOVERY_OR_POSTGRESQL_ADMISSION: NO
```

Backdating a receipt, forcing a timestamp to reproduce that value, or treating it as the digest of future bytes is
forbidden. The actual root-receipt digest will be accepted only through the forward authority chain defined below.

## Preserved authority and immutable references

- CC07 remains `EVIDENCE_LOCATION_LOST`, `NO_GO_CRITICAL_DEPENDENCY_UNAVAILABLE` and
  `OLD_D00_RECOVERY: CLOSED_NO_NEW_LEAD`.
- CC08 retains its accepted root/registry semantics and every generation, runtime and admission Gate.
- Accepted CC08 plan: SHA `218f4b5a5ee4e6e2223995d232da61496dd47de3`, tree
  `1cff56bd1f1127a310622d5b8a72045b39290549`.
- Accepted R06 registry implementation: SHA `ab08a6e861ec364c62a6ab3dcf46a69483f1b741`, tree
  `47f1b6ccfa73f757348dd3c4038cf3dae9335ba1`.
- Its governed bytes are fixed as:

  ```text
  services/api/src/mirror_api/demo_d02_r2_private_registry.py
    blob: 1beee70d53b172a334ecf76e18f08a137f7bb9a0
    sha256: 72fd639da11a80b5a5b6f4d19c2a45ddd03d5c1b740518c22ac26a3e98c5239e
  services/api/tests/test_demo_d02_r2_private_registry.py
    blob: 7906e46d62a2530d9eaba16e9af4418a206d1300
    sha256: 9158c732d063f9540f1b488c2f27215bcd225b71639f53dd1154b06950b8f4e0
  services/api/src/mirror_api/demo_measurement_quality.py
    blob: c9f319b9410b6741a8a000395d525fe2a103de59
    sha256: abbade973f106f4d63700fc382109b5b86803b1cf976359f684bbb6421f301f7
  ```

- Registry implementation acceptance: record digest
  `a7170831675c35aaf9354a12a788d16251ec40d98fcd472c8f4c78dbf3f1d1e3` and Principal acceptance-authority digest
  `08af0bbc6802939cee9a26020b505dc9b323c3f67992f987ee4dc7b5d4930943`.
- The tracked R06 acceptance checkpoint is `3c743cdf5167bf3484be98b4f50e0ea6c77c5f13`; this revision's base is its
  one-file formatting-policy repair descendant. The canonical acceptance JSON bytes remain unchanged.
- The accepted `demo_d02_r2_private_registry.py`, its tests and `demo_measurement_quality.py` remain byte-identical.
- The control-plane namespace stores locator custody only. It is not a second D02 evidence root.

## Canonicalization and typed-digest rule

Every CC09 JSON object is strict UTF-8 `demo-canonical-json-v1`: recursively normalized JSON, keys sorted, no whitespace,
no NaN/Infinity, no duplicate keys and a trailing newline is absent. A typed digest is:

```text
sha256(UTF8(schema_version) || 0x0a || canonical_json_bytes(payload))
```

The payload excludes only the object's final self-digest field. File SHA-256 is over the complete canonical file bytes.
Every timestamp is canonical UTC `YYYY-MM-DDTHH:MM:SS.ffffffZ`; negative zero, floats, unordered sets, paths and implicit
wall-clock defaults are forbidden.

### Field type and grammar closure

- Every `schema_version` equals the exact schema string named by its section.
- IDs, roles, states and logical tokens are non-empty ASCII strings. Object/task/allocation/copy IDs match
  `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`; no separator, colon, `.` or `..` token is accepted.
- Every field ending `_digest` or `_sha256` is a JSON string matching exactly `[0-9a-f]{64}`. Every Git SHA/tree/blob
  OID is a string matching `[0-9a-f]{40}`. Private-only physical identity preimages use
  `volume_serial_number_hex`, `file_id_128_hex`, `file_attributes_hex` and `reparse_tag_hex` with exact lengths 16, 32,
  8 and 8 lowercase hexadecimal characters; those preimages never enter tracked governance.
- Sequences, counts and byte ceilings are JSON integers, never booleans. Sequence/count values are non-negative;
  transaction sequences are positive and at most `99,999,999`; byte ceilings are positive and at most
  `42,949,672,960`.
- `is_directory` is the JSON boolean `true`. The namespace/genesis/locator/event/intent/snapshot/commit custody wire
  schemas contain no other boolean; future tracked acceptance records use their separately frozen evidence shapes.
- `authorized_implementation_paths`, `authorized_validation_actions`, `prohibited_scope`, `allowed_subject_root_ids`,
  `allowed_principal_tasks`, `ordered_worktree_identity_digests`, `ordered_event_digests` and
  `relative_control_manifest`, every PowerShell manifest collection, `ordered_command_rows`, `ordered_script_rows`,
  `ordered_loaded_member_identity_digests`, `accepted_r06_governed_rows` and `probe_targets` are JSON arrays. Their order
  is authority, duplicates are forbidden and their member types are fixed by the corresponding section.
- Nested objects are schema-specific. Custody namespace wire schemas allow only the exact five-field
  `relative_control_manifest` rows; acceptance records allow only their frozen `governed_paths`, review, CI and
  Principal-evidence objects; PowerShell projections allow only their exact member/command/script rows; the accepted
  R06 checkout seal allows only its exact governed rows; the R05 rehome manifest allows only exact `ordered_entries`
  rows. No other schema permits nested objects unless its section explicitly freezes every key and type.
- Base64url strings are ASCII, unpadded and must decode/re-encode byte-identically. Timestamps match exactly
  `[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{6}Z` and parse as valid UTC.
- JSON `null` is legal only for the event fields and initial snapshot state explicitly listed by the transition table.
  Missing keys, extra keys, wrong types, empty strings, uppercase hex, malformed UTF-8 and non-canonical bytes stop.

## Future tracked acceptance authorities

The authority chain is deliberately non-circular and must advance in this exact order:

```text
CC09_PLAN_ACCEPTANCE
-> CC09_LOCATOR_IMPLEMENTATION_ACCEPTANCE
-> WINDOWS_HOST_BINDING_CANDIDATE
-> WINDOWS_HOST_BINDING_ACCEPTANCE
-> CODE_CACHE_NAME_RECEIPT + ACCEPTED_R06_CHECKOUT_SEAL_RECEIPT
-> PROJECT_MIRROR_CONTAINER_NAME_RECEIPT
-> PRIVATE_HOME_NAME_RECEIPT + PRIVATE_HOME_BINDING_CANDIDATE
-> PRIVATE_HOME_BINDING_ACCEPTANCE
-> BRIDGE_SCRATCH_NAME_RECEIPT
-> namespace / locator custody / CC08 root
```

No object may contain the digest of a later authority. In particular, the plan never contains its future acceptance
digest; implementation source never contains its future implementation-acceptance digest; a host candidate never
contains host acceptance; the private-home name receipt and candidate never contain private-home acceptance; and an
event or rehome manifest never includes its own digest in its digest preimage.

Plan acceptance will be a canonical JSON record at
`docs/operations/P3_P7_D02_R2_LOCATOR_CUSTODY_PLAN_ACCEPTANCE.json`, schema/domain
`mirror.demo/D02R2LocatorCustodyPlanAcceptance/v1`. It has exactly:

```text
schema_version
authority_id
change_control_id
reviewed_plan_file_sha256
reviewed_plan_git_blob_oid
reviewed_risk_register_file_sha256
reviewed_risk_register_git_blob_oid
accepted_governance_sha
accepted_governance_tree
base_sha
schema_contract_digest
independent_review
same_sha_ci
principal_acceptance
authorized_implementation_paths
authorized_validation_actions
authorized_scope
prohibited_scope
record_created_at_utc
record_digest
```

`authority_id=P3_P7_D02_R2_LOCATOR_CUSTODY_PLAN_ACCEPTANCE_01` and
`authorized_scope=IMPLEMENT_AND_VALIDATE_EXACT_TWO_FILE_CC09_LOCATOR_CUSTODY_ONLY`.
`authorized_implementation_paths` is the ordered literal:

```text
[
  services/api/src/mirror_api/demo_d02_r2_locator_custody.py,
  services/api/tests/test_demo_d02_r2_locator_custody.py
]
```

`authorized_validation_actions` is the ordered literal:

```text
[
  RUFF_FORMAT_AND_CHECK_AUTHORIZED_PATHS_ONLY,
  STRICT_MYPY_AUTHORIZED_IMPLEMENTATION_ONLY,
  TARGETED_PYTEST_SYNTHETIC_TEMP_ROOTS_ONLY,
  GIT_DIFF_CHECK,
  INDEPENDENT_EXACT_SHA_IMPLEMENTATION_REVIEW,
  SAME_SHA_CI
]
```

`prohibited_scope` is the ordered literal:

```text
[
  ANY_TRACKED_PATH_OUTSIDE_AUTHORIZED_IMPLEMENTATION_PATHS,
  HOST_SPECIFIC_DIRECTORY_OPERATION,
  WINDOWS_HOST_BINDING_CANDIDATE_OR_ACCEPTANCE,
  PRIVATE_HOME_CREATION_OR_BINDING,
  LOCATOR_NAMESPACE_CREATION,
  LOCATOR_EVENT_CREATION,
  CC08_EVIDENCE_ROOT_CREATION,
  R05_REHOME,
  SOURCE_GENERATION,
  M3_M4_EXECUTION,
  MIGRATION_OR_ORM,
  POSTGRESQL_ADMISSION,
  PUBLIC_API_CHANGE,
  DEPENDENCY_CHANGE,
  D02_R2_TASK_ACCEPTANCE,
  D03_D04_B_D07_B_OPENING,
  FORMAL_PHASE_AUTHORITY,
  PRODUCTION_RELEASE
]
```

The implementation commit may change only the two ordered paths above, and
`plan_acceptance.authorized_implementation_paths` must equal both the implementation acceptance
`governed_paths[*].path` sequence and the two-file Implementation boundary below. Its `principal_acceptance` object has
exactly `status`, `accepted_governance_sha`, `accepted_at_utc` and
`acceptance_authority_digest`; `status=PRINCIPAL_ACCEPTED`, `accepted_governance_sha` equals the top-level value and
`accepted_at_utc=record_created_at_utc`. Its `record_digest` is the future
`cc09_plan_acceptance_record_digest` and binds the reviewed plan/risk-register SHA-256/Git blob IDs, accepted
governance SHA/tree, exact independent-review evidence and same-SHA CI.

Implementation acceptance will be a canonical JSON record at
`docs/operations/P3_P7_D02_R2_LOCATOR_CUSTODY_IMPLEMENTATION_ACCEPTANCE.json`, schema/domain
`mirror.demo/D02R2LocatorCustodyImplementationAcceptance/v1`, with exactly:

```text
schema_version
authority_id
change_control_id
accepted_plan_sha
accepted_plan_tree
accepted_plan_acceptance_record_digest
implementation_sha
implementation_tree
governed_paths
schema_contract_digest
independent_review
same_sha_ci
principal_acceptance
authorized_scope
prohibited_scope
record_created_at_utc
record_digest
```

`governed_paths` is the ordered two-file list with exact path/SHA-256/Git-blob objects. `independent_review`,
`same_sha_ci` and `principal_acceptance` use the same exact evidence shapes as the accepted CC08 implementation record.
`principal_acceptance.status=PRINCIPAL_ACCEPTED`; its `accepted_implementation_sha` equals `implementation_sha`; its
`accepted_at_utc` must equal top-level `record_created_at_utc`. The namespace, copy-genesis and locator receipts use that
same explicit timestamp. Their implementation SHA and implementation-acceptance record digest come from this record.

The two ordered governed rows are exactly the implementation path followed by the test path, each with exactly
`path`, `sha256` and `git_blob_oid`. The plan and implementation `independent_review` objects have exactly
`evidence_digest`, `findings_p0`, `findings_p1`, `findings_p2`, `findings_p3`, `result`, `review_task_id` and one reviewed
SHA key: `reviewed_governance_sha` for plan acceptance or `reviewed_implementation_sha` for implementation acceptance.
All findings are integer zero and `result=PASS`. `same_sha_ci` has exactly `artifact_manifest_digest`, `head_sha`,
`provider`, `repository`, `required_jobs`, `result`, `run_id` and `workflow_identity`; its literals are
`provider=GITHUB_ACTIONS`, `repository=yangyy816/project-mirror`,
`required_jobs=[quality-and-integration,secret-scan,docker-validation]`, `result=PASS` and
`workflow_identity=.github/workflows/ci.yml`. Implementation `principal_acceptance` has exactly `status`,
`accepted_implementation_sha`, `accepted_at_utc` and `acceptance_authority_digest`.

Implementation `authority_id=P3_P7_D02_R2_LOCATOR_CUSTODY_IMPLEMENTATION_ACCEPTANCE_01` and its frozen scopes are:

```text
authorized_scope =
  READ_ONLY_WINDOWS_HOST_BINDING_CANDIDATE_PROJECTION_ONLY

prohibited_scope =
  [
    ANY_IMPLEMENTATION_OR_TEST_PATH_CHANGE,
    HOST_SPECIFIC_DIRECTORY_CREATION_OR_MUTATION,
    PRIVATE_HOME_CREATION,
    PRIVATE_HOME_BINDING_ACCEPTANCE,
    LOCATOR_NAMESPACE_CREATION,
    LOCATOR_EVENT_CREATION,
    CC08_EVIDENCE_ROOT_CREATION_OR_REPLAY,
    R05_REHOME,
    SOURCE_GENERATION,
    M3_M4_EXECUTION,
    MIGRATION_OR_ORM,
    POSTGRESQL_ADMISSION,
    PUBLIC_API_CHANGE,
    D02_R2_TASK_ACCEPTANCE,
    D03_D04_B_D07_B_OPENING,
    FORMAL_PHASE_AUTHORITY,
    PRODUCTION_RELEASE
  ]
```

Plan acceptance authorizes only the exact two-file implementation and validation. Implementation acceptance authorizes
only the read-only host-binding candidate projection; neither authority permits a host-specific directory operation.
Host and private-home binding authorities below are independently reviewed, same-SHA CI-bound tracked records.

### Windows principal, executable and resolver digest domains

`mirror.governance/WindowsPrincipalSid/v1` has the single private preimage key `sid_string`. The Principal obtains the
canonical SID through `OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY)` and `GetTokenInformation(TokenUser)`.
`principal_sid_digest=TD(schema, {"sid_string": canonical_sid_string})`; only the digest may enter tracked bytes.

`mirror.governance/WindowsExecutableIdentity/v1` has exactly this private preimage for PE executable or DLL bytes:

```text
volume_serial_number_hex
file_id_128_hex
file_size
file_sha256
product_name
product_version
machine_type
```

It is used for Python, Git, PowerShell, `cmd.exe`, `ntdll.dll`, `kernel32.dll`, `advapi32.dll`, `fwpuclnt.dll` and the
Security module's PE nested binary. It is never used for a `.psd1` manifest. Tracked records retain only typed identity
digests, file SHA-256 values and non-sensitive version tokens, never an absolute path, volume serial or file ID.

`mirror.governance/WindowsFileIdentity/v1` is the non-PE file domain. Its private preimage has exactly
`volume_serial_number_hex`, `file_id_128_hex`, `file_size` and `file_sha256`. It is used for the exact PowerShell
Security `.psd1` manifest and any other accepted non-PE bootstrap file; tracked bytes retain only its typed identity
digest and file SHA-256.

`mirror.governance/WindowsNativeRelativeCreateContract/v1` has exactly:

```text
backend = NTDLL_NTCREATEFILE_ROOT_DIRECTORY_V1
object_attributes_flags = OBJ_CASE_INSENSITIVE|OBJ_DONT_REPARSE
parent_desired_access = GENERIC_READ|GENERIC_WRITE|READ_CONTROL|SYNCHRONIZE
parent_share_access = FILE_SHARE_READ|FILE_SHARE_WRITE
parent_create_options = FILE_DIRECTORY_FILE|FILE_OPEN_REPARSE_POINT|FILE_SYNCHRONOUS_IO_NONALERT
child_disposition = FILE_CREATE
file_create_options = FILE_NON_DIRECTORY_FILE|FILE_OPEN_REPARSE_POINT|FILE_SYNCHRONOUS_IO_NONALERT
directory_create_options = FILE_DIRECTORY_FILE|FILE_OPEN_REPARSE_POINT|FILE_SYNCHRONOUS_IO_NONALERT
child_share_access = NONE
directory_durability = FLUSH_FILE_BUFFERS_PARENT_REQUIRED
contract_version = P3_P7_D02_R2_WINDOWS_NATIVE_RELATIVE_CREATE_V1
```

No path-based full-destination create is equivalent to this contract. Unsupported `OBJ_DONT_REPARSE`, a failed parent
directory flush or an inability to bind `RootDirectory` to the still-open parent handle fails closed before creation.

`mirror.governance/WindowsProtectedDirectoryDaclContract/v1` has exactly:

```text
owner_role = CURRENT_PRINCIPAL_SID
dacl_protection = SE_DACL_PROTECTED
ace_order = CURRENT_PRINCIPAL_FULL_CONTROL_OICI|LOCAL_SYSTEM_FULL_CONTROL_OICI|BUILTIN_ADMINISTRATORS_FULL_CONTROL_OICI
inherited_aces = FORBIDDEN
other_allow_aces = FORBIDDEN
post_create_acl_mutation = FORBIDDEN
contract_version = P3_P7_D02_R2_WINDOWS_PROTECTED_PRIVATE_DIRECTORY_DACL_V1
```

The raw Principal SID is substituted only in private process memory when the security descriptor is built. The same
descriptor is supplied in the native create request for `ProjectMirror`, `principal-private-output-v1` and every CC09
private control-plane child; an existing directory must already replay the exact protected DACL and is never repaired.

`mirror.governance/WindowsRestrictedAncestorAclContract/v1` freezes the handle-based ancestor ACL projection and has
exactly:

```text
projection_api = GetSecurityInfo_BY_OPEN_HANDLE
owner_role = CURRENT_PRINCIPAL_SID
null_dacl = FORBIDDEN
accepted_ace_types = ACCESS_ALLOWED_ACE|ACCESS_DENIED_ACE
accepted_ace_flags = OBJECT_INHERIT_ACE|CONTAINER_INHERIT_ACE|NO_PROPAGATE_INHERIT_ACE|INHERIT_ONLY_ACE|INHERITED_ACE
ace_applicability = APPLIES_TO_CURRENT_DIRECTORY_IFF_INHERIT_ONLY_ACE_IS_CLEAR
unknown_ace_flag = STOP
approved_write_roles = CURRENT_PRINCIPAL_SID|LOCAL_SYSTEM|BUILTIN_ADMINISTRATORS
dangerous_write_mask = FILE_WRITE_DATA|FILE_APPEND_DATA|FILE_ADD_FILE|FILE_ADD_SUBDIRECTORY|FILE_DELETE_CHILD|DELETE|WRITE_DAC|WRITE_OWNER|GENERIC_WRITE|GENERIC_ALL
generic_right_mapping_api = MapGenericMask
file_generic_mapping = GenericRead=FILE_GENERIC_READ|GenericWrite=FILE_GENERIC_WRITE|GenericExecute=FILE_GENERIC_EXECUTE|GenericAll=FILE_ALL_ACCESS
other_applicable_allow_dangerous_mask = FORBIDDEN
inherited_ace_policy = ALLOWED_ONLY_WHEN_THE_SAME_APPLICABLE_MASK_RULE_PASSES
required_current_principal_access = GENERIC_READ|GENERIC_WRITE|READ_CONTROL|SYNCHRONIZE
current_principal_access_verification = AccessCheck_EXACT_HANDLE_SECURITY_DESCRIPTOR_AND_CURRENT_IMPERSONATION_TOKEN
unknown_ace_type = STOP
contract_version = P3_P7_D02_R2_WINDOWS_RESTRICTED_ANCESTOR_ACL_V1
```

The ACL is obtained from the still-open directory handle, not by reopening a path. The owner must be the current
Principal. Every ACE header type and flags byte is parsed from the exact handle security descriptor. Only the five
listed inheritance flags are accepted; an ACE is applicable to the current directory exactly when `INHERIT_ONLY_ACE` is
clear. Object/container/no-propagate/inherited flags otherwise do not change current-object applicability. Before any
mask test, `MapGenericMask` applies the exact file generic mapping; the mapped mask is authority. Any applicable allow
ACE granting a dangerous bit to a SID outside the three approved roles stops even if a deny ACE also exists. Inherited
ACEs are not trusted by origin and pass only the same applicability/SID/mapped-mask predicate. `AccessCheck` separately
proves the current Principal's required effective access against the same descriptor; failure stops. Null DACL, malformed
SID/ACE, unknown ACE type or unknown flag stops.

`mirror.governance/WindowsKnownFolderBoundaryContract/v1` has exactly:

```text
local_app_data_source = SHGetKnownFolderPath(FOLDERID_LocalAppData)
profile_source = SHGetKnownFolderPath(FOLDERID_Profile)
default_relation = LOCAL_APP_DATA_IDENTITY_EQUALS_HANDLE_RELATIVE_PROFILE_APPDATA_LOCAL_IDENTITY
volume_policy = FIXED_LOCAL_VOLUME_REQUIRED
forbidden_namespace_classes = UNC|DEVICE|NETWORK
reparse_tag_policy = ZERO_REQUIRED
cloud_file_attributes = REPARSE_POINT|RECALL_ON_OPEN|RECALL_ON_DATA_ACCESS|PINNED|UNPINNED
cloud_file_attributes_policy = REJECT_IF_PRESENT
onedrive_account_source = HKCU\\Software\\Microsoft\\OneDrive\\Accounts\\*\\UserFolder
onedrive_value_type = REG_SZ_ONLY
onedrive_account_order = CompareStringOrdinal(ignoreCase=TRUE)_THEN_UTF16_CODE_UNIT_ORDINAL
onedrive_path_grammar = NONEMPTY_ABSOLUTE_DOS_DRIVE_ROOTED_NO_EMBEDDED_NUL_NO_UNC_DEVICE_OR_EXTENDED_PREFIX
onedrive_canonicalization = GetFullPathNameW_THEN_OPEN_NOFOLLOW_THEN_GetFinalPathNameByHandleW(FILE_NAME_NORMALIZED|VOLUME_NAME_GUID)
project_boundary_candidates = LocalAppData/ProjectMirror-code-cache-v1|LocalAppData/ProjectMirror|LocalAppData/ProjectMirror/principal-private-output-v1|LocalAppData/ProjectMirror/principal-private-output-v1/bridge-scratch-v1
onedrive_containment_comparison = SAME_VOLUME_GUID_AND_CompareStringOrdinal(ignoreCase=TRUE)_EQUAL_OR_COMPONENT_BOUNDARY_DESCENDANT_IN_EITHER_DIRECTION
onedrive_containment = REJECT_ANY_PROJECT_BOUNDARY_OVERLAP
malformed_or_nonabsolute_onedrive_value = PRIVATE_HOME_BOUNDARY_INVALID_STOP
unreadable_existing_onedrive_account = STOP
ancestor_acl_contract_digest
residual_boundary = DETECTABLE_WINDOWS_KNOWN_FOLDER_REDIRECTION_CLOUD_FILES_AND_ONEDRIVE_RELATIONSHIPS_ARE_REJECTED_UNIVERSAL_THIRD_PARTY_SYNC_ABSENCE_IS_NOT_CLAIMED
contract_version = P3_P7_D02_R2_WINDOWS_KNOWN_FOLDER_BOUNDARY_V1
```

Both Known Folder identities and the handle-relative `Profile/AppData/Local` identity are opened and projected through
the same `WindowsPathIdentity/v1` rules. Existing OneDrive account subkeys are enumerated in the fixed order. Every
account must expose one readable `REG_SZ` `UserFolder`; `REG_EXPAND_SZ`, missing value, embedded NUL, empty, relative,
UNC/device/extended prefix, failed canonicalization/open, non-directory, reparse/cloud attribute or non-fixed volume
stops. No environment expansion or current-directory resolution occurs.

For each valid `UserFolder`, the opened final path uses its handle-derived volume-GUID normalized path. Each project
candidate is formed only by appending its frozen relative components to the accepted LocalAppData handle-derived
volume-GUID path; every already-existing ancestor is separately opened and replayed, while an absent final candidate is
never resolved through current working directory or an environment value. Containment is component-aware: equality or
descendant requires the next UTF-16 code unit to be a backslash, uses `CompareStringOrdinal(..., TRUE)`, and is checked
in both directions to reject a OneDrive root above or inside a project boundary. Different volume GUIDs are
non-overlapping only after both fixed-volume checks pass. This contract makes the honest bounded claim shown in
`residual_boundary`; it does not claim universal detection of every third-party synchronization product.

`mirror.governance/PowerShellAclModuleClosure/v1` has exactly:

```text
powershell_executable_identity_digest
windows_directory_identity_digest
windows_system_directory_identity_digest
module_root_directory_identity_digest
module_manifest_projection_digest
required_cmdlet_projection_digest
acl_bootstrap_script_projection_digest
runtime_projection_digest
closure_digest
```

`closure_digest=TD("mirror.governance/PowerShellAclModuleClosure/v1", closure excluding only closure_digest)`. Its four
projection digests must equal the exact four projection objects below; a scalar or a member hash cannot substitute.

`mirror.governance/PowerShellModuleManifestProjection/v1` has exactly:

```text
schema_version
windows_directory_identity_digest
windows_system_directory_identity_digest
module_root_directory_identity_digest
security_manifest_file_identity_digest
security_manifest_file_sha256
security_guid
security_module_version
security_root_module_state
security_required_modules
security_scripts_to_process
security_types_to_process
security_formats_to_process
security_nested_members
utility_manifest_file_identity_digest
utility_manifest_file_sha256
utility_guid
utility_module_version
utility_root_module_state
utility_required_modules
utility_scripts_to_process
utility_types_to_process
utility_formats_to_process
utility_nested_members
projection_digest
```

Each ordered `security_nested_members` or `utility_nested_members` row has exactly
`member_role`, `relative_name`, `member_kind`, `member_identity_schema_version`, `member_identity_digest` and
`file_sha256`. The exact scalar/empty preimage is:

```text
schema_version = mirror.governance/PowerShellModuleManifestProjection/v1
security_guid = A94C8C7E-9810-47C0-B8AF-65089C13A35A
security_module_version = 3.0.0.0
security_root_module_state = ABSENT
security_required_modules = []
security_scripts_to_process = []
security_types_to_process = []
security_formats_to_process = []
utility_guid = 1DA87E53-152B-403E-98DC-74D7B4D63D59
utility_module_version = 3.1.0.0
utility_root_module_state = ABSENT
utility_required_modules = []
utility_scripts_to_process = []
utility_types_to_process = []
utility_formats_to_process = []
```

The nested rows are exactly, in order:

```text
security_nested_members[0] = {
  member_role: SECURITY_NESTED_BINARY,
  relative_name: Microsoft.PowerShell.Security.dll,
  member_kind: PE_DLL,
  member_identity_schema_version: mirror.governance/WindowsExecutableIdentity/v1,
  member_identity_digest: TD(WindowsExecutableIdentity/v1, exact opened Security DLL preimage),
  file_sha256: sha256(exact opened Security DLL bytes)
}
utility_nested_members[0] = {
  member_role: UTILITY_NESTED_BINARY,
  relative_name: Microsoft.PowerShell.Commands.Utility.dll,
  member_kind: PE_DLL,
  member_identity_schema_version: mirror.governance/WindowsExecutableIdentity/v1,
  member_identity_digest: TD(WindowsExecutableIdentity/v1, exact opened Utility DLL preimage),
  file_sha256: sha256(exact opened Utility DLL bytes)
}
utility_nested_members[1] = {
  member_role: UTILITY_NESTED_SCRIPT,
  relative_name: Microsoft.PowerShell.Utility.psm1,
  member_kind: POWERSHELL_MODULE_SCRIPT,
  member_identity_schema_version: mirror.governance/WindowsFileIdentity/v1,
  member_identity_digest: TD(WindowsFileIdentity/v1, exact opened Utility PSM1 preimage),
  file_sha256: sha256(exact opened Utility PSM1 bytes)
}
```

Both manifest identities use `WindowsFileIdentity/v1`; their file SHA-256 values bind exact manifest bytes. Rooted,
escaping, reparse-backed, additional or dynamically resolved members stop. The empty values above are JSON empty arrays
and the `ABSENT` values are JSON strings; null, omitted fields or alternate empty encodings are forbidden.

`mirror.governance/PowerShellRequiredCmdletProjection/v1` has exactly:

```text
schema_version
module_manifest_projection_digest
ordered_command_rows
projection_digest
```

Each ordered row has exactly `command_name`, `command_type`, `module_name`, `module_guid`, `module_version`,
`implementing_type_name`, `implementing_member_role` and `implementing_member_identity_digest`. The exact ordered rows
are:

```text
Get-Acl | Cmdlet | Microsoft.PowerShell.Security | A94C8C7E-9810-47C0-B8AF-65089C13A35A | 3.0.0.0 | Microsoft.PowerShell.Commands.GetAclCommand | SECURITY_NESTED_BINARY | security_nested_members[0].member_identity_digest
Set-Acl | Cmdlet | Microsoft.PowerShell.Security | A94C8C7E-9810-47C0-B8AF-65089C13A35A | 3.0.0.0 | Microsoft.PowerShell.Commands.SetAclCommand | SECURITY_NESTED_BINARY | security_nested_members[0].member_identity_digest
ConvertTo-Json | Cmdlet | Microsoft.PowerShell.Utility | 1DA87E53-152B-403E-98DC-74D7B4D63D59 | 3.1.0.0 | Microsoft.PowerShell.Commands.ConvertToJsonCommand | UTILITY_NESTED_BINARY | utility_nested_members[0].member_identity_digest
```

The eight pipe-separated values map left-to-right to the eight exact row fields; the pipes are plan notation, not JSON.
`module_manifest_projection_digest` equals the exact manifest projection above.

`mirror.governance/PowerShellAclBootstrapScriptProjection/v1` has exactly:

```text
schema_version
accepted_cc09_implementation_sha
accepted_r06_source_file_sha256
extraction_rule
ordered_script_rows
projection_digest
```

Each ordered script row has exactly `script_role`, `source_role`, `source_file_sha256`, `function_name`,
`assignment_target` and `strict_utf8_script_sha256`. The extraction rule is
`PYTHON_AST_EXACT_FUNCTION_LOCAL_STRING_CONSTANT_ASSIGNMENT_V1`; it rejects concatenation, interpolation, computed
values, duplicate assignments and AST/source drift. The exact four rows are:

```text
CC09_MODULE_MANIFEST_PREFLIGHT_SCRIPT | CC09_LOCATOR_CUSTODY_IMPLEMENTATION_SOURCE | accepted CC09 source governed-row SHA-256 | _project_powershell_module_manifest_preflight | script | sha256(strict UTF-8 exact AST string value)
CC09_MODULE_RUNTIME_PROJECTION_SCRIPT | CC09_LOCATOR_CUSTODY_IMPLEMENTATION_SOURCE | accepted CC09 source governed-row SHA-256 | _project_powershell_acl_runtime_projection | script | sha256(strict UTF-8 exact AST string value)
R06_HARDEN_NEW_ROOT_SCRIPT | ACCEPTED_R06_PRIVATE_REGISTRY_SOURCE | 72fd639da11a80b5a5b6f4d19c2a45ddd03d5c1b740518c22ac26a3e98c5239e | _harden_new_root_access_boundary | script | c68c2dd675def9cccaa6786132954897c910e36b63eb4e65e151432121c75a94
R06_VALIDATE_RESTRICTED_ACL_SCRIPT | ACCEPTED_R06_PRIVATE_REGISTRY_SOURCE | 72fd639da11a80b5a5b6f4d19c2a45ddd03d5c1b740518c22ac26a3e98c5239e | _validate_windows_restricted_acl | script | 3f06a66b3edbc36c6762cf414d4c402e33155b7133f95bc5d5415e2fb242a7a0
```

The six pipe-separated values map left-to-right to the six exact row fields. For both CC09 rows,
`source_file_sha256` equals the implementation-acceptance governed source row for
`services/api/src/mirror_api/demo_d02_r2_locator_custody.py` and `strict_utf8_script_sha256` is recomputed from that same
file. `accepted_cc09_implementation_sha` equals both the implementation acceptance `implementation_sha` and host
candidate `locator_custody_implementation_sha`; `accepted_r06_source_file_sha256` equals the fixed R06 SHA above.

`mirror.governance/PowerShellAclRuntimeProjection/v1` has exactly:

```text
schema_version
powershell_executable_identity_digest
powershell_version
windows_directory_identity_digest
windows_system_directory_identity_digest
module_root_directory_identity_digest
module_manifest_projection_digest
required_cmdlet_projection_digest
acl_bootstrap_script_projection_digest
ordered_loaded_member_identity_digests
runtime_projection_digest
```

The ordered member identities equal Security row 0, Utility row 0, Utility row 1, in that exact order. `powershell_version`
is canonical ASCII `Major.Minor.Build.Revision`, where each component is the invariant-culture unsigned decimal value
from the same child's `$PSVersionTable.PSVersion`; a missing/negative/non-integer component stops. It equals the host
candidate `powershell_version`, and the executable, three directory and three projection digests equal the same host
candidate and closure fields. The ACL child receives a
`PSModulePath` containing only the accepted module-root identity, imports Security by its accepted manifest and resolves
Utility only from that root. Profiles and all other roots are forbidden. The same-environment no-locator runtime
projection must bind both manifests, all three loaded members and all three cmdlet implementations before disclosure.

`mirror.governance/WindowsWfpEgressDenialContract/v1` has exactly:

```text
backend
session_flags
layers
condition
action
blocked_application_roles
remote_scope
local_scope
network_exemptions
filter_persistence
child_process_policy
install_order
verification
cleanup
key_derivation
key_namespace_uuid
session_key_role
provider_key_role
sublayer_key_role
filter_key_role_pattern
session_display_name
session_description_policy
session_txn_wait_timeout_ms
session_input_zero_null_policy
provider_display_name
provider_description_policy
provider_flags
provider_service_name
provider_data_binding
provider_data_encoding
sublayer_display_name
sublayer_description_policy
sublayer_flags
sublayer_weight
empty_provider_data_policy
filter_display_name_equation
filter_description_policy
filter_flags
filter_weight_type
filter_weight
match_type
condition_value_source
filter_condition_projection
filter_action_projection
filter_raw_context
filter_reserved_policy
caller_controlled_zero_null_policy
session_ownership_verification
object_correlation_verification
provider_sublayer_replay_verification
filter_replay_included_fields
filter_host_assigned_field_policy
probe_targets
collateral_scope
exclusive_window_policy
contract_version
```

Its frozen values are:

```text
backend = FWPUCLNT_DYNAMIC_WFP_SESSION_V1
session_flags = FWPM_SESSION_FLAG_DYNAMIC
layers = ALE_AUTH_CONNECT_V4|ALE_AUTH_CONNECT_V6
condition = ALE_APP_ID_EQUAL
action = FWP_ACTION_BLOCK
blocked_application_roles = DETACHED_PYTHON|GIT|POWERSHELL|CMD
remote_scope = ALL
local_scope = ALL
network_exemptions = NONE
filter_persistence = NON_PERSISTENT_DYNAMIC_SESSION
child_process_policy = JOB_OBJECT_ACTIVE_PROCESS_LIMIT_2_NO_BREAKAWAY
install_order = BEFORE_CHILD_CREATION_AND_LOCATOR_DISCLOSURE
verification = SESSION_ENUM_OBJECT_CORRELATION_FILTER_EXACT_REPLAY_AND_IPV4_IPV6_WSAEACCES_PROBE
cleanup = DELETE_OWN_DERIVED_FILTERS_SUBLAYER_PROVIDER_CLOSE_DYNAMIC_SESSION_AND_OBSERVER_VERIFY_ABSENT
key_derivation = RFC4122_UUIDV5_LOWERCASE_V1
key_namespace_uuid = 6ba7b811-9dad-11d1-80b4-00c04fd430c8
session_key_role = SESSION
provider_key_role = PROVIDER
sublayer_key_role = SUBLAYER
filter_key_role_pattern = FILTER:<DETACHED_PYTHON|GIT|POWERSHELL|CMD>:<V4|V6>
session_display_name = Project Mirror D02-R2 CC09 dynamic egress session
session_description_policy = NULL
session_txn_wait_timeout_ms = 0
session_input_zero_null_policy = processId=0|sid=NULL|username=NULL|kernelMode=FALSE
provider_display_name = Project Mirror D02-R2 CC09 dynamic egress provider
provider_description_policy = NULL
provider_flags = NONE
provider_service_name = NULL
provider_data_binding = locator_custody_implementation_acceptance_record_digest
provider_data_encoding = RAW_32_BYTES_DECODED_FROM_LOWER_HEX_SHA256
sublayer_display_name = Project Mirror D02-R2 CC09 dynamic egress sublayer
sublayer_description_policy = NULL
sublayer_flags = NONE
sublayer_weight = 65535
empty_provider_data_policy = size=0|data=NULL
filter_display_name_equation = "Project Mirror D02-R2 CC09 block " + application_role + " " + address_family
filter_description_policy = NULL
filter_flags = NONE
filter_weight_type = FWP_UINT64
filter_weight = 18446744073709551615
match_type = FWP_MATCH_EQUAL
condition_value_source = FwpmGetAppIdFromFileName0
filter_condition_projection = fieldKey=FWPM_CONDITION_ALE_APP_ID|matchType=FWP_MATCH_EQUAL|conditionValue.type=FWP_BYTE_BLOB_TYPE|conditionValue.bytes=exact_app_id_blob
filter_action_projection = type=FWP_ACTION_BLOCK|filterType=GUID_NULL
filter_raw_context = 0
filter_reserved_policy = NULL
caller_controlled_zero_null_policy = ZERO_INITIALIZE_ALL_WFP_STRUCTS_AND_REQUIRE_EVERY_UNLISTED_CALLER_FIELD_ZERO_OR_NULL
session_ownership_verification = FWPM_SESSION_ENUM_EXACT_KEY_PID_SID_DYNAMIC_USER_MODE
object_correlation_verification = PROVIDER_TO_SUBLAYER_TO_EXACT_EIGHT_FILTERS
provider_sublayer_replay_verification = GET_BY_DERIVED_KEY_EXACT_CALLER_CONTROLLED_PROJECTION
filter_replay_included_fields = filterKey|displayData|flags|providerKey|providerData|layerKey|subLayerKey|weight|numFilterConditions|filterCondition|action|rawContext|reserved
filter_host_assigned_field_policy = filterId excluded from caller projection but equals unique nonzero add-result ID; effectiveWeight excluded from caller projection but must equal FWP_UINT64 exact requested weight; pointer addresses excluded while pointed-to bytes are included
probe_targets = [192.0.2.1,2001:db8::1]
collateral_scope = ALL_HOST_PROCESSES_USING_THE_FOUR_ACCEPTED_EXECUTABLE_IMAGES
exclusive_window_policy = SERIALIZED_CC09_MAINTENANCE_WINDOW_WITH_SAME_IMAGE_COLLATERAL_EXPLICITLY_ACCEPTED
contract_version = P3_P7_D02_R2_WINDOWS_WFP_EGRESS_DENIAL_V1
```

The key namespace is UUID namespace URL `6ba7b811-9dad-11d1-80b4-00c04fd430c8`. Exact lower-case RFC-4122 UUIDv5
keys are derived as:

```text
base_uuid = uuid5(
  UUID_NAMESPACE_URL,
  "urn:project-mirror:p3-p7-d02-r2:cc09:wfp:v1:"
  + locator_custody_implementation_acceptance_record_digest
  + ":"
  + principal_sid_digest
)
object_uuid(role) = uuid5(base_uuid, role)
```

The fixed roles are `SESSION`, `PROVIDER`, `SUBLAYER` and the eight
`FILTER:<DETACHED_PYTHON|GIT|POWERSHELL|CMD>:<V4|V6>` roles. The exact filter display/layer/app rows are:

```text
Project Mirror D02-R2 CC09 block DETACHED_PYTHON V4 | FWPM_LAYER_ALE_AUTH_CONNECT_V4 | DETACHED_PYTHON
Project Mirror D02-R2 CC09 block DETACHED_PYTHON V6 | FWPM_LAYER_ALE_AUTH_CONNECT_V6 | DETACHED_PYTHON
Project Mirror D02-R2 CC09 block GIT V4 | FWPM_LAYER_ALE_AUTH_CONNECT_V4 | GIT
Project Mirror D02-R2 CC09 block GIT V6 | FWPM_LAYER_ALE_AUTH_CONNECT_V6 | GIT
Project Mirror D02-R2 CC09 block POWERSHELL V4 | FWPM_LAYER_ALE_AUTH_CONNECT_V4 | POWERSHELL
Project Mirror D02-R2 CC09 block POWERSHELL V6 | FWPM_LAYER_ALE_AUTH_CONNECT_V6 | POWERSHELL
Project Mirror D02-R2 CC09 block CMD V4 | FWPM_LAYER_ALE_AUTH_CONNECT_V4 | CMD
Project Mirror D02-R2 CC09 block CMD V6 | FWPM_LAYER_ALE_AUTH_CONNECT_V6 | CMD
```

The three pipe-separated values are exact display name, layer and accepted executable role. All descriptions are NULL.
Provider data is exactly 32 bytes decoded from the acceptance record's 64 lower-hex digest; sublayer/filter provider
data are exact empty blobs. Every ctypes structure is zero-initialized, and every caller-controlled field not listed in
the contract must remain zero/NULL. Pointer addresses never enter canonical comparison; exact pointed-to GUID, SID,
UTF-16 string and blob bytes do.

Session ownership is proven only when `FwpmSessionEnum0` returns exactly one row matching the derived `sessionKey`,
current Principal PID, current process-token SID, `FWPM_SESSION_FLAG_DYNAMIC` and `kernelMode=FALSE`. Input session
process/SID/username fields are zero/NULL and the enumerated host fields are verification outputs. The same engine
transaction creates the provider, sublayer and eight filters. `FwpmProviderGetByKey0` and `FwpmSubLayerGetByKey0`
replay every caller-controlled field; every filter repeats the provider and sublayer keys.

`FwpmFilterGetById0` canonical replay includes the exact fields named by `filter_replay_included_fields`, recursively
compares pointed-to content, and excludes only pointer addresses plus host-assigned `filterId` and `effectiveWeight`.
The returned ID must equal the unique nonzero `FwpmFilterAdd0` ID for that role; returned effective weight must equal the
exact requested `FWP_UINT64` value. Thus it proves the caller-controlled filter projection, not session ownership.
Session, provider, sublayer and all eight filter proofs must correlate before any probe or disclosure.

This WFP denial is image-wide, with `collateral_scope=ALL_HOST_PROCESSES_USING_THE_FOUR_ACCEPTED_EXECUTABLE_IMAGES` and
`exclusive_window_policy=SERIALIZED_CC09_MAINTENANCE_WINDOW_WITH_SAME_IMAGE_COLLATERAL_EXPLICITLY_ACCEPTED`. The bridge
needs no network, but the Principal must enter an exclusive maintenance window in which no other Demo task may require
those images. Same-image unrelated processes can be affected and are not claimed unaffected; processes using other
images, including the local service topology, are outside these app-ID filters.

`mirror.governance/ProjectPrivateHomeResolverContract/v1` has exactly:

```text
platform
known_folder_guid
known_folder_api
known_folder_flags
code_cache_relative_component
ordered_project_relative_components
control_plane_relative_root
evidence_relative_root
bridge_scratch_relative_root
known_folder_boundary_contract_digest
restricted_ancestor_acl_contract_digest
canonicalization_version
```

with frozen literals:

```text
platform = WINDOWS_LOCAL_DEMO
known_folder_guid = F1B32785-6FBA-4FCF-9D55-7B8E7F157091
known_folder_api = SHGetKnownFolderPath
known_folder_flags = KF_FLAG_DEFAULT
code_cache_relative_component = ProjectMirror-code-cache-v1
ordered_project_relative_components = [ProjectMirror, principal-private-output-v1]
control_plane_relative_root = control-plane/p3-p7-d02-r2-locator-custody-v1
evidence_relative_root = d02-r2-evidence/p3-p7-d02-r2-cc08-e1-evidence
bridge_scratch_relative_root = bridge-scratch-v1
known_folder_boundary_contract_digest = exact WindowsKnownFolderBoundaryContract/v1 digest
restricted_ancestor_acl_contract_digest = exact WindowsRestrictedAncestorAclContract/v1 digest
canonicalization_version = demo-canonical-json-v1
```

Windows-directory authority is frozen independently of environment text:

```text
windows_directory = GetWindowsDirectoryW()
windows_system_directory = GetSystemDirectoryW()
parent_identity(windows_system_directory) = windows_directory_identity_digest
same_volume(windows_directory, windows_system_directory) = TRUE
SystemRoot = exact absolute text returned by GetWindowsDirectoryW()
WINDIR = exact absolute text returned by GetWindowsDirectoryW()
ComSpec = handle-validated windows_system_directory/cmd.exe
PowerShell = handle-validated windows_system_directory/WindowsPowerShell/v1.0/powershell.exe
PSModulePath = handle-validated windows_system_directory/WindowsPowerShell/v1.0/Modules
```

The system-directory result is never assigned directly to `SystemRoot` or `WINDIR`. The directory, system-directory and
PowerShell-module-root handles replay roles `WINDOWS_DIRECTORY`, `WINDOWS_SYSTEM_DIRECTORY` and
`POWERSHELL_MODULE_ROOT`; parent/volume mismatch stops.

### Windows host-binding candidate and acceptance

The read-only tracked candidate uses schema `mirror.demo/D02R2WindowsHostBindingCandidate/v1` and exactly:

```text
schema_version
authority_id
change_control_id
private_home_handle_id
resolver_contract_digest
principal_sid_digest
known_folder_identity_digest
known_folder_boundary_contract_digest
restricted_ancestor_acl_contract_digest
project_container_precondition
project_code_cache_precondition
project_code_checkout_resolver_contract_digest
python_runtime_identity_digest
python_runtime_file_sha256
python_runtime_version
git_executable_identity_digest
git_executable_file_sha256
windows_directory_identity_digest
windows_system_directory_identity_digest
ntdll_library_identity_digest
ntdll_library_file_sha256
kernel32_library_identity_digest
kernel32_library_file_sha256
advapi32_library_identity_digest
advapi32_library_file_sha256
fwpuclnt_library_identity_digest
fwpuclnt_library_file_sha256
powershell_executable_identity_digest
powershell_executable_file_sha256
powershell_version
cmd_executable_identity_digest
cmd_executable_file_sha256
powershell_module_root_directory_identity_digest
powershell_module_manifest_projection_digest
powershell_required_cmdlet_projection_digest
powershell_acl_bootstrap_script_projection_digest
powershell_acl_runtime_projection_digest
powershell_acl_module_closure_digest
native_relative_create_contract_digest
protected_directory_dacl_contract_digest
wfp_egress_denial_contract_digest
locator_custody_implementation_sha
locator_custody_implementation_acceptance_record_digest
observed_at_utc
record_digest
```

The frozen candidate path is
`docs/operations/P3_P7_D02_R2_WINDOWS_HOST_BINDING_CANDIDATE.json`. The frozen literals are
`authority_id=P3_P7_D02_R2_WINDOWS_HOST_BINDING_AUTHORITY_01`,
`change_control_id=P3_P7_D02_CC_09` and `private_home_handle_id=PM_PROJECT_MIRROR_PRIVATE_HOME_V1`. Its physical
preimages are obtained without creating a directory; only their typed digests enter the candidate.
`project_container_precondition=ABSENT_CREATE_NEW` and `project_code_cache_precondition=ABSENT_CREATE_NEW` are the sole
revision-8 candidate modes. A pre-existing `ProjectMirror` or `ProjectMirror-code-cache-v1` at initial candidate
projection is not adopted and stops. The Known Folder, Windows Directory, Windows System Directory and PowerShell
module-root digests are `WindowsPathIdentity/v1` values under their exact roles; a digest under another role cannot
substitute. The candidate's boundary/ACL, checkout-resolver, four PowerShell projection, module-closure, native-create,
protected-DACL and WFP digests must each equal a freshly replayed exact contract object. The closure's four projection
fields must equal the four corresponding candidate fields, and its Windows-directory, system-directory and module-root
fields must equal the candidate fields. Every manifest/member/cmdlet/script/runtime identity is represented once by its
typed projection; ambiguous duplicate `*_nested_module_identity_digest` fields are forbidden.

Host acceptance uses schema `mirror.demo/D02R2WindowsHostBindingAcceptance/v1` and exactly:

```text
schema_version
authority_id
change_control_id
accepted_candidate_sha
accepted_candidate_tree
accepted_candidate_path
accepted_candidate_git_blob_oid
accepted_candidate_file_sha256
accepted_candidate_record_digest
accepted_plan_acceptance_record_digest
locator_custody_implementation_acceptance_record_digest
independent_review
same_sha_ci
principal_acceptance
authorized_scope
prohibited_scope
record_created_at_utc
record_digest
```

`accepted_candidate_path` is the fixed repository-relative tracked candidate path, never a host path. Review/CI and
Principal objects use the frozen shapes above, substituting `reviewed_candidate_sha` and `accepted_candidate_sha` for
their SHA key. Its scopes are:

`authority_id=P3_P7_D02_R2_WINDOWS_HOST_BINDING_ACCEPTANCE_01` and
`accepted_candidate_path=docs/operations/P3_P7_D02_R2_WINDOWS_HOST_BINDING_CANDIDATE.json`. The
`independent_review` object has exactly `evidence_digest`, `findings_p0`, `findings_p1`, `findings_p2`, `findings_p3`,
`result`, `review_task_id`, `reviewed_candidate_sha`; `same_sha_ci` has the exact eight-key shape and literals frozen
above; `principal_acceptance` has exactly `status`, `accepted_candidate_sha`, `accepted_at_utc`,
`acceptance_authority_digest`, with `status=PRINCIPAL_ACCEPTED` and timestamps equal.

```text
authorized_scope = CREATE_EXACT_CODE_CACHE_AND_TWO_COMPONENT_PRIVATE_HOME_CANDIDATES_AND_RECEIPTS_ONLY
prohibited_scope =
  [
    LOCATOR_NAMESPACE_CREATION,
    LOCATOR_EVENT_CREATION,
    CC08_EVIDENCE_ROOT_CREATION,
    R05_REHOME,
    SOURCE_GENERATION,
    M3_M4_EXECUTION,
    POSTGRESQL_ADMISSION,
    FORMAL_PHASE_AUTHORITY,
    PRODUCTION_RELEASE
  ]
```

For host acceptance, let `B` be the exact Git blob bytes at
`accepted_candidate_sha:accepted_candidate_path` and `O` be the strict canonical parse of `B`. Acceptance requires all
of these byte equations simultaneously:

```text
accepted_candidate_tree = git rev-parse accepted_candidate_sha^{tree}
accepted_candidate_git_blob_oid = git hash-object(B)
accepted_candidate_file_sha256 = sha256(B)
accepted_candidate_record_digest = O.record_digest
accepted_candidate_record_digest = TD(candidate_schema, O excluding only record_digest)
independent_review.reviewed_candidate_sha = accepted_candidate_sha
same_sha_ci.head_sha = accepted_candidate_sha
principal_acceptance.accepted_candidate_sha = accepted_candidate_sha
principal_acceptance.accepted_at_utc = record_created_at_utc
```

Commit, tree, path, blob, file SHA-256, typed record, review, CI or Principal evidence from different bytes stops.

### Accepted R06 code cache and checkout seal

`mirror.governance/ProjectCodeCheckoutResolverContract/v1` has exactly:

```text
known_folder_role = KNOWN_FOLDER
code_cache_component = ProjectMirror-code-cache-v1
checkout_component = accepted-r06-ab08a6e861ec
source = CURRENT_ACCEPTED_CC09_REPOSITORY_ONLY
destination_creation = HANDLE_RELATIVE_NATIVE_CREATE_EMPTY_DIRECTORY_WITH_PROTECTED_DACL
clone_command = git clone --local --no-hardlinks --no-checkout --no-tags <source> .
remote_cleanup_command = git remote remove origin
required_ref = refs/remotes/origin/codex/p3-p7-core-demo
required_ref_target = 3c743cdf5167bf3484be98b4f50e0ea6c77c5f13
required_ref_recreation = git update-ref refs/remotes/origin/codex/p3-p7-core-demo 3c743cdf5167bf3484be98b4f50e0ea6c77c5f13
checkout_command = git checkout --detach ab08a6e861ec364c62a6ab3dcf46a69483f1b741
detached_head = ab08a6e861ec364c62a6ab3dcf46a69483f1b741
network = FORBIDDEN
partial_checkout = PRESERVE_AND_STOP
cleanup = NO_DELETE_WITHOUT_FORWARD_CHANGE_CONTROL
contract_version = P3_P7_D02_R2_PROJECT_CODE_CHECKOUT_RESOLVER_V1
```

The Principal creates the cache and checkout components handle-relative under the accepted LocalAppData handle with
the protected DACL already present. Git runs with cwd `.` only after the checkout directory is proven empty. Immediately
after the local clone it removes `origin`, recreates the fixed remote-tracking ref by object ID, checks out the accepted
R06 SHA detached, verifies its tree/governed blobs and proves `.git/config` contains no source absolute path. This is
public code only and must complete before any private locator disclosure. Existing, directory-only, partial, replaced or
corrupt cache/checkout state is preserved and stopped; it is never repaired or deleted in place.

The cache component's first file is `PROJECT_MIRROR_CODE_CACHE_NAME_RECEIPT.json`, schema
`mirror.governance/ProjectCodeCacheNameReceipt/v1`, with exactly:

```text
schema_version
project_id
code_cache_handle_id
purpose
resolver_contract_digest
host_binding_acceptance_record_digest
principal_sid_digest
known_folder_identity_digest
code_cache_identity_digest
protected_directory_dacl_contract_digest
allowed_checkout_component
locator_custody_implementation_sha
locator_custody_implementation_acceptance_record_digest
retention_policy
cleanup_policy
created_at_utc
receipt_digest
```

Its literals include `project_id=PROJECT_MIRROR`, `code_cache_handle_id=PM_PROJECT_MIRROR_CODE_CACHE_V1`,
`purpose=PUBLIC_CODE_ONLY_CC09_ACCEPTED_R06_CHECKOUT`, `allowed_checkout_component=accepted-r06-ab08a6e861ec`, and
`created_at_utc=WindowsHostBindingAcceptance.record_created_at_utc`. `resolver_contract_digest` is the exact
`ProjectCodeCheckoutResolverContract/v1` digest. Its directory identity uses role `PROJECT_CODE_CACHE`.

After detached checkout replay, the checkout's first and only at-rest control file outside `.git` and accepted tracked
code is `PROJECT_MIRROR_ACCEPTED_R06_CHECKOUT_SEAL_RECEIPT.json`, schema
`mirror.governance/AcceptedR06CheckoutSealReceipt/v1`, with exactly:

```text
schema_version
project_id
checkout_handle_id
purpose
resolver_contract_digest
host_binding_acceptance_record_digest
principal_sid_digest
known_folder_identity_digest
code_cache_identity_digest
code_cache_name_receipt_digest
checkout_identity_digest
protected_directory_dacl_contract_digest
accepted_git_executable_identity_digest
accepted_git_executable_file_sha256
head_sha
head_tree
required_ref
required_ref_target
accepted_r06_implementation_sha
accepted_r06_implementation_tree
accepted_r06_acceptance_checkpoint_sha
accepted_r06_acceptance_record_digest
accepted_r06_governed_rows
retention_policy
cleanup_policy
created_at_utc
receipt_digest
```

Each ordered `accepted_r06_governed_rows` item has exactly `path`, `git_blob_oid` and `sha256` and repeats the governed
rows frozen above. The checkout identity uses role `ACCEPTED_R06_CHECKOUT`; `head_sha`, `head_tree`, required ref/target,
R06 implementation/tree/checkpoint/acceptance and Git executable values equal the accepted authorities. The receipt
contains no source or destination absolute path. Its `resolver_contract_digest` equals the same checkout-resolver
contract, and `created_at_utc` equals the host-binding acceptance timestamp.

### Private-home name receipt, binding candidate and acceptance

The first and only control object permitted in a newly created `ProjectMirror` container before the second component is
created is `PROJECT_MIRROR_CONTAINER_NAME_RECEIPT.json`, schema
`mirror.governance/ProjectMirrorContainerNameReceipt/v1`, with exactly:

```text
schema_version
project_id
project_container_handle_id
purpose
resolver_contract_digest
host_binding_acceptance_record_digest
principal_sid_digest
known_folder_identity_digest
project_container_identity_digest
protected_directory_dacl_contract_digest
allowed_next_component
locator_custody_implementation_sha
locator_custody_implementation_acceptance_record_digest
retention_policy
cleanup_policy
created_at_utc
receipt_digest
```

Its literals are `project_id=PROJECT_MIRROR`, `project_container_handle_id=PM_PROJECT_MIRROR_CONTAINER_V1`,
`purpose=PROJECT_MIRROR_PRINCIPAL_PRIVATE_OUTPUT_CONTAINER_ONLY`,
`allowed_next_component=principal-private-output-v1`, the same retention/cleanup literals used below and the exact
accepted host/implementation/digest values. `project_container_identity_digest` is a
`WindowsPathIdentity/v1` digest with role `PROJECT_CONTAINER`. The protected DACL is supplied at handle-relative
creation and must replay before and after the receipt's durability barrier.
`ProjectMirrorContainerNameReceipt.created_at_utc` equals the already accepted
`WindowsHostBindingAcceptance.record_created_at_utc`; execution-time wall clock is forbidden.

The first and only object permitted in a newly created private-home candidate is
`PROJECT_MIRROR_PRIVATE_HOME_NAME_RECEIPT.json`, schema
`mirror.governance/ProjectPrivateHomeNameReceipt/v1`, with exactly:

```text
schema_version
project_id
private_home_handle_id
purpose
resolver_contract_digest
host_binding_acceptance_record_digest
principal_sid_digest
known_folder_identity_digest
project_container_identity_digest
project_container_name_receipt_digest
private_home_identity_digest
protected_directory_dacl_contract_digest
allowed_subject_root_ids
locator_custody_implementation_sha
locator_custody_implementation_acceptance_record_digest
retention_policy
cleanup_policy
created_at_utc
receipt_digest
```

Its literals are:

```text
project_id = PROJECT_MIRROR
purpose = PRINCIPAL_PRIVATE_OUTPUT_CONTROL_AND_D02_R2_CUSTODY_ONLY
allowed_subject_root_ids = [P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT]
retention_policy = RETAIN_UNTIL_D02_R2_AND_ALL_DEPENDENT_TASKS_RELEASE_CUSTODY
cleanup_policy = PRINCIPAL_EXACT_DEPENDENCY_SCAN_AND_FORWARD_CHANGE_CONTROL_REQUIRED
created_at_utc = WindowsHostBindingAcceptance.record_created_at_utc
```

Both component receipts use that one pre-existing host-acceptance timestamp. A different component timestamp, a
host-acceptance timestamp mismatch or an otherwise valid self-digest around an unbound timestamp is rejected.

The tracked candidate uses schema `mirror.demo/D02R2PrivateHomeBindingCandidate/v1` and exactly:

```text
schema_version
authority_id
change_control_id
private_home_handle_id
host_binding_acceptance_record_digest
resolver_contract_digest
principal_sid_digest
known_folder_identity_digest
project_container_identity_digest
project_container_name_receipt_digest
private_home_identity_digest
private_home_name_receipt_digest
protected_directory_dacl_contract_digest
locator_custody_implementation_acceptance_record_digest
observed_at_utc
record_digest
```

Its frozen path is `docs/operations/P3_P7_D02_R2_PRIVATE_HOME_BINDING_CANDIDATE.json` and its authority ID is
`P3_P7_D02_R2_PRIVATE_HOME_BINDING_AUTHORITY_01`. The tracked candidate contains no absolute path, raw SID, volume
serial or file ID.

Private-home acceptance uses schema `mirror.demo/D02R2PrivateHomeBindingAcceptance/v1` and exactly:

```text
schema_version
authority_id
change_control_id
accepted_candidate_sha
accepted_candidate_tree
accepted_candidate_path
accepted_candidate_git_blob_oid
accepted_candidate_file_sha256
accepted_candidate_record_digest
accepted_plan_acceptance_record_digest
locator_custody_implementation_acceptance_record_digest
host_binding_acceptance_record_digest
project_container_name_receipt_digest
private_home_name_receipt_digest
independent_review
same_sha_ci
principal_acceptance
authorized_scope
prohibited_scope
record_created_at_utc
record_digest
```

`authority_id=P3_P7_D02_R2_PRIVATE_HOME_BINDING_ACCEPTANCE_01` and
`accepted_candidate_path=docs/operations/P3_P7_D02_R2_PRIVATE_HOME_BINDING_CANDIDATE.json`. Its review, CI and
Principal objects have exactly the same key sets and equality rules as host acceptance. Its frozen scopes are:

```text
authorized_scope = OPEN_EXACT_PRIVATE_HOME_FOR_RECEIPT_BOUND_BRIDGE_SCRATCH_AND_CC09_LOCATOR_CUSTODY_ONLY
prohibited_scope =
  [
    ALTERNATE_PRIVATE_HOME,
    PRIVATE_HOME_REBIND,
    SECOND_LOCATOR_NAMESPACE,
    SECOND_EVIDENCE_ROOT,
    SOURCE_GENERATION,
    M3_M4_EXECUTION,
    POSTGRESQL_ADMISSION,
    FORMAL_PHASE_AUTHORITY,
    PRODUCTION_RELEASE
  ]
```

For private-home acceptance, `B` and `O` use the same exact Git-byte definition and every host-acceptance equation above
applies with the private-home candidate schema. In addition:

```text
host_binding_acceptance_record_digest = candidate.host_binding_acceptance_record_digest
project_container_name_receipt_digest = candidate.project_container_name_receipt_digest
project_container_name_receipt_digest = replayed physical container receipt digest
private_home_name_receipt_digest = candidate.private_home_name_receipt_digest
private_home_name_receipt_digest = replayed physical private-home receipt digest
```

The physically replayed receipts must also reproduce their self-digests, host-acceptance timestamp, identities, DACLs
and implementation authority. A candidate scalar never substitutes for the immutable receipt bytes.

After private-home acceptance, the Principal creates exactly `bridge-scratch-v1` handle-relative under the accepted
private home, with the protected DACL at creation. Its first file is
`PROJECT_MIRROR_CC09_BRIDGE_SCRATCH_NAME_RECEIPT.json`, schema
`mirror.governance/ProjectPrivateBridgeScratchNameReceipt/v1`, with exactly:

```text
schema_version
project_id
bridge_scratch_handle_id
purpose
private_home_binding_acceptance_record_digest
host_binding_acceptance_record_digest
principal_sid_digest
private_home_identity_digest
bridge_scratch_identity_digest
protected_directory_dacl_contract_digest
locator_custody_implementation_sha
locator_custody_implementation_acceptance_record_digest
at_rest_policy
locator_session_policy
crash_residue_policy
retention_policy
cleanup_policy
created_at_utc
receipt_digest
```

Its literals are `project_id=PROJECT_MIRROR`, `bridge_scratch_handle_id=PM_PROJECT_MIRROR_CC09_BRIDGE_SCRATCH_V1`,
`purpose=CC09_RECEIPT_BOUND_PRIVATE_TEMP_ONLY`, `at_rest_policy=RECEIPT_ONLY`,
`locator_session_policy=RECEIPT_ONLY_BEFORE_AND_AFTER_EVERY_LOCATOR_SESSION`,
`crash_residue_policy=PRESERVE_AND_STOP` and
`created_at_utc=WindowsHostBindingAcceptance.record_created_at_utc`. Its identity role is `BRIDGE_SCRATCH`. Only the
detached child may use this directory as `TEMP`/`TMP` during its lifetime. Every locator session requires receipt-only
state before disclosure and after child exit; any crash residue, unknown object, replacement or directory-only state is
preserved as `BRIDGE_SCRATCH_RESIDUE_STOP`, never cleaned automatically.

After acceptance, deletion, replacement, redirection or physical-identity drift is a permanent fail-closed state. It
does not reopen candidate bootstrap and never authorizes a second private home.

`schema_contract_digest` is the typed digest under `mirror.demo/D02R2LocatorCustodySchemaContract/v1` of this exact
payload and no other key:

```json
{
  "bridge_decision_policy_version": "P3_P7_D02_R2_LOCATOR_BRIDGE_DECISIONS_V1",
  "canonicalization_version": "demo-canonical-json-v1",
  "ordered_schema_versions": [
    "mirror.demo/D02R2LocatorCustodySchemaContract/v1",
    "mirror.demo/D02R2LocatorCustodyPlanAcceptance/v1",
    "mirror.demo/D02R2LocatorCustodyImplementationAcceptance/v1",
    "mirror.governance/WindowsPrincipalSid/v1",
    "mirror.governance/WindowsExecutableIdentity/v1",
    "mirror.governance/WindowsFileIdentity/v1",
    "mirror.governance/WindowsPathIdentity/v1",
    "mirror.governance/WindowsNativeRelativeCreateContract/v1",
    "mirror.governance/WindowsProtectedDirectoryDaclContract/v1",
    "mirror.governance/WindowsRestrictedAncestorAclContract/v1",
    "mirror.governance/WindowsKnownFolderBoundaryContract/v1",
    "mirror.governance/ProjectPrivateHomeResolverContract/v1",
    "mirror.governance/PowerShellModuleManifestProjection/v1",
    "mirror.governance/PowerShellRequiredCmdletProjection/v1",
    "mirror.governance/PowerShellAclBootstrapScriptProjection/v1",
    "mirror.governance/PowerShellAclRuntimeProjection/v1",
    "mirror.governance/PowerShellAclModuleClosure/v1",
    "mirror.governance/WindowsWfpEgressDenialContract/v1",
    "mirror.governance/ProjectCodeCheckoutResolverContract/v1",
    "mirror.governance/ProjectCodeCacheNameReceipt/v1",
    "mirror.governance/AcceptedR06CheckoutSealReceipt/v1",
    "mirror.governance/ProjectPrivateBridgeScratchNameReceipt/v1",
    "mirror.demo/D02R2WindowsHostBindingCandidate/v1",
    "mirror.demo/D02R2WindowsHostBindingAcceptance/v1",
    "mirror.governance/ProjectMirrorContainerNameReceipt/v1",
    "mirror.governance/ProjectPrivateHomeNameReceipt/v1",
    "mirror.demo/D02R2PrivateHomeBindingCandidate/v1",
    "mirror.demo/D02R2PrivateHomeBindingAcceptance/v1",
    "mirror.governance/ProjectPrivateOutputRegistryNamespaceNameReceipt/v1",
    "mirror.demo/D02R2LocatorCustodyCommonGenesis/v1",
    "mirror.demo/D02R2LocatorCustodyCopyGenesisReceipt/v1",
    "mirror.demo/D02R2EvidenceRootLocator/v1",
    "mirror.demo/D02R2EvidenceRootLocatorNameReceipt/v1",
    "mirror.governance/ExcludedGitWorktreeIdentitySet/v1",
    "mirror.demo/D02R2LocatorCustodyTransactionId/v1",
    "mirror.demo/D02R2EvidenceRootLocatorCustodyEvent/v1",
    "mirror.demo/D02R2LocatorCustodyTransactionIntent/v1",
    "mirror.demo/D02R2LocatorCustodySemanticSnapshot/v1",
    "mirror.demo/D02R2LocatorCustodyCommitReceipt/v1",
    "mirror.demo/D02R2R05EvidenceRehomeManifest/v1",
    "mirror.demo/D02R2ActualRootDigestBindingAddendum/v1",
    "mirror.demo/D02R2ActualRootDigestBindingAddendumAcceptance/v1"
  ],
  "relative_control_manifest": [
    {
      "control_class": "NAMESPACE_NAME_RECEIPT",
      "logical_name_pattern": "^PROJECT_MIRROR_PRIVATE_OUTPUT_REGISTRY_NAMESPACE_NAME_RECEIPT[.]json$",
      "maximum_bytes": 262144,
      "mutability": "CREATE_NEW_IMMUTABLE",
      "relative_destination": "."
    },
    {
      "control_class": "COPY_A_GENESIS",
      "logical_name_pattern": "^D02_R2_LOCATOR_CUSTODY_COPY_GENESIS[.]json$",
      "maximum_bytes": 262144,
      "mutability": "CREATE_NEW_IMMUTABLE",
      "relative_destination": "copy-a"
    },
    {
      "control_class": "COPY_B_GENESIS",
      "logical_name_pattern": "^D02_R2_LOCATOR_CUSTODY_COPY_GENESIS[.]json$",
      "maximum_bytes": 262144,
      "mutability": "CREATE_NEW_IMMUTABLE",
      "relative_destination": "copy-b"
    },
    {
      "control_class": "COPY_A_EVENT",
      "logical_name_pattern": "^D02_R2_LOCATOR_CUSTODY_EVENT__[0-9]{8}__[0-9a-f]{64}[.]json$",
      "maximum_bytes": 262144,
      "mutability": "CREATE_NEW_IMMUTABLE",
      "relative_destination": "copy-a/events"
    },
    {
      "control_class": "COPY_B_EVENT",
      "logical_name_pattern": "^D02_R2_LOCATOR_CUSTODY_EVENT__[0-9]{8}__[0-9a-f]{64}[.]json$",
      "maximum_bytes": 262144,
      "mutability": "CREATE_NEW_IMMUTABLE",
      "relative_destination": "copy-b/events"
    },
    {
      "control_class": "LOCATOR_NAME_RECEIPT",
      "logical_name_pattern": "^D02_R2_EVIDENCE_ROOT_LOCATOR_NAME_RECEIPT[.]json$",
      "maximum_bytes": 262144,
      "mutability": "CREATE_NEW_IMMUTABLE",
      "relative_destination": "allocations/P3_P7_D02_R2_CC08_E1_ROOT_LOCATOR_ALLOCATION"
    },
    {
      "control_class": "TRANSACTION_INTENT",
      "logical_name_pattern": "^D02_R2_LOCATOR_CUSTODY_INTENT__[0-9a-f]{64}[.]json$",
      "maximum_bytes": 262144,
      "mutability": "CREATE_NEW_IMMUTABLE",
      "relative_destination": "transactions/intents"
    },
    {
      "control_class": "TRANSACTION_COMMIT",
      "logical_name_pattern": "^D02_R2_LOCATOR_CUSTODY_COMMIT__[0-9a-f]{64}[.]json$",
      "maximum_bytes": 262144,
      "mutability": "CREATE_NEW_IMMUTABLE",
      "relative_destination": "transactions/commits"
    }
  ],
  "timestamp_policy_version": "P3_P7_D02_R2_LOCATOR_TIMESTAMPS_V1",
  "transition_matrix_version": "P3_P7_D02_R2_LOCATOR_TRANSITIONS_V1"
}
```

The six keys, 42-member schema array and eight manifest rows are byte-for-byte the literals shown; all 42 entries are
unique and the schema contract itself is a member of its own closed ordered authority list.

## Fixed Project Mirror private-home resolver

```text
PLATFORM: WINDOWS_LOCAL_DEMO
KNOWN_FOLDER: FOLDERID_LocalAppData
KNOWN_FOLDER_GUID: F1B32785-6FBA-4FCF-9D55-7B8E7F157091
KNOWN_FOLDER_API: SHGetKnownFolderPath
KNOWN_FOLDER_FLAGS: KF_FLAG_DEFAULT
CODE_CACHE_COMPONENT: ProjectMirror-code-cache-v1
CODE_CACHE_FIRST_FILE: PROJECT_MIRROR_CODE_CACHE_NAME_RECEIPT.json
ACCEPTED_R06_CHECKOUT_COMPONENT: accepted-r06-ab08a6e861ec
ACCEPTED_R06_CHECKOUT_SEAL: PROJECT_MIRROR_ACCEPTED_R06_CHECKOUT_SEAL_RECEIPT.json
PROJECT_RELATIVE_SUFFIX: ProjectMirror/principal-private-output-v1
PROJECT_SUFFIX_STATE_MACHINE_VERSION: P3_P7_D02_R2_PROJECT_MIRROR_TWO_COMPONENT_V1
CONTROL_PLANE_RELATIVE_ROOT: control-plane/p3-p7-d02-r2-locator-custody-v1
D02_EVIDENCE_DESTINATION_CLASS: D02_R2_CC08_E1_EVIDENCE
D02_EVIDENCE_RELATIVE_ROOT: d02-r2-evidence/p3-p7-d02-r2-cc08-e1-evidence
KNOWN_FOLDER_REDIRECTION_POLICY_VERSION: P3_P7_D02_R2_WINDOWS_KNOWN_FOLDER_BOUNDARY_V1
PROJECT_CONTAINER_FIRST_FILE: PROJECT_MIRROR_CONTAINER_NAME_RECEIPT.json
PRIVATE_HOME_FIRST_FILE: PROJECT_MIRROR_PRIVATE_HOME_NAME_RECEIPT.json
BRIDGE_SCRATCH_RELATIVE_ROOT: bridge-scratch-v1
BRIDGE_SCRATCH_FIRST_FILE: PROJECT_MIRROR_CC09_BRIDGE_SCRATCH_NAME_RECEIPT.json
MINIMUM_FREE_BYTES: 42949672960
```

This fixed Project Mirror directory is the specified Git-external folder for all new D02-R2 private receipts and
evidence. The resolver accepts no path, drive, suffix, candidate list, fallback, current working directory, CLI flag or
ordinary environment-variable override. An internal test seam may supply a synthetic Known Folder result; the real
entry point cannot.

Before any directory creation, the Principal produces a read-only host projection from the current process token and
`SHGetKnownFolderPath(FOLDERID_LocalAppData, KF_FLAG_DEFAULT, token=NULL)`. It opens the Known Folder and every existing
suffix ancestor separately with `FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT`; from each still-open handle
it reads `FILE_ID_INFO` and `FILE_ATTRIBUTE_TAG_INFO`, requires a fixed local volume, directory type, no reparse bit and
`ReparseTag=0`, and validates `WindowsRestrictedAncestorAclContract/v1` from each still-open handle. It also resolves
`FOLDERID_Profile`, proves the default handle-relative `Profile/AppData/Local` identity relationship, rejects the frozen
Cloud Files attributes and enumerates `HKCU\Software\Microsoft\OneDrive\Accounts\*\UserFolder` under the exact boundary
contract. UNC, device/network namespaces, detectable Known Folder redirection, Cloud Files, OneDrive containment, an
unreadable existing OneDrive account or an unprovable boundary stops as `PRIVATE_HOME_BOUNDARY_INVALID_STOP`.
Universal third-party synchronization absence is explicitly not claimed. Detection occurs in the Principal parent and
does not depend on variables cleared from the detached child.

The two suffix components are independent durable stages. All of the following child creates are handle-relative to a
still-open no-delete-share parent handle and receive the exact protected DACL at creation; existing ACLs are never
modified. The non-circular first-use sequence is:

```text
read-only host projection
-> tracked host-binding candidate
-> independent exact review + candidate-SHA CI
-> tracked host-binding acceptance
-> handle-relative create ProjectMirror-code-cache-v1 + immutable cache receipt
-> handle-relative local clone into accepted-r06-ab08a6e861ec
-> remove origin, recreate fixed ref, detached checkout + immutable checkout seal
-> handle-relative create ProjectMirror with a protected DACL at creation
-> first file PROJECT_MIRROR_CONTAINER_NAME_RECEIPT.json
-> handle-relative create principal-private-output-v1 with the same protected DACL at creation
-> first file PROJECT_MIRROR_PRIVATE_HOME_NAME_RECEIPT.json
-> tracked private-home binding candidate
-> independent exact review + candidate-SHA CI
-> tracked private-home binding acceptance
-> handle-relative create bridge-scratch-v1 + immutable scratch receipt
-> namespace bootstrap
```

The exact two-component bootstrap state table is:

| observed state                                                                                                 | unique action                                                                                                                                                             |
| -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| both suffix components absent before host candidate                                                            | record `ABSENT_CREATE_NEW`; after host acceptance create `ProjectMirror`, durably write its receipt, create `principal-private-output-v1`, then durably write its receipt |
| `ProjectMirror` exists at initial host candidate                                                               | `PRIVATE_HOME_PROJECT_COMPONENT_UNBOUND_STOP`; never adopt it                                                                                                             |
| `ProjectMirror` exists after host acceptance without the exact container receipt                               | `PRIVATE_HOME_PROJECT_COMPONENT_UNBOUND_STOP`; preserve and stop                                                                                                          |
| exact container receipt and second component absent                                                            | create only the second component and its receipt                                                                                                                          |
| second component exists without the exact private-home receipt                                                 | `PRIVATE_HOME_DIRECTORY_ONLY_STOP`; preserve and stop                                                                                                                     |
| both receipts, DACLs and physical identities replay exactly                                                    | create or replay only the tracked private-home binding candidate                                                                                                          |
| receipt/identity/DACL mismatch, reparse, reversed stage, unknown object or extra pre-acceptance control object | preserve and stop                                                                                                                                                         |

A crash between a directory create and its corresponding first-file receipt intentionally becomes a preserve-and-stop
state; availability does not authorize adoption. Only a directory plus its exact durable receipt is a recoverable
prefix. `ProjectMirror` may contain only its receipt and the fixed second component; before private-home acceptance the
second component may contain only its receipt.

The code cache follows the same create-new-only rule independently: a pre-existing cache at host projection, a
directory-only cache or checkout, a missing/changed receipt, wrong HEAD/tree/ref, retained origin URL, unexpected file
or partial clone is preserved and stopped. After private-home acceptance, bridge scratch follows the same
directory-plus-first-receipt rule and must be receipt-only at rest. Neither code cache nor scratch may be repaired,
rebound, suffixed or automatically cleaned.

CC09 never modifies an existing `ProjectMirror`, private-home or ancestor ACL. The byte-identical accepted CC08 bridge
remains authorized to apply its existing one-time ACL hardening to the newly created CC08 evidence root, then verify
that ACL. No other post-create ACL mutation is authorized. Before every namespace or root action, the Principal reopens
all boundaries and requires the accepted principal-SID, Known Folder, project-container and private-home identity/DACL
digests. After private-home binding acceptance, a missing/replaced/redirection identity is a permanent fail-closed
state; it cannot bootstrap a replacement or choose a second root.

## Exact control-plane storage manifest

The directory `CONTROL_PLANE_RELATIVE_ROOT` has the following exact relative layout. Directory creation is not an
authority object; the namespace name receipt is the first file object.

```text
PROJECT_MIRROR_PRIVATE_OUTPUT_REGISTRY_NAMESPACE_NAME_RECEIPT.json
copy-a/D02_R2_LOCATOR_CUSTODY_COPY_GENESIS.json
copy-a/events/D02_R2_LOCATOR_CUSTODY_EVENT__<sequence-8d>__<event-digest>.json
copy-b/D02_R2_LOCATOR_CUSTODY_COPY_GENESIS.json
copy-b/events/D02_R2_LOCATOR_CUSTODY_EVENT__<sequence-8d>__<event-digest>.json
allocations/P3_P7_D02_R2_CC08_E1_ROOT_LOCATOR_ALLOCATION/
  D02_R2_EVIDENCE_ROOT_LOCATOR_NAME_RECEIPT.json
transactions/intents/D02_R2_LOCATOR_CUSTODY_INTENT__<transaction-id>.json
transactions/commits/D02_R2_LOCATOR_CUSTODY_COMMIT__<transaction-id>.json
```

`relative_control_manifest` is an ordered array of objects with exactly
`control_class`, `logical_name_pattern`, `relative_destination`, `mutability` and `maximum_bytes`. Its exact rows are:

| control_class            | logical_name_pattern                                                     | relative_destination                                       | mutability             | maximum_bytes |
| ------------------------ | ------------------------------------------------------------------------ | ---------------------------------------------------------- | ---------------------- | ------------: |
| `NAMESPACE_NAME_RECEIPT` | `^PROJECT_MIRROR_PRIVATE_OUTPUT_REGISTRY_NAMESPACE_NAME_RECEIPT[.]json$` | `.`                                                        | `CREATE_NEW_IMMUTABLE` |        262144 |
| `COPY_A_GENESIS`         | `^D02_R2_LOCATOR_CUSTODY_COPY_GENESIS[.]json$`                           | `copy-a`                                                   | `CREATE_NEW_IMMUTABLE` |        262144 |
| `COPY_B_GENESIS`         | `^D02_R2_LOCATOR_CUSTODY_COPY_GENESIS[.]json$`                           | `copy-b`                                                   | `CREATE_NEW_IMMUTABLE` |        262144 |
| `COPY_A_EVENT`           | `^D02_R2_LOCATOR_CUSTODY_EVENT__[0-9]{8}__[0-9a-f]{64}[.]json$`          | `copy-a/events`                                            | `CREATE_NEW_IMMUTABLE` |        262144 |
| `COPY_B_EVENT`           | `^D02_R2_LOCATOR_CUSTODY_EVENT__[0-9]{8}__[0-9a-f]{64}[.]json$`          | `copy-b/events`                                            | `CREATE_NEW_IMMUTABLE` |        262144 |
| `LOCATOR_NAME_RECEIPT`   | `^D02_R2_EVIDENCE_ROOT_LOCATOR_NAME_RECEIPT[.]json$`                     | `allocations/P3_P7_D02_R2_CC08_E1_ROOT_LOCATOR_ALLOCATION` | `CREATE_NEW_IMMUTABLE` |        262144 |
| `TRANSACTION_INTENT`     | `^D02_R2_LOCATOR_CUSTODY_INTENT__[0-9a-f]{64}[.]json$`                   | `transactions/intents`                                     | `CREATE_NEW_IMMUTABLE` |        262144 |
| `TRANSACTION_COMMIT`     | `^D02_R2_LOCATOR_CUSTODY_COMMIT__[0-9a-f]{64}[.]json$`                   | `transactions/commits`                                     | `CREATE_NEW_IMMUTABLE` |        262144 |

Unknown files, alternate directories, duplicate logical names and writable replacements stop. Namespace, copy-genesis,
locator, intent and commit objects are preallocated by this manifest and do not require recursive name receipts.

## Exact schemas and digest domains

### Namespace name receipt

Schema/domain: `mirror.governance/ProjectPrivateOutputRegistryNamespaceNameReceipt/v1`.

It has exactly, in schema terms:

```text
schema_version
project_id
private_home_handle_id
custody_namespace_id
purpose
change_control_id
authority_id
allowed_subject_root_ids
resolver_contract_digest
host_binding_acceptance_record_digest
private_home_binding_acceptance_record_digest
principal_sid_digest
known_folder_identity_digest
private_home_identity_digest
copy_a_id
copy_b_id
namespace_first_object_logical_name
copy_common_genesis_schema_version
copy_genesis_receipt_schema_version
locator_name_receipt_schema_version
event_schema_version
intent_schema_version
commit_schema_version
snapshot_schema_version
transaction_id_schema_version
locator_schema_version
path_identity_schema_version
worktree_set_schema_version
canonicalization_version
relative_control_manifest
locator_custody_implementation_sha
locator_custody_implementation_acceptance_record_digest
retention_policy
cleanup_policy
created_at_utc
receipt_digest
```

`project_id=PROJECT_MIRROR`, `purpose=D02_R2_SINGLE_ROOT_LOCATOR_CUSTODY_ONLY`, and `allowed_subject_root_ids` is
exactly `[P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT]`. `retention_policy` is
`RETAIN_UNTIL_D02_R2_AND_ALL_DEPENDENT_TASKS_RELEASE_CUSTODY`; `cleanup_policy` is
`PRINCIPAL_EXACT_DEPENDENCY_SCAN_AND_FORWARD_CHANGE_CONTROL_REQUIRED`. The first-object name is the filename above.
Resolver/host/private-home digests come from the accepted one-way binding chain. The implementation SHA, acceptance
record digest and timestamp come from the accepted CC09 implementation record, which must exist before real namespace
creation. This makes the expected receipt bytes deterministic before the directory is created without embedding a
physical locator.

### Common genesis and copy-genesis receipts

Common-genesis schema/domain: `mirror.demo/D02R2LocatorCustodyCommonGenesis/v1`. Its payload has exactly:

```text
schema_version
namespace_receipt_digest
locator_authority_id
allocation_id
evidence_root_id
root_basename
initial_sequence
initial_authority_state
```

`initial_sequence=0` and `initial_authority_state=null`. Its typed digest is the initial previous-event head for both
copies.

Copy-genesis schema/domain: `mirror.demo/D02R2LocatorCustodyCopyGenesisReceipt/v1`. It has exactly:

```text
schema_version
namespace_receipt_digest
locator_authority_id
allocation_id
evidence_root_id
root_basename
copy_id
peer_copy_id
common_genesis_digest
created_at_utc
genesis_receipt_digest
```

Copy A and B have different receipt bytes because their IDs are reversed, but bind the same common genesis. Their
timestamp equals the accepted CC09 implementation record timestamp.

### Locator name receipt and locator digest

Locator schema/domain: `mirror.demo/D02R2EvidenceRootLocator/v1`. Its digest payload is exactly:

```text
private_home_handle_id
destination_class
normalized_relative_locator
evidence_root_id
root_basename
```

The normalized relative locator is exactly
`d02-r2-evidence/p3-p7-d02-r2-cc08-e1-evidence`. `opaque_locator` is `pmhome1:` followed by unpadded RFC-4648 base64url
of its UTF-8 bytes.

Locator-name-receipt schema/domain: `mirror.demo/D02R2EvidenceRootLocatorNameReceipt/v1`. It has exactly:

```text
schema_version
namespace_receipt_digest
locator_authority_id
allocation_id
evidence_root_id
root_basename
semantic_role
private_home_handle_id
destination_class
normalized_relative_locator
opaque_locator_scheme
opaque_locator
locator_digest
allowed_principal_tasks
accepted_cc08_plan_sha
accepted_cc08_plan_tree
registry_implementation_sha
registry_implementation_tree
registry_implementation_acceptance_record_digest
registry_implementation_acceptance_authority_digest
maximum_bytes
retention
allocated_at_utc
name_receipt_digest
```

`semantic_role=CC08_SINGLE_EVIDENCE_ROOT_LOCATOR`; `opaque_locator_scheme=pmhome1`; acceptance digests are the exact
values listed in Preserved authority; `maximum_bytes=42949672960`; `allowed_principal_tasks` is exactly
`[P3_P7_D02_R2_EXECUTION_01,P3_P7_D02_R2_EVIDENCE_REVIEW_01,P3_P7_D02_R2_R05_DURABILITY_01]`; and
`retention=RETAIN_UNTIL_D02_R2_AND_ALL_DEPENDENT_TASKS_RELEASE_CUSTODY`. `allocated_at_utc` equals the accepted CC09
implementation-record timestamp. No absolute locator is persisted.

### Windows path identity and excluded-worktree set

Path-identity schema/domain: `mirror.governance/WindowsPathIdentity/v1`. A record has exactly:

```text
schema_version
path_role
volume_serial_number_hex
file_id_128_hex
file_attributes_hex
reparse_tag_hex
is_directory
identity_digest
```

The implementation opens the directory with `FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT`, reads
`FILE_ID_INFO` from that same handle using `GetFileInformationByHandleEx(FileIdInfo)`, then reads
`FILE_ATTRIBUTE_TAG_INFO` from the same still-open handle using `GetFileInformationByHandleEx(FileAttributeTagInfo)`.
It encodes the 64-bit volume serial as 16 lowercase hex characters, the 128-bit file ID as 32 lowercase hex characters,
`FileAttributes` as 8 lowercase hex characters and `ReparseTag` as 8 lowercase hex characters. It requires the
`FILE_ATTRIBUTE_DIRECTORY` bit, rejects the `FILE_ATTRIBUTE_REPARSE_POINT` bit, requires `ReparseTag=00000000`, sets
`is_directory=true`, and only then closes the handle. Path-level `GetFileAttributes`, `stat` or a second handle cannot
substitute for this projection. `path_role` is exactly one of `KNOWN_FOLDER`, `WINDOWS_DIRECTORY`,
`WINDOWS_SYSTEM_DIRECTORY`, `POWERSHELL_MODULE_ROOT`, `PROJECT_CODE_CACHE`, `ACCEPTED_R06_CHECKOUT`,
`PROJECT_CONTAINER`, `PRIVATE_HOME`, `BRIDGE_SCRATCH`, `EVIDENCE_PARENT`, `EVIDENCE_ROOT`, `GIT_COMMON_DIR` or
`GIT_WORKTREE_ROOT`. `identity_digest=TD("mirror.governance/WindowsPathIdentity/v1", record excluding only
identity_digest)`. The host candidate's Known Folder, Windows Directory, Windows System Directory and module-root
fields must replay their exact roles; code-cache/checkout/container/private-home/scratch receipts must replay their
exact roles; event parent/root fields and the excluded-worktree set must replay their corresponding roles. Identical
physical preimages under different roles produce distinct typed payloads and cannot substitute.

Worktree-set schema/domain: `mirror.governance/ExcludedGitWorktreeIdentitySet/v1`. It has exactly:

```text
schema_version
enumeration_method
repository_common_dir_identity_digest
ordered_worktree_identity_digests
set_digest
```

`enumeration_method=git-worktree-list-porcelain-z-v1`. The Principal parses `git worktree list --porcelain -z` in
memory, validates every root identity, deduplicates and sorts the identity digests lexicographically, and never persists
or logs the paths. Every transition performs a fresh collision check; a changed worktree-set digest alone does not
rewrite an earlier event.

### Transaction ID, event, intent, snapshot and commit

Transaction-ID schema/domain: `mirror.demo/D02R2LocatorCustodyTransactionId/v1`. Its exact payload is:

```text
namespace_receipt_digest
locator_name_receipt_digest
locator_authority_id
allocation_id
evidence_root_id
sequence
previous_event_digest
decision
authority_state
transition_at_utc
```

Event schema/domain: `mirror.demo/D02R2EvidenceRootLocatorCustodyEvent/v1`. It has exactly:

```text
schema_version
namespace_receipt_digest
locator_name_receipt_digest
locator_authority_id
allocation_id
evidence_root_id
root_basename
opaque_locator
locator_digest
transaction_id
decision
authority_state
transition_at_utc
root_receipt_created_at_utc
accepted_cc08_plan_sha
accepted_cc08_plan_tree
registry_implementation_sha
registry_implementation_tree
registry_implementation_acceptance_record_digest
registry_implementation_acceptance_authority_digest
parent_identity_digest
excluded_worktree_set_digest
root_identity_digest
root_receipt_digest
root_registry_state
root_registry_common_genesis_digest
root_registry_copy_a_snapshot_digest
root_registry_copy_b_snapshot_digest
sequence
previous_event_digest
event_digest
```

Intent schema/domain: `mirror.demo/D02R2LocatorCustodyTransactionIntent/v1`. It has exactly:

```text
schema_version
namespace_receipt_digest
locator_name_receipt_digest
locator_authority_id
allocation_id
evidence_root_id
transaction_id
expected_sequence
expected_previous_event_digest
decision
authority_state
canonical_event_base64url
canonical_event_sha256
event_digest
copy_a_prior_snapshot_digest
copy_b_prior_snapshot_digest
intent_created_at_utc
commit_created_at_utc
intent_digest
```

`canonical_event_base64url` is unpadded RFC-4648 base64url of the complete canonical event bytes. It is the sole event
byte source used by recovery.

Snapshot schema/domain: `mirror.demo/D02R2LocatorCustodySemanticSnapshot/v1`. It has exactly:

```text
schema_version
namespace_receipt_digest
locator_authority_id
allocation_id
evidence_root_id
common_genesis_digest
event_count
head_event_digest
ordered_event_digests
authority_state
semantic_snapshot_digest
```

At event count zero, `head_event_digest=common_genesis_digest`, `ordered_event_digests=[]` and
`authority_state=null`. Later events are ordered by continuous sequence. A and B semantic snapshots must be identical.

Commit schema/domain: `mirror.demo/D02R2LocatorCustodyCommitReceipt/v1`. It has exactly:

```text
schema_version
namespace_receipt_digest
locator_name_receipt_digest
locator_authority_id
allocation_id
evidence_root_id
transaction_id
sequence
intent_digest
event_digest
copy_a_genesis_receipt_digest
copy_b_genesis_receipt_digest
copy_a_event_file_sha256
copy_b_event_file_sha256
copy_a_snapshot_digest
copy_b_snapshot_digest
commit_created_at_utc
commit_digest
```

The event logical name is
`D02_R2_LOCATOR_CUSTODY_EVENT__{sequence:08d}__{event_digest}.json`; intent and commit logical names use the formulas
in the storage manifest. A commit is authoritative only when the exact intent, both event files, both complete chains
and the exact commit receipt replay.

### Mandatory cross-object equations

For each transition, one explicit `transition_at_utc` is supplied before intent creation. The event
`transition_at_utc`, intent `intent_created_at_utc` and intent/commit `commit_created_at_utc` are exactly that same
string. Sequence 1 also sets `root_receipt_created_at_utc` to it; sequences 2 and 3 repeat that exact sequence-1 value.

The transaction/event/intent equations are:

```text
transaction_id
  = typed_digest(TransactionId/v1, exact transaction payload)
event.transaction_id
  = transaction_id
event.event_digest
  = typed_digest(Event/v1, event excluding only event_digest)
base64url_decode(intent.canonical_event_base64url)
  = canonical_json_bytes(event)
intent.canonical_event_sha256
  = sha256(canonical_json_bytes(event))
intent.event_digest
  = event.event_digest
intent.expected_sequence
  = event.sequence
intent.expected_previous_event_digest
  = event.previous_event_digest
intent.decision / intent.authority_state
  = event.decision / event.authority_state
intent.intent_digest
  = typed_digest(Intent/v1, intent excluding only intent_digest)
```

Before append, A and B prior snapshots must be identical, their digest must equal both intent prior-snapshot fields,
their `event_count=expected_sequence-1`, their head equals `expected_previous_event_digest`, and their authority state is
the transition table's prior state. Each event file is byte-identical to the decoded intent event and its filename binds
the same sequence/digest.

After append, A and B snapshots must be identical and have:

```text
event_count = expected_sequence
head_event_digest = event.event_digest
ordered_event_digests = prior ordered_event_digests || [event.event_digest]
authority_state = event.authority_state
```

The commit genesis-receipt digests equal the exact A/B copy-genesis files; both event-file SHA fields equal the SHA-256
of the identical canonical event bytes; both snapshot fields equal the recomputed post-append semantic snapshot digest;
the commit transaction/sequence/intent/event fields equal their source objects; and
`commit_digest=typed_digest(CommitReceipt/v1, commit excluding only commit_digest)`. Any failed equality is corruption,
not a recoverable alternative encoding.

## Event nullability and transition matrix

Only three committed events exist. A read-only replay creates no event and has no `REPLAY` decision value.

| sequence | prior state            | decision                           | authority_state        | required state fields                                                                                                                    |
| -------: | ---------------------- | ---------------------------------- | ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
|        1 | empty                  | `CREATE_NEW`                       | `PREPARED`             | root receipt timestamp, parent identity and worktree-set digest non-null; root/registry result fields null                               |
|        2 | `PREPARED`             | `CREATE_NEW` or `RECOVER_EXISTING` | `ROOT_RECEIPT_DURABLE` | prior fields replay; root identity and actual root-receipt digest non-null; `root_registry_state=NOT_INITIALIZED`; registry digests null |
|        3 | `ROOT_RECEIPT_DURABLE` | `CREATE_NEW` or `RECOVER_EXISTING` | `ROOT_REGISTRY_READY`  | all root fields non-null; `root_registry_state=READY_EMPTY`; common genesis and equal A/B CC08 snapshot digests non-null                 |

All fixed provenance, locator and receipt fields are non-null in every event. Fields declared null above must be present
with JSON `null`, not omitted, empty or guessed. The sequence is continuous, the previous head is exact, a terminal
state has no transition, and no transition can skip a state.

## Bootstrap and crash-state disposition

After the namespace receipt is durable, scaffold directories are created in this exact order:

```text
copy-a
copy-a/events
copy-b
copy-b/events
allocations
allocations/P3_P7_D02_R2_CC08_E1_ROOT_LOCATOR_ALLOCATION
transactions
transactions/intents
transactions/commits
```

The namespace receipt preauthorizes exactly those directories. Before either copy genesis exists, any exact prefix of
that ordered scaffold with every created directory empty is recoverable by creating only the missing suffix in order.
A directory outside the manifest, an out-of-order non-empty directory, a file where a directory is expected or any
unknown object stops. Event and transaction directories may remain empty between transitions; emptiness is not an
authority event.

Under a Principal mutex, the implementation recognizes only these states:

| observed state                                      | unique action                                                                      |
| --------------------------------------------------- | ---------------------------------------------------------------------------------- |
| namespace absent                                    | create fixed directory, then create the predetermined namespace receipt            |
| namespace directory exists and is byte-empty        | `CUSTODY_NAMESPACE_DIRECTORY_ONLY_STOP`; never adopt or fill it                    |
| exact receipt plus exact empty scaffold prefix      | continue only the ordered suffix, then create copy A genesis followed by B         |
| only exact A genesis                                | create exact B genesis                                                             |
| only exact B genesis                                | `CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP`; B-first is not a legal write prefix        |
| exact A+B genesis, no locator receipt               | create predetermined locator receipt                                               |
| allocation directory exists and is empty            | create predetermined locator receipt                                               |
| exact locator receipt, no event                     | derive sequence-1 transaction                                                      |
| intent only, intent+A, or intent+A+B without commit | replay only the canonical event bytes frozen by that intent, then the exact commit |
| complete committed prefix                           | derive only the next legal transition or exact read-only replay                    |

Any partial/corrupt JSON, unknown object, non-empty unrecognized directory, impossible scaffold prefix, B-only
transaction event, event without intent, commit without both events, copy-ID swap, sequence gap, unequal head/snapshot,
or second allocation is preserved and stops. The implementation never deletes, renames, overwrites, suffixes, adopts
or infers missing bytes.

## Exact durability barriers

`PATH_BASED_IMMUTABLE_CREATION: FORBIDDEN`. Every creation below the initially opened Known Folder is bound to an
already-open parent directory handle before the first destination byte is written. Validating a path and then using
`CreateDirectoryW`, `CreateFileW`, `pathlib`, `os.open` or another API that re-resolves the full textual destination is
not authority proof.

The implementation uses its separately tested `NtCreateFile`/`NtOpenFile` binding with
`OBJECT_ATTRIBUTES.RootDirectory=parent_handle`, `OBJ_CASE_INSENSITIVE|OBJ_DONT_REPARSE`, a single validated UTF-16
logical component and `FILE_CREATE`. A component containing a separator, colon, rooted prefix, alternate data stream,
`.` or `..` is rejected. Parent handles use
`GENERIC_READ|GENERIC_WRITE|READ_CONTROL|SYNCHRONIZE`, share only `FILE_SHARE_READ|FILE_SHARE_WRITE` and therefore deny
delete/rename sharing, with `FILE_DIRECTORY_FILE|FILE_OPEN_REPARSE_POINT|FILE_SYNCHRONOUS_IO_NONALERT`. The complete
handle chain remains open until the child durability barrier finishes. If the native binding, `OBJ_DONT_REPARSE`,
no-delete-share semantics or a successful parent-directory `FlushFileBuffers` cannot be proven on the host, execution
stops before creation as `HANDLE_RELATIVE_CREATION_UNAVAILABLE_STOP` or
`CUSTODY_DURABILITY_BARRIER_FAILED_STOP`.

Every new directory stage uses this exact order and may not expose the stage as durable earlier:

```text
open and validate the no-delete-share parent handle identity and exact protected DACL
-> NtCreateFile(RootDirectory=parent, single component, FILE_CREATE, FILE_DIRECTORY_FILE, creation-time protected DACL)
-> query child FILE_ID_INFO and FILE_ATTRIBUTE_TAG_INFO from the returned handle
-> require directory / non-reparse / expected fixed-volume identity / exact protected DACL
-> FlushFileBuffers(parent_directory_handle) and require success
-> reopen the child handle-relative from the same parent and require identical identity, type and DACL
-> after closing the stage, future replay reopens the entire Known-Folder-relative handle chain and requires equality
```

Every Git-external immutable file, including project-container/private-home receipts, namespace/genesis receipts,
locator receipts, intents, events, commits, R05 name/seal receipts and the rehome manifest, uses exactly:

```text
hold the validated no-delete-share parent handle and record its physical identity and DACL
-> NtCreateFile(RootDirectory=parent, single component, FILE_CREATE, FILE_NON_DIRECTORY_FILE, creation-time protected DACL)
-> query the returned child handle and prove file / non-reparse / same fixed volume before the first byte
-> full write loop until all canonical bytes are consumed
-> FlushFileBuffers(file)
-> close
-> reopen handle-relative from the still-open parent with no-follow semantics
-> verify type, size, canonical bytes, file SHA-256 and typed self-digest
-> FlushFileBuffers(parent_directory_handle) and require success
-> require the still-open parent identity/DACL unchanged and reopen the child again to compare its recorded identity
-> only then expose the stage as durable
```

Tracked governance candidates and acceptances, including the actual-root addendum and its acceptance, are not private
control-plane files and use the normal Git canonical-bytes -> commit -> independent exact review -> same-SHA CI ->
Principal acceptance workflow instead of this private storage barrier.

The transaction barrier is exact and serial:

```text
intent durable
-> copy-A event durable
-> fresh copy-A replay
-> copy-B event durable
-> fresh equal copy-A/copy-B replay
-> commit receipt durable
-> fresh intent/A/B/commit full replay
```

File flush success without the parent-directory flush and identity recheck is not durable evidence. Any short write,
flush failure, reopen mismatch, type/reparse change or parent identity change preserves existing bytes and stops as
`CUSTODY_DURABILITY_BARRIER_FAILED_STOP` or `CUSTODY_PARENT_IDENTITY_CHANGED_STOP`. No later-stage object may be
created while an earlier durability barrier remains unproven.

## Root authority predicate and orphan disposition

After CC09 acceptance, a D02-R2 root is consumable if and only if all of the following replay together:

```text
fixed Known Folder resolver
+ exact accepted-R06 code-cache receipt and checkout seal
+ receipt-only bridge scratch
+ exact namespace and locator name receipts
+ committed CC09 ROOT_REGISTRY_READY allocation head
+ fixed destination identity
+ exact CC08 root receipt
+ equal, empty-or-later-valid CC08 registry A/B committed history
```

The CC09 facade is the sole production-shaped Demo entry point for root lookup. Direct caller-supplied invocation of
CC08 root functions is permitted only inside the accepted CC09 bridge or synthetic tests. Any root lacking the committed
CC09 allocation is `ORPHANED_UNBOUND_NON_AUTHORITY`, even if it contains plausible CC08 bytes. It is non-consumable and
is not scanned for, adopted, moved, deleted or superseded in place. A future exact locator lead requires a new change
control and cannot displace the committed fixed allocation.

This predicate prevents a previously unbound physical directory from becoming competing authority without pretending
to prove that no orphan bytes exist elsewhere.

## CREATE_NEW and RECOVER_EXISTING

`PREPARED` is legal only when the fixed destination is absent, the locator allocation is unique, the accepted CC08
authority replays, the parent identity is frozen, current worktrees do not collide, the ACL/local/cloud/reparse Gates
pass and free space is at least 40 GiB. It freezes the sole `root_receipt_created_at_utc` before root creation.

- The bridge records whether the fixed root existed immediately before the accepted CC08 call. `absent -> successful
create and replay in the same uninterrupted bridge invocation` returns `ROOT_CREATED_NEW`; sequence 2 uses
  `CREATE_NEW` only for that token.
- `PREPARED + exact matching receipt observed before the bridge call`, including restart after receipt creation but
  before the sequence-2 intent, returns `ROOT_REPLAYED_EXISTING`; sequence 2 uses `RECOVER_EXISTING` only for that token.
- `PREPARED + root absent` continues the original creation with the frozen timestamp. If the process stops after CC08
  receipt durability, restart necessarily follows the previous bullet and cannot recreate `CREATE_NEW` bytes.
- `PREPARED + empty root`, partial receipt or mismatch: stop.
- Before registry initialization the bridge records A/B existence. Both absent plus successful same-invocation
  initialization returns `REGISTRY_CREATED_NEW`; sequence 3 uses `CREATE_NEW`. Either exact empty copy already present,
  or restart after either copy was created, returns `REGISTRY_RECOVERED_EXISTING`; sequence 3 uses
  `RECOVER_EXISTING`.
- `ROOT_RECEIPT_DURABLE + both registries absent`: invoke accepted CC08 empty initialization under that mapping.
- `ROOT_RECEIPT_DURABLE + one valid empty registry`: invoke accepted CC08 peer recovery under that mapping.
- A populated unilateral registry, divergent pair or unknown control object: stop.
- `ROOT_REGISTRY_READY`: exact replay only.

## Detached accepted-implementation bridge and disclosure exception

The root operation executes the accepted module from the receipt-bound code-only checkout at exact SHA
`ab08a6e861ec364c62a6ab3dcf46a69483f1b741`. Before every use, the Principal replays the cache receipt, checkout seal,
checkout identity, detached HEAD/tree, fixed remote-tracking ref, absence of `origin`, all governed source/test/digest
bytes and accepted ancestry. The bridge bootstrap/module bytes themselves come only from the future accepted CC09
implementation SHA. The cwd is that accepted checkout and never an inherited worktree, partial clone, ordinary temp
directory or user-site import root.

The Principal resolves the candidate Python from its current `sys.executable` only in memory and requires exact match
to the accepted host-binding executable identity, SHA-256 and version before revealing a locator. It launches that
exact path as `<accepted-python> -I -S -B -X utf8 <verified-bootstrap>`, with no user site, no Python environment
configuration, no `.pth` or `sitecustomize`, and loads the accepted bootstrap/module by verified file identity rather
than current-directory import. Process creation starts suspended, assigns Python and all descendants to a fresh Windows
Job Object with `JOB_OBJECT_LIMIT_ACTIVE_PROCESS=2`, `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` and no breakaway flags, then
resumes it. Git and PowerShell invocations are serialized, so the bridge plus at most one child may exist and a child
cannot create a grandchild. Process creation uses an explicit inherited-handle list containing only the anonymous
stdin/stdout/stderr pipes; no other caller handle is inheritable.

Git lookup in the Principal parent may discover a candidate, but PATH is never authority. The candidate must match the
accepted Git executable identity and SHA-256; the child PATH contains only that verified Git directory and there is no
fallback or second candidate. The exact Windows Directory/System Directory/module-root relationship, fixed
PowerShell/`cmd.exe`, both manifests, all three nested members, three cmdlet rows, four extracted script rows and the
no-locator runtime projection must replay the accepted four projection digests and closure digest. The no-locator
manifest/runtime checks run first under the same synthesized module root and WFP/Job restrictions. Only after every
cross-equality passes may the byte-identical CC08 ACL child receive the locator.

The absolute root and excluded-worktree paths enter the detached Principal Python child only as one binary frame over an
anonymous stdin pipe; they are absent from argv and the outer child environment. The frame is exactly ASCII magic
`PMCC09L1`, a four-byte unsigned big-endian payload length, then strict UTF-8 canonical JSON with exactly
`absolute_root_path`, `ordered_excluded_worktree_paths` and
`protocol_version=P3_P7_D02_R2_LOCATOR_BRIDGE_STDIN_V1`, followed by EOF. The payload length is `1..1048576`; BOM,
NUL, unpaired surrogate, duplicate/extra/missing key, truncation, a second frame or trailing bytes stop before path use.
The parent uses binary pipes (`text=False`); the child reads `sys.stdin.buffer` and writes only fixed ASCII status tokens
and non-sensitive digests through `sys.stdout.buffer`/`sys.stderr.buffer`. This ephemeral frame is not a governance
object, digest authority, log or artifact.

The detached child receives only this inherited environment allowlist:

```text
SystemRoot=<exact GetWindowsDirectoryW result>
WINDIR=<exact same GetWindowsDirectoryW result>
ComSpec=<handle-validated windows_system_directory/cmd.exe>
PATHEXT=.COM;.EXE
PATH=<validated Git directory only>
PSModulePath=<handle-validated windows_system_directory/WindowsPowerShell/v1.0/Modules only>
TEMP=<receipt-bound private-home/bridge-scratch-v1>
TMP=<exact same receipt-bound bridge scratch>
```

The environment is synthesized from scratch. Proxy, credential, token, provider, Python-startup and `MIRROR_*`
variables are not inherited. `-I` ignores `PYTHON*` variables; no encoding or path authority depends on them.
Before and after the child lifetime, bridge scratch must replay its immutable name receipt and contain no other object.

Before any detached child is created or locator frame is written, the Principal acquires the fixed CC09 bridge mutex and
an exclusive maintenance window for all four accepted executable images, replays `fwpuclnt.dll`, derives the exact
UUIDv5 session/provider/sublayer/filter keys and opens WFP through `FwpmEngineOpen0` with the derived session key and
`FWPM_SESSION_FLAG_DYNAMIC`. `FwpmSessionEnum0` must prove exactly one current-PID/current-SID dynamic user-mode
session. In one transaction the derived provider owns the derived sublayer and all eight block filters at
`FWPM_LAYER_ALE_AUTH_CONNECT_V4`/`V6`, each bound to the exact `FwpmGetAppIdFromFileName0` ID for Python, Git,
PowerShell or `cmd.exe`. Provider key, sublayer key, layer, condition, action and weights all replay exactly.

This is deliberately application-image-wide, not PID-specific. It blocks local and public traffic for every host
process using any of the four images during the serialized window. Same-image collateral is explicitly accepted and no
other task may use those images concurrently. Local services running under other executable images remain outside these
filters; no claim is made that unrelated same-image processes are unaffected.

Before disclosure, `FwpmFilterGetById0` replays each filter's bytes only; it does not prove session ownership. The
separate session-enumeration proof and provider-to-sublayer-to-eight-filter correlation must also pass. A no-locator
accepted-Python probe must receive `WSAEACCES` for both fixed documentation addresses `192.0.2.1` and `2001:db8::1`;
timeout, unreachable or DNS failure is not proof. The actual child additionally installs a fail-closed Python audit
policy that rejects socket/DNS/network events and permits direct subprocess creation only for accepted Git and
PowerShell. The Job Object active-process/no-breakaway boundary prevents either child from creating a descendant.

In `finally`, the owner deletes only the eight derived filter IDs, derived sublayer and derived provider, closes the
dynamic session and opens an observer session to prove every derived key absent. A process crash closes the dynamic
session and removes its non-persistent objects. Missing administrative/BFE capability, session ownership mismatch,
provider/sublayer/filter correlation failure, collision, partial filter replay, stale key, non-`WSAEACCES` probe,
cleanup failure, code-cache/scratch/runtime/Git/module identity drift, handle isolation failure or subprocess boundary
failure stops before disclosure as `BRIDGE_NETWORK_DENIAL_UNAVAILABLE_STOP`,
`WFP_SESSION_OWNERSHIP_UNPROVEN_STOP`, `WFP_PROVIDER_SUBLAYER_FILTER_CORRELATION_STOP`,
`WFP_EGRESS_SESSION_CLEANUP_FAILED_STOP`, `CODE_CHECKOUT_PARTIAL_OR_CORRUPT_STOP`,
`BRIDGE_SCRATCH_RESIDUE_STOP`, `DETACHED_RUNTIME_IDENTITY_CHANGED_STOP`,
`DETACHED_GIT_IDENTITY_CHANGED_STOP`, `POWERSHELL_ACL_MODULE_CLOSURE_UNPROVEN_STOP` or
`BRIDGE_UNAUTHORIZED_SUBPROCESS_STOP`.

There is one narrow accepted exception:
CC08's byte-identical `_validate_windows_restricted_acl` creates the handle-validated Windows-system-directory
PowerShell child and sets
`MIRROR_D02_R2_ACL_PATH` to the in-memory path in that trusted child's process environment. It captures only the
non-path ACL JSON projection and does not print the variable. The exception is limited to that child lifetime; it is
not an ordinary environment binding, locator authority or allowed log/artifact field.

Leakage tests require the locator to be absent from Git, CI artifacts, argv, the outer bridge environment, stdout,
stderr, exceptions, coordination mailboxes and `MEMORY.md`; they explicitly recognize only the trusted ACL-child
environment capability above. Bound capability paths `SystemRoot`, `WINDIR`, `ComSpec`, `PATH`, `PSModulePath`, `TEMP`
and `TMP` are validated separately and are not mistaken for disclosure of the D02 root/private-home locator.
Egress-denial evidence records only rule/audit status, accepted executable identity
digests and zero attempted public egress; it never records a host path. The accepted CC08 bytes are not changed or
bypassed.

## Forward migration-authority supersession

The following accepted records remain immutable historical evidence but are immediately
`HELD_PENDING_ACTUAL_ROOT_RECEIPT_REBIND` for private execution and PostgreSQL admission:

| authority                                                 | immutable record digest                                            | held field                       |
| --------------------------------------------------------- | ------------------------------------------------------------------ | -------------------------------- |
| `P3_P7_D02_R2_MIGRATION_AUTHORITY_CONTRACT_ACCEPTANCE_01` | `9954d9e91a041f9db94ca069ce618eac36f869d7017b09e55faa786736aa062a` | `root_name_receipt_digest=c3ae…` |
| `P3_P7_D02_R2_MIGRATION_DISPATCH_ADDENDUM_ACCEPTANCE_01`  | `01c22e1e62b592b48a09bb23a800bb3a2395157fae7c77c8ee82639105a0a34e` | `root_name_receipt_digest=c3ae…` |

Their schema, algorithm and software-correctness decisions are not revoked. The held scalar cannot authorize a source,
Report, Bank, Pair or database row.

After `ROOT_REGISTRY_READY` and R05 registration, the Principal creates the tracked candidate
`docs/operations/P3_P7_D02_R2_ACTUAL_ROOT_DIGEST_BINDING_ADDENDUM.json`, authority ID
`P3_P7_D02_R2_ACTUAL_ROOT_DIGEST_BINDING_ADDENDUM_01`. Its canonical payload binds exactly:

```text
schema_version
authority_id
change_control_id
cc09_plan_acceptance_record_digest
cc09_implementation_acceptance_record_digest
cc09_locator_name_receipt_digest
cc09_root_registry_ready_commit_digest
cc08_root_receipt_digest
cc08_registry_common_genesis_digest
cc08_registry_copy_a_snapshot_digest
cc08_registry_copy_b_snapshot_digest
r05_committed_output_count
cc08_registry_event_count_after_r05
cc08_registry_copy_a_snapshot_digest_after_r05
cc08_registry_copy_b_snapshot_digest_after_r05
cc08_registry_head_event_digest_after_r05
ordered_r05_output_ids
held_contract_acceptance_authority_id
held_contract_acceptance_record_digest
held_dispatch_acceptance_authority_id
held_dispatch_acceptance_record_digest
pre_root_expectation_digest
effective_root_name_receipt_digest
r05_rehome_manifest_digest
candidate_state
created_at_utc
record_digest
```

Schema/domain is `mirror.demo/D02R2ActualRootDigestBindingAddendum/v1`;
`candidate_state=CANDIDATE_PENDING_INDEPENDENT_REVIEW_SAME_SHA_CI_AND_PRINCIPAL_ACCEPTANCE`. The effective digest must
equal the rehashed CC08 receipt and must differ by authority source from the pre-root expectation even if the scalar
value were accidentally equal. `record_digest` is the typed digest of the exact candidate excluding only itself. The
candidate never reopens the held binding and never describes itself as accepted.

The separate tracked acceptance is
`docs/operations/P3_P7_D02_R2_ACTUAL_ROOT_DIGEST_BINDING_ADDENDUM_ACCEPTANCE.json`, schema/domain
`mirror.demo/D02R2ActualRootDigestBindingAddendumAcceptance/v1`, with exactly:

```text
schema_version
authority_id
change_control_id
accepted_addendum_sha
accepted_addendum_tree
accepted_addendum_path
accepted_addendum_git_blob_oid
accepted_addendum_file_sha256
accepted_addendum_record_digest
accepted_plan_acceptance_record_digest
locator_custody_implementation_acceptance_record_digest
independent_review
same_sha_ci
principal_acceptance
authorized_scope
prohibited_scope
effective_state
record_created_at_utc
record_digest
```

Frozen literals and scopes are:

```text
authority_id = P3_P7_D02_R2_ACTUAL_ROOT_DIGEST_BINDING_ADDENDUM_ACCEPTANCE_01
change_control_id = P3_P7_D02_CC_09
accepted_addendum_path = docs/operations/P3_P7_D02_R2_ACTUAL_ROOT_DIGEST_BINDING_ADDENDUM.json
authorized_scope = SUPERSEDE_HELD_ROOT_DIGEST_INPUT_BINDING_ONLY
effective_state = ACTUAL_ROOT_BINDING_ACCEPTED
prohibited_scope =
  [
    EDIT_ACCEPTED_HISTORICAL_AUTHORITY,
    ROOT_RECEIPT_SCALAR_SUBSTITUTION,
    R05_TASK_ACCEPTANCE,
    MIGRATION_OR_ORM,
    POSTGRESQL_ADMISSION,
    SOURCE_GENERATION,
    M3_M4_EXECUTION,
    D02_R2_TASK_ACCEPTANCE,
    D03_D04_B_D07_B_OPENING,
    FORMAL_PHASE_AUTHORITY,
    PRODUCTION_RELEASE
  ]
```

Its `independent_review` has exactly the frozen review keys with `reviewed_addendum_sha`; all findings are integer zero,
`result=PASS` and the reviewed SHA equals `accepted_addendum_sha`. `same_sha_ci` has the frozen eight-key shape,
`head_sha=accepted_addendum_sha` and `result=PASS`. `principal_acceptance` has exactly `status`,
`accepted_addendum_sha`, `accepted_at_utc`, `acceptance_authority_digest`; status is `PRINCIPAL_ACCEPTED`, the SHA
matches and its timestamp equals `record_created_at_utc`.

The acceptance file SHA and blob replay the exact candidate bytes; `accepted_addendum_record_digest` equals the
candidate typed digest; both plan/implementation acceptance digests equal the candidate fields; and acceptance
`record_digest` is its typed digest excluding only itself. The effective authority predicate additionally requires all
post-R05 count/snapshot/head/ordered-output equations below to replay. Only this accepted forward record reopens the held
migration input binding. No accepted historical file is edited.

The R05 final literals are `r05_committed_output_count=8` and `cc08_registry_event_count_after_r05=8`.
`ordered_r05_output_ids` is the exact eight-row order below. Both post-R05 snapshot digests must replay equal after all
eight output transactions have valid intent, A event, B event and commit receipt, and the final head event must be the
eighth committed output. The sequence-3 `ROOT_REGISTRY_READY` empty snapshot is pre-R05 evidence and is forbidden as a
substitute for these final fields.

## Existing R05 evidence re-registration

The sole permitted source is the already named task-scoped handoff
`P3_P7_D02_R2_R05_DATA_INTEGRITY_E2`. No parent enumeration or locator discovery is allowed. The seven known source
files are immutable inputs with this exact CC08 allocation matrix:

| seq | destination logical name                                    | fixed maximum bytes | media type         | new output ID                                 | source SHA-256                                                     |
| --: | ----------------------------------------------------------- | ------------------: | ------------------ | --------------------------------------------- | ------------------------------------------------------------------ |
|   1 | `D02_R2_R05_DATA_INTEGRITY_EVIDENCE_ROOT_NAME_RECEIPT.json` |              262144 | `application/json` | `D02_R2_R05_E2_LEGACY_ROOT_RECEIPT_BYTES`     | `476a68d77c31c6595e01ddc7c47b82acdcdb4a7124af04558df1e2832e072b09` |
|   2 | `D02_R2_R05_EVIDENCE_SET_REGISTRY_RECEIPT.json`             |              262144 | `application/json` | `D02_R2_R05_E2_LEGACY_REGISTRY_RECEIPT_BYTES` | `15b64de95dc8684481e00cc4d9e1a976b50c8242807b1a0d09b27ee648f701d5` |
|   3 | `D02_R2_R05_EXACT_CANDIDATE_MANIFEST.json`                  |              262144 | `application/json` | `D02_R2_R05_E2_EXACT_CANDIDATE_MANIFEST`      | `796d6fb5588e8d7b888b7c5e6ed7e1a97ca49fe25d34cb583013352666042331` |
|   4 | `D02_R2_R05_INDEPENDENT_CORRECTNESS_REVIEW.md`              |              262144 | `text/markdown`    | `D02_R2_R05_E2_INDEPENDENT_REVIEW`            | `bd6dbe3dcc1a8f45064ea4d6862ddc2c46615153f7ffb0617326c36decbac21d` |
|   5 | `D02_R2_R05_MANIFEST_SEAL_RECEIPT.json`                     |              262144 | `application/json` | `D02_R2_R05_E2_LEGACY_MANIFEST_SEAL_BYTES`    | `e662549d2dbbbcd644eee42a0e7c38710dd39797b00f48f50d964b728c28f221` |
|   6 | `D02_R2_R05_REVIEW_SEAL_RECEIPT.json`                       |              262144 | `application/json` | `D02_R2_R05_E2_LEGACY_REVIEW_SEAL_BYTES`      | `6615d3b7a1045d5946c8bae24d3515814730a41e434d6b40491c133378a4a2c9` |
|   7 | `D02_R2_R05_VALIDATION_SUMMARY.md`                          |              262144 | `text/markdown`    | `D02_R2_R05_E2_VALIDATION_SUMMARY`            | `84e48f37e74aef8fca81adb86459f285e0f6daa223e1b3d7df90abf892c6679e` |
|   8 | `D02_R2_R05_REHOME_MANIFEST.json`                           |              262144 | `application/json` | `D02_R2_R05_E2_REHOME_MANIFEST`               | created after rows 1–7 rehash                                      |

The sequence column is the exact CC08 `allocation_sequence`; destination logical name is the exact `logical_name`; all
rows use the same non-sensitive 262,144-byte ceiling. Actual byte sizes are private registry/rehome-manifest fields and
never enter tracked governance. Every row uses:

```text
semantic_role: BANK_IMPORT_EVIDENCE
relative_destination_class: DATA_BANK_IMPORT
producer_task_id: P3_P7_D02_R2_EXECUTION_01
expected_parent_authority: f9b690a5ba9f5b3bbda7acb2e24e5dd38e9a743bd1da2f6410a77cf6843d2e83
```

`P3_P7_D02_R2_R05_DURABILITY_01` is only the outer Principal orchestration operation ID and is never passed as the
accepted CC08 `producer_task_id`. The expected-parent value is read only from the exact task-scoped
`D02_R2_R05_EXACT_CANDIDATE_MANIFEST.json` field `manifest_digest`, requiring schema
`mirror.demo/D02R2R05ExactCandidateManifest/v1`, exact file SHA-256
`796d6fb5588e8d7b888b7c5e6ed7e1a97ca49fe25d34cb583013352666042331`, status `ACTIVE_EXACT_CANDIDATE` and literal
value `f9b690a5ba9f5b3bbda7acb2e24e5dd38e9a743bd1da2f6410a77cf6843d2e83`. The exact legacy registry receipt
(SHA-256 `15b64de95dc8684481e00cc4d9e1a976b50c8242807b1a0d09b27ee648f701d5`) must independently carry schema
`mirror.demo/D02R2R05EvidenceSetRegistryReceipt/v1`, task ID
`P3_P7_D02_R2_R05_DATA_INTEGRITY_E2` and the same `CANDIDATE_MANIFEST_DIGEST`. This is a cross-sealed legacy authority
field, not a newly invented digest algorithm.

Let `T0` be the committed sequence-3 `ROOT_REGISTRY_READY.transition_at_utc`. All eight name receipts use
`allocated_at_utc=T0`. For ordinal `n` in 1–8, `sealed_at_utc=T0+n microseconds` and
`intent_created_at_utc=T0+(100+n) microseconds`, using exact UTC timedelta arithmetic with normal day rollover. These are
logical authority timestamps derived from a committed input, not hidden wall-clock reads. Their fixed values are reused
after a crash.

The old root/registry/seal names are data labels only; they are not adopted as CC08 control objects. All eight outputs
use the matrix above. `D02_R2_R05_REHOME_MANIFEST.json` has schema/domain
`mirror.demo/D02R2R05EvidenceRehomeManifest/v1` and exactly:

```text
schema_version
operation_id
source_task_id
source_evidence_set_schema
source_evidence_set_logical_name
source_evidence_set_registry_receipt_sha256
source_candidate_manifest_schema
source_candidate_manifest_digest
actual_root_receipt_digest
execution_contract_digest
registry_snapshot_before_digest
rehome_manifest_name_receipt_digest
logical_authority_epoch_utc
ordered_entries
manifest_digest
```

`ordered_entries` has seven objects in ordinal order, each with exactly `ordinal`, `source_logical_name`,
`source_sha256`, `source_byte_size`, `output_id`, `allocation_sequence`, `destination_logical_name`,
`output_name_receipt_digest`, `destination_sha256`, `destination_byte_size` and `media_type`. Source and destination hash
and size must be equal. The manifest digest excludes only itself.

The Principal performs exactly:

```text
known task-scoped source handle replay
-> source count/name/size/SHA recheck
-> preallocate all eight output IDs and immutable CC08 output-name receipts
-> byte-identical create-new copy of the seven source files
-> reopen and rehash every destination
-> create the rehome manifest binding source and destination hashes plus name-receipt digests
-> create-new the manifest bytes
-> reopen and rehash the manifest
-> create eight immutable seal receipts
-> for each output: intent -> registry A -> replay -> registry B -> equal snapshot -> commit receipt
-> fresh-process replay of the final equal A/B snapshots
```

No move, overwrite, suffix, rename, retrospective root adoption or digest substitution is allowed. Missing source
handle, mismatched bytes, an output collision or any registry divergence stops without scanning. The original seven
files remain non-authoritative source evidence until the eight destination transactions are committed. The rehome
manifest digest and final registry snapshot bind the R05 durability acceptance; code correctness and evidence custody
remain separate conclusions.

For each ordinal 1–8, restart classifies exactly one state and performs only its frozen next action:

```text
name receipt durable / output absent
  -> create and durably rehash the exact output bytes
output durable / seal absent
  -> create and durably replay the exact seal receipt
seal durable / intent absent
  -> create the frozen transaction intent
intent durable / A+B absent
  -> create A, fresh replay A, create B, fresh equal A/B replay
A only
  -> fresh replay A, create B, fresh equal A/B replay
A+B / commit absent
  -> fresh equal A/B replay, create commit, fresh full replay
complete commit
  -> byte-identical full replay and no write
```

The ladder is applied in ordinal order; a later ordinal cannot advance while an earlier one is not fully committed.
B-only, output-without-name-receipt, seal-without-output, event-without-intent, commit-before-B, corrupt/partial bytes,
an unexpected logical name or a digest mismatch are preserve-and-stop states, never reconstruction permission.

## Implementation boundary and tests

After this exact plan passes independent review, same-SHA CI and Principal plan acceptance, implementation is limited
to:

```text
services/api/src/mirror_api/demo_d02_r2_locator_custody.py
services/api/tests/test_demo_d02_r2_locator_custody.py
```

The new module owns Known Folder/Windows-directory projection, exact schemas, protected code-cache/checkout/scratch
bootstrap, two-copy JSON custody, crash replay, the redacted detached bridge and the sole root-consumption facade. It may
import accepted digest primitives and CC08 public APIs but may not modify or weaken accepted bytes.

Mandatory validation:

- plan/implementation/host/private-home/addendum acceptance schemas reject every missing/extra/wrong-type key and every
  circular future-authority binding; plan authorized paths/actions equal the implementation governed-path sequence and
  no other tracked file may change in the implementation commit;
- same Known Folder text with different file identity, same physical projection under a different SID, alternate
  Windows account, Known Folder/System Directory role substitution, Known Folder remap, private-home delete/recreate
  and replacement-at-same-path all stop before write;
- host or private-home acceptance missing/partial/wrong candidate commit/tree/path/blob/file-SHA/typed-digest stops;
  review, CI and Principal SHA/time equations bind the same bytes; both private-home receipt digests equal candidate
  fields and physically replayed receipts; an unaccepted candidate cannot create a namespace and an accepted-but-missing
  home cannot rebootstrap;
- reparse insertion/swap at every ancestor, UNC/device/network, Cloud Files attribute, Profile/LocalAppData identity
  mismatch, malformed/nonabsolute/wrong-type OneDrive values, component-boundary overlap/unreadability, fixed-volume
  failure, null DACL, unknown ACE/flag, inherit-only applicability drift, generic-right mapping drift or dangerous-write
  role all stop; inherited ACEs pass only the same mapped-mask predicate and AccessCheck proves Principal access; the
  `ProjectMirror` and private-home components each receive their protected DACL at creation, while the accepted CC08
  hardener remains limited to its new evidence root;
- two-component bootstrap tests cover initial pre-existing ProjectMirror, container-directory-only, exact container
  receipt/second absent, private-home-directory-only, reversed stages, DACL/identity drift and both legal receipt-bound
  prefixes; no directory-only stage is adopted;
- code cache tests cover pre-existing/unbound/directory-only states, local no-hardlink clone, origin removal, fixed-ref
  recreation, exact detached R06 HEAD/tree/blobs, partial checkout, config source-path leakage and immutable cache/seal
  receipt replay; bridge scratch tests cover directory-only, receipt-only, transient child use, before/after
  receipt-only replay and preserve-and-stop crash residue;
- exact schema/key/type/digest replay and unknown-key rejection for every object;
- namespace absent, directory-only, receipt-only, A-only genesis, B-only genesis and exact A+B bootstrap;
- locator directory-only, exact receipt replay and corrupt/unknown/collision stops;
- empty snapshots, copy-ID swap, sequence gap, head divergence and complete transition/null matrix;
- intent-only, A-only and A+B/no-commit exact recovery; B-only and commit-before-both stop;
- partial/corrupt intent, event and commit preserve-and-stop;
- second allocation, caller path, fallback, automatic suffix and root-ID rebinding reject;
- fixed-destination absent create, PREPARED timestamp recovery and unbound-existing-root rejection;
- empty/partial/mismatched root receipt and populated/divergent registry stop;
- Windows Known Folder, fixed drive, worktree, UNC, cloud, reparse, ACL and free-space host fault tests;
- partial write, file-flush failure, parent-flush failure, reopen mismatch, parent/child identity swap and crash after
  file flush but before parent flush for every immutable-object class;
- path-based create, unsupported `OBJ_DONT_REPARSE`, root-handle mismatch, parent rename/delete sharing, final-component
  reparse/ADS/separator, any non-`FILE_CREATE` disposition and native/directory-flush unavailability all stop before the
  first destination byte or before stage durability;
- exact detached `ab08a6e…` bridge and accepted CC08/R06 registry regression;
- fake/caller-PATH Git, Python/version replacement, `.pth`/user-site/`sitecustomize`, cwd/import-root drift,
  unauthorized inherited handle, Windows-directory/system-directory relationship drift, each of the four PowerShell
  projection digests, manifest/member/cmdlet/extracted-script cross-equality, socket/DNS/connect attempt and unauthorized
  subprocess all fail before or during the bridge without disclosing a locator;
- binary stdin tests cover non-ASCII Known Folder/root/worktree names, embedded newline, exact byte round-trip,
  invalid UTF-8, BOM, truncation, over-size, second frame and trailing bytes; injected `PYTHON*` values are ignored and
  absent from the child environment;
- WFP tests cover deterministic UUIDv5 keys, missing privilege/BFE/API, wrong `fwpuclnt.dll`,
  `FwpmSessionEnum0` PID/SID/dynamic/user-mode ownership drift, provider/sublayer/eight-filter correlation, partial V4/V6
  filters, exact display/description/provider-data/empty-blob/zero-null/rawContext/reserved/condition/action drift,
  app-ID/layer/weight drift, host-assigned ID/effective-weight policy, collision, non-`WSAEACCES` probes, image-wide
  same-image collateral, serialized maintenance-window enforcement, Job bypass, crash cleanup, explicit cleanup failure
  and observer absence; `FwpmFilterGetById0` is never treated as session proof and the rule is never labelled PID-specific;
- sanitized outer child environment and narrow trusted ACL-child exception;
- no locator in tracked bytes, argv, outer env, stdout/stderr, exception, CI artifact or mailbox;
- every R05 ordinal restart state follows the exact recovery ladder; B-only, commit-before-B and corrupt prior-stage
  combinations preserve and stop; final count/head/equal-snapshot/ordered-ID binding must be eight and must reject the
  earlier `READY_EMPTY` snapshot;
- actual-root addendum candidate and separate acceptance schemas, candidate-only non-authority, exact review/CI/
  Principal evidence, effective-state transition and held-binding predicate all replay; the tracked files are never
  treated as private control-plane durability objects;
- synthetic temporary roots only in automated tests; real host projection is read-only and the real private home/root
  remain untouched until implementation, host-binding and private-home-binding acceptances respectively authorize the
  next exact stage;
- Ruff format/check, strict mypy, targeted pytest, `git diff --check`, independent exact-SHA implementation review and
  same-SHA CI.

## Stop rules

```text
PRIVATE_HOME_BINDING_UNAVAILABLE_STOP
PRIVATE_HOME_BOUNDARY_INVALID_STOP
PRIVATE_HOME_PROJECT_COMPONENT_UNBOUND_STOP
WINDOWS_HOST_BINDING_AUTHORITY_MISSING_STOP
WINDOWS_PRINCIPAL_SID_CHANGED_STOP
KNOWN_FOLDER_IDENTITY_CHANGED_STOP
WINDOWS_DIRECTORY_IDENTITY_CHANGED_STOP
WINDOWS_SYSTEM_DIRECTORY_IDENTITY_CHANGED_STOP
WINDOWS_DIRECTORY_SYSTEM_DIRECTORY_RELATIONSHIP_STOP
CODE_CACHE_PREEXISTING_UNBOUND_STOP
CODE_CACHE_DIRECTORY_ONLY_STOP
CODE_CHECKOUT_PARTIAL_OR_CORRUPT_STOP
CODE_CHECKOUT_ACCEPTED_REF_MISMATCH_STOP
PRIVATE_HOME_DIRECTORY_ONLY_STOP
PRIVATE_HOME_RECEIPT_PARTIAL_OR_CORRUPT_STOP
PRIVATE_HOME_BINDING_AUTHORITY_MISSING_STOP
PRIVATE_HOME_IDENTITY_CHANGED_STOP
PRIVATE_HOME_REDIRECTION_STOP
BRIDGE_SCRATCH_DIRECTORY_ONLY_STOP
BRIDGE_SCRATCH_RESIDUE_STOP
CUSTODY_NAMESPACE_COLLISION_STOP
CUSTODY_NAMESPACE_RECEIPT_PARTIAL_OR_CORRUPT_STOP
CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP
HANDLE_RELATIVE_CREATION_UNAVAILABLE_STOP
CUSTODY_DURABILITY_BARRIER_FAILED_STOP
CUSTODY_PARENT_IDENTITY_CHANGED_STOP
LOCATOR_NAME_RECEIPT_COLLISION_STOP
LOCATOR_INTENT_PARTIAL_OR_CORRUPT_STOP
LOCATOR_COPY_DIVERGENCE_STOP
LOCATOR_COMMIT_PARTIAL_OR_CORRUPT_STOP
UNBOUND_EXISTING_EVIDENCE_ROOT_STOP
SECOND_ROOT_OR_REBIND_STOP
ROOT_DIRECTORY_RECEIPT_ABSENT_STOP
ROOT_RECEIPT_MISMATCH_STOP
ROOT_IDENTITY_CHANGED_STOP
ROOT_REGISTRY_NOT_READY_STOP
ABSOLUTE_LOCATOR_DISCLOSURE_STOP
DETACHED_RUNTIME_IDENTITY_CHANGED_STOP
DETACHED_GIT_IDENTITY_CHANGED_STOP
BRIDGE_NETWORK_DENIAL_UNAVAILABLE_STOP
WFP_EGRESS_SESSION_CLEANUP_FAILED_STOP
WFP_SESSION_OWNERSHIP_UNPROVEN_STOP
WFP_PROVIDER_SUBLAYER_FILTER_CORRELATION_STOP
POWERSHELL_ACL_MODULE_CLOSURE_UNPROVEN_STOP
POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP
POWERSHELL_CMDLET_PROJECTION_MISMATCH_STOP
POWERSHELL_ACL_SCRIPT_PROJECTION_MISMATCH_STOP
POWERSHELL_RUNTIME_PROJECTION_MISMATCH_STOP
BRIDGE_UNAUTHORIZED_SUBPROCESS_STOP
PRE_ROOT_EXPECTATION_DIGEST_NON_CONSUMABLE_STOP
MIGRATION_ROOT_BINDING_HELD_STOP
R05_SOURCE_EVIDENCE_MISMATCH_STOP
```

All CC08 stop states remain active. A stop never authorizes delete, overwrite, rename, suffix, scan, adoption, ACL
change or a new allocation.

## Retention, risk and DAG

Code-cache/checkout/scratch receipts, namespace receipts, both custody copies, intents, commits, root, re-registered R05
evidence and their registries remain `RETAINED` until D02-R2 and all dependent tasks release custody. CC09 authorizes no
cleanup. The same-home A/B pair is logical corruption detection, not independent-device disaster backup.

```text
CC09 revision 8 exact plan
-> independent Sol exact-plan review
-> Principal plan commit / same-SHA CI / plan acceptance
-> two-file locator custody implementation
-> fault, Windows and disclosure validation
-> independent Sol exact-implementation review
-> implementation commit / same-SHA CI / implementation acceptance
-> read-only Windows host-binding candidate / review / same-SHA CI / acceptance
-> code cache name receipt + exact local accepted-R06 checkout + checkout seal
-> handle-relative ProjectMirror container + container name receipt
-> handle-relative private-home candidate + private-home name receipt
-> private-home binding candidate / review / same-SHA CI / acceptance
-> receipt-bound bridge scratch + name receipt
-> accepted SID/Known Folder/code-cache/checkout/project-container/private-home/scratch replay
-> namespace receipt (first object) + copy A/B genesis
-> locator name receipt
-> PREPARED A/B
-> detached ab08a6e root creation/replay
-> ROOT_RECEIPT_DURABLE A/B
-> accepted CC08 registry initialization/replay
-> ROOT_REGISTRY_READY A/B
-> preallocate/copy/rehash/seal/register R05 evidence
-> actual-root-digest forward addendum and acceptance
-> R05 durability acceptance
```

Generation capability remains a separate dependency. This change control does not open source generation, M3/M4,
PostgreSQL admission, D03, D04-B or D07-B.

If the fixed private home cannot resolve or fails the existing ACL/local-volume boundary and repair would require an
ACL change or a different locator, execution stops with `OWNER_ACTION_REQUIRED`; CC09 never broadens the resolver.
