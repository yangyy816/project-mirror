"""Add the bounded D02-R2 Epoch 03 authority branches.

Revision ID: demo_0014_d02_r2_e3_versioning
Revises: demo_0013_d07_publish_auth
Create Date: 2026-08-30

PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "demo_0014_d02_r2_e3_versioning"
down_revision: str | None = "demo_0013_d07_publish_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROTOTYPE_MIGRATION = True
FORMAL_PHASE_AUTHORITY = False
DIRECT_MAINLINE_CHERRY_PICK = "FORBIDDEN"

_SOURCE_V1 = "mirror.demo/D02R2SourceAuthorityRecord/v1"
_SOURCE_E2 = "mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1"
_SOURCE_E3 = "mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1"
_SOURCE_E4 = "mirror.demo/D02R2Epoch4SourceAuthorityRecord/v1"
_ADMISSION_E2 = "mirror.demo/D02R2Epoch2Admission/v1"
_ADMISSION_E3 = "mirror.demo/D02R2Epoch3Admission/v1"
_ADMISSION_E4 = "mirror.demo/D02R2Epoch4Admission/v1"
_E1_ROOT = "P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT"
_E2_ROOT = "P3_P7_D02_R2_CC08_E2_EVIDENCE_ROOT"
_E3_ROOT = "P3_P7_D02_R2_E3_EVIDENCE_ROOT"
_E4_ROOT = "P3_P7_D02_R2_E4_EVIDENCE_ROOT"

_SOURCE_TRIGGER_V3_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_r2_source_authority()
RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE
    expected_id text;
    source_asset assets%ROWTYPE;
    expected_payload jsonb;
    id_preimage jsonb;
BEGIN
    IF TG_OP IS DISTINCT FROM 'INSERT' THEN
        RAISE EXCEPTION 'D02 R2 supporting row is append-only';
    END IF;
    IF NEW.schema_version NOT IN (
        'mirror.demo/D02R2SourceAuthorityRecord/v1',
        'mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1',
        'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1',
        'mirror.demo/D02R2Epoch4SourceAuthorityRecord/v1'
    ) THEN
        RAISE EXCEPTION 'D02 R2 supporting row schema is unsupported';
    END IF;
    expected_payload := mirror_demo_authority_projection(to_jsonb(NEW), TG_TABLE_NAME);
    IF NEW.schema_version = 'mirror.demo/D02R2SourceAuthorityRecord/v1' THEN
        expected_payload := expected_payload - ARRAY[
            'generation_request_digest','execution_epoch','producer_task_id','dispatch_epoch',
            'generation_source_asset_sha256','generation_source_asset_byte_size',
            'generation_source_asset_mime_type','generation_source_asset_width',
            'generation_source_asset_height','source_normalization_receipt_digest'
        ]::text[];
    END IF;
    IF NEW.schema_version NOT IN (
       'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1',
       'mirror.demo/D02R2Epoch4SourceAuthorityRecord/v1'
    ) THEN
        expected_payload := expected_payload - 'generation_policy_metadata';
    END IF;
    IF NEW.canonical_payload IS DISTINCT FROM expected_payload
       OR NEW.content_digest IS DISTINCT FROM mirror_demo_digest(NEW.schema_version, expected_payload) THEN
        RAISE EXCEPTION 'D02 R2 supporting row canonical authority is invalid';
    END IF;
    id_preimage := jsonb_build_object(
        'execution_contract_digest', NEW.execution_contract_digest,
        'evidence_root_id', NEW.evidence_root_id,
        'root_name_receipt_digest', NEW.root_name_receipt_digest,
        'generation_preregistration_digest', NEW.generation_preregistration_digest,
        'source_allocation_manifest_digest', NEW.source_allocation_manifest_digest,
        'source_producer_dispatch_digest', NEW.source_producer_dispatch_digest,
        'source_ordinal', NEW.source_ordinal,
        'source_output_id', NEW.source_output_id,
        'source_authority_key', NEW.source_authority_key,
        'source_authority_digest', NEW.source_authority_digest,
        'source_qa_snapshot_digest', NEW.source_qa_snapshot_digest,
        'content_digest', NEW.content_digest
    );
    IF NEW.schema_version IN (
        'mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1',
        'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1',
        'mirror.demo/D02R2Epoch4SourceAuthorityRecord/v1'
    ) THEN
        id_preimage := id_preimage || jsonb_build_object(
            'generation_request_digest', NEW.generation_request_digest,
            'execution_epoch', NEW.execution_epoch,
            'producer_task_id', NEW.producer_task_id,
            'dispatch_epoch', NEW.dispatch_epoch,
            'generation_source_asset_sha256', NEW.generation_source_asset_sha256,
            'generation_source_asset_byte_size', NEW.generation_source_asset_byte_size,
            'generation_source_asset_mime_type', NEW.generation_source_asset_mime_type,
            'generation_source_asset_width', NEW.generation_source_asset_width,
            'generation_source_asset_height', NEW.generation_source_asset_height,
            'source_normalization_receipt_digest', NEW.source_normalization_receipt_digest
        );
        IF NEW.schema_version = 'mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1' THEN
            expected_id := substring(mirror_demo_digest(
                'mirror.demo/D02R2Epoch2SourceAuthorityRecordId/v1', id_preimage
            ) FROM 1 FOR 32);
        ELSIF NEW.schema_version = 'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1' THEN
            expected_id := substring(mirror_demo_digest(
                'mirror.demo/D02R2Epoch3SourceAuthorityRecordId/v1', id_preimage
            ) FROM 1 FOR 32);
        ELSE
            expected_id := substring(mirror_demo_digest(
                'mirror.demo/D02R2Epoch4SourceAuthorityRecordId/v1', id_preimage
            ) FROM 1 FOR 32);
        END IF;
    ELSE
        expected_id := substring(mirror_demo_digest(
            'mirror.demo/D02R2SourceAuthorityRecordId/v1', id_preimage
        ) FROM 1 FOR 32);
    END IF;
    IF NEW.id IS DISTINCT FROM expected_id THEN
        RAISE EXCEPTION 'D02 R2 supporting row ID is invalid';
    END IF;
    IF NEW.source_authority_key IS DISTINCT FROM mirror_demo_r2_source_authority_key(
        NEW.source_output_id, NEW.source_asset_id, NEW.source_asset_sha256,
        NEW.source_generation_receipt_digest, NEW.source_authority_digest
    ) THEN
        RAISE EXCEPTION 'D02 R2 supporting row source key is invalid';
    END IF;
    IF NEW.schema_version IN (
        'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1',
        'mirror.demo/D02R2Epoch4SourceAuthorityRecord/v1'
    ) AND (
        NEW.generation_policy_metadata IS NULL
        OR NEW.generation_policy_metadata ->> 'schema_version' IS DISTINCT FROM
           CASE WHEN NEW.schema_version = 'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1'
                THEN 'mirror.demo/D02R2Epoch3GenerationPolicyMetadata/v1'
                ELSE 'mirror.demo/D02R2Epoch4GenerationPolicyMetadata/v1' END
        OR NEW.generation_policy_metadata ->> 'source_digest' IS DISTINCT FROM
           NEW.source_asset_sha256
        OR NEW.generation_policy_metadata ->> 'adult_status' IS DISTINCT FROM
           'VERIFIED_SYNTHETIC_ADULT'
        OR NEW.generation_policy_metadata ->> 'suspected_minor' IS DISTINCT FROM 'false'
        OR NEW.generation_policy_metadata ->> 'real_person_reference' IS DISTINCT FROM 'false'
        OR NEW.generation_policy_metadata ->> 'celebrity_resemblance' IS DISTINCT FROM 'false'
        OR NEW.generation_policy_metadata ->> 'metadata_digest' IS DISTINCT FROM
           mirror_demo_digest(
               CASE WHEN NEW.schema_version = 'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1'
                    THEN 'mirror.demo/D02R2Epoch3GenerationPolicyMetadata/v1'
                    ELSE 'mirror.demo/D02R2Epoch4GenerationPolicyMetadata/v1' END,
               NEW.generation_policy_metadata - 'metadata_digest'
           )
        OR NEW.generation_policy_metadata -> 'source_policy_profile' ->> 'profile_digest'
           IS DISTINCT FROM NEW.generation_policy_metadata ->> 'source_policy_profile_digest'
        OR NEW.generation_policy_metadata -> 'source_policy_profile' ->> 'profile_digest'
           IS DISTINCT FROM mirror_demo_digest(
               CASE WHEN NEW.schema_version = 'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1'
                    THEN 'mirror.demo/D02R2Epoch3SourcePolicyProfile/v1'
                    ELSE 'mirror.demo/D02R2Epoch4SourcePolicyProfile/v1' END,
               (NEW.generation_policy_metadata -> 'source_policy_profile')
               - 'profile_digest'::text
           )
        OR (NEW.generation_policy_metadata -> 'source_policy_profile' ->> 'source_ordinal')::integer
           IS DISTINCT FROM NEW.source_ordinal
    ) THEN
        RAISE EXCEPTION 'D02 R2 Epoch 03 generation policy metadata is invalid';
    END IF;
    SELECT * INTO source_asset FROM assets WHERE id = NEW.source_asset_id;
    IF NOT FOUND OR source_asset.sha256 IS DISTINCT FROM NEW.source_asset_sha256
       OR source_asset.byte_size IS DISTINCT FROM NEW.source_asset_byte_size
       OR source_asset.mime_type IS DISTINCT FROM NEW.source_asset_mime_type
       OR source_asset.width IS DISTINCT FROM NEW.source_asset_width
       OR source_asset.height IS DISTINCT FROM NEW.source_asset_height
       OR source_asset.asset_role IS DISTINCT FROM 'synthetic'
       OR source_asset.owner_user_id IS NOT NULL
       OR source_asset.internal_purpose IS DISTINCT FROM 'synthetic_dataset'
       OR source_asset.synthetic IS NOT TRUE
       OR source_asset.deleted_at IS NOT NULL THEN
        RAISE EXCEPTION 'D02 R2 supporting row Asset authority is invalid';
    END IF;
    RETURN NEW;
END;
$function$;
"""

