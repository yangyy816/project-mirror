from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast

import pytest

from mirror_api import demo_d02_r2_locator_custody as custody
from mirror_api.demo_measurement_quality import canonical_json_bytes

R06_SOURCE_SHA256 = "72fd639da11a80b5a5b6f4d19c2a45ddd03d5c1b740518c22ac26a3e98c5239e"
R06_HARDEN_SCRIPT_SHA256 = "c68c2dd675def9cccaa6786132954897c910e36b63eb4e65e151432121c75a94"
R06_VALIDATE_SCRIPT_SHA256 = "3f06a66b3edbc36c6762cf414d4c402e33155b7133f95bc5d5415e2fb242a7a0"


def digest(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def test_schema_contract_is_closed_and_has_exact_manifest() -> None:
    assert len(custody.ORDERED_SCHEMA_VERSIONS) == 42
    assert len(set(custody.ORDERED_SCHEMA_VERSIONS)) == 42
    assert len(custody.RELATIVE_CONTROL_MANIFEST) == 8
    assert custody.schema_contract_digest() == custody.typed_digest(
        custody.SCHEMA_CONTRACT, custody.schema_contract_payload()
    )


def test_canonical_loader_rejects_duplicate_noncanonical_and_nonfinite() -> None:
    with pytest.raises(custody.LocatorCustodyError):
        custody.canonical_loads(b'{"a":1,"a":2}')
    with pytest.raises(custody.LocatorCustodyError):
        custody.canonical_loads(b'{"a": 1}')
    with pytest.raises(custody.LocatorCustodyError):
        custody.canonical_loads(b'{"a":NaN}')


def test_synthetic_store_is_create_new_and_never_accepts_path_traversal(tmp_path: Path) -> None:
    store = custody.SyntheticCustodyStore(tmp_path)
    record = {"schema_version": "mirror.example/v1", "value": "x"}
    store.create_immutable("receipt.json", record)
    assert store.replay("receipt.json") == record
    with pytest.raises(custody.LocatorCustodyError):
        store.create_immutable("receipt.json", record)
    with pytest.raises(custody.LocatorCustodyError):
        store.create_immutable("../escape.json", record)


@pytest.mark.parametrize(
    "sequence,state", [(1, "PREPARED"), (2, "ROOT_RECEIPT_DURABLE"), (3, "ROOT_REGISTRY_READY")]
)
def test_three_transition_intents_round_trip(sequence: int, state: str) -> None:
    root_fields = {
        "accepted_cc08_plan_sha": "a" * 40,
        "accepted_cc08_plan_tree": "b" * 40,
        "registry_implementation_sha": "c" * 40,
        "registry_implementation_tree": "d" * 40,
        "registry_implementation_acceptance_record_digest": digest("r"),
        "registry_implementation_acceptance_authority_digest": digest("a"),
        "parent_identity_digest": digest("parent"),
        "excluded_worktree_set_digest": digest("worktree"),
        "root_identity_digest": None if sequence == 1 else digest("root"),
        "root_receipt_digest": None if sequence == 1 else digest("receipt"),
        "root_registry_state": None
        if sequence == 1
        else ("NOT_INITIALIZED" if sequence == 2 else "READY_EMPTY"),
        "root_registry_common_genesis_digest": None if sequence < 3 else digest("genesis"),
        "root_registry_copy_a_snapshot_digest": None if sequence < 3 else digest("snap-a"),
        "root_registry_copy_b_snapshot_digest": None if sequence < 3 else digest("snap-b"),
    }
    event, intent = custody.make_transaction(
        namespace_receipt_digest=digest("namespace"),
        locator_name_receipt_digest=digest("locator"),
        locator_authority_id="AUTH",
        allocation_id="ALLOC",
        evidence_root_id="ROOT",
        root_basename="root",
        opaque_locator="pmhome1:YWJj",
        locator_digest=digest("opaque"),
        sequence=sequence,
        previous_event_digest=digest(f"previous-{sequence}"),
        decision="CREATE_NEW" if sequence == 1 else "RECOVER_EXISTING",
        authority_state=state,
        transition_at_utc="2026-08-28T00:00:00.000001Z",
        root_receipt_created_at_utc="2026-08-28T00:00:00.000001Z",
        root_fields=root_fields,
        copy_a_prior_snapshot_digest=digest("a"),
        copy_b_prior_snapshot_digest=digest("b"),
    )
    custody.validate_transition(event, intent)
    event["decision"] = "UNKNOWN"
    transaction = {
        key: event[key]
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
    event["transaction_id"] = custody.typed_digest(custody.TRANSACTION_ID_SCHEMA, transaction)
    event["event_digest"] = custody.typed_digest(
        custody.EVENT_SCHEMA, {key: value for key, value in event.items() if key != "event_digest"}
    )
    raw = canonical_json_bytes(event)
    intent.update(
        {
            "transaction_id": event["transaction_id"],
            "decision": "UNKNOWN",
            "event_digest": event["event_digest"],
            "canonical_event_base64url": custody._b64(raw),
            "canonical_event_sha256": digest(raw.decode()),
        }
    )
    intent["canonical_event_sha256"] = hashlib.sha256(raw).hexdigest()
    intent["intent_digest"] = custody.typed_digest(
        custody.INTENT_SCHEMA,
        {key: value for key, value in intent.items() if key != "intent_digest"},
    )
    with pytest.raises(custody.LocatorCustodyError, match="LOCATOR_COPY_DIVERGENCE_STOP"):
        custody.validate_transition(event, intent)
    intent["event_digest"] = digest("tampered")
    with pytest.raises(custody.LocatorCustodyError):
        custody.validate_transition(event, intent)


def test_binary_frame_is_exact_and_has_no_text_assumption() -> None:
    payload = "根\n目录".encode()
    assert custody.read_single_binary_frame(len(payload).to_bytes(4, "big") + payload) == payload
    with pytest.raises(custody.LocatorCustodyError):
        custody.read_single_binary_frame((1).to_bytes(4, "big"))
    with pytest.raises(custody.LocatorCustodyError):
        custody.read_single_binary_frame((1).to_bytes(4, "big") + b"ab")


def test_read_only_host_projection_has_no_fallback_or_locator() -> None:
    expected = custody.ReadOnlyHostProjection(
        *(digest(value) for value in ("sid", "known", "home", "resolver"))
    )
    assert custody.project_host(lambda: expected) == expected
    with pytest.raises(custody.LocatorCustodyError):
        custody.project_host(
            lambda: custody.ReadOnlyHostProjection("bad", digest("k"), digest("h"), digest("r"))
        )


@pytest.mark.parametrize(
    ("stage", "action"),
    [
        (custody.RehomeStage(True, False, False, False, False, False, False), "CREATE_OUTPUT"),
        (
            custody.RehomeStage(True, True, True, True, True, False, False),
            "REPLAY_COPY_A_CREATE_COPY_B_AND_COMPARE",
        ),
        (custody.RehomeStage(True, True, True, True, True, True, True), "FULL_REPLAY_NO_WRITE"),
    ],
)
def test_r05_restart_ladder_only_accepts_durable_prefixes(
    stage: custody.RehomeStage, action: str
) -> None:
    assert custody.r05_recovery_action(stage) == action
    with pytest.raises(custody.LocatorCustodyError):
        custody.r05_recovery_action(custody.RehomeStage(True, True, True, True, False, True, False))


def test_windows_identity_and_native_create_are_handle_bound_and_fail_closed() -> None:
    sid = custody.validate_windows_principal_sid({"sid_string": "S-1-5-21-7"})
    assert len(sid) == 64
    preimage = {
        "volume_serial_number_hex": "0" * 16,
        "file_id_128_hex": "1" * 32,
        "file_size": 0,
        "file_sha256": digest("file"),
    }
    assert len(custody.validate_windows_file_identity(preimage, executable=False)) == 64
    with pytest.raises(custody.LocatorCustodyError):
        custody.validate_windows_file_identity({**preimage, "file_size": True}, executable=False)
    custody.validate_native_create_request(
        {
            "parent_handle_id": "opaque",
            "component": "child",
            "disposition": "FILE_CREATE",
            "object_attributes_flags": "OBJ_CASE_INSENSITIVE|OBJ_DONT_REPARSE",
            "parent_flushed": True,
        }
    )
    with pytest.raises(custody.LocatorCustodyError):
        custody.validate_native_create_request(
            {
                "parent_handle_id": "opaque",
                "component": "child:ads",
                "disposition": "FILE_OPEN",
                "object_attributes_flags": "",
                "parent_flushed": False,
            }
        )


def test_windows_path_acl_and_known_folder_adversaries_stop() -> None:
    payload = {
        "schema_version": custody.PATH_IDENTITY_SCHEMA,
        "path_role": "KNOWN_FOLDER",
        "volume_serial_number_hex": "0" * 16,
        "file_id_128_hex": "1" * 32,
        "file_attributes_hex": "00000010",
        "reparse_tag_hex": "00000000",
        "is_directory": True,
    }
    payload["identity_digest"] = custody.typed_digest(custody.PATH_IDENTITY_SCHEMA, payload)
    assert custody.validate_windows_path_identity(payload) == payload["identity_digest"]
    payload["reparse_tag_hex"] = "00000001"
    with pytest.raises(custody.LocatorCustodyError):
        custody.validate_windows_path_identity(payload)
    custody.validate_restricted_acl(
        {
            "owner_sid": "S-1-5-21-7",
            "null_dacl": False,
            "access_check": True,
            "generic_mapping_applied": True,
            "aces": [
                {
                    "type": "ALLOW",
                    "sid": "S-1-5-21-7",
                    "flags": [],
                    "mapped_rights": ["GENERIC_WRITE"],
                }
            ],
        },
        "S-1-5-21-7",
    )
    with pytest.raises(custody.LocatorCustodyError):
        custody.validate_restricted_acl(
            {
                "owner_sid": "S-1-5-21-7",
                "null_dacl": False,
                "access_check": True,
                "generic_mapping_applied": True,
                "aces": [
                    {"type": "ALLOW", "sid": "OTHER", "flags": [], "mapped_rights": ["DELETE"]}
                ],
            },
            "S-1-5-21-7",
        )
    good = {
        "local_appdata": "same-handle",
        "profile_local": "same-handle",
        "fixed_volume": True,
        "namespace": "DOS",
        "cloud": False,
        "onedrive_accounts": [],
        "free_bytes": 42_949_672_960,
        "candidate_worktree_identity_digest": digest("candidate-worktree"),
        "ordered_worktree_identity_digests": [],
    }
    custody.validate_known_folder_boundary(good)
    with pytest.raises(custody.LocatorCustodyError):
        custody.validate_known_folder_boundary({**good, "namespace": "UNC"})
    with pytest.raises(custody.LocatorCustodyError):
        custody.validate_known_folder_boundary(
            {
                **good,
                "onedrive_accounts": [
                    {
                        "account_name": "personal",
                        "value_type": "REG_EXPAND_SZ",
                        "path": "C:\\OneDrive",
                        "path_valid": True,
                        "fixed_volume": True,
                        "cloud": False,
                        "reparse": False,
                        "overlaps_project": False,
                    }
                ],
            }
        )


def _resign(schema: str, record: dict[str, object]) -> dict[str, object]:
    key = {
        custody.PATH_IDENTITY_SCHEMA: "identity_digest",
        custody.PS_MANIFEST_SCHEMA: "projection_digest",
        custody.PS_CMDLET_SCHEMA: "projection_digest",
        custody.PS_SCRIPT_SCHEMA: "projection_digest",
        custody.PS_RUNTIME_SCHEMA: "runtime_projection_digest",
        custody.PS_CLOSURE_SCHEMA: "closure_digest",
    }.get(schema)
    if key is not None:
        record[key] = custody.typed_digest(
            schema, {name: value for name, value in record.items() if name != key}
        )
    return record


def _wire_records() -> dict[str, dict[str, object]]:
    d = digest
    security_member = {
        "member_role": "SECURITY_NESTED_BINARY",
        "relative_name": "Microsoft.PowerShell.Security.dll",
        "member_kind": "PE_DLL",
        "member_identity_schema_version": custody.EXECUTABLE_SCHEMA,
        "member_identity_digest": d("security-member"),
        "file_sha256": d("security-member-bytes"),
    }
    utility_binary = {
        "member_role": "UTILITY_NESTED_BINARY",
        "relative_name": "Microsoft.PowerShell.Commands.Utility.dll",
        "member_kind": "PE_DLL",
        "member_identity_schema_version": custody.EXECUTABLE_SCHEMA,
        "member_identity_digest": d("utility-binary"),
        "file_sha256": d("utility-binary-bytes"),
    }
    utility_script = {
        "member_role": "UTILITY_NESTED_SCRIPT",
        "relative_name": "Microsoft.PowerShell.Utility.psm1",
        "member_kind": "POWERSHELL_MODULE_SCRIPT",
        "member_identity_schema_version": custody.FILE_SCHEMA,
        "member_identity_digest": d("utility-script"),
        "file_sha256": d("utility-script-bytes"),
    }
    manifest = _resign(
        custody.PS_MANIFEST_SCHEMA,
        {
            "schema_version": custody.PS_MANIFEST_SCHEMA,
            "windows_directory_identity_digest": d("windows"),
            "windows_system_directory_identity_digest": d("system"),
            "module_root_directory_identity_digest": d("modules"),
            "security_manifest_file_identity_digest": d("security-manifest"),
            "security_manifest_file_sha256": d("security-manifest-bytes"),
            "security_guid": "A94C8C7E-9810-47C0-B8AF-65089C13A35A",
            "security_module_version": "3.0.0.0",
            "security_root_module_state": "ABSENT",
            "security_required_modules": [],
            "security_scripts_to_process": [],
            "security_types_to_process": [],
            "security_formats_to_process": [],
            "security_nested_members": [security_member],
            "utility_manifest_file_identity_digest": d("utility-manifest"),
            "utility_manifest_file_sha256": d("utility-manifest-bytes"),
            "utility_guid": "1DA87E53-152B-403E-98DC-74D7B4D63D59",
            "utility_module_version": "3.1.0.0",
            "utility_root_module_state": "ABSENT",
            "utility_required_modules": [],
            "utility_scripts_to_process": [],
            "utility_types_to_process": [],
            "utility_formats_to_process": [],
            "utility_nested_members": [utility_binary, utility_script],
        },
    )
    cmdlets = _resign(
        custody.PS_CMDLET_SCHEMA,
        {
            "schema_version": custody.PS_CMDLET_SCHEMA,
            "module_manifest_projection_digest": manifest["projection_digest"],
            "ordered_command_rows": [
                {
                    "command_name": "Get-Acl",
                    "command_type": "Cmdlet",
                    "module_name": "Microsoft.PowerShell.Security",
                    "module_guid": "A94C8C7E-9810-47C0-B8AF-65089C13A35A",
                    "module_version": "3.0.0.0",
                    "implementing_type_name": "Microsoft.PowerShell.Commands.GetAclCommand",
                    "implementing_member_role": "SECURITY_NESTED_BINARY",
                    "implementing_member_identity_digest": security_member[
                        "member_identity_digest"
                    ],
                },
                {
                    "command_name": "Set-Acl",
                    "command_type": "Cmdlet",
                    "module_name": "Microsoft.PowerShell.Security",
                    "module_guid": "A94C8C7E-9810-47C0-B8AF-65089C13A35A",
                    "module_version": "3.0.0.0",
                    "implementing_type_name": "Microsoft.PowerShell.Commands.SetAclCommand",
                    "implementing_member_role": "SECURITY_NESTED_BINARY",
                    "implementing_member_identity_digest": security_member[
                        "member_identity_digest"
                    ],
                },
                {
                    "command_name": "ConvertTo-Json",
                    "command_type": "Cmdlet",
                    "module_name": "Microsoft.PowerShell.Utility",
                    "module_guid": "1DA87E53-152B-403E-98DC-74D7B4D63D59",
                    "module_version": "3.1.0.0",
                    "implementing_type_name": "Microsoft.PowerShell.Commands.ConvertToJsonCommand",
                    "implementing_member_role": "UTILITY_NESTED_BINARY",
                    "implementing_member_identity_digest": utility_binary["member_identity_digest"],
                },
            ],
        },
    )
    scripts = _resign(
        custody.PS_SCRIPT_SCHEMA,
        {
            "schema_version": custody.PS_SCRIPT_SCHEMA,
            "accepted_cc09_implementation_sha": "a" * 40,
            "accepted_r06_source_file_sha256": R06_SOURCE_SHA256,
            "extraction_rule": "PYTHON_AST_EXACT_FUNCTION_LOCAL_STRING_CONSTANT_ASSIGNMENT_V1",
            "ordered_script_rows": [
                {
                    "script_role": "CC09_MODULE_MANIFEST_PREFLIGHT_SCRIPT",
                    "source_role": "CC09_LOCATOR_CUSTODY_IMPLEMENTATION_SOURCE",
                    "source_file_sha256": d("cc09-source"),
                    "function_name": "_project_powershell_module_manifest_preflight",
                    "assignment_target": "script",
                    "strict_utf8_script_sha256": d("manifest-script"),
                },
                {
                    "script_role": "CC09_MODULE_RUNTIME_PROJECTION_SCRIPT",
                    "source_role": "CC09_LOCATOR_CUSTODY_IMPLEMENTATION_SOURCE",
                    "source_file_sha256": d("cc09-source"),
                    "function_name": "_project_powershell_acl_runtime_projection",
                    "assignment_target": "script",
                    "strict_utf8_script_sha256": d("runtime-script"),
                },
                {
                    "script_role": "R06_HARDEN_NEW_ROOT_SCRIPT",
                    "source_role": "ACCEPTED_R06_PRIVATE_REGISTRY_SOURCE",
                    "source_file_sha256": R06_SOURCE_SHA256,
                    "function_name": "_harden_new_root_access_boundary",
                    "assignment_target": "script",
                    "strict_utf8_script_sha256": R06_HARDEN_SCRIPT_SHA256,
                },
                {
                    "script_role": "R06_VALIDATE_RESTRICTED_ACL_SCRIPT",
                    "source_role": "ACCEPTED_R06_PRIVATE_REGISTRY_SOURCE",
                    "source_file_sha256": R06_SOURCE_SHA256,
                    "function_name": "_validate_windows_restricted_acl",
                    "assignment_target": "script",
                    "strict_utf8_script_sha256": R06_VALIDATE_SCRIPT_SHA256,
                },
            ],
        },
    )
    runtime = _resign(
        custody.PS_RUNTIME_SCHEMA,
        {
            "schema_version": custody.PS_RUNTIME_SCHEMA,
            "powershell_executable_identity_digest": d("powershell"),
            "powershell_version": "5.1.22621.1",
            "windows_directory_identity_digest": manifest["windows_directory_identity_digest"],
            "windows_system_directory_identity_digest": manifest[
                "windows_system_directory_identity_digest"
            ],
            "module_root_directory_identity_digest": manifest[
                "module_root_directory_identity_digest"
            ],
            "module_manifest_projection_digest": manifest["projection_digest"],
            "required_cmdlet_projection_digest": cmdlets["projection_digest"],
            "acl_bootstrap_script_projection_digest": scripts["projection_digest"],
            "ordered_loaded_member_identity_digests": [
                security_member["member_identity_digest"],
                utility_binary["member_identity_digest"],
                utility_script["member_identity_digest"],
            ],
        },
    )
    closure = _resign(
        custody.PS_CLOSURE_SCHEMA,
        {
            "powershell_executable_identity_digest": runtime[
                "powershell_executable_identity_digest"
            ],
            "windows_directory_identity_digest": manifest["windows_directory_identity_digest"],
            "windows_system_directory_identity_digest": manifest[
                "windows_system_directory_identity_digest"
            ],
            "module_root_directory_identity_digest": manifest[
                "module_root_directory_identity_digest"
            ],
            "module_manifest_projection_digest": manifest["projection_digest"],
            "required_cmdlet_projection_digest": cmdlets["projection_digest"],
            "acl_bootstrap_script_projection_digest": scripts["projection_digest"],
            "runtime_projection_digest": runtime["runtime_projection_digest"],
        },
    )
    path = _resign(
        custody.PATH_IDENTITY_SCHEMA,
        {
            "schema_version": custody.PATH_IDENTITY_SCHEMA,
            "path_role": "KNOWN_FOLDER",
            "volume_serial_number_hex": "0" * 16,
            "file_id_128_hex": "1" * 32,
            "file_attributes_hex": "00000010",
            "reparse_tag_hex": "00000000",
            "is_directory": True,
        },
    )
    return {
        custody.SID_SCHEMA: {"sid_string": "S-1-5-21-7"},
        custody.EXECUTABLE_SCHEMA: {
            "volume_serial_number_hex": "0" * 16,
            "file_id_128_hex": "1" * 32,
            "file_size": 0,
            "file_sha256": d("exe"),
            "product_name": "PowerShell",
            "product_version": "5.1",
            "machine_type": "AMD64",
        },
        custody.FILE_SCHEMA: {
            "volume_serial_number_hex": "0" * 16,
            "file_id_128_hex": "1" * 32,
            "file_size": 0,
            "file_sha256": d("file"),
        },
        custody.PATH_IDENTITY_SCHEMA: path,
        custody.NATIVE_CREATE_SCHEMA: dict(custody._NATIVE_CREATE_CONTRACT),
        custody.PROTECTED_DACL_SCHEMA: dict(custody._PROTECTED_DACL_CONTRACT),
        custody.RESTRICTED_ACL_SCHEMA: dict(custody._RESTRICTED_ACL_CONTRACT),
        custody.KNOWN_FOLDER_SCHEMA: {
            **custody._KNOWN_FOLDER_CONTRACT_LITERALS,
            "ancestor_acl_contract_digest": d("acl-contract"),
        },
        custody.RESOLVER_SCHEMA: {
            **custody._RESOLVER_CONTRACT_LITERALS,
            "known_folder_boundary_contract_digest": d("known-contract"),
            "restricted_ancestor_acl_contract_digest": d("acl-contract"),
        },
        custody.PS_MANIFEST_SCHEMA: manifest,
        custody.PS_CMDLET_SCHEMA: cmdlets,
        custody.PS_SCRIPT_SCHEMA: scripts,
        custody.PS_RUNTIME_SCHEMA: runtime,
        custody.PS_CLOSURE_SCHEMA: closure,
    }


def test_all_fourteen_windows_wire_schemas_have_one_exact_field_authority() -> None:
    records = _wire_records()
    assert set(custody.WINDOWS_WIRE_SCHEMA_FIELDS) == set(records)
    for schema, fields in custody.WINDOWS_WIRE_SCHEMA_FIELDS.items():
        assert set(records[schema]) == set(fields)
        assert len(fields) == len(set(fields))
        result = custody.validate_windows_wire_schema(schema, records[schema])
        self_digest_key = {
            custody.PATH_IDENTITY_SCHEMA: "identity_digest",
            custody.PS_MANIFEST_SCHEMA: "projection_digest",
            custody.PS_CMDLET_SCHEMA: "projection_digest",
            custody.PS_SCRIPT_SCHEMA: "projection_digest",
            custody.PS_RUNTIME_SCHEMA: "runtime_projection_digest",
            custody.PS_CLOSURE_SCHEMA: "closure_digest",
        }.get(schema)
        assert result == custody.typed_digest(
            schema,
            {key: value for key, value in records[schema].items() if key != self_digest_key},
        )


@pytest.mark.parametrize("attack", ["missing", "extra", "wrong_type", "stale_digest"])
def test_all_fourteen_wire_schemas_reject_exact_shape_and_digest_adversaries(attack: str) -> None:
    for schema, good in _wire_records().items():
        bad = dict(good)
        if attack == "missing":
            del bad[next(iter(bad))]
            expected_code = "CUSTODY_EXACT_KEY_STOP"
        elif attack == "extra":
            bad["unexpected"] = "x"
            expected_code = "CUSTODY_EXACT_KEY_STOP"
        elif attack == "wrong_type":
            field = next(iter(bad))
            bad[field] = 1
            _resign(schema, bad)
            expected_code = {
                custody.SID_SCHEMA: "WINDOWS_PRINCIPAL_SID_CHANGED_STOP",
                custody.EXECUTABLE_SCHEMA: "KNOWN_FOLDER_IDENTITY_CHANGED_STOP",
                custody.FILE_SCHEMA: "KNOWN_FOLDER_IDENTITY_CHANGED_STOP",
                custody.PATH_IDENTITY_SCHEMA: "KNOWN_FOLDER_IDENTITY_CHANGED_STOP",
                custody.NATIVE_CREATE_SCHEMA: "WINDOWS_CONTRACT_PROJECTION_MISMATCH_STOP",
                custody.PROTECTED_DACL_SCHEMA: "WINDOWS_CONTRACT_PROJECTION_MISMATCH_STOP",
                custody.RESTRICTED_ACL_SCHEMA: "WINDOWS_CONTRACT_PROJECTION_MISMATCH_STOP",
                custody.KNOWN_FOLDER_SCHEMA: "WINDOWS_CONTRACT_PROJECTION_MISMATCH_STOP",
                custody.RESOLVER_SCHEMA: "WINDOWS_CONTRACT_PROJECTION_MISMATCH_STOP",
                custody.PS_MANIFEST_SCHEMA: "POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP",
                custody.PS_CMDLET_SCHEMA: "POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP",
                custody.PS_SCRIPT_SCHEMA: "POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP",
                custody.PS_RUNTIME_SCHEMA: "POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP",
                custody.PS_CLOSURE_SCHEMA: "CUSTODY_DIGEST_GRAMMAR_STOP",
            }[schema]
        elif schema in {
            custody.PATH_IDENTITY_SCHEMA,
            custody.PS_MANIFEST_SCHEMA,
            custody.PS_CMDLET_SCHEMA,
            custody.PS_SCRIPT_SCHEMA,
            custody.PS_RUNTIME_SCHEMA,
            custody.PS_CLOSURE_SCHEMA,
        }:
            key = {
                custody.PATH_IDENTITY_SCHEMA: "identity_digest",
                custody.PS_RUNTIME_SCHEMA: "runtime_projection_digest",
                custody.PS_CLOSURE_SCHEMA: "closure_digest",
            }.get(schema, "projection_digest")
            bad[key] = digest("stale")
            expected_code = (
                "KNOWN_FOLDER_IDENTITY_CHANGED_STOP"
                if schema == custody.PATH_IDENTITY_SCHEMA
                else "POWERSHELL_ACL_MODULE_CLOSURE_UNPROVEN_STOP"
                if schema == custody.PS_CLOSURE_SCHEMA
                else "POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP"
            )
        else:
            # Private preimage and contract domains deliberately carry no
            # self-digest. Their typed digest is recomputed at this boundary.
            assert custody.validate_windows_wire_schema(schema, bad) == custody.typed_digest(
                schema, bad
            )
            continue
        with pytest.raises(custody.LocatorCustodyError) as error:
            custody.validate_windows_wire_schema(schema, bad)
        assert error.value.code == expected_code


def test_powershell_cross_projection_rejects_resigned_order_and_nullable_attacks() -> None:
    records = _wire_records()
    custody.validate_powershell_closure(
        records[custody.PS_MANIFEST_SCHEMA],
        records[custody.PS_CMDLET_SCHEMA],
        records[custody.PS_SCRIPT_SCHEMA],
        records[custody.PS_RUNTIME_SCHEMA],
        records[custody.PS_CLOSURE_SCHEMA],
    )
    runtime = dict(records[custody.PS_RUNTIME_SCHEMA])
    loaded_member_identity_digests = runtime["ordered_loaded_member_identity_digests"]
    assert isinstance(loaded_member_identity_digests, list)
    runtime["ordered_loaded_member_identity_digests"] = list(
        reversed(loaded_member_identity_digests)
    )
    _resign(custody.PS_RUNTIME_SCHEMA, runtime)
    closure = dict(records[custody.PS_CLOSURE_SCHEMA])
    closure["runtime_projection_digest"] = runtime["runtime_projection_digest"]
    _resign(custody.PS_CLOSURE_SCHEMA, closure)
    with pytest.raises(
        custody.LocatorCustodyError, match="POWERSHELL_RUNTIME_PROJECTION_MISMATCH_STOP"
    ):
        custody.validate_powershell_closure(
            records[custody.PS_MANIFEST_SCHEMA],
            records[custody.PS_CMDLET_SCHEMA],
            records[custody.PS_SCRIPT_SCHEMA],
            runtime,
            closure,
        )
    manifest = dict(records[custody.PS_MANIFEST_SCHEMA])
    manifest["security_required_modules"] = None
    _resign(custody.PS_MANIFEST_SCHEMA, manifest)
    with pytest.raises(
        custody.LocatorCustodyError, match="POWERSHELL_MANIFEST_PROJECTION_MISMATCH_STOP"
    ):
        custody.validate_powershell_module_manifest_projection(manifest)


def _native_create_observation(*, child_kind: str = "DIRECTORY") -> dict[str, object]:
    return {
        "parent_handle_id": "opaque-parent",
        "component": "child",
        "disposition": "FILE_CREATE",
        "object_attributes_flags": "OBJ_CASE_INSENSITIVE|OBJ_DONT_REPARSE",
        "parent_flushed": True,
        "native_binding_available": True,
        "parent_no_delete_share": True,
        "parent_identity_matches": True,
        "parent_dacl_matches": True,
        "creation_time_protected_dacl": True,
        "child_kind": child_kind,
        "child_reparse": False,
        "child_identity_matches": True,
        "child_dacl_matches": True,
        "file_write_complete": True,
        "file_flush_success": True,
        "parent_flush_success": True,
        "reopen_identity_matches": True,
        "reopen_dacl_matches": True,
    }


def test_native_create_model_gates_before_write_and_preserves_undurable_stage() -> None:
    adapter = custody.SyntheticNativeCreateAdapter()
    adapter.create(_native_create_observation())
    assert adapter.writes == ["child"]
    assert adapter.durable_components == ["child"]
    file_adapter = custody.SyntheticNativeCreateAdapter()
    file_adapter.create(_native_create_observation(child_kind="FILE"))
    assert file_adapter.durable_components == ["child"]
    for gate in (
        "native_binding_available",
        "parent_no_delete_share",
        "parent_identity_matches",
        "parent_dacl_matches",
        "creation_time_protected_dacl",
    ):
        blocked = custody.SyntheticNativeCreateAdapter()
        with pytest.raises(custody.LocatorCustodyError) as error:
            blocked.create({**_native_create_observation(), gate: False})
        assert error.value.code == "HANDLE_RELATIVE_CREATION_UNAVAILABLE_STOP"
        assert blocked.writes == []
        assert blocked.durable_components == []
    for failure in (
        "child_reparse",
        "child_identity_matches",
        "child_dacl_matches",
        "parent_flush_success",
    ):
        preserved = custody.SyntheticNativeCreateAdapter()
        with pytest.raises(custody.LocatorCustodyError) as error:
            preserved.create(
                {
                    **_native_create_observation(),
                    failure: True if failure == "child_reparse" else False,
                }
            )
        assert error.value.code == "CUSTODY_DURABILITY_BARRIER_FAILED_STOP"
        assert preserved.writes == ["child"]
        assert preserved.durable_components == []
    reopened = custody.SyntheticNativeCreateAdapter()
    with pytest.raises(custody.LocatorCustodyError) as error:
        reopened.create({**_native_create_observation(), "reopen_identity_matches": False})
    assert error.value.code == "CUSTODY_PARENT_IDENTITY_CHANGED_STOP"
    assert reopened.writes == ["child"]
    assert reopened.durable_components == []
    file_flush = custody.SyntheticNativeCreateAdapter()
    with pytest.raises(custody.LocatorCustodyError) as error:
        file_flush.create(
            {**_native_create_observation(child_kind="FILE"), "file_flush_success": False}
        )
    assert error.value.code == "CUSTODY_DURABILITY_BARRIER_FAILED_STOP"
    assert file_flush.writes == ["child"]
    assert file_flush.durable_components == []


@pytest.mark.parametrize("component", ["child:ads", "a/b", "a\\b", ".", ".."])
def test_native_create_rejects_non_component_before_mutation(component: str) -> None:
    adapter = custody.SyntheticNativeCreateAdapter()
    with pytest.raises(custody.LocatorCustodyError) as error:
        adapter.create({**_native_create_observation(child_kind="FILE"), "component": component})
    assert error.value.code == "HANDLE_RELATIVE_CREATION_UNAVAILABLE_STOP"
    assert adapter.writes == []


def test_native_create_rejects_non_file_create_before_mutation() -> None:
    adapter = custody.SyntheticNativeCreateAdapter()
    with pytest.raises(custody.LocatorCustodyError) as error:
        adapter.create({**_native_create_observation(), "disposition": "FILE_OPEN"})
    assert error.value.code == "CUSTODY_DURABILITY_BARRIER_FAILED_STOP"
    assert adapter.writes == []


def test_same_open_handle_acl_and_known_folder_adversaries_are_fail_closed() -> None:
    path = _wire_records()[custody.PATH_IDENTITY_SCHEMA]
    assert (
        custody.validate_same_open_handle_path_identity(path, path, role="KNOWN_FOLDER")
        == path["identity_digest"]
    )
    swapped_path = dict(path)
    swapped_path["file_id_128_hex"] = "2" * 32
    _resign(custody.PATH_IDENTITY_SCHEMA, swapped_path)
    with pytest.raises(custody.LocatorCustodyError) as error:
        custody.validate_same_open_handle_path_identity(path, swapped_path, role="KNOWN_FOLDER")
    assert error.value.code == "CUSTODY_PARENT_IDENTITY_CHANGED_STOP"

    good_acl = {
        "owner_sid": "S-1-5-21-7",
        "null_dacl": False,
        "access_check": True,
        "generic_mapping_applied": True,
        "aces": [
            {"type": "ALLOW", "sid": "S-1-5-21-7", "flags": [], "mapped_rights": ["GENERIC_WRITE"]},
            {
                "type": "ALLOW",
                "sid": "S-1-5-99",
                "flags": ["INHERIT_ONLY"],
                "mapped_rights": ["DELETE"],
            },
        ],
    }
    custody.validate_restricted_acl(good_acl, "S-1-5-21-7")
    attacks = (
        {"owner_sid": "S-1-5-21-8"},
        {"null_dacl": True},
        {"access_check": False},
        {"generic_mapping_applied": False},
        {"aces": [{"type": "UNKNOWN", "sid": "S-1-5-21-7", "flags": [], "mapped_rights": []}]},
        {"aces": [{"type": "ALLOW", "sid": "not-a-sid", "flags": [], "mapped_rights": []}]},
        {"aces": [{"type": "ALLOW", "sid": "S-1-5-99", "flags": ["UNKNOWN"], "mapped_rights": []}]},
        {"aces": [{"type": "ALLOW", "sid": "S-1-5-99", "flags": [], "mapped_rights": ["DELETE"]}]},
    )
    for attack in attacks:
        with pytest.raises(custody.LocatorCustodyError) as error:
            custody.validate_restricted_acl({**good_acl, **attack}, "S-1-5-21-7")
        assert error.value.code == "PRIVATE_HOME_BOUNDARY_INVALID_STOP"

    onedrive_accounts: list[dict[str, object]] = [
        {
            "account_name": "A",
            "value_type": "REG_SZ",
            "path": "C:\\OneDrive-A",
            "path_valid": True,
            "fixed_volume": True,
            "cloud": False,
            "reparse": False,
            "overlaps_project": False,
        },
        {
            "account_name": "b",
            "value_type": "REG_SZ",
            "path": "D:\\OneDrive-B",
            "path_valid": True,
            "fixed_volume": True,
            "cloud": False,
            "reparse": False,
            "overlaps_project": False,
        },
    ]
    good_boundary: dict[str, object] = {
        "local_appdata": "same-handle",
        "profile_local": "same-handle",
        "fixed_volume": True,
        "namespace": "DOS",
        "cloud": False,
        "free_bytes": 42_949_672_960,
        "candidate_worktree_identity_digest": digest("candidate"),
        "ordered_worktree_identity_digests": [digest("other")],
        "onedrive_accounts": onedrive_accounts,
    }
    custody.validate_known_folder_boundary(good_boundary)
    boundary_attacks: tuple[dict[str, object], ...] = (
        {"namespace": "UNC"},
        {"fixed_volume": False},
        {"cloud": True},
        {"free_bytes": 0},
        {"candidate_worktree_identity_digest": digest("other")},
        {"onedrive_accounts": [{**onedrive_accounts[0], "path": "\\\\server\\share"}]},
        {"onedrive_accounts": [{**onedrive_accounts[0], "path": "\\\\?\\C:\\OneDrive"}]},
        {"onedrive_accounts": [{**onedrive_accounts[0], "path": "\\\\.\\C:\\OneDrive"}]},
        {"onedrive_accounts": [{**onedrive_accounts[0], "value_type": "REG_EXPAND_SZ"}]},
        {"onedrive_accounts": [{**onedrive_accounts[0], "reparse": True}]},
        {"onedrive_accounts": [{**onedrive_accounts[0], "overlaps_project": True}]},
        {"onedrive_accounts": list(reversed(onedrive_accounts))},
    )
    for boundary_attack in boundary_attacks:
        with pytest.raises(custody.LocatorCustodyError) as error:
            custody.validate_known_folder_boundary({**good_boundary, **boundary_attack})
        assert error.value.code == "PRIVATE_HOME_BOUNDARY_INVALID_STOP"


def _host_candidate(
    records: dict[str, dict[str, object]],
) -> tuple[dict[str, object], dict[str, str]]:
    closure = records[custody.PS_CLOSURE_SCHEMA]
    candidate: dict[str, object] = {
        "schema_version": custody.HOST_CANDIDATE_SCHEMA,
        "authority_id": "P3_P7_D02_R2_WINDOWS_HOST_BINDING_AUTHORITY_01",
        "change_control_id": "P3_P7_D02_CC_09",
        "private_home_handle_id": "PM_PROJECT_MIRROR_PRIVATE_HOME_V1",
        "resolver_contract_digest": digest("resolver"),
        "principal_sid_digest": digest("sid"),
        "known_folder_identity_digest": digest("known-folder"),
        "known_folder_boundary_contract_digest": digest("boundary"),
        "restricted_ancestor_acl_contract_digest": digest("restricted"),
        "project_container_precondition": "ABSENT_CREATE_NEW",
        "project_code_cache_precondition": "ABSENT_CREATE_NEW",
        "project_code_checkout_resolver_contract_digest": digest("checkout"),
        "python_runtime_identity_digest": digest("python"),
        "python_runtime_file_sha256": digest("python-bytes"),
        "python_runtime_version": "3.13.0",
        "git_executable_identity_digest": digest("git"),
        "git_executable_file_sha256": digest("git-bytes"),
        "windows_directory_identity_digest": closure["windows_directory_identity_digest"],
        "windows_system_directory_identity_digest": closure[
            "windows_system_directory_identity_digest"
        ],
        "ntdll_library_identity_digest": digest("ntdll"),
        "ntdll_library_file_sha256": digest("ntdll-bytes"),
        "kernel32_library_identity_digest": digest("kernel32"),
        "kernel32_library_file_sha256": digest("kernel32-bytes"),
        "advapi32_library_identity_digest": digest("advapi32"),
        "advapi32_library_file_sha256": digest("advapi32-bytes"),
        "fwpuclnt_library_identity_digest": digest("fwpuclnt"),
        "fwpuclnt_library_file_sha256": digest("fwpuclnt-bytes"),
        "powershell_executable_identity_digest": closure["powershell_executable_identity_digest"],
        "powershell_executable_file_sha256": digest("powershell-bytes"),
        "powershell_version": "5.1.22621.1",
        "cmd_executable_identity_digest": digest("cmd"),
        "cmd_executable_file_sha256": digest("cmd-bytes"),
        "powershell_module_root_directory_identity_digest": closure[
            "module_root_directory_identity_digest"
        ],
        "powershell_module_manifest_projection_digest": closure[
            "module_manifest_projection_digest"
        ],
        "powershell_required_cmdlet_projection_digest": closure[
            "required_cmdlet_projection_digest"
        ],
        "powershell_acl_bootstrap_script_projection_digest": closure[
            "acl_bootstrap_script_projection_digest"
        ],
        "powershell_acl_runtime_projection_digest": closure["runtime_projection_digest"],
        "powershell_acl_module_closure_digest": closure["closure_digest"],
        "native_relative_create_contract_digest": digest("native"),
        "protected_directory_dacl_contract_digest": digest("dacl"),
        "wfp_egress_denial_contract_digest": custody.validate_windows_wfp_egress_denial_contract(
            custody.windows_wfp_egress_denial_contract()
        ),
        "locator_custody_implementation_sha": "a" * 40,
        "locator_custody_implementation_acceptance_record_digest": digest("acceptance"),
        "observed_at_utc": "2026-08-28T00:00:00.000001Z",
    }
    candidate["record_digest"] = custody.typed_digest(custody.HOST_CANDIDATE_SCHEMA, candidate)
    native_contract_digest = candidate["native_relative_create_contract_digest"]
    protected_dacl_digest = candidate["protected_directory_dacl_contract_digest"]
    assert isinstance(native_contract_digest, str)
    assert isinstance(protected_dacl_digest, str)
    return candidate, {
        "native_relative_create_contract_digest": native_contract_digest,
        "protected_directory_dacl_contract_digest": protected_dacl_digest,
        "wfp_egress_denial_contract_digest": custody.validate_windows_wfp_egress_denial_contract(
            custody.windows_wfp_egress_denial_contract()
        ),
    }


def test_host_candidate_rejects_all_resigned_runtime_and_windows_replacements() -> None:
    records = _wire_records()
    candidate, contracts = _host_candidate(records)
    bindings = {
        key: value
        for key, value in candidate.items()
        if key
        not in {
            "schema_version",
            "authority_id",
            "change_control_id",
            "private_home_handle_id",
            "project_container_precondition",
            "project_code_cache_precondition",
            "observed_at_utc",
            "record_digest",
        }
    }
    assert (
        custody.validate_windows_host_candidate(
            candidate,
            contracts=contracts,
            expected_bindings=bindings,
            closure=records[custody.PS_CLOSURE_SCHEMA],
        )
        == candidate
    )
    for key in (
        "principal_sid_digest",
        "python_runtime_identity_digest",
        "git_executable_identity_digest",
        "ntdll_library_identity_digest",
        "kernel32_library_identity_digest",
        "advapi32_library_identity_digest",
        "fwpuclnt_library_identity_digest",
        "powershell_executable_identity_digest",
        "cmd_executable_identity_digest",
        "windows_directory_identity_digest",
        "windows_system_directory_identity_digest",
        "powershell_module_root_directory_identity_digest",
        "wfp_egress_denial_contract_digest",
    ):
        replaced = dict(candidate)
        replaced[key] = digest(f"replacement-{key}")
        replaced["record_digest"] = custody.typed_digest(
            custody.HOST_CANDIDATE_SCHEMA,
            {name: value for name, value in replaced.items() if name != "record_digest"},
        )
        with pytest.raises(custody.LocatorCustodyError) as error:
            custody.validate_windows_host_candidate(
                replaced,
                contracts=contracts,
                expected_bindings=bindings,
                closure=records[custody.PS_CLOSURE_SCHEMA],
            )
        assert error.value.code == "WINDOWS_HOST_BINDING_AUTHORITY_MISSING_STOP"


def test_wfp_contract_is_closed_and_uuidv5_replays_exactly() -> None:
    contract = custody.windows_wfp_egress_denial_contract()
    assert len(contract) == 56
    assert custody.validate_windows_wfp_egress_denial_contract(contract) == custody.typed_digest(
        custody.WFP_EGRESS_SCHEMA, contract
    )
    first = custody.derive_windows_wfp_keys(digest("acceptance"), digest("sid"))
    assert tuple(first) == (
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
    assert first == custody.derive_windows_wfp_keys(digest("acceptance"), digest("sid"))
    assert first != custody.derive_windows_wfp_keys(digest("acceptance-2"), digest("sid"))
    for attack in (
        {key: value for key, value in contract.items() if key != "backend"},
        {**contract, "unexpected": "x"},
        {**contract, "filter_weight": 0},
        {**contract, "probe_targets": ["192.0.2.1"]},
    ):
        with pytest.raises(custody.LocatorCustodyError):
            custody.validate_windows_wfp_egress_denial_contract(attack)
    projections = custody.windows_wfp_filter_projections(first)
    assert [projection["layer_key"] for projection in projections] == [
        "FWPM_LAYER_ALE_AUTH_CONNECT_V4",
        "FWPM_LAYER_ALE_AUTH_CONNECT_V6",
    ] * 4
    for field, replacement in (
        ("filter_key", first["FILTER:CMD:V4"]),
        ("layer_key", "FWPM_LAYER_ALE_AUTH_CONNECT_V4"),
        ("action_type", "FWP_ACTION_PERMIT"),
        ("weight", 0),
        ("condition_value_type", "FWP_UINT64"),
        ("unlisted_caller_fields_zero_or_null", False),
    ):
        altered = [dict(projection) for projection in projections]
        altered[1][field] = replacement
        with pytest.raises(custody.LocatorCustodyError):
            custody.validate_windows_wfp_filter_projections(first, altered)


def test_locator_frame_is_exact_single_canonical_binary_frame() -> None:
    frame = custody.build_locator_bridge_frame("C:\\证据\\root", ["D:\\worktree\nname"])
    assert custody.parse_locator_bridge_frame(frame) == {
        "absolute_root_path": "C:\\证据\\root",
        "ordered_excluded_worktree_paths": ["D:\\worktree\nname"],
        "protocol_version": "P3_P7_D02_R2_LOCATOR_BRIDGE_STDIN_V1",
    }
    attacks = (
        b"",
        b"WRONGMAG" + frame[8:],
        frame + b"x",
        frame[:11],
        b"PMCC09L1" + (1_048_577).to_bytes(4, "big") + b"x",
        b"PMCC09L1" + (3).to_bytes(4, "big") + b"\xef\xbb\xbf",
        b"PMCC09L1" + (3).to_bytes(4, "big") + b"\xff\xff\xff",
        b"PMCC09L1" + (1).to_bytes(4, "big") + b"\0",
    )
    for attack in attacks:
        with pytest.raises(custody.LocatorCustodyError, match="BRIDGE_FRAME_INVALID_STOP"):
            custody.parse_locator_bridge_frame(attack)


def bridge_stage_authority() -> tuple[custody.JsonObject, dict[str, str]]:
    trusted = {
        "IMPLEMENTATION_ACCEPTANCE": digest("implementation-acceptance"),
        "HOST_BINDING_ACCEPTANCE": digest("host-binding-acceptance"),
        "PRIVATE_HOME_BINDING_ACCEPTANCE": digest("private-home-binding-acceptance"),
        "R06_CHECKOUT_SEAL": digest("checkout-seal"),
        "BRIDGE_SCRATCH_RECEIPT": digest("scratch-receipt"),
        "LOCATOR_CUSTODY": digest("locator-custody"),
    }
    return custody.make_detached_bridge_stage_authority(trusted), trusted


def bridge_status(seed: str = "status") -> bytes:
    return f"STATUS: PASS\nDIGEST: {digest(seed)}\n".encode("ascii")


@pytest.mark.parametrize(
    "backend",
    [
        custody.SyntheticWindowsWfpBackend(api_available=False),
        custody.SyntheticWindowsWfpBackend(privileged=False),
        custody.SyntheticWindowsWfpBackend(bfe_running=False),
        custody.SyntheticWindowsWfpBackend(dll_identity_matches=False),
        custody.SyntheticWindowsWfpBackend(ownership_matches=False),
        custody.SyntheticWindowsWfpBackend(replay_matches=False),
    ],
)
def test_wfp_installation_failures_fail_closed_and_cleanup_own_objects(
    backend: custody.SyntheticWindowsWfpBackend,
) -> None:
    frame = custody.build_locator_bridge_frame("C:\\private", ["D:\\worktree"])
    stages, trusted = bridge_stage_authority()
    with pytest.raises(custody.LocatorCustodyError):
        custody.run_synthetic_detached_bridge(
            stage_authority=stages,
            trusted_stage_digests=trusted,
            backend=backend,
            job=custody.SyntheticJobObject(),
            implementation_acceptance_digest=trusted["IMPLEMENTATION_ACCEPTANCE"],
            principal_sid_digest=digest("sid"),
            frame=frame,
            outer_child=lambda _frame, _env: (bridge_status(), bridge_status("stderr")),
            acl_child=lambda _env: (bridge_status("acl"), bridge_status("acl-stderr")),
        )
    assert backend.installed_keys == set()
    assert "cleanup" in backend.calls


def test_bridge_orders_prerequisites_wfp_probes_job_disclosure_and_cleanup() -> None:
    backend = custody.SyntheticWindowsWfpBackend()
    job = custody.SyntheticJobObject()
    frame = custody.build_locator_bridge_frame("C:\\private\\root", ["D:\\worktree"])
    stages, trusted = bridge_stage_authority()
    seen: dict[str, object] = {}

    def outer_child(received: bytes, env: object) -> tuple[bytes, bytes]:
        assert received == frame
        assert isinstance(env, dict)
        seen["env"] = dict(env)
        return bridge_status(), bridge_status("outer-stderr")

    def acl_child(env: object) -> tuple[bytes, bytes]:
        assert isinstance(env, dict)
        seen["acl_env"] = dict(env)
        return bridge_status("acl"), bridge_status("acl-stderr")

    assert custody.run_synthetic_detached_bridge(
        stage_authority=stages,
        trusted_stage_digests=trusted,
        backend=backend,
        job=job,
        implementation_acceptance_digest=trusted["IMPLEMENTATION_ACCEPTANCE"],
        principal_sid_digest=digest("sid"),
        frame=frame,
        outer_child=outer_child,
        acl_child=acl_child,
    ) == (bridge_status(), bridge_status("acl"))
    assert seen == {
        "env": {},
        "acl_env": {"MIRROR_D02_R2_ACL_PATH": "C:\\private\\root"},
    }
    assert backend.calls == [
        "install",
        "verify",
        "probe:dns:192.0.2.1",
        "probe:dns:2001:db8::1",
        "probe:socket:192.0.2.1",
        "probe:socket:2001:db8::1",
        "probe:connect:192.0.2.1",
        "probe:connect:2001:db8::1",
        "cleanup",
    ]
    assert backend.installed_keys == set()
    assert not job.bridge_active and not job.child_active


@pytest.mark.parametrize("probe_result", ["SUCCESS", "ETIMEDOUT", "EHOSTUNREACH", "DNS_FAILURE"])
def test_any_non_access_denied_probe_stops_before_locator_disclosure(probe_result: str) -> None:
    backend = custody.SyntheticWindowsWfpBackend(probe_result=probe_result)
    stages, trusted = bridge_stage_authority()
    called = False

    def child(_frame: bytes, _env: object) -> tuple[bytes, bytes]:
        nonlocal called
        called = True
        return b"", b""

    with pytest.raises(custody.LocatorCustodyError, match="BRIDGE_NETWORK_DENIAL_UNAVAILABLE_STOP"):
        custody.run_synthetic_detached_bridge(
            stage_authority=stages,
            trusted_stage_digests=trusted,
            backend=backend,
            job=custody.SyntheticJobObject(),
            implementation_acceptance_digest=trusted["IMPLEMENTATION_ACCEPTANCE"],
            principal_sid_digest=digest("sid"),
            frame=custody.build_locator_bridge_frame("C:\\private", ["D:\\worktree"]),
            outer_child=child,
            acl_child=lambda _env: (bridge_status("acl"), bridge_status("acl-stderr")),
        )
    assert not called
    assert backend.installed_keys == set()


def test_job_boundary_and_locator_leak_or_cleanup_failure_are_fail_closed() -> None:
    frame = custody.build_locator_bridge_frame("C:\\private", ["D:\\worktree"])
    stages, trusted = bridge_stage_authority()
    for job in (
        custody.SyntheticJobObject(active_process_limit=3),
        custody.SyntheticJobObject(no_breakaway=False),
    ):
        with pytest.raises(
            custody.LocatorCustodyError, match="BRIDGE_UNAUTHORIZED_SUBPROCESS_STOP"
        ):
            custody.run_synthetic_detached_bridge(
                stage_authority=stages,
                trusted_stage_digests=trusted,
                backend=custody.SyntheticWindowsWfpBackend(),
                job=job,
                implementation_acceptance_digest=trusted["IMPLEMENTATION_ACCEPTANCE"],
                principal_sid_digest=digest("sid"),
                frame=frame,
                outer_child=lambda _frame, _env: (bridge_status(), bridge_status("stderr")),
                acl_child=lambda _env: (bridge_status("acl"), bridge_status("acl-stderr")),
            )
    leaking = custody.SyntheticWindowsWfpBackend()
    with pytest.raises(custody.LocatorCustodyError, match="BRIDGE_LOCATOR_LEAK_STOP"):
        custody.run_synthetic_detached_bridge(
            stage_authority=stages,
            trusted_stage_digests=trusted,
            backend=leaking,
            job=custody.SyntheticJobObject(),
            implementation_acceptance_digest=trusted["IMPLEMENTATION_ACCEPTANCE"],
            principal_sid_digest=digest("sid"),
            frame=frame,
            outer_child=lambda _frame, _env: (b"D:\\secret-worktree", bridge_status("stderr")),
            acl_child=lambda _env: (bridge_status("acl"), bridge_status("acl-stderr")),
        )
    assert leaking.installed_keys == set()
    with pytest.raises(custody.LocatorCustodyError, match="WFP_EGRESS_SESSION_CLEANUP_FAILED_STOP"):
        custody.run_synthetic_detached_bridge(
            stage_authority=stages,
            trusted_stage_digests=trusted,
            backend=custody.SyntheticWindowsWfpBackend(cleanup_succeeds=False),
            job=custody.SyntheticJobObject(),
            implementation_acceptance_digest=trusted["IMPLEMENTATION_ACCEPTANCE"],
            principal_sid_digest=digest("sid"),
            frame=frame,
            outer_child=lambda _frame, _env: (bridge_status(), bridge_status("stderr")),
            acl_child=lambda _env: (bridge_status("acl"), bridge_status("acl-stderr")),
        )


def test_sol_p1_02_reproductions_reject_unrelated_stage_and_arbitrary_or_path_output() -> None:
    stages, trusted = bridge_stage_authority()
    frame = custody.build_locator_bridge_frame("C:\\private", ["D:\\worktree"])
    with pytest.raises(custody.LocatorCustodyError, match="DETACHED_RUNTIME_IDENTITY_CHANGED_STOP"):
        custody.run_synthetic_detached_bridge(
            stage_authority={"unrelated": True},
            trusted_stage_digests=trusted,
            backend=custody.SyntheticWindowsWfpBackend(),
            job=custody.SyntheticJobObject(),
            implementation_acceptance_digest=trusted["IMPLEMENTATION_ACCEPTANCE"],
            principal_sid_digest=digest("sid"),
            frame=frame,
            outer_child=lambda _frame, _env: (bridge_status(), bridge_status("outer-stderr")),
            acl_child=lambda _env: (bridge_status("acl"), bridge_status("acl-stderr")),
        )
    for output in (b"D:\\secret-worktree", b"ARBITRARY"):

        def outer_output(
            _frame: bytes, _env: Mapping[str, str], payload: bytes = output
        ) -> tuple[bytes, bytes]:
            return payload, bridge_status("stderr")

        with pytest.raises(custody.LocatorCustodyError, match="BRIDGE_LOCATOR_LEAK_STOP"):
            custody.run_synthetic_detached_bridge(
                stage_authority=stages,
                trusted_stage_digests=trusted,
                backend=custody.SyntheticWindowsWfpBackend(),
                job=custody.SyntheticJobObject(),
                implementation_acceptance_digest=trusted["IMPLEMENTATION_ACCEPTANCE"],
                principal_sid_digest=digest("sid"),
                frame=frame,
                outer_child=outer_output,
                acl_child=lambda _env: (bridge_status("acl"), bridge_status("acl-stderr")),
            )


def test_stage_authority_exact_order_trusted_cross_check_and_job_contract_are_closed() -> None:
    stages, trusted = bridge_stage_authority()
    assert custody.validate_detached_bridge_stage_authority(stages, trusted) == stages
    rows = stages["ordered_stage_rows"]
    assert isinstance(rows, list)
    for attack in (
        {"unrelated": True},
        {**stages, "unrelated": True},
        {**stages, "ordered_stage_rows": list(reversed(rows))},
    ):
        with pytest.raises(
            custody.LocatorCustodyError, match="DETACHED_RUNTIME_IDENTITY_CHANGED_STOP"
        ):
            custody.validate_detached_bridge_stage_authority(attack, trusted)
    changed_trusted = {**trusted, "LOCATOR_CUSTODY": digest("other")}
    with pytest.raises(custody.LocatorCustodyError, match="DETACHED_RUNTIME_IDENTITY_CHANGED_STOP"):
        custody.validate_detached_bridge_stage_authority(stages, changed_trusted)
    for job in (
        custody.SyntheticJobObject(kill_on_close=False),
        custody.SyntheticJobObject(inherited_handles=("stdin", "stdout")),
        custody.SyntheticJobObject(maintenance_window_exclusive=False),
        custody.SyntheticJobObject(audit_policy_network_denied=False),
    ):
        with pytest.raises(
            custody.LocatorCustodyError, match="BRIDGE_UNAUTHORIZED_SUBPROCESS_STOP"
        ):
            job.start_bridge()


def cc09_record(schema: str, stamp: str = "2026-08-28T00:00:00.000001Z") -> custody.JsonObject:
    terminal = (
        "receipt_digest"
        if custody._CC09_RECORD_FIELDS[schema][-1] == "receipt_digest"
        else "record_digest"
    )
    values: custody.JsonObject = {}
    for key in custody._CC09_RECORD_FIELDS[schema]:
        if key in {"schema_version", terminal}:
            continue
        values[key] = (
            digest(f"{schema}:{key}") if key.endswith(("_digest", "_file_sha256")) else "value"
        )
    fixed = {
        "project_id": "PROJECT_MIRROR",
        "retention_policy": custody._RETAIN,
        "cleanup_policy": custody._CLEANUP,
        "created_at_utc": stamp,
        "observed_at_utc": stamp,
        "record_created_at_utc": stamp,
    }
    values.update({key: value for key, value in fixed.items() if key in values})
    if "locator_custody_implementation_sha" in values:
        values["locator_custody_implementation_sha"] = "a" * 40
    for key in (
        "accepted_candidate_sha",
        "accepted_candidate_tree",
        "accepted_candidate_git_blob_oid",
    ):
        if key in values:
            values[key] = "b" * 40
    if schema == custody.CODE_CACHE_RECEIPT_SCHEMA:
        values.update(
            {
                "code_cache_handle_id": "PM_PROJECT_MIRROR_CODE_CACHE_V1",
                "purpose": "PUBLIC_CODE_ONLY_CC09_ACCEPTED_R06_CHECKOUT",
                "allowed_checkout_component": "accepted-r06-ab08a6e861ec",
            }
        )
    if schema == custody.PROJECT_CONTAINER_RECEIPT_SCHEMA:
        values.update(
            {
                "project_container_handle_id": "PM_PROJECT_MIRROR_CONTAINER_V1",
                "purpose": "PROJECT_MIRROR_PRINCIPAL_PRIVATE_OUTPUT_CONTAINER_ONLY",
                "allowed_next_component": "principal-private-output-v1",
            }
        )
    if schema == custody.PRIVATE_HOME_RECEIPT_SCHEMA:
        values.update(
            {
                "private_home_handle_id": "PM_PROJECT_MIRROR_PRIVATE_HOME_V1",
                "purpose": "PRINCIPAL_PRIVATE_OUTPUT_CONTROL_AND_D02_R2_CUSTODY_ONLY",
                "allowed_subject_root_ids": ["P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT"],
            }
        )
    if schema == custody.PRIVATE_HOME_CANDIDATE_SCHEMA:
        values.update(
            {
                "authority_id": "P3_P7_D02_R2_PRIVATE_HOME_BINDING_AUTHORITY_01",
                "change_control_id": "P3_P7_D02_CC_09",
                "private_home_handle_id": "PM_PROJECT_MIRROR_PRIVATE_HOME_V1",
            }
        )
    if schema == custody.BRIDGE_SCRATCH_RECEIPT_SCHEMA:
        values.update(
            {
                "bridge_scratch_handle_id": "PM_PROJECT_MIRROR_CC09_BRIDGE_SCRATCH_V1",
                "purpose": "CC09_RECEIPT_BOUND_PRIVATE_TEMP_ONLY",
                "at_rest_policy": "RECEIPT_ONLY",
                "locator_session_policy": "RECEIPT_ONLY_BEFORE_AND_AFTER_EVERY_LOCATOR_SESSION",
                "crash_residue_policy": "PRESERVE_AND_STOP",
            }
        )
    if schema == custody.R06_CHECKOUT_SEAL_SCHEMA:
        values.update(
            {
                "checkout_handle_id": "PM_ACCEPTED_R06_CHECKOUT_V1",
                "purpose": "PUBLIC_CODE_ONLY_CC09_ACCEPTED_R06_CHECKOUT_SEAL",
                "accepted_git_executable_file_sha256": digest("git"),
                "head_sha": custody._R06_SHA,
                "head_tree": custody._R06_TREE,
                "required_ref": "refs/remotes/origin/codex/p3-p7-core-demo",
                "required_ref_target": custody._R06_CHECKPOINT,
                "accepted_r06_implementation_sha": custody._R06_SHA,
                "accepted_r06_implementation_tree": custody._R06_TREE,
                "accepted_r06_acceptance_checkpoint_sha": custody._R06_CHECKPOINT,
                "accepted_r06_acceptance_record_digest": custody._R06_ACCEPTANCE_DIGEST,
                "accepted_r06_governed_rows": [dict(row) for row in custody._R06_ROWS],
            }
        )
    return custody.make_cc09_record(schema, values)


def bindings(record: custody.JsonObject) -> custody.JsonObject:
    return {
        key: value
        for key, value in record.items()
        if key not in {"schema_version", "receipt_digest", "record_digest"}
    }


def resign(schema: str, record: custody.JsonObject) -> custody.JsonObject:
    record["record_digest"] = custody.typed_digest(
        schema, {key: value for key, value in record.items() if key != "record_digest"}
    )
    return record


def trusted_bindings(
    record: custody.JsonObject, anchor_id: str
) -> custody.TrustedAcceptanceBindingSource:
    raw = canonical_json_bytes(record)
    return custody.load_trusted_acceptance_binding_source(
        raw,
        anchor_id=anchor_id,
    )


def candidate_acceptance_record(
    *, schema: str, candidate: custody.JsonObject, private_home: bool
) -> custody.JsonObject:
    candidate_sha = "c" * 40
    bindings: custody.JsonObject = {
        "accepted_candidate_sha": candidate_sha,
        "accepted_candidate_tree": "d" * 40,
        "accepted_candidate_path": (
            "docs/operations/P3_P7_D02_R2_PRIVATE_HOME_BINDING_CANDIDATE.json"
            if private_home
            else "docs/operations/P3_P7_D02_R2_WINDOWS_HOST_BINDING_CANDIDATE.json"
        ),
        "accepted_candidate_git_blob_oid": "e" * 40,
        "accepted_candidate_file_sha256": digest("candidate-bytes"),
        "accepted_candidate_record_digest": candidate["record_digest"],
        "accepted_plan_acceptance_record_digest": digest("plan-acceptance"),
        "locator_custody_implementation_acceptance_record_digest": (
            "1afa590ef8284d9dbd0977d1777091e11b4ecd0032cc974471c3dfd3a81ec950"
        ),
    }
    if private_home:
        bindings.update(
            {
                "host_binding_acceptance_record_digest": candidate[
                    "host_binding_acceptance_record_digest"
                ],
                "project_container_name_receipt_digest": candidate[
                    "project_container_name_receipt_digest"
                ],
                "private_home_name_receipt_digest": candidate["private_home_name_receipt_digest"],
            }
        )
    record: custody.JsonObject = {
        "schema_version": schema,
        "authority_id": (
            "P3_P7_D02_R2_PRIVATE_HOME_BINDING_ACCEPTANCE_01"
            if private_home
            else "P3_P7_D02_R2_WINDOWS_HOST_BINDING_ACCEPTANCE_01"
        ),
        "change_control_id": "P3_P7_D02_CC_09",
        **bindings,
        "independent_review": {
            "evidence_digest": digest("review"),
            "findings_p0": 0,
            "findings_p1": 0,
            "findings_p2": 0,
            "findings_p3": 0,
            "result": "PASS",
            "review_task_id": "CC09_EXACT_REVIEW",
            "reviewed_candidate_sha": candidate_sha,
        },
        "same_sha_ci": {
            "artifact_manifest_digest": digest("CI"),
            "head_sha": candidate_sha,
            "provider": "GITHUB_ACTIONS",
            "repository": "yangyy816/project-mirror",
            "required_jobs": ["quality-and-integration", "secret-scan", "docker-validation"],
            "result": "PASS",
            "run_id": 1,
            "workflow_identity": ".github/workflows/ci.yml",
        },
        "principal_acceptance": {
            "status": "PRINCIPAL_ACCEPTED",
            "accepted_candidate_sha": candidate_sha,
            "accepted_at_utc": "2026-08-28T00:00:00.000001Z",
            "acceptance_authority_digest": digest("principal"),
        },
        "authorized_scope": (
            "OPEN_EXACT_PRIVATE_HOME_FOR_RECEIPT_BOUND_BRIDGE_SCRATCH_AND_CC09_LOCATOR_CUSTODY_ONLY"
            if private_home
            else (
                "CREATE_EXACT_CODE_CACHE_AND_TWO_COMPONENT_PRIVATE_HOME_CANDIDATES_AND_"
                "RECEIPTS_ONLY"
            )
        ),
        "prohibited_scope": (
            [
                "ALTERNATE_PRIVATE_HOME",
                "PRIVATE_HOME_REBIND",
                "SECOND_LOCATOR_NAMESPACE",
                "SECOND_EVIDENCE_ROOT",
                "SOURCE_GENERATION",
                "M3_M4_EXECUTION",
                "POSTGRESQL_ADMISSION",
                "FORMAL_PHASE_AUTHORITY",
                "PRODUCTION_RELEASE",
            ]
            if private_home
            else [
                "LOCATOR_NAMESPACE_CREATION",
                "LOCATOR_EVENT_CREATION",
                "CC08_EVIDENCE_ROOT_CREATION",
                "R05_REHOME",
                "SOURCE_GENERATION",
                "M3_M4_EXECUTION",
                "POSTGRESQL_ADMISSION",
                "FORMAL_PHASE_AUTHORITY",
                "PRODUCTION_RELEASE",
            ]
        ),
        "record_created_at_utc": "2026-08-28T00:00:00.000001Z",
    }
    return resign(schema, record)


def candidate_acceptance(
    *, schema: str, candidate: custody.JsonObject, private_home: bool
) -> tuple[custody.JsonObject, custody.TrustedAcceptanceBindingSource]:
    acceptance = candidate_acceptance_record(
        schema=schema,
        candidate=candidate,
        private_home=private_home,
    )
    return acceptance, trusted_bindings(
        acceptance,
        (
            custody.PRIVATE_HOME_ACCEPTANCE_TEST_ANCHOR_ID
            if private_home
            else custody.HOST_ACCEPTANCE_TEST_ANCHOR_ID
        ),
    )


def test_plan_acceptance_rejects_fully_resigned_nested_evidence_type_and_ci_drift() -> None:
    plan = json.loads(
        (
            Path(__file__).parents[3]
            / "docs/operations/P3_P7_D02_R2_LOCATOR_CUSTODY_PLAN_ACCEPTANCE.json"
        ).read_text()
    )
    trusted = trusted_bindings(plan, custody.PLAN_ACCEPTANCE_ANCHOR_ID)
    assert (
        custody.validate_plan_acceptance(plan, expected_bindings=trusted)["record_digest"]
        == plan["record_digest"]
    )
    with pytest.raises(
        custody.LocatorCustodyError, match="CUSTODY_TRUSTED_BINDING_SOURCE_REQUIRED_STOP"
    ):
        custody.validate_plan_acceptance(
            plan, expected_bindings=cast(custody.TrustedAcceptanceBindingSource, plan)
        )

    forged = copy.deepcopy(plan)
    forged_sha = "9" * 40
    forged["accepted_governance_sha"] = forged_sha
    independent_review = cast(custody.JsonObject, forged["independent_review"])
    independent_review["reviewed_governance_sha"] = forged_sha
    same_sha_ci = cast(custody.JsonObject, forged["same_sha_ci"])
    same_sha_ci["head_sha"] = forged_sha
    principal_acceptance = cast(custody.JsonObject, forged["principal_acceptance"])
    principal_acceptance["accepted_governance_sha"] = forged_sha
    resign(custody.PLAN_SCHEMA, forged)
    forged_mapping = copy.deepcopy(
        {key: value for key, value in forged.items() if key != "record_digest"}
    )
    with pytest.raises(
        custody.LocatorCustodyError, match="CUSTODY_TRUSTED_BINDING_SOURCE_REQUIRED_STOP"
    ):
        custody.validate_plan_acceptance(
            forged,
            expected_bindings=cast(custody.TrustedAcceptanceBindingSource, forged_mapping),
        )
    with pytest.raises(custody.LocatorCustodyError, match="CUSTODY_ACCEPTED_BINDING_DRIFT_STOP"):
        custody.validate_plan_acceptance(forged, expected_bindings=trusted)
    with pytest.raises(
        custody.LocatorCustodyError, match="CUSTODY_TRUSTED_BINDING_SOURCE_MISMATCH_STOP"
    ):
        custody.load_trusted_acceptance_binding_source(
            canonical_json_bytes(forged),
            anchor_id=custody.PLAN_ACCEPTANCE_ANCHOR_ID,
        )
    with pytest.raises(
        custody.LocatorCustodyError, match="CUSTODY_TRUSTED_BINDING_ANCHOR_UNKNOWN_STOP"
    ):
        custody.load_trusted_acceptance_binding_source(
            canonical_json_bytes(forged),
            anchor_id=cast(str, forged["record_digest"]),
        )
    for path, replacement in (
        (("same_sha_ci",), "not-an-object"),
        (("same_sha_ci", "run_id"), "33108087102"),
        (("same_sha_ci", "required_jobs"), ["quality-and-integration"]),
        (("principal_acceptance", "acceptance_authority_digest"), "not-a-digest"),
    ):
        altered = copy.deepcopy(plan)
        target: dict[str, object] = altered
        for key in path[:-1]:
            item = target[key]
            assert isinstance(item, dict)
            target = item
        target[path[-1]] = replacement
        resign(custody.PLAN_SCHEMA, altered)
        with pytest.raises(custody.LocatorCustodyError):
            custody.validate_plan_acceptance(altered, expected_bindings=trusted)


def implementation_acceptance(plan: custody.JsonObject) -> custody.JsonObject:
    implementation_sha = "f" * 40
    authorized_paths = cast(list[str], plan["authorized_implementation_paths"])
    record: custody.JsonObject = {
        "schema_version": custody.IMPLEMENTATION_SCHEMA,
        "authority_id": "P3_P7_D02_R2_LOCATOR_CUSTODY_IMPLEMENTATION_ACCEPTANCE_01",
        "change_control_id": "P3_P7_D02_CC_09",
        "accepted_plan_sha": plan["accepted_governance_sha"],
        "accepted_plan_tree": plan["accepted_governance_tree"],
        "accepted_plan_acceptance_record_digest": plan["record_digest"],
        "implementation_sha": implementation_sha,
        "implementation_tree": "e" * 40,
        "governed_paths": [
            {
                "path": path,
                "sha256": digest(f"implementation:{path}"),
                "git_blob_oid": ("a" if index == 0 else "b") * 40,
            }
            for index, path in enumerate(authorized_paths)
        ],
        "schema_contract_digest": plan["schema_contract_digest"],
        "independent_review": {
            "evidence_digest": digest("implementation-review"),
            "findings_p0": 0,
            "findings_p1": 0,
            "findings_p2": 0,
            "findings_p3": 0,
            "result": "PASS",
            "review_task_id": "CC09_IMPLEMENTATION_REVIEW",
            "reviewed_implementation_sha": implementation_sha,
        },
        "same_sha_ci": {
            "artifact_manifest_digest": digest("implementation-CI"),
            "head_sha": implementation_sha,
            "provider": "GITHUB_ACTIONS",
            "repository": "yangyy816/project-mirror",
            "required_jobs": ["quality-and-integration", "secret-scan", "docker-validation"],
            "result": "PASS",
            "run_id": 2,
            "workflow_identity": ".github/workflows/ci.yml",
        },
        "principal_acceptance": {
            "status": "PRINCIPAL_ACCEPTED",
            "accepted_implementation_sha": implementation_sha,
            "accepted_at_utc": "2026-08-28T00:00:00.000001Z",
            "acceptance_authority_digest": digest("implementation-principal"),
        },
        "authorized_scope": "READ_ONLY_WINDOWS_HOST_BINDING_CANDIDATE_PROJECTION_ONLY",
        "prohibited_scope": [
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
        ],
        "record_created_at_utc": "2026-08-28T00:00:00.000001Z",
    }
    return resign(custody.IMPLEMENTATION_SCHEMA, record)


def test_implementation_acceptance_rejects_fully_resigned_nested_and_governed_path_drift() -> None:
    plan = json.loads(
        (
            Path(__file__).parents[3]
            / "docs/operations/P3_P7_D02_R2_LOCATOR_CUSTODY_PLAN_ACCEPTANCE.json"
        ).read_text()
    )
    acceptance = implementation_acceptance(plan)
    plan_bindings = trusted_bindings(plan, custody.PLAN_ACCEPTANCE_ANCHOR_ID)
    assert (
        custody.validate_implementation_acceptance(
            acceptance,
            plan,
            expected_bindings=trusted_bindings(
                acceptance, custody.IMPLEMENTATION_ACCEPTANCE_TEST_ANCHOR_ID
            ),
            plan_expected_bindings=plan_bindings,
        )["record_digest"]
        == acceptance["record_digest"]
    )
    for path, replacement in (
        (("same_sha_ci", "run_id"), 0),
        (("principal_acceptance",), "self-attested"),
        (("governed_paths",), "not-a-list"),
        (("accepted_plan_acceptance_record_digest",), digest("forged-plan")),
    ):
        altered = copy.deepcopy(acceptance)
        target: custody.JsonObject = altered
        for key in path[:-1]:
            item = target[key]
            assert isinstance(item, dict)
            target = item
        target[path[-1]] = replacement
        resign(custody.IMPLEMENTATION_SCHEMA, altered)
        with pytest.raises(custody.LocatorCustodyError):
            custody.validate_implementation_acceptance(
                altered,
                plan,
                expected_bindings=trusted_bindings(
                    acceptance, custody.IMPLEMENTATION_ACCEPTANCE_TEST_ANCHOR_ID
                ),
                plan_expected_bindings=plan_bindings,
            )


@pytest.mark.parametrize("private_home", [False, True])
def test_host_and_private_acceptance_bind_external_git_candidate_and_nested_authority(
    private_home: bool,
) -> None:
    candidate: custody.JsonObject = (
        cc09_record(custody.PRIVATE_HOME_CANDIDATE_SCHEMA)
        if private_home
        else cast(custody.JsonObject, _host_candidate(_wire_records())[0])
    )
    schema = (
        custody.PRIVATE_HOME_ACCEPTANCE_SCHEMA if private_home else custody.HOST_ACCEPTANCE_SCHEMA
    )
    acceptance, trusted = candidate_acceptance(
        schema=schema, candidate=candidate, private_home=private_home
    )
    validator = (
        custody.validate_private_home_binding_acceptance
        if private_home
        else custody.validate_windows_host_binding_acceptance
    )
    assert (
        validator(acceptance, candidate=candidate, expected_bindings=trusted)
        == acceptance["record_digest"]
    )
    for path, replacement in (
        (("independent_review",), "self-attested"),
        (("same_sha_ci",), "self-attested"),
        (("same_sha_ci", "required_jobs"), "quality-and-integration"),
        (("same_sha_ci", "head_sha"), "f" * 40),
        (("principal_acceptance", "accepted_at_utc"), "2026-08-28T00:00:00.000002Z"),
        (("accepted_candidate_file_sha256",), digest("replacement")),
    ):
        altered = copy.deepcopy(acceptance)
        target: custody.JsonObject = altered
        for key in path[:-1]:
            item = target[key]
            assert isinstance(item, dict)
            target = item
        target[path[-1]] = replacement
        resign(schema, altered)
        with pytest.raises(custody.LocatorCustodyError):
            validator(altered, candidate=candidate, expected_bindings=trusted)


def test_fully_resigned_future_acceptance_chain_cannot_mint_bootstrap_authority() -> None:
    plan = json.loads(
        (
            Path(__file__).parents[3]
            / "docs/operations/P3_P7_D02_R2_LOCATOR_CUSTODY_PLAN_ACCEPTANCE.json"
        ).read_text()
    )
    implementation = implementation_acceptance(plan)
    host_candidate = cast(custody.JsonObject, _host_candidate(_wire_records())[0])
    host_candidate["locator_custody_implementation_sha"] = implementation["implementation_sha"]
    host_candidate["locator_custody_implementation_acceptance_record_digest"] = implementation[
        "record_digest"
    ]
    resign(custody.HOST_CANDIDATE_SCHEMA, host_candidate)
    host_acceptance = candidate_acceptance_record(
        schema=custody.HOST_ACCEPTANCE_SCHEMA,
        candidate=host_candidate,
        private_home=False,
    )
    host_acceptance["accepted_plan_acceptance_record_digest"] = plan["record_digest"]
    host_acceptance["locator_custody_implementation_acceptance_record_digest"] = implementation[
        "record_digest"
    ]
    resign(custody.HOST_ACCEPTANCE_SCHEMA, host_acceptance)
    private_candidate = cc09_record(custody.PRIVATE_HOME_CANDIDATE_SCHEMA)
    private_candidate["host_binding_acceptance_record_digest"] = host_acceptance["record_digest"]
    private_candidate["locator_custody_implementation_acceptance_record_digest"] = implementation[
        "record_digest"
    ]
    resign(custody.PRIVATE_HOME_CANDIDATE_SCHEMA, private_candidate)
    private_acceptance = candidate_acceptance_record(
        schema=custody.PRIVATE_HOME_ACCEPTANCE_SCHEMA,
        candidate=private_candidate,
        private_home=True,
    )
    private_acceptance["accepted_plan_acceptance_record_digest"] = plan["record_digest"]
    private_acceptance["locator_custody_implementation_acceptance_record_digest"] = implementation[
        "record_digest"
    ]
    private_acceptance["host_binding_acceptance_record_digest"] = host_acceptance["record_digest"]
    resign(custody.PRIVATE_HOME_ACCEPTANCE_SCHEMA, private_acceptance)

    with pytest.raises(
        custody.LocatorCustodyError, match="CUSTODY_BOOTSTRAP_AUTHORITY_ANCHOR_REQUIRED_STOP"
    ):
        custody.load_locator_bootstrap_authority_anchor(
            implementation_acceptance=cast(
                custody.TrustedAcceptanceBindingSource,
                implementation,
            ),
            private_home_acceptance=cast(
                custody.TrustedAcceptanceBindingSource,
                private_acceptance,
            ),
        )


def registry_snapshot(*, populated: bool) -> custody.JsonObject:
    root_receipt_digest = digest("root")
    common_genesis_digest = digest("genesis")
    ordered_events: list[custody.Json] = []
    if populated:
        for sequence, output_id in enumerate(custody.ORDERED_R05_OUTPUT_IDS, 1):
            ordered_events.append(
                {
                    "sequence": sequence,
                    "transaction_id": digest(f"registry-transaction-{sequence}"),
                    "output_id": output_id,
                    "semantic_role": "BANK_IMPORT_EVIDENCE",
                    "authority_digest": digest(f"registry-authority-{sequence}"),
                    "event_digest": digest(f"registry-event-{sequence}"),
                }
            )
    snapshot: custody.JsonObject = {
        "schema_version": custody.REGISTRY_SNAPSHOT_SCHEMA,
        "evidence_root_id": "P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT",
        "root_name_receipt_digest": root_receipt_digest,
        "execution_contract_digest": digest("execution-contract"),
        "registry_schema_contract_digest": digest("registry-schema-contract"),
        "common_genesis_digest": common_genesis_digest,
        "event_count": len(ordered_events),
        "head_event_digest": (
            cast(dict[str, custody.Json], ordered_events[-1])["event_digest"]
            if ordered_events
            else common_genesis_digest
        ),
        "ordered_events": ordered_events,
    }
    snapshot["semantic_snapshot_digest"] = custody.typed_digest(
        custody.REGISTRY_SNAPSHOT_SCHEMA, snapshot
    )
    return snapshot


type ActualRootAddendumRecords = tuple[
    custody.JsonObject,
    custody.JsonObject,
    custody.TrustedAcceptanceBindingSource,
    custody.JsonObject,
    custody.JsonObject,
    custody.JsonObject,
    custody.JsonObject,
]


def actual_root_addendum_records() -> ActualRootAddendumRecords:
    before_a = registry_snapshot(populated=False)
    before_b = copy.deepcopy(before_a)
    after_a = registry_snapshot(populated=True)
    after_b = copy.deepcopy(after_a)
    candidate: custody.JsonObject = {
        "schema_version": custody.ADDENDUM_SCHEMA,
        "authority_id": "P3_P7_D02_R2_ACTUAL_ROOT_DIGEST_BINDING_ADDENDUM_01",
        "change_control_id": "P3_P7_D02_CC_09",
        "cc09_plan_acceptance_record_digest": digest("plan"),
        "cc09_implementation_acceptance_record_digest": digest("implementation"),
        "cc09_locator_name_receipt_digest": digest("locator"),
        "cc09_root_registry_ready_commit_digest": digest("ready"),
        "cc08_root_receipt_digest": before_a["root_name_receipt_digest"],
        "cc08_registry_common_genesis_digest": before_a["common_genesis_digest"],
        "cc08_registry_copy_a_snapshot_digest": before_a["semantic_snapshot_digest"],
        "cc08_registry_copy_b_snapshot_digest": before_b["semantic_snapshot_digest"],
        "r05_committed_output_count": 8,
        "cc08_registry_event_count_after_r05": 8,
        "cc08_registry_copy_a_snapshot_digest_after_r05": after_a["semantic_snapshot_digest"],
        "cc08_registry_copy_b_snapshot_digest_after_r05": after_b["semantic_snapshot_digest"],
        "cc08_registry_head_event_digest_after_r05": after_a["head_event_digest"],
        "ordered_r05_output_ids": list(custody.ORDERED_R05_OUTPUT_IDS),
        "held_contract_acceptance_authority_id": (custody._HELD_CONTRACT_ACCEPTANCE_AUTHORITY_ID),
        "held_contract_acceptance_record_digest": (custody._HELD_CONTRACT_ACCEPTANCE_RECORD_DIGEST),
        "held_dispatch_acceptance_authority_id": (custody._HELD_DISPATCH_ACCEPTANCE_AUTHORITY_ID),
        "held_dispatch_acceptance_record_digest": (custody._HELD_DISPATCH_ACCEPTANCE_RECORD_DIGEST),
        "pre_root_expectation_digest": custody._PRE_ROOT_EXPECTATION_DIGEST,
        "effective_root_name_receipt_digest": before_a["root_name_receipt_digest"],
        "r05_rehome_manifest_digest": digest("rehome"),
        "candidate_state": (
            "CANDIDATE_PENDING_INDEPENDENT_REVIEW_SAME_SHA_CI_AND_PRINCIPAL_ACCEPTANCE"
        ),
        "created_at_utc": "2026-08-28T00:00:00.000001Z",
    }
    candidate["record_digest"] = custody.typed_digest(custody.ADDENDUM_SCHEMA, candidate)
    candidate_sha = "a" * 40
    trusted: custody.JsonObject = {
        "accepted_addendum_sha": candidate_sha,
        "accepted_addendum_tree": "b" * 40,
        "accepted_addendum_path": (
            "docs/operations/P3_P7_D02_R2_ACTUAL_ROOT_DIGEST_BINDING_ADDENDUM.json"
        ),
        "accepted_addendum_git_blob_oid": "c" * 40,
        "accepted_addendum_file_sha256": digest("addendum-bytes"),
        "accepted_addendum_record_digest": candidate["record_digest"],
        "accepted_plan_acceptance_record_digest": candidate["cc09_plan_acceptance_record_digest"],
        "locator_custody_implementation_acceptance_record_digest": candidate[
            "cc09_implementation_acceptance_record_digest"
        ],
    }
    acceptance: custody.JsonObject = {
        "schema_version": custody.ADDENDUM_ACCEPTANCE_SCHEMA,
        "authority_id": "P3_P7_D02_R2_ACTUAL_ROOT_DIGEST_BINDING_ADDENDUM_ACCEPTANCE_01",
        "change_control_id": "P3_P7_D02_CC_09",
        **trusted,
        "independent_review": {
            "evidence_digest": digest("addendum-review"),
            "findings_p0": 0,
            "findings_p1": 0,
            "findings_p2": 0,
            "findings_p3": 0,
            "result": "PASS",
            "review_task_id": "CC09_ADDENDUM_REVIEW",
            "reviewed_addendum_sha": candidate_sha,
        },
        "same_sha_ci": {
            "artifact_manifest_digest": digest("addendum-CI"),
            "head_sha": candidate_sha,
            "provider": "GITHUB_ACTIONS",
            "repository": "yangyy816/project-mirror",
            "required_jobs": ["quality-and-integration", "secret-scan", "docker-validation"],
            "result": "PASS",
            "run_id": 1,
            "workflow_identity": ".github/workflows/ci.yml",
        },
        "principal_acceptance": {
            "status": "PRINCIPAL_ACCEPTED",
            "accepted_addendum_sha": candidate_sha,
            "accepted_at_utc": "2026-08-28T00:00:00.000001Z",
            "acceptance_authority_digest": digest("addendum-principal"),
        },
        "authorized_scope": "SUPERSEDE_HELD_ROOT_DIGEST_INPUT_BINDING_ONLY",
        "prohibited_scope": [
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
        ],
        "effective_state": "ACTUAL_ROOT_BINDING_ACCEPTED",
        "record_created_at_utc": "2026-08-28T00:00:00.000001Z",
    }
    acceptance = resign(custody.ADDENDUM_ACCEPTANCE_SCHEMA, acceptance)
    return (
        candidate,
        acceptance,
        trusted_bindings(acceptance, custody.ADDENDUM_ACCEPTANCE_TEST_ANCHOR_ID),
        before_a,
        before_b,
        after_a,
        after_b,
    )


def test_actual_root_addendum_rejects_fully_resigned_nested_and_git_binding_attacks() -> None:
    candidate, acceptance, trusted, before_a, before_b, after_a, after_b = (
        actual_root_addendum_records()
    )
    snapshot_args = {
        "registry_copy_a_snapshot_before_r05": before_a,
        "registry_copy_b_snapshot_before_r05": before_b,
        "registry_copy_a_snapshot_after_r05": after_a,
        "registry_copy_b_snapshot_after_r05": after_b,
    }
    custody.validate_actual_root_addendum(
        candidate, acceptance, expected_bindings=trusted, **snapshot_args
    )
    for path, replacement in (
        (("independent_review", "findings_p0"), False),
        (("same_sha_ci",), "self-attested"),
        (("principal_acceptance", "accepted_addendum_sha"), "d" * 40),
        (("accepted_addendum_git_blob_oid",), "e" * 40),
    ):
        altered = copy.deepcopy(acceptance)
        target: custody.JsonObject = altered
        for key in path[:-1]:
            item = target[key]
            assert isinstance(item, dict)
            target = item
        target[path[-1]] = replacement
        resign(custody.ADDENDUM_ACCEPTANCE_SCHEMA, altered)
        with pytest.raises(custody.LocatorCustodyError):
            custody.validate_actual_root_addendum(
                candidate, altered, expected_bindings=trusted, **snapshot_args
            )


def test_actual_root_snapshots_reject_extra_keys_contract_drift_copy_swap_and_wrong_order() -> None:
    candidate, acceptance, trusted, before_a, before_b, after_a, after_b = (
        actual_root_addendum_records()
    )

    extra = copy.deepcopy(after_a)
    extra["registry_copy_id"] = "COPY_A"
    with pytest.raises(custody.LocatorCustodyError, match="MIGRATION_ROOT_BINDING_HELD_STOP"):
        custody.canonical_registry_snapshot_projection(extra)

    swapped_before_b = copy.deepcopy(before_b)
    swapped_before_b["root_name_receipt_digest"] = digest("swapped-root")
    swapped_before_b["semantic_snapshot_digest"] = custody.typed_digest(
        custody.REGISTRY_SNAPSHOT_SCHEMA,
        {
            key: value
            for key, value in swapped_before_b.items()
            if key != "semantic_snapshot_digest"
        },
    )
    with pytest.raises(custody.LocatorCustodyError, match="MIGRATION_ROOT_BINDING_HELD_STOP"):
        custody.validate_actual_root_addendum(
            candidate,
            acceptance,
            expected_bindings=trusted,
            registry_copy_a_snapshot_before_r05=before_a,
            registry_copy_b_snapshot_before_r05=swapped_before_b,
            registry_copy_a_snapshot_after_r05=after_a,
            registry_copy_b_snapshot_after_r05=after_b,
        )

    for immutable_key in ("execution_contract_digest", "registry_schema_contract_digest"):
        drift_a = copy.deepcopy(after_a)
        drift_b = copy.deepcopy(after_b)
        for snapshot in (drift_a, drift_b):
            snapshot[immutable_key] = digest(f"drift:{immutable_key}")
            snapshot["semantic_snapshot_digest"] = custody.typed_digest(
                custody.REGISTRY_SNAPSHOT_SCHEMA,
                {
                    key: value
                    for key, value in snapshot.items()
                    if key != "semantic_snapshot_digest"
                },
            )
        drift_candidate = copy.deepcopy(candidate)
        drift_candidate["cc08_registry_copy_a_snapshot_digest_after_r05"] = drift_a[
            "semantic_snapshot_digest"
        ]
        drift_candidate["cc08_registry_copy_b_snapshot_digest_after_r05"] = drift_b[
            "semantic_snapshot_digest"
        ]
        resign(custody.ADDENDUM_SCHEMA, drift_candidate)
        with pytest.raises(custody.LocatorCustodyError, match="MIGRATION_ROOT_BINDING_HELD_STOP"):
            custody.validate_actual_root_addendum(
                drift_candidate,
                acceptance,
                expected_bindings=trusted,
                registry_copy_a_snapshot_before_r05=before_a,
                registry_copy_b_snapshot_before_r05=before_b,
                registry_copy_a_snapshot_after_r05=drift_a,
                registry_copy_b_snapshot_after_r05=drift_b,
            )

    wrong_order_a = copy.deepcopy(after_a)
    wrong_order_b = copy.deepcopy(after_b)
    for snapshot in (wrong_order_a, wrong_order_b):
        rows = cast(list[custody.Json], snapshot["ordered_events"])
        first = cast(dict[str, custody.Json], rows[0])
        second = cast(dict[str, custody.Json], rows[1])
        first["output_id"], second["output_id"] = second["output_id"], first["output_id"]
        snapshot["semantic_snapshot_digest"] = custody.typed_digest(
            custody.REGISTRY_SNAPSHOT_SCHEMA,
            {key: value for key, value in snapshot.items() if key != "semantic_snapshot_digest"},
        )
    with pytest.raises(custody.LocatorCustodyError, match="MIGRATION_ROOT_BINDING_HELD_STOP"):
        custody.validate_actual_root_addendum(
            candidate,
            acceptance,
            expected_bindings=trusted,
            registry_copy_a_snapshot_before_r05=before_a,
            registry_copy_b_snapshot_before_r05=before_b,
            registry_copy_a_snapshot_after_r05=wrong_order_a,
            registry_copy_b_snapshot_after_r05=wrong_order_b,
        )


def test_cc09_e5_wire_records_are_closed_and_resigned_drift_stops() -> None:
    contract = custody.project_code_checkout_resolver_contract()
    assert custody.validate_project_code_checkout_resolver_contract(
        contract
    ) == custody.typed_digest(custody.CODE_CHECKOUT_RESOLVER_SCHEMA, contract)
    for schema in custody._CC09_RECORD_FIELDS:
        record = cc09_record(schema)
        assert custody.validate_cc09_record(schema, record, bindings=bindings(record)) in {
            record.get("receipt_digest"),
            record.get("record_digest"),
        }
        resigned = dict(record)
        key = next(
            key
            for key in resigned
            if key.endswith("_digest") and key not in {"receipt_digest", "record_digest"}
        )
        resigned[key] = digest("fully-resigned-attack")
        terminal = "receipt_digest" if "receipt_digest" in resigned else "record_digest"
        resigned[terminal] = custody.typed_digest(
            schema, {k: v for k, v in resigned.items() if k != terminal}
        )
        with pytest.raises(custody.LocatorCustodyError, match="CC09_ACCEPTED_BINDING_DRIFT_STOP"):
            custody.validate_cc09_record(schema, resigned, bindings=bindings(record))
    with pytest.raises(custody.LocatorCustodyError, match="CODE_CHECKOUT_PARTIAL_OR_CORRUPT_STOP"):
        custody.validate_project_code_checkout_resolver_contract({**contract, "network": "ALLOWED"})


def test_private_home_is_only_two_durable_prefixes_and_never_adopts() -> None:
    container = cc09_record(custody.PROJECT_CONTAINER_RECEIPT_SCHEMA)
    private = cc09_record(custody.PRIVATE_HOME_RECEIPT_SCHEMA)
    store = custody.SyntheticCc09BootstrapStore()
    assert (
        custody.bootstrap_private_home(
            store,
            container_receipt=container,
            private_home_receipt=private,
            container_bindings=bindings(container),
            private_home_bindings=bindings(private),
        )
        == "PRIVATE_HOME_CREATED"
    )
    assert store.mutations == [
        "CREATE:ProjectMirror",
        "RECEIPT:ProjectMirror",
        "CREATE:principal-private-output-v1",
        "RECEIPT:principal-private-output-v1",
    ]
    assert (
        custody.bootstrap_private_home(
            store,
            container_receipt=container,
            private_home_receipt=private,
            container_bindings=bindings(container),
            private_home_bindings=bindings(private),
        )
        == "PRIVATE_HOME_REPLAYED"
    )
    for name, receipt in (("ProjectMirror", None), ("principal-private-output-v1", None)):
        attacked = custody.SyntheticCc09BootstrapStore(
            components={
                name: custody.SyntheticCc09Component(identity_digest=digest(name), receipt=receipt)
            }
        )
        with pytest.raises(custody.LocatorCustodyError):
            custody.bootstrap_private_home(
                attacked,
                container_receipt=container,
                private_home_receipt=private,
                container_bindings=bindings(container),
                private_home_bindings=bindings(private),
            )
    reversed_store = custody.SyntheticCc09BootstrapStore(
        components={
            "principal-private-output-v1": custody.SyntheticCc09Component(
                identity_digest=digest("home"), receipt=private
            )
        }
    )
    with pytest.raises(custody.LocatorCustodyError, match="PRIVATE_HOME_DIRECTORY_ONLY_STOP"):
        custody.bootstrap_private_home(
            reversed_store,
            container_receipt=container,
            private_home_receipt=private,
            container_bindings=bindings(container),
            private_home_bindings=bindings(private),
        )


def test_code_checkout_and_scratch_are_create_new_sealed_and_cleanup_only() -> None:
    cache, seal = (
        cc09_record(custody.CODE_CACHE_RECEIPT_SCHEMA),
        cc09_record(custody.R06_CHECKOUT_SEAL_SCHEMA),
    )
    store = custody.SyntheticCc09BootstrapStore()
    assert (
        custody.bootstrap_code_cache_checkout(
            store,
            cache_receipt=cache,
            seal_receipt=seal,
            cache_bindings=bindings(cache),
            seal_bindings=bindings(seal),
        )
        == "CHECKOUT_SEALED"
    )
    assert (
        custody.bootstrap_code_cache_checkout(
            store,
            cache_receipt=cache,
            seal_receipt=seal,
            cache_bindings=bindings(cache),
            seal_bindings=bindings(seal),
        )
        == "CHECKOUT_REPLAYED"
    )
    store.checkout["origin"] = True
    with pytest.raises(custody.LocatorCustodyError, match="CODE_CHECKOUT_PARTIAL_OR_CORRUPT_STOP"):
        custody.bootstrap_code_cache_checkout(
            store,
            cache_receipt=cache,
            seal_receipt=seal,
            cache_bindings=bindings(cache),
            seal_bindings=bindings(seal),
        )
    scratch = cc09_record(custody.BRIDGE_SCRATCH_RECEIPT_SCHEMA)
    clean = custody.SyntheticCc09BootstrapStore()
    assert (
        custody.bootstrap_bridge_scratch(
            clean, scratch_receipt=scratch, scratch_bindings=bindings(scratch)
        )
        == "BRIDGE_SCRATCH_CREATED"
    )

    def successful(env: Mapping[str, str], item: custody.SyntheticCc09Component) -> None:
        assert_temp(env)
        item.payloads.add("child.tmp")

    custody.run_synthetic_bridge_scratch(clean, successful)
    assert clean.components["bridge-scratch-v1"].payloads == set()

    def failing(_env: object, item: custody.SyntheticCc09Component) -> None:
        item.payloads.add("exception.tmp")
        raise RuntimeError("child failure")

    with pytest.raises(custody.LocatorCustodyError, match="BRIDGE_SCRATCH_RESIDUE_STOP"):
        custody.run_synthetic_bridge_scratch(clean, failing)
    assert clean.components["bridge-scratch-v1"].payloads == {"exception.tmp"}
    clean.components["bridge-scratch-v1"].payloads.add("residue")
    with pytest.raises(custody.LocatorCustodyError, match="BRIDGE_SCRATCH_RESIDUE_STOP"):
        custody.run_synthetic_bridge_scratch(clean, lambda _env, _item: None)


def assert_temp(env: Mapping[str, str]) -> None:
    assert env == {"TEMP": "receipt-bound-bridge-scratch", "TMP": "receipt-bound-bridge-scratch"}


@pytest.mark.parametrize("attack", ("invalid_receipt", "dacl_drift", "replacement"))
def test_scratch_replays_physical_receipt_identity_and_dacl_before_child(attack: str) -> None:
    scratch = cc09_record(custody.BRIDGE_SCRATCH_RECEIPT_SCHEMA)
    store = custody.SyntheticCc09BootstrapStore()
    custody.bootstrap_bridge_scratch(
        store, scratch_receipt=scratch, scratch_bindings=bindings(scratch)
    )
    component = store.components["bridge-scratch-v1"]
    if attack == "invalid_receipt":
        component.receipt = {}
    elif attack == "dacl_drift":
        component.protected_dacl = False
    else:
        component.replaced = True
    called = False

    def child(_env: Mapping[str, str], _item: custody.SyntheticCc09Component) -> None:
        nonlocal called
        called = True

    with pytest.raises(custody.LocatorCustodyError, match="BRIDGE_SCRATCH_RESIDUE_STOP"):
        custody.run_synthetic_bridge_scratch(store, child)
    assert not called


@pytest.mark.parametrize("attack", ("receipt", "identity", "dacl", "replacement"))
def test_scratch_post_child_controls_replay_before_cleanup_preserves_payload(attack: str) -> None:
    scratch = cc09_record(custody.BRIDGE_SCRATCH_RECEIPT_SCHEMA)
    store = custody.SyntheticCc09BootstrapStore()
    custody.bootstrap_bridge_scratch(
        store, scratch_receipt=scratch, scratch_bindings=bindings(scratch)
    )
    component = store.components["bridge-scratch-v1"]

    def child(_env: Mapping[str, str], item: custody.SyntheticCc09Component) -> None:
        item.payloads.add("child-residue")
        if attack == "receipt":
            item.receipt = {}
        elif attack == "identity":
            item.identity_digest = digest("replacement-identity")
        elif attack == "dacl":
            item.protected_dacl = False
        else:
            item.replaced = True

    with pytest.raises(custody.LocatorCustodyError, match="BRIDGE_SCRATCH_RESIDUE_STOP"):
        custody.run_synthetic_bridge_scratch(store, child)
    assert component.payloads == {"child-residue"}
    assert "CLEANUP:bridge-scratch-v1" not in store.mutations


def test_scratch_cleanup_failure_preserves_payload_and_success_replays_receipt_only() -> None:
    scratch = cc09_record(custody.BRIDGE_SCRATCH_RECEIPT_SCHEMA)
    store = custody.SyntheticCc09BootstrapStore()
    custody.bootstrap_bridge_scratch(
        store, scratch_receipt=scratch, scratch_bindings=bindings(scratch)
    )
    component = store.components["bridge-scratch-v1"]
    component.cleanup_succeeds = False

    def leave_cleanup_failure(
        _env: Mapping[str, str], item: custody.SyntheticCc09Component
    ) -> None:
        item.payloads.add("cleanup-failure")

    with pytest.raises(custody.LocatorCustodyError, match="BRIDGE_SCRATCH_RESIDUE_STOP"):
        custody.run_synthetic_bridge_scratch(store, leave_cleanup_failure)
    assert component.payloads == {"cleanup-failure"}
    assert "CLEANUP:bridge-scratch-v1" not in store.mutations
    component.cleanup_succeeds = True
    component.payloads.clear()

    def leave_success(_env: Mapping[str, str], item: custody.SyntheticCc09Component) -> None:
        item.payloads.add("success")

    custody.run_synthetic_bridge_scratch(store, leave_success)
    assert component.payloads == set()
    assert store.mutations[-1] == "CLEANUP:bridge-scratch-v1"


def test_e6a_worktree_set_is_sorted_unique_and_resigned_shape_is_not_accepted() -> None:
    record = custody.make_excluded_git_worktree_identity_set(
        {
            "schema_version": custody.WORKTREE_SCHEMA,
            "enumeration_method": "git-worktree-list-porcelain-z-v1",
            "repository_common_dir_identity_digest": digest("common"),
            "ordered_worktree_identity_digests": sorted([digest("a"), digest("b")]),
        }
    )
    assert (
        custody.validate_excluded_git_worktree_identity_set(record)["set_digest"]
        == record["set_digest"]
    )
    bad = dict(record)
    ordered = record["ordered_worktree_identity_digests"]
    assert isinstance(ordered, list)
    bad["ordered_worktree_identity_digests"] = list(reversed(ordered))
    bad["set_digest"] = custody.typed_digest(
        custody.WORKTREE_SCHEMA, {key: value for key, value in bad.items() if key != "set_digest"}
    )
    with pytest.raises(custody.LocatorCustodyError, match="CUSTODY_WORKTREE_SET_STOP"):
        custody.validate_excluded_git_worktree_identity_set(bad)


def test_e6a_transaction_matrix_rejects_unknown_decision() -> None:
    event, intent = custody.make_transaction(
        namespace_receipt_digest=digest("namespace"),
        locator_name_receipt_digest=digest("locator"),
        locator_authority_id="AUTH",
        allocation_id="ALLOC",
        evidence_root_id="ROOT",
        root_basename="root",
        opaque_locator="pmhome1:YWJj",
        locator_digest=digest("opaque"),
        sequence=2,
        previous_event_digest=digest("previous"),
        decision="CREATE_NEW",
        authority_state="ROOT_RECEIPT_DURABLE",
        transition_at_utc="2026-08-28T00:00:00.000001Z",
        root_receipt_created_at_utc="2026-08-28T00:00:00.000001Z",
        root_fields={
            "accepted_cc08_plan_sha": "a" * 40,
            "accepted_cc08_plan_tree": "b" * 40,
            "registry_implementation_sha": "c" * 40,
            "registry_implementation_tree": "d" * 40,
            "registry_implementation_acceptance_record_digest": digest("r"),
            "registry_implementation_acceptance_authority_digest": digest("aa"),
            "parent_identity_digest": digest("p"),
            "excluded_worktree_set_digest": digest("w"),
            "root_identity_digest": digest("root"),
            "root_receipt_digest": digest("receipt"),
            "root_registry_state": "NOT_INITIALIZED",
            "root_registry_common_genesis_digest": None,
            "root_registry_copy_a_snapshot_digest": None,
            "root_registry_copy_b_snapshot_digest": None,
        },
        copy_a_prior_snapshot_digest=digest("a"),
        copy_b_prior_snapshot_digest=digest("a"),
    )
    custody.validate_transition(event, intent)


def test_e6a_opaque_locator_is_relative_locator_bytes_not_locator_json() -> None:
    locator: custody.JsonObject = {
        "private_home_handle_id": "PM_HOME",
        "destination_class": "D02_R2_EVIDENCE_ROOT",
        "normalized_relative_locator": "d02-r2-evidence/p3-p7-d02-r2-cc08-e1-evidence",
        "evidence_root_id": "ROOT",
        "root_basename": "evidence",
    }
    opaque = custody.opaque_locator_for(locator)
    assert opaque == "pmhome1:" + custody._b64(b"d02-r2-evidence/p3-p7-d02-r2-cc08-e1-evidence")
    relative = locator["normalized_relative_locator"]
    assert isinstance(relative, str)
    assert custody._unb64(opaque.removeprefix("pmhome1:")) == relative.encode()


type LocatorLedgerRecords = tuple[
    custody.SyntheticLocatorCustodyLedger,
    custody.JsonObject,
    custody.JsonObject,
    custody.JsonObject,
    custody.JsonObject,
    custody.JsonObject,
    custody.JsonObject,
    custody.JsonObject,
    custody.JsonObject,
]


def synthetic_bootstrap_authority() -> tuple[
    custody.TrustedAcceptanceBindingSource,
    custody.TrustedAcceptanceBindingSource,
    custody.LocatorBootstrapAuthorityAnchor,
]:
    plan = json.loads(
        (
            Path(__file__).parents[3]
            / "docs/operations/P3_P7_D02_R2_LOCATOR_CUSTODY_PLAN_ACCEPTANCE.json"
        ).read_text()
    )
    implementation = implementation_acceptance(plan)
    private_candidate = cc09_record(custody.PRIVATE_HOME_CANDIDATE_SCHEMA)
    _, private_source = candidate_acceptance(
        schema=custody.PRIVATE_HOME_ACCEPTANCE_SCHEMA,
        candidate=private_candidate,
        private_home=True,
    )
    implementation_source = trusted_bindings(
        implementation, custody.IMPLEMENTATION_ACCEPTANCE_TEST_ANCHOR_ID
    )
    return (
        implementation_source,
        private_source,
        custody.load_locator_bootstrap_authority_anchor(
            implementation_acceptance=implementation_source,
            private_home_acceptance=private_source,
        ),
    )


def locator_ledger_records(tmp_path: Path) -> LocatorLedgerRecords:
    created_at = "2026-08-28T00:00:00.000001Z"
    implementation_source, private_home_source, anchor = synthetic_bootstrap_authority()
    copy_a_id = custody._COPY_A_ID
    copy_b_id = custody._COPY_B_ID
    namespace = custody.make_namespace_name_receipt(
        {
            "schema_version": custody.NAMESPACE_SCHEMA,
            "project_id": "PROJECT_MIRROR",
            "private_home_handle_id": "PM_PROJECT_MIRROR_PRIVATE_HOME_V1",
            "custody_namespace_id": custody._CUSTODY_NAMESPACE_ID,
            "purpose": "D02_R2_SINGLE_ROOT_LOCATOR_CUSTODY_ONLY",
            "change_control_id": "P3_P7_D02_CC_09",
            "authority_id": "P3_P7_D02_R2_LOCATOR_CUSTODY_AUTHORITY_01",
            "allowed_subject_root_ids": ["P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT"],
            "resolver_contract_digest": digest("resolver"),
            "host_binding_acceptance_record_digest": (anchor.host_binding_acceptance_record_digest),
            "private_home_binding_acceptance_record_digest": (
                anchor.private_home_binding_acceptance_record_digest
            ),
            "principal_sid_digest": digest("sid"),
            "known_folder_identity_digest": digest("known-folder"),
            "private_home_identity_digest": digest("private-home"),
            "copy_a_id": copy_a_id,
            "copy_b_id": copy_b_id,
            "namespace_first_object_logical_name": custody._NAMESPACE_FILE,
            "copy_common_genesis_schema_version": custody.COMMON_GENESIS_SCHEMA,
            "copy_genesis_receipt_schema_version": custody.COPY_GENESIS_SCHEMA,
            "locator_name_receipt_schema_version": custody.LOCATOR_RECEIPT_SCHEMA,
            "event_schema_version": custody.EVENT_SCHEMA,
            "intent_schema_version": custody.INTENT_SCHEMA,
            "commit_schema_version": custody.COMMIT_SCHEMA,
            "snapshot_schema_version": custody.SNAPSHOT_SCHEMA,
            "transaction_id_schema_version": custody.TRANSACTION_ID_SCHEMA,
            "locator_schema_version": custody.LOCATOR_SCHEMA,
            "path_identity_schema_version": custody.PATH_IDENTITY_SCHEMA,
            "worktree_set_schema_version": custody.WORKTREE_SCHEMA,
            "canonicalization_version": "demo-canonical-json-v1",
            "relative_control_manifest": [dict(row) for row in custody.RELATIVE_CONTROL_MANIFEST],
            "locator_custody_implementation_sha": anchor.implementation_sha,
            "locator_custody_implementation_acceptance_record_digest": (
                anchor.implementation_acceptance_record_digest
            ),
            "retention_policy": "RETAIN_UNTIL_D02_R2_AND_ALL_DEPENDENT_TASKS_RELEASE_CUSTODY",
            "cleanup_policy": "PRINCIPAL_EXACT_DEPENDENCY_SCAN_AND_FORWARD_CHANGE_CONTROL_REQUIRED",
            "created_at_utc": created_at,
        }
    )
    common = custody.make_common_genesis(
        {
            "schema_version": custody.COMMON_GENESIS_SCHEMA,
            "namespace_receipt_digest": namespace["receipt_digest"],
            "locator_authority_id": custody._CUSTODY_AUTHORITY_ID,
            "allocation_id": custody._ALLOCATION,
            "evidence_root_id": "P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT",
            "root_basename": "p3-p7-d02-r2-cc08-e1-evidence",
            "initial_sequence": 0,
            "initial_authority_state": None,
        }
    )
    common_digest = custody.validate_common_genesis(common)
    copy_a = custody.make_copy_genesis(
        {
            "schema_version": custody.COPY_GENESIS_SCHEMA,
            "namespace_receipt_digest": namespace["receipt_digest"],
            "locator_authority_id": common["locator_authority_id"],
            "allocation_id": common["allocation_id"],
            "evidence_root_id": common["evidence_root_id"],
            "root_basename": common["root_basename"],
            "copy_id": copy_a_id,
            "peer_copy_id": copy_b_id,
            "common_genesis_digest": common_digest,
            "created_at_utc": created_at,
        }
    )
    copy_b = custody.make_copy_genesis(
        {
            **{key: value for key, value in copy_a.items() if key != "genesis_receipt_digest"},
            "copy_id": copy_b_id,
            "peer_copy_id": copy_a_id,
        }
    )
    locator_fields: custody.JsonObject = {
        "private_home_handle_id": namespace["private_home_handle_id"],
        "destination_class": "D02_R2_EVIDENCE_ROOT",
        "normalized_relative_locator": "d02-r2-evidence/p3-p7-d02-r2-cc08-e1-evidence",
        "evidence_root_id": common["evidence_root_id"],
        "root_basename": common["root_basename"],
    }
    locator_digest = custody.validate_evidence_root_locator(locator_fields)
    locator = custody.make_locator_name_receipt(
        {
            "schema_version": custody.LOCATOR_RECEIPT_SCHEMA,
            "namespace_receipt_digest": namespace["receipt_digest"],
            "locator_authority_id": common["locator_authority_id"],
            "allocation_id": common["allocation_id"],
            "evidence_root_id": common["evidence_root_id"],
            "root_basename": common["root_basename"],
            "semantic_role": "CC08_SINGLE_EVIDENCE_ROOT_LOCATOR",
            **locator_fields,
            "opaque_locator_scheme": "pmhome1",
            "opaque_locator": custody.opaque_locator_for(locator_fields),
            "locator_digest": locator_digest,
            "allowed_principal_tasks": [
                "P3_P7_D02_R2_EXECUTION_01",
                "P3_P7_D02_R2_EVIDENCE_REVIEW_01",
                "P3_P7_D02_R2_R05_DURABILITY_01",
            ],
            "accepted_cc08_plan_sha": custody._CC08_PLAN_SHA,
            "accepted_cc08_plan_tree": custody._CC08_PLAN_TREE,
            "registry_implementation_sha": custody._R06_SHA,
            "registry_implementation_tree": custody._R06_TREE,
            "registry_implementation_acceptance_record_digest": custody._R06_ACCEPTANCE_DIGEST,
            "registry_implementation_acceptance_authority_digest": (
                custody._R06_ACCEPTANCE_AUTHORITY_DIGEST
            ),
            "maximum_bytes": 42_949_672_960,
            "retention": "RETAIN_UNTIL_D02_R2_AND_ALL_DEPENDENT_TASKS_RELEASE_CUSTODY",
            "allocated_at_utc": created_at,
        }
    )
    ledger = custody.SyntheticLocatorCustodyLedger(
        tmp_path / "locator-custody",
        implementation_source,
        private_home_source,
    )
    assert ledger.bootstrap(namespace, common, copy_a, copy_b, locator) == (
        "LOCATOR_CUSTODY_BOOTSTRAPPED"
    )
    prior = custody.make_semantic_snapshot(
        {
            "schema_version": custody.SNAPSHOT_SCHEMA,
            "namespace_receipt_digest": namespace["receipt_digest"],
            "locator_authority_id": common["locator_authority_id"],
            "allocation_id": common["allocation_id"],
            "evidence_root_id": common["evidence_root_id"],
            "common_genesis_digest": common_digest,
            "event_count": 0,
            "head_event_digest": common_digest,
            "ordered_event_digests": [],
            "authority_state": None,
        }
    )
    root_fields: dict[str, str | None] = {
        "accepted_cc08_plan_sha": cast(str, locator["accepted_cc08_plan_sha"]),
        "accepted_cc08_plan_tree": cast(str, locator["accepted_cc08_plan_tree"]),
        "registry_implementation_sha": cast(str, locator["registry_implementation_sha"]),
        "registry_implementation_tree": cast(str, locator["registry_implementation_tree"]),
        "registry_implementation_acceptance_record_digest": cast(
            str, locator["registry_implementation_acceptance_record_digest"]
        ),
        "registry_implementation_acceptance_authority_digest": cast(
            str, locator["registry_implementation_acceptance_authority_digest"]
        ),
        "parent_identity_digest": digest("parent"),
        "excluded_worktree_set_digest": digest("worktrees-1"),
        "root_identity_digest": None,
        "root_receipt_digest": None,
        "root_registry_state": None,
        "root_registry_common_genesis_digest": None,
        "root_registry_copy_a_snapshot_digest": None,
        "root_registry_copy_b_snapshot_digest": None,
    }
    event, intent = custody.make_transaction(
        namespace_receipt_digest=cast(str, namespace["receipt_digest"]),
        locator_name_receipt_digest=cast(str, locator["name_receipt_digest"]),
        locator_authority_id=cast(str, common["locator_authority_id"]),
        allocation_id=cast(str, common["allocation_id"]),
        evidence_root_id=cast(str, common["evidence_root_id"]),
        root_basename=cast(str, common["root_basename"]),
        opaque_locator=cast(str, locator["opaque_locator"]),
        locator_digest=cast(str, locator["locator_digest"]),
        sequence=1,
        previous_event_digest=common_digest,
        decision="CREATE_NEW",
        authority_state="PREPARED",
        transition_at_utc=created_at,
        root_receipt_created_at_utc=created_at,
        root_fields=root_fields,
        copy_a_prior_snapshot_digest=cast(str, prior["semantic_snapshot_digest"]),
        copy_b_prior_snapshot_digest=cast(str, prior["semantic_snapshot_digest"]),
    )
    return ledger, namespace, common, copy_a, copy_b, locator, prior, event, intent


def replay_locator_ledger(
    ledger: custody.SyntheticLocatorCustodyLedger,
    namespace: custody.JsonObject,
    common: custody.JsonObject,
    copy_a: custody.JsonObject,
    copy_b: custody.JsonObject,
    locator: custody.JsonObject,
) -> tuple[custody.JsonObject, custody.JsonObject]:
    return ledger.replay(
        namespace_receipt=namespace,
        locator_receipt=locator,
        common_genesis=common,
        copy_a_genesis=copy_a,
        copy_b_genesis=copy_b,
    )


def test_locator_bootstrap_rejects_caller_constructed_anchor_and_resigned_swaps_before_write(
    tmp_path: Path,
) -> None:
    ledger, namespace, common, copy_a, copy_b, locator, _, _, _ = locator_ledger_records(tmp_path)
    forged_anchor = custody.LocatorBootstrapAuthorityAnchor(
        implementation_sha="9" * 40,
        implementation_acceptance_record_digest=digest("forged-implementation"),
        host_binding_acceptance_record_digest=digest("forged-host"),
        private_home_binding_acceptance_record_digest=digest("forged-home"),
        authority_created_at_utc="2026-08-28T00:00:00.000001Z",
        _token=custody._BOOTSTRAP_AUTHORITY_ANCHOR_TOKEN,
    )
    forged_root = tmp_path / "forged-anchor-root"
    forged_ledger = custody.SyntheticLocatorCustodyLedger(
        forged_root,
        cast(custody.TrustedAcceptanceBindingSource, forged_anchor),
        ledger.bootstrap_private_home_acceptance,
    )
    with pytest.raises(
        custody.LocatorCustodyError, match="CUSTODY_BOOTSTRAP_AUTHORITY_ANCHOR_REQUIRED_STOP"
    ):
        forged_ledger.bootstrap(namespace, common, copy_a, copy_b, locator)
    assert not forged_root.exists()
    assert forged_ledger.mutations == []

    swapped_namespace = copy.deepcopy(namespace)
    swapped_namespace["copy_a_id"], swapped_namespace["copy_b_id"] = (
        swapped_namespace["copy_b_id"],
        swapped_namespace["copy_a_id"],
    )
    swapped_namespace["receipt_digest"] = custody.typed_digest(
        custody.NAMESPACE_SCHEMA,
        {key: value for key, value in swapped_namespace.items() if key != "receipt_digest"},
    )
    swap_root = tmp_path / "copy-swap-root"
    swap_ledger = custody.SyntheticLocatorCustodyLedger(
        swap_root,
        ledger.bootstrap_implementation_acceptance,
        ledger.bootstrap_private_home_acceptance,
    )
    with pytest.raises(
        custody.LocatorCustodyError, match="CUSTODY_BOOTSTRAP_AUTHORITY_MISMATCH_STOP"
    ):
        swap_ledger.bootstrap(swapped_namespace, common, copy_a, copy_b, locator)
    assert not swap_root.exists()
    assert swap_ledger.mutations == []

    swapped_common = copy.deepcopy(common)
    swapped_common["evidence_root_id"] = "P3_P7_D02_R2_CC08_E2_FORGED_ROOT"
    swapped_common = custody.make_common_genesis(swapped_common)
    root_swap = tmp_path / "root-swap-root"
    root_swap_ledger = custody.SyntheticLocatorCustodyLedger(
        root_swap,
        ledger.bootstrap_implementation_acceptance,
        ledger.bootstrap_private_home_acceptance,
    )
    with pytest.raises(
        custody.LocatorCustodyError, match="CUSTODY_BOOTSTRAP_AUTHORITY_MISMATCH_STOP"
    ):
        root_swap_ledger.bootstrap(namespace, swapped_common, copy_a, copy_b, locator)
    assert not root_swap.exists()
    assert root_swap_ledger.mutations == []


def make_followup_locator_transaction(
    *,
    sequence: int,
    namespace: custody.JsonObject,
    common: custody.JsonObject,
    locator: custody.JsonObject,
    prior: custody.JsonObject,
    first_event: custody.JsonObject,
) -> tuple[custody.JsonObject, custody.JsonObject]:
    if sequence not in {2, 3}:
        raise AssertionError("follow-up sequence must be 2 or 3")
    root_fields: dict[str, str | None] = {
        "accepted_cc08_plan_sha": cast(str, first_event["accepted_cc08_plan_sha"]),
        "accepted_cc08_plan_tree": cast(str, first_event["accepted_cc08_plan_tree"]),
        "registry_implementation_sha": cast(str, first_event["registry_implementation_sha"]),
        "registry_implementation_tree": cast(str, first_event["registry_implementation_tree"]),
        "registry_implementation_acceptance_record_digest": cast(
            str, first_event["registry_implementation_acceptance_record_digest"]
        ),
        "registry_implementation_acceptance_authority_digest": cast(
            str, first_event["registry_implementation_acceptance_authority_digest"]
        ),
        "parent_identity_digest": cast(str, first_event["parent_identity_digest"]),
        "excluded_worktree_set_digest": digest(f"worktrees-{sequence}"),
        "root_identity_digest": digest("root-identity"),
        "root_receipt_digest": digest("root-receipt"),
        "root_registry_state": "NOT_INITIALIZED" if sequence == 2 else "READY_EMPTY",
        "root_registry_common_genesis_digest": (
            None if sequence == 2 else digest("root-registry-common")
        ),
        "root_registry_copy_a_snapshot_digest": (
            None if sequence == 2 else digest("root-registry-copy-a")
        ),
        "root_registry_copy_b_snapshot_digest": (
            None if sequence == 2 else digest("root-registry-copy-b")
        ),
    }
    return custody.make_transaction(
        namespace_receipt_digest=cast(str, namespace["receipt_digest"]),
        locator_name_receipt_digest=cast(str, locator["name_receipt_digest"]),
        locator_authority_id=cast(str, common["locator_authority_id"]),
        allocation_id=cast(str, common["allocation_id"]),
        evidence_root_id=cast(str, common["evidence_root_id"]),
        root_basename=cast(str, common["root_basename"]),
        opaque_locator=cast(str, locator["opaque_locator"]),
        locator_digest=cast(str, locator["locator_digest"]),
        sequence=sequence,
        previous_event_digest=cast(str, prior["head_event_digest"]),
        decision="CREATE_NEW",
        authority_state="ROOT_RECEIPT_DURABLE" if sequence == 2 else "ROOT_REGISTRY_READY",
        transition_at_utc=f"2026-08-28T00:00:0{sequence - 1}.000001Z",
        root_receipt_created_at_utc=cast(str, first_event["root_receipt_created_at_utc"]),
        root_fields=root_fields,
        copy_a_prior_snapshot_digest=cast(str, prior["semantic_snapshot_digest"]),
        copy_b_prior_snapshot_digest=cast(str, prior["semantic_snapshot_digest"]),
    )


def locator_target_for_sequence(tmp_path: Path, sequence: int) -> LocatorLedgerRecords:
    if sequence not in {1, 2, 3}:
        raise AssertionError("sequence must be in the frozen three-event chain")
    records = locator_ledger_records(tmp_path)
    ledger, namespace, common, copy_a, copy_b, locator, prior, event, intent = records
    first_event = event
    for next_sequence in range(2, sequence + 1):
        assert (
            custody.recover_synthetic_transition(
                ledger,
                event=event,
                intent=intent,
                copy_a_genesis=copy_a,
                copy_b_genesis=copy_b,
                prior_snapshot=prior,
            )
            == "COMMIT_DURABLE"
        )
        prior, replayed_b = replay_locator_ledger(
            ledger, namespace, common, copy_a, copy_b, locator
        )
        assert prior == replayed_b
        event, intent = make_followup_locator_transaction(
            sequence=next_sequence,
            namespace=namespace,
            common=common,
            locator=locator,
            prior=prior,
            first_event=first_event,
        )
    return ledger, namespace, common, copy_a, copy_b, locator, prior, event, intent


@pytest.mark.parametrize(
    "contaminated_relative_path",
    [
        "copy-a/UNKNOWN.json",
        "copy-b/UNKNOWN.json",
        f"allocations/{custody._ALLOCATION}/UNKNOWN.json",
    ],
)
def test_locator_bootstrap_rejects_contaminated_partial_prefix_before_completion(
    tmp_path: Path, contaminated_relative_path: str
) -> None:
    ledger, namespace, common, copy_a, copy_b, locator, _, _, _ = locator_ledger_records(tmp_path)
    for relative_name in (
        f"copy-a/{custody._GENESIS_FILE}",
        f"copy-b/{custody._GENESIS_FILE}",
        f"allocations/{custody._ALLOCATION}/{custody._LOCATOR_FILE}",
    ):
        ledger._path(relative_name).unlink()
    ledger._write(contaminated_relative_path, {"kind": "unknown-bootstrap-object"})
    mutations = list(ledger.mutations)
    with pytest.raises(custody.LocatorCustodyError, match="CUSTODY_BOOTSTRAP_UNKNOWN_STATE_STOP"):
        ledger.bootstrap(namespace, common, copy_a, copy_b, locator)
    assert ledger.mutations == mutations
    assert not ledger._path(f"copy-a/{custody._GENESIS_FILE}").exists()
    assert not ledger._path(f"copy-b/{custody._GENESIS_FILE}").exists()
    assert not ledger._path(f"allocations/{custody._ALLOCATION}/{custody._LOCATOR_FILE}").exists()


@pytest.mark.parametrize(
    ("stop_after", "expected"),
    [
        ("INTENT", "INTENT_DURABLE"),
        ("COPY_A", "COPY_A_DURABLE"),
        ("COPY_B", "COPY_B_DURABLE"),
    ],
)
def test_locator_ledger_recovers_only_three_legal_uncommitted_prefixes(
    tmp_path: Path, stop_after: str, expected: str
) -> None:
    ledger, namespace, common, copy_a, copy_b, locator, prior, event, intent = (
        locator_ledger_records(tmp_path)
    )
    assert (
        custody.recover_synthetic_transition(
            ledger,
            event=event,
            intent=intent,
            copy_a_genesis=copy_a,
            copy_b_genesis=copy_b,
            prior_snapshot=prior,
            stop_after=stop_after,
        )
        == expected
    )
    assert (
        custody.recover_synthetic_transition(
            ledger,
            event=event,
            intent=intent,
            copy_a_genesis=copy_a,
            copy_b_genesis=copy_b,
            prior_snapshot=prior,
        )
        == "COMMIT_DURABLE"
    )
    replayed_a, replayed_b = replay_locator_ledger(
        ledger, namespace, common, copy_a, copy_b, locator
    )
    assert replayed_a == replayed_b
    assert replayed_a["event_count"] == 1
    assert replayed_a["head_event_digest"] == event["event_digest"]


def test_locator_ledger_rejects_b_only_before_any_repair_write(tmp_path: Path) -> None:
    ledger, _, _, copy_a, copy_b, _, prior, event, intent = locator_ledger_records(tmp_path)
    custody.recover_synthetic_transition(
        ledger,
        event=event,
        intent=intent,
        copy_a_genesis=copy_a,
        copy_b_genesis=copy_b,
        prior_snapshot=prior,
        stop_after="INTENT",
    )
    name = custody.event_filename(cast(int, event["sequence"]), cast(str, event["event_digest"]))
    ledger._write(f"copy-b/events/{name}", event)
    mutations = list(ledger.mutations)
    with pytest.raises(custody.LocatorCustodyError, match="LOCATOR_COPY_DIVERGENCE_STOP"):
        custody.recover_synthetic_transition(
            ledger,
            event=event,
            intent=intent,
            copy_a_genesis=copy_a,
            copy_b_genesis=copy_b,
            prior_snapshot=prior,
        )
    assert ledger.mutations == mutations
    assert not ledger._path(f"copy-a/events/{name}").exists()


def test_locator_ledger_rejects_commit_before_both_events(tmp_path: Path) -> None:
    ledger, _, common, copy_a, copy_b, _, prior, event, intent = locator_ledger_records(tmp_path)
    custody.recover_synthetic_transition(
        ledger,
        event=event,
        intent=intent,
        copy_a_genesis=copy_a,
        copy_b_genesis=copy_b,
        prior_snapshot=prior,
        stop_after="INTENT",
    )
    raw = canonical_json_bytes(event)
    expected_post = ledger._snapshot(
        copy_genesis=copy_a,
        common_digest=custody.validate_common_genesis(common),
        ordered_event_digests=[cast(str, event["event_digest"])],
        authority_state=event["authority_state"],
    )
    commit = custody.make_commit_receipt(
        {
            "schema_version": custody.COMMIT_SCHEMA,
            "namespace_receipt_digest": event["namespace_receipt_digest"],
            "locator_name_receipt_digest": event["locator_name_receipt_digest"],
            "locator_authority_id": event["locator_authority_id"],
            "allocation_id": event["allocation_id"],
            "evidence_root_id": event["evidence_root_id"],
            "transaction_id": event["transaction_id"],
            "sequence": event["sequence"],
            "intent_digest": intent["intent_digest"],
            "event_digest": event["event_digest"],
            "copy_a_genesis_receipt_digest": copy_a["genesis_receipt_digest"],
            "copy_b_genesis_receipt_digest": copy_b["genesis_receipt_digest"],
            "copy_a_event_file_sha256": hashlib.sha256(raw).hexdigest(),
            "copy_b_event_file_sha256": hashlib.sha256(raw).hexdigest(),
            "copy_a_snapshot_digest": expected_post["semantic_snapshot_digest"],
            "copy_b_snapshot_digest": expected_post["semantic_snapshot_digest"],
            "commit_created_at_utc": intent["commit_created_at_utc"],
        }
    )
    ledger._write(
        f"transactions/commits/{custody.commit_filename(cast(str, event['transaction_id']))}",
        commit,
    )
    mutations = list(ledger.mutations)
    with pytest.raises(custody.LocatorCustodyError, match="LOCATOR_COPY_DIVERGENCE_STOP"):
        custody.recover_synthetic_transition(
            ledger,
            event=event,
            intent=intent,
            copy_a_genesis=copy_a,
            copy_b_genesis=copy_b,
            prior_snapshot=prior,
        )
    assert ledger.mutations == mutations


@pytest.mark.parametrize("attack", ["UNKNOWN_OBJECT", "SECOND_ALLOCATION", "EXTRA_INTENT"])
def test_locator_ledger_rejects_unknown_layout_before_mutation(tmp_path: Path, attack: str) -> None:
    ledger, _, _, copy_a, copy_b, _, prior, event, intent = locator_ledger_records(tmp_path)
    if attack == "UNKNOWN_OBJECT":
        ledger._write("unexpected.json", {"kind": "unknown"})
    elif attack == "SECOND_ALLOCATION":
        ledger._path("allocations/SECOND_ALLOCATION").mkdir()
    else:
        ledger._write(
            f"transactions/intents/{custody.intent_filename(digest('unrelated-transaction'))}",
            {"kind": "unknown-intent"},
        )
    mutations = list(ledger.mutations)
    with pytest.raises(custody.LocatorCustodyError):
        custody.recover_synthetic_transition(
            ledger,
            event=event,
            intent=intent,
            copy_a_genesis=copy_a,
            copy_b_genesis=copy_b,
            prior_snapshot=prior,
        )
    assert ledger.mutations == mutations


def test_locator_ledger_rejects_sequence_gap_and_a_b_divergence_before_write(
    tmp_path: Path,
) -> None:
    ledger, _, _, copy_a, copy_b, _, prior, event, intent = locator_ledger_records(tmp_path)
    custody.recover_synthetic_transition(
        ledger,
        event=event,
        intent=intent,
        copy_a_genesis=copy_a,
        copy_b_genesis=copy_b,
        prior_snapshot=prior,
        stop_after="INTENT",
    )
    gap_name = custody.event_filename(2, cast(str, event["event_digest"]))
    ledger._write(f"copy-a/events/{gap_name}", event)
    with pytest.raises(custody.LocatorCustodyError, match="LOCATOR_COPY_DIVERGENCE_STOP"):
        custody.recover_synthetic_transition(
            ledger,
            event=event,
            intent=intent,
            copy_a_genesis=copy_a,
            copy_b_genesis=copy_b,
            prior_snapshot=prior,
        )
    ledger._path(f"copy-a/events/{gap_name}").unlink()
    target_name = custody.event_filename(1, cast(str, event["event_digest"]))
    ledger._write(f"copy-a/events/{target_name}", event)
    altered_event = copy.deepcopy(event)
    altered_event["excluded_worktree_set_digest"] = digest("divergent-worktrees")
    altered_event["event_digest"] = custody.typed_digest(
        custody.EVENT_SCHEMA,
        {key: value for key, value in altered_event.items() if key != "event_digest"},
    )
    ledger._write(f"copy-b/events/{target_name}", altered_event)
    with pytest.raises(custody.LocatorCustodyError, match="LOCATOR_COPY_DIVERGENCE_STOP"):
        custody.recover_synthetic_transition(
            ledger,
            event=event,
            intent=intent,
            copy_a_genesis=copy_a,
            copy_b_genesis=copy_b,
            prior_snapshot=prior,
        )


def test_locator_ledger_rejects_resigned_state_skip_before_mutation(tmp_path: Path) -> None:
    ledger, _, _, copy_a, copy_b, _, prior, event, intent = locator_ledger_records(tmp_path)
    altered_event = copy.deepcopy(event)
    altered_intent = copy.deepcopy(intent)
    altered_event["authority_state"] = "ROOT_RECEIPT_DURABLE"
    altered_event["root_identity_digest"] = digest("root")
    altered_event["root_receipt_digest"] = digest("receipt")
    altered_event["root_registry_state"] = "NOT_INITIALIZED"
    transaction_payload = {
        key: altered_event[key]
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
    altered_event["transaction_id"] = custody.typed_digest(
        custody.TRANSACTION_ID_SCHEMA, transaction_payload
    )
    altered_event["event_digest"] = custody.typed_digest(
        custody.EVENT_SCHEMA,
        {key: value for key, value in altered_event.items() if key != "event_digest"},
    )
    altered_raw = canonical_json_bytes(altered_event)
    altered_intent.update(
        {
            "transaction_id": altered_event["transaction_id"],
            "authority_state": altered_event["authority_state"],
            "canonical_event_base64url": custody._b64(altered_raw),
            "canonical_event_sha256": hashlib.sha256(altered_raw).hexdigest(),
            "event_digest": altered_event["event_digest"],
        }
    )
    altered_intent["intent_digest"] = custody.typed_digest(
        custody.INTENT_SCHEMA,
        {key: value for key, value in altered_intent.items() if key != "intent_digest"},
    )
    mutations = list(ledger.mutations)
    with pytest.raises(custody.LocatorCustodyError, match="LOCATOR_COPY_DIVERGENCE_STOP"):
        custody.recover_synthetic_transition(
            ledger,
            event=altered_event,
            intent=altered_intent,
            copy_a_genesis=copy_a,
            copy_b_genesis=copy_b,
            prior_snapshot=prior,
        )
    assert ledger.mutations == mutations


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("namespace_receipt_digest", digest("forged-namespace")),
        ("locator_name_receipt_digest", digest("forged-locator-receipt")),
        ("locator_authority_id", "FORGED_LOCATOR_AUTHORITY"),
        ("allocation_id", "FORGED_ALLOCATION"),
        ("evidence_root_id", "FORGED_EVIDENCE_ROOT"),
    ],
)
def test_locator_ledger_rejects_resigned_intent_event_authority_mismatch_before_mutation(
    tmp_path: Path, field: str, replacement: str
) -> None:
    ledger, _, _, copy_a, copy_b, _, prior, event, intent = locator_ledger_records(tmp_path)
    altered_intent = copy.deepcopy(intent)
    altered_intent[field] = replacement
    altered_intent["intent_digest"] = custody.typed_digest(
        custody.INTENT_SCHEMA,
        {key: value for key, value in altered_intent.items() if key != "intent_digest"},
    )
    mutations = list(ledger.mutations)
    with pytest.raises(custody.LocatorCustodyError, match="LOCATOR_INTENT_PARTIAL_OR_CORRUPT_STOP"):
        custody.recover_synthetic_transition(
            ledger,
            event=event,
            intent=altered_intent,
            copy_a_genesis=copy_a,
            copy_b_genesis=copy_b,
            prior_snapshot=prior,
        )
    assert ledger.mutations == mutations


def test_locator_ledger_rejects_root_timestamp_drift_before_sequence_two_write(
    tmp_path: Path,
) -> None:
    ledger, namespace, common, copy_a, copy_b, locator, prior, event, intent = (
        locator_ledger_records(tmp_path)
    )
    custody.recover_synthetic_transition(
        ledger,
        event=event,
        intent=intent,
        copy_a_genesis=copy_a,
        copy_b_genesis=copy_b,
        prior_snapshot=prior,
    )
    committed, _ = replay_locator_ledger(ledger, namespace, common, copy_a, copy_b, locator)
    root_fields: dict[str, str | None] = {
        "accepted_cc08_plan_sha": cast(str, event["accepted_cc08_plan_sha"]),
        "accepted_cc08_plan_tree": cast(str, event["accepted_cc08_plan_tree"]),
        "registry_implementation_sha": cast(str, event["registry_implementation_sha"]),
        "registry_implementation_tree": cast(str, event["registry_implementation_tree"]),
        "registry_implementation_acceptance_record_digest": cast(
            str, event["registry_implementation_acceptance_record_digest"]
        ),
        "registry_implementation_acceptance_authority_digest": cast(
            str, event["registry_implementation_acceptance_authority_digest"]
        ),
        "parent_identity_digest": cast(str, event["parent_identity_digest"]),
        "excluded_worktree_set_digest": digest("worktrees-2"),
        "root_identity_digest": digest("root-identity"),
        "root_receipt_digest": digest("root-receipt"),
        "root_registry_state": "NOT_INITIALIZED",
        "root_registry_common_genesis_digest": None,
        "root_registry_copy_a_snapshot_digest": None,
        "root_registry_copy_b_snapshot_digest": None,
    }
    event_two, intent_two = custody.make_transaction(
        namespace_receipt_digest=cast(str, namespace["receipt_digest"]),
        locator_name_receipt_digest=cast(str, locator["name_receipt_digest"]),
        locator_authority_id=cast(str, common["locator_authority_id"]),
        allocation_id=cast(str, common["allocation_id"]),
        evidence_root_id=cast(str, common["evidence_root_id"]),
        root_basename=cast(str, common["root_basename"]),
        opaque_locator=cast(str, locator["opaque_locator"]),
        locator_digest=cast(str, locator["locator_digest"]),
        sequence=2,
        previous_event_digest=cast(str, committed["head_event_digest"]),
        decision="CREATE_NEW",
        authority_state="ROOT_RECEIPT_DURABLE",
        transition_at_utc="2026-08-28T00:00:01.000001Z",
        root_receipt_created_at_utc="2026-08-28T00:00:01.000001Z",
        root_fields=root_fields,
        copy_a_prior_snapshot_digest=cast(str, committed["semantic_snapshot_digest"]),
        copy_b_prior_snapshot_digest=cast(str, committed["semantic_snapshot_digest"]),
    )
    mutations = list(ledger.mutations)
    with pytest.raises(custody.LocatorCustodyError, match="LOCATOR_COPY_DIVERGENCE_STOP"):
        custody.recover_synthetic_transition(
            ledger,
            event=event_two,
            intent=intent_two,
            copy_a_genesis=copy_a,
            copy_b_genesis=copy_b,
            prior_snapshot=committed,
        )
    assert ledger.mutations == mutations


@pytest.mark.parametrize("sequence", [1, 2, 3])
@pytest.mark.parametrize(
    ("keep_intent", "keep_copy_a", "keep_copy_b", "keep_commit"),
    [
        (False, False, False, True),
        (False, False, True, False),
        (False, False, True, True),
        (False, True, False, False),
        (False, True, False, True),
        (False, True, True, False),
        (False, True, True, True),
        (True, False, False, True),
        (True, False, True, False),
        (True, False, True, True),
        (True, True, False, True),
    ],
    ids=[
        "commit-only",
        "b-only",
        "b-and-commit",
        "a-only",
        "a-and-commit",
        "a-b-no-intent",
        "a-b-commit-no-intent",
        "intent-commit",
        "intent-b",
        "intent-b-commit",
        "intent-a-commit",
    ],
)
def test_locator_ledger_rejects_every_illegal_physical_stage_before_mutation(
    tmp_path: Path,
    sequence: int,
    keep_intent: bool,
    keep_copy_a: bool,
    keep_copy_b: bool,
    keep_commit: bool,
) -> None:
    ledger, _, _, copy_a, copy_b, _, prior, event, intent = locator_target_for_sequence(
        tmp_path, sequence
    )
    assert (
        custody.recover_synthetic_transition(
            ledger,
            event=event,
            intent=intent,
            copy_a_genesis=copy_a,
            copy_b_genesis=copy_b,
            prior_snapshot=prior,
        )
        == "COMMIT_DURABLE"
    )
    transaction_id = cast(str, event["transaction_id"])
    event_name = custody.event_filename(sequence, cast(str, event["event_digest"]))
    physical = (
        (
            keep_intent,
            ledger._path(f"transactions/intents/{custody.intent_filename(transaction_id)}"),
        ),
        (keep_copy_a, ledger._path(f"copy-a/events/{event_name}")),
        (keep_copy_b, ledger._path(f"copy-b/events/{event_name}")),
        (
            keep_commit,
            ledger._path(f"transactions/commits/{custody.commit_filename(transaction_id)}"),
        ),
    )
    assert all(path.is_file() for _, path in physical)
    for keep, path in physical:
        if not keep:
            path.unlink()
    mutations = list(ledger.mutations)
    with pytest.raises(custody.LocatorCustodyError):
        custody.recover_synthetic_transition(
            ledger,
            event=event,
            intent=intent,
            copy_a_genesis=copy_a,
            copy_b_genesis=copy_b,
            prior_snapshot=prior,
        )
    assert ledger.mutations == mutations


def test_locator_commit_forces_fresh_full_replay_and_idempotent_read_only_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger, namespace, common, copy_a, copy_b, locator, prior, event, intent = (
        locator_ledger_records(tmp_path)
    )
    replay_calls = 0
    original_replay = ledger.replay

    def counted_replay(
        *,
        namespace_receipt: Mapping[str, object],
        locator_receipt: Mapping[str, object],
        common_genesis: Mapping[str, object],
        copy_a_genesis: Mapping[str, object],
        copy_b_genesis: Mapping[str, object],
    ) -> tuple[custody.JsonObject, custody.JsonObject]:
        nonlocal replay_calls
        replay_calls += 1
        return original_replay(
            namespace_receipt=namespace_receipt,
            locator_receipt=locator_receipt,
            common_genesis=common_genesis,
            copy_a_genesis=copy_a_genesis,
            copy_b_genesis=copy_b_genesis,
        )

    monkeypatch.setattr(ledger, "replay", counted_replay)
    assert (
        custody.recover_synthetic_transition(
            ledger,
            event=event,
            intent=intent,
            copy_a_genesis=copy_a,
            copy_b_genesis=copy_b,
            prior_snapshot=prior,
        )
        == "COMMIT_DURABLE"
    )
    assert replay_calls == 1
    mutation_count = len(ledger.mutations)
    assert (
        custody.recover_synthetic_transition(
            ledger,
            event=event,
            intent=intent,
            copy_a_genesis=copy_a,
            copy_b_genesis=copy_b,
            prior_snapshot=prior,
        )
        == "COMMIT_DURABLE"
    )
    assert replay_calls == 2
    assert len(ledger.mutations) == mutation_count
    replayed_a, replayed_b = replay_locator_ledger(
        ledger, namespace, common, copy_a, copy_b, locator
    )
    assert replayed_a == replayed_b


def test_namespace_guard_serializes_classification_through_commit_across_ledger_instances(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, namespace, common, copy_a, copy_b, locator, prior, event, intent = (
        locator_ledger_records(tmp_path)
    )
    second = custody.SyntheticLocatorCustodyLedger(
        first.root,
        first.bootstrap_implementation_acceptance,
        first.bootstrap_private_home_acceptance,
    )
    first_entered = threading.Event()
    release_first = threading.Event()
    second_started = threading.Event()
    second_entered = threading.Event()
    original_first_classify = first._classify_transition_prefix
    original_second_classify = second._classify_transition_prefix

    def blocking_first_classify(
        *,
        event: Mapping[str, object],
        intent: Mapping[str, object],
        copy_a_genesis: Mapping[str, object],
        copy_b_genesis: Mapping[str, object],
        prior_snapshot: Mapping[str, object],
    ) -> tuple[
        str,
        custody.JsonObject,
        custody.JsonObject,
        custody.JsonObject,
        custody.JsonObject,
        custody.JsonObject,
    ]:
        first_entered.set()
        assert release_first.wait(5)
        return original_first_classify(
            event=event,
            intent=intent,
            copy_a_genesis=copy_a_genesis,
            copy_b_genesis=copy_b_genesis,
            prior_snapshot=prior_snapshot,
        )

    def observed_second_classify(
        *,
        event: Mapping[str, object],
        intent: Mapping[str, object],
        copy_a_genesis: Mapping[str, object],
        copy_b_genesis: Mapping[str, object],
        prior_snapshot: Mapping[str, object],
    ) -> tuple[
        str,
        custody.JsonObject,
        custody.JsonObject,
        custody.JsonObject,
        custody.JsonObject,
        custody.JsonObject,
    ]:
        second_entered.set()
        return original_second_classify(
            event=event,
            intent=intent,
            copy_a_genesis=copy_a_genesis,
            copy_b_genesis=copy_b_genesis,
            prior_snapshot=prior_snapshot,
        )

    monkeypatch.setattr(first, "_classify_transition_prefix", blocking_first_classify)
    monkeypatch.setattr(second, "_classify_transition_prefix", observed_second_classify)

    def recover(ledger: custody.SyntheticLocatorCustodyLedger) -> str:
        return custody.recover_synthetic_transition(
            ledger,
            event=event,
            intent=intent,
            copy_a_genesis=copy_a,
            copy_b_genesis=copy_b,
            prior_snapshot=prior,
        )

    def recover_second() -> str:
        second_started.set()
        return recover(second)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(recover, first)
        assert first_entered.wait(5)
        second_future = executor.submit(recover_second)
        assert second_started.wait(5)
        assert not second_entered.wait(0.2)
        release_first.set()
        assert first_future.result(timeout=5) == "COMMIT_DURABLE"
        assert second_future.result(timeout=5) == "COMMIT_DURABLE"
    assert second_entered.is_set()
    replayed_a, replayed_b = replay_locator_ledger(
        first, namespace, common, copy_a, copy_b, locator
    )
    assert replayed_a == replayed_b
    assert replayed_a["event_count"] == 1


def _wait_for_marker(path: Path, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 10
    while not path.exists() and time.monotonic() < deadline:
        if process.poll() is not None:
            break
        time.sleep(0.01)
    assert path.is_file(), f"child exited before acquiring guard: {process.poll()}"


def _namespace_guard_child(
    root: Path,
    acquired: Path,
    release: Path,
    *,
    crash: bool,
) -> subprocess.Popen[bytes]:
    script = """
import os
from pathlib import Path
import sys
import time
from mirror_api.demo_d02_r2_locator_custody import _namespace_scoped_exclusive_guard

root = Path(sys.argv[1])
acquired = Path(sys.argv[2])
release = Path(sys.argv[3])
crash = sys.argv[4] == "crash"
with _namespace_scoped_exclusive_guard(root):
    acquired.write_bytes(b"LOCKED")
    if crash:
        os._exit(0)
    while not release.exists():
        time.sleep(0.01)
"""
    return subprocess.Popen(  # noqa: S603 - exact current interpreter and fixed inline script
        [
            sys.executable,
            "-c",
            script,
            str(root),
            str(acquired),
            str(release),
            "crash" if crash else "release",
        ],
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join(
                filter(
                    None,
                    [
                        str(Path(__file__).parents[1] / "src"),
                        os.environ.get("PYTHONPATH", ""),
                    ],
                )
            ),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_namespace_guard_is_cross_process_and_released_after_process_exit(tmp_path: Path) -> None:
    root = tmp_path / "cross-process-namespace"
    acquired = tmp_path / "child-acquired"
    release = tmp_path / "release-child"
    child = _namespace_guard_child(root, acquired, release, crash=False)
    try:
        _wait_for_marker(acquired, child)
        parent_started = threading.Event()
        parent_acquired = threading.Event()

        def acquire_in_parent() -> None:
            parent_started.set()
            with custody._namespace_scoped_exclusive_guard(root):
                parent_acquired.set()

        with ThreadPoolExecutor(max_workers=1) as executor:
            parent_future = executor.submit(acquire_in_parent)
            assert parent_started.wait(5)
            assert not parent_acquired.wait(0.2)
            release.write_bytes(b"RELEASE")
            assert parent_future.result(timeout=10) is None
        assert child.wait(timeout=10) == 0
        assert parent_acquired.is_set()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)

    crash_acquired = tmp_path / "crash-acquired"
    crash_release = tmp_path / "unused-release"
    crash_child = _namespace_guard_child(root, crash_acquired, crash_release, crash=True)
    _wait_for_marker(crash_acquired, crash_child)
    assert crash_child.wait(timeout=10) == 0
    with custody._namespace_scoped_exclusive_guard(root):
        assert not root.exists()
    if os.name == "posix":
        lock_files = list(tmp_path.glob(".project-mirror-d02-r2-custody-*.lock"))
        assert len(lock_files) == 1
