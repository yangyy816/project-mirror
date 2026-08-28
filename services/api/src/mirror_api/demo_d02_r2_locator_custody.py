# ruff: noqa: E501
"""CC09 locator-custody primitives.

This module is deliberately a control-plane implementation.  It never resolves
the real private home, creates a Windows directory, changes an ACL, or invokes
the accepted CC08 implementation.  Those host operations are represented by
validated projections and can only be exercised by a later, separately
accepted bridge.  ``SyntheticCustodyStore`` is a test-only filesystem model:
callers must pass an already-created temporary directory.
"""

from __future__ import annotations

import base64
import hashlib
import importlib
import json
import os
import re
import threading
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Protocol, cast

from mirror_api.demo_measurement_quality import canonical_json_bytes, mirror_demo_digest

type Json = bool | int | str | list[Json] | dict[str, Json] | None
type JsonObject = dict[str, Json]


class LocatorCustodyError(RuntimeError):
    """A fail-closed CC09 check failed without disclosing a locator."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


_TRUSTED_BINDING_SOURCE_TOKEN: Final = object()
_BOOTSTRAP_AUTHORITY_ANCHOR_TOKEN: Final = object()


@dataclass(frozen=True, slots=True, init=False)
class TrustedAcceptanceBindingSource:
    """Canonical acceptance bytes anchored outside the record being checked.

    A plain mapping is intentionally insufficient: it can be copied from a
    fully re-signed forged record.  Instances are minted only by
    ``load_trusted_acceptance_binding_source`` after a frozen, candidate-
    independent anchor matches the canonical source bytes.
    """

    anchor_id: str
    authority_id: str
    schema_version: str
    record_digest: str
    source_file_sha256: str
    canonical_record_bytes: bytes
    _token: object = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        anchor_id: str,
        authority_id: str,
        schema_version: str,
        record_digest: str,
        source_file_sha256: str,
        canonical_record_bytes: bytes,
        _token: object,
    ) -> None:
        if _token is not _TRUSTED_BINDING_SOURCE_TOKEN:
            raise LocatorCustodyError("CUSTODY_TRUSTED_BINDING_SOURCE_REQUIRED_STOP")
        object.__setattr__(self, "anchor_id", anchor_id)
        object.__setattr__(self, "authority_id", authority_id)
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "record_digest", record_digest)
        object.__setattr__(self, "source_file_sha256", source_file_sha256)
        object.__setattr__(self, "canonical_record_bytes", canonical_record_bytes)
        object.__setattr__(self, "_token", _token)


@dataclass(frozen=True, slots=True, init=False)
class LocatorBootstrapAuthorityAnchor:
    """Validated projection of the authorities required before a custody write.

    This value is not treated as a Python capability.  A write path must retain
    and replay the underlying accepted sources (or the fixed tracked-path
    chain), rather than accepting a caller-constructed instance of this class.
    """

    implementation_sha: str
    implementation_acceptance_record_digest: str
    host_binding_acceptance_record_digest: str
    private_home_binding_acceptance_record_digest: str
    authority_created_at_utc: str
    _token: object = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        implementation_sha: str,
        implementation_acceptance_record_digest: str,
        host_binding_acceptance_record_digest: str,
        private_home_binding_acceptance_record_digest: str,
        authority_created_at_utc: str,
        _token: object,
    ) -> None:
        if _token is not _BOOTSTRAP_AUTHORITY_ANCHOR_TOKEN:
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_AUTHORITY_ANCHOR_REQUIRED_STOP")
        object.__setattr__(self, "implementation_sha", implementation_sha)
        object.__setattr__(
            self,
            "implementation_acceptance_record_digest",
            implementation_acceptance_record_digest,
        )
        object.__setattr__(
            self,
            "host_binding_acceptance_record_digest",
            host_binding_acceptance_record_digest,
        )
        object.__setattr__(
            self,
            "private_home_binding_acceptance_record_digest",
            private_home_binding_acceptance_record_digest,
        )
        object.__setattr__(self, "authority_created_at_utc", authority_created_at_utc)
        object.__setattr__(self, "_token", _token)


PLAN_SCHEMA: Final = "mirror.demo/D02R2LocatorCustodyPlanAcceptance/v1"
IMPLEMENTATION_SCHEMA: Final = "mirror.demo/D02R2LocatorCustodyImplementationAcceptance/v1"
SCHEMA_CONTRACT: Final = "mirror.demo/D02R2LocatorCustodySchemaContract/v1"
NAMESPACE_SCHEMA: Final = "mirror.governance/ProjectPrivateOutputRegistryNamespaceNameReceipt/v1"
COMMON_GENESIS_SCHEMA: Final = "mirror.demo/D02R2LocatorCustodyCommonGenesis/v1"
COPY_GENESIS_SCHEMA: Final = "mirror.demo/D02R2LocatorCustodyCopyGenesisReceipt/v1"
LOCATOR_SCHEMA: Final = "mirror.demo/D02R2EvidenceRootLocator/v1"
LOCATOR_RECEIPT_SCHEMA: Final = "mirror.demo/D02R2EvidenceRootLocatorNameReceipt/v1"
TRANSACTION_ID_SCHEMA: Final = "mirror.demo/D02R2LocatorCustodyTransactionId/v1"
EVENT_SCHEMA: Final = "mirror.demo/D02R2EvidenceRootLocatorCustodyEvent/v1"
INTENT_SCHEMA: Final = "mirror.demo/D02R2LocatorCustodyTransactionIntent/v1"
SNAPSHOT_SCHEMA: Final = "mirror.demo/D02R2LocatorCustodySemanticSnapshot/v1"
COMMIT_SCHEMA: Final = "mirror.demo/D02R2LocatorCustodyCommitReceipt/v1"
PATH_IDENTITY_SCHEMA: Final = "mirror.governance/WindowsPathIdentity/v1"
WORKTREE_SCHEMA: Final = "mirror.governance/ExcludedGitWorktreeIdentitySet/v1"
SID_SCHEMA: Final = "mirror.governance/WindowsPrincipalSid/v1"
EXECUTABLE_SCHEMA: Final = "mirror.governance/WindowsExecutableIdentity/v1"
FILE_SCHEMA: Final = "mirror.governance/WindowsFileIdentity/v1"
NATIVE_CREATE_SCHEMA: Final = "mirror.governance/WindowsNativeRelativeCreateContract/v1"
PROTECTED_DACL_SCHEMA: Final = "mirror.governance/WindowsProtectedDirectoryDaclContract/v1"
RESTRICTED_ACL_SCHEMA: Final = "mirror.governance/WindowsRestrictedAncestorAclContract/v1"
KNOWN_FOLDER_SCHEMA: Final = "mirror.governance/WindowsKnownFolderBoundaryContract/v1"
RESOLVER_SCHEMA: Final = "mirror.governance/ProjectPrivateHomeResolverContract/v1"
PS_MANIFEST_SCHEMA: Final = "mirror.governance/PowerShellModuleManifestProjection/v1"
PS_CMDLET_SCHEMA: Final = "mirror.governance/PowerShellRequiredCmdletProjection/v1"
PS_SCRIPT_SCHEMA: Final = "mirror.governance/PowerShellAclBootstrapScriptProjection/v1"
PS_RUNTIME_SCHEMA: Final = "mirror.governance/PowerShellAclRuntimeProjection/v1"
PS_CLOSURE_SCHEMA: Final = "mirror.governance/PowerShellAclModuleClosure/v1"
HOST_CANDIDATE_SCHEMA: Final = "mirror.demo/D02R2WindowsHostBindingCandidate/v1"
HOST_ACCEPTANCE_SCHEMA: Final = "mirror.demo/D02R2WindowsHostBindingAcceptance/v1"
ADDENDUM_SCHEMA: Final = "mirror.demo/D02R2ActualRootDigestBindingAddendum/v1"
ADDENDUM_ACCEPTANCE_SCHEMA: Final = "mirror.demo/D02R2ActualRootDigestBindingAddendumAcceptance/v1"

PLAN_ACCEPTANCE_ANCHOR_ID: Final = "CC09_PLAN_ACCEPTANCE_FROZEN_V1"
IMPLEMENTATION_ACCEPTANCE_TEST_ANCHOR_ID: Final = (
    "CC09_SYNTHETIC_IMPLEMENTATION_ACCEPTANCE_FROZEN_V1"
)
HOST_ACCEPTANCE_TEST_ANCHOR_ID: Final = "CC09_SYNTHETIC_HOST_ACCEPTANCE_FROZEN_V1"
PRIVATE_HOME_ACCEPTANCE_TEST_ANCHOR_ID: Final = "CC09_SYNTHETIC_PRIVATE_HOME_ACCEPTANCE_FROZEN_V1"
ADDENDUM_ACCEPTANCE_TEST_ANCHOR_ID: Final = (
    "CC09_SYNTHETIC_ACTUAL_ROOT_ADDENDUM_ACCEPTANCE_FROZEN_V1"
)

# Trust expectations are deliberately not parameters of the loader. Adding a
# future accepted authority requires a reviewed code change; candidate bytes
# cannot mint their own trust root by supplying matching hashes.
_FROZEN_ACCEPTANCE_ANCHORS: Final[tuple[tuple[str, str, str, str, str], ...]] = (
    (
        PLAN_ACCEPTANCE_ANCHOR_ID,
        "P3_P7_D02_R2_LOCATOR_CUSTODY_PLAN_ACCEPTANCE_01",
        PLAN_SCHEMA,
        "23dc24e8d91e2080388a04b53e7fb7f1a9e5aadb3fab8f28e06c978872781c30",
        "c1442fbd6b1a057e262114c7bb02a9a66682224fb042ae59ccff2754f5b3ec5f",
    ),
    (
        IMPLEMENTATION_ACCEPTANCE_TEST_ANCHOR_ID,
        "P3_P7_D02_R2_LOCATOR_CUSTODY_IMPLEMENTATION_ACCEPTANCE_01",
        IMPLEMENTATION_SCHEMA,
        "1afa590ef8284d9dbd0977d1777091e11b4ecd0032cc974471c3dfd3a81ec950",
        "c72d9624e421f37974dec1c704d03931ae66127ae92c7d623c30db8247979719",
    ),
    (
        HOST_ACCEPTANCE_TEST_ANCHOR_ID,
        "P3_P7_D02_R2_WINDOWS_HOST_BINDING_ACCEPTANCE_01",
        HOST_ACCEPTANCE_SCHEMA,
        "8bf3f30d6286524792d1e9cbeb4eaef16feac970edfa1ad5a0fa902066cabed6",
        "1e45df59ee709acc0ec9e30a862e45a2ae43f44b9baebfb4dd044c51e2c2a03b",
    ),
    (
        PRIVATE_HOME_ACCEPTANCE_TEST_ANCHOR_ID,
        "P3_P7_D02_R2_PRIVATE_HOME_BINDING_ACCEPTANCE_01",
        "mirror.demo/D02R2PrivateHomeBindingAcceptance/v1",
        "bb1a751ac836a5a90a99298cf5c2ed237520b693b11fa9bcede399328ed49173",
        "9068ec7e1cd45b9d1fa05f9b61f06f7c738acddba53a692393b7634fb2edc1be",
    ),
    (
        ADDENDUM_ACCEPTANCE_TEST_ANCHOR_ID,
        "P3_P7_D02_R2_ACTUAL_ROOT_DIGEST_BINDING_ADDENDUM_ACCEPTANCE_01",
        ADDENDUM_ACCEPTANCE_SCHEMA,
        "f6edc154ec8b7f182f70c8ca439fcef480f817687907343e6f7e5da2118f9690",
        "383716f6bf39f1421dc795d9197460efbc90860587340993285375d32fd9f111",
    ),
)

_SAME_SHA_CI_KEYS: Final = {
    "artifact_manifest_digest",
    "head_sha",
    "provider",
    "repository",
    "required_jobs",
    "result",
    "run_id",
    "workflow_identity",
}
_REVIEW_FINDING_KEYS: Final = ("findings_p0", "findings_p1", "findings_p2", "findings_p3")
_REQUIRED_CI_JOBS: Final = ["quality-and-integration", "secret-scan", "docker-validation"]

ORDERED_SCHEMA_VERSIONS: Final[tuple[str, ...]] = (
    SCHEMA_CONTRACT,
    PLAN_SCHEMA,
    IMPLEMENTATION_SCHEMA,
    "mirror.governance/WindowsPrincipalSid/v1",
    "mirror.governance/WindowsExecutableIdentity/v1",
    "mirror.governance/WindowsFileIdentity/v1",
    PATH_IDENTITY_SCHEMA,
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
    NAMESPACE_SCHEMA,
    COMMON_GENESIS_SCHEMA,
    COPY_GENESIS_SCHEMA,
    LOCATOR_SCHEMA,
    LOCATOR_RECEIPT_SCHEMA,
    WORKTREE_SCHEMA,
    TRANSACTION_ID_SCHEMA,
    EVENT_SCHEMA,
    INTENT_SCHEMA,
    SNAPSHOT_SCHEMA,
    COMMIT_SCHEMA,
    "mirror.demo/D02R2R05EvidenceRehomeManifest/v1",
    ADDENDUM_SCHEMA,
    ADDENDUM_ACCEPTANCE_SCHEMA,
)

RELATIVE_CONTROL_MANIFEST: Final[tuple[JsonObject, ...]] = (
    {
        "control_class": "NAMESPACE_NAME_RECEIPT",
        "logical_name_pattern": "^PROJECT_MIRROR_PRIVATE_OUTPUT_REGISTRY_NAMESPACE_NAME_RECEIPT[.]json$",
        "relative_destination": ".",
        "mutability": "CREATE_NEW_IMMUTABLE",
        "maximum_bytes": 262144,
    },
    {
        "control_class": "COPY_A_GENESIS",
        "logical_name_pattern": "^D02_R2_LOCATOR_CUSTODY_COPY_GENESIS[.]json$",
        "relative_destination": "copy-a",
        "mutability": "CREATE_NEW_IMMUTABLE",
        "maximum_bytes": 262144,
    },
    {
        "control_class": "COPY_B_GENESIS",
        "logical_name_pattern": "^D02_R2_LOCATOR_CUSTODY_COPY_GENESIS[.]json$",
        "relative_destination": "copy-b",
        "mutability": "CREATE_NEW_IMMUTABLE",
        "maximum_bytes": 262144,
    },
    {
        "control_class": "COPY_A_EVENT",
        "logical_name_pattern": "^D02_R2_LOCATOR_CUSTODY_EVENT__[0-9]{8}__[0-9a-f]{64}[.]json$",
        "relative_destination": "copy-a/events",
        "mutability": "CREATE_NEW_IMMUTABLE",
        "maximum_bytes": 262144,
    },
    {
        "control_class": "COPY_B_EVENT",
        "logical_name_pattern": "^D02_R2_LOCATOR_CUSTODY_EVENT__[0-9]{8}__[0-9a-f]{64}[.]json$",
        "relative_destination": "copy-b/events",
        "mutability": "CREATE_NEW_IMMUTABLE",
        "maximum_bytes": 262144,
    },
    {
        "control_class": "LOCATOR_NAME_RECEIPT",
        "logical_name_pattern": "^D02_R2_EVIDENCE_ROOT_LOCATOR_NAME_RECEIPT[.]json$",
        "relative_destination": "allocations/P3_P7_D02_R2_CC08_E1_ROOT_LOCATOR_ALLOCATION",
        "mutability": "CREATE_NEW_IMMUTABLE",
        "maximum_bytes": 262144,
    },
    {
        "control_class": "TRANSACTION_INTENT",
        "logical_name_pattern": "^D02_R2_LOCATOR_CUSTODY_INTENT__[0-9a-f]{64}[.]json$",
        "relative_destination": "transactions/intents",
        "mutability": "CREATE_NEW_IMMUTABLE",
        "maximum_bytes": 262144,
    },
    {
        "control_class": "TRANSACTION_COMMIT",
        "logical_name_pattern": "^D02_R2_LOCATOR_CUSTODY_COMMIT__[0-9a-f]{64}[.]json$",
        "relative_destination": "transactions/commits",
        "mutability": "CREATE_NEW_IMMUTABLE",
        "maximum_bytes": 262144,
    },
)

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T][0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{6}Z\Z")

# This is the one closed authority for CC09's Windows/PowerShell wire shapes.
# Values are tuples (rather than sets) so the frozen payload order stays visible
# to reviewers; exact-key validation itself deliberately remains order agnostic.
WINDOWS_WIRE_SCHEMA_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    SID_SCHEMA: ("sid_string",),
    EXECUTABLE_SCHEMA: (
        "volume_serial_number_hex",
        "file_id_128_hex",
        "file_size",
        "file_sha256",
        "product_name",
        "product_version",
        "machine_type",
    ),
    FILE_SCHEMA: ("volume_serial_number_hex", "file_id_128_hex", "file_size", "file_sha256"),
    PATH_IDENTITY_SCHEMA: (
        "schema_version",
        "path_role",
        "volume_serial_number_hex",
        "file_id_128_hex",
        "file_attributes_hex",
        "reparse_tag_hex",
        "is_directory",
        "identity_digest",
    ),
    NATIVE_CREATE_SCHEMA: (
        "backend",
        "object_attributes_flags",
        "parent_desired_access",
        "parent_share_access",
        "parent_create_options",
        "child_disposition",
        "file_create_options",
        "directory_create_options",
        "child_share_access",
        "directory_durability",
        "contract_version",
    ),
    PROTECTED_DACL_SCHEMA: (
        "owner_role",
        "dacl_protection",
        "ace_order",
        "inherited_aces",
        "other_allow_aces",
        "post_create_acl_mutation",
        "contract_version",
    ),
    RESTRICTED_ACL_SCHEMA: (
        "projection_api",
        "owner_role",
        "null_dacl",
        "accepted_ace_types",
        "accepted_ace_flags",
        "ace_applicability",
        "unknown_ace_flag",
        "approved_write_roles",
        "dangerous_write_mask",
        "generic_right_mapping_api",
        "file_generic_mapping",
        "other_applicable_allow_dangerous_mask",
        "inherited_ace_policy",
        "required_current_principal_access",
        "current_principal_access_verification",
        "unknown_ace_type",
        "contract_version",
    ),
    KNOWN_FOLDER_SCHEMA: (
        "local_app_data_source",
        "profile_source",
        "default_relation",
        "volume_policy",
        "forbidden_namespace_classes",
        "reparse_tag_policy",
        "cloud_file_attributes",
        "cloud_file_attributes_policy",
        "onedrive_account_source",
        "onedrive_value_type",
        "onedrive_account_order",
        "onedrive_path_grammar",
        "onedrive_canonicalization",
        "project_boundary_candidates",
        "onedrive_containment_comparison",
        "onedrive_containment",
        "malformed_or_nonabsolute_onedrive_value",
        "unreadable_existing_onedrive_account",
        "ancestor_acl_contract_digest",
        "residual_boundary",
        "contract_version",
    ),
    RESOLVER_SCHEMA: (
        "platform",
        "known_folder_guid",
        "known_folder_api",
        "known_folder_flags",
        "code_cache_relative_component",
        "ordered_project_relative_components",
        "control_plane_relative_root",
        "evidence_relative_root",
        "bridge_scratch_relative_root",
        "known_folder_boundary_contract_digest",
        "restricted_ancestor_acl_contract_digest",
        "canonicalization_version",
    ),
    PS_MANIFEST_SCHEMA: (
        "schema_version",
        "windows_directory_identity_digest",
        "windows_system_directory_identity_digest",
        "module_root_directory_identity_digest",
        "security_manifest_file_identity_digest",
        "security_manifest_file_sha256",
        "security_guid",
        "security_module_version",
        "security_root_module_state",
        "security_required_modules",
        "security_scripts_to_process",
        "security_types_to_process",
        "security_formats_to_process",
        "security_nested_members",
        "utility_manifest_file_identity_digest",
        "utility_manifest_file_sha256",
        "utility_guid",
        "utility_module_version",
        "utility_root_module_state",
        "utility_required_modules",
        "utility_scripts_to_process",
        "utility_types_to_process",
        "utility_formats_to_process",
        "utility_nested_members",
        "projection_digest",
    ),
    PS_CMDLET_SCHEMA: (
        "schema_version",
        "module_manifest_projection_digest",
        "ordered_command_rows",
        "projection_digest",
    ),
    PS_SCRIPT_SCHEMA: (
        "schema_version",
        "accepted_cc09_implementation_sha",
        "accepted_r06_source_file_sha256",
        "extraction_rule",
        "ordered_script_rows",
        "projection_digest",
    ),
    PS_RUNTIME_SCHEMA: (
        "schema_version",
        "powershell_executable_identity_digest",
        "powershell_version",
        "windows_directory_identity_digest",
        "windows_system_directory_identity_digest",
        "module_root_directory_identity_digest",
        "module_manifest_projection_digest",
        "required_cmdlet_projection_digest",
        "acl_bootstrap_script_projection_digest",
        "ordered_loaded_member_identity_digests",
        "runtime_projection_digest",
    ),
    PS_CLOSURE_SCHEMA: (
        "powershell_executable_identity_digest",
        "windows_directory_identity_digest",
        "windows_system_directory_identity_digest",
        "module_root_directory_identity_digest",
        "module_manifest_projection_digest",
        "required_cmdlet_projection_digest",
        "acl_bootstrap_script_projection_digest",
        "runtime_projection_digest",
        "closure_digest",
    ),
}

_NATIVE_CREATE_CONTRACT: Final[JsonObject] = {
    "backend": "NTDLL_NTCREATEFILE_ROOT_DIRECTORY_V1",
    "object_attributes_flags": "OBJ_CASE_INSENSITIVE|OBJ_DONT_REPARSE",
    "parent_desired_access": "GENERIC_READ|GENERIC_WRITE|READ_CONTROL|SYNCHRONIZE",
    "parent_share_access": "FILE_SHARE_READ|FILE_SHARE_WRITE",
    "parent_create_options": "FILE_DIRECTORY_FILE|FILE_OPEN_REPARSE_POINT|FILE_SYNCHRONOUS_IO_NONALERT",
    "child_disposition": "FILE_CREATE",
    "file_create_options": "FILE_NON_DIRECTORY_FILE|FILE_OPEN_REPARSE_POINT|FILE_SYNCHRONOUS_IO_NONALERT",
    "directory_create_options": "FILE_DIRECTORY_FILE|FILE_OPEN_REPARSE_POINT|FILE_SYNCHRONOUS_IO_NONALERT",
    "child_share_access": "NONE",
    "directory_durability": "FLUSH_FILE_BUFFERS_PARENT_REQUIRED",
    "contract_version": "P3_P7_D02_R2_WINDOWS_NATIVE_RELATIVE_CREATE_V1",
}
_PROTECTED_DACL_CONTRACT: Final[JsonObject] = {
    "owner_role": "CURRENT_PRINCIPAL_SID",
    "dacl_protection": "SE_DACL_PROTECTED",
    "ace_order": "CURRENT_PRINCIPAL_FULL_CONTROL_OICI|LOCAL_SYSTEM_FULL_CONTROL_OICI|BUILTIN_ADMINISTRATORS_FULL_CONTROL_OICI",
    "inherited_aces": "FORBIDDEN",
    "other_allow_aces": "FORBIDDEN",
    "post_create_acl_mutation": "FORBIDDEN",
    "contract_version": "P3_P7_D02_R2_WINDOWS_PROTECTED_PRIVATE_DIRECTORY_DACL_V1",
}
_RESTRICTED_ACL_CONTRACT: Final[JsonObject] = {
    "projection_api": "GetSecurityInfo_BY_OPEN_HANDLE",
    "owner_role": "CURRENT_PRINCIPAL_SID",
    "null_dacl": "FORBIDDEN",
    "accepted_ace_types": "ACCESS_ALLOWED_ACE|ACCESS_DENIED_ACE",
    "accepted_ace_flags": "OBJECT_INHERIT_ACE|CONTAINER_INHERIT_ACE|NO_PROPAGATE_INHERIT_ACE|INHERIT_ONLY_ACE|INHERITED_ACE",
    "ace_applicability": "APPLIES_TO_CURRENT_DIRECTORY_IFF_INHERIT_ONLY_ACE_IS_CLEAR",
    "unknown_ace_flag": "STOP",
    "approved_write_roles": "CURRENT_PRINCIPAL_SID|LOCAL_SYSTEM|BUILTIN_ADMINISTRATORS",
    "dangerous_write_mask": "FILE_WRITE_DATA|FILE_APPEND_DATA|FILE_ADD_FILE|FILE_ADD_SUBDIRECTORY|FILE_DELETE_CHILD|DELETE|WRITE_DAC|WRITE_OWNER|GENERIC_WRITE|GENERIC_ALL",
    "generic_right_mapping_api": "MapGenericMask",
    "file_generic_mapping": "GenericRead=FILE_GENERIC_READ|GenericWrite=FILE_GENERIC_WRITE|GenericExecute=FILE_GENERIC_EXECUTE|GenericAll=FILE_ALL_ACCESS",
    "other_applicable_allow_dangerous_mask": "FORBIDDEN",
    "inherited_ace_policy": "ALLOWED_ONLY_WHEN_THE_SAME_APPLICABLE_MASK_RULE_PASSES",
    "required_current_principal_access": "GENERIC_READ|GENERIC_WRITE|READ_CONTROL|SYNCHRONIZE",
    "current_principal_access_verification": "AccessCheck_EXACT_HANDLE_SECURITY_DESCRIPTOR_AND_CURRENT_IMPERSONATION_TOKEN",
    "unknown_ace_type": "STOP",
    "contract_version": "P3_P7_D02_R2_WINDOWS_RESTRICTED_ANCESTOR_ACL_V1",
}
_KNOWN_FOLDER_CONTRACT_LITERALS: Final[JsonObject] = {
    "local_app_data_source": "SHGetKnownFolderPath(FOLDERID_LocalAppData)",
    "profile_source": "SHGetKnownFolderPath(FOLDERID_Profile)",
    "default_relation": "LOCAL_APP_DATA_IDENTITY_EQUALS_HANDLE_RELATIVE_PROFILE_APPDATA_LOCAL_IDENTITY",
    "volume_policy": "FIXED_LOCAL_VOLUME_REQUIRED",
    "forbidden_namespace_classes": "UNC|DEVICE|NETWORK",
    "reparse_tag_policy": "ZERO_REQUIRED",
    "cloud_file_attributes": "REPARSE_POINT|RECALL_ON_OPEN|RECALL_ON_DATA_ACCESS|PINNED|UNPINNED",
    "cloud_file_attributes_policy": "REJECT_IF_PRESENT",
    "onedrive_account_source": r"HKCU\Software\Microsoft\OneDrive\Accounts\*\UserFolder",
    "onedrive_value_type": "REG_SZ_ONLY",
    "onedrive_account_order": "CompareStringOrdinal(ignoreCase=TRUE)_THEN_UTF16_CODE_UNIT_ORDINAL",
    "onedrive_path_grammar": "NONEMPTY_ABSOLUTE_DOS_DRIVE_ROOTED_NO_EMBEDDED_NUL_NO_UNC_DEVICE_OR_EXTENDED_PREFIX",
    "onedrive_canonicalization": "GetFullPathNameW_THEN_OPEN_NOFOLLOW_THEN_GetFinalPathNameByHandleW(FILE_NAME_NORMALIZED|VOLUME_NAME_GUID)",
    "project_boundary_candidates": "LocalAppData/ProjectMirror-code-cache-v1|LocalAppData/ProjectMirror|LocalAppData/ProjectMirror/principal-private-output-v1|LocalAppData/ProjectMirror/principal-private-output-v1/bridge-scratch-v1",
    "onedrive_containment_comparison": "SAME_VOLUME_GUID_AND_CompareStringOrdinal(ignoreCase=TRUE)_EQUAL_OR_COMPONENT_BOUNDARY_DESCENDANT_IN_EITHER_DIRECTION",
    "onedrive_containment": "REJECT_ANY_PROJECT_BOUNDARY_OVERLAP",
    "malformed_or_nonabsolute_onedrive_value": "PRIVATE_HOME_BOUNDARY_INVALID_STOP",
    "unreadable_existing_onedrive_account": "STOP",
    "residual_boundary": "DETECTABLE_WINDOWS_KNOWN_FOLDER_REDIRECTION_CLOUD_FILES_AND_ONEDRIVE_RELATIONSHIPS_ARE_REJECTED_UNIVERSAL_THIRD_PARTY_SYNC_ABSENCE_IS_NOT_CLAIMED",
    "contract_version": "P3_P7_D02_R2_WINDOWS_KNOWN_FOLDER_BOUNDARY_V1",
}
_RESOLVER_CONTRACT_LITERALS: Final[JsonObject] = {
    "platform": "WINDOWS_LOCAL_DEMO",
    "known_folder_guid": "F1B32785-6FBA-4FCF-9D55-7B8E7F157091",
    "known_folder_api": "SHGetKnownFolderPath",
    "known_folder_flags": "KF_FLAG_DEFAULT",
    "code_cache_relative_component": "ProjectMirror-code-cache-v1",
    "ordered_project_relative_components": ["ProjectMirror", "principal-private-output-v1"],
    "control_plane_relative_root": "control-plane/p3-p7-d02-r2-locator-custody-v1",
    "evidence_relative_root": "d02-r2-evidence/p3-p7-d02-r2-cc08-e1-evidence",
    "bridge_scratch_relative_root": "bridge-scratch-v1",
    "canonicalization_version": "demo-canonical-json-v1",
}


def schema_contract_payload() -> JsonObject:
    return {
        "bridge_decision_policy_version": "P3_P7_D02_R2_LOCATOR_BRIDGE_DECISIONS_V1",
        "canonicalization_version": "demo-canonical-json-v1",
        "ordered_schema_versions": list(ORDERED_SCHEMA_VERSIONS),
        "relative_control_manifest": [dict(row) for row in RELATIVE_CONTROL_MANIFEST],
        "timestamp_policy_version": "P3_P7_D02_R2_LOCATOR_TIMESTAMPS_V1",
        "transition_matrix_version": "P3_P7_D02_R2_LOCATOR_TRANSITIONS_V1",
    }


def schema_contract_digest() -> str:
    return typed_digest(SCHEMA_CONTRACT, schema_contract_payload())


def typed_digest(schema_version: str, payload: Mapping[str, object]) -> str:
    """Strictly calculate the frozen typed digest without self-digest guessing."""
    _require_schema(schema_version)
    normalized = _json_object(payload)
    return mirror_demo_digest(schema_version, normalized)


def canonical_loads(raw: bytes) -> JsonObject:
    """Decode exactly one canonical JSON object; duplicate keys fail closed."""
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise LocatorCustodyError("CUSTODY_JSON_UTF8_INVALID_STOP") from exc

    def no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise LocatorCustodyError("CUSTODY_JSON_DUPLICATE_KEY_STOP")
            result[key] = value
        return result

    try:
        loaded = json.loads(text, object_pairs_hook=no_duplicates, parse_constant=_no_constant)
    except (TypeError, ValueError) as exc:
        if isinstance(exc, LocatorCustodyError):
            raise
        raise LocatorCustodyError("CUSTODY_JSON_INVALID_STOP") from exc
    if not isinstance(loaded, dict):
        raise LocatorCustodyError("CUSTODY_JSON_OBJECT_REQUIRED_STOP")
    result = _json_object(loaded)
    if canonical_json_bytes(result) != raw:
        raise LocatorCustodyError("CUSTODY_JSON_NONCANONICAL_STOP")
    return result


def load_trusted_acceptance_binding_source(
    raw: bytes,
    *,
    anchor_id: str,
) -> TrustedAcceptanceBindingSource:
    """Load one externally anchored canonical acceptance record.

    The anchor ID resolves only against code-frozen expectations. A caller
    cannot supply hashes derived from the candidate under validation.
    """

    if not isinstance(raw, bytes):
        raise LocatorCustodyError("CUSTODY_TRUSTED_BINDING_SOURCE_REQUIRED_STOP")
    if not isinstance(anchor_id, str):
        raise LocatorCustodyError("CUSTODY_TRUSTED_BINDING_SOURCE_REQUIRED_STOP")
    anchor = next((row for row in _FROZEN_ACCEPTANCE_ANCHORS if row[0] == anchor_id), None)
    if anchor is None:
        raise LocatorCustodyError("CUSTODY_TRUSTED_BINDING_ANCHOR_UNKNOWN_STOP")
    (
        _,
        expected_authority_id,
        expected_schema_version,
        expected_record_digest,
        expected_file_sha256,
    ) = anchor
    _id(expected_authority_id, "trusted authority id")
    _require_schema(expected_schema_version)
    _digest(expected_record_digest, "trusted record digest")
    _digest(expected_file_sha256, "trusted file sha256")
    if _sha256(raw) != expected_file_sha256:
        raise LocatorCustodyError("CUSTODY_TRUSTED_BINDING_SOURCE_MISMATCH_STOP")
    record = canonical_loads(raw)
    if (
        record.get("authority_id") != expected_authority_id
        or record.get("schema_version") != expected_schema_version
        or record.get("record_digest") != expected_record_digest
    ):
        raise LocatorCustodyError("CUSTODY_TRUSTED_BINDING_SOURCE_MISMATCH_STOP")
    validate_typed_record(record, expected_schema_version, "record_digest")
    return TrustedAcceptanceBindingSource(
        anchor_id=anchor_id,
        authority_id=expected_authority_id,
        schema_version=expected_schema_version,
        record_digest=expected_record_digest,
        source_file_sha256=expected_file_sha256,
        canonical_record_bytes=raw,
        _token=_TRUSTED_BINDING_SOURCE_TOKEN,
    )


def _no_constant(_: str) -> None:
    raise LocatorCustodyError("CUSTODY_JSON_NONFINITE_STOP")


def validate_typed_record(
    record: Mapping[str, object], schema: str, self_digest_key: str
) -> JsonObject:
    normalized = _json_object(record)
    _exact(normalized, set(normalized), "record")
    if normalized.get("schema_version") != schema:
        raise LocatorCustodyError("CUSTODY_SCHEMA_MISMATCH_STOP")
    digest = normalized.get(self_digest_key)
    _digest(digest, self_digest_key)
    payload = {key: value for key, value in normalized.items() if key != self_digest_key}
    if typed_digest(schema, payload) != digest:
        raise LocatorCustodyError("CUSTODY_TYPED_DIGEST_MISMATCH_STOP")
    return normalized


def validate_plan_acceptance(
    record: Mapping[str, object], *, expected_bindings: TrustedAcceptanceBindingSource
) -> JsonObject:
    keys = {
        "schema_version",
        "authority_id",
        "change_control_id",
        "reviewed_plan_file_sha256",
        "reviewed_plan_git_blob_oid",
        "reviewed_risk_register_file_sha256",
        "reviewed_risk_register_git_blob_oid",
        "accepted_governance_sha",
        "accepted_governance_tree",
        "base_sha",
        "schema_contract_digest",
        "independent_review",
        "same_sha_ci",
        "principal_acceptance",
        "authorized_implementation_paths",
        "authorized_validation_actions",
        "authorized_scope",
        "prohibited_scope",
        "record_created_at_utc",
        "record_digest",
    }
    value = _validate_acceptance(
        record, PLAN_SCHEMA, "record_digest", keys, "accepted_governance_sha"
    )
    _validate_trusted_record_bindings(value, expected_bindings, "record_digest")
    paths = value["authorized_implementation_paths"]
    expected_paths = [
        "services/api/src/mirror_api/demo_d02_r2_locator_custody.py",
        "services/api/tests/test_demo_d02_r2_locator_custody.py",
    ]
    if (
        paths != expected_paths
        or value["authority_id"] != "P3_P7_D02_R2_LOCATOR_CUSTODY_PLAN_ACCEPTANCE_01"
        or value["change_control_id"] != "P3_P7_D02_CC_09"
        or value["authorized_validation_actions"]
        != [
            "RUFF_FORMAT_AND_CHECK_AUTHORIZED_PATHS_ONLY",
            "STRICT_MYPY_AUTHORIZED_IMPLEMENTATION_ONLY",
            "TARGETED_PYTEST_SYNTHETIC_TEMP_ROOTS_ONLY",
            "GIT_DIFF_CHECK",
            "INDEPENDENT_EXACT_SHA_IMPLEMENTATION_REVIEW",
            "SAME_SHA_CI",
        ]
        or value["authorized_scope"]
        != "IMPLEMENT_AND_VALIDATE_EXACT_TWO_FILE_CC09_LOCATOR_CUSTODY_ONLY"
        or value["prohibited_scope"]
        != [
            "ANY_TRACKED_PATH_OUTSIDE_AUTHORIZED_IMPLEMENTATION_PATHS",
            "HOST_SPECIFIC_DIRECTORY_OPERATION",
            "WINDOWS_HOST_BINDING_CANDIDATE_OR_ACCEPTANCE",
            "PRIVATE_HOME_CREATION_OR_BINDING",
            "LOCATOR_NAMESPACE_CREATION",
            "LOCATOR_EVENT_CREATION",
            "CC08_EVIDENCE_ROOT_CREATION",
            "R05_REHOME",
            "SOURCE_GENERATION",
            "M3_M4_EXECUTION",
            "MIGRATION_OR_ORM",
            "POSTGRESQL_ADMISSION",
            "PUBLIC_API_CHANGE",
            "DEPENDENCY_CHANGE",
            "D02_R2_TASK_ACCEPTANCE",
            "D03_D04_B_D07_B_OPENING",
            "FORMAL_PHASE_AUTHORITY",
            "PRODUCTION_RELEASE",
        ]
    ):
        raise LocatorCustodyError("CUSTODY_IMPLEMENTATION_BOUNDARY_STOP")
    return value


def validate_implementation_acceptance(
    record: Mapping[str, object],
    plan: Mapping[str, object],
    *,
    expected_bindings: TrustedAcceptanceBindingSource,
    plan_expected_bindings: TrustedAcceptanceBindingSource,
) -> JsonObject:
    value = _validate_implementation_acceptance_core(
        record,
        plan,
        plan_expected_bindings=plan_expected_bindings,
    )
    _validate_trusted_record_bindings(value, expected_bindings, "record_digest")
    return value


def _validate_implementation_acceptance_core(
    record: Mapping[str, object],
    plan: Mapping[str, object],
    *,
    plan_expected_bindings: TrustedAcceptanceBindingSource,
) -> JsonObject:
    keys = {
        "schema_version",
        "authority_id",
        "change_control_id",
        "accepted_plan_sha",
        "accepted_plan_tree",
        "accepted_plan_acceptance_record_digest",
        "implementation_sha",
        "implementation_tree",
        "governed_paths",
        "schema_contract_digest",
        "independent_review",
        "same_sha_ci",
        "principal_acceptance",
        "authorized_scope",
        "prohibited_scope",
        "record_created_at_utc",
        "record_digest",
    }
    value = _validate_acceptance(
        record, IMPLEMENTATION_SCHEMA, "record_digest", keys, "implementation_sha"
    )
    checked_plan = validate_plan_acceptance(plan, expected_bindings=plan_expected_bindings)
    if (
        value["authority_id"] != "P3_P7_D02_R2_LOCATOR_CUSTODY_IMPLEMENTATION_ACCEPTANCE_01"
        or value["change_control_id"] != "P3_P7_D02_CC_09"
        or value["authorized_scope"] != "READ_ONLY_WINDOWS_HOST_BINDING_CANDIDATE_PROJECTION_ONLY"
        or value["accepted_plan_acceptance_record_digest"] != checked_plan["record_digest"]
        or value["accepted_plan_sha"] != checked_plan["accepted_governance_sha"]
        or value["accepted_plan_tree"] != checked_plan["accepted_governance_tree"]
        or value["schema_contract_digest"] != checked_plan["schema_contract_digest"]
        or value["prohibited_scope"]
        != [
            "ANY_IMPLEMENTATION_OR_TEST_PATH_CHANGE",
            "HOST_SPECIFIC_DIRECTORY_CREATION_OR_MUTATION",
            "PRIVATE_HOME_CREATION",
            "PRIVATE_HOME_BINDING_ACCEPTANCE",
            "LOCATOR_NAMESPACE_CREATION",
            "LOCATOR_EVENT_CREATION",
            "CC08_EVIDENCE_ROOT_CREATION_OR_REPLAY",
            "R05_REHOME",
            "SOURCE_GENERATION",
            "M3_M4_EXECUTION",
            "MIGRATION_OR_ORM",
            "POSTGRESQL_ADMISSION",
            "PUBLIC_API_CHANGE",
            "D02_R2_TASK_ACCEPTANCE",
            "D03_D04_B_D07_B_OPENING",
            "FORMAL_PHASE_AUTHORITY",
            "PRODUCTION_RELEASE",
        ]
    ):
        raise LocatorCustodyError("CUSTODY_FUTURE_AUTHORITY_OR_PLAN_MISMATCH_STOP")
    governed = value["governed_paths"]
    if (
        not isinstance(governed, list)
        or [row.get("path") if isinstance(row, dict) else None for row in governed]
        != checked_plan["authorized_implementation_paths"]
    ):
        raise LocatorCustodyError("CUSTODY_IMPLEMENTATION_BOUNDARY_STOP")
    for row in governed:
        if not isinstance(row, dict):
            raise LocatorCustodyError("CUSTODY_GOVERNED_PATH_INVALID_STOP")
        _exact(row, {"path", "sha256", "git_blob_oid"}, "governed path")
        if not isinstance(row["path"], str):
            raise LocatorCustodyError("CUSTODY_GOVERNED_PATH_INVALID_STOP")
        _digest(row["sha256"], "sha256")
        _sha(row["git_blob_oid"], "git blob")
    return value


def _validate_acceptance(
    record: Mapping[str, object], schema: str, digest_key: str, keys: set[str], sha_key: str
) -> JsonObject:
    value = _json_object(record)
    _exact(value, keys, "acceptance")
    validate_typed_record(value, schema, digest_key)
    _id(value["authority_id"], "authority id")
    _id(value["change_control_id"], "change control id")
    _sha(value[sha_key], sha_key)
    _sha(value["base_sha"] if "base_sha" in value else value["accepted_plan_sha"], "base sha")
    _digest(value["schema_contract_digest"], "schema contract digest")
    _timestamp(value["record_created_at_utc"])
    for key, item in value.items():
        if key.endswith("_file_sha256"):
            _digest(item, key)
        elif key.endswith("_git_blob_oid") or key.endswith("_tree"):
            _sha(item, key)
        elif key.endswith("_record_digest"):
            _digest(item, key)
    review_sha = (
        "reviewed_governance_sha" if schema == PLAN_SCHEMA else "reviewed_implementation_sha"
    )
    accepted_key = (
        "accepted_governance_sha" if schema == PLAN_SCHEMA else "accepted_implementation_sha"
    )
    _validate_acceptance_evidence(
        value,
        accepted_sha_key=sha_key,
        review_sha_key=review_sha,
        principal_sha_key=accepted_key,
    )
    return value


def _validate_trusted_record_bindings(
    value: Mapping[str, Json],
    expected_bindings: TrustedAcceptanceBindingSource,
    digest_key: str,
) -> None:
    """Require canonical bytes loaded through an external trust anchor."""
    if not isinstance(expected_bindings, TrustedAcceptanceBindingSource):
        raise LocatorCustodyError("CUSTODY_TRUSTED_BINDING_SOURCE_REQUIRED_STOP")
    if (
        expected_bindings._token is not _TRUSTED_BINDING_SOURCE_TOKEN
        or not any(
            row
            == (
                expected_bindings.anchor_id,
                expected_bindings.authority_id,
                expected_bindings.schema_version,
                expected_bindings.record_digest,
                expected_bindings.source_file_sha256,
            )
            for row in _FROZEN_ACCEPTANCE_ANCHORS
        )
        or _sha256(expected_bindings.canonical_record_bytes) != expected_bindings.source_file_sha256
    ):
        raise LocatorCustodyError("CUSTODY_TRUSTED_BINDING_SOURCE_MISMATCH_STOP")
    trusted_record = canonical_loads(expected_bindings.canonical_record_bytes)
    validate_typed_record(trusted_record, expected_bindings.schema_version, digest_key)
    if (
        trusted_record.get("authority_id") != expected_bindings.authority_id
        or trusted_record.get("schema_version") != expected_bindings.schema_version
        or trusted_record.get(digest_key) != expected_bindings.record_digest
        or value.get("authority_id") != expected_bindings.authority_id
        or value.get("schema_version") != expected_bindings.schema_version
        or value.get(digest_key) != expected_bindings.record_digest
    ):
        raise LocatorCustodyError("CUSTODY_ACCEPTED_BINDING_DRIFT_STOP")
    expected = {key: item for key, item in trusted_record.items() if key != digest_key}
    _exact(expected, set(value) - {digest_key}, "trusted acceptance bindings")
    if any(value[key] != expected[key] for key in expected):
        raise LocatorCustodyError("CUSTODY_ACCEPTED_BINDING_DRIFT_STOP")


def _trusted_acceptance_record(
    source: TrustedAcceptanceBindingSource,
    *,
    schema: str,
    authority_id: str,
) -> JsonObject:
    if (
        not isinstance(source, TrustedAcceptanceBindingSource)
        or source.schema_version != schema
        or source.authority_id != authority_id
    ):
        raise LocatorCustodyError("CUSTODY_BOOTSTRAP_AUTHORITY_ANCHOR_REQUIRED_STOP")
    record = canonical_loads(source.canonical_record_bytes)
    _validate_trusted_record_bindings(record, source, "record_digest")
    return record


def load_locator_bootstrap_authority_anchor(
    *,
    implementation_acceptance: TrustedAcceptanceBindingSource,
    private_home_acceptance: TrustedAcceptanceBindingSource,
) -> LocatorBootstrapAuthorityAnchor:
    """Mint a synthetic-test bootstrap projection from frozen acceptance bytes.

    This helper is not the future real-host authority loader.  In particular,
    fixed tracked paths, self-consistent acceptance JSON, and Python object
    identity are not candidate-independent checkout proof.  A later accepted
    host bridge must introduce and replay its own independently sealed checkout
    authority before any real namespace write; this module deliberately has no
    such real-host entry point in the current implementation checkpoint.
    """

    implementation = _trusted_acceptance_record(
        implementation_acceptance,
        schema=IMPLEMENTATION_SCHEMA,
        authority_id="P3_P7_D02_R2_LOCATOR_CUSTODY_IMPLEMENTATION_ACCEPTANCE_01",
    )
    private_home = _trusted_acceptance_record(
        private_home_acceptance,
        schema="mirror.demo/D02R2PrivateHomeBindingAcceptance/v1",
        authority_id="P3_P7_D02_R2_PRIVATE_HOME_BINDING_ACCEPTANCE_01",
    )
    if (
        private_home.get("locator_custody_implementation_acceptance_record_digest")
        != implementation["record_digest"]
    ):
        raise LocatorCustodyError("CUSTODY_BOOTSTRAP_AUTHORITY_ANCHOR_MISMATCH_STOP")
    implementation_sha = implementation.get("implementation_sha")
    host_acceptance_digest = private_home.get("host_binding_acceptance_record_digest")
    created_at = implementation.get("record_created_at_utc")
    _sha(implementation_sha, "bootstrap implementation SHA")
    _digest(host_acceptance_digest, "bootstrap host acceptance")
    _timestamp(created_at)
    return LocatorBootstrapAuthorityAnchor(
        implementation_sha=cast(str, implementation_sha),
        implementation_acceptance_record_digest=cast(str, implementation["record_digest"]),
        host_binding_acceptance_record_digest=cast(str, host_acceptance_digest),
        private_home_binding_acceptance_record_digest=private_home_acceptance.record_digest,
        authority_created_at_utc=cast(str, created_at),
        _token=_BOOTSTRAP_AUTHORITY_ANCHOR_TOKEN,
    )


def _validate_acceptance_evidence(
    value: Mapping[str, Json],
    *,
    accepted_sha_key: str,
    review_sha_key: str,
    principal_sha_key: str,
) -> None:
    """Validate the fixed nested review/CI/Principal evidence shapes.

    The expected SHA is supplied by the surrounding independently-bound record;
    this helper never derives an authority expectation from a nested object.
    """
    review = _mapping(value["independent_review"], "review")
    _exact(
        review,
        {"evidence_digest", *_REVIEW_FINDING_KEYS, "result", "review_task_id", review_sha_key},
        "review",
    )
    _digest(review["evidence_digest"], "review evidence digest")
    _id(review["review_task_id"], "review task id")
    _sha(review[review_sha_key], "reviewed SHA")
    if (
        review[review_sha_key] != value[accepted_sha_key]
        or review["result"] != "PASS"
        or any(
            not isinstance(review[key], int) or isinstance(review[key], bool) or review[key] != 0
            for key in _REVIEW_FINDING_KEYS
        )
    ):
        raise LocatorCustodyError("CUSTODY_REVIEW_BINDING_STOP")
    ci = _mapping(value["same_sha_ci"], "same-SHA CI")
    _exact(ci, _SAME_SHA_CI_KEYS, "same-SHA CI")
    _digest(ci["artifact_manifest_digest"], "CI artifact manifest digest")
    _sha(ci["head_sha"], "CI head SHA")
    if (
        ci["head_sha"] != value[accepted_sha_key]
        or ci["provider"] != "GITHUB_ACTIONS"
        or ci["repository"] != "yangyy816/project-mirror"
        or ci["required_jobs"] != _REQUIRED_CI_JOBS
        or ci["result"] != "PASS"
        or ci["workflow_identity"] != ".github/workflows/ci.yml"
        or not isinstance(ci["run_id"], int)
        or isinstance(ci["run_id"], bool)
        or ci["run_id"] < 1
    ):
        raise LocatorCustodyError("CUSTODY_SAME_SHA_CI_STOP")
    acceptance = _mapping(value["principal_acceptance"], "principal acceptance")
    _exact(
        acceptance,
        {"status", principal_sha_key, "accepted_at_utc", "acceptance_authority_digest"},
        "principal acceptance",
    )
    _sha(acceptance[principal_sha_key], "principal accepted SHA")
    _timestamp(acceptance["accepted_at_utc"])
    _digest(acceptance["acceptance_authority_digest"], "principal acceptance authority digest")
    if (
        acceptance["status"] != "PRINCIPAL_ACCEPTED"
        or acceptance[principal_sha_key] != value[accepted_sha_key]
        or acceptance["accepted_at_utc"] != value["record_created_at_utc"]
    ):
        raise LocatorCustodyError("CUSTODY_PRINCIPAL_ACCEPTANCE_STOP")


def make_transaction(
    *,
    namespace_receipt_digest: str,
    locator_name_receipt_digest: str,
    locator_authority_id: str,
    allocation_id: str,
    evidence_root_id: str,
    root_basename: str,
    opaque_locator: str,
    locator_digest: str,
    sequence: int,
    previous_event_digest: str,
    decision: str,
    authority_state: str,
    transition_at_utc: str,
    root_receipt_created_at_utc: str | None,
    root_fields: Mapping[str, str | None],
    copy_a_prior_snapshot_digest: str,
    copy_b_prior_snapshot_digest: str,
) -> tuple[JsonObject, JsonObject]:
    """Build one immutable event and its only permitted recovery intent."""
    _sequence(sequence)
    _timestamp(transition_at_utc)
    transaction_payload: JsonObject = {
        "namespace_receipt_digest": namespace_receipt_digest,
        "locator_name_receipt_digest": locator_name_receipt_digest,
        "locator_authority_id": locator_authority_id,
        "allocation_id": allocation_id,
        "evidence_root_id": evidence_root_id,
        "sequence": sequence,
        "previous_event_digest": previous_event_digest,
        "decision": decision,
        "authority_state": authority_state,
        "transition_at_utc": transition_at_utc,
    }
    transaction_id = typed_digest(TRANSACTION_ID_SCHEMA, transaction_payload)
    event: JsonObject = {
        "schema_version": EVENT_SCHEMA,
        **transaction_payload,
        "root_basename": root_basename,
        "opaque_locator": opaque_locator,
        "locator_digest": locator_digest,
        "transaction_id": transaction_id,
        "root_receipt_created_at_utc": root_receipt_created_at_utc,
        "accepted_cc08_plan_sha": root_fields["accepted_cc08_plan_sha"],
        "accepted_cc08_plan_tree": root_fields["accepted_cc08_plan_tree"],
        "registry_implementation_sha": root_fields["registry_implementation_sha"],
        "registry_implementation_tree": root_fields["registry_implementation_tree"],
        "registry_implementation_acceptance_record_digest": root_fields[
            "registry_implementation_acceptance_record_digest"
        ],
        "registry_implementation_acceptance_authority_digest": root_fields[
            "registry_implementation_acceptance_authority_digest"
        ],
        "parent_identity_digest": root_fields["parent_identity_digest"],
        "excluded_worktree_set_digest": root_fields["excluded_worktree_set_digest"],
        "root_identity_digest": root_fields["root_identity_digest"],
        "root_receipt_digest": root_fields["root_receipt_digest"],
        "root_registry_state": root_fields["root_registry_state"],
        "root_registry_common_genesis_digest": root_fields["root_registry_common_genesis_digest"],
        "root_registry_copy_a_snapshot_digest": root_fields["root_registry_copy_a_snapshot_digest"],
        "root_registry_copy_b_snapshot_digest": root_fields["root_registry_copy_b_snapshot_digest"],
    }
    event["event_digest"] = typed_digest(EVENT_SCHEMA, event)
    raw = canonical_json_bytes(event)
    intent: JsonObject = {
        "schema_version": INTENT_SCHEMA,
        "namespace_receipt_digest": namespace_receipt_digest,
        "locator_name_receipt_digest": locator_name_receipt_digest,
        "locator_authority_id": locator_authority_id,
        "allocation_id": allocation_id,
        "evidence_root_id": evidence_root_id,
        "transaction_id": transaction_id,
        "expected_sequence": sequence,
        "expected_previous_event_digest": previous_event_digest,
        "decision": decision,
        "authority_state": authority_state,
        "canonical_event_base64url": _b64(raw),
        "canonical_event_sha256": _sha256(raw),
        "event_digest": event["event_digest"],
        "copy_a_prior_snapshot_digest": copy_a_prior_snapshot_digest,
        "copy_b_prior_snapshot_digest": copy_b_prior_snapshot_digest,
        "intent_created_at_utc": transition_at_utc,
        "commit_created_at_utc": transition_at_utc,
    }
    intent["intent_digest"] = typed_digest(INTENT_SCHEMA, intent)
    validate_transition(event, intent)
    return event, intent


def validate_transition(event: Mapping[str, object], intent: Mapping[str, object]) -> None:
    event_value = validate_typed_record(event, EVENT_SCHEMA, "event_digest")
    intent_value = validate_typed_record(intent, INTENT_SCHEMA, "intent_digest")
    required_event = {
        "schema_version",
        "namespace_receipt_digest",
        "locator_name_receipt_digest",
        "locator_authority_id",
        "allocation_id",
        "evidence_root_id",
        "root_basename",
        "opaque_locator",
        "locator_digest",
        "transaction_id",
        "decision",
        "authority_state",
        "transition_at_utc",
        "root_receipt_created_at_utc",
        "accepted_cc08_plan_sha",
        "accepted_cc08_plan_tree",
        "registry_implementation_sha",
        "registry_implementation_tree",
        "registry_implementation_acceptance_record_digest",
        "registry_implementation_acceptance_authority_digest",
        "parent_identity_digest",
        "excluded_worktree_set_digest",
        "root_identity_digest",
        "root_receipt_digest",
        "root_registry_state",
        "root_registry_common_genesis_digest",
        "root_registry_copy_a_snapshot_digest",
        "root_registry_copy_b_snapshot_digest",
        "sequence",
        "previous_event_digest",
        "event_digest",
    }
    required_intent = {
        "schema_version",
        "namespace_receipt_digest",
        "locator_name_receipt_digest",
        "locator_authority_id",
        "allocation_id",
        "evidence_root_id",
        "transaction_id",
        "expected_sequence",
        "expected_previous_event_digest",
        "decision",
        "authority_state",
        "canonical_event_base64url",
        "canonical_event_sha256",
        "event_digest",
        "copy_a_prior_snapshot_digest",
        "copy_b_prior_snapshot_digest",
        "intent_created_at_utc",
        "commit_created_at_utc",
        "intent_digest",
    }
    _exact(event_value, required_event, "event")
    _exact(intent_value, required_intent, "intent")
    _sequence(event_value["sequence"])
    transaction_payload = {
        key: event_value[key]
        for key in (
            "namespace_receipt_digest",
            "locator_name_receipt_digest",
            "locator_authority_id",
            "allocation_id",
            "evidence_root_id",
            "sequence",
            "previous_event_digest",
            "decision",
            "authority_state",
            "transition_at_utc",
        )
    }
    if event_value["transaction_id"] != typed_digest(TRANSACTION_ID_SCHEMA, transaction_payload):
        raise LocatorCustodyError("LOCATOR_INTENT_PARTIAL_OR_CORRUPT_STOP")
    if (
        event_value["transition_at_utc"] != intent_value["intent_created_at_utc"]
        or event_value["transition_at_utc"] != intent_value["commit_created_at_utc"]
    ):
        raise LocatorCustodyError("LOCATOR_INTENT_PARTIAL_OR_CORRUPT_STOP")
    _timestamp(event_value["transition_at_utc"])
    _timestamp(intent_value["intent_created_at_utc"])
    _timestamp(intent_value["commit_created_at_utc"])
    if event_value["root_receipt_created_at_utc"] is None:
        raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
    _timestamp(event_value["root_receipt_created_at_utc"])
    if _unb64(intent_value["canonical_event_base64url"]) != canonical_json_bytes(event_value):
        raise LocatorCustodyError("LOCATOR_INTENT_PARTIAL_OR_CORRUPT_STOP")
    for event_key, intent_key in (
        ("namespace_receipt_digest", "namespace_receipt_digest"),
        ("locator_name_receipt_digest", "locator_name_receipt_digest"),
        ("locator_authority_id", "locator_authority_id"),
        ("allocation_id", "allocation_id"),
        ("evidence_root_id", "evidence_root_id"),
        ("transaction_id", "transaction_id"),
        ("sequence", "expected_sequence"),
        ("previous_event_digest", "expected_previous_event_digest"),
        ("decision", "decision"),
        ("authority_state", "authority_state"),
        ("event_digest", "event_digest"),
    ):
        if event_value[event_key] != intent_value[intent_key]:
            raise LocatorCustodyError("LOCATOR_INTENT_PARTIAL_OR_CORRUPT_STOP")
    if intent_value["canonical_event_sha256"] != _sha256(canonical_json_bytes(event_value)):
        raise LocatorCustodyError("LOCATOR_INTENT_PARTIAL_OR_CORRUPT_STOP")
    _validate_transition_matrix(event_value)


def _validate_transition_matrix(event: Mapping[str, Json]) -> None:
    sequence = cast(int, event["sequence"])
    required: tuple[str, ...]
    nulls: tuple[str, ...]
    expected = {
        1: ("CREATE_NEW", "PREPARED"),
        2: (None, "ROOT_RECEIPT_DURABLE"),
        3: (None, "ROOT_REGISTRY_READY"),
    }.get(sequence)
    if (
        expected is None
        or event["authority_state"] != expected[1]
        or (expected[0] is not None and event["decision"] != expected[0])
        or (sequence in {2, 3} and event["decision"] not in {"CREATE_NEW", "RECOVER_EXISTING"})
    ):
        raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
    if sequence == 1:
        required = ("parent_identity_digest", "excluded_worktree_set_digest")
        nulls = (
            "root_identity_digest",
            "root_receipt_digest",
            "root_registry_state",
            "root_registry_common_genesis_digest",
            "root_registry_copy_a_snapshot_digest",
            "root_registry_copy_b_snapshot_digest",
        )
    elif sequence == 2:
        required = ("root_identity_digest", "root_receipt_digest", "root_registry_state")
        nulls = (
            "root_registry_common_genesis_digest",
            "root_registry_copy_a_snapshot_digest",
            "root_registry_copy_b_snapshot_digest",
        )
    else:
        required = (
            "root_identity_digest",
            "root_receipt_digest",
            "root_registry_state",
            "root_registry_common_genesis_digest",
            "root_registry_copy_a_snapshot_digest",
            "root_registry_copy_b_snapshot_digest",
        )
        nulls = ()
    if any(event[key] is None for key in required) or any(event[key] is not None for key in nulls):
        raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
    if sequence == 2 and event["root_registry_state"] != "NOT_INITIALIZED":
        raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
    if sequence == 3 and event["root_registry_state"] != "READY_EMPTY":
        raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")


def read_single_binary_frame(data: bytes, maximum_bytes: int = 262_144) -> bytes:
    """Read one length-prefixed UTF-8-safe bridge frame, with no trailing input."""
    if len(data) < 4:
        raise LocatorCustodyError("BRIDGE_FRAME_TRUNCATED_STOP")
    length = int.from_bytes(data[:4], "big")
    if length > maximum_bytes or len(data) != length + 4:
        raise LocatorCustodyError("BRIDGE_FRAME_INVALID_STOP")
    return data[4:]


def validate_windows_principal_sid(preimage: Mapping[str, object]) -> str:
    """Validate the private SID preimage retained only by the injected adapter."""
    value = _json_object(preimage)
    _exact(value, set(WINDOWS_WIRE_SCHEMA_FIELDS[SID_SCHEMA]), "SID")
    sid = value["sid_string"]
    if not isinstance(sid, str) or re.fullmatch(r"S-[0-9]+(?:-[0-9]+)+", sid) is None:
        raise LocatorCustodyError("WINDOWS_PRINCIPAL_SID_CHANGED_STOP")
    return typed_digest(SID_SCHEMA, value)


def validate_windows_file_identity(preimage: Mapping[str, object], *, executable: bool) -> str:
    """Validate one same-open-handle file identity projection, never a path."""
    schema = FILE_SCHEMA
    if executable:
        schema = EXECUTABLE_SCHEMA
    value = _json_object(preimage)
    _exact(value, set(WINDOWS_WIRE_SCHEMA_FIELDS[schema]), "Windows file identity")
    _hex(value["volume_serial_number_hex"], 16)
    _hex(value["file_id_128_hex"], 32)
    if (
        not isinstance(value["file_size"], int)
        or isinstance(value["file_size"], bool)
        or value["file_size"] < 0
    ):
        raise LocatorCustodyError("DETACHED_RUNTIME_IDENTITY_CHANGED_STOP")
    _digest(value["file_sha256"], "file SHA")
    if executable and not all(
        isinstance(value[key], str) and value[key]
        for key in ("product_name", "product_version", "machine_type")
    ):
        raise LocatorCustodyError("DETACHED_RUNTIME_IDENTITY_CHANGED_STOP")
    return typed_digest(schema, value)


def validate_windows_path_identity(record: Mapping[str, object]) -> str:
    value = _json_object(record)
    _exact(value, set(WINDOWS_WIRE_SCHEMA_FIELDS[PATH_IDENTITY_SCHEMA]), "Windows path identity")
    if value["schema_version"] != PATH_IDENTITY_SCHEMA:
        raise LocatorCustodyError("KNOWN_FOLDER_IDENTITY_CHANGED_STOP")
    if value["path_role"] not in {
        "KNOWN_FOLDER",
        "WINDOWS_DIRECTORY",
        "WINDOWS_SYSTEM_DIRECTORY",
        "POWERSHELL_MODULE_ROOT",
        "PROJECT_CODE_CACHE",
        "ACCEPTED_R06_CHECKOUT",
        "PROJECT_CONTAINER",
        "PRIVATE_HOME",
        "BRIDGE_SCRATCH",
        "EVIDENCE_PARENT",
        "EVIDENCE_ROOT",
        "GIT_COMMON_DIR",
        "GIT_WORKTREE_ROOT",
    }:
        raise LocatorCustodyError("KNOWN_FOLDER_IDENTITY_CHANGED_STOP")
    _hex(value["volume_serial_number_hex"], 16)
    _hex(value["file_id_128_hex"], 32)
    attributes_hex = _hex(value["file_attributes_hex"], 8)
    _hex(value["reparse_tag_hex"], 8)
    if value["is_directory"] is not True or value["reparse_tag_hex"] != "00000000":
        raise LocatorCustodyError("PRIVATE_HOME_BOUNDARY_INVALID_STOP")
    attributes = int(attributes_hex, 16)
    if attributes & 0x400 or not attributes & 0x10:
        raise LocatorCustodyError("PRIVATE_HOME_BOUNDARY_INVALID_STOP")
    payload = {key: item for key, item in value.items() if key != "identity_digest"}
    if value["identity_digest"] != typed_digest(PATH_IDENTITY_SCHEMA, payload):
        raise LocatorCustodyError("KNOWN_FOLDER_IDENTITY_CHANGED_STOP")
    return value["identity_digest"]


def validate_same_open_handle_path_identity(
    expected: Mapping[str, object], observed: Mapping[str, object], *, role: str
) -> str:
    """Require a still-open-handle replay to preserve role and physical identity."""
    expected_value = _json_object(expected)
    observed_value = _json_object(observed)
    expected_digest = validate_windows_path_identity(expected_value)
    observed_digest = validate_windows_path_identity(observed_value)
    if (
        expected_value["path_role"] != role
        or observed_value["path_role"] != role
        or expected_digest != observed_digest
    ):
        raise LocatorCustodyError("CUSTODY_PARENT_IDENTITY_CHANGED_STOP")
    return observed_digest


def _validate_exact_contract(
    record: Mapping[str, object], schema: str, expected: Mapping[str, Json]
) -> str:
    value = _json_object(record)
    _exact(value, set(WINDOWS_WIRE_SCHEMA_FIELDS[schema]), "Windows contract")
    if value != expected:
        raise LocatorCustodyError("WINDOWS_CONTRACT_PROJECTION_MISMATCH_STOP")
    return typed_digest(schema, value)


def validate_windows_native_relative_create_contract(record: Mapping[str, object]) -> str:
    return _validate_exact_contract(record, NATIVE_CREATE_SCHEMA, _NATIVE_CREATE_CONTRACT)


def validate_windows_protected_directory_dacl_contract(record: Mapping[str, object]) -> str:
    return _validate_exact_contract(record, PROTECTED_DACL_SCHEMA, _PROTECTED_DACL_CONTRACT)


def validate_windows_restricted_ancestor_acl_contract(record: Mapping[str, object]) -> str:
    return _validate_exact_contract(record, RESTRICTED_ACL_SCHEMA, _RESTRICTED_ACL_CONTRACT)


def validate_windows_known_folder_boundary_contract(record: Mapping[str, object]) -> str:
    value = _json_object(record)
    _exact(value, set(WINDOWS_WIRE_SCHEMA_FIELDS[KNOWN_FOLDER_SCHEMA]), "Known Folder contract")
    if value.get("ancestor_acl_contract_digest") is None:
        raise LocatorCustodyError("CUSTODY_DIGEST_GRAMMAR_STOP")
    _digest(value["ancestor_acl_contract_digest"], "ancestor ACL contract")
    expected = {
        **_KNOWN_FOLDER_CONTRACT_LITERALS,
        "ancestor_acl_contract_digest": value["ancestor_acl_contract_digest"],
    }
    if value != expected:
        raise LocatorCustodyError("WINDOWS_CONTRACT_PROJECTION_MISMATCH_STOP")
    return typed_digest(KNOWN_FOLDER_SCHEMA, value)


def validate_project_private_home_resolver_contract(record: Mapping[str, object]) -> str:
    value = _json_object(record)
    _exact(
        value, set(WINDOWS_WIRE_SCHEMA_FIELDS[RESOLVER_SCHEMA]), "private home resolver contract"
    )
    for key in ("known_folder_boundary_contract_digest", "restricted_ancestor_acl_contract_digest"):
        _digest(value[key], key)
    expected = {
        **_RESOLVER_CONTRACT_LITERALS,
        "known_folder_boundary_contract_digest": value["known_folder_boundary_contract_digest"],
        "restricted_ancestor_acl_contract_digest": value["restricted_ancestor_acl_contract_digest"],
    }
    if value != expected:
        raise LocatorCustodyError("WINDOWS_CONTRACT_PROJECTION_MISMATCH_STOP")
    return typed_digest(RESOLVER_SCHEMA, value)


def frozen_windows_contracts() -> dict[str, JsonObject]:
    """Frozen contract payloads whose digests are bound into host candidates."""
    return {
        NATIVE_CREATE_SCHEMA: dict(_NATIVE_CREATE_CONTRACT),
        PROTECTED_DACL_SCHEMA: dict(_PROTECTED_DACL_CONTRACT),
        RESTRICTED_ACL_SCHEMA: dict(_RESTRICTED_ACL_CONTRACT),
    }


def contract_digest(schema: str) -> str:
    contracts = frozen_windows_contracts()
    if schema not in contracts:
        raise LocatorCustodyError("CUSTODY_SCHEMA_MISMATCH_STOP")
    return typed_digest(schema, contracts[schema])


def validate_native_create_request(request: Mapping[str, object]) -> None:
    value = _json_object(request)
    _exact(
        value,
        {
            "parent_handle_id",
            "component",
            "disposition",
            "object_attributes_flags",
            "parent_flushed",
        },
        "native request",
    )
    component = value["component"]
    if (
        not isinstance(component, str)
        or not component
        or any(token in component for token in ("/", "\\", ":"))
        or component in {".", ".."}
    ):
        raise LocatorCustodyError("HANDLE_RELATIVE_CREATION_UNAVAILABLE_STOP")
    if (
        value["disposition"] != "FILE_CREATE"
        or value["object_attributes_flags"] != "OBJ_CASE_INSENSITIVE|OBJ_DONT_REPARSE"
        or value["parent_flushed"] is not True
        or not isinstance(value["parent_handle_id"], str)
    ):
        raise LocatorCustodyError("CUSTODY_DURABILITY_BARRIER_FAILED_STOP")


@dataclass
class SyntheticNativeCreateAdapter:
    """Pure event model for the frozen handle-relative durability sequence.

    It deliberately stores only component labels, never a filesystem path or
    bytes.  A failed post-create durability check retains its prior write event
    but never marks it durable, matching the required preserve-and-stop rule.
    """

    writes: list[str] = field(default_factory=list)
    durable_components: list[str] = field(default_factory=list)

    def create(self, observation: Mapping[str, object]) -> None:
        value = _json_object(observation)
        _exact(
            value,
            {
                "parent_handle_id",
                "component",
                "disposition",
                "object_attributes_flags",
                "parent_flushed",
                "native_binding_available",
                "parent_no_delete_share",
                "parent_identity_matches",
                "parent_dacl_matches",
                "creation_time_protected_dacl",
                "child_kind",
                "child_reparse",
                "child_identity_matches",
                "child_dacl_matches",
                "file_write_complete",
                "file_flush_success",
                "parent_flush_success",
                "reopen_identity_matches",
                "reopen_dacl_matches",
            },
            "native create observation",
        )
        validate_native_create_request(
            {
                "parent_handle_id": value["parent_handle_id"],
                "component": value["component"],
                "disposition": value["disposition"],
                "object_attributes_flags": value["object_attributes_flags"],
                "parent_flushed": value["parent_flushed"],
            }
        )
        if (
            value["native_binding_available"] is not True
            or value["parent_no_delete_share"] is not True
            or value["parent_identity_matches"] is not True
            or value["parent_dacl_matches"] is not True
            or value["creation_time_protected_dacl"] is not True
            or value["child_kind"] not in {"DIRECTORY", "FILE"}
        ):
            raise LocatorCustodyError("HANDLE_RELATIVE_CREATION_UNAVAILABLE_STOP")
        # All pre-create gates have passed; this is the only modeled mutation.
        component = cast(str, value["component"])
        self.writes.append(component)
        if (
            value["child_reparse"] is not False
            or value["child_identity_matches"] is not True
            or value["child_dacl_matches"] is not True
            or (value["child_kind"] == "FILE" and value["file_write_complete"] is not True)
            or (value["child_kind"] == "FILE" and value["file_flush_success"] is not True)
            or value["parent_flush_success"] is not True
        ):
            raise LocatorCustodyError("CUSTODY_DURABILITY_BARRIER_FAILED_STOP")
        if value["reopen_identity_matches"] is not True or value["reopen_dacl_matches"] is not True:
            raise LocatorCustodyError("CUSTODY_PARENT_IDENTITY_CHANGED_STOP")
        self.durable_components.append(component)


def validate_restricted_acl(observation: Mapping[str, object], principal_sid: str) -> None:
    """Validate a decoded descriptor captured from the same still-open handle."""
    value = _json_object(observation)
    _exact(
        value,
        {"owner_sid", "null_dacl", "access_check", "generic_mapping_applied", "aces"},
        "ACL observation",
    )
    if re.fullmatch(r"S-[0-9]+(?:-[0-9]+)+", principal_sid) is None:
        raise LocatorCustodyError("PRIVATE_HOME_BOUNDARY_INVALID_STOP")
    if (
        value["owner_sid"] != principal_sid
        or value["null_dacl"] is not False
        or value["access_check"] is not True
        or value["generic_mapping_applied"] is not True
        or not isinstance(value["aces"], list)
    ):
        raise LocatorCustodyError("PRIVATE_HOME_BOUNDARY_INVALID_STOP")
    accepted_flags = {
        "OBJECT_INHERIT",
        "CONTAINER_INHERIT",
        "NO_PROPAGATE",
        "INHERIT_ONLY",
        "INHERITED",
    }
    approved = {principal_sid, "LOCAL_SYSTEM", "BUILTIN_ADMINISTRATORS"}
    dangerous = {
        "FILE_WRITE_DATA",
        "FILE_APPEND_DATA",
        "FILE_ADD_FILE",
        "FILE_ADD_SUBDIRECTORY",
        "FILE_DELETE_CHILD",
        "DELETE",
        "WRITE_DAC",
        "WRITE_OWNER",
        "GENERIC_WRITE",
        "GENERIC_ALL",
    }
    for ace in value["aces"]:
        if not isinstance(ace, dict):
            raise LocatorCustodyError("PRIVATE_HOME_BOUNDARY_INVALID_STOP")
        _exact(ace, {"type", "sid", "flags", "mapped_rights"}, "ACL ACE")
        if (
            ace["type"] not in {"ALLOW", "DENY"}
            or not isinstance(ace["sid"], str)
            or not isinstance(ace["flags"], list)
            or not isinstance(ace["mapped_rights"], list)
        ):
            raise LocatorCustodyError("PRIVATE_HOME_BOUNDARY_INVALID_STOP")
        if (
            ace["sid"] not in {"LOCAL_SYSTEM", "BUILTIN_ADMINISTRATORS"}
            and re.fullmatch(r"S-[0-9]+(?:-[0-9]+)+", ace["sid"]) is None
        ):
            raise LocatorCustodyError("PRIVATE_HOME_BOUNDARY_INVALID_STOP")
        if (
            not all(isinstance(flag, str) and flag in accepted_flags for flag in ace["flags"])
            or len(set(cast(list[str], ace["flags"]))) != len(ace["flags"])
            or not all(
                isinstance(right, str) and right in dangerous for right in ace["mapped_rights"]
            )
        ):
            raise LocatorCustodyError("PRIVATE_HOME_BOUNDARY_INVALID_STOP")
        applicable = "INHERIT_ONLY" not in ace["flags"]
        if (
            ace["type"] == "ALLOW"
            and applicable
            and set(cast(list[str], ace["mapped_rights"])) & dangerous
            and ace["sid"] not in approved
        ):
            raise LocatorCustodyError("PRIVATE_HOME_BOUNDARY_INVALID_STOP")


def validate_known_folder_boundary(observation: Mapping[str, object]) -> None:
    """Validate a pre-opened, opaque resolver observation without environment fallback."""
    value = _json_object(observation)
    keys = {
        "local_appdata",
        "profile_local",
        "fixed_volume",
        "namespace",
        "cloud",
        "onedrive_accounts",
        "free_bytes",
        "candidate_worktree_identity_digest",
        "ordered_worktree_identity_digests",
    }
    _exact(value, keys, "Known Folder observation")
    if (
        value["local_appdata"] != value["profile_local"]
        or value["fixed_volume"] is not True
        or value["namespace"] != "DOS"
        or value["cloud"] is not False
        or not isinstance(value["free_bytes"], int)
        or isinstance(value["free_bytes"], bool)
        or value["free_bytes"] < 42_949_672_960
    ):
        raise LocatorCustodyError("PRIVATE_HOME_BOUNDARY_INVALID_STOP")
    accounts = value["onedrive_accounts"]
    worktrees = value["ordered_worktree_identity_digests"]
    _digest(value["candidate_worktree_identity_digest"], "candidate worktree identity")
    if (
        not isinstance(accounts, list)
        or not isinstance(worktrees, list)
        or any(not isinstance(item, str) for item in worktrees)
    ):
        raise LocatorCustodyError("PRIVATE_HOME_BOUNDARY_INVALID_STOP")
    typed_worktrees = cast(list[str], worktrees)
    for worktree in typed_worktrees:
        _digest(worktree, "worktree identity")
    if (
        typed_worktrees != sorted(set(typed_worktrees))
        or value["candidate_worktree_identity_digest"] in typed_worktrees
    ):
        raise LocatorCustodyError("PRIVATE_HOME_BOUNDARY_INVALID_STOP")
    account_names: list[str] = []
    for account in accounts:
        if not isinstance(account, dict):
            raise LocatorCustodyError("PRIVATE_HOME_BOUNDARY_INVALID_STOP")
        _exact(
            account,
            {
                "account_name",
                "value_type",
                "path",
                "path_valid",
                "fixed_volume",
                "cloud",
                "reparse",
                "overlaps_project",
            },
            "OneDrive",
        )
        account_name = account["account_name"]
        path = account["path"]
        if (
            not isinstance(account_name, str)
            or not account_name
            or not isinstance(path, str)
            or re.fullmatch(r"[A-Za-z]:\\(?:[^\\\x00]+\\)*[^\\\x00]+", path) is None
            or account["value_type"] != "REG_SZ"
            or account["path_valid"] is not True
            or account["fixed_volume"] is not True
            or account["cloud"] is not False
            or account["reparse"] is not False
            or account["overlaps_project"] is not False
        ):
            raise LocatorCustodyError("PRIVATE_HOME_BOUNDARY_INVALID_STOP")
        account_names.append(account_name)
    if account_names != sorted(
        account_names, key=lambda name: (name.upper(), name.encode("utf-16-le"))
    ):
        raise LocatorCustodyError("PRIVATE_HOME_BOUNDARY_INVALID_STOP")


def validate_powershell_closure(
    manifest: Mapping[str, object],
    cmdlets: Mapping[str, object],
    scripts: Mapping[str, object],
    runtime: Mapping[str, object],
    closure: Mapping[str, object],
) -> None:
    """Cross-bind all PowerShell projections; each input is strict canonical data."""
    m = validate_powershell_module_manifest_projection(manifest)
    c = validate_powershell_required_cmdlet_projection(cmdlets)
    s = validate_powershell_acl_bootstrap_script_projection(scripts)
    r = validate_powershell_acl_runtime_projection(runtime)
    cv = validate_powershell_acl_module_closure(closure)
    if (
        cv["module_manifest_projection_digest"] != m["projection_digest"]
        or cv["required_cmdlet_projection_digest"] != c["projection_digest"]
        or cv["acl_bootstrap_script_projection_digest"] != s["projection_digest"]
        or cv["runtime_projection_digest"] != r["runtime_projection_digest"]
    ):
        raise LocatorCustodyError("POWERSHELL_ACL_MODULE_CLOSURE_UNPROVEN_STOP")
    if c["module_manifest_projection_digest"] != m["projection_digest"]:
        raise LocatorCustodyError("POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP")
    # Keep the extraction explicit to preserve the frozen member order.
    utility_members = cast(list[Json], m["utility_nested_members"])
    expected_member_digests = [
        cast(dict[str, Json], cast(list[Json], m["security_nested_members"])[0])[
            "member_identity_digest"
        ],
        cast(dict[str, Json], utility_members[0])["member_identity_digest"],
        cast(dict[str, Json], utility_members[1])["member_identity_digest"],
    ]
    command_rows = cast(list[Json], c["ordered_command_rows"])
    if [
        cast(dict[str, Json], row)["implementing_member_identity_digest"] for row in command_rows
    ] != [expected_member_digests[0], expected_member_digests[0], expected_member_digests[1]]:
        raise LocatorCustodyError("POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP")
    if r["ordered_loaded_member_identity_digests"] != expected_member_digests:
        raise LocatorCustodyError("POWERSHELL_RUNTIME_PROJECTION_MISMATCH_STOP")
    for key in (
        "windows_directory_identity_digest",
        "windows_system_directory_identity_digest",
        "module_root_directory_identity_digest",
    ):
        if cv[key] != m[key] or cv[key] != r[key]:
            raise LocatorCustodyError("POWERSHELL_RUNTIME_PROJECTION_MISMATCH_STOP")


def _validate_projection(record: Mapping[str, object], schema: str, digest_key: str) -> JsonObject:
    value = _json_object(record)
    _exact(value, set(WINDOWS_WIRE_SCHEMA_FIELDS[schema]), "PowerShell projection")
    if value["schema_version"] != schema or value[digest_key] != typed_digest(
        schema, {key: item for key, item in value.items() if key != digest_key}
    ):
        raise LocatorCustodyError("POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP")
    return value


def _identity_digest_fields(value: Mapping[str, Json], names: Sequence[str]) -> None:
    for name in names:
        _digest(value[name], name)


def _exact_empty_arrays(value: Mapping[str, Json], names: Sequence[str]) -> None:
    if any(value[name] != [] for name in names):
        raise LocatorCustodyError("POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP")


def _validate_nested_member(row: Json, expected: Mapping[str, str]) -> None:
    member = _mapping(row, "PowerShell nested member")
    _exact(member, set(expected), "PowerShell nested member")
    if any(
        member[key] != value
        for key, value in expected.items()
        if key not in {"member_identity_digest", "file_sha256"}
    ):
        raise LocatorCustodyError("POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP")
    _digest(member["member_identity_digest"], "member identity digest")
    _digest(member["file_sha256"], "member file SHA")


def validate_powershell_module_manifest_projection(record: Mapping[str, object]) -> JsonObject:
    value = _validate_projection(record, PS_MANIFEST_SCHEMA, "projection_digest")
    _identity_digest_fields(
        value,
        (
            "windows_directory_identity_digest",
            "windows_system_directory_identity_digest",
            "module_root_directory_identity_digest",
            "security_manifest_file_identity_digest",
            "security_manifest_file_sha256",
            "utility_manifest_file_identity_digest",
            "utility_manifest_file_sha256",
        ),
    )
    if any(
        value[key] != expected
        for key, expected in {
            "security_guid": "A94C8C7E-9810-47C0-B8AF-65089C13A35A",
            "security_module_version": "3.0.0.0",
            "security_root_module_state": "ABSENT",
            "utility_guid": "1DA87E53-152B-403E-98DC-74D7B4D63D59",
            "utility_module_version": "3.1.0.0",
            "utility_root_module_state": "ABSENT",
        }.items()
    ):
        raise LocatorCustodyError("POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP")
    _exact_empty_arrays(
        value,
        (
            "security_required_modules",
            "security_scripts_to_process",
            "security_types_to_process",
            "security_formats_to_process",
            "utility_required_modules",
            "utility_scripts_to_process",
            "utility_types_to_process",
            "utility_formats_to_process",
        ),
    )
    expected_security = {
        "member_role": "SECURITY_NESTED_BINARY",
        "relative_name": "Microsoft.PowerShell.Security.dll",
        "member_kind": "PE_DLL",
        "member_identity_schema_version": EXECUTABLE_SCHEMA,
        "member_identity_digest": "",
        "file_sha256": "",
    }
    expected_utility = (
        {
            "member_role": "UTILITY_NESTED_BINARY",
            "relative_name": "Microsoft.PowerShell.Commands.Utility.dll",
            "member_kind": "PE_DLL",
            "member_identity_schema_version": EXECUTABLE_SCHEMA,
            "member_identity_digest": "",
            "file_sha256": "",
        },
        {
            "member_role": "UTILITY_NESTED_SCRIPT",
            "relative_name": "Microsoft.PowerShell.Utility.psm1",
            "member_kind": "POWERSHELL_MODULE_SCRIPT",
            "member_identity_schema_version": FILE_SCHEMA,
            "member_identity_digest": "",
            "file_sha256": "",
        },
    )
    security = value["security_nested_members"]
    utility = value["utility_nested_members"]
    if (
        not isinstance(security, list)
        or len(security) != 1
        or not isinstance(utility, list)
        or len(utility) != 2
    ):
        raise LocatorCustodyError("POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP")
    _validate_nested_member(security[0], expected_security)
    _validate_nested_member(utility[0], expected_utility[0])
    _validate_nested_member(utility[1], expected_utility[1])
    _digest(value["projection_digest"], "manifest projection digest")
    return value


def validate_powershell_required_cmdlet_projection(record: Mapping[str, object]) -> JsonObject:
    value = _validate_projection(record, PS_CMDLET_SCHEMA, "projection_digest")
    _digest(value["module_manifest_projection_digest"], "module manifest projection digest")
    rows = value["ordered_command_rows"]
    if not isinstance(rows, list) or len(rows) != 3:
        raise LocatorCustodyError("POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP")
    expected = (
        (
            "Get-Acl",
            "Microsoft.PowerShell.Security",
            "A94C8C7E-9810-47C0-B8AF-65089C13A35A",
            "3.0.0.0",
            "Microsoft.PowerShell.Commands.GetAclCommand",
            "SECURITY_NESTED_BINARY",
        ),
        (
            "Set-Acl",
            "Microsoft.PowerShell.Security",
            "A94C8C7E-9810-47C0-B8AF-65089C13A35A",
            "3.0.0.0",
            "Microsoft.PowerShell.Commands.SetAclCommand",
            "SECURITY_NESTED_BINARY",
        ),
        (
            "ConvertTo-Json",
            "Microsoft.PowerShell.Utility",
            "1DA87E53-152B-403E-98DC-74D7B4D63D59",
            "3.1.0.0",
            "Microsoft.PowerShell.Commands.ConvertToJsonCommand",
            "UTILITY_NESTED_BINARY",
        ),
    )
    keys = {
        "command_name",
        "command_type",
        "module_name",
        "module_guid",
        "module_version",
        "implementing_type_name",
        "implementing_member_role",
        "implementing_member_identity_digest",
    }
    for row, item in zip(rows, expected, strict=True):
        command = _mapping(row, "PowerShell command")
        _exact(command, keys, "PowerShell command")
        if (
            command["command_name"],
            command["command_type"],
            command["module_name"],
            command["module_guid"],
            command["module_version"],
            command["implementing_type_name"],
            command["implementing_member_role"],
        ) != (item[0], "Cmdlet", *item[1:]):
            raise LocatorCustodyError("POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP")
        _digest(command["implementing_member_identity_digest"], "command member digest")
    _digest(value["projection_digest"], "cmdlet projection digest")
    return value


def validate_powershell_acl_bootstrap_script_projection(record: Mapping[str, object]) -> JsonObject:
    value = _validate_projection(record, PS_SCRIPT_SCHEMA, "projection_digest")
    _sha(value["accepted_cc09_implementation_sha"], "accepted CC09 implementation SHA")
    if (
        value["accepted_r06_source_file_sha256"]
        != "72fd639da11a80b5a5b6f4d19c2a45ddd03d5c1b740518c22ac26a3e98c5239e"
        or value["extraction_rule"]
        != "PYTHON_AST_EXACT_FUNCTION_LOCAL_STRING_CONSTANT_ASSIGNMENT_V1"
    ):
        raise LocatorCustodyError("POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP")
    rows = value["ordered_script_rows"]
    if not isinstance(rows, list) or len(rows) != 4:
        raise LocatorCustodyError("POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP")
    expected = (
        (
            "CC09_MODULE_MANIFEST_PREFLIGHT_SCRIPT",
            "CC09_LOCATOR_CUSTODY_IMPLEMENTATION_SOURCE",
            "_project_powershell_module_manifest_preflight",
            None,
        ),
        (
            "CC09_MODULE_RUNTIME_PROJECTION_SCRIPT",
            "CC09_LOCATOR_CUSTODY_IMPLEMENTATION_SOURCE",
            "_project_powershell_acl_runtime_projection",
            None,
        ),
        (
            "R06_HARDEN_NEW_ROOT_SCRIPT",
            "ACCEPTED_R06_PRIVATE_REGISTRY_SOURCE",
            "_harden_new_root_access_boundary",
            "c68c2dd675def9cccaa6786132954897c910e36b63eb4e65e151432121c75a94",
        ),
        (
            "R06_VALIDATE_RESTRICTED_ACL_SCRIPT",
            "ACCEPTED_R06_PRIVATE_REGISTRY_SOURCE",
            "_validate_windows_restricted_acl",
            "3f06a66b3edbc36c6762cf414d4c402e33155b7133f95bc5d5415e2fb242a7a0",
        ),
    )
    keys = {
        "script_role",
        "source_role",
        "source_file_sha256",
        "function_name",
        "assignment_target",
        "strict_utf8_script_sha256",
    }
    for row, item in zip(rows, expected, strict=True):
        script = _mapping(row, "PowerShell script")
        _exact(script, keys, "PowerShell script")
        if (
            script["script_role"],
            script["source_role"],
            script["function_name"],
            script["assignment_target"],
        ) != (*item[:3], "script"):
            raise LocatorCustodyError("POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP")
        _digest(script["source_file_sha256"], "script source SHA")
        _digest(script["strict_utf8_script_sha256"], "strict UTF-8 script SHA")
        if item[3] is not None and script["strict_utf8_script_sha256"] != item[3]:
            raise LocatorCustodyError("POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP")
    _digest(value["projection_digest"], "script projection digest")
    return value


def validate_powershell_acl_runtime_projection(record: Mapping[str, object]) -> JsonObject:
    value = _validate_projection(record, PS_RUNTIME_SCHEMA, "runtime_projection_digest")
    _identity_digest_fields(
        value,
        (
            "powershell_executable_identity_digest",
            "windows_directory_identity_digest",
            "windows_system_directory_identity_digest",
            "module_root_directory_identity_digest",
            "module_manifest_projection_digest",
            "required_cmdlet_projection_digest",
            "acl_bootstrap_script_projection_digest",
            "runtime_projection_digest",
        ),
    )
    if (
        not isinstance(value["powershell_version"], str)
        or re.fullmatch(
            r"(?:0|[1-9][0-9]*)[.](?:0|[1-9][0-9]*)[.](?:0|[1-9][0-9]*)[.](?:0|[1-9][0-9]*)",
            value["powershell_version"],
        )
        is None
    ):
        raise LocatorCustodyError("POWERSHELL_RUNTIME_PROJECTION_MISMATCH_STOP")
    loaded = value["ordered_loaded_member_identity_digests"]
    if not isinstance(loaded, list) or len(loaded) != 3:
        raise LocatorCustodyError("POWERSHELL_RUNTIME_PROJECTION_MISMATCH_STOP")
    for digest in loaded:
        _digest(digest, "loaded member identity digest")
    return value


def validate_powershell_acl_module_closure(record: Mapping[str, object]) -> JsonObject:
    value = _json_object(record)
    _exact(value, set(WINDOWS_WIRE_SCHEMA_FIELDS[PS_CLOSURE_SCHEMA]), "PowerShell closure")
    _identity_digest_fields(value, tuple(WINDOWS_WIRE_SCHEMA_FIELDS[PS_CLOSURE_SCHEMA]))
    if value["closure_digest"] != typed_digest(
        PS_CLOSURE_SCHEMA, {key: item for key, item in value.items() if key != "closure_digest"}
    ):
        raise LocatorCustodyError("POWERSHELL_ACL_MODULE_CLOSURE_UNPROVEN_STOP")
    return value


def validate_windows_wire_schema(schema: str, record: Mapping[str, object]) -> str:
    """Validate one frozen CC09 wire schema and return its typed digest."""
    validators: dict[str, Callable[[Mapping[str, object]], object]] = {
        SID_SCHEMA: validate_windows_principal_sid,
        EXECUTABLE_SCHEMA: lambda value: validate_windows_file_identity(value, executable=True),
        FILE_SCHEMA: lambda value: validate_windows_file_identity(value, executable=False),
        PATH_IDENTITY_SCHEMA: validate_windows_path_identity,
        NATIVE_CREATE_SCHEMA: validate_windows_native_relative_create_contract,
        PROTECTED_DACL_SCHEMA: validate_windows_protected_directory_dacl_contract,
        RESTRICTED_ACL_SCHEMA: validate_windows_restricted_ancestor_acl_contract,
        KNOWN_FOLDER_SCHEMA: validate_windows_known_folder_boundary_contract,
        RESOLVER_SCHEMA: validate_project_private_home_resolver_contract,
        PS_MANIFEST_SCHEMA: validate_powershell_module_manifest_projection,
        PS_CMDLET_SCHEMA: validate_powershell_required_cmdlet_projection,
        PS_SCRIPT_SCHEMA: validate_powershell_acl_bootstrap_script_projection,
        PS_RUNTIME_SCHEMA: validate_powershell_acl_runtime_projection,
        PS_CLOSURE_SCHEMA: validate_powershell_acl_module_closure,
    }
    try:
        result = validators[schema](record)
    except KeyError as exc:
        raise LocatorCustodyError("CUSTODY_SCHEMA_MISMATCH_STOP") from exc
    if isinstance(result, str):
        return result
    digest_key = (
        "runtime_projection_digest"
        if schema == PS_RUNTIME_SCHEMA
        else "closure_digest"
        if schema == PS_CLOSURE_SCHEMA
        else "projection_digest"
    )
    digest = cast(JsonObject, result)[digest_key]
    if not isinstance(digest, str):
        raise LocatorCustodyError("CUSTODY_DIGEST_GRAMMAR_STOP")
    return digest


def validate_windows_host_candidate(
    candidate: Mapping[str, object],
    *,
    contracts: Mapping[str, str],
    expected_bindings: Mapping[str, object],
    closure: Mapping[str, object],
) -> JsonObject:
    """Validate the tracked candidate against freshly replayed projection digests."""
    keys = {
        "schema_version",
        "authority_id",
        "change_control_id",
        "private_home_handle_id",
        "resolver_contract_digest",
        "principal_sid_digest",
        "known_folder_identity_digest",
        "known_folder_boundary_contract_digest",
        "restricted_ancestor_acl_contract_digest",
        "project_container_precondition",
        "project_code_cache_precondition",
        "project_code_checkout_resolver_contract_digest",
        "python_runtime_identity_digest",
        "python_runtime_file_sha256",
        "python_runtime_version",
        "git_executable_identity_digest",
        "git_executable_file_sha256",
        "windows_directory_identity_digest",
        "windows_system_directory_identity_digest",
        "ntdll_library_identity_digest",
        "ntdll_library_file_sha256",
        "kernel32_library_identity_digest",
        "kernel32_library_file_sha256",
        "advapi32_library_identity_digest",
        "advapi32_library_file_sha256",
        "fwpuclnt_library_identity_digest",
        "fwpuclnt_library_file_sha256",
        "powershell_executable_identity_digest",
        "powershell_executable_file_sha256",
        "powershell_version",
        "cmd_executable_identity_digest",
        "cmd_executable_file_sha256",
        "powershell_module_root_directory_identity_digest",
        "powershell_module_manifest_projection_digest",
        "powershell_required_cmdlet_projection_digest",
        "powershell_acl_bootstrap_script_projection_digest",
        "powershell_acl_runtime_projection_digest",
        "powershell_acl_module_closure_digest",
        "native_relative_create_contract_digest",
        "protected_directory_dacl_contract_digest",
        "wfp_egress_denial_contract_digest",
        "locator_custody_implementation_sha",
        "locator_custody_implementation_acceptance_record_digest",
        "observed_at_utc",
        "record_digest",
    }
    value = _json_object(candidate)
    _exact(value, keys, "host candidate")
    if value["schema_version"] != HOST_CANDIDATE_SCHEMA:
        raise LocatorCustodyError("WINDOWS_HOST_BINDING_AUTHORITY_MISSING_STOP")
    if value["record_digest"] != typed_digest(
        HOST_CANDIDATE_SCHEMA, {key: item for key, item in value.items() if key != "record_digest"}
    ):
        raise LocatorCustodyError("WINDOWS_HOST_BINDING_AUTHORITY_MISSING_STOP")
    if (
        value["authority_id"] != "P3_P7_D02_R2_WINDOWS_HOST_BINDING_AUTHORITY_01"
        or value["change_control_id"] != "P3_P7_D02_CC_09"
        or value["private_home_handle_id"] != "PM_PROJECT_MIRROR_PRIVATE_HOME_V1"
        or value["project_container_precondition"] != "ABSENT_CREATE_NEW"
        or value["project_code_cache_precondition"] != "ABSENT_CREATE_NEW"
    ):
        raise LocatorCustodyError("WINDOWS_HOST_BINDING_AUTHORITY_MISSING_STOP")
    _timestamp(value["observed_at_utc"])
    _sha(value["locator_custody_implementation_sha"], "implementation SHA")
    binding_keys = keys - {
        "schema_version",
        "authority_id",
        "change_control_id",
        "private_home_handle_id",
        "project_container_precondition",
        "project_code_cache_precondition",
        "observed_at_utc",
        "record_digest",
    }
    expected_binding = _json_object(expected_bindings)
    _exact(expected_binding, binding_keys, "host candidate expected bindings")
    if any(value[key] != expected_binding[key] for key in binding_keys):
        raise LocatorCustodyError("WINDOWS_HOST_BINDING_AUTHORITY_MISSING_STOP")
    for key, expected_contract in contracts.items():
        if value.get(key) != expected_contract:
            raise LocatorCustodyError("WINDOWS_HOST_BINDING_AUTHORITY_MISSING_STOP")
    if value["wfp_egress_denial_contract_digest"] != validate_windows_wfp_egress_denial_contract(
        windows_wfp_egress_denial_contract()
    ):
        raise LocatorCustodyError("WINDOWS_HOST_BINDING_AUTHORITY_MISSING_STOP")
    closure_value = validate_powershell_acl_module_closure(closure)
    if value["powershell_acl_module_closure_digest"] != closure_value.get("closure_digest"):
        raise LocatorCustodyError("POWERSHELL_ACL_MODULE_CLOSURE_UNPROVEN_STOP")
    pairs = {
        "powershell_module_manifest_projection_digest": "module_manifest_projection_digest",
        "powershell_required_cmdlet_projection_digest": "required_cmdlet_projection_digest",
        "powershell_acl_bootstrap_script_projection_digest": "acl_bootstrap_script_projection_digest",
        "powershell_acl_runtime_projection_digest": "runtime_projection_digest",
        "windows_directory_identity_digest": "windows_directory_identity_digest",
        "windows_system_directory_identity_digest": "windows_system_directory_identity_digest",
        "powershell_module_root_directory_identity_digest": "module_root_directory_identity_digest",
        "powershell_executable_identity_digest": "powershell_executable_identity_digest",
    }
    if any(value[left] != closure_value.get(right) for left, right in pairs.items()):
        raise LocatorCustodyError("POWERSHELL_RUNTIME_PROJECTION_MISMATCH_STOP")
    for key, item in value.items():
        if key.endswith("_digest") and key != "record_digest":
            _digest(item, key)
        elif key.endswith("_file_sha256"):
            _digest(item, key)
    return value


@dataclass(frozen=True)
class ReadOnlyHostProjection:
    """Opaque host result returned by an injected, read-only resolver."""

    principal_sid_digest: str
    known_folder_identity_digest: str
    private_home_identity_digest: str
    resolver_contract_digest: str

    def validate(self) -> None:
        for value in (
            self.principal_sid_digest,
            self.known_folder_identity_digest,
            self.private_home_identity_digest,
            self.resolver_contract_digest,
        ):
            _digest(value, "projection digest")


def project_host(
    read_only_resolver: Callable[[], ReadOnlyHostProjection],
) -> ReadOnlyHostProjection:
    """Validate an injected projection; no Windows API fallback exists here."""
    projection = read_only_resolver()
    projection.validate()
    return projection


class SyntheticCustodyStore:
    """Crash-replay model used only with a caller-owned temporary root."""

    def __init__(self, root: Path) -> None:
        if not root.is_dir() or any(root.iterdir()):
            raise LocatorCustodyError("CUSTODY_NAMESPACE_DIRECTORY_ONLY_STOP")
        self._root = root

    def create_immutable(self, relative_name: str, record: Mapping[str, object]) -> Path:
        if "/" in relative_name or "\\" in relative_name or relative_name in {"", ".", ".."}:
            raise LocatorCustodyError("HANDLE_RELATIVE_CREATION_UNAVAILABLE_STOP")
        destination = self._root / relative_name
        raw = canonical_json_bytes(_json_object(record))
        try:
            with destination.open("xb") as handle:
                handle.write(raw)
                handle.flush()
        except FileExistsError as exc:
            raise LocatorCustodyError("LOCATOR_NAME_RECEIPT_COLLISION_STOP") from exc
        if destination.read_bytes() != raw:
            raise LocatorCustodyError("CUSTODY_DURABILITY_BARRIER_FAILED_STOP")
        return destination

    def replay(self, relative_name: str) -> JsonObject:
        if "/" in relative_name or "\\" in relative_name:
            raise LocatorCustodyError("HANDLE_RELATIVE_CREATION_UNAVAILABLE_STOP")
        return canonical_loads((self._root / relative_name).read_bytes())


@dataclass(frozen=True)
class RehomeStage:
    """One R05 ordinal's durable-prefix observations, in authority order."""

    name_receipt: bool
    output: bool
    seal: bool
    intent: bool
    copy_a_event: bool
    copy_b_event: bool
    commit: bool


