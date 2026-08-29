"""Add D02-R2 Epoch 02 source and atomic bank admission authority.

Revision ID: demo_0009_d02_r2_e2_adm
Revises: demo_0008_d02_r2_source_auth
Create Date: 2026-08-29

PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "demo_0009_d02_r2_e2_adm"
down_revision: str | None = "demo_0008_d02_r2_source_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROTOTYPE_MIGRATION = True
FORMAL_PHASE_AUTHORITY = False
DIRECT_MAINLINE_CHERRY_PICK = "FORBIDDEN"

_SOURCE_V1 = "mirror.demo/D02R2SourceAuthorityRecord/v1"
_SOURCE_E2 = "mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1"
_ADMISSION = "mirror.demo/D02R2Epoch2Admission/v1"
_E1_ROOT = "P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT"
_E2_ROOT = "P3_P7_D02_R2_CC08_E2_EVIDENCE_ROOT"

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

_SOURCE_TRIGGER_V1_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_r2_source_authority()
RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE expected_id text; source_asset assets%ROWTYPE; expected_payload jsonb;
BEGIN
    IF TG_OP IS DISTINCT FROM 'INSERT' THEN
        RAISE EXCEPTION 'D02 R2 supporting row is append-only';
    END IF;
    expected_payload := mirror_demo_authority_projection(to_jsonb(NEW), TG_TABLE_NAME);
    IF NEW.canonical_payload IS DISTINCT FROM expected_payload
       OR NEW.content_digest IS DISTINCT FROM mirror_demo_digest(NEW.schema_version, expected_payload) THEN
        RAISE EXCEPTION 'D02 R2 supporting row canonical authority is invalid';
    END IF;
    expected_id := substring(mirror_demo_digest('mirror.demo/D02R2SourceAuthorityRecordId/v1',
        jsonb_build_object(
          'execution_contract_digest', NEW.execution_contract_digest,
          'evidence_root_id', NEW.evidence_root_id,
          'root_name_receipt_digest', NEW.root_name_receipt_digest,
          'generation_preregistration_digest', NEW.generation_preregistration_digest,
          'source_allocation_manifest_digest', NEW.source_allocation_manifest_digest,
          'source_producer_dispatch_digest', NEW.source_producer_dispatch_digest,
          'source_ordinal', NEW.source_ordinal, 'source_output_id', NEW.source_output_id,
          'source_authority_key', NEW.source_authority_key,
          'source_authority_digest', NEW.source_authority_digest,
          'source_qa_snapshot_digest', NEW.source_qa_snapshot_digest,
          'content_digest', NEW.content_digest)) FROM 1 FOR 32);
    IF NEW.id IS DISTINCT FROM expected_id THEN
        RAISE EXCEPTION 'D02 R2 supporting row ID is invalid';
    END IF;
    IF NEW.source_authority_key IS DISTINCT FROM mirror_demo_r2_source_authority_key(
        NEW.source_output_id, NEW.source_asset_id, NEW.source_asset_sha256,
        NEW.source_generation_receipt_digest, NEW.source_authority_digest) THEN
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


def upgrade() -> None:
    op.execute(
        "LOCK TABLE demo_d02_r2_source_authorities, demo_synthetic_identities, "
        "demo_pair_screening_reports, demo_question_banks, demo_question_pairs "
        "IN ACCESS EXCLUSIVE MODE"
    )
    op.add_column(
        "demo_d02_r2_source_authorities",
        sa.Column("generation_request_digest", sa.String(length=64)),
    )
    op.add_column(
        "demo_d02_r2_source_authorities",
        sa.Column("execution_epoch", sa.String(length=64)),
    )
    op.add_column(
        "demo_d02_r2_source_authorities",
        sa.Column("producer_task_id", sa.String(length=128)),
    )
    op.add_column(
        "demo_d02_r2_source_authorities",
        sa.Column("dispatch_epoch", sa.SmallInteger()),
    )
    op.add_column(
        "demo_d02_r2_source_authorities",
        sa.Column("generation_source_asset_sha256", sa.String(length=64)),
    )
    op.add_column(
        "demo_d02_r2_source_authorities",
        sa.Column("generation_source_asset_byte_size", sa.BigInteger()),
    )
    op.add_column(
        "demo_d02_r2_source_authorities",
        sa.Column("generation_source_asset_mime_type", sa.String(length=64)),
    )
    op.add_column(
        "demo_d02_r2_source_authorities",
        sa.Column("generation_source_asset_width", sa.Integer()),
    )
    op.add_column(
        "demo_d02_r2_source_authorities",
        sa.Column("generation_source_asset_height", sa.Integer()),
    )
    op.add_column(
        "demo_d02_r2_source_authorities",
        sa.Column("source_normalization_receipt_digest", sa.String(length=64)),
    )
    for name in ("schema_version_shape", "decoded_mime", "evidence_root", "digest_shapes"):
        op.drop_constraint(
            op.f(f"ck_demo_d02_r2_source_authorities_{name}"),
            "demo_d02_r2_source_authorities",
            type_="check",
        )
    op.create_check_constraint(
        op.f("ck_demo_d02_r2_source_authorities_schema_version_shape"),
        "demo_d02_r2_source_authorities",
        f"schema_version IN ('{_SOURCE_V1}','{_SOURCE_E2}')",
    )
    op.create_check_constraint(
        op.f("ck_demo_d02_r2_source_authorities_decoded_mime"),
        "demo_d02_r2_source_authorities",
        "source_asset_mime_type = 'image/jpeg'",
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
        "AND generation_source_asset_width > 0 "
        "AND generation_source_asset_height > 0 "
        "AND source_normalization_receipt_digest ~ '^[0-9a-f]{64}$')",
    )
    op.create_check_constraint(
        op.f("ck_demo_d02_r2_source_authorities_digest_shapes"),
        "demo_d02_r2_source_authorities",
        "source_asset_sha256 ~ '^[0-9a-f]{64}$' "
        "AND source_authority_key ~ '^[0-9a-f]{64}$' "
        "AND execution_contract_digest ~ '^[0-9a-f]{64}$' "
        "AND root_name_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND generation_preregistration_digest ~ '^[0-9a-f]{64}$' "
        "AND source_allocation_manifest_digest ~ '^[0-9a-f]{64}$' "
        "AND source_producer_dispatch_digest ~ '^[0-9a-f]{64}$' "
        "AND source_generation_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND output_name_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND output_seal_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND registry_commit_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND generation_capability_authority_digest ~ '^[0-9a-f]{64}$' "
        "AND generation_request_policy_digest ~ '^[0-9a-f]{64}$' "
        "AND (generation_request_digest IS NULL OR generation_request_digest ~ '^[0-9a-f]{64}$') "
        "AND (generation_source_asset_sha256 IS NULL OR "
        "generation_source_asset_sha256 ~ '^[0-9a-f]{64}$') "
        "AND (source_normalization_receipt_digest IS NULL OR "
        "source_normalization_receipt_digest ~ '^[0-9a-f]{64}$') "
        "AND source_provenance_digest ~ '^[0-9a-f]{64}$' "
        "AND source_provenance_name_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND source_provenance_seal_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND source_provenance_registry_commit_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND source_authority_digest ~ '^[0-9a-f]{64}$' "
        "AND source_qa_snapshot_digest ~ '^[0-9a-f]{64}$'",
    )
    op.create_unique_constraint(
        "generation_request_digest",
        "demo_d02_r2_source_authorities",
        ["generation_request_digest"],
    )
    op.create_unique_constraint(
        "source_normalization_receipt_digest",
        "demo_d02_r2_source_authorities",
        ["source_normalization_receipt_digest"],
    )
    op.execute(_SOURCE_TRIGGER_V2_SQL)

    op.create_table(
        "demo_d02_r2_epoch2_admissions",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("schema_version", sa.String(length=112), nullable=False),
        sa.Column("canonical_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("execution_epoch", sa.String(length=64), nullable=False),
        sa.Column("evidence_root_id", sa.String(length=128), nullable=False),
        sa.Column("source_manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("screening_report_id", sa.String(length=32), nullable=False),
        sa.Column("screening_report_digest", sa.String(length=64), nullable=False),
        sa.Column("question_bank_id", sa.String(length=32), nullable=False),
        sa.Column("question_bank_content_digest", sa.String(length=64), nullable=False),
        sa.Column("question_bank_version", sa.String(length=64), nullable=False),
        sa.Column("selected_pair_manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("source_authority_count", sa.SmallInteger(), nullable=False),
        sa.Column("synthetic_identity_count", sa.SmallInteger(), nullable=False),
        sa.Column("question_pair_count", sa.SmallInteger(), nullable=False),
        sa.Column("selected_result_side_count", sa.SmallInteger(), nullable=False),
        sa.Column("admission_state", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{32}$'", name=op.f("ck_demo_d02_r2_epoch2_admissions_id_shape")
        ),
        sa.CheckConstraint(
            f"schema_version = '{_ADMISSION}'",
            name=op.f("ck_demo_d02_r2_epoch2_admissions_schema_version_shape"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(canonical_payload) = 'object'",
            name=op.f("ck_demo_d02_r2_epoch2_admissions_canonical_payload_object"),
        ),
        sa.CheckConstraint(
            "content_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_d02_r2_epoch2_admissions_content_digest_shape"),
        ),
        sa.CheckConstraint(
            "idempotency_key_hash ~ '^[0-9a-f]{64}$' AND request_digest ~ '^[0-9a-f]{64}$' "
            "AND source_manifest_digest ~ '^[0-9a-f]{64}$' "
            "AND screening_report_digest ~ '^[0-9a-f]{64}$' "
            "AND question_bank_content_digest ~ '^[0-9a-f]{64}$' "
            "AND selected_pair_manifest_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_d02_r2_epoch2_admissions_digest_shapes"),
        ),
        sa.CheckConstraint(
            f"execution_epoch = 'D02_R2_EPOCH_02' AND evidence_root_id = '{_E2_ROOT}'",
            name=op.f("ck_demo_d02_r2_epoch2_admissions_epoch_root"),
        ),
        sa.CheckConstraint(
            "source_authority_count = 4 AND synthetic_identity_count = 4 "
            "AND question_pair_count = 16 AND selected_result_side_count = 32",
            name=op.f("ck_demo_d02_r2_epoch2_admissions_fixed_cardinality"),
        ),
        sa.CheckConstraint(
            "admission_state = 'COMPLETED'",
            name=op.f("ck_demo_d02_r2_epoch2_admissions_state"),
        ),
        sa.ForeignKeyConstraint(
            ["screening_report_id"],
            ["demo_pair_screening_reports.id"],
            name=op.f(
                "fk_demo_d02_r2_epoch2_admissions_screening_report_id_demo_pair_screening_reports"
            ),
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["question_bank_id"],
            ["demo_question_banks.id"],
            name=op.f("fk_demo_d02_r2_epoch2_admissions_question_bank_id_demo_question_banks"),
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.UniqueConstraint(
            "content_digest", name=op.f("uq_demo_d02_r2_epoch2_admissions_content_digest")
        ),
        sa.UniqueConstraint(
            "idempotency_key_hash",
            name="idempotency_key_hash",
        ),
        sa.UniqueConstraint("screening_report_id", name="screening_report_id"),
        sa.UniqueConstraint("question_bank_id", name="question_bank_id"),
    )
    op.create_index(
        op.f("ix_demo_d02_r2_epoch2_admissions_screening_report_id"),
        "demo_d02_r2_epoch2_admissions",
        ["screening_report_id"],
    )
    op.create_index(
        op.f("ix_demo_d02_r2_epoch2_admissions_question_bank_id"),
        "demo_d02_r2_epoch2_admissions",
        ["question_bank_id"],
    )
    op.execute(
        "CREATE TRIGGER trg_demo_authority_demo_d02_r2_epoch2_admissions "
        "BEFORE INSERT OR UPDATE OR DELETE ON demo_d02_r2_epoch2_admissions "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_guard_authority()"
    )
    op.execute(_ADMISSION_INTEGRITY_SQL)
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_demo_d02_r2_epoch2_admission_integrity "
        "AFTER INSERT ON demo_d02_r2_epoch2_admissions DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d02_r2_epoch2_admission()"
    )


def downgrade() -> None:
    op.execute(
        """