_ADMISSION_TRIGGER_V3_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_r2_epoch2_admission()
RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE
    report_row demo_pair_screening_reports%ROWTYPE;
    bank_row demo_question_banks%ROWTYPE;
    source_count integer;
    identity_count integer;
    pair_count integer;
    side_count integer;
    expected_id text;
    expected_source_schema text;
    expected_root text;
    expected_epoch text;
    expected_dispatch smallint;
    expected_id_schema text;
BEGIN
    IF TG_OP IS DISTINCT FROM 'INSERT' THEN
        RAISE EXCEPTION 'D02 R2 admission is append-only';
    END IF;
    IF NEW.schema_version = 'mirror.demo/D02R2Epoch2Admission/v1' THEN
        expected_source_schema := 'mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1';
        expected_root := 'P3_P7_D02_R2_CC08_E2_EVIDENCE_ROOT';
        expected_epoch := 'D02_R2_EPOCH_02';
        expected_dispatch := 2;
        expected_id_schema := 'mirror.demo/D02R2Epoch2AdmissionId/v1';
    ELSIF NEW.schema_version = 'mirror.demo/D02R2Epoch3Admission/v1' THEN
        expected_source_schema := 'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1';
        expected_root := 'P3_P7_D02_R2_E3_EVIDENCE_ROOT';
        expected_epoch := 'D02_R2_EPOCH_03';
        expected_dispatch := 3;
        expected_id_schema := 'mirror.demo/D02R2Epoch3AdmissionId/v1';
    ELSIF NEW.schema_version = 'mirror.demo/D02R2Epoch4Admission/v1' THEN
        expected_source_schema := 'mirror.demo/D02R2Epoch4SourceAuthorityRecord/v1';
        expected_root := 'P3_P7_D02_R2_E4_EVIDENCE_ROOT';
        expected_epoch := 'D02_R2_EPOCH_04';
        expected_dispatch := 4;
        expected_id_schema := 'mirror.demo/D02R2Epoch4AdmissionId/v1';
    ELSE
        RAISE EXCEPTION 'D02 R2 admission schema is unsupported';
    END IF;
    SELECT * INTO report_row FROM demo_pair_screening_reports
      WHERE id = NEW.screening_report_id;
    SELECT * INTO bank_row FROM demo_question_banks
      WHERE id = NEW.question_bank_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'D02 R2 admission target graph is missing';
    END IF;
    IF report_row.schema_version IS DISTINCT FROM 'mirror.demo/D02PairScreeningReport/v3'
       OR report_row.status IS DISTINCT FROM 'PASSED'
       OR report_row.report_digest IS DISTINCT FROM NEW.screening_report_digest
       OR report_row.source_manifest_digest IS DISTINCT FROM NEW.source_manifest_digest
       OR report_row.selected_pair_manifest_digest IS DISTINCT FROM NEW.selected_pair_manifest_digest
       OR report_row.source_count IS DISTINCT FROM 4
       OR report_row.selected_pair_count IS DISTINCT FROM 16
       OR report_row.selected_result_side_count IS DISTINCT FROM 32
       OR bank_row.schema_version IS DISTINCT FROM 'mirror.demo/DemoQuestionBank/v3'
       OR bank_row.screening_report_id IS DISTINCT FROM report_row.id
       OR bank_row.screening_report_digest IS DISTINCT FROM report_row.report_digest
       OR bank_row.content_digest IS DISTINCT FROM NEW.question_bank_content_digest
       OR bank_row.version IS DISTINCT FROM NEW.question_bank_version
       OR bank_row.pair_manifest_digest IS DISTINCT FROM NEW.selected_pair_manifest_digest THEN
        RAISE EXCEPTION 'D02 R2 admission graph binding is invalid';
    END IF;
    SELECT count(*) INTO source_count
    FROM jsonb_array_elements(report_row.report_payload -> 'ordered_source_manifest') entry
    JOIN demo_d02_r2_source_authorities source_row
      ON source_row.id = entry ->> 'r2_source_authority_record_id'
    WHERE source_row.schema_version = expected_source_schema
      AND source_row.evidence_root_id = expected_root
      AND source_row.execution_epoch = expected_epoch
      AND source_row.dispatch_epoch = expected_dispatch
      AND source_row.generation_request_digest = source_row.generation_request_policy_digest;
    SELECT count(*) INTO identity_count
    FROM jsonb_array_elements(report_row.report_payload -> 'ordered_source_manifest') entry
    JOIN demo_synthetic_identities identity_row
      ON identity_row.id = entry ->> 'source_admission_event_id'
    WHERE identity_row.schema_version = 'mirror.demo/DemoSyntheticIdentity/v4'
      AND identity_row.admission_action = 'ADMIT'
      AND identity_row.r2_source_authority_record_id = entry ->> 'r2_source_authority_record_id';
    SELECT count(*), count(DISTINCT side.asset_id) INTO pair_count, side_count
    FROM demo_question_pairs pair_row
    CROSS JOIN LATERAL (
        VALUES (pair_row.left_asset_id), (pair_row.right_asset_id)
    ) AS side(asset_id)
    WHERE pair_row.question_bank_id = bank_row.id
      AND pair_row.schema_version = 'mirror.demo/DemoQuestionPair/v3'
      AND pair_row.screening_report_id = report_row.id
      AND pair_row.screening_report_digest = report_row.report_digest;
    pair_count := pair_count / 2;
    IF source_count IS DISTINCT FROM 4
       OR identity_count IS DISTINCT FROM 4
       OR pair_count IS DISTINCT FROM 16
       OR side_count IS DISTINCT FROM 32 THEN
        RAISE EXCEPTION 'D02 R2 admission cardinality is invalid';
    END IF;
    expected_id := substring(mirror_demo_digest(
        expected_id_schema,
        jsonb_build_object(
            'idempotency_key_hash', NEW.idempotency_key_hash,
            'request_digest', NEW.request_digest,
            'screening_report_id', NEW.screening_report_id,
            'question_bank_id', NEW.question_bank_id
        )
    ) FROM 1 FOR 32);
    IF NEW.id IS DISTINCT FROM expected_id THEN
        RAISE EXCEPTION 'D02 R2 admission ID is invalid';
    END IF;
    RETURN NULL;