def r05_recovery_action(stage: RehomeStage) -> str:
    """Return the sole legal R05 restart action, rejecting non-prefix states.

    The byte/digest validation for each present object is deliberately performed
    by its owning receipt/registry implementation before this state classifier
    is called.  This function never reconstructs missing bytes.
    """
    values = (
        stage.name_receipt,
        stage.output,
        stage.seal,
        stage.intent,
        stage.copy_a_event,
        stage.copy_b_event,
        stage.commit,
    )
    if any(values[index] and not all(values[:index]) for index in range(1, len(values))):
        raise LocatorCustodyError("R05_SOURCE_EVIDENCE_MISMATCH_STOP")
    if stage.copy_b_event and not stage.copy_a_event:
        raise LocatorCustodyError("R05_SOURCE_EVIDENCE_MISMATCH_STOP")
    actions = (
        "CREATE_NAME_RECEIPT",
        "CREATE_OUTPUT",
        "CREATE_SEAL",
        "CREATE_INTENT",
        "CREATE_COPY_A_AND_REPLAY",
        "REPLAY_COPY_A_CREATE_COPY_B_AND_COMPARE",
        "COMPARE_COPIES_CREATE_COMMIT_AND_REPLAY",
        "FULL_REPLAY_NO_WRITE",
    )
    for index, present in enumerate(values):
        if not present:
            return actions[index]
    return actions[-1]


