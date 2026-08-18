"""Add immutable preregistered LandmarkWarpPlan authority.

Revision ID: 0013_warp_plan_authority
Revises: 0012_geometry_variant_authority
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_warp_plan_authority"
down_revision: str | None = "0012_geometry_variant_authority"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _replace_transform_run_guard(*, require_plan: bool) -> None:
    plan_declaration = "plan landmark_warp_plans%ROWTYPE;" if require_plan else ""
    plan_lock = (
        """
            SELECT * INTO plan FROM landmark_warp_plans
             WHERE variant_specification_id = specification.id FOR UPDATE;
            IF plan.id IS NULL THEN
                RAISE EXCEPTION 'transform run requires immutable landmark warp plan';
            END IF;
    """
        if require_plan
        else ""
    )
    statement = """
        CREATE OR REPLACE FUNCTION mirror_validate_transform_run() RETURNS trigger AS $$
        DECLARE
            specification variant_specifications%ROWTYPE;
            __PLAN_DECLARATION__
            source_asset assets%ROWTYPE;
            result_asset assets%ROWTYPE;
            allowed_transition boolean;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'transform run authority is immutable';
            END IF;
            SELECT * INTO specification FROM variant_specifications
             WHERE id = NEW.variant_specification_id FOR UPDATE;
            IF specification.id IS NULL THEN
                RAISE EXCEPTION 'transform run requires immutable variant specification';
            END IF;
            __PLAN_LOCK__
            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'SPECIFIED' OR NEW.result_asset_id IS NOT NULL
                   OR NEW.result_code IS NOT NULL OR NEW.started_at IS NOT NULL
                   OR NEW.output_stored_at IS NOT NULL OR NEW.measurement_started_at IS NOT NULL
                   OR NEW.finalized_at IS NOT NULL THEN
                    RAISE EXCEPTION 'transform run must start specified';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD.id IS DISTINCT FROM NEW.id
               OR OLD.created_at IS DISTINCT FROM NEW.created_at
               OR OLD.schema_version IS DISTINCT FROM NEW.schema_version
               OR OLD.variant_specification_id IS DISTINCT FROM NEW.variant_specification_id
               OR OLD.attempt IS DISTINCT FROM NEW.attempt THEN
                RAISE EXCEPTION 'transform run authority is immutable';
            END IF;
            IF (OLD.result_asset_id IS NOT NULL
                AND OLD.result_asset_id IS DISTINCT FROM NEW.result_asset_id)
               OR (OLD.started_at IS NOT NULL AND OLD.started_at IS DISTINCT FROM NEW.started_at)
               OR (OLD.output_stored_at IS NOT NULL
                   AND OLD.output_stored_at IS DISTINCT FROM NEW.output_stored_at)
               OR (OLD.measurement_started_at IS NOT NULL
                   AND OLD.measurement_started_at IS DISTINCT FROM NEW.measurement_started_at)
               OR (OLD.finalized_at IS NOT NULL
                   AND OLD.finalized_at IS DISTINCT FROM NEW.finalized_at)
               OR (OLD.result_code IS NOT NULL AND OLD.result_code IS DISTINCT FROM NEW.result_code) THEN
                RAISE EXCEPTION 'transform run evidence is immutable once recorded';
            END IF;
            IF (OLD.started_at IS NULL AND NEW.started_at IS NOT NULL
                AND NOT (OLD.status = 'SPECIFIED' AND NEW.status = 'RUNNING'))
               OR (OLD.result_asset_id IS NULL AND NEW.result_asset_id IS NOT NULL
                   AND NOT (OLD.status = 'RUNNING' AND NEW.status = 'OUTPUT_STORED'))
               OR (OLD.output_stored_at IS NULL AND NEW.output_stored_at IS NOT NULL
                   AND NOT (OLD.status = 'RUNNING' AND NEW.status = 'OUTPUT_STORED'))
               OR (OLD.measurement_started_at IS NULL AND NEW.measurement_started_at IS NOT NULL
                   AND NOT (OLD.status = 'OUTPUT_STORED' AND NEW.status = 'MEASURING'))
               OR (OLD.finalized_at IS NULL AND NEW.finalized_at IS NOT NULL
                   AND NEW.status NOT IN ('COMPLETED','REJECTED','FAILED','CANCELLED'))
               OR (OLD.result_code IS NULL AND NEW.result_code IS NOT NULL
                   AND NEW.status NOT IN ('REJECTED','FAILED','CANCELLED')) THEN
                RAISE EXCEPTION 'transform run evidence does not match state transition';
            END IF;
            allowed_transition :=
                (OLD.status = 'SPECIFIED' AND NEW.status IN ('RUNNING','CANCELLED')) OR
                (OLD.status = 'RUNNING' AND NEW.status IN (
                    'OUTPUT_STORED','REJECTED','FAILED','CANCELLED'
                )) OR
                (OLD.status = 'OUTPUT_STORED' AND NEW.status IN (
                    'MEASURING','REJECTED','FAILED'
                )) OR
                (OLD.status = 'MEASURING' AND NEW.status IN (
                    'COMPLETED','REJECTED','FAILED'
                ));
            IF OLD.status IS DISTINCT FROM NEW.status AND NOT allowed_transition THEN
                RAISE EXCEPTION 'invalid transform run state transition';
            END IF;
            IF NEW.result_asset_id IS NOT NULL THEN
                SELECT * INTO source_asset FROM assets WHERE id = specification.source_asset_id;
                SELECT * INTO result_asset FROM assets WHERE id = NEW.result_asset_id FOR UPDATE;
                IF result_asset.id IS NULL
                   OR result_asset.id = source_asset.id
                   OR result_asset.owner_user_id IS NOT NULL
                   OR result_asset.asset_role IS DISTINCT FROM 'synthetic'
                   OR NOT result_asset.synthetic
                   OR NOT result_asset.is_ai_modified
                   OR result_asset.internal_purpose IS DISTINCT FROM 'synthetic_dataset'
                   OR result_asset.deleted_at IS NOT NULL
                   OR result_asset.width IS DISTINCT FROM specification.output_width
                   OR result_asset.height IS DISTINCT FROM specification.output_height
                   OR result_asset.sha256 IS NOT DISTINCT FROM source_asset.sha256 THEN
                    RAISE EXCEPTION 'transform result requires a distinct immutable synthetic asset';
                END IF;
            END IF;
            IF NEW.status = 'MEASURING' AND NOT EXISTS (
                SELECT 1 FROM synthetic_qa_runs
                 WHERE transform_run_id = NEW.id
                   AND subject_kind = 'GEOMETRY_VARIANT'
                   AND normalized_asset_id = NEW.result_asset_id
                   AND status = 'RUNNING'
            ) THEN
                RAISE EXCEPTION 'measuring transform requires matching running QA';
            END IF;
            IF NEW.status = 'COMPLETED' AND NOT EXISTS (
                SELECT 1 FROM synthetic_qa_runs
                 WHERE transform_run_id = NEW.id
                   AND subject_kind = 'GEOMETRY_VARIANT'
                   AND normalized_asset_id = NEW.result_asset_id
                   AND status = 'PASSED'
            ) THEN
                RAISE EXCEPTION 'completed transform requires matching passed QA';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    op.execute(
        statement.replace("__PLAN_DECLARATION__", plan_declaration).replace(
            "__PLAN_LOCK__", plan_lock
        )
    )


