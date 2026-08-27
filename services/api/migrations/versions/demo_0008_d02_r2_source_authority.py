"""Add D02-R2 parallel source authority.

Revision ID: demo_0008_d02_r2_source_auth
Revises: demo_0007_d02_recovered_qa
Create Date: 2026-08-26

PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "demo_0008_d02_r2_source_auth"
down_revision: str | None = "demo_0007_d02_recovered_qa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROTOTYPE_MIGRATION = True
FORMAL_PHASE_AUTHORITY = False
DIRECT_MAINLINE_CHERRY_PICK = "FORBIDDEN"

_LOCK_SQL = """
LOCK TABLE demo_synthetic_identities IN ACCESS EXCLUSIVE MODE;
LOCK TABLE demo_pair_screening_reports IN ACCESS EXCLUSIVE MODE;
LOCK TABLE demo_question_banks IN ACCESS EXCLUSIVE MODE;
LOCK TABLE demo_question_pairs IN ACCESS EXCLUSIVE MODE;
"""


def _authority_projection_sql(*, r2: bool) -> str:
    compatibility_projection = (
        r"""
    IF authority_table = 'demo_synthetic_identities'
       AND row_data ->> 'schema_version' IN (
           'mirror.demo/DemoSyntheticIdentity/v1',
           'mirror.demo/DemoSyntheticIdentity/v2',
           'mirror.demo/DemoSyntheticIdentity/v3'
       ) THEN
        projected := projected - 'r2_source_authority_record_id';
    END IF;
    IF authority_table = 'demo_pair_screening_reports'
       AND row_data ->> 'schema_version' IN (
           'mirror.demo/D02PairScreeningReport/v1',
           'mirror.demo/D02PairScreeningReport/v2'
       ) THEN
        projected := projected - ARRAY[
            'measurement_gate_count',
            'decode_structure_record_count'
        ]::text[];
    END IF;
    IF authority_table = 'demo_pair_screening_reports'
       AND row_data ->> 'schema_version' =
           'mirror.demo/D02PairScreeningReport/v3' THEN
        projected := projected - 'report_digest';
    END IF;
"""
        if r2
        else ""
    )
    return (
        r"""
CREATE OR REPLACE FUNCTION mirror_demo_authority_projection(
    row_data jsonb,
    authority_table text
)
RETURNS jsonb
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
DECLARE
    projected jsonb;
    timestamp_key text;
BEGIN
    projected := row_data - ARRAY[
        'id',
        'schema_version',
        'canonical_payload',
        'content_digest',
        'created_at',
        'closed_at',
        'tombstoned_at'
    ]::text[];

    FOREACH timestamp_key IN ARRAY ARRAY[
        'authority_at',
        'expires_at',
        'occurred_at',
        'context_as_of_time'
    ]::text[] LOOP
        IF projected ? timestamp_key AND projected -> timestamp_key <> 'null'::jsonb THEN
            projected := jsonb_set(
                projected,
                ARRAY[timestamp_key],
                to_jsonb(
                    to_char(
                        (projected ->> timestamp_key)::timestamptz AT TIME ZONE 'UTC',
                        'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
                    )
                ),
                false
            );
        END IF;
    END LOOP;

    IF authority_table NOT LIKE 'demo\_%' ESCAPE '\' THEN
        RAISE EXCEPTION 'Demo authority projection rejected unexpected table %', authority_table;
    END IF;
"""
        + compatibility_projection
        + r"""    RETURN projected;
END;
$function$;
"""
    )


_DIGEST_COLUMNS = (
    "execution_contract_digest",
    "root_name_receipt_digest",
    "generation_preregistration_digest",
    "source_allocation_manifest_digest",
    "source_producer_dispatch_digest",
    "source_asset_sha256",
    "source_generation_receipt_digest",
    "output_name_receipt_digest",
    "output_seal_receipt_digest",
    "registry_commit_receipt_digest",
    "generation_capability_authority_digest",
    "generation_request_policy_digest",
    "source_provenance_digest",
    "source_provenance_name_receipt_digest",
    "source_provenance_seal_receipt_digest",
    "source_provenance_registry_commit_receipt_digest",
    "source_authority_digest",
    "source_authority_key",
    "source_qa_snapshot_digest",
)

_R2_ROW_COLUMNS = (
    "execution_contract_digest",
    "evidence_root_id",
    "root_name_receipt_digest",
    "generation_preregistration_digest",
    "source_allocation_manifest_digest",
    "source_producer_dispatch_digest",
    "source_ordinal",
    "source_output_id",
    "source_asset_id",
    "source_asset_sha256",
    "source_asset_byte_size",
    "source_asset_mime_type",
    "source_asset_width",
    "source_asset_height",
    "source_generation_receipt_digest",
    "output_name_receipt_digest",
    "output_seal_receipt_digest",
    "registry_commit_receipt_digest",
    "generation_capability_authority_digest",
    "generation_request_policy_digest",
    "source_provenance_digest",
    "source_provenance_output_id",
    "source_provenance_name_receipt_digest",
    "source_provenance_seal_receipt_digest",
    "source_provenance_registry_commit_receipt_digest",
    "source_authority_digest",
    "source_authority_key",
    "source_qa_snapshot_digest",
    "adult_synthetic_attested",
    "synthetic_only_attested",
    "real_person_reference_used",
    "authority_state",
)

_R2_ID_PREIMAGE = (
    "execution_contract_digest",
    "evidence_root_id",
    "root_name_receipt_digest",
    "generation_preregistration_digest",
    "source_allocation_manifest_digest",
    "source_producer_dispatch_digest",
    "source_ordinal",
    "source_output_id",
    "source_authority_key",
    "source_authority_digest",
    "source_qa_snapshot_digest",
    "content_digest",
)

_UNIQUE_CONSTRAINT_NAMES = {
    "source_output_id": "source_output_id",
    "source_generation_receipt_digest": "source_generation_receipt",
    "output_name_receipt_digest": "output_name_receipt",
    "output_seal_receipt_digest": "output_seal_receipt",
    "registry_commit_receipt_digest": "registry_commit_receipt",
    "source_provenance_output_id": "source_provenance_output_id",
    "source_provenance_name_receipt_digest": "source_provenance_name",
    "source_provenance_seal_receipt_digest": "source_provenance_seal",
    "source_provenance_registry_commit_receipt_digest": "source_provenance_commit",
    "source_authority_digest": "source_authority_digest",
    "source_authority_key": "source_authority_key",
    "source_qa_snapshot_digest": "source_qa_snapshot_digest",
}

_LOCAL_QA_CHECK = """schema_version <> 'mirror.demo/DemoSyntheticIdentity/v3'
OR source_authority_kind <> 'DEMO_LOCAL_IMPORTED_COPY'
OR (
    source_qa_snapshot_digest IS NOT NULL
    AND jsonb_typeof(source_fact_snapshot) IS NOT DISTINCT FROM 'object'
    AND (source_fact_snapshot ->> 'source_qa_snapshot_digest') IS NOT DISTINCT FROM source_qa_snapshot_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM formal_canonical_asset_sha256
    AND source_qa_snapshot_digest IS DISTINCT FROM source_receipt_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM source_authority_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM source_landmark_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM source_measurement_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM source_provenance_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM source_fact_snapshot_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM source_measurement_projection_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM (source_fact_snapshot ->> 'source_asset_sha256')
    AND source_qa_snapshot_digest IS DISTINCT FROM (source_fact_snapshot ->> 'source_receipt_digest')
    AND source_qa_snapshot_digest IS DISTINCT FROM (source_fact_snapshot ->> 'source_authority_digest')
    AND source_qa_snapshot_digest IS DISTINCT FROM (source_fact_snapshot ->> 'qa_policy_digest')
    AND source_qa_snapshot_digest IS DISTINCT FROM (source_fact_snapshot ->> 'source_landmark_digest')
    AND source_qa_snapshot_digest IS DISTINCT FROM (source_fact_snapshot ->> 'source_measurement_digest')
    AND source_qa_snapshot_digest IS DISTINCT FROM (source_fact_snapshot ->> 'source_provenance_digest')
    AND source_qa_snapshot_digest IS DISTINCT FROM (source_fact_snapshot ->> 'source_measurement_projection_digest')
    AND source_qa_snapshot_digest IS DISTINCT FROM (source_fact_snapshot ->> 'raw_measurement_authority_digest')
    AND source_qa_snapshot_digest IS DISTINCT FROM (source_fact_snapshot ->> 'source_measurement_observation_digest')
    AND source_qa_snapshot_digest IS DISTINCT FROM (source_fact_snapshot ->> 'source_repeat_certification_digest')
    AND source_qa_snapshot_digest IS DISTINCT FROM (source_fact_snapshot ->> 'source_p2_candidate_manifest_content_digest')
    AND source_qa_snapshot_digest IS DISTINCT FROM (source_fact_snapshot ->> 'dimension_authority_manifest_content_digest')
)"""


# This is the exact v10 authority guard introduced by demo_0005.  The R2
# upgrade replaces it only while the R2-only column is present; downgrade must
# reinstate the clean demo_0007 definition before later historical downgrades.
_D02_V10_GUARD_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_guard_authority()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    expected_payload jsonb;
    expected_digest text;
    close_changed boolean := false;
    tombstone_changed boolean := false;
    derived_kind text;
    derived_key text;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Demo authority row is append-only: %', TG_TABLE_NAME;
    END IF;

    IF TG_OP = 'UPDATE' THEN
        IF TG_TABLE_NAME NOT IN ('demo_actors', 'demo_sessions', 'demo_editing_sessions') THEN
            RAISE EXCEPTION 'Demo authority row is immutable: %', TG_TABLE_NAME;
        END IF;
        IF TG_TABLE_NAME = 'demo_actors' THEN
            IF OLD.tombstoned_at IS NOT NULL
                OR NEW.tombstoned_at IS NULL
                OR (to_jsonb(NEW) - 'tombstoned_at') IS DISTINCT FROM
                   (to_jsonb(OLD) - 'tombstoned_at') THEN
                RAISE EXCEPTION 'Invalid Demo actor tombstone transition';
            END IF;
        ELSE
            close_changed := OLD.closed_at IS NULL AND NEW.closed_at IS NOT NULL;
            tombstone_changed := OLD.tombstoned_at IS NULL AND NEW.tombstoned_at IS NOT NULL;
            IF NOT (close_changed OR tombstone_changed)
                OR (tombstone_changed AND OLD.closed_at IS NULL)
                OR (OLD.closed_at IS NOT NULL AND NEW.closed_at IS DISTINCT FROM OLD.closed_at)
                OR (OLD.tombstoned_at IS NOT NULL AND
                    NEW.tombstoned_at IS DISTINCT FROM OLD.tombstoned_at)
                OR (to_jsonb(NEW) - ARRAY['closed_at', 'tombstoned_at']::text[]) IS DISTINCT FROM
                   (to_jsonb(OLD) - ARRAY['closed_at', 'tombstoned_at']::text[]) THEN
                RAISE EXCEPTION 'Invalid Demo terminal header transition: %', TG_TABLE_NAME;
            END IF;
        END IF;
    ELSIF TG_TABLE_NAME = 'demo_actors' THEN
        IF NEW.tombstoned_at IS NOT NULL THEN
            RAISE EXCEPTION 'Demo actor must be created active';
        END IF;
    ELSIF TG_TABLE_NAME IN ('demo_sessions', 'demo_editing_sessions') THEN
        IF NEW.closed_at IS NOT NULL OR NEW.tombstoned_at IS NOT NULL THEN
            RAISE EXCEPTION 'Demo session header must be created open';
        END IF;
    END IF;

    IF jsonb_typeof(NEW.canonical_payload) IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION 'Demo canonical payload must be a JSON object';
    END IF;

    IF TG_TABLE_NAME = 'demo_synthetic_identities'
        AND NEW.schema_version IN (
            'mirror.demo/DemoSyntheticIdentity/v2',
            'mirror.demo/DemoSyntheticIdentity/v3'
        ) THEN
        derived_kind := CASE
            WHEN NEW.formal_synthetic_identity_id IS NOT NULL THEN 'FORMAL_REFERENCE'
            ELSE 'DEMO_LOCAL_IMPORTED_COPY'
        END;
        derived_key := CASE derived_kind
            WHEN 'FORMAL_REFERENCE' THEN mirror_demo_formal_source_authority_key(
                NEW.formal_synthetic_identity_id
            )
            ELSE mirror_demo_local_source_authority_key(
                NEW.source_output_id,
                NEW.formal_canonical_asset_id,
                NEW.formal_canonical_asset_sha256,
                NEW.source_receipt_digest
            )
        END;
        expected_payload := mirror_demo_authority_projection(
            to_jsonb(NEW) || jsonb_build_object(
                'source_authority_kind', derived_kind,
                'source_authority_key', derived_key
            ),
            TG_TABLE_NAME
        );
    ELSE
        expected_payload := mirror_demo_authority_projection(to_jsonb(NEW), TG_TABLE_NAME);
        IF TG_TABLE_NAME = 'demo_pair_screening_reports'
            AND to_jsonb(NEW) ->> 'status' = 'FAILED' THEN
            expected_payload := expected_payload - 'selected_pair_manifest_digest';
        END IF;
    END IF;
    IF NEW.canonical_payload IS DISTINCT FROM expected_payload THEN
        RAISE EXCEPTION 'Demo canonical payload disagrees with structured authority: %', TG_TABLE_NAME;
    END IF;

    expected_digest := mirror_demo_digest(NEW.schema_version, NEW.canonical_payload);
    IF NEW.content_digest IS DISTINCT FROM expected_digest THEN
        RAISE EXCEPTION 'Demo canonical digest mismatch: %', TG_TABLE_NAME;
    END IF;
    RETURN NEW;
END;
$function$;
"""


# R2 temporarily broadens this parent guard for v4/v3 writes.  Its exact
# demo_0007 definition must be restored on downgrade so a clean 0007 schema
# retains the same function fingerprint and legacy fail-closed behavior.
_D02_V10_WRITE_GUARDS_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_write_version_v10()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    report_schema text;
    identity_schema text;
BEGIN
    IF TG_TABLE_NAME = 'demo_synthetic_identities' THEN
        IF NEW.schema_version = 'mirror.demo/DemoSyntheticIdentity/v3'
            AND NEW.formal_synthetic_identity_id IS NULL THEN
            RETURN NEW;
        END IF;
        IF NEW.schema_version = 'mirror.demo/DemoSyntheticIdentity/v2'
            AND NEW.formal_synthetic_identity_id IS NOT NULL THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION
            'New Demo local synthetic identity events must use v3 authority';
    ELSIF TG_TABLE_NAME = 'demo_pair_screening_reports' THEN
        IF NEW.schema_version <> 'mirror.demo/D02PairScreeningReport/v2' THEN
            RAISE EXCEPTION 'New D02 screening reports must use v2 authority';
        END IF;
        RETURN NEW;
    ELSIF TG_TABLE_NAME = 'demo_question_banks' THEN
        IF NEW.schema_version <> 'mirror.demo/DemoQuestionBank/v2' THEN
            RAISE EXCEPTION 'New Demo question banks must use v2 authority';
        END IF;
        SELECT schema_version INTO report_schema
        FROM demo_pair_screening_reports
        WHERE id = NEW.screening_report_id
          AND report_digest = NEW.screening_report_digest;
        IF report_schema IS DISTINCT FROM
            'mirror.demo/D02PairScreeningReport/v2' THEN
            RAISE EXCEPTION
                'D02 v10 question bank must bind one Report v2 authority';
        END IF;
        RETURN NEW;
    ELSIF TG_TABLE_NAME = 'demo_question_pairs' THEN
        IF NEW.schema_version <> 'mirror.demo/DemoQuestionPair/v2' THEN
            RAISE EXCEPTION 'New Demo question pairs must use v2 authority';
        END IF;
        SELECT schema_version INTO report_schema
        FROM demo_pair_screening_reports
        WHERE id = NEW.screening_report_id
          AND report_digest = NEW.screening_report_digest;
        SELECT schema_version INTO identity_schema
        FROM demo_synthetic_identities
        WHERE id = NEW.demo_synthetic_identity_id;
        IF report_schema IS DISTINCT FROM
                'mirror.demo/D02PairScreeningReport/v2'
            OR identity_schema IS DISTINCT FROM
                'mirror.demo/DemoSyntheticIdentity/v3' THEN
            RAISE EXCEPTION
                'D02 v10 pair requires Report v2 and Identity v3 authority';
        END IF;
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'D02 v10 write-version guard attached to unknown table';
END;
$function$;
"""


_V3_SOURCE_MODE_NULL_MATRIX_CHECK = (
    "(source_authority_kind = 'FORMAL_REFERENCE' "
    "AND schema_version <> 'mirror.demo/DemoSyntheticIdentity/v3' "
    "AND formal_synthetic_identity_id IS NOT NULL "
    "AND formal_accepted_qa_run_id IS NOT NULL "
    "AND formal_accepted_qa_snapshot_digest IS NOT NULL "
    "AND source_output_id IS NULL AND source_receipt_digest IS NULL "
    "AND source_authority_digest IS NULL AND source_qa_snapshot_digest IS NULL "
    "AND source_landmark_digest IS NULL AND source_measurement_digest IS NULL "
    "AND source_provenance_digest IS NULL AND source_fact_snapshot IS NULL "
    "AND source_fact_snapshot_digest IS NULL "
    "AND source_measurement_projection IS NULL "
    "AND source_measurement_projection_digest IS NULL "
    "AND original_formal_identity_id_status IS NULL "
    "AND adult_synthetic_attested IS NULL AND importer_version IS NULL "
    "AND import_config_digest IS NULL) OR "
    "(source_authority_kind = 'DEMO_LOCAL_IMPORTED_COPY' "
    "AND formal_synthetic_identity_id IS NULL "
    "AND formal_accepted_qa_run_id IS NULL "
    "AND formal_accepted_qa_snapshot_digest IS NULL "
    "AND source_output_id IS NOT NULL AND source_receipt_digest IS NOT NULL "
    "AND source_authority_digest IS NOT NULL "
    "AND source_qa_snapshot_digest IS NOT NULL "
    "AND source_landmark_digest IS NOT NULL "
    "AND source_measurement_digest IS NOT NULL "
    "AND source_provenance_digest IS NOT NULL "
    "AND source_fact_snapshot IS NOT NULL "
    "AND source_fact_snapshot_digest IS NOT NULL "
    "AND source_measurement_projection IS NOT NULL "
    "AND source_measurement_projection_digest IS NOT NULL "
    "AND original_formal_identity_id_status = "
    "'UNKNOWN_REDACTED_NOT_RECOVERED' "
    "AND adult_synthetic_attested IS TRUE "
    "AND ((schema_version = 'mirror.demo/DemoSyntheticIdentity/v2' "
    "AND importer_version = 'demo-d02-identity-importer-v2') OR "
    "(schema_version = 'mirror.demo/DemoSyntheticIdentity/v3' "
    "AND importer_version = 'demo-d02-identity-importer-v3')) "
    "AND import_config_digest IS NOT NULL)"
)


def _create_supporting_table() -> None:
    op.create_table(
        "demo_d02_r2_source_authorities",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("schema_version", sa.String(length=112), nullable=False),
        sa.Column("canonical_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("execution_contract_digest", sa.String(length=64), nullable=False),
        sa.Column("evidence_root_id", sa.String(length=128), nullable=False),
        sa.Column("root_name_receipt_digest", sa.String(length=64), nullable=False),
        sa.Column("generation_preregistration_digest", sa.String(length=64), nullable=False),
        sa.Column("source_allocation_manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("source_producer_dispatch_digest", sa.String(length=64), nullable=False),
        sa.Column("source_ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("source_output_id", sa.String(length=128), nullable=False),
        sa.Column("source_asset_id", sa.String(length=32), nullable=False),
        sa.Column("source_asset_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_asset_byte_size", sa.BigInteger(), nullable=False),
        sa.Column("source_asset_mime_type", sa.String(length=64), nullable=False),
        sa.Column("source_asset_width", sa.Integer(), nullable=False),
        sa.Column("source_asset_height", sa.Integer(), nullable=False),
        sa.Column("source_generation_receipt_digest", sa.String(length=64), nullable=False),
        sa.Column("output_name_receipt_digest", sa.String(length=64), nullable=False),
        sa.Column("output_seal_receipt_digest", sa.String(length=64), nullable=False),
        sa.Column("registry_commit_receipt_digest", sa.String(length=64), nullable=False),
        sa.Column("generation_capability_authority_digest", sa.String(length=64), nullable=False),
        sa.Column("generation_request_policy_digest", sa.String(length=64), nullable=False),
        sa.Column("source_provenance_digest", sa.String(length=64), nullable=False),
        sa.Column("source_provenance_output_id", sa.String(length=128), nullable=False),
        sa.Column("source_provenance_name_receipt_digest", sa.String(length=64), nullable=False),
        sa.Column("source_provenance_seal_receipt_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "source_provenance_registry_commit_receipt_digest", sa.String(length=64), nullable=False
        ),
        sa.Column("source_authority_digest", sa.String(length=64), nullable=False),
        sa.Column("source_authority_key", sa.String(length=64), nullable=False),
        sa.Column("source_qa_snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("adult_synthetic_attested", sa.Boolean(), nullable=False),
        sa.Column("synthetic_only_attested", sa.Boolean(), nullable=False),
        sa.Column("real_person_reference_used", sa.Boolean(), nullable=False),
        sa.Column("authority_state", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_asset_id"],
            ["assets.id"],
            ondelete="RESTRICT",
            name=op.f("fk_demo_d02_r2_source_authorities_source_asset_id_assets"),
        ),
        sa.UniqueConstraint(
            "content_digest", name=op.f("uq_demo_d02_r2_source_authorities_content_digest")
        ),
        sa.UniqueConstraint(
            "execution_contract_digest",
            "source_ordinal",
            name="execution_ordinal",
        ),
        *[
            sa.UniqueConstraint(column, name=_UNIQUE_CONSTRAINT_NAMES[column])
            for column in (
                "source_output_id",
                "source_generation_receipt_digest",
                "output_name_receipt_digest",
                "output_seal_receipt_digest",
                "registry_commit_receipt_digest",
                "source_provenance_output_id",
                "source_provenance_name_receipt_digest",
                "source_provenance_seal_receipt_digest",
                "source_provenance_registry_commit_receipt_digest",
                "source_authority_digest",
                "source_authority_key",
                "source_qa_snapshot_digest",
            )
        ],
        sa.CheckConstraint("id ~ '^[0-9a-f]{32}$'", name="id_shape"),
        sa.CheckConstraint(
            "schema_version = 'mirror.demo/D02R2SourceAuthorityRecord/v1'",
            name="schema_version_shape",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(canonical_payload) = 'object'", name="canonical_payload_object"
        ),
        sa.CheckConstraint("content_digest ~ '^[0-9a-f]{64}$'", name="content_digest_shape"),
        sa.CheckConstraint(
            " AND ".join(f"{column} ~ '^[0-9a-f]{{64}}$'" for column in _DIGEST_COLUMNS),
            name=op.f("ck_demo_d02_r2_source_authorities_digest_shapes"),
        ),
        sa.CheckConstraint("source_ordinal BETWEEN 1 AND 4", name="source_ordinal"),
        sa.CheckConstraint("source_asset_byte_size > 0", name="positive_asset_byte_size"),
        sa.CheckConstraint(
            "source_asset_width > 0 AND source_asset_height > 0", name="positive_dimensions"
        ),
        sa.CheckConstraint("source_asset_mime_type = 'image/jpeg'", name="decoded_mime"),
        sa.CheckConstraint(
            "evidence_root_id = 'P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT'", name="evidence_root"
        ),
        sa.CheckConstraint(
            "source_output_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$' AND "
            "source_provenance_output_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'",
            name=op.f("ck_demo_d02_r2_source_authorities_opaque_output_ids"),
        ),
        sa.CheckConstraint(
            "adult_synthetic_attested IS TRUE AND synthetic_only_attested IS TRUE "
            "AND real_person_reference_used IS FALSE",
            name="fixed_attestations",
        ),
        sa.CheckConstraint("authority_state = 'PRINCIPAL_ACCEPTED'", name="authority_state"),
    )
    op.create_index(
        op.f("ix_demo_d02_r2_source_authorities_source_asset_id"),
        "demo_d02_r2_source_authorities",
        ["source_asset_id"],
        unique=False,
    )


def _replace_identity_shape_constraints() -> None:
    table = "demo_synthetic_identities"
    for name in ("schema_version_shape", "source_authority_kind", "source_mode_null_matrix"):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS ck_{table}_{name}")
    op.create_check_constraint(
        op.f(f"ck_{table}_schema_version_shape"),
        table,
        "schema_version IN ('mirror.demo/DemoSyntheticIdentity/v1',"
        "'mirror.demo/DemoSyntheticIdentity/v2','mirror.demo/DemoSyntheticIdentity/v3',"
        "'mirror.demo/DemoSyntheticIdentity/v4')",
    )
    op.create_check_constraint(
        op.f(f"ck_{table}_source_authority_kind"),
        table,
        "source_authority_kind IN ('FORMAL_REFERENCE','DEMO_LOCAL_IMPORTED_COPY',"
        "'DEMO_R2_GENERATED_SOURCE')",
    )
    op.create_check_constraint(
        op.f(f"ck_{table}_source_mode_null_matrix"),
        table,
        "(schema_version = 'mirror.demo/DemoSyntheticIdentity/v4' "
        "AND source_authority_kind = 'DEMO_R2_GENERATED_SOURCE' "
        "AND r2_source_authority_record_id IS NOT NULL "
        "AND formal_synthetic_identity_id IS NULL AND formal_accepted_qa_run_id IS NULL "
        "AND formal_accepted_qa_snapshot_digest IS NULL AND source_output_id IS NOT NULL "
        "AND source_receipt_digest IS NOT NULL AND source_authority_digest IS NOT NULL "
        "AND source_qa_snapshot_digest IS NOT NULL AND source_landmark_digest IS NOT NULL "
        "AND source_measurement_digest IS NOT NULL AND source_provenance_digest IS NOT NULL "
        "AND source_fact_snapshot IS NOT NULL AND source_fact_snapshot_digest IS NOT NULL "
        "AND source_measurement_projection IS NOT NULL "
        "AND source_measurement_projection_digest IS NOT NULL "
        "AND original_formal_identity_id_status = 'NOT_APPLICABLE_DEMO_R2_GENERATED_SOURCE' "
        "AND adult_synthetic_attested IS TRUE "
        "AND importer_version = 'demo-d02-r2-identity-importer-v1' "
        "AND import_config_digest IS NOT NULL) OR "
        "(schema_version <> 'mirror.demo/DemoSyntheticIdentity/v4' "
        "AND r2_source_authority_record_id IS NULL AND ("
        "(source_authority_kind = 'FORMAL_REFERENCE' "
        "AND schema_version <> 'mirror.demo/DemoSyntheticIdentity/v3' "
        "AND formal_synthetic_identity_id IS NOT NULL "
        "AND formal_accepted_qa_run_id IS NOT NULL "
        "AND formal_accepted_qa_snapshot_digest IS NOT NULL "
        "AND source_output_id IS NULL AND source_receipt_digest IS NULL "
        "AND source_authority_digest IS NULL AND source_qa_snapshot_digest IS NULL "
        "AND source_landmark_digest IS NULL AND source_measurement_digest IS NULL "
        "AND source_provenance_digest IS NULL AND source_fact_snapshot IS NULL "
        "AND source_fact_snapshot_digest IS NULL AND source_measurement_projection IS NULL "
        "AND source_measurement_projection_digest IS NULL "
        "AND original_formal_identity_id_status IS NULL "
        "AND adult_synthetic_attested IS NULL AND importer_version IS NULL "
        "AND import_config_digest IS NULL) OR "
        "(source_authority_kind = 'DEMO_LOCAL_IMPORTED_COPY' "
        "AND formal_synthetic_identity_id IS NULL AND formal_accepted_qa_run_id IS NULL "
        "AND formal_accepted_qa_snapshot_digest IS NULL AND source_output_id IS NOT NULL "
        "AND source_receipt_digest IS NOT NULL AND source_authority_digest IS NOT NULL "
        "AND source_qa_snapshot_digest IS NOT NULL AND source_landmark_digest IS NOT NULL "
        "AND source_measurement_digest IS NOT NULL AND source_provenance_digest IS NOT NULL "
        "AND source_fact_snapshot IS NOT NULL AND source_fact_snapshot_digest IS NOT NULL "
        "AND source_measurement_projection IS NOT NULL "
        "AND source_measurement_projection_digest IS NOT NULL "
        "AND original_formal_identity_id_status = 'UNKNOWN_REDACTED_NOT_RECOVERED' "
        "AND adult_synthetic_attested IS TRUE "
        "AND ((schema_version = 'mirror.demo/DemoSyntheticIdentity/v2' "
        "AND importer_version = 'demo-d02-identity-importer-v2') OR "
        "(schema_version = 'mirror.demo/DemoSyntheticIdentity/v3' "
        "AND importer_version = 'demo-d02-identity-importer-v3')) "
        "AND import_config_digest IS NOT NULL)))",
    )


def _replace_identity_generated_columns(*, r2: bool) -> None:
    """Rebuild only generated projections; v1-v3 expressions stay unchanged."""
    table = "demo_synthetic_identities"
    for name in ("source_authority_kind", "source_mode_null_matrix"):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS ck_{table}_{name}")
    op.drop_constraint(op.f("uq_demo_synthetic_identities_source_sequence"), table, type_="unique")
    op.drop_constraint(
        op.f("ck_demo_synthetic_identities_source_authority_key_shape"), table, type_="check"
    )
    op.drop_column(table, "source_authority_key")
    op.drop_column(table, "source_authority_kind")
    if r2:
        kind_expression = (
            "CASE WHEN formal_synthetic_identity_id IS NOT NULL THEN 'FORMAL_REFERENCE' "
            "WHEN r2_source_authority_record_id IS NOT NULL THEN 'DEMO_R2_GENERATED_SOURCE' "
            "ELSE 'DEMO_LOCAL_IMPORTED_COPY' END"
        )
        key_expression = (
            "CASE WHEN formal_synthetic_identity_id IS NOT NULL "
            "THEN mirror_demo_formal_source_authority_key(formal_synthetic_identity_id) "
            "WHEN r2_source_authority_record_id IS NOT NULL "
            "THEN mirror_demo_r2_source_authority_key(source_output_id, formal_canonical_asset_id, "
            "formal_canonical_asset_sha256, source_receipt_digest, source_authority_digest) "
            "ELSE mirror_demo_local_source_authority_key(source_output_id, formal_canonical_asset_id, "
            "formal_canonical_asset_sha256, source_receipt_digest) END"
        )
    else:
        kind_expression = (
            "CASE WHEN formal_synthetic_identity_id IS NOT NULL THEN 'FORMAL_REFERENCE' "
            "ELSE 'DEMO_LOCAL_IMPORTED_COPY' END"
        )
        key_expression = (
            "CASE WHEN formal_synthetic_identity_id IS NOT NULL "
            "THEN mirror_demo_formal_source_authority_key(formal_synthetic_identity_id) "
            "ELSE mirror_demo_local_source_authority_key(source_output_id, formal_canonical_asset_id, "
            "formal_canonical_asset_sha256, source_receipt_digest) END"
        )
    op.add_column(
        table,
        sa.Column(
            "source_authority_kind",
            sa.String(length=32),
            sa.Computed(kind_expression, persisted=True),
            nullable=False,
        ),
    )
    op.add_column(
        table,
        sa.Column(
            "source_authority_key",
            sa.String(length=64),
            sa.Computed(key_expression, persisted=True),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        op.f("uq_demo_synthetic_identities_source_sequence"),
        table,
        ["source_authority_key", "admission_sequence"],
    )
    op.create_check_constraint(
        op.f("ck_demo_synthetic_identities_source_authority_key_shape"),
        table,
        "source_authority_key ~ '^[0-9a-f]{64}$'",
    )


def _create_legacy_qa_constraint() -> None:
    op.execute(
        "ALTER TABLE demo_synthetic_identities DROP CONSTRAINT IF EXISTS "
        "ck_demo_synthetic_identities_d02_local_qa_digest_separation"
    )
    op.create_check_constraint(
        op.f("ck_demo_synthetic_identities_d02_local_qa_digest_separation"),
        "demo_synthetic_identities",
        _LOCAL_QA_CHECK,
    )


def _restore_v3_identity_constraints() -> None:
    """Restore the demo_0007 identity constraints after all R2 columns are gone."""
    table = "demo_synthetic_identities"
    op.create_check_constraint(
        op.f(f"ck_{table}_schema_version_shape"),
        table,
        "schema_version IN ('mirror.demo/DemoSyntheticIdentity/v1',"
        "'mirror.demo/DemoSyntheticIdentity/v2',"
        "'mirror.demo/DemoSyntheticIdentity/v3')",
    )
    op.create_check_constraint(
        op.f(f"ck_{table}_source_authority_kind"),
        table,
        "source_authority_kind IN ('FORMAL_REFERENCE','DEMO_LOCAL_IMPORTED_COPY')",
    )
    op.create_check_constraint(
        op.f(f"ck_{table}_source_mode_null_matrix"),
        table,
        _V3_SOURCE_MODE_NULL_MATRIX_CHECK,
    )
    _create_legacy_qa_constraint()


def _set_v10_identity_validator_r2_projection(*, include_r2_column: bool) -> None:
    old_fragment = "'source_authority_kind','source_authority_key'"
    new_fragment = "'source_authority_kind','source_authority_key','r2_source_authority_record_id'"
    source_fragment, target_fragment = (
        (old_fragment, new_fragment) if include_r2_column else (new_fragment, old_fragment)
    )
    op.execute(
        f"""
