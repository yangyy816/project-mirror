# ruff: noqa: E501
"""Principal-owned D02-R2 private evidence root and two-copy registry.

The module implements the frozen CC08 control plane only.  It has no Provider,
PostgreSQL, M3, M4, migration, or public API dependency.  Callers must supply an
already accepted tracked implementation SHA before creating a real evidence root.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import ctypes
import hashlib
import importlib
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, NoReturn, cast

from mirror_api.demo_measurement_quality import canonical_json_bytes, mirror_demo_digest

type JsonScalar = bool | int | str | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]


class D02R2RegistryError(RuntimeError):
    """A frozen CC08 root, receipt, registry, or recovery invariant failed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


ROOT_RECEIPT_SCHEMA: Final = "mirror.demo/D02R2EvidenceRootNameReceipt/v1"
OUTPUT_NAME_RECEIPT_SCHEMA: Final = "mirror.demo/D02R2OutputNameReceipt/v1"
OUTPUT_SEAL_RECEIPT_SCHEMA: Final = "mirror.demo/D02R2OutputSealReceipt/v1"
REGISTRY_SCHEMA_CONTRACT_SCHEMA: Final = "mirror.demo/D02R2RegistrySchemaContract/v1"
REGISTRY_COMMON_GENESIS_SCHEMA: Final = "mirror.demo/D02R2RegistryCommonGenesis/v1"
REGISTRY_METADATA_SCHEMA: Final = "mirror.demo/D02R2RegistryMetadata/v1"
REGISTRY_EVENT_SCHEMA: Final = "mirror.demo/D02R2PrivateRegistryEvent/v1"
REGISTRY_INTENT_SCHEMA: Final = "mirror.demo/D02R2RegistryTransactionIntent/v1"
REGISTRY_COMMIT_SCHEMA: Final = "mirror.demo/D02R2RegistryCommitReceipt/v1"
REGISTRY_RECOVERY_SCHEMA: Final = "mirror.demo/D02R2RegistryRecoveryReceipt/v1"
REGISTRY_SNAPSHOT_SCHEMA: Final = "mirror.demo/D02R2PrivateRegistrySemanticSnapshot/v1"
REGISTRY_TRANSACTION_ID_SCHEMA: Final = "mirror.demo/D02R2RegistryTransactionId/v1"
SEALED_BINARY_AUTHORITY_SCHEMA: Final = "mirror.demo/D02R2SealedBinaryAuthority/v1"
EXECUTION_CONTRACT_SCHEMA: Final = "mirror.demo/D02R2ExecutionContract/v1"
COHORT_POLICY_SCHEMA: Final = "mirror.demo/D02R2SourceCohortPolicy/v1"
REGISTRY_IMPLEMENTATION_ACCEPTANCE_SCHEMA: Final = (
    "mirror.demo/D02R2RegistryImplementationAcceptance/v1"
)

SOURCE_GENERATION_PREREGISTRATION_SCHEMA: Final = (
    "mirror.demo/D02R2SourceGenerationPreregistrationAuthority/v1"
)
SOURCE_ALLOCATION_MANIFEST_SCHEMA: Final = "mirror.demo/D02R2SourceAllocationManifest/v1"
SOURCE_PRODUCER_DISPATCH_SCHEMA: Final = "mirror.demo/D02R2SourceProducerDispatchReceipt/v1"
SOURCE_GENERATION_RECEIPT_SCHEMA: Final = "mirror.demo/D02R2SourceGenerationReceipt/v1"

CHANGE_CONTROL_ID: Final = "P3_P7_D02_CC_08"
ACCEPTED_PLAN_SHA: Final = "218f4b5a5ee4e6e2223995d232da61496dd47de3"
ACCEPTED_PLAN_TREE: Final = "1cff56bd1f1127a310622d5b8a72045b39290549"
TASK_ID: Final = "P3_P7_D02_R2_EXECUTION_01"
SOURCE_PRODUCER_TASK_ID: Final = "P3_P7_D02_R2_SOURCE_COHORT_01"
REVIEW_TASK_ID: Final = "P3_P7_D02_R2_EVIDENCE_REVIEW_01"
DISPATCH_EPOCH: Final = 1
PRIVATE_NAMESPACE_ID: Final = "pm-p3p7-d02-r2-cc08-e1"
EVIDENCE_ROOT_ID: Final = "P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT"
EVIDENCE_ROOT_BASENAME: Final = "p3-p7-d02-r2-cc08-e1-evidence"
ROOT_RECEIPT_LOGICAL_NAME: Final = "D02_R2_EVIDENCE_ROOT_NAME_RECEIPT.json"
REGISTRY_COPY_A_ID: Final = "P3_P7_D02_R2_CC08_E1_REGISTRY_A"
REGISTRY_COPY_B_ID: Final = "P3_P7_D02_R2_CC08_E1_REGISTRY_B"
REGISTRY_A_LOGICAL_NAME: Final = "D02_R2_PRIVATE_OUTPUT_REGISTRY_A.sqlite3"
REGISTRY_B_LOGICAL_NAME: Final = "D02_R2_PRIVATE_OUTPUT_REGISTRY_B.sqlite3"
ROOT_PURPOSE: Final = "D02_R2_FORWARD_ONLY_SYNTHETIC_SOURCE_AND_PAIR_SCREENING_EVIDENCE"
CANONICALIZATION_VERSION: Final = "demo-canonical-json-v1"
SCHEMA_MATRIX_VERSION: Final = "P3_P7_D02_R2_SCHEMA_MATRIX_V1"
GENERATION_DISPATCH_STATE: Final = "BLOCKED_PENDING_SEPARATE_GENERATION_CAPABILITY_AUTHORITY"
CORE_NETWORK_POLICY: Final = "LOCALHOST_AND_DOCKER_INTERNAL_ALLOWED_PUBLIC_INTERNET_EGRESS_DENIED"
MAXIMUM_ROOT_BYTES: Final = 42_949_672_960
RETENTION_POLICY: Final = "RETAIN_UNTIL_D02_R2_AND_ALL_REFERENCING_DOWNSTREAM_TASKS_RELEASE_CUSTODY"
CLEANUP_DEPENDENCY_SCAN_POLICY: Final = (
    "PRINCIPAL_EXACT_OUTPUT_ID_DEPENDENCY_SCAN_REQUIRED_BEFORE_ANY_CLEANUP"
)
DEFAULT_CUSTODY: Final = "PRINCIPAL_PRIVATE_OUTPUT_CUSTODY"

REGISTRY_IMPLEMENTATION_AUTHORITY_ID: Final = "P3_P7_D02_R2_REGISTRY_IMPLEMENTATION_ACCEPTANCE_01"
REGISTRY_IMPLEMENTATION_TASK_ID: Final = "P3_P7_D02_R2_REGISTRY_IMPLEMENTATION_01"
REGISTRY_IMPLEMENTATION_ACCEPTANCE_REF: Final = "refs/remotes/origin/codex/p3-p7-core-demo"
REGISTRY_IMPLEMENTATION_ACCEPTANCE_PATH: Final = (
    "docs/operations/P3_P7_D02_R2_REGISTRY_IMPLEMENTATION_ACCEPTANCE.json"
)
REGISTRY_SOURCE_REPO_PATH: Final = "services/api/src/mirror_api/demo_d02_r2_private_registry.py"
REGISTRY_TEST_REPO_PATH: Final = "services/api/tests/test_demo_d02_r2_private_registry.py"
REGISTRY_DIGEST_DEPENDENCY_REPO_PATH: Final = (
    "services/api/src/mirror_api/demo_measurement_quality.py"
)
REGISTRY_GOVERNED_PATHS: Final[tuple[str, ...]] = (
    REGISTRY_SOURCE_REPO_PATH,
    REGISTRY_TEST_REPO_PATH,
    REGISTRY_DIGEST_DEPENDENCY_REPO_PATH,
)
REGISTRY_AUTHORIZED_SCOPE: Final = "D02_R2_ROOT_RECEIPT_AND_PRIVATE_TWO_COPY_REGISTRY_ONLY"
REGISTRY_PROHIBITED_SCOPE: Final[tuple[str, ...]] = (
    "SOURCE_GENERATION",
    "M3_M4_EXECUTION",
    "MIGRATION_OR_ORM",
    "POSTGRESQL_ADMISSION",
    "FORMAL_PHASE_AUTHORITY",
    "PRODUCTION_RELEASE",
)
REGISTRY_REQUIRED_CI_JOBS: Final[tuple[str, ...]] = (
    "quality-and-integration",
    "secret-scan",
    "docker-validation",
)
_ROOT_AUTHORITY_TOKEN: Final = object()

SQLITE_APPLICATION_ID: Final = 1_297_232_466
SQLITE_USER_VERSION: Final = 1

_DIGEST_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_SHA_RE: Final = re.compile(r"[0-9a-f]{40}\Z")
_OUTPUT_ID_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_LOGICAL_NAME_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,255}\Z")
_UTC_RE: Final = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{6}Z\Z")

ALLOWED_ROLES: Final[tuple[str, ...]] = (
    "INTEGRATION_PRINCIPAL",
    "D02_R2_SOURCE_COHORT_PRODUCER",
    "D02_R2_RUNTIME_EXECUTOR",
    "D02_R2_REVIEWER_READ_ONLY",
)

ALLOWED_OUTPUT_CLASSES: Final[tuple[str, ...]] = (
    "SOURCE_GENERATION_PREREGISTRATION",
    "SOURCE_PRODUCER_DISPATCH_RECEIPT",
    "SOURCE_ALLOCATION_MANIFEST",
    "SOURCE_CANDIDATE",
    "SOURCE_PROVENANCE",
    "SOURCE_GENERATION_RECEIPT",
    "SOURCE_AUTHORITY",
    "SOURCE_QA",
    "SOURCE_COHORT_RECEIPT",
    "SOURCE_MANIFEST",
    "SOURCE_M3",
    "GEOMETRY_CASE",
    "CASE_MANIFEST",
    "M4_EXECUTION",
    "RESULT_M3",
    "MEASUREMENT_GATE",
    "STRUCTURE_GATE",
    "MANUAL_REVIEW",
    "IMAGE_AUTHORITY",
    "PHASH",
    "PAIR_SCREENING",
    "REPORT",
    "BANK_IMPORT_EVIDENCE",
    "NEGATIVE_RECEIPT",
    "RUNTIME_LOG_REDACTED",
)

CONTROL_DESTINATIONS: Final[dict[str, str]] = {
    "CONTROL_ROOT": ".",
    "CONTROL_NAME_RECEIPTS": "control/name-receipts",
    "CONTROL_SEAL_RECEIPTS": "control/seal-receipts",
    "CONTROL_REGISTRY_A": "control/registry-a",
    "CONTROL_REGISTRY_B": "control/registry-b",
    "CONTROL_REGISTRY_INTENTS": "control/registry-intents",
    "CONTROL_REGISTRY_COMMITS": "control/registry-commits",
    "CONTROL_REGISTRY_RECOVERY": "control/registry-recovery",
}

ROLE_DESTINATIONS: Final[dict[str, tuple[str, str]]] = {
    "SOURCE_GENERATION_PREREGISTRATION": (
        "DATA_GENERATION_PREREG",
        "authority/generation-preregistration",
    ),
    "SOURCE_PRODUCER_DISPATCH_RECEIPT": (
        "DATA_SOURCE_DISPATCH",
        "authority/source-dispatch",
    ),
    "SOURCE_ALLOCATION_MANIFEST": (
        "DATA_SOURCE_ALLOCATION",
        "authority/source-allocation",
    ),
    "SOURCE_CANDIDATE": ("DATA_SOURCE_CANDIDATES", "bytes/source-candidates"),
    "SOURCE_PROVENANCE": ("DATA_SOURCE_PROVENANCE", "authority/source-provenance"),
    "SOURCE_GENERATION_RECEIPT": (
        "DATA_GENERATION_RECEIPTS",
        "authority/generation-receipts",
    ),
    "SOURCE_AUTHORITY": ("DATA_SOURCE_AUTHORITY", "authority/sources"),
    "SOURCE_QA": ("DATA_SOURCE_QA", "evidence/source-qa"),
    "SOURCE_COHORT_RECEIPT": ("DATA_SOURCE_COHORT", "authority/source-cohort"),
    "SOURCE_MANIFEST": ("DATA_SOURCE_MANIFEST", "authority/manifests/sources"),
    "SOURCE_M3": ("DATA_SOURCE_M3", "evidence/source-m3"),
    "GEOMETRY_CASE": ("DATA_GEOMETRY_CASES", "authority/geometry-cases"),
    "CASE_MANIFEST": ("DATA_CASE_MANIFEST", "authority/manifests/cases"),
    "M4_EXECUTION": ("DATA_M4_EXECUTION", "evidence/m4"),
    "RESULT_M3": ("DATA_RESULT_M3", "evidence/result-m3"),
    "MEASUREMENT_GATE": ("DATA_MEASUREMENT_GATES", "evidence/gates/measurement"),
    "STRUCTURE_GATE": ("DATA_STRUCTURE_GATES", "evidence/gates/structure"),
    "MANUAL_REVIEW": ("DATA_MANUAL_REVIEWS", "evidence/manual-review"),
    "IMAGE_AUTHORITY": ("DATA_IMAGE_AUTHORITY", "authority/images"),
    "PHASH": ("DATA_PHASH", "evidence/phash"),
    "PAIR_SCREENING": ("DATA_PAIR_SCREENING", "evidence/pair-screening"),
    "REPORT": ("DATA_REPORT", "authority/report"),
    "BANK_IMPORT_EVIDENCE": ("DATA_BANK_IMPORT", "evidence/bank-import"),
    "NEGATIVE_RECEIPT": ("DATA_NEGATIVE_RECEIPTS", "evidence/negative"),
    "RUNTIME_LOG_REDACTED": ("DATA_REDACTED_LOGS", "logs/redacted"),
}

_CONTROL_MANIFEST_SOURCE: Final[tuple[tuple[str, str, str, str, int], ...]] = (
    (
        "ROOT_NAME_RECEIPT",
        r"^D02_R2_EVIDENCE_ROOT_NAME_RECEIPT[.]json$",
        "CONTROL_ROOT",
        "CREATE_NEW_IMMUTABLE",
        262_144,
    ),
    (
        "OUTPUT_NAME_RECEIPT",
        r"^D02_R2_OUTPUT_NAME_RECEIPT__[0-9]{8}__[A-Za-z0-9][A-Za-z0-9._-]{0,127}[.]json$",
        "CONTROL_NAME_RECEIPTS",
        "CREATE_NEW_IMMUTABLE",
        262_144,
    ),
    (
        "OUTPUT_SEAL_RECEIPT",
        r"^D02_R2_OUTPUT_SEAL_RECEIPT__[0-9]{8}__[A-Za-z0-9][A-Za-z0-9._-]{0,127}[.]json$",
        "CONTROL_SEAL_RECEIPTS",
        "CREATE_NEW_IMMUTABLE",
        262_144,
    ),
    (
        "REGISTRY_DATABASE_A",
        r"^D02_R2_PRIVATE_OUTPUT_REGISTRY_A[.]sqlite3(?:-journal)?$",
        "CONTROL_REGISTRY_A",
        "APPEND_ONLY_SQLITE_WITH_TRANSIENT_DELETE_JOURNAL",
        2_147_483_648,
    ),
    (
        "REGISTRY_DATABASE_B",
        r"^D02_R2_PRIVATE_OUTPUT_REGISTRY_B[.]sqlite3(?:-journal)?$",
        "CONTROL_REGISTRY_B",
        "APPEND_ONLY_SQLITE_WITH_TRANSIENT_DELETE_JOURNAL",
        2_147_483_648,
    ),
    (
        "REGISTRY_TRANSACTION_INTENT",
        r"^D02_R2_REGISTRY_TRANSACTION_INTENT__[0-9a-f]{64}[.]json$",
        "CONTROL_REGISTRY_INTENTS",
        "CREATE_NEW_IMMUTABLE",
        262_144,
    ),
    (
        "REGISTRY_COMMIT_RECEIPT",
        r"^D02_R2_REGISTRY_COMMIT_RECEIPT__[0-9a-f]{64}[.]json$",
        "CONTROL_REGISTRY_COMMITS",
        "CREATE_NEW_IMMUTABLE",
        262_144,
    ),
    (
        "REGISTRY_RECOVERY_RECEIPT",
        r"^D02_R2_REGISTRY_RECOVERY_RECEIPT__[0-9a-f]{64}__[0-9]{4}[.]json$",
        "CONTROL_REGISTRY_RECOVERY",
        "CREATE_NEW_IMMUTABLE",
        262_144,
    ),
)

REQUIRED_PRAGMAS: Final[tuple[str, ...]] = (
    "application_id=1297232466",
    "user_version=1",
    "journal_mode=DELETE",
    "synchronous=FULL",
    "foreign_keys=ON",
    "temp_store=MEMORY",
    "trusted_schema=OFF",
)

ORDERED_TABLE_CONTRACTS: Final[tuple[str, ...]] = (
    "registry_metadata|singleton:INTEGER:PK:CHECK_EQ_1|schema_version:TEXT:NOT_NULL|"
    "evidence_root_id:TEXT:NOT_NULL|root_name_receipt_digest:CHAR64:NOT_NULL|"
    "execution_contract_digest:CHAR64:NOT_NULL|registry_schema_contract_digest:CHAR64:NOT_NULL|"
    "registry_normalized_ddl_sha256:CHAR64:NOT_NULL|registry_implementation_sha:CHAR40:NOT_NULL|"
    "registry_copy_id:TEXT:NOT_NULL:UNIQUE|common_genesis_digest:CHAR64:NOT_NULL|"
    "created_at_utc:TEXT:NOT_NULL|metadata_digest:CHAR64:NOT_NULL:UNIQUE",
    "registry_events|sequence:INTEGER:PK:CHECK_GE_1|transaction_id:CHAR64:NOT_NULL:UNIQUE:"
    "FK_registry_transactions.transaction_id_DEFERRED|output_id:VARCHAR128:NOT_NULL:UNIQUE|"
    "semantic_role:TEXT:NOT_NULL|authority_digest:CHAR64:NOT_NULL:UNIQUE|"
    "name_receipt_digest:CHAR64:NOT_NULL:UNIQUE|seal_receipt_digest:CHAR64:NOT_NULL:UNIQUE|"
    "previous_event_digest:CHAR64:NOT_NULL|event_digest:CHAR64:NOT_NULL:UNIQUE|"
    "canonical_event_json:BLOB:NOT_NULL:UNIQUE",
    "registry_transactions|transaction_id:CHAR64:PK|output_id:VARCHAR128:NOT_NULL:UNIQUE|"
    "semantic_role:TEXT:NOT_NULL|authority_digest:CHAR64:NOT_NULL:UNIQUE|"
    "intent_digest:CHAR64:NOT_NULL:UNIQUE|expected_sequence:INTEGER:NOT_NULL:UNIQUE:CHECK_GE_1|"
    "canonical_event_digest:CHAR64:NOT_NULL:UNIQUE:FK_registry_events.event_digest_DEFERRED|"
    "transaction_state:TEXT:NOT_NULL:CHECK_COPY_PREPARED|intent_created_at_utc:TEXT:NOT_NULL",
)

