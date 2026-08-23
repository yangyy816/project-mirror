"""Branch-local D02 recovered-source and pair-screening authority.

Revision ID: demo_0003_d02_import_auth
Revises: demo_0002_p3_p7_command_auth
Create Date: 2026-08-24

PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "demo_0003_d02_import_auth"
down_revision: str | None = "demo_0002_p3_p7_command_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROTOTYPE_MIGRATION = True
FORMAL_PHASE_AUTHORITY = False
DIRECT_MAINLINE_CHERRY_PICK = "FORBIDDEN"


_D02_HELPER_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_formal_source_authority_key(
    formal_identity_id text
)
RETURNS text
LANGUAGE sql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
    SELECT mirror_demo_digest(
        'mirror.demo/SourceAuthorityKey/v1',
        jsonb_build_object(
            'source_authority_kind', 'FORMAL_REFERENCE',
            'formal_synthetic_identity_id', formal_identity_id
        )
    );
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_local_source_authority_key(
    recovered_output_id text,
    source_asset_id text,
    source_asset_sha256 text,
    recovered_receipt_digest text
)
RETURNS text
LANGUAGE sql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
    SELECT mirror_demo_digest(
        'mirror.demo/SourceAuthorityKey/v1',
        jsonb_build_object(
            'source_authority_kind', 'DEMO_LOCAL_IMPORTED_COPY',
            'source_output_id', recovered_output_id,
            'formal_canonical_asset_id', source_asset_id,
            'source_asset_sha256', source_asset_sha256,
            'source_receipt_digest', recovered_receipt_digest
        )
    );
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_jsonb_exact_keys(
    input_value jsonb,
    expected_keys text[]
)
RETURNS boolean
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
DECLARE
    actual_keys text[];
    normalized_expected text[];
BEGIN
    IF jsonb_typeof(input_value) <> 'object' THEN
        RETURN false;
    END IF;
    SELECT array_agg(key_name ORDER BY key_name COLLATE "C")
    INTO actual_keys
    FROM jsonb_object_keys(input_value) AS key_name;
    SELECT array_agg(key_name ORDER BY key_name COLLATE "C")
    INTO normalized_expected
    FROM unnest(expected_keys) AS key_name;
    RETURN actual_keys IS NOT DISTINCT FROM normalized_expected;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_round_half_even_ppm(
    fixed18_value text
)
RETURNS integer
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
DECLARE
    scaled_value numeric;
    lower_value numeric;
    fractional_value numeric;
BEGIN
    IF fixed18_value !~ '^(0\.[0-9]{18}|1\.000000000000000000)$' THEN
        RAISE EXCEPTION 'D02 fixed18 value is not canonical and nonnegative';
    END IF;
    scaled_value := fixed18_value::numeric * 1000000;
    lower_value := floor(scaled_value);
    fractional_value := scaled_value - lower_value;
    IF fractional_value < 0.5 THEN
        RETURN lower_value::integer;
    ELSIF fractional_value > 0.5 THEN
        RETURN (lower_value + 1)::integer;
    ELSIF mod(lower_value, 2) = 0 THEN
        RETURN lower_value::integer;
    END IF;
    RETURN (lower_value + 1)::integer;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_d02_dimension_array_valid(
    dimension_keys jsonb,
    maximum_count integer
)
RETURNS boolean
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
DECLARE
    projected text[];
    ordered_candidates constant text[] := ARRAY['jaw_width','chin_height','eye_spacing'];
    selected_value text;
    selected_position integer;
    previous_position integer := 0;
BEGIN
    IF jsonb_typeof(dimension_keys) <> 'array'
        OR jsonb_array_length(dimension_keys) > maximum_count
        OR EXISTS (
            SELECT 1
            FROM jsonb_array_elements(dimension_keys) AS item(value)
            WHERE jsonb_typeof(item.value) <> 'string'
        ) THEN
        RETURN false;
    END IF;
    SELECT array_agg(item.value #>> '{}' ORDER BY item.ordinality)
    INTO projected
    FROM jsonb_array_elements(dimension_keys) WITH ORDINALITY AS item(value, ordinality);
    projected := COALESCE(projected, ARRAY[]::text[]);
    FOREACH selected_value IN ARRAY projected LOOP
        selected_position := array_position(ordered_candidates, selected_value);
        IF selected_position IS NULL OR selected_position <= previous_position THEN
            RETURN false;
        END IF;
        previous_position := selected_position;
    END LOOP;
    RETURN true;
END;
$function$;
"""