REGISTRY_SNAPSHOT_SCHEMA: Final = "mirror.demo/D02R2PrivateRegistrySemanticSnapshot/v1"
ORDERED_R05_OUTPUT_IDS: Final[tuple[str, ...]] = (
    "D02_R2_R05_E2_LEGACY_ROOT_RECEIPT_BYTES",
    "D02_R2_R05_E2_LEGACY_REGISTRY_RECEIPT_BYTES",
    "D02_R2_R05_E2_EXACT_CANDIDATE_MANIFEST",
    "D02_R2_R05_E2_INDEPENDENT_REVIEW",
    "D02_R2_R05_E2_LEGACY_MANIFEST_SEAL_BYTES",
    "D02_R2_R05_E2_LEGACY_REVIEW_SEAL_BYTES",
    "D02_R2_R05_E2_VALIDATION_SUMMARY",
    "D02_R2_R05_E2_REHOME_MANIFEST",
)
ACTUAL_ROOT_ADDENDUM_HASH_DEPENDENCY_ORDER: Final[tuple[str, ...]] = (
    "POST_R05_PRIOR_REGISTRY_HEAD",
    "ACTUAL_ROOT_ADDENDUM_RECORD_DIGEST",
    "FUTURE_NEXT_REGISTRY_HEAD",
)
_HELD_CONTRACT_ACCEPTANCE_AUTHORITY_ID: Final = (
    "P3_P7_D02_R2_MIGRATION_AUTHORITY_CONTRACT_ACCEPTANCE_01"
)
_HELD_CONTRACT_ACCEPTANCE_RECORD_DIGEST: Final = (
    "9954d9e91a041f9db94ca069ce618eac36f869d7017b09e55faa786736aa062a"
)
_HELD_DISPATCH_ACCEPTANCE_AUTHORITY_ID: Final = (
    "P3_P7_D02_R2_MIGRATION_DISPATCH_ADDENDUM_ACCEPTANCE_01"
)
_HELD_DISPATCH_ACCEPTANCE_RECORD_DIGEST: Final = (
    "01c22e1e62b592b48a09bb23a800bb3a2395157fae7c77c8ee82639105a0a34e"
)
_PRE_ROOT_EXPECTATION_DIGEST: Final = (
    "c3ae43887d51d15347153e392ca092866dff890bdcda959572cc1dd07e6195c4"
)
_REGISTRY_SNAPSHOT_LOGICAL_FIELDS: Final[tuple[str, ...]] = (
    "schema_version",
    "evidence_root_id",
    "root_name_receipt_digest",
    "execution_contract_digest",
    "registry_schema_contract_digest",
    "common_genesis_digest",
    "event_count",
    "head_event_digest",
    "ordered_events",
)
_REGISTRY_SNAPSHOT_EVENT_FIELDS: Final[tuple[str, ...]] = (
    "sequence",
    "transaction_id",
    "output_id",
    "semantic_role",
    "authority_digest",
    "event_digest",
)
_REGISTRY_SNAPSHOT_IMMUTABLE_AUTHORITY_FIELDS: Final[tuple[str, ...]] = (
    "schema_version",
    "evidence_root_id",
    "root_name_receipt_digest",
    "execution_contract_digest",
    "registry_schema_contract_digest",
    "common_genesis_digest",
)