DO $block$
DECLARE
    function_sql text;
BEGIN
    SELECT pg_get_functiondef(
        'mirror_demo_validate_d02_synthetic_identity_v10()'::regprocedure
    ) INTO function_sql;
    IF position($source${source_fragment}$source$ IN function_sql) = 0 THEN
        RAISE EXCEPTION 'D02 v10 identity validator projection baseline is invalid';
    END IF;
    function_sql := replace(
        function_sql,
        $source${source_fragment}$source$,
        $target${target_fragment}$target$
    );
    EXECUTE function_sql;
END $block$;
"""
    )


_R2_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_r2_source_authority_key(
    source_output_id text, source_asset_id text, source_asset_sha256 text,
    source_generation_receipt_digest text, source_authority_digest text
) RETURNS text LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $function$
    SELECT mirror_demo_digest('mirror.demo/D02R2SourceAuthorityKey/v1', jsonb_build_object(
        'authority_kind', 'DEMO_R2_GENERATED_SOURCE',
        'source_output_id', source_output_id, 'source_asset_id', source_asset_id,
        'source_asset_sha256', source_asset_sha256,
        'source_generation_receipt_digest', source_generation_receipt_digest,
        'authority_digest', source_authority_digest));
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_write_version_v10()
RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE report_schema text; identity_schema text;
BEGIN
    IF TG_TABLE_NAME = 'demo_synthetic_identities' THEN
        IF NEW.schema_version = 'mirror.demo/DemoSyntheticIdentity/v4' THEN RETURN NEW; END IF;
        IF NEW.schema_version = 'mirror.demo/DemoSyntheticIdentity/v3'
           AND NEW.formal_synthetic_identity_id IS NULL THEN RETURN NEW; END IF;
        IF NEW.schema_version = 'mirror.demo/DemoSyntheticIdentity/v2'
           AND NEW.formal_synthetic_identity_id IS NOT NULL THEN RETURN NEW; END IF;
        RAISE EXCEPTION 'New Demo local synthetic identity events must use v3 authority';
    ELSIF TG_TABLE_NAME = 'demo_pair_screening_reports' THEN
        IF NEW.schema_version = 'mirror.demo/D02PairScreeningReport/v3' THEN
            IF NEW.measurement_gate_count IS DISTINCT FROM 48
               OR NEW.decode_structure_record_count IS DISTINCT FROM 48 THEN
                RAISE EXCEPTION 'D02 R2 Report v3 counts are invalid';
            END IF;
            RETURN NEW;
        END IF;
        IF NEW.schema_version = 'mirror.demo/D02PairScreeningReport/v2' THEN RETURN NEW; END IF;
        RAISE EXCEPTION 'New D02 screening reports must use v2 authority';
    ELSIF TG_TABLE_NAME = 'demo_question_banks' THEN
        IF NEW.schema_version NOT IN ('mirror.demo/DemoQuestionBank/v2','mirror.demo/DemoQuestionBank/v3') THEN RAISE EXCEPTION 'New Demo question banks must use v2 authority'; END IF;
        SELECT schema_version INTO report_schema FROM demo_pair_screening_reports WHERE id = NEW.screening_report_id AND report_digest = NEW.screening_report_digest;
        IF report_schema IS DISTINCT FROM (CASE WHEN NEW.schema_version = 'mirror.demo/DemoQuestionBank/v3' THEN 'mirror.demo/D02PairScreeningReport/v3' ELSE 'mirror.demo/D02PairScreeningReport/v2' END) THEN RAISE EXCEPTION 'D02 v10 question bank must bind matching Report authority'; END IF;
        RETURN NEW;
    ELSIF TG_TABLE_NAME = 'demo_question_pairs' THEN
        IF NEW.schema_version NOT IN ('mirror.demo/DemoQuestionPair/v2','mirror.demo/DemoQuestionPair/v3') THEN RAISE EXCEPTION 'New Demo question pairs must use v2 authority'; END IF;
        SELECT schema_version INTO report_schema FROM demo_pair_screening_reports WHERE id = NEW.screening_report_id AND report_digest = NEW.screening_report_digest;
        SELECT schema_version INTO identity_schema FROM demo_synthetic_identities WHERE id = NEW.demo_synthetic_identity_id;
        IF report_schema IS DISTINCT FROM (CASE WHEN NEW.schema_version = 'mirror.demo/DemoQuestionPair/v3' THEN 'mirror.demo/D02PairScreeningReport/v3' ELSE 'mirror.demo/D02PairScreeningReport/v2' END)
           OR identity_schema IS DISTINCT FROM (CASE WHEN NEW.schema_version = 'mirror.demo/DemoQuestionPair/v3' THEN 'mirror.demo/DemoSyntheticIdentity/v4' ELSE 'mirror.demo/DemoSyntheticIdentity/v3' END) THEN RAISE EXCEPTION 'D02 v10 pair requires matching Report and Identity authority'; END IF;
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'D02 v10 write-version guard attached to unknown table';
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_guard_authority()
RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE
    expected_payload jsonb;
    expected_digest text;
    close_changed boolean := false;
    tombstone_changed boolean := false;
    derived_kind text;
    derived_key text;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Demo authority row is append-only: %', TG_TABLE_NAME;
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF TG_TABLE_NAME NOT IN ('demo_actors','demo_sessions','demo_editing_sessions') THEN
            RAISE EXCEPTION 'Demo authority row is immutable: %', TG_TABLE_NAME;
        END IF;
        IF TG_TABLE_NAME = 'demo_actors' THEN
            IF OLD.tombstoned_at IS NOT NULL OR NEW.tombstoned_at IS NULL
               OR (to_jsonb(NEW) - 'tombstoned_at') IS DISTINCT FROM
                  (to_jsonb(OLD) - 'tombstoned_at') THEN
                RAISE EXCEPTION 'Invalid Demo actor tombstone transition';
            END IF;
        ELSE
            close_changed := OLD.closed_at IS NULL AND NEW.closed_at IS NOT NULL;
            tombstone_changed := OLD.tombstoned_at IS NULL AND NEW.tombstoned_at IS NOT NULL;
            IF NOT (close_changed OR tombstone_changed)
               OR (tombstone_changed AND OLD.closed_at IS NULL)
               OR (OLD.closed_at IS NOT NULL AND NEW.closed_at IS DISTINCT FROM OLD.closed_at)
               OR (OLD.tombstoned_at IS NOT NULL AND NEW.tombstoned_at IS DISTINCT FROM OLD.tombstoned_at)
               OR (to_jsonb(NEW) - ARRAY['closed_at','tombstoned_at']::text[]) IS DISTINCT FROM
                  (to_jsonb(OLD) - ARRAY['closed_at','tombstoned_at']::text[]) THEN
                RAISE EXCEPTION 'Invalid Demo terminal header transition: %', TG_TABLE_NAME;
            END IF;
        END IF;
    ELSIF TG_TABLE_NAME = 'demo_actors' THEN
        IF NEW.tombstoned_at IS NOT NULL THEN
            RAISE EXCEPTION 'Demo actor must be created active';
        END IF;
    ELSIF TG_TABLE_NAME IN ('demo_sessions','demo_editing_sessions') THEN
        IF NEW.closed_at IS NOT NULL OR NEW.tombstoned_at IS NOT NULL THEN
            RAISE EXCEPTION 'Demo session header must be created open';
        END IF;
    END IF;
    IF jsonb_typeof(NEW.canonical_payload) IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION 'Demo canonical payload must be a JSON object';
    END IF;
    IF TG_TABLE_NAME = 'demo_synthetic_identities'
       AND NEW.schema_version IN ('mirror.demo/DemoSyntheticIdentity/v2',
                                  'mirror.demo/DemoSyntheticIdentity/v3') THEN
        derived_kind := CASE
            WHEN NEW.formal_synthetic_identity_id IS NOT NULL THEN 'FORMAL_REFERENCE'
            ELSE 'DEMO_LOCAL_IMPORTED_COPY'
        END;
        derived_key := CASE derived_kind
            WHEN 'FORMAL_REFERENCE' THEN mirror_demo_formal_source_authority_key(
                NEW.formal_synthetic_identity_id
            )
            ELSE mirror_demo_local_source_authority_key(
                NEW.source_output_id,
                NEW.formal_canonical_asset_id,
                NEW.formal_canonical_asset_sha256,
                NEW.source_receipt_digest
            )
        END;
        expected_payload := mirror_demo_authority_projection(
            to_jsonb(NEW) || jsonb_build_object(
                'source_authority_kind', derived_kind,
                'source_authority_key', derived_key
            ),
            TG_TABLE_NAME
        );
    ELSIF TG_TABLE_NAME = 'demo_synthetic_identities'
       AND NEW.schema_version = 'mirror.demo/DemoSyntheticIdentity/v4' THEN
        expected_payload := mirror_demo_authority_projection(
            to_jsonb(NEW) || jsonb_build_object(
                'source_authority_kind', 'DEMO_R2_GENERATED_SOURCE',
                'source_authority_key', mirror_demo_r2_source_authority_key(
                    NEW.source_output_id,
                    NEW.formal_canonical_asset_id,
                    NEW.formal_canonical_asset_sha256,
                    NEW.source_receipt_digest,
                    NEW.source_authority_digest
                )
            ),
            TG_TABLE_NAME
        );
    ELSE
        expected_payload := mirror_demo_authority_projection(to_jsonb(NEW), TG_TABLE_NAME);
    IF TG_TABLE_NAME = 'demo_synthetic_identities'
       AND NEW.schema_version = 'mirror.demo/DemoSyntheticIdentity/v1' THEN
            expected_payload := expected_payload - 'r2_source_authority_record_id';
        END IF;
        IF TG_TABLE_NAME = 'demo_pair_screening_reports'
           AND to_jsonb(NEW) ->> 'status' = 'FAILED' THEN
            expected_payload := expected_payload - 'selected_pair_manifest_digest';
        END IF;
        IF TG_TABLE_NAME = 'demo_pair_screening_reports'
           AND NEW.schema_version IN (
               'mirror.demo/D02PairScreeningReport/v1',
               'mirror.demo/D02PairScreeningReport/v2'
           ) THEN
            expected_payload := expected_payload - ARRAY[
                'measurement_gate_count',
                'decode_structure_record_count'
            ]::text[];
        END IF;
    END IF;
    IF TG_TABLE_NAME = 'demo_synthetic_identities'
       AND NEW.schema_version IN (
           'mirror.demo/DemoSyntheticIdentity/v2',
           'mirror.demo/DemoSyntheticIdentity/v3'
       ) THEN
        expected_payload := expected_payload - 'r2_source_authority_record_id';
    END IF;
    IF NEW.canonical_payload IS DISTINCT FROM expected_payload THEN
        RAISE EXCEPTION 'Demo canonical payload disagrees with structured authority: %', TG_TABLE_NAME;
    END IF;
    expected_digest := mirror_demo_digest(NEW.schema_version, NEW.canonical_payload);
    IF NEW.content_digest IS DISTINCT FROM expected_digest THEN
        RAISE EXCEPTION 'Demo canonical digest mismatch: %', TG_TABLE_NAME;
    END IF;
    RETURN NEW;
END;
$function$;

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

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_r2_identity()
RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE
    source_row demo_d02_r2_source_authorities%ROWTYPE;
    previous_admission demo_synthetic_identities%ROWTYPE;
    expected_payload jsonb;
    expected_key text;
    has_previous boolean;
BEGIN
    IF NEW.schema_version IS DISTINCT FROM 'mirror.demo/DemoSyntheticIdentity/v4' THEN
        RETURN NEW;
    END IF;
    IF NEW.admission_config_digest IS DISTINCT FROM
           '08dd11a4161286bef11b5a64928f4c5f1447ed54d326dbc47c6b5a52905ed021'
       OR NEW.import_config_digest IS DISTINCT FROM
           '08dd11a4161286bef11b5a64928f4c5f1447ed54d326dbc47c6b5a52905ed021' THEN
        RAISE EXCEPTION 'D02 R2 identity admission config is invalid';
    END IF;
    SELECT * INTO source_row FROM demo_d02_r2_source_authorities
      WHERE id = NEW.r2_source_authority_record_id;
    expected_key := mirror_demo_r2_source_authority_key(
        NEW.source_output_id, NEW.formal_canonical_asset_id,
        NEW.formal_canonical_asset_sha256, NEW.source_receipt_digest,
        NEW.source_authority_digest
    );
    IF NOT FOUND OR NEW.source_output_id IS DISTINCT FROM source_row.source_output_id
       OR NEW.formal_canonical_asset_id IS DISTINCT FROM source_row.source_asset_id
       OR NEW.formal_canonical_asset_sha256 IS DISTINCT FROM source_row.source_asset_sha256
       OR NEW.source_receipt_digest IS DISTINCT FROM source_row.source_generation_receipt_digest
       OR NEW.source_authority_digest IS DISTINCT FROM source_row.source_authority_digest
       OR NEW.source_qa_snapshot_digest IS DISTINCT FROM source_row.source_qa_snapshot_digest
       OR NEW.source_provenance_digest IS DISTINCT FROM source_row.source_provenance_digest
       OR NEW.adult_synthetic_attested IS DISTINCT FROM source_row.adult_synthetic_attested
       OR expected_key IS DISTINCT FROM source_row.source_authority_key THEN
        RAISE EXCEPTION 'D02 R2 identity/source supporting-row equality is invalid';
    END IF;
    PERFORM pg_advisory_xact_lock(
        hashtextextended('mirror.demo.synthetic-admission-v2/' || expected_key, 0)
    );
    SELECT * INTO previous_admission
    FROM demo_synthetic_identities
    WHERE source_authority_key = expected_key
    ORDER BY admission_sequence DESC, id DESC
    LIMIT 1
    FOR UPDATE;
    has_previous := FOUND;
    IF NOT has_previous THEN
        IF NEW.admission_sequence IS DISTINCT FROM 1
           OR NEW.admission_action IS DISTINCT FROM 'ADMIT'
           OR NEW.supersedes_id IS NOT NULL THEN
            RAISE EXCEPTION 'First D02 R2 source event must be ADMIT';
        END IF;
    ELSIF previous_admission.schema_version IS DISTINCT FROM
              'mirror.demo/DemoSyntheticIdentity/v4'
       OR previous_admission.source_authority_kind IS DISTINCT FROM
              'DEMO_R2_GENERATED_SOURCE'
       OR NEW.admission_sequence IS DISTINCT FROM previous_admission.admission_sequence + 1
       OR NEW.supersedes_id IS DISTINCT FROM previous_admission.id
       OR NEW.admission_action IS NOT DISTINCT FROM previous_admission.admission_action THEN
        RAISE EXCEPTION 'D02 R2 source admission chain is invalid or mixed-version';
    END IF;
    IF has_previous AND (
        NEW.r2_source_authority_record_id IS DISTINCT FROM
            previous_admission.r2_source_authority_record_id
        OR NEW.formal_canonical_asset_id IS DISTINCT FROM
            previous_admission.formal_canonical_asset_id
        OR NEW.formal_canonical_asset_sha256 IS DISTINCT FROM
            previous_admission.formal_canonical_asset_sha256
        OR NEW.source_output_id IS DISTINCT FROM previous_admission.source_output_id
        OR NEW.source_receipt_digest IS DISTINCT FROM previous_admission.source_receipt_digest
        OR NEW.source_authority_digest IS DISTINCT FROM
            previous_admission.source_authority_digest
        OR NEW.source_qa_snapshot_digest IS DISTINCT FROM
            previous_admission.source_qa_snapshot_digest
        OR NEW.source_landmark_digest IS DISTINCT FROM
            previous_admission.source_landmark_digest
        OR NEW.source_measurement_digest IS DISTINCT FROM
            previous_admission.source_measurement_digest
        OR NEW.source_provenance_digest IS DISTINCT FROM
            previous_admission.source_provenance_digest
        OR NEW.source_fact_snapshot IS DISTINCT FROM previous_admission.source_fact_snapshot
        OR NEW.source_fact_snapshot_digest IS DISTINCT FROM
            previous_admission.source_fact_snapshot_digest
        OR NEW.source_measurement_projection IS DISTINCT FROM
            previous_admission.source_measurement_projection
        OR NEW.source_measurement_projection_digest IS DISTINCT FROM
            previous_admission.source_measurement_projection_digest
        OR NEW.original_formal_identity_id_status IS DISTINCT FROM
            previous_admission.original_formal_identity_id_status
        OR NEW.adult_synthetic_attested IS DISTINCT FROM
            previous_admission.adult_synthetic_attested
        OR NEW.importer_version IS DISTINCT FROM previous_admission.importer_version
        OR NEW.import_config_digest IS DISTINCT FROM previous_admission.import_config_digest
        OR NEW.admission_config_digest IS DISTINCT FROM
            previous_admission.admission_config_digest
    ) THEN
        RAISE EXCEPTION 'D02 R2 ADMIT/REVOKE evidence copy differs';
    END IF;
    expected_payload := mirror_demo_authority_projection(
        to_jsonb(NEW) || jsonb_build_object(
            'source_authority_kind', 'DEMO_R2_GENERATED_SOURCE',
            'source_authority_key', expected_key
        ),
        TG_TABLE_NAME
    );
    IF NEW.canonical_payload IS DISTINCT FROM expected_payload
       OR NEW.content_digest IS DISTINCT FROM mirror_demo_digest(NEW.schema_version, expected_payload)
       OR NEW.id IS DISTINCT FROM substring(mirror_demo_digest(
          'mirror.demo/DemoSyntheticIdentityAdmissionEventId/v3',
           jsonb_build_object('source_authority_kind', 'DEMO_R2_GENERATED_SOURCE',
             'source_authority_key', expected_key,
             'r2_source_authority_record_id', NEW.r2_source_authority_record_id,
             'admission_sequence', NEW.admission_sequence, 'admission_action', NEW.admission_action,
             'supersedes_id', NEW.supersedes_id, 'admission_config_digest', NEW.admission_config_digest,
             'canonical_payload_digest', NEW.content_digest)) FROM 1 FOR 32) THEN
        RAISE EXCEPTION 'D02 R2 identity canonical authority is invalid';
    END IF;
    RETURN NEW;
END;
$function$;

"""