_D02_GUARD_SQL = r"""
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
        AND NEW.schema_version = 'mirror.demo/DemoSyntheticIdentity/v2' THEN
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


_LEGACY_GUARD_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_guard_authority()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    expected_payload jsonb;
    expected_digest text;
    close_changed boolean := false;
    tombstone_changed boolean := false;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Demo authority row is append-only: %', TG_TABLE_NAME;
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF TG_TABLE_NAME NOT IN ('demo_actors', 'demo_sessions', 'demo_editing_sessions') THEN
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
    expected_payload := mirror_demo_authority_projection(to_jsonb(NEW), TG_TABLE_NAME);
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


_D02_IDENTITY_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_local_snapshot(
    authority_row demo_synthetic_identities
)
RETURNS void
LANGUAGE plpgsql
AS $function$
DECLARE
    fact_payload jsonb := authority_row.source_fact_snapshot;
    raw_payload jsonb := authority_row.source_fact_snapshot -> 'raw_measurement_authority';
    projection_payload jsonb := authority_row.source_measurement_projection;
    raw_entry jsonb;
    projection_entry jsonb;
    expected_dimension text;
    entry_index integer;
    asset_row assets%ROWTYPE;
    unsupported_reasons constant text[] := ARRAY[
        'MISSING_MEASUREMENT','LOW_CONFIDENCE','OUT_OF_BOUNDS','RUNTIME_UNSUPPORTED'
    ];
BEGIN
    IF NOT mirror_demo_jsonb_exact_keys(
        fact_payload,
        ARRAY[
            'source_output_id','source_asset_sha256','source_asset_byte_size',
            'source_asset_mime_type','source_asset_width','source_asset_height',
            'source_receipt_digest','source_authority_digest','qa_policy_digest',
            'source_qa_snapshot_digest','source_landmark_digest',
            'source_measurement_digest','source_provenance_digest',
            'source_measurement_projection','source_measurement_projection_digest',
            'raw_measurement_authority','raw_measurement_authority_digest',
            'adult_synthetic_attested','original_formal_identity_id_status',
            'measurement_projection_version','measurement_quantization_version',
            'source_p2_candidate_manifest_content_digest',
            'dimension_authority_manifest_content_digest'
        ]
    ) THEN
        RAISE EXCEPTION 'D02 recovered fact snapshot keys are invalid';
    END IF;
    IF NOT mirror_demo_jsonb_exact_keys(
        raw_payload,
        ARRAY[
            'measurement_version','decimal_serialization_version',
            'source_p2_candidate_manifest_content_digest',
            'dimension_authority_manifest_content_digest','ordered_entries'
        ]
    ) OR NOT mirror_demo_jsonb_exact_keys(
        projection_payload,
        ARRAY[
            'measurement_version','measurement_projection_version',
            'measurement_quantization_version',
            'source_p2_candidate_manifest_content_digest',
            'dimension_authority_manifest_content_digest','ordered_entries'
        ]
    ) THEN
        RAISE EXCEPTION 'D02 morphology authority envelope is invalid';
    END IF;
    IF raw_payload ->> 'measurement_version' <> 'demo-d02-face-height-normalized-measurement-v1'
        OR raw_payload ->> 'decimal_serialization_version' <>
           'demo-d02-decimal-fixed18-v1'
        OR projection_payload ->> 'measurement_version' <>
           raw_payload ->> 'measurement_version'
        OR projection_payload ->> 'measurement_projection_version' <>
           fact_payload ->> 'measurement_projection_version'
        OR projection_payload ->> 'measurement_quantization_version' <>
           fact_payload ->> 'measurement_quantization_version'
        OR projection_payload ->> 'measurement_quantization_version' <>
           'demo-d02-round-half-even-ppm-v1'
        OR raw_payload ->> 'source_p2_candidate_manifest_content_digest' <>
           'eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4'
        OR projection_payload ->> 'source_p2_candidate_manifest_content_digest' <>
           'eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4'
        OR fact_payload ->> 'source_p2_candidate_manifest_content_digest' <>
           'eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4'
        OR raw_payload ->> 'dimension_authority_manifest_content_digest' <>
           'd4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a'
        OR projection_payload ->> 'dimension_authority_manifest_content_digest' <>
           'd4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a'
        OR fact_payload ->> 'dimension_authority_manifest_content_digest' <>
           'd4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a' THEN
        RAISE EXCEPTION 'D02 morphology version or manifest binding mismatch';
    END IF;
    IF jsonb_typeof(raw_payload -> 'ordered_entries') <> 'array'
        OR jsonb_array_length(raw_payload -> 'ordered_entries') <> 6
        OR jsonb_typeof(projection_payload -> 'ordered_entries') <> 'array'
        OR jsonb_array_length(projection_payload -> 'ordered_entries') <> 6 THEN
        RAISE EXCEPTION 'D02 morphology authority must contain six ordered entries';
    END IF;

    FOR entry_index IN 0..5 LOOP
        expected_dimension := (ARRAY[
            'cheekbone_width','chin_height','eye_spacing',
            'jaw_width','mouth_width','nose_width'
        ])[entry_index + 1];
        raw_entry := raw_payload -> 'ordered_entries' -> entry_index;
        projection_entry := projection_payload -> 'ordered_entries' -> entry_index;
        IF NOT mirror_demo_jsonb_exact_keys(
            raw_entry,
            ARRAY[
                'dimension_key','support_state','raw_value_fixed18',
                'raw_confidence_fixed18','raw_reliability_fixed18','unsupported_reason'
            ]
        ) OR NOT mirror_demo_jsonb_exact_keys(
            projection_entry,
            ARRAY[
                'dimension_key','support_state','value_ppm','unit',
                'confidence_ppm','reliability_ppm','unsupported_reason'
            ]
        ) OR raw_entry ->> 'dimension_key' <> expected_dimension
            OR projection_entry ->> 'dimension_key' <> expected_dimension
            OR raw_entry ->> 'support_state' IS DISTINCT FROM
               projection_entry ->> 'support_state'
            OR projection_entry ->> 'unit' <> 'FACE_HEIGHT_PPM' THEN
            RAISE EXCEPTION 'D02 morphology entry shape, order or unit mismatch';
        END IF;
        IF raw_entry ->> 'support_state' = 'SUPPORTED' THEN
            IF jsonb_typeof(raw_entry -> 'raw_value_fixed18') IS DISTINCT FROM 'string'
                OR jsonb_typeof(raw_entry -> 'raw_confidence_fixed18') IS DISTINCT FROM 'string'
                OR jsonb_typeof(raw_entry -> 'raw_reliability_fixed18') IS DISTINCT FROM 'string'
                OR raw_entry ->> 'raw_value_fixed18' !~
                   '^(0\.[0-9]{18}|1\.000000000000000000)$'
                OR raw_entry ->> 'raw_confidence_fixed18' !~
                   '^(0\.[0-9]{18}|1\.000000000000000000)$'
                OR raw_entry ->> 'raw_reliability_fixed18' !~
                   '^(0\.[0-9]{18}|1\.000000000000000000)$'
                OR (raw_entry ->> 'raw_value_fixed18')::numeric < 0.000001
                OR (raw_entry ->> 'raw_confidence_fixed18')::numeric < 0.000001
                OR (raw_entry ->> 'raw_reliability_fixed18')::numeric < 0.000001
                OR raw_entry -> 'unsupported_reason' <> 'null'::jsonb
                OR projection_entry -> 'unsupported_reason' <> 'null'::jsonb
                OR jsonb_typeof(projection_entry -> 'value_ppm') IS DISTINCT FROM 'number'
                OR jsonb_typeof(projection_entry -> 'confidence_ppm') IS DISTINCT FROM 'number'
                OR jsonb_typeof(projection_entry -> 'reliability_ppm') IS DISTINCT FROM 'number'
                OR (projection_entry ->> 'value_ppm')::integer < 1
                OR (projection_entry ->> 'value_ppm')::integer > 1000000
                OR (projection_entry ->> 'confidence_ppm')::integer < 1
                OR (projection_entry ->> 'confidence_ppm')::integer > 1000000
                OR (projection_entry ->> 'reliability_ppm')::integer < 1
                OR (projection_entry ->> 'reliability_ppm')::integer > 1000000
                OR (projection_entry ->> 'value_ppm')::integer <>
                   mirror_demo_round_half_even_ppm(raw_entry ->> 'raw_value_fixed18')
                OR (projection_entry ->> 'confidence_ppm')::integer <>
                   mirror_demo_round_half_even_ppm(raw_entry ->> 'raw_confidence_fixed18')
                OR (projection_entry ->> 'reliability_ppm')::integer <>
                   mirror_demo_round_half_even_ppm(raw_entry ->> 'raw_reliability_fixed18') THEN
                RAISE EXCEPTION 'D02 supported morphology entry is invalid';
            END IF;
        ELSIF raw_entry ->> 'support_state' = 'UNSUPPORTED' THEN
            IF raw_entry -> 'raw_value_fixed18' <> 'null'::jsonb
                OR raw_entry -> 'raw_confidence_fixed18' <> 'null'::jsonb
                OR raw_entry -> 'raw_reliability_fixed18' <> 'null'::jsonb
                OR projection_entry -> 'value_ppm' <> 'null'::jsonb
                OR (projection_entry ->> 'confidence_ppm')::integer <> 0
                OR (projection_entry ->> 'reliability_ppm')::integer <> 0
                OR NOT ((raw_entry ->> 'unsupported_reason') = ANY(unsupported_reasons))
                OR projection_entry ->> 'unsupported_reason' IS DISTINCT FROM
                   raw_entry ->> 'unsupported_reason' THEN
                RAISE EXCEPTION 'D02 unsupported morphology entry is invalid';
            END IF;
        ELSE
            RAISE EXCEPTION 'D02 morphology support state is invalid';
        END IF;
    END LOOP;

    SELECT * INTO asset_row FROM assets WHERE id = authority_row.formal_canonical_asset_id;
    IF NOT FOUND
        OR asset_row.owner_user_id IS NOT NULL
        OR asset_row.asset_role <> 'synthetic'
        OR asset_row.internal_purpose <> 'synthetic_dataset'
        OR NOT asset_row.synthetic
        OR asset_row.sha256 <> authority_row.formal_canonical_asset_sha256 THEN
        RAISE EXCEPTION 'D02 local source Asset authority mismatch';
    END IF;
    IF fact_payload ->> 'source_output_id' <> authority_row.source_output_id
        OR fact_payload ->> 'source_asset_sha256' <> asset_row.sha256
        OR (fact_payload ->> 'source_asset_byte_size')::bigint <> asset_row.byte_size
        OR fact_payload ->> 'source_asset_mime_type' <> asset_row.mime_type
        OR (fact_payload ->> 'source_asset_width')::integer <> asset_row.width
        OR (fact_payload ->> 'source_asset_height')::integer <> asset_row.height
        OR fact_payload ->> 'source_receipt_digest' <> authority_row.source_receipt_digest
        OR fact_payload ->> 'source_authority_digest' <> authority_row.source_authority_digest
        OR fact_payload ->> 'source_qa_snapshot_digest' <>
           authority_row.source_qa_snapshot_digest
        OR fact_payload ->> 'source_landmark_digest' <> authority_row.source_landmark_digest
        OR fact_payload ->> 'source_measurement_digest' <>
           authority_row.source_measurement_digest
        OR fact_payload ->> 'source_provenance_digest' <>
           authority_row.source_provenance_digest
        OR fact_payload -> 'source_measurement_projection' IS DISTINCT FROM
           authority_row.source_measurement_projection
        OR fact_payload ->> 'source_measurement_projection_digest' <>
           authority_row.source_measurement_projection_digest
        OR fact_payload ->> 'original_formal_identity_id_status' <>
           authority_row.original_formal_identity_id_status
        OR (fact_payload ->> 'adult_synthetic_attested')::boolean IS NOT TRUE
        OR fact_payload ->> 'qa_policy_digest' !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'D02 recovered fact snapshot disagrees with structured authority';
    END IF;
    IF fact_payload ->> 'raw_measurement_authority_digest' IS DISTINCT FROM
       mirror_demo_digest('mirror.demo/D02RawMeasurementAuthority/v1', raw_payload)
        OR authority_row.source_measurement_projection_digest IS DISTINCT FROM
           mirror_demo_digest(
               'mirror.demo/D02MorphologyProjection/v1',
               authority_row.source_measurement_projection
           )
        OR authority_row.source_fact_snapshot_digest IS DISTINCT FROM
           mirror_demo_digest(
               'mirror.demo/RecoveredSyntheticIdentityFacts/v2',
               authority_row.source_fact_snapshot
           ) THEN
        RAISE EXCEPTION 'D02 recovered morphology or fact digest mismatch';
    END IF;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_synthetic_identity()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    derived_kind text;
    derived_key text;
    expected_event_id text;
    expected_qa_snapshot_digest text;
    previous_admission demo_synthetic_identities%ROWTYPE;
    has_previous boolean;
BEGIN
    IF NEW.schema_version <> 'mirror.demo/DemoSyntheticIdentity/v2' THEN
        RAISE EXCEPTION 'New Demo synthetic identity events must use v2 authority';
    END IF;
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
    IF derived_key IS NULL THEN
        RAISE EXCEPTION 'D02 source authority key cannot be derived';
    END IF;
    PERFORM pg_advisory_xact_lock(
        hashtextextended('mirror.demo.synthetic-admission-v2/' || derived_key, 0)
    );
    SELECT * INTO previous_admission
    FROM demo_synthetic_identities
    WHERE source_authority_key = derived_key
    ORDER BY admission_sequence DESC, id DESC
    LIMIT 1
    FOR UPDATE;
    has_previous := FOUND;

    IF NOT has_previous THEN
        IF NEW.admission_sequence <> 1 OR NEW.admission_action <> 'ADMIT'
            OR NEW.supersedes_id IS NOT NULL THEN
            RAISE EXCEPTION 'First D02 source admission event must be ADMIT';
        END IF;
    ELSIF NEW.admission_sequence <> previous_admission.admission_sequence + 1
        OR NEW.supersedes_id IS DISTINCT FROM previous_admission.id
        OR NEW.admission_action = previous_admission.admission_action
        OR previous_admission.source_authority_kind <> derived_kind THEN
        RAISE EXCEPTION 'D02 source admission chain is not the next alternating event';
    END IF;

    expected_event_id := substring(
        mirror_demo_digest(
            'mirror.demo/DemoSyntheticIdentityAdmissionEventId/v2',
            jsonb_build_object(
                'source_authority_kind', derived_kind,
                'source_authority_key', derived_key,
                'admission_sequence', NEW.admission_sequence,
                'admission_action', NEW.admission_action,
                'supersedes_id', NEW.supersedes_id,
                'admission_config_digest', NEW.admission_config_digest,
                'canonical_payload_digest', NEW.content_digest
            )
        )
        FROM 1 FOR 32
    );
    IF NEW.id <> expected_event_id THEN
        RAISE EXCEPTION 'D02 synthetic admission event ID mismatch';
    END IF;

    IF NEW.admission_action = 'REVOKE' THEN
        IF NOT has_previous
            OR NEW.formal_canonical_asset_id IS DISTINCT FROM
               previous_admission.formal_canonical_asset_id
            OR NEW.formal_canonical_asset_sha256 IS DISTINCT FROM
               previous_admission.formal_canonical_asset_sha256 THEN
            RAISE EXCEPTION 'D02 revocation must copy source Asset authority';
        END IF;
        IF derived_kind = 'FORMAL_REFERENCE' AND (
            NEW.formal_synthetic_identity_id IS DISTINCT FROM
                previous_admission.formal_synthetic_identity_id
            OR NEW.formal_accepted_qa_run_id IS DISTINCT FROM
                previous_admission.formal_accepted_qa_run_id
            OR NEW.formal_accepted_qa_snapshot_digest IS DISTINCT FROM
                previous_admission.formal_accepted_qa_snapshot_digest
        ) THEN
            RAISE EXCEPTION 'D02 formal revocation must copy the frozen snapshot';
        ELSIF derived_kind = 'DEMO_LOCAL_IMPORTED_COPY' AND (
            NEW.source_output_id IS DISTINCT FROM previous_admission.source_output_id
            OR NEW.source_receipt_digest IS DISTINCT FROM
                previous_admission.source_receipt_digest
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
        ) THEN
            RAISE EXCEPTION 'D02 local revocation must copy recovered authority';
        END IF;
        RETURN NEW;
    END IF;

    IF derived_kind = 'FORMAL_REFERENCE' THEN
        expected_qa_snapshot_digest := mirror_demo_formal_qa_snapshot_digest(
            NEW.formal_accepted_qa_run_id
        );
        IF expected_qa_snapshot_digest IS DISTINCT FROM
           NEW.formal_accepted_qa_snapshot_digest OR NOT EXISTS (
            SELECT 1
            FROM synthetic_identities identity_row
            JOIN synthetic_qa_runs qa_row ON qa_row.id = identity_row.accepted_qa_run_id
            JOIN assets asset_row ON asset_row.id = identity_row.canonical_asset_id
            WHERE identity_row.id = NEW.formal_synthetic_identity_id
              AND identity_row.bank_version_id IS NULL
              AND identity_row.authority_kind = 'CANONICAL_QA'
              AND identity_row.adult_synthetic_attested
              AND identity_row.canonical_asset_id = NEW.formal_canonical_asset_id
              AND identity_row.accepted_qa_run_id = NEW.formal_accepted_qa_run_id
              AND qa_row.subject_kind = 'CANONICAL_BASE'
              AND qa_row.status = 'PASSED'
              AND qa_row.normalized_asset_id = NEW.formal_canonical_asset_id
              AND asset_row.owner_user_id IS NULL
              AND asset_row.asset_role = 'synthetic'
              AND asset_row.internal_purpose = 'synthetic_dataset'
              AND asset_row.synthetic
              AND asset_row.deleted_at IS NULL
              AND asset_row.sha256 = NEW.formal_canonical_asset_sha256
        ) THEN
            RAISE EXCEPTION 'D02 formal source snapshot does not match live authority';
        END IF;
    ELSE
        PERFORM mirror_demo_validate_d02_local_snapshot(NEW);
        IF NOT EXISTS (
            SELECT 1 FROM assets asset_row
            WHERE asset_row.id = NEW.formal_canonical_asset_id
              AND asset_row.deleted_at IS NULL
              AND asset_row.is_ai_generated
              AND NOT asset_row.is_ai_modified
        ) THEN
            RAISE EXCEPTION 'D02 local source Asset is not live original synthetic authority';
        END IF;
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_require_current_synthetic_admission(
    authority_admission_id text
)
RETURNS void
LANGUAGE plpgsql
AS $function$
DECLARE
    admission_row demo_synthetic_identities%ROWTYPE;
    latest_admission_id text;
BEGIN
    SELECT * INTO admission_row
    FROM demo_synthetic_identities
    WHERE id = authority_admission_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo synthetic admission authority does not exist';
    END IF;
    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            'mirror.demo.synthetic-admission-v2/' || admission_row.source_authority_key,
            0
        )
    );
    SELECT id INTO latest_admission_id
    FROM demo_synthetic_identities
    WHERE source_authority_key = admission_row.source_authority_key
    ORDER BY admission_sequence DESC, id DESC
    LIMIT 1;
    IF latest_admission_id IS DISTINCT FROM admission_row.id
        OR admission_row.admission_action <> 'ADMIT' THEN
        RAISE EXCEPTION 'Demo synthetic admission is not the current eligible row';
    END IF;
    PERFORM mirror_demo_require_asset(
        admission_row.formal_canonical_asset_id,
        admission_row.formal_canonical_asset_sha256
    );
    IF admission_row.source_authority_kind = 'FORMAL_REFERENCE' AND NOT EXISTS (
        SELECT 1
        FROM synthetic_identities identity_row
        JOIN synthetic_qa_runs qa_row ON qa_row.id = identity_row.accepted_qa_run_id
        WHERE identity_row.id = admission_row.formal_synthetic_identity_id
          AND identity_row.canonical_asset_id = admission_row.formal_canonical_asset_id
          AND identity_row.accepted_qa_run_id = admission_row.formal_accepted_qa_run_id
          AND qa_row.status = 'PASSED'
          AND mirror_demo_formal_qa_snapshot_digest(qa_row.id) =
              admission_row.formal_accepted_qa_snapshot_digest
    ) THEN
        RAISE EXCEPTION 'Demo formal synthetic admission live authority mismatch';
    END IF;
END;
$function$;
"""