DO $block$
BEGIN
    IF EXISTS (SELECT 1 FROM demo_d02_r2_epoch2_admissions)
       OR EXISTS (
           SELECT 1 FROM demo_d02_r2_source_authorities
           WHERE schema_version = 'mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1'
       ) THEN
        RAISE EXCEPTION 'Prototype downgrade blocked by D02 R2 Epoch 02 authority';
    END IF;
END;
$block$;
"""
    )
    op.execute(
        "DROP TRIGGER trg_demo_d02_r2_epoch2_admission_integrity ON demo_d02_r2_epoch2_admissions"
    )
    op.execute("DROP FUNCTION mirror_demo_validate_d02_r2_epoch2_admission()")
    op.execute(
        "DROP TRIGGER trg_demo_authority_demo_d02_r2_epoch2_admissions "
        "ON demo_d02_r2_epoch2_admissions"
    )
    op.drop_index(
        op.f("ix_demo_d02_r2_epoch2_admissions_question_bank_id"),
        table_name="demo_d02_r2_epoch2_admissions",
    )
    op.drop_index(
        op.f("ix_demo_d02_r2_epoch2_admissions_screening_report_id"),
        table_name="demo_d02_r2_epoch2_admissions",
    )
    op.drop_table("demo_d02_r2_epoch2_admissions")
    op.execute(_SOURCE_TRIGGER_V1_SQL)
    op.drop_constraint(
        "source_normalization_receipt_digest",
        "demo_d02_r2_source_authorities",
        type_="unique",
    )
    op.drop_constraint(
        "generation_request_digest",
        "demo_d02_r2_source_authorities",
        type_="unique",
    )
    for name in ("schema_version_shape", "decoded_mime", "evidence_root", "digest_shapes"):
        op.drop_constraint(
            op.f(f"ck_demo_d02_r2_source_authorities_{name}"),
            "demo_d02_r2_source_authorities",
            type_="check",
        )
    op.drop_column("demo_d02_r2_source_authorities", "dispatch_epoch")
    op.drop_column("demo_d02_r2_source_authorities", "producer_task_id")
    op.drop_column("demo_d02_r2_source_authorities", "execution_epoch")
    op.drop_column("demo_d02_r2_source_authorities", "generation_request_digest")
    op.drop_column("demo_d02_r2_source_authorities", "source_normalization_receipt_digest")
    op.drop_column("demo_d02_r2_source_authorities", "generation_source_asset_height")
    op.drop_column("demo_d02_r2_source_authorities", "generation_source_asset_width")
    op.drop_column("demo_d02_r2_source_authorities", "generation_source_asset_mime_type")
    op.drop_column("demo_d02_r2_source_authorities", "generation_source_asset_byte_size")
    op.drop_column("demo_d02_r2_source_authorities", "generation_source_asset_sha256")
    op.create_check_constraint(
        op.f("ck_demo_d02_r2_source_authorities_schema_version_shape"),
        "demo_d02_r2_source_authorities",
        f"schema_version = '{_SOURCE_V1}'",
    )
    op.create_check_constraint(
        op.f("ck_demo_d02_r2_source_authorities_decoded_mime"),
        "demo_d02_r2_source_authorities",
        "source_asset_mime_type IN ('image/jpeg')",
    )
    op.create_check_constraint(
        op.f("ck_demo_d02_r2_source_authorities_evidence_root"),
        "demo_d02_r2_source_authorities",
        f"evidence_root_id = '{_E1_ROOT}'",
    )
    op.create_check_constraint(
        op.f("ck_demo_d02_r2_source_authorities_digest_shapes"),
        "demo_d02_r2_source_authorities",
        "source_asset_sha256 ~ '^[0-9a-f]{64}$' AND source_authority_key ~ '^[0-9a-f]{64}$' "
        "AND execution_contract_digest ~ '^[0-9a-f]{64}$' "
        "AND root_name_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND generation_preregistration_digest ~ '^[0-9a-f]{64}$' "
        "AND source_allocation_manifest_digest ~ '^[0-9a-f]{64}$' "
        "AND source_producer_dispatch_digest ~ '^[0-9a-f]{64}$' "
        "AND source_generation_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND output_name_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND output_seal_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND registry_commit_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND generation_capability_authority_digest ~ '^[0-9a-f]{64}$' "
        "AND generation_request_policy_digest ~ '^[0-9a-f]{64}$' "
        "AND source_provenance_digest ~ '^[0-9a-f]{64}$' "
        "AND source_provenance_name_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND source_provenance_seal_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND source_provenance_registry_commit_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND source_authority_digest ~ '^[0-9a-f]{64}$' "
        "AND source_qa_snapshot_digest ~ '^[0-9a-f]{64}$'",
    )