_R2_V3_AUTHORITY_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_d02_r2_require_mandatory_digest_leaves(
    record_value jsonb,
    mandatory_keys text[],
    record_label text
)
RETURNS void
LANGUAGE plpgsql
IMMUTABLE
PARALLEL SAFE
AS $function$
DECLARE
    digest_key text;
BEGIN
    IF jsonb_typeof(record_value) IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION 'D02 R2 % mandatory digest leaf container is invalid', record_label;
    END IF;

    FOREACH digest_key IN ARRAY mandatory_keys
    LOOP
        IF (record_value ? digest_key) IS NOT TRUE
           OR jsonb_typeof(record_value -> digest_key) IS DISTINCT FROM 'string'
           OR mirror_demo_d02_json_string_matches(
                  record_value -> digest_key, '^[0-9a-f]{64}$'
              ) IS NOT TRUE THEN
            RAISE EXCEPTION 'D02 R2 % mandatory digest leaf is invalid: %',
                record_label, digest_key;
        END IF;
    END LOOP;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_d02_r2_require_record(
    record_value jsonb,
    expected_schema text,
    expected_keys text[],
    digest_key text DEFAULT 'record_digest'
)
RETURNS void
LANGUAGE plpgsql
IMMUTABLE
PARALLEL SAFE
AS $function$
BEGIN
    IF jsonb_typeof(record_value) IS DISTINCT FROM 'object'
       OR mirror_demo_jsonb_exact_keys(record_value, expected_keys) IS NOT TRUE
       OR jsonb_typeof(record_value -> digest_key) IS DISTINCT FROM 'string'
       OR mirror_demo_d02_record_digest_matches(
              record_value, expected_schema, digest_key
          ) IS NOT TRUE THEN
        RAISE EXCEPTION 'D02 R2 record shape or digest mismatch: %', expected_schema;
    END IF;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_r2_source_m3_v3(
    source_record jsonb,
    source_entry jsonb,
    source_manifest_digest text
)
RETURNS void
LANGUAGE plpgsql
STRICT
AS $function$
DECLARE
    shadow_record jsonb;
    expected_id text;
    shadow_id text;
BEGIN
    PERFORM mirror_demo_d02_r2_require_mandatory_digest_leaves(
        source_record,
        ARRAY[
            'source_authority_key','source_authority_digest','source_asset_sha256',
            'execution_receipt_digest','vision_model_manifest_digest',
            'runtime_manifest_digest','topology_digest','canonical_output_digest',
            'landmark_digest','measurement_observation_digest','record_digest'
        ],
        'SourceM3'
    );
    PERFORM mirror_demo_d02_r2_require_record(
        source_record,
        'mirror.demo/D02SourceM3RepeatRecord/v3',
        ARRAY[
            'schema_version','source_m3_record_id','source_ordinal',
            'source_authority_key','source_admission_event_id','source_asset_id',
            'source_asset_sha256','repeat_index','execution_receipt_digest',
            'vision_model_manifest_digest','runtime_manifest_digest','topology_digest',
            'canonical_output_digest','landmark_digest','measurement_observation',
            'measurement_observation_digest','face_count','landmark_count',
            'coordinates_finite','coordinates_in_bounds','repeat_gate_passed',
            'record_digest','source_authority_digest'
        ]
    );
    expected_id := substring(mirror_demo_digest(
        'mirror.demo/D02SourceM3RecordId/v2',
        jsonb_build_object(
            'source_manifest_digest', source_manifest_digest,
            'source_authority_key', source_entry ->> 'source_authority_key',
            'source_admission_event_id', source_entry ->> 'source_admission_event_id',
            'source_asset_id', source_entry ->> 'source_asset_id',
            'source_asset_sha256', source_entry ->> 'source_asset_sha256',
            'repeat_index', (source_record ->> 'repeat_index')::integer,
            'vision_model_manifest_digest', source_record ->> 'vision_model_manifest_digest',
            'runtime_manifest_digest', source_record ->> 'runtime_manifest_digest',
            'topology_digest', source_record ->> 'topology_digest'
        )
    ) FROM 1 FOR 32);
    IF source_record ->> 'source_m3_record_id' IS DISTINCT FROM expected_id
       OR source_record ->> 'source_authority_digest' IS DISTINCT FROM
          source_entry ->> 'source_authority_digest' THEN
        RAISE EXCEPTION 'D02 R2 SourceM3 ID or source authority is invalid';
    END IF;

    shadow_id := substring(mirror_demo_digest(
        'mirror.demo/D02SourceM3RecordId/v1',
        jsonb_build_object(
            'source_manifest_digest', source_manifest_digest,
            'source_authority_key', source_entry ->> 'source_authority_key',
            'source_admission_event_id', source_entry ->> 'source_admission_event_id',
            'source_asset_id', source_entry ->> 'source_asset_id',
            'source_asset_sha256', source_entry ->> 'source_asset_sha256',
            'repeat_index', (source_record ->> 'repeat_index')::integer,
            'vision_model_manifest_digest', source_record ->> 'vision_model_manifest_digest',
            'runtime_manifest_digest', source_record ->> 'runtime_manifest_digest',
            'topology_digest', source_record ->> 'topology_digest'
        )
    ) FROM 1 FOR 32);
    shadow_record := source_record - ARRAY[
        'source_authority_digest','record_digest'
    ]::text[];
    shadow_record := shadow_record || jsonb_build_object(
        'schema_version', 'mirror.demo/D02SourceM3RepeatRecord/v2',
        'source_m3_record_id', shadow_id
    );
    shadow_record := shadow_record || jsonb_build_object(
        'record_digest', mirror_demo_digest(
            'mirror.demo/D02SourceM3RepeatRecord/v2',
            shadow_record - 'schema_version'
        )
    );
    PERFORM mirror_demo_d02_validate_source_m3_v10(
        shadow_record, source_entry, source_manifest_digest
    );
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_r2_m4_v2(
    m4_record jsonb,
    case_entry jsonb,
    source_entry jsonb,
    expected_replay integer
)
RETURNS void
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
DECLARE
    expected_id text;
BEGIN
    PERFORM mirror_demo_d02_r2_require_record(
        m4_record,
        'mirror.demo/D02M4ExecutionRecord/v2',
        ARRAY[
            'schema_version','m4_execution_record_id','case_id',
            'case_specification_digest','replay_index','source_output_id',
            'source_asset_id','source_asset_sha256','result_output_id','result_sha256',
            'result_byte_size','result_mime_type','result_width','result_height',
            'changed_pixel_count','warp_plan_digest','geometry_algorithm_version',
            'runtime_manifest_digest','runtime_config_digest','determinism_level',
            'execution_receipt_digest','execution_succeeded','record_digest'
        ]
    );
    expected_id := substring(mirror_demo_digest(
        'mirror.demo/D02M4ExecutionRecordId/v2',
        jsonb_build_object(
            'case_id', case_entry ->> 'case_id',
            'case_specification_digest', case_entry ->> 'case_specification_digest',
            'replay_index', expected_replay,
            'geometry_algorithm_version', case_entry ->> 'geometry_algorithm_version',
            'runtime_manifest_digest', case_entry ->> 'runtime_manifest_digest',
            'runtime_config_digest', case_entry ->> 'runtime_config_digest',
            'determinism_level', case_entry ->> 'determinism_level'
        )
    ) FROM 1 FOR 32);
    IF m4_record ->> 'm4_execution_record_id' IS DISTINCT FROM expected_id
       OR m4_record ->> 'case_id' IS DISTINCT FROM case_entry ->> 'case_id'
       OR m4_record ->> 'case_specification_digest' IS DISTINCT FROM
          case_entry ->> 'case_specification_digest'
       OR m4_record -> 'replay_index' IS DISTINCT FROM to_jsonb(expected_replay)
       OR m4_record ->> 'source_output_id' IS DISTINCT FROM
          source_entry ->> 'source_output_id'
       OR m4_record ->> 'source_asset_id' IS DISTINCT FROM
          case_entry ->> 'source_asset_id'
       OR m4_record ->> 'source_asset_sha256' IS DISTINCT FROM
          case_entry ->> 'source_asset_sha256'
       OR mirror_demo_d02_json_string_matches(
              m4_record -> 'result_output_id', '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'
          ) IS NOT TRUE
       OR mirror_demo_d02_json_string_matches(
              m4_record -> 'result_sha256', '^[0-9a-f]{64}$'
          ) IS NOT TRUE
       OR mirror_demo_d02_json_integer_between(
              m4_record -> 'result_byte_size', 1, 9223372036854775807
          ) IS NOT TRUE
       OR m4_record ->> 'result_mime_type' IS DISTINCT FROM 'image/jpeg'
       OR mirror_demo_d02_json_integer_between(
              m4_record -> 'result_width', 1, 2147483647
          ) IS NOT TRUE
       OR mirror_demo_d02_json_integer_between(
              m4_record -> 'result_height', 1, 2147483647
          ) IS NOT TRUE
       OR mirror_demo_d02_json_integer_between(
              m4_record -> 'changed_pixel_count',
              1,
              (m4_record ->> 'result_width')::integer *
                  (m4_record ->> 'result_height')::integer
          ) IS NOT TRUE
       OR m4_record ->> 'warp_plan_digest' IS DISTINCT FROM
          case_entry ->> 'warp_plan_digest'
       OR m4_record ->> 'geometry_algorithm_version' IS DISTINCT FROM
          case_entry ->> 'geometry_algorithm_version'
       OR m4_record ->> 'runtime_manifest_digest' IS DISTINCT FROM
          case_entry ->> 'runtime_manifest_digest'
       OR m4_record ->> 'runtime_config_digest' IS DISTINCT FROM
          case_entry ->> 'runtime_config_digest'
       OR m4_record ->> 'determinism_level' IS DISTINCT FROM
          case_entry ->> 'determinism_level'
       OR mirror_demo_d02_json_string_matches(
              m4_record -> 'execution_receipt_digest', '^[0-9a-f]{64}$'
          ) IS NOT TRUE
       OR m4_record -> 'execution_succeeded' IS DISTINCT FROM 'true'::jsonb THEN
        RAISE EXCEPTION 'D02 R2 M4 execution authority is invalid';
    END IF;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_r2_result_m3_v3(
    result_record jsonb,
    case_entry jsonb,
    first_m4_record jsonb,
    expected_repeat integer
)
RETURNS void
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
DECLARE
    expected_id text;
    shadow_id text;
    shadow_record jsonb;
BEGIN
    PERFORM mirror_demo_d02_r2_require_mandatory_digest_leaves(
        result_record,
        ARRAY[
            'case_specification_digest','result_sha256','execution_receipt_digest',
            'vision_model_manifest_digest','runtime_manifest_digest','topology_digest',
            'canonical_output_digest','landmark_digest',
            'measurement_observation_digest','record_digest'
        ],
        'ResultM3'
    );
    PERFORM mirror_demo_d02_r2_require_record(
        result_record,
        'mirror.demo/D02ResultM3RepeatRecord/v3',
        ARRAY[
            'schema_version','result_m3_record_id','case_id',
            'case_specification_digest','result_output_id','result_sha256','repeat_index',
            'execution_receipt_digest','vision_model_manifest_digest',
            'runtime_manifest_digest','topology_digest','canonical_output_digest',
            'landmark_digest','measurement_observation','measurement_observation_digest',
            'face_count','landmark_count','coordinates_finite','coordinates_in_bounds',
            'observation_state','repeat_gate_passed','record_digest'
        ]
    );
    expected_id := substring(mirror_demo_digest(
        'mirror.demo/D02ResultM3RepeatRecordId/v2',
        jsonb_build_object(
            'case_id', case_entry ->> 'case_id',
            'case_specification_digest', case_entry ->> 'case_specification_digest',
            'result_output_id', first_m4_record ->> 'result_output_id',
            'result_sha256', first_m4_record ->> 'result_sha256',
            'repeat_index', expected_repeat,
            'runtime_manifest_digest', result_record ->> 'runtime_manifest_digest',
            'vision_model_manifest_digest', result_record ->> 'vision_model_manifest_digest',
            'topology_digest', result_record ->> 'topology_digest'
        )
    ) FROM 1 FOR 32);
    IF result_record ->> 'result_m3_record_id' IS DISTINCT FROM expected_id THEN
        RAISE EXCEPTION 'D02 R2 ResultM3 ID is invalid';
    END IF;

    shadow_id := substring(mirror_demo_digest(
        'mirror.demo/D02ResultM3RecordId/v1',
        jsonb_build_object(
            'case_id', case_entry ->> 'case_id',
            'case_specification_digest', case_entry ->> 'case_specification_digest',
            'result_output_id', first_m4_record ->> 'result_output_id',
            'result_sha256', first_m4_record ->> 'result_sha256',
            'repeat_index', expected_repeat,
            'vision_model_manifest_digest', result_record ->> 'vision_model_manifest_digest',
            'runtime_manifest_digest', result_record ->> 'runtime_manifest_digest',
            'topology_digest', result_record ->> 'topology_digest'
        )
    ) FROM 1 FOR 32);
    shadow_record := result_record - 'record_digest';
    shadow_record := shadow_record || jsonb_build_object(
        'schema_version', 'mirror.demo/D02ResultM3RepeatRecord/v2',
        'result_m3_record_id', shadow_id
    );
    shadow_record := shadow_record || jsonb_build_object(
        'record_digest', mirror_demo_digest(
            'mirror.demo/D02ResultM3RepeatRecord/v2',
            shadow_record - 'schema_version'
        )
    );
    PERFORM mirror_demo_d02_validate_result_m3_v10(
        shadow_record, case_entry, first_m4_record, expected_repeat
    );
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_r2_gate_v5(
    gate_record jsonb,
    case_entry jsonb,
    peer_case_entry jsonb,
    source_entry jsonb,
    result_records jsonb
)
RETURNS void
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
DECLARE
    certificate jsonb := gate_record -> 'result_repeat_certification';
    certificate_subject jsonb := certificate -> 'subject';
    binding jsonb;
    result_record jsonb;
    repeat_index integer;
    semantic_key text;
BEGIN
    PERFORM mirror_demo_d02_r2_require_record(
        gate_record,
        'mirror.demo/D02MeasurementGateRecord/v5',
        ARRAY[
            'schema_version','case_id','case_specification_digest','dimension_key',
            'requested_direction','requested_magnitude_ppm','monotonicity_peer_case_id',
            'source_target_measurement','ordered_source_control_measurements',
            'ordered_result_repeat_measurements','measurement_evaluation_state',
            'gate_evaluation','result_repeat_certification',
            'result_repeat_certification_digest','record_digest'
        ]
    );
    PERFORM mirror_demo_d02_r2_require_record(
        certificate,
        'mirror.demo/D02ResultRepeatDeterminismCertification/v1',
        ARRAY[
            'schema_version','subject','runtime_manifest_digest',
            'vision_model_manifest_digest','topology_digest','measurement_config_digest',
            'measurement_quality_config_digest',
            'measurement_quality_manifest_content_digest','reliability_kind',
            'repeat_count','certification_state','certified_raw_reliability_fixed18',
            'certified_reliability_ppm','ordered_repeat_bindings',
            'result_repeat_certification_digest'
        ],
        'result_repeat_certification_digest'
    );
    IF jsonb_typeof(result_records) IS DISTINCT FROM 'array'
       OR jsonb_array_length(result_records) IS DISTINCT FROM 3
       OR jsonb_typeof(certificate -> 'ordered_repeat_bindings') IS DISTINCT FROM 'array'
       OR jsonb_array_length(certificate -> 'ordered_repeat_bindings') IS DISTINCT FROM 3
       OR mirror_demo_jsonb_exact_keys(
              certificate_subject,
              ARRAY[
                  'schema_version','case_id','case_specification_digest',
                  'result_output_id','result_sha256'
              ]
          ) IS NOT TRUE
       OR certificate_subject ->> 'schema_version' IS DISTINCT FROM
          'mirror.demo/D02ResultObservationSubject/v1'
       OR gate_record ->> 'result_repeat_certification_digest' IS DISTINCT FROM
          certificate ->> 'result_repeat_certification_digest'
       OR gate_record ->> 'case_id' IS DISTINCT FROM case_entry ->> 'case_id'
       OR gate_record ->> 'case_specification_digest' IS DISTINCT FROM
          case_entry ->> 'case_specification_digest'
       OR gate_record ->> 'dimension_key' IS DISTINCT FROM
          case_entry ->> 'dimension_key'
       OR gate_record ->> 'requested_direction' IS DISTINCT FROM
          case_entry ->> 'direction'
       OR gate_record -> 'requested_magnitude_ppm' IS DISTINCT FROM
          case_entry -> 'magnitude_ppm'
       OR gate_record ->> 'monotonicity_peer_case_id' IS DISTINCT FROM
          peer_case_entry ->> 'case_id'
       OR peer_case_entry ->> 'source_authority_key' IS DISTINCT FROM
          case_entry ->> 'source_authority_key'
       OR peer_case_entry ->> 'source_admission_event_id' IS DISTINCT FROM
          case_entry ->> 'source_admission_event_id'
       OR peer_case_entry ->> 'dimension_key' IS DISTINCT FROM
          case_entry ->> 'dimension_key'
       OR peer_case_entry ->> 'direction' IS DISTINCT FROM
          case_entry ->> 'direction'
       OR gate_record -> 'source_target_measurement' IS DISTINCT FROM (
              SELECT item.value
              FROM jsonb_array_elements(
                  source_entry -> 'ordered_supported_measurements'
              ) AS item(value)
              WHERE item.value ->> 'dimension_key' = case_entry ->> 'dimension_key'
          ) THEN
        RAISE EXCEPTION 'D02 R2 Gate graph binding is invalid';
    END IF;
    FOR repeat_index IN 0..2 LOOP
        result_record := result_records -> repeat_index;
        binding := certificate -> 'ordered_repeat_bindings' -> repeat_index;
        IF mirror_demo_jsonb_exact_keys(
            binding,
            ARRAY[
                'result_m3_record_id','repeat_index','execution_receipt_digest',
                'canonical_output_digest','landmark_digest',
                'measurement_observation_digest','face_count','landmark_count',
                'coordinates_finite','coordinates_in_bounds','observation_state',
                'repeat_gate_passed'
            ]
        ) IS NOT TRUE
           OR binding -> 'repeat_index' IS DISTINCT FROM to_jsonb(repeat_index + 1)
           OR result_record -> 'measurement_observation' -> 'subject' IS DISTINCT FROM
              certificate_subject THEN
            RAISE EXCEPTION 'D02 R2 Gate certificate order or subject is invalid';
        END IF;
        FOREACH semantic_key IN ARRAY ARRAY[
            'result_m3_record_id','repeat_index','execution_receipt_digest',
            'canonical_output_digest','landmark_digest',
            'measurement_observation_digest','face_count','landmark_count',
            'coordinates_finite','coordinates_in_bounds','observation_state',
            'repeat_gate_passed'
        ] LOOP
            IF binding -> semantic_key IS DISTINCT FROM result_record -> semantic_key THEN
                RAISE EXCEPTION 'D02 R2 Gate certificate tuple is invalid';
            END IF;
        END LOOP;
    END LOOP;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_r2_screening_report_v3()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    payload jsonb := NEW.report_payload;
    binding jsonb := payload -> 'schema_and_policy';
    measurement_config jsonb := binding -> 'measurement_execution_config';
    network_boundary jsonb := payload -> 'network_and_runtime_boundary';
    exact_duplicate jsonb := payload -> 'exact_duplicate_evidence';
    phash_evidence jsonb := payload -> 'phash_observation_evidence';
    source_entry jsonb;
    previous_source_entry jsonb;
    source_record jsonb;
    source_identity demo_synthetic_identities%ROWTYPE;
    source_support demo_d02_r2_source_authorities%ROWTYPE;
    source_index integer;
    record_index integer;
    expected_source_index integer;
    expected_case_index integer;
    expected_dimension_index integer;
    expected_magnitude_index integer;
    expected_dimension text;
    expected_direction text;
    expected_control_dimensions text[];
    expected_execution_config_digest text;
    expected_case_id text;
    expected_case_specification_digest text;
    expected_result_asset_id text;
    case_entry jsonb;
    peer_case_entry jsonb;
    m4_record jsonb;
    first_m4_record jsonb;
    second_m4_record jsonb;
    result_record jsonb;
    result_records jsonb;
    gate_record jsonb;
    shadow_record jsonb;
    shadow_m4_records jsonb := '[]'::jsonb;
    shadow_gate_records jsonb := '[]'::jsonb;
    shadow_structure_records jsonb := '[]'::jsonb;
    shadow_manual_records jsonb := '[]'::jsonb;
    shadow_row demo_pair_screening_reports%ROWTYPE;
    manual_case_entry jsonb;
    manual_structure_entry jsonb;
    previous_manual_case_id text := '';
    expected_manual_verdict text;
    pair_wrapper jsonb;
    pair_payload jsonb;
    left_side jsonb;
    right_side jsonb;
    left_case jsonb;
    right_case jsonb;
    dimension_entry jsonb;
    selection_entry jsonb;
    selected_entry jsonb;
    image_entry jsonb;
    prior_image_entry jsonb;
    signature_entry jsonb;
    comparison_entry jsonb;
    eligible_dimensions jsonb;
    selected_dimensions jsonb;
    expected_selected_manifest_digest text;
    expected_report_digest text;
    expected_id text;
    expected_pair_digests jsonb;
    expected_side_digests jsonb;
    expected_side_entries jsonb;
    expected_pair_entries jsonb;
    expected_failure_reasons jsonb;
    expected_payload jsonb;
    expected_decision text;
    expected_pair_gate boolean;
    expected_side_gate boolean;
    expected_all_side boolean;
    expected_all_pair boolean;
    expected_all_manual boolean;
    expected_all_lock boolean;
    expected_eligible boolean;
    expected_exact_sha boolean;
    expected_selected boolean;
    expected_quality integer;
    expected_rank integer;
    expected_slot integer;
    pair_index integer;
    left_case_index integer;
    right_case_index integer;
    left_image_index integer;
    right_image_index integer;
    comparison_index integer := 0;
    selected_dimension_index integer;
    eligible_count integer := 0;
    eligible_rank integer := 0;
    duplicate_all_unique boolean;
    duplicate_source_unique boolean;
    duplicate_result_unique boolean;
    duplicate_disjoint boolean;
    candidate_dimensions constant text[] := ARRAY['jaw_width','chin_height','eye_spacing'];
    failure_reason_order constant text[] := ARRAY[
        'ONE_OR_MORE_SIDE_GATES_FAILED',
        'ONE_OR_MORE_PAIR_GATES_FAILED',
        'ONE_OR_MORE_MANUAL_GATES_FAILED',
        'GLOBAL_EXACT_SHA_GATE_FAILED',
        'EMPTY_LOCK_POLICY_GATE_FAILED'
    ];