_LEGACY_CURRENT_ADMISSION_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_require_current_synthetic_admission(
    authority_admission_id text
)
RETURNS void
LANGUAGE plpgsql
AS $function$
DECLARE
    admission_row record;
    latest_admission_id text;
BEGIN
    SELECT * INTO admission_row FROM demo_synthetic_identities
    WHERE id = authority_admission_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo synthetic admission authority does not exist';
    END IF;
    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            'mirror.demo.synthetic-admission/' || admission_row.formal_synthetic_identity_id,
            0
        )
    );
    SELECT id INTO latest_admission_id
    FROM demo_synthetic_identities
    WHERE formal_synthetic_identity_id = admission_row.formal_synthetic_identity_id
    ORDER BY admission_sequence DESC
    LIMIT 1;
    IF latest_admission_id IS DISTINCT FROM admission_row.id
        OR admission_row.admission_action <> 'ADMIT' THEN
        RAISE EXCEPTION 'Demo synthetic admission is not the current eligible row';
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM synthetic_identities identity_row
        JOIN synthetic_qa_runs qa_row ON qa_row.id = identity_row.accepted_qa_run_id
        JOIN assets asset_row ON asset_row.id = identity_row.canonical_asset_id
        WHERE identity_row.id = admission_row.formal_synthetic_identity_id
          AND identity_row.bank_version_id IS NULL
          AND identity_row.authority_kind = 'CANONICAL_QA'
          AND identity_row.adult_synthetic_attested
          AND identity_row.canonical_asset_id = admission_row.formal_canonical_asset_id
          AND identity_row.accepted_qa_run_id = admission_row.formal_accepted_qa_run_id
          AND qa_row.subject_kind = 'CANONICAL_BASE'
          AND qa_row.status = 'PASSED'
          AND qa_row.normalized_asset_id = admission_row.formal_canonical_asset_id
          AND asset_row.owner_user_id IS NULL
          AND asset_row.asset_role = 'synthetic'
          AND asset_row.internal_purpose = 'synthetic_dataset'
          AND asset_row.synthetic
          AND asset_row.deleted_at IS NULL
          AND asset_row.sha256 = admission_row.formal_canonical_asset_sha256
          AND mirror_demo_formal_qa_snapshot_digest(qa_row.id) =
              admission_row.formal_accepted_qa_snapshot_digest
    ) THEN
        RAISE EXCEPTION 'Demo synthetic admission live authority no longer matches snapshot';
    END IF;