def _install_plan_guard() -> None:
    op.execute(
        """
        CREATE FUNCTION mirror_validate_landmark_warp_plan() RETURNS trigger AS $$
        DECLARE
            specification variant_specifications%ROWTYPE;
            raw_document json;
            raw_point json;
            document jsonb;
            point jsonb;
            triangle jsonb;
            top_level_keys text[];
            point_keys text[];
            point_codes text[] := ARRAY[]::text[];
            referenced_codes text[] := ARRAY[]::text[];
            triangle_keys text[] := ARRAY[]::text[];
            point_count integer := 0;
            triangle_count integer := 0;
            previous_point text := NULL;
            previous_triangle text := NULL;
            current_triangle text;
            triangle_key text;
            first_code text;
            second_code text;
            third_code text;
            coordinate_name text;
            coordinate_value text;
            canonical_coordinate text;
            canonical_authority text;
        BEGIN
            IF TG_OP IN ('UPDATE', 'DELETE') THEN
                RAISE EXCEPTION 'landmark warp plan authority is immutable';
            END IF;
            SELECT * INTO specification FROM variant_specifications
             WHERE id = NEW.variant_specification_id FOR UPDATE;
            IF specification.id IS NULL THEN
                RAISE EXCEPTION 'landmark warp plan requires immutable variant specification';
            END IF;
            IF NEW.schema_version <> 'mirror.synthetic-dataset/LandmarkWarpPlanAuthority/v1'
               OR NEW.plan_schema_version <> 'mirror.synthetic-dataset/LandmarkWarpPlan/v1'
               OR NEW.origin_kind <> 'PREREGISTERED_M4_RESEARCH_PLAN'
               OR NEW.origin_reference !~ '^[A-Za-z0-9][A-Za-z0-9._@-]{2,127}$'
               OR NEW.builder_version <> 'canonical-warp-plan-builder-v1'
               OR NEW.origin_digest !~ '^[0-9a-f]{64}$'
               OR NEW.builder_manifest_digest !~ '^[0-9a-f]{64}$'
               OR NEW.warp_plan_digest !~ '^[0-9a-f]{64}$'
               OR NEW.authority_digest !~ '^[0-9a-f]{64}$'
               OR octet_length(NEW.canonical_payload) > 262144
               OR NEW.canonical_payload ~ '[^\\x20-\\x7e]'
               OR NEW.canonical_payload ~ '[[:space:]]'
               OR position(chr(92) in NEW.canonical_payload) > 0
               OR left(NEW.canonical_payload, 19) <> '{"control_points":['
               OR position('],"specification_digest":"' in NEW.canonical_payload) = 0
               OR position('","triangles":[' in NEW.canonical_payload) = 0
               OR right(NEW.canonical_payload, 2) <> ']}' THEN
                RAISE EXCEPTION 'landmark warp plan authority fields are invalid';
            END IF;
            raw_document := NEW.canonical_payload::json;
            document := raw_document::jsonb;
            SELECT array_agg(entry.key ORDER BY entry.ordinality)
              INTO top_level_keys
              FROM json_each(raw_document) WITH ORDINALITY AS entry(key, value, ordinality);
            IF jsonb_typeof(document) <> 'object'
               OR top_level_keys IS DISTINCT FROM ARRAY[
                   'control_points','specification_digest','triangles'
               ]::text[]
               OR (SELECT count(*) FROM jsonb_object_keys(document)) <> 3
               OR NOT document ?& ARRAY['control_points','specification_digest','triangles']
               OR document->>'specification_digest' IS DISTINCT FROM specification.content_digest
               OR jsonb_typeof(document->'control_points') <> 'array'
               OR jsonb_typeof(document->'triangles') <> 'array' THEN
                RAISE EXCEPTION 'landmark warp plan payload is not closed canonical grammar';
            END IF;
            FOR raw_point IN SELECT value FROM json_array_elements(raw_document->'control_points') LOOP
                point := raw_point::jsonb;
                point_count := point_count + 1;
                SELECT array_agg(entry.key ORDER BY entry.ordinality)
                  INTO point_keys
                  FROM json_each(raw_point) WITH ORDINALITY AS entry(key, value, ordinality);
                IF jsonb_typeof(point) <> 'object'
                   OR point_keys IS DISTINCT FROM ARRAY[
                       'confidence_ppm','destination_x','destination_y',
                       'landmark_code','source_x','source_y'
                   ]::text[]
                   OR (SELECT count(*) FROM jsonb_object_keys(point)) <> 6
                   OR NOT point ?& ARRAY[
                       'confidence_ppm','destination_x','destination_y','landmark_code','source_x','source_y'
                   ]
                   OR jsonb_typeof(point->'landmark_code') <> 'string'
                   OR point->>'landmark_code' !~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$'
                   OR jsonb_typeof(point->'confidence_ppm') <> 'number'
                   OR (point->>'confidence_ppm') !~ '^[0-9]+$'
                   OR (point->>'confidence_ppm')::integer NOT BETWEEN 500000 AND 1000000
                   OR jsonb_typeof(point->'source_x') <> 'number'
                   OR jsonb_typeof(point->'source_y') <> 'number'
                   OR jsonb_typeof(point->'destination_x') <> 'number'
                   OR jsonb_typeof(point->'destination_y') <> 'number'
                   OR (point->>'source_x')::numeric NOT BETWEEN 0 AND 1
                   OR (point->>'source_y')::numeric NOT BETWEEN 0 AND 1
                   OR (point->>'destination_x')::numeric NOT BETWEEN 0 AND 1
                   OR (point->>'destination_y')::numeric NOT BETWEEN 0 AND 1
                   OR (previous_point IS NOT NULL AND point->>'landmark_code' <= previous_point) THEN
                    RAISE EXCEPTION 'landmark warp plan control points are invalid';
                END IF;
                FOREACH coordinate_name IN ARRAY ARRAY[
                    'source_x','source_y','destination_x','destination_y'
                ] LOOP
                    coordinate_value := (raw_point->coordinate_name)::text;
                    canonical_coordinate := to_json(
                        coordinate_value::double precision
                    )::text;
                    IF canonical_coordinate !~ '[.e]' THEN
                        canonical_coordinate := canonical_coordinate || '.0';
                    END IF;
                    IF coordinate_value IS DISTINCT FROM canonical_coordinate THEN
                        RAISE EXCEPTION 'landmark warp plan coordinate is not canonical';
                    END IF;
                END LOOP;
                previous_point := point->>'landmark_code';
                point_codes := array_append(point_codes, previous_point);
            END LOOP;
            IF point_count NOT BETWEEN 3 AND 512
               OR cardinality(point_codes) <> (SELECT count(DISTINCT value) FROM unnest(point_codes) AS value)
               OR NOT EXISTS (
                   SELECT 1 FROM jsonb_array_elements(document->'control_points') AS item
                    WHERE (item->>'source_x')::numeric <> (item->>'destination_x')::numeric
                       OR (item->>'source_y')::numeric <> (item->>'destination_y')::numeric
               ) THEN
                RAISE EXCEPTION 'landmark warp plan control point set is invalid';
            END IF;
            FOR triangle IN SELECT value FROM jsonb_array_elements(document->'triangles') LOOP
                triangle_count := triangle_count + 1;
                IF jsonb_typeof(triangle) <> 'array' OR jsonb_array_length(triangle) <> 3
                   OR EXISTS (
                       SELECT 1 FROM jsonb_array_elements(triangle) AS item
                        WHERE jsonb_typeof(item) <> 'string'
                   ) THEN
                    RAISE EXCEPTION 'landmark warp plan triangle is invalid';
                END IF;
                first_code := triangle->>0;
                second_code := triangle->>1;
                third_code := triangle->>2;
                current_triangle := first_code || E'\\x1f' || second_code || E'\\x1f' || third_code;
                triangle_key := array_to_string(
                    ARRAY(SELECT value FROM unnest(ARRAY[first_code, second_code, third_code]) AS value ORDER BY value),
                    E'\\x1f'
                );
                IF first_code = second_code OR first_code = third_code OR second_code = third_code
                   OR NOT (first_code = ANY(point_codes) AND second_code = ANY(point_codes) AND third_code = ANY(point_codes))
                   OR current_triangle <> least(
                       current_triangle,
                       second_code || E'\\x1f' || third_code || E'\\x1f' || first_code,
                       third_code || E'\\x1f' || first_code || E'\\x1f' || second_code
                   )
                   OR (previous_triangle IS NOT NULL AND current_triangle <= previous_triangle)
                   OR triangle_key = ANY(triangle_keys) THEN
                    RAISE EXCEPTION 'landmark warp plan triangle set is invalid';
                END IF;
                previous_triangle := current_triangle;
                triangle_keys := array_append(triangle_keys, triangle_key);
                referenced_codes := referenced_codes || ARRAY[first_code, second_code, third_code];
            END LOOP;
            IF triangle_count NOT BETWEEN 1 AND 1024
               OR (SELECT count(DISTINCT value) FROM unnest(referenced_codes) AS value) <> point_count THEN
                RAISE EXCEPTION 'landmark warp plan triangles do not fully bind control points';
            END IF;
            IF NEW.warp_plan_digest IS DISTINCT FROM encode(
                sha256((NEW.plan_schema_version || E'\\n' || NEW.canonical_payload)::bytea), 'hex'
            ) THEN
                RAISE EXCEPTION 'landmark warp plan digest mismatch';
            END IF;
            canonical_authority :=
                '{"builder_manifest_digest":"' || NEW.builder_manifest_digest ||
                '","builder_version":"' || NEW.builder_version ||
                '","origin_digest":"' || NEW.origin_digest ||
                '","origin_kind":"' || NEW.origin_kind ||
                '","origin_reference":"' || NEW.origin_reference ||
                '","specification_digest":"' || specification.content_digest ||
                '","warp_plan_digest":"' || NEW.warp_plan_digest || '"}';
            IF NEW.authority_digest IS DISTINCT FROM encode(
                sha256(('mirror.synthetic-dataset/LandmarkWarpPlanAuthority/v1' || E'\\n' || canonical_authority)::bytea), 'hex'
            ) THEN
                RAISE EXCEPTION 'landmark warp plan authority digest mismatch';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_landmark_warp_plans_guard
        BEFORE INSERT OR UPDATE OR DELETE ON landmark_warp_plans
        FOR EACH ROW EXECUTE FUNCTION mirror_validate_landmark_warp_plan();
        """
    )


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM transform_runs) THEN
                RAISE EXCEPTION '0013 upgrade cannot infer landmark warp plan authority for existing transform runs';
            END IF;
        END;
        $$;
        """
    )
    op.create_table(
        "landmark_warp_plans",
        sa.Column("schema_version", sa.String(length=96), nullable=False),
        sa.Column("plan_schema_version", sa.String(length=96), nullable=False),
        sa.Column("variant_specification_id", sa.String(length=32), nullable=False),
        sa.Column("canonical_payload", sa.Text(), nullable=False),
        sa.Column("warp_plan_digest", sa.String(length=64), nullable=False),
        sa.Column("authority_digest", sa.String(length=64), nullable=False),
        sa.Column("origin_kind", sa.String(length=48), nullable=False),
        sa.Column("origin_reference", sa.String(length=128), nullable=False),
        sa.Column("origin_digest", sa.String(length=64), nullable=False),
        sa.Column("builder_version", sa.String(length=64), nullable=False),
        sa.Column("builder_manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/LandmarkWarpPlanAuthority/v1'",
            name=op.f("ck_landmark_warp_plans_schema_version"),
        ),
        sa.CheckConstraint(
            "plan_schema_version = 'mirror.synthetic-dataset/LandmarkWarpPlan/v1'",
            name=op.f("ck_landmark_warp_plans_plan_schema_version"),
        ),
        sa.CheckConstraint(
            "origin_kind = 'PREREGISTERED_M4_RESEARCH_PLAN'",
            name=op.f("ck_landmark_warp_plans_origin_kind"),
        ),
        sa.CheckConstraint(
            "origin_reference ~ '^[A-Za-z0-9][A-Za-z0-9._@-]{2,127}$'",
            name=op.f("ck_landmark_warp_plans_origin_reference"),
        ),
        sa.CheckConstraint(
            "builder_version = 'canonical-warp-plan-builder-v1'",
            name=op.f("ck_landmark_warp_plans_builder_version"),
        ),
        sa.CheckConstraint(
            "octet_length(canonical_payload) BETWEEN 1 AND 262144",
            name=op.f("ck_landmark_warp_plans_payload_size"),
        ),
        sa.CheckConstraint(
            "canonical_payload !~ '[^\\x20-\\x7e]'",
            name=op.f("ck_landmark_warp_plans_payload_ascii"),
        ),
        *[
            sa.CheckConstraint(
                f"{column} ~ '^[0-9a-f]{{64}}$'",
                name=op.f(f"ck_landmark_warp_plans_{column}"),
            )
            for column in (
                "warp_plan_digest",
                "authority_digest",
                "origin_digest",
                "builder_manifest_digest",
            )
        ],
        sa.ForeignKeyConstraint(
            ["variant_specification_id"],
            ["variant_specifications.id"],
            name=op.f("fk_landmark_warp_plans_variant_specification_id_variant_specifications"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_landmark_warp_plans")),
        sa.UniqueConstraint(
            "variant_specification_id",
            name=op.f("uq_landmark_warp_plans_variant_specification_id"),
        ),
        sa.UniqueConstraint(
            "authority_digest", name=op.f("uq_landmark_warp_plans_authority_digest")
        ),
        sa.UniqueConstraint(
            "warp_plan_digest", name=op.f("uq_landmark_warp_plans_warp_plan_digest")
        ),
    )
    _install_plan_guard()
    _replace_transform_run_guard(require_plan=True)


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM landmark_warp_plans)
               OR EXISTS (SELECT 1 FROM transform_runs) THEN
                RAISE EXCEPTION '0013 downgrade would discard landmark warp plan or transform execution authority';
            END IF;
        END;
        $$;
        """
    )
    _replace_transform_run_guard(require_plan=False)
    op.execute("DROP TRIGGER IF EXISTS trg_landmark_warp_plans_guard ON landmark_warp_plans")
    op.execute("DROP FUNCTION IF EXISTS mirror_validate_landmark_warp_plan()")
    op.drop_table("landmark_warp_plans")