BEGIN
    IF NEW.schema_version IS DISTINCT FROM 'mirror.demo/D02PairScreeningReport/v3'
       OR mirror_demo_jsonb_exact_keys(
           payload,
           ARRAY[
               'schema_and_policy','ordered_source_manifest','ordered_case_manifest',
               'source_m3_repeat_evidence','m4_repeat_evidence',
               'result_m3_repeat_evidence','measurement_gate_evidence',
               'decode_structure_immutability_evidence','manual_review_evidence',
               'exact_duplicate_evidence','phash_observation_evidence',
               'pair_quality_evidence','dimension_eligibility',
               'fixed_priority_selection_trace','selected_pair_manifest',
               'network_and_runtime_boundary'
           ]
       ) IS NOT TRUE THEN
        RAISE EXCEPTION 'D02 R2 Report v3 envelope is invalid';
    END IF;

    IF mirror_demo_jsonb_exact_keys(
        binding,
        ARRAY[
            'schema_version','source_manifest_digest','case_manifest_digest',
            'screening_policy_digest','runtime_manifest_digest',
            'vision_model_manifest_digest','topology_digest',
            'measurement_config_digest','measurement_quality_config_digest',
            'measurement_quality_manifest_content_digest','confidence_kind',
            'reliability_kind','measurement_execution_config',
            'manual_review_policy_digest','duplicate_policy_digest',
            'phash_implementation_digest'
        ]
    ) IS NOT TRUE
       OR binding ->> 'schema_version' IS DISTINCT FROM
          'mirror.demo/D02SchemaAndPolicyBinding/v3'
       OR binding ->> 'source_manifest_digest' IS DISTINCT FROM NEW.source_manifest_digest
       OR binding ->> 'case_manifest_digest' IS DISTINCT FROM NEW.case_manifest_digest
       OR binding ->> 'screening_policy_digest' IS DISTINCT FROM NEW.screening_policy_digest
       OR binding ->> 'runtime_manifest_digest' IS DISTINCT FROM NEW.runtime_manifest_digest
       OR binding ->> 'vision_model_manifest_digest' IS DISTINCT FROM
          NEW.vision_model_manifest_digest
       OR binding ->> 'topology_digest' IS DISTINCT FROM NEW.topology_digest
       OR binding ->> 'measurement_config_digest' IS DISTINCT FROM
          NEW.measurement_config_digest
       OR binding ->> 'manual_review_policy_digest' IS DISTINCT FROM
          NEW.manual_review_policy_digest
       OR binding ->> 'duplicate_policy_digest' IS DISTINCT FROM
          NEW.duplicate_policy_digest
       OR binding ->> 'phash_implementation_digest' IS DISTINCT FROM
          NEW.phash_implementation_digest
       OR NEW.screening_policy_digest IS DISTINCT FROM
          mirror_demo_d02_expected_screening_policy_digest()
       OR NEW.runtime_manifest_digest IS DISTINCT FROM
          '6d739c2e269128ea7bc09358203aa7efe0714484b1a216a9f401353a243135ed'
       OR NEW.vision_model_manifest_digest IS DISTINCT FROM
          '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'
       OR NEW.topology_digest IS DISTINCT FROM
          '85eea84eef15dd963e06382d6e61f7357029d9901acc935731ecaa7eab856b63'
       OR NEW.measurement_config_digest IS DISTINCT FROM
          'ab5f745641a6f4539a8010fe32dda82b6c1066a8cb97d36ae17de737b901e8d3'
       OR binding ->> 'measurement_quality_config_digest' IS DISTINCT FROM
          'ed52feca45f18b976e34d419da117d777d540978b9552c3e423a0d0c543e8f47'
       OR binding ->> 'measurement_quality_manifest_content_digest' IS DISTINCT FROM
          'ed11f53e8e75428c396fb2b6711bd17fa996d49f8c4f5c9cdfebcfb36b42ed74'
       OR binding ->> 'confidence_kind' IS DISTINCT FROM
          'DEMO_GEOMETRIC_OBSERVABILITY_PROXY_NOT_MODEL_CONFIDENCE'
       OR binding ->> 'reliability_kind' IS DISTINCT FROM
          'EXACT_REPEAT_DETERMINISM_CERTIFICATION_NOT_MODEL_RELIABILITY'
       OR mirror_demo_jsonb_exact_keys(
           measurement_config,
           ARRAY[
               'schema_version','measurement_algorithm_version',
               'measurement_projection_version','measurement_quantization_version',
               'decimal_serialization_version','decimal_precision','rounding',
               'coordinate_system','required_face_count','required_landmark_count',
               'repeat_count','supported_raw_min_fixed18','supported_ppm_min',
               'supported_ppm_max','unsupported_reason_precedence',
               'unsupported_projection_policy_version','source_repeat_failure_policy_version',
               'result_repeat_failure_policy_version','confidence_algorithm_version',
               'confidence_kind','reliability_algorithm_version','reliability_kind',
               'source_p2_candidate_manifest_content_digest',
               'dimension_authority_manifest_content_digest',
               'geometry_ontology_version_digest','vision_model_manifest_digest',
               'topology_digest','d02_execution_runtime_set_digest',
               'measurement_quality_config_digest',
               'measurement_observation_schema_version',
               'source_repeat_certification_schema_version',
               'result_repeat_certification_schema_version',
               'source_m3_repeat_record_schema_version',
               'result_m3_repeat_record_schema_version',
               'measurement_gate_record_schema_version'
           ]
       ) IS NOT TRUE
       OR measurement_config ->> 'schema_version' IS DISTINCT FROM
          'mirror.demo/D02MeasurementExecutionConfig/v1'
       OR mirror_demo_digest(
              'mirror.demo/D02MeasurementExecutionConfig/v1',
              measurement_config - 'schema_version'
          ) IS DISTINCT FROM NEW.measurement_config_digest
       OR measurement_config ->> 'source_p2_candidate_manifest_content_digest'
          IS DISTINCT FROM
          'eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4'
       OR measurement_config ->> 'dimension_authority_manifest_content_digest'
          IS DISTINCT FROM
          'd4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a'
       OR measurement_config ->> 'geometry_ontology_version_digest' IS DISTINCT FROM
          'd902fe2cfdf69db9f62ccc2e5fa7c569227d652f1204aa683742fc3c592f38b9'
       OR measurement_config ->> 'measurement_quality_config_digest' IS DISTINCT FROM
          binding ->> 'measurement_quality_config_digest'
       OR measurement_config ->> 'd02_execution_runtime_set_digest' IS DISTINCT FROM
          NEW.runtime_manifest_digest
       OR measurement_config ->> 'vision_model_manifest_digest' IS DISTINCT FROM
          NEW.vision_model_manifest_digest
       OR measurement_config ->> 'topology_digest' IS DISTINCT FROM NEW.topology_digest
       OR measurement_config ->> 'confidence_kind' IS DISTINCT FROM
          binding ->> 'confidence_kind'
       OR measurement_config ->> 'reliability_kind' IS DISTINCT FROM
          binding ->> 'reliability_kind' THEN
        RAISE EXCEPTION 'D02 R2 Report v3 schema/policy authority is invalid';
    END IF;

    IF jsonb_typeof(payload -> 'ordered_source_manifest') IS DISTINCT FROM 'array'
       OR jsonb_array_length(payload -> 'ordered_source_manifest') IS DISTINCT FROM 4
       OR jsonb_typeof(payload -> 'ordered_case_manifest') IS DISTINCT FROM 'array'
       OR jsonb_array_length(payload -> 'ordered_case_manifest') IS DISTINCT FROM 48
       OR jsonb_typeof(payload -> 'source_m3_repeat_evidence') IS DISTINCT FROM 'array'
       OR jsonb_array_length(payload -> 'source_m3_repeat_evidence') IS DISTINCT FROM 12
       OR jsonb_typeof(payload -> 'm4_repeat_evidence') IS DISTINCT FROM 'array'
       OR jsonb_array_length(payload -> 'm4_repeat_evidence') IS DISTINCT FROM 96
       OR jsonb_typeof(payload -> 'result_m3_repeat_evidence') IS DISTINCT FROM 'array'
       OR jsonb_array_length(payload -> 'result_m3_repeat_evidence') IS DISTINCT FROM 144
       OR jsonb_typeof(payload -> 'measurement_gate_evidence') IS DISTINCT FROM 'array'
       OR jsonb_array_length(payload -> 'measurement_gate_evidence') IS DISTINCT FROM 48
       OR jsonb_typeof(payload -> 'decode_structure_immutability_evidence')
          IS DISTINCT FROM 'array'
       OR jsonb_array_length(payload -> 'decode_structure_immutability_evidence')
          IS DISTINCT FROM 48
       OR jsonb_typeof(payload -> 'manual_review_evidence') IS DISTINCT FROM 'array'
       OR jsonb_array_length(payload -> 'manual_review_evidence') IS DISTINCT FROM 48
       OR jsonb_typeof(payload -> 'pair_quality_evidence') IS DISTINCT FROM 'array'
       OR jsonb_array_length(payload -> 'pair_quality_evidence') IS DISTINCT FROM 24
       OR jsonb_typeof(payload -> 'dimension_eligibility') IS DISTINCT FROM 'array'
       OR jsonb_array_length(payload -> 'dimension_eligibility') IS DISTINCT FROM 3
       OR jsonb_typeof(payload -> 'fixed_priority_selection_trace')
          IS DISTINCT FROM 'array'
       OR jsonb_array_length(payload -> 'fixed_priority_selection_trace')
          IS DISTINCT FROM 3
       OR jsonb_typeof(payload -> 'selected_pair_manifest') IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'D02 R2 Report v3 evidence universe is incomplete';
    END IF;

    FOR source_index IN 0..3 LOOP
        source_entry := payload -> 'ordered_source_manifest' -> source_index;
        PERFORM mirror_demo_d02_r2_require_record(
            source_entry,
            'mirror.demo/D02SourceAuthorityManifestEntry/v4',
            ARRAY[
                'schema_version','source_ordinal','source_authority_kind',
                'source_authority_key','source_admission_event_id',
                'source_admission_content_digest','source_output_id','source_asset_id',
                'source_asset_sha256','source_asset_byte_size','source_asset_mime_type',
                'source_asset_width','source_asset_height','source_receipt_digest',
                'source_authority_digest','source_qa_snapshot_digest',
                'source_landmark_digest','source_measurement_digest',
                'source_provenance_digest','source_fact_snapshot_digest',
                'raw_measurement_authority_digest','source_measurement_projection_digest',
                'adult_synthetic_attested','original_formal_identity_id_status',
                'source_p2_candidate_manifest_content_digest',
                'dimension_authority_manifest_content_digest','measurement_config_digest',
                'measurement_quality_config_digest',
                'measurement_quality_manifest_content_digest','confidence_kind',
                'reliability_kind','runtime_manifest_digest','vision_model_manifest_digest',
                'topology_digest','source_repeat_certification_digest','import_config_digest',
                'ordered_supported_measurements','record_digest',
                'r2_source_authority_record_id'
            ]
        );
        SELECT * INTO source_identity
        FROM demo_synthetic_identities
        WHERE id = source_entry ->> 'source_admission_event_id'
          AND schema_version = 'mirror.demo/DemoSyntheticIdentity/v4';
        IF NOT FOUND THEN
            RAISE EXCEPTION 'D02 R2 Report v3 source Identity authority is missing';
        END IF;
        SELECT * INTO source_support
        FROM demo_d02_r2_source_authorities
        WHERE id = source_entry ->> 'r2_source_authority_record_id';
        IF NOT FOUND
           OR source_entry -> 'source_ordinal' IS DISTINCT FROM to_jsonb(source_index + 1)
           OR source_identity.r2_source_authority_record_id IS DISTINCT FROM source_support.id
           OR source_identity.content_digest IS DISTINCT FROM
              source_entry ->> 'source_admission_content_digest'
           OR source_identity.source_authority_key IS DISTINCT FROM
              source_entry ->> 'source_authority_key'
           OR source_identity.formal_canonical_asset_id IS DISTINCT FROM
              source_entry ->> 'source_asset_id'
           OR source_identity.formal_canonical_asset_sha256 IS DISTINCT FROM
              source_entry ->> 'source_asset_sha256'
           OR source_identity.source_output_id IS DISTINCT FROM
              source_entry ->> 'source_output_id'
           OR source_identity.source_receipt_digest IS DISTINCT FROM
              source_entry ->> 'source_receipt_digest'
           OR source_identity.source_authority_digest IS DISTINCT FROM
              source_entry ->> 'source_authority_digest'
           OR source_identity.source_qa_snapshot_digest IS DISTINCT FROM
              source_entry ->> 'source_qa_snapshot_digest'
           OR source_identity.source_landmark_digest IS DISTINCT FROM
              source_entry ->> 'source_landmark_digest'
           OR source_identity.source_measurement_digest IS DISTINCT FROM
              source_entry ->> 'source_measurement_digest'
           OR source_identity.source_provenance_digest IS DISTINCT FROM
              source_entry ->> 'source_provenance_digest'
           OR source_identity.source_fact_snapshot_digest IS DISTINCT FROM
              source_entry ->> 'source_fact_snapshot_digest'
           OR source_identity.source_measurement_projection_digest IS DISTINCT FROM
              source_entry ->> 'source_measurement_projection_digest'
           OR source_identity.original_formal_identity_id_status IS DISTINCT FROM
              source_entry ->> 'original_formal_identity_id_status'
           OR source_identity.import_config_digest IS DISTINCT FROM
              source_entry ->> 'import_config_digest'
           OR source_support.source_ordinal IS DISTINCT FROM source_index + 1
           OR source_support.source_output_id IS DISTINCT FROM
              source_entry ->> 'source_output_id'
           OR source_support.source_asset_id IS DISTINCT FROM
              source_entry ->> 'source_asset_id'
           OR source_support.source_asset_sha256 IS DISTINCT FROM
              source_entry ->> 'source_asset_sha256'
           OR source_support.source_authority_key IS DISTINCT FROM
              source_entry ->> 'source_authority_key'
           OR source_support.source_authority_digest IS DISTINCT FROM
              source_entry ->> 'source_authority_digest'
           OR source_support.source_qa_snapshot_digest IS DISTINCT FROM
              source_entry ->> 'source_qa_snapshot_digest'
           OR source_support.source_provenance_digest IS DISTINCT FROM
              source_entry ->> 'source_provenance_digest'
           OR source_entry ->> 'source_authority_kind' IS DISTINCT FROM
              'DEMO_R2_GENERATED_SOURCE'
           OR source_entry ->> 'source_asset_mime_type' IS DISTINCT FROM 'image/jpeg'
           OR source_entry -> 'adult_synthetic_attested' IS DISTINCT FROM 'true'::jsonb
           OR source_entry ->> 'original_formal_identity_id_status' IS DISTINCT FROM
              'NOT_APPLICABLE_DEMO_R2_GENERATED_SOURCE'
           OR source_entry ->> 'import_config_digest' IS DISTINCT FROM
              '08dd11a4161286bef11b5a64928f4c5f1447ed54d326dbc47c6b5a52905ed021' THEN
            RAISE EXCEPTION 'D02 R2 Report v3 SourceEntry projection is invalid';
        END IF;
        PERFORM mirror_demo_require_current_synthetic_admission(source_identity.id);
    END LOOP;
    IF NEW.source_manifest_digest IS DISTINCT FROM mirror_demo_digest(
        'mirror.demo/D02SourceAuthorityManifest/v2',
        payload -> 'ordered_source_manifest'
    ) OR (
        SELECT count(DISTINCT item.value ->> 'record_digest')
        FROM jsonb_array_elements(payload -> 'ordered_source_manifest') AS item(value)
    ) IS DISTINCT FROM 4 THEN
        RAISE EXCEPTION 'D02 R2 Report v3 source manifest is invalid';
    END IF;

    FOR record_index IN 0..47 LOOP
        case_entry := payload -> 'ordered_case_manifest' -> record_index;
        PERFORM mirror_demo_d02_r2_require_record(
            case_entry,
            'mirror.demo/D02GeometryCaseManifestEntry/v4',
            ARRAY[
                'schema_version','case_ordinal','case_id','source_manifest_digest',
                'source_ordinal','source_authority_key','source_admission_event_id',
                'source_asset_id','source_asset_sha256','source_qa_snapshot_digest',
                'source_measurement_projection_digest',
                'source_p2_candidate_manifest_content_digest',
                'dimension_authority_manifest_content_digest',
                'geometry_ontology_version_digest','dimension_key','priority_index',
                'direction','direction_index','magnitude_ppm','magnitude_index',
                'ordered_control_dimensions','warp_plan_digest','geometry_algorithm_version',
                'runtime_manifest_digest','runtime_config_digest','output_policy_version',
                'output_width','output_height','determinism_level','execution_config_digest',
                'case_specification_digest','record_digest','r2_source_authority_record_id'
            ]
        );
        expected_source_index := record_index / 12;
        expected_dimension_index := (record_index % 12) / 4;
        expected_magnitude_index := record_index % 2;
        source_entry := payload -> 'ordered_source_manifest' -> expected_source_index;
        expected_dimension := candidate_dimensions[expected_dimension_index + 1];
        expected_direction :=
            (ARRAY['DECREASE','INCREASE'])[((record_index % 4) / 2) + 1];
        expected_control_dimensions := CASE expected_dimension
            WHEN 'jaw_width' THEN ARRAY[
                'cheekbone_width','chin_height','eye_spacing','mouth_width','nose_width'
            ]
            WHEN 'chin_height' THEN ARRAY[
                'cheekbone_width','eye_spacing','jaw_width','mouth_width','nose_width'
            ]
            ELSE ARRAY[
                'cheekbone_width','chin_height','jaw_width','mouth_width','nose_width'
            ]
        END;
        expected_execution_config_digest := mirror_demo_digest(
            'mirror.demo/D02ExecutionConfiguration/v2',
            jsonb_build_object(
                'screening_policy_digest', NEW.screening_policy_digest,
                'runtime_manifest_digest', NEW.runtime_manifest_digest,
                'vision_model_manifest_digest', NEW.vision_model_manifest_digest,
                'topology_digest', NEW.topology_digest,
                'measurement_config_digest', NEW.measurement_config_digest,
                'manual_review_policy_digest', NEW.manual_review_policy_digest,
                'duplicate_policy_digest', NEW.duplicate_policy_digest,
                'phash_implementation_digest', NEW.phash_implementation_digest,
                'geometry_algorithm_version', case_entry ->> 'geometry_algorithm_version',
                'runtime_config_digest', case_entry ->> 'runtime_config_digest',
                'output_policy_version', case_entry ->> 'output_policy_version',
                'output_width', (case_entry ->> 'output_width')::integer,
                'output_height', (case_entry ->> 'output_height')::integer,
                'determinism_level', case_entry ->> 'determinism_level'
            )
        );
        expected_case_id := substring(mirror_demo_digest(
            'mirror.demo/D02GeometryCaseId/v2',
            jsonb_build_object(
                'source_manifest_digest', NEW.source_manifest_digest,
                'source_authority_key', source_entry ->> 'source_authority_key',
                'source_admission_event_id', source_entry ->> 'source_admission_event_id',
                'source_asset_sha256', source_entry ->> 'source_asset_sha256',
                'r2_source_authority_record_id',
                    source_entry ->> 'r2_source_authority_record_id',
                'source_p2_candidate_manifest_content_digest',
                    source_entry ->> 'source_p2_candidate_manifest_content_digest',
                'dimension_authority_manifest_content_digest',
                    source_entry ->> 'dimension_authority_manifest_content_digest',
                'dimension_key', expected_dimension,
                'direction', expected_direction,
                'magnitude_ppm',
                    (ARRAY[15000,30000])[expected_magnitude_index + 1],
                'execution_config_digest', expected_execution_config_digest
            )
        ) FROM 1 FOR 32);
        expected_case_specification_digest := mirror_demo_digest(
            'mirror.demo/D02GeometryCaseSpecification/v2',
            case_entry - ARRAY[
                'schema_version','case_ordinal','case_id','record_digest',
                'case_specification_digest'
            ]::text[]
        );
        IF case_entry -> 'case_ordinal' IS DISTINCT FROM to_jsonb(record_index + 1)
           OR case_entry ->> 'source_manifest_digest' IS DISTINCT FROM
              NEW.source_manifest_digest
           OR case_entry -> 'source_ordinal' IS DISTINCT FROM source_entry -> 'source_ordinal'
           OR case_entry ->> 'source_authority_key' IS DISTINCT FROM
              source_entry ->> 'source_authority_key'
           OR case_entry ->> 'source_admission_event_id' IS DISTINCT FROM
              source_entry ->> 'source_admission_event_id'
           OR case_entry ->> 'source_asset_id' IS DISTINCT FROM
              source_entry ->> 'source_asset_id'
           OR case_entry ->> 'source_asset_sha256' IS DISTINCT FROM
              source_entry ->> 'source_asset_sha256'
           OR case_entry ->> 'source_qa_snapshot_digest' IS DISTINCT FROM
              source_entry ->> 'source_qa_snapshot_digest'
           OR case_entry ->> 'source_measurement_projection_digest' IS DISTINCT FROM
              source_entry ->> 'source_measurement_projection_digest'
           OR case_entry ->> 'source_p2_candidate_manifest_content_digest'
              IS DISTINCT FROM
              source_entry ->> 'source_p2_candidate_manifest_content_digest'
           OR case_entry ->> 'dimension_authority_manifest_content_digest'
              IS DISTINCT FROM
              source_entry ->> 'dimension_authority_manifest_content_digest'
           OR case_entry ->> 'r2_source_authority_record_id' IS DISTINCT FROM
              source_entry ->> 'r2_source_authority_record_id'
           OR case_entry ->> 'geometry_ontology_version_digest' IS DISTINCT FROM
              measurement_config ->> 'geometry_ontology_version_digest'
           OR case_entry ->> 'dimension_key' IS DISTINCT FROM expected_dimension
           OR case_entry -> 'priority_index' IS DISTINCT FROM to_jsonb(expected_dimension_index + 1)
           OR case_entry ->> 'direction' IS DISTINCT FROM expected_direction
           OR case_entry -> 'direction_index' IS DISTINCT FROM
              to_jsonb(((record_index % 4) / 2) + 1)
           OR case_entry -> 'magnitude_ppm' IS DISTINCT FROM
              to_jsonb((ARRAY[15000,30000])[expected_magnitude_index + 1])
           OR case_entry -> 'magnitude_index' IS DISTINCT FROM
              to_jsonb(expected_magnitude_index + 1)
           OR case_entry -> 'ordered_control_dimensions' IS DISTINCT FROM
              to_jsonb(expected_control_dimensions)
           OR case_entry ->> 'runtime_manifest_digest' IS DISTINCT FROM
              NEW.runtime_manifest_digest
           OR mirror_demo_d02_json_string_matches(
                  case_entry -> 'warp_plan_digest', '^[0-9a-f]{64}$'
              ) IS NOT TRUE
           OR mirror_demo_d02_json_string_matches(
                  case_entry -> 'runtime_config_digest', '^[0-9a-f]{64}$'
              ) IS NOT TRUE
           OR mirror_demo_d02_json_string_matches(
                  case_entry -> 'geometry_algorithm_version',
                  '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'
              ) IS NOT TRUE
           OR mirror_demo_d02_json_string_matches(
                  case_entry -> 'output_policy_version',
                  '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'
              ) IS NOT TRUE
           OR mirror_demo_d02_json_string_matches(
                  case_entry -> 'determinism_level',
                  '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'
              ) IS NOT TRUE
           OR mirror_demo_d02_json_integer_between(
                  case_entry -> 'output_width', 1, 2147483647
              ) IS NOT TRUE
           OR mirror_demo_d02_json_integer_between(
                  case_entry -> 'output_height', 1, 2147483647
              ) IS NOT TRUE
           OR case_entry ->> 'execution_config_digest' IS DISTINCT FROM
              expected_execution_config_digest
           OR case_entry ->> 'case_id' IS DISTINCT FROM expected_case_id
           OR case_entry ->> 'case_specification_digest' IS DISTINCT FROM
              expected_case_specification_digest THEN
            RAISE EXCEPTION 'D02 R2 Report v3 Case projection is invalid';
        END IF;
    END LOOP;
    IF NEW.case_manifest_digest IS DISTINCT FROM mirror_demo_digest(
        'mirror.demo/D02GeometryCaseManifest/v2',
        payload -> 'ordered_case_manifest'
    ) OR (
        SELECT count(DISTINCT item.value ->> 'case_id')
        FROM jsonb_array_elements(payload -> 'ordered_case_manifest') AS item(value)
    ) IS DISTINCT FROM 48 OR (
        SELECT count(DISTINCT item.value ->> 'case_specification_digest')
        FROM jsonb_array_elements(payload -> 'ordered_case_manifest') AS item(value)
    ) IS DISTINCT FROM 48 THEN
        RAISE EXCEPTION 'D02 R2 Report v3 Case manifest digest is invalid';
    END IF;

    FOR record_index IN 0..11 LOOP
        source_entry := payload -> 'source_m3_repeat_evidence' -> record_index;
        expected_source_index := record_index / 3;
        PERFORM mirror_demo_d02_r2_require_mandatory_digest_leaves(
            source_entry,
            ARRAY[
                'source_authority_key','source_authority_digest','source_asset_sha256',
                'execution_receipt_digest','vision_model_manifest_digest',
                'runtime_manifest_digest','topology_digest','canonical_output_digest',
                'landmark_digest','measurement_observation_digest','record_digest'
            ],
            'SourceM3'
        );
        IF source_entry -> 'source_ordinal' IS DISTINCT FROM
              payload -> 'ordered_source_manifest' -> expected_source_index -> 'source_ordinal'
           OR source_entry ->> 'source_authority_key' IS DISTINCT FROM
              payload -> 'ordered_source_manifest' -> expected_source_index ->> 'source_authority_key'
           OR source_entry ->> 'source_authority_digest' IS DISTINCT FROM
              payload -> 'ordered_source_manifest' -> expected_source_index ->> 'source_authority_digest'
           OR source_entry -> 'repeat_index' IS DISTINCT FROM to_jsonb(record_index % 3 + 1) THEN
            RAISE EXCEPTION 'D02 R2 Report v3 SourceM3 order is invalid';
        END IF;
        PERFORM mirror_demo_validate_d02_r2_source_m3_v3(
            source_entry,
            payload -> 'ordered_source_manifest' -> expected_source_index,
            NEW.source_manifest_digest
        );
    END LOOP;
    IF (
        SELECT count(DISTINCT item.value ->> 'source_m3_record_id')
        FROM jsonb_array_elements(payload -> 'source_m3_repeat_evidence') AS item(value)
    ) IS DISTINCT FROM 12 OR (
        SELECT count(DISTINCT item.value ->> 'record_digest')
        FROM jsonb_array_elements(payload -> 'source_m3_repeat_evidence') AS item(value)
    ) IS DISTINCT FROM 12 THEN
        RAISE EXCEPTION 'D02 R2 Report v3 SourceM3 uniqueness is invalid';
    END IF;

    FOR record_index IN 0..95 LOOP
        m4_record := payload -> 'm4_repeat_evidence' -> record_index;
        case_entry := payload -> 'ordered_case_manifest' -> (record_index / 2);
        source_entry := payload -> 'ordered_source_manifest' ->
            ((case_entry ->> 'source_ordinal')::integer - 1);
        PERFORM mirror_demo_validate_d02_r2_m4_v2(
            m4_record, case_entry, source_entry, record_index % 2 + 1
        );
        first_m4_record := payload -> 'm4_repeat_evidence' ->
            ((record_index / 2) * 2);
        IF EXISTS (
            SELECT 1
            FROM unnest(ARRAY[
                'case_id','case_specification_digest','source_output_id',
                'source_asset_id','source_asset_sha256','result_output_id',
                'result_sha256','result_byte_size','result_mime_type',
                'result_width','result_height','changed_pixel_count',
                'warp_plan_digest','geometry_algorithm_version',
                'runtime_manifest_digest','runtime_config_digest','determinism_level'
            ]) AS deterministic_key
            WHERE m4_record -> deterministic_key IS DISTINCT FROM
                  first_m4_record -> deterministic_key
        ) THEN
            RAISE EXCEPTION 'D02 R2 Report v3 M4 replay pair is not deterministic';
        END IF;
    END LOOP;
    IF (
        SELECT count(DISTINCT item.value ->> 'm4_execution_record_id')
        FROM jsonb_array_elements(payload -> 'm4_repeat_evidence') AS item(value)
    ) IS DISTINCT FROM 96 OR (
        SELECT count(DISTINCT item.value ->> 'record_digest')
        FROM jsonb_array_elements(payload -> 'm4_repeat_evidence') AS item(value)
    ) IS DISTINCT FROM 96 THEN
        RAISE EXCEPTION 'D02 R2 Report v3 M4 uniqueness is invalid';
    END IF;

    FOR record_index IN 0..143 LOOP
        result_record := payload -> 'result_m3_repeat_evidence' -> record_index;
        case_entry := payload -> 'ordered_case_manifest' -> (record_index / 3);
        first_m4_record := payload -> 'm4_repeat_evidence' ->
            ((record_index / 3) * 2);
        PERFORM mirror_demo_validate_d02_r2_result_m3_v3(
            result_record, case_entry, first_m4_record, record_index % 3 + 1
        );
    END LOOP;
    IF (
        SELECT count(DISTINCT item.value ->> 'result_m3_record_id')
        FROM jsonb_array_elements(payload -> 'result_m3_repeat_evidence') AS item(value)
    ) IS DISTINCT FROM 144 OR (
        SELECT count(DISTINCT item.value ->> 'record_digest')
        FROM jsonb_array_elements(payload -> 'result_m3_repeat_evidence') AS item(value)
    ) IS DISTINCT FROM 144 THEN
        RAISE EXCEPTION 'D02 R2 Report v3 ResultM3 uniqueness is invalid';
    END IF;

    FOR record_index IN 0..47 LOOP
        case_entry := payload -> 'ordered_case_manifest' -> record_index;
        peer_case_entry := payload -> 'ordered_case_manifest' ->
            (CASE WHEN record_index % 2 = 0 THEN record_index + 1 ELSE record_index - 1 END);
        source_entry := payload -> 'ordered_source_manifest' ->
            ((case_entry ->> 'source_ordinal')::integer - 1);
        gate_record := payload -> 'measurement_gate_evidence' -> record_index;
        result_records := jsonb_build_array(
            payload -> 'result_m3_repeat_evidence' -> (record_index * 3),
            payload -> 'result_m3_repeat_evidence' -> (record_index * 3 + 1),
            payload -> 'result_m3_repeat_evidence' -> (record_index * 3 + 2)
        );
        PERFORM mirror_demo_validate_d02_r2_gate_v5(
            gate_record, case_entry, peer_case_entry, source_entry, result_records
        );

        source_entry := payload -> 'decode_structure_immutability_evidence' -> record_index;
        PERFORM mirror_demo_d02_r2_require_record(
            source_entry,
            'mirror.demo/D02DecodeStructureImmutabilityRecord/v2',
            ARRAY[
                'schema_version','case_id','case_specification_digest','source_asset_id',
                'source_asset_sha256','m4_execution_record_digests','result_output_id',
                'result_sha256','result_byte_size','result_mime_type','result_width',
                'result_height','result_image_record_id','source_decode_valid',
                'result_decode_valid','bounded_dimensions_passed','source_checksum_unchanged',
                'm4_replay_bytes_equal','m4_replay_dimensions_equal',
                'changed_pixel_count_equal','changed_pixel_count_positive',
                'immutable_result_binding_passed','exact_lineage_passed',
                'target_and_controls_complete','structure_gate_passed','record_digest'
            ]
        );
        IF source_entry ->> 'case_id' IS DISTINCT FROM case_entry ->> 'case_id'
           OR source_entry ->> 'case_specification_digest' IS DISTINCT FROM
              case_entry ->> 'case_specification_digest' THEN
            RAISE EXCEPTION 'D02 R2 Report v3 structure projection is invalid';
        END IF;

        source_entry := payload -> 'manual_review_evidence' -> record_index;
        PERFORM mirror_demo_d02_r2_require_record(
            source_entry,
            'mirror.demo/D02ManualArtifactDecision/v1',
            ARRAY[
                'schema_version','case_id','result_sha256','manual_review_version',
                'manual_review_policy_digest','decision_sequence','background_seam',
                'disconnected_contour','duplicated_feature','warp_tear','verdict',
                'review_authority_digest','manual_decision_digest'
            ],
            'manual_decision_digest'
        );
        SELECT value INTO manual_case_entry
        FROM jsonb_array_elements(payload -> 'ordered_case_manifest') AS cases(value)
        WHERE value ->> 'case_id' = source_entry ->> 'case_id';
        SELECT value INTO manual_structure_entry
        FROM jsonb_array_elements(
            payload -> 'decode_structure_immutability_evidence'
        ) AS structures(value)
        WHERE value ->> 'case_id' = source_entry ->> 'case_id';
        IF manual_case_entry IS NULL
           OR manual_structure_entry IS NULL
           OR source_entry ->> 'case_id' <= previous_manual_case_id
           OR source_entry -> 'decision_sequence' IS DISTINCT FROM to_jsonb(record_index + 1)
           OR source_entry ->> 'result_sha256' IS DISTINCT FROM
              manual_structure_entry ->> 'result_sha256'
           OR source_entry ->> 'manual_review_policy_digest' IS DISTINCT FROM
              NEW.manual_review_policy_digest THEN
            RAISE EXCEPTION 'D02 R2 Report v3 manual review projection is invalid';
        END IF;
        IF jsonb_typeof(source_entry -> 'background_seam') IS DISTINCT FROM 'boolean'
           OR jsonb_typeof(source_entry -> 'disconnected_contour') IS DISTINCT FROM 'boolean'
           OR jsonb_typeof(source_entry -> 'duplicated_feature') IS DISTINCT FROM 'boolean'
           OR jsonb_typeof(source_entry -> 'warp_tear') IS DISTINCT FROM 'boolean' THEN
            RAISE EXCEPTION 'D02 R2 Report v3 manual review verdict is invalid';
        END IF;
        expected_manual_verdict := CASE
            WHEN (source_entry ->> 'background_seam')::boolean
              OR (source_entry ->> 'disconnected_contour')::boolean
              OR (source_entry ->> 'duplicated_feature')::boolean
              OR (source_entry ->> 'warp_tear')::boolean
            THEN 'FAIL'
            ELSE 'PASS'
        END;
        IF source_entry ->> 'verdict' IS DISTINCT FROM expected_manual_verdict THEN
            RAISE EXCEPTION 'D02 R2 Report v3 manual review verdict is invalid';
        END IF;
        previous_manual_case_id := source_entry ->> 'case_id';
    END LOOP;

    FOR record_index IN 0..95 LOOP
        m4_record := payload -> 'm4_repeat_evidence' -> record_index;
        shadow_record := m4_record - 'record_digest';
        shadow_record := shadow_record || jsonb_build_object(
            'schema_version', 'mirror.demo/D02M4ExecutionRecord/v1'
        );
        shadow_record := shadow_record || jsonb_build_object(
            'record_digest', mirror_demo_digest(
                'mirror.demo/D02M4ExecutionRecord/v1',
                shadow_record - 'schema_version'
            )
        );
        shadow_m4_records := shadow_m4_records || jsonb_build_array(shadow_record);
    END LOOP;
    FOR record_index IN 0..47 LOOP
        gate_record := payload -> 'measurement_gate_evidence' -> record_index;
        shadow_record := gate_record - ARRAY[
            'schema_version','record_digest','result_repeat_certification',
            'result_repeat_certification_digest'
        ]::text[];
        shadow_record := jsonb_build_object(
            'schema_version', 'mirror.demo/D02MeasurementGateRecord/v3'
        ) || shadow_record;
        shadow_record := shadow_record || jsonb_build_object(
            'record_digest', mirror_demo_digest(
                'mirror.demo/D02MeasurementGateRecord/v3',
                shadow_record - 'schema_version'
            )
        );
        shadow_gate_records := shadow_gate_records || jsonb_build_array(shadow_record);

        source_record := payload -> 'decode_structure_immutability_evidence' ->
            record_index;
        shadow_record := source_record - 'record_digest';
        shadow_record := shadow_record || jsonb_build_object(
            'schema_version', 'mirror.demo/D02DecodeStructureImmutabilityRecord/v1',
            'm4_execution_record_digests', jsonb_build_array(
                shadow_m4_records -> (record_index * 2) -> 'record_digest',
                shadow_m4_records -> (record_index * 2 + 1) -> 'record_digest'
            )
        );
        shadow_record := shadow_record || jsonb_build_object(
            'record_digest', mirror_demo_digest(
                'mirror.demo/D02DecodeStructureImmutabilityRecord/v1',
                shadow_record - 'schema_version'
            )
        );
        shadow_structure_records :=
            shadow_structure_records || jsonb_build_array(shadow_record);

        source_record := payload -> 'manual_review_evidence' -> record_index;
        IF source_record IS NULL THEN
            RAISE EXCEPTION 'D02 R2 Report v3 manual shadow binding is incomplete';
        END IF;
        shadow_record := source_record - 'manual_decision_digest';
        shadow_record := shadow_record || jsonb_build_object(
            'decision_sequence', record_index + 1
        );
        shadow_record := shadow_record || jsonb_build_object(
            'manual_decision_digest', mirror_demo_digest(
                'mirror.demo/D02ManualArtifactDecision/v1',
                shadow_record - 'schema_version'
            )
        );
        shadow_manual_records := shadow_manual_records || jsonb_build_array(shadow_record);
    END LOOP;
    shadow_row := NEW;
    shadow_row.report_payload := jsonb_set(
        jsonb_set(
            jsonb_set(
                jsonb_set(
                    payload,
                    ARRAY['m4_repeat_evidence'], shadow_m4_records, false
                ),
                ARRAY['measurement_gate_evidence'], shadow_gate_records, false
            ),
            ARRAY['decode_structure_immutability_evidence'],
            shadow_structure_records,
            false
        ),
        ARRAY['manual_review_evidence'], shadow_manual_records, false
    );
    PERFORM mirror_demo_validate_d02_measurements_v9(shadow_row);

    IF mirror_demo_jsonb_exact_keys(
        exact_duplicate,
        ARRAY[
            'schema_version','image_records','all_record_sha_unique','source_sha_unique',
            'result_sha_unique','source_result_sha_disjoint','exact_sha_gate_passed'
        ]
    ) IS NOT TRUE
       OR exact_duplicate ->> 'schema_version' IS DISTINCT FROM
          'mirror.demo/D02ExactDuplicateEvidence/v2'
       OR jsonb_typeof(exact_duplicate -> 'image_records') IS DISTINCT FROM 'array'
       OR jsonb_array_length(exact_duplicate -> 'image_records') IS DISTINCT FROM 52 THEN
        RAISE EXCEPTION 'D02 R2 Report v3 exact duplicate evidence is invalid';
    END IF;
    FOR record_index IN 0..51 LOOP
        image_entry := exact_duplicate -> 'image_records' -> record_index;
        IF image_entry ->> 'schema_version' = 'mirror.demo/D02SourceImageAuthorityRecord/v3' THEN
            PERFORM mirror_demo_d02_r2_require_record(
                image_entry,
                'mirror.demo/D02SourceImageAuthorityRecord/v3',
                ARRAY[
                    'schema_version','image_record_ordinal','image_record_id','authority_role',
                    'source_ordinal','source_authority_key','source_admission_event_id',
                    'source_asset_id','sha256','byte_size','mime_type','width','height',
                    'image_record_digest'
                ],
                'image_record_digest'
            );
        ELSIF image_entry ->> 'schema_version' = 'mirror.demo/D02ResultImageAuthorityRecord/v3' THEN
            PERFORM mirror_demo_d02_r2_require_record(
                image_entry,
                'mirror.demo/D02ResultImageAuthorityRecord/v3',
                ARRAY[
                    'schema_version','image_record_ordinal','image_record_id','authority_role',
                    'source_ordinal','source_authority_key','source_admission_event_id','case_id',
                    'case_specification_digest','result_output_id',
                    'deterministic_result_asset_id','sha256','byte_size','mime_type','width',
                    'height','image_record_digest'
                ],
                'image_record_digest'
            );
        ELSE
            RAISE EXCEPTION 'D02 R2 Report v3 image record schema is invalid';
        END IF;
        IF image_entry ->> 'authority_role' = 'SOURCE' THEN
            IF mirror_demo_d02_json_integer_between(
                image_entry -> 'source_ordinal', 1, 4
            ) IS NOT TRUE THEN
                RAISE EXCEPTION 'D02 R2 Report v3 source image ordinal is invalid';
            END IF;
            source_entry := payload -> 'ordered_source_manifest' ->
                ((image_entry ->> 'source_ordinal')::integer - 1);
            expected_id := substring(mirror_demo_digest(
                'mirror.demo/D02SourceImageAuthorityRecordId/v2',
                jsonb_build_object(
                    'authority_role', 'SOURCE',
                    'source_authority_key', source_entry ->> 'source_authority_key',
                    'source_admission_event_id',
                        source_entry ->> 'source_admission_event_id',
                    'source_asset_id', source_entry ->> 'source_asset_id',
                    'sha256', source_entry ->> 'source_asset_sha256'
                )
            ) FROM 1 FOR 32);
            IF image_entry ->> 'image_record_id' IS DISTINCT FROM expected_id
               OR image_entry ->> 'source_authority_key' IS DISTINCT FROM
                  source_entry ->> 'source_authority_key'
               OR image_entry ->> 'source_admission_event_id' IS DISTINCT FROM
                  source_entry ->> 'source_admission_event_id'
               OR image_entry ->> 'source_asset_id' IS DISTINCT FROM
                  source_entry ->> 'source_asset_id'
               OR image_entry ->> 'sha256' IS DISTINCT FROM
                  source_entry ->> 'source_asset_sha256'
               OR image_entry -> 'byte_size' IS DISTINCT FROM
                  source_entry -> 'source_asset_byte_size'
               OR image_entry -> 'mime_type' IS DISTINCT FROM
                  source_entry -> 'source_asset_mime_type'
               OR image_entry -> 'width' IS DISTINCT FROM source_entry -> 'source_asset_width'
               OR image_entry -> 'height' IS DISTINCT FROM
                  source_entry -> 'source_asset_height' THEN
                RAISE EXCEPTION 'D02 R2 Report v3 source image authority is invalid';
            END IF;
        ELSE
            SELECT item.value, (item.ordinality - 1)::integer
            INTO case_entry, expected_case_index
            FROM jsonb_array_elements(payload -> 'ordered_case_manifest')
                 WITH ORDINALITY AS item(value, ordinality)
            WHERE item.value ->> 'case_id' = image_entry ->> 'case_id';
            IF case_entry IS NULL THEN
                RAISE EXCEPTION 'D02 R2 Report v3 result image case is missing';
            END IF;
            source_entry := payload -> 'ordered_source_manifest' ->
                ((case_entry ->> 'source_ordinal')::integer - 1);
            first_m4_record := payload -> 'm4_repeat_evidence' ->
                (expected_case_index * 2);
            expected_result_asset_id := substring(mirror_demo_digest(
                'mirror.demo/D02ImportedAssetId/v1',
                jsonb_build_object(
                    'asset_role', 'synthetic',
                    'semantic_role', 'SELECTED_RESULT',
                    'sha256', first_m4_record ->> 'result_sha256',
                    'byte_size', (first_m4_record ->> 'result_byte_size')::bigint,
                    'mime_type', first_m4_record ->> 'result_mime_type',
                    'width', (first_m4_record ->> 'result_width')::integer,
                    'height', (first_m4_record ->> 'result_height')::integer
                )
            ) FROM 1 FOR 32);
            expected_id := substring(mirror_demo_digest(
                'mirror.demo/D02ResultImageAuthorityRecordId/v2',
                jsonb_build_object(
                    'authority_role', 'RESULT',
                    'source_authority_key', source_entry ->> 'source_authority_key',
                    'source_admission_event_id',
                        source_entry ->> 'source_admission_event_id',
                    'case_id', case_entry ->> 'case_id',
                    'case_specification_digest',
                        case_entry ->> 'case_specification_digest',
                    'result_output_id', first_m4_record ->> 'result_output_id',
                    'deterministic_result_asset_id', expected_result_asset_id,
                    'sha256', first_m4_record ->> 'result_sha256'
                )
            ) FROM 1 FOR 32);
            IF image_entry ->> 'image_record_id' IS DISTINCT FROM expected_id
               OR image_entry -> 'source_ordinal' IS DISTINCT FROM
                  case_entry -> 'source_ordinal'
               OR image_entry ->> 'source_authority_key' IS DISTINCT FROM
                  source_entry ->> 'source_authority_key'
               OR image_entry ->> 'source_admission_event_id' IS DISTINCT FROM
                  source_entry ->> 'source_admission_event_id'
               OR image_entry ->> 'case_specification_digest' IS DISTINCT FROM
                  case_entry ->> 'case_specification_digest'
               OR image_entry ->> 'result_output_id' IS DISTINCT FROM
                  first_m4_record ->> 'result_output_id'
               OR image_entry ->> 'deterministic_result_asset_id' IS DISTINCT FROM
                  expected_result_asset_id
               OR image_entry ->> 'sha256' IS DISTINCT FROM
                  first_m4_record ->> 'result_sha256'
               OR image_entry -> 'byte_size' IS DISTINCT FROM
                  first_m4_record -> 'result_byte_size'
               OR image_entry -> 'mime_type' IS DISTINCT FROM
                  first_m4_record -> 'result_mime_type'
               OR image_entry -> 'width' IS DISTINCT FROM
                  first_m4_record -> 'result_width'
               OR image_entry -> 'height' IS DISTINCT FROM
                  first_m4_record -> 'result_height' THEN
                RAISE EXCEPTION 'D02 R2 Report v3 result image authority is invalid';
            END IF;
        END IF;
        IF image_entry -> 'image_record_ordinal' IS DISTINCT FROM to_jsonb(record_index + 1)
           OR mirror_demo_d02_json_string_matches(
                  image_entry -> 'image_record_id', '^[0-9a-f]{32}$'
              ) IS NOT TRUE
           OR mirror_demo_d02_json_string_matches(
                  image_entry -> 'sha256', '^[0-9a-f]{64}$'
              ) IS NOT TRUE
           OR mirror_demo_d02_json_integer_between(
                  image_entry -> 'byte_size', 1, 9223372036854775807
              ) IS NOT TRUE
           OR image_entry ->> 'mime_type' IS DISTINCT FROM 'image/jpeg'
           OR mirror_demo_d02_json_integer_between(
                  image_entry -> 'width', 1, 2147483647
              ) IS NOT TRUE
           OR mirror_demo_d02_json_integer_between(
                  image_entry -> 'height', 1, 2147483647
              ) IS NOT TRUE
           OR NOT EXISTS (
               SELECT 1 FROM assets asset_row
               WHERE asset_row.id = COALESCE(
                         image_entry ->> 'source_asset_id',
                         image_entry ->> 'deterministic_result_asset_id'
                     )
                 AND asset_row.sha256 = image_entry ->> 'sha256'
                 AND asset_row.byte_size = (image_entry ->> 'byte_size')::bigint
                 AND asset_row.mime_type = image_entry ->> 'mime_type'
                 AND asset_row.width = (image_entry ->> 'width')::integer
                 AND asset_row.height = (image_entry ->> 'height')::integer
                 AND asset_row.owner_user_id IS NULL
                 AND asset_row.asset_role = 'synthetic'
                 AND asset_row.internal_purpose = 'synthetic_dataset'
                 AND asset_row.synthetic IS TRUE
                 AND asset_row.deleted_at IS NULL
        ) THEN
            RAISE EXCEPTION 'D02 R2 Report v3 image Asset projection is invalid';
        END IF;
        IF record_index > 0 THEN
            prior_image_entry := exact_duplicate -> 'image_records' -> (record_index - 1);
            IF (prior_image_entry ->> 'sha256', prior_image_entry ->> 'image_record_id') >=
               (image_entry ->> 'sha256', image_entry ->> 'image_record_id') THEN
                RAISE EXCEPTION 'D02 R2 Report v3 image order is invalid';
            END IF;
        END IF;
    END LOOP;
    IF (
        SELECT count(*)
        FROM jsonb_array_elements(exact_duplicate -> 'image_records') AS item(value)
        WHERE item.value ->> 'authority_role' = 'SOURCE'
    ) IS DISTINCT FROM 4 OR (
        SELECT count(*)
        FROM jsonb_array_elements(exact_duplicate -> 'image_records') AS item(value)
        WHERE item.value ->> 'authority_role' = 'RESULT'
    ) IS DISTINCT FROM 48 THEN
        RAISE EXCEPTION 'D02 R2 Report v3 image role cardinality is invalid';
    END IF;
    SELECT
        count(DISTINCT item.value ->> 'sha256') = 52,
        count(DISTINCT item.value ->> 'sha256') FILTER (
            WHERE item.value ->> 'authority_role' = 'SOURCE'
        ) = 4,
        count(DISTINCT item.value ->> 'sha256') FILTER (
            WHERE item.value ->> 'authority_role' = 'RESULT'
        ) = 48,
        NOT EXISTS (
            SELECT 1
            FROM jsonb_array_elements(exact_duplicate -> 'image_records') source_item(value)
            JOIN jsonb_array_elements(exact_duplicate -> 'image_records') result_item(value)
              ON source_item.value ->> 'sha256' = result_item.value ->> 'sha256'
            WHERE source_item.value ->> 'authority_role' = 'SOURCE'
              AND result_item.value ->> 'authority_role' = 'RESULT'
        )
    INTO duplicate_all_unique, duplicate_source_unique, duplicate_result_unique,
         duplicate_disjoint
    FROM jsonb_array_elements(exact_duplicate -> 'image_records') item(value);
    IF exact_duplicate -> 'all_record_sha_unique' IS DISTINCT FROM to_jsonb(duplicate_all_unique)
       OR exact_duplicate -> 'source_sha_unique' IS DISTINCT FROM to_jsonb(duplicate_source_unique)
       OR exact_duplicate -> 'result_sha_unique' IS DISTINCT FROM to_jsonb(duplicate_result_unique)
       OR exact_duplicate -> 'source_result_sha_disjoint' IS DISTINCT FROM
          to_jsonb(duplicate_disjoint)
       OR exact_duplicate -> 'exact_sha_gate_passed' IS DISTINCT FROM
          to_jsonb(
              duplicate_all_unique AND duplicate_source_unique
              AND duplicate_result_unique AND duplicate_disjoint
          ) THEN
        RAISE EXCEPTION 'D02 R2 Report v3 exact SHA Gate does not replay';
    END IF;

    IF mirror_demo_jsonb_exact_keys(
        phash_evidence,
        ARRAY[
            'schema_version','implementation_digest','bit_width','threshold_policy',
            'ordered_record_signatures','comparisons'
        ]
    ) IS NOT TRUE
       OR phash_evidence ->> 'schema_version' IS DISTINCT FROM
          'mirror.demo/D02PHashObservationEvidence/v2'
       OR phash_evidence ->> 'implementation_digest' IS DISTINCT FROM
          NEW.phash_implementation_digest
       OR phash_evidence -> 'bit_width' IS DISTINCT FROM '64'::jsonb
       OR jsonb_typeof(phash_evidence -> 'ordered_record_signatures')
          IS DISTINCT FROM 'array'
       OR jsonb_array_length(phash_evidence -> 'ordered_record_signatures')
          IS DISTINCT FROM 52
       OR jsonb_typeof(phash_evidence -> 'comparisons') IS DISTINCT FROM 'array'
       OR jsonb_array_length(phash_evidence -> 'comparisons') IS DISTINCT FROM 1326 THEN
        RAISE EXCEPTION 'D02 R2 Report v3 pHash envelope is invalid';
    END IF;
    FOR record_index IN 0..51 LOOP
        signature_entry := phash_evidence -> 'ordered_record_signatures' -> record_index;
        PERFORM mirror_demo_d02_r2_require_record(
            signature_entry,
            'mirror.demo/D02PHashSignatureRecord/v1',
            ARRAY[
                'schema_version','image_record_ordinal','image_record_id','image_record_digest',
                'image_sha256','phash_hex','signature_digest'
            ],
            'signature_digest'
        );
        image_entry := exact_duplicate -> 'image_records' -> record_index;
        IF signature_entry -> 'image_record_ordinal' IS DISTINCT FROM to_jsonb(record_index + 1)
           OR signature_entry ->> 'image_record_id' IS DISTINCT FROM
              image_entry ->> 'image_record_id'
           OR signature_entry ->> 'image_record_digest' IS DISTINCT FROM
              image_entry ->> 'image_record_digest'
           OR signature_entry ->> 'image_sha256' IS DISTINCT FROM
              image_entry ->> 'sha256'
           OR mirror_demo_d02_json_string_matches(
                  signature_entry -> 'phash_hex', '^[0-9a-f]{16}$'
              ) IS NOT TRUE THEN
            RAISE EXCEPTION 'D02 R2 Report v3 pHash signature projection is invalid';
        END IF;
    END LOOP;
    FOR left_image_index IN 0..50 LOOP
        FOR right_image_index IN (left_image_index + 1)..51 LOOP
            comparison_index := comparison_index + 1;
            comparison_entry := phash_evidence -> 'comparisons' ->
                (comparison_index - 1);
            left_side := phash_evidence -> 'ordered_record_signatures' -> left_image_index;
            right_side := phash_evidence -> 'ordered_record_signatures' -> right_image_index;
            PERFORM mirror_demo_d02_r2_require_record(
                comparison_entry,
                'mirror.demo/D02PHashComparisonRecord/v1',
                ARRAY[
                    'schema_version','comparison_ordinal','left_image_record_ordinal',
                    'left_image_record_id','left_signature_digest',
                    'right_image_record_ordinal','right_image_record_id',
                    'right_signature_digest','hamming_distance','comparison_digest'
                ],
                'comparison_digest'
            );
            IF comparison_entry -> 'comparison_ordinal' IS DISTINCT FROM
                  to_jsonb(comparison_index)
               OR comparison_entry -> 'left_image_record_ordinal' IS DISTINCT FROM
                  to_jsonb(left_image_index + 1)
               OR comparison_entry ->> 'left_image_record_id' IS DISTINCT FROM
                  left_side ->> 'image_record_id'
               OR comparison_entry ->> 'left_signature_digest' IS DISTINCT FROM
                  left_side ->> 'signature_digest'
               OR comparison_entry -> 'right_image_record_ordinal' IS DISTINCT FROM
                  to_jsonb(right_image_index + 1)
               OR comparison_entry ->> 'right_image_record_id' IS DISTINCT FROM
                  right_side ->> 'image_record_id'
               OR comparison_entry ->> 'right_signature_digest' IS DISTINCT FROM
                  right_side ->> 'signature_digest'
               OR mirror_demo_d02_json_integer_between(
                      comparison_entry -> 'hamming_distance', 0, 64
                  ) IS NOT TRUE
               OR (comparison_entry ->> 'hamming_distance')::integer IS DISTINCT FROM
                  mirror_demo_d02_hamming64(
                      left_side ->> 'phash_hex', right_side ->> 'phash_hex'
                  ) THEN
                RAISE EXCEPTION 'D02 R2 Report v3 pHash comparison projection is invalid';
            END IF;
        END LOOP;
    END LOOP;

    FOR record_index IN 0..23 LOOP
        pair_wrapper := payload -> 'pair_quality_evidence' -> record_index;
        pair_payload := pair_wrapper -> 'pair_screening_record_payload';
        IF mirror_demo_jsonb_exact_keys(
            pair_wrapper,
            ARRAY['schema_version','pair_screening_record_payload','pair_screening_record_digest']
        ) IS NOT TRUE
           OR pair_wrapper ->> 'schema_version' IS DISTINCT FROM
              'mirror.demo/D02PairScreeningRecord/v4'
           OR jsonb_typeof(pair_payload) IS DISTINCT FROM 'object'
           OR mirror_demo_jsonb_exact_keys(
              pair_payload,
              ARRAY[
                  'pair_record_id','source_ordinal','source_authority_key',
                  'source_admission_event_id','source_asset_id','source_asset_sha256',
                  'dimension_key','priority_index','magnitude_ppm','screening_policy_digest',
                  'left','right','same_source_gate_passed','opposed_direction_gate_passed',
                  'equal_magnitude_gate_passed','pair_side_gates_passed',
                  'empty_lock_policy_gate_passed','pair_quality_state','pair_quality_ppm',
                  'lock_conclusion','lock_policy_digest','pair_gate_passed'
              ]
           ) IS NOT TRUE
           OR pair_wrapper ->> 'pair_screening_record_digest' IS DISTINCT FROM
              mirror_demo_digest('mirror.demo/D02PairScreeningRecord/v4', pair_payload) THEN
            RAISE EXCEPTION 'D02 R2 Report v3 pair wrapper or payload is invalid';
        END IF;
        expected_source_index := record_index / 6;
        expected_dimension_index := (record_index % 6) / 2;
        expected_magnitude_index := record_index % 2;
        left_case_index := expected_source_index * 12 + expected_dimension_index * 4 +
            expected_magnitude_index;
        right_case_index := left_case_index + 2;
        source_entry := payload -> 'ordered_source_manifest' -> expected_source_index;
        left_case := payload -> 'ordered_case_manifest' -> left_case_index;
        right_case := payload -> 'ordered_case_manifest' -> right_case_index;
        left_side := pair_payload -> 'left';
        right_side := pair_payload -> 'right';
        PERFORM mirror_demo_validate_d02_pair_side_v9(
            NEW, left_side, left_case_index, 'DECREASE'
        );
        PERFORM mirror_demo_validate_d02_pair_side_v9(
            NEW, right_side, right_case_index, 'INCREASE'
        );
        expected_id := substring(mirror_demo_digest(
            'mirror.demo/D02PairScreeningRecordId/v2',
            jsonb_build_object(
                'source_authority_key', source_entry ->> 'source_authority_key',
                'source_admission_event_id', source_entry ->> 'source_admission_event_id',
                'source_asset_sha256', source_entry ->> 'source_asset_sha256',
                'dimension_key', candidate_dimensions[expected_dimension_index + 1],
                'priority_index', expected_dimension_index + 1,
                'magnitude_ppm', (ARRAY[15000,30000])[expected_magnitude_index + 1],
                'left_case_id', left_case ->> 'case_id',
                'right_case_id', right_case ->> 'case_id',
                'screening_policy_digest', NEW.screening_policy_digest,
                'lock_policy_digest', mirror_demo_d02_expected_lock_policy_digest()
            )
        ) FROM 1 FOR 32);
        expected_side_gate := (left_side ->> 'side_gate_passed')::boolean
            AND (right_side ->> 'side_gate_passed')::boolean;
        expected_pair_gate := expected_side_gate;
        expected_quality := CASE WHEN expected_pair_gate THEN least(
            (left_side ->> 'side_quality_component_ppm')::integer,
            (right_side ->> 'side_quality_component_ppm')::integer
        ) ELSE 0 END;
        IF pair_payload ->> 'pair_record_id' IS DISTINCT FROM expected_id
           OR pair_payload -> 'source_ordinal' IS DISTINCT FROM
              to_jsonb(expected_source_index + 1)
           OR pair_payload ->> 'source_authority_key' IS DISTINCT FROM
              source_entry ->> 'source_authority_key'
           OR pair_payload ->> 'source_admission_event_id' IS DISTINCT FROM
              source_entry ->> 'source_admission_event_id'
           OR pair_payload ->> 'source_asset_id' IS DISTINCT FROM
              source_entry ->> 'source_asset_id'
           OR pair_payload ->> 'source_asset_sha256' IS DISTINCT FROM
              source_entry ->> 'source_asset_sha256'
           OR pair_payload ->> 'dimension_key' IS DISTINCT FROM
              candidate_dimensions[expected_dimension_index + 1]
           OR pair_payload -> 'priority_index' IS DISTINCT FROM
              to_jsonb(expected_dimension_index + 1)
           OR pair_payload -> 'magnitude_ppm' IS DISTINCT FROM
              to_jsonb((ARRAY[15000,30000])[expected_magnitude_index + 1])
           OR pair_payload ->> 'screening_policy_digest' IS DISTINCT FROM
              NEW.screening_policy_digest
           OR pair_payload ->> 'lock_policy_digest' IS DISTINCT FROM
              mirror_demo_d02_expected_lock_policy_digest()
           OR pair_payload ->> 'lock_conclusion' IS DISTINCT FROM
              'PASS_FOR_FROZEN_EMPTY_NEUTRAL_POLICY_ONLY'
           OR EXISTS (
              SELECT 1 FROM unnest(ARRAY[
                  'same_source_gate_passed','opposed_direction_gate_passed',
                  'equal_magnitude_gate_passed','pair_side_gates_passed',
                  'empty_lock_policy_gate_passed','pair_gate_passed'
              ]) AS boolean_key
              WHERE mirror_demo_d02_json_boolean(pair_payload -> boolean_key) IS NOT TRUE
           )
           OR (pair_payload ->> 'same_source_gate_passed')::boolean IS DISTINCT FROM true
           OR (pair_payload ->> 'opposed_direction_gate_passed')::boolean IS DISTINCT FROM true
           OR (pair_payload ->> 'equal_magnitude_gate_passed')::boolean IS DISTINCT FROM true
           OR (pair_payload ->> 'pair_side_gates_passed')::boolean IS DISTINCT FROM
              expected_side_gate
           OR (pair_payload ->> 'empty_lock_policy_gate_passed')::boolean IS DISTINCT FROM true
           OR (pair_payload ->> 'pair_gate_passed')::boolean IS DISTINCT FROM
              expected_pair_gate
           OR pair_payload ->> 'pair_quality_state' IS DISTINCT FROM (
              CASE WHEN expected_pair_gate
                  THEN 'COMPUTED'
                  ELSE 'NOT_COMPUTED_GATE_FAILED'
              END
           )
           OR mirror_demo_d02_json_integer_between(
              pair_payload -> 'pair_quality_ppm', expected_quality, expected_quality
           ) IS NOT TRUE THEN
            RAISE EXCEPTION 'D02 R2 Report v3 pair Gate or quality is invalid';
        END IF;
    END LOOP;

    expected_exact_sha := (exact_duplicate ->> 'exact_sha_gate_passed')::boolean;
    eligible_dimensions := '[]'::jsonb;
    FOR record_index IN 0..2 LOOP
        expected_dimension := candidate_dimensions[record_index + 1];
        dimension_entry := payload -> 'dimension_eligibility' -> record_index;
        expected_pair_digests := '[]'::jsonb;
        expected_side_digests := '[]'::jsonb;
        expected_side_entries := '[]'::jsonb;
        expected_pair_entries := '[]'::jsonb;
        expected_all_side := true;
        expected_all_pair := true;
        expected_all_manual := true;
        expected_all_lock := true;
        FOR source_index IN 0..3 LOOP
            FOR expected_magnitude_index IN 0..1 LOOP
                pair_index := source_index * 6 + record_index * 2 +
                    expected_magnitude_index;
                pair_wrapper := payload -> 'pair_quality_evidence' -> pair_index;
                pair_payload := pair_wrapper -> 'pair_screening_record_payload';
                left_side := pair_payload -> 'left';
                right_side := pair_payload -> 'right';
                expected_pair_digests := expected_pair_digests || jsonb_build_array(
                    pair_wrapper -> 'pair_screening_record_digest'
                );
                expected_side_digests := expected_side_digests ||
                    jsonb_build_array(left_side -> 'automated_gate_digest') ||
                    jsonb_build_array(right_side -> 'automated_gate_digest');
                expected_side_entries := expected_side_entries || jsonb_build_array(
                    jsonb_build_object(
                        'schema_version', 'mirror.demo/D02DimensionSideGateEntry/v1',
                        'source_ordinal', source_index + 1,
                        'magnitude_ppm',
                            (ARRAY[15000,30000])[expected_magnitude_index + 1],
                        'side', 'LEFT',
                        'case_id', left_side ->> 'case_id',
                        'automated_gate_digest', left_side ->> 'automated_gate_digest',
                        'manual_decision_digest', left_side ->> 'manual_decision_digest',
                        'automated_gate_passed',
                            (left_side ->> 'automated_gate_passed')::boolean,
                        'manual_gate_passed', (left_side ->> 'manual_gate_passed')::boolean,
                        'side_gate_passed', (left_side ->> 'side_gate_passed')::boolean
                    ),
                    jsonb_build_object(
                        'schema_version', 'mirror.demo/D02DimensionSideGateEntry/v1',
                        'source_ordinal', source_index + 1,
                        'magnitude_ppm',
                            (ARRAY[15000,30000])[expected_magnitude_index + 1],
                        'side', 'RIGHT',
                        'case_id', right_side ->> 'case_id',
                        'automated_gate_digest', right_side ->> 'automated_gate_digest',
                        'manual_decision_digest', right_side ->> 'manual_decision_digest',
                        'automated_gate_passed',
                            (right_side ->> 'automated_gate_passed')::boolean,
                        'manual_gate_passed', (right_side ->> 'manual_gate_passed')::boolean,
                        'side_gate_passed', (right_side ->> 'side_gate_passed')::boolean
                    )
                );
                expected_pair_entries := expected_pair_entries || jsonb_build_array(
                    jsonb_build_object(
                        'schema_version', 'mirror.demo/D02DimensionPairGateEntry/v1',
                        'source_ordinal', source_index + 1,
                        'magnitude_ppm',
                            (ARRAY[15000,30000])[expected_magnitude_index + 1],
                        'pair_record_id', pair_payload ->> 'pair_record_id',
                        'pair_screening_record_digest',
                            pair_wrapper ->> 'pair_screening_record_digest',
                        'pair_gate_passed', (pair_payload ->> 'pair_gate_passed')::boolean
                    )
                );
                expected_all_side := expected_all_side
                    AND (left_side ->> 'side_gate_passed')::boolean
                    AND (right_side ->> 'side_gate_passed')::boolean;
                expected_all_pair := expected_all_pair
                    AND (pair_payload ->> 'pair_gate_passed')::boolean;
                expected_all_manual := expected_all_manual
                    AND (left_side ->> 'manual_gate_passed')::boolean
                    AND (right_side ->> 'manual_gate_passed')::boolean;
                expected_all_lock := expected_all_lock
                    AND (pair_payload ->> 'empty_lock_policy_gate_passed')::boolean;
            END LOOP;
        END LOOP;
        PERFORM mirror_demo_d02_r2_require_record(
            dimension_entry,
            'mirror.demo/D02DimensionEligibilityRecord/v4',
            ARRAY[
                'schema_version','dimension_key','priority_index',
                'ordered_pair_screening_record_digests',
                'ordered_side_automated_gate_digests','sixteen_side_gate_digest',
                'eight_pair_gate_digest','all_sixteen_side_gates_passed',
                'all_eight_pair_gates_passed','all_manual_gates_passed',
                'global_exact_sha_gate_passed','empty_lock_policy_gate_passed',
                'eligible','failure_reasons','record_digest'
            ]
        );
        expected_eligible := expected_all_side AND expected_all_pair
            AND expected_all_manual AND expected_exact_sha AND expected_all_lock;
        expected_failure_reasons := '[]'::jsonb;
        IF NOT expected_all_side THEN
            expected_failure_reasons := expected_failure_reasons ||
                jsonb_build_array(failure_reason_order[1]);
        END IF;
        IF NOT expected_all_pair THEN
            expected_failure_reasons := expected_failure_reasons ||
                jsonb_build_array(failure_reason_order[2]);
        END IF;
        IF NOT expected_all_manual THEN
            expected_failure_reasons := expected_failure_reasons ||
                jsonb_build_array(failure_reason_order[3]);
        END IF;
        IF NOT expected_exact_sha THEN
            expected_failure_reasons := expected_failure_reasons ||
                jsonb_build_array(failure_reason_order[4]);
        END IF;
        IF NOT expected_all_lock THEN
            expected_failure_reasons := expected_failure_reasons ||
                jsonb_build_array(failure_reason_order[5]);
        END IF;
        IF dimension_entry ->> 'dimension_key' IS DISTINCT FROM expected_dimension
           OR dimension_entry -> 'priority_index' IS DISTINCT FROM to_jsonb(record_index + 1)
           OR dimension_entry -> 'ordered_pair_screening_record_digests' IS DISTINCT FROM
              expected_pair_digests
           OR dimension_entry -> 'ordered_side_automated_gate_digests' IS DISTINCT FROM
              expected_side_digests
           OR dimension_entry ->> 'sixteen_side_gate_digest' IS DISTINCT FROM
              mirror_demo_digest(
              'mirror.demo/D02SixteenSideGate/v1',
              jsonb_build_object(
                  'dimension_key', expected_dimension,
                  'priority_index', record_index + 1,
                  'ordered_side_gate_entries', expected_side_entries
              )
           )
           OR dimension_entry ->> 'eight_pair_gate_digest' IS DISTINCT FROM
              mirror_demo_digest(
              'mirror.demo/D02EightPairGate/v1',
              jsonb_build_object(
                  'dimension_key', expected_dimension,
                  'priority_index', record_index + 1,
                  'ordered_pair_gate_entries', expected_pair_entries
              )
           )
           OR EXISTS (
              SELECT 1 FROM unnest(ARRAY[
                  'all_sixteen_side_gates_passed','all_eight_pair_gates_passed',
                  'all_manual_gates_passed','global_exact_sha_gate_passed',
                  'empty_lock_policy_gate_passed','eligible'
              ]) AS boolean_key
              WHERE mirror_demo_d02_json_boolean(dimension_entry -> boolean_key)
                    IS NOT TRUE
           )
           OR (dimension_entry ->> 'all_sixteen_side_gates_passed')::boolean
              IS DISTINCT FROM expected_all_side
           OR (dimension_entry ->> 'all_eight_pair_gates_passed')::boolean
              IS DISTINCT FROM expected_all_pair
           OR (dimension_entry ->> 'all_manual_gates_passed')::boolean
              IS DISTINCT FROM expected_all_manual
           OR (dimension_entry ->> 'global_exact_sha_gate_passed')::boolean
              IS DISTINCT FROM expected_exact_sha
           OR (dimension_entry ->> 'empty_lock_policy_gate_passed')::boolean
              IS DISTINCT FROM expected_all_lock
           OR (dimension_entry ->> 'eligible')::boolean IS DISTINCT FROM expected_eligible
           OR dimension_entry -> 'failure_reasons' IS DISTINCT FROM
              expected_failure_reasons THEN
            RAISE EXCEPTION 'D02 R2 Report v3 dimension eligibility is invalid';
        END IF;
        IF expected_eligible THEN
            eligible_count := eligible_count + 1;
            eligible_dimensions := eligible_dimensions || jsonb_build_array(expected_dimension);
        END IF;
    END LOOP;

    selected_dimensions := CASE WHEN eligible_count >= 2 THEN
        jsonb_build_array(eligible_dimensions -> 0, eligible_dimensions -> 1)
        ELSE '[]'::jsonb END;
    FOR record_index IN 0..2 LOOP
        dimension_entry := payload -> 'dimension_eligibility' -> record_index;
        selection_entry := payload -> 'fixed_priority_selection_trace' -> record_index;
        expected_eligible := (dimension_entry ->> 'eligible')::boolean;
        IF expected_eligible THEN
            eligible_rank := eligible_rank + 1;
            expected_rank := eligible_rank;
        ELSE
            expected_rank := 0;
        END IF;
        expected_slot := 0;
        expected_selected := false;
        IF NOT expected_eligible THEN
            expected_decision := 'INELIGIBLE';
        ELSIF eligible_count < 2 THEN
            expected_decision := 'ELIGIBLE_NOT_SELECTED_INSUFFICIENT_SET';
        ELSIF expected_rank = 1 THEN
            expected_decision := 'SELECTED_SLOT_1';
            expected_slot := 1;
            expected_selected := true;
        ELSIF expected_rank = 2 THEN
            expected_decision := 'SELECTED_SLOT_2';
            expected_slot := 2;
            expected_selected := true;
        ELSE
            expected_decision := 'ELIGIBLE_NOT_SELECTED_CAPACITY';
        END IF;
        PERFORM mirror_demo_d02_r2_require_record(
            selection_entry,
            'mirror.demo/D02SelectionTraceRecord/v3',
            ARRAY[
                'schema_version','selection_step','dimension_key','priority_index',
                'dimension_eligibility_record_digest','eligible','eligible_rank',
                'selection_decision','selection_slot','selected','record_digest'
            ]
        );
        IF selection_entry -> 'selection_step' IS DISTINCT FROM to_jsonb(record_index + 1)
           OR selection_entry ->> 'dimension_key' IS DISTINCT FROM
              candidate_dimensions[record_index + 1]
           OR selection_entry -> 'priority_index' IS DISTINCT FROM to_jsonb(record_index + 1)
           OR selection_entry ->> 'dimension_eligibility_record_digest' IS DISTINCT FROM
              dimension_entry ->> 'record_digest'
           OR selection_entry -> 'eligible' IS DISTINCT FROM to_jsonb(expected_eligible)
           OR selection_entry -> 'eligible_rank' IS DISTINCT FROM to_jsonb(expected_rank)
           OR selection_entry ->> 'selection_decision' IS DISTINCT FROM expected_decision
           OR selection_entry -> 'selection_slot' IS DISTINCT FROM to_jsonb(expected_slot)
           OR selection_entry -> 'selected' IS DISTINCT FROM to_jsonb(expected_selected) THEN
            RAISE EXCEPTION 'D02 R2 Report v3 selection trace is invalid';
        END IF;
    END LOOP;
    IF NEW.eligible_dimension_keys IS DISTINCT FROM eligible_dimensions
       OR NEW.selected_dimension_keys IS DISTINCT FROM selected_dimensions
       OR NEW.status IS DISTINCT FROM (
          CASE WHEN eligible_count >= 2 THEN 'PASSED' ELSE 'FAILED' END
       )
       OR jsonb_array_length(payload -> 'selected_pair_manifest') IS DISTINCT FROM
          (CASE WHEN eligible_count >= 2 THEN 16 ELSE 0 END)
       OR NEW.selected_pair_count IS DISTINCT FROM
          (CASE WHEN eligible_count >= 2 THEN 16 ELSE 0 END)
       OR NEW.selected_result_side_count IS DISTINCT FROM
          (CASE WHEN eligible_count >= 2 THEN 32 ELSE 0 END) THEN
        RAISE EXCEPTION 'D02 R2 Report v3 selection state is invalid';
    END IF;

    FOR record_index IN 0..jsonb_array_length(payload -> 'selected_pair_manifest') - 1 LOOP
        selected_entry := payload -> 'selected_pair_manifest' -> record_index;
        expected_slot := record_index / 8 + 1;
        expected_source_index := (record_index % 8) / 2;
        expected_magnitude_index := record_index % 2;
        expected_dimension := selected_dimensions ->> (expected_slot - 1);
        selected_dimension_index := array_position(candidate_dimensions, expected_dimension) - 1;
        pair_index := expected_source_index * 6 + selected_dimension_index * 2 +
            expected_magnitude_index;
        pair_wrapper := payload -> 'pair_quality_evidence' -> pair_index;
        pair_payload := pair_wrapper -> 'pair_screening_record_payload';
        left_side := pair_payload -> 'left';
        right_side := pair_payload -> 'right';
        PERFORM mirror_demo_d02_r2_require_record(
            selected_entry,
            'mirror.demo/D02SelectedPairManifestEntry/v3',
            ARRAY[
                'schema_version','selected_pair_ordinal','selected_dimension_slot',
                'dimension_key','priority_index','source_ordinal','source_authority_key',
                'source_admission_event_id','magnitude_ppm','pair_record_id',
                'pair_screening_record_digest','left_case_id','left_result_asset_id',
                'left_result_asset_sha256','left_asset_variant_id','right_case_id',
                'right_result_asset_id','right_result_asset_sha256',
                'right_asset_variant_id','entry_digest'
            ],
            'entry_digest'
        );
        expected_payload := jsonb_build_object(
            'schema_version', 'mirror.demo/D02SelectedPairManifestEntry/v3',
            'selected_pair_ordinal', record_index + 1,
            'selected_dimension_slot', expected_slot,
            'dimension_key', expected_dimension,
            'priority_index', selected_dimension_index + 1,
            'source_ordinal', expected_source_index + 1,
            'source_authority_key', pair_payload ->> 'source_authority_key',
            'source_admission_event_id', pair_payload ->> 'source_admission_event_id',
            'magnitude_ppm', (ARRAY[15000,30000])[expected_magnitude_index + 1],
            'pair_record_id', pair_payload ->> 'pair_record_id',
            'pair_screening_record_digest',
                pair_wrapper ->> 'pair_screening_record_digest',
            'left_case_id', left_side ->> 'case_id',
            'left_result_asset_id', left_side ->> 'result_asset_id',
            'left_result_asset_sha256', left_side ->> 'result_asset_sha256',
            'left_asset_variant_id', left_side ->> 'asset_variant_id',
            'right_case_id', right_side ->> 'case_id',
            'right_result_asset_id', right_side ->> 'result_asset_id',
            'right_result_asset_sha256', right_side ->> 'result_asset_sha256',
            'right_asset_variant_id', right_side ->> 'asset_variant_id',
            'entry_digest', selected_entry ->> 'entry_digest'
        );
        IF selected_entry IS DISTINCT FROM expected_payload
           OR pair_payload -> 'pair_gate_passed' IS DISTINCT FROM 'true'::jsonb THEN
            RAISE EXCEPTION 'D02 R2 Report v3 selected manifest projection is invalid';
        END IF;
    END LOOP;
    expected_selected_manifest_digest := CASE WHEN NEW.status = 'PASSED' THEN
        mirror_demo_digest(
            'mirror.demo/D02SelectedPairManifest/v3',
            payload -> 'selected_pair_manifest'
        ) ELSE NULL END;
    IF NEW.selected_pair_manifest_digest IS DISTINCT FROM expected_selected_manifest_digest THEN
        RAISE EXCEPTION 'D02 R2 Report v3 selected manifest digest is invalid';
    END IF;

    IF mirror_demo_jsonb_exact_keys(
        network_boundary,
        ARRAY[
            'schema_version','public_internet_egress',
            'localhost_and_docker_internal_network','proxy_environment_present',
            'production_provider_calls','runtime_generation_calls','boundary_receipt_digest'
        ]
    ) IS NOT TRUE
       OR network_boundary ->> 'schema_version' IS DISTINCT FROM
          'mirror.demo/D02NetworkRuntimeBoundary/v2'
       OR network_boundary ->> 'public_internet_egress' IS DISTINCT FROM 'DENIED'
       OR network_boundary -> 'localhost_and_docker_internal_network'
          IS DISTINCT FROM 'true'::jsonb
       OR network_boundary -> 'proxy_environment_present' IS DISTINCT FROM 'false'::jsonb
       OR network_boundary -> 'production_provider_calls' IS DISTINCT FROM '0'::jsonb
       OR network_boundary -> 'runtime_generation_calls' IS DISTINCT FROM '0'::jsonb
       OR network_boundary ->> 'boundary_receipt_digest' IS DISTINCT FROM mirror_demo_digest(
           'mirror.demo/D02R2NetworkRuntimeBoundaryReceipt/v1',
           network_boundary - ARRAY['schema_version','boundary_receipt_digest']::text[]
       ) THEN
        RAISE EXCEPTION 'D02 R2 Report v3 network boundary is invalid';
    END IF;

    expected_report_digest := mirror_demo_digest(
        'mirror.demo/D02PairScreeningReport/v3', payload
    );
    expected_id := substring(mirror_demo_digest(
        'mirror.demo/D02PairScreeningReportId/v2',
        jsonb_build_object(
            'report_digest', expected_report_digest,
            'source_manifest_digest', NEW.source_manifest_digest,
            'case_manifest_digest', NEW.case_manifest_digest
        )
    ) FROM 1 FOR 32);
    IF NEW.report_digest IS DISTINCT FROM expected_report_digest
       OR NEW.id IS DISTINCT FROM expected_id THEN
        RAISE EXCEPTION 'D02 R2 Report v3 digest or ID is invalid';
    END IF;
    IF NEW.source_count IS DISTINCT FROM 4
       OR NEW.case_count IS DISTINCT FROM 48
       OR NEW.source_m3_repeat_count IS DISTINCT FROM 12
       OR NEW.m4_execution_count IS DISTINCT FROM 96
       OR NEW.result_m3_repeat_count IS DISTINCT FROM 144
       OR NEW.measurement_gate_count IS DISTINCT FROM 48
       OR NEW.decode_structure_record_count IS DISTINCT FROM 48
       OR NEW.manual_decision_count IS DISTINCT FROM 48
       OR NEW.exact_sha_record_count IS DISTINCT FROM 52
       OR NEW.phash_comparison_count IS DISTINCT FROM 1326
       OR NEW.candidate_pair_count IS DISTINCT FROM 24 THEN
        RAISE EXCEPTION 'D02 R2 Report v3 fixed counts are invalid';
    END IF;
    expected_payload := mirror_demo_authority_projection(
        to_jsonb(NEW), 'demo_pair_screening_reports'
    );
    IF NEW.status = 'FAILED' THEN
        expected_payload := expected_payload - 'selected_pair_manifest_digest';
    END IF;
    IF NEW.canonical_payload IS DISTINCT FROM expected_payload
       OR NEW.content_digest IS DISTINCT FROM mirror_demo_digest(
          NEW.schema_version, expected_payload
       ) THEN
        RAISE EXCEPTION 'D02 R2 Report v3 canonical authority is invalid';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_r2_question_bank_v3()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    report_row demo_pair_screening_reports%ROWTYPE;
    dimension_entry jsonb;
    report_dimension jsonb;
    observed_entries jsonb;
    expected_entries jsonb;
    entry_index integer;
    expected_id text;