ORDERED_INDEX_CONTRACTS: Final[tuple[str, ...]] = (
    "uq_registry_execution_singleton_roles|UNIQUE|registry_events(semantic_role)|WHERE semantic_role "
    "IN ('SOURCE_GENERATION_PREREGISTRATION','SOURCE_ALLOCATION_MANIFEST',"
    "'SOURCE_PRODUCER_DISPATCH_RECEIPT')",
)

ORDERED_TRIGGER_CONTRACTS: Final[tuple[str, ...]] = (
    "trg_registry_metadata_no_update|BEFORE_UPDATE|RAISE_REGISTRY_APPEND_ONLY",
    "trg_registry_metadata_no_delete|BEFORE_DELETE|RAISE_REGISTRY_APPEND_ONLY",
    "trg_registry_events_no_update|BEFORE_UPDATE|RAISE_REGISTRY_APPEND_ONLY",
    "trg_registry_events_no_delete|BEFORE_DELETE|RAISE_REGISTRY_APPEND_ONLY",
    "trg_registry_transactions_no_update|BEFORE_UPDATE|RAISE_REGISTRY_APPEND_ONLY",
    "trg_registry_transactions_no_delete|BEFORE_DELETE|RAISE_REGISTRY_APPEND_ONLY",
    "trg_registry_transactions_sequence_guard|BEFORE_INSERT|"
    "EXPECTED_SEQUENCE_EQUALS_EVENT_COUNT_PLUS_ONE_AND_OUTPUT_UNIQUE",
    "trg_registry_events_pair_guard|BEFORE_INSERT|"
    "MATCH_TRANSACTION_OUTPUT_SEQUENCE_ROLE_AUTHORITY_EVENT_DIGEST_AND_CURRENT_HEAD",
)

EVENT_KEYS: Final[tuple[str, ...]] = (
    "SCHEMA_VERSION",
    "EVIDENCE_ROOT_ID",
    "ROOT_NAME_RECEIPT_DIGEST",
    "EXECUTION_CONTRACT_DIGEST",
    "OUTPUT_ID",
    "SEMANTIC_ROLE",
    "CREATING_TASK",
    "OPAQUE_LOCATOR",
    "EXPECTED_DIGEST",
    "ACTUAL_DIGEST",
    "BYTE_SIZE",
    "MEDIA_TYPE",
    "AUTHORITY",
    "ALLOWED_TASKS",
    "RETENTION",
    "CUSTODY",
    "RECOVERY_STATUS",
    "BACKUP_STATUS",
    "CLEANUP_STATUS",
    "NAME_RECEIPT_DIGEST",
    "SEAL_RECEIPT_DIGEST",
    "TRANSACTION_ID",
    "SEQUENCE",
    "PREVIOUS_EVENT_DIGEST",
    "EVENT_DIGEST",
)