def canonical_registry_snapshot_projection(record: Mapping[str, object]) -> JsonObject:
    """Validate and return the exact CC08 semantic snapshot payload."""

    value = _json_object(record)
    required = {*_REGISTRY_SNAPSHOT_LOGICAL_FIELDS, "semantic_snapshot_digest"}
    if set(value) != required:
        raise LocatorCustodyError("MIGRATION_ROOT_BINDING_HELD_STOP")
    if value["schema_version"] != REGISTRY_SNAPSHOT_SCHEMA:
        raise LocatorCustodyError("MIGRATION_ROOT_BINDING_HELD_STOP")
    if value["evidence_root_id"] != "P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT":
        raise LocatorCustodyError("MIGRATION_ROOT_BINDING_HELD_STOP")
    for key in (
        "root_name_receipt_digest",
        "execution_contract_digest",
        "registry_schema_contract_digest",
        "common_genesis_digest",
        "head_event_digest",
        "semantic_snapshot_digest",
    ):
        _digest(value[key], key)
    count = value["event_count"]
    rows = value["ordered_events"]
    if (
        not isinstance(count, int)
        or isinstance(count, bool)
        or count < 0
        or not isinstance(rows, list)
        or len(rows) != count
    ):
        raise LocatorCustodyError("MIGRATION_ROOT_BINDING_HELD_STOP")
    ordered: list[Json] = []
    seen_outputs: set[str] = set()
    for expected_sequence, row in enumerate(rows, 1):
        item = _mapping(row, "registry snapshot event")
        _exact(item, set(_REGISTRY_SNAPSHOT_EVENT_FIELDS), "registry snapshot event")
        if item["sequence"] != expected_sequence or item["semantic_role"] != "BANK_IMPORT_EVIDENCE":
            raise LocatorCustodyError("MIGRATION_ROOT_BINDING_HELD_STOP")
        transaction_id = item["transaction_id"]
        output_id = item["output_id"]
        _digest(transaction_id, "registry transaction ID")
        _id(output_id, "registry output ID")
        if cast(str, output_id) in seen_outputs:
            raise LocatorCustodyError("MIGRATION_ROOT_BINDING_HELD_STOP")
        seen_outputs.add(cast(str, output_id))
        _digest(item["authority_digest"], "registry authority digest")
        _digest(item["event_digest"], "registry event digest")
        ordered.append(_json_object(item))
    expected_head = (
        cast(str, cast(dict[str, Json], ordered[-1])["event_digest"])
        if ordered
        else cast(str, value["common_genesis_digest"])
    )
    if value["head_event_digest"] != expected_head:
        raise LocatorCustodyError("MIGRATION_ROOT_BINDING_HELD_STOP")
    projection = _json_object(
        {
            key: ordered if key == "ordered_events" else value[key]
            for key in _REGISTRY_SNAPSHOT_LOGICAL_FIELDS
        }
    )
    if value["semantic_snapshot_digest"] != typed_digest(REGISTRY_SNAPSHOT_SCHEMA, projection):
        raise LocatorCustodyError("MIGRATION_ROOT_BINDING_HELD_STOP")
    return projection


def validate_actual_root_addendum(
    candidate: Mapping[str, object],
    acceptance: Mapping[str, object],
    *,
    expected_bindings: TrustedAcceptanceBindingSource,
    registry_copy_a_snapshot_before_r05: Mapping[str, object],
    registry_copy_b_snapshot_before_r05: Mapping[str, object],
    registry_copy_a_snapshot_after_r05: Mapping[str, object],
    registry_copy_b_snapshot_after_r05: Mapping[str, object],
) -> None:
    """Prove the forward-only addendum predicate; candidate-only is non-authority."""
    candidate_keys = {
        "schema_version",
        "authority_id",
        "change_control_id",
        "cc09_plan_acceptance_record_digest",
        "cc09_implementation_acceptance_record_digest",
        "cc09_locator_name_receipt_digest",
        "cc09_root_registry_ready_commit_digest",
        "cc08_root_receipt_digest",
        "cc08_registry_common_genesis_digest",
        "cc08_registry_copy_a_snapshot_digest",
        "cc08_registry_copy_b_snapshot_digest",
        "r05_committed_output_count",
        "cc08_registry_event_count_after_r05",
        "cc08_registry_copy_a_snapshot_digest_after_r05",
        "cc08_registry_copy_b_snapshot_digest_after_r05",
        "cc08_registry_head_event_digest_after_r05",
        "ordered_r05_output_ids",
        "held_contract_acceptance_authority_id",
        "held_contract_acceptance_record_digest",
        "held_dispatch_acceptance_authority_id",
        "held_dispatch_acceptance_record_digest",
        "pre_root_expectation_digest",
        "effective_root_name_receipt_digest",
        "r05_rehome_manifest_digest",
        "candidate_state",
        "created_at_utc",
        "record_digest",
    }
    candidate_value = _json_object(candidate)
    _exact(candidate_value, candidate_keys, "actual root candidate")
    validate_typed_record(candidate_value, ADDENDUM_SCHEMA, "record_digest")
    if (
        candidate_value["candidate_state"]
        != "CANDIDATE_PENDING_INDEPENDENT_REVIEW_SAME_SHA_CI_AND_PRINCIPAL_ACCEPTANCE"
    ):
        raise LocatorCustodyError("MIGRATION_ROOT_BINDING_HELD_STOP")
    if (
        candidate_value["r05_committed_output_count"] != 8
        or candidate_value["cc08_registry_event_count_after_r05"] != 8
    ):
        raise LocatorCustodyError("MIGRATION_ROOT_BINDING_HELD_STOP")
    if (
        candidate_value["authority_id"] != "P3_P7_D02_R2_ACTUAL_ROOT_DIGEST_BINDING_ADDENDUM_01"
        or candidate_value["change_control_id"] != "P3_P7_D02_CC_09"
    ):
        raise LocatorCustodyError("MIGRATION_ROOT_BINDING_HELD_STOP")
    _timestamp(candidate_value["created_at_utc"])
    for key, item in candidate_value.items():
        if key.endswith("_digest") and key != "record_digest":
            _digest(item, key)
    for key in ("r05_committed_output_count", "cc08_registry_event_count_after_r05"):
        if not isinstance(candidate_value[key], int) or isinstance(candidate_value[key], bool):
            raise LocatorCustodyError("MIGRATION_ROOT_BINDING_HELD_STOP")
    ids = candidate_value["ordered_r05_output_ids"]
    if ids != list(ORDERED_R05_OUTPUT_IDS):
        raise LocatorCustodyError("MIGRATION_ROOT_BINDING_HELD_STOP")
    if (
        candidate_value["held_contract_acceptance_authority_id"]
        != _HELD_CONTRACT_ACCEPTANCE_AUTHORITY_ID
        or candidate_value["held_contract_acceptance_record_digest"]
        != _HELD_CONTRACT_ACCEPTANCE_RECORD_DIGEST
        or candidate_value["held_dispatch_acceptance_authority_id"]
        != _HELD_DISPATCH_ACCEPTANCE_AUTHORITY_ID
        or candidate_value["held_dispatch_acceptance_record_digest"]
        != _HELD_DISPATCH_ACCEPTANCE_RECORD_DIGEST
        or candidate_value["pre_root_expectation_digest"] != _PRE_ROOT_EXPECTATION_DIGEST
        or candidate_value["effective_root_name_receipt_digest"]
        != candidate_value["cc08_root_receipt_digest"]
    ):
        raise LocatorCustodyError("MIGRATION_ROOT_BINDING_HELD_STOP")
    before_a = canonical_registry_snapshot_projection(registry_copy_a_snapshot_before_r05)
    before_b = canonical_registry_snapshot_projection(registry_copy_b_snapshot_before_r05)
    after_a = canonical_registry_snapshot_projection(registry_copy_a_snapshot_after_r05)
    after_b = canonical_registry_snapshot_projection(registry_copy_b_snapshot_after_r05)
    before_digest = typed_digest(REGISTRY_SNAPSHOT_SCHEMA, before_a)
    after_digest = typed_digest(REGISTRY_SNAPSHOT_SCHEMA, after_a)
    before_rows = cast(list[Json], before_a["ordered_events"])
    after_rows = cast(list[Json], after_a["ordered_events"])
    if (
        before_a != before_b
        or after_a != after_b
        or before_a["event_count"] != 0
        or before_rows
        or before_a["head_event_digest"] != before_a["common_genesis_digest"]
        or after_a["event_count"] != 8
        or len(after_rows) != 8
        or candidate_value["cc08_registry_common_genesis_digest"]
        != before_a["common_genesis_digest"]
        or any(
            before_a[key] != after_a[key] for key in _REGISTRY_SNAPSHOT_IMMUTABLE_AUTHORITY_FIELDS
        )
        or before_a["root_name_receipt_digest"] != candidate_value["cc08_root_receipt_digest"]
        or after_a["root_name_receipt_digest"] != candidate_value["cc08_root_receipt_digest"]
        or candidate_value["cc08_registry_copy_a_snapshot_digest"] != before_digest
        or candidate_value["cc08_registry_copy_b_snapshot_digest"] != before_digest
        or candidate_value["cc08_registry_copy_a_snapshot_digest_after_r05"] != after_digest
        or candidate_value["cc08_registry_copy_b_snapshot_digest_after_r05"] != after_digest
        or candidate_value["cc08_registry_head_event_digest_after_r05"]
        != after_a["head_event_digest"]
        or [cast(dict[str, Json], row)["output_id"] for row in after_rows]
        != list(ORDERED_R05_OUTPUT_IDS)
    ):
        raise LocatorCustodyError("MIGRATION_ROOT_BINDING_HELD_STOP")
    acceptance_keys = {
        "schema_version",
        "authority_id",
        "change_control_id",
        "accepted_addendum_sha",
        "accepted_addendum_tree",
        "accepted_addendum_path",
        "accepted_addendum_git_blob_oid",
        "accepted_addendum_file_sha256",
        "accepted_addendum_record_digest",
        "accepted_plan_acceptance_record_digest",
        "locator_custody_implementation_acceptance_record_digest",
        "independent_review",
        "same_sha_ci",
        "principal_acceptance",
        "authorized_scope",
        "prohibited_scope",
        "effective_state",
        "record_created_at_utc",
        "record_digest",
    }
    acceptance_value = _json_object(acceptance)
    _exact(acceptance_value, acceptance_keys, "actual root acceptance")
    validate_typed_record(acceptance_value, ADDENDUM_ACCEPTANCE_SCHEMA, "record_digest")
    binding_keys = {
        "accepted_addendum_sha",
        "accepted_addendum_tree",
        "accepted_addendum_path",
        "accepted_addendum_git_blob_oid",
        "accepted_addendum_file_sha256",
        "accepted_addendum_record_digest",
        "accepted_plan_acceptance_record_digest",
        "locator_custody_implementation_acceptance_record_digest",
    }
    _validate_trusted_record_bindings(acceptance_value, expected_bindings, "record_digest")
    if (
        acceptance_value["authority_id"]
        != "P3_P7_D02_R2_ACTUAL_ROOT_DIGEST_BINDING_ADDENDUM_ACCEPTANCE_01"
        or acceptance_value["change_control_id"] != "P3_P7_D02_CC_09"
        or acceptance_value["accepted_addendum_path"]
        != "docs/operations/P3_P7_D02_R2_ACTUAL_ROOT_DIGEST_BINDING_ADDENDUM.json"
        or acceptance_value["authorized_scope"] != "SUPERSEDE_HELD_ROOT_DIGEST_INPUT_BINDING_ONLY"
        or acceptance_value["prohibited_scope"]
        != [
            "EDIT_ACCEPTED_HISTORICAL_AUTHORITY",
            "ROOT_RECEIPT_SCALAR_SUBSTITUTION",
            "R05_TASK_ACCEPTANCE",
            "MIGRATION_OR_ORM",
            "POSTGRESQL_ADMISSION",
            "SOURCE_GENERATION",
            "M3_M4_EXECUTION",
            "D02_R2_TASK_ACCEPTANCE",
            "D03_D04_B_D07_B_OPENING",
            "FORMAL_PHASE_AUTHORITY",
            "PRODUCTION_RELEASE",
        ]
        or acceptance_value["accepted_addendum_record_digest"] != candidate_value["record_digest"]
        or acceptance_value["accepted_plan_acceptance_record_digest"]
        != candidate_value["cc09_plan_acceptance_record_digest"]
        or acceptance_value["locator_custody_implementation_acceptance_record_digest"]
        != candidate_value["cc09_implementation_acceptance_record_digest"]
        or acceptance_value["effective_state"] != "ACTUAL_ROOT_BINDING_ACCEPTED"
    ):
        raise LocatorCustodyError("MIGRATION_ROOT_BINDING_HELD_STOP")
    for key in binding_keys:
        if key.endswith("_digest") or key.endswith("_file_sha256"):
            _digest(acceptance_value[key], key)
        elif key != "accepted_addendum_path":
            _sha(acceptance_value[key], key)
        elif not isinstance(acceptance_value[key], str):
            raise LocatorCustodyError("MIGRATION_ROOT_BINDING_HELD_STOP")
    _timestamp(acceptance_value["record_created_at_utc"])
    _validate_acceptance_evidence(
        acceptance_value,
        accepted_sha_key="accepted_addendum_sha",
        review_sha_key="reviewed_addendum_sha",
        principal_sha_key="accepted_addendum_sha",
    )


def _json_object(value: Mapping[str, object]) -> JsonObject:
    result: JsonObject = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise LocatorCustodyError("CUSTODY_JSON_INVALID_STOP")
        result[key] = _json_value(item)
    return result


def _json_value(value: object) -> Json:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        raise LocatorCustodyError("CUSTODY_JSON_NONCANONICAL_STOP")
    if isinstance(value, Mapping):
        return _json_object(value)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [_json_value(item) for item in value]
    raise LocatorCustodyError("CUSTODY_JSON_INVALID_STOP")


def _exact(value: Mapping[str, Json], expected: set[str], _: str) -> None:
    if set(value) != expected:
        raise LocatorCustodyError("CUSTODY_EXACT_KEY_STOP")


def _mapping(value: Json, _: str) -> Mapping[str, Json]:
    if not isinstance(value, dict):
        raise LocatorCustodyError("CUSTODY_EXACT_KEY_STOP")
    return value


def _require_schema(value: str) -> None:
    if not isinstance(value, str) or not value.startswith("mirror."):
        raise LocatorCustodyError("CUSTODY_SCHEMA_MISMATCH_STOP")


def _digest(value: object, _: str) -> None:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise LocatorCustodyError("CUSTODY_DIGEST_GRAMMAR_STOP")


def _sha(value: object, _: str) -> None:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise LocatorCustodyError("CUSTODY_SHA_GRAMMAR_STOP")


def _hex(value: object, length: int) -> str:
    if not isinstance(value, str) or re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is None:
        raise LocatorCustodyError("KNOWN_FOLDER_IDENTITY_CHANGED_STOP")
    return value


def _id(value: object, _: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None or value in {".", ".."}:
        raise LocatorCustodyError("CUSTODY_ID_GRAMMAR_STOP")


def _timestamp(value: object) -> None:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise LocatorCustodyError("CUSTODY_TIMESTAMP_GRAMMAR_STOP")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise LocatorCustodyError("CUSTODY_TIMESTAMP_GRAMMAR_STOP") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ") != value:
        raise LocatorCustodyError("CUSTODY_TIMESTAMP_GRAMMAR_STOP")


def _sequence(value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 99_999_999:
        raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: Json) -> bytes:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]*", value) is None:
        raise LocatorCustodyError("LOCATOR_INTENT_PARTIAL_OR_CORRUPT_STOP")
    try:
        result = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except ValueError as exc:
        raise LocatorCustodyError("LOCATOR_INTENT_PARTIAL_OR_CORRUPT_STOP") from exc
    if _b64(result) != value:
        raise LocatorCustodyError("LOCATOR_INTENT_PARTIAL_OR_CORRUPT_STOP")
    return result