BEGIN
    SELECT * INTO report_row
    FROM demo_pair_screening_reports
    WHERE id = NEW.screening_report_id
      AND report_digest = NEW.screening_report_digest
      AND schema_version = 'mirror.demo/D02PairScreeningReport/v3'
      AND status = 'PASSED';
    IF NOT FOUND
       OR NEW.schema_version IS DISTINCT FROM 'mirror.demo/DemoQuestionBank/v3'
       OR mirror_demo_jsonb_exact_keys(
           NEW.dimension_manifest,
           ARRAY[
               'schema_version','screening_report_id','screening_report_digest',
               'source_manifest_digest','source_p2_candidate_manifest_content_digest',
               'dimension_authority_manifest_content_digest',
               'selected_pair_manifest_digest','selected_dimensions'
           ]
       ) IS NOT TRUE
       OR NEW.dimension_manifest ->> 'schema_version' IS DISTINCT FROM
          'mirror.demo/D02QuestionBankDimensionManifest/v2'
       OR NEW.dimension_manifest ->> 'screening_report_id' IS DISTINCT FROM
          NEW.screening_report_id
       OR NEW.dimension_manifest ->> 'screening_report_digest' IS DISTINCT FROM
          NEW.screening_report_digest
       OR NEW.dimension_manifest ->> 'source_manifest_digest' IS DISTINCT FROM
          report_row.source_manifest_digest
       OR NEW.dimension_manifest ->> 'source_p2_candidate_manifest_content_digest'
          IS DISTINCT FROM
          'eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4'
       OR NEW.dimension_manifest ->> 'dimension_authority_manifest_content_digest'
          IS DISTINCT FROM
          'd4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a'
       OR NEW.dimension_manifest ->> 'selected_pair_manifest_digest' IS DISTINCT FROM
          report_row.selected_pair_manifest_digest
       OR NEW.pair_manifest_digest IS DISTINCT FROM report_row.selected_pair_manifest_digest
       OR jsonb_typeof(NEW.dimension_manifest -> 'selected_dimensions')
          IS DISTINCT FROM 'array'
       OR jsonb_array_length(NEW.dimension_manifest -> 'selected_dimensions')
          IS DISTINCT FROM 2 THEN
        RAISE EXCEPTION 'D02 R2 QuestionBank v3 Report or manifest binding is invalid';
    END IF;
    FOR entry_index IN 0..1 LOOP
        dimension_entry := NEW.dimension_manifest -> 'selected_dimensions' -> entry_index;
        SELECT candidate.value INTO report_dimension
        FROM jsonb_array_elements(report_row.report_payload -> 'dimension_eligibility')
             AS candidate(value)
        WHERE candidate.value ->> 'dimension_key' =
              report_row.selected_dimension_keys ->> entry_index;
        IF mirror_demo_jsonb_exact_keys(
            dimension_entry,
            ARRAY[
                'dimension_key','priority_index','sixteen_side_gate_digest',
                'eight_pair_gate_digest','ordered_selected_pair_entry_digests'
            ]
        ) IS NOT TRUE
           OR dimension_entry ->> 'dimension_key' IS DISTINCT FROM
             report_row.selected_dimension_keys ->> entry_index
           OR dimension_entry -> 'priority_index' IS DISTINCT FROM
              report_dimension -> 'priority_index'
           OR dimension_entry ->> 'sixteen_side_gate_digest' IS DISTINCT FROM
              report_dimension ->> 'sixteen_side_gate_digest'
           OR dimension_entry ->> 'eight_pair_gate_digest' IS DISTINCT FROM
              report_dimension ->> 'eight_pair_gate_digest'
           OR jsonb_typeof(dimension_entry -> 'ordered_selected_pair_entry_digests')
              IS DISTINCT FROM 'array'
           OR jsonb_array_length(
                  dimension_entry -> 'ordered_selected_pair_entry_digests'
              ) IS DISTINCT FROM 8 THEN
            RAISE EXCEPTION 'D02 R2 QuestionBank v3 selected dimension is invalid';
        END IF;
    END LOOP;
    SELECT jsonb_agg(to_jsonb(entry.value) ORDER BY dimension.ordinality, entry.ordinality)
    INTO observed_entries
    FROM jsonb_array_elements(NEW.dimension_manifest -> 'selected_dimensions')
         WITH ORDINALITY AS dimension(value, ordinality)
    CROSS JOIN LATERAL jsonb_array_elements_text(
        dimension.value -> 'ordered_selected_pair_entry_digests'
    ) WITH ORDINALITY AS entry(value, ordinality);
    SELECT jsonb_agg(to_jsonb(entry.value ->> 'entry_digest') ORDER BY entry.ordinality)
    INTO expected_entries
    FROM jsonb_array_elements(report_row.report_payload -> 'selected_pair_manifest')
         WITH ORDINALITY AS entry(value, ordinality);
    IF observed_entries IS DISTINCT FROM expected_entries THEN
        RAISE EXCEPTION 'D02 R2 QuestionBank v3 selected entry ordering is invalid';
    END IF;
    expected_id := substring(mirror_demo_digest(
        'mirror.demo/D02QuestionBankId/v2',
        jsonb_build_object(
            'algorithm_config_digest', NEW.algorithm_config_digest,
            'screening_report_digest', NEW.screening_report_digest,
            'screening_report_id', NEW.screening_report_id,
            'selected_pair_manifest_digest', NEW.pair_manifest_digest,
            'source_manifest_digest', report_row.source_manifest_digest
        )
    ) FROM 1 FOR 32);
    IF NEW.id IS DISTINCT FROM expected_id THEN
        RAISE EXCEPTION 'D02 R2 QuestionBank v3 ID is invalid';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_r2_question_pair_v3()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    bank_row demo_question_banks%ROWTYPE;
    report_row demo_pair_screening_reports%ROWTYPE;
    identity_row demo_synthetic_identities%ROWTYPE;
    source_entry jsonb;
    pair_wrapper jsonb;
    pair_payload jsonb;
    selected_entry jsonb;
    member_count integer;
    side_payload jsonb;
    side_name text;
    expected_result_asset_id text;
    expected_result_sha text;
    expected_variant_id text;
    expected_direction text;
    expected_delta_ppm integer;
    expected_id text;