END;
$function$;
"""


_D02_REPORT_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_screening_report()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    expected_id text;
    expected_eligible jsonb;
    selected_manifest jsonb;
BEGIN
    IF NEW.schema_version <> 'mirror.demo/D02PairScreeningReport/v1' THEN
        RAISE EXCEPTION 'D02 screening report schema is invalid';
    END IF;
    IF NOT mirror_demo_jsonb_exact_keys(
        NEW.report_payload,
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
    ) OR NOT mirror_demo_jsonb_exact_keys(
        NEW.report_payload -> 'schema_and_policy',
        ARRAY[
            'source_manifest_digest','case_manifest_digest','screening_policy_digest',
            'runtime_manifest_digest','vision_model_manifest_digest','topology_digest',
            'measurement_config_digest','manual_review_policy_digest',
            'duplicate_policy_digest','phash_implementation_digest'
        ]
    ) THEN
        RAISE EXCEPTION 'D02 screening report top-level authority is invalid';
    END IF;
    IF NEW.report_payload -> 'schema_and_policy' IS DISTINCT FROM jsonb_build_object(
        'source_manifest_digest', NEW.source_manifest_digest,
        'case_manifest_digest', NEW.case_manifest_digest,
        'screening_policy_digest', NEW.screening_policy_digest,
        'runtime_manifest_digest', NEW.runtime_manifest_digest,
        'vision_model_manifest_digest', NEW.vision_model_manifest_digest,
        'topology_digest', NEW.topology_digest,
        'measurement_config_digest', NEW.measurement_config_digest,
        'manual_review_policy_digest', NEW.manual_review_policy_digest,
        'duplicate_policy_digest', NEW.duplicate_policy_digest,
        'phash_implementation_digest', NEW.phash_implementation_digest
    ) THEN
        RAISE EXCEPTION 'D02 screening report policy digests disagree with columns';
    END IF;
    IF jsonb_typeof(NEW.report_payload -> 'ordered_source_manifest') <> 'array'
        OR jsonb_array_length(NEW.report_payload -> 'ordered_source_manifest') <> 4
        OR jsonb_typeof(NEW.report_payload -> 'ordered_case_manifest') <> 'array'
        OR jsonb_array_length(NEW.report_payload -> 'ordered_case_manifest') <> 48
        OR jsonb_typeof(NEW.report_payload -> 'source_m3_repeat_evidence') <> 'array'
        OR jsonb_array_length(NEW.report_payload -> 'source_m3_repeat_evidence') <> 12
        OR jsonb_typeof(NEW.report_payload -> 'm4_repeat_evidence') <> 'array'
        OR jsonb_array_length(NEW.report_payload -> 'm4_repeat_evidence') <> 96
        OR jsonb_typeof(NEW.report_payload -> 'result_m3_repeat_evidence') <> 'array'
        OR jsonb_array_length(NEW.report_payload -> 'result_m3_repeat_evidence') <> 144
        OR jsonb_typeof(NEW.report_payload -> 'measurement_gate_evidence') <> 'array'
        OR jsonb_array_length(NEW.report_payload -> 'measurement_gate_evidence') <> 48
        OR jsonb_typeof(
            NEW.report_payload -> 'decode_structure_immutability_evidence'
        ) <> 'array'
        OR jsonb_array_length(
            NEW.report_payload -> 'decode_structure_immutability_evidence'
        ) <> 48
        OR jsonb_typeof(NEW.report_payload -> 'manual_review_evidence') <> 'array'
        OR jsonb_array_length(NEW.report_payload -> 'manual_review_evidence') <> 48
        OR jsonb_typeof(NEW.report_payload -> 'pair_quality_evidence') <> 'array'
        OR jsonb_array_length(NEW.report_payload -> 'pair_quality_evidence') <> 24
        OR jsonb_typeof(NEW.report_payload -> 'dimension_eligibility') <> 'array'
        OR jsonb_array_length(NEW.report_payload -> 'dimension_eligibility') <> 3
        OR jsonb_typeof(NEW.report_payload -> 'fixed_priority_selection_trace') <> 'array'
        OR jsonb_array_length(NEW.report_payload -> 'fixed_priority_selection_trace') <> 3
        OR jsonb_typeof(NEW.report_payload -> 'selected_pair_manifest') <> 'array' THEN
        RAISE EXCEPTION 'D02 screening report evidence cardinality is invalid';
    END IF;
    IF NOT mirror_demo_jsonb_exact_keys(
        NEW.report_payload -> 'exact_duplicate_evidence',
        ARRAY['image_records','exact_sha_gate_passed']
    ) OR jsonb_typeof(
        NEW.report_payload -> 'exact_duplicate_evidence' -> 'image_records'
    ) <> 'array' OR jsonb_array_length(
        NEW.report_payload -> 'exact_duplicate_evidence' -> 'image_records'
    ) <> 52 OR jsonb_typeof(
        NEW.report_payload -> 'exact_duplicate_evidence' -> 'exact_sha_gate_passed'
    ) <> 'boolean' OR NOT mirror_demo_jsonb_exact_keys(
        NEW.report_payload -> 'phash_observation_evidence',
        ARRAY['implementation_digest','comparisons']
    ) OR NEW.report_payload -> 'phash_observation_evidence' ->>
        'implementation_digest' <> NEW.phash_implementation_digest
        OR jsonb_typeof(
            NEW.report_payload -> 'phash_observation_evidence' -> 'comparisons'
        ) <> 'array'
        OR jsonb_array_length(
            NEW.report_payload -> 'phash_observation_evidence' -> 'comparisons'
        ) <> 1326 THEN
        RAISE EXCEPTION 'D02 duplicate or pHash evidence is invalid';
    END IF;
    IF NOT mirror_demo_jsonb_exact_keys(
        NEW.report_payload -> 'network_and_runtime_boundary',
        ARRAY[
            'public_internet_egress','localhost_and_docker_internal_network',
            'production_provider_calls','runtime_generation_calls'
        ]
    ) OR NEW.report_payload -> 'network_and_runtime_boundary' ->>
        'public_internet_egress' <> 'DENIED'
        OR NEW.report_payload -> 'network_and_runtime_boundary' ->
           'localhost_and_docker_internal_network' <> 'true'::jsonb
        OR (NEW.report_payload -> 'network_and_runtime_boundary' ->>
            'production_provider_calls')::integer <> 0
        OR (NEW.report_payload -> 'network_and_runtime_boundary' ->>
            'runtime_generation_calls')::integer <> 0 THEN
        RAISE EXCEPTION 'D02 screening report network boundary is invalid';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM jsonb_array_elements(NEW.report_payload -> 'dimension_eligibility')
             WITH ORDINALITY AS item(value, ordinality)
        WHERE NOT mirror_demo_jsonb_exact_keys(
            item.value,
            ARRAY[
                'dimension_key','priority_index','eligible',
                'sixteen_side_gate_digest','eight_pair_gate_digest','failure_reasons'
            ]
        ) OR item.value ->> 'dimension_key' <>
            (ARRAY['jaw_width','chin_height','eye_spacing'])[item.ordinality]
          OR (item.value ->> 'priority_index')::integer <> item.ordinality
          OR jsonb_typeof(item.value -> 'eligible') IS DISTINCT FROM 'boolean'
          OR item.value ->> 'sixteen_side_gate_digest' !~ '^[0-9a-f]{64}$'
          OR item.value ->> 'eight_pair_gate_digest' !~ '^[0-9a-f]{64}$'
          OR jsonb_typeof(item.value -> 'failure_reasons') IS DISTINCT FROM 'array'
    ) THEN
        RAISE EXCEPTION 'D02 dimension eligibility evidence is invalid';
    END IF;
    SELECT COALESCE(
        jsonb_agg(item.value -> 'dimension_key' ORDER BY item.ordinality),
        '[]'::jsonb
    )
    INTO expected_eligible
    FROM jsonb_array_elements(NEW.report_payload -> 'dimension_eligibility')
         WITH ORDINALITY AS item(value, ordinality)
    WHERE item.value -> 'eligible' = 'true'::jsonb;
    IF NEW.eligible_dimension_keys IS DISTINCT FROM expected_eligible
        OR NOT mirror_demo_d02_dimension_array_valid(NEW.eligible_dimension_keys, 3)
        OR NOT mirror_demo_d02_dimension_array_valid(NEW.selected_dimension_keys, 2) THEN
        RAISE EXCEPTION 'D02 screening report dimension projection is invalid';
    END IF;
    selected_manifest := NEW.report_payload -> 'selected_pair_manifest';
    IF NEW.status = 'PASSED' THEN
        IF jsonb_array_length(selected_manifest) <> 16
            OR jsonb_array_length(NEW.eligible_dimension_keys) < 2
            OR NEW.selected_dimension_keys IS DISTINCT FROM
               (SELECT jsonb_agg(item.value ORDER BY item.ordinality)
                FROM jsonb_array_elements(NEW.eligible_dimension_keys)
                     WITH ORDINALITY AS item(value, ordinality)
                WHERE item.ordinality <= 2)
            OR NEW.selected_pair_manifest_digest IS DISTINCT FROM
               mirror_demo_digest(
                   'mirror.demo/D02SelectedPairManifest/v1',
                   selected_manifest
               ) THEN
            RAISE EXCEPTION 'D02 PASSED report selection authority is invalid';
        END IF;
    ELSIF jsonb_array_length(selected_manifest) <> 0
        OR NEW.selected_dimension_keys <> '[]'::jsonb
        OR NEW.selected_pair_manifest_digest IS NOT NULL THEN
        RAISE EXCEPTION 'D02 FAILED report cannot expose selected authority';
    END IF;
    IF NEW.source_manifest_digest IS DISTINCT FROM mirror_demo_digest(
        'mirror.demo/D02SourceAuthorityManifest/v1',
        NEW.report_payload -> 'ordered_source_manifest'
    ) OR NEW.case_manifest_digest IS DISTINCT FROM mirror_demo_digest(
        'mirror.demo/D02GeometryCaseManifest/v1',
        NEW.report_payload -> 'ordered_case_manifest'
    ) OR NEW.report_digest IS DISTINCT FROM mirror_demo_digest(
        NEW.schema_version,
        NEW.report_payload
    ) THEN
        RAISE EXCEPTION 'D02 screening report manifest or report digest mismatch';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM jsonb_array_elements(
            NEW.report_payload -> 'ordered_source_manifest'
        ) WITH ORDINALITY AS source_entry(value, ordinality)
        WHERE NOT mirror_demo_jsonb_exact_keys(
            source_entry.value,
            ARRAY[
                'source_admission_event_id','source_asset_id',
                'source_asset_sha256','source_authority_key'
            ]
        )
        OR source_entry.value ->> 'source_admission_event_id' !~ '^[0-9a-f]{32}$'
        OR source_entry.value ->> 'source_asset_id' !~ '^[0-9a-f]{32}$'
        OR source_entry.value ->> 'source_asset_sha256' !~ '^[0-9a-f]{64}$'
        OR source_entry.value ->> 'source_authority_key' !~ '^[0-9a-f]{64}$'
        OR NOT EXISTS (
            SELECT 1
            FROM demo_synthetic_identities identity_row
            JOIN assets source_asset
              ON source_asset.id = identity_row.formal_canonical_asset_id
            WHERE identity_row.id =
                  source_entry.value ->> 'source_admission_event_id'
              AND identity_row.source_authority_key =
                  source_entry.value ->> 'source_authority_key'
              AND identity_row.formal_canonical_asset_id =
                  source_entry.value ->> 'source_asset_id'
              AND identity_row.formal_canonical_asset_sha256 =
                  source_entry.value ->> 'source_asset_sha256'
              AND identity_row.admission_action = 'ADMIT'
              AND source_asset.sha256 =
                  source_entry.value ->> 'source_asset_sha256'
              AND source_asset.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM demo_synthetic_identities later_event
                  WHERE later_event.source_authority_key =
                        identity_row.source_authority_key
                    AND later_event.admission_sequence >
                        identity_row.admission_sequence
              )
        )
        OR (
            source_entry.ordinality > 1
            AND (
                SELECT prior.value ->> 'source_authority_key'
                FROM jsonb_array_elements(
                    NEW.report_payload -> 'ordered_source_manifest'
                ) WITH ORDINALITY AS prior(value, ordinality)
                WHERE prior.ordinality = source_entry.ordinality - 1
            ) >= source_entry.value ->> 'source_authority_key'
        )
    ) OR (
        SELECT count(DISTINCT source_entry.value ->> 'source_admission_event_id')
        FROM jsonb_array_elements(
            NEW.report_payload -> 'ordered_source_manifest'
        ) AS source_entry(value)
    ) <> 4 OR (
        SELECT count(DISTINCT source_entry.value ->> 'source_asset_id')
        FROM jsonb_array_elements(
            NEW.report_payload -> 'ordered_source_manifest'
        ) AS source_entry(value)
    ) <> 4 OR (
        SELECT count(DISTINCT source_entry.value ->> 'source_authority_key')
        FROM jsonb_array_elements(
            NEW.report_payload -> 'ordered_source_manifest'
        ) AS source_entry(value)
    ) <> 4 THEN
        RAISE EXCEPTION 'D02 screening report source manifest authority is invalid';
    END IF;
    IF NEW.status = 'PASSED' AND (
        EXISTS (
            SELECT 1
            FROM jsonb_array_elements(
                NEW.report_payload -> 'selected_pair_manifest'
            ) AS selected_pair(value)
            WHERE NOT mirror_demo_jsonb_exact_keys(
                selected_pair.value,
                ARRAY[
                    'dimension_key','magnitude_ppm',
                    'pair_screening_record_digest','source_admission_event_id'
                ]
            )
            OR selected_pair.value ->> 'dimension_key' NOT IN (
                SELECT dimension.value #>> '{}'
                FROM jsonb_array_elements(NEW.selected_dimension_keys)
                     AS dimension(value)
            )
            OR selected_pair.value ->> 'magnitude_ppm' NOT IN ('15000','30000')
            OR selected_pair.value ->> 'pair_screening_record_digest'
               !~ '^[0-9a-f]{64}$'
            OR selected_pair.value ->> 'source_admission_event_id'
               !~ '^[0-9a-f]{32}$'
            OR NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(
                    NEW.report_payload -> 'ordered_source_manifest'
                ) AS source_entry(value)
                WHERE source_entry.value ->> 'source_admission_event_id' =
                      selected_pair.value ->> 'source_admission_event_id'
            )
        )
        OR (
            SELECT count(DISTINCT selected_pair.value ->>
                'pair_screening_record_digest')
            FROM jsonb_array_elements(
                NEW.report_payload -> 'selected_pair_manifest'
            ) AS selected_pair(value)
        ) <> 16
        OR (
            SELECT count(DISTINCT selected_pair.value ->>
                'source_admission_event_id')
            FROM jsonb_array_elements(
                NEW.report_payload -> 'selected_pair_manifest'
            ) AS selected_pair(value)
        ) <> 4
        OR (
            SELECT count(DISTINCT selected_pair.value ->> 'dimension_key')
            FROM jsonb_array_elements(
                NEW.report_payload -> 'selected_pair_manifest'
            ) AS selected_pair(value)
        ) <> 2
        OR (
            SELECT count(DISTINCT selected_pair.value ->> 'magnitude_ppm')
            FROM jsonb_array_elements(
                NEW.report_payload -> 'selected_pair_manifest'
            ) AS selected_pair(value)
        ) <> 2
        OR EXISTS (
            SELECT 1
            FROM jsonb_array_elements(
                NEW.report_payload -> 'selected_pair_manifest'
            ) AS selected_pair(value)
            GROUP BY
                selected_pair.value ->> 'source_admission_event_id',
                selected_pair.value ->> 'dimension_key',
                selected_pair.value ->> 'magnitude_ppm'
            HAVING count(*) <> 1
        )
    ) THEN
        RAISE EXCEPTION 'D02 selected pair manifest authority is invalid';
    END IF;
    expected_id := substring(
        mirror_demo_digest(
            'mirror.demo/D02PairScreeningReportId/v1',
            jsonb_build_object('report_digest', NEW.report_digest)
        )
        FROM 1 FOR 32
    );
    IF NEW.id <> expected_id THEN
        RAISE EXCEPTION 'D02 screening report ID mismatch';
    END IF;
    RETURN NEW;
END;
$function$;
"""


