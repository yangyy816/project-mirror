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

CREATE OR REPLACE FUNCTION mirror_demo_d02_expected_screening_policy_digest()
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $function$
    SELECT mirror_demo_digest(
        'mirror.demo/D02ScreeningPolicyRoot/v1',
        jsonb_build_object(
            'preregistration_id', 'P3_P7_D02_PAIR_SCREENING_V9',
            'policy_schema', 'mirror.demo/D02PairScreeningPolicy/v8',
            'policy_revision', 9,
            'preregistration_sha256',
                '3fb0a1192d006560d45083b8d9d933f15a22648c0108f81ef305d31980073ba3'
        )
    );
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_d02_expected_lock_policy_digest()
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $function$
    SELECT mirror_demo_digest(
        'mirror.demo/D02EmptyNeutralLockPolicy/v1',
        jsonb_build_object(
            'policy_id', 'D02_FROZEN_EMPTY_NEUTRAL_POLICY_V1',
            'ordered_feature_locks', '[]'::jsonb,
            'ordered_temporary_session_overrides', '[]'::jsonb,
            'ordered_prohibited_operations', '[]'::jsonb
        )
    );
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_d02_json_string_matches(
    input_value jsonb,
    expected_pattern text
)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
    SELECT jsonb_typeof(input_value) = 'string'
       AND (input_value #>> '{}') ~ expected_pattern;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_d02_json_string_equals(
    input_value jsonb,
    expected_value text
)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
    SELECT jsonb_typeof(input_value) = 'string'
       AND (input_value #>> '{}') = expected_value;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_d02_json_boolean(input_value jsonb)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
    SELECT jsonb_typeof(input_value) = 'boolean';
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_d02_json_integer_between(
    input_value jsonb,
    minimum_value bigint,
    maximum_value bigint
)
RETURNS boolean
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
DECLARE
    integer_text text;
    integer_value numeric;
BEGIN
    IF jsonb_typeof(input_value) <> 'number' THEN
        RETURN false;
    END IF;
    integer_text := input_value #>> '{}';
    IF integer_text !~ '^-?(0|[1-9][0-9]*)$' THEN
        RETURN false;
    END IF;
    integer_value := integer_text::numeric;
    RETURN integer_value >= minimum_value AND integer_value <= maximum_value;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_d02_json_fixed18(
    input_value jsonb,
    signed_value boolean DEFAULT false
)
RETURNS boolean
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
DECLARE
    fixed_value text;
BEGIN
    IF jsonb_typeof(input_value) <> 'string' THEN
        RETURN false;
    END IF;
    fixed_value := input_value #>> '{}';
    IF signed_value THEN
        RETURN fixed_value ~ '^-?(0\.[0-9]{18}|1\.000000000000000000)$'
           AND fixed_value <> '-0.000000000000000000'
           AND fixed_value::numeric BETWEEN -1 AND 1;
    END IF;
    RETURN fixed_value ~ '^(0\.[0-9]{18}|1\.000000000000000000)$';
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_d02_record_digest_matches(
    record_value jsonb,
    expected_schema text,
    digest_key text
)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
    SELECT jsonb_typeof(record_value) = 'object'
       AND mirror_demo_d02_json_string_equals(
               record_value -> 'schema_version', expected_schema
           )
       AND mirror_demo_d02_json_string_matches(
               record_value -> digest_key, '^[0-9a-f]{64}$'
           )
       AND (record_value ->> digest_key) = mirror_demo_digest(
               expected_schema,
               record_value - 'schema_version' - digest_key
           );
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_d02_require_record(
    record_value jsonb,
    expected_schema text,
    expected_keys text[],
    digest_key text DEFAULT 'record_digest'
)
RETURNS void
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
BEGIN
    IF NOT mirror_demo_jsonb_exact_keys(record_value, expected_keys)
        OR NOT mirror_demo_d02_record_digest_matches(
            record_value, expected_schema, digest_key
        ) THEN
        RAISE EXCEPTION 'D02 record shape or digest mismatch: %', expected_schema;
    END IF;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_d02_hamming64(
    left_hex text,
    right_hex text
)
RETURNS integer
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
DECLARE
    left_bytes bytea;
    right_bytes bytea;
    bit_index integer;
    distance integer := 0;
BEGIN
    IF left_hex !~ '^[0-9a-f]{16}$' OR right_hex !~ '^[0-9a-f]{16}$' THEN
        RAISE EXCEPTION 'D02 pHash value must be 64 lowercase hexadecimal bits';
    END IF;
    left_bytes := decode(left_hex, 'hex');
    right_bytes := decode(right_hex, 'hex');
    FOR bit_index IN 0..63 LOOP
        IF get_bit(left_bytes, bit_index) <> get_bit(right_bytes, bit_index) THEN
            distance := distance + 1;
        END IF;
    END LOOP;
    RETURN distance;
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

CREATE OR REPLACE FUNCTION mirror_demo_d02_quality_ppm(
    raw_max_control_drift_fixed18 text
)
RETURNS integer
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
DECLARE
    drift_value numeric;
    scaled_value numeric;
    lower_value numeric;
    fractional_value numeric;
    rounded_value integer;
BEGIN
    IF raw_max_control_drift_fixed18 !~
       '^(0\.[0-9]{18}|1\.000000000000000000)$' THEN
        RAISE EXCEPTION 'D02 quality drift is not canonical Fixed18';
    END IF;
    drift_value := raw_max_control_drift_fixed18::numeric;
    scaled_value := (1 - drift_value / 0.020000000000000000) * 1000000;
    IF scaled_value <= 1 THEN
        RETURN 1;
    ELSIF scaled_value >= 1000000 THEN
        RETURN 1000000;
    END IF;
    lower_value := floor(scaled_value);
    fractional_value := scaled_value - lower_value;
    IF fractional_value < 0.5 THEN
        rounded_value := lower_value::integer;
    ELSIF fractional_value > 0.5 THEN
        rounded_value := (lower_value + 1)::integer;
    ELSIF mod(lower_value, 2) = 0 THEN
        rounded_value := lower_value::integer;
    ELSE
        rounded_value := (lower_value + 1)::integer;
    END IF;
    RETURN greatest(1, least(1000000, rounded_value));
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


_D02_REPORT_V9_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_measurements_v9(
    authority_row demo_pair_screening_reports
)
RETURNS void
LANGUAGE plpgsql
AS $function$
DECLARE
    payload jsonb := authority_row.report_payload;
    case_entry jsonb;
    peer_case_entry jsonb;
    source_entry jsonb;
    source_measurement jsonb;
    measurement_record jsonb;
    peer_measurement_record jsonb;
    result_measurement jsonb;
    peer_result_measurement jsonb;
    control_delta jsonb;
    gate_evaluation jsonb;
    result_m3_record jsonb;
    first_result_m3_record jsonb;
    first_m4_record jsonb;
    second_m4_record jsonb;
    structure_record jsonb;
    manual_record jsonb;
    expected_unsupported_indexes jsonb;
    expected_unsupported_reasons jsonb;
    expected_control_dimensions text[];
    expected_dimension text;
    expected_direction text;
    expected_peer_index integer;
    case_index integer;
    repeat_index integer;
    control_index integer;
    expected_repeat integer;
    raw_source numeric;
    raw_result numeric;
    raw_signed_delta numeric;
    raw_absolute_delta numeric;
    raw_control_source numeric;
    raw_control_result numeric;
    control_absolute_delta numeric;
    maximum_control_delta numeric;
    winning_control_ordinal integer;
    signed_delta_ppm integer;
    expected_direction_gate boolean;
    expected_target_min_gate boolean;
    expected_target_max_gate boolean;
    expected_control_gate boolean;
    expected_monotonic_gate boolean;
    expected_measurement_gate boolean;
    all_supported boolean;
    peer_all_supported boolean;
    expected_structure_gate boolean;
    artifact_present boolean;
BEGIN
    FOR case_index IN 0..47 LOOP
        case_entry := payload -> 'ordered_case_manifest' -> case_index;
        source_entry := payload -> 'ordered_source_manifest' ->
            ((case_entry ->> 'source_ordinal')::integer - 1);
        measurement_record := payload -> 'measurement_gate_evidence' -> case_index;
        structure_record := payload ->
            'decode_structure_immutability_evidence' -> case_index;
        expected_dimension := case_entry ->> 'dimension_key';
        expected_direction := case_entry ->> 'direction';
        expected_peer_index := CASE
            WHEN (case_entry ->> 'magnitude_ppm')::integer = 15000
                THEN case_index + 1
            ELSE case_index - 1
        END;
        peer_case_entry := payload -> 'ordered_case_manifest' -> expected_peer_index;
        peer_measurement_record := payload -> 'measurement_gate_evidence' ->
            expected_peer_index;

        first_result_m3_record := payload -> 'result_m3_repeat_evidence' ->
            (case_index * 3);
        FOR repeat_index IN 0..2 LOOP
            result_m3_record := payload -> 'result_m3_repeat_evidence' ->
                (case_index * 3 + repeat_index);
            IF result_m3_record -> 'canonical_output_digest' IS DISTINCT FROM
               first_result_m3_record -> 'canonical_output_digest'
                OR result_m3_record -> 'landmark_digest' IS DISTINCT FROM
                   first_result_m3_record -> 'landmark_digest'
                OR result_m3_record -> 'measurement_observation_digest'
                   IS DISTINCT FROM
                   first_result_m3_record -> 'measurement_observation_digest' THEN
                RAISE EXCEPTION 'D02 result M3 repeats are not deterministic';
            END IF;
        END LOOP;

        PERFORM mirror_demo_d02_require_record(
            measurement_record,
            'mirror.demo/D02MeasurementGateRecord/v3',
            ARRAY[
                'schema_version','case_id','case_specification_digest',
                'dimension_key','requested_direction','requested_magnitude_ppm',
                'monotonicity_peer_case_id','source_target_measurement',
                'ordered_source_control_measurements',
                'ordered_result_repeat_measurements','measurement_evaluation_state',
                'gate_evaluation','record_digest'
            ]
        );
        IF measurement_record ->> 'case_id' <> case_entry ->> 'case_id'
            OR measurement_record ->> 'case_specification_digest' <>
               case_entry ->> 'case_specification_digest'
            OR measurement_record ->> 'dimension_key' <> expected_dimension
            OR measurement_record ->> 'requested_direction' <> expected_direction
            OR NOT mirror_demo_d02_json_integer_between(
                measurement_record -> 'requested_magnitude_ppm',
                (case_entry ->> 'magnitude_ppm')::integer,
                (case_entry ->> 'magnitude_ppm')::integer
            )
            OR measurement_record ->> 'monotonicity_peer_case_id' <>
               peer_case_entry ->> 'case_id'
            OR peer_measurement_record ->> 'monotonicity_peer_case_id' <>
               case_entry ->> 'case_id'
            OR peer_case_entry ->> 'source_authority_key' <>
               case_entry ->> 'source_authority_key'
            OR peer_case_entry ->> 'source_admission_event_id' <>
               case_entry ->> 'source_admission_event_id'
            OR peer_case_entry ->> 'source_asset_id' <>
               case_entry ->> 'source_asset_id'
            OR peer_case_entry ->> 'dimension_key' <> expected_dimension
            OR peer_case_entry ->> 'direction' <> expected_direction
            OR peer_case_entry ->> 'execution_config_digest' <>
               case_entry ->> 'execution_config_digest' THEN
            RAISE EXCEPTION 'D02 measurement peer or case binding is invalid';
        END IF;

        SELECT item.value INTO source_measurement
        FROM jsonb_array_elements(
            source_entry -> 'ordered_supported_measurements'
        ) AS item(value)
        WHERE item.value ->> 'dimension_key' = expected_dimension;
        IF source_measurement IS NULL
            OR measurement_record -> 'source_target_measurement'
               IS DISTINCT FROM source_measurement
            OR jsonb_typeof(
                measurement_record -> 'ordered_source_control_measurements'
            ) <> 'array'
            OR jsonb_array_length(
                measurement_record -> 'ordered_source_control_measurements'
            ) <> 5
            OR jsonb_typeof(
                measurement_record -> 'ordered_result_repeat_measurements'
            ) <> 'array'
            OR jsonb_array_length(
                measurement_record -> 'ordered_result_repeat_measurements'
            ) <> 3 THEN
            RAISE EXCEPTION 'D02 measurement source or repeat shape is invalid';
        END IF;
        expected_control_dimensions := ARRAY(
            SELECT item.value #>> '{}'
            FROM jsonb_array_elements(
                case_entry -> 'ordered_control_dimensions'
            ) WITH ORDINALITY AS item(value, ordinality)
            ORDER BY item.ordinality
        );
        FOR control_index IN 0..4 LOOP
            SELECT item.value INTO source_measurement
            FROM jsonb_array_elements(
                source_entry -> 'ordered_supported_measurements'
            ) AS item(value)
            WHERE item.value ->> 'dimension_key' =
                  expected_control_dimensions[control_index + 1];
            IF measurement_record -> 'ordered_source_control_measurements' ->
               control_index IS DISTINCT FROM source_measurement THEN
                RAISE EXCEPTION 'D02 ordered source controls are not authoritative';
            END IF;
        END LOOP;

        all_supported := true;
        expected_direction_gate := true;
        expected_target_min_gate := true;
        expected_target_max_gate := true;
        expected_control_gate := true;
        expected_unsupported_indexes := '[]'::jsonb;
        expected_unsupported_reasons := '[]'::jsonb;
        SELECT item.value INTO source_measurement
        FROM jsonb_array_elements(
            source_entry -> 'ordered_supported_measurements'
        ) AS item(value)
        WHERE item.value ->> 'dimension_key' = expected_dimension;
        raw_source := (source_measurement ->> 'raw_value_fixed18')::numeric;

        FOR repeat_index IN 0..2 LOOP
            expected_repeat := repeat_index + 1;
            result_measurement := measurement_record ->
                'ordered_result_repeat_measurements' -> repeat_index;
            result_m3_record := payload -> 'result_m3_repeat_evidence' ->
                (case_index * 3 + repeat_index);
            IF result_m3_record ->> 'observation_state' = 'SUPPORTED' THEN
                IF NOT mirror_demo_jsonb_exact_keys(
                    result_measurement,
                    ARRAY[
                        'schema_version','repeat_index','result_m3_record_digest',
                        'raw_result_target_fixed18',
                        'raw_signed_target_delta_fixed18',
                        'raw_target_absolute_delta_fixed18',
                        'ordered_control_deltas','winning_control_ordinal',
                        'max_control_dimension_key',
                        'raw_max_control_drift_fixed18','measured_signed_delta_ppm',
                        'target_absolute_delta_ppm','drift_ppm',
                        'direction_gate_passed','target_min_gate_passed',
                        'target_max_gate_passed','control_drift_gate_passed'
                    ]
                ) OR NOT mirror_demo_d02_json_string_equals(
                    result_measurement -> 'schema_version',
                    'mirror.demo/D02SupportedResultMeasurement/v1'
                ) OR NOT mirror_demo_d02_json_integer_between(
                    result_measurement -> 'repeat_index',
                    expected_repeat,
                    expected_repeat
                ) OR result_measurement ->> 'result_m3_record_digest' <>
                   result_m3_record ->> 'record_digest'
                    OR NOT mirror_demo_d02_json_fixed18(
                        result_measurement -> 'raw_result_target_fixed18'
                    )
                    OR NOT mirror_demo_d02_json_fixed18(
                        result_measurement -> 'raw_signed_target_delta_fixed18', true
                    )
                    OR NOT mirror_demo_d02_json_fixed18(
                        result_measurement -> 'raw_target_absolute_delta_fixed18'
                    )
                    OR NOT mirror_demo_d02_json_integer_between(
                        result_measurement -> 'measured_signed_delta_ppm',
                        -1000000,
                        1000000
                    )
                    OR NOT mirror_demo_d02_json_integer_between(
                        result_measurement -> 'target_absolute_delta_ppm',
                        0,
                        1000000
                    )
                    OR NOT mirror_demo_d02_json_integer_between(
                        result_measurement -> 'drift_ppm', 0, 1000000
                    ) THEN
                    RAISE EXCEPTION 'D02 supported result measurement is invalid';
                END IF;
                raw_result := (
                    result_measurement ->> 'raw_result_target_fixed18'
                )::numeric;
                raw_signed_delta := raw_result - raw_source;
                raw_absolute_delta := abs(raw_signed_delta);
                signed_delta_ppm := CASE
                    WHEN raw_signed_delta < 0 THEN -mirror_demo_round_half_even_ppm(
                        to_char(
                            raw_absolute_delta,
                            'FM0.000000000000000000'
                        )
                    )
                    ELSE mirror_demo_round_half_even_ppm(
                        to_char(
                            raw_absolute_delta,
                            'FM0.000000000000000000'
                        )
                    )
                END;
                IF (result_measurement ->> 'raw_signed_target_delta_fixed18')::numeric
                   IS DISTINCT FROM raw_signed_delta
                    OR (result_measurement ->>
                        'raw_target_absolute_delta_fixed18')::numeric
                       IS DISTINCT FROM raw_absolute_delta
                    OR (result_measurement ->> 'measured_signed_delta_ppm')::integer
                       IS DISTINCT FROM signed_delta_ppm
                    OR (result_measurement ->> 'target_absolute_delta_ppm')::integer
                       IS DISTINCT FROM mirror_demo_round_half_even_ppm(
                           result_measurement ->>
                               'raw_target_absolute_delta_fixed18'
                       )
                    OR jsonb_typeof(
                        result_measurement -> 'ordered_control_deltas'
                    ) <> 'array'
                    OR jsonb_array_length(
                        result_measurement -> 'ordered_control_deltas'
                    ) <> 5 THEN
                    RAISE EXCEPTION 'D02 target delta derivation is invalid';
                END IF;

                maximum_control_delta := -1;
                winning_control_ordinal := 0;
                FOR control_index IN 0..4 LOOP
                    control_delta := result_measurement ->
                        'ordered_control_deltas' -> control_index;
                    SELECT item.value INTO source_measurement
                    FROM jsonb_array_elements(
                        source_entry -> 'ordered_supported_measurements'
                    ) AS item(value)
                    WHERE item.value ->> 'dimension_key' =
                          expected_control_dimensions[control_index + 1];
                    IF NOT mirror_demo_jsonb_exact_keys(
                        control_delta,
                        ARRAY[
                            'schema_version','control_ordinal','dimension_key',
                            'raw_source_value_fixed18','raw_result_value_fixed18',
                            'raw_absolute_delta_fixed18','drift_ppm'
                        ]
                    ) OR NOT mirror_demo_d02_json_string_equals(
                        control_delta -> 'schema_version',
                        'mirror.demo/D02ControlDelta/v1'
                    ) OR NOT mirror_demo_d02_json_integer_between(
                        control_delta -> 'control_ordinal',
                        control_index + 1,
                        control_index + 1
                    ) OR control_delta ->> 'dimension_key' <>
                       expected_control_dimensions[control_index + 1]
                        OR NOT mirror_demo_d02_json_fixed18(
                            control_delta -> 'raw_source_value_fixed18'
                        )
                        OR NOT mirror_demo_d02_json_fixed18(
                            control_delta -> 'raw_result_value_fixed18'
                        )
                        OR NOT mirror_demo_d02_json_fixed18(
                            control_delta -> 'raw_absolute_delta_fixed18'
                        )
                        OR NOT mirror_demo_d02_json_integer_between(
                            control_delta -> 'drift_ppm', 0, 1000000
                        )
                        OR control_delta ->> 'raw_source_value_fixed18' <>
                           source_measurement ->> 'raw_value_fixed18' THEN
                        RAISE EXCEPTION 'D02 control delta shape is invalid';
                    END IF;
                    raw_control_source := (
                        control_delta ->> 'raw_source_value_fixed18'
                    )::numeric;
                    raw_control_result := (
                        control_delta ->> 'raw_result_value_fixed18'
                    )::numeric;
                    control_absolute_delta := abs(
                        raw_control_result - raw_control_source
                    );
                    IF (control_delta ->> 'raw_absolute_delta_fixed18')::numeric
                       IS DISTINCT FROM control_absolute_delta
                        OR (control_delta ->> 'drift_ppm')::integer
                           IS DISTINCT FROM mirror_demo_round_half_even_ppm(
                               control_delta ->> 'raw_absolute_delta_fixed18'
                           ) THEN
                        RAISE EXCEPTION 'D02 control delta arithmetic is invalid';
                    END IF;
                    IF control_absolute_delta > maximum_control_delta THEN
                        maximum_control_delta := control_absolute_delta;
                        winning_control_ordinal := control_index + 1;
                    END IF;
                END LOOP;
                IF NOT mirror_demo_d02_json_integer_between(
                    result_measurement -> 'winning_control_ordinal',
                    winning_control_ordinal,
                    winning_control_ordinal
                ) OR result_measurement ->> 'max_control_dimension_key' <>
                   expected_control_dimensions[winning_control_ordinal]
                    OR NOT mirror_demo_d02_json_fixed18(
                        result_measurement -> 'raw_max_control_drift_fixed18'
                    )
                    OR (result_measurement ->>
                        'raw_max_control_drift_fixed18')::numeric
                       IS DISTINCT FROM maximum_control_delta
                    OR (result_measurement ->> 'drift_ppm')::integer
                       IS DISTINCT FROM mirror_demo_round_half_even_ppm(
                           result_measurement -> 'ordered_control_deltas' ->
                               (winning_control_ordinal - 1) ->>
                               'raw_absolute_delta_fixed18'
                       ) THEN
                    RAISE EXCEPTION 'D02 maximum control authority is invalid';
                END IF;
                expected_direction_gate := expected_direction_gate AND (
                    CASE expected_direction
                        WHEN 'DECREASE' THEN raw_signed_delta < 0
                        ELSE raw_signed_delta > 0
                    END
                );
                expected_target_min_gate := expected_target_min_gate AND
                    raw_absolute_delta >= 0.000010000000000000;
                expected_target_max_gate := expected_target_max_gate AND
                    raw_absolute_delta <= 0.060000000000000000;
                expected_control_gate := expected_control_gate AND
                    maximum_control_delta <= 0.020000000000000000;
                IF EXISTS (
                    SELECT 1
                    FROM unnest(ARRAY[
                        'direction_gate_passed','target_min_gate_passed',
                        'target_max_gate_passed','control_drift_gate_passed'
                    ]) AS boolean_key
                    WHERE NOT mirror_demo_d02_json_boolean(
                        result_measurement -> boolean_key
                    )
                ) OR (result_measurement ->> 'direction_gate_passed')::boolean
                       IS DISTINCT FROM (CASE expected_direction
                           WHEN 'DECREASE' THEN raw_signed_delta < 0
                           ELSE raw_signed_delta > 0
                       END)
                    OR (result_measurement ->> 'target_min_gate_passed')::boolean
                       IS DISTINCT FROM
                       (raw_absolute_delta >= 0.000010000000000000)
                    OR (result_measurement ->> 'target_max_gate_passed')::boolean
                       IS DISTINCT FROM
                       (raw_absolute_delta <= 0.060000000000000000)
                    OR (result_measurement ->>
                        'control_drift_gate_passed')::boolean
                       IS DISTINCT FROM
                       (maximum_control_delta <= 0.020000000000000000) THEN
                    RAISE EXCEPTION 'D02 per-repeat measurement Gates are invalid';
                END IF;
            ELSE
                all_supported := false;
                IF NOT mirror_demo_jsonb_exact_keys(
                    result_measurement,
                    ARRAY[
                        'schema_version','repeat_index','result_m3_record_digest',
                        'unsupported_dimension_key','unsupported_reason',
                        'measurement_gate_passed'
                    ]
                ) OR NOT mirror_demo_d02_json_string_equals(
                    result_measurement -> 'schema_version',
                    'mirror.demo/D02UnsupportedResultMeasurement/v1'
                ) OR NOT mirror_demo_d02_json_integer_between(
                    result_measurement -> 'repeat_index',
                    expected_repeat,
                    expected_repeat
                ) OR result_measurement ->> 'result_m3_record_digest' <>
                   result_m3_record ->> 'record_digest'
                    OR result_measurement ->> 'unsupported_dimension_key' <>
                       expected_dimension
                    OR result_measurement ->> 'unsupported_reason' NOT IN (
                        'MISSING_MEASUREMENT','LOW_CONFIDENCE',
                        'OUT_OF_BOUNDS','RUNTIME_UNSUPPORTED'
                    )
                    OR NOT mirror_demo_d02_json_boolean(
                        result_measurement -> 'measurement_gate_passed'
                    )
                    OR result_measurement -> 'measurement_gate_passed' <>
                       'false'::jsonb THEN
                    RAISE EXCEPTION 'D02 unsupported result measurement is invalid';
                END IF;
                expected_unsupported_indexes := expected_unsupported_indexes ||
                    jsonb_build_array(expected_repeat);
                expected_unsupported_reasons := expected_unsupported_reasons ||
                    jsonb_build_array(result_measurement -> 'unsupported_reason');
            END IF;
        END LOOP;

        gate_evaluation := measurement_record -> 'gate_evaluation';
        peer_all_supported := peer_measurement_record ->>
            'measurement_evaluation_state' = 'SUPPORTED_EVALUATED';
        IF all_supported THEN
            IF measurement_record ->> 'measurement_evaluation_state' <>
               'SUPPORTED_EVALUATED'
                OR NOT mirror_demo_jsonb_exact_keys(
                    gate_evaluation,
                    ARRAY[
                        'schema_version','direction_gate_passed',
                        'target_min_gate_passed','target_max_gate_passed',
                        'control_drift_gate_passed',
                        'magnitude_monotonicity_gate_passed',
                        'measurement_gate_passed'
                    ]
                ) OR NOT mirror_demo_d02_json_string_equals(
                    gate_evaluation -> 'schema_version',
                    'mirror.demo/D02SupportedMeasurementGateEvaluation/v1'
                ) OR EXISTS (
                    SELECT 1 FROM unnest(ARRAY[
                        'direction_gate_passed','target_min_gate_passed',
                        'target_max_gate_passed','control_drift_gate_passed',
                        'magnitude_monotonicity_gate_passed',
                        'measurement_gate_passed'
                    ]) AS boolean_key
                    WHERE NOT mirror_demo_d02_json_boolean(
                        gate_evaluation -> boolean_key
                    )
                ) THEN
                RAISE EXCEPTION 'D02 supported measurement evaluation is invalid';
            END IF;
            expected_monotonic_gate := peer_all_supported;
            IF peer_all_supported THEN
                FOR repeat_index IN 0..2 LOOP
                    result_measurement := measurement_record ->
                        'ordered_result_repeat_measurements' -> repeat_index;
                    peer_result_measurement := peer_measurement_record ->
                        'ordered_result_repeat_measurements' -> repeat_index;
                    IF NOT mirror_demo_d02_json_fixed18(
                        peer_result_measurement ->
                            'raw_target_absolute_delta_fixed18'
                    ) THEN
                        RAISE EXCEPTION 'D02 peer raw monotonicity authority is invalid';
                    END IF;
                    IF (case_entry ->> 'magnitude_ppm')::integer = 15000 THEN
                        expected_monotonic_gate := expected_monotonic_gate AND
                            (peer_result_measurement ->>
                                'raw_target_absolute_delta_fixed18')::numeric >=
                            (result_measurement ->>
                                'raw_target_absolute_delta_fixed18')::numeric;
                    ELSE
                        expected_monotonic_gate := expected_monotonic_gate AND
                            (result_measurement ->>
                                'raw_target_absolute_delta_fixed18')::numeric >=
                            (peer_result_measurement ->>
                                'raw_target_absolute_delta_fixed18')::numeric;
                    END IF;
                END LOOP;
            END IF;
            expected_measurement_gate := expected_direction_gate
                AND expected_target_min_gate
                AND expected_target_max_gate
                AND expected_control_gate
                AND expected_monotonic_gate;
            IF (gate_evaluation ->> 'direction_gate_passed')::boolean
               IS DISTINCT FROM expected_direction_gate
                OR (gate_evaluation ->> 'target_min_gate_passed')::boolean
                   IS DISTINCT FROM expected_target_min_gate
                OR (gate_evaluation ->> 'target_max_gate_passed')::boolean
                   IS DISTINCT FROM expected_target_max_gate
                OR (gate_evaluation ->> 'control_drift_gate_passed')::boolean
                   IS DISTINCT FROM expected_control_gate
                OR (gate_evaluation ->>
                    'magnitude_monotonicity_gate_passed')::boolean
                   IS DISTINCT FROM expected_monotonic_gate
                OR (gate_evaluation ->> 'measurement_gate_passed')::boolean
                   IS DISTINCT FROM expected_measurement_gate THEN
                RAISE EXCEPTION 'D02 supported measurement Gate derivation is invalid';
            END IF;
        ELSE
            IF measurement_record ->> 'measurement_evaluation_state' <>
               'UNSUPPORTED_EXPLICIT'
                OR NOT mirror_demo_jsonb_exact_keys(
                    gate_evaluation,
                    ARRAY[
                        'schema_version','unsupported_repeat_indexes',
                        'ordered_unsupported_reasons','measurement_gate_passed'
                    ]
                ) OR NOT mirror_demo_d02_json_string_equals(
                    gate_evaluation -> 'schema_version',
                    'mirror.demo/D02UnsupportedMeasurementGateEvaluation/v1'
                ) OR gate_evaluation -> 'unsupported_repeat_indexes'
                   IS DISTINCT FROM expected_unsupported_indexes
                    OR gate_evaluation -> 'ordered_unsupported_reasons'
                       IS DISTINCT FROM expected_unsupported_reasons
                    OR NOT mirror_demo_d02_json_boolean(
                        gate_evaluation -> 'measurement_gate_passed'
                    )
                    OR gate_evaluation -> 'measurement_gate_passed' <>
                       'false'::jsonb THEN
                RAISE EXCEPTION 'D02 unsupported measurement evaluation is invalid';
            END IF;
        END IF;

        first_m4_record := payload -> 'm4_repeat_evidence' -> (case_index * 2);
        second_m4_record := payload -> 'm4_repeat_evidence' ->
            (case_index * 2 + 1);
        PERFORM mirror_demo_d02_require_record(
            structure_record,
            'mirror.demo/D02DecodeStructureImmutabilityRecord/v1',
            ARRAY[
                'schema_version','case_id','case_specification_digest',
                'source_asset_id','source_asset_sha256',
                'm4_execution_record_digests','result_output_id','result_sha256',
                'result_byte_size','result_mime_type','result_width','result_height',
                'result_image_record_id','source_decode_valid','result_decode_valid',
                'bounded_dimensions_passed','source_checksum_unchanged',
                'm4_replay_bytes_equal','m4_replay_dimensions_equal',
                'changed_pixel_count_equal','changed_pixel_count_positive',
                'immutable_result_binding_passed','exact_lineage_passed',
                'target_and_controls_complete','structure_gate_passed','record_digest'
            ]
        );
        IF structure_record ->> 'case_id' <> case_entry ->> 'case_id'
            OR structure_record ->> 'case_specification_digest' <>
               case_entry ->> 'case_specification_digest'
            OR structure_record ->> 'source_asset_id' <>
               case_entry ->> 'source_asset_id'
            OR structure_record ->> 'source_asset_sha256' <>
               case_entry ->> 'source_asset_sha256'
            OR structure_record -> 'm4_execution_record_digests'
               IS DISTINCT FROM jsonb_build_array(
                   first_m4_record -> 'record_digest',
                   second_m4_record -> 'record_digest'
               )
            OR structure_record ->> 'result_output_id' <>
               first_m4_record ->> 'result_output_id'
            OR structure_record ->> 'result_sha256' <>
               first_m4_record ->> 'result_sha256'
            OR structure_record -> 'result_byte_size' IS DISTINCT FROM
               first_m4_record -> 'result_byte_size'
            OR structure_record -> 'result_mime_type' IS DISTINCT FROM
               first_m4_record -> 'result_mime_type'
            OR structure_record -> 'result_width' IS DISTINCT FROM
               first_m4_record -> 'result_width'
            OR structure_record -> 'result_height' IS DISTINCT FROM
               first_m4_record -> 'result_height'
            OR NOT mirror_demo_d02_json_string_matches(
                structure_record -> 'result_image_record_id', '^[0-9a-f]{32}$'
            )
            OR EXISTS (
                SELECT 1 FROM unnest(ARRAY[
                    'source_decode_valid','result_decode_valid',
                    'bounded_dimensions_passed','source_checksum_unchanged',
                    'm4_replay_bytes_equal','m4_replay_dimensions_equal',
                    'changed_pixel_count_equal','changed_pixel_count_positive',
                    'immutable_result_binding_passed','exact_lineage_passed',
                    'target_and_controls_complete','structure_gate_passed'
                ]) AS boolean_key
                WHERE NOT mirror_demo_d02_json_boolean(
                    structure_record -> boolean_key
                )
            ) THEN
            RAISE EXCEPTION 'D02 structure evidence shape or binding is invalid';
        END IF;
        expected_structure_gate :=
            (structure_record ->> 'source_decode_valid')::boolean
            AND (structure_record ->> 'result_decode_valid')::boolean
            AND (structure_record ->> 'bounded_dimensions_passed')::boolean
            AND (structure_record ->> 'source_checksum_unchanged')::boolean
            AND (structure_record ->> 'm4_replay_bytes_equal')::boolean
            AND (structure_record ->> 'm4_replay_dimensions_equal')::boolean
            AND (structure_record ->> 'changed_pixel_count_equal')::boolean
            AND (structure_record ->> 'changed_pixel_count_positive')::boolean
            AND (structure_record ->> 'immutable_result_binding_passed')::boolean
            AND (structure_record ->> 'exact_lineage_passed')::boolean
            AND (structure_record ->> 'target_and_controls_complete')::boolean;
        IF (structure_record ->> 'source_decode_valid')::boolean IS DISTINCT FROM true
            OR (structure_record ->> 'result_decode_valid')::boolean
               IS DISTINCT FROM true
            OR (structure_record ->> 'bounded_dimensions_passed')::boolean
               IS DISTINCT FROM (
                   first_m4_record -> 'result_width' IS NOT DISTINCT FROM
                       case_entry -> 'output_width'
                   AND first_m4_record -> 'result_height' IS NOT DISTINCT FROM
                       case_entry -> 'output_height'
               )
            OR (structure_record ->> 'source_checksum_unchanged')::boolean
               IS DISTINCT FROM true
            OR (structure_record ->> 'm4_replay_bytes_equal')::boolean
               IS DISTINCT FROM true
            OR (structure_record ->> 'm4_replay_dimensions_equal')::boolean
               IS DISTINCT FROM true
            OR (structure_record ->> 'changed_pixel_count_equal')::boolean
               IS DISTINCT FROM true
            OR (structure_record ->> 'changed_pixel_count_positive')::boolean
               IS DISTINCT FROM
               ((first_m4_record ->> 'changed_pixel_count')::integer > 0)
            OR (structure_record ->> 'immutable_result_binding_passed')::boolean
               IS DISTINCT FROM true
            OR (structure_record ->> 'exact_lineage_passed')::boolean
               IS DISTINCT FROM true
            OR (structure_record ->> 'target_and_controls_complete')::boolean
               IS DISTINCT FROM true
            OR (structure_record ->> 'structure_gate_passed')::boolean
               IS DISTINCT FROM expected_structure_gate THEN
            RAISE EXCEPTION 'D02 structure Gate is not derived';
        END IF;
    END LOOP;

    FOR case_index IN 0..47 LOOP
        manual_record := payload -> 'manual_review_evidence' -> case_index;
        SELECT item.value INTO case_entry
        FROM jsonb_array_elements(payload -> 'ordered_case_manifest') AS item(value)
        ORDER BY item.value ->> 'case_id' COLLATE "C"
        OFFSET case_index LIMIT 1;
        SELECT item.value INTO first_m4_record
        FROM jsonb_array_elements(payload -> 'm4_repeat_evidence') AS item(value)
        WHERE item.value ->> 'case_id' = case_entry ->> 'case_id'
          AND item.value ->> 'replay_index' = '1';
        PERFORM mirror_demo_d02_require_record(
            manual_record,
            'mirror.demo/D02ManualArtifactDecision/v1',
            ARRAY[
                'schema_version','case_id','result_sha256','manual_review_version',
                'manual_review_policy_digest','decision_sequence','background_seam',
                'disconnected_contour','duplicated_feature','warp_tear','verdict',
                'review_authority_digest','manual_decision_digest'
            ],
            'manual_decision_digest'
        );
        IF manual_record ->> 'case_id' <> case_entry ->> 'case_id'
            OR manual_record ->> 'result_sha256' <>
               first_m4_record ->> 'result_sha256'
            OR NOT mirror_demo_d02_json_string_matches(
                manual_record -> 'manual_review_version',
                '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'
            )
            OR manual_record ->> 'manual_review_policy_digest' <>
               authority_row.manual_review_policy_digest
            OR NOT mirror_demo_d02_json_integer_between(
                manual_record -> 'decision_sequence', case_index + 1, case_index + 1
            )
            OR NOT mirror_demo_d02_json_string_matches(
                manual_record -> 'review_authority_digest', '^[0-9a-f]{64}$'
            )
            OR manual_record ->> 'verdict' NOT IN ('PASS','FAIL')
            OR EXISTS (
                SELECT 1 FROM unnest(ARRAY[
                    'background_seam','disconnected_contour',
                    'duplicated_feature','warp_tear'
                ]) AS boolean_key
                WHERE NOT mirror_demo_d02_json_boolean(
                    manual_record -> boolean_key
                )
            ) THEN
            RAISE EXCEPTION 'D02 manual decision authority is invalid';
        END IF;
        artifact_present :=
            (manual_record ->> 'background_seam')::boolean
            OR (manual_record ->> 'disconnected_contour')::boolean
            OR (manual_record ->> 'duplicated_feature')::boolean
            OR (manual_record ->> 'warp_tear')::boolean;
        IF (manual_record ->> 'verdict' = 'PASS') IS DISTINCT FROM
           (NOT artifact_present) THEN
            RAISE EXCEPTION 'D02 manual verdict is not derived';
        END IF;
    END LOOP;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_images_v9(
    authority_row demo_pair_screening_reports
)
RETURNS void
LANGUAGE plpgsql
AS $function$
DECLARE
    payload jsonb := authority_row.report_payload;
    duplicate_evidence jsonb := payload -> 'exact_duplicate_evidence';
    phash_evidence jsonb := payload -> 'phash_observation_evidence';
    image_record jsonb;
    prior_image_record jsonb;
    signature_record jsonb;
    left_signature jsonb;
    right_signature jsonb;
    comparison_record jsonb;
    source_entry jsonb;
    case_entry jsonb;
    m4_record jsonb;
    expected_id text;
    expected_gate boolean;
    all_record_sha_unique boolean;
    source_sha_unique boolean;
    result_sha_unique boolean;
    source_result_sha_disjoint boolean;
    image_index integer;
    case_index integer;
    left_index integer;
    right_index integer;
    comparison_index integer := 0;
BEGIN
    IF NOT mirror_demo_jsonb_exact_keys(
        duplicate_evidence,
        ARRAY[
            'schema_version','image_records','all_record_sha_unique',
            'source_sha_unique','result_sha_unique','source_result_sha_disjoint',
            'exact_sha_gate_passed'
        ]
    ) OR NOT mirror_demo_d02_json_string_equals(
        duplicate_evidence -> 'schema_version',
        'mirror.demo/D02ExactDuplicateEvidence/v2'
    ) OR jsonb_typeof(duplicate_evidence -> 'image_records') <> 'array'
        OR jsonb_array_length(duplicate_evidence -> 'image_records') <> 52
        OR EXISTS (
            SELECT 1 FROM unnest(ARRAY[
                'all_record_sha_unique','source_sha_unique','result_sha_unique',
                'source_result_sha_disjoint','exact_sha_gate_passed'
            ]) AS boolean_key
            WHERE NOT mirror_demo_d02_json_boolean(
                duplicate_evidence -> boolean_key
            )
        ) THEN
        RAISE EXCEPTION 'D02 exact duplicate evidence shape is invalid';
    END IF;

    FOR image_index IN 0..51 LOOP
        image_record := duplicate_evidence -> 'image_records' -> image_index;
        IF image_record ->> 'authority_role' = 'SOURCE' THEN
            PERFORM mirror_demo_d02_require_record(
                image_record,
                'mirror.demo/D02SourceImageAuthorityRecord/v2',
                ARRAY[
                    'schema_version','image_record_ordinal','image_record_id',
                    'authority_role','source_ordinal','source_authority_key',
                    'source_admission_event_id','source_asset_id','sha256','byte_size',
                    'mime_type','width','height','image_record_digest'
                ],
                'image_record_digest'
            );
            IF NOT mirror_demo_d02_json_integer_between(
                image_record -> 'source_ordinal', 1, 4
            ) THEN
                RAISE EXCEPTION 'D02 source image ordinal is invalid';
            END IF;
            source_entry := payload -> 'ordered_source_manifest' ->
                ((image_record ->> 'source_ordinal')::integer - 1);
            expected_id := substring(
                mirror_demo_digest(
                    'mirror.demo/D02SourceImageAuthorityRecordId/v1',
                    jsonb_build_object(
                        'authority_role', 'SOURCE',
                        'source_authority_key',
                            source_entry ->> 'source_authority_key',
                        'source_admission_event_id',
                            source_entry ->> 'source_admission_event_id',
                        'source_asset_id', source_entry ->> 'source_asset_id',
                        'sha256', source_entry ->> 'source_asset_sha256'
                    )
                ) FROM 1 FOR 32
            );
            IF image_record ->> 'image_record_id' <> expected_id
                OR image_record ->> 'source_authority_key' <>
                   source_entry ->> 'source_authority_key'
                OR image_record ->> 'source_admission_event_id' <>
                   source_entry ->> 'source_admission_event_id'
                OR image_record ->> 'source_asset_id' <>
                   source_entry ->> 'source_asset_id'
                OR image_record ->> 'sha256' <>
                   source_entry ->> 'source_asset_sha256'
                OR image_record -> 'byte_size' IS DISTINCT FROM
                   source_entry -> 'source_asset_byte_size'
                OR image_record -> 'mime_type' IS DISTINCT FROM
                   source_entry -> 'source_asset_mime_type'
                OR image_record -> 'width' IS DISTINCT FROM
                   source_entry -> 'source_asset_width'
                OR image_record -> 'height' IS DISTINCT FROM
                   source_entry -> 'source_asset_height' THEN
                RAISE EXCEPTION 'D02 source image authority is invalid';
            END IF;
        ELSIF image_record ->> 'authority_role' = 'RESULT' THEN
            PERFORM mirror_demo_d02_require_record(
                image_record,
                'mirror.demo/D02ResultImageAuthorityRecord/v2',
                ARRAY[
                    'schema_version','image_record_ordinal','image_record_id',
                    'authority_role','source_ordinal','source_authority_key',
                    'source_admission_event_id','case_id','case_specification_digest',
                    'result_output_id','deterministic_result_asset_id','sha256',
                    'byte_size','mime_type','width','height','image_record_digest'
                ],
                'image_record_digest'
            );
            SELECT item.value, (item.ordinality - 1)::integer
            INTO case_entry, case_index
            FROM jsonb_array_elements(payload -> 'ordered_case_manifest')
                 WITH ORDINALITY AS item(value, ordinality)
            WHERE item.value ->> 'case_id' = image_record ->> 'case_id';
            IF case_entry IS NULL THEN
                RAISE EXCEPTION 'D02 result image case binding is missing';
            END IF;
            source_entry := payload -> 'ordered_source_manifest' ->
                ((case_entry ->> 'source_ordinal')::integer - 1);
            m4_record := payload -> 'm4_repeat_evidence' -> (case_index * 2);
            expected_id := substring(
                mirror_demo_digest(
                    'mirror.demo/D02ResultImageAuthorityRecordId/v1',
                    jsonb_build_object(
                        'authority_role', 'RESULT',
                        'source_authority_key',
                            source_entry ->> 'source_authority_key',
                        'source_admission_event_id',
                            source_entry ->> 'source_admission_event_id',
                        'case_id', case_entry ->> 'case_id',
                        'case_specification_digest',
                            case_entry ->> 'case_specification_digest',
                        'result_output_id', m4_record ->> 'result_output_id',
                        'deterministic_result_asset_id',
                            image_record ->> 'deterministic_result_asset_id',
                        'sha256', m4_record ->> 'result_sha256'
                    )
                ) FROM 1 FOR 32
            );
            IF image_record ->> 'image_record_id' <> expected_id
                OR NOT mirror_demo_d02_json_string_matches(
                    image_record -> 'deterministic_result_asset_id',
                    '^[0-9a-f]{32}$'
                )
                OR image_record ->> 'source_ordinal' <>
                   case_entry ->> 'source_ordinal'
                OR image_record ->> 'source_authority_key' <>
                   source_entry ->> 'source_authority_key'
                OR image_record ->> 'source_admission_event_id' <>
                   source_entry ->> 'source_admission_event_id'
                OR image_record ->> 'case_specification_digest' <>
                   case_entry ->> 'case_specification_digest'
                OR image_record ->> 'result_output_id' <>
                   m4_record ->> 'result_output_id'
                OR image_record ->> 'sha256' <> m4_record ->> 'result_sha256'
                OR image_record -> 'byte_size' IS DISTINCT FROM
                   m4_record -> 'result_byte_size'
                OR image_record -> 'mime_type' IS DISTINCT FROM
                   m4_record -> 'result_mime_type'
                OR image_record -> 'width' IS DISTINCT FROM
                   m4_record -> 'result_width'
                OR image_record -> 'height' IS DISTINCT FROM
                   m4_record -> 'result_height' THEN
                RAISE EXCEPTION 'D02 result image authority is invalid';
            END IF;
        ELSE
            RAISE EXCEPTION 'D02 image authority role is invalid';
        END IF;
        IF NOT mirror_demo_d02_json_integer_between(
            image_record -> 'image_record_ordinal', image_index + 1, image_index + 1
        ) OR NOT mirror_demo_d02_json_string_matches(
            image_record -> 'image_record_id', '^[0-9a-f]{32}$'
        ) OR NOT mirror_demo_d02_json_string_matches(
            image_record -> 'sha256', '^[0-9a-f]{64}$'
        ) OR NOT mirror_demo_d02_json_integer_between(
            image_record -> 'byte_size', 1, 9223372036854775807
        ) OR NOT mirror_demo_d02_json_string_equals(
            image_record -> 'mime_type', 'image/jpeg'
        ) OR NOT mirror_demo_d02_json_integer_between(
            image_record -> 'width', 1, 2147483647
        ) OR NOT mirror_demo_d02_json_integer_between(
            image_record -> 'height', 1, 2147483647
        ) THEN
            RAISE EXCEPTION 'D02 image scalar authority is invalid';
        END IF;
        IF image_index > 0 THEN
            prior_image_record := duplicate_evidence -> 'image_records' ->
                (image_index - 1);
            IF (prior_image_record ->> 'sha256',
                prior_image_record ->> 'image_record_id') >=
               (image_record ->> 'sha256', image_record ->> 'image_record_id') THEN
                RAISE EXCEPTION 'D02 image record order is invalid';
            END IF;
        END IF;
    END LOOP;

    SELECT count(DISTINCT item.value ->> 'sha256') = 52
    INTO all_record_sha_unique
    FROM jsonb_array_elements(duplicate_evidence -> 'image_records') AS item(value);
    SELECT count(DISTINCT item.value ->> 'sha256') = 4
    INTO source_sha_unique
    FROM jsonb_array_elements(duplicate_evidence -> 'image_records') AS item(value)
    WHERE item.value ->> 'authority_role' = 'SOURCE';
    SELECT count(DISTINCT item.value ->> 'sha256') = 48
    INTO result_sha_unique
    FROM jsonb_array_elements(duplicate_evidence -> 'image_records') AS item(value)
    WHERE item.value ->> 'authority_role' = 'RESULT';
    SELECT NOT EXISTS (
        SELECT 1
        FROM jsonb_array_elements(duplicate_evidence -> 'image_records') AS source(value)
        JOIN jsonb_array_elements(duplicate_evidence -> 'image_records') AS result(value)
          ON source.value ->> 'sha256' = result.value ->> 'sha256'
        WHERE source.value ->> 'authority_role' = 'SOURCE'
          AND result.value ->> 'authority_role' = 'RESULT'
    ) INTO source_result_sha_disjoint;
    expected_gate := all_record_sha_unique AND source_sha_unique
        AND result_sha_unique AND source_result_sha_disjoint;
    IF (duplicate_evidence ->> 'all_record_sha_unique')::boolean
       IS DISTINCT FROM all_record_sha_unique
        OR (duplicate_evidence ->> 'source_sha_unique')::boolean
           IS DISTINCT FROM source_sha_unique
        OR (duplicate_evidence ->> 'result_sha_unique')::boolean
           IS DISTINCT FROM result_sha_unique
        OR (duplicate_evidence ->> 'source_result_sha_disjoint')::boolean
           IS DISTINCT FROM source_result_sha_disjoint
        OR (duplicate_evidence ->> 'exact_sha_gate_passed')::boolean
           IS DISTINCT FROM expected_gate THEN
        RAISE EXCEPTION 'D02 exact-SHA Gate is not derived';
    END IF;

    IF NOT mirror_demo_jsonb_exact_keys(
        phash_evidence,
        ARRAY[
            'schema_version','implementation_digest','bit_width','threshold_policy',
            'ordered_record_signatures','comparisons'
        ]
    ) OR NOT mirror_demo_d02_json_string_equals(
        phash_evidence -> 'schema_version',
        'mirror.demo/D02PHashObservationEvidence/v2'
    ) OR phash_evidence ->> 'implementation_digest' <>
       authority_row.phash_implementation_digest
        OR NOT mirror_demo_d02_json_integer_between(
            phash_evidence -> 'bit_width', 64, 64
        )
        OR NOT mirror_demo_d02_json_string_equals(
            phash_evidence -> 'threshold_policy',
            'OBSERVATION_ONLY_NO_THRESHOLD'
        )
        OR jsonb_typeof(phash_evidence -> 'ordered_record_signatures') <> 'array'
        OR jsonb_array_length(phash_evidence -> 'ordered_record_signatures') <> 52
        OR jsonb_typeof(phash_evidence -> 'comparisons') <> 'array'
        OR jsonb_array_length(phash_evidence -> 'comparisons') <> 1326 THEN
        RAISE EXCEPTION 'D02 pHash evidence shape is invalid';
    END IF;
    FOR image_index IN 0..51 LOOP
        image_record := duplicate_evidence -> 'image_records' -> image_index;
        signature_record := phash_evidence -> 'ordered_record_signatures' ->
            image_index;
        PERFORM mirror_demo_d02_require_record(
            signature_record,
            'mirror.demo/D02PHashSignatureRecord/v1',
            ARRAY[
                'schema_version','image_record_ordinal','image_record_id',
                'image_record_digest','image_sha256','phash_hex','signature_digest'
            ],
            'signature_digest'
        );
        IF signature_record -> 'image_record_ordinal' IS DISTINCT FROM
           image_record -> 'image_record_ordinal'
            OR signature_record -> 'image_record_id' IS DISTINCT FROM
               image_record -> 'image_record_id'
            OR signature_record -> 'image_record_digest' IS DISTINCT FROM
               image_record -> 'image_record_digest'
            OR signature_record -> 'image_sha256' IS DISTINCT FROM
               image_record -> 'sha256'
            OR NOT mirror_demo_d02_json_string_matches(
                signature_record -> 'phash_hex', '^[0-9a-f]{16}$'
            ) THEN
            RAISE EXCEPTION 'D02 pHash signature binding is invalid';
        END IF;
    END LOOP;
    FOR left_index IN 0..50 LOOP
        FOR right_index IN (left_index + 1)..51 LOOP
            comparison_index := comparison_index + 1;
            comparison_record := phash_evidence -> 'comparisons' ->
                (comparison_index - 1);
            left_signature := phash_evidence -> 'ordered_record_signatures' ->
                left_index;
            right_signature := phash_evidence -> 'ordered_record_signatures' ->
                right_index;
            PERFORM mirror_demo_d02_require_record(
                comparison_record,
                'mirror.demo/D02PHashComparisonRecord/v1',
                ARRAY[
                    'schema_version','comparison_ordinal',
                    'left_image_record_ordinal','left_image_record_id',
                    'left_signature_digest','right_image_record_ordinal',
                    'right_image_record_id','right_signature_digest',
                    'hamming_distance','comparison_digest'
                ],
                'comparison_digest'
            );
            IF NOT mirror_demo_d02_json_integer_between(
                comparison_record -> 'comparison_ordinal',
                comparison_index,
                comparison_index
            ) OR NOT mirror_demo_d02_json_integer_between(
                comparison_record -> 'left_image_record_ordinal',
                left_index + 1,
                left_index + 1
            ) OR comparison_record -> 'left_image_record_id' IS DISTINCT FROM
               left_signature -> 'image_record_id'
                OR comparison_record -> 'left_signature_digest' IS DISTINCT FROM
                   left_signature -> 'signature_digest'
                OR NOT mirror_demo_d02_json_integer_between(
                    comparison_record -> 'right_image_record_ordinal',
                    right_index + 1,
                    right_index + 1
                ) OR comparison_record -> 'right_image_record_id' IS DISTINCT FROM
                   right_signature -> 'image_record_id'
                OR comparison_record -> 'right_signature_digest' IS DISTINCT FROM
                   right_signature -> 'signature_digest'
                OR NOT mirror_demo_d02_json_integer_between(
                    comparison_record -> 'hamming_distance', 0, 64
                ) OR (comparison_record ->> 'hamming_distance')::integer <>
                   mirror_demo_d02_hamming64(
                       left_signature ->> 'phash_hex',
                       right_signature ->> 'phash_hex'
                   ) THEN
                RAISE EXCEPTION 'D02 pHash comparison universe is invalid';
            END IF;
        END LOOP;
    END LOOP;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_pair_side_v9(
    authority_row demo_pair_screening_reports,
    side_payload jsonb,
    expected_case_index integer,
    expected_direction text
)
RETURNS void
LANGUAGE plpgsql
AS $function$
DECLARE
    payload jsonb := authority_row.report_payload;
    case_entry jsonb := payload -> 'ordered_case_manifest' -> expected_case_index;
    measurement_record jsonb := payload -> 'measurement_gate_evidence' ->
        expected_case_index;
    structure_record jsonb := payload ->
        'decode_structure_immutability_evidence' -> expected_case_index;
    first_m4_record jsonb := payload -> 'm4_repeat_evidence' ->
        (expected_case_index * 2);
    result_measurement jsonb;
    result_m3_record jsonb;
    manual_record jsonb;
    image_record jsonb;
    expected_result_m3_digests jsonb := '[]'::jsonb;
    expected_repeat_gates jsonb := '[]'::jsonb;
    expected_automated_payload jsonb;
    expected_lineage_digest text;
    expected_automated_digest text;
    expected_measurement_gate boolean;
    expected_structure_gate boolean;
    expected_automated_gate boolean;
    expected_manual_gate boolean;
    expected_side_gate boolean;
    expected_quality integer;
    repeat_index integer;
BEGIN
    FOR repeat_index IN 0..2 LOOP
        result_m3_record := payload -> 'result_m3_repeat_evidence' ->
            (expected_case_index * 3 + repeat_index);
        expected_result_m3_digests := expected_result_m3_digests ||
            jsonb_build_array(result_m3_record -> 'record_digest');
        expected_repeat_gates := expected_repeat_gates ||
            jsonb_build_array(result_m3_record -> 'repeat_gate_passed');
    END LOOP;
    SELECT item.value INTO manual_record
    FROM jsonb_array_elements(payload -> 'manual_review_evidence') AS item(value)
    WHERE item.value ->> 'case_id' = case_entry ->> 'case_id';
    SELECT item.value INTO image_record
    FROM jsonb_array_elements(
        payload -> 'exact_duplicate_evidence' -> 'image_records'
    ) AS item(value)
    WHERE item.value ->> 'authority_role' = 'RESULT'
      AND item.value ->> 'case_id' = case_entry ->> 'case_id';
    IF manual_record IS NULL OR image_record IS NULL THEN
        RAISE EXCEPTION 'D02 pair side evidence binding is incomplete';
    END IF;
    expected_lineage_digest := mirror_demo_digest(
        'mirror.demo/D02AssetVariantLineage/v1',
        jsonb_build_object(
            'variant_type', 'demo_p3_p7_geometry_v1',
            'source_asset_id', case_entry ->> 'source_asset_id',
            'source_asset_sha256', case_entry ->> 'source_asset_sha256',
            'result_asset_id', side_payload ->> 'result_asset_id',
            'result_asset_sha256', first_m4_record ->> 'result_sha256'
        )
    );
    expected_measurement_gate := (
        measurement_record -> 'gate_evaluation' ->> 'measurement_gate_passed'
    )::boolean;
    expected_structure_gate := (
        structure_record ->> 'structure_gate_passed'
    )::boolean;
    expected_automated_gate := expected_measurement_gate
        AND expected_structure_gate
        AND NOT EXISTS (
            SELECT 1
            FROM jsonb_array_elements(expected_repeat_gates) AS item(value)
            WHERE item.value <> 'true'::jsonb
        );
    expected_manual_gate := manual_record ->> 'verdict' = 'PASS';
    expected_side_gate := expected_automated_gate AND expected_manual_gate;
    expected_automated_payload := jsonb_build_object(
        'case_id', case_entry ->> 'case_id',
        'case_specification_digest',
            case_entry ->> 'case_specification_digest',
        'result_m3_record_digests', expected_result_m3_digests,
        'result_m3_repeat_gate_results', expected_repeat_gates,
        'measurement_gate_record_digest',
            measurement_record ->> 'record_digest',
        'measurement_evaluation_state',
            measurement_record ->> 'measurement_evaluation_state',
        'measurement_gate_passed', expected_measurement_gate,
        'decode_structure_record_digest',
            structure_record ->> 'record_digest',
        'structure_gate_passed', expected_structure_gate,
        'automated_gate_passed', expected_automated_gate
    );
    expected_automated_digest := mirror_demo_digest(
        'mirror.demo/D02AutomatedSideGate/v1', expected_automated_payload
    );

    IF side_payload ->> 'case_id' <> case_entry ->> 'case_id'
        OR side_payload ->> 'case_specification_digest' <>
           case_entry ->> 'case_specification_digest'
        OR side_payload ->> 'requested_direction' <> expected_direction
        OR side_payload -> 'requested_magnitude_ppm' IS DISTINCT FROM
           case_entry -> 'magnitude_ppm'
        OR side_payload ->> 'result_output_id' <>
           first_m4_record ->> 'result_output_id'
        OR NOT mirror_demo_d02_json_string_matches(
            side_payload -> 'result_asset_id', '^[0-9a-f]{32}$'
        )
        OR side_payload ->> 'result_asset_id' <>
           image_record ->> 'deterministic_result_asset_id'
        OR side_payload ->> 'result_asset_sha256' <>
           first_m4_record ->> 'result_sha256'
        OR side_payload -> 'result_asset_byte_size' IS DISTINCT FROM
           first_m4_record -> 'result_byte_size'
        OR side_payload -> 'result_asset_mime_type' IS DISTINCT FROM
           first_m4_record -> 'result_mime_type'
        OR side_payload -> 'result_asset_width' IS DISTINCT FROM
           first_m4_record -> 'result_width'
        OR side_payload -> 'result_asset_height' IS DISTINCT FROM
           first_m4_record -> 'result_height'
        OR NOT mirror_demo_d02_json_string_matches(
            side_payload -> 'asset_variant_id', '^[0-9a-f]{32}$'
        )
        OR NOT mirror_demo_d02_json_string_equals(
            side_payload -> 'asset_variant_type', 'demo_p3_p7_geometry_v1'
        )
        OR side_payload ->> 'lineage_digest' <> expected_lineage_digest
        OR side_payload -> 'image_record_id' IS DISTINCT FROM
           image_record -> 'image_record_id'
        OR side_payload -> 'image_record_digest' IS DISTINCT FROM
           image_record -> 'image_record_digest'
        OR side_payload -> 'result_m3_record_digests' IS DISTINCT FROM
           expected_result_m3_digests
        OR side_payload ->> 'measurement_gate_record_digest' <>
           measurement_record ->> 'record_digest'
        OR side_payload ->> 'decode_structure_record_digest' <>
           structure_record ->> 'record_digest'
        OR side_payload ->> 'manual_decision_digest' <>
           manual_record ->> 'manual_decision_digest'
        OR side_payload ->> 'automated_gate_digest' <> expected_automated_digest
        OR EXISTS (
            SELECT 1 FROM unnest(ARRAY[
                'automated_gate_passed','manual_gate_passed','side_gate_passed'
            ]) AS boolean_key
            WHERE NOT mirror_demo_d02_json_boolean(
                side_payload -> boolean_key
            )
        )
        OR (side_payload ->> 'automated_gate_passed')::boolean
           IS DISTINCT FROM expected_automated_gate
        OR (side_payload ->> 'manual_gate_passed')::boolean
           IS DISTINCT FROM expected_manual_gate
        OR (side_payload ->> 'side_gate_passed')::boolean
           IS DISTINCT FROM expected_side_gate THEN
        RAISE EXCEPTION 'D02 pair side common authority is invalid';
    END IF;

    IF measurement_record ->> 'measurement_evaluation_state' =
       'SUPPORTED_EVALUATED' THEN
        IF NOT mirror_demo_jsonb_exact_keys(
            side_payload,
            ARRAY[
                'schema_version','measurement_evaluation_state','case_id',
                'case_specification_digest','requested_direction',
                'requested_magnitude_ppm','result_output_id','result_asset_id',
                'result_asset_sha256','result_asset_byte_size',
                'result_asset_mime_type','result_asset_width','result_asset_height',
                'asset_variant_id','asset_variant_type','lineage_digest',
                'image_record_id','image_record_digest','result_m3_record_digests',
                'measurement_gate_record_digest','decode_structure_record_digest',
                'manual_decision_digest','raw_signed_target_delta_fixed18',
                'raw_target_absolute_delta_fixed18',
                'raw_max_control_drift_fixed18','measured_signed_delta_ppm',
                'drift_ppm','automated_gate_digest','automated_gate_passed',
                'manual_gate_passed','side_gate_passed','side_quality_state',
                'side_quality_component_ppm'
            ]
        ) OR NOT mirror_demo_d02_json_string_equals(
            side_payload -> 'schema_version',
            'mirror.demo/D02EvaluatedPairSide/v3'
        ) OR NOT mirror_demo_d02_json_string_equals(
            side_payload -> 'measurement_evaluation_state',
            'SUPPORTED_EVALUATED'
        ) THEN
            RAISE EXCEPTION 'D02 evaluated pair side shape is invalid';
        END IF;
        result_measurement := measurement_record ->
            'ordered_result_repeat_measurements' -> 0;
        IF side_payload -> 'raw_signed_target_delta_fixed18' IS DISTINCT FROM
           result_measurement -> 'raw_signed_target_delta_fixed18'
            OR side_payload -> 'raw_target_absolute_delta_fixed18'
               IS DISTINCT FROM
               result_measurement -> 'raw_target_absolute_delta_fixed18'
            OR side_payload -> 'raw_max_control_drift_fixed18'
               IS DISTINCT FROM
               result_measurement -> 'raw_max_control_drift_fixed18'
            OR side_payload -> 'measured_signed_delta_ppm' IS DISTINCT FROM
               result_measurement -> 'measured_signed_delta_ppm'
            OR side_payload -> 'drift_ppm' IS DISTINCT FROM
               result_measurement -> 'drift_ppm' THEN
            RAISE EXCEPTION 'D02 evaluated pair side measurement projection is invalid';
        END IF;
        expected_quality := CASE
            WHEN expected_side_gate THEN mirror_demo_d02_quality_ppm(
                side_payload ->> 'raw_max_control_drift_fixed18'
            )
            ELSE 0
        END;
        IF side_payload ->> 'side_quality_state' <>
           (CASE WHEN expected_side_gate
               THEN 'COMPUTED' ELSE 'NOT_COMPUTED_GATE_FAILED' END)
            OR NOT mirror_demo_d02_json_integer_between(
                side_payload -> 'side_quality_component_ppm',
                expected_quality,
                expected_quality
            ) THEN
            RAISE EXCEPTION 'D02 evaluated pair side quality is invalid';
        END IF;
    ELSE
        IF NOT mirror_demo_jsonb_exact_keys(
            side_payload,
            ARRAY[
                'schema_version','measurement_evaluation_state','case_id',
                'case_specification_digest','requested_direction',
                'requested_magnitude_ppm','result_output_id','result_asset_id',
                'result_asset_sha256','result_asset_byte_size',
                'result_asset_mime_type','result_asset_width','result_asset_height',
                'asset_variant_id','asset_variant_type','lineage_digest',
                'image_record_id','image_record_digest','result_m3_record_digests',
                'measurement_gate_record_digest','decode_structure_record_digest',
                'manual_decision_digest','unsupported_repeat_indexes',
                'ordered_unsupported_reasons','automated_gate_digest',
                'automated_gate_passed','manual_gate_passed','side_gate_passed',
                'side_quality_state','side_quality_component_ppm'
            ]
        ) OR NOT mirror_demo_d02_json_string_equals(
            side_payload -> 'schema_version',
            'mirror.demo/D02UnsupportedPairSide/v3'
        ) OR NOT mirror_demo_d02_json_string_equals(
            side_payload -> 'measurement_evaluation_state',
            'UNSUPPORTED_EXPLICIT'
        ) OR side_payload -> 'unsupported_repeat_indexes' IS DISTINCT FROM
           measurement_record -> 'gate_evaluation' -> 'unsupported_repeat_indexes'
            OR side_payload -> 'ordered_unsupported_reasons' IS DISTINCT FROM
               measurement_record -> 'gate_evaluation' ->
                   'ordered_unsupported_reasons'
            OR expected_automated_gate
            OR expected_side_gate
            OR side_payload ->> 'side_quality_state' <>
               'NOT_COMPUTED_GATE_FAILED'
            OR NOT mirror_demo_d02_json_integer_between(
                side_payload -> 'side_quality_component_ppm', 0, 0
            ) THEN
            RAISE EXCEPTION 'D02 unsupported pair side authority is invalid';
        END IF;
    END IF;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_pairs_v9(
    authority_row demo_pair_screening_reports
)
RETURNS void
LANGUAGE plpgsql
AS $function$
DECLARE
    payload jsonb := authority_row.report_payload;
    pair_wrapper jsonb;
    pair_payload jsonb;
    left_side jsonb;
    right_side jsonb;
    left_case jsonb;
    right_case jsonb;
    source_entry jsonb;
    dimension_record jsonb;
    trace_record jsonb;
    selected_entry jsonb;
    expected_pair_digests jsonb;
    expected_side_digests jsonb;
    expected_side_entries jsonb;
    expected_pair_entries jsonb;
    expected_failure_reasons jsonb;
    expected_eligible_keys jsonb := '[]'::jsonb;
    expected_selected_keys jsonb := '[]'::jsonb;
    expected_id text;
    expected_digest text;
    expected_dimension text;
    expected_decision text;
    expected_status text;
    expected_pair_gate boolean;
    expected_side_gate boolean;
    expected_manual_gate boolean;
    expected_all_side boolean;
    expected_all_pair boolean;
    expected_all_manual boolean;
    expected_all_lock boolean;
    expected_eligible boolean;
    expected_exact_sha boolean;
    expected_slot integer;
    expected_rank integer;
    expected_selected boolean;
    expected_quality integer;
    source_index integer;
    dimension_index integer;
    magnitude_index integer;
    pair_index integer;
    left_case_index integer;
    right_case_index integer;
    selected_index integer := 0;
    selected_slot integer;
    selected_dimension_index integer;
    eligible_count integer := 0;
    eligible_rank integer := 0;
    expected_payload jsonb;
    candidate_dimensions constant text[] := ARRAY[
        'jaw_width','chin_height','eye_spacing'
    ];
    failure_reason_order constant text[] := ARRAY[
        'ONE_OR_MORE_SIDE_GATES_FAILED',
        'ONE_OR_MORE_PAIR_GATES_FAILED',
        'ONE_OR_MORE_MANUAL_GATES_FAILED',
        'GLOBAL_EXACT_SHA_GATE_FAILED',
        'EMPTY_LOCK_POLICY_GATE_FAILED'
    ];
BEGIN
    FOR source_index IN 0..3 LOOP
        source_entry := payload -> 'ordered_source_manifest' -> source_index;
        FOR dimension_index IN 0..2 LOOP
            expected_dimension := candidate_dimensions[dimension_index + 1];
            FOR magnitude_index IN 0..1 LOOP
                pair_index := source_index * 6 + dimension_index * 2 +
                    magnitude_index;
                left_case_index := source_index * 12 + dimension_index * 4 +
                    magnitude_index;
                right_case_index := source_index * 12 + dimension_index * 4 +
                    2 + magnitude_index;
                pair_wrapper := payload -> 'pair_quality_evidence' -> pair_index;
                pair_payload := pair_wrapper -> 'pair_screening_record_payload';
                left_side := pair_payload -> 'left';
                right_side := pair_payload -> 'right';
                left_case := payload -> 'ordered_case_manifest' -> left_case_index;
                right_case := payload -> 'ordered_case_manifest' -> right_case_index;
                IF NOT mirror_demo_jsonb_exact_keys(
                    pair_wrapper,
                    ARRAY[
                        'schema_version','pair_screening_record_payload',
                        'pair_screening_record_digest'
                    ]
                ) OR NOT mirror_demo_d02_json_string_equals(
                    pair_wrapper -> 'schema_version',
                    'mirror.demo/D02PairScreeningRecord/v3'
                ) OR jsonb_typeof(pair_payload) <> 'object'
                    OR NOT mirror_demo_d02_json_string_matches(
                        pair_wrapper -> 'pair_screening_record_digest',
                        '^[0-9a-f]{64}$'
                    )
                    OR pair_wrapper ->> 'pair_screening_record_digest' <>
                       mirror_demo_digest(
                           'mirror.demo/D02PairScreeningRecord/v3', pair_payload
                       )
                    OR NOT mirror_demo_jsonb_exact_keys(
                        pair_payload,
                        ARRAY[
                            'pair_record_id','source_ordinal','source_authority_key',
                            'source_admission_event_id','source_asset_id',
                            'source_asset_sha256','dimension_key','priority_index',
                            'magnitude_ppm','screening_policy_digest','left','right',
                            'same_source_gate_passed',
                            'opposed_direction_gate_passed',
                            'equal_magnitude_gate_passed','pair_side_gates_passed',
                            'empty_lock_policy_gate_passed','pair_quality_state',
                            'pair_quality_ppm','lock_conclusion',
                            'lock_policy_digest','pair_gate_passed'
                        ]
                    ) THEN
                    RAISE EXCEPTION 'D02 pair wrapper or payload shape is invalid';
                END IF;
                expected_id := substring(
                    mirror_demo_digest(
                        'mirror.demo/D02PairScreeningRecordId/v1',
                        jsonb_build_object(
                            'source_authority_key',
                                source_entry ->> 'source_authority_key',
                            'source_admission_event_id',
                                source_entry ->> 'source_admission_event_id',
                            'source_asset_sha256',
                                source_entry ->> 'source_asset_sha256',
                            'dimension_key', expected_dimension,
                            'priority_index', dimension_index + 1,
                            'magnitude_ppm',
                                (ARRAY[15000,30000])[magnitude_index + 1],
                            'left_case_id', left_case ->> 'case_id',
                            'right_case_id', right_case ->> 'case_id',
                            'screening_policy_digest',
                                mirror_demo_d02_expected_screening_policy_digest(),
                            'lock_policy_digest',
                                mirror_demo_d02_expected_lock_policy_digest()
                        )
                    ) FROM 1 FOR 32
                );
                PERFORM mirror_demo_validate_d02_pair_side_v9(
                    authority_row, left_side, left_case_index, 'DECREASE'
                );
                PERFORM mirror_demo_validate_d02_pair_side_v9(
                    authority_row, right_side, right_case_index, 'INCREASE'
                );
                expected_side_gate :=
                    (left_side ->> 'side_gate_passed')::boolean
                    AND (right_side ->> 'side_gate_passed')::boolean;
                expected_pair_gate := expected_side_gate;
                expected_quality := CASE
                    WHEN expected_pair_gate THEN least(
                        (left_side ->> 'side_quality_component_ppm')::integer,
                        (right_side ->> 'side_quality_component_ppm')::integer
                    )
                    ELSE 0
                END;
                IF pair_payload ->> 'pair_record_id' <> expected_id
                    OR NOT mirror_demo_d02_json_integer_between(
                        pair_payload -> 'source_ordinal',
                        source_index + 1,
                        source_index + 1
                    )
                    OR pair_payload ->> 'source_authority_key' <>
                       source_entry ->> 'source_authority_key'
                    OR pair_payload ->> 'source_admission_event_id' <>
                       source_entry ->> 'source_admission_event_id'
                    OR pair_payload ->> 'source_asset_id' <>
                       source_entry ->> 'source_asset_id'
                    OR pair_payload ->> 'source_asset_sha256' <>
                       source_entry ->> 'source_asset_sha256'
                    OR pair_payload ->> 'dimension_key' <> expected_dimension
                    OR NOT mirror_demo_d02_json_integer_between(
                        pair_payload -> 'priority_index',
                        dimension_index + 1,
                        dimension_index + 1
                    )
                    OR NOT mirror_demo_d02_json_integer_between(
                        pair_payload -> 'magnitude_ppm',
                        (ARRAY[15000,30000])[magnitude_index + 1],
                        (ARRAY[15000,30000])[magnitude_index + 1]
                    )
                    OR pair_payload ->> 'screening_policy_digest' <>
                       mirror_demo_d02_expected_screening_policy_digest()
                    OR pair_payload ->> 'lock_policy_digest' <>
                       mirror_demo_d02_expected_lock_policy_digest()
                    OR pair_payload ->> 'lock_conclusion' <>
                       'PASS_FOR_FROZEN_EMPTY_NEUTRAL_POLICY_ONLY'
                    OR EXISTS (
                        SELECT 1 FROM unnest(ARRAY[
                            'same_source_gate_passed',
                            'opposed_direction_gate_passed',
                            'equal_magnitude_gate_passed','pair_side_gates_passed',
                            'empty_lock_policy_gate_passed','pair_gate_passed'
                        ]) AS boolean_key
                        WHERE NOT mirror_demo_d02_json_boolean(
                            pair_payload -> boolean_key
                        )
                    )
                    OR (pair_payload ->> 'same_source_gate_passed')::boolean
                       IS DISTINCT FROM true
                    OR (pair_payload ->>
                        'opposed_direction_gate_passed')::boolean
                       IS DISTINCT FROM true
                    OR (pair_payload ->> 'equal_magnitude_gate_passed')::boolean
                       IS DISTINCT FROM true
                    OR (pair_payload ->> 'pair_side_gates_passed')::boolean
                       IS DISTINCT FROM expected_side_gate
                    OR (pair_payload ->>
                        'empty_lock_policy_gate_passed')::boolean
                       IS DISTINCT FROM true
                    OR (pair_payload ->> 'pair_gate_passed')::boolean
                       IS DISTINCT FROM expected_pair_gate
                    OR pair_payload ->> 'pair_quality_state' <>
                       (CASE WHEN expected_pair_gate
                           THEN 'COMPUTED' ELSE 'NOT_COMPUTED_GATE_FAILED' END)
                    OR NOT mirror_demo_d02_json_integer_between(
                        pair_payload -> 'pair_quality_ppm',
                        expected_quality,
                        expected_quality
                    ) THEN
                    RAISE EXCEPTION 'D02 pair Gate or quality authority is invalid';
                END IF;
            END LOOP;
        END LOOP;
    END LOOP;

    expected_exact_sha := (
        payload -> 'exact_duplicate_evidence' ->> 'exact_sha_gate_passed'
    )::boolean;
    FOR dimension_index IN 0..2 LOOP
        expected_dimension := candidate_dimensions[dimension_index + 1];
        dimension_record := payload -> 'dimension_eligibility' -> dimension_index;
        expected_pair_digests := '[]'::jsonb;
        expected_side_digests := '[]'::jsonb;
        expected_side_entries := '[]'::jsonb;
        expected_pair_entries := '[]'::jsonb;
        expected_all_side := true;
        expected_all_pair := true;
        expected_all_manual := true;
        expected_all_lock := true;
        FOR source_index IN 0..3 LOOP
            FOR magnitude_index IN 0..1 LOOP
                pair_index := source_index * 6 + dimension_index * 2 +
                    magnitude_index;
                pair_wrapper := payload -> 'pair_quality_evidence' -> pair_index;
                pair_payload := pair_wrapper -> 'pair_screening_record_payload';
                left_side := pair_payload -> 'left';
                right_side := pair_payload -> 'right';
                expected_pair_digests := expected_pair_digests ||
                    jsonb_build_array(
                        pair_wrapper -> 'pair_screening_record_digest'
                    );
                expected_side_digests := expected_side_digests ||
                    jsonb_build_array(left_side -> 'automated_gate_digest') ||
                    jsonb_build_array(right_side -> 'automated_gate_digest');
                expected_side_entries := expected_side_entries ||
                    jsonb_build_array(jsonb_build_object(
                        'schema_version',
                            'mirror.demo/D02DimensionSideGateEntry/v1',
                        'source_ordinal', source_index + 1,
                        'magnitude_ppm',
                            (ARRAY[15000,30000])[magnitude_index + 1],
                        'side', 'LEFT',
                        'case_id', left_side ->> 'case_id',
                        'automated_gate_digest',
                            left_side ->> 'automated_gate_digest',
                        'manual_decision_digest',
                            left_side ->> 'manual_decision_digest',
                        'automated_gate_passed',
                            (left_side ->> 'automated_gate_passed')::boolean,
                        'manual_gate_passed',
                            (left_side ->> 'manual_gate_passed')::boolean,
                        'side_gate_passed',
                            (left_side ->> 'side_gate_passed')::boolean
                    )) || jsonb_build_array(jsonb_build_object(
                        'schema_version',
                            'mirror.demo/D02DimensionSideGateEntry/v1',
                        'source_ordinal', source_index + 1,
                        'magnitude_ppm',
                            (ARRAY[15000,30000])[magnitude_index + 1],
                        'side', 'RIGHT',
                        'case_id', right_side ->> 'case_id',
                        'automated_gate_digest',
                            right_side ->> 'automated_gate_digest',
                        'manual_decision_digest',
                            right_side ->> 'manual_decision_digest',
                        'automated_gate_passed',
                            (right_side ->> 'automated_gate_passed')::boolean,
                        'manual_gate_passed',
                            (right_side ->> 'manual_gate_passed')::boolean,
                        'side_gate_passed',
                            (right_side ->> 'side_gate_passed')::boolean
                    ));
                expected_pair_entries := expected_pair_entries ||
                    jsonb_build_array(jsonb_build_object(
                        'schema_version',
                            'mirror.demo/D02DimensionPairGateEntry/v1',
                        'source_ordinal', source_index + 1,
                        'magnitude_ppm',
                            (ARRAY[15000,30000])[magnitude_index + 1],
                        'pair_record_id', pair_payload ->> 'pair_record_id',
                        'pair_screening_record_digest',
                            pair_wrapper ->> 'pair_screening_record_digest',
                        'pair_gate_passed',
                            (pair_payload ->> 'pair_gate_passed')::boolean
                    ));
                expected_all_side := expected_all_side
                    AND (left_side ->> 'side_gate_passed')::boolean
                    AND (right_side ->> 'side_gate_passed')::boolean;
                expected_all_pair := expected_all_pair
                    AND (pair_payload ->> 'pair_gate_passed')::boolean;
                expected_all_manual := expected_all_manual
                    AND (left_side ->> 'manual_gate_passed')::boolean
                    AND (right_side ->> 'manual_gate_passed')::boolean;
                expected_all_lock := expected_all_lock
                    AND (pair_payload ->>
                        'empty_lock_policy_gate_passed')::boolean;
            END LOOP;
        END LOOP;
        PERFORM mirror_demo_d02_require_record(
            dimension_record,
            'mirror.demo/D02DimensionEligibilityRecord/v3',
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
        IF dimension_record ->> 'dimension_key' <> expected_dimension
            OR NOT mirror_demo_d02_json_integer_between(
                dimension_record -> 'priority_index',
                dimension_index + 1,
                dimension_index + 1
            )
            OR dimension_record -> 'ordered_pair_screening_record_digests'
               IS DISTINCT FROM expected_pair_digests
            OR dimension_record -> 'ordered_side_automated_gate_digests'
               IS DISTINCT FROM expected_side_digests
            OR dimension_record ->> 'sixteen_side_gate_digest' <>
               mirror_demo_digest(
                   'mirror.demo/D02SixteenSideGate/v1',
                   jsonb_build_object(
                       'dimension_key', expected_dimension,
                       'priority_index', dimension_index + 1,
                       'ordered_side_gate_entries', expected_side_entries
                   )
               )
            OR dimension_record ->> 'eight_pair_gate_digest' <>
               mirror_demo_digest(
                   'mirror.demo/D02EightPairGate/v1',
                   jsonb_build_object(
                       'dimension_key', expected_dimension,
                       'priority_index', dimension_index + 1,
                       'ordered_pair_gate_entries', expected_pair_entries
                   )
               )
            OR EXISTS (
                SELECT 1 FROM unnest(ARRAY[
                    'all_sixteen_side_gates_passed',
                    'all_eight_pair_gates_passed','all_manual_gates_passed',
                    'global_exact_sha_gate_passed',
                    'empty_lock_policy_gate_passed','eligible'
                ]) AS boolean_key
                WHERE NOT mirror_demo_d02_json_boolean(
                    dimension_record -> boolean_key
                )
            )
            OR (dimension_record ->>
                'all_sixteen_side_gates_passed')::boolean
               IS DISTINCT FROM expected_all_side
            OR (dimension_record ->>
                'all_eight_pair_gates_passed')::boolean
               IS DISTINCT FROM expected_all_pair
            OR (dimension_record ->> 'all_manual_gates_passed')::boolean
               IS DISTINCT FROM expected_all_manual
            OR (dimension_record ->> 'global_exact_sha_gate_passed')::boolean
               IS DISTINCT FROM expected_exact_sha
            OR (dimension_record ->>
                'empty_lock_policy_gate_passed')::boolean
               IS DISTINCT FROM expected_all_lock
            OR (dimension_record ->> 'eligible')::boolean
               IS DISTINCT FROM expected_eligible
            OR dimension_record -> 'failure_reasons' IS DISTINCT FROM
               expected_failure_reasons THEN
            RAISE EXCEPTION 'D02 dimension eligibility authority is invalid';
        END IF;
        IF expected_eligible THEN
            eligible_count := eligible_count + 1;
            expected_eligible_keys := expected_eligible_keys ||
                jsonb_build_array(expected_dimension);
        END IF;
    END LOOP;

    FOR dimension_index IN 0..2 LOOP
        expected_dimension := candidate_dimensions[dimension_index + 1];
        dimension_record := payload -> 'dimension_eligibility' -> dimension_index;
        trace_record := payload -> 'fixed_priority_selection_trace' ->
            dimension_index;
        expected_eligible := (dimension_record ->> 'eligible')::boolean;
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
        PERFORM mirror_demo_d02_require_record(
            trace_record,
            'mirror.demo/D02SelectionTraceRecord/v2',
            ARRAY[
                'schema_version','selection_step','dimension_key','priority_index',
                'dimension_eligibility_record_digest','eligible','eligible_rank',
                'selection_decision','selection_slot','selected','record_digest'
            ]
        );
        IF NOT mirror_demo_d02_json_integer_between(
                trace_record -> 'selection_step',
                dimension_index + 1,
                dimension_index + 1
            )
            OR trace_record ->> 'dimension_key' <> expected_dimension
            OR NOT mirror_demo_d02_json_integer_between(
                trace_record -> 'priority_index',
                dimension_index + 1,
                dimension_index + 1
            )
            OR trace_record ->> 'dimension_eligibility_record_digest' <>
               dimension_record ->> 'record_digest'
            OR NOT mirror_demo_d02_json_boolean(trace_record -> 'eligible')
            OR (trace_record ->> 'eligible')::boolean
               IS DISTINCT FROM expected_eligible
            OR NOT mirror_demo_d02_json_integer_between(
                trace_record -> 'eligible_rank', expected_rank, expected_rank
            )
            OR trace_record ->> 'selection_decision' <> expected_decision
            OR NOT mirror_demo_d02_json_integer_between(
                trace_record -> 'selection_slot', expected_slot, expected_slot
            )
            OR NOT mirror_demo_d02_json_boolean(trace_record -> 'selected')
            OR (trace_record ->> 'selected')::boolean
               IS DISTINCT FROM expected_selected THEN
            RAISE EXCEPTION 'D02 selection trace is not the unique state projection';
        END IF;
        IF expected_selected THEN
            expected_selected_keys := expected_selected_keys ||
                jsonb_build_array(expected_dimension);
        END IF;
    END LOOP;

    expected_status := CASE
        WHEN expected_exact_sha AND eligible_count >= 2 THEN 'PASSED'
        ELSE 'FAILED'
    END;
    IF authority_row.status <> expected_status
        OR authority_row.eligible_dimension_keys IS DISTINCT FROM
           expected_eligible_keys
        OR authority_row.selected_dimension_keys IS DISTINCT FROM
           expected_selected_keys
        OR NOT mirror_demo_d02_dimension_array_valid(
            authority_row.eligible_dimension_keys, 3
        )
        OR NOT mirror_demo_d02_dimension_array_valid(
            authority_row.selected_dimension_keys, 2
        ) THEN
        RAISE EXCEPTION 'D02 report status or dimension projection is invalid';
    END IF;

    IF expected_status = 'PASSED' THEN
        IF jsonb_array_length(payload -> 'selected_pair_manifest') <> 16 THEN
            RAISE EXCEPTION 'D02 PASSED selected manifest cardinality is invalid';
        END IF;
        FOR selected_slot IN 1..2 LOOP
            expected_dimension := authority_row.selected_dimension_keys ->>
                (selected_slot - 1);
            selected_dimension_index := array_position(
                candidate_dimensions, expected_dimension
            ) - 1;
            FOR source_index IN 0..3 LOOP
                FOR magnitude_index IN 0..1 LOOP
                    selected_entry := payload -> 'selected_pair_manifest' ->
                        selected_index;
                    pair_index := source_index * 6 +
                        selected_dimension_index * 2 + magnitude_index;
                    pair_wrapper := payload -> 'pair_quality_evidence' ->
                        pair_index;
                    pair_payload := pair_wrapper ->
                        'pair_screening_record_payload';
                    left_side := pair_payload -> 'left';
                    right_side := pair_payload -> 'right';
                    PERFORM mirror_demo_d02_require_record(
                        selected_entry,
                        'mirror.demo/D02SelectedPairManifestEntry/v2',
                        ARRAY[
                            'schema_version','selected_pair_ordinal',
                            'selected_dimension_slot','dimension_key','priority_index',
                            'source_ordinal','source_authority_key',
                            'source_admission_event_id','magnitude_ppm','pair_record_id',
                            'pair_screening_record_digest','left_case_id',
                            'left_result_asset_id','left_result_asset_sha256',
                            'left_asset_variant_id','right_case_id',
                            'right_result_asset_id','right_result_asset_sha256',
                            'right_asset_variant_id','entry_digest'
                        ],
                        'entry_digest'
                    );
                    expected_payload := jsonb_build_object(
                        'schema_version',
                            'mirror.demo/D02SelectedPairManifestEntry/v2',
                        'selected_pair_ordinal', selected_index + 1,
                        'selected_dimension_slot', selected_slot,
                        'dimension_key', expected_dimension,
                        'priority_index', selected_dimension_index + 1,
                        'source_ordinal', source_index + 1,
                        'source_authority_key',
                            pair_payload ->> 'source_authority_key',
                        'source_admission_event_id',
                            pair_payload ->> 'source_admission_event_id',
                        'magnitude_ppm',
                            (ARRAY[15000,30000])[magnitude_index + 1],
                        'pair_record_id', pair_payload ->> 'pair_record_id',
                        'pair_screening_record_digest',
                            pair_wrapper ->> 'pair_screening_record_digest',
                        'left_case_id', left_side ->> 'case_id',
                        'left_result_asset_id', left_side ->> 'result_asset_id',
                        'left_result_asset_sha256',
                            left_side ->> 'result_asset_sha256',
                        'left_asset_variant_id',
                            left_side ->> 'asset_variant_id',
                        'right_case_id', right_side ->> 'case_id',
                        'right_result_asset_id', right_side ->> 'result_asset_id',
                        'right_result_asset_sha256',
                            right_side ->> 'result_asset_sha256',
                        'right_asset_variant_id',
                            right_side ->> 'asset_variant_id',
                        'entry_digest', selected_entry ->> 'entry_digest'
                    );
                    IF selected_entry IS DISTINCT FROM expected_payload
                        OR (pair_payload ->> 'pair_gate_passed')::boolean
                           IS DISTINCT FROM true THEN
                        RAISE EXCEPTION 'D02 selected manifest projection is invalid';
                    END IF;
                    selected_index := selected_index + 1;
                END LOOP;
            END LOOP;
        END LOOP;
        expected_digest := mirror_demo_digest(
            'mirror.demo/D02SelectedPairManifest/v2',
            payload -> 'selected_pair_manifest'
        );
        IF authority_row.selected_pair_manifest_digest IS DISTINCT FROM
           expected_digest
            OR authority_row.selected_pair_count <> 16
            OR authority_row.selected_result_side_count <> 32 THEN
            RAISE EXCEPTION 'D02 selected manifest digest or count is invalid';
        END IF;
    ELSE
        IF payload -> 'selected_pair_manifest' <> '[]'::jsonb
            OR authority_row.selected_dimension_keys <> '[]'::jsonb
            OR authority_row.selected_pair_manifest_digest IS NOT NULL
            OR authority_row.selected_pair_count <> 0
            OR authority_row.selected_result_side_count <> 0 THEN
            RAISE EXCEPTION 'D02 FAILED report exposes selected authority';
        END IF;
    END IF;

    IF authority_row.source_count <> 4
        OR authority_row.case_count <> 48
        OR authority_row.source_m3_repeat_count <> 12
        OR authority_row.m4_execution_count <> 96
        OR authority_row.result_m3_repeat_count <> 144
        OR authority_row.manual_decision_count <> 48
        OR authority_row.exact_sha_record_count <> 52
        OR authority_row.phash_comparison_count <> 1326
        OR authority_row.candidate_pair_count <> 24
        OR authority_row.report_digest IS DISTINCT FROM mirror_demo_digest(
            authority_row.schema_version, payload
        ) THEN
        RAISE EXCEPTION 'D02 report fixed counts or digest are invalid';
    END IF;
    expected_id := substring(
        mirror_demo_digest(
            'mirror.demo/D02PairScreeningReportId/v1',
            jsonb_build_object('report_digest', authority_row.report_digest)
        ) FROM 1 FOR 32
    );
    IF authority_row.id <> expected_id THEN
        RAISE EXCEPTION 'D02 screening report ID mismatch';
    END IF;
    expected_payload := mirror_demo_authority_projection(
        to_jsonb(authority_row), 'demo_pair_screening_reports'
    );
    IF authority_row.status = 'FAILED' THEN
        expected_payload := expected_payload - 'selected_pair_manifest_digest';
    END IF;
    IF authority_row.canonical_payload IS DISTINCT FROM expected_payload
        OR authority_row.content_digest IS DISTINCT FROM mirror_demo_digest(
            authority_row.schema_version, expected_payload
        ) THEN
        RAISE EXCEPTION 'D02 report canonical authority is invalid';
    END IF;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_report_outcomes_v9(
    authority_row demo_pair_screening_reports
)
RETURNS void
LANGUAGE plpgsql
AS $function$
BEGIN
    PERFORM mirror_demo_validate_d02_measurements_v9(authority_row);
    PERFORM mirror_demo_validate_d02_images_v9(authority_row);
    PERFORM mirror_demo_validate_d02_pairs_v9(authority_row);
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_screening_report_v9(
    authority_row demo_pair_screening_reports
)
RETURNS void
LANGUAGE plpgsql
AS $function$
DECLARE
    payload jsonb := authority_row.report_payload;
    binding jsonb;
    network_boundary jsonb;
    source_entry jsonb;
    prior_source_entry jsonb;
    raw_entry jsonb;
    projection_entry jsonb;
    supported_measurement jsonb;
    case_entry jsonb;
    source_m3_record jsonb;
    first_source_m3_record jsonb;
    m4_record jsonb;
    first_m4_record jsonb;
    result_m3_record jsonb;
    measurement_record jsonb;
    peer_measurement_record jsonb;
    gate_evaluation jsonb;
    result_measurement jsonb;
    control_delta jsonb;
    structure_record jsonb;
    manual_record jsonb;
    image_record jsonb;
    prior_image_record jsonb;
    signature_record jsonb;
    comparison_record jsonb;
    pair_wrapper jsonb;
    pair_payload jsonb;
    side_payload jsonb;
    dimension_record jsonb;
    trace_record jsonb;
    selected_entry jsonb;
    identity_row demo_synthetic_identities%ROWTYPE;
    source_asset assets%ROWTYPE;
    expected_payload jsonb;
    expected_id text;
    expected_digest text;
    expected_dimension text;
    expected_direction text;
    expected_control_dimensions text[];
    expected_source_ordinal integer;
    expected_priority integer;
    expected_direction_index integer;
    expected_magnitude integer;
    expected_magnitude_index integer;
    expected_repeat integer;
    expected_case_index integer;
    source_index integer;
    case_index integer;
    repeat_index integer;
    replay_index integer;
    image_index integer;
    pair_index integer;
    dimension_index integer;
    control_index integer;
    comparison_index integer := 0;
    left_index integer;
    right_index integer;
    raw_source numeric;
    raw_result numeric;
    raw_signed_delta numeric;
    raw_absolute_delta numeric;
    control_absolute_delta numeric;
    maximum_control_delta numeric;
    winning_control_ordinal integer;
    expected_gate boolean;
    exact_sha_gate boolean;
    eligible_count integer := 0;
    candidate_dimensions constant text[] := ARRAY[
        'jaw_width','chin_height','eye_spacing'
    ];
    all_dimensions constant text[] := ARRAY[
        'cheekbone_width','chin_height','eye_spacing',
        'jaw_width','mouth_width','nose_width'
    ];
    failure_reason_order constant text[] := ARRAY[
        'ONE_OR_MORE_SIDE_GATES_FAILED',
        'ONE_OR_MORE_PAIR_GATES_FAILED',
        'ONE_OR_MORE_MANUAL_GATES_FAILED',
        'GLOBAL_EXACT_SHA_GATE_FAILED',
        'EMPTY_LOCK_POLICY_GATE_FAILED'
    ];
BEGIN
    IF authority_row.schema_version <> 'mirror.demo/D02PairScreeningReport/v1'
        OR NOT mirror_demo_jsonb_exact_keys(
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
        ) THEN
        RAISE EXCEPTION 'D02 Revision 9 report envelope is invalid';
    END IF;

    binding := payload -> 'schema_and_policy';
    IF NOT mirror_demo_jsonb_exact_keys(
        binding,
        ARRAY[
            'schema_version','source_manifest_digest','case_manifest_digest',
            'screening_policy_digest','runtime_manifest_digest',
            'vision_model_manifest_digest','topology_digest',
            'measurement_config_digest','manual_review_policy_digest',
            'duplicate_policy_digest','phash_implementation_digest'
        ]
    ) OR NOT mirror_demo_d02_json_string_equals(
        binding -> 'schema_version', 'mirror.demo/D02SchemaAndPolicyBinding/v1'
    ) OR EXISTS (
        SELECT 1
        FROM unnest(ARRAY[
            'source_manifest_digest','case_manifest_digest','screening_policy_digest',
            'runtime_manifest_digest','vision_model_manifest_digest','topology_digest',
            'measurement_config_digest','manual_review_policy_digest',
            'duplicate_policy_digest','phash_implementation_digest'
        ]) AS digest_key
        WHERE NOT mirror_demo_d02_json_string_matches(
            binding -> digest_key, '^[0-9a-f]{64}$'
        )
    ) OR binding ->> 'source_manifest_digest' <> authority_row.source_manifest_digest
        OR binding ->> 'case_manifest_digest' <> authority_row.case_manifest_digest
        OR binding ->> 'screening_policy_digest' <>
           authority_row.screening_policy_digest
        OR binding ->> 'runtime_manifest_digest' <>
           authority_row.runtime_manifest_digest
        OR binding ->> 'vision_model_manifest_digest' <>
           authority_row.vision_model_manifest_digest
        OR binding ->> 'topology_digest' <> authority_row.topology_digest
        OR binding ->> 'measurement_config_digest' <>
           authority_row.measurement_config_digest
        OR binding ->> 'manual_review_policy_digest' <>
           authority_row.manual_review_policy_digest
        OR binding ->> 'duplicate_policy_digest' <>
           authority_row.duplicate_policy_digest
        OR binding ->> 'phash_implementation_digest' <>
           authority_row.phash_implementation_digest THEN
        RAISE EXCEPTION 'D02 Revision 9 policy binding is invalid';
    END IF;
    IF authority_row.screening_policy_digest IS DISTINCT FROM
       mirror_demo_d02_expected_screening_policy_digest() THEN
        RAISE EXCEPTION 'D02 screening policy root is not the accepted Revision 9 root';
    END IF;

    network_boundary := payload -> 'network_and_runtime_boundary';
    IF NOT mirror_demo_jsonb_exact_keys(
        network_boundary,
        ARRAY[
            'schema_version','public_internet_egress',
            'localhost_and_docker_internal_network','proxy_environment_present',
            'production_provider_calls','runtime_generation_calls',
            'boundary_receipt_digest'
        ]
    ) OR NOT mirror_demo_d02_json_string_equals(
        network_boundary -> 'schema_version',
        'mirror.demo/D02NetworkRuntimeBoundary/v2'
    ) OR NOT mirror_demo_d02_json_string_equals(
        network_boundary -> 'public_internet_egress', 'DENIED'
    ) OR NOT mirror_demo_d02_json_boolean(
        network_boundary -> 'localhost_and_docker_internal_network'
    ) OR network_boundary -> 'localhost_and_docker_internal_network' <> 'true'::jsonb
        OR NOT mirror_demo_d02_json_boolean(
            network_boundary -> 'proxy_environment_present'
        )
        OR network_boundary -> 'proxy_environment_present' <> 'false'::jsonb
        OR NOT mirror_demo_d02_json_integer_between(
            network_boundary -> 'production_provider_calls', 0, 0
        )
        OR NOT mirror_demo_d02_json_integer_between(
            network_boundary -> 'runtime_generation_calls', 0, 0
        )
        OR NOT mirror_demo_d02_json_string_matches(
            network_boundary -> 'boundary_receipt_digest', '^[0-9a-f]{64}$'
        ) THEN
        RAISE EXCEPTION 'D02 Revision 9 network boundary is invalid';
    END IF;

    IF jsonb_typeof(payload -> 'ordered_source_manifest') <> 'array'
        OR jsonb_array_length(payload -> 'ordered_source_manifest') <> 4
        OR jsonb_typeof(payload -> 'ordered_case_manifest') <> 'array'
        OR jsonb_array_length(payload -> 'ordered_case_manifest') <> 48
        OR jsonb_typeof(payload -> 'source_m3_repeat_evidence') <> 'array'
        OR jsonb_array_length(payload -> 'source_m3_repeat_evidence') <> 12
        OR jsonb_typeof(payload -> 'm4_repeat_evidence') <> 'array'
        OR jsonb_array_length(payload -> 'm4_repeat_evidence') <> 96
        OR jsonb_typeof(payload -> 'result_m3_repeat_evidence') <> 'array'
        OR jsonb_array_length(payload -> 'result_m3_repeat_evidence') <> 144
        OR jsonb_typeof(payload -> 'measurement_gate_evidence') <> 'array'
        OR jsonb_array_length(payload -> 'measurement_gate_evidence') <> 48
        OR jsonb_typeof(payload -> 'decode_structure_immutability_evidence') <> 'array'
        OR jsonb_array_length(payload -> 'decode_structure_immutability_evidence') <> 48
        OR jsonb_typeof(payload -> 'manual_review_evidence') <> 'array'
        OR jsonb_array_length(payload -> 'manual_review_evidence') <> 48
        OR jsonb_typeof(payload -> 'pair_quality_evidence') <> 'array'
        OR jsonb_array_length(payload -> 'pair_quality_evidence') <> 24
        OR jsonb_typeof(payload -> 'dimension_eligibility') <> 'array'
        OR jsonb_array_length(payload -> 'dimension_eligibility') <> 3
        OR jsonb_typeof(payload -> 'fixed_priority_selection_trace') <> 'array'
        OR jsonb_array_length(payload -> 'fixed_priority_selection_trace') <> 3
        OR jsonb_typeof(payload -> 'selected_pair_manifest') <> 'array' THEN
        RAISE EXCEPTION 'D02 Revision 9 fixed evidence universe is incomplete';
    END IF;

    FOR source_index IN 0..3 LOOP
        source_entry := payload -> 'ordered_source_manifest' -> source_index;
        PERFORM mirror_demo_d02_require_record(
            source_entry,
            'mirror.demo/D02SourceAuthorityManifestEntry/v2',
            ARRAY[
                'schema_version','source_ordinal','source_authority_kind',
                'source_authority_key','source_admission_event_id',
                'source_admission_content_digest','source_output_id','source_asset_id',
                'source_asset_sha256','source_asset_byte_size','source_asset_mime_type',
                'source_asset_width','source_asset_height','source_receipt_digest',
                'source_authority_digest','source_qa_snapshot_digest',
                'source_landmark_digest','source_measurement_digest',
                'source_provenance_digest','source_fact_snapshot_digest',
                'raw_measurement_authority_digest',
                'source_measurement_projection_digest','adult_synthetic_attested',
                'original_formal_identity_id_status',
                'source_p2_candidate_manifest_content_digest',
                'dimension_authority_manifest_content_digest',
                'ordered_supported_measurements','record_digest'
            ]
        );
        IF NOT mirror_demo_d02_json_integer_between(
                source_entry -> 'source_ordinal', source_index + 1, source_index + 1
            )
            OR NOT mirror_demo_d02_json_string_equals(
                source_entry -> 'source_authority_kind', 'DEMO_LOCAL_IMPORTED_COPY'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                source_entry -> 'source_authority_key', '^[0-9a-f]{64}$'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                source_entry -> 'source_admission_event_id', '^[0-9a-f]{32}$'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                source_entry -> 'source_admission_content_digest', '^[0-9a-f]{64}$'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                source_entry -> 'source_output_id',
                '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                source_entry -> 'source_asset_id', '^[0-9a-f]{32}$'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                source_entry -> 'source_asset_sha256', '^[0-9a-f]{64}$'
            )
            OR NOT mirror_demo_d02_json_integer_between(
                source_entry -> 'source_asset_byte_size', 1, 9223372036854775807
            )
            OR NOT mirror_demo_d02_json_string_equals(
                source_entry -> 'source_asset_mime_type', 'image/jpeg'
            )
            OR NOT mirror_demo_d02_json_integer_between(
                source_entry -> 'source_asset_width', 1, 2147483647
            )
            OR NOT mirror_demo_d02_json_integer_between(
                source_entry -> 'source_asset_height', 1, 2147483647
            )
            OR EXISTS (
                SELECT 1
                FROM unnest(ARRAY[
                    'source_receipt_digest','source_authority_digest',
                    'source_qa_snapshot_digest','source_landmark_digest',
                    'source_measurement_digest','source_provenance_digest',
                    'source_fact_snapshot_digest','raw_measurement_authority_digest',
                    'source_measurement_projection_digest',
                    'source_p2_candidate_manifest_content_digest',
                    'dimension_authority_manifest_content_digest'
                ]) AS digest_key
                WHERE NOT mirror_demo_d02_json_string_matches(
                    source_entry -> digest_key, '^[0-9a-f]{64}$'
                )
            )
            OR NOT mirror_demo_d02_json_boolean(
                source_entry -> 'adult_synthetic_attested'
            )
            OR source_entry -> 'adult_synthetic_attested' <> 'true'::jsonb
            OR NOT mirror_demo_d02_json_string_equals(
                source_entry -> 'original_formal_identity_id_status',
                'UNKNOWN_REDACTED_NOT_RECOVERED'
            )
            OR source_entry ->> 'source_p2_candidate_manifest_content_digest' <>
               'eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4'
            OR source_entry ->> 'dimension_authority_manifest_content_digest' <>
               'd4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a'
            OR jsonb_typeof(source_entry -> 'ordered_supported_measurements') <> 'array'
            OR jsonb_array_length(source_entry -> 'ordered_supported_measurements') <> 6 THEN
            RAISE EXCEPTION 'D02 source manifest scalar authority is invalid';
        END IF;

        SELECT * INTO identity_row
        FROM demo_synthetic_identities
        WHERE id = source_entry ->> 'source_admission_event_id';
        SELECT * INTO source_asset
        FROM assets
        WHERE id = source_entry ->> 'source_asset_id';
        IF NOT FOUND
            OR identity_row.id IS NULL
            OR identity_row.schema_version <> 'mirror.demo/DemoSyntheticIdentity/v2'
            OR identity_row.source_authority_kind <> 'DEMO_LOCAL_IMPORTED_COPY'
            OR identity_row.admission_action <> 'ADMIT'
            OR identity_row.source_authority_key <>
               source_entry ->> 'source_authority_key'
            OR identity_row.content_digest <>
               source_entry ->> 'source_admission_content_digest'
            OR identity_row.source_output_id <> source_entry ->> 'source_output_id'
            OR identity_row.formal_canonical_asset_id <>
               source_entry ->> 'source_asset_id'
            OR identity_row.formal_canonical_asset_sha256 <>
               source_entry ->> 'source_asset_sha256'
            OR identity_row.source_receipt_digest <>
               source_entry ->> 'source_receipt_digest'
            OR identity_row.source_authority_digest <>
               source_entry ->> 'source_authority_digest'
            OR identity_row.source_qa_snapshot_digest <>
               source_entry ->> 'source_qa_snapshot_digest'
            OR identity_row.source_landmark_digest <>
               source_entry ->> 'source_landmark_digest'
            OR identity_row.source_measurement_digest <>
               source_entry ->> 'source_measurement_digest'
            OR source_entry ->> 'raw_measurement_authority_digest' <>
               identity_row.source_measurement_digest
            OR source_entry ->> 'raw_measurement_authority_digest' <>
               identity_row.source_fact_snapshot ->> 'raw_measurement_authority_digest'
            OR identity_row.source_provenance_digest <>
               source_entry ->> 'source_provenance_digest'
            OR identity_row.source_fact_snapshot_digest <>
               source_entry ->> 'source_fact_snapshot_digest'
            OR identity_row.source_measurement_projection_digest <>
               source_entry ->> 'source_measurement_projection_digest'
            OR source_asset.deleted_at IS NOT NULL
            OR source_asset.owner_user_id IS NOT NULL
            OR source_asset.asset_role <> 'synthetic'
            OR source_asset.internal_purpose <> 'synthetic_dataset'
            OR NOT source_asset.synthetic
            OR NOT source_asset.is_ai_generated
            OR source_asset.is_ai_modified
            OR source_asset.sha256 <> source_entry ->> 'source_asset_sha256'
            OR source_asset.byte_size <>
               (source_entry ->> 'source_asset_byte_size')::bigint
            OR source_asset.mime_type <> 'image/jpeg'
            OR source_asset.width <> (source_entry ->> 'source_asset_width')::integer
            OR source_asset.height <> (source_entry ->> 'source_asset_height')::integer
            OR EXISTS (
                SELECT 1
                FROM demo_synthetic_identities later_event
                WHERE later_event.source_authority_key = identity_row.source_authority_key
                  AND later_event.admission_sequence > identity_row.admission_sequence
            ) THEN
            RAISE EXCEPTION 'D02 source manifest does not match current local authority';
        END IF;
        IF source_index > 0 THEN
            prior_source_entry := payload -> 'ordered_source_manifest' -> (source_index - 1);
            IF (prior_source_entry ->> 'source_authority_key',
                prior_source_entry ->> 'source_admission_event_id') >=
               (source_entry ->> 'source_authority_key',
                source_entry ->> 'source_admission_event_id') THEN
                RAISE EXCEPTION 'D02 source manifest order is invalid';
            END IF;
        END IF;

        FOR control_index IN 0..5 LOOP
            supported_measurement :=
                source_entry -> 'ordered_supported_measurements' -> control_index;
            raw_entry := identity_row.source_fact_snapshot ->
                'raw_measurement_authority' -> 'ordered_entries' -> control_index;
            projection_entry := identity_row.source_measurement_projection ->
                'ordered_entries' -> control_index;
            expected_dimension := all_dimensions[control_index + 1];
            IF NOT mirror_demo_jsonb_exact_keys(
                supported_measurement,
                ARRAY[
                    'schema_version','dimension_key','raw_value_fixed18',
                    'raw_confidence_fixed18','raw_reliability_fixed18','value_ppm',
                    'confidence_ppm','reliability_ppm','unit'
                ]
            ) OR NOT mirror_demo_d02_json_string_equals(
                supported_measurement -> 'schema_version',
                'mirror.demo/D02SupportedSourceMeasurement/v1'
            ) OR NOT mirror_demo_d02_json_string_equals(
                supported_measurement -> 'dimension_key', expected_dimension
            ) OR NOT mirror_demo_d02_json_fixed18(
                supported_measurement -> 'raw_value_fixed18'
            ) OR NOT mirror_demo_d02_json_fixed18(
                supported_measurement -> 'raw_confidence_fixed18'
            ) OR NOT mirror_demo_d02_json_fixed18(
                supported_measurement -> 'raw_reliability_fixed18'
            ) OR NOT mirror_demo_d02_json_integer_between(
                supported_measurement -> 'value_ppm', 1, 1000000
            ) OR NOT mirror_demo_d02_json_integer_between(
                supported_measurement -> 'confidence_ppm', 1, 1000000
            ) OR NOT mirror_demo_d02_json_integer_between(
                supported_measurement -> 'reliability_ppm', 1, 1000000
            ) OR NOT mirror_demo_d02_json_string_equals(
                supported_measurement -> 'unit', 'FACE_HEIGHT_PPM'
            ) OR supported_measurement ->> 'raw_value_fixed18' <>
                 raw_entry ->> 'raw_value_fixed18'
                OR supported_measurement ->> 'raw_confidence_fixed18' <>
                   raw_entry ->> 'raw_confidence_fixed18'
                OR supported_measurement ->> 'raw_reliability_fixed18' <>
                   raw_entry ->> 'raw_reliability_fixed18'
                OR supported_measurement -> 'value_ppm' IS DISTINCT FROM
                   projection_entry -> 'value_ppm'
                OR supported_measurement -> 'confidence_ppm' IS DISTINCT FROM
                   projection_entry -> 'confidence_ppm'
                OR supported_measurement -> 'reliability_ppm' IS DISTINCT FROM
                   projection_entry -> 'reliability_ppm' THEN
                RAISE EXCEPTION 'D02 source measurement projection is invalid';
            END IF;
        END LOOP;
    END LOOP;
    IF authority_row.source_manifest_digest IS DISTINCT FROM mirror_demo_digest(
        'mirror.demo/D02SourceAuthorityManifest/v1',
        payload -> 'ordered_source_manifest'
    ) THEN
        RAISE EXCEPTION 'D02 source manifest digest mismatch';
    END IF;

    FOR case_index IN 0..47 LOOP
        case_entry := payload -> 'ordered_case_manifest' -> case_index;
        PERFORM mirror_demo_d02_require_record(
            case_entry,
            'mirror.demo/D02GeometryCaseManifestEntry/v3',
            ARRAY[
                'schema_version','case_ordinal','case_id','source_manifest_digest',
                'source_ordinal','source_authority_key','source_admission_event_id',
                'source_asset_id','source_asset_sha256','source_qa_snapshot_digest',
                'source_measurement_projection_digest',
                'source_p2_candidate_manifest_content_digest',
                'dimension_authority_manifest_content_digest',
                'geometry_ontology_version_digest','dimension_key','priority_index',
                'direction','direction_index','magnitude_ppm','magnitude_index',
                'ordered_control_dimensions','warp_plan_digest',
                'geometry_algorithm_version','runtime_manifest_digest',
                'runtime_config_digest','output_policy_version','output_width',
                'output_height','determinism_level','execution_config_digest',
                'case_specification_digest','record_digest'
            ]
        );
        expected_source_ordinal := case_index / 12 + 1;
        expected_priority := (case_index % 12) / 4 + 1;
        expected_direction_index := (case_index % 4) / 2 + 1;
        expected_magnitude_index := case_index % 2 + 1;
        expected_dimension := candidate_dimensions[expected_priority];
        expected_direction := (ARRAY['DECREASE','INCREASE'])[expected_direction_index];
        expected_magnitude := (ARRAY[15000,30000])[expected_magnitude_index];
        source_entry := payload -> 'ordered_source_manifest' ->
            (expected_source_ordinal - 1);
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
        IF NOT mirror_demo_d02_json_integer_between(
                case_entry -> 'case_ordinal', case_index + 1, case_index + 1
            )
            OR NOT mirror_demo_d02_json_string_matches(
                case_entry -> 'case_id', '^[0-9a-f]{32}$'
            )
            OR NOT mirror_demo_d02_json_integer_between(
                case_entry -> 'source_ordinal',
                expected_source_ordinal,
                expected_source_ordinal
            )
            OR NOT mirror_demo_d02_json_string_equals(
                case_entry -> 'dimension_key', expected_dimension
            )
            OR NOT mirror_demo_d02_json_integer_between(
                case_entry -> 'priority_index', expected_priority, expected_priority
            )
            OR NOT mirror_demo_d02_json_string_equals(
                case_entry -> 'direction', expected_direction
            )
            OR NOT mirror_demo_d02_json_integer_between(
                case_entry -> 'direction_index',
                expected_direction_index,
                expected_direction_index
            )
            OR NOT mirror_demo_d02_json_integer_between(
                case_entry -> 'magnitude_ppm', expected_magnitude, expected_magnitude
            )
            OR NOT mirror_demo_d02_json_integer_between(
                case_entry -> 'magnitude_index',
                expected_magnitude_index,
                expected_magnitude_index
            )
            OR case_entry -> 'ordered_control_dimensions' IS DISTINCT FROM
               to_jsonb(expected_control_dimensions)
            OR case_entry ->> 'source_manifest_digest' <>
               authority_row.source_manifest_digest
            OR case_entry ->> 'source_authority_key' <>
               source_entry ->> 'source_authority_key'
            OR case_entry ->> 'source_admission_event_id' <>
               source_entry ->> 'source_admission_event_id'
            OR case_entry ->> 'source_asset_id' <> source_entry ->> 'source_asset_id'
            OR case_entry ->> 'source_asset_sha256' <>
               source_entry ->> 'source_asset_sha256'
            OR case_entry ->> 'source_qa_snapshot_digest' <>
               source_entry ->> 'source_qa_snapshot_digest'
            OR case_entry ->> 'source_measurement_projection_digest' <>
               source_entry ->> 'source_measurement_projection_digest'
            OR case_entry ->> 'source_p2_candidate_manifest_content_digest' <>
               'eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4'
            OR case_entry ->> 'dimension_authority_manifest_content_digest' <>
               'd4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a'
            OR case_entry ->> 'geometry_ontology_version_digest' <>
               'd902fe2cfdf69db9f62ccc2e5fa7c569227d652f1204aa683742fc3c592f38b9'
            OR case_entry ->> 'runtime_manifest_digest' <>
               authority_row.runtime_manifest_digest
            OR NOT mirror_demo_d02_json_string_matches(
                case_entry -> 'warp_plan_digest', '^[0-9a-f]{64}$'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                case_entry -> 'runtime_config_digest', '^[0-9a-f]{64}$'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                case_entry -> 'execution_config_digest', '^[0-9a-f]{64}$'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                case_entry -> 'case_specification_digest', '^[0-9a-f]{64}$'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                case_entry -> 'geometry_algorithm_version',
                '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                case_entry -> 'output_policy_version',
                '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                case_entry -> 'determinism_level',
                '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'
            )
            OR NOT mirror_demo_d02_json_integer_between(
                case_entry -> 'output_width', 1, 2147483647
            )
            OR NOT mirror_demo_d02_json_integer_between(
                case_entry -> 'output_height', 1, 2147483647
            ) THEN
            RAISE EXCEPTION 'D02 case manifest order or scalar authority is invalid';
        END IF;
        expected_digest := mirror_demo_digest(
            'mirror.demo/D02ExecutionConfiguration/v1',
            jsonb_build_object(
                'screening_policy_digest', authority_row.screening_policy_digest,
                'runtime_manifest_digest', authority_row.runtime_manifest_digest,
                'vision_model_manifest_digest', authority_row.vision_model_manifest_digest,
                'topology_digest', authority_row.topology_digest,
                'measurement_config_digest', authority_row.measurement_config_digest,
                'manual_review_policy_digest', authority_row.manual_review_policy_digest,
                'duplicate_policy_digest', authority_row.duplicate_policy_digest,
                'phash_implementation_digest', authority_row.phash_implementation_digest,
                'geometry_algorithm_version', case_entry ->> 'geometry_algorithm_version',
                'runtime_config_digest', case_entry ->> 'runtime_config_digest',
                'output_policy_version', case_entry ->> 'output_policy_version',
                'output_width', (case_entry ->> 'output_width')::integer,
                'output_height', (case_entry ->> 'output_height')::integer,
                'determinism_level', case_entry ->> 'determinism_level'
            )
        );
        IF case_entry ->> 'execution_config_digest' <> expected_digest THEN
            RAISE EXCEPTION 'D02 execution configuration digest mismatch';
        END IF;
        expected_id := substring(
            mirror_demo_digest(
                'mirror.demo/D02GeometryCaseId/v1',
                jsonb_build_object(
                    'source_manifest_digest', authority_row.source_manifest_digest,
                    'source_authority_key', source_entry ->> 'source_authority_key',
                    'source_admission_event_id',
                        source_entry ->> 'source_admission_event_id',
                    'source_asset_sha256', source_entry ->> 'source_asset_sha256',
                    'source_p2_candidate_manifest_content_digest',
                        'eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4',
                    'dimension_authority_manifest_content_digest',
                        'd4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a',
                    'dimension_key', expected_dimension,
                    'direction', expected_direction,
                    'magnitude_ppm', expected_magnitude,
                    'execution_config_digest', expected_digest
                )
            ) FROM 1 FOR 32
        );
        IF case_entry ->> 'case_id' <> expected_id THEN
            RAISE EXCEPTION 'D02 case ID preimage mismatch';
        END IF;
        expected_payload := jsonb_build_object(
            'source_manifest_digest', authority_row.source_manifest_digest,
            'source_ordinal', expected_source_ordinal,
            'source_authority_key', source_entry ->> 'source_authority_key',
            'source_admission_event_id', source_entry ->> 'source_admission_event_id',
            'source_asset_id', source_entry ->> 'source_asset_id',
            'source_asset_sha256', source_entry ->> 'source_asset_sha256',
            'source_qa_snapshot_digest', source_entry ->> 'source_qa_snapshot_digest',
            'source_measurement_projection_digest',
                source_entry ->> 'source_measurement_projection_digest',
            'source_p2_candidate_manifest_content_digest',
                'eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4',
            'dimension_authority_manifest_content_digest',
                'd4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a',
            'geometry_ontology_version_digest',
                'd902fe2cfdf69db9f62ccc2e5fa7c569227d652f1204aa683742fc3c592f38b9',
            'dimension_key', expected_dimension,
            'priority_index', expected_priority,
            'direction', expected_direction,
            'direction_index', expected_direction_index,
            'magnitude_ppm', expected_magnitude,
            'magnitude_index', expected_magnitude_index,
            'ordered_control_dimensions', to_jsonb(expected_control_dimensions),
            'warp_plan_digest', case_entry ->> 'warp_plan_digest',
            'geometry_algorithm_version', case_entry ->> 'geometry_algorithm_version',
            'runtime_manifest_digest', authority_row.runtime_manifest_digest,
            'runtime_config_digest', case_entry ->> 'runtime_config_digest',
            'output_policy_version', case_entry ->> 'output_policy_version',
            'output_width', (case_entry ->> 'output_width')::integer,
            'output_height', (case_entry ->> 'output_height')::integer,
            'determinism_level', case_entry ->> 'determinism_level',
            'execution_config_digest', expected_digest
        );
        IF case_entry ->> 'case_specification_digest' IS DISTINCT FROM
           mirror_demo_digest(
               'mirror.demo/D02GeometryCaseSpecification/v1', expected_payload
           ) THEN
            RAISE EXCEPTION 'D02 case specification digest mismatch';
        END IF;
    END LOOP;
    IF authority_row.case_manifest_digest IS DISTINCT FROM mirror_demo_digest(
        'mirror.demo/D02GeometryCaseManifest/v1', payload -> 'ordered_case_manifest'
    ) THEN
        RAISE EXCEPTION 'D02 case manifest digest mismatch';
    END IF;

    FOR repeat_index IN 0..11 LOOP
        source_m3_record := payload -> 'source_m3_repeat_evidence' -> repeat_index;
        expected_source_ordinal := repeat_index / 3 + 1;
        expected_repeat := repeat_index % 3 + 1;
        source_entry := payload -> 'ordered_source_manifest' ->
            (expected_source_ordinal - 1);
        PERFORM mirror_demo_d02_require_record(
            source_m3_record,
            'mirror.demo/D02SourceM3RepeatRecord/v1',
            ARRAY[
                'schema_version','source_m3_record_id','source_ordinal',
                'source_authority_key','source_admission_event_id','source_asset_id',
                'source_asset_sha256','repeat_index','execution_receipt_digest',
                'vision_model_manifest_digest','runtime_manifest_digest',
                'topology_digest','canonical_output_digest','landmark_digest',
                'measurement_digest','face_count','landmark_count',
                'coordinates_finite','coordinates_in_bounds','repeat_gate_passed',
                'record_digest'
            ]
        );
        expected_id := substring(
            mirror_demo_digest(
                'mirror.demo/D02SourceM3RecordId/v1',
                jsonb_build_object(
                    'source_manifest_digest', authority_row.source_manifest_digest,
                    'source_authority_key', source_entry ->> 'source_authority_key',
                    'source_admission_event_id',
                        source_entry ->> 'source_admission_event_id',
                    'source_asset_id', source_entry ->> 'source_asset_id',
                    'source_asset_sha256', source_entry ->> 'source_asset_sha256',
                    'repeat_index', expected_repeat,
                    'vision_model_manifest_digest',
                        authority_row.vision_model_manifest_digest,
                    'runtime_manifest_digest', authority_row.runtime_manifest_digest,
                    'topology_digest', authority_row.topology_digest
                )
            ) FROM 1 FOR 32
        );
        IF NOT mirror_demo_d02_json_string_equals(
                source_m3_record -> 'source_m3_record_id', expected_id
            )
            OR NOT mirror_demo_d02_json_integer_between(
                source_m3_record -> 'source_ordinal',
                expected_source_ordinal,
                expected_source_ordinal
            )
            OR NOT mirror_demo_d02_json_integer_between(
                source_m3_record -> 'repeat_index', expected_repeat, expected_repeat
            )
            OR source_m3_record ->> 'source_authority_key' <>
               source_entry ->> 'source_authority_key'
            OR source_m3_record ->> 'source_admission_event_id' <>
               source_entry ->> 'source_admission_event_id'
            OR source_m3_record ->> 'source_asset_id' <>
               source_entry ->> 'source_asset_id'
            OR source_m3_record ->> 'source_asset_sha256' <>
               source_entry ->> 'source_asset_sha256'
            OR source_m3_record ->> 'vision_model_manifest_digest' <>
               authority_row.vision_model_manifest_digest
            OR source_m3_record ->> 'runtime_manifest_digest' <>
               authority_row.runtime_manifest_digest
            OR source_m3_record ->> 'topology_digest' <> authority_row.topology_digest
            OR EXISTS (
                SELECT 1 FROM unnest(ARRAY[
                    'execution_receipt_digest','canonical_output_digest',
                    'landmark_digest','measurement_digest'
                ]) AS digest_key
                WHERE NOT mirror_demo_d02_json_string_matches(
                    source_m3_record -> digest_key, '^[0-9a-f]{64}$'
                )
            )
            OR NOT mirror_demo_d02_json_integer_between(
                source_m3_record -> 'face_count', 1, 1
            )
            OR NOT mirror_demo_d02_json_integer_between(
                source_m3_record -> 'landmark_count', 478, 478
            )
            OR NOT mirror_demo_d02_json_boolean(
                source_m3_record -> 'coordinates_finite'
            )
            OR source_m3_record -> 'coordinates_finite' <> 'true'::jsonb
            OR NOT mirror_demo_d02_json_boolean(
                source_m3_record -> 'coordinates_in_bounds'
            )
            OR source_m3_record -> 'coordinates_in_bounds' <> 'true'::jsonb
            OR NOT mirror_demo_d02_json_boolean(
                source_m3_record -> 'repeat_gate_passed'
            )
            OR source_m3_record -> 'repeat_gate_passed' <> 'true'::jsonb THEN
            RAISE EXCEPTION 'D02 source M3 record authority is invalid';
        END IF;
        first_source_m3_record := payload -> 'source_m3_repeat_evidence' ->
            ((expected_source_ordinal - 1) * 3);
        IF source_m3_record ->> 'canonical_output_digest' <>
           first_source_m3_record ->> 'canonical_output_digest'
            OR source_m3_record ->> 'landmark_digest' <>
               first_source_m3_record ->> 'landmark_digest'
            OR source_m3_record ->> 'measurement_digest' <>
               first_source_m3_record ->> 'measurement_digest' THEN
            RAISE EXCEPTION 'D02 source M3 repeats are not deterministic';
        END IF;
    END LOOP;

    FOR replay_index IN 0..95 LOOP
        m4_record := payload -> 'm4_repeat_evidence' -> replay_index;
        expected_case_index := replay_index / 2;
        expected_repeat := replay_index % 2 + 1;
        case_entry := payload -> 'ordered_case_manifest' -> expected_case_index;
        source_entry := payload -> 'ordered_source_manifest' ->
            ((case_entry ->> 'source_ordinal')::integer - 1);
        PERFORM mirror_demo_d02_require_record(
            m4_record,
            'mirror.demo/D02M4ExecutionRecord/v1',
            ARRAY[
                'schema_version','m4_execution_record_id','case_id',
                'case_specification_digest','replay_index','source_output_id',
                'source_asset_id','source_asset_sha256','result_output_id',
                'result_sha256','result_byte_size','result_mime_type','result_width',
                'result_height','changed_pixel_count','warp_plan_digest',
                'geometry_algorithm_version','runtime_manifest_digest',
                'runtime_config_digest','determinism_level',
                'execution_receipt_digest','execution_succeeded','record_digest'
            ]
        );
        expected_id := substring(
            mirror_demo_digest(
                'mirror.demo/D02M4ExecutionRecordId/v1',
                jsonb_build_object(
                    'case_id', case_entry ->> 'case_id',
                    'case_specification_digest',
                        case_entry ->> 'case_specification_digest',
                    'replay_index', expected_repeat,
                    'geometry_algorithm_version',
                        case_entry ->> 'geometry_algorithm_version',
                    'runtime_manifest_digest',
                        case_entry ->> 'runtime_manifest_digest',
                    'runtime_config_digest', case_entry ->> 'runtime_config_digest',
                    'determinism_level', case_entry ->> 'determinism_level'
                )
            ) FROM 1 FOR 32
        );
        IF NOT mirror_demo_d02_json_string_equals(
                m4_record -> 'm4_execution_record_id', expected_id
            )
            OR m4_record ->> 'case_id' <> case_entry ->> 'case_id'
            OR m4_record ->> 'case_specification_digest' <>
               case_entry ->> 'case_specification_digest'
            OR NOT mirror_demo_d02_json_integer_between(
                m4_record -> 'replay_index', expected_repeat, expected_repeat
            )
            OR m4_record ->> 'source_output_id' <> source_entry ->> 'source_output_id'
            OR m4_record ->> 'source_asset_id' <> source_entry ->> 'source_asset_id'
            OR m4_record ->> 'source_asset_sha256' <>
               source_entry ->> 'source_asset_sha256'
            OR NOT mirror_demo_d02_json_string_matches(
                m4_record -> 'result_output_id',
                '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                m4_record -> 'result_sha256', '^[0-9a-f]{64}$'
            )
            OR NOT mirror_demo_d02_json_integer_between(
                m4_record -> 'result_byte_size', 1, 9223372036854775807
            )
            OR NOT mirror_demo_d02_json_string_equals(
                m4_record -> 'result_mime_type', 'image/jpeg'
            )
            OR NOT mirror_demo_d02_json_integer_between(
                m4_record -> 'result_width', 1, 2147483647
            )
            OR NOT mirror_demo_d02_json_integer_between(
                m4_record -> 'result_height', 1, 2147483647
            )
            OR NOT mirror_demo_d02_json_integer_between(
                m4_record -> 'changed_pixel_count',
                1,
                (m4_record ->> 'result_width')::integer *
                    (m4_record ->> 'result_height')::integer
            )
            OR m4_record ->> 'warp_plan_digest' <> case_entry ->> 'warp_plan_digest'
            OR m4_record ->> 'geometry_algorithm_version' <>
               case_entry ->> 'geometry_algorithm_version'
            OR m4_record ->> 'runtime_manifest_digest' <>
               case_entry ->> 'runtime_manifest_digest'
            OR m4_record ->> 'runtime_config_digest' <>
               case_entry ->> 'runtime_config_digest'
            OR m4_record ->> 'determinism_level' <>
               case_entry ->> 'determinism_level'
            OR NOT mirror_demo_d02_json_string_matches(
                m4_record -> 'execution_receipt_digest', '^[0-9a-f]{64}$'
            )
            OR NOT mirror_demo_d02_json_boolean(
                m4_record -> 'execution_succeeded'
            )
            OR m4_record -> 'execution_succeeded' <> 'true'::jsonb THEN
            RAISE EXCEPTION 'D02 M4 record or execution precondition is invalid';
        END IF;
        first_m4_record := payload -> 'm4_repeat_evidence' -> (expected_case_index * 2);
        IF m4_record -> 'result_output_id' IS DISTINCT FROM
           first_m4_record -> 'result_output_id'
            OR m4_record -> 'result_sha256' IS DISTINCT FROM
               first_m4_record -> 'result_sha256'
            OR m4_record -> 'result_byte_size' IS DISTINCT FROM
               first_m4_record -> 'result_byte_size'
            OR m4_record -> 'result_mime_type' IS DISTINCT FROM
               first_m4_record -> 'result_mime_type'
            OR m4_record -> 'result_width' IS DISTINCT FROM
               first_m4_record -> 'result_width'
            OR m4_record -> 'result_height' IS DISTINCT FROM
               first_m4_record -> 'result_height'
            OR m4_record -> 'changed_pixel_count' IS DISTINCT FROM
               first_m4_record -> 'changed_pixel_count' THEN
            RAISE EXCEPTION 'D02 M4 replay pair is not byte/dimension deterministic';
        END IF;
    END LOOP;

    FOR repeat_index IN 0..143 LOOP
        result_m3_record := payload -> 'result_m3_repeat_evidence' -> repeat_index;
        expected_case_index := repeat_index / 3;
        expected_repeat := repeat_index % 3 + 1;
        case_entry := payload -> 'ordered_case_manifest' -> expected_case_index;
        first_m4_record := payload -> 'm4_repeat_evidence' -> (expected_case_index * 2);
        PERFORM mirror_demo_d02_require_record(
            result_m3_record,
            'mirror.demo/D02ResultM3RepeatRecord/v1',
            ARRAY[
                'schema_version','result_m3_record_id','case_id',
                'case_specification_digest','result_output_id','result_sha256',
                'repeat_index','execution_receipt_digest',
                'vision_model_manifest_digest','runtime_manifest_digest',
                'topology_digest','canonical_output_digest','landmark_digest',
                'measurement_observation_digest','face_count','landmark_count',
                'coordinates_finite','coordinates_in_bounds','observation_state',
                'repeat_gate_passed','record_digest'
            ]
        );
        expected_id := substring(
            mirror_demo_digest(
                'mirror.demo/D02ResultM3RecordId/v1',
                jsonb_build_object(
                    'case_id', case_entry ->> 'case_id',
                    'case_specification_digest',
                        case_entry ->> 'case_specification_digest',
                    'result_output_id', first_m4_record ->> 'result_output_id',
                    'result_sha256', first_m4_record ->> 'result_sha256',
                    'repeat_index', expected_repeat,
                    'vision_model_manifest_digest',
                        authority_row.vision_model_manifest_digest,
                    'runtime_manifest_digest', authority_row.runtime_manifest_digest,
                    'topology_digest', authority_row.topology_digest
                )
            ) FROM 1 FOR 32
        );
        IF NOT mirror_demo_d02_json_string_equals(
                result_m3_record -> 'result_m3_record_id', expected_id
            )
            OR result_m3_record ->> 'case_id' <> case_entry ->> 'case_id'
            OR result_m3_record ->> 'case_specification_digest' <>
               case_entry ->> 'case_specification_digest'
            OR result_m3_record ->> 'result_output_id' <>
               first_m4_record ->> 'result_output_id'
            OR result_m3_record ->> 'result_sha256' <>
               first_m4_record ->> 'result_sha256'
            OR NOT mirror_demo_d02_json_integer_between(
                result_m3_record -> 'repeat_index', expected_repeat, expected_repeat
            )
            OR result_m3_record ->> 'vision_model_manifest_digest' <>
               authority_row.vision_model_manifest_digest
            OR result_m3_record ->> 'runtime_manifest_digest' <>
               authority_row.runtime_manifest_digest
            OR result_m3_record ->> 'topology_digest' <> authority_row.topology_digest
            OR EXISTS (
                SELECT 1 FROM unnest(ARRAY[
                    'execution_receipt_digest','canonical_output_digest',
                    'landmark_digest','measurement_observation_digest'
                ]) AS digest_key
                WHERE NOT mirror_demo_d02_json_string_matches(
                    result_m3_record -> digest_key, '^[0-9a-f]{64}$'
                )
            )
            OR NOT mirror_demo_d02_json_integer_between(
                result_m3_record -> 'face_count', 0, 2147483647
            )
            OR NOT mirror_demo_d02_json_integer_between(
                result_m3_record -> 'landmark_count', 0, 2147483647
            )
            OR NOT mirror_demo_d02_json_boolean(
                result_m3_record -> 'coordinates_finite'
            )
            OR NOT mirror_demo_d02_json_boolean(
                result_m3_record -> 'coordinates_in_bounds'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                result_m3_record -> 'observation_state',
                '^(SUPPORTED|UNSUPPORTED_EXPLICIT)$'
            )
            OR NOT mirror_demo_d02_json_boolean(
                result_m3_record -> 'repeat_gate_passed'
            ) THEN
            RAISE EXCEPTION 'D02 result M3 record scalar authority is invalid';
        END IF;
        expected_gate := (result_m3_record ->> 'face_count')::integer = 1
            AND (result_m3_record ->> 'landmark_count')::integer = 478
            AND result_m3_record -> 'coordinates_finite' = 'true'::jsonb
            AND result_m3_record -> 'coordinates_in_bounds' = 'true'::jsonb
            AND result_m3_record ->> 'observation_state' = 'SUPPORTED';
        IF (result_m3_record ->> 'repeat_gate_passed')::boolean IS DISTINCT FROM
           expected_gate THEN
            RAISE EXCEPTION 'D02 result M3 repeat Gate is not derived';
        END IF;
    END LOOP;

    -- Remaining nested groups are validated by the second-stage helper so the
    -- report trigger has one fail-closed transaction boundary.
    PERFORM mirror_demo_validate_d02_report_outcomes_v9(authority_row);
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_screening_report()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    PERFORM mirror_demo_validate_d02_screening_report_v9(NEW);
    RETURN NEW;
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
    IF NOT mirror_demo_d02_json_string_matches(
            fact_payload -> 'source_output_id',
            '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'
        )
        OR NOT mirror_demo_d02_json_string_matches(
            fact_payload -> 'source_asset_sha256', '^[0-9a-f]{64}$'
        )
        OR NOT mirror_demo_d02_json_integer_between(
            fact_payload -> 'source_asset_byte_size', 1, 9223372036854775807
        )
        OR jsonb_typeof(fact_payload -> 'source_asset_mime_type') <> 'string'
        OR NOT mirror_demo_d02_json_integer_between(
            fact_payload -> 'source_asset_width', 1, 2147483647
        )
        OR NOT mirror_demo_d02_json_integer_between(
            fact_payload -> 'source_asset_height', 1, 2147483647
        )
        OR EXISTS (
            SELECT 1
            FROM unnest(ARRAY[
                'source_receipt_digest','source_authority_digest','qa_policy_digest',
                'source_qa_snapshot_digest','source_landmark_digest',
                'source_measurement_digest','source_provenance_digest',
                'source_measurement_projection_digest',
                'raw_measurement_authority_digest',
                'source_p2_candidate_manifest_content_digest',
                'dimension_authority_manifest_content_digest'
            ]) AS digest_key
            WHERE NOT mirror_demo_d02_json_string_matches(
                fact_payload -> digest_key, '^[0-9a-f]{64}$'
            )
        )
        OR NOT mirror_demo_d02_json_boolean(fact_payload -> 'adult_synthetic_attested')
        OR fact_payload -> 'adult_synthetic_attested' <> 'true'::jsonb
        OR NOT mirror_demo_d02_json_string_equals(
            fact_payload -> 'original_formal_identity_id_status',
            'UNKNOWN_REDACTED_NOT_RECOVERED'
        )
        OR jsonb_typeof(fact_payload -> 'measurement_projection_version') <> 'string'
        OR jsonb_typeof(fact_payload -> 'measurement_quantization_version') <> 'string'
        OR jsonb_typeof(fact_payload -> 'source_measurement_projection') <> 'object'
        OR jsonb_typeof(fact_payload -> 'raw_measurement_authority') <> 'object' THEN
        RAISE EXCEPTION 'D02 recovered fact snapshot scalar types are invalid';
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
    IF EXISTS (
        SELECT 1
        FROM unnest(ARRAY[
            'measurement_version','decimal_serialization_version'
        ]) AS string_key
        WHERE jsonb_typeof(raw_payload -> string_key) <> 'string'
    ) OR EXISTS (
        SELECT 1
        FROM unnest(ARRAY[
            'source_p2_candidate_manifest_content_digest',
            'dimension_authority_manifest_content_digest'
        ]) AS digest_key
        WHERE NOT mirror_demo_d02_json_string_matches(
            raw_payload -> digest_key, '^[0-9a-f]{64}$'
        )
    ) OR EXISTS (
        SELECT 1
        FROM unnest(ARRAY[
            'measurement_version','measurement_projection_version',
            'measurement_quantization_version'
        ]) AS string_key
        WHERE jsonb_typeof(projection_payload -> string_key) <> 'string'
    ) OR EXISTS (
        SELECT 1
        FROM unnest(ARRAY[
            'source_p2_candidate_manifest_content_digest',
            'dimension_authority_manifest_content_digest'
        ]) AS digest_key
        WHERE NOT mirror_demo_d02_json_string_matches(
            projection_payload -> digest_key, '^[0-9a-f]{64}$'
        )
    ) THEN
        RAISE EXCEPTION 'D02 morphology authority scalar types are invalid';
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
            OR jsonb_typeof(raw_entry -> 'dimension_key') <> 'string'
            OR jsonb_typeof(projection_entry -> 'dimension_key') <> 'string'
            OR jsonb_typeof(raw_entry -> 'support_state') <> 'string'
            OR jsonb_typeof(projection_entry -> 'support_state') <> 'string'
            OR jsonb_typeof(projection_entry -> 'unit') <> 'string'
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
                OR NOT mirror_demo_d02_json_integer_between(
                    projection_entry -> 'value_ppm', 1, 1000000
                )
                OR NOT mirror_demo_d02_json_integer_between(
                    projection_entry -> 'confidence_ppm', 1, 1000000
                )
                OR NOT mirror_demo_d02_json_integer_between(
                    projection_entry -> 'reliability_ppm', 1, 1000000
                )
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
                OR NOT mirror_demo_d02_json_integer_between(
                    projection_entry -> 'confidence_ppm', 0, 0
                )
                OR NOT mirror_demo_d02_json_integer_between(
                    projection_entry -> 'reliability_ppm', 0, 0
                )
                OR jsonb_typeof(raw_entry -> 'unsupported_reason') <> 'string'
                OR jsonb_typeof(projection_entry -> 'unsupported_reason') <> 'string'
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
        OR authority_row.source_measurement_digest IS DISTINCT FROM
           fact_payload ->> 'raw_measurement_authority_digest'
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
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_screening_report_rejected_v5()
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
    dimension_record jsonb;
    dimension_record_count integer;
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
        SELECT count(*), jsonb_agg(candidate.value) -> 0
        INTO dimension_record_count, dimension_record
        FROM jsonb_array_elements(
            report_row.report_payload -> 'dimension_eligibility'
        ) AS candidate(value)
        WHERE candidate.value ->> 'dimension_key' = expected_dimension;
        IF NOT mirror_demo_jsonb_exact_keys(
            dimension_entry,
            ARRAY[
                'dimension_key','priority_index','sixteen_side_gate_digest',
                'eight_pair_gate_digest'
            ]
        ) OR dimension_entry ->> 'dimension_key' <> expected_dimension
            OR NOT mirror_demo_d02_json_integer_between(
                dimension_entry -> 'priority_index', expected_priority, expected_priority
            )
            OR dimension_record_count <> 1
            OR NOT mirror_demo_d02_json_boolean(dimension_record -> 'eligible')
            OR dimension_record -> 'eligible' <> 'true'::jsonb
            OR dimension_entry -> 'priority_index' IS DISTINCT FROM
               dimension_record -> 'priority_index'
            OR dimension_entry -> 'sixteen_side_gate_digest' IS DISTINCT FROM
               dimension_record -> 'sixteen_side_gate_digest'
            OR dimension_entry -> 'eight_pair_gate_digest' IS DISTINCT FROM
               dimension_record -> 'eight_pair_gate_digest' THEN
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
    pair_wrapper jsonb;
    pair_payload jsonb;
    selected_entry jsonb;
    side_payload jsonb;
    side_name text;
    wrapper_count integer;
    selected_entry_count integer;
    expected_result_asset_id text;
    expected_result_sha text;
    expected_variant_id text;
    expected_direction text;
    expected_delta_ppm integer;
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
        OR bank_row.pair_manifest_digest IS DISTINCT FROM
           report_row.selected_pair_manifest_digest
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
            'pair_screening_record_schema_version','pair_screening_record_digest',
            'pair_screening_record_payload'
        ]
    ) OR NEW.qa_payload ->> 'schema_version' <>
           'mirror.demo/D02QuestionPairQAPayload/v2'
        OR NEW.qa_payload ->> 'screening_report_id' <> NEW.screening_report_id
        OR NEW.qa_payload ->> 'screening_report_digest' <> NEW.screening_report_digest
        OR NEW.qa_payload ->> 'pair_screening_record_schema_version' <>
           'mirror.demo/D02PairScreeningRecord/v3'
        OR NEW.qa_payload ->> 'pair_screening_record_digest' !~ '^[0-9a-f]{64}$'
        OR jsonb_typeof(NEW.qa_payload -> 'pair_screening_record_payload') <> 'object'
        OR NEW.magnitude_ppm NOT IN (15000,30000) THEN
        RAISE EXCEPTION 'D02 question pair QA payload is invalid';
    END IF;

    SELECT count(*), jsonb_agg(candidate.value) -> 0
    INTO wrapper_count, pair_wrapper
    FROM jsonb_array_elements(
        report_row.report_payload -> 'pair_quality_evidence'
    ) AS candidate(value)
    WHERE candidate.value ->> 'pair_screening_record_digest' =
          NEW.qa_payload ->> 'pair_screening_record_digest';
    pair_payload := NEW.qa_payload -> 'pair_screening_record_payload';
    IF wrapper_count <> 1
        OR pair_wrapper ->> 'schema_version' <>
           NEW.qa_payload ->> 'pair_screening_record_schema_version'
        OR pair_wrapper ->> 'pair_screening_record_digest' <>
           NEW.qa_payload ->> 'pair_screening_record_digest'
        OR pair_wrapper -> 'pair_screening_record_payload' IS DISTINCT FROM pair_payload
        OR NEW.qa_payload ->> 'pair_screening_record_digest' IS DISTINCT FROM
           mirror_demo_digest('mirror.demo/D02PairScreeningRecord/v3', pair_payload) THEN
        RAISE EXCEPTION 'D02 question pair QA does not resolve one exact report record';
    END IF;

    SELECT count(*), jsonb_agg(candidate.value) -> 0
    INTO selected_entry_count, selected_entry
    FROM jsonb_array_elements(
        report_row.report_payload -> 'selected_pair_manifest'
    ) AS candidate(value)
    WHERE candidate.value ->> 'pair_screening_record_digest' =
          NEW.qa_payload ->> 'pair_screening_record_digest';
    IF selected_entry_count <> 1
        OR pair_payload ->> 'source_authority_key' <>
           identity_row.source_authority_key
        OR pair_payload ->> 'source_admission_event_id' <>
           NEW.demo_synthetic_identity_id
        OR pair_payload ->> 'source_asset_id' <> NEW.source_asset_id
        OR pair_payload ->> 'source_asset_sha256' <> NEW.source_asset_sha256
        OR pair_payload ->> 'dimension_key' <> NEW.dimension_key
        OR NOT mirror_demo_d02_json_integer_between(
            pair_payload -> 'magnitude_ppm', NEW.magnitude_ppm, NEW.magnitude_ppm
        )
        OR NOT mirror_demo_d02_json_integer_between(
            pair_payload -> 'pair_quality_ppm', NEW.pair_quality_ppm, NEW.pair_quality_ppm
        )
        OR NOT mirror_demo_d02_json_boolean(pair_payload -> 'pair_gate_passed')
        OR pair_payload -> 'pair_gate_passed' <> 'true'::jsonb
        OR selected_entry -> 'source_ordinal' IS DISTINCT FROM
           pair_payload -> 'source_ordinal'
        OR selected_entry ->> 'source_authority_key' <>
           pair_payload ->> 'source_authority_key'
        OR selected_entry ->> 'source_admission_event_id' <>
           pair_payload ->> 'source_admission_event_id'
        OR selected_entry ->> 'dimension_key' <> pair_payload ->> 'dimension_key'
        OR selected_entry -> 'priority_index' IS DISTINCT FROM
           pair_payload -> 'priority_index'
        OR selected_entry -> 'magnitude_ppm' IS DISTINCT FROM
           pair_payload -> 'magnitude_ppm'
        OR selected_entry ->> 'pair_record_id' <> pair_payload ->> 'pair_record_id'
        OR selected_entry ->> 'left_case_id' <> pair_payload -> 'left' ->> 'case_id'
        OR selected_entry ->> 'left_result_asset_id' <>
           pair_payload -> 'left' ->> 'result_asset_id'
        OR selected_entry ->> 'left_result_asset_sha256' <>
           pair_payload -> 'left' ->> 'result_asset_sha256'
        OR selected_entry ->> 'left_asset_variant_id' <>
           pair_payload -> 'left' ->> 'asset_variant_id'
        OR selected_entry ->> 'right_case_id' <> pair_payload -> 'right' ->> 'case_id'
        OR selected_entry ->> 'right_result_asset_id' <>
           pair_payload -> 'right' ->> 'result_asset_id'
        OR selected_entry ->> 'right_result_asset_sha256' <>
           pair_payload -> 'right' ->> 'result_asset_sha256'
        OR selected_entry ->> 'right_asset_variant_id' <>
           pair_payload -> 'right' ->> 'asset_variant_id' THEN
        RAISE EXCEPTION 'D02 question pair is not one exact selected report pair';
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
        IF side_payload ->> 'result_asset_id' <> expected_result_asset_id
            OR side_payload ->> 'result_asset_sha256' <> expected_result_sha
            OR side_payload ->> 'asset_variant_id' <> expected_variant_id
            OR side_payload ->> 'asset_variant_type' <> 'demo_p3_p7_geometry_v1'
            OR side_payload ->> 'requested_direction' <> expected_direction
            OR NOT mirror_demo_d02_json_integer_between(
                side_payload -> 'requested_magnitude_ppm',
                NEW.magnitude_ppm,
                NEW.magnitude_ppm
            )
            OR NOT mirror_demo_d02_json_integer_between(
                side_payload -> 'measured_signed_delta_ppm',
                expected_delta_ppm,
                expected_delta_ppm
            )
            OR NOT mirror_demo_d02_json_boolean(side_payload -> 'side_gate_passed')
            OR side_payload -> 'side_gate_passed' <> 'true'::jsonb
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
                  AND result_asset.byte_size =
                      (side_payload ->> 'result_asset_byte_size')::bigint
                  AND result_asset.mime_type = side_payload ->> 'result_asset_mime_type'
                  AND result_asset.width = (side_payload ->> 'result_asset_width')::integer
                  AND result_asset.height = (side_payload ->> 'result_asset_height')::integer
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
    IF bank_row.pair_manifest_digest IS DISTINCT FROM
           report_row.selected_pair_manifest_digest
        OR report_row.selected_pair_count <> 16
        OR report_row.selected_result_side_count <> 32
        OR jsonb_typeof(report_row.report_payload -> 'selected_pair_manifest') <>
           'array'
        OR jsonb_array_length(report_row.report_payload -> 'selected_pair_manifest') <> 16
        OR pair_count <> 16 OR side_count <> 32 OR source_count <> 4
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
            SELECT 1
            FROM jsonb_array_elements(
                report_row.report_payload -> 'selected_pair_manifest'
            ) WITH ORDINALITY AS selected_pair(value, ordinality)
            WHERE NOT mirror_demo_d02_json_integer_between(
                selected_pair.value -> 'selected_pair_ordinal',
                selected_pair.ordinality::integer,
                selected_pair.ordinality::integer
            ) OR (
                SELECT count(*)
                FROM demo_question_pairs pair_row
                WHERE pair_row.question_bank_id = authority_bank_id
                  AND pair_row.qa_payload ->> 'pair_screening_record_digest' =
                      selected_pair.value ->> 'pair_screening_record_digest'
                  AND pair_row.demo_synthetic_identity_id =
                      selected_pair.value ->> 'source_admission_event_id'
                  AND pair_row.dimension_key = selected_pair.value ->> 'dimension_key'
                  AND pair_row.magnitude_ppm::text =
                      selected_pair.value ->> 'magnitude_ppm'
                  AND (selected_pair.value ->> 'selected_dimension_slot')::integer =
                      CASE
                          WHEN pair_row.dimension_key =
                               report_row.selected_dimension_keys ->> 0 THEN 1
                          WHEN pair_row.dimension_key =
                               report_row.selected_dimension_keys ->> 1 THEN 2
                          ELSE 0
                      END
                  AND selected_pair.value -> 'source_ordinal' IS NOT DISTINCT FROM
                      pair_row.qa_payload -> 'pair_screening_record_payload' ->
                      'source_ordinal'
                  AND selected_pair.value -> 'priority_index' IS NOT DISTINCT FROM
                      pair_row.qa_payload -> 'pair_screening_record_payload' ->
                      'priority_index'
                  AND selected_pair.value ->> 'source_authority_key' =
                      pair_row.qa_payload -> 'pair_screening_record_payload' ->>
                      'source_authority_key'
                  AND selected_pair.value ->> 'pair_record_id' =
                      pair_row.qa_payload -> 'pair_screening_record_payload' ->>
                      'pair_record_id'
                  AND selected_pair.value ->> 'left_case_id' =
                      pair_row.qa_payload -> 'pair_screening_record_payload' ->
                      'left' ->> 'case_id'
                  AND selected_pair.value ->> 'left_result_asset_id' =
                      pair_row.left_asset_id
                  AND selected_pair.value ->> 'left_result_asset_sha256' =
                      pair_row.left_asset_sha256
                  AND selected_pair.value ->> 'left_asset_variant_id' =
                      pair_row.left_asset_variant_id
                  AND selected_pair.value ->> 'right_case_id' =
                      pair_row.qa_payload -> 'pair_screening_record_payload' ->
                      'right' ->> 'case_id'
                  AND selected_pair.value ->> 'right_result_asset_id' =
                      pair_row.right_asset_id
                  AND selected_pair.value ->> 'right_result_asset_sha256' =
                      pair_row.right_asset_sha256
                  AND selected_pair.value ->> 'right_asset_variant_id' =
                      pair_row.right_asset_variant_id
            ) <> 1
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
    op.execute(_D02_REPORT_V9_SQL)
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
    op.execute(
        "DROP FUNCTION mirror_demo_validate_d02_screening_report_v9(demo_pair_screening_reports)"
    )
    op.execute(
        "DROP FUNCTION mirror_demo_validate_d02_report_outcomes_v9(demo_pair_screening_reports)"
    )
    op.execute("DROP FUNCTION mirror_demo_validate_d02_pairs_v9(demo_pair_screening_reports)")
    op.execute(
        "DROP FUNCTION mirror_demo_validate_d02_pair_side_v9("
        "demo_pair_screening_reports, jsonb, integer, text)"
    )
    op.execute("DROP FUNCTION mirror_demo_validate_d02_images_v9(demo_pair_screening_reports)")
    op.execute(
        "DROP FUNCTION mirror_demo_validate_d02_measurements_v9(demo_pair_screening_reports)"
    )
    op.drop_table("demo_pair_screening_reports")
    _downgrade_identity_authority()
    op.execute(_LEGACY_GUARD_SQL)
    op.execute("DROP FUNCTION mirror_demo_d02_dimension_array_valid(jsonb, integer)")
    op.execute("DROP FUNCTION mirror_demo_d02_quality_ppm(text)")
    op.execute("DROP FUNCTION mirror_demo_round_half_even_ppm(text)")
    op.execute("DROP FUNCTION mirror_demo_d02_hamming64(text, text)")
    op.execute("DROP FUNCTION mirror_demo_d02_require_record(jsonb, text, text[], text)")
    op.execute("DROP FUNCTION mirror_demo_d02_record_digest_matches(jsonb, text, text)")
    op.execute("DROP FUNCTION mirror_demo_d02_json_fixed18(jsonb, boolean)")
    op.execute("DROP FUNCTION mirror_demo_d02_json_integer_between(jsonb, bigint, bigint)")
    op.execute("DROP FUNCTION mirror_demo_d02_json_boolean(jsonb)")
    op.execute("DROP FUNCTION mirror_demo_d02_json_string_equals(jsonb, text)")
    op.execute("DROP FUNCTION mirror_demo_d02_json_string_matches(jsonb, text)")
    op.execute("DROP FUNCTION mirror_demo_d02_expected_lock_policy_digest()")
    op.execute("DROP FUNCTION mirror_demo_d02_expected_screening_policy_digest()")
    op.execute("DROP FUNCTION mirror_demo_jsonb_exact_keys(jsonb, text[])")
    op.execute("DROP FUNCTION mirror_demo_local_source_authority_key(text, text, text, text)")
    op.execute("DROP FUNCTION mirror_demo_formal_source_authority_key(text)")