# The following objects model the CC09 native boundary.  They intentionally
# have no ctypes/Win32 implementation: a host binding is separately accepted.
WFP_EGRESS_SCHEMA: Final = "mirror.governance/WindowsWfpEgressDenialContract/v1"
_WFP_NAMESPACE: Final = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")
_WFP_ROLES: Final[tuple[str, ...]] = (
    "SESSION",
    "PROVIDER",
    "SUBLAYER",
    "FILTER:DETACHED_PYTHON:V4",
    "FILTER:DETACHED_PYTHON:V6",
    "FILTER:GIT:V4",
    "FILTER:GIT:V6",
    "FILTER:POWERSHELL:V4",
    "FILTER:POWERSHELL:V6",
    "FILTER:CMD:V4",
    "FILTER:CMD:V6",
)
_WFP_APPLICATION_ROLES: Final[tuple[str, ...]] = ("DETACHED_PYTHON", "GIT", "POWERSHELL", "CMD")
_WFP_FILTER_ROWS: Final[tuple[tuple[str, str, str], ...]] = tuple(
    (
        role,
        family,
        f"FWPM_LAYER_ALE_AUTH_CONNECT_{family}",
    )
    for role in _WFP_APPLICATION_ROLES
    for family in ("V4", "V6")
)


def windows_wfp_egress_denial_contract() -> JsonObject:
    """Return CC09's closed WFP caller-controlled projection."""
    return {
        "backend": "FWPUCLNT_DYNAMIC_WFP_SESSION_V1",
        "session_flags": "FWPM_SESSION_FLAG_DYNAMIC",
        "layers": "ALE_AUTH_CONNECT_V4|ALE_AUTH_CONNECT_V6",
        "condition": "ALE_APP_ID_EQUAL",
        "action": "FWP_ACTION_BLOCK",
        "blocked_application_roles": "DETACHED_PYTHON|GIT|POWERSHELL|CMD",
        "remote_scope": "ALL",
        "local_scope": "ALL",
        "network_exemptions": "NONE",
        "filter_persistence": "NON_PERSISTENT_DYNAMIC_SESSION",
        "child_process_policy": "JOB_OBJECT_ACTIVE_PROCESS_LIMIT_2_NO_BREAKAWAY",
        "install_order": "BEFORE_CHILD_CREATION_AND_LOCATOR_DISCLOSURE",
        "verification": "SESSION_ENUM_OBJECT_CORRELATION_FILTER_EXACT_REPLAY_AND_IPV4_IPV6_WSAEACCES_PROBE",
        "cleanup": "DELETE_OWN_DERIVED_FILTERS_SUBLAYER_PROVIDER_CLOSE_DYNAMIC_SESSION_AND_OBSERVER_VERIFY_ABSENT",
        "key_derivation": "RFC4122_UUIDV5_LOWERCASE_V1",
        "key_namespace_uuid": str(_WFP_NAMESPACE),
        "session_key_role": "SESSION",
        "provider_key_role": "PROVIDER",
        "sublayer_key_role": "SUBLAYER",
        "filter_key_role_pattern": "FILTER:<DETACHED_PYTHON|GIT|POWERSHELL|CMD>:<V4|V6>",
        "session_display_name": "Project Mirror D02-R2 CC09 dynamic egress session",
        "session_description_policy": "NULL",
        "session_txn_wait_timeout_ms": 0,
        "session_input_zero_null_policy": "processId=0|sid=NULL|username=NULL|kernelMode=FALSE",
        "provider_display_name": "Project Mirror D02-R2 CC09 dynamic egress provider",
        "provider_description_policy": "NULL",
        "provider_flags": "NONE",
        "provider_service_name": "NULL",
        "provider_data_binding": "locator_custody_implementation_acceptance_record_digest",
        "provider_data_encoding": "RAW_32_BYTES_DECODED_FROM_LOWER_HEX_SHA256",
        "sublayer_display_name": "Project Mirror D02-R2 CC09 dynamic egress sublayer",
        "sublayer_description_policy": "NULL",
        "sublayer_flags": "NONE",
        "sublayer_weight": 65535,
        "empty_provider_data_policy": "size=0|data=NULL",
        "filter_display_name_equation": '"Project Mirror D02-R2 CC09 block " + application_role + " " + address_family',
        "filter_description_policy": "NULL",
        "filter_flags": "NONE",
        "filter_weight_type": "FWP_UINT64",
        "filter_weight": 18_446_744_073_709_551_615,
        "match_type": "FWP_MATCH_EQUAL",
        "condition_value_source": "FwpmGetAppIdFromFileName0",
        "filter_condition_projection": "fieldKey=FWPM_CONDITION_ALE_APP_ID|matchType=FWP_MATCH_EQUAL|conditionValue.type=FWP_BYTE_BLOB_TYPE|conditionValue.bytes=exact_app_id_blob",
        "filter_action_projection": "type=FWP_ACTION_BLOCK|filterType=GUID_NULL",
        "filter_raw_context": 0,
        "filter_reserved_policy": "NULL",
        "caller_controlled_zero_null_policy": "ZERO_INITIALIZE_ALL_WFP_STRUCTS_AND_REQUIRE_EVERY_UNLISTED_CALLER_FIELD_ZERO_OR_NULL",
        "session_ownership_verification": "FWPM_SESSION_ENUM_EXACT_KEY_PID_SID_DYNAMIC_USER_MODE",
        "object_correlation_verification": "PROVIDER_TO_SUBLAYER_TO_EXACT_EIGHT_FILTERS",
        "provider_sublayer_replay_verification": "GET_BY_DERIVED_KEY_EXACT_CALLER_CONTROLLED_PROJECTION",
        "filter_replay_included_fields": "filterKey|displayData|flags|providerKey|providerData|layerKey|subLayerKey|weight|numFilterConditions|filterCondition|action|rawContext|reserved",
        "filter_host_assigned_field_policy": "filterId excluded from caller projection but equals unique nonzero add-result ID; effectiveWeight excluded from caller projection but must equal FWP_UINT64 exact requested weight; pointer addresses excluded while pointed-to bytes are included",
        "probe_targets": ["192.0.2.1", "2001:db8::1"],
        "collateral_scope": "ALL_HOST_PROCESSES_USING_THE_FOUR_ACCEPTED_EXECUTABLE_IMAGES",
        "exclusive_window_policy": "SERIALIZED_CC09_MAINTENANCE_WINDOW_WITH_SAME_IMAGE_COLLATERAL_EXPLICITLY_ACCEPTED",
        "contract_version": "P3_P7_D02_R2_WINDOWS_WFP_EGRESS_DENIAL_V1",
    }


def validate_windows_wfp_egress_denial_contract(record: Mapping[str, object]) -> str:
    value = _json_object(record)
    expected = windows_wfp_egress_denial_contract()
    _exact(value, set(expected), "WFP egress contract")
    if value != expected:
        raise LocatorCustodyError("WFP_EGRESS_CONTRACT_PROJECTION_MISMATCH_STOP")
    return typed_digest(WFP_EGRESS_SCHEMA, expected)


def derive_windows_wfp_keys(
    implementation_acceptance_digest: str, principal_sid_digest: str
) -> dict[str, str]:
    """Derive the one session, provider, sublayer and eight filter GUIDs."""
    _digest(implementation_acceptance_digest, "implementation acceptance digest")
    _digest(principal_sid_digest, "principal SID digest")
    base = uuid.uuid5(
        _WFP_NAMESPACE,
        "urn:project-mirror:p3-p7-d02-r2:cc09:wfp:v1:"
        f"{implementation_acceptance_digest}:{principal_sid_digest}",
    )
    return {role: str(uuid.uuid5(base, role)) for role in _WFP_ROLES}


def windows_wfp_filter_projections(keys: Mapping[str, str]) -> tuple[dict[str, object], ...]:
    """Build the exact eight caller-controlled WFP filter projections."""
    if tuple(keys) != _WFP_ROLES:
        raise LocatorCustodyError("WFP_PROVIDER_SUBLAYER_FILTER_CORRELATION_STOP")
    weight = windows_wfp_egress_denial_contract()["filter_weight"]
    return tuple(
        {
            "filter_key": keys[f"FILTER:{role}:{family}"],
            "display_name": f"Project Mirror D02-R2 CC09 block {role} {family}",
            "description": None,
            "flags": 0,
            "provider_key": keys["PROVIDER"],
            "provider_data": b"",
            "layer_key": layer,
            "sublayer_key": keys["SUBLAYER"],
            "weight_type": "FWP_UINT64",
            "weight": weight,
            "num_filter_conditions": 1,
            "condition_field_key": "FWPM_CONDITION_ALE_APP_ID",
            "condition_match_type": "FWP_MATCH_EQUAL",
            "condition_value_type": "FWP_BYTE_BLOB_TYPE",
            "application_role": role,
            "action_type": "FWP_ACTION_BLOCK",
            "action_filter_type": None,
            "raw_context": 0,
            "reserved": None,
            "unlisted_caller_fields_zero_or_null": True,
        }
        for role, family, layer in _WFP_FILTER_ROWS
    )


def validate_windows_wfp_filter_projections(
    keys: Mapping[str, str], projections: Sequence[Mapping[str, object]]
) -> None:
    expected = windows_wfp_filter_projections(keys)
    if len(projections) != 8:
        raise LocatorCustodyError("WFP_PROVIDER_SUBLAYER_FILTER_CORRELATION_STOP")
    for actual, frozen in zip(projections, expected, strict=True):
        if dict(actual) != frozen:
            raise LocatorCustodyError("WFP_PROVIDER_SUBLAYER_FILTER_CORRELATION_STOP")


def build_locator_bridge_frame(
    absolute_root_path: str, ordered_excluded_worktree_paths: Sequence[str]
) -> bytes:
    payload: JsonObject = {
        "absolute_root_path": absolute_root_path,
        "ordered_excluded_worktree_paths": list(ordered_excluded_worktree_paths),
        "protocol_version": "P3_P7_D02_R2_LOCATOR_BRIDGE_STDIN_V1",
    }
    _validate_locator_bridge_payload(payload)
    raw = canonical_json_bytes(payload)
    return b"PMCC09L1" + len(raw).to_bytes(4, "big") + raw


def parse_locator_bridge_frame(data: bytes) -> JsonObject:
    """Decode the exact one-frame bridge protocol before any path is consumed."""
    if len(data) < 12 or not data.startswith(b"PMCC09L1"):
        raise LocatorCustodyError("BRIDGE_FRAME_INVALID_STOP")
    length = int.from_bytes(data[8:12], "big")
    if not 1 <= length <= 1_048_576 or len(data) != 12 + length:
        raise LocatorCustodyError("BRIDGE_FRAME_INVALID_STOP")
    raw = data[12:]
    if raw.startswith(b"\xef\xbb\xbf") or b"\0" in raw:
        raise LocatorCustodyError("BRIDGE_FRAME_INVALID_STOP")
    try:
        value = canonical_loads(raw)
    except LocatorCustodyError as exc:
        raise LocatorCustodyError("BRIDGE_FRAME_INVALID_STOP") from exc
    _validate_locator_bridge_payload(value)
    return value


def _validate_locator_bridge_payload(value: Mapping[str, object]) -> None:
    payload = _json_object(value)
    _exact(
        payload,
        {"absolute_root_path", "ordered_excluded_worktree_paths", "protocol_version"},
        "bridge stdin payload",
    )
    if payload["protocol_version"] != "P3_P7_D02_R2_LOCATOR_BRIDGE_STDIN_V1":
        raise LocatorCustodyError("BRIDGE_FRAME_INVALID_STOP")
    root = payload["absolute_root_path"]
    paths = payload["ordered_excluded_worktree_paths"]
    if (
        not isinstance(root, str)
        or not root
        or "\0" in root
        or not isinstance(paths, list)
        or not paths
        or len(set(paths)) != len(paths)
        or any(not isinstance(path, str) or not path or "\0" in path for path in paths)
    ):
        raise LocatorCustodyError("BRIDGE_FRAME_INVALID_STOP")


class WindowsWfpBackend(Protocol):
    """Injected native boundary with a deliberately detailed WFP projection."""

    def install(
        self, contract: Mapping[str, object], keys: Mapping[str, str], provider_data: bytes
    ) -> None: ...

    def verify(self, contract: Mapping[str, object], keys: Mapping[str, str]) -> None: ...

    def probe(self, target: str, operation: str) -> str: ...

    def cleanup(self, keys: Mapping[str, str]) -> None: ...


@dataclass
class SyntheticWindowsWfpBackend:
    """Test-only exact WFP model; never loads fwpuclnt or touches host WFP."""

    api_available: bool = True
    privileged: bool = True
    bfe_running: bool = True
    dll_identity_matches: bool = True
    ownership_matches: bool = True
    replay_matches: bool = True
    probe_result: str = "WSAEACCES"
    cleanup_succeeds: bool = True
    installed_keys: set[str] = field(default_factory=set)
    calls: list[str] = field(default_factory=list)
    filter_projections: tuple[dict[str, object], ...] = ()

    def install(
        self, contract: Mapping[str, object], keys: Mapping[str, str], provider_data: bytes
    ) -> None:
        self.calls.append("install")
        if not (
            self.api_available
            and self.privileged
            and self.bfe_running
            and self.dll_identity_matches
        ):
            raise LocatorCustodyError("BRIDGE_NETWORK_DENIAL_UNAVAILABLE_STOP")
        validate_windows_wfp_egress_denial_contract(contract)
        if (
            len(keys) != len(_WFP_ROLES)
            or tuple(keys) != _WFP_ROLES
            or len(set(keys.values())) != len(keys)
        ):
            raise LocatorCustodyError("WFP_PROVIDER_SUBLAYER_FILTER_CORRELATION_STOP")
        if len(provider_data) != 32:
            raise LocatorCustodyError("WFP_PROVIDER_SUBLAYER_FILTER_CORRELATION_STOP")
        self.installed_keys = set(keys.values())
        self.filter_projections = windows_wfp_filter_projections(keys)

    def verify(self, contract: Mapping[str, object], keys: Mapping[str, str]) -> None:
        self.calls.append("verify")
        if not self.ownership_matches:
            raise LocatorCustodyError("WFP_SESSION_OWNERSHIP_UNPROVEN_STOP")
        if not self.replay_matches or self.installed_keys != set(keys.values()):
            raise LocatorCustodyError("WFP_PROVIDER_SUBLAYER_FILTER_CORRELATION_STOP")
        validate_windows_wfp_filter_projections(keys, self.filter_projections)
        validate_windows_wfp_egress_denial_contract(contract)

    def probe(self, target: str, operation: str) -> str:
        self.calls.append(f"probe:{operation}:{target}")
        return self.probe_result

    def cleanup(self, keys: Mapping[str, str]) -> None:
        self.calls.append("cleanup")
        self.installed_keys.clear()
        self.filter_projections = ()
        if not self.cleanup_succeeds or self.installed_keys:
            raise LocatorCustodyError("WFP_EGRESS_SESSION_CLEANUP_FAILED_STOP")


@dataclass
class SyntheticJobObject:
    """Injected active-process/no-breakaway boundary for bridge tests."""

    active_process_limit: int = 2
    no_breakaway: bool = True
    kill_on_close: bool = True
    inherited_handles: tuple[str, ...] = ("stdin", "stdout", "stderr")
    maintenance_window_owner: str = "P3_P7_D02_R2_CC09_BRIDGE"
    maintenance_window_exclusive: bool = True
    audit_policy_network_denied: bool = True
    audit_policy_subprocess_roles: tuple[str, ...] = ("GIT", "POWERSHELL")
    bridge_active: bool = False
    child_active: bool = False

    def start_bridge(self) -> None:
        if (
            self.active_process_limit != 2
            or not self.no_breakaway
            or not self.kill_on_close
            or self.inherited_handles != ("stdin", "stdout", "stderr")
            or self.maintenance_window_owner != "P3_P7_D02_R2_CC09_BRIDGE"
            or not self.maintenance_window_exclusive
            or not self.audit_policy_network_denied
            or self.audit_policy_subprocess_roles != ("GIT", "POWERSHELL")
            or self.bridge_active
        ):
            raise LocatorCustodyError("BRIDGE_UNAUTHORIZED_SUBPROCESS_STOP")
        self.bridge_active = True

    def start_child(self, *, reparented: bool = False) -> None:
        if (
            not self.bridge_active
            or self.child_active
            or reparented
            or self.active_process_limit < 2
        ):
            raise LocatorCustodyError("BRIDGE_UNAUTHORIZED_SUBPROCESS_STOP")
        self.child_active = True

    def request_descendant(self) -> None:
        raise LocatorCustodyError("BRIDGE_UNAUTHORIZED_SUBPROCESS_STOP")

    def finish_child(self) -> None:
        self.child_active = False

    def close(self) -> None:
        self.child_active = False
        self.bridge_active = False


def run_synthetic_detached_bridge(
    *,
    stage_authority: Mapping[str, object],
    trusted_stage_digests: Mapping[str, str],
    backend: WindowsWfpBackend,
    job: SyntheticJobObject,
    implementation_acceptance_digest: str,
    principal_sid_digest: str,
    frame: bytes,
    outer_child: Callable[[bytes, Mapping[str, str]], tuple[bytes, bytes]],
    acl_child: Callable[[Mapping[str, str]], tuple[bytes, bytes]],
) -> tuple[bytes, bytes]:
    """Execute the typed-stage bridge without exposing locator capability to its outer child."""
    keys = derive_windows_wfp_keys(implementation_acceptance_digest, principal_sid_digest)
    contract = windows_wfp_egress_denial_contract()
    install_attempted = False
    acl_environment: dict[str, str] = {}
    try:
        stage_value = validate_detached_bridge_stage_authority(
            stage_authority, trusted_stage_digests
        )
        rows = cast(list[Json], stage_value["ordered_stage_rows"])
        first_row = _mapping(rows[0], "bridge implementation stage")
        if first_row["authority_digest"] != implementation_acceptance_digest:
            raise LocatorCustodyError("DETACHED_RUNTIME_IDENTITY_CHANGED_STOP")
        install_attempted = True
        backend.install(contract, keys, bytes.fromhex(implementation_acceptance_digest))
        backend.verify(contract, keys)
        for operation in ("dns", "socket", "connect"):
            for target in ("192.0.2.1", "2001:db8::1"):
                if backend.probe(target, operation) != "WSAEACCES":
                    raise LocatorCustodyError("BRIDGE_NETWORK_DENIAL_UNAVAILABLE_STOP")
        payload = parse_locator_bridge_frame(frame)
        job.start_bridge()
        job.start_child()
        try:
            outer_stdout, outer_stderr = outer_child(frame, {})
        except Exception as exc:
            raise LocatorCustodyError("BRIDGE_UNAUTHORIZED_SUBPROCESS_STOP") from exc
        finally:
            job.finish_child()
        _validate_bridge_output(outer_stdout)
        _validate_bridge_output(outer_stderr)
        if not outer_stdout.startswith(b"STATUS: PASS\n"):
            raise LocatorCustodyError("BRIDGE_UNAUTHORIZED_SUBPROCESS_STOP")
        job.start_child()
        acl_environment = {"MIRROR_D02_R2_ACL_PATH": cast(str, payload["absolute_root_path"])}
        try:
            acl_stdout, acl_stderr = acl_child(acl_environment)
        except Exception as exc:
            raise LocatorCustodyError("BRIDGE_UNAUTHORIZED_SUBPROCESS_STOP") from exc
        finally:
            acl_environment.clear()
            job.finish_child()
        _validate_bridge_output(acl_stdout)
        _validate_bridge_output(acl_stderr)
        if not acl_stdout.startswith(b"STATUS: PASS\n"):
            raise LocatorCustodyError("BRIDGE_UNAUTHORIZED_SUBPROCESS_STOP")
        return outer_stdout, acl_stdout
    finally:
        acl_environment.clear()
        job.close()
        if install_attempted:
            try:
                backend.cleanup(keys)
            except LocatorCustodyError:
                raise
            except Exception as exc:
                raise LocatorCustodyError("WFP_EGRESS_SESSION_CLEANUP_FAILED_STOP") from exc


BRIDGE_STAGE_AUTHORITY_SCHEMA: Final = "mirror.demo/D02R2DetachedBridgeStageAuthority/v1"
_BRIDGE_STAGE_ORDER: Final[tuple[tuple[str, str], ...]] = (
    ("IMPLEMENTATION_ACCEPTANCE", "IMPLEMENTATION_ACCEPTED"),
    ("HOST_BINDING_ACCEPTANCE", "HOST_BINDING_ACCEPTED"),
    ("PRIVATE_HOME_BINDING_ACCEPTANCE", "PRIVATE_HOME_BINDING_ACCEPTED"),
    ("R06_CHECKOUT_SEAL", "R06_CHECKOUT_SEALED"),
    ("BRIDGE_SCRATCH_RECEIPT", "BRIDGE_SCRATCH_RECEIPT_ONLY"),
    ("LOCATOR_CUSTODY", "LOCATOR_CUSTODY_COMMITTED"),
)
_BRIDGE_OUTPUT = re.compile(rb"STATUS: (?:PASS|FAIL|CANCELLED)\nDIGEST: [0-9a-f]{64}\n\Z")


def make_detached_bridge_stage_authority(trusted_stage_digests: Mapping[str, str]) -> JsonObject:
    """Build a test/injected stage record; the caller remains authority for every digest."""
    _validate_trusted_bridge_stage_digests(trusted_stage_digests)
    value: JsonObject = {
        "schema_version": BRIDGE_STAGE_AUTHORITY_SCHEMA,
        "ordered_stage_rows": [
            {"stage": stage, "authority_digest": trusted_stage_digests[stage], "state": state}
            for stage, state in _BRIDGE_STAGE_ORDER
        ],
    }
    value["record_digest"] = typed_digest(BRIDGE_STAGE_AUTHORITY_SCHEMA, value)
    return value


def validate_detached_bridge_stage_authority(
    record: Mapping[str, object], trusted_stage_digests: Mapping[str, str]
) -> JsonObject:
    """Require the exact CC09 stage set/order and independently supplied trusted digests."""
    _validate_trusted_bridge_stage_digests(trusted_stage_digests)
    value = _json_object(record)
    if set(value) != {"schema_version", "ordered_stage_rows", "record_digest"}:
        raise LocatorCustodyError("DETACHED_RUNTIME_IDENTITY_CHANGED_STOP")
    if value["schema_version"] != BRIDGE_STAGE_AUTHORITY_SCHEMA or not isinstance(
        value["ordered_stage_rows"], list
    ):
        raise LocatorCustodyError("DETACHED_RUNTIME_IDENTITY_CHANGED_STOP")
    if value["record_digest"] != typed_digest(
        BRIDGE_STAGE_AUTHORITY_SCHEMA,
        {key: item for key, item in value.items() if key != "record_digest"},
    ):
        raise LocatorCustodyError("DETACHED_RUNTIME_IDENTITY_CHANGED_STOP")
    rows = value["ordered_stage_rows"]
    assert isinstance(rows, list)
    if len(rows) != len(_BRIDGE_STAGE_ORDER):
        raise LocatorCustodyError("DETACHED_RUNTIME_IDENTITY_CHANGED_STOP")
    for row, (stage, state) in zip(rows, _BRIDGE_STAGE_ORDER, strict=True):
        item = _mapping(row, "bridge stage")
        if set(item) != {"stage", "authority_digest", "state"}:
            raise LocatorCustodyError("DETACHED_RUNTIME_IDENTITY_CHANGED_STOP")
        if (
            item["stage"] != stage
            or item["state"] != state
            or item["authority_digest"] != trusted_stage_digests[stage]
        ):
            raise LocatorCustodyError("DETACHED_RUNTIME_IDENTITY_CHANGED_STOP")
        _digest(item["authority_digest"], "bridge stage digest")
    return value


def _validate_trusted_bridge_stage_digests(trusted_stage_digests: Mapping[str, str]) -> None:
    if tuple(trusted_stage_digests) != tuple(stage for stage, _ in _BRIDGE_STAGE_ORDER):
        raise LocatorCustodyError("DETACHED_RUNTIME_IDENTITY_CHANGED_STOP")
    for stage, _ in _BRIDGE_STAGE_ORDER:
        _digest(trusted_stage_digests[stage], stage)


def _validate_bridge_output(output: bytes) -> None:
    if not isinstance(output, bytes) or not _BRIDGE_OUTPUT.fullmatch(output):
        raise LocatorCustodyError("BRIDGE_LOCATOR_LEAK_STOP")


# E5 deliberately models only the protocol's durable projections.  It has no
# Path, subprocess, git, or environment implementation; those boundaries stay
# with the separately accepted host bridge.
CODE_CHECKOUT_RESOLVER_SCHEMA: Final = "mirror.governance/ProjectCodeCheckoutResolverContract/v1"
CODE_CACHE_RECEIPT_SCHEMA: Final = "mirror.governance/ProjectCodeCacheNameReceipt/v1"
R06_CHECKOUT_SEAL_SCHEMA: Final = "mirror.governance/AcceptedR06CheckoutSealReceipt/v1"
PROJECT_CONTAINER_RECEIPT_SCHEMA: Final = "mirror.governance/ProjectMirrorContainerNameReceipt/v1"
PRIVATE_HOME_RECEIPT_SCHEMA: Final = "mirror.governance/ProjectPrivateHomeNameReceipt/v1"
PRIVATE_HOME_CANDIDATE_SCHEMA: Final = "mirror.demo/D02R2PrivateHomeBindingCandidate/v1"
PRIVATE_HOME_ACCEPTANCE_SCHEMA: Final = "mirror.demo/D02R2PrivateHomeBindingAcceptance/v1"
BRIDGE_SCRATCH_RECEIPT_SCHEMA: Final = "mirror.governance/ProjectPrivateBridgeScratchNameReceipt/v1"

_R06_SHA: Final = "ab08a6e861ec364c62a6ab3dcf46a69483f1b741"
_R06_TREE: Final = "47f1b6ccfa73f757348dd3c4038cf3dae9335ba1"
_R06_CHECKPOINT: Final = "3c743cdf5167bf3484be98b4f50e0ea6c77c5f13"
_R06_ACCEPTANCE_DIGEST: Final = "a7170831675c35aaf9354a12a788d16251ec40d98fcd472c8f4c78dbf3f1d1e3"
_R06_ROWS: Final[tuple[JsonObject, ...]] = (
    {
        "path": "services/api/src/mirror_api/demo_d02_r2_private_registry.py",
        "git_blob_oid": "1beee70d53b172a334ecf76e18f08a137f7bb9a0",
        "sha256": "72fd639da11a80b5a5b6f4d19c2a45ddd03d5c1b740518c22ac26a3e98c5239e",
    },
    {
        "path": "services/api/tests/test_demo_d02_r2_private_registry.py",
        "git_blob_oid": "7906e46d62a2530d9eaba16e9af4418a206d1300",
        "sha256": "9158c732d063f9540f1b488c2f27215bcd225b71639f53dd1154b06950b8f4e0",
    },
    {
        "path": "services/api/src/mirror_api/demo_measurement_quality.py",
        "git_blob_oid": "c9f319b9410b6741a8a000395d525fe2a103de59",
        "sha256": "abbade973f106f4d63700fc382109b5b86803b1cf976359f684bbb6421f301f7",
    },
)
_RETAIN: Final = "RETAIN_UNTIL_D02_R2_AND_ALL_DEPENDENT_TASKS_RELEASE_CUSTODY"
_CLEANUP: Final = "PRINCIPAL_EXACT_DEPENDENCY_SCAN_AND_FORWARD_CHANGE_CONTROL_REQUIRED"
_CC09_FIXED_LITERALS: Final[dict[str, JsonObject]] = {
    CODE_CACHE_RECEIPT_SCHEMA: {
        "code_cache_handle_id": "PM_PROJECT_MIRROR_CODE_CACHE_V1",
        "purpose": "PUBLIC_CODE_ONLY_CC09_ACCEPTED_R06_CHECKOUT",
        "allowed_checkout_component": "accepted-r06-ab08a6e861ec",
    },
    PROJECT_CONTAINER_RECEIPT_SCHEMA: {
        "project_container_handle_id": "PM_PROJECT_MIRROR_CONTAINER_V1",
        "purpose": "PROJECT_MIRROR_PRINCIPAL_PRIVATE_OUTPUT_CONTAINER_ONLY",
        "allowed_next_component": "principal-private-output-v1",
    },
    PRIVATE_HOME_RECEIPT_SCHEMA: {
        "private_home_handle_id": "PM_PROJECT_MIRROR_PRIVATE_HOME_V1",
        "purpose": "PRINCIPAL_PRIVATE_OUTPUT_CONTROL_AND_D02_R2_CUSTODY_ONLY",
        "allowed_subject_root_ids": ["P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT"],
    },
    PRIVATE_HOME_CANDIDATE_SCHEMA: {
        "authority_id": "P3_P7_D02_R2_PRIVATE_HOME_BINDING_AUTHORITY_01",
        "change_control_id": "P3_P7_D02_CC_09",
        "private_home_handle_id": "PM_PROJECT_MIRROR_PRIVATE_HOME_V1",
    },
    BRIDGE_SCRATCH_RECEIPT_SCHEMA: {
        "bridge_scratch_handle_id": "PM_PROJECT_MIRROR_CC09_BRIDGE_SCRATCH_V1",
        "purpose": "CC09_RECEIPT_BOUND_PRIVATE_TEMP_ONLY",
        "at_rest_policy": "RECEIPT_ONLY",
        "locator_session_policy": "RECEIPT_ONLY_BEFORE_AND_AFTER_EVERY_LOCATOR_SESSION",
        "crash_residue_policy": "PRESERVE_AND_STOP",
    },
}