BEGIN
    SELECT * INTO bank_row FROM demo_question_banks
    WHERE id = NEW.question_bank_id
      AND schema_version = 'mirror.demo/DemoQuestionBank/v3';
    SELECT * INTO report_row FROM demo_pair_screening_reports
    WHERE id = NEW.screening_report_id
      AND report_digest = NEW.screening_report_digest
      AND schema_version = 'mirror.demo/D02PairScreeningReport/v3'
      AND status = 'PASSED';
    SELECT * INTO identity_row FROM demo_synthetic_identities
    WHERE id = NEW.demo_synthetic_identity_id
      AND schema_version = 'mirror.demo/DemoSyntheticIdentity/v4';
    IF bank_row.id IS NULL OR report_row.id IS NULL OR identity_row.id IS NULL
       OR bank_row.screening_report_id IS DISTINCT FROM NEW.screening_report_id
       OR bank_row.screening_report_digest IS DISTINCT FROM NEW.screening_report_digest
       OR bank_row.pair_manifest_digest IS DISTINCT FROM
          report_row.selected_pair_manifest_digest
       OR NEW.schema_version IS DISTINCT FROM 'mirror.demo/DemoQuestionPair/v3'
       OR mirror_demo_jsonb_exact_keys(
           NEW.qa_payload,
           ARRAY[
               'schema_version','screening_report_id','screening_report_digest',
               'source_manifest_digest','source_manifest_entry_schema_version',
               'source_manifest_entry_digest','pair_screening_record_schema_version',
               'pair_screening_record_digest','pair_screening_record_payload',
               'selected_pair_manifest_digest','selected_pair_entry_schema_version',
               'selected_pair_entry_digest','selected_pair_entry_payload'
           ]
       ) IS NOT TRUE
       OR NEW.qa_payload ->> 'schema_version' IS DISTINCT FROM
          'mirror.demo/D02QuestionPairQAPayload/v3'
       OR NEW.qa_payload ->> 'screening_report_id' IS DISTINCT FROM
          NEW.screening_report_id
       OR NEW.qa_payload ->> 'screening_report_digest' IS DISTINCT FROM
          NEW.screening_report_digest
       OR NEW.qa_payload ->> 'source_manifest_digest' IS DISTINCT FROM
          report_row.source_manifest_digest
       OR NEW.qa_payload ->> 'selected_pair_manifest_digest' IS DISTINCT FROM
          report_row.selected_pair_manifest_digest
       OR NEW.qa_payload ->> 'source_manifest_entry_schema_version' IS DISTINCT FROM
          'mirror.demo/D02SourceAuthorityManifestEntry/v4'
       OR NEW.qa_payload ->> 'pair_screening_record_schema_version' IS DISTINCT FROM
          'mirror.demo/D02PairScreeningRecord/v4'
       OR NEW.qa_payload ->> 'selected_pair_entry_schema_version' IS DISTINCT FROM
          'mirror.demo/D02SelectedPairManifestEntry/v3' THEN
        RAISE EXCEPTION 'D02 R2 QuestionPair v3 graph binding is invalid';
    END IF;
    SELECT count(*), jsonb_agg(candidate.value) -> 0
    INTO member_count, source_entry
    FROM jsonb_array_elements(report_row.report_payload -> 'ordered_source_manifest')
         AS candidate(value)
    WHERE candidate.value ->> 'record_digest' =
          NEW.qa_payload ->> 'source_manifest_entry_digest';
    IF member_count IS DISTINCT FROM 1
       OR source_entry ->> 'source_admission_event_id' IS DISTINCT FROM
          NEW.demo_synthetic_identity_id
       OR source_entry ->> 'source_authority_key' IS DISTINCT FROM
          identity_row.source_authority_key
       OR source_entry ->> 'source_admission_content_digest' IS DISTINCT FROM
          identity_row.content_digest
       OR source_entry ->> 'r2_source_authority_record_id' IS DISTINCT FROM
          identity_row.r2_source_authority_record_id
       OR source_entry ->> 'source_asset_id' IS DISTINCT FROM NEW.source_asset_id
       OR source_entry ->> 'source_asset_sha256' IS DISTINCT FROM
          NEW.source_asset_sha256 THEN
        RAISE EXCEPTION 'D02 R2 QuestionPair v3 source member is invalid';
    END IF;
    PERFORM mirror_demo_require_current_synthetic_admission(identity_row.id);

    SELECT count(*), jsonb_agg(candidate.value) -> 0
    INTO member_count, pair_wrapper
    FROM jsonb_array_elements(report_row.report_payload -> 'pair_quality_evidence')
         AS candidate(value)
    WHERE candidate.value ->> 'pair_screening_record_digest' =
          NEW.qa_payload ->> 'pair_screening_record_digest';
    IF member_count IS DISTINCT FROM 1
       OR NEW.qa_payload -> 'pair_screening_record_payload' IS DISTINCT FROM pair_wrapper
       OR pair_wrapper ->> 'pair_screening_record_digest' IS DISTINCT FROM mirror_demo_digest(
           'mirror.demo/D02PairScreeningRecord/v4',
           pair_wrapper -> 'pair_screening_record_payload'
       ) THEN
        RAISE EXCEPTION 'D02 R2 QuestionPair v3 pair member is invalid';
    END IF;
    pair_payload := pair_wrapper -> 'pair_screening_record_payload';
    SELECT count(*), jsonb_agg(candidate.value) -> 0
    INTO member_count, selected_entry
    FROM jsonb_array_elements(report_row.report_payload -> 'selected_pair_manifest')
         AS candidate(value)
    WHERE candidate.value ->> 'entry_digest' =
          NEW.qa_payload ->> 'selected_pair_entry_digest';
    IF member_count IS DISTINCT FROM 1
       OR NEW.qa_payload -> 'selected_pair_entry_payload' IS DISTINCT FROM selected_entry
       OR selected_entry ->> 'entry_digest' IS DISTINCT FROM mirror_demo_digest(
           'mirror.demo/D02SelectedPairManifestEntry/v3',
           selected_entry - ARRAY['schema_version','entry_digest']::text[]
       )
       OR selected_entry ->> 'pair_screening_record_digest' IS DISTINCT FROM
          pair_wrapper ->> 'pair_screening_record_digest'
       OR selected_entry ->> 'pair_record_id' IS DISTINCT FROM
          pair_payload ->> 'pair_record_id'
       OR selected_entry ->> 'source_admission_event_id' IS DISTINCT FROM
          NEW.demo_synthetic_identity_id
       OR selected_entry ->> 'dimension_key' IS DISTINCT FROM NEW.dimension_key
       OR selected_entry -> 'magnitude_ppm' IS DISTINCT FROM to_jsonb(NEW.magnitude_ppm)
       OR pair_payload ->> 'source_asset_id' IS DISTINCT FROM NEW.source_asset_id
       OR pair_payload ->> 'source_asset_sha256' IS DISTINCT FROM NEW.source_asset_sha256
       OR pair_payload ->> 'dimension_key' IS DISTINCT FROM NEW.dimension_key
       OR pair_payload -> 'magnitude_ppm' IS DISTINCT FROM to_jsonb(NEW.magnitude_ppm)
       OR pair_payload -> 'pair_quality_ppm' IS DISTINCT FROM to_jsonb(NEW.pair_quality_ppm)
       OR pair_payload -> 'pair_gate_passed' IS DISTINCT FROM 'true'::jsonb THEN
        RAISE EXCEPTION 'D02 R2 QuestionPair v3 selected member is invalid';
    END IF;

    FOREACH side_name IN ARRAY ARRAY['left','right'] LOOP
        side_payload := pair_payload -> side_name;
        IF side_name = 'left' THEN
            expected_result_asset_id := NEW.left_asset_id;
            expected_result_sha := NEW.left_asset_sha256;
            expected_variant_id := NEW.left_asset_variant_id;
            expected_direction := 'DECREASE';
            expected_delta_ppm := NEW.left_delta_ppm;
        ELSE
            expected_result_asset_id := NEW.right_asset_id;
            expected_result_sha := NEW.right_asset_sha256;
            expected_variant_id := NEW.right_asset_variant_id;
            expected_direction := 'INCREASE';
            expected_delta_ppm := NEW.right_delta_ppm;
        END IF;
        IF side_payload ->> 'schema_version' IS DISTINCT FROM
              'mirror.demo/D02EvaluatedPairSide/v3'
           OR side_payload ->> 'result_asset_id' IS DISTINCT FROM expected_result_asset_id
           OR side_payload ->> 'result_asset_sha256' IS DISTINCT FROM expected_result_sha
           OR side_payload ->> 'asset_variant_id' IS DISTINCT FROM expected_variant_id
           OR side_payload ->> 'asset_variant_type' IS DISTINCT FROM
              'demo_p3_p7_geometry_v1'
           OR side_payload ->> 'requested_direction' IS DISTINCT FROM expected_direction
           OR side_payload -> 'requested_magnitude_ppm' IS DISTINCT FROM
              to_jsonb(NEW.magnitude_ppm)
           OR side_payload -> 'measured_signed_delta_ppm' IS DISTINCT FROM
              to_jsonb(expected_delta_ppm)
           OR side_payload -> 'side_gate_passed' IS DISTINCT FROM 'true'::jsonb
           OR NOT EXISTS (
               SELECT 1
               FROM assets result_asset
               JOIN asset_variants variant_row
                 ON variant_row.id = expected_variant_id
                AND variant_row.source_asset_id = NEW.source_asset_id
                AND variant_row.result_asset_id = expected_result_asset_id
                AND variant_row.variant_type = 'demo_p3_p7_geometry_v1'
               WHERE result_asset.id = expected_result_asset_id
                 AND result_asset.sha256 = expected_result_sha
                 AND result_asset.byte_size = (side_payload ->> 'result_asset_byte_size')::bigint
                 AND result_asset.mime_type = side_payload ->> 'result_asset_mime_type'
                 AND result_asset.width = (side_payload ->> 'result_asset_width')::integer
                 AND result_asset.height = (side_payload ->> 'result_asset_height')::integer
                 AND result_asset.owner_user_id IS NULL
                 AND result_asset.asset_role = 'synthetic'
                 AND result_asset.internal_purpose = 'synthetic_dataset'
                 AND result_asset.synthetic IS TRUE
                 AND result_asset.deleted_at IS NULL
                 AND result_asset.is_ai_generated IS FALSE
                 AND result_asset.is_ai_modified IS TRUE
           )
           OR side_payload ->> 'lineage_digest' IS DISTINCT FROM mirror_demo_digest(
               'mirror.demo/D02AssetVariantLineage/v1',
               jsonb_build_object(
                   'variant_type', 'demo_p3_p7_geometry_v1',
                   'source_asset_id', NEW.source_asset_id,
                   'source_asset_sha256', NEW.source_asset_sha256,
                   'result_asset_id', expected_result_asset_id,
                   'result_asset_sha256', expected_result_sha
               )
           ) THEN
            RAISE EXCEPTION 'D02 R2 QuestionPair v3 side authority is invalid';
        END IF;
    END LOOP;
    expected_id := substring(mirror_demo_digest(
        'mirror.demo/D02QuestionPairId/v2',
        jsonb_build_object(
            'dimension_key', NEW.dimension_key,
            'magnitude_ppm', NEW.magnitude_ppm,
            'pair_screening_record_digest',
                NEW.qa_payload ->> 'pair_screening_record_digest',
            'question_bank_id', NEW.question_bank_id,
            'source_admission_event_id', NEW.demo_synthetic_identity_id,
            'source_manifest_entry_digest',
                NEW.qa_payload ->> 'source_manifest_entry_digest',
            'selected_pair_entry_digest',
                NEW.qa_payload ->> 'selected_pair_entry_digest'
        )
    ) FROM 1 FOR 32);
    IF NEW.id IS DISTINCT FROM expected_id THEN
        RAISE EXCEPTION 'D02 R2 QuestionPair v3 ID is invalid';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_r2_complete_bank_v3()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    authority_bank_id text;
    bank_row demo_question_banks%ROWTYPE;
    report_row demo_pair_screening_reports%ROWTYPE;
    pair_count integer;
    side_count integer;
    source_count integer;
    dimension_count integer;
    magnitude_count integer;
    observed_entries jsonb;
    expected_entries jsonb;