SNAPSHOT_KEYS: Final[tuple[str, ...]] = (
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

SNAPSHOT_EVENT_KEYS: Final[tuple[str, ...]] = (
    "sequence",
    "transaction_id",
    "output_id",
    "semantic_role",
    "authority_digest",
    "event_digest",
)


def _sql(statement: str) -> str:
    return "\n".join(line.rstrip() for line in statement.strip().splitlines())


_DDL_STATEMENTS: Final[tuple[tuple[str, str, str], ...]] = (
    (
        "table",
        "registry_metadata",
        _sql(
            """
CREATE TABLE registry_metadata (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  schema_version TEXT NOT NULL,
  evidence_root_id TEXT NOT NULL,
  root_name_receipt_digest CHAR(64) NOT NULL CHECK (length(root_name_receipt_digest) = 64 AND root_name_receipt_digest NOT GLOB '*[^0-9a-f]*'),
  execution_contract_digest CHAR(64) NOT NULL CHECK (length(execution_contract_digest) = 64 AND execution_contract_digest NOT GLOB '*[^0-9a-f]*'),
  registry_schema_contract_digest CHAR(64) NOT NULL CHECK (length(registry_schema_contract_digest) = 64 AND registry_schema_contract_digest NOT GLOB '*[^0-9a-f]*'),
  registry_normalized_ddl_sha256 CHAR(64) NOT NULL CHECK (length(registry_normalized_ddl_sha256) = 64 AND registry_normalized_ddl_sha256 NOT GLOB '*[^0-9a-f]*'),
  registry_implementation_sha CHAR(40) NOT NULL CHECK (length(registry_implementation_sha) = 40 AND registry_implementation_sha NOT GLOB '*[^0-9a-f]*'),
  registry_copy_id TEXT NOT NULL UNIQUE,
  common_genesis_digest CHAR(64) NOT NULL CHECK (length(common_genesis_digest) = 64 AND common_genesis_digest NOT GLOB '*[^0-9a-f]*'),
  created_at_utc TEXT NOT NULL CHECK (length(created_at_utc) = 27 AND created_at_utc GLOB '????-??-??T??:??:??.??????Z'),
  metadata_digest CHAR(64) NOT NULL UNIQUE CHECK (length(metadata_digest) = 64 AND metadata_digest NOT GLOB '*[^0-9a-f]*')
)
"""
        ),
    ),
    (
        "table",
        "registry_events",
        _sql(
            """
CREATE TABLE registry_events (
  sequence INTEGER PRIMARY KEY CHECK (sequence >= 1),
  transaction_id CHAR(64) NOT NULL UNIQUE REFERENCES registry_transactions(transaction_id) DEFERRABLE INITIALLY DEFERRED,
  output_id VARCHAR(128) NOT NULL UNIQUE CHECK (length(output_id) BETWEEN 1 AND 128 AND substr(output_id, 1, 1) GLOB '[A-Za-z0-9]' AND output_id NOT GLOB '*[^A-Za-z0-9._-]*'),
  semantic_role TEXT NOT NULL,
  authority_digest CHAR(64) NOT NULL UNIQUE CHECK (length(authority_digest) = 64 AND authority_digest NOT GLOB '*[^0-9a-f]*'),
  name_receipt_digest CHAR(64) NOT NULL UNIQUE CHECK (length(name_receipt_digest) = 64 AND name_receipt_digest NOT GLOB '*[^0-9a-f]*'),
  seal_receipt_digest CHAR(64) NOT NULL UNIQUE CHECK (length(seal_receipt_digest) = 64 AND seal_receipt_digest NOT GLOB '*[^0-9a-f]*'),
  previous_event_digest CHAR(64) NOT NULL CHECK (length(previous_event_digest) = 64 AND previous_event_digest NOT GLOB '*[^0-9a-f]*'),
  event_digest CHAR(64) NOT NULL UNIQUE CHECK (length(event_digest) = 64 AND event_digest NOT GLOB '*[^0-9a-f]*'),
  canonical_event_json BLOB NOT NULL UNIQUE
)
"""
        ),
    ),
    (
        "table",
        "registry_transactions",
        _sql(
            """
CREATE TABLE registry_transactions (
  transaction_id CHAR(64) PRIMARY KEY CHECK (length(transaction_id) = 64 AND transaction_id NOT GLOB '*[^0-9a-f]*'),
  output_id VARCHAR(128) NOT NULL UNIQUE CHECK (length(output_id) BETWEEN 1 AND 128 AND substr(output_id, 1, 1) GLOB '[A-Za-z0-9]' AND output_id NOT GLOB '*[^A-Za-z0-9._-]*'),
  semantic_role TEXT NOT NULL,
  authority_digest CHAR(64) NOT NULL UNIQUE CHECK (length(authority_digest) = 64 AND authority_digest NOT GLOB '*[^0-9a-f]*'),
  intent_digest CHAR(64) NOT NULL UNIQUE CHECK (length(intent_digest) = 64 AND intent_digest NOT GLOB '*[^0-9a-f]*'),
  expected_sequence INTEGER NOT NULL UNIQUE CHECK (expected_sequence >= 1),
  canonical_event_digest CHAR(64) NOT NULL UNIQUE REFERENCES registry_events(event_digest) DEFERRABLE INITIALLY DEFERRED,
  transaction_state TEXT NOT NULL CHECK (transaction_state = 'COPY_PREPARED'),
  intent_created_at_utc TEXT NOT NULL CHECK (length(intent_created_at_utc) = 27 AND intent_created_at_utc GLOB '????-??-??T??:??:??.??????Z')
)
"""
        ),
    ),
    (
        "index",
        "uq_registry_execution_singleton_roles",
        _sql(
            """
CREATE UNIQUE INDEX uq_registry_execution_singleton_roles
ON registry_events(semantic_role)
WHERE semantic_role IN (
  'SOURCE_GENERATION_PREREGISTRATION',
  'SOURCE_ALLOCATION_MANIFEST',
  'SOURCE_PRODUCER_DISPATCH_RECEIPT'
)
"""
        ),
    ),
    (
        "trigger",
        "trg_registry_metadata_no_update",
        _sql(
            """
CREATE TRIGGER trg_registry_metadata_no_update
BEFORE UPDATE ON registry_metadata
BEGIN
  SELECT RAISE(ABORT, 'REGISTRY_APPEND_ONLY');
END
"""
        ),
    ),
    (
        "trigger",
        "trg_registry_metadata_no_delete",
        _sql(
            """
CREATE TRIGGER trg_registry_metadata_no_delete
BEFORE DELETE ON registry_metadata
BEGIN
  SELECT RAISE(ABORT, 'REGISTRY_APPEND_ONLY');
END
"""
        ),
    ),
    (
        "trigger",
        "trg_registry_events_no_update",
        _sql(
            """
CREATE TRIGGER trg_registry_events_no_update
BEFORE UPDATE ON registry_events
BEGIN
  SELECT RAISE(ABORT, 'REGISTRY_APPEND_ONLY');
END
"""
        ),
    ),
    (
        "trigger",
        "trg_registry_events_no_delete",
        _sql(
            """
CREATE TRIGGER trg_registry_events_no_delete
BEFORE DELETE ON registry_events
BEGIN
  SELECT RAISE(ABORT, 'REGISTRY_APPEND_ONLY');
END
"""
        ),
    ),
    (
        "trigger",
        "trg_registry_transactions_no_update",
        _sql(
            """
CREATE TRIGGER trg_registry_transactions_no_update
BEFORE UPDATE ON registry_transactions
BEGIN
  SELECT RAISE(ABORT, 'REGISTRY_APPEND_ONLY');
END
"""
        ),
    ),
    (
        "trigger",
        "trg_registry_transactions_no_delete",
        _sql(
            """
CREATE TRIGGER trg_registry_transactions_no_delete
BEFORE DELETE ON registry_transactions
BEGIN
  SELECT RAISE(ABORT, 'REGISTRY_APPEND_ONLY');
END
"""
        ),
    ),
    (
        "trigger",
        "trg_registry_transactions_sequence_guard",
        _sql(
            """
CREATE TRIGGER trg_registry_transactions_sequence_guard
BEFORE INSERT ON registry_transactions
BEGIN
  SELECT CASE
    WHEN NEW.expected_sequence != (SELECT count(*) + 1 FROM registry_events)
    THEN RAISE(ABORT, 'REGISTRY_SEQUENCE_INVALID')
  END;
END
"""
        ),
    ),
    (
        "trigger",
        "trg_registry_events_pair_guard",
        _sql(
            """
CREATE TRIGGER trg_registry_events_pair_guard
BEFORE INSERT ON registry_events
BEGIN
  SELECT CASE
    WHEN NOT EXISTS (
      SELECT 1
      FROM registry_transactions AS transaction_row
      WHERE transaction_row.transaction_id = NEW.transaction_id
        AND transaction_row.output_id = NEW.output_id
        AND transaction_row.semantic_role = NEW.semantic_role
        AND transaction_row.authority_digest = NEW.authority_digest
        AND transaction_row.expected_sequence = NEW.sequence
        AND transaction_row.canonical_event_digest = NEW.event_digest
    )
    THEN RAISE(ABORT, 'REGISTRY_EVENT_TRANSACTION_MISMATCH')
  END;
  SELECT CASE
    WHEN NEW.previous_event_digest != COALESCE(
      (SELECT event_digest FROM registry_events ORDER BY sequence DESC LIMIT 1),
      (SELECT common_genesis_digest FROM registry_metadata WHERE singleton = 1)
    )
    THEN RAISE(ABORT, 'REGISTRY_PREVIOUS_HEAD_MISMATCH')
  END;
END
"""
        ),
    ),
)

NORMALIZED_REGISTRY_DDL: Final = ";\n\n".join(item[2] for item in _DDL_STATEMENTS) + ";\n"
REGISTRY_NORMALIZED_DDL_SHA256: Final = hashlib.sha256(
    NORMALIZED_REGISTRY_DDL.encode("utf-8")
).hexdigest()


def _registry_schema_contract_payload() -> JsonObject:
    return {
        "schema_version": REGISTRY_SCHEMA_CONTRACT_SCHEMA,
        "sqlite_application_id": SQLITE_APPLICATION_ID,
        "sqlite_user_version": SQLITE_USER_VERSION,
        "required_pragmas": list(REQUIRED_PRAGMAS),
        "ordered_table_contracts": list(ORDERED_TABLE_CONTRACTS),
        "ordered_index_contracts": list(ORDERED_INDEX_CONTRACTS),
        "ordered_trigger_contracts": list(ORDERED_TRIGGER_CONTRACTS),
        "canonical_event_projection": list(EVENT_KEYS),
        "semantic_snapshot_preimage": list(SNAPSHOT_KEYS),
        "semantic_snapshot_ordered_event_projection": list(SNAPSHOT_EVENT_KEYS),
        "unknown_application_objects_forbidden": True,
    }


REGISTRY_SCHEMA_CONTRACT_DIGEST: Final = mirror_demo_digest(
    REGISTRY_SCHEMA_CONTRACT_SCHEMA,
    _registry_schema_contract_payload(),
)


@dataclass(frozen=True, init=False)
class RootReceiptAuthority:
    accepted_plan_sha: str
    accepted_plan_tree: str
    registry_implementation_sha: str
    created_at_utc: str
    _repository_root: Path = field(repr=False, compare=False)
    _acceptance_checkpoint_sha: str = field(repr=False, compare=False)
    _acceptance_record_digest: str = field(repr=False, compare=False)
    _trust_token: object = field(repr=False, compare=False)


def load_accepted_root_receipt_authority(*, created_at_utc: str) -> RootReceiptAuthority:
    """Load the sole accepted implementation authority from fixed tracked Git objects."""

    _require_timestamp(created_at_utc)
    running_source = Path(__file__).resolve(strict=True)
    repository_root = _discover_implementation_repository(running_source)
    expected_source = (repository_root / REGISTRY_SOURCE_REPO_PATH).resolve(strict=True)
    if running_source != expected_source:
        _fail_root("registry implementation was imported from an unauthorized installation path")
    return _load_accepted_root_receipt_authority(
        repository_root,
        running_source=running_source,
        created_at_utc=created_at_utc,
    )


def _load_accepted_root_receipt_authority(
    repository_root: Path,
    *,
    running_source: Path,
    created_at_utc: str,
) -> RootReceiptAuthority:
    """Internal loader kept separate so fault tests can build an isolated local Git graph."""

    repository_root = repository_root.resolve(strict=True)
    _require_not_reparse(repository_root)
    expected_source = (repository_root / REGISTRY_SOURCE_REPO_PATH).resolve(strict=True)
    if running_source.resolve(strict=True) != expected_source:
        _fail_root("running registry source does not match the governed repository path")
    _require_timestamp(created_at_utc)

    head_sha = _git_text(repository_root, "rev-parse", "--verify", "HEAD^{commit}")
    if _SHA_RE.fullmatch(head_sha) is None:
        _fail_root("registry implementation HEAD is not an exact commit SHA")
    if _git_result(repository_root, "symbolic-ref", "-q", "HEAD").returncode == 0:
        _fail_root("registry root creation requires a clean detached implementation checkout")

    acceptance_sha = _git_text(
        repository_root,
        "rev-parse",
        "--verify",
        f"{REGISTRY_IMPLEMENTATION_ACCEPTANCE_REF}^{{commit}}",
    )
    if _SHA_RE.fullmatch(acceptance_sha) is None:
        _fail_root("registry acceptance ref is not an exact commit SHA")
    if (
        _git_result(
            repository_root,
            "merge-base",
            "--is-ancestor",
            ACCEPTED_PLAN_SHA,
            head_sha,
        ).returncode
        != 0
    ):
        _fail_root("accepted CC08 plan is not an ancestor of the implementation commit")
    if (
        _git_result(
            repository_root,
            "merge-base",
            "--is-ancestor",
            head_sha,
            acceptance_sha,
        ).returncode
        != 0
    ):
        _fail_root("acceptance checkpoint is not a descendant of the implementation commit")

    status = _git_bytes(
        repository_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        *REGISTRY_GOVERNED_PATHS,
    )
    if status:
        _fail_root("governed registry implementation paths are not clean")

    record_bytes = _git_bytes(
        repository_root,
        "show",
        f"{acceptance_sha}:{REGISTRY_IMPLEMENTATION_ACCEPTANCE_PATH}",
    )
    record = _parse_canonical_json_bytes(record_bytes)
    _validate_registry_implementation_acceptance_record(record)
    implementation_sha = _require_string(
        record["registry_implementation_sha"],
        "registry implementation SHA",
    )
    if implementation_sha != head_sha:
        _fail_root("detached HEAD differs from the accepted implementation SHA")
    implementation_tree = _git_text(
        repository_root,
        "rev-parse",
        "--verify",
        f"{implementation_sha}^{{tree}}",
    )
    if implementation_tree != record["registry_implementation_tree"]:
        _fail_root("accepted implementation tree does not replay")

    governed = cast(list[JsonValue], record["governed_paths"])
    governed_by_path = {
        cast(str, cast(dict[str, JsonValue], item)["path"]): cast(dict[str, JsonValue], item)
        for item in governed
    }
    for relative_path in REGISTRY_GOVERNED_PATHS:
        item = governed_by_path[relative_path]
        candidate_bytes = _git_bytes(
            repository_root,
            "show",
            f"{implementation_sha}:{relative_path}",
        )
        acceptance_bytes = _git_bytes(
            repository_root,
            "show",
            f"{acceptance_sha}:{relative_path}",
        )
        disk_path = repository_root / relative_path
        _require_not_reparse(disk_path)
        disk_bytes = disk_path.read_bytes()
        disk_matches_candidate = candidate_bytes == disk_bytes or (
            b"\r" not in candidate_bytes
            and disk_bytes.replace(b"\r\n", b"\n") == candidate_bytes
            and b"\r" not in disk_bytes.replace(b"\r\n", b"")
        )
        if candidate_bytes != acceptance_bytes or not disk_matches_candidate:
            _fail_root("a governed registry implementation path differs across I, A, or checkout")
        if hashlib.sha256(candidate_bytes).hexdigest() != item["sha256"]:
            _fail_root("governed registry implementation SHA-256 does not replay")
        blob_oid = _git_text(
            repository_root,
            "rev-parse",
            "--verify",
            f"{implementation_sha}:{relative_path}",
        )
        if blob_oid != item["git_blob_oid"]:
            _fail_root("governed registry implementation blob OID does not replay")

    record_digest = _require_string(record["record_digest"], "acceptance record digest")
    authority = object.__new__(RootReceiptAuthority)
    object.__setattr__(authority, "accepted_plan_sha", ACCEPTED_PLAN_SHA)
    object.__setattr__(authority, "accepted_plan_tree", ACCEPTED_PLAN_TREE)
    object.__setattr__(authority, "registry_implementation_sha", implementation_sha)
    object.__setattr__(authority, "created_at_utc", created_at_utc)
    object.__setattr__(authority, "_repository_root", repository_root)
    object.__setattr__(authority, "_acceptance_checkpoint_sha", acceptance_sha)
    object.__setattr__(authority, "_acceptance_record_digest", record_digest)
    object.__setattr__(authority, "_trust_token", _ROOT_AUTHORITY_TOKEN)
    _validate_authority(authority)
    return authority


def _validate_registry_implementation_acceptance_record(record: JsonObject) -> None:
    expected_keys = {
        "schema_version",
        "authority_id",
        "change_control_id",
        "implementation_task_id",
        "evidence_root_id",
        "accepted_plan_sha",
        "accepted_plan_tree",
        "registry_implementation_sha",
        "registry_implementation_tree",
        "registry_schema_contract_digest",
        "registry_normalized_ddl_sha256",
        "governed_paths",
        "independent_review",
        "same_sha_ci",
        "principal_acceptance",
        "authorized_scope",
        "prohibited_scope",
        "canonicalization_version",
        "record_created_at_utc",
        "record_digest",
    }
    _require_exact_keys(record, expected_keys, "registry implementation acceptance record")
    if (
        record["schema_version"] != REGISTRY_IMPLEMENTATION_ACCEPTANCE_SCHEMA
        or record["authority_id"] != REGISTRY_IMPLEMENTATION_AUTHORITY_ID
        or record["change_control_id"] != CHANGE_CONTROL_ID
        or record["implementation_task_id"] != REGISTRY_IMPLEMENTATION_TASK_ID
        or record["evidence_root_id"] != EVIDENCE_ROOT_ID
        or record["accepted_plan_sha"] != ACCEPTED_PLAN_SHA
        or record["accepted_plan_tree"] != ACCEPTED_PLAN_TREE
        or record["registry_schema_contract_digest"] != REGISTRY_SCHEMA_CONTRACT_DIGEST
        or record["registry_normalized_ddl_sha256"] != REGISTRY_NORMALIZED_DDL_SHA256
        or record["authorized_scope"] != REGISTRY_AUTHORIZED_SCOPE
        or record["prohibited_scope"] != list(REGISTRY_PROHIBITED_SCOPE)
        or record["canonicalization_version"] != CANONICALIZATION_VERSION
    ):
        _fail_root("registry implementation acceptance fixed authority does not replay")
    for commit_field in (
        "registry_implementation_sha",
        "registry_implementation_tree",
    ):
        value = record[commit_field]
        if not isinstance(value, str) or _SHA_RE.fullmatch(value) is None:
            _fail_root(f"{commit_field} is not a lowercase 40-hex Git object ID")
    _require_digest(record["registry_schema_contract_digest"], "registry schema contract")
    _require_digest(record["registry_normalized_ddl_sha256"], "normalized registry DDL")
    _require_timestamp(record["record_created_at_utc"])

    governed = record["governed_paths"]
    if not isinstance(governed, list) or len(governed) != len(REGISTRY_GOVERNED_PATHS):
        _fail_root("registry governed-path closure is incomplete")
    observed_paths: list[str] = []
    for item in governed:
        if not isinstance(item, dict):
            _fail_root("registry governed-path entry is not an object")
        _require_exact_keys(item, {"path", "git_blob_oid", "sha256"}, "governed path")
        path = _require_string(item["path"], "governed path")
        blob_oid = item["git_blob_oid"]
        if not isinstance(blob_oid, str) or _SHA_RE.fullmatch(blob_oid) is None:
            _fail_root("governed-path blob OID is invalid")
        _require_digest(item["sha256"], "governed-path SHA-256")
        observed_paths.append(path)
    if observed_paths != list(REGISTRY_GOVERNED_PATHS):
        _fail_root("registry governed-path order or membership differs from the frozen closure")

    review = _require_json_object(record["independent_review"], "independent review")
    _require_exact_keys(
        review,
        {
            "review_task_id",
            "reviewed_implementation_sha",
            "result",
            "findings_p0",
            "findings_p1",
            "findings_p2",
            "findings_p3",
            "evidence_digest",
        },
        "independent review",
    )
    if (
        review["review_task_id"] != "P3_P7_D02_R2_REGISTRY_EXACT_SHA_REVIEW_01"
        or review["reviewed_implementation_sha"] != record["registry_implementation_sha"]
        or review["result"] != "PASS"
        or any(review[f"findings_p{priority}"] != 0 for priority in range(4))
    ):
        _fail_root("independent exact implementation review is not an all-zero PASS")
    _require_digest(review["evidence_digest"], "independent review evidence")

    ci = _require_json_object(record["same_sha_ci"], "same-SHA CI")
    _require_exact_keys(
        ci,
        {
            "provider",
            "repository",
            "workflow_identity",
            "run_id",
            "head_sha",
            "result",
            "required_jobs",
            "artifact_manifest_digest",
        },
        "same-SHA CI",
    )
    run_id = ci["run_id"]
    if (
        ci["provider"] != "GITHUB_ACTIONS"
        or ci["repository"] != "yangyy816/project-mirror"
        or ci["workflow_identity"] != ".github/workflows/ci.yml"
        or not isinstance(run_id, int)
        or isinstance(run_id, bool)
        or run_id < 1
        or ci["head_sha"] != record["registry_implementation_sha"]
        or ci["result"] != "PASS"
        or ci["required_jobs"] != list(REGISTRY_REQUIRED_CI_JOBS)
    ):
        _fail_root("same-SHA CI authority is invalid")
    _require_digest(ci["artifact_manifest_digest"], "same-SHA CI artifact manifest")

    principal = _require_json_object(record["principal_acceptance"], "Principal acceptance")
    _require_exact_keys(
        principal,
        {
            "status",
            "accepted_implementation_sha",
            "acceptance_authority_digest",
            "accepted_at_utc",
        },
        "Principal acceptance",
    )
    if (
        principal["status"] != "PRINCIPAL_ACCEPTED"
        or principal["accepted_implementation_sha"] != record["registry_implementation_sha"]
    ):
        _fail_root("Principal acceptance does not bind the implementation commit")
    _require_digest(principal["acceptance_authority_digest"], "Principal acceptance authority")
    _require_timestamp(principal["accepted_at_utc"])

    _require_digest(record["record_digest"], "acceptance record")
    claimed = cast(str, record["record_digest"])
    payload = {key: value for key, value in record.items() if key != "record_digest"}
    if mirror_demo_digest(REGISTRY_IMPLEMENTATION_ACCEPTANCE_SCHEMA, payload) != claimed:
        _fail_root("registry implementation acceptance record digest does not replay")


def _discover_implementation_repository(running_source: Path) -> Path:
    completed = _run_git_from(
        running_source.parent,
        "rev-parse",
        "--show-toplevel",
    )
    try:
        root_text = completed.stdout.decode("utf-8", errors="strict").strip()
        root = Path(root_text).resolve(strict=True)
    except (UnicodeDecodeError, OSError) as error:
        _fail_root("registry implementation repository discovery failed", cause=error)
    return root


def _git_result(repository_root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    return _run_git_from(repository_root, "-C", str(repository_root), *arguments, check=False)


def _git_bytes(repository_root: Path, *arguments: str) -> bytes:
    completed = _run_git_from(repository_root, "-C", str(repository_root), *arguments)
    return completed.stdout


def _git_text(repository_root: Path, *arguments: str) -> str:
    raw = _git_bytes(repository_root, *arguments)
    try:
        return raw.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as error:
        _fail_root("Git authority output is not strict UTF-8", cause=error)


def _run_git_from(
    working_directory: Path,
    *arguments: str,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    git_executable = shutil.which("git")
    if git_executable is None:
        _fail_root("local Git executable is unavailable")
    try:
        completed = subprocess.run(  # noqa: S603 - fixed executable and argument array.
            [str(Path(git_executable).resolve(strict=True)), *arguments],
            cwd=working_directory,
            check=False,
            capture_output=True,
            timeout=15,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as error:
        _fail_root("local Git authority replay could not execute", cause=error)
    if check and completed.returncode != 0:
        _fail_root("local Git authority replay failed closed")
    return completed


def _require_json_object(value: JsonValue, description: str) -> JsonObject:
    if not isinstance(value, dict):
        _fail_root(f"{description} must be an exact JSON object")
    return value


@dataclass(frozen=True)
class RegistrySnapshot:
    event_count: int
    head_event_digest: str
    semantic_snapshot_digest: str
    ordered_events: tuple[JsonObject, ...]


def control_subtree_manifest() -> list[JsonValue]:
    return [
        {
            "control_class": control_class,
            "logical_name_pattern": pattern,
            "relative_destination_class": destination,
            "mutability": mutability,
            "maximum_bytes": maximum_bytes,
        }
        for control_class, pattern, destination, mutability, maximum_bytes in _CONTROL_MANIFEST_SOURCE
    ]


def cohort_policy_payload() -> JsonObject:
    return {
        "source_count": 4,
        "source_m3_count": 12,
        "geometry_case_count": 48,
        "m4_execution_count": 96,
        "result_m3_count": 144,
        "measurement_gate_count": 48,
        "decode_structure_record_count": 48,
        "manual_review_count": 48,
        "image_authority_count": 52,
        "phash_comparison_count": 1326,
        "candidate_pair_count": 24,
        "selected_dimension_count_on_pass": 2,
        "selected_pair_count_on_pass": 16,
        "ordered_candidate_dimensions": ["jaw_width", "chin_height", "eye_spacing"],
        "ordered_directions": ["DECREASE", "INCREASE"],
        "ordered_magnitudes_ppm": [15000, 30000],
        "synthetic_only_required": True,
        "clearly_adult_required": True,
        "real_person_reference_forbidden": True,
    }


COHORT_POLICY_DIGEST: Final = mirror_demo_digest(COHORT_POLICY_SCHEMA, cohort_policy_payload())


def execution_contract_payload(authority: RootReceiptAuthority) -> JsonObject:
    _validate_authority(authority)
    return {
        "change_control_id": CHANGE_CONTROL_ID,
        "task_id": TASK_ID,
        "dispatch_epoch": DISPATCH_EPOCH,
        "accepted_plan_sha": authority.accepted_plan_sha,
        "accepted_plan_tree": authority.accepted_plan_tree,
        "private_namespace_id": PRIVATE_NAMESPACE_ID,
        "evidence_root_id": EVIDENCE_ROOT_ID,
        "root_basename": EVIDENCE_ROOT_BASENAME,
        "root_receipt_schema_version": ROOT_RECEIPT_SCHEMA,
        "output_name_receipt_schema_version": OUTPUT_NAME_RECEIPT_SCHEMA,
        "output_seal_receipt_schema_version": OUTPUT_SEAL_RECEIPT_SCHEMA,
        "registry_metadata_schema_version": REGISTRY_METADATA_SCHEMA,
        "registry_event_schema_version": REGISTRY_EVENT_SCHEMA,
        "registry_intent_schema_version": REGISTRY_INTENT_SCHEMA,
        "registry_commit_receipt_schema_version": REGISTRY_COMMIT_SCHEMA,
        "registry_recovery_receipt_schema_version": REGISTRY_RECOVERY_SCHEMA,
        "registry_schema_contract_digest": REGISTRY_SCHEMA_CONTRACT_DIGEST,
        "registry_normalized_ddl_sha256": REGISTRY_NORMALIZED_DDL_SHA256,
        "registry_implementation_sha": authority.registry_implementation_sha,
        "source_generation_preregistration_schema_version": (
            SOURCE_GENERATION_PREREGISTRATION_SCHEMA
        ),
        "source_allocation_manifest_schema_version": SOURCE_ALLOCATION_MANIFEST_SCHEMA,
        "source_producer_dispatch_schema_version": SOURCE_PRODUCER_DISPATCH_SCHEMA,
        "source_generation_receipt_schema_version": SOURCE_GENERATION_RECEIPT_SCHEMA,
        "r2_schema_matrix_version": SCHEMA_MATRIX_VERSION,
        "generation_dispatch_state": GENERATION_DISPATCH_STATE,
        "core_network_policy": CORE_NETWORK_POLICY,
        "maximum_bytes": MAXIMUM_ROOT_BYTES,
    }


def build_root_name_receipt(authority: RootReceiptAuthority) -> JsonObject:
    _validate_authority(authority)
    contract_digest = mirror_demo_digest(
        EXECUTION_CONTRACT_SCHEMA,
        execution_contract_payload(authority),
    )
    payload: JsonObject = {
        "schema_version": ROOT_RECEIPT_SCHEMA,
        "evidence_root_id": EVIDENCE_ROOT_ID,
        "root_basename": EVIDENCE_ROOT_BASENAME,
        "purpose": ROOT_PURPOSE,
        "change_control_id": CHANGE_CONTROL_ID,
        "task_id": TASK_ID,
        "dispatch_epoch": DISPATCH_EPOCH,
        "accepted_plan_sha": authority.accepted_plan_sha,
        "accepted_plan_tree": authority.accepted_plan_tree,
        "private_namespace_id": PRIVATE_NAMESPACE_ID,
        "contract_digest": contract_digest,
        "cohort_policy_digest": COHORT_POLICY_DIGEST,
        "network_policy": CORE_NETWORK_POLICY,
        "allowed_roles": list(ALLOWED_ROLES),
        "allowed_output_classes": list(ALLOWED_OUTPUT_CLASSES),
        "maximum_bytes": MAXIMUM_ROOT_BYTES,
        "registry_copy_a_id": REGISTRY_COPY_A_ID,
        "registry_copy_b_id": REGISTRY_COPY_B_ID,
        "registry_schema_contract_digest": REGISTRY_SCHEMA_CONTRACT_DIGEST,
        "registry_normalized_ddl_sha256": REGISTRY_NORMALIZED_DDL_SHA256,
        "registry_implementation_sha": authority.registry_implementation_sha,
        "relative_subtree_manifest": control_subtree_manifest(),
        "created_at_utc": authority.created_at_utc,
        "retention_policy": RETENTION_POLICY,
        "cleanup_dependency_scan_policy": CLEANUP_DEPENDENCY_SCAN_POLICY,
        "canonicalization_version": CANONICALIZATION_VERSION,
    }
    payload["receipt_digest"] = mirror_demo_digest(ROOT_RECEIPT_SCHEMA, payload)
    return payload


def create_evidence_root(
    root: Path,
    authority: RootReceiptAuthority,
    *,
    excluded_roots: Sequence[Path],
    minimum_free_bytes: int = MAXIMUM_ROOT_BYTES,
) -> JsonObject:
    """Create or replay the one root; the receipt is its first immutable file."""

    with _root_creation_mutex(root.parent):
        _validate_root_candidate(
            root,
            excluded_roots=excluded_roots,
            minimum_free_bytes=minimum_free_bytes,
        )
        expected = build_root_name_receipt(authority)
        if root.exists():
            return load_root_name_receipt(root, authority)

        try:
            os.mkdir(root, 0o700)
        except FileExistsError as error:
            raise D02R2RegistryError(
                "EVIDENCE_ROOT_NAME_COLLISION_STOP",
                "the evidence root appeared during exclusive creation",
            ) from error
        _require_not_reparse(root)
        _validate_root_access_boundary(root)
        if any(root.iterdir()):  # pragma: no cover - the mutex and exclusive mkdir prevent it.
            raise D02R2RegistryError(
                "EVIDENCE_ROOT_NAME_COLLISION_STOP",
                "the new evidence root was not empty",
            )
        _write_exclusive_json(
            root,
            root / ROOT_RECEIPT_LOGICAL_NAME,
            expected,
            maximum_bytes=262_144,
        )
        _sync_directory(root)
        observed = load_root_name_receipt(root, authority)
        if observed != expected:
            raise D02R2RegistryError(
                "EVIDENCE_ROOT_NAME_COLLISION_STOP",
                "the durable root receipt failed exact replay",
            )
        return observed


def load_root_name_receipt(root: Path, authority: RootReceiptAuthority) -> JsonObject:
    _validate_authority(authority)
    _require_not_reparse(root)
    _validate_root_access_boundary(root)
    path = root / ROOT_RECEIPT_LOGICAL_NAME
    try:
        receipt = _read_canonical_json(path, maximum_bytes=262_144)
    except (OSError, D02R2RegistryError) as error:
        _fail_root("root receipt is absent, unreadable, or non-canonical", cause=error)
    _require_exact_keys(
        receipt,
        {
            "schema_version",
            "evidence_root_id",
            "root_basename",
            "purpose",
            "change_control_id",
            "task_id",
            "dispatch_epoch",
            "accepted_plan_sha",
            "accepted_plan_tree",
            "private_namespace_id",
            "contract_digest",
            "cohort_policy_digest",
            "network_policy",
            "allowed_roles",
            "allowed_output_classes",
            "maximum_bytes",
            "registry_copy_a_id",
            "registry_copy_b_id",
            "registry_schema_contract_digest",
            "registry_normalized_ddl_sha256",
            "registry_implementation_sha",
            "relative_subtree_manifest",
            "created_at_utc",
            "retention_policy",
            "cleanup_dependency_scan_policy",
            "canonicalization_version",
            "receipt_digest",
        },
        "root receipt",
    )
    if receipt["schema_version"] != ROOT_RECEIPT_SCHEMA:
        _fail_root("root receipt schema is invalid")
    if receipt["evidence_root_id"] != EVIDENCE_ROOT_ID:
        _fail_root("root receipt ID is invalid")
    if receipt["root_basename"] != EVIDENCE_ROOT_BASENAME or root.name != EVIDENCE_ROOT_BASENAME:
        _fail_root("root basename is invalid")
    _require_digest(receipt["receipt_digest"], "root receipt digest")
    claimed = cast(str, receipt["receipt_digest"])
    payload = {key: value for key, value in receipt.items() if key != "receipt_digest"}
    if mirror_demo_digest(ROOT_RECEIPT_SCHEMA, payload) != claimed:
        _fail_root("root receipt digest does not replay")
    expected = build_root_name_receipt(authority)
    if receipt != expected:
        _fail_root("root receipt fixed authority does not replay")
    return receipt


def common_genesis_payload(root_receipt: Mapping[str, JsonValue]) -> JsonObject:
    return {
        "schema_version": REGISTRY_COMMON_GENESIS_SCHEMA,
        "evidence_root_id": EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": root_receipt["receipt_digest"],
        "execution_contract_digest": root_receipt["contract_digest"],
        "registry_schema_contract_digest": REGISTRY_SCHEMA_CONTRACT_DIGEST,
        "registry_normalized_ddl_sha256": REGISTRY_NORMALIZED_DDL_SHA256,
        "registry_implementation_sha": root_receipt["registry_implementation_sha"],
        "registry_event_schema_version": REGISTRY_EVENT_SCHEMA,
        "genesis_state": "EMPTY_TWO_COPY_REGISTRY",
    }


def initialize_registry_pair(root: Path, authority: RootReceiptAuthority) -> str:
    """Initialize or replay the exact two-copy empty registry state machine."""

    root_receipt = load_root_name_receipt(root, authority)
    with _principal_mutex(root):
        return _initialize_registry_pair_locked(root, root_receipt)


def _initialize_registry_pair_locked(
    root: Path,
    root_receipt: Mapping[str, JsonValue],
) -> str:
    _create_control_directories(root)
    path_a = _control_path(root, "CONTROL_REGISTRY_A", REGISTRY_A_LOGICAL_NAME)
    path_b = _control_path(root, "CONTROL_REGISTRY_B", REGISTRY_B_LOGICAL_NAME)
    exists_a = path_a.exists()
    exists_b = path_b.exists()
    if not exists_a and not exists_b:
        _create_registry_copy(path_a, REGISTRY_COPY_A_ID, root_receipt)
        snapshot_a = validate_registry_copy(path_a, REGISTRY_COPY_A_ID, root_receipt)
        if snapshot_a.event_count != 0:
            _fail_registry("new registry A was not empty")
        _create_registry_copy(path_b, REGISTRY_COPY_B_ID, root_receipt)
    elif exists_a != exists_b:
        existing_path = path_a if exists_a else path_b
        existing_id = REGISTRY_COPY_A_ID if exists_a else REGISTRY_COPY_B_ID
        missing_path = path_b if exists_a else path_a
        missing_id = REGISTRY_COPY_B_ID if exists_a else REGISTRY_COPY_A_ID
        snapshot = validate_registry_copy(existing_path, existing_id, root_receipt)
        if snapshot.event_count != 0:
            raise D02R2RegistryError(
                "REGISTRY_INCONSISTENT_STOP",
                "one registry copy has history while the peer is absent",
            )
        _create_registry_copy(missing_path, missing_id, root_receipt)
    snapshot_a = validate_registry_copy(path_a, REGISTRY_COPY_A_ID, root_receipt)
    snapshot_b = validate_registry_copy(path_b, REGISTRY_COPY_B_ID, root_receipt)
    _require_equal_snapshots(snapshot_a, snapshot_b)
    _validate_committed_history(root, root_receipt, snapshot_a, snapshot_b)
    return "REGISTRY_READY_EMPTY" if snapshot_a.event_count == 0 else "REGISTRY_READY_REPLAYED"


def validate_registry_copy(
    path: Path,
    expected_copy_id: str,
    root_receipt: Mapping[str, JsonValue],
) -> RegistrySnapshot:
    _require_not_reparse(path)
    _require_no_sqlite_sidecars(path)
    try:
        connection = _open_registry(path)
        try:
            _validate_pragmas(connection)
            _validate_sqlite_objects(connection)
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                _fail_registry("SQLite integrity check failed")
            metadata_row = connection.execute(
                "SELECT * FROM registry_metadata WHERE singleton = 1"
            ).fetchone()
            if metadata_row is None:
                _fail_registry("registry metadata is absent")
            metadata = dict(metadata_row)
            expected_metadata = _metadata_payload(root_receipt, expected_copy_id)
            if metadata != {"singleton": 1, **expected_metadata}:
                _fail_registry("registry metadata does not replay")
            events = connection.execute(
                "SELECT * FROM registry_events ORDER BY sequence ASC"
            ).fetchall()
            transactions = connection.execute(
                "SELECT * FROM registry_transactions ORDER BY expected_sequence ASC"
            ).fetchall()
            if len(events) != len(transactions):
                _fail_registry("event and transaction cardinality differ")
            genesis = cast(str, metadata["common_genesis_digest"])
            previous = genesis
            ordered: list[JsonObject] = []
            for expected_sequence, (event_row, transaction_row) in enumerate(
                zip(events, transactions, strict=True),
                start=1,
            ):
                event = dict(event_row)
                transaction = dict(transaction_row)
                _validate_event_transaction(
                    event,
                    transaction,
                    expected_sequence=expected_sequence,
                    expected_previous=previous,
                    root_receipt=root_receipt,
                )
                previous = cast(str, event["event_digest"])
                ordered.append(
                    {
                        "sequence": expected_sequence,
                        "transaction_id": cast(str, event["transaction_id"]),
                        "output_id": cast(str, event["output_id"]),
                        "semantic_role": cast(str, event["semantic_role"]),
                        "authority_digest": cast(str, event["authority_digest"]),
                        "event_digest": previous,
                    }
                )
        finally:
            connection.close()
    except (OSError, sqlite3.Error, D02R2RegistryError) as error:
        if isinstance(error, D02R2RegistryError):
            raise
        raise D02R2RegistryError(
            "REGISTRY_INITIALIZATION_CORRUPTION_STOP",
            "registry copy could not be opened and replayed",
        ) from error
    snapshot_payload: JsonObject = {
        "schema_version": REGISTRY_SNAPSHOT_SCHEMA,
        "evidence_root_id": EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": root_receipt["receipt_digest"],
        "execution_contract_digest": root_receipt["contract_digest"],
        "registry_schema_contract_digest": REGISTRY_SCHEMA_CONTRACT_DIGEST,
        "common_genesis_digest": genesis,
        "event_count": len(ordered),
        "head_event_digest": previous,
        "ordered_events": cast(list[JsonValue], ordered),
    }
    return RegistrySnapshot(
        event_count=len(ordered),
        head_event_digest=previous,
        semantic_snapshot_digest=mirror_demo_digest(
            REGISTRY_SNAPSHOT_SCHEMA,
            snapshot_payload,
        ),
        ordered_events=tuple(ordered),
    )


def allocate_output_name_receipt(
    root: Path,
    authority: RootReceiptAuthority,
    *,
    output_id: str,
    allocation_sequence: int,
    semantic_role: str,
    logical_name: str,
    producer_task_id: str,
    expected_parent_authority: str,
    expected_media_type: str,
    maximum_bytes: int,
    allocated_at_utc: str,
) -> JsonObject:
    root_receipt = load_root_name_receipt(root, authority)
    _require_output_id(output_id)
    if allocation_sequence < 1 or allocation_sequence > 99_999_999:
        _fail_output("allocation sequence is outside the eight-digit positive range")
    destination = _role_destination(semantic_role)
    _require_logical_name(logical_name)
    _require_digest(expected_parent_authority, "expected parent authority")
    _require_media_type(expected_media_type)
    _require_timestamp(allocated_at_utc)
    if maximum_bytes < 1 or maximum_bytes > MAXIMUM_ROOT_BYTES:
        _fail_output("maximum bytes are outside the root envelope")
    allowed_tasks: list[JsonValue] = (
        [TASK_ID, SOURCE_PRODUCER_TASK_ID, REVIEW_TASK_ID]
        if semantic_role in {"SOURCE_CANDIDATE", "SOURCE_PROVENANCE"}
        else [TASK_ID, REVIEW_TASK_ID]
    )
    if producer_task_id not in allowed_tasks or producer_task_id == REVIEW_TASK_ID:
        _fail_output("producer task is not authorized for the semantic role")
    payload: JsonObject = {
        "schema_version": OUTPUT_NAME_RECEIPT_SCHEMA,
        "evidence_root_id": EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": root_receipt["receipt_digest"],
        "execution_contract_digest": root_receipt["contract_digest"],
        "output_id": output_id,
        "allocation_sequence": allocation_sequence,
        "semantic_role": semantic_role,
        "logical_name": logical_name,
        "producer_task_id": producer_task_id,
        "dispatch_epoch": DISPATCH_EPOCH,
        "allowed_tasks": allowed_tasks,
        "expected_parent_authority": expected_parent_authority,
        "expected_media_type": expected_media_type,
        "maximum_bytes": maximum_bytes,
        "relative_destination_class": destination[0],
        "allocated_at_utc": allocated_at_utc,
    }
    payload["name_receipt_digest"] = mirror_demo_digest(OUTPUT_NAME_RECEIPT_SCHEMA, payload)
    logical_receipt_name = (
        f"D02_R2_OUTPUT_NAME_RECEIPT__{allocation_sequence:08d}__{output_id}.json"
    )
    with _principal_mutex(root):
        _initialize_registry_pair_locked(root, root_receipt)
        path = _control_path(root, "CONTROL_NAME_RECEIPTS", logical_receipt_name)
        _validate_name_allocation_uniqueness(root, root_receipt, payload, path)
        if path.exists():
            observed = _load_name_receipt(path, root_receipt)
            if observed != payload:
                raise D02R2RegistryError(
                    "OUTPUT_NAME_OR_ID_COLLISION_STOP",
                    "existing name receipt differs from deterministic replay",
                )
            return observed
        _write_exclusive_json(root, path, payload, maximum_bytes=262_144)
        return _load_name_receipt(path, root_receipt)


def _validate_name_allocation_uniqueness(
    root: Path,
    root_receipt: Mapping[str, JsonValue],
    candidate: Mapping[str, JsonValue],
    candidate_path: Path,
) -> None:
    directory = root / Path(CONTROL_DESTINATIONS["CONTROL_NAME_RECEIPTS"])
    _require_not_reparse(directory)
    receipt_pattern = re.compile(
        r"D02_R2_OUTPUT_NAME_RECEIPT__[0-9]{8}__[A-Za-z0-9][A-Za-z0-9._-]{0,127}[.]json\Z"
    )
    candidate_relative = _relative_output_path(candidate)
    for entry in directory.iterdir():
        _require_not_reparse(entry)
        if not entry.is_file() or receipt_pattern.fullmatch(entry.name) is None:
            _fail_output("unknown or malformed output name receipt object")
        observed = _load_name_receipt(entry, root_receipt)
        if entry == candidate_path:
            continue
        collisions = (
            observed["output_id"] == candidate["output_id"],
            observed["allocation_sequence"] == candidate["allocation_sequence"],
            _relative_output_path(observed) == candidate_relative,
            observed["name_receipt_digest"] == candidate["name_receipt_digest"],
        )
        if any(collisions):
            raise D02R2RegistryError(
                "OUTPUT_NAME_OR_ID_COLLISION_STOP",
                "output ID, allocation sequence, destination, or receipt digest is already allocated",
            )


def seal_output(
    root: Path,
    authority: RootReceiptAuthority,
    name_receipt_logical_name: str,
    *,
    media_type: str,
    sealed_at_utc: str,
    authority_digest: str | None = None,
    retention: str = RETENTION_POLICY,
    custody: str = DEFAULT_CUSTODY,
) -> JsonObject:
    root_receipt = load_root_name_receipt(root, authority)
    with _principal_mutex(root):
        return _seal_output_locked(
            root,
            root_receipt,
            name_receipt_logical_name,
            media_type=media_type,
            sealed_at_utc=sealed_at_utc,
            authority_digest=authority_digest,
            retention=retention,
            custody=custody,
        )


def _seal_output_locked(
    root: Path,
    root_receipt: Mapping[str, JsonValue],
    name_receipt_logical_name: str,
    *,
    media_type: str,
    sealed_at_utc: str,
    authority_digest: str | None,
    retention: str,
    custody: str,
) -> JsonObject:
    name_path = _control_path(root, "CONTROL_NAME_RECEIPTS", name_receipt_logical_name)
    name_receipt = _load_name_receipt(name_path, root_receipt)
    _require_media_type(media_type)
    if media_type != name_receipt["expected_media_type"]:
        _fail_output("sealed media type differs from the name receipt")
    _require_timestamp(sealed_at_utc)
    output_path = _output_path(root, name_receipt)
    _require_not_reparse(output_path)
    if not output_path.is_file():
        _fail_output("allocated output is not a regular file")
    actual_sha256, byte_size = _hash_file(
        output_path,
        maximum_bytes=cast(int, name_receipt["maximum_bytes"]),
    )
    resolved_authority = authority_digest
    if resolved_authority is None:
        resolved_authority = mirror_demo_digest(
            SEALED_BINARY_AUTHORITY_SCHEMA,
            {
                "semantic_role": name_receipt["semantic_role"],
                "actual_sha256": actual_sha256,
                "byte_size": byte_size,
                "media_type": media_type,
                "name_receipt_digest": name_receipt["name_receipt_digest"],
            },
        )
    _require_digest(resolved_authority, "sealed authority digest")
    payload: JsonObject = {
        "schema_version": OUTPUT_SEAL_RECEIPT_SCHEMA,
        "evidence_root_id": EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": root_receipt["receipt_digest"],
        "execution_contract_digest": root_receipt["contract_digest"],
        "output_id": name_receipt["output_id"],
        "name_receipt_digest": name_receipt["name_receipt_digest"],
        "semantic_role": name_receipt["semantic_role"],
        "producer_task_id": name_receipt["producer_task_id"],
        "actual_sha256": actual_sha256,
        "byte_size": byte_size,
        "media_type": media_type,
        "authority_digest": resolved_authority,
        "retention": retention,
        "custody": custody,
        "sealed_at_utc": sealed_at_utc,
    }
    payload["seal_digest"] = mirror_demo_digest(OUTPUT_SEAL_RECEIPT_SCHEMA, payload)
    allocation_sequence = cast(int, name_receipt["allocation_sequence"])
    output_id = cast(str, name_receipt["output_id"])
    seal_name = f"D02_R2_OUTPUT_SEAL_RECEIPT__{allocation_sequence:08d}__{output_id}.json"
    path = _control_path(root, "CONTROL_SEAL_RECEIPTS", seal_name)
    if path.exists():
        observed = _load_seal_receipt(path, root_receipt, name_receipt)
        if observed != payload:
            raise D02R2RegistryError(
                "OUTPUT_SEAL_RECEIPT_PARTIAL_OR_CORRUPT_STOP",
                "existing seal receipt differs from deterministic replay",
            )
        _rehash_sealed_output(root, name_receipt, observed)
        return observed
    _write_exclusive_json(root, path, payload, maximum_bytes=262_144)
    return _load_seal_receipt(path, root_receipt, name_receipt)


def recover_output_seal(
    root: Path,
    authority: RootReceiptAuthority,
    name_receipt_logical_name: str,
    *,
    media_type: str,
    sealed_at_utc: str,
    recovery_attempt: int,
    principal_authority_digest: str,
    created_at_utc: str,
    authority_digest: str | None = None,
    retention: str = RETENTION_POLICY,
    custody: str = DEFAULT_CUSTODY,
) -> JsonObject:
    """Recover the sole deterministic seal after durable output publication."""

    if recovery_attempt < 1 or recovery_attempt > 9_999:
        _fail_registry("recovery attempt must fit the four-digit positive range")
    _require_digest(principal_authority_digest, "Principal recovery authority")
    _require_timestamp(created_at_utc)
    root_receipt = load_root_name_receipt(root, authority)
    with _principal_mutex(root):
        _initialize_registry_pair_locked(root, root_receipt)
        name_receipt = _load_name_receipt(
            _control_path(root, "CONTROL_NAME_RECEIPTS", name_receipt_logical_name),
            root_receipt,
        )
        allocation_sequence = cast(int, name_receipt["allocation_sequence"])
        output_id = _require_string(name_receipt["output_id"], "output ID")
        seal_name = f"D02_R2_OUTPUT_SEAL_RECEIPT__{allocation_sequence:08d}__{output_id}.json"
        seal_path = _control_path(root, "CONTROL_SEAL_RECEIPTS", seal_name)
        if seal_path.exists():
            raise D02R2RegistryError(
                "OUTPUT_SEAL_RECEIPT_PARTIAL_OR_CORRUPT_STOP",
                "seal recovery is only legal when the deterministic path is absent",
            )
        seal_receipt = _seal_output_locked(
            root,
            root_receipt,
            name_receipt_logical_name,
            media_type=media_type,
            sealed_at_utc=sealed_at_utc,
            authority_digest=authority_digest,
            retention=retention,
            custody=custody,
        )
        transaction_id = _transaction_id(root_receipt, name_receipt, seal_receipt)
        path_a, path_b = _registry_paths(root)
        snapshot_a = validate_registry_copy(path_a, REGISTRY_COPY_A_ID, root_receipt)
        snapshot_b = validate_registry_copy(path_b, REGISTRY_COPY_B_ID, root_receipt)
        _require_equal_snapshots(snapshot_a, snapshot_b)
        if _snapshot_has_transaction(snapshot_a, transaction_id):
            raise D02R2RegistryError(
                "IMPOSSIBLE_ORDER_OR_CUSTODY_CORRUPTION_STOP",
                "registry row exists before the recovered seal authority",
            )
        return _write_recovery_receipt(
            root,
            root_receipt=root_receipt,
            transaction_id=transaction_id,
            observed_intent_digest=None,
            resulting_intent_digest=None,
            observed_intent_bytes_sha256=None,
            recovery_attempt=recovery_attempt,
            observed_prior_state="OUTPUT_DURABLE_SEAL_ABSENT",
            output_rehash_digest=_require_string(
                seal_receipt["actual_sha256"], "sealed output digest"
            ),
            copy_a_head_event_digest=snapshot_a.head_event_digest,
            copy_b_head_event_digest=snapshot_b.head_event_digest,
            recovery_action="REHASH_OUTPUT_AND_CREATE_DETERMINISTIC_SEAL",
            recovery_outcome="SEAL_DURABLE_INTENT_ABSENT",
            principal_authority_digest=principal_authority_digest,
            created_at_utc=created_at_utc,
        )


def register_sealed_output(
    root: Path,
    authority: RootReceiptAuthority,
    name_receipt_logical_name: str,
    seal_receipt_logical_name: str,
    *,
    intent_created_at_utc: str,
) -> JsonObject:
    """Commit one sealed output to A then B and publish the immutable receipt."""

    _require_timestamp(intent_created_at_utc)
    root_receipt = load_root_name_receipt(root, authority)
    name_receipt = _load_name_receipt(
        _control_path(root, "CONTROL_NAME_RECEIPTS", name_receipt_logical_name),
        root_receipt,
    )
    seal_receipt = _load_seal_receipt(
        _control_path(root, "CONTROL_SEAL_RECEIPTS", seal_receipt_logical_name),
        root_receipt,
        name_receipt,
    )
    _rehash_sealed_output(root, name_receipt, seal_receipt)
    with _principal_mutex(root):
        _initialize_registry_pair_locked(root, root_receipt)
        path_a, path_b = _registry_paths(root)
        snapshot_a = validate_registry_copy(path_a, REGISTRY_COPY_A_ID, root_receipt)
        snapshot_b = validate_registry_copy(path_b, REGISTRY_COPY_B_ID, root_receipt)
        _require_equal_snapshots(snapshot_a, snapshot_b)
        transaction_id = _transaction_id(root_receipt, name_receipt, seal_receipt)
        intent_path = _intent_path(root, transaction_id)
        commit_path = _commit_path(root, transaction_id)
        if commit_path.exists():
            return _load_commit_receipt(
                commit_path,
                root_receipt=root_receipt,
                expected_transaction_id=transaction_id,
            )
        if intent_path.exists():
            raise D02R2RegistryError(
                "REGISTRY_RECOVERY_REQUIRED",
                "an immutable intent already exists without a commit receipt",
            )
        intent, canonical_event = _build_intent_and_event(
            root_receipt,
            name_receipt,
            seal_receipt,
            transaction_id=transaction_id,
            expected_sequence=snapshot_a.event_count + 1,
            previous_head=snapshot_a.head_event_digest,
            created_at_utc=intent_created_at_utc,
        )
        _write_exclusive_json(root, intent_path, intent, maximum_bytes=262_144)
        _append_registry_copy(path_a, intent, canonical_event)
        validated_a = validate_registry_copy(path_a, REGISTRY_COPY_A_ID, root_receipt)
        _append_registry_copy(path_b, intent, canonical_event)
        validated_b = validate_registry_copy(path_b, REGISTRY_COPY_B_ID, root_receipt)
        _require_equal_snapshots(validated_a, validated_b)
        commit = _build_commit_receipt(
            root_receipt,
            intent,
            validated_a,
            validated_b,
        )
        _write_exclusive_json(root, commit_path, commit, maximum_bytes=262_144)
        return _load_commit_receipt(
            commit_path,
            root_receipt=root_receipt,
            expected_transaction_id=transaction_id,
        )


def recover_registry_transaction(
    root: Path,
    authority: RootReceiptAuthority,
    name_receipt_logical_name: str,
    seal_receipt_logical_name: str,
    *,
    recovery_attempt: int,
    principal_authority_digest: str,
    created_at_utc: str,
    intent_created_at_utc: str | None = None,
) -> JsonObject:
    """Replay one interrupted sealed-output transaction under the Principal mutex."""

    if recovery_attempt < 1 or recovery_attempt > 9_999:
        _fail_registry("recovery attempt must fit the four-digit positive range")
    _require_digest(principal_authority_digest, "Principal recovery authority")
    _require_timestamp(created_at_utc)
    if intent_created_at_utc is not None:
        _require_timestamp(intent_created_at_utc)
    root_receipt = load_root_name_receipt(root, authority)
    name_receipt = _load_name_receipt(
        _control_path(root, "CONTROL_NAME_RECEIPTS", name_receipt_logical_name),
        root_receipt,
    )
    seal_receipt = _load_seal_receipt(
        _control_path(root, "CONTROL_SEAL_RECEIPTS", seal_receipt_logical_name),
        root_receipt,
        name_receipt,
    )
    _rehash_sealed_output(root, name_receipt, seal_receipt)
    transaction_id = _transaction_id(root_receipt, name_receipt, seal_receipt)
    intent_path = _intent_path(root, transaction_id)
    commit_path = _commit_path(root, transaction_id)
    with _principal_mutex(root):
        path_a, path_b = _registry_paths(root)
        if not path_a.exists() or not path_b.exists():
            raise D02R2RegistryError(
                "REGISTRY_INCONSISTENT_STOP",
                "recovery requires both initialized registry copies",
            )
        snapshot_a = validate_registry_copy(path_a, REGISTRY_COPY_A_ID, root_receipt)
        snapshot_b = validate_registry_copy(path_b, REGISTRY_COPY_B_ID, root_receipt)
        observed_intent_bytes_sha256: str | None = None
        observed_intent_digest: str | None = None
        prior_state: str
        action: str
        if intent_path.exists():
            observed_intent_bytes_sha256, _ = _hash_file(
                intent_path,
                maximum_bytes=262_144,
            )
            try:
                intent, canonical_event = _load_intent(
                    intent_path,
                    root_receipt=root_receipt,
                    name_receipt=name_receipt,
                    seal_receipt=seal_receipt,
                    expected_transaction_id=transaction_id,
                )
            except D02R2RegistryError as error:
                receipt = _write_recovery_receipt(
                    root,
                    root_receipt=root_receipt,
                    transaction_id=transaction_id,
                    observed_intent_digest=None,
                    resulting_intent_digest=None,
                    observed_intent_bytes_sha256=observed_intent_bytes_sha256,
                    recovery_attempt=recovery_attempt,
                    observed_prior_state="REGISTRY_INTENT_PARTIAL_OR_CORRUPT_STOP",
                    output_rehash_digest=_require_string(
                        seal_receipt["actual_sha256"], "sealed output digest"
                    ),
                    copy_a_head_event_digest=snapshot_a.head_event_digest,
                    copy_b_head_event_digest=snapshot_b.head_event_digest,
                    recovery_action="PRESERVE_CORRUPT_INTENT_AND_STOP",
                    recovery_outcome="REGISTRY_INTENT_PARTIAL_OR_CORRUPT_STOP",
                    principal_authority_digest=principal_authority_digest,
                    created_at_utc=created_at_utc,
                )
                raise D02R2RegistryError(
                    "REGISTRY_INTENT_PARTIAL_OR_CORRUPT_STOP",
                    f"intent replay failed; recovery receipt {receipt['recovery_receipt_digest']}",
                ) from error
            observed_intent_digest = _require_string(
                intent["intent_digest"], "observed intent digest"
            )
            prior_state = _derive_registry_recovery_state(
                snapshot_a,
                snapshot_b,
                transaction_id=transaction_id,
                commit_exists=commit_path.exists(),
            )
            action = _replay_intent_to_registry_copies(
                path_a,
                path_b,
                root_receipt=root_receipt,
                intent=intent,
                canonical_event=canonical_event,
                snapshot_a=snapshot_a,
                snapshot_b=snapshot_b,
            )
        else:
            if commit_path.exists():
                raise D02R2RegistryError(
                    "IMPOSSIBLE_ORDER_OR_CUSTODY_CORRUPTION_STOP",
                    "commit receipt exists while the immutable intent is absent",
                )
            _require_equal_snapshots(snapshot_a, snapshot_b)
            if _snapshot_has_transaction(snapshot_a, transaction_id):
                raise D02R2RegistryError(
                    "IMPOSSIBLE_ORDER_OR_CUSTODY_CORRUPTION_STOP",
                    "registry row exists while the immutable intent is absent",
                )
            chosen_timestamp = intent_created_at_utc or created_at_utc
            intent, canonical_event = _build_intent_and_event(
                root_receipt,
                name_receipt,
                seal_receipt,
                transaction_id=transaction_id,
                expected_sequence=snapshot_a.event_count + 1,
                previous_head=snapshot_a.head_event_digest,
                created_at_utc=chosen_timestamp,
            )
            _write_exclusive_json(root, intent_path, intent, maximum_bytes=262_144)
            prior_state = "SEAL_DURABLE_INTENT_ABSENT"
            action = _replay_intent_to_registry_copies(
                path_a,
                path_b,
                root_receipt=root_receipt,
                intent=intent,
                canonical_event=canonical_event,
                snapshot_a=snapshot_a,
                snapshot_b=snapshot_b,
            )
        resulting_intent_digest = _require_string(
            intent["intent_digest"], "resulting intent digest"
        )
        final_a = validate_registry_copy(path_a, REGISTRY_COPY_A_ID, root_receipt)
        final_b = validate_registry_copy(path_b, REGISTRY_COPY_B_ID, root_receipt)
        _require_equal_snapshots(final_a, final_b)
        expected_sequence = cast(int, intent["expected_sequence"])
        if final_a.event_count != expected_sequence:
            _fail_registry("recovered registry count differs from the immutable intent")
        expected_commit = _build_commit_receipt(root_receipt, intent, final_a, final_b)
        if commit_path.exists():
            try:
                _load_commit_receipt(
                    commit_path,
                    root_receipt=root_receipt,
                    expected_transaction_id=transaction_id,
                    expected_intent=intent,
                    expected_snapshot_a=final_a,
                    expected_snapshot_b=final_b,
                )
            except (OSError, D02R2RegistryError) as error:
                receipt = _write_recovery_receipt(
                    root,
                    root_receipt=root_receipt,
                    transaction_id=transaction_id,
                    observed_intent_digest=observed_intent_digest,
                    resulting_intent_digest=resulting_intent_digest,
                    observed_intent_bytes_sha256=observed_intent_bytes_sha256,
                    recovery_attempt=recovery_attempt,
                    observed_prior_state="REGISTRY_COMMIT_RECEIPT_PARTIAL_OR_CORRUPT_STOP",
                    output_rehash_digest=_require_string(
                        seal_receipt["actual_sha256"], "sealed output digest"
                    ),
                    copy_a_head_event_digest=final_a.head_event_digest,
                    copy_b_head_event_digest=final_b.head_event_digest,
                    recovery_action="PRESERVE_CORRUPT_COMMIT_RECEIPT_AND_STOP",
                    recovery_outcome="REGISTRY_COMMIT_RECEIPT_PARTIAL_OR_CORRUPT_STOP",
                    principal_authority_digest=principal_authority_digest,
                    created_at_utc=created_at_utc,
                )
                raise D02R2RegistryError(
                    "REGISTRY_COMMIT_RECEIPT_PARTIAL_OR_CORRUPT_STOP",
                    f"commit replay failed; recovery receipt {receipt['recovery_receipt_digest']}",
                ) from error
        else:
            _write_exclusive_json(root, commit_path, expected_commit, maximum_bytes=262_144)
        recovery_receipt = _write_recovery_receipt(
            root,
            root_receipt=root_receipt,
            transaction_id=transaction_id,
            observed_intent_digest=observed_intent_digest,
            resulting_intent_digest=resulting_intent_digest,
            observed_intent_bytes_sha256=observed_intent_bytes_sha256,
            recovery_attempt=recovery_attempt,
            observed_prior_state=prior_state,
            output_rehash_digest=_require_string(
                seal_receipt["actual_sha256"], "sealed output digest"
            ),
            copy_a_head_event_digest=final_a.head_event_digest,
            copy_b_head_event_digest=final_b.head_event_digest,
            recovery_action=action,
            recovery_outcome="COMMITTED_BOTH_COPIES",
            principal_authority_digest=principal_authority_digest,
            created_at_utc=created_at_utc,
        )
        _validate_committed_history(root, root_receipt, final_a, final_b)
        return recovery_receipt


def _derive_registry_recovery_state(
    snapshot_a: RegistrySnapshot,
    snapshot_b: RegistrySnapshot,
    *,
    transaction_id: str,
    commit_exists: bool,
) -> str:
    has_a = _snapshot_has_transaction(snapshot_a, transaction_id)
    has_b = _snapshot_has_transaction(snapshot_b, transaction_id)
    if not has_a and not has_b:
        return "INTENT_DURABLE_BOTH_COPIES_ABSENT"
    if has_a and not has_b:
        return "REGISTRY_ONE_COPY_PREPARED_STOP"
    if not has_a and has_b:
        return "REGISTRY_INCONSISTENT_STOP"
    if snapshot_a != snapshot_b:
        return "REGISTRY_INCONSISTENT_STOP"
    return "COMMITTED_BOTH_COPIES" if commit_exists else "BOTH_COPIES_PREPARED_NOT_COMMITTED"


def _replay_intent_to_registry_copies(
    path_a: Path,
    path_b: Path,
    *,
    root_receipt: Mapping[str, JsonValue],
    intent: Mapping[str, JsonValue],
    canonical_event: Mapping[str, JsonValue],
    snapshot_a: RegistrySnapshot,
    snapshot_b: RegistrySnapshot,
) -> str:
    transaction_id = _require_string(intent["transaction_id"], "intent transaction ID")
    expected_sequence = cast(int, intent["expected_sequence"])
    previous_head = _require_string(intent["expected_copy_a_previous_head"], "intent previous head")
    has_a = _snapshot_has_transaction(snapshot_a, transaction_id)
    has_b = _snapshot_has_transaction(snapshot_b, transaction_id)
    if not has_a and not has_b:
        _require_equal_snapshots(snapshot_a, snapshot_b)
        if (
            snapshot_a.event_count + 1 != expected_sequence
            or snapshot_a.head_event_digest != previous_head
        ):
            _fail_registry("current registry heads no longer match the immutable intent")
        _append_registry_copy(path_a, intent, canonical_event)
        _append_registry_copy(path_b, intent, canonical_event)
        return "APPEND_EXACT_INTENT_TO_COPY_A_THEN_COPY_B_AND_COMMIT"
    if has_a and not has_b:
        if snapshot_a.event_count != expected_sequence:
            _fail_registry("copy A prepared event is not the intent's final sequence")
        if snapshot_b.event_count + 1 != expected_sequence:
            _fail_registry("copy B is not the exact prefix required by the intent")
        if snapshot_b.head_event_digest != previous_head:
            _fail_registry("copy B head no longer matches the immutable intent")
        if snapshot_a.ordered_events[:-1] != snapshot_b.ordered_events:
            _fail_registry("copy A is not copy B plus the exact final intent event")
        expected_projection = _event_projection(canonical_event)
        if snapshot_a.ordered_events[-1] != expected_projection:
            _fail_registry("copy A final event differs from the immutable intent")
        _append_registry_copy(path_b, intent, canonical_event)
        return "APPEND_EXACT_INTENT_TO_COPY_B_AND_COMMIT"
    if not has_a and has_b:
        raise D02R2RegistryError(
            "REGISTRY_INCONSISTENT_STOP",
            "copy B contains a transaction absent from copy A",
        )
    _require_equal_snapshots(snapshot_a, snapshot_b)
    if snapshot_a.event_count != expected_sequence:
        _fail_registry("prepared transaction is not the intent's final sequence")
    if snapshot_a.ordered_events[-1] != _event_projection(canonical_event):
        _fail_registry("prepared transaction differs from the immutable intent")
    return "VERIFY_BOTH_PREPARED_COPIES_AND_COMMIT"


def _snapshot_has_transaction(snapshot: RegistrySnapshot, transaction_id: str) -> bool:
    return any(event["transaction_id"] == transaction_id for event in snapshot.ordered_events)


def _event_projection(event: Mapping[str, JsonValue]) -> JsonObject:
    return {
        "sequence": event["SEQUENCE"],
        "transaction_id": event["TRANSACTION_ID"],
        "output_id": event["OUTPUT_ID"],
        "semantic_role": event["SEMANTIC_ROLE"],
        "authority_digest": event["AUTHORITY"],
        "event_digest": event["EVENT_DIGEST"],
    }


def _write_recovery_receipt(
    root: Path,
    *,
    root_receipt: Mapping[str, JsonValue],
    transaction_id: str,
    observed_intent_digest: str | None,
    resulting_intent_digest: str | None,
    observed_intent_bytes_sha256: str | None,
    recovery_attempt: int,
    observed_prior_state: str,
    output_rehash_digest: str,
    copy_a_head_event_digest: str,
    copy_b_head_event_digest: str,
    recovery_action: str,
    recovery_outcome: str,
    principal_authority_digest: str,
    created_at_utc: str,
) -> JsonObject:
    payload: JsonObject = {
        "schema_version": REGISTRY_RECOVERY_SCHEMA,
        "evidence_root_id": EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": root_receipt["receipt_digest"],
        "execution_contract_digest": root_receipt["contract_digest"],
        "transaction_id": transaction_id,
        "observed_intent_digest": observed_intent_digest,
        "resulting_intent_digest": resulting_intent_digest,
        "observed_intent_bytes_sha256": observed_intent_bytes_sha256,
        "recovery_attempt": recovery_attempt,
        "observed_prior_state": observed_prior_state,
        "output_rehash_digest": output_rehash_digest,
        "copy_a_head_event_digest": copy_a_head_event_digest,
        "copy_b_head_event_digest": copy_b_head_event_digest,
        "recovery_action": recovery_action,
        "recovery_outcome": recovery_outcome,
        "principal_authority_digest": principal_authority_digest,
        "created_at_utc": created_at_utc,
    }
    payload["recovery_receipt_digest"] = mirror_demo_digest(REGISTRY_RECOVERY_SCHEMA, payload)
    logical_name = (
        f"D02_R2_REGISTRY_RECOVERY_RECEIPT__{transaction_id}__{recovery_attempt:04d}.json"
    )
    path = _control_path(root, "CONTROL_REGISTRY_RECOVERY", logical_name)
    _write_exclusive_json(root, path, payload, maximum_bytes=262_144)
    observed = _read_canonical_json(path, maximum_bytes=262_144)
    if observed != payload:
        _fail_registry("recovery receipt failed exact durable replay")
    return observed


def _build_intent_and_event(
    root_receipt: Mapping[str, JsonValue],
    name_receipt: Mapping[str, JsonValue],
    seal_receipt: Mapping[str, JsonValue],
    *,
    transaction_id: str,
    expected_sequence: int,
    previous_head: str,
    created_at_utc: str,
) -> tuple[JsonObject, JsonObject]:
    relative = _relative_output_path(name_receipt)
    locator = "r2rel1:" + base64.urlsafe_b64encode(relative.encode("utf-8")).decode("ascii").rstrip(
        "="
    )
    event: JsonObject = {
        "SCHEMA_VERSION": REGISTRY_EVENT_SCHEMA,
        "EVIDENCE_ROOT_ID": EVIDENCE_ROOT_ID,
        "ROOT_NAME_RECEIPT_DIGEST": root_receipt["receipt_digest"],
        "EXECUTION_CONTRACT_DIGEST": root_receipt["contract_digest"],
        "OUTPUT_ID": name_receipt["output_id"],
        "SEMANTIC_ROLE": name_receipt["semantic_role"],
        "CREATING_TASK": name_receipt["producer_task_id"],
        "OPAQUE_LOCATOR": locator,
        "EXPECTED_DIGEST": seal_receipt["actual_sha256"],
        "ACTUAL_DIGEST": seal_receipt["actual_sha256"],
        "BYTE_SIZE": seal_receipt["byte_size"],
        "MEDIA_TYPE": seal_receipt["media_type"],
        "AUTHORITY": seal_receipt["authority_digest"],
        "ALLOWED_TASKS": name_receipt["allowed_tasks"],
        "RETENTION": seal_receipt["retention"],
        "CUSTODY": seal_receipt["custody"],
        "RECOVERY_STATUS": "NOT_REQUIRED",
        "BACKUP_STATUS": "TWO_LOGICAL_COPIES_SAME_ROOT_REQUIRED",
        "CLEANUP_STATUS": "RETAINED",
        "NAME_RECEIPT_DIGEST": name_receipt["name_receipt_digest"],
        "SEAL_RECEIPT_DIGEST": seal_receipt["seal_digest"],
        "TRANSACTION_ID": transaction_id,
        "SEQUENCE": expected_sequence,
        "PREVIOUS_EVENT_DIGEST": previous_head,
    }
    event["EVENT_DIGEST"] = mirror_demo_digest(REGISTRY_EVENT_SCHEMA, event)
    canonical_event = canonical_json_bytes(event)
    commit_name = f"D02_R2_REGISTRY_COMMIT_RECEIPT__{transaction_id}.json"
    intent: JsonObject = {
        "schema_version": REGISTRY_INTENT_SCHEMA,
        "evidence_root_id": EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": root_receipt["receipt_digest"],
        "execution_contract_digest": root_receipt["contract_digest"],
        "transaction_id": transaction_id,
        "output_id": name_receipt["output_id"],
        "semantic_role": name_receipt["semantic_role"],
        "authority_digest": seal_receipt["authority_digest"],
        "name_receipt_digest": name_receipt["name_receipt_digest"],
        "seal_receipt_digest": seal_receipt["seal_digest"],
        "canonical_event_digest": event["EVENT_DIGEST"],
        "canonical_event_json_b64": base64.b64encode(canonical_event).decode("ascii"),
        "expected_copy_a_previous_head": previous_head,
        "expected_copy_b_previous_head": previous_head,
        "expected_sequence": expected_sequence,
        "commit_receipt_logical_name": commit_name,
        "commit_receipt_created_at_utc": created_at_utc,
        "intent_created_at_utc": created_at_utc,
    }
    intent["intent_digest"] = mirror_demo_digest(REGISTRY_INTENT_SCHEMA, intent)
    return intent, event


def _build_commit_receipt(
    root_receipt: Mapping[str, JsonValue],
    intent: Mapping[str, JsonValue],
    snapshot_a: RegistrySnapshot,
    snapshot_b: RegistrySnapshot,
) -> JsonObject:
    payload: JsonObject = {
        "schema_version": REGISTRY_COMMIT_SCHEMA,
        "evidence_root_id": EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": root_receipt["receipt_digest"],
        "execution_contract_digest": root_receipt["contract_digest"],
        "transaction_id": intent["transaction_id"],
        "intent_digest": intent["intent_digest"],
        "output_id": intent["output_id"],
        "canonical_event_digest": intent["canonical_event_digest"],
        "copy_a_event_count": snapshot_a.event_count,
        "copy_a_head_event_digest": snapshot_a.head_event_digest,
        "copy_a_semantic_snapshot_digest": snapshot_a.semantic_snapshot_digest,
        "copy_b_event_count": snapshot_b.event_count,
        "copy_b_head_event_digest": snapshot_b.head_event_digest,
        "copy_b_semantic_snapshot_digest": snapshot_b.semantic_snapshot_digest,
        "commit_state": "COMMITTED_BOTH_COPIES",
        "created_at_utc": intent["commit_receipt_created_at_utc"],
    }
    payload["commit_receipt_digest"] = mirror_demo_digest(REGISTRY_COMMIT_SCHEMA, payload)
    return payload


def _load_intent(
    path: Path,
    *,
    root_receipt: Mapping[str, JsonValue],
    name_receipt: Mapping[str, JsonValue],
    seal_receipt: Mapping[str, JsonValue],
    expected_transaction_id: str,
) -> tuple[JsonObject, JsonObject]:
    intent = _read_canonical_json(path, maximum_bytes=262_144)
    expected_keys = {
        "schema_version",
        "evidence_root_id",
        "root_name_receipt_digest",
        "execution_contract_digest",
        "transaction_id",
        "output_id",
        "semantic_role",
        "authority_digest",
        "name_receipt_digest",
        "seal_receipt_digest",
        "canonical_event_digest",
        "canonical_event_json_b64",
        "expected_copy_a_previous_head",
        "expected_copy_b_previous_head",
        "expected_sequence",
        "commit_receipt_logical_name",
        "commit_receipt_created_at_utc",
        "intent_created_at_utc",
        "intent_digest",
    }
    _require_exact_keys(intent, expected_keys, "registry transaction intent")
    if intent["schema_version"] != REGISTRY_INTENT_SCHEMA:
        _fail_registry("intent schema is invalid")
    fixed_equalities: dict[str, JsonValue] = {
        "evidence_root_id": EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": root_receipt["receipt_digest"],
        "execution_contract_digest": root_receipt["contract_digest"],
        "transaction_id": expected_transaction_id,
        "output_id": name_receipt["output_id"],
        "semantic_role": name_receipt["semantic_role"],
        "authority_digest": seal_receipt["authority_digest"],
        "name_receipt_digest": name_receipt["name_receipt_digest"],
        "seal_receipt_digest": seal_receipt["seal_digest"],
        "commit_receipt_logical_name": (
            f"D02_R2_REGISTRY_COMMIT_RECEIPT__{expected_transaction_id}.json"
        ),
    }
    if any(intent[key] != value for key, value in fixed_equalities.items()):
        _fail_registry("intent authority binding differs from immutable receipts")
    if intent["expected_copy_a_previous_head"] != intent["expected_copy_b_previous_head"]:
        _fail_registry("intent registry heads are not equal")
    expected_sequence = intent["expected_sequence"]
    if not isinstance(expected_sequence, int) or isinstance(expected_sequence, bool):
        _fail_registry("intent expected sequence is not an integer")
    if expected_sequence < 1:
        _fail_registry("intent expected sequence is invalid")
    previous_head = _require_string(intent["expected_copy_a_previous_head"], "intent previous head")
    _require_digest(previous_head, "intent previous head")
    created_at = _require_string(intent["intent_created_at_utc"], "intent timestamp")
    _require_timestamp(created_at)
    if intent["commit_receipt_created_at_utc"] != created_at:
        _fail_registry("intent timestamps differ")
    encoded = _require_string(intent["canonical_event_json_b64"], "canonical event bytes")
    try:
        event_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise D02R2RegistryError(
            "REGISTRY_INTENT_PARTIAL_OR_CORRUPT_STOP",
            "intent canonical event base64 is invalid",
        ) from error
    event = _parse_canonical_json_bytes(event_bytes)
    expected_intent, expected_event = _build_intent_and_event(
        root_receipt,
        name_receipt,
        seal_receipt,
        transaction_id=expected_transaction_id,
        expected_sequence=expected_sequence,
        previous_head=previous_head,
        created_at_utc=created_at,
    )
    if intent != expected_intent or event != expected_event:
        raise D02R2RegistryError(
            "REGISTRY_INTENT_PARTIAL_OR_CORRUPT_STOP",
            "intent or canonical event does not exactly replay",
        )
    return intent, event


def _validate_committed_history(
    root: Path,
    root_receipt: Mapping[str, JsonValue],
    snapshot_a: RegistrySnapshot,
    snapshot_b: RegistrySnapshot,
) -> None:
    _require_equal_snapshots(snapshot_a, snapshot_b)
    _validate_recovery_receipts(root, root_receipt)
    expected_transaction_ids = {
        _require_string(event["transaction_id"], "snapshot transaction ID")
        for event in snapshot_a.ordered_events
    }
    observed_intents = _control_transaction_ids(root, "CONTROL_REGISTRY_INTENTS")
    observed_commits = _control_transaction_ids(root, "CONTROL_REGISTRY_COMMITS")
    if observed_intents != expected_transaction_ids or observed_commits != expected_transaction_ids:
        raise D02R2RegistryError(
            "REGISTRY_RECOVERY_REQUIRED",
            "registry rows, intents, and commit receipts are not a complete equal set",
        )
    prefix: list[JsonObject] = []
    for projection in snapshot_a.ordered_events:
        output_id = _require_string(projection["output_id"], "snapshot output ID")
        transaction_id = _require_string(projection["transaction_id"], "snapshot transaction ID")
        name_receipt, seal_receipt = _resolve_output_receipts(
            root,
            root_receipt,
            output_id=output_id,
        )
        intent, event = _load_intent(
            _intent_path(root, transaction_id),
            root_receipt=root_receipt,
            name_receipt=name_receipt,
            seal_receipt=seal_receipt,
            expected_transaction_id=transaction_id,
        )
        if event["EVENT_DIGEST"] != projection["event_digest"]:
            _fail_registry("intent event differs from the registry event")
        prefix.append(projection)
        prefix_snapshot = _snapshot_from_ordered(root_receipt, prefix)
        _load_commit_receipt(
            _commit_path(root, transaction_id),
            root_receipt=root_receipt,
            expected_transaction_id=transaction_id,
            expected_intent=intent,
            expected_snapshot_a=prefix_snapshot,
            expected_snapshot_b=prefix_snapshot,
        )
        _rehash_sealed_output(root, name_receipt, seal_receipt)


def _validate_recovery_receipts(
    root: Path,
    root_receipt: Mapping[str, JsonValue],
) -> None:
    directory = root / Path(CONTROL_DESTINATIONS["CONTROL_REGISTRY_RECOVERY"])
    _require_not_reparse(directory)
    pattern = re.compile(r"D02_R2_REGISTRY_RECOVERY_RECEIPT__([0-9a-f]{64})__([0-9]{4})[.]json\Z")
    for entry in directory.iterdir():
        _require_not_reparse(entry)
        match = pattern.fullmatch(entry.name)
        if match is None or not entry.is_file() or int(match.group(2)) < 1:
            _fail_registry("unknown or malformed registry recovery receipt")
        try:
            receipt = _read_canonical_json(entry, maximum_bytes=262_144)
        except (OSError, D02R2RegistryError):
            _fail_registry("registry recovery receipt is unreadable or non-canonical")
        expected_keys = {
            "schema_version",
            "evidence_root_id",
            "root_name_receipt_digest",
            "execution_contract_digest",
            "transaction_id",
            "observed_intent_digest",
            "resulting_intent_digest",
            "observed_intent_bytes_sha256",
            "recovery_attempt",
            "observed_prior_state",
            "output_rehash_digest",
            "copy_a_head_event_digest",
            "copy_b_head_event_digest",
            "recovery_action",
            "recovery_outcome",
            "principal_authority_digest",
            "created_at_utc",
            "recovery_receipt_digest",
        }
        _require_exact_keys(receipt, expected_keys, "registry recovery receipt")
        if receipt["schema_version"] != REGISTRY_RECOVERY_SCHEMA:
            _fail_registry("recovery receipt schema is invalid")
        if (
            receipt["evidence_root_id"] != EVIDENCE_ROOT_ID
            or receipt["root_name_receipt_digest"] != root_receipt["receipt_digest"]
            or receipt["execution_contract_digest"] != root_receipt["contract_digest"]
            or receipt["transaction_id"] != match.group(1)
            or receipt["recovery_attempt"] != int(match.group(2))
        ):
            _fail_registry("recovery receipt root, transaction, or attempt binding is invalid")
        for nullable_digest in (
            "observed_intent_digest",
            "resulting_intent_digest",
            "observed_intent_bytes_sha256",
        ):
            value = receipt[nullable_digest]
            if value is not None:
                _require_digest(value, nullable_digest)
        for digest_field in (
            "output_rehash_digest",
            "copy_a_head_event_digest",
            "copy_b_head_event_digest",
            "principal_authority_digest",
            "recovery_receipt_digest",
        ):
            _require_digest(receipt[digest_field], digest_field)
        _require_timestamp(receipt["created_at_utc"])
        claimed = receipt["recovery_receipt_digest"]
        payload = {key: value for key, value in receipt.items() if key != "recovery_receipt_digest"}
        if mirror_demo_digest(REGISTRY_RECOVERY_SCHEMA, payload) != claimed:
            _fail_registry("recovery receipt digest does not replay")


def _snapshot_from_ordered(
    root_receipt: Mapping[str, JsonValue],
    ordered_events: Sequence[JsonObject],
) -> RegistrySnapshot:
    genesis = mirror_demo_digest(
        REGISTRY_COMMON_GENESIS_SCHEMA,
        common_genesis_payload(root_receipt),
    )
    head = (
        _require_string(ordered_events[-1]["event_digest"], "snapshot event digest")
        if ordered_events
        else genesis
    )
    ordered: list[JsonValue] = [cast(JsonValue, event) for event in ordered_events]
    payload: JsonObject = {
        "schema_version": REGISTRY_SNAPSHOT_SCHEMA,
        "evidence_root_id": EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": root_receipt["receipt_digest"],
        "execution_contract_digest": root_receipt["contract_digest"],
        "registry_schema_contract_digest": REGISTRY_SCHEMA_CONTRACT_DIGEST,
        "common_genesis_digest": genesis,
        "event_count": len(ordered_events),
        "head_event_digest": head,
        "ordered_events": ordered,
    }
    return RegistrySnapshot(
        event_count=len(ordered_events),
        head_event_digest=head,
        semantic_snapshot_digest=mirror_demo_digest(REGISTRY_SNAPSHOT_SCHEMA, payload),
        ordered_events=tuple(ordered_events),
    )


def _control_transaction_ids(root: Path, destination_class: str) -> set[str]:
    directory_relative = CONTROL_DESTINATIONS[destination_class]
    directory = root / Path(directory_relative)
    if not directory.exists():
        return set()
    _require_contained(root, directory / "placeholder", allow_missing=True)
    if destination_class == "CONTROL_REGISTRY_INTENTS":
        pattern = re.compile(r"D02_R2_REGISTRY_TRANSACTION_INTENT__([0-9a-f]{64})[.]json\Z")
    else:
        pattern = re.compile(r"D02_R2_REGISTRY_COMMIT_RECEIPT__([0-9a-f]{64})[.]json\Z")
    result: set[str] = set()
    for entry in directory.iterdir():
        _require_not_reparse(entry)
        match = pattern.fullmatch(entry.name)
        if match is None or not entry.is_file():
            _fail_registry("unknown or malformed registry control object")
        result.add(match.group(1))
    return result


def _resolve_output_receipts(
    root: Path,
    root_receipt: Mapping[str, JsonValue],
    *,
    output_id: str,
) -> tuple[JsonObject, JsonObject]:
    _require_output_id(output_id)
    escaped = re.escape(output_id)
    name_pattern = re.compile(rf"D02_R2_OUTPUT_NAME_RECEIPT__[0-9]{{8}}__{escaped}[.]json\Z")
    seal_pattern = re.compile(rf"D02_R2_OUTPUT_SEAL_RECEIPT__[0-9]{{8}}__{escaped}[.]json\Z")
    name_paths = _matching_control_paths(root, "CONTROL_NAME_RECEIPTS", name_pattern)
    seal_paths = _matching_control_paths(root, "CONTROL_SEAL_RECEIPTS", seal_pattern)
    if len(name_paths) != 1 or len(seal_paths) != 1:
        _fail_registry("registered output does not have one exact name and seal receipt")
    name_receipt = _load_name_receipt(name_paths[0], root_receipt)
    seal_receipt = _load_seal_receipt(seal_paths[0], root_receipt, name_receipt)
    return name_receipt, seal_receipt


def _matching_control_paths(
    root: Path,
    destination_class: str,
    pattern: re.Pattern[str],
) -> list[Path]:
    directory = root / Path(CONTROL_DESTINATIONS[destination_class])
    _require_not_reparse(directory)
    result: list[Path] = []
    for entry in directory.iterdir():
        _require_not_reparse(entry)
        if pattern.fullmatch(entry.name):
            if not entry.is_file():
                _fail_registry("receipt path is not a regular file")
            result.append(entry)
    return result


def _append_registry_copy(
    path: Path, intent: Mapping[str, JsonValue], event: Mapping[str, JsonValue]
) -> None:
    connection = _open_registry(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO registry_transactions (
              transaction_id, output_id, semantic_role, authority_digest, intent_digest,
              expected_sequence, canonical_event_digest, transaction_state,
              intent_created_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'COPY_PREPARED', ?)
            """,
            (
                intent["transaction_id"],
                intent["output_id"],
                intent["semantic_role"],
                intent["authority_digest"],
                intent["intent_digest"],
                intent["expected_sequence"],
                intent["canonical_event_digest"],
                intent["intent_created_at_utc"],
            ),
        )
        canonical_event = canonical_json_bytes(cast(Mapping[str, object], event))
        connection.execute(
            """
            INSERT INTO registry_events (
              sequence, transaction_id, output_id, semantic_role, authority_digest,
              name_receipt_digest, seal_receipt_digest, previous_event_digest,
              event_digest, canonical_event_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["SEQUENCE"],
                event["TRANSACTION_ID"],
                event["OUTPUT_ID"],
                event["SEMANTIC_ROLE"],
                event["AUTHORITY"],
                event["NAME_RECEIPT_DIGEST"],
                event["SEAL_RECEIPT_DIGEST"],
                event["PREVIOUS_EVENT_DIGEST"],
                event["EVENT_DIGEST"],
                canonical_event,
            ),
        )
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        raise
    finally:
        connection.close()
    _sync_file_and_parent(path)
    _require_no_sqlite_sidecars(path)


def _create_registry_copy(
    path: Path,
    copy_id: str,
    root_receipt: Mapping[str, JsonValue],
) -> None:
    _ensure_parent_directory(path.parent)
    flags = os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as error:
        raise D02R2RegistryError(
            "REGISTRY_INITIALIZATION_CORRUPTION_STOP",
            "registry file appeared during exclusive creation",
        ) from error
    os.close(descriptor)
    try:
        connection = sqlite3.connect(path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute(f"PRAGMA application_id={SQLITE_APPLICATION_ID}")
            connection.execute(f"PRAGMA user_version={SQLITE_USER_VERSION}")
            connection.execute("PRAGMA journal_mode=DELETE")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA temp_store=MEMORY")
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("BEGIN IMMEDIATE")
            for _, _, statement in _DDL_STATEMENTS:
                connection.execute(statement)
            metadata = _metadata_payload(root_receipt, copy_id)
            connection.execute(
                """
                INSERT INTO registry_metadata (
                  singleton, schema_version, evidence_root_id, root_name_receipt_digest,
                  execution_contract_digest, registry_schema_contract_digest,
                  registry_normalized_ddl_sha256, registry_implementation_sha,
                  registry_copy_id, common_genesis_digest, created_at_utc, metadata_digest
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata["schema_version"],
                    metadata["evidence_root_id"],
                    metadata["root_name_receipt_digest"],
                    metadata["execution_contract_digest"],
                    metadata["registry_schema_contract_digest"],
                    metadata["registry_normalized_ddl_sha256"],
                    metadata["registry_implementation_sha"],
                    metadata["registry_copy_id"],
                    metadata["common_genesis_digest"],
                    metadata["created_at_utc"],
                    metadata["metadata_digest"],
                ),
            )
            connection.commit()
        except sqlite3.Error:
            connection.rollback()
            raise
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise D02R2RegistryError(
            "REGISTRY_INITIALIZATION_CORRUPTION_STOP",
            "registry initialization failed and the partial file was preserved",
        ) from error
    _sync_file_and_parent(path)
    _require_no_sqlite_sidecars(path)


def _metadata_payload(root_receipt: Mapping[str, JsonValue], copy_id: str) -> JsonObject:
    common_genesis = mirror_demo_digest(
        REGISTRY_COMMON_GENESIS_SCHEMA,
        common_genesis_payload(root_receipt),
    )
    payload: JsonObject = {
        "schema_version": REGISTRY_METADATA_SCHEMA,
        "evidence_root_id": EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": root_receipt["receipt_digest"],
        "execution_contract_digest": root_receipt["contract_digest"],
        "registry_schema_contract_digest": REGISTRY_SCHEMA_CONTRACT_DIGEST,
        "registry_normalized_ddl_sha256": REGISTRY_NORMALIZED_DDL_SHA256,
        "registry_implementation_sha": root_receipt["registry_implementation_sha"],
        "registry_copy_id": copy_id,
        "common_genesis_digest": common_genesis,
        "created_at_utc": root_receipt["created_at_utc"],
    }
    payload["metadata_digest"] = mirror_demo_digest(REGISTRY_METADATA_SCHEMA, payload)
    return payload


def _validate_event_transaction(
    event_row: Mapping[str, object],
    transaction_row: Mapping[str, object],
    *,
    expected_sequence: int,
    expected_previous: str,
    root_receipt: Mapping[str, JsonValue],
) -> None:
    raw = event_row["canonical_event_json"]
    if not isinstance(raw, bytes):
        _fail_registry("canonical event is not bytes")
    event = _parse_canonical_json_bytes(raw)
    _require_exact_keys(event, set(EVENT_KEYS), "registry event")
    if event["SCHEMA_VERSION"] != REGISTRY_EVENT_SCHEMA:
        _fail_registry("event schema is invalid")
    claimed = event["EVENT_DIGEST"]
    _require_digest(claimed, "event digest")
    payload = {key: value for key, value in event.items() if key != "EVENT_DIGEST"}
    if mirror_demo_digest(REGISTRY_EVENT_SCHEMA, payload) != claimed:
        _fail_registry("event digest does not replay")
    projections = {
        "sequence": event["SEQUENCE"],
        "transaction_id": event["TRANSACTION_ID"],
        "output_id": event["OUTPUT_ID"],
        "semantic_role": event["SEMANTIC_ROLE"],
        "authority_digest": event["AUTHORITY"],
        "name_receipt_digest": event["NAME_RECEIPT_DIGEST"],
        "seal_receipt_digest": event["SEAL_RECEIPT_DIGEST"],
        "previous_event_digest": event["PREVIOUS_EVENT_DIGEST"],
        "event_digest": event["EVENT_DIGEST"],
        "canonical_event_json": raw,
    }
    if dict(event_row) != projections:
        _fail_registry("event row projection differs from canonical event")
    if (
        event["SEQUENCE"] != expected_sequence
        or event["PREVIOUS_EVENT_DIGEST"] != expected_previous
    ):
        _fail_registry("event chain sequence or previous head is invalid")
    if event["EVIDENCE_ROOT_ID"] != EVIDENCE_ROOT_ID:
        _fail_registry("event root ID is invalid")
    if event["ROOT_NAME_RECEIPT_DIGEST"] != root_receipt["receipt_digest"]:
        _fail_registry("event root receipt binding is invalid")
    if event["EXECUTION_CONTRACT_DIGEST"] != root_receipt["contract_digest"]:
        _fail_registry("event execution contract binding is invalid")
    expected_transaction = {
        "transaction_id": event["TRANSACTION_ID"],
        "output_id": event["OUTPUT_ID"],
        "semantic_role": event["SEMANTIC_ROLE"],
        "authority_digest": event["AUTHORITY"],
        "intent_digest": transaction_row["intent_digest"],
        "expected_sequence": event["SEQUENCE"],
        "canonical_event_digest": event["EVENT_DIGEST"],
        "transaction_state": "COPY_PREPARED",
        "intent_created_at_utc": transaction_row["intent_created_at_utc"],
    }
    if dict(transaction_row) != expected_transaction:
        _fail_registry("transaction row projection differs from canonical event")


def _validate_pragmas(connection: sqlite3.Connection) -> None:
    observed = {
        "application_id": connection.execute("PRAGMA application_id").fetchone()[0],
        "user_version": connection.execute("PRAGMA user_version").fetchone()[0],
        "journal_mode": str(connection.execute("PRAGMA journal_mode").fetchone()[0]).upper(),
        "synchronous": connection.execute("PRAGMA synchronous").fetchone()[0],
        "foreign_keys": connection.execute("PRAGMA foreign_keys").fetchone()[0],
        "temp_store": connection.execute("PRAGMA temp_store").fetchone()[0],
        "trusted_schema": connection.execute("PRAGMA trusted_schema").fetchone()[0],
    }
    expected = {
        "application_id": SQLITE_APPLICATION_ID,
        "user_version": SQLITE_USER_VERSION,
        "journal_mode": "DELETE",
        "synchronous": 2,
        "foreign_keys": 1,
        "temp_store": 2,
        "trusted_schema": 0,
    }
    if observed != expected:
        _fail_registry("required SQLite pragmas differ")


def _validate_sqlite_objects(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        """
        SELECT type, name, sql
        FROM sqlite_master
        WHERE name NOT LIKE 'sqlite_%'
        ORDER BY rowid ASC
        """
    ).fetchall()
    observed = [(row[0], row[1], row[2]) for row in rows]
    expected = list(_DDL_STATEMENTS)
    if observed != expected:
        _fail_registry("SQLite application object or exact DDL drift was detected")


def _open_registry(path: Path) -> sqlite3.Connection:
    _require_not_reparse(path)
    expected_identity = _path_identity(path)
    uri = f"{path.resolve(strict=True).as_uri()}?mode=rw"
    connection = sqlite3.connect(uri, uri=True, isolation_level=None)
    if _path_identity(path) != expected_identity:
        connection.close()
        _fail_registry("registry file identity changed while opening")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=DELETE")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA temp_store=MEMORY")
    connection.execute("PRAGMA trusted_schema=OFF")
    return connection


def _registry_paths(root: Path) -> tuple[Path, Path]:
    return (
        _control_path(root, "CONTROL_REGISTRY_A", REGISTRY_A_LOGICAL_NAME),
        _control_path(root, "CONTROL_REGISTRY_B", REGISTRY_B_LOGICAL_NAME),
    )


def _create_control_directories(root: Path) -> None:
    ordered = sorted(
        {destination for destination in CONTROL_DESTINATIONS.values() if destination != "."},
        key=lambda value: (value.count("/"), value),
    )
    for relative in ordered:
        current = root
        for component in relative.split("/"):
            current = current / component
            _ensure_parent_directory(current)


def _ensure_parent_directory(path: Path) -> None:
    if path.exists():
        _require_not_reparse(path)
        if not path.is_dir():
            _fail_root("a required control directory path is not a directory")
        return
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        pass
    _require_not_reparse(path)
    _sync_directory(path.parent)


def _control_path(root: Path, destination_class: str, logical_name: str) -> Path:
    _require_logical_name(logical_name)
    relative = CONTROL_DESTINATIONS.get(destination_class)
    if relative is None:
        _fail_root("unknown control destination class")
    target = root / logical_name if relative == "." else root / Path(relative) / logical_name
    _require_contained(root, target, allow_missing=True)
    return target


def _role_destination(semantic_role: str) -> tuple[str, str]:
    destination = ROLE_DESTINATIONS.get(semantic_role)
    if destination is None:
        _fail_output("semantic role is not allowed by CC08")
    return destination


def _relative_output_path(name_receipt: Mapping[str, JsonValue]) -> str:
    semantic_role = _require_string(name_receipt["semantic_role"], "semantic role")
    destination_class = _require_string(
        name_receipt["relative_destination_class"], "relative destination class"
    )
    expected_class, relative = _role_destination(semantic_role)
    if destination_class != expected_class:
        _fail_output("name receipt destination class differs from the role mapping")
    logical_name = _require_string(name_receipt["logical_name"], "logical name")
    _require_logical_name(logical_name)
    return f"{relative}/{logical_name}"


def _output_path(root: Path, name_receipt: Mapping[str, JsonValue]) -> Path:
    relative = _relative_output_path(name_receipt)
    directory, logical_name = relative.rsplit("/", 1)
    target_directory = root / Path(directory)
    _ensure_directory_chain(root, target_directory)
    target = target_directory / logical_name
    _require_contained(root, target, allow_missing=True)
    return target


def output_path_for_principal(
    root: Path,
    authority: RootReceiptAuthority,
    name_receipt_logical_name: str,
) -> Path:
    """Resolve a preallocated destination for Principal-only process handoff."""

    root_receipt = load_root_name_receipt(root, authority)
    receipt = _load_name_receipt(
        _control_path(root, "CONTROL_NAME_RECEIPTS", name_receipt_logical_name),
        root_receipt,
    )
    return _output_path(root, receipt)


def _ensure_directory_chain(root: Path, target: Path) -> None:
    relative = target.relative_to(root)
    current = root
    for component in relative.parts:
        current = current / component
        _ensure_parent_directory(current)


def _load_name_receipt(path: Path, root_receipt: Mapping[str, JsonValue]) -> JsonObject:
    receipt = _read_canonical_json(path, maximum_bytes=262_144)
    expected_keys = {
        "schema_version",
        "evidence_root_id",
        "root_name_receipt_digest",
        "execution_contract_digest",
        "output_id",
        "allocation_sequence",
        "semantic_role",
        "logical_name",
        "producer_task_id",
        "dispatch_epoch",
        "allowed_tasks",
        "expected_parent_authority",
        "expected_media_type",
        "maximum_bytes",
        "relative_destination_class",
        "allocated_at_utc",
        "name_receipt_digest",
    }
    _require_exact_keys(receipt, expected_keys, "output name receipt")
    if receipt["schema_version"] != OUTPUT_NAME_RECEIPT_SCHEMA:
        _fail_output("name receipt schema is invalid")
    if receipt["evidence_root_id"] != EVIDENCE_ROOT_ID:
        _fail_output("name receipt root is invalid")
    if receipt["root_name_receipt_digest"] != root_receipt["receipt_digest"]:
        _fail_output("name receipt root digest is invalid")
    if receipt["execution_contract_digest"] != root_receipt["contract_digest"]:
        _fail_output("name receipt execution contract is invalid")
    _require_output_id(receipt["output_id"])
    allocation_sequence = receipt["allocation_sequence"]
    if (
        not isinstance(allocation_sequence, int)
        or isinstance(allocation_sequence, bool)
        or allocation_sequence < 1
        or allocation_sequence > 99_999_999
    ):
        _fail_output("name receipt allocation sequence is invalid")
    if receipt["dispatch_epoch"] != DISPATCH_EPOCH:
        _fail_output("name receipt dispatch epoch is invalid")
    semantic_role = _require_string(receipt["semantic_role"], "semantic role")
    expected_allowed_tasks: list[JsonValue] = (
        [TASK_ID, SOURCE_PRODUCER_TASK_ID, REVIEW_TASK_ID]
        if semantic_role in {"SOURCE_CANDIDATE", "SOURCE_PROVENANCE"}
        else [TASK_ID, REVIEW_TASK_ID]
    )
    if receipt["allowed_tasks"] != expected_allowed_tasks:
        _fail_output("name receipt allowed tasks are invalid")
    if (
        receipt["producer_task_id"] not in expected_allowed_tasks
        or receipt["producer_task_id"] == REVIEW_TASK_ID
    ):
        _fail_output("name receipt producer task is invalid")
    _require_digest(receipt["expected_parent_authority"], "expected parent authority")
    _require_media_type(receipt["expected_media_type"])
    maximum_bytes = receipt["maximum_bytes"]
    if (
        not isinstance(maximum_bytes, int)
        or isinstance(maximum_bytes, bool)
        or maximum_bytes < 1
        or maximum_bytes > MAXIMUM_ROOT_BYTES
    ):
        _fail_output("name receipt maximum bytes are invalid")
    _require_timestamp(receipt["allocated_at_utc"])
    claimed = receipt["name_receipt_digest"]
    _require_digest(claimed, "name receipt digest")
    payload = {key: value for key, value in receipt.items() if key != "name_receipt_digest"}
    if mirror_demo_digest(OUTPUT_NAME_RECEIPT_SCHEMA, payload) != claimed:
        _fail_output("name receipt digest does not replay")
    _relative_output_path(receipt)
    return receipt


def _load_seal_receipt(
    path: Path,
    root_receipt: Mapping[str, JsonValue],
    name_receipt: Mapping[str, JsonValue],
) -> JsonObject:
    receipt = _read_canonical_json(path, maximum_bytes=262_144)
    expected_keys = {
        "schema_version",
        "evidence_root_id",
        "root_name_receipt_digest",
        "execution_contract_digest",
        "output_id",
        "name_receipt_digest",
        "semantic_role",
        "producer_task_id",
        "actual_sha256",
        "byte_size",
        "media_type",
        "authority_digest",
        "retention",
        "custody",
        "sealed_at_utc",
        "seal_digest",
    }
    _require_exact_keys(receipt, expected_keys, "output seal receipt")
    if receipt["schema_version"] != OUTPUT_SEAL_RECEIPT_SCHEMA:
        _fail_output("seal receipt schema is invalid")
    equalities = {
        "evidence_root_id": EVIDENCE_ROOT_ID,
        "root_name_receipt_digest": root_receipt["receipt_digest"],
        "execution_contract_digest": root_receipt["contract_digest"],
        "output_id": name_receipt["output_id"],
        "name_receipt_digest": name_receipt["name_receipt_digest"],
        "semantic_role": name_receipt["semantic_role"],
        "producer_task_id": name_receipt["producer_task_id"],
    }
    if any(receipt[key] != value for key, value in equalities.items()):
        _fail_output("seal receipt binding differs from the name receipt")
    if receipt["media_type"] != name_receipt["expected_media_type"]:
        _fail_output("seal receipt media type differs from the name receipt")
    byte_size = receipt["byte_size"]
    if (
        not isinstance(byte_size, int)
        or isinstance(byte_size, bool)
        or byte_size < 0
        or byte_size > cast(int, name_receipt["maximum_bytes"])
    ):
        _fail_output("seal receipt byte size is outside the name receipt envelope")
    _require_digest(receipt["actual_sha256"], "sealed output SHA-256")
    _require_digest(receipt["authority_digest"], "sealed authority digest")
    _require_timestamp(receipt["sealed_at_utc"])
    claimed = receipt["seal_digest"]
    _require_digest(claimed, "seal receipt digest")
    payload = {key: value for key, value in receipt.items() if key != "seal_digest"}
    if mirror_demo_digest(OUTPUT_SEAL_RECEIPT_SCHEMA, payload) != claimed:
        _fail_output("seal receipt digest does not replay")
    return receipt


def _load_commit_receipt(
    path: Path,
    *,
    root_receipt: Mapping[str, JsonValue],
    expected_transaction_id: str,
    expected_intent: Mapping[str, JsonValue] | None = None,
    expected_snapshot_a: RegistrySnapshot | None = None,
    expected_snapshot_b: RegistrySnapshot | None = None,
) -> JsonObject:
    receipt = _read_canonical_json(path, maximum_bytes=262_144)
    expected_keys = {
        "schema_version",
        "evidence_root_id",
        "root_name_receipt_digest",
        "execution_contract_digest",
        "transaction_id",
        "intent_digest",
        "output_id",
        "canonical_event_digest",
        "copy_a_event_count",
        "copy_a_head_event_digest",
        "copy_a_semantic_snapshot_digest",
        "copy_b_event_count",
        "copy_b_head_event_digest",
        "copy_b_semantic_snapshot_digest",
        "commit_state",
        "created_at_utc",
        "commit_receipt_digest",
    }
    _require_exact_keys(receipt, expected_keys, "registry commit receipt")
    if receipt["schema_version"] != REGISTRY_COMMIT_SCHEMA:
        _fail_registry("commit receipt schema is invalid")
    if receipt["transaction_id"] != expected_transaction_id:
        _fail_registry("commit receipt transaction ID is invalid")
    if receipt["commit_state"] != "COMMITTED_BOTH_COPIES":
        _fail_registry("commit receipt state is invalid")
    if receipt["root_name_receipt_digest"] != root_receipt["receipt_digest"]:
        _fail_registry("commit receipt root binding is invalid")
    if receipt["evidence_root_id"] != EVIDENCE_ROOT_ID:
        _fail_registry("commit receipt root ID is invalid")
    if receipt["execution_contract_digest"] != root_receipt["contract_digest"]:
        _fail_registry("commit receipt execution contract is invalid")
    claimed = receipt["commit_receipt_digest"]
    _require_digest(claimed, "commit receipt digest")
    payload = {key: value for key, value in receipt.items() if key != "commit_receipt_digest"}
    if mirror_demo_digest(REGISTRY_COMMIT_SCHEMA, payload) != claimed:
        _fail_registry("commit receipt digest does not replay")
    if any(
        value is not None for value in (expected_intent, expected_snapshot_a, expected_snapshot_b)
    ):
        if expected_intent is None or expected_snapshot_a is None or expected_snapshot_b is None:
            _fail_registry("commit replay expectations are incomplete")
        expected = _build_commit_receipt(
            root_receipt,
            expected_intent,
            expected_snapshot_a,
            expected_snapshot_b,
        )
        if receipt != expected:
            _fail_registry("commit receipt differs from the immutable intent and snapshots")
    return receipt


def _transaction_id(
    root_receipt: Mapping[str, JsonValue],
    name_receipt: Mapping[str, JsonValue],
    seal_receipt: Mapping[str, JsonValue],
) -> str:
    return mirror_demo_digest(
        REGISTRY_TRANSACTION_ID_SCHEMA,
        {
            "evidence_root_id": EVIDENCE_ROOT_ID,
            "root_name_receipt_digest": root_receipt["receipt_digest"],
            "execution_contract_digest": root_receipt["contract_digest"],
            "output_id": name_receipt["output_id"],
            "name_receipt_digest": name_receipt["name_receipt_digest"],
            "seal_receipt_digest": seal_receipt["seal_digest"],
        },
    )


def _intent_path(root: Path, transaction_id: str) -> Path:
    return _control_path(
        root,
        "CONTROL_REGISTRY_INTENTS",
        f"D02_R2_REGISTRY_TRANSACTION_INTENT__{transaction_id}.json",
    )


def _commit_path(root: Path, transaction_id: str) -> Path:
    return _control_path(
        root,
        "CONTROL_REGISTRY_COMMITS",
        f"D02_R2_REGISTRY_COMMIT_RECEIPT__{transaction_id}.json",
    )


def _rehash_sealed_output(
    root: Path,
    name_receipt: Mapping[str, JsonValue],
    seal_receipt: Mapping[str, JsonValue],
) -> None:
    actual, size = _hash_file(
        _output_path(root, name_receipt),
        maximum_bytes=cast(int, name_receipt["maximum_bytes"]),
    )
    if actual != seal_receipt["actual_sha256"] or size != seal_receipt["byte_size"]:
        _fail_output("sealed output no longer matches its immutable receipt")


def _hash_file(path: Path, *, maximum_bytes: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened_identity = _descriptor_identity(descriptor)
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            while chunk := handle.read(1024 * 1024):
                total += len(chunk)
                if total > maximum_bytes:
                    _fail_output("output exceeds its preallocated maximum bytes")
                digest.update(chunk)
        _require_opened_path_identity(path, opened_identity)
    finally:
        os.close(descriptor)
    return digest.hexdigest(), total


def _write_exclusive_json(
    root: Path,
    path: Path,
    payload: Mapping[str, object],
    *,
    maximum_bytes: int,
) -> None:
    data = canonical_json_bytes(payload)
    if len(data) > maximum_bytes:
        _fail_output("control JSON exceeds its fixed maximum bytes")
    _write_exclusive_bytes(root, path, data)


def _write_exclusive_bytes(root: Path, path: Path, data: bytes) -> None:
    _require_contained(root, path, allow_missing=True)
    _ensure_directory_chain(root, path.parent)
    _require_contained(root, path, allow_missing=True)
    root_identity = _path_identity(root)
    parent_identity = _path_identity(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as error:
        raise D02R2RegistryError(
            "OUTPUT_NAME_OR_ID_COLLISION_STOP",
            "an immutable control object already exists",
        ) from error
    try:
        opened_identity = _descriptor_identity(descriptor)
        view = memoryview(data)
        offset = 0
        while offset < len(view):
            offset += os.write(descriptor, view[offset:])
        os.fsync(descriptor)
        _require_opened_path_identity(path, opened_identity)
    finally:
        os.close(descriptor)
    _sync_directory(path.parent)
    if _path_identity(root) != root_identity or _path_identity(path.parent) != parent_identity:
        _fail_root("evidence ancestry identity changed during exclusive write")
    if _read_file_bytes_no_follow(path, maximum_bytes=len(data)) != data:
        _fail_output("exclusive control write failed byte replay")


def _read_canonical_json(path: Path, *, maximum_bytes: int) -> JsonObject:
    _require_not_reparse(path)
    raw = _read_file_bytes_no_follow(path, maximum_bytes=maximum_bytes)
    return _parse_canonical_json_bytes(raw)


def _read_file_bytes_no_follow(path: Path, *, maximum_bytes: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened_identity = _descriptor_identity(descriptor)
        chunks: list[bytes] = []
        total = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            total += len(chunk)
            if total > maximum_bytes:
                _fail_output("control object exceeds its fixed maximum bytes")
            chunks.append(chunk)
        _require_opened_path_identity(path, opened_identity)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _descriptor_identity(descriptor: int) -> tuple[int, int]:
    info = os.fstat(descriptor)
    return info.st_dev, info.st_ino


def _require_opened_path_identity(path: Path, opened_identity: tuple[int, int]) -> None:
    _require_not_reparse(path)
    if _path_identity(path) != opened_identity:
        _fail_root("opened evidence object identity changed before validation")


def _parse_canonical_json_bytes(raw: bytes) -> JsonObject:
    def pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    try:
        parsed = json.loads(raw, object_pairs_hook=pairs_hook)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        _fail_output("control JSON is not strict UTF-8 JSON", cause=error)
    if not isinstance(parsed, dict):
        _fail_output("control JSON root is not an object")
    result = cast(dict[str, object], parsed)
    if canonical_json_bytes(result) != raw:
        _fail_output("control JSON bytes are not canonical")
    return cast(JsonObject, result)


def _validate_root_candidate(
    root: Path,
    *,
    excluded_roots: Sequence[Path],
    minimum_free_bytes: int,
) -> None:
    if not root.is_absolute() or root.name != EVIDENCE_ROOT_BASENAME:
        _fail_root("authorized root must be absolute with the fixed basename")
    if str(root).startswith("\\\\"):
        _fail_root("network or UNC evidence roots are forbidden")
    parent = root.parent
    if not parent.exists() or not parent.is_dir():
        _fail_root("the Principal-controlled parent directory must already exist")
    _require_not_reparse(parent)
    _validate_root_access_boundary(parent)
    resolved_candidate = parent.resolve(strict=True) / root.name
    for excluded in excluded_roots:
        resolved_excluded = excluded.resolve(strict=False)
        if _is_within(resolved_candidate, resolved_excluded) or _is_within(
            resolved_excluded, resolved_candidate
        ):
            _fail_root("evidence root collides with an excluded or Git worktree root")
    if minimum_free_bytes < MAXIMUM_ROOT_BYTES:
        _fail_root("minimum free-space Gate cannot be below the frozen root ceiling")
    if shutil.disk_usage(parent).free < minimum_free_bytes:
        _fail_root("insufficient free space for the frozen evidence root ceiling")
    if root.exists():
        _require_not_reparse(root)
        _validate_root_access_boundary(root)


def _validate_root_access_boundary(root: Path) -> None:
    """Fail closed on non-local, cloud-synced, or broadly writable evidence roots."""

    resolved = root.resolve(strict=True)
    if os.name == "nt":
        _validate_windows_fixed_drive(resolved)
        lowered = str(resolved).casefold()
        for variable in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
            configured = os.environ.get(variable)
            if configured and _is_within_casefolded(
                lowered, str(Path(configured).resolve()).casefold()
            ):
                _fail_root("cloud-synchronized evidence roots are forbidden")
        _validate_windows_restricted_acl(resolved)
    else:
        mode = stat.S_IMODE(os.stat(resolved, follow_symlinks=False).st_mode)
        if mode & 0o077:
            _fail_root("evidence root permissions are not Principal-restricted")
    if not os.access(resolved, os.R_OK | os.W_OK):
        _fail_root("Principal cannot read and write the evidence root")


def _is_within_casefolded(candidate: str, parent: str) -> bool:
    separator = os.sep.casefold()
    normalized_parent = parent.rstrip("\\/")
    return candidate == normalized_parent or candidate.startswith(normalized_parent + separator)


def _validate_windows_fixed_drive(path: Path) -> None:
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_drive_type = kernel32.GetDriveTypeW
    get_drive_type.argtypes = [wintypes.LPCWSTR]
    get_drive_type.restype = wintypes.UINT
    anchor = path.anchor
    if not anchor or get_drive_type(anchor) != 3:  # DRIVE_FIXED
        _fail_root("evidence root must reside on a fixed local drive")


def _validate_windows_restricted_acl(path: Path) -> None:
    script = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Import-Module (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1') -Force
$acl = Get-Acl -LiteralPath $env:MIRROR_D02_R2_ACL_PATH
$ownerSid = ([System.Security.Principal.NTAccount]$acl.Owner).Translate(
  [System.Security.Principal.SecurityIdentifier]
).Value
$currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$rules = @($acl.Access | ForEach-Object {
  [PSCustomObject]@{
    sid = $_.IdentityReference.Translate(
      [System.Security.Principal.SecurityIdentifier]
    ).Value
    type = $_.AccessControlType.ToString()
    inherited = $_.IsInherited
  }
})
[PSCustomObject]@{
  owner_sid = $ownerSid
  current_sid = $currentSid
  protected = $acl.AreAccessRulesProtected
  rules = $rules
} | ConvertTo-Json -Compress -Depth 4
"""
    environment = os.environ.copy()
    environment["MIRROR_D02_R2_ACL_PATH"] = str(path)
    system_root = Path(environment.get("SystemRoot", r"C:\Windows")).resolve(strict=True)
    powershell = (
        system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    ).resolve(strict=True)
    if not _is_within(powershell, system_root):
        _fail_root("trusted Windows PowerShell path escaped SystemRoot")
    try:
        completed = subprocess.run(  # noqa: S603 - fixed SystemRoot executable and static script.
            [
                str(powershell),
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            env=environment,
        )
        parsed = json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        _fail_root("Windows ACL verification failed closed", cause=error)
    if not isinstance(parsed, dict):
        _fail_root("Windows ACL verification returned an invalid payload")
    owner_sid = parsed.get("owner_sid")
    current_sid = parsed.get("current_sid")
    allowed_sids = {current_sid, owner_sid, "S-1-3-4", "S-1-5-18", "S-1-5-32-544"}
    if parsed.get("protected") is not True:
        _fail_root("evidence root ACL inheritance is not disabled")
    rules = parsed.get("rules")
    if not isinstance(rules, list) or not rules:
        _fail_root("evidence root ACL has no explicit access rules")
    for rule in rules:
        if not isinstance(rule, dict):
            _fail_root("evidence root ACL rule is invalid")
        if rule.get("type") == "Allow" and rule.get("sid") not in allowed_sids:
            _fail_root("evidence root ACL grants an unapproved principal")
        if rule.get("type") == "Allow" and rule.get("inherited") is not False:
            _fail_root("evidence root ACL contains inherited allow access")


def _require_contained(root: Path, target: Path, *, allow_missing: bool) -> None:
    resolved_root = root.resolve(strict=True)
    root_identity = _path_identity(resolved_root)
    parent = target.parent.resolve(strict=True)
    try:
        parent.relative_to(resolved_root)
    except ValueError as error:
        _fail_root("resolved target escapes the evidence root", cause=error)
    _require_not_reparse(resolved_root)
    current = resolved_root
    for component in parent.relative_to(resolved_root).parts:
        current = current / component
        _require_not_reparse(current)
    if target.exists() or not allow_missing:
        _require_not_reparse(target)
    if _path_identity(resolved_root) != root_identity:
        _fail_root("evidence root identity changed during path validation")


def _path_identity(path: Path) -> tuple[int, int]:
    info = os.stat(path, follow_symlinks=False)
    return info.st_dev, info.st_ino


def _require_not_reparse(path: Path) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError as error:
        _fail_root("required path does not exist", cause=error)
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if stat.S_ISLNK(info.st_mode) or (reparse_flag and attributes & reparse_flag):
        _fail_root("symlink, junction, or reparse point is forbidden")


def _is_within(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
    except ValueError:
        return False
    return True


def _sync_file_and_parent(path: Path) -> None:
    flags = os.O_RDWR | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _sync_directory(path.parent)


def _sync_directory(path: Path) -> None:
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return
    _sync_directory_windows(path)


def _sync_directory_windows(path: Path) -> None:
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    flush_file_buffers = kernel32.FlushFileBuffers
    flush_file_buffers.argtypes = [wintypes.HANDLE]
    flush_file_buffers.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    handle = create_file(
        str(path),
        0x80000000 | 0x40000000,
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,
        0x02000000 | 0x00200000,
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        raise OSError(ctypes.get_last_error(), "CreateFileW failed for directory durability")
    try:
        if not flush_file_buffers(handle):
            raise OSError(ctypes.get_last_error(), "FlushFileBuffers failed for directory")
    finally:
        if not close_handle(handle):
            raise OSError(ctypes.get_last_error(), "CloseHandle failed for directory")


def _require_no_sqlite_sidecars(path: Path) -> None:
    for suffix in ("-journal", "-wal", "-shm"):
        if Path(f"{path}{suffix}").exists():
            raise D02R2RegistryError(
                "REGISTRY_INITIALIZATION_CORRUPTION_STOP",
                "unexpected SQLite sidecar remains at a durability boundary",
            )


@contextlib.contextmanager
def _principal_mutex(root: Path) -> Iterator[None]:
    if os.name == "nt":
        with _windows_named_mutex():
            yield
        return
    fcntl = importlib.import_module("fcntl")

    descriptor = os.open(root, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


@contextlib.contextmanager
def _root_creation_mutex(parent: Path) -> Iterator[None]:
    if os.name == "nt":
        with _windows_named_mutex():
            yield
        return
    fcntl = importlib.import_module("fcntl")
    descriptor = os.open(parent, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


@contextlib.contextmanager
def _windows_named_mutex() -> Iterator[None]:
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_mutex = kernel32.CreateMutexW
    create_mutex.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    create_mutex.restype = wintypes.HANDLE
    wait_for_single_object = kernel32.WaitForSingleObject
    wait_for_single_object.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    wait_for_single_object.restype = wintypes.DWORD
    release_mutex = kernel32.ReleaseMutex
    release_mutex.argtypes = [wintypes.HANDLE]
    release_mutex.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    name = "Local\\ProjectMirrorD02R2_" + hashlib.sha256(EVIDENCE_ROOT_ID.encode()).hexdigest()
    handle = create_mutex(None, False, name)
    if not handle:
        raise OSError(ctypes.get_last_error(), "CreateMutexW failed")
    try:
        wait_result = wait_for_single_object(handle, 0xFFFFFFFF)
        if wait_result not in {0x00000000, 0x00000080}:
            raise OSError(ctypes.get_last_error(), "WaitForSingleObject failed")
        yield
    finally:
        if not release_mutex(handle):
            raise OSError(ctypes.get_last_error(), "ReleaseMutex failed")
        if not close_handle(handle):
            raise OSError(ctypes.get_last_error(), "CloseHandle failed")


def _validate_authority(authority: RootReceiptAuthority) -> None:
    if authority._trust_token is not _ROOT_AUTHORITY_TOKEN:
        _fail_root("root authority was not created by the tracked acceptance loader")
    if _SHA_RE.fullmatch(authority.accepted_plan_sha) is None:
        _fail_root("accepted plan SHA must be 40 lowercase hexadecimal characters")
    if _SHA_RE.fullmatch(authority.accepted_plan_tree) is None:
        _fail_root("accepted plan tree must be 40 lowercase hexadecimal characters")
    if _SHA_RE.fullmatch(authority.registry_implementation_sha) is None:
        _fail_root("registry implementation SHA must be 40 lowercase hexadecimal characters")
    if authority.accepted_plan_sha != ACCEPTED_PLAN_SHA:
        _fail_root("accepted plan SHA differs from the frozen CC08 authority")
    if authority.accepted_plan_tree != ACCEPTED_PLAN_TREE:
        _fail_root("accepted plan tree differs from the frozen CC08 authority")
    if _SHA_RE.fullmatch(authority._acceptance_checkpoint_sha) is None:
        _fail_root("acceptance checkpoint SHA is invalid")
    _require_digest(authority._acceptance_record_digest, "acceptance record")
    _require_timestamp(authority.created_at_utc)


def _require_equal_snapshots(first: RegistrySnapshot, second: RegistrySnapshot) -> None:
    if first != second:
        raise D02R2RegistryError(
            "REGISTRY_INCONSISTENT_STOP",
            "registry copies differ in count, head, snapshot, or ordered events",
        )


def _require_exact_keys(value: Mapping[str, object], expected: set[str], description: str) -> None:
    if set(value) != expected:
        raise D02R2RegistryError(
            "REGISTRY_SCHEMA_MISMATCH_STOP",
            f"{description} exact keys do not match",
        )


def _require_digest(value: object, description: str) -> None:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        _fail_output(f"{description} must be a lowercase SHA-256 digest")


def _require_output_id(value: object) -> None:
    if not isinstance(value, str) or _OUTPUT_ID_RE.fullmatch(value) is None:
        _fail_output("output ID does not match the frozen opaque grammar")


def _require_logical_name(value: object) -> None:
    if not isinstance(value, str) or _LOGICAL_NAME_RE.fullmatch(value) is None:
        _fail_output("logical name must be separator-free ASCII")
    if value in {".", ".."} or ":" in value:
        _fail_output("dot segments and alternate streams are forbidden")


def _require_timestamp(value: object) -> None:
    if not isinstance(value, str) or _UTC_RE.fullmatch(value) is None:
        _fail_output("timestamp must be canonical UTC with six fractional digits")


def _require_media_type(value: object) -> None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 127
        or re.fullmatch(r"[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*", value) is None
    ):
        _fail_output("media type is not canonical")


def _require_string(value: object, description: str) -> str:
    if not isinstance(value, str):
        _fail_output(f"{description} must be a string")
    return value


def _fail_root(message: str, *, cause: BaseException | None = None) -> NoReturn:
    error = D02R2RegistryError("EVIDENCE_ROOT_NAME_COLLISION_STOP", message)
    if cause is None:
        raise error
    raise error from cause


def _fail_registry(message: str) -> NoReturn:
    raise D02R2RegistryError("REGISTRY_INITIALIZATION_CORRUPTION_STOP", message)


def _fail_output(message: str, *, cause: BaseException | None = None) -> NoReturn:
    error = D02R2RegistryError("OUTPUT_NAME_OR_ID_COLLISION_STOP", message)
    if cause is None:
        raise error
    raise error from cause