END;
$function$;
"""


_SOURCE_TRIGGER_V2_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_r2_source_authority()
RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE
    expected_id text;
    source_asset assets%ROWTYPE;
    expected_payload jsonb;
    id_preimage jsonb;
BEGIN
    IF TG_OP IS DISTINCT FROM 'INSERT' THEN
        RAISE EXCEPTION 'D02 R2 supporting row is append-only';
    END IF;
    IF NEW.schema_version NOT IN (
        'mirror.demo/D02R2SourceAuthorityRecord/v1',
        'mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1'
    ) THEN
        RAISE EXCEPTION 'D02 R2 supporting row schema is unsupported';
    END IF;
    expected_payload := mirror_demo_authority_projection(to_jsonb(NEW), TG_TABLE_NAME);
    IF NEW.schema_version = 'mirror.demo/D02R2SourceAuthorityRecord/v1' THEN
        expected_payload := expected_payload - ARRAY[
            'generation_request_digest','execution_epoch','producer_task_id','dispatch_epoch',
            'generation_source_asset_sha256','generation_source_asset_byte_size',
            'generation_source_asset_mime_type','generation_source_asset_width',
            'generation_source_asset_height','source_normalization_receipt_digest'
        ]::text[];
    END IF;
    IF NEW.canonical_payload IS DISTINCT FROM expected_payload
       OR NEW.content_digest IS DISTINCT FROM mirror_demo_digest(NEW.schema_version, expected_payload) THEN
        RAISE EXCEPTION 'D02 R2 supporting row canonical authority is invalid';
    END IF;
    id_preimage := jsonb_build_object(
        'execution_contract_digest', NEW.execution_contract_digest,
        'evidence_root_id', NEW.evidence_root_id,
        'root_name_receipt_digest', NEW.root_name_receipt_digest,
        'generation_preregistration_digest', NEW.generation_preregistration_digest,
        'source_allocation_manifest_digest', NEW.source_allocation_manifest_digest,
        'source_producer_dispatch_digest', NEW.source_producer_dispatch_digest,
        'source_ordinal', NEW.source_ordinal,
        'source_output_id', NEW.source_output_id,
        'source_authority_key', NEW.source_authority_key,
        'source_authority_digest', NEW.source_authority_digest,
        'source_qa_snapshot_digest', NEW.source_qa_snapshot_digest,
        'content_digest', NEW.content_digest
    );
    IF NEW.schema_version = 'mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1' THEN
        id_preimage := id_preimage || jsonb_build_object(
            'generation_request_digest', NEW.generation_request_digest,
            'execution_epoch', NEW.execution_epoch,
            'producer_task_id', NEW.producer_task_id,
            'dispatch_epoch', NEW.dispatch_epoch,
            'generation_source_asset_sha256', NEW.generation_source_asset_sha256,
            'generation_source_asset_byte_size', NEW.generation_source_asset_byte_size,
            'generation_source_asset_mime_type', NEW.generation_source_asset_mime_type,
            'generation_source_asset_width', NEW.generation_source_asset_width,
            'generation_source_asset_height', NEW.generation_source_asset_height,
            'source_normalization_receipt_digest', NEW.source_normalization_receipt_digest
        );
        expected_id := substring(mirror_demo_digest(
            'mirror.demo/D02R2Epoch2SourceAuthorityRecordId/v1', id_preimage
        ) FROM 1 FOR 32);
    ELSE
        expected_id := substring(mirror_demo_digest(
            'mirror.demo/D02R2SourceAuthorityRecordId/v1', id_preimage
        ) FROM 1 FOR 32);
    END IF;
    IF NEW.id IS DISTINCT FROM expected_id THEN
        RAISE EXCEPTION 'D02 R2 supporting row ID is invalid';
    END IF;
    IF NEW.source_authority_key IS DISTINCT FROM mirror_demo_r2_source_authority_key(
        NEW.source_output_id, NEW.source_asset_id, NEW.source_asset_sha256,
        NEW.source_generation_receipt_digest, NEW.source_authority_digest
    ) THEN
        RAISE EXCEPTION 'D02 R2 supporting row source key is invalid';
    END IF;
    SELECT * INTO source_asset FROM assets WHERE id = NEW.source_asset_id;
    IF NOT FOUND OR source_asset.sha256 IS DISTINCT FROM NEW.source_asset_sha256
       OR source_asset.byte_size IS DISTINCT FROM NEW.source_asset_byte_size
       OR source_asset.mime_type IS DISTINCT FROM NEW.source_asset_mime_type
       OR source_asset.width IS DISTINCT FROM NEW.source_asset_width
       OR source_asset.height IS DISTINCT FROM NEW.source_asset_height
       OR source_asset.asset_role IS DISTINCT FROM 'synthetic'
       OR source_asset.owner_user_id IS NOT NULL
       OR source_asset.internal_purpose IS DISTINCT FROM 'synthetic_dataset'
       OR source_asset.synthetic IS NOT TRUE
       OR source_asset.deleted_at IS NOT NULL THEN
        RAISE EXCEPTION 'D02 R2 supporting row Asset authority is invalid';
    END IF;
    RETURN NEW;
END;
$function$;
"""