BEGIN
    authority_bank_id := CASE
        WHEN TG_TABLE_NAME = 'demo_question_banks' THEN to_jsonb(NEW) ->> 'id'
        ELSE to_jsonb(NEW) ->> 'question_bank_id'
    END;
    SELECT * INTO bank_row FROM demo_question_banks
    WHERE id = authority_bank_id
      AND schema_version = 'mirror.demo/DemoQuestionBank/v3';
    IF NOT FOUND THEN
        RETURN NEW;
    END IF;
    SELECT * INTO report_row FROM demo_pair_screening_reports
    WHERE id = bank_row.screening_report_id
      AND report_digest = bank_row.screening_report_digest
      AND schema_version = 'mirror.demo/D02PairScreeningReport/v3'
      AND status = 'PASSED';
    SELECT count(*), count(DISTINCT demo_synthetic_identity_id),
           count(DISTINCT dimension_key), count(DISTINCT magnitude_ppm)
    INTO pair_count, source_count, dimension_count, magnitude_count
    FROM demo_question_pairs
    WHERE question_bank_id = authority_bank_id;
    SELECT count(DISTINCT side_id) INTO side_count
    FROM (
        SELECT left_asset_id AS side_id FROM demo_question_pairs
        WHERE question_bank_id = authority_bank_id
        UNION
        SELECT right_asset_id AS side_id FROM demo_question_pairs
        WHERE question_bank_id = authority_bank_id
    ) selected_sides;
    SELECT jsonb_agg(to_jsonb(pair_row.qa_payload ->> 'selected_pair_entry_digest')
                     ORDER BY selected_entry.ordinality)
    INTO observed_entries
    FROM jsonb_array_elements(report_row.report_payload -> 'selected_pair_manifest')
         WITH ORDINALITY AS selected_entry(value, ordinality)
    LEFT JOIN demo_question_pairs pair_row
      ON pair_row.question_bank_id = authority_bank_id
     AND pair_row.qa_payload ->> 'selected_pair_entry_digest' =
         selected_entry.value ->> 'entry_digest';
    SELECT jsonb_agg(to_jsonb(selected_entry.value ->> 'entry_digest')
                     ORDER BY selected_entry.ordinality)
    INTO expected_entries
    FROM jsonb_array_elements(report_row.report_payload -> 'selected_pair_manifest')
         WITH ORDINALITY AS selected_entry(value, ordinality);
    IF report_row.id IS NULL
       OR bank_row.pair_manifest_digest IS DISTINCT FROM
          report_row.selected_pair_manifest_digest
       OR report_row.selected_pair_count IS DISTINCT FROM 16
       OR report_row.selected_result_side_count IS DISTINCT FROM 32
       OR pair_count IS DISTINCT FROM 16
       OR side_count IS DISTINCT FROM 32
       OR source_count IS DISTINCT FROM 4
       OR dimension_count IS DISTINCT FROM 2
       OR magnitude_count IS DISTINCT FROM 2
       OR observed_entries IS DISTINCT FROM expected_entries
       OR (
           SELECT count(DISTINCT pair_row.qa_payload ->> 'selected_pair_entry_digest')
           FROM demo_question_pairs pair_row
           WHERE pair_row.question_bank_id = authority_bank_id
       ) IS DISTINCT FROM 16
       OR EXISTS (
           SELECT 1 FROM demo_question_pairs pair_row
           WHERE pair_row.question_bank_id = authority_bank_id
             AND (
                 pair_row.schema_version IS DISTINCT FROM
                    'mirror.demo/DemoQuestionPair/v3'
                 OR pair_row.screening_report_id IS DISTINCT FROM
                    bank_row.screening_report_id
                 OR pair_row.screening_report_digest IS DISTINCT FROM
                    bank_row.screening_report_digest
             )
       )
       OR EXISTS (
           SELECT 1
           FROM jsonb_array_elements(report_row.selected_dimension_keys) AS selected(value)
           WHERE (
               SELECT count(*) FROM demo_question_pairs pair_row
               WHERE pair_row.question_bank_id = authority_bank_id
                 AND pair_row.dimension_key = selected.value #>> '{}'
           ) IS DISTINCT FROM 8
       ) THEN
        RAISE EXCEPTION 'D02 R2 QuestionBank v3 is not the complete selected 16-pair authority';
    END IF;
    RETURN NEW;