_D02_BANK_PAIR_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_question_bank_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    report_row demo_pair_screening_reports%ROWTYPE;
    dimension_entry jsonb;
    entry_index integer;
    expected_dimension text;
    expected_priority integer;
    expected_id text;
BEGIN
    IF NEW.schema_version <> 'mirror.demo/DemoQuestionBank/v2' THEN
        RAISE EXCEPTION 'New Demo question banks must use v2 authority';
    END IF;
    SELECT * INTO report_row
    FROM demo_pair_screening_reports
    WHERE id = NEW.screening_report_id
      AND report_digest = NEW.screening_report_digest
      AND status = 'PASSED';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'D02 question bank requires a PASSED screening report';
    END IF;
    IF NOT mirror_demo_jsonb_exact_keys(
        NEW.dimension_manifest,
        ARRAY[
            'schema_version','screening_report_id','screening_report_digest',
            'source_manifest_digest','source_p2_candidate_manifest_content_digest',
            'dimension_authority_manifest_content_digest',
            'selected_pair_manifest_digest','selected_dimensions'
        ]
    ) OR NEW.dimension_manifest ->> 'schema_version' <>
        'mirror.demo/D02QuestionBankDimensionManifest/v1'
        OR NEW.dimension_manifest ->> 'screening_report_id' <> NEW.screening_report_id
        OR NEW.dimension_manifest ->> 'screening_report_digest' <>
           NEW.screening_report_digest
        OR NEW.dimension_manifest ->> 'source_manifest_digest' <>
           report_row.source_manifest_digest
        OR NEW.dimension_manifest ->> 'source_p2_candidate_manifest_content_digest' <>
           'eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4'
        OR NEW.dimension_manifest ->> 'dimension_authority_manifest_content_digest' <>
           'd4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a'
        OR NEW.dimension_manifest ->> 'selected_pair_manifest_digest' <>
           report_row.selected_pair_manifest_digest
        OR NEW.pair_manifest_digest <> report_row.selected_pair_manifest_digest
        OR jsonb_typeof(NEW.dimension_manifest -> 'selected_dimensions') <> 'array'
        OR jsonb_array_length(NEW.dimension_manifest -> 'selected_dimensions') <> 2 THEN
        RAISE EXCEPTION 'D02 question bank dimension manifest is invalid';
    END IF;
    FOR entry_index IN 0..1 LOOP
        dimension_entry := NEW.dimension_manifest -> 'selected_dimensions' -> entry_index;
        expected_dimension := report_row.selected_dimension_keys ->> entry_index;
        expected_priority := array_position(
            ARRAY['jaw_width','chin_height','eye_spacing'],
            expected_dimension
        );
        IF NOT mirror_demo_jsonb_exact_keys(
            dimension_entry,
            ARRAY[
                'dimension_key','priority_index','sixteen_side_gate_digest',
                'eight_pair_gate_digest'
            ]
        ) OR dimension_entry ->> 'dimension_key' <> expected_dimension
            OR (dimension_entry ->> 'priority_index')::integer <> expected_priority
            OR dimension_entry ->> 'sixteen_side_gate_digest' !~ '^[0-9a-f]{64}$'
            OR dimension_entry ->> 'eight_pair_gate_digest' !~ '^[0-9a-f]{64}$' THEN
            RAISE EXCEPTION 'D02 selected dimension authority is invalid';
        END IF;
    END LOOP;
    expected_id := substring(
        mirror_demo_digest(
            'mirror.demo/D02QuestionBankId/v1',
            jsonb_build_object(
                'screening_report_id', NEW.screening_report_id,
                'screening_report_digest', NEW.screening_report_digest,
                'selected_pair_manifest_digest', NEW.pair_manifest_digest,
                'algorithm_config_digest', NEW.algorithm_config_digest
            )
        )
        FROM 1 FOR 32
    );
    IF NEW.id <> expected_id THEN
        RAISE EXCEPTION 'D02 question bank ID mismatch';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_question_pair_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    bank_row demo_question_banks%ROWTYPE;
    report_row demo_pair_screening_reports%ROWTYPE;
    identity_row demo_synthetic_identities%ROWTYPE;
    side_payload jsonb;
    side_name text;
    expected_result_asset_id text;
    expected_result_sha text;
    expected_variant_id text;
    expected_direction text;
    expected_signed_prefix text;
    expected_id text;