_ADMISSION_INTEGRITY_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_r2_epoch2_admission()
RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE
    report_row demo_pair_screening_reports%ROWTYPE;
    bank_row demo_question_banks%ROWTYPE;
    source_count integer;
    identity_count integer;
    pair_count integer;
    side_count integer;
    expected_id text;
BEGIN
    IF TG_OP IS DISTINCT FROM 'INSERT' THEN
        RAISE EXCEPTION 'D02 R2 Epoch 02 admission is append-only';
    END IF;
    SELECT * INTO report_row FROM demo_pair_screening_reports
      WHERE id = NEW.screening_report_id;
    SELECT * INTO bank_row FROM demo_question_banks
      WHERE id = NEW.question_bank_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'D02 R2 Epoch 02 admission target graph is missing';
    END IF;
    IF report_row.schema_version IS DISTINCT FROM 'mirror.demo/D02PairScreeningReport/v3'
       OR report_row.status IS DISTINCT FROM 'PASSED'
       OR report_row.report_digest IS DISTINCT FROM NEW.screening_report_digest
       OR report_row.source_manifest_digest IS DISTINCT FROM NEW.source_manifest_digest
       OR report_row.selected_pair_manifest_digest IS DISTINCT FROM
          NEW.selected_pair_manifest_digest
       OR report_row.source_count IS DISTINCT FROM 4
       OR report_row.selected_pair_count IS DISTINCT FROM 16
       OR report_row.selected_result_side_count IS DISTINCT FROM 32
       OR bank_row.schema_version IS DISTINCT FROM 'mirror.demo/DemoQuestionBank/v3'
       OR bank_row.screening_report_id IS DISTINCT FROM report_row.id
       OR bank_row.screening_report_digest IS DISTINCT FROM report_row.report_digest
       OR bank_row.content_digest IS DISTINCT FROM NEW.question_bank_content_digest
       OR bank_row.version IS DISTINCT FROM NEW.question_bank_version
       OR bank_row.pair_manifest_digest IS DISTINCT FROM NEW.selected_pair_manifest_digest THEN
        RAISE EXCEPTION 'D02 R2 Epoch 02 admission graph binding is invalid';
    END IF;
    SELECT count(*) INTO source_count
    FROM jsonb_array_elements(report_row.report_payload -> 'ordered_source_manifest') entry
    JOIN demo_d02_r2_source_authorities source_row
      ON source_row.id = entry ->> 'r2_source_authority_record_id'
    WHERE source_row.schema_version = 'mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1'
      AND source_row.evidence_root_id = 'P3_P7_D02_R2_CC08_E2_EVIDENCE_ROOT'
      AND source_row.execution_epoch = 'D02_R2_EPOCH_02'
      AND source_row.dispatch_epoch = 2
      AND source_row.generation_request_digest = source_row.generation_request_policy_digest;
    SELECT count(*) INTO identity_count
    FROM jsonb_array_elements(report_row.report_payload -> 'ordered_source_manifest') entry
    JOIN demo_synthetic_identities identity_row
      ON identity_row.id = entry ->> 'source_admission_event_id'
    WHERE identity_row.schema_version = 'mirror.demo/DemoSyntheticIdentity/v4'
      AND identity_row.admission_action = 'ADMIT'
      AND identity_row.r2_source_authority_record_id =
          entry ->> 'r2_source_authority_record_id';
    SELECT count(*), count(DISTINCT side.asset_id) INTO pair_count, side_count
    FROM demo_question_pairs pair_row
    CROSS JOIN LATERAL (
        VALUES (pair_row.left_asset_id), (pair_row.right_asset_id)
    ) AS side(asset_id)
    WHERE pair_row.question_bank_id = bank_row.id
      AND pair_row.schema_version = 'mirror.demo/DemoQuestionPair/v3'
      AND pair_row.screening_report_id = report_row.id
      AND pair_row.screening_report_digest = report_row.report_digest;
    pair_count := pair_count / 2;
    IF source_count IS DISTINCT FROM 4
       OR identity_count IS DISTINCT FROM 4
       OR pair_count IS DISTINCT FROM 16
       OR side_count IS DISTINCT FROM 32 THEN
        RAISE EXCEPTION 'D02 R2 Epoch 02 admission cardinality is invalid';
    END IF;
    expected_id := substring(mirror_demo_digest(
        'mirror.demo/D02R2Epoch2AdmissionId/v1',
        jsonb_build_object(
            'idempotency_key_hash', NEW.idempotency_key_hash,
            'request_digest', NEW.request_digest,
            'screening_report_id', NEW.screening_report_id,
            'question_bank_id', NEW.question_bank_id
        )
    ) FROM 1 FOR 32);
    IF NEW.id IS DISTINCT FROM expected_id THEN
        RAISE EXCEPTION 'D02 R2 Epoch 02 admission ID is invalid';
    END IF;
    RETURN NULL;