_CC09_RECORD_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    CODE_CACHE_RECEIPT_SCHEMA: (
        "schema_version",
        "project_id",
        "code_cache_handle_id",
        "purpose",
        "resolver_contract_digest",
        "host_binding_acceptance_record_digest",
        "principal_sid_digest",
        "known_folder_identity_digest",
        "code_cache_identity_digest",
        "protected_directory_dacl_contract_digest",
        "allowed_checkout_component",
        "locator_custody_implementation_sha",
        "locator_custody_implementation_acceptance_record_digest",
        "retention_policy",
        "cleanup_policy",
        "created_at_utc",
        "receipt_digest",
    ),
    R06_CHECKOUT_SEAL_SCHEMA: (
        "schema_version",
        "project_id",
        "checkout_handle_id",
        "purpose",
        "resolver_contract_digest",
        "host_binding_acceptance_record_digest",
        "principal_sid_digest",
        "known_folder_identity_digest",
        "code_cache_identity_digest",
        "code_cache_name_receipt_digest",
        "checkout_identity_digest",
        "protected_directory_dacl_contract_digest",
        "accepted_git_executable_identity_digest",
        "accepted_git_executable_file_sha256",
        "head_sha",
        "head_tree",
        "required_ref",
        "required_ref_target",
        "accepted_r06_implementation_sha",
        "accepted_r06_implementation_tree",
        "accepted_r06_acceptance_checkpoint_sha",
        "accepted_r06_acceptance_record_digest",
        "accepted_r06_governed_rows",
        "retention_policy",
        "cleanup_policy",
        "created_at_utc",
        "receipt_digest",
    ),
    PROJECT_CONTAINER_RECEIPT_SCHEMA: (
        "schema_version",
        "project_id",
        "project_container_handle_id",
        "purpose",
        "resolver_contract_digest",
        "host_binding_acceptance_record_digest",
        "principal_sid_digest",
        "known_folder_identity_digest",
        "project_container_identity_digest",
        "protected_directory_dacl_contract_digest",
        "allowed_next_component",
        "locator_custody_implementation_sha",
        "locator_custody_implementation_acceptance_record_digest",
        "retention_policy",
        "cleanup_policy",
        "created_at_utc",
        "receipt_digest",
    ),
    PRIVATE_HOME_RECEIPT_SCHEMA: (
        "schema_version",
        "project_id",
        "private_home_handle_id",
        "purpose",
        "resolver_contract_digest",
        "host_binding_acceptance_record_digest",
        "principal_sid_digest",
        "known_folder_identity_digest",
        "project_container_identity_digest",
        "project_container_name_receipt_digest",
        "private_home_identity_digest",
        "protected_directory_dacl_contract_digest",
        "allowed_subject_root_ids",
        "locator_custody_implementation_sha",
        "locator_custody_implementation_acceptance_record_digest",
        "retention_policy",
        "cleanup_policy",
        "created_at_utc",
        "receipt_digest",
    ),
    PRIVATE_HOME_CANDIDATE_SCHEMA: (
        "schema_version",
        "authority_id",
        "change_control_id",
        "private_home_handle_id",
        "host_binding_acceptance_record_digest",
        "resolver_contract_digest",
        "principal_sid_digest",
        "known_folder_identity_digest",
        "project_container_identity_digest",
        "project_container_name_receipt_digest",
        "private_home_identity_digest",
        "private_home_name_receipt_digest",
        "protected_directory_dacl_contract_digest",
        "locator_custody_implementation_acceptance_record_digest",
        "observed_at_utc",
        "record_digest",
    ),
    PRIVATE_HOME_ACCEPTANCE_SCHEMA: (
        "schema_version",
        "authority_id",
        "change_control_id",
        "accepted_candidate_sha",
        "accepted_candidate_tree",
        "accepted_candidate_path",
        "accepted_candidate_git_blob_oid",
        "accepted_candidate_file_sha256",
        "accepted_candidate_record_digest",
        "accepted_plan_acceptance_record_digest",
        "locator_custody_implementation_acceptance_record_digest",
        "host_binding_acceptance_record_digest",
        "project_container_name_receipt_digest",
        "private_home_name_receipt_digest",
        "independent_review",
        "same_sha_ci",
        "principal_acceptance",
        "authorized_scope",
        "prohibited_scope",
        "record_created_at_utc",
        "record_digest",
    ),
    BRIDGE_SCRATCH_RECEIPT_SCHEMA: (
        "schema_version",
        "project_id",
        "bridge_scratch_handle_id",
        "purpose",
        "private_home_binding_acceptance_record_digest",
        "host_binding_acceptance_record_digest",
        "principal_sid_digest",
        "private_home_identity_digest",
        "bridge_scratch_identity_digest",
        "protected_directory_dacl_contract_digest",
        "locator_custody_implementation_sha",
        "locator_custody_implementation_acceptance_record_digest",
        "at_rest_policy",
        "locator_session_policy",
        "crash_residue_policy",
        "retention_policy",
        "cleanup_policy",
        "created_at_utc",
        "receipt_digest",
    ),
}


def project_code_checkout_resolver_contract() -> JsonObject:
    return {
        "known_folder_role": "KNOWN_FOLDER",
        "code_cache_component": "ProjectMirror-code-cache-v1",
        "checkout_component": "accepted-r06-ab08a6e861ec",
        "source": "CURRENT_ACCEPTED_CC09_REPOSITORY_ONLY",
        "destination_creation": "HANDLE_RELATIVE_NATIVE_CREATE_EMPTY_DIRECTORY_WITH_PROTECTED_DACL",
        "clone_command": "git clone --local --no-hardlinks --no-checkout --no-tags <source> .",
        "remote_cleanup_command": "git remote remove origin",
        "required_ref": "refs/remotes/origin/codex/p3-p7-core-demo",
        "required_ref_target": _R06_CHECKPOINT,
        "required_ref_recreation": f"git update-ref refs/remotes/origin/codex/p3-p7-core-demo {_R06_CHECKPOINT}",
        "checkout_command": f"git checkout --detach {_R06_SHA}",
        "detached_head": _R06_SHA,
        "network": "FORBIDDEN",
        "partial_checkout": "PRESERVE_AND_STOP",
        "cleanup": "NO_DELETE_WITHOUT_FORWARD_CHANGE_CONTROL",
        "contract_version": "P3_P7_D02_R2_PROJECT_CODE_CHECKOUT_RESOLVER_V1",
    }


def validate_project_code_checkout_resolver_contract(record: Mapping[str, object]) -> str:
    value = _json_object(record)
    expected = project_code_checkout_resolver_contract()
    _exact(value, set(expected), "code checkout resolver")
    if value != expected:
        raise LocatorCustodyError("CODE_CHECKOUT_PARTIAL_OR_CORRUPT_STOP")
    return typed_digest(CODE_CHECKOUT_RESOLVER_SCHEMA, expected)


def make_cc09_record(schema: str, fields: Mapping[str, object]) -> JsonObject:
    """Create one deterministic synthetic wire record; callers supply all bindings."""
    expected = _CC09_RECORD_FIELDS.get(schema)
    if expected is None:
        raise LocatorCustodyError("CUSTODY_SCHEMA_MISMATCH_STOP")
    value = _json_object(fields)
    terminal = "receipt_digest" if expected[-1] == "receipt_digest" else "record_digest"
    _exact(value, set(expected) - {terminal, "schema_version"}, "CC09 preimage")
    payload: JsonObject = {"schema_version": schema, **value}
    payload[terminal] = typed_digest(schema, payload)
    return payload


def validate_cc09_record(
    schema: str, record: Mapping[str, object], *, bindings: Mapping[str, object] | None = None
) -> str:
    expected = _CC09_RECORD_FIELDS.get(schema)
    if expected is None:
        raise LocatorCustodyError("CUSTODY_SCHEMA_MISMATCH_STOP")
    value = _json_object(record)
    _exact(value, set(expected), "CC09 record")
    terminal = "receipt_digest" if expected[-1] == "receipt_digest" else "record_digest"
    if value.get("schema_version") != schema or value[terminal] != typed_digest(
        schema, {key: item for key, item in value.items() if key != terminal}
    ):
        raise LocatorCustodyError("CC09_RECORD_DIGEST_OR_SCHEMA_STOP")
    if bindings is not None:
        bound = _json_object(bindings)
        if any(value.get(key) != item for key, item in bound.items()):
            raise LocatorCustodyError("CC09_ACCEPTED_BINDING_DRIFT_STOP")
    for key, item in value.items():
        if key.endswith("_digest") and key != terminal:
            _digest(item, key)
        elif key.endswith("_sha") or key.endswith("_tree") or key.endswith("_git_blob_oid"):
            _sha(item, key)
        elif key.endswith("_file_sha256"):
            _digest(item, key)
    if (
        value.get("project_id") not in {None, "PROJECT_MIRROR"}
        or value.get("retention_policy") not in {None, _RETAIN}
        or value.get("cleanup_policy") not in {None, _CLEANUP}
    ):
        raise LocatorCustodyError("CC09_RECORD_LITERAL_STOP")
    if any(value.get(key) != item for key, item in _CC09_FIXED_LITERALS.get(schema, {}).items()):
        raise LocatorCustodyError("CC09_RECORD_LITERAL_STOP")
    timestamp_key = (
        "observed_at_utc"
        if schema == PRIVATE_HOME_CANDIDATE_SCHEMA
        else (
            "record_created_at_utc"
            if schema == PRIVATE_HOME_ACCEPTANCE_SCHEMA
            else "created_at_utc"
        )
    )
    _timestamp(value[timestamp_key])
    if schema == R06_CHECKOUT_SEAL_SCHEMA and (
        value["head_sha"] != _R06_SHA
        or value["head_tree"] != _R06_TREE
        or value["required_ref"] != "refs/remotes/origin/codex/p3-p7-core-demo"
        or value["required_ref_target"] != _R06_CHECKPOINT
        or value["accepted_r06_implementation_sha"] != _R06_SHA
        or value["accepted_r06_implementation_tree"] != _R06_TREE
        or value["accepted_r06_acceptance_checkpoint_sha"] != _R06_CHECKPOINT
        or value["accepted_r06_acceptance_record_digest"] != _R06_ACCEPTANCE_DIGEST
        or value["accepted_r06_governed_rows"] != list(_R06_ROWS)
    ):
        raise LocatorCustodyError("CODE_CHECKOUT_PARTIAL_OR_CORRUPT_STOP")
    return cast(str, value[terminal])


def validate_project_code_cache_name_receipt(
    record: Mapping[str, object], *, bindings: Mapping[str, object] | None = None
) -> str:
    return validate_cc09_record(CODE_CACHE_RECEIPT_SCHEMA, record, bindings=bindings)


def validate_accepted_r06_checkout_seal_receipt(
    record: Mapping[str, object], *, bindings: Mapping[str, object] | None = None
) -> str:
    return validate_cc09_record(R06_CHECKOUT_SEAL_SCHEMA, record, bindings=bindings)


def validate_project_mirror_container_name_receipt(
    record: Mapping[str, object], *, bindings: Mapping[str, object] | None = None
) -> str:
    return validate_cc09_record(PROJECT_CONTAINER_RECEIPT_SCHEMA, record, bindings=bindings)


def validate_project_private_home_name_receipt(
    record: Mapping[str, object], *, bindings: Mapping[str, object] | None = None
) -> str:
    return validate_cc09_record(PRIVATE_HOME_RECEIPT_SCHEMA, record, bindings=bindings)


def validate_private_home_binding_candidate(
    record: Mapping[str, object], *, bindings: Mapping[str, object] | None = None
) -> str:
    return validate_cc09_record(PRIVATE_HOME_CANDIDATE_SCHEMA, record, bindings=bindings)


def validate_private_home_binding_acceptance(
    record: Mapping[str, object],
    *,
    candidate: Mapping[str, object],
    expected_bindings: TrustedAcceptanceBindingSource,
) -> str:
    return _validate_candidate_acceptance(
        record,
        candidate=candidate,
        expected_bindings=expected_bindings,
        acceptance_schema=PRIVATE_HOME_ACCEPTANCE_SCHEMA,
        candidate_schema=PRIVATE_HOME_CANDIDATE_SCHEMA,
        authority_id="P3_P7_D02_R2_PRIVATE_HOME_BINDING_ACCEPTANCE_01",
        candidate_path="docs/operations/P3_P7_D02_R2_PRIVATE_HOME_BINDING_CANDIDATE.json",
        authorized_scope="OPEN_EXACT_PRIVATE_HOME_FOR_RECEIPT_BOUND_BRIDGE_SCRATCH_AND_CC09_LOCATOR_CUSTODY_ONLY",
        prohibited_scope=[
            "ALTERNATE_PRIVATE_HOME",
            "PRIVATE_HOME_REBIND",
            "SECOND_LOCATOR_NAMESPACE",
            "SECOND_EVIDENCE_ROOT",
            "SOURCE_GENERATION",
            "M3_M4_EXECUTION",
            "POSTGRESQL_ADMISSION",
            "FORMAL_PHASE_AUTHORITY",
            "PRODUCTION_RELEASE",
        ],
        extra_candidate_bindings=(
            "host_binding_acceptance_record_digest",
            "project_container_name_receipt_digest",
            "private_home_name_receipt_digest",
        ),
    )


def validate_windows_host_binding_acceptance(
    record: Mapping[str, object],
    *,
    candidate: Mapping[str, object],
    expected_bindings: TrustedAcceptanceBindingSource,
) -> str:
    """Validate host acceptance against externally replayed Git and prior authority bindings."""
    return _validate_candidate_acceptance(
        record,
        candidate=candidate,
        expected_bindings=expected_bindings,
        acceptance_schema=HOST_ACCEPTANCE_SCHEMA,
        candidate_schema=HOST_CANDIDATE_SCHEMA,
        authority_id="P3_P7_D02_R2_WINDOWS_HOST_BINDING_ACCEPTANCE_01",
        candidate_path="docs/operations/P3_P7_D02_R2_WINDOWS_HOST_BINDING_CANDIDATE.json",
        authorized_scope="CREATE_EXACT_CODE_CACHE_AND_TWO_COMPONENT_PRIVATE_HOME_CANDIDATES_AND_RECEIPTS_ONLY",
        prohibited_scope=[
            "LOCATOR_NAMESPACE_CREATION",
            "LOCATOR_EVENT_CREATION",
            "CC08_EVIDENCE_ROOT_CREATION",
            "R05_REHOME",
            "SOURCE_GENERATION",
            "M3_M4_EXECUTION",
            "POSTGRESQL_ADMISSION",
            "FORMAL_PHASE_AUTHORITY",
            "PRODUCTION_RELEASE",
        ],
        extra_candidate_bindings=(),
    )


def _validate_candidate_acceptance(
    record: Mapping[str, object],
    *,
    candidate: Mapping[str, object],
    expected_bindings: TrustedAcceptanceBindingSource,
    acceptance_schema: str,
    candidate_schema: str,
    authority_id: str,
    candidate_path: str,
    authorized_scope: str,
    prohibited_scope: list[str],
    extra_candidate_bindings: tuple[str, ...],
) -> str:
    """Validate an acceptance chain without letting it attest its own Git bindings."""
    value = _validate_candidate_acceptance_core(
        record,
        candidate=candidate,
        acceptance_schema=acceptance_schema,
        candidate_schema=candidate_schema,
        authority_id=authority_id,
        candidate_path=candidate_path,
        authorized_scope=authorized_scope,
        prohibited_scope=prohibited_scope,
        extra_candidate_bindings=extra_candidate_bindings,
    )
    _validate_trusted_record_bindings(value, expected_bindings, "record_digest")
    return cast(str, value["record_digest"])


def _validate_candidate_acceptance_core(
    record: Mapping[str, object],
    *,
    candidate: Mapping[str, object],
    acceptance_schema: str,
    candidate_schema: str,
    authority_id: str,
    candidate_path: str,
    authorized_scope: str,
    prohibited_scope: list[str],
    extra_candidate_bindings: tuple[str, ...],
) -> JsonObject:
    binding_keys = {
        "accepted_candidate_sha",
        "accepted_candidate_tree",
        "accepted_candidate_path",
        "accepted_candidate_git_blob_oid",
        "accepted_candidate_file_sha256",
        "accepted_candidate_record_digest",
        "accepted_plan_acceptance_record_digest",
        "locator_custody_implementation_acceptance_record_digest",
        *extra_candidate_bindings,
    }
    value = _json_object(record)
    keys = {
        "schema_version",
        "authority_id",
        "change_control_id",
        *binding_keys,
        "independent_review",
        "same_sha_ci",
        "principal_acceptance",
        "authorized_scope",
        "prohibited_scope",
        "record_created_at_utc",
        "record_digest",
    }
    _exact(value, keys, "candidate acceptance")
    validate_typed_record(value, acceptance_schema, "record_digest")
    candidate_value = validate_typed_record(
        _json_object(candidate), candidate_schema, "record_digest"
    )
    if (
        value["authority_id"] != authority_id
        or value["change_control_id"] != "P3_P7_D02_CC_09"
        or value["accepted_candidate_path"] != candidate_path
        or value["authorized_scope"] != authorized_scope
        or value["prohibited_scope"] != prohibited_scope
        or value["accepted_candidate_record_digest"] != candidate_value["record_digest"]
        or any(value[key] != candidate_value[key] for key in extra_candidate_bindings)
    ):
        raise LocatorCustodyError("CUSTODY_CANDIDATE_ACCEPTANCE_BINDING_STOP")
    for key in binding_keys:
        if key.endswith("_digest") or key.endswith("_file_sha256"):
            _digest(value[key], key)
        elif key != "accepted_candidate_path":
            _sha(value[key], key)
        elif not isinstance(value[key], str):
            raise LocatorCustodyError("CUSTODY_CANDIDATE_ACCEPTANCE_BINDING_STOP")
    _timestamp(value["record_created_at_utc"])
    _validate_acceptance_evidence(
        value,
        accepted_sha_key="accepted_candidate_sha",
        review_sha_key="reviewed_candidate_sha",
        principal_sha_key="accepted_candidate_sha",
    )
    return value


def validate_project_private_bridge_scratch_name_receipt(
    record: Mapping[str, object], *, bindings: Mapping[str, object] | None = None
) -> str:
    return validate_cc09_record(BRIDGE_SCRATCH_RECEIPT_SCHEMA, record, bindings=bindings)


@dataclass
class SyntheticCc09Component:
    identity_digest: str
    protected_dacl: bool = True
    receipt: JsonObject | None = None
    receipt_bytes: bytes | None = None
    expected_bindings: JsonObject | None = None
    payloads: set[str] = field(default_factory=set)
    replaced: bool = False
    cleanup_succeeds: bool = True


@dataclass
class SyntheticCc09BootstrapStore:
    """Injected-only state machine, with mutation evidence but no host I/O."""

    components: dict[str, SyntheticCc09Component] = field(default_factory=dict)
    mutations: list[str] = field(default_factory=list)
    checkout: dict[str, object] = field(default_factory=dict)

    def _component(self, name: str) -> SyntheticCc09Component | None:
        return self.components.get(name)

    def create_new(self, name: str, identity_digest: str) -> SyntheticCc09Component:
        _digest(identity_digest, "identity")
        if name in self.components:
            raise LocatorCustodyError("CC09_CREATE_NEW_COLLISION_STOP")
        self.mutations.append(f"CREATE:{name}")
        item = SyntheticCc09Component(identity_digest=identity_digest)
        self.components[name] = item
        return item

    def write_first_receipt(
        self, name: str, record: Mapping[str, object], schema: str, bindings: Mapping[str, object]
    ) -> None:
        item = self.components.get(name)
        if (
            item is None
            or item.receipt is not None
            or not item.protected_dacl
            or item.replaced
            or item.payloads
        ):
            raise LocatorCustodyError("CC09_FIRST_RECEIPT_PRECONDITION_STOP")
        validate_cc09_record(schema, record, bindings=bindings)
        self._replay_new_component(item, record, schema, bindings)
        self.mutations.append(f"RECEIPT:{name}")
        item.receipt = _json_object(record)
        item.receipt_bytes = canonical_json_bytes(item.receipt)
        item.expected_bindings = _json_object(bindings)

    @staticmethod
    def _replay_new_component(
        item: SyntheticCc09Component,
        record: Mapping[str, object],
        schema: str,
        bindings: Mapping[str, object],
    ) -> None:
        bound = _json_object(bindings)
        identity_key = {
            CODE_CACHE_RECEIPT_SCHEMA: "code_cache_identity_digest",
            R06_CHECKOUT_SEAL_SCHEMA: "checkout_identity_digest",
            PROJECT_CONTAINER_RECEIPT_SCHEMA: "project_container_identity_digest",
            PRIVATE_HOME_RECEIPT_SCHEMA: "private_home_identity_digest",
            BRIDGE_SCRATCH_RECEIPT_SCHEMA: "bridge_scratch_identity_digest",
        }.get(schema)
        if identity_key is None or bound.get(identity_key) != item.identity_digest:
            raise LocatorCustodyError("CC09_PHYSICAL_IDENTITY_DRIFT_STOP")
        if not item.protected_dacl or item.replaced:
            raise LocatorCustodyError("CC09_PHYSICAL_REPLAY_STOP")
        validate_cc09_record(schema, record, bindings=bound)

    @staticmethod
    def replay_immutable_controls(item: SyntheticCc09Component | None, schema: str) -> JsonObject:
        if (
            item is None
            or item.receipt is None
            or item.receipt_bytes is None
            or item.expected_bindings is None
            or item.replaced
            or not item.protected_dacl
            or canonical_json_bytes(item.receipt) != item.receipt_bytes
        ):
            raise LocatorCustodyError("CC09_PHYSICAL_REPLAY_STOP")
        SyntheticCc09BootstrapStore._replay_new_component(
            item, item.receipt, schema, item.expected_bindings
        )
        return item.receipt

    @staticmethod
    def replay_component(item: SyntheticCc09Component | None, schema: str) -> JsonObject:
        if item is None or item.payloads:
            raise LocatorCustodyError("CC09_PHYSICAL_REPLAY_STOP")
        return SyntheticCc09BootstrapStore.replay_immutable_controls(item, schema)

    def cleanup_scratch_payloads(self, item: SyntheticCc09Component) -> None:
        if not item.cleanup_succeeds:
            raise LocatorCustodyError("BRIDGE_SCRATCH_RESIDUE_STOP")
        self.mutations.append("CLEANUP:bridge-scratch-v1")
        item.payloads.clear()


def bootstrap_private_home(
    store: SyntheticCc09BootstrapStore,
    *,
    container_receipt: Mapping[str, object],
    private_home_receipt: Mapping[str, object],
    container_bindings: Mapping[str, object],
    private_home_bindings: Mapping[str, object],
) -> str:
    """Only durable prefixes are recoverable; every other observed state stops."""
    container = store._component("ProjectMirror")
    home = store._component("principal-private-output-v1")
    if container is None and home is not None:
        raise LocatorCustodyError("PRIVATE_HOME_DIRECTORY_ONLY_STOP")
    if container is None:
        if home is not None:
            raise LocatorCustodyError("PRIVATE_HOME_PROJECT_COMPONENT_UNBOUND_STOP")
        container = store.create_new(
            "ProjectMirror", cast(str, container_bindings["project_container_identity_digest"])
        )
        store.write_first_receipt(
            "ProjectMirror", container_receipt, PROJECT_CONTAINER_RECEIPT_SCHEMA, container_bindings
        )
    else:
        if (
            container.receipt is None
            or container.replaced
            or not container.protected_dacl
            or container.payloads
        ):
            raise LocatorCustodyError("PRIVATE_HOME_PROJECT_COMPONENT_UNBOUND_STOP")
        SyntheticCc09BootstrapStore.replay_component(container, PROJECT_CONTAINER_RECEIPT_SCHEMA)
        validate_project_mirror_container_name_receipt(
            container.receipt, bindings=container_bindings
        )
    if home is None:
        home = store.create_new(
            "principal-private-output-v1",
            cast(str, private_home_bindings["private_home_identity_digest"]),
        )
        store.write_first_receipt(
            "principal-private-output-v1",
            private_home_receipt,
            PRIVATE_HOME_RECEIPT_SCHEMA,
            private_home_bindings,
        )
        return "PRIVATE_HOME_CREATED"
    if home.receipt is None or home.replaced or not home.protected_dacl or home.payloads:
        raise LocatorCustodyError("PRIVATE_HOME_DIRECTORY_ONLY_STOP")
    SyntheticCc09BootstrapStore.replay_component(home, PRIVATE_HOME_RECEIPT_SCHEMA)
    validate_project_private_home_name_receipt(home.receipt, bindings=private_home_bindings)
    return "PRIVATE_HOME_REPLAYED"


def bootstrap_code_cache_checkout(
    store: SyntheticCc09BootstrapStore,
    *,
    cache_receipt: Mapping[str, object],
    seal_receipt: Mapping[str, object],
    cache_bindings: Mapping[str, object],
    seal_bindings: Mapping[str, object],
) -> str:
    cache = store._component("ProjectMirror-code-cache-v1")
    checkout = store._component("accepted-r06-ab08a6e861ec")
    if cache is None:
        if checkout is not None:
            raise LocatorCustodyError("CODE_CHECKOUT_PARTIAL_OR_CORRUPT_STOP")
        cache = store.create_new(
            "ProjectMirror-code-cache-v1", cast(str, cache_bindings["code_cache_identity_digest"])
        )
        store.write_first_receipt(
            "ProjectMirror-code-cache-v1", cache_receipt, CODE_CACHE_RECEIPT_SCHEMA, cache_bindings
        )
    elif cache.receipt is None or cache.replaced or not cache.protected_dacl or cache.payloads:
        raise LocatorCustodyError("CODE_CHECKOUT_PARTIAL_OR_CORRUPT_STOP")
    else:
        SyntheticCc09BootstrapStore.replay_component(cache, CODE_CACHE_RECEIPT_SCHEMA)
        validate_project_code_cache_name_receipt(cache.receipt, bindings=cache_bindings)
    if checkout is None:
        checkout = store.create_new(
            "accepted-r06-ab08a6e861ec", cast(str, seal_bindings["checkout_identity_digest"])
        )
        store.checkout = {
            "clone_local": True,
            "hardlinks": False,
            "origin": False,
            "required_ref": _R06_CHECKPOINT,
            "head": _R06_SHA,
            "tree": _R06_TREE,
            "governed_rows": list(_R06_ROWS),
            "source_absolute_path": False,
        }
        store.write_first_receipt(
            "accepted-r06-ab08a6e861ec", seal_receipt, R06_CHECKOUT_SEAL_SCHEMA, seal_bindings
        )
        return "CHECKOUT_SEALED"
    if (
        checkout.receipt is None
        or checkout.replaced
        or not checkout.protected_dacl
        or checkout.payloads
    ):
        raise LocatorCustodyError("CODE_CHECKOUT_PARTIAL_OR_CORRUPT_STOP")
    expected = {
        "clone_local": True,
        "hardlinks": False,
        "origin": False,
        "required_ref": _R06_CHECKPOINT,
        "head": _R06_SHA,
        "tree": _R06_TREE,
        "governed_rows": list(_R06_ROWS),
        "source_absolute_path": False,
    }
    if store.checkout != expected:
        raise LocatorCustodyError("CODE_CHECKOUT_PARTIAL_OR_CORRUPT_STOP")
    SyntheticCc09BootstrapStore.replay_component(checkout, R06_CHECKOUT_SEAL_SCHEMA)
    validate_accepted_r06_checkout_seal_receipt(checkout.receipt, bindings=seal_bindings)
    return "CHECKOUT_REPLAYED"


def bootstrap_bridge_scratch(
    store: SyntheticCc09BootstrapStore,
    *,
    scratch_receipt: Mapping[str, object],
    scratch_bindings: Mapping[str, object],
) -> str:
    scratch = store._component("bridge-scratch-v1")
    if scratch is None:
        scratch = store.create_new(
            "bridge-scratch-v1", cast(str, scratch_bindings["bridge_scratch_identity_digest"])
        )
        store.write_first_receipt(
            "bridge-scratch-v1", scratch_receipt, BRIDGE_SCRATCH_RECEIPT_SCHEMA, scratch_bindings
        )
        return "BRIDGE_SCRATCH_CREATED"
    if (
        scratch.receipt is None
        or scratch.replaced
        or not scratch.protected_dacl
        or scratch.payloads
    ):
        raise LocatorCustodyError("BRIDGE_SCRATCH_RESIDUE_STOP")
    SyntheticCc09BootstrapStore.replay_component(scratch, BRIDGE_SCRATCH_RECEIPT_SCHEMA)
    validate_project_private_bridge_scratch_name_receipt(scratch.receipt, bindings=scratch_bindings)
    return "BRIDGE_SCRATCH_REPLAYED"


def run_synthetic_bridge_scratch(
    store: SyntheticCc09BootstrapStore,
    child: Callable[[Mapping[str, str], SyntheticCc09Component], None],
) -> None:
    scratch = store._component("bridge-scratch-v1")
    try:
        SyntheticCc09BootstrapStore.replay_component(scratch, BRIDGE_SCRATCH_RECEIPT_SCHEMA)
    except LocatorCustodyError as exc:
        raise LocatorCustodyError("BRIDGE_SCRATCH_RESIDUE_STOP") from exc
    if scratch is None:
        raise LocatorCustodyError("BRIDGE_SCRATCH_RESIDUE_STOP")
    env = {"TEMP": "receipt-bound-bridge-scratch", "TMP": "receipt-bound-bridge-scratch"}
    try:
        child(env, scratch)
    except BaseException as exc:
        # Crashes/cancellation preserve transient bytes for custody review.
        raise LocatorCustodyError("BRIDGE_SCRATCH_RESIDUE_STOP") from exc
    else:
        try:
            SyntheticCc09BootstrapStore.replay_immutable_controls(
                scratch, BRIDGE_SCRATCH_RECEIPT_SCHEMA
            )
            store.cleanup_scratch_payloads(scratch)
        except LocatorCustodyError as exc:
            raise LocatorCustodyError("BRIDGE_SCRATCH_RESIDUE_STOP") from exc
    try:
        SyntheticCc09BootstrapStore.replay_component(scratch, BRIDGE_SCRATCH_RECEIPT_SCHEMA)
    except LocatorCustodyError as exc:
        raise LocatorCustodyError("BRIDGE_SCRATCH_RESIDUE_STOP") from exc