END;
$function$;
"""


def _replace_version_constraints() -> None:
    for table, constraint, expression in (
        (
            "demo_pair_screening_reports",
            "schema_version_shape",
            "schema_version IN ('mirror.demo/D02PairScreeningReport/v1','mirror.demo/D02PairScreeningReport/v2','mirror.demo/D02PairScreeningReport/v3')",
        ),
        (
            "demo_pair_screening_reports",
            "exact_schema_version",
            "schema_version IN ('mirror.demo/D02PairScreeningReport/v1','mirror.demo/D02PairScreeningReport/v2','mirror.demo/D02PairScreeningReport/v3')",
        ),
        (
            "demo_question_banks",
            "schema_version_shape",
            "schema_version IN ('mirror.demo/DemoQuestionBank/v1','mirror.demo/DemoQuestionBank/v2','mirror.demo/DemoQuestionBank/v3')",
        ),
        (
            "demo_question_banks",
            "versioned_dimension_manifest",
            "(schema_version = 'mirror.demo/DemoQuestionBank/v1' "
            "AND jsonb_typeof(dimension_manifest) = 'array' "
            "AND screening_report_id IS NULL AND screening_report_digest IS NULL) OR "
            "(schema_version IN ('mirror.demo/DemoQuestionBank/v2',"
            "'mirror.demo/DemoQuestionBank/v3') "
            "AND jsonb_typeof(dimension_manifest) = 'object' "
            "AND screening_report_id IS NOT NULL AND screening_report_digest IS NOT NULL)",
        ),
        (
            "demo_question_pairs",
            "schema_version_shape",
            "schema_version IN ('mirror.demo/DemoQuestionPair/v1','mirror.demo/DemoQuestionPair/v2','mirror.demo/DemoQuestionPair/v3')",
        ),
        (
            "demo_question_pairs",
            "versioned_report_binding",
            "(schema_version = 'mirror.demo/DemoQuestionPair/v1' "
            "AND screening_report_id IS NULL AND screening_report_digest IS NULL) OR "
            "(schema_version IN ('mirror.demo/DemoQuestionPair/v2',"
            "'mirror.demo/DemoQuestionPair/v3') "
            "AND screening_report_id IS NOT NULL AND screening_report_digest IS NOT NULL)",
        ),
    ):
        op.drop_constraint(op.f(f"ck_{table}_{constraint}"), table, type_="check")
        op.create_check_constraint(op.f(f"ck_{table}_{constraint}"), table, expression)


def _set_bank_pair_trigger_dispatch(*, r2: bool) -> None:
    """Keep historical v1/v2 functions intact while routing v3 to R2 validators."""

    op.execute("DROP TRIGGER trg_demo_d02_question_bank_insert ON demo_question_banks")
    op.execute("DROP TRIGGER trg_demo_d02_question_pair_insert ON demo_question_pairs")
    for table_name in ("demo_question_banks", "demo_question_pairs"):
        op.execute(f"DROP TRIGGER trg_demo_d02_complete_bank_{table_name} ON {table_name}")

    bank_when = " WHEN (NEW.schema_version <> 'mirror.demo/DemoQuestionBank/v3')" if r2 else ""
    pair_when = " WHEN (NEW.schema_version <> 'mirror.demo/DemoQuestionPair/v3')" if r2 else ""
    op.execute(
        "CREATE TRIGGER trg_demo_d02_question_bank_insert "
        "BEFORE INSERT ON demo_question_banks FOR EACH ROW"
        f"{bank_when} EXECUTE FUNCTION mirror_demo_validate_d02_question_bank_insert()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d02_question_pair_insert "
        "BEFORE INSERT ON demo_question_pairs FOR EACH ROW"
        f"{pair_when} EXECUTE FUNCTION mirror_demo_validate_d02_question_pair_insert()"
    )
    for table_name, when_clause in (
        ("demo_question_banks", bank_when),
        ("demo_question_pairs", pair_when),
    ):
        op.execute(
            f"CREATE CONSTRAINT TRIGGER trg_demo_d02_complete_bank_{table_name} "
            f"AFTER INSERT ON {table_name} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW"
            f"{when_clause} EXECUTE FUNCTION mirror_demo_validate_d02_complete_bank()"
        )


def upgrade() -> None:
    op.execute(_LOCK_SQL)
    _create_supporting_table()
    op.add_column(
        "demo_synthetic_identities",
        sa.Column("r2_source_authority_record_id", sa.String(length=32)),
    )
    op.create_foreign_key(
        op.f(
            "fk_demo_synthetic_identities_r2_source_authority_record_id_demo_d02_r2_source_authorities"
        ),
        "demo_synthetic_identities",
        "demo_d02_r2_source_authorities",
        ["r2_source_authority_record_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_demo_synthetic_identities_r2_source_authority_record_id"),
        "demo_synthetic_identities",
        ["r2_source_authority_record_id"],
        unique=False,
    )
    _set_v10_identity_validator_r2_projection(include_r2_column=True)
    op.add_column("demo_pair_screening_reports", sa.Column("measurement_gate_count", sa.Integer()))
    op.add_column(
        "demo_pair_screening_reports", sa.Column("decode_structure_record_count", sa.Integer())
    )
    op.create_check_constraint(
        op.f("ck_demo_pair_screening_reports_r2_v3_exact_counts"),
        "demo_pair_screening_reports",
        "(schema_version IN ('mirror.demo/D02PairScreeningReport/v1','mirror.demo/D02PairScreeningReport/v2') "
        "AND measurement_gate_count IS NULL AND decode_structure_record_count IS NULL) OR "
        "(schema_version = 'mirror.demo/D02PairScreeningReport/v3' "
        "AND measurement_gate_count = 48 AND decode_structure_record_count = 48)",
    )
    op.execute(_authority_projection_sql(r2=True))
    op.execute(_R2_SQL)
    op.execute(_R2_V3_AUTHORITY_SQL)
    _replace_identity_generated_columns(r2=True)
    _replace_identity_shape_constraints()
    _create_legacy_qa_constraint()
    _replace_version_constraints()
    _set_bank_pair_trigger_dispatch(r2=True)
    op.execute(
        "DROP TRIGGER trg_demo_authority_guard ON demo_d02_r2_source_authorities"
    ) if False else None
    op.execute(
        "CREATE TRIGGER trg_demo_d02_r2_source_authority BEFORE INSERT OR UPDATE OR DELETE ON demo_d02_r2_source_authorities FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d02_r2_source_authority()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d02_r2_identity BEFORE INSERT ON demo_synthetic_identities FOR EACH ROW WHEN (NEW.schema_version = 'mirror.demo/DemoSyntheticIdentity/v4') EXECUTE FUNCTION mirror_demo_validate_d02_r2_identity()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d02_r2_screening_report_v3 "
        "BEFORE INSERT ON demo_pair_screening_reports FOR EACH ROW "
        "WHEN (NEW.schema_version = 'mirror.demo/D02PairScreeningReport/v3') "
        "EXECUTE FUNCTION mirror_demo_validate_d02_r2_screening_report_v3()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d02_r2_question_bank_v3 "
        "BEFORE INSERT ON demo_question_banks FOR EACH ROW "
        "WHEN (NEW.schema_version = 'mirror.demo/DemoQuestionBank/v3') "
        "EXECUTE FUNCTION mirror_demo_validate_d02_r2_question_bank_v3()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d02_r2_question_pair_v3 "
        "BEFORE INSERT ON demo_question_pairs FOR EACH ROW "
        "WHEN (NEW.schema_version = 'mirror.demo/DemoQuestionPair/v3') "
        "EXECUTE FUNCTION mirror_demo_validate_d02_r2_question_pair_v3()"
    )
    for table_name, schema_version, suffix in (
        (
            "demo_question_banks",
            "mirror.demo/DemoQuestionBank/v3",
            "bank",
        ),
        (
            "demo_question_pairs",
            "mirror.demo/DemoQuestionPair/v3",
            "pair",
        ),
    ):
        op.execute(
            f"CREATE CONSTRAINT TRIGGER trg_demo_d02_r2_complete_bank_v3_{suffix} "
            f"AFTER INSERT ON {table_name} DEFERRABLE INITIALLY DEFERRED "
            f"FOR EACH ROW WHEN (NEW.schema_version = '{schema_version}') "
            "EXECUTE FUNCTION mirror_demo_validate_d02_r2_complete_bank_v3()"
        )


def downgrade() -> None:
    op.execute(_LOCK_SQL)
    if_exists = """
DO $block$
BEGIN
    IF EXISTS (SELECT 1 FROM demo_d02_r2_source_authorities)
       OR EXISTS (SELECT 1 FROM demo_synthetic_identities WHERE schema_version = 'mirror.demo/DemoSyntheticIdentity/v4')
       OR EXISTS (SELECT 1 FROM demo_pair_screening_reports WHERE schema_version = 'mirror.demo/D02PairScreeningReport/v3')
       OR EXISTS (SELECT 1 FROM demo_question_banks WHERE schema_version = 'mirror.demo/DemoQuestionBank/v3')
       OR EXISTS (SELECT 1 FROM demo_question_pairs WHERE schema_version = 'mirror.demo/DemoQuestionPair/v3') THEN
        RAISE EXCEPTION 'Cannot downgrade populated D02 R2 source authority';
    END IF;
END $block$;
    """
    op.execute(if_exists)
    op.execute("DROP TRIGGER trg_demo_d02_r2_complete_bank_v3_pair ON demo_question_pairs")
    op.execute("DROP TRIGGER trg_demo_d02_r2_complete_bank_v3_bank ON demo_question_banks")
    op.execute("DROP TRIGGER trg_demo_d02_r2_question_pair_v3 ON demo_question_pairs")
    op.execute("DROP TRIGGER trg_demo_d02_r2_question_bank_v3 ON demo_question_banks")
    op.execute("DROP TRIGGER trg_demo_d02_r2_screening_report_v3 ON demo_pair_screening_reports")
    _set_bank_pair_trigger_dispatch(r2=False)
    op.execute("DROP FUNCTION mirror_demo_validate_d02_r2_complete_bank_v3()")
    op.execute("DROP FUNCTION mirror_demo_validate_d02_r2_question_pair_v3()")
    op.execute("DROP FUNCTION mirror_demo_validate_d02_r2_question_bank_v3()")
    op.execute("DROP FUNCTION mirror_demo_validate_d02_r2_screening_report_v3()")
    op.execute("DROP FUNCTION mirror_demo_validate_d02_r2_gate_v5(jsonb,jsonb,jsonb,jsonb,jsonb)")
    op.execute("DROP FUNCTION mirror_demo_validate_d02_r2_result_m3_v3(jsonb,jsonb,jsonb,integer)")
    op.execute("DROP FUNCTION mirror_demo_validate_d02_r2_m4_v2(jsonb,jsonb,jsonb,integer)")
    op.execute("DROP FUNCTION mirror_demo_validate_d02_r2_source_m3_v3(jsonb,jsonb,text)")
    op.execute("DROP FUNCTION mirror_demo_d02_r2_require_record(jsonb,text,text[],text)")
    op.execute(
        "DROP FUNCTION mirror_demo_d02_r2_require_mandatory_digest_leaves(jsonb,text[],text)"
    )
    op.execute("DROP TRIGGER trg_demo_d02_r2_identity ON demo_synthetic_identities")
    op.execute("DROP TRIGGER trg_demo_d02_r2_source_authority ON demo_d02_r2_source_authorities")
    op.drop_constraint(
        op.f("ck_demo_pair_screening_reports_r2_v3_exact_counts"),
        "demo_pair_screening_reports",
        type_="check",
    )
    op.drop_column("demo_pair_screening_reports", "decode_structure_record_count")
    op.drop_column("demo_pair_screening_reports", "measurement_gate_count")
    for table, constraint, expression in (
        (
            "demo_pair_screening_reports",
            "schema_version_shape",
            "schema_version IN ('mirror.demo/D02PairScreeningReport/v1','mirror.demo/D02PairScreeningReport/v2')",
        ),
        (
            "demo_pair_screening_reports",
            "exact_schema_version",
            "schema_version IN ('mirror.demo/D02PairScreeningReport/v1','mirror.demo/D02PairScreeningReport/v2')",
        ),
        (
            "demo_question_banks",
            "schema_version_shape",
            "schema_version IN ('mirror.demo/DemoQuestionBank/v1','mirror.demo/DemoQuestionBank/v2')",
        ),
        (
            "demo_question_banks",
            "versioned_dimension_manifest",
            "(schema_version = 'mirror.demo/DemoQuestionBank/v1' "
            "AND jsonb_typeof(dimension_manifest) = 'array' "
            "AND screening_report_id IS NULL AND screening_report_digest IS NULL) OR "
            "(schema_version = 'mirror.demo/DemoQuestionBank/v2' "
            "AND jsonb_typeof(dimension_manifest) = 'object' "
            "AND screening_report_id IS NOT NULL AND screening_report_digest IS NOT NULL)",
        ),
        (
            "demo_question_pairs",
            "schema_version_shape",
            "schema_version IN ('mirror.demo/DemoQuestionPair/v1','mirror.demo/DemoQuestionPair/v2')",
        ),
        (
            "demo_question_pairs",
            "versioned_report_binding",
            "(schema_version = 'mirror.demo/DemoQuestionPair/v1' "
            "AND screening_report_id IS NULL AND screening_report_digest IS NULL) OR "
            "(schema_version = 'mirror.demo/DemoQuestionPair/v2' "
            "AND screening_report_id IS NOT NULL AND screening_report_digest IS NOT NULL)",
        ),
    ):
        op.drop_constraint(op.f(f"ck_{table}_{constraint}"), table, type_="check")
        op.create_check_constraint(op.f(f"ck_{table}_{constraint}"), table, expression)
    # Remove every constraint which can depend on the R2 generated columns
    # before altering them.  In particular, do not recreate a constraint that
    # references r2_source_authority_record_id until after that column is gone.
    op.drop_constraint(
        op.f("ck_demo_synthetic_identities_d02_local_qa_digest_separation"),
        "demo_synthetic_identities",
        type_="check",
    )
    _set_v10_identity_validator_r2_projection(include_r2_column=False)
    op.drop_constraint(
        op.f("ck_demo_synthetic_identities_schema_version_shape"),
        "demo_synthetic_identities",
        type_="check",
    )
    _replace_identity_generated_columns(r2=False)
    op.drop_index(
        op.f("ix_demo_synthetic_identities_r2_source_authority_record_id"),
        table_name="demo_synthetic_identities",
    )
    op.drop_constraint(
        op.f(
            "fk_demo_synthetic_identities_r2_source_authority_record_id_demo_d02_r2_source_authorities"
        ),
        "demo_synthetic_identities",
        type_="foreignkey",
    )
    op.drop_column("demo_synthetic_identities", "r2_source_authority_record_id")
    op.drop_table("demo_d02_r2_source_authorities")
    op.execute("DROP FUNCTION mirror_demo_validate_d02_r2_identity()")
    op.execute("DROP FUNCTION mirror_demo_validate_d02_r2_source_authority()")
    op.execute("DROP FUNCTION mirror_demo_r2_source_authority_key(text,text,text,text,text)")
    _restore_v3_identity_constraints()
    op.execute(_authority_projection_sql(r2=False))
    op.execute(_D02_V10_GUARD_SQL)
    op.execute(_D02_V10_WRITE_GUARDS_SQL)