BEGIN
    IF NEW.schema_version <> 'mirror.demo/DemoQuestionPair/v2' THEN
        RAISE EXCEPTION 'New Demo question pairs must use v2 authority';
    END IF;
    SELECT * INTO bank_row FROM demo_question_banks
    WHERE id = NEW.question_bank_id
      AND schema_version = 'mirror.demo/DemoQuestionBank/v2';
    SELECT * INTO report_row FROM demo_pair_screening_reports
    WHERE id = NEW.screening_report_id
      AND report_digest = NEW.screening_report_digest
      AND status = 'PASSED';
    SELECT * INTO identity_row FROM demo_synthetic_identities
    WHERE id = NEW.demo_synthetic_identity_id;
    IF bank_row.id IS NULL OR report_row.id IS NULL OR identity_row.id IS NULL
        OR bank_row.screening_report_id <> NEW.screening_report_id
        OR bank_row.screening_report_digest <> NEW.screening_report_digest
        OR identity_row.source_authority_key IS NULL
        OR identity_row.formal_canonical_asset_id <> NEW.source_asset_id
        OR identity_row.formal_canonical_asset_sha256 <> NEW.source_asset_sha256 THEN
        RAISE EXCEPTION 'D02 pair bank, report or source binding is invalid';
    END IF;
    PERFORM mirror_demo_require_current_synthetic_admission(NEW.demo_synthetic_identity_id);
    IF NOT mirror_demo_jsonb_exact_keys(
        NEW.qa_payload,
        ARRAY[
            'schema_version','screening_report_id','screening_report_digest',
            'pair_screening_record_digest','source_authority_key',
            'source_admission_event_id','source_asset','dimension_key','magnitude_ppm',
            'left','right','pair_quality_ppm','lock_conclusion','lock_policy_digest'
        ]
    ) OR NEW.qa_payload ? 'qa_payload_digest'
        OR NEW.qa_payload ->> 'schema_version' <>
           'mirror.demo/D02QuestionPairQAPayload/v1'
        OR NEW.qa_payload ->> 'screening_report_id' <> NEW.screening_report_id
        OR NEW.qa_payload ->> 'screening_report_digest' <> NEW.screening_report_digest
        OR NEW.qa_payload ->> 'pair_screening_record_digest' !~ '^[0-9a-f]{64}$'
        OR NEW.qa_payload ->> 'source_authority_key' <>
           identity_row.source_authority_key
        OR NEW.qa_payload ->> 'source_admission_event_id' <> NEW.demo_synthetic_identity_id
        OR NEW.qa_payload ->> 'dimension_key' <> NEW.dimension_key
        OR (NEW.qa_payload ->> 'magnitude_ppm')::integer <> NEW.magnitude_ppm
        OR (NEW.qa_payload ->> 'pair_quality_ppm')::integer <> NEW.pair_quality_ppm
        OR NEW.qa_payload ->> 'lock_conclusion' <> 'COMPATIBLE'
        OR NEW.qa_payload ->> 'lock_policy_digest' !~ '^[0-9a-f]{64}$'
        OR NOT mirror_demo_jsonb_exact_keys(
            NEW.qa_payload -> 'source_asset', ARRAY['id','sha256']
        )
        OR NEW.qa_payload -> 'source_asset' ->> 'id' <> NEW.source_asset_id
        OR NEW.qa_payload -> 'source_asset' ->> 'sha256' <> NEW.source_asset_sha256
        OR NEW.magnitude_ppm NOT IN (15000,30000) THEN
        RAISE EXCEPTION 'D02 question pair QA payload is invalid';
    END IF;

    FOREACH side_name IN ARRAY ARRAY['left','right'] LOOP
        side_payload := NEW.qa_payload -> side_name;
        IF side_name = 'left' THEN
            expected_result_asset_id := NEW.left_asset_id;
            expected_result_sha := NEW.left_asset_sha256;
            expected_variant_id := NEW.left_asset_variant_id;
            expected_direction := 'DECREASE';
            expected_signed_prefix := '-';
        ELSE
            expected_result_asset_id := NEW.right_asset_id;
            expected_result_sha := NEW.right_asset_sha256;
            expected_variant_id := NEW.right_asset_variant_id;
            expected_direction := 'INCREASE';
            expected_signed_prefix := '';
        END IF;
        IF NOT mirror_demo_jsonb_exact_keys(
            side_payload,
            ARRAY[
                'case_id','case_specification_digest','result_asset_id',
                'result_asset_sha256','asset_variant_id','asset_variant_type',
                'lineage_digest','requested_direction','requested_magnitude_ppm',
                'raw_signed_target_delta_fixed18','raw_target_absolute_delta_fixed18',
                'raw_max_control_drift_fixed18','measured_signed_delta_ppm','drift_ppm',
                'automated_gate_digest','manual_decision_digest',
                'side_quality_component_ppm'
            ]
        ) OR side_payload ->> 'case_id' !~ '^[0-9a-f]{32}$'
            OR side_payload ->> 'case_specification_digest' !~ '^[0-9a-f]{64}$'
            OR side_payload ->> 'result_asset_id' <> expected_result_asset_id
            OR side_payload ->> 'result_asset_sha256' <> expected_result_sha
            OR side_payload ->> 'asset_variant_id' <> expected_variant_id
            OR side_payload ->> 'asset_variant_type' <> 'demo_p3_p7_geometry_v1'
            OR side_payload ->> 'lineage_digest' !~ '^[0-9a-f]{64}$'
            OR side_payload ->> 'requested_direction' <> expected_direction
            OR (side_payload ->> 'requested_magnitude_ppm')::integer <> NEW.magnitude_ppm
            OR side_payload ->> 'raw_signed_target_delta_fixed18' !~
               ('^' || expected_signed_prefix || '(0\.[0-9]{18}|1\.000000000000000000)$')
            OR side_payload ->> 'raw_target_absolute_delta_fixed18' !~
               '^(0\.[0-9]{18}|1\.000000000000000000)$'
            OR side_payload ->> 'raw_max_control_drift_fixed18' !~
               '^(0\.[0-9]{18}|1\.000000000000000000)$'
            OR mirror_demo_round_half_even_ppm(
                side_payload ->> 'raw_target_absolute_delta_fixed18'
            ) <> NEW.magnitude_ppm
            OR ltrim(side_payload ->> 'raw_signed_target_delta_fixed18', '-') <>
               side_payload ->> 'raw_target_absolute_delta_fixed18'
            OR abs((side_payload ->> 'measured_signed_delta_ppm')::integer) > 1000000
            OR (side_payload ->> 'drift_ppm')::integer NOT BETWEEN 0 AND 1000000
            OR side_payload ->> 'automated_gate_digest' !~ '^[0-9a-f]{64}$'
            OR side_payload ->> 'manual_decision_digest' !~ '^[0-9a-f]{64}$'
            OR (side_payload ->> 'side_quality_component_ppm')::integer
               NOT BETWEEN 0 AND 1000000
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
                  AND result_asset.owner_user_id IS NULL
                  AND result_asset.asset_role = 'synthetic'
                  AND result_asset.internal_purpose = 'synthetic_dataset'
                  AND result_asset.synthetic
                  AND result_asset.deleted_at IS NULL
                  AND NOT result_asset.is_ai_generated
                  AND result_asset.is_ai_modified
            ) OR side_payload ->> 'lineage_digest' IS DISTINCT FROM
                mirror_demo_digest(
                    'mirror.demo/D02AssetVariantLineage/v1',
                    jsonb_build_object(
                        'variant_type', 'demo_p3_p7_geometry_v1',
                        'source_asset_id', NEW.source_asset_id,
                        'source_asset_sha256', NEW.source_asset_sha256,
                        'result_asset_id', expected_result_asset_id,
                        'result_asset_sha256', expected_result_sha
                    )
                ) THEN
            RAISE EXCEPTION 'D02 question pair side authority is invalid';
        END IF;
    END LOOP;
    expected_id := substring(
        mirror_demo_digest(
            'mirror.demo/D02QuestionPairId/v1',
            jsonb_build_object(
                'question_bank_id', NEW.question_bank_id,
                'pair_screening_record_digest',
                    NEW.qa_payload ->> 'pair_screening_record_digest',
                'source_admission_event_id', NEW.demo_synthetic_identity_id,
                'dimension_key', NEW.dimension_key,
                'magnitude_ppm', NEW.magnitude_ppm
            )
        )
        FROM 1 FOR 32
    );
    IF NEW.id <> expected_id THEN
        RAISE EXCEPTION 'D02 question pair ID mismatch';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_complete_bank()
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
BEGIN
    authority_bank_id := COALESCE(
        to_jsonb(NEW) ->> 'question_bank_id',
        NEW.id
    );
    SELECT * INTO bank_row FROM demo_question_banks WHERE id = authority_bank_id;
    IF NOT FOUND OR bank_row.schema_version = 'mirror.demo/DemoQuestionBank/v1' THEN
        RETURN NEW;
    END IF;
    SELECT * INTO report_row FROM demo_pair_screening_reports
    WHERE id = bank_row.screening_report_id
      AND report_digest = bank_row.screening_report_digest
      AND status = 'PASSED';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'D02 complete bank lacks its PASSED report';
    END IF;
    SELECT count(*),
           count(DISTINCT demo_synthetic_identity_id),
           count(DISTINCT dimension_key),
           count(DISTINCT magnitude_ppm)
    INTO pair_count, source_count, dimension_count, magnitude_count
    FROM demo_question_pairs
    WHERE question_bank_id = authority_bank_id;
    SELECT count(DISTINCT side_id)
    INTO side_count
    FROM (
        SELECT left_asset_id AS side_id FROM demo_question_pairs
        WHERE question_bank_id = authority_bank_id
        UNION
        SELECT right_asset_id AS side_id FROM demo_question_pairs
        WHERE question_bank_id = authority_bank_id
    ) AS selected_sides;
    IF pair_count <> 16 OR side_count <> 32 OR source_count <> 4
        OR dimension_count <> 2 OR magnitude_count <> 2
        OR EXISTS (
            SELECT 1
            FROM jsonb_array_elements(report_row.selected_dimension_keys) AS selected(value)
            WHERE (
                SELECT count(*) FROM demo_question_pairs pair_row
                WHERE pair_row.question_bank_id = authority_bank_id
                  AND pair_row.dimension_key = selected.value #>> '{}'
            ) <> 8
        ) OR EXISTS (
            SELECT 1 FROM demo_question_pairs pair_row
            WHERE pair_row.question_bank_id = authority_bank_id
              AND (
                  pair_row.schema_version <> 'mirror.demo/DemoQuestionPair/v2'
                  OR pair_row.screening_report_id IS DISTINCT FROM
                     bank_row.screening_report_id
                  OR pair_row.screening_report_digest IS DISTINCT FROM
                     bank_row.screening_report_digest
              )
        ) OR (
            SELECT count(DISTINCT pair_row.qa_payload ->> 'pair_screening_record_digest')
            FROM demo_question_pairs pair_row
            WHERE pair_row.question_bank_id = authority_bank_id
        ) <> 16 OR EXISTS (
            SELECT 1 FROM demo_question_pairs pair_row
            WHERE pair_row.question_bank_id = authority_bank_id
              AND NOT EXISTS (
                  SELECT 1
                  FROM jsonb_array_elements(
                      report_row.report_payload -> 'selected_pair_manifest'
                  ) AS selected_pair(value)
                  WHERE selected_pair.value ->> 'pair_screening_record_digest' =
                        pair_row.qa_payload ->> 'pair_screening_record_digest'
                    AND selected_pair.value ->> 'source_admission_event_id' =
                        pair_row.demo_synthetic_identity_id
                    AND selected_pair.value ->> 'dimension_key' =
                        pair_row.dimension_key
                    AND selected_pair.value ->> 'magnitude_ppm' =
                        pair_row.magnitude_ppm::text
              )
        ) THEN
        RAISE EXCEPTION 'D02 question bank is not the complete selected 16-pair authority';
    END IF;
    RETURN NEW;
END;
$function$;
"""


_DOWNGRADE_PREFLIGHT_SQL = r"""
DO $block$
DECLARE
    incompatible_identity_count bigint;
    screening_report_count bigint;
    incompatible_bank_count bigint;
    incompatible_pair_count bigint;
BEGIN
    SELECT count(*) INTO incompatible_identity_count
    FROM demo_synthetic_identities
        WHERE schema_version <> 'mirror.demo/DemoSyntheticIdentity/v1'
           OR source_authority_kind <> 'FORMAL_REFERENCE';
    SELECT count(*) INTO screening_report_count
    FROM demo_pair_screening_reports;
    SELECT count(*) INTO incompatible_bank_count
    FROM demo_question_banks
        WHERE schema_version <> 'mirror.demo/DemoQuestionBank/v1'
           OR screening_report_id IS NOT NULL
           OR screening_report_digest IS NOT NULL;
    SELECT count(*) INTO incompatible_pair_count
    FROM demo_question_pairs
        WHERE schema_version <> 'mirror.demo/DemoQuestionPair/v1'
           OR screening_report_id IS NOT NULL
           OR screening_report_digest IS NOT NULL;
    IF incompatible_identity_count > 0
        OR screening_report_count > 0
        OR incompatible_bank_count > 0
        OR incompatible_pair_count > 0 THEN
        RAISE EXCEPTION
            'D02 downgrade blocked by incompatible authority: identity=%, report=%, bank=%, pair=%',
            incompatible_identity_count,
            screening_report_count,
            incompatible_bank_count,
            incompatible_pair_count;
    END IF;