# E6A deliberately models the receipt-bound ledger only.  It is not a host
# filesystem implementation and accepts only a caller-owned synthetic root.
_NAMESPACE_FIELDS: Final[tuple[str, ...]] = (
    "schema_version",
    "project_id",
    "private_home_handle_id",
    "custody_namespace_id",
    "purpose",
    "change_control_id",
    "authority_id",
    "allowed_subject_root_ids",
    "resolver_contract_digest",
    "host_binding_acceptance_record_digest",
    "private_home_binding_acceptance_record_digest",
    "principal_sid_digest",
    "known_folder_identity_digest",
    "private_home_identity_digest",
    "copy_a_id",
    "copy_b_id",
    "namespace_first_object_logical_name",
    "copy_common_genesis_schema_version",
    "copy_genesis_receipt_schema_version",
    "locator_name_receipt_schema_version",
    "event_schema_version",
    "intent_schema_version",
    "commit_schema_version",
    "snapshot_schema_version",
    "transaction_id_schema_version",
    "locator_schema_version",
    "path_identity_schema_version",
    "worktree_set_schema_version",
    "canonicalization_version",
    "relative_control_manifest",
    "locator_custody_implementation_sha",
    "locator_custody_implementation_acceptance_record_digest",
    "retention_policy",
    "cleanup_policy",
    "created_at_utc",
    "receipt_digest",
)
_COMMON_GENESIS_FIELDS: Final[tuple[str, ...]] = (
    "schema_version",
    "namespace_receipt_digest",
    "locator_authority_id",
    "allocation_id",
    "evidence_root_id",
    "root_basename",
    "initial_sequence",
    "initial_authority_state",
)
_COPY_GENESIS_FIELDS: Final[tuple[str, ...]] = (
    "schema_version",
    "namespace_receipt_digest",
    "locator_authority_id",
    "allocation_id",
    "evidence_root_id",
    "root_basename",
    "copy_id",
    "peer_copy_id",
    "common_genesis_digest",
    "created_at_utc",
    "genesis_receipt_digest",
)
_LOCATOR_FIELDS: Final[tuple[str, ...]] = (
    "private_home_handle_id",
    "destination_class",
    "normalized_relative_locator",
    "evidence_root_id",
    "root_basename",
)
_LOCATOR_RECEIPT_FIELDS: Final[tuple[str, ...]] = (
    "schema_version",
    "namespace_receipt_digest",
    "locator_authority_id",
    "allocation_id",
    "evidence_root_id",
    "root_basename",
    "semantic_role",
    "private_home_handle_id",
    "destination_class",
    "normalized_relative_locator",
    "opaque_locator_scheme",
    "opaque_locator",
    "locator_digest",
    "allowed_principal_tasks",
    "accepted_cc08_plan_sha",
    "accepted_cc08_plan_tree",
    "registry_implementation_sha",
    "registry_implementation_tree",
    "registry_implementation_acceptance_record_digest",
    "registry_implementation_acceptance_authority_digest",
    "maximum_bytes",
    "retention",
    "allocated_at_utc",
    "name_receipt_digest",
)
_WORKTREE_FIELDS: Final[tuple[str, ...]] = (
    "schema_version",
    "enumeration_method",
    "repository_common_dir_identity_digest",
    "ordered_worktree_identity_digests",
    "set_digest",
)
_SNAPSHOT_FIELDS: Final[tuple[str, ...]] = (
    "schema_version",
    "namespace_receipt_digest",
    "locator_authority_id",
    "allocation_id",
    "evidence_root_id",
    "common_genesis_digest",
    "event_count",
    "head_event_digest",
    "ordered_event_digests",
    "authority_state",
    "semantic_snapshot_digest",
)
_COMMIT_FIELDS: Final[tuple[str, ...]] = (
    "schema_version",
    "namespace_receipt_digest",
    "locator_name_receipt_digest",
    "locator_authority_id",
    "allocation_id",
    "evidence_root_id",
    "transaction_id",
    "sequence",
    "intent_digest",
    "event_digest",
    "copy_a_genesis_receipt_digest",
    "copy_b_genesis_receipt_digest",
    "copy_a_event_file_sha256",
    "copy_b_event_file_sha256",
    "copy_a_snapshot_digest",
    "copy_b_snapshot_digest",
    "commit_created_at_utc",
    "commit_digest",
)
_NAMESPACE_FILE: Final = "PROJECT_MIRROR_PRIVATE_OUTPUT_REGISTRY_NAMESPACE_NAME_RECEIPT.json"
_GENESIS_FILE: Final = "D02_R2_LOCATOR_CUSTODY_COPY_GENESIS.json"
_LOCATOR_FILE: Final = "D02_R2_EVIDENCE_ROOT_LOCATOR_NAME_RECEIPT.json"
_ALLOCATION: Final = "P3_P7_D02_R2_CC08_E1_ROOT_LOCATOR_ALLOCATION"
_CUSTODY_NAMESPACE_ID: Final = "pm-project-mirror-principal-private-output-registry-v1"
_CUSTODY_AUTHORITY_ID: Final = "P3_P7_D02_R2_LOCATOR_CUSTODY_AUTHORITY_01"
_COPY_A_ID: Final = "P3_P7_D02_R2_LOCATOR_CUSTODY_A"
_COPY_B_ID: Final = "P3_P7_D02_R2_LOCATOR_CUSTODY_B"
_EVIDENCE_ROOT_ID: Final = "P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT"
_EVIDENCE_ROOT_BASENAME: Final = "p3-p7-d02-r2-cc08-e1-evidence"
_PRIVATE_HOME_HANDLE_ID: Final = "PM_PROJECT_MIRROR_PRIVATE_HOME_V1"
_CC08_PLAN_SHA: Final = "218f4b5a5ee4e6e2223995d232da61496dd47de3"
_CC08_PLAN_TREE: Final = "1cff56bd1f1127a310622d5b8a72045b39290549"
_R06_ACCEPTANCE_AUTHORITY_DIGEST: Final = (
    "08af0bbc6802939cee9a26020b505dc9b323c3f67992f987ee4dc7b5d4930943"
)
PROTECTED_CUSTODY_WRITE_BOUNDARY: Final = "SyntheticLocatorCustodyLedger.root_AND_DESCENDANTS"
_SCAFFOLD: Final[tuple[str, ...]] = (
    "copy-a",
    "copy-a/events",
    "copy-b",
    "copy-b/events",
    "allocations",
    f"allocations/{_ALLOCATION}",
    "transactions",
    "transactions/intents",
    "transactions/commits",
)
_EVENT_FIXED_CONTINUITY_FIELDS: Final[tuple[str, ...]] = (
    "namespace_receipt_digest",
    "locator_name_receipt_digest",
    "locator_authority_id",
    "allocation_id",
    "evidence_root_id",
    "root_basename",
    "opaque_locator",
    "locator_digest",
    "root_receipt_created_at_utc",
    "accepted_cc08_plan_sha",
    "accepted_cc08_plan_tree",
    "registry_implementation_sha",
    "registry_implementation_tree",
    "registry_implementation_acceptance_record_digest",
    "registry_implementation_acceptance_authority_digest",
    "parent_identity_digest",
)

_NAMESPACE_GUARD_REGISTRY_LOCK: Final = threading.Lock()
_NAMESPACE_GUARDS: Final[dict[str, threading.RLock]] = {}
_NAMESPACE_GUARD_STATE: Final = threading.local()


@contextmanager
def _windows_namespace_mutex(identity_digest: str) -> Iterator[None]:
    import ctypes

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_mutex = kernel32.CreateMutexW
        wait_for_single_object = kernel32.WaitForSingleObject
        release_mutex = kernel32.ReleaseMutex
        close_handle = kernel32.CloseHandle
        create_mutex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        create_mutex.restype = ctypes.c_void_p
        wait_for_single_object.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        wait_for_single_object.restype = ctypes.c_uint32
        release_mutex.argtypes = [ctypes.c_void_p]
        release_mutex.restype = ctypes.c_int
        close_handle.argtypes = [ctypes.c_void_p]
        close_handle.restype = ctypes.c_int
        handle = create_mutex(
            None,
            0,
            f"Global\\ProjectMirror-D02R2-Custody-{identity_digest}",
        )
    except (AttributeError, OSError, TypeError):
        raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP") from None
    if not handle:
        raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
    acquired = False
    try:
        wait_result = wait_for_single_object(handle, 0xFFFFFFFF)
        if wait_result == 0x00000080:  # WAIT_ABANDONED
            if not release_mutex(handle):
                raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
        if wait_result != 0x00000000:  # WAIT_OBJECT_0
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
        acquired = True
        yield
    finally:
        release_failed = acquired and not release_mutex(handle)
        close_failed = not close_handle(handle)
        if release_failed or close_failed:
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")


@contextmanager
def _posix_namespace_lock(root: Path, identity_digest: str) -> Iterator[None]:
    class FlockApi(Protocol):
        LOCK_EX: int
        LOCK_UN: int

        def flock(self, descriptor: int, operation: int) -> None: ...

    fcntl = cast(FlockApi, importlib.import_module("fcntl"))

    lock_path = root.parent / f".project-mirror-d02-r2-custody-{identity_digest}.lock"
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError:
        raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP") from None
    acquired = False
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        acquired = True
        yield
    except OSError:
        raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP") from None
    finally:
        try:
            if acquired:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


@contextmanager
def _namespace_scoped_exclusive_guard(root: Path) -> Iterator[None]:
    """Serialize one namespace across threads/processes without an inner artifact."""

    try:
        resolved = root.resolve(strict=False)
        key = os.path.normcase(str(resolved))
    except OSError:
        raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP") from None
    identity_digest = _sha256(key.encode("utf-8"))
    with _NAMESPACE_GUARD_REGISTRY_LOCK:
        guard = _NAMESPACE_GUARDS.setdefault(key, threading.RLock())
    with guard:
        held_keys = cast(set[str], getattr(_NAMESPACE_GUARD_STATE, "held_keys", set()))
        if key in held_keys:
            yield
            return
        _NAMESPACE_GUARD_STATE.held_keys = {*held_keys, key}
        try:
            if os.name == "nt":
                with _windows_namespace_mutex(identity_digest):
                    yield
            else:
                with _posix_namespace_lock(resolved, identity_digest):
                    yield
        finally:
            _NAMESPACE_GUARD_STATE.held_keys = held_keys


def _ledger_record(
    schema: str, fields: tuple[str, ...], digest_key: str, values: Mapping[str, object]
) -> JsonObject:
    record = _json_object(values)
    _exact(record, set(fields) - {digest_key}, "ledger builder")
    record["schema_version"] = schema
    record[digest_key] = typed_digest(schema, record)
    return record


def _validate_ledger_record(
    record: Mapping[str, object], schema: str, fields: tuple[str, ...], digest_key: str
) -> JsonObject:
    value = _json_object(record)
    _exact(value, set(fields), "ledger record")
    return validate_typed_record(value, schema, digest_key)


def make_namespace_name_receipt(fields: Mapping[str, object]) -> JsonObject:
    result = _ledger_record(NAMESPACE_SCHEMA, _NAMESPACE_FIELDS, "receipt_digest", fields)
    validate_namespace_name_receipt(result)
    return result


def validate_namespace_name_receipt(record: Mapping[str, object]) -> JsonObject:
    value = _validate_ledger_record(record, NAMESPACE_SCHEMA, _NAMESPACE_FIELDS, "receipt_digest")
    if (value["project_id"], value["purpose"], value["namespace_first_object_logical_name"]) != (
        "PROJECT_MIRROR",
        "D02_R2_SINGLE_ROOT_LOCATOR_CUSTODY_ONLY",
        _NAMESPACE_FILE,
    ) or value["allowed_subject_root_ids"] != ["P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT"]:
        raise LocatorCustodyError("CUSTODY_NAMESPACE_RECEIPT_BINDING_STOP")
    if value["copy_a_id"] == value["copy_b_id"] or value["relative_control_manifest"] != [
        dict(row) for row in RELATIVE_CONTROL_MANIFEST
    ]:
        raise LocatorCustodyError("CUSTODY_NAMESPACE_RECEIPT_BINDING_STOP")
    for key in (
        "resolver_contract_digest",
        "host_binding_acceptance_record_digest",
        "private_home_binding_acceptance_record_digest",
        "principal_sid_digest",
        "known_folder_identity_digest",
        "private_home_identity_digest",
        "locator_custody_implementation_acceptance_record_digest",
    ):
        _digest(value[key], key)
    _sha(value["locator_custody_implementation_sha"], "implementation sha")
    _timestamp(value["created_at_utc"])
    return value


def make_common_genesis(fields: Mapping[str, object]) -> JsonObject:
    # This schema deliberately has no self field; its complete typed digest is the genesis head.
    result = _json_object(fields)
    _exact(result, set(_COMMON_GENESIS_FIELDS), "common genesis builder")
    result["schema_version"] = COMMON_GENESIS_SCHEMA
    validate_common_genesis(result)
    return result


def validate_common_genesis(record: Mapping[str, object]) -> str:
    value = _json_object(record)
    _exact(value, set(_COMMON_GENESIS_FIELDS), "common genesis")
    if (
        value.get("schema_version") != COMMON_GENESIS_SCHEMA
        or value.get("initial_sequence") != 0
        or value.get("initial_authority_state") is not None
    ):
        raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
    for key in ("namespace_receipt_digest",):
        _digest(value[key], key)
    for key in ("locator_authority_id", "allocation_id", "evidence_root_id", "root_basename"):
        _id(value[key], key)
    return typed_digest(COMMON_GENESIS_SCHEMA, value)


def make_copy_genesis(fields: Mapping[str, object]) -> JsonObject:
    result = _ledger_record(
        COPY_GENESIS_SCHEMA, _COPY_GENESIS_FIELDS, "genesis_receipt_digest", fields
    )
    validate_copy_genesis(result)
    return result


def validate_copy_genesis(record: Mapping[str, object]) -> JsonObject:
    value = _validate_ledger_record(
        record, COPY_GENESIS_SCHEMA, _COPY_GENESIS_FIELDS, "genesis_receipt_digest"
    )
    if value["copy_id"] == value["peer_copy_id"]:
        raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
    for key in ("namespace_receipt_digest", "common_genesis_digest"):
        _digest(value[key], key)
    for key in (
        "locator_authority_id",
        "allocation_id",
        "evidence_root_id",
        "root_basename",
        "copy_id",
        "peer_copy_id",
    ):
        _id(value[key], key)
    _timestamp(value["created_at_utc"])
    return value


def make_evidence_root_locator(fields: Mapping[str, object]) -> JsonObject:
    value = _json_object(fields)
    _exact(value, set(_LOCATOR_FIELDS), "locator")
    validate_evidence_root_locator(value)
    return value


def validate_evidence_root_locator(record: Mapping[str, object]) -> str:
    value = _json_object(record)
    _exact(value, set(_LOCATOR_FIELDS), "locator")
    if (
        value["destination_class"] != "D02_R2_EVIDENCE_ROOT"
        or value["normalized_relative_locator"] != "d02-r2-evidence/p3-p7-d02-r2-cc08-e1-evidence"
    ):
        raise LocatorCustodyError("CUSTODY_LOCATOR_BINDING_STOP")
    for key in ("private_home_handle_id", "evidence_root_id", "root_basename"):
        _id(value[key], key)
    return typed_digest(LOCATOR_SCHEMA, value)


def opaque_locator_for(locator: Mapping[str, object]) -> str:
    value = make_evidence_root_locator(locator)
    return "pmhome1:" + _b64(cast(str, value["normalized_relative_locator"]).encode("utf-8"))


def make_locator_name_receipt(fields: Mapping[str, object]) -> JsonObject:
    result = _ledger_record(
        LOCATOR_RECEIPT_SCHEMA, _LOCATOR_RECEIPT_FIELDS, "name_receipt_digest", fields
    )
    validate_locator_name_receipt(result)
    return result


def validate_locator_name_receipt(record: Mapping[str, object]) -> JsonObject:
    value = _validate_ledger_record(
        record, LOCATOR_RECEIPT_SCHEMA, _LOCATOR_RECEIPT_FIELDS, "name_receipt_digest"
    )
    locator = {key: value[key] for key in _LOCATOR_FIELDS}
    if (
        value["semantic_role"] != "CC08_SINGLE_EVIDENCE_ROOT_LOCATOR"
        or value["opaque_locator_scheme"] != "pmhome1"
        or value["opaque_locator"] != opaque_locator_for(locator)
        or value["locator_digest"] != validate_evidence_root_locator(locator)
    ):
        raise LocatorCustodyError("CUSTODY_LOCATOR_BINDING_STOP")
    if value["maximum_bytes"] != 42_949_672_960 or value["allowed_principal_tasks"] != [
        "P3_P7_D02_R2_EXECUTION_01",
        "P3_P7_D02_R2_EVIDENCE_REVIEW_01",
        "P3_P7_D02_R2_R05_DURABILITY_01",
    ]:
        raise LocatorCustodyError("CUSTODY_LOCATOR_BINDING_STOP")
    for key in (
        "namespace_receipt_digest",
        "registry_implementation_acceptance_record_digest",
        "registry_implementation_acceptance_authority_digest",
    ):
        _digest(value[key], key)
    for key in (
        "accepted_cc08_plan_sha",
        "accepted_cc08_plan_tree",
        "registry_implementation_sha",
        "registry_implementation_tree",
    ):
        _sha(value[key], key)
    _timestamp(value["allocated_at_utc"])
    return value


def make_excluded_git_worktree_identity_set(fields: Mapping[str, object]) -> JsonObject:
    result = _ledger_record(WORKTREE_SCHEMA, _WORKTREE_FIELDS, "set_digest", fields)
    validate_excluded_git_worktree_identity_set(result)
    return result


def validate_excluded_git_worktree_identity_set(record: Mapping[str, object]) -> JsonObject:
    value = _validate_ledger_record(record, WORKTREE_SCHEMA, _WORKTREE_FIELDS, "set_digest")
    rows = value["ordered_worktree_identity_digests"]
    if not isinstance(rows, list) or any(not isinstance(row, str) for row in rows):
        raise LocatorCustodyError("CUSTODY_WORKTREE_SET_STOP")
    text_rows = cast(list[str], rows)
    if value["enumeration_method"] != "git-worktree-list-porcelain-z-v1" or text_rows != sorted(
        set(text_rows)
    ):
        raise LocatorCustodyError("CUSTODY_WORKTREE_SET_STOP")
    _digest(value["repository_common_dir_identity_digest"], "common dir")
    for row in text_rows:
        _digest(row, "worktree identity")
    return value


def make_semantic_snapshot(fields: Mapping[str, object]) -> JsonObject:
    result = _ledger_record(SNAPSHOT_SCHEMA, _SNAPSHOT_FIELDS, "semantic_snapshot_digest", fields)
    validate_semantic_snapshot(result)
    return result


def validate_semantic_snapshot(record: Mapping[str, object]) -> JsonObject:
    value = _validate_ledger_record(
        record, SNAPSHOT_SCHEMA, _SNAPSHOT_FIELDS, "semantic_snapshot_digest"
    )
    count, ordered = value["event_count"], value["ordered_event_digests"]
    if (
        not isinstance(count, int)
        or isinstance(count, bool)
        or count < 0
        or not isinstance(ordered, list)
        or len(ordered) != count
    ):
        raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
    _digest(value["common_genesis_digest"], "common genesis")
    for item in ordered:
        _digest(item, "event digest")
    if count == 0:
        if (
            value["head_event_digest"] != value["common_genesis_digest"]
            or value["authority_state"] is not None
        ):
            raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
    elif value["head_event_digest"] != ordered[-1] or value["authority_state"] not in {
        "PREPARED",
        "ROOT_RECEIPT_DURABLE",
        "ROOT_REGISTRY_READY",
    }:
        raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
    return value


def make_commit_receipt(fields: Mapping[str, object]) -> JsonObject:
    result = _ledger_record(COMMIT_SCHEMA, _COMMIT_FIELDS, "commit_digest", fields)
    validate_commit_receipt(result)
    return result


def validate_commit_receipt(record: Mapping[str, object]) -> JsonObject:
    value = _validate_ledger_record(record, COMMIT_SCHEMA, _COMMIT_FIELDS, "commit_digest")
    _sequence(value["sequence"])
    for key in (
        "namespace_receipt_digest",
        "locator_name_receipt_digest",
        "transaction_id",
        "intent_digest",
        "event_digest",
        "copy_a_genesis_receipt_digest",
        "copy_b_genesis_receipt_digest",
        "copy_a_event_file_sha256",
        "copy_b_event_file_sha256",
        "copy_a_snapshot_digest",
        "copy_b_snapshot_digest",
    ):
        _digest(value[key], key)
    _timestamp(value["commit_created_at_utc"])
    return value


def event_filename(sequence: int, event_digest: str) -> str:
    _sequence(sequence)
    _digest(event_digest, "event digest")
    return f"D02_R2_LOCATOR_CUSTODY_EVENT__{sequence:08d}__{event_digest}.json"


def intent_filename(transaction_id: str) -> str:
    _digest(transaction_id, "transaction id")
    return f"D02_R2_LOCATOR_CUSTODY_INTENT__{transaction_id}.json"


def commit_filename(transaction_id: str) -> str:
    _digest(transaction_id, "transaction id")
    return f"D02_R2_LOCATOR_CUSTODY_COMMIT__{transaction_id}.json"