END;
$function$;
"""


def _create_e3_constraints() -> None:
    op.create_check_constraint(
        op.f("ck_demo_d02_r2_source_authorities_schema_version_shape"),
        "demo_d02_r2_source_authorities",
        f"schema_version IN ('{_SOURCE_V1}','{_SOURCE_E2}','{_SOURCE_E3}','{_SOURCE_E4}')",
    )
    op.create_check_constraint(
        op.f("ck_demo_d02_r2_source_authorities_evidence_root"),
        "demo_d02_r2_source_authorities",
        f"(schema_version = '{_SOURCE_V1}' AND evidence_root_id = '{_E1_ROOT}' "
        "AND generation_request_digest IS NULL AND execution_epoch IS NULL "
        "AND producer_task_id IS NULL AND dispatch_epoch IS NULL "
        "AND generation_source_asset_sha256 IS NULL "
        "AND generation_source_asset_byte_size IS NULL "
        "AND generation_source_asset_mime_type IS NULL "
        "AND generation_source_asset_width IS NULL "
        "AND generation_source_asset_height IS NULL "
        "AND source_normalization_receipt_digest IS NULL "
        "AND generation_policy_metadata IS NULL) OR "
        f"(schema_version = '{_SOURCE_E2}' AND evidence_root_id = '{_E2_ROOT}' "
        "AND generation_request_digest = generation_request_policy_digest "
        "AND execution_epoch = 'D02_R2_EPOCH_02' "
        "AND producer_task_id = 'P3_P7_D02_R2_SOURCE_COHORT_02' AND dispatch_epoch = 2 "
        "AND generation_source_asset_sha256 ~ '^[0-9a-f]{64}$' "
        "AND generation_source_asset_byte_size > 0 "
        "AND generation_source_asset_mime_type = 'image/png' "
        "AND generation_source_asset_width > 0 AND generation_source_asset_height > 0 "
        "AND source_normalization_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND generation_policy_metadata IS NULL) OR "
        f"(schema_version = '{_SOURCE_E3}' AND evidence_root_id = '{_E3_ROOT}' "
        "AND generation_request_digest = generation_request_policy_digest "
        "AND execution_epoch = 'D02_R2_EPOCH_03' "
        "AND producer_task_id = 'P3_P7_D02_R2_SOURCE_COHORT_03' AND dispatch_epoch = 3 "
        "AND generation_source_asset_sha256 ~ '^[0-9a-f]{64}$' "
        "AND generation_source_asset_byte_size > 0 "
        "AND generation_source_asset_mime_type = 'image/png' "
        "AND generation_source_asset_width > 0 AND generation_source_asset_height > 0 "
        "AND source_normalization_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND jsonb_typeof(generation_policy_metadata) = 'object') OR "
        f"(schema_version = '{_SOURCE_E4}' AND evidence_root_id = '{_E4_ROOT}' "
        "AND generation_request_digest = generation_request_policy_digest "
        "AND execution_epoch = 'D02_R2_EPOCH_04' "
        "AND producer_task_id = 'P3_P7_D02_R2_SOURCE_COHORT_04' AND dispatch_epoch = 4 "
        "AND generation_source_asset_sha256 ~ '^[0-9a-f]{64}$' "
        "AND generation_source_asset_byte_size > 0 "
        "AND generation_source_asset_mime_type = 'image/png' "
        "AND generation_source_asset_width > 0 AND generation_source_asset_height > 0 "
        "AND source_normalization_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND jsonb_typeof(generation_policy_metadata) = 'object')",
    )
    op.create_check_constraint(
        op.f("ck_demo_d02_r2_epoch2_admissions_schema_version_shape"),
        "demo_d02_r2_epoch2_admissions",
        f"schema_version IN ('{_ADMISSION_E2}','{_ADMISSION_E3}','{_ADMISSION_E4}')",
    )
    op.create_check_constraint(
        op.f("ck_demo_d02_r2_epoch2_admissions_epoch_root"),
        "demo_d02_r2_epoch2_admissions",
        f"(schema_version = '{_ADMISSION_E2}' AND execution_epoch = 'D02_R2_EPOCH_02' "
        f"AND evidence_root_id = '{_E2_ROOT}') OR "
        f"(schema_version = '{_ADMISSION_E3}' AND execution_epoch = 'D02_R2_EPOCH_03' "
        f"AND evidence_root_id = '{_E3_ROOT}') OR "
        f"(schema_version = '{_ADMISSION_E4}' AND execution_epoch = 'D02_R2_EPOCH_04' "
        f"AND evidence_root_id = '{_E4_ROOT}')",
    )


def _create_e3_policy_constraint() -> None:
    op.create_check_constraint(
        op.f("ck_demo_d02_r2_source_authorities_generation_policy_metadata"),
        "demo_d02_r2_source_authorities",
        "generation_policy_metadata IS NULL OR ("
        f"schema_version IN ('{_SOURCE_E3}','{_SOURCE_E4}') "
        "AND generation_policy_metadata ->> 'schema_version' = "
        "CASE WHEN schema_version = 'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1' "
        "THEN 'mirror.demo/D02R2Epoch3GenerationPolicyMetadata/v1' "
        "ELSE 'mirror.demo/D02R2Epoch4GenerationPolicyMetadata/v1' END "
        "AND generation_policy_metadata ->> 'adult_status' = "
        "'VERIFIED_SYNTHETIC_ADULT' "
        "AND generation_policy_metadata ->> 'suspected_minor' = 'false' "
        "AND generation_policy_metadata ->> 'real_person_reference' = 'false' "
        "AND generation_policy_metadata ->> 'celebrity_resemblance' = 'false' "
        "AND generation_policy_metadata ->> 'source_digest' = source_asset_sha256 "
        "AND generation_policy_metadata ->> 'metadata_digest' ~ '^[0-9a-f]{64}$' "
        "AND generation_policy_metadata -> 'source_policy_profile' ->> "
        "'declared_age_band' IN ('ADULT_18_19','ADULT_20_25'))",
    )


def _create_e2_constraints() -> None:
    op.create_check_constraint(
        op.f("ck_demo_d02_r2_source_authorities_schema_version_shape"),
        "demo_d02_r2_source_authorities",
        f"schema_version IN ('{_SOURCE_V1}','{_SOURCE_E2}')",
    )
    op.create_check_constraint(
        op.f("ck_demo_d02_r2_source_authorities_evidence_root"),
        "demo_d02_r2_source_authorities",
        f"(schema_version = '{_SOURCE_V1}' AND evidence_root_id = '{_E1_ROOT}' "
        "AND generation_request_digest IS NULL AND execution_epoch IS NULL "
        "AND producer_task_id IS NULL AND dispatch_epoch IS NULL "
        "AND generation_source_asset_sha256 IS NULL "
        "AND generation_source_asset_byte_size IS NULL "
        "AND generation_source_asset_mime_type IS NULL "
        "AND generation_source_asset_width IS NULL "
        "AND generation_source_asset_height IS NULL "
        "AND source_normalization_receipt_digest IS NULL) OR "
        f"(schema_version = '{_SOURCE_E2}' AND evidence_root_id = '{_E2_ROOT}' "
        "AND generation_request_digest = generation_request_policy_digest "
        "AND execution_epoch = 'D02_R2_EPOCH_02' "
        "AND producer_task_id = 'P3_P7_D02_R2_SOURCE_COHORT_02' AND dispatch_epoch = 2 "
        "AND generation_source_asset_sha256 ~ '^[0-9a-f]{64}$' "
        "AND generation_source_asset_byte_size > 0 "
        "AND generation_source_asset_mime_type = 'image/png' "
        "AND generation_source_asset_width > 0 AND generation_source_asset_height > 0 "
        "AND source_normalization_receipt_digest ~ '^[0-9a-f]{64}$')",
    )
    op.create_check_constraint(
        op.f("ck_demo_d02_r2_epoch2_admissions_schema_version_shape"),
        "demo_d02_r2_epoch2_admissions",
        f"schema_version = '{_ADMISSION_E2}'",
    )
    op.create_check_constraint(
        op.f("ck_demo_d02_r2_epoch2_admissions_epoch_root"),
        "demo_d02_r2_epoch2_admissions",
        f"execution_epoch = 'D02_R2_EPOCH_02' AND evidence_root_id = '{_E2_ROOT}'",
    )


def _drop_version_constraints() -> None:
    for table_name, constraint_name in (
        ("demo_d02_r2_source_authorities", "schema_version_shape"),
        ("demo_d02_r2_source_authorities", "evidence_root"),
        ("demo_d02_r2_epoch2_admissions", "schema_version_shape"),
        ("demo_d02_r2_epoch2_admissions", "epoch_root"),
    ):
        op.drop_constraint(op.f(f"ck_{table_name}_{constraint_name}"), table_name, type_="check")


def upgrade() -> None:
    op.add_column(
        "demo_d02_r2_source_authorities",
        sa.Column(
            "generation_policy_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    _drop_version_constraints()
    _create_e3_constraints()
    _create_e3_policy_constraint()
    op.execute(_SOURCE_TRIGGER_V3_SQL)
    op.execute(_ADMISSION_TRIGGER_V3_SQL)


def downgrade() -> None:
    op.execute(
        """
        DO $block$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM demo_d02_r2_source_authorities
                WHERE schema_version IN (
                    'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1',
                    'mirror.demo/D02R2Epoch4SourceAuthorityRecord/v1'
                )
            ) OR EXISTS (
                SELECT 1 FROM demo_d02_r2_epoch2_admissions
                WHERE schema_version IN (
                    'mirror.demo/D02R2Epoch3Admission/v1',
                    'mirror.demo/D02R2Epoch4Admission/v1'
                )
            ) THEN
                RAISE EXCEPTION 'D02 R2 Epoch 03 authority exists or Epoch 04 authority exists; downgrade is forbidden';
            END IF;
        END;
        $block$;
        """
    )
    _drop_version_constraints()
    op.drop_constraint(
        op.f("ck_demo_d02_r2_source_authorities_generation_policy_metadata"),
        "demo_d02_r2_source_authorities",
        type_="check",
    )
    op.execute(_SOURCE_TRIGGER_V2_SQL)
    op.execute(_ADMISSION_INTEGRITY_SQL)
    op.drop_column("demo_d02_r2_source_authorities", "generation_policy_metadata")
    _create_e2_constraints()