END;
$block$;
"""


def _upgrade_identity_authority() -> None:
    op.alter_column("demo_synthetic_identities", "formal_synthetic_identity_id", nullable=True)
    op.alter_column("demo_synthetic_identities", "formal_accepted_qa_run_id", nullable=True)
    op.alter_column(
        "demo_synthetic_identities",
        "formal_accepted_qa_snapshot_digest",
        nullable=True,
    )
    for column in (
        sa.Column("source_output_id", sa.String(length=128), nullable=True),
        sa.Column("source_receipt_digest", sa.String(length=64), nullable=True),
        sa.Column("source_authority_digest", sa.String(length=64), nullable=True),
        sa.Column("source_qa_snapshot_digest", sa.String(length=64), nullable=True),
        sa.Column("source_landmark_digest", sa.String(length=64), nullable=True),
        sa.Column("source_measurement_digest", sa.String(length=64), nullable=True),
        sa.Column("source_provenance_digest", sa.String(length=64), nullable=True),
        sa.Column(
            "source_fact_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("source_fact_snapshot_digest", sa.String(length=64), nullable=True),
        sa.Column(
            "source_measurement_projection",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "source_measurement_projection_digest",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column("original_formal_identity_id_status", sa.String(length=48), nullable=True),
        sa.Column("adult_synthetic_attested", sa.Boolean(), nullable=True),
        sa.Column("importer_version", sa.String(length=64), nullable=True),
        sa.Column("import_config_digest", sa.String(length=64), nullable=True),
    ):
        op.add_column("demo_synthetic_identities", column)
    op.add_column(
        "demo_synthetic_identities",
        sa.Column(
            "source_authority_kind",
            sa.String(length=32),
            sa.Computed(
                "CASE WHEN formal_synthetic_identity_id IS NOT NULL "
                "THEN 'FORMAL_REFERENCE' ELSE 'DEMO_LOCAL_IMPORTED_COPY' END",
                persisted=True,
            ),
            nullable=False,
        ),
    )
    op.add_column(
        "demo_synthetic_identities",
        sa.Column(
            "source_authority_key",
            sa.String(length=64),
            sa.Computed(
                "CASE WHEN formal_synthetic_identity_id IS NOT NULL "
                "THEN mirror_demo_formal_source_authority_key(formal_synthetic_identity_id) "
                "ELSE mirror_demo_local_source_authority_key(source_output_id, "
                "formal_canonical_asset_id, formal_canonical_asset_sha256, "
                "source_receipt_digest) END",
                persisted=True,
            ),
            nullable=False,
        ),
    )
    op.drop_constraint(
        op.f("uq_demo_synthetic_identities_formal_sequence"),
        "demo_synthetic_identities",
        type_="unique",
    )
    op.drop_constraint(
        op.f("ck_demo_synthetic_identities_schema_version_shape"),
        "demo_synthetic_identities",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_demo_synthetic_identities_qa_snapshot_digest_shape"),
        "demo_synthetic_identities",
        type_="check",
    )
    op.create_unique_constraint(
        op.f("uq_demo_synthetic_identities_source_sequence"),
        "demo_synthetic_identities",
        ["source_authority_key", "admission_sequence"],
    )
    op.create_check_constraint(
        op.f("ck_demo_synthetic_identities_schema_version_shape"),
        "demo_synthetic_identities",
        "schema_version IN ('mirror.demo/DemoSyntheticIdentity/v1',"
        "'mirror.demo/DemoSyntheticIdentity/v2')",
    )
    op.create_check_constraint(
        op.f("ck_demo_synthetic_identities_qa_snapshot_digest_shape"),
        "demo_synthetic_identities",
        "formal_accepted_qa_snapshot_digest IS NULL OR "
        "formal_accepted_qa_snapshot_digest ~ '^[0-9a-f]{64}$'",
    )
    op.create_check_constraint(
        op.f("ck_demo_synthetic_identities_source_authority_kind"),
        "demo_synthetic_identities",
        "source_authority_kind IN ('FORMAL_REFERENCE','DEMO_LOCAL_IMPORTED_COPY')",
    )
    op.create_check_constraint(
        op.f("ck_demo_synthetic_identities_source_authority_key_shape"),
        "demo_synthetic_identities",
        "source_authority_key ~ '^[0-9a-f]{64}$'",
    )
    op.create_check_constraint(
        op.f("ck_demo_synthetic_identities_source_output_id_shape"),
        "demo_synthetic_identities",
        "source_output_id IS NULL OR source_output_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'",
    )
    op.create_check_constraint(
        op.f("ck_demo_synthetic_identities_local_digest_shapes"),
        "demo_synthetic_identities",
        "(source_receipt_digest IS NULL OR source_receipt_digest ~ '^[0-9a-f]{64}$') "
        "AND (source_authority_digest IS NULL OR source_authority_digest ~ '^[0-9a-f]{64}$') "
        "AND (source_qa_snapshot_digest IS NULL OR source_qa_snapshot_digest ~ '^[0-9a-f]{64}$') "
        "AND (source_landmark_digest IS NULL OR source_landmark_digest ~ '^[0-9a-f]{64}$') "
        "AND (source_measurement_digest IS NULL OR source_measurement_digest ~ '^[0-9a-f]{64}$') "
        "AND (source_provenance_digest IS NULL OR source_provenance_digest ~ '^[0-9a-f]{64}$') "
        "AND (source_fact_snapshot_digest IS NULL OR source_fact_snapshot_digest ~ '^[0-9a-f]{64}$') "
        "AND (source_measurement_projection_digest IS NULL OR "
        "source_measurement_projection_digest ~ '^[0-9a-f]{64}$') "
        "AND (import_config_digest IS NULL OR import_config_digest ~ '^[0-9a-f]{64}$')",
    )
    op.create_check_constraint(
        op.f("ck_demo_synthetic_identities_local_json_objects"),
        "demo_synthetic_identities",
        "(source_fact_snapshot IS NULL OR jsonb_typeof(source_fact_snapshot) = 'object') "
        "AND (source_measurement_projection IS NULL OR "
        "jsonb_typeof(source_measurement_projection) = 'object')",
    )
    op.create_check_constraint(
        op.f("ck_demo_synthetic_identities_source_mode_null_matrix"),
        "demo_synthetic_identities",
        "(source_authority_kind = 'FORMAL_REFERENCE' "
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
        "AND original_formal_identity_id_status = 'UNKNOWN_REDACTED_NOT_RECOVERED' "
        "AND adult_synthetic_attested IS TRUE "
        "AND importer_version = 'demo-d02-identity-importer-v2' "
        "AND import_config_digest IS NOT NULL)",
    )


def _create_screening_report_table() -> None:
    digest_columns = [
        sa.Column("source_manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("case_manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("screening_policy_digest", sa.String(length=64), nullable=False),
        sa.Column("runtime_manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("vision_model_manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("topology_digest", sa.String(length=64), nullable=False),
        sa.Column("measurement_config_digest", sa.String(length=64), nullable=False),
        sa.Column("manual_review_policy_digest", sa.String(length=64), nullable=False),
        sa.Column("duplicate_policy_digest", sa.String(length=64), nullable=False),
        sa.Column("phash_implementation_digest", sa.String(length=64), nullable=False),
    ]
    count_columns = [
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("source_m3_repeat_count", sa.Integer(), nullable=False),
        sa.Column("m4_execution_count", sa.Integer(), nullable=False),
        sa.Column("result_m3_repeat_count", sa.Integer(), nullable=False),
        sa.Column("manual_decision_count", sa.Integer(), nullable=False),
        sa.Column("exact_sha_record_count", sa.Integer(), nullable=False),
        sa.Column("phash_comparison_count", sa.Integer(), nullable=False),
        sa.Column("candidate_pair_count", sa.Integer(), nullable=False),
        sa.Column("selected_pair_count", sa.Integer(), nullable=False),
        sa.Column("selected_result_side_count", sa.Integer(), nullable=False),
    ]
    op.create_table(
        "demo_pair_screening_reports",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.String(length=112), nullable=False),
        *digest_columns,
        sa.Column("report_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("report_digest", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        *count_columns,
        sa.Column(
            "eligible_dimension_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "selected_dimension_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("selected_pair_manifest_digest", sa.String(length=64), nullable=True),
        sa.Column("canonical_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_demo_pair_screening_reports")),
        sa.UniqueConstraint(
            "content_digest",
            name=op.f("uq_demo_pair_screening_reports_content_digest"),
        ),
        sa.UniqueConstraint(
            "report_digest",
            name=op.f("uq_demo_pair_screening_reports_report_digest"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{32}$'",
            name=op.f("ck_demo_pair_screening_reports_id_shape"),
        ),
        sa.CheckConstraint(
            "schema_version ~ '^mirror[.]demo/[A-Za-z0-9]+/v1$'",
            name=op.f("ck_demo_pair_screening_reports_schema_version_shape"),
        ),
        sa.CheckConstraint(
            "schema_version = 'mirror.demo/D02PairScreeningReport/v1'",
            name=op.f("ck_demo_pair_screening_reports_exact_schema_version"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(canonical_payload) = 'object'",
            name=op.f("ck_demo_pair_screening_reports_canonical_payload_object"),
        ),
        sa.CheckConstraint(
            "content_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_pair_screening_reports_content_digest_shape"),
        ),
        sa.CheckConstraint(
            "source_manifest_digest ~ '^[0-9a-f]{64}$' "
            "AND case_manifest_digest ~ '^[0-9a-f]{64}$' "
            "AND screening_policy_digest ~ '^[0-9a-f]{64}$' "
            "AND runtime_manifest_digest ~ '^[0-9a-f]{64}$' "
            "AND vision_model_manifest_digest ~ '^[0-9a-f]{64}$' "
            "AND topology_digest ~ '^[0-9a-f]{64}$' "
            "AND measurement_config_digest ~ '^[0-9a-f]{64}$' "
            "AND manual_review_policy_digest ~ '^[0-9a-f]{64}$' "
            "AND duplicate_policy_digest ~ '^[0-9a-f]{64}$' "
            "AND phash_implementation_digest ~ '^[0-9a-f]{64}$' "
            "AND report_digest ~ '^[0-9a-f]{64}$' "
            "AND (selected_pair_manifest_digest IS NULL OR "
            "selected_pair_manifest_digest ~ '^[0-9a-f]{64}$')",
            name=op.f("ck_demo_pair_screening_reports_digest_shapes"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(report_payload) = 'object' "
            "AND jsonb_typeof(eligible_dimension_keys) = 'array' "
            "AND jsonb_typeof(selected_dimension_keys) = 'array'",
            name=op.f("ck_demo_pair_screening_reports_json_shapes"),
        ),
        sa.CheckConstraint(
            "status IN ('PASSED','FAILED')",
            name=op.f("ck_demo_pair_screening_reports_status"),
        ),
        sa.CheckConstraint(
            "source_count = 4 AND case_count = 48 "
            "AND source_m3_repeat_count = 12 AND m4_execution_count = 96 "
            "AND result_m3_repeat_count = 144 AND manual_decision_count = 48 "
            "AND exact_sha_record_count = 52 AND phash_comparison_count = 1326 "
            "AND candidate_pair_count = 24 AND ("
            "(status = 'PASSED' AND selected_pair_count = 16 "
            "AND selected_result_side_count = 32 "
            "AND jsonb_array_length(selected_dimension_keys) = 2 "
            "AND selected_pair_manifest_digest IS NOT NULL) OR "
            "(status = 'FAILED' AND selected_pair_count = 0 "
            "AND selected_result_side_count = 0 "
            "AND jsonb_array_length(selected_dimension_keys) = 0 "
            "AND selected_pair_manifest_digest IS NULL))",
            name=op.f("ck_demo_pair_screening_reports_fixed_cardinality"),
        ),
    )


def _upgrade_bank_pair_authority() -> None:
    for table_name in ("demo_question_banks", "demo_question_pairs"):
        op.add_column(
            table_name,
            sa.Column("screening_report_id", sa.String(length=32), nullable=True),
        )
        op.add_column(
            table_name,
            sa.Column("screening_report_digest", sa.String(length=64), nullable=True),
        )
        op.create_foreign_key(
            op.f(f"fk_{table_name}_screening_report_id_demo_pair_screening_reports"),
            table_name,
            "demo_pair_screening_reports",
            ["screening_report_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.create_index(
            op.f(f"ix_{table_name}_screening_report_id"),
            table_name,
            ["screening_report_id"],
            unique=False,
        )
        op.drop_constraint(
            op.f(f"ck_{table_name}_schema_version_shape"),
            table_name,
            type_="check",
        )
    op.drop_constraint(
        op.f("ck_demo_question_banks_dimension_manifest_array"),
        "demo_question_banks",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_demo_question_banks_schema_version_shape"),
        "demo_question_banks",
        "schema_version IN ('mirror.demo/DemoQuestionBank/v1','mirror.demo/DemoQuestionBank/v2')",
    )
    op.create_check_constraint(
        op.f("ck_demo_question_banks_versioned_dimension_manifest"),
        "demo_question_banks",
        "(schema_version = 'mirror.demo/DemoQuestionBank/v1' "
        "AND jsonb_typeof(dimension_manifest) = 'array' "
        "AND screening_report_id IS NULL AND screening_report_digest IS NULL) OR "
        "(schema_version = 'mirror.demo/DemoQuestionBank/v2' "
        "AND jsonb_typeof(dimension_manifest) = 'object' "
        "AND screening_report_id IS NOT NULL AND screening_report_digest IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_demo_question_banks_screening_report_digest_shape"),
        "demo_question_banks",
        "screening_report_digest IS NULL OR screening_report_digest ~ '^[0-9a-f]{64}$'",
    )
    op.create_check_constraint(
        op.f("ck_demo_question_pairs_schema_version_shape"),
        "demo_question_pairs",
        "schema_version IN ('mirror.demo/DemoQuestionPair/v1','mirror.demo/DemoQuestionPair/v2')",
    )
    op.create_check_constraint(
        op.f("ck_demo_question_pairs_versioned_report_binding"),
        "demo_question_pairs",
        "(schema_version = 'mirror.demo/DemoQuestionPair/v1' "
        "AND screening_report_id IS NULL AND screening_report_digest IS NULL) OR "
        "(schema_version = 'mirror.demo/DemoQuestionPair/v2' "
        "AND screening_report_id IS NOT NULL AND screening_report_digest IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_demo_question_pairs_screening_report_digest_shape"),
        "demo_question_pairs",
        "screening_report_digest IS NULL OR screening_report_digest ~ '^[0-9a-f]{64}$'",
    )


def upgrade() -> None:
    op.execute(_D02_HELPER_SQL)
    _upgrade_identity_authority()
    op.execute(_D02_GUARD_SQL)
    op.execute(_D02_IDENTITY_SQL)
    op.execute(
        "DROP TRIGGER trg_demo_references_demo_synthetic_identities ON demo_synthetic_identities"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d02_synthetic_identity_validation "
        "BEFORE INSERT ON demo_synthetic_identities "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d02_synthetic_identity()"
    )

    _create_screening_report_table()
    op.execute(_D02_REPORT_SQL)
    op.execute(
        "CREATE TRIGGER trg_demo_authority_demo_pair_screening_reports "
        "BEFORE INSERT OR UPDATE OR DELETE ON demo_pair_screening_reports "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_guard_authority()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d02_screening_report_validation "
        "BEFORE INSERT ON demo_pair_screening_reports "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d02_screening_report()"
    )

    _upgrade_bank_pair_authority()
    op.execute(_D02_BANK_PAIR_SQL)
    op.execute(
        "CREATE TRIGGER trg_demo_d02_question_bank_insert "
        "BEFORE INSERT ON demo_question_banks "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d02_question_bank_insert()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d02_question_pair_insert "
        "BEFORE INSERT ON demo_question_pairs "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d02_question_pair_insert()"
    )
    for table_name in ("demo_question_banks", "demo_question_pairs"):
        op.execute(
            sa.text(
                f"CREATE CONSTRAINT TRIGGER trg_demo_d02_complete_bank_{table_name} "
                f"AFTER INSERT ON {table_name} DEFERRABLE INITIALLY DEFERRED "
                "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d02_complete_bank()"
            )
        )


def _downgrade_bank_pair_authority() -> None:
    for table_name in ("demo_question_pairs", "demo_question_banks"):
        op.execute(f"DROP TRIGGER trg_demo_d02_complete_bank_{table_name} ON {table_name}")
    op.execute("DROP TRIGGER trg_demo_d02_question_pair_insert ON demo_question_pairs")
    op.execute("DROP TRIGGER trg_demo_d02_question_bank_insert ON demo_question_banks")
    op.execute("DROP FUNCTION mirror_demo_validate_d02_complete_bank()")
    op.execute("DROP FUNCTION mirror_demo_validate_d02_question_pair_insert()")
    op.execute("DROP FUNCTION mirror_demo_validate_d02_question_bank_insert()")
    op.drop_constraint(
        op.f("ck_demo_question_pairs_screening_report_digest_shape"),
        "demo_question_pairs",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_demo_question_pairs_versioned_report_binding"),
        "demo_question_pairs",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_demo_question_pairs_schema_version_shape"),
        "demo_question_pairs",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_demo_question_banks_screening_report_digest_shape"),
        "demo_question_banks",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_demo_question_banks_versioned_dimension_manifest"),
        "demo_question_banks",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_demo_question_banks_schema_version_shape"),
        "demo_question_banks",
        type_="check",
    )
    for table_name in ("demo_question_pairs", "demo_question_banks"):
        op.drop_index(op.f(f"ix_{table_name}_screening_report_id"), table_name=table_name)
        op.drop_constraint(
            op.f(f"fk_{table_name}_screening_report_id_demo_pair_screening_reports"),
            table_name,
            type_="foreignkey",
        )
        op.drop_column(table_name, "screening_report_digest")
        op.drop_column(table_name, "screening_report_id")
    op.create_check_constraint(
        op.f("ck_demo_question_banks_schema_version_shape"),
        "demo_question_banks",
        "schema_version ~ '^mirror[.]demo/[A-Za-z0-9]+/v1$'",
    )
    op.create_check_constraint(
        op.f("ck_demo_question_banks_dimension_manifest_array"),
        "demo_question_banks",
        "jsonb_typeof(dimension_manifest) = 'array'",
    )
    op.create_check_constraint(
        op.f("ck_demo_question_pairs_schema_version_shape"),
        "demo_question_pairs",
        "schema_version ~ '^mirror[.]demo/[A-Za-z0-9]+/v1$'",
    )


def _downgrade_identity_authority() -> None:
    op.execute(
        "DROP TRIGGER trg_demo_d02_synthetic_identity_validation ON demo_synthetic_identities"
    )
    op.execute("DROP FUNCTION mirror_demo_validate_d02_synthetic_identity()")
    op.execute("DROP FUNCTION mirror_demo_validate_d02_local_snapshot(demo_synthetic_identities)")
    op.execute(_LEGACY_CURRENT_ADMISSION_SQL)
    op.execute(
        "CREATE TRIGGER trg_demo_references_demo_synthetic_identities "
        "BEFORE INSERT ON demo_synthetic_identities "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_references()"
    )
    for constraint_name in (
        "ck_demo_synthetic_identities_source_mode_null_matrix",
        "ck_demo_synthetic_identities_local_json_objects",
        "ck_demo_synthetic_identities_local_digest_shapes",
        "ck_demo_synthetic_identities_source_output_id_shape",
        "ck_demo_synthetic_identities_source_authority_key_shape",
        "ck_demo_synthetic_identities_source_authority_kind",
        "ck_demo_synthetic_identities_qa_snapshot_digest_shape",
        "ck_demo_synthetic_identities_schema_version_shape",
    ):
        op.drop_constraint(op.f(constraint_name), "demo_synthetic_identities", type_="check")
    op.drop_constraint(
        op.f("uq_demo_synthetic_identities_source_sequence"),
        "demo_synthetic_identities",
        type_="unique",
    )
    op.drop_column("demo_synthetic_identities", "source_authority_key")
    op.drop_column("demo_synthetic_identities", "source_authority_kind")
    for column_name in (
        "import_config_digest",
        "importer_version",
        "adult_synthetic_attested",
        "original_formal_identity_id_status",
        "source_measurement_projection_digest",
        "source_measurement_projection",
        "source_fact_snapshot_digest",
        "source_fact_snapshot",
        "source_provenance_digest",
        "source_measurement_digest",
        "source_landmark_digest",
        "source_qa_snapshot_digest",
        "source_authority_digest",
        "source_receipt_digest",
        "source_output_id",
    ):
        op.drop_column("demo_synthetic_identities", column_name)
    op.alter_column(
        "demo_synthetic_identities",
        "formal_accepted_qa_snapshot_digest",
        nullable=False,
    )
    op.alter_column("demo_synthetic_identities", "formal_accepted_qa_run_id", nullable=False)
    op.alter_column("demo_synthetic_identities", "formal_synthetic_identity_id", nullable=False)
    op.create_unique_constraint(
        op.f("uq_demo_synthetic_identities_formal_sequence"),
        "demo_synthetic_identities",
        ["formal_synthetic_identity_id", "admission_sequence"],
    )
    op.create_check_constraint(
        op.f("ck_demo_synthetic_identities_schema_version_shape"),
        "demo_synthetic_identities",
        "schema_version ~ '^mirror[.]demo/[A-Za-z0-9]+/v1$'",
    )
    op.create_check_constraint(
        op.f("ck_demo_synthetic_identities_qa_snapshot_digest_shape"),
        "demo_synthetic_identities",
        "formal_accepted_qa_snapshot_digest ~ '^[0-9a-f]{64}$'",
    )


def downgrade() -> None:
    op.execute(_DOWNGRADE_PREFLIGHT_SQL)
    _downgrade_bank_pair_authority()
    op.execute(
        "DROP TRIGGER trg_demo_d02_screening_report_validation ON demo_pair_screening_reports"
    )
    op.execute(
        "DROP TRIGGER trg_demo_authority_demo_pair_screening_reports ON demo_pair_screening_reports"
    )
    op.execute("DROP FUNCTION mirror_demo_validate_d02_screening_report()")
    op.drop_table("demo_pair_screening_reports")
    _downgrade_identity_authority()
    op.execute(_LEGACY_GUARD_SQL)
    op.execute("DROP FUNCTION mirror_demo_d02_dimension_array_valid(jsonb, integer)")
    op.execute("DROP FUNCTION mirror_demo_round_half_even_ppm(text)")
    op.execute("DROP FUNCTION mirror_demo_jsonb_exact_keys(jsonb, text[])")
    op.execute("DROP FUNCTION mirror_demo_local_source_authority_key(text, text, text, text)")
    op.execute("DROP FUNCTION mirror_demo_formal_source_authority_key(text)")