@dataclass
class SyntheticLocatorCustodyLedger:
    """Deterministic two-copy crash-recovery ledger over a synthetic temp root."""

    root: Path
    bootstrap_implementation_acceptance: TrustedAcceptanceBindingSource = field(repr=False)
    bootstrap_private_home_acceptance: TrustedAcceptanceBindingSource = field(repr=False)
    mutations: list[str] = field(default_factory=list)

    def _path(self, name: str) -> Path:
        if not name or name.startswith(("/", "\\")) or ".." in Path(name).parts:
            raise LocatorCustodyError("HANDLE_RELATIVE_CREATION_UNAVAILABLE_STOP")
        return self.root / name

    def _write(self, name: str, record: Mapping[str, object]) -> None:
        path = self._path(name)
        raw = canonical_json_bytes(_json_object(record))
        try:
            if path.exists():
                raise LocatorCustodyError("LOCATOR_NAME_RECEIPT_COLLISION_STOP")
            with path.open("xb") as handle:
                handle.write(raw)
                handle.flush()
            if path.read_bytes() != raw:
                raise LocatorCustodyError("CUSTODY_DURABILITY_BARRIER_FAILED_STOP")
        except FileExistsError:
            raise LocatorCustodyError("LOCATOR_NAME_RECEIPT_COLLISION_STOP") from None
        except OSError:
            raise LocatorCustodyError("CUSTODY_DURABILITY_BARRIER_FAILED_STOP") from None
        self.mutations.append(f"FILE:{name}")

    def _read(self, name: str) -> JsonObject:
        try:
            return canonical_loads(self._path(name).read_bytes())
        except (FileNotFoundError, IsADirectoryError, OSError):
            raise LocatorCustodyError("LOCATOR_INTENT_PARTIAL_OR_CORRUPT_STOP") from None

    def bootstrap(
        self,
        namespace_receipt: Mapping[str, object],
        common: Mapping[str, object],
        copy_a: Mapping[str, object],
        copy_b: Mapping[str, object],
        locator: Mapping[str, object],
    ) -> str:
        try:
            with _namespace_scoped_exclusive_guard(self.root):
                namespace, common_value, copy_a_value, copy_b_value, locator_value = (
                    self._validate_bootstrap_records(
                        namespace_receipt=namespace_receipt,
                        common=common,
                        copy_a=copy_a,
                        copy_b=copy_b,
                        locator=locator,
                    )
                )
                root_exists = self.root.exists()
                if root_exists:
                    if self.root.is_symlink() or not self.root.is_dir():
                        raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
                    if not self._path(_NAMESPACE_FILE).exists():
                        raise LocatorCustodyError("CUSTODY_NAMESPACE_DIRECTORY_ONLY_STOP")
                    self._validate_bootstrap_prefix(
                        namespace=namespace,
                        common=common_value,
                        copy_a=copy_a_value,
                        copy_b=copy_b_value,
                        locator=locator_value,
                    )
                if not root_exists:
                    self.root.mkdir()
                    self.mutations.append("DIR:namespace")
                    self._write(_NAMESPACE_FILE, namespace)
                for item in _SCAFFOLD:
                    path = self._path(item)
                    if not path.exists():
                        path.mkdir()
                        self.mutations.append(f"DIR:{item}")
                common_digest = validate_common_genesis(common_value)
                self._bootstrap_genesis("copy-a", copy_a_value, common_digest)
                self._bootstrap_genesis("copy-b", copy_b_value, common_digest)
                location = f"allocations/{_ALLOCATION}/{_LOCATOR_FILE}"
                if not self._path(location).exists():
                    self._write(location, locator_value)
                self._validate_fixed_authority(
                    namespace_receipt=namespace,
                    locator_receipt=locator_value,
                    common_genesis=common_value,
                    copy_a_genesis=copy_a_value,
                    copy_b_genesis=copy_b_value,
                )
                return "LOCATOR_CUSTODY_BOOTSTRAPPED"
        except LocatorCustodyError:
            raise
        except OSError:
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP") from None

    def _validate_bootstrap_records(
        self,
        *,
        namespace_receipt: Mapping[str, object],
        common: Mapping[str, object],
        copy_a: Mapping[str, object],
        copy_b: Mapping[str, object],
        locator: Mapping[str, object],
    ) -> tuple[JsonObject, JsonObject, JsonObject, JsonObject, JsonObject]:
        anchor = load_locator_bootstrap_authority_anchor(
            implementation_acceptance=self.bootstrap_implementation_acceptance,
            private_home_acceptance=self.bootstrap_private_home_acceptance,
        )
        namespace = validate_namespace_name_receipt(namespace_receipt)
        common_value = _json_object(common)
        common_digest = validate_common_genesis(common_value)
        copy_a_value = validate_copy_genesis(copy_a)
        copy_b_value = validate_copy_genesis(copy_b)
        locator_value = validate_locator_name_receipt(locator)
        namespace_literals: dict[str, Json] = {
            "project_id": "PROJECT_MIRROR",
            "private_home_handle_id": _PRIVATE_HOME_HANDLE_ID,
            "custody_namespace_id": _CUSTODY_NAMESPACE_ID,
            "purpose": "D02_R2_SINGLE_ROOT_LOCATOR_CUSTODY_ONLY",
            "change_control_id": "P3_P7_D02_CC_09",
            "authority_id": _CUSTODY_AUTHORITY_ID,
            "allowed_subject_root_ids": [_EVIDENCE_ROOT_ID],
            "host_binding_acceptance_record_digest": anchor.host_binding_acceptance_record_digest,
            "private_home_binding_acceptance_record_digest": (
                anchor.private_home_binding_acceptance_record_digest
            ),
            "copy_a_id": _COPY_A_ID,
            "copy_b_id": _COPY_B_ID,
            "namespace_first_object_logical_name": _NAMESPACE_FILE,
            "copy_common_genesis_schema_version": COMMON_GENESIS_SCHEMA,
            "copy_genesis_receipt_schema_version": COPY_GENESIS_SCHEMA,
            "locator_name_receipt_schema_version": LOCATOR_RECEIPT_SCHEMA,
            "event_schema_version": EVENT_SCHEMA,
            "intent_schema_version": INTENT_SCHEMA,
            "commit_schema_version": COMMIT_SCHEMA,
            "snapshot_schema_version": SNAPSHOT_SCHEMA,
            "transaction_id_schema_version": TRANSACTION_ID_SCHEMA,
            "locator_schema_version": LOCATOR_SCHEMA,
            "path_identity_schema_version": PATH_IDENTITY_SCHEMA,
            "worktree_set_schema_version": WORKTREE_SCHEMA,
            "canonicalization_version": "demo-canonical-json-v1",
            "relative_control_manifest": [dict(row) for row in RELATIVE_CONTROL_MANIFEST],
            "locator_custody_implementation_sha": anchor.implementation_sha,
            "locator_custody_implementation_acceptance_record_digest": (
                anchor.implementation_acceptance_record_digest
            ),
            "retention_policy": _RETAIN,
            "cleanup_policy": _CLEANUP,
            "created_at_utc": anchor.authority_created_at_utc,
        }
        if any(namespace[key] != expected for key, expected in namespace_literals.items()):
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_AUTHORITY_MISMATCH_STOP")
        common_literals: dict[str, Json] = {
            "namespace_receipt_digest": namespace["receipt_digest"],
            "locator_authority_id": _CUSTODY_AUTHORITY_ID,
            "allocation_id": _ALLOCATION,
            "evidence_root_id": _EVIDENCE_ROOT_ID,
            "root_basename": _EVIDENCE_ROOT_BASENAME,
            "initial_sequence": 0,
            "initial_authority_state": None,
        }
        if any(common_value[key] != expected for key, expected in common_literals.items()):
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_AUTHORITY_MISMATCH_STOP")
        copy_a_literals: dict[str, Json] = {
            **common_literals,
            "copy_id": _COPY_A_ID,
            "peer_copy_id": _COPY_B_ID,
            "common_genesis_digest": common_digest,
            "created_at_utc": anchor.authority_created_at_utc,
        }
        copy_b_literals: dict[str, Json] = {
            **common_literals,
            "copy_id": _COPY_B_ID,
            "peer_copy_id": _COPY_A_ID,
            "common_genesis_digest": common_digest,
            "created_at_utc": anchor.authority_created_at_utc,
        }
        for values in (copy_a_literals, copy_b_literals):
            values.pop("initial_sequence")
            values.pop("initial_authority_state")
        if any(copy_a_value[key] != expected for key, expected in copy_a_literals.items()) or any(
            copy_b_value[key] != expected for key, expected in copy_b_literals.items()
        ):
            raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
        locator_literals: dict[str, Json] = {
            "namespace_receipt_digest": namespace["receipt_digest"],
            "locator_authority_id": _CUSTODY_AUTHORITY_ID,
            "allocation_id": _ALLOCATION,
            "evidence_root_id": _EVIDENCE_ROOT_ID,
            "root_basename": _EVIDENCE_ROOT_BASENAME,
            "private_home_handle_id": _PRIVATE_HOME_HANDLE_ID,
            "destination_class": "D02_R2_EVIDENCE_ROOT",
            "normalized_relative_locator": ("d02-r2-evidence/p3-p7-d02-r2-cc08-e1-evidence"),
            "accepted_cc08_plan_sha": _CC08_PLAN_SHA,
            "accepted_cc08_plan_tree": _CC08_PLAN_TREE,
            "registry_implementation_sha": _R06_SHA,
            "registry_implementation_tree": _R06_TREE,
            "registry_implementation_acceptance_record_digest": _R06_ACCEPTANCE_DIGEST,
            "registry_implementation_acceptance_authority_digest": (
                _R06_ACCEPTANCE_AUTHORITY_DIGEST
            ),
            "retention": _RETAIN,
            "allocated_at_utc": anchor.authority_created_at_utc,
        }
        if any(locator_value[key] != expected for key, expected in locator_literals.items()):
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_AUTHORITY_MISMATCH_STOP")
        return namespace, common_value, copy_a_value, copy_b_value, locator_value

    def _validate_bootstrap_prefix(
        self,
        *,
        namespace: Mapping[str, object],
        common: Mapping[str, object],
        copy_a: Mapping[str, object],
        copy_b: Mapping[str, object],
        locator: Mapping[str, object],
    ) -> None:
        if canonical_json_bytes(self._read(_NAMESPACE_FILE)) != canonical_json_bytes(
            _json_object(namespace)
        ):
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
        self._validate_scaffold_prefix()
        if not all(self._path(item).exists() for item in _SCAFFOLD):
            return
        common_digest = validate_common_genesis(common)
        artifact_rows = (
            (f"copy-a/{_GENESIS_FILE}", copy_a, "LOCATOR_COPY_DIVERGENCE_STOP"),
            (f"copy-b/{_GENESIS_FILE}", copy_b, "LOCATOR_COPY_DIVERGENCE_STOP"),
            (
                f"allocations/{_ALLOCATION}/{_LOCATOR_FILE}",
                locator,
                "CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP",
            ),
        )
        for relative_name, expected, code in artifact_rows:
            path = self._path(relative_name)
            if path.exists() and canonical_json_bytes(
                self._read(relative_name)
            ) != canonical_json_bytes(_json_object(expected)):
                raise LocatorCustodyError(code)
        for copy_value in (copy_a, copy_b):
            if copy_value["common_genesis_digest"] != common_digest:
                raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")

    def _validate_scaffold_prefix(self) -> None:
        existing_scaffold: set[str] = set()
        seen_missing = False
        for item in _SCAFFOLD:
            path = self._path(item)
            if not path.exists():
                seen_missing = True
                continue
            if seen_missing or not path.is_dir() or path.is_symlink():
                raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
            existing_scaffold.add(item)

        expected_root = {_NAMESPACE_FILE} | {
            item for item in existing_scaffold if len(Path(item).parts) == 1
        }
        root_children = list(self.root.iterdir())
        if {item.name for item in root_children} != expected_root or any(
            item.is_symlink()
            or (item.name == _NAMESPACE_FILE and not item.is_file())
            or (item.name != _NAMESPACE_FILE and not item.is_dir())
            for item in root_children
        ):
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")

        scaffold_complete = len(existing_scaffold) == len(_SCAFFOLD)
        artifact_paths = {
            "copy-a": self._path(f"copy-a/{_GENESIS_FILE}"),
            "copy-b": self._path(f"copy-b/{_GENESIS_FILE}"),
            f"allocations/{_ALLOCATION}": self._path(f"allocations/{_ALLOCATION}/{_LOCATOR_FILE}"),
        }
        for item in existing_scaffold:
            path = self._path(item)
            expected_directories = {
                Path(candidate).name
                for candidate in existing_scaffold
                if Path(candidate).parent.as_posix() == item
            }
            expected_files: set[str] = set()
            artifact = artifact_paths.get(item)
            if scaffold_complete and artifact is not None and artifact.exists():
                expected_files.add(artifact.name)
            children = list(path.iterdir())
            if {child.name for child in children} != expected_directories | expected_files:
                raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
            if any(
                child.is_symlink()
                or (child.name in expected_directories and not child.is_dir())
                or (child.name in expected_files and not child.is_file())
                for child in children
            ):
                raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")

        if scaffold_complete:
            copy_a_genesis = artifact_paths["copy-a"].exists()
            copy_b_genesis = artifact_paths["copy-b"].exists()
            locator_receipt = artifact_paths[f"allocations/{_ALLOCATION}"].exists()
            if (copy_b_genesis and not copy_a_genesis) or (
                locator_receipt and not (copy_a_genesis and copy_b_genesis)
            ):
                raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")

    def _bootstrap_genesis(
        self, copy: str, record: Mapping[str, object], common_digest: str
    ) -> None:
        path = f"{copy}/{_GENESIS_FILE}"
        if self._path(path).exists():
            existing = self._read(path)
            if (
                canonical_json_bytes(existing) != canonical_json_bytes(_json_object(record))
                or existing["common_genesis_digest"] != common_digest
            ):
                raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
            return
        if copy == "copy-b" and not self._path(f"copy-a/{_GENESIS_FILE}").exists():
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
        self._write(path, record)

    def replay(
        self,
        *,
        namespace_receipt: Mapping[str, object],
        locator_receipt: Mapping[str, object],
        common_genesis: Mapping[str, object],
        copy_a_genesis: Mapping[str, object],
        copy_b_genesis: Mapping[str, object],
    ) -> tuple[JsonObject, JsonObject]:
        try:
            with _namespace_scoped_exclusive_guard(self.root):
                return self._replay_unlocked(
                    namespace_receipt=namespace_receipt,
                    locator_receipt=locator_receipt,
                    common_genesis=common_genesis,
                    copy_a_genesis=copy_a_genesis,
                    copy_b_genesis=copy_b_genesis,
                )
        except LocatorCustodyError:
            raise
        except OSError:
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP") from None

    def _replay_unlocked(
        self,
        *,
        namespace_receipt: Mapping[str, object],
        locator_receipt: Mapping[str, object],
        common_genesis: Mapping[str, object],
        copy_a_genesis: Mapping[str, object],
        copy_b_genesis: Mapping[str, object],
    ) -> tuple[JsonObject, JsonObject]:
        """Fully replay the exact physical committed layout in event-sequence order."""
        namespace, locator, common, copy_a, copy_b = self._validate_fixed_authority(
            namespace_receipt=namespace_receipt,
            locator_receipt=locator_receipt,
            common_genesis=common_genesis,
            copy_a_genesis=copy_a_genesis,
            copy_b_genesis=copy_b_genesis,
        )
        common_digest = validate_common_genesis(common)
        event_paths_a = self._event_paths("copy-a")
        event_paths_b = self._event_paths("copy-b")
        if len(event_paths_a) != len(event_paths_b):
            raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
        snapshot, expected_intents, expected_commits = self._replay_committed_prefix(
            count=len(event_paths_a),
            namespace_receipt=namespace,
            locator_receipt=locator,
            common_digest=common_digest,
            copy_a_genesis=copy_a,
            copy_b_genesis=copy_b,
        )
        if self._directory_file_names("transactions/intents") != expected_intents:
            raise LocatorCustodyError("LOCATOR_INTENT_PARTIAL_OR_CORRUPT_STOP")
        if self._directory_file_names("transactions/commits") != expected_commits:
            raise LocatorCustodyError("LOCATOR_COMMIT_PARTIAL_OR_CORRUPT_STOP")
        return snapshot, dict(snapshot)

    def _event_paths(self, copy: str) -> list[Path]:
        path = self._path(f"{copy}/events")
        if not path.is_dir():
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
        children = list(path.iterdir())
        if any(not item.is_file() for item in children):
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
        return sorted(children, key=lambda item: item.name)

    def _directory_file_names(self, relative_name: str) -> set[str]:
        path = self._path(relative_name)
        if not path.is_dir():
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
        children = list(path.iterdir())
        if any(not item.is_file() for item in children):
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
        return {item.name for item in children}

    def _validate_full_layout(self) -> None:
        expected = {_NAMESPACE_FILE, "copy-a", "copy-b", "allocations", "transactions"}
        if not self.root.is_dir() or {item.name for item in self.root.iterdir()} != expected:
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
        for copy in ("copy-a", "copy-b"):
            if {item.name for item in self._path(copy).iterdir()} != {_GENESIS_FILE, "events"}:
                raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
        if (
            {item.name for item in self._path("allocations").iterdir()} != {_ALLOCATION}
            or {item.name for item in self._path(f"allocations/{_ALLOCATION}").iterdir()}
            != {_LOCATOR_FILE}
            or {item.name for item in self._path("transactions").iterdir()}
            != {"intents", "commits"}
        ):
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
        if any(not self._path(item).is_dir() for item in _SCAFFOLD):
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
        for relative_name in (
            _NAMESPACE_FILE,
            f"copy-a/{_GENESIS_FILE}",
            f"copy-b/{_GENESIS_FILE}",
            f"allocations/{_ALLOCATION}/{_LOCATOR_FILE}",
        ):
            if not self._path(relative_name).is_file():
                raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")

    @staticmethod
    def _common_genesis_from_copy(copy_genesis: Mapping[str, Json]) -> JsonObject:
        return make_common_genesis(
            {
                "schema_version": COMMON_GENESIS_SCHEMA,
                "namespace_receipt_digest": copy_genesis["namespace_receipt_digest"],
                "locator_authority_id": copy_genesis["locator_authority_id"],
                "allocation_id": copy_genesis["allocation_id"],
                "evidence_root_id": copy_genesis["evidence_root_id"],
                "root_basename": copy_genesis["root_basename"],
                "initial_sequence": 0,
                "initial_authority_state": None,
            }
        )

    def _validate_fixed_authority(
        self,
        *,
        namespace_receipt: Mapping[str, object] | None,
        locator_receipt: Mapping[str, object] | None,
        common_genesis: Mapping[str, object] | None,
        copy_a_genesis: Mapping[str, object],
        copy_b_genesis: Mapping[str, object],
    ) -> tuple[JsonObject, JsonObject, JsonObject, JsonObject, JsonObject]:
        self._validate_full_layout()
        physical_namespace = validate_namespace_name_receipt(self._read(_NAMESPACE_FILE))
        physical_locator = validate_locator_name_receipt(
            self._read(f"allocations/{_ALLOCATION}/{_LOCATOR_FILE}")
        )
        copy_a = validate_copy_genesis(self._read(f"copy-a/{_GENESIS_FILE}"))
        copy_b = validate_copy_genesis(self._read(f"copy-b/{_GENESIS_FILE}"))
        if canonical_json_bytes(copy_a) != canonical_json_bytes(
            _json_object(copy_a_genesis)
        ) or canonical_json_bytes(copy_b) != canonical_json_bytes(_json_object(copy_b_genesis)):
            raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
        if namespace_receipt is not None and canonical_json_bytes(
            physical_namespace
        ) != canonical_json_bytes(_json_object(namespace_receipt)):
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
        if locator_receipt is not None and canonical_json_bytes(
            physical_locator
        ) != canonical_json_bytes(_json_object(locator_receipt)):
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
        common = self._common_genesis_from_copy(copy_a)
        if common_genesis is not None and canonical_json_bytes(common) != canonical_json_bytes(
            _json_object(common_genesis)
        ):
            raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
        self._validate_bootstrap_records(
            namespace_receipt=physical_namespace,
            common=common,
            copy_a=copy_a,
            copy_b=copy_b,
            locator=physical_locator,
        )
        common_digest = validate_common_genesis(common)
        if (
            copy_a["common_genesis_digest"] != common_digest
            or copy_b["common_genesis_digest"] != common_digest
            or copy_a["copy_id"] != physical_namespace["copy_a_id"]
            or copy_a["peer_copy_id"] != physical_namespace["copy_b_id"]
            or copy_b["copy_id"] != physical_namespace["copy_b_id"]
            or copy_b["peer_copy_id"] != physical_namespace["copy_a_id"]
            or copy_a["namespace_receipt_digest"] != physical_namespace["receipt_digest"]
            or copy_b["namespace_receipt_digest"] != physical_namespace["receipt_digest"]
            or physical_locator["namespace_receipt_digest"] != physical_namespace["receipt_digest"]
            or physical_locator["locator_authority_id"] != common["locator_authority_id"]
            or physical_locator["allocation_id"] != common["allocation_id"]
            or physical_locator["evidence_root_id"] != common["evidence_root_id"]
            or physical_locator["root_basename"] != common["root_basename"]
            or physical_locator["private_home_handle_id"]
            != physical_namespace["private_home_handle_id"]
            or copy_a["created_at_utc"] != physical_namespace["created_at_utc"]
            or copy_b["created_at_utc"] != physical_namespace["created_at_utc"]
            or physical_locator["allocated_at_utc"] != physical_namespace["created_at_utc"]
        ):
            raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
        return physical_namespace, physical_locator, common, copy_a, copy_b

    @staticmethod
    def _snapshot(
        *,
        copy_genesis: Mapping[str, Json],
        common_digest: str,
        ordered_event_digests: Sequence[str],
        authority_state: Json,
    ) -> JsonObject:
        rows = list(ordered_event_digests)
        return make_semantic_snapshot(
            {
                "schema_version": SNAPSHOT_SCHEMA,
                "namespace_receipt_digest": copy_genesis["namespace_receipt_digest"],
                "locator_authority_id": copy_genesis["locator_authority_id"],
                "allocation_id": copy_genesis["allocation_id"],
                "evidence_root_id": copy_genesis["evidence_root_id"],
                "common_genesis_digest": common_digest,
                "event_count": len(rows),
                "head_event_digest": rows[-1] if rows else common_digest,
                "ordered_event_digests": rows,
                "authority_state": authority_state,
            }
        )

    @staticmethod
    def _validate_event_authority(
        event: Mapping[str, Json],
        *,
        namespace_receipt: Mapping[str, Json],
        locator_receipt: Mapping[str, Json],
        first_event: Mapping[str, Json] | None,
        previous_event: Mapping[str, Json] | None,
    ) -> None:
        if (
            event["namespace_receipt_digest"] != namespace_receipt["receipt_digest"]
            or event["locator_name_receipt_digest"] != locator_receipt["name_receipt_digest"]
            or event["locator_authority_id"] != locator_receipt["locator_authority_id"]
            or event["allocation_id"] != locator_receipt["allocation_id"]
            or event["evidence_root_id"] != locator_receipt["evidence_root_id"]
            or event["root_basename"] != locator_receipt["root_basename"]
            or event["opaque_locator"] != locator_receipt["opaque_locator"]
            or event["locator_digest"] != locator_receipt["locator_digest"]
            or event["accepted_cc08_plan_sha"] != locator_receipt["accepted_cc08_plan_sha"]
            or event["accepted_cc08_plan_tree"] != locator_receipt["accepted_cc08_plan_tree"]
            or event["registry_implementation_sha"]
            != locator_receipt["registry_implementation_sha"]
            or event["registry_implementation_tree"]
            != locator_receipt["registry_implementation_tree"]
            or event["registry_implementation_acceptance_record_digest"]
            != locator_receipt["registry_implementation_acceptance_record_digest"]
            or event["registry_implementation_acceptance_authority_digest"]
            != locator_receipt["registry_implementation_acceptance_authority_digest"]
        ):
            raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
        for key in (
            "namespace_receipt_digest",
            "locator_name_receipt_digest",
            "locator_digest",
            "registry_implementation_acceptance_record_digest",
            "registry_implementation_acceptance_authority_digest",
            "parent_identity_digest",
            "excluded_worktree_set_digest",
        ):
            _digest(event[key], key)
        for key in (
            "root_identity_digest",
            "root_receipt_digest",
            "root_registry_common_genesis_digest",
            "root_registry_copy_a_snapshot_digest",
            "root_registry_copy_b_snapshot_digest",
        ):
            if event[key] is not None:
                _digest(event[key], key)
        for key in (
            "accepted_cc08_plan_sha",
            "accepted_cc08_plan_tree",
            "registry_implementation_sha",
            "registry_implementation_tree",
        ):
            _sha(event[key], key)
        if first_event is not None and any(
            event[key] != first_event[key] for key in _EVENT_FIXED_CONTINUITY_FIELDS
        ):
            raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
        if previous_event is not None and cast(int, event["sequence"]) >= 3:
            if (
                event["root_identity_digest"] != previous_event["root_identity_digest"]
                or event["root_receipt_digest"] != previous_event["root_receipt_digest"]
            ):
                raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")

    def _replay_committed_prefix(
        self,
        *,
        count: int,
        namespace_receipt: Mapping[str, Json],
        locator_receipt: Mapping[str, Json],
        common_digest: str,
        copy_a_genesis: Mapping[str, Json],
        copy_b_genesis: Mapping[str, Json],
    ) -> tuple[JsonObject, set[str], set[str]]:
        event_paths_a = self._event_paths("copy-a")
        event_paths_b = self._event_paths("copy-b")
        if count < 0 or len(event_paths_a) < count or len(event_paths_b) < count:
            raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
        ordered: list[str] = []
        head = common_digest
        state: Json = None
        first_event: JsonObject | None = None
        previous_event: JsonObject | None = None
        expected_intents: set[str] = set()
        expected_commits: set[str] = set()
        for sequence in range(1, count + 1):
            path_a, path_b = event_paths_a[sequence - 1], event_paths_b[sequence - 1]
            raw_a, raw_b = path_a.read_bytes(), path_b.read_bytes()
            if raw_a != raw_b:
                raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
            event = canonical_loads(raw_a)
            if (
                path_a.name != event_filename(sequence, cast(str, event.get("event_digest")))
                or path_b.name != path_a.name
                or event.get("sequence") != sequence
                or event.get("previous_event_digest") != head
            ):
                raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
            tx = cast(str, event["transaction_id"])
            intent_name = intent_filename(tx)
            commit_name = commit_filename(tx)
            intent = self._read(f"transactions/intents/{intent_name}")
            validate_transition(event, intent)
            expected_prior_state = {1: None, 2: "PREPARED", 3: "ROOT_RECEIPT_DURABLE"}.get(sequence)
            if state != expected_prior_state:
                raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
            self._validate_event_authority(
                event,
                namespace_receipt=namespace_receipt,
                locator_receipt=locator_receipt,
                first_event=first_event,
                previous_event=previous_event,
            )
            if first_event is None:
                first_event = event
            ordered.append(cast(str, event["event_digest"]))
            state = event["authority_state"]
            snapshot = self._snapshot(
                copy_genesis=copy_a_genesis,
                common_digest=common_digest,
                ordered_event_digests=ordered,
                authority_state=state,
            )
            commit = validate_commit_receipt(self._read(f"transactions/commits/{commit_name}"))
            if (
                commit["namespace_receipt_digest"] != namespace_receipt["receipt_digest"]
                or commit["locator_name_receipt_digest"] != locator_receipt["name_receipt_digest"]
                or commit["locator_authority_id"] != event["locator_authority_id"]
                or commit["allocation_id"] != event["allocation_id"]
                or commit["evidence_root_id"] != event["evidence_root_id"]
                or commit["transaction_id"] != tx
                or commit["sequence"] != sequence
                or commit["intent_digest"] != intent["intent_digest"]
                or commit["event_digest"] != event["event_digest"]
                or commit["copy_a_genesis_receipt_digest"]
                != copy_a_genesis["genesis_receipt_digest"]
                or commit["copy_b_genesis_receipt_digest"]
                != copy_b_genesis["genesis_receipt_digest"]
                or commit["copy_a_event_file_sha256"] != _sha256(raw_a)
                or commit["copy_b_event_file_sha256"] != _sha256(raw_b)
                or commit["copy_a_snapshot_digest"] != snapshot["semantic_snapshot_digest"]
                or commit["copy_b_snapshot_digest"] != snapshot["semantic_snapshot_digest"]
                or commit["commit_created_at_utc"] != intent["commit_created_at_utc"]
                or commit["commit_created_at_utc"] != event["transition_at_utc"]
            ):
                raise LocatorCustodyError("LOCATOR_COMMIT_PARTIAL_OR_CORRUPT_STOP")
            expected_intents.add(intent_name)
            expected_commits.add(commit_name)
            previous_event = event
            head = cast(str, event["event_digest"])
        return (
            self._snapshot(
                copy_genesis=copy_a_genesis,
                common_digest=common_digest,
                ordered_event_digests=ordered,
                authority_state=state,
            ),
            expected_intents,
            expected_commits,
        )

    def _classify_transition_prefix(
        self,
        *,
        event: Mapping[str, object],
        intent: Mapping[str, object],
        copy_a_genesis: Mapping[str, object],
        copy_b_genesis: Mapping[str, object],
        prior_snapshot: Mapping[str, object],
    ) -> tuple[str, JsonObject, JsonObject, JsonObject, JsonObject, JsonObject]:
        event_value = _json_object(event)
        intent_value = _json_object(intent)
        validate_transition(event_value, intent_value)
        prior = validate_semantic_snapshot(prior_snapshot)
        namespace, locator, common, copy_a, copy_b = self._validate_fixed_authority(
            namespace_receipt=None,
            locator_receipt=None,
            common_genesis=None,
            copy_a_genesis=copy_a_genesis,
            copy_b_genesis=copy_b_genesis,
        )
        common_digest = validate_common_genesis(common)
        sequence = cast(int, event_value["sequence"])
        prior_count = cast(int, prior["event_count"])
        if (
            sequence != prior_count + 1
            or sequence not in {1, 2, 3}
            or event_value["previous_event_digest"] != prior["head_event_digest"]
            or prior["common_genesis_digest"] != common_digest
            or prior["semantic_snapshot_digest"]
            not in {
                intent_value["copy_a_prior_snapshot_digest"],
                intent_value["copy_b_prior_snapshot_digest"],
            }
            or intent_value["copy_a_prior_snapshot_digest"]
            != intent_value["copy_b_prior_snapshot_digest"]
            or prior["authority_state"]
            != {1: None, 2: "PREPARED", 3: "ROOT_RECEIPT_DURABLE"}[sequence]
        ):
            raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
        event_paths_a = self._event_paths("copy-a")
        event_paths_b = self._event_paths("copy-b")
        prior_names = [
            event_filename(index, cast(str, digest_value))
            for index, digest_value in enumerate(
                cast(list[Json], prior["ordered_event_digests"]), 1
            )
        ]
        target_name = event_filename(sequence, cast(str, event_value["event_digest"]))
        if [item.name for item in event_paths_a[:prior_count]] != prior_names or [
            item.name for item in event_paths_b[:prior_count]
        ] != prior_names:
            raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
        if len(event_paths_a) not in {prior_count, prior_count + 1} or len(event_paths_b) not in {
            prior_count,
            prior_count + 1,
        }:
            raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
        target_a = len(event_paths_a) == prior_count + 1
        target_b = len(event_paths_b) == prior_count + 1
        if (target_a and event_paths_a[-1].name != target_name) or (
            target_b and event_paths_b[-1].name != target_name
        ):
            raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
        physical_prior, prior_intents, prior_commits = self._replay_committed_prefix(
            count=prior_count,
            namespace_receipt=namespace,
            locator_receipt=locator,
            common_digest=common_digest,
            copy_a_genesis=copy_a,
            copy_b_genesis=copy_b,
        )
        if physical_prior != prior:
            raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
        first_event = canonical_loads(event_paths_a[0].read_bytes()) if prior_count else event_value
        previous_event = (
            canonical_loads(event_paths_a[prior_count - 1].read_bytes()) if prior_count else None
        )
        self._validate_event_authority(
            event_value,
            namespace_receipt=namespace,
            locator_receipt=locator,
            first_event=first_event,
            previous_event=previous_event,
        )
        tx = cast(str, intent_value["transaction_id"])
        target_intent_name = intent_filename(tx)
        target_commit_name = commit_filename(tx)
        intent_names = self._directory_file_names("transactions/intents")
        commit_names = self._directory_file_names("transactions/commits")
        target_intent = target_intent_name in intent_names
        target_commit = target_commit_name in commit_names
        expected_intents = prior_intents | ({target_intent_name} if target_intent else set())
        expected_commits = prior_commits | ({target_commit_name} if target_commit else set())
        if intent_names != expected_intents or commit_names != expected_commits:
            raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP")
        stages = {
            (False, False, False, False): "EMPTY",
            (True, False, False, False): "INTENT",
            (True, True, False, False): "COPY_A",
            (True, True, True, False): "COPY_B",
            (True, True, True, True): "COMMITTED",
        }
        try:
            stage = stages[(target_intent, target_a, target_b, target_commit)]
        except KeyError as exc:
            raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP") from exc
        raw = _unb64(intent_value["canonical_event_base64url"])
        if target_intent and canonical_json_bytes(
            self._read(f"transactions/intents/{target_intent_name}")
        ) != canonical_json_bytes(intent_value):
            raise LocatorCustodyError("LOCATOR_INTENT_PARTIAL_OR_CORRUPT_STOP")
        if target_a and event_paths_a[-1].read_bytes() != raw:
            raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
        if target_b and event_paths_b[-1].read_bytes() != raw:
            raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
        if stage == "COMMITTED":
            replayed_a, replayed_b = self.replay(
                namespace_receipt=namespace,
                locator_receipt=locator,
                common_genesis=common,
                copy_a_genesis=copy_a,
                copy_b_genesis=copy_b,
            )
            expected_post = self._snapshot(
                copy_genesis=copy_a,
                common_digest=common_digest,
                ordered_event_digests=[
                    *cast(list[str], prior["ordered_event_digests"]),
                    cast(str, event_value["event_digest"]),
                ],
                authority_state=event_value["authority_state"],
            )
            if replayed_a != expected_post or replayed_b != expected_post:
                raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
        return stage, namespace, locator, common, copy_a, copy_b

    def _replay_copy(
        self, copy: str, genesis: Mapping[str, object], common_digest: str
    ) -> JsonObject:
        checked = validate_copy_genesis(genesis)
        if canonical_json_bytes(self._read(f"{copy}/{_GENESIS_FILE}")) != canonical_json_bytes(
            checked
        ):
            raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
        events = sorted(self._path(f"{copy}/events").iterdir(), key=lambda item: item.name)
        digests: list[str] = []
        state: Json = None
        head = common_digest
        root_receipt_timestamp: Json = None
        for sequence, path in enumerate(events, 1):
            event = canonical_loads(path.read_bytes())
            if path.name != event_filename(sequence, cast(str, event.get("event_digest"))):
                raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
            if event.get("sequence") != sequence:
                raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
            if event.get("previous_event_digest") != head:
                raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
            intent = self._read(
                f"transactions/intents/{intent_filename(cast(str, event.get('transaction_id')))}"
            )
            validate_transition(event, intent)
            if sequence == 1:
                root_receipt_timestamp = event["root_receipt_created_at_utc"]
            elif event["root_receipt_created_at_utc"] != root_receipt_timestamp:
                raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
            head = cast(str, event["event_digest"])
            digests.append(head)
            state = event["authority_state"]
        return self._snapshot(
            copy_genesis=checked,
            common_digest=common_digest,
            ordered_event_digests=digests,
            authority_state=state,
        )


def recover_synthetic_transition(
    ledger: SyntheticLocatorCustodyLedger,
    *,
    event: Mapping[str, object],
    intent: Mapping[str, object],
    copy_a_genesis: Mapping[str, object],
    copy_b_genesis: Mapping[str, object],
    prior_snapshot: Mapping[str, object],
    stop_after: str | None = None,
) -> str:
    try:
        with _namespace_scoped_exclusive_guard(ledger.root):
            return _recover_synthetic_transition_unlocked(
                ledger,
                event=event,
                intent=intent,
                copy_a_genesis=copy_a_genesis,
                copy_b_genesis=copy_b_genesis,
                prior_snapshot=prior_snapshot,
                stop_after=stop_after,
            )
    except LocatorCustodyError:
        raise
    except (AttributeError, OSError):
        raise LocatorCustodyError("CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP") from None


def _recover_synthetic_transition_unlocked(
    ledger: SyntheticLocatorCustodyLedger,
    *,
    event: Mapping[str, object],
    intent: Mapping[str, object],
    copy_a_genesis: Mapping[str, object],
    copy_b_genesis: Mapping[str, object],
    prior_snapshot: Mapping[str, object],
    stop_after: str | None = None,
) -> str:
    """Complete one durable prefix using only the intent's frozen event bytes.

    ``stop_after`` is a test crash injection point: INTENT, COPY_A, COPY_B.
    It never manufactures alternative event bytes and never overwrites a stage.
    """
    event_value = _json_object(event)
    intent_value = _json_object(intent)
    prior = validate_semantic_snapshot(prior_snapshot)
    stage, namespace, locator, common, copy_a, copy_b = ledger._classify_transition_prefix(
        event=event_value,
        intent=intent_value,
        copy_a_genesis=copy_a_genesis,
        copy_b_genesis=copy_b_genesis,
        prior_snapshot=prior,
    )
    if stage == "COMMITTED":
        return "COMMIT_DURABLE"
    raw = _unb64(intent_value["canonical_event_base64url"])
    if raw != canonical_json_bytes(event_value):
        raise LocatorCustodyError("LOCATOR_INTENT_PARTIAL_OR_CORRUPT_STOP")
    tx = cast(str, intent_value["transaction_id"])
    intent_path = f"transactions/intents/{intent_filename(tx)}"
    if stage == "EMPTY":
        ledger._write(intent_path, intent_value)
    if stop_after == "INTENT":
        return "INTENT_DURABLE"
    name = event_filename(
        cast(int, event_value["sequence"]), cast(str, event_value["event_digest"])
    )
    common_digest = validate_common_genesis(common)
    expected_post = ledger._snapshot(
        copy_genesis=copy_a,
        common_digest=common_digest,
        ordered_event_digests=[
            *cast(list[str], prior["ordered_event_digests"]),
            cast(str, event_value["event_digest"]),
        ],
        authority_state=event_value["authority_state"],
    )
    if stage in {"EMPTY", "INTENT"}:
        ledger._write(f"copy-a/events/{name}", event_value)
    replayed_a = ledger._replay_copy("copy-a", copy_a, common_digest)
    if replayed_a != expected_post:
        raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
    if stop_after == "COPY_A":
        return "COPY_A_DURABLE"
    if stage in {"EMPTY", "INTENT", "COPY_A"}:
        ledger._write(f"copy-b/events/{name}", event_value)
    replayed_a = ledger._replay_copy("copy-a", copy_a, common_digest)
    replayed_b = ledger._replay_copy("copy-b", copy_b, common_digest)
    if replayed_a != expected_post or replayed_b != expected_post:
        raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
    if stop_after == "COPY_B":
        return "COPY_B_DURABLE"
    commit_path = f"transactions/commits/{commit_filename(tx)}"
    commit_fields = _json_object(
        {
            "schema_version": COMMIT_SCHEMA,
            "namespace_receipt_digest": event_value["namespace_receipt_digest"],
            "locator_name_receipt_digest": event_value["locator_name_receipt_digest"],
            "locator_authority_id": event_value["locator_authority_id"],
            "allocation_id": event_value["allocation_id"],
            "evidence_root_id": event_value["evidence_root_id"],
            "transaction_id": tx,
            "sequence": event_value["sequence"],
            "intent_digest": intent_value["intent_digest"],
            "event_digest": event_value["event_digest"],
            "copy_a_genesis_receipt_digest": copy_a["genesis_receipt_digest"],
            "copy_b_genesis_receipt_digest": copy_b["genesis_receipt_digest"],
            "copy_a_event_file_sha256": _sha256(raw),
            "copy_b_event_file_sha256": _sha256(raw),
            "copy_a_snapshot_digest": expected_post["semantic_snapshot_digest"],
            "copy_b_snapshot_digest": expected_post["semantic_snapshot_digest"],
            "commit_created_at_utc": intent_value["commit_created_at_utc"],
        }
    )
    commit = make_commit_receipt(commit_fields)
    if ledger._path(commit_path).exists():
        raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
    ledger._write(commit_path, commit)
    final_a, final_b = ledger.replay(
        namespace_receipt=namespace,
        locator_receipt=locator,
        common_genesis=common,
        copy_a_genesis=copy_a,
        copy_b_genesis=copy_b,
    )
    if final_a != expected_post or final_b != expected_post:
        raise LocatorCustodyError("LOCATOR_COPY_DIVERGENCE_STOP")
    return "COMMIT_DURABLE"
