"""Upgrade Demo D02 measurement-quality persistence authority.

Revision ID: demo_0005_d02_quality_auth
Revises: demo_0004_d09_episode_prov
Create Date: 2026-08-24

PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
"""

from collections.abc import Sequence

from alembic import op

revision: str = "demo_0005_d02_quality_auth"
down_revision: str | None = "demo_0004_d09_episode_prov"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROTOTYPE_MIGRATION = True
FORMAL_PHASE_AUTHORITY = False
DIRECT_MAINLINE_CHERRY_PICK = "FORBIDDEN"


_D02_TABLE_LOCK_SQL = r"""
LOCK TABLE demo_synthetic_identities IN ACCESS EXCLUSIVE MODE;
LOCK TABLE demo_pair_screening_reports IN ACCESS EXCLUSIVE MODE;
LOCK TABLE demo_question_banks IN ACCESS EXCLUSIVE MODE;
LOCK TABLE demo_question_pairs IN ACCESS EXCLUSIVE MODE;
"""


_D02_V9_GUARD_RESTORE_SQL = r"""
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


_D02_V10_GUARD_SQL = _D02_V9_GUARD_RESTORE_SQL.replace(
    "AND NEW.schema_version = 'mirror.demo/DemoSyntheticIdentity/v2' THEN",
    "AND NEW.schema_version IN (\n"
    "            'mirror.demo/DemoSyntheticIdentity/v2',\n"
    "            'mirror.demo/DemoSyntheticIdentity/v3'\n"
    "        ) THEN",
    1,
)


_D02_V10_QUALITY_HELPERS_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_d02_validate_observation_v10(
    observation jsonb,
    expected_role text
)
RETURNS void
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
DECLARE
    entry jsonb;
    subject jsonb;
    entry_index integer;
    expected_dimension text;
    dimensions constant text[] := ARRAY[
        'cheekbone_width','chin_height','eye_spacing',
        'jaw_width','mouth_width','nose_width'
    ];
BEGIN
    IF NOT mirror_demo_jsonb_exact_keys(
        observation,
        ARRAY[
            'schema_version','observation_role','subject','canonical_output_digest',
            'landmark_digest','runtime_manifest_digest','vision_model_manifest_digest',
            'topology_digest','measurement_config_digest',
            'measurement_quality_config_digest',
            'measurement_quality_manifest_content_digest','confidence_kind',
            'ordered_measurements','measurement_observation_digest'
        ]
    ) OR observation ->> 'schema_version' <>
            'mirror.demo/D02MeasurementObservation/v1'
        OR observation ->> 'observation_role' <> expected_role
        OR observation ->> 'runtime_manifest_digest' <>
            '6d739c2e269128ea7bc09358203aa7efe0714484b1a216a9f401353a243135ed'
        OR observation ->> 'vision_model_manifest_digest' <>
            '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'
        OR observation ->> 'topology_digest' <>
            '85eea84eef15dd963e06382d6e61f7357029d9901acc935731ecaa7eab856b63'
        OR observation ->> 'measurement_config_digest' <>
            'ab5f745641a6f4539a8010fe32dda82b6c1066a8cb97d36ae17de737b901e8d3'
        OR observation ->> 'measurement_quality_config_digest' <>
            'ed52feca45f18b976e34d419da117d777d540978b9552c3e423a0d0c543e8f47'
        OR observation ->> 'measurement_quality_manifest_content_digest' <>
            'ed11f53e8e75428c396fb2b6711bd17fa996d49f8c4f5c9cdfebcfb36b42ed74'
        OR observation ->> 'confidence_kind' <>
            'DEMO_GEOMETRIC_OBSERVABILITY_PROXY_NOT_MODEL_CONFIDENCE'
        OR NOT mirror_demo_d02_json_string_matches(
            observation -> 'canonical_output_digest', '^[0-9a-f]{64}$'
        )
        OR NOT mirror_demo_d02_json_string_matches(
            observation -> 'landmark_digest', '^[0-9a-f]{64}$'
        )
        OR jsonb_typeof(observation -> 'ordered_measurements') <> 'array'
        OR jsonb_array_length(observation -> 'ordered_measurements') <> 6
        OR observation ->> 'measurement_observation_digest' IS DISTINCT FROM
            mirror_demo_digest(
                'mirror.demo/D02MeasurementObservation/v1',
                observation - 'schema_version' - 'measurement_observation_digest'
            ) THEN
        RAISE EXCEPTION 'D02 v10 observation envelope or digest is invalid';
    END IF;

    subject := observation -> 'subject';
    IF expected_role = 'SOURCE' THEN
        IF NOT mirror_demo_jsonb_exact_keys(
            subject,
            ARRAY['schema_version','source_output_id','source_asset_id','source_asset_sha256']
        ) OR subject ->> 'schema_version' <>
                'mirror.demo/D02SourceObservationSubject/v1'
            OR NOT mirror_demo_d02_json_string_matches(
                subject -> 'source_output_id', '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                subject -> 'source_asset_id', '^[0-9a-f]{32}$'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                subject -> 'source_asset_sha256', '^[0-9a-f]{64}$'
            ) THEN
            RAISE EXCEPTION 'D02 v10 source observation subject is invalid';
        END IF;
    ELSIF expected_role = 'RESULT' THEN
        IF NOT mirror_demo_jsonb_exact_keys(
            subject,
            ARRAY[
                'schema_version','case_id','case_specification_digest',
                'result_output_id','result_sha256'
            ]
        ) OR subject ->> 'schema_version' <>
                'mirror.demo/D02ResultObservationSubject/v1'
            OR NOT mirror_demo_d02_json_string_matches(
                subject -> 'case_id', '^[0-9a-f]{32}$'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                subject -> 'case_specification_digest', '^[0-9a-f]{64}$'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                subject -> 'result_output_id', '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                subject -> 'result_sha256', '^[0-9a-f]{64}$'
            ) THEN
            RAISE EXCEPTION 'D02 v10 result observation subject is invalid';
        END IF;
    ELSE
        RAISE EXCEPTION 'D02 v10 observation role is invalid';
    END IF;

    FOR entry_index IN 0..5 LOOP
        entry := observation -> 'ordered_measurements' -> entry_index;
        expected_dimension := dimensions[entry_index + 1];
        IF NOT mirror_demo_jsonb_exact_keys(
            entry,
            ARRAY[
                'schema_version','dimension_key','support_state','raw_value_fixed18',
                'observability_state','raw_observability_fixed18','unsupported_reason'
            ]
        ) OR entry ->> 'schema_version' <>
                'mirror.demo/D02MeasurementObservationEntry/v1'
            OR entry ->> 'dimension_key' <> expected_dimension THEN
            RAISE EXCEPTION 'D02 v10 observation entry shape or order is invalid';
        END IF;
        IF entry ->> 'support_state' = 'SUPPORTED' THEN
            IF NOT mirror_demo_d02_json_fixed18(entry -> 'raw_value_fixed18')
                OR NOT mirror_demo_d02_json_fixed18(
                    entry -> 'raw_observability_fixed18'
                )
                OR (entry ->> 'raw_observability_fixed18')::numeric <
                    0.000001000000000000
                OR entry ->> 'observability_state' <> 'COMPUTED'
                OR entry -> 'unsupported_reason' <> 'null'::jsonb THEN
                RAISE EXCEPTION 'D02 v10 supported observation union is invalid';
            END IF;
        ELSIF entry ->> 'support_state' = 'UNSUPPORTED' THEN
            IF entry -> 'raw_value_fixed18' <> 'null'::jsonb
                OR entry ->> 'unsupported_reason' NOT IN (
                    'RUNTIME_UNSUPPORTED','MISSING_MEASUREMENT',
                    'OUT_OF_BOUNDS','LOW_CONFIDENCE'
                )
                OR (
                    entry ->> 'unsupported_reason' = 'LOW_CONFIDENCE'
                    AND (
                        entry ->> 'observability_state' <> 'COMPUTED'
                        OR NOT mirror_demo_d02_json_fixed18(
                            entry -> 'raw_observability_fixed18'
                        )
                        OR (entry ->> 'raw_observability_fixed18')::numeric >=
                            0.000001000000000000
                    )
                )
                OR (
                    entry ->> 'unsupported_reason' <> 'LOW_CONFIDENCE'
                    AND (
                        entry ->> 'observability_state' <> 'NOT_COMPUTABLE'
                        OR entry -> 'raw_observability_fixed18' <> 'null'::jsonb
                    )
                ) THEN
                RAISE EXCEPTION 'D02 v10 unsupported observation union is invalid';
            END IF;
        ELSE
            RAISE EXCEPTION 'D02 v10 observation support state is invalid';
        END IF;
    END LOOP;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_d02_validate_source_certificate_v10(
    certificate jsonb,
    observation jsonb
)
RETURNS void
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
DECLARE
    binding jsonb;
    binding_index integer;
    first_binding jsonb;
BEGIN
    IF NOT mirror_demo_jsonb_exact_keys(
        certificate,
        ARRAY[
            'schema_version','subject','runtime_manifest_digest',
            'vision_model_manifest_digest','topology_digest','measurement_config_digest',
            'measurement_quality_config_digest',
            'measurement_quality_manifest_content_digest','reliability_kind',
            'repeat_count','ordered_repeat_bindings','certification_state',
            'certified_raw_reliability_fixed18','certified_reliability_ppm',
            'source_repeat_certification_digest'
        ]
    ) OR certificate ->> 'schema_version' <>
            'mirror.demo/D02SourceRepeatDeterminismCertification/v1'
        OR certificate -> 'subject' IS DISTINCT FROM observation -> 'subject'
        OR certificate ->> 'runtime_manifest_digest' <>
            '6d739c2e269128ea7bc09358203aa7efe0714484b1a216a9f401353a243135ed'
        OR certificate ->> 'vision_model_manifest_digest' <>
            '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'
        OR certificate ->> 'topology_digest' <>
            '85eea84eef15dd963e06382d6e61f7357029d9901acc935731ecaa7eab856b63'
        OR certificate ->> 'measurement_config_digest' <>
            'ab5f745641a6f4539a8010fe32dda82b6c1066a8cb97d36ae17de737b901e8d3'
        OR certificate ->> 'measurement_quality_config_digest' <>
            'ed52feca45f18b976e34d419da117d777d540978b9552c3e423a0d0c543e8f47'
        OR certificate ->> 'measurement_quality_manifest_content_digest' <>
            'ed11f53e8e75428c396fb2b6711bd17fa996d49f8c4f5c9cdfebcfb36b42ed74'
        OR certificate ->> 'reliability_kind' <>
            'EXACT_REPEAT_DETERMINISM_CERTIFICATION_NOT_MODEL_RELIABILITY'
        OR NOT mirror_demo_d02_json_integer_between(certificate -> 'repeat_count', 3, 3)
        OR certificate ->> 'certification_state' <> 'CERTIFIED_EXACT_REPEAT'
        OR certificate ->> 'certified_raw_reliability_fixed18' <>
            '1.000000000000000000'
        OR NOT mirror_demo_d02_json_integer_between(
            certificate -> 'certified_reliability_ppm', 1000000, 1000000
        )
        OR jsonb_typeof(certificate -> 'ordered_repeat_bindings') <> 'array'
        OR jsonb_array_length(certificate -> 'ordered_repeat_bindings') <> 3
        OR certificate ->> 'source_repeat_certification_digest' IS DISTINCT FROM
            mirror_demo_digest(
                'mirror.demo/D02SourceRepeatDeterminismCertification/v1',
                certificate - 'schema_version' - 'source_repeat_certification_digest'
            ) THEN
        RAISE EXCEPTION 'D02 v10 source repeat certificate is invalid';
    END IF;
    first_binding := certificate -> 'ordered_repeat_bindings' -> 0;
    FOR binding_index IN 0..2 LOOP
        binding := certificate -> 'ordered_repeat_bindings' -> binding_index;
        IF NOT mirror_demo_jsonb_exact_keys(
            binding,
            ARRAY[
                'repeat_index','execution_receipt_digest','canonical_output_digest',
                'landmark_digest','measurement_observation_digest','face_count',
                'landmark_count','coordinates_finite','coordinates_in_bounds',
                'repeat_gate_passed'
            ]
        ) OR NOT mirror_demo_d02_json_integer_between(
                binding -> 'repeat_index', binding_index + 1, binding_index + 1
            )
            OR NOT mirror_demo_d02_json_integer_between(binding -> 'face_count', 1, 1)
            OR NOT mirror_demo_d02_json_integer_between(
                binding -> 'landmark_count', 478, 478
            )
            OR binding -> 'coordinates_finite' <> 'true'::jsonb
            OR binding -> 'coordinates_in_bounds' <> 'true'::jsonb
            OR binding -> 'repeat_gate_passed' <> 'true'::jsonb
            OR EXISTS (
                SELECT 1
                FROM unnest(ARRAY[
                    'execution_receipt_digest','canonical_output_digest',
                    'landmark_digest','measurement_observation_digest'
                ]) AS digest_key
                WHERE NOT mirror_demo_d02_json_string_matches(
                    binding -> digest_key, '^[0-9a-f]{64}$'
                )
            )
            OR binding ->> 'canonical_output_digest' <>
                observation ->> 'canonical_output_digest'
            OR binding ->> 'landmark_digest' <> observation ->> 'landmark_digest'
            OR binding ->> 'measurement_observation_digest' <>
                observation ->> 'measurement_observation_digest'
            OR binding ->> 'canonical_output_digest' <>
                first_binding ->> 'canonical_output_digest'
            OR binding ->> 'landmark_digest' <> first_binding ->> 'landmark_digest'
            OR binding ->> 'measurement_observation_digest' <>
                first_binding ->> 'measurement_observation_digest' THEN
            RAISE EXCEPTION 'D02 v10 source repeat binding is invalid';
        END IF;
    END LOOP;
END;
$function$;
"""


_D02_V10_IDENTITY_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_local_snapshot_v10(
    authority_row demo_synthetic_identities
)
RETURNS void
LANGUAGE plpgsql
AS $function$
DECLARE
    facts jsonb := authority_row.source_fact_snapshot;
    raw_authority jsonb := facts -> 'raw_measurement_authority';
    projection jsonb := facts -> 'source_measurement_projection';
    observation jsonb := facts -> 'source_measurement_observation';
    certificate jsonb := facts -> 'source_repeat_certification';
    raw_entry jsonb;
    projection_entry jsonb;
    observation_entry jsonb;
    asset_row assets%ROWTYPE;
    entry_index integer;
    expected_dimension text;
    dimensions constant text[] := ARRAY[
        'cheekbone_width','chin_height','eye_spacing',
        'jaw_width','mouth_width','nose_width'
    ];
BEGIN
    IF NOT mirror_demo_jsonb_exact_keys(
        facts,
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
            'dimension_authority_manifest_content_digest',
            'source_measurement_observation','source_measurement_observation_digest',
            'source_repeat_certification','source_repeat_certification_digest'
        ]
    ) OR NOT mirror_demo_jsonb_exact_keys(
        raw_authority,
        ARRAY[
            'measurement_version','decimal_serialization_version',
            'source_p2_candidate_manifest_content_digest',
            'dimension_authority_manifest_content_digest','measurement_config_digest',
            'measurement_quality_config_digest',
            'measurement_quality_manifest_content_digest','confidence_kind',
            'reliability_kind','runtime_manifest_digest','vision_model_manifest_digest',
            'topology_digest','source_repeat_certification_digest','ordered_entries'
        ]
    ) OR NOT mirror_demo_jsonb_exact_keys(
        projection,
        ARRAY[
            'measurement_version','measurement_projection_version',
            'measurement_quantization_version',
            'source_p2_candidate_manifest_content_digest',
            'dimension_authority_manifest_content_digest','measurement_config_digest',
            'measurement_quality_config_digest',
            'measurement_quality_manifest_content_digest','confidence_kind',
            'reliability_kind','runtime_manifest_digest','vision_model_manifest_digest',
            'topology_digest','source_repeat_certification_digest','ordered_entries'
        ]
    ) THEN
        RAISE EXCEPTION 'D02 v10 facts or morphology envelope keys are invalid';
    END IF;

    PERFORM mirror_demo_d02_validate_observation_v10(observation, 'SOURCE');
    PERFORM mirror_demo_d02_validate_source_certificate_v10(certificate, observation);

    IF facts ->> 'source_measurement_observation_digest' <>
            observation ->> 'measurement_observation_digest'
        OR facts ->> 'source_measurement_digest' <>
            observation ->> 'measurement_observation_digest'
        OR facts ->> 'source_measurement_digest' =
            facts ->> 'raw_measurement_authority_digest'
        OR facts ->> 'source_landmark_digest' <>
            observation ->> 'landmark_digest'
        OR facts ->> 'source_repeat_certification_digest' <>
            certificate ->> 'source_repeat_certification_digest'
        OR raw_authority ->> 'measurement_version' <>
            'demo-d02-landmark-distance-v1'
        OR raw_authority ->> 'decimal_serialization_version' <>
            'fixed18-round-half-even-v1'
        OR projection ->> 'measurement_projection_version' <>
            'demo-d02-morphology-projection-v2'
        OR projection ->> 'measurement_quantization_version' <>
            'fixed18-to-ppm-round-half-even-v1'
        OR projection ->> 'measurement_version' <>
            raw_authority ->> 'measurement_version'
        OR facts ->> 'measurement_projection_version' <>
            projection ->> 'measurement_projection_version'
        OR facts ->> 'measurement_quantization_version' <>
            projection ->> 'measurement_quantization_version'
        OR raw_authority ->> 'measurement_config_digest' <>
            'ab5f745641a6f4539a8010fe32dda82b6c1066a8cb97d36ae17de737b901e8d3'
        OR projection ->> 'measurement_config_digest' <>
            raw_authority ->> 'measurement_config_digest'
        OR raw_authority ->> 'measurement_quality_config_digest' <>
            'ed52feca45f18b976e34d419da117d777d540978b9552c3e423a0d0c543e8f47'
        OR projection ->> 'measurement_quality_config_digest' <>
            raw_authority ->> 'measurement_quality_config_digest'
        OR raw_authority ->> 'measurement_quality_manifest_content_digest' <>
            'ed11f53e8e75428c396fb2b6711bd17fa996d49f8c4f5c9cdfebcfb36b42ed74'
        OR projection ->> 'measurement_quality_manifest_content_digest' <>
            raw_authority ->> 'measurement_quality_manifest_content_digest'
        OR raw_authority ->> 'confidence_kind' <>
            'DEMO_GEOMETRIC_OBSERVABILITY_PROXY_NOT_MODEL_CONFIDENCE'
        OR projection ->> 'confidence_kind' <> raw_authority ->> 'confidence_kind'
        OR raw_authority ->> 'reliability_kind' <>
            'EXACT_REPEAT_DETERMINISM_CERTIFICATION_NOT_MODEL_RELIABILITY'
        OR projection ->> 'reliability_kind' <> raw_authority ->> 'reliability_kind'
        OR raw_authority ->> 'runtime_manifest_digest' <>
            '6d739c2e269128ea7bc09358203aa7efe0714484b1a216a9f401353a243135ed'
        OR projection ->> 'runtime_manifest_digest' <>
            raw_authority ->> 'runtime_manifest_digest'
        OR raw_authority ->> 'vision_model_manifest_digest' <>
            '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'
        OR projection ->> 'vision_model_manifest_digest' <>
            raw_authority ->> 'vision_model_manifest_digest'
        OR raw_authority ->> 'topology_digest' <>
            '85eea84eef15dd963e06382d6e61f7357029d9901acc935731ecaa7eab856b63'
        OR projection ->> 'topology_digest' <> raw_authority ->> 'topology_digest'
        OR raw_authority ->> 'source_repeat_certification_digest' <>
            certificate ->> 'source_repeat_certification_digest'
        OR projection ->> 'source_repeat_certification_digest' <>
            certificate ->> 'source_repeat_certification_digest'
        OR NOT mirror_demo_d02_json_string_matches(
            raw_authority -> 'source_p2_candidate_manifest_content_digest',
            '^[0-9a-f]{64}$'
        )
        OR raw_authority ->> 'source_p2_candidate_manifest_content_digest' <>
            'eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4'
        OR facts ->> 'source_p2_candidate_manifest_content_digest' <>
            raw_authority ->> 'source_p2_candidate_manifest_content_digest'
        OR projection ->> 'source_p2_candidate_manifest_content_digest' <>
            raw_authority ->> 'source_p2_candidate_manifest_content_digest'
        OR NOT mirror_demo_d02_json_string_matches(
            raw_authority -> 'dimension_authority_manifest_content_digest',
            '^[0-9a-f]{64}$'
        )
        OR raw_authority ->> 'dimension_authority_manifest_content_digest' <>
            'd4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a'
        OR facts ->> 'dimension_authority_manifest_content_digest' <>
            raw_authority ->> 'dimension_authority_manifest_content_digest'
        OR projection ->> 'dimension_authority_manifest_content_digest' <>
            raw_authority ->> 'dimension_authority_manifest_content_digest'
        OR jsonb_typeof(raw_authority -> 'ordered_entries') <> 'array'
        OR jsonb_array_length(raw_authority -> 'ordered_entries') <> 6
        OR jsonb_typeof(projection -> 'ordered_entries') <> 'array'
        OR jsonb_array_length(projection -> 'ordered_entries') <> 6
        OR jsonb_typeof(facts -> 'source_asset_byte_size') <> 'number'
        OR jsonb_typeof(facts -> 'source_asset_width') <> 'number'
        OR jsonb_typeof(facts -> 'source_asset_height') <> 'number'
        OR NOT mirror_demo_d02_json_integer_between(
            facts -> 'source_asset_byte_size', 1, 9223372036854775807
        )
        OR NOT mirror_demo_d02_json_integer_between(
            facts -> 'source_asset_width', 1, 2147483647
        )
        OR NOT mirror_demo_d02_json_integer_between(
            facts -> 'source_asset_height', 1, 2147483647
        )
        OR facts ->> 'source_asset_mime_type' <> 'image/jpeg' THEN
        RAISE EXCEPTION 'D02 v10 facts quality authority binding is invalid';
    END IF;

    FOR entry_index IN 0..5 LOOP
        raw_entry := raw_authority -> 'ordered_entries' -> entry_index;
        projection_entry := projection -> 'ordered_entries' -> entry_index;
        observation_entry := observation -> 'ordered_measurements' -> entry_index;
        expected_dimension := dimensions[entry_index + 1];
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
            OR observation_entry ->> 'dimension_key' <> expected_dimension
            OR raw_entry ->> 'support_state' <> observation_entry ->> 'support_state'
            OR projection_entry ->> 'support_state' <> raw_entry ->> 'support_state'
            OR projection_entry ->> 'unit' <> 'FACE_HEIGHT_PPM' THEN
            RAISE EXCEPTION 'D02 v10 morphology entry shape or order is invalid';
        END IF;
        IF raw_entry ->> 'support_state' = 'SUPPORTED' THEN
            IF raw_entry ->> 'raw_value_fixed18' <>
                    observation_entry ->> 'raw_value_fixed18'
                OR raw_entry ->> 'raw_confidence_fixed18' <>
                    observation_entry ->> 'raw_observability_fixed18'
                OR raw_entry ->> 'raw_reliability_fixed18' <>
                    '1.000000000000000000'
                OR raw_entry -> 'unsupported_reason' <> 'null'::jsonb
                OR projection_entry -> 'unsupported_reason' <> 'null'::jsonb
                OR NOT mirror_demo_d02_json_integer_between(
                    projection_entry -> 'value_ppm', 1, 1000000
                )
                OR NOT mirror_demo_d02_json_integer_between(
                    projection_entry -> 'confidence_ppm', 1, 1000000
                )
                OR NOT mirror_demo_d02_json_integer_between(
                    projection_entry -> 'reliability_ppm', 1000000, 1000000
                )
                OR (projection_entry ->> 'value_ppm')::integer <>
                    mirror_demo_round_half_even_ppm(raw_entry ->> 'raw_value_fixed18')
                OR (projection_entry ->> 'confidence_ppm')::integer <>
                    mirror_demo_round_half_even_ppm(
                        raw_entry ->> 'raw_confidence_fixed18'
                    ) THEN
                RAISE EXCEPTION 'D02 v10 supported morphology projection is invalid';
            END IF;
        ELSE
            RAISE EXCEPTION
                'D02 v10 identity import requires all six supported dimensions';
        END IF;
    END LOOP;

    SELECT * INTO asset_row
    FROM assets
    WHERE id = authority_row.formal_canonical_asset_id;
    IF NOT FOUND
        OR asset_row.owner_user_id IS NOT NULL
        OR asset_row.asset_role <> 'synthetic'
        OR asset_row.internal_purpose <> 'synthetic_dataset'
        OR NOT asset_row.synthetic
        OR asset_row.sha256 <> authority_row.formal_canonical_asset_sha256
        OR asset_row.sha256 <> facts ->> 'source_asset_sha256'
        OR asset_row.byte_size <> (facts ->> 'source_asset_byte_size')::bigint
        OR asset_row.mime_type <> facts ->> 'source_asset_mime_type'
        OR asset_row.width <> (facts ->> 'source_asset_width')::integer
        OR asset_row.height <> (facts ->> 'source_asset_height')::integer THEN
        RAISE EXCEPTION 'D02 v10 local source Asset authority mismatch';
    END IF;

    IF authority_row.formal_canonical_asset_id IS DISTINCT FROM substring(
            mirror_demo_digest(
                'mirror.demo/D02ImportedAssetId/v1',
                jsonb_build_object(
                    'asset_role', 'synthetic',
                    'semantic_role', 'SOURCE',
                    'sha256', facts ->> 'source_asset_sha256',
                    'byte_size', (facts ->> 'source_asset_byte_size')::bigint,
                    'mime_type', facts ->> 'source_asset_mime_type',
                    'width', (facts ->> 'source_asset_width')::integer,
                    'height', (facts ->> 'source_asset_height')::integer
                )
            ) FROM 1 FOR 32
        )
        OR observation -> 'subject' ->> 'source_output_id' <>
            authority_row.source_output_id
        OR observation -> 'subject' ->> 'source_asset_id' <>
            authority_row.formal_canonical_asset_id
        OR observation -> 'subject' ->> 'source_asset_sha256' <>
            authority_row.formal_canonical_asset_sha256
        OR authority_row.source_output_id <> facts ->> 'source_output_id'
        OR authority_row.source_receipt_digest <> facts ->> 'source_receipt_digest'
        OR authority_row.source_authority_digest <> facts ->> 'source_authority_digest'
        OR authority_row.source_qa_snapshot_digest <> facts ->> 'source_qa_snapshot_digest'
        OR authority_row.source_landmark_digest <> facts ->> 'source_landmark_digest'
        OR authority_row.source_measurement_digest <> facts ->> 'source_measurement_digest'
        OR authority_row.source_provenance_digest <> facts ->> 'source_provenance_digest'
        OR authority_row.source_measurement_projection IS DISTINCT FROM projection
        OR authority_row.source_measurement_projection_digest <>
            facts ->> 'source_measurement_projection_digest'
        OR authority_row.original_formal_identity_id_status <>
            facts ->> 'original_formal_identity_id_status'
        OR authority_row.adult_synthetic_attested IS NOT TRUE
        OR facts -> 'adult_synthetic_attested' <> 'true'::jsonb
        OR authority_row.source_fact_snapshot_digest IS DISTINCT FROM
            mirror_demo_digest('mirror.demo/RecoveredSyntheticIdentityFacts/v3', facts)
        OR facts ->> 'raw_measurement_authority_digest' IS DISTINCT FROM
            mirror_demo_digest(
                'mirror.demo/D02RawMeasurementAuthority/v2', raw_authority
            )
        OR facts ->> 'source_measurement_projection_digest' IS DISTINCT FROM
            mirror_demo_digest('mirror.demo/D02MorphologyProjection/v2', projection)
        OR authority_row.import_config_digest <>
            '3cb5043028bec1c25e95822432db69a84b1eae9af3788201fafffe53f40acec2'
        OR authority_row.importer_version <> 'demo-d02-identity-importer-v3'
        OR authority_row.original_formal_identity_id_status <>
            'UNKNOWN_REDACTED_NOT_RECOVERED' THEN
        RAISE EXCEPTION 'D02 v10 identity/facts canonical equality is invalid';
    END IF;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_synthetic_identity_v10()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    expected_key text;
    expected_id text;
    expected_canonical jsonb;
    previous_admission demo_synthetic_identities%ROWTYPE;
    has_previous boolean;
BEGIN
    IF NEW.schema_version <> 'mirror.demo/DemoSyntheticIdentity/v3'
        OR NEW.formal_synthetic_identity_id IS NOT NULL
        OR NEW.formal_accepted_qa_run_id IS NOT NULL
        OR NEW.formal_accepted_qa_snapshot_digest IS NOT NULL THEN
        RAISE EXCEPTION 'D02 v10 identity must be a complete local v3 authority';
    END IF;
    expected_key := mirror_demo_local_source_authority_key(
        NEW.source_output_id,
        NEW.formal_canonical_asset_id,
        NEW.formal_canonical_asset_sha256,
        NEW.source_receipt_digest
    );
    IF NEW.canonical_payload ->> 'source_authority_kind' <>
            'DEMO_LOCAL_IMPORTED_COPY'
        OR NEW.canonical_payload ->> 'source_authority_key' <> expected_key THEN
        RAISE EXCEPTION 'D02 v10 source authority key does not replay';
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
        IF NEW.admission_sequence <> 1 OR NEW.admission_action <> 'ADMIT'
            OR NEW.supersedes_id IS NOT NULL THEN
            RAISE EXCEPTION 'First D02 v10 source event must be ADMIT';
        END IF;
    ELSIF previous_admission.schema_version <>
            'mirror.demo/DemoSyntheticIdentity/v3'
        OR NEW.admission_sequence <> previous_admission.admission_sequence + 1
        OR NEW.supersedes_id IS DISTINCT FROM previous_admission.id
        OR NEW.admission_action = previous_admission.admission_action THEN
        RAISE EXCEPTION 'D02 v10 source admission chain is invalid or mixed-version';
    END IF;

    PERFORM mirror_demo_validate_d02_local_snapshot_v10(NEW);
    IF has_previous AND (
        NEW.formal_canonical_asset_id IS DISTINCT FROM
            previous_admission.formal_canonical_asset_id
        OR NEW.formal_canonical_asset_sha256 IS DISTINCT FROM
            previous_admission.formal_canonical_asset_sha256
        OR NEW.source_output_id IS DISTINCT FROM previous_admission.source_output_id
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
        OR NEW.source_fact_snapshot IS DISTINCT FROM
            previous_admission.source_fact_snapshot
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
        OR NEW.import_config_digest IS DISTINCT FROM
            previous_admission.import_config_digest
    ) THEN
        RAISE EXCEPTION 'D02 v10 ADMIT/REVOKE evidence copy differs';
    END IF;

    expected_canonical := to_jsonb(NEW) - ARRAY[
        'id','schema_version','canonical_payload','content_digest','created_at',
        'source_authority_kind','source_authority_key'
    ];
    expected_canonical := expected_canonical || jsonb_build_object(
        'source_authority_kind', 'DEMO_LOCAL_IMPORTED_COPY',
        'source_authority_key', expected_key
    );
    IF NEW.canonical_payload IS DISTINCT FROM expected_canonical
        OR NEW.content_digest IS DISTINCT FROM mirror_demo_digest(
            NEW.schema_version, NEW.canonical_payload
        ) THEN
        RAISE EXCEPTION 'D02 v10 identity canonical payload or digest mismatch';
    END IF;
    expected_id := substring(
        mirror_demo_digest(
            'mirror.demo/DemoSyntheticIdentityAdmissionEventId/v2',
            jsonb_build_object(
                'source_authority_kind', 'DEMO_LOCAL_IMPORTED_COPY',
                'source_authority_key', expected_key,
                'admission_sequence', NEW.admission_sequence,
                'admission_action', NEW.admission_action,
                'supersedes_id', NEW.supersedes_id,
                'admission_config_digest', NEW.admission_config_digest,
                'canonical_payload_digest', NEW.content_digest
            )
        ) FROM 1 FOR 32
    );
    IF NEW.id <> expected_id THEN
        RAISE EXCEPTION 'D02 v10 identity event ID does not replay';
    END IF;
    RETURN NEW;
END;
$function$;
"""


_D02_V10_REPORT_HELPERS_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_d02_validate_result_certificate_v10(
    certificate jsonb,
    records jsonb
)
RETURNS void
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
DECLARE
    binding jsonb;
    record jsonb;
    binding_index integer;
    first_binding jsonb;
BEGIN
    IF NOT mirror_demo_jsonb_exact_keys(
        certificate,
        ARRAY[
            'schema_version','subject','runtime_manifest_digest',
            'vision_model_manifest_digest','topology_digest','measurement_config_digest',
            'measurement_quality_config_digest',
            'measurement_quality_manifest_content_digest','reliability_kind',
            'repeat_count','ordered_repeat_bindings','certification_state',
            'certified_raw_reliability_fixed18','certified_reliability_ppm',
            'result_repeat_certification_digest'
        ]
    ) OR certificate ->> 'schema_version' <>
            'mirror.demo/D02ResultRepeatDeterminismCertification/v1'
        OR certificate ->> 'runtime_manifest_digest' <>
            '6d739c2e269128ea7bc09358203aa7efe0714484b1a216a9f401353a243135ed'
        OR certificate ->> 'vision_model_manifest_digest' <>
            '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'
        OR certificate ->> 'topology_digest' <>
            '85eea84eef15dd963e06382d6e61f7357029d9901acc935731ecaa7eab856b63'
        OR certificate ->> 'measurement_config_digest' <>
            'ab5f745641a6f4539a8010fe32dda82b6c1066a8cb97d36ae17de737b901e8d3'
        OR certificate ->> 'measurement_quality_config_digest' <>
            'ed52feca45f18b976e34d419da117d777d540978b9552c3e423a0d0c543e8f47'
        OR certificate ->> 'measurement_quality_manifest_content_digest' <>
            'ed11f53e8e75428c396fb2b6711bd17fa996d49f8c4f5c9cdfebcfb36b42ed74'
        OR certificate ->> 'reliability_kind' <>
            'EXACT_REPEAT_DETERMINISM_CERTIFICATION_NOT_MODEL_RELIABILITY'
        OR NOT mirror_demo_d02_json_integer_between(certificate -> 'repeat_count', 3, 3)
        OR certificate ->> 'certification_state' <> 'CERTIFIED_EXACT_REPEAT'
        OR certificate ->> 'certified_raw_reliability_fixed18' <>
            '1.000000000000000000'
        OR NOT mirror_demo_d02_json_integer_between(
            certificate -> 'certified_reliability_ppm', 1000000, 1000000
        )
        OR jsonb_typeof(certificate -> 'ordered_repeat_bindings') <> 'array'
        OR jsonb_array_length(certificate -> 'ordered_repeat_bindings') <> 3
        OR jsonb_typeof(records) <> 'array'
        OR jsonb_array_length(records) <> 3
        OR certificate ->> 'result_repeat_certification_digest' IS DISTINCT FROM
            mirror_demo_digest(
                'mirror.demo/D02ResultRepeatDeterminismCertification/v1',
                certificate - 'schema_version' - 'result_repeat_certification_digest'
            ) THEN
        RAISE EXCEPTION 'D02 v10 result repeat certificate is invalid';
    END IF;

    first_binding := certificate -> 'ordered_repeat_bindings' -> 0;
    FOR binding_index IN 0..2 LOOP
        binding := certificate -> 'ordered_repeat_bindings' -> binding_index;
        record := records -> binding_index;
        IF NOT mirror_demo_jsonb_exact_keys(
            binding,
            ARRAY[
                'repeat_index','result_m3_record_id','execution_receipt_digest',
                'canonical_output_digest','landmark_digest',
                'measurement_observation_digest','face_count','landmark_count',
                'coordinates_finite','coordinates_in_bounds','observation_state',
                'repeat_gate_passed'
            ]
        ) OR NOT mirror_demo_d02_json_integer_between(
                binding -> 'repeat_index', binding_index + 1, binding_index + 1
            )
            OR NOT mirror_demo_d02_json_string_matches(
                binding -> 'result_m3_record_id', '^[0-9a-f]{32}$'
            )
            OR NOT mirror_demo_d02_json_integer_between(binding -> 'face_count', 1, 1)
            OR NOT mirror_demo_d02_json_integer_between(
                binding -> 'landmark_count', 478, 478
            )
            OR binding -> 'coordinates_finite' <> 'true'::jsonb
            OR binding -> 'coordinates_in_bounds' <> 'true'::jsonb
            OR binding ->> 'observation_state' NOT IN (
                'SUPPORTED','UNSUPPORTED_EXPLICIT'
            )
            OR binding -> 'repeat_gate_passed' IS DISTINCT FROM
                to_jsonb(binding ->> 'observation_state' = 'SUPPORTED')
            OR EXISTS (
                SELECT 1
                FROM unnest(ARRAY[
                    'execution_receipt_digest','canonical_output_digest',
                    'landmark_digest','measurement_observation_digest'
                ]) AS digest_key
                WHERE NOT mirror_demo_d02_json_string_matches(
                    binding -> digest_key, '^[0-9a-f]{64}$'
                )
            )
            OR binding ->> 'result_m3_record_id' <>
                record ->> 'result_m3_record_id'
            OR binding -> 'repeat_index' IS DISTINCT FROM record -> 'repeat_index'
            OR binding ->> 'execution_receipt_digest' <>
                record ->> 'execution_receipt_digest'
            OR binding ->> 'canonical_output_digest' <>
                record ->> 'canonical_output_digest'
            OR binding ->> 'landmark_digest' <> record ->> 'landmark_digest'
            OR binding ->> 'measurement_observation_digest' <>
                record ->> 'measurement_observation_digest'
            OR binding -> 'face_count' IS DISTINCT FROM record -> 'face_count'
            OR binding -> 'landmark_count' IS DISTINCT FROM record -> 'landmark_count'
            OR binding -> 'coordinates_finite' IS DISTINCT FROM
                record -> 'coordinates_finite'
            OR binding -> 'coordinates_in_bounds' IS DISTINCT FROM
                record -> 'coordinates_in_bounds'
            OR binding ->> 'observation_state' <> record ->> 'observation_state'
            OR binding -> 'repeat_gate_passed' IS DISTINCT FROM
                record -> 'repeat_gate_passed'
            OR binding ->> 'canonical_output_digest' <>
                first_binding ->> 'canonical_output_digest'
            OR binding ->> 'landmark_digest' <> first_binding ->> 'landmark_digest'
            OR binding ->> 'measurement_observation_digest' <>
                first_binding ->> 'measurement_observation_digest'
            OR binding ->> 'observation_state' <>
                first_binding ->> 'observation_state' THEN
            RAISE EXCEPTION 'D02 v10 result certificate binding is invalid';
        END IF;
    END LOOP;
    IF (
        SELECT count(DISTINCT item.value ->> 'result_m3_record_id')
        FROM jsonb_array_elements(
            certificate -> 'ordered_repeat_bindings'
        ) AS item(value)
    ) <> 3 THEN
        RAISE EXCEPTION 'D02 v10 result certificate record IDs are not distinct';
    END IF;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_d02_validate_source_entry_v10(
    source_entry jsonb,
    expected_ordinal integer
)
RETURNS void
LANGUAGE plpgsql
AS $function$
DECLARE
    identity_row demo_synthetic_identities%ROWTYPE;
    source_asset assets%ROWTYPE;
    facts jsonb;
    raw_authority jsonb;
    projection jsonb;
    raw_entry jsonb;
    projection_entry jsonb;
    supported_measurement jsonb;
    entry_index integer;
    expected_dimension text;
    dimensions constant text[] := ARRAY[
        'cheekbone_width','chin_height','eye_spacing',
        'jaw_width','mouth_width','nose_width'
    ];
BEGIN
    PERFORM mirror_demo_d02_require_record(
        source_entry,
        'mirror.demo/D02SourceAuthorityManifestEntry/v3',
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
            'dimension_authority_manifest_content_digest','measurement_config_digest',
            'measurement_quality_config_digest',
            'measurement_quality_manifest_content_digest','confidence_kind',
            'reliability_kind','runtime_manifest_digest',
            'vision_model_manifest_digest','topology_digest',
            'source_repeat_certification_digest','import_config_digest',
            'ordered_supported_measurements','record_digest'
        ]
    );
    IF NOT mirror_demo_d02_json_integer_between(
            source_entry -> 'source_ordinal', expected_ordinal, expected_ordinal
        )
        OR source_entry ->> 'source_authority_kind' <> 'DEMO_LOCAL_IMPORTED_COPY'
        OR NOT mirror_demo_d02_json_string_matches(
            source_entry -> 'source_authority_key', '^[0-9a-f]{64}$'
        )
        OR NOT mirror_demo_d02_json_string_matches(
            source_entry -> 'source_admission_event_id', '^[0-9a-f]{32}$'
        )
        OR NOT mirror_demo_d02_json_string_matches(
            source_entry -> 'source_output_id', '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'
        )
        OR NOT mirror_demo_d02_json_string_matches(
            source_entry -> 'source_asset_id', '^[0-9a-f]{32}$'
        )
        OR NOT mirror_demo_d02_json_integer_between(
            source_entry -> 'source_asset_byte_size', 1, 9223372036854775807
        )
        OR source_entry ->> 'source_asset_mime_type' <> 'image/jpeg'
        OR NOT mirror_demo_d02_json_integer_between(
            source_entry -> 'source_asset_width', 1, 2147483647
        )
        OR NOT mirror_demo_d02_json_integer_between(
            source_entry -> 'source_asset_height', 1, 2147483647
        )
        OR source_entry -> 'adult_synthetic_attested' <> 'true'::jsonb
        OR source_entry ->> 'original_formal_identity_id_status' <>
            'UNKNOWN_REDACTED_NOT_RECOVERED'
        OR NOT mirror_demo_d02_json_string_matches(
            source_entry -> 'source_p2_candidate_manifest_content_digest',
            '^[0-9a-f]{64}$'
        )
        OR source_entry ->> 'source_p2_candidate_manifest_content_digest' <>
            'eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4'
        OR NOT mirror_demo_d02_json_string_matches(
            source_entry -> 'dimension_authority_manifest_content_digest',
            '^[0-9a-f]{64}$'
        )
        OR source_entry ->> 'dimension_authority_manifest_content_digest' <>
            'd4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a'
        OR source_entry ->> 'measurement_config_digest' <>
            'ab5f745641a6f4539a8010fe32dda82b6c1066a8cb97d36ae17de737b901e8d3'
        OR source_entry ->> 'measurement_quality_config_digest' <>
            'ed52feca45f18b976e34d419da117d777d540978b9552c3e423a0d0c543e8f47'
        OR source_entry ->> 'measurement_quality_manifest_content_digest' <>
            'ed11f53e8e75428c396fb2b6711bd17fa996d49f8c4f5c9cdfebcfb36b42ed74'
        OR source_entry ->> 'confidence_kind' <>
            'DEMO_GEOMETRIC_OBSERVABILITY_PROXY_NOT_MODEL_CONFIDENCE'
        OR source_entry ->> 'reliability_kind' <>
            'EXACT_REPEAT_DETERMINISM_CERTIFICATION_NOT_MODEL_RELIABILITY'
        OR source_entry ->> 'runtime_manifest_digest' <>
            '6d739c2e269128ea7bc09358203aa7efe0714484b1a216a9f401353a243135ed'
        OR source_entry ->> 'vision_model_manifest_digest' <>
            '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'
        OR source_entry ->> 'topology_digest' <>
            '85eea84eef15dd963e06382d6e61f7357029d9901acc935731ecaa7eab856b63'
        OR source_entry ->> 'import_config_digest' <>
            '3cb5043028bec1c25e95822432db69a84b1eae9af3788201fafffe53f40acec2'
        OR EXISTS (
            SELECT 1
            FROM unnest(ARRAY[
                'source_admission_content_digest','source_asset_sha256',
                'source_receipt_digest','source_authority_digest',
                'source_qa_snapshot_digest','source_landmark_digest',
                'source_measurement_digest','source_provenance_digest',
                'source_fact_snapshot_digest','raw_measurement_authority_digest',
                'source_measurement_projection_digest',
                'source_repeat_certification_digest'
            ]) AS digest_key
            WHERE NOT mirror_demo_d02_json_string_matches(
                source_entry -> digest_key, '^[0-9a-f]{64}$'
            )
        )
        OR jsonb_typeof(source_entry -> 'ordered_supported_measurements') <> 'array'
        OR jsonb_array_length(source_entry -> 'ordered_supported_measurements') <> 6 THEN
        RAISE EXCEPTION 'D02 v10 source manifest scalar authority is invalid';
    END IF;

    SELECT * INTO identity_row
    FROM demo_synthetic_identities
    WHERE id = source_entry ->> 'source_admission_event_id';
    IF NOT FOUND
        OR identity_row.schema_version <> 'mirror.demo/DemoSyntheticIdentity/v3'
        OR identity_row.admission_action <> 'ADMIT'
        OR identity_row.source_authority_kind <> 'DEMO_LOCAL_IMPORTED_COPY'
        OR EXISTS (
            SELECT 1
            FROM demo_synthetic_identities later_event
            WHERE later_event.source_authority_key = identity_row.source_authority_key
              AND later_event.admission_sequence > identity_row.admission_sequence
        ) THEN
        RAISE EXCEPTION 'D02 v10 source entry lacks current v3 ADMIT authority';
    END IF;
    PERFORM mirror_demo_validate_d02_local_snapshot_v10(identity_row);
    facts := identity_row.source_fact_snapshot;
    raw_authority := facts -> 'raw_measurement_authority';
    projection := facts -> 'source_measurement_projection';

    SELECT * INTO source_asset FROM assets
    WHERE id = source_entry ->> 'source_asset_id';
    IF NOT FOUND
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
        OR source_asset.mime_type <> source_entry ->> 'source_asset_mime_type'
        OR source_asset.width <> (source_entry ->> 'source_asset_width')::integer
        OR source_asset.height <> (source_entry ->> 'source_asset_height')::integer THEN
        RAISE EXCEPTION 'D02 v10 source entry Asset authority is invalid';
    END IF;

    IF source_entry ->> 'source_authority_key' <> identity_row.source_authority_key
        OR source_entry ->> 'source_admission_content_digest' <>
            identity_row.content_digest
        OR source_entry ->> 'source_output_id' <> identity_row.source_output_id
        OR source_entry ->> 'source_asset_id' <>
            identity_row.formal_canonical_asset_id
        OR source_entry ->> 'source_asset_sha256' <>
            identity_row.formal_canonical_asset_sha256
        OR source_entry ->> 'source_receipt_digest' <>
            identity_row.source_receipt_digest
        OR source_entry ->> 'source_authority_digest' <>
            identity_row.source_authority_digest
        OR source_entry ->> 'source_qa_snapshot_digest' <>
            identity_row.source_qa_snapshot_digest
        OR source_entry ->> 'source_landmark_digest' <>
            identity_row.source_landmark_digest
        OR source_entry ->> 'source_measurement_digest' <>
            identity_row.source_measurement_digest
        OR source_entry ->> 'source_provenance_digest' <>
            identity_row.source_provenance_digest
        OR source_entry ->> 'source_fact_snapshot_digest' <>
            identity_row.source_fact_snapshot_digest
        OR source_entry ->> 'raw_measurement_authority_digest' <>
            facts ->> 'raw_measurement_authority_digest'
        OR source_entry ->> 'source_measurement_projection_digest' <>
            identity_row.source_measurement_projection_digest
        OR source_entry ->> 'source_repeat_certification_digest' <>
            facts ->> 'source_repeat_certification_digest'
        OR source_entry ->> 'import_config_digest' <> identity_row.import_config_digest
        OR source_entry ->> 'source_p2_candidate_manifest_content_digest' <>
            facts ->> 'source_p2_candidate_manifest_content_digest'
        OR source_entry ->> 'dimension_authority_manifest_content_digest' <>
            facts ->> 'dimension_authority_manifest_content_digest'
        OR source_entry ->> 'source_asset_sha256' <> facts ->> 'source_asset_sha256'
        OR source_entry -> 'source_asset_byte_size' IS DISTINCT FROM
            facts -> 'source_asset_byte_size'
        OR source_entry ->> 'source_asset_mime_type' <>
            facts ->> 'source_asset_mime_type'
        OR source_entry -> 'source_asset_width' IS DISTINCT FROM
            facts -> 'source_asset_width'
        OR source_entry -> 'source_asset_height' IS DISTINCT FROM
            facts -> 'source_asset_height'
        OR source_entry ->> 'source_measurement_digest' <>
            facts ->> 'source_measurement_observation_digest' THEN
        RAISE EXCEPTION 'D02 v10 source entry identity/facts equality is invalid';
    END IF;

    FOR entry_index IN 0..5 LOOP
        supported_measurement :=
            source_entry -> 'ordered_supported_measurements' -> entry_index;
        raw_entry := raw_authority -> 'ordered_entries' -> entry_index;
        projection_entry := projection -> 'ordered_entries' -> entry_index;
        expected_dimension := dimensions[entry_index + 1];
        IF NOT mirror_demo_jsonb_exact_keys(
            supported_measurement,
            ARRAY[
                'schema_version','dimension_key','raw_value_fixed18',
                'raw_confidence_fixed18','raw_reliability_fixed18','value_ppm',
                'confidence_ppm','reliability_ppm','unit'
            ]
        ) OR supported_measurement ->> 'schema_version' <>
                'mirror.demo/D02SupportedSourceMeasurement/v1'
            OR supported_measurement ->> 'dimension_key' <> expected_dimension
            OR supported_measurement ->> 'raw_value_fixed18' <>
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
                projection_entry -> 'reliability_ppm'
            OR supported_measurement ->> 'unit' <> 'FACE_HEIGHT_PPM' THEN
            RAISE EXCEPTION 'D02 v10 source supported projection is invalid';
        END IF;
    END LOOP;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_d02_validate_source_m3_v10(
    source_record jsonb,
    source_entry jsonb,
    source_manifest_digest text
)
RETURNS void
LANGUAGE plpgsql
AS $function$
DECLARE
    identity_row demo_synthetic_identities%ROWTYPE;
    facts jsonb;
    observation jsonb;
    certificate jsonb;
    binding jsonb;
    expected_id text;
    repeat_index integer;
BEGIN
    PERFORM mirror_demo_d02_require_record(
        source_record,
        'mirror.demo/D02SourceM3RepeatRecord/v2',
        ARRAY[
            'schema_version','source_m3_record_id','source_ordinal',
            'source_authority_key','source_admission_event_id','source_asset_id',
            'source_asset_sha256','repeat_index','execution_receipt_digest',
            'vision_model_manifest_digest','runtime_manifest_digest',
            'topology_digest','canonical_output_digest','landmark_digest',
            'measurement_observation','measurement_observation_digest','face_count',
            'landmark_count','coordinates_finite','coordinates_in_bounds',
            'repeat_gate_passed','record_digest'
        ]
    );
    repeat_index := (source_record ->> 'repeat_index')::integer;
    IF repeat_index NOT IN (1,2,3)
        OR source_record -> 'source_ordinal' IS DISTINCT FROM
            source_entry -> 'source_ordinal'
        OR source_record ->> 'source_authority_key' <>
            source_entry ->> 'source_authority_key'
        OR source_record ->> 'source_admission_event_id' <>
            source_entry ->> 'source_admission_event_id'
        OR source_record ->> 'source_asset_id' <> source_entry ->> 'source_asset_id'
        OR source_record ->> 'source_asset_sha256' <>
            source_entry ->> 'source_asset_sha256'
        OR source_record ->> 'vision_model_manifest_digest' <>
            '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'
        OR source_record ->> 'runtime_manifest_digest' <>
            '6d739c2e269128ea7bc09358203aa7efe0714484b1a216a9f401353a243135ed'
        OR source_record ->> 'topology_digest' <>
            '85eea84eef15dd963e06382d6e61f7357029d9901acc935731ecaa7eab856b63'
        OR NOT mirror_demo_d02_json_integer_between(source_record -> 'face_count', 1, 1)
        OR NOT mirror_demo_d02_json_integer_between(
            source_record -> 'landmark_count', 478, 478
        )
        OR source_record -> 'coordinates_finite' <> 'true'::jsonb
        OR source_record -> 'coordinates_in_bounds' <> 'true'::jsonb
        OR source_record -> 'repeat_gate_passed' <> 'true'::jsonb THEN
        RAISE EXCEPTION 'D02 v10 source M3 scalar authority is invalid';
    END IF;
    SELECT * INTO identity_row FROM demo_synthetic_identities
    WHERE id = source_entry ->> 'source_admission_event_id';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'D02 v10 source M3 identity is missing';
    END IF;
    facts := identity_row.source_fact_snapshot;
    observation := facts -> 'source_measurement_observation';
    certificate := facts -> 'source_repeat_certification';
    PERFORM mirror_demo_d02_validate_observation_v10(observation, 'SOURCE');
    PERFORM mirror_demo_d02_validate_source_certificate_v10(certificate, observation);
    binding := certificate -> 'ordered_repeat_bindings' -> (repeat_index - 1);
    expected_id := substring(
        mirror_demo_digest(
            'mirror.demo/D02SourceM3RecordId/v1',
            jsonb_build_object(
                'source_manifest_digest', source_manifest_digest,
                'source_authority_key', source_entry ->> 'source_authority_key',
                'source_admission_event_id',
                    source_entry ->> 'source_admission_event_id',
                'source_asset_id', source_entry ->> 'source_asset_id',
                'source_asset_sha256', source_entry ->> 'source_asset_sha256',
                'repeat_index', repeat_index,
                'vision_model_manifest_digest',
                    source_record ->> 'vision_model_manifest_digest',
                'runtime_manifest_digest',
                    source_record ->> 'runtime_manifest_digest',
                'topology_digest', source_record ->> 'topology_digest'
            )
        ) FROM 1 FOR 32
    );
    IF source_record ->> 'source_m3_record_id' <> expected_id
        OR source_record -> 'measurement_observation' IS DISTINCT FROM observation
        OR source_record ->> 'measurement_observation_digest' <>
            observation ->> 'measurement_observation_digest'
        OR source_record ->> 'canonical_output_digest' <>
            observation ->> 'canonical_output_digest'
        OR source_record ->> 'landmark_digest' <> observation ->> 'landmark_digest'
        OR source_record ->> 'execution_receipt_digest' <>
            binding ->> 'execution_receipt_digest'
        OR source_record ->> 'canonical_output_digest' <>
            binding ->> 'canonical_output_digest'
        OR source_record ->> 'landmark_digest' <> binding ->> 'landmark_digest'
        OR source_record ->> 'measurement_observation_digest' <>
            binding ->> 'measurement_observation_digest'
        OR source_record -> 'face_count' IS DISTINCT FROM binding -> 'face_count'
        OR source_record -> 'landmark_count' IS DISTINCT FROM binding -> 'landmark_count'
        OR source_record -> 'coordinates_finite' IS DISTINCT FROM
            binding -> 'coordinates_finite'
        OR source_record -> 'coordinates_in_bounds' IS DISTINCT FROM
            binding -> 'coordinates_in_bounds'
        OR source_record -> 'repeat_gate_passed' IS DISTINCT FROM
            binding -> 'repeat_gate_passed' THEN
        RAISE EXCEPTION 'D02 v10 source M3 graph equality is invalid';
    END IF;
END;
$function$;
"""


_D02_V10_RESULT_GATE_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_d02_validate_result_m3_v10(
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
    observation jsonb := result_record -> 'measurement_observation';
    subject jsonb;
    expected_id text;
    expected_state text;
BEGIN
    PERFORM mirror_demo_d02_require_record(
        result_record,
        'mirror.demo/D02ResultM3RepeatRecord/v2',
        ARRAY[
            'schema_version','result_m3_record_id','case_id',
            'case_specification_digest','result_output_id','result_sha256',
            'repeat_index','execution_receipt_digest',
            'vision_model_manifest_digest','runtime_manifest_digest',
            'topology_digest','canonical_output_digest','landmark_digest',
            'measurement_observation','measurement_observation_digest',
            'face_count','landmark_count','coordinates_finite',
            'coordinates_in_bounds','observation_state','repeat_gate_passed',
            'record_digest'
        ]
    );
    PERFORM mirror_demo_d02_validate_observation_v10(observation, 'RESULT');
    subject := observation -> 'subject';
    expected_state := CASE
        WHEN EXISTS (
            SELECT 1
            FROM jsonb_array_elements(
                observation -> 'ordered_measurements'
            ) AS measurement(value)
            WHERE measurement.value ->> 'support_state' <> 'SUPPORTED'
        ) THEN 'UNSUPPORTED_EXPLICIT'
        ELSE 'SUPPORTED'
    END;
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
                    '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff',
                'runtime_manifest_digest',
                    '6d739c2e269128ea7bc09358203aa7efe0714484b1a216a9f401353a243135ed',
                'topology_digest',
                    '85eea84eef15dd963e06382d6e61f7357029d9901acc935731ecaa7eab856b63'
            )
        ) FROM 1 FOR 32
    );
    IF result_record ->> 'result_m3_record_id' <> expected_id
        OR result_record ->> 'case_id' <> case_entry ->> 'case_id'
        OR result_record ->> 'case_specification_digest' <>
            case_entry ->> 'case_specification_digest'
        OR result_record ->> 'result_output_id' <>
            first_m4_record ->> 'result_output_id'
        OR result_record ->> 'result_sha256' <>
            first_m4_record ->> 'result_sha256'
        OR NOT mirror_demo_d02_json_integer_between(
            result_record -> 'repeat_index', expected_repeat, expected_repeat
        )
        OR result_record ->> 'runtime_manifest_digest' <>
            '6d739c2e269128ea7bc09358203aa7efe0714484b1a216a9f401353a243135ed'
        OR result_record ->> 'vision_model_manifest_digest' <>
            '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'
        OR result_record ->> 'topology_digest' <>
            '85eea84eef15dd963e06382d6e61f7357029d9901acc935731ecaa7eab856b63'
        OR EXISTS (
            SELECT 1
            FROM unnest(ARRAY[
                'execution_receipt_digest','canonical_output_digest',
                'landmark_digest','measurement_observation_digest'
            ]) AS digest_key
            WHERE NOT mirror_demo_d02_json_string_matches(
                result_record -> digest_key, '^[0-9a-f]{64}$'
            )
        )
        OR result_record ->> 'canonical_output_digest' <>
            observation ->> 'canonical_output_digest'
        OR result_record ->> 'landmark_digest' <> observation ->> 'landmark_digest'
        OR result_record ->> 'measurement_observation_digest' <>
            observation ->> 'measurement_observation_digest'
        OR subject ->> 'case_id' <> result_record ->> 'case_id'
        OR subject ->> 'case_specification_digest' <>
            result_record ->> 'case_specification_digest'
        OR subject ->> 'result_output_id' <> result_record ->> 'result_output_id'
        OR subject ->> 'result_sha256' <> result_record ->> 'result_sha256'
        OR NOT mirror_demo_d02_json_integer_between(
            result_record -> 'face_count', 1, 1
        )
        OR NOT mirror_demo_d02_json_integer_between(
            result_record -> 'landmark_count', 478, 478
        )
        OR result_record -> 'coordinates_finite' <> 'true'::jsonb
        OR result_record -> 'coordinates_in_bounds' <> 'true'::jsonb
        OR result_record ->> 'observation_state' <> expected_state
        OR NOT mirror_demo_d02_json_boolean(
            result_record -> 'repeat_gate_passed'
        )
        OR result_record -> 'repeat_gate_passed' IS DISTINCT FROM
            to_jsonb(expected_state = 'SUPPORTED') THEN
        RAISE EXCEPTION 'D02 v10 ResultM3 authority is invalid';
    END IF;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_d02_validate_gate_v10(
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
    first_observation_subject jsonb :=
        result_records -> 0 -> 'measurement_observation' -> 'subject';
    result_record jsonb;
    result_measurement jsonb;
    target_observation jsonb;
    control_observation jsonb;
    control_delta jsonb;
    expected_control_dimension text;
    expected_repeat integer;
    control_index integer;
BEGIN
    PERFORM mirror_demo_d02_require_record(
        gate_record,
        'mirror.demo/D02MeasurementGateRecord/v4',
        ARRAY[
            'schema_version','case_id','case_specification_digest',
            'dimension_key','requested_direction','requested_magnitude_ppm',
            'monotonicity_peer_case_id','source_target_measurement',
            'ordered_source_control_measurements',
            'ordered_result_repeat_measurements','measurement_evaluation_state',
            'gate_evaluation','result_repeat_certification',
            'result_repeat_certification_digest','record_digest'
        ]
    );
    IF jsonb_typeof(result_records) <> 'array'
        OR jsonb_array_length(result_records) <> 3 THEN
        RAISE EXCEPTION 'D02 v10 Gate requires exactly three ResultM3 records';
    END IF;
    PERFORM mirror_demo_d02_validate_result_certificate_v10(
        certificate, result_records
    );
    IF NOT mirror_demo_jsonb_exact_keys(
        certificate_subject,
        ARRAY[
            'schema_version','case_id','case_specification_digest',
            'result_output_id','result_sha256'
        ]
    ) OR certificate_subject ->> 'schema_version' <>
            'mirror.demo/D02ResultObservationSubject/v1'
        OR certificate_subject IS DISTINCT FROM first_observation_subject
        OR EXISTS (
            SELECT 1
            FROM jsonb_array_elements(result_records) AS result_record(value)
            WHERE result_record.value -> 'measurement_observation' -> 'subject'
                IS DISTINCT FROM certificate_subject
        )
        OR gate_record ->> 'result_repeat_certification_digest' <>
            certificate ->> 'result_repeat_certification_digest'
        OR gate_record ->> 'case_id' <> case_entry ->> 'case_id'
        OR gate_record ->> 'case_specification_digest' <>
            case_entry ->> 'case_specification_digest'
        OR gate_record ->> 'dimension_key' <> case_entry ->> 'dimension_key'
        OR gate_record ->> 'requested_direction' <> case_entry ->> 'direction'
        OR gate_record -> 'requested_magnitude_ppm' IS DISTINCT FROM
            case_entry -> 'magnitude_ppm'
        OR gate_record ->> 'monotonicity_peer_case_id' <>
            peer_case_entry ->> 'case_id'
        OR peer_case_entry ->> 'source_authority_key' <>
            case_entry ->> 'source_authority_key'
        OR peer_case_entry ->> 'source_admission_event_id' <>
            case_entry ->> 'source_admission_event_id'
        OR peer_case_entry ->> 'dimension_key' <> case_entry ->> 'dimension_key'
        OR peer_case_entry ->> 'direction' <> case_entry ->> 'direction'
        OR gate_record -> 'source_target_measurement' IS DISTINCT FROM (
            SELECT measurement.value
            FROM jsonb_array_elements(
                source_entry -> 'ordered_supported_measurements'
            ) AS measurement(value)
            WHERE measurement.value ->> 'dimension_key' =
                case_entry ->> 'dimension_key'
        )
        OR jsonb_typeof(
            gate_record -> 'ordered_source_control_measurements'
        ) <> 'array'
        OR jsonb_array_length(
            gate_record -> 'ordered_source_control_measurements'
        ) <> 5
        OR jsonb_typeof(
            gate_record -> 'ordered_result_repeat_measurements'
        ) <> 'array'
        OR jsonb_array_length(
            gate_record -> 'ordered_result_repeat_measurements'
        ) <> 3
        OR gate_record ->> 'measurement_evaluation_state' NOT IN (
            'SUPPORTED_EVALUATED','UNSUPPORTED_EXPLICIT'
        ) THEN
        RAISE EXCEPTION 'D02 v10 Gate graph binding is invalid';
    END IF;

    FOR expected_repeat IN 1..3 LOOP
        result_record := result_records -> (expected_repeat - 1);
        result_measurement := gate_record ->
            'ordered_result_repeat_measurements' -> (expected_repeat - 1);
        SELECT measurement.value INTO target_observation
        FROM jsonb_array_elements(
            result_record -> 'measurement_observation' -> 'ordered_measurements'
        ) AS measurement(value)
        WHERE measurement.value ->> 'dimension_key' = case_entry ->> 'dimension_key';
        IF target_observation IS NULL THEN
            RAISE EXCEPTION 'D02 v10 Gate observation projection is invalid';
        END IF;

        IF target_observation ->> 'support_state' = 'SUPPORTED' THEN
            IF result_record ->> 'observation_state' <> 'SUPPORTED'
                OR result_measurement ->> 'schema_version' <>
                    'mirror.demo/D02SupportedResultMeasurement/v1'
                OR result_measurement -> 'repeat_index' IS DISTINCT FROM
                    to_jsonb(expected_repeat)
                OR result_measurement ->> 'result_m3_record_digest' <>
                    result_record ->> 'record_digest'
                OR result_measurement ->> 'raw_result_target_fixed18' <>
                    target_observation ->> 'raw_value_fixed18'
                OR jsonb_typeof(result_measurement -> 'ordered_control_deltas') <>
                    'array'
                OR jsonb_array_length(result_measurement -> 'ordered_control_deltas') <> 5
            THEN
                RAISE EXCEPTION 'D02 v10 Gate observation projection is invalid';
            END IF;
            FOR control_index IN 0..4 LOOP
                expected_control_dimension :=
                    case_entry -> 'ordered_control_dimensions' ->> control_index;
                SELECT measurement.value INTO control_observation
                FROM jsonb_array_elements(
                    result_record -> 'measurement_observation' -> 'ordered_measurements'
                ) AS measurement(value)
                WHERE measurement.value ->> 'dimension_key' = expected_control_dimension;
                control_delta := result_measurement -> 'ordered_control_deltas' ->
                    control_index;
                IF control_observation IS NULL
                    OR control_observation ->> 'support_state' <> 'SUPPORTED'
                    OR control_delta ->> 'dimension_key' <> expected_control_dimension
                    OR control_delta ->> 'raw_result_value_fixed18' <>
                        control_observation ->> 'raw_value_fixed18'
                THEN
                    RAISE EXCEPTION 'D02 v10 Gate observation projection is invalid';
                END IF;
            END LOOP;
        ELSIF target_observation ->> 'support_state' = 'UNSUPPORTED' THEN
            IF result_record ->> 'observation_state' <> 'UNSUPPORTED_EXPLICIT'
                OR result_measurement ->> 'schema_version' <>
                    'mirror.demo/D02UnsupportedResultMeasurement/v1'
                OR result_measurement -> 'repeat_index' IS DISTINCT FROM
                    to_jsonb(expected_repeat)
                OR result_measurement ->> 'result_m3_record_digest' <>
                    result_record ->> 'record_digest'
                OR result_measurement ->> 'unsupported_dimension_key' <>
                    case_entry ->> 'dimension_key'
                OR result_measurement ->> 'unsupported_reason' <>
                    target_observation ->> 'unsupported_reason'
                OR result_measurement -> 'measurement_gate_passed' <> 'false'::jsonb
            THEN
                RAISE EXCEPTION 'D02 v10 Gate observation projection is invalid';
            END IF;
        ELSE
            RAISE EXCEPTION 'D02 v10 Gate observation projection is invalid';
        END IF;
    END LOOP;
END;
$function$;
"""


_D02_V10_REPORT_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_screening_report_v10()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    payload jsonb := NEW.report_payload;
    binding jsonb := payload -> 'schema_and_policy';
    measurement_config jsonb := binding -> 'measurement_execution_config';
    network_boundary jsonb := payload -> 'network_and_runtime_boundary';
    source_entry jsonb;
    previous_source_entry jsonb;
    source_record jsonb;
    case_entry jsonb;
    peer_case_entry jsonb;
    m4_record jsonb;
    first_m4_record jsonb;
    result_record jsonb;
    gate_record jsonb;
    result_records jsonb;
    shadow_gates jsonb;
    shadow_row demo_pair_screening_reports%ROWTYPE;
    expected_id text;
    expected_digest text;
    expected_payload jsonb;
    expected_control_dimensions text[];
    expected_dimension text;
    expected_direction text;
    expected_source_ordinal integer;
    expected_priority integer;
    expected_direction_index integer;
    expected_magnitude integer;
    expected_magnitude_index integer;
    expected_repeat integer;
    source_index integer;
    case_index integer;
    record_index integer;
    replay_index integer;
    candidate_dimensions constant text[] := ARRAY[
        'jaw_width','chin_height','eye_spacing'
    ];
BEGIN
    IF NEW.schema_version <> 'mirror.demo/D02PairScreeningReport/v2'
        OR NOT mirror_demo_jsonb_exact_keys(
            payload,
            ARRAY[
                'schema_and_policy','ordered_source_manifest',
                'ordered_case_manifest','source_m3_repeat_evidence',
                'm4_repeat_evidence','result_m3_repeat_evidence',
                'measurement_gate_evidence',
                'decode_structure_immutability_evidence',
                'manual_review_evidence','exact_duplicate_evidence',
                'phash_observation_evidence','pair_quality_evidence',
                'dimension_eligibility','fixed_priority_selection_trace',
                'selected_pair_manifest','network_and_runtime_boundary'
            ]
        ) THEN
        RAISE EXCEPTION 'D02 v10 report envelope is invalid';
    END IF;

    IF NOT mirror_demo_jsonb_exact_keys(
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
    ) OR binding ->> 'schema_version' <>
            'mirror.demo/D02SchemaAndPolicyBinding/v2'
        OR binding ->> 'source_manifest_digest' <> NEW.source_manifest_digest
        OR binding ->> 'case_manifest_digest' <> NEW.case_manifest_digest
        OR binding ->> 'screening_policy_digest' <> NEW.screening_policy_digest
        OR binding ->> 'runtime_manifest_digest' <> NEW.runtime_manifest_digest
        OR binding ->> 'vision_model_manifest_digest' <>
            NEW.vision_model_manifest_digest
        OR binding ->> 'topology_digest' <> NEW.topology_digest
        OR binding ->> 'measurement_config_digest' <>
            NEW.measurement_config_digest
        OR binding ->> 'manual_review_policy_digest' <>
            NEW.manual_review_policy_digest
        OR binding ->> 'duplicate_policy_digest' <> NEW.duplicate_policy_digest
        OR binding ->> 'phash_implementation_digest' <>
            NEW.phash_implementation_digest
        OR NEW.screening_policy_digest IS DISTINCT FROM
            mirror_demo_d02_expected_screening_policy_digest()
        OR NEW.runtime_manifest_digest <>
            '6d739c2e269128ea7bc09358203aa7efe0714484b1a216a9f401353a243135ed'
        OR NEW.vision_model_manifest_digest <>
            '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'
        OR NEW.topology_digest <>
            '85eea84eef15dd963e06382d6e61f7357029d9901acc935731ecaa7eab856b63'
        OR NEW.measurement_config_digest <>
            'ab5f745641a6f4539a8010fe32dda82b6c1066a8cb97d36ae17de737b901e8d3'
        OR binding ->> 'measurement_quality_config_digest' <>
            'ed52feca45f18b976e34d419da117d777d540978b9552c3e423a0d0c543e8f47'
        OR binding ->> 'measurement_quality_manifest_content_digest' <>
            'ed11f53e8e75428c396fb2b6711bd17fa996d49f8c4f5c9cdfebcfb36b42ed74'
        OR binding ->> 'confidence_kind' <>
            'DEMO_GEOMETRIC_OBSERVABILITY_PROXY_NOT_MODEL_CONFIDENCE'
        OR binding ->> 'reliability_kind' <>
            'EXACT_REPEAT_DETERMINISM_CERTIFICATION_NOT_MODEL_RELIABILITY'
        OR NOT mirror_demo_jsonb_exact_keys(
            measurement_config,
            ARRAY[
                'schema_version','measurement_algorithm_version',
                'measurement_projection_version',
                'measurement_quantization_version',
                'decimal_serialization_version','decimal_precision','rounding',
                'coordinate_system','required_face_count',
                'required_landmark_count','repeat_count',
                'supported_raw_min_fixed18','supported_ppm_min',
                'supported_ppm_max','unsupported_reason_precedence',
                'unsupported_projection_policy_version',
                'source_repeat_failure_policy_version',
                'result_repeat_failure_policy_version',
                'confidence_algorithm_version','confidence_kind',
                'reliability_algorithm_version','reliability_kind',
                'source_p2_candidate_manifest_content_digest',
                'dimension_authority_manifest_content_digest',
                'geometry_ontology_version_digest',
                'vision_model_manifest_digest','topology_digest',
                'd02_execution_runtime_set_digest',
                'measurement_quality_config_digest',
                'measurement_observation_schema_version',
                'source_repeat_certification_schema_version',
                'result_repeat_certification_schema_version',
                'source_m3_repeat_record_schema_version',
                'result_m3_repeat_record_schema_version',
                'measurement_gate_record_schema_version'
            ]
        )
        OR measurement_config ->> 'schema_version' <>
            'mirror.demo/D02MeasurementExecutionConfig/v1'
        OR mirror_demo_digest(
            'mirror.demo/D02MeasurementExecutionConfig/v1',
            measurement_config - 'schema_version'
        ) <> NEW.measurement_config_digest
        OR measurement_config ->> 'source_p2_candidate_manifest_content_digest' <>
            'eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4'
        OR measurement_config ->> 'dimension_authority_manifest_content_digest' <>
            'd4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a'
        OR measurement_config ->> 'geometry_ontology_version_digest' <>
            'd902fe2cfdf69db9f62ccc2e5fa7c569227d652f1204aa683742fc3c592f38b9'
        OR measurement_config ->> 'measurement_quality_config_digest' <>
            binding ->> 'measurement_quality_config_digest'
        OR measurement_config ->> 'd02_execution_runtime_set_digest' <>
            NEW.runtime_manifest_digest
        OR measurement_config ->> 'vision_model_manifest_digest' <>
            NEW.vision_model_manifest_digest
        OR measurement_config ->> 'topology_digest' <> NEW.topology_digest
        OR measurement_config ->> 'confidence_kind' <> binding ->> 'confidence_kind'
        OR measurement_config ->> 'reliability_kind' <> binding ->> 'reliability_kind'
        THEN
        RAISE EXCEPTION 'D02 v10 schema/policy authority is invalid';
    END IF;

    IF NOT mirror_demo_jsonb_exact_keys(
        network_boundary,
        ARRAY[
            'schema_version','public_internet_egress',
            'localhost_and_docker_internal_network','proxy_environment_present',
            'production_provider_calls','runtime_generation_calls',
            'boundary_receipt_digest'
        ]
    ) OR network_boundary ->> 'schema_version' <>
            'mirror.demo/D02NetworkRuntimeBoundary/v2'
        OR network_boundary ->> 'public_internet_egress' <> 'DENIED'
        OR network_boundary -> 'localhost_and_docker_internal_network' <>
            'true'::jsonb
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
        RAISE EXCEPTION 'D02 v10 network boundary is invalid';
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
        OR jsonb_typeof(
            payload -> 'decode_structure_immutability_evidence'
        ) <> 'array'
        OR jsonb_array_length(
            payload -> 'decode_structure_immutability_evidence'
        ) <> 48
        OR jsonb_typeof(payload -> 'manual_review_evidence') <> 'array'
        OR jsonb_array_length(payload -> 'manual_review_evidence') <> 48
        OR jsonb_typeof(payload -> 'pair_quality_evidence') <> 'array'
        OR jsonb_array_length(payload -> 'pair_quality_evidence') <> 24
        OR jsonb_typeof(payload -> 'dimension_eligibility') <> 'array'
        OR jsonb_array_length(payload -> 'dimension_eligibility') <> 3
        OR jsonb_typeof(
            payload -> 'fixed_priority_selection_trace'
        ) <> 'array'
        OR jsonb_array_length(
            payload -> 'fixed_priority_selection_trace'
        ) <> 3
        OR jsonb_typeof(payload -> 'selected_pair_manifest') <> 'array' THEN
        RAISE EXCEPTION 'D02 v10 fixed evidence universe is incomplete';
    END IF;

    FOR source_index IN 0..3 LOOP
        source_entry := payload -> 'ordered_source_manifest' -> source_index;
        PERFORM mirror_demo_d02_validate_source_entry_v10(
            source_entry, source_index + 1
        );
        IF source_index > 0 THEN
            previous_source_entry :=
                payload -> 'ordered_source_manifest' -> (source_index - 1);
            IF (
                previous_source_entry ->> 'source_authority_key',
                previous_source_entry ->> 'source_admission_event_id'
            ) >= (
                source_entry ->> 'source_authority_key',
                source_entry ->> 'source_admission_event_id'
            ) THEN
                RAISE EXCEPTION 'D02 v10 source manifest order is invalid';
            END IF;
        END IF;
        FOR expected_repeat IN 1..3 LOOP
            record_index := source_index * 3 + expected_repeat - 1;
            source_record :=
                payload -> 'source_m3_repeat_evidence' -> record_index;
            IF source_record -> 'source_ordinal' IS DISTINCT FROM
                    source_entry -> 'source_ordinal'
                OR source_record -> 'repeat_index' IS DISTINCT FROM
                    to_jsonb(expected_repeat) THEN
                RAISE EXCEPTION 'D02 v10 source M3 natural order is invalid';
            END IF;
            PERFORM mirror_demo_d02_validate_source_m3_v10(
                source_record, source_entry, NEW.source_manifest_digest
            );
        END LOOP;
    END LOOP;
    IF NEW.source_manifest_digest IS DISTINCT FROM mirror_demo_digest(
        'mirror.demo/D02SourceAuthorityManifest/v1',
        payload -> 'ordered_source_manifest'
    ) OR (
        SELECT count(DISTINCT item.value ->> 'source_m3_record_id')
        FROM jsonb_array_elements(
            payload -> 'source_m3_repeat_evidence'
        ) AS item(value)
    ) <> 12 OR (
        SELECT count(DISTINCT item.value ->> 'record_digest')
        FROM jsonb_array_elements(
            payload -> 'source_m3_repeat_evidence'
        ) AS item(value)
    ) <> 12 THEN
        RAISE EXCEPTION 'D02 v10 source manifest or repeat uniqueness is invalid';
    END IF;

    FOR case_index IN 0..47 LOOP
        case_entry := payload -> 'ordered_case_manifest' -> case_index;
        PERFORM mirror_demo_d02_require_record(
            case_entry,
            'mirror.demo/D02GeometryCaseManifestEntry/v3',
            ARRAY[
                'schema_version','case_ordinal','case_id',
                'source_manifest_digest','source_ordinal',
                'source_authority_key','source_admission_event_id',
                'source_asset_id','source_asset_sha256',
                'source_qa_snapshot_digest',
                'source_measurement_projection_digest',
                'source_p2_candidate_manifest_content_digest',
                'dimension_authority_manifest_content_digest',
                'geometry_ontology_version_digest','dimension_key',
                'priority_index','direction','direction_index',
                'magnitude_ppm','magnitude_index',
                'ordered_control_dimensions','warp_plan_digest',
                'geometry_algorithm_version','runtime_manifest_digest',
                'runtime_config_digest','output_policy_version',
                'output_width','output_height','determinism_level',
                'execution_config_digest','case_specification_digest',
                'record_digest'
            ]
        );
        expected_source_ordinal := case_index / 12 + 1;
        expected_priority := (case_index % 12) / 4 + 1;
        expected_direction_index := (case_index % 4) / 2 + 1;
        expected_magnitude_index := case_index % 2 + 1;
        expected_dimension := candidate_dimensions[expected_priority];
        expected_direction :=
            (ARRAY['DECREASE','INCREASE'])[expected_direction_index];
        expected_magnitude :=
            (ARRAY[15000,30000])[expected_magnitude_index];
        source_entry := payload -> 'ordered_source_manifest' ->
            (expected_source_ordinal - 1);
        expected_control_dimensions := CASE expected_dimension
            WHEN 'jaw_width' THEN ARRAY[
                'cheekbone_width','chin_height','eye_spacing',
                'mouth_width','nose_width'
            ]
            WHEN 'chin_height' THEN ARRAY[
                'cheekbone_width','eye_spacing','jaw_width',
                'mouth_width','nose_width'
            ]
            ELSE ARRAY[
                'cheekbone_width','chin_height','jaw_width',
                'mouth_width','nose_width'
            ]
        END;
        IF NOT mirror_demo_d02_json_integer_between(
                case_entry -> 'case_ordinal', case_index + 1, case_index + 1
            )
            OR case_entry -> 'source_ordinal' IS DISTINCT FROM
                to_jsonb(expected_source_ordinal)
            OR case_entry ->> 'dimension_key' <> expected_dimension
            OR case_entry -> 'priority_index' IS DISTINCT FROM
                to_jsonb(expected_priority)
            OR case_entry ->> 'direction' <> expected_direction
            OR case_entry -> 'direction_index' IS DISTINCT FROM
                to_jsonb(expected_direction_index)
            OR case_entry -> 'magnitude_ppm' IS DISTINCT FROM
                to_jsonb(expected_magnitude)
            OR case_entry -> 'magnitude_index' IS DISTINCT FROM
                to_jsonb(expected_magnitude_index)
            OR case_entry -> 'ordered_control_dimensions' IS DISTINCT FROM
                to_jsonb(expected_control_dimensions)
            OR case_entry ->> 'source_manifest_digest' <>
                NEW.source_manifest_digest
            OR case_entry ->> 'source_authority_key' <>
                source_entry ->> 'source_authority_key'
            OR case_entry ->> 'source_admission_event_id' <>
                source_entry ->> 'source_admission_event_id'
            OR case_entry ->> 'source_asset_id' <>
                source_entry ->> 'source_asset_id'
            OR case_entry ->> 'source_asset_sha256' <>
                source_entry ->> 'source_asset_sha256'
            OR case_entry ->> 'source_qa_snapshot_digest' <>
                source_entry ->> 'source_qa_snapshot_digest'
            OR case_entry ->> 'source_measurement_projection_digest' <>
                source_entry ->> 'source_measurement_projection_digest'
            OR case_entry ->> 'source_p2_candidate_manifest_content_digest' <>
                source_entry ->> 'source_p2_candidate_manifest_content_digest'
            OR case_entry ->> 'dimension_authority_manifest_content_digest' <>
                source_entry ->> 'dimension_authority_manifest_content_digest'
            OR NOT mirror_demo_d02_json_string_matches(
                case_entry -> 'geometry_ontology_version_digest',
                '^[0-9a-f]{64}$'
            )
            OR case_entry ->> 'geometry_ontology_version_digest' <>
                measurement_config ->> 'geometry_ontology_version_digest'
            OR case_entry ->> 'runtime_manifest_digest' <>
                NEW.runtime_manifest_digest
            OR NOT mirror_demo_d02_json_string_matches(
                case_entry -> 'warp_plan_digest', '^[0-9a-f]{64}$'
            )
            OR NOT mirror_demo_d02_json_string_matches(
                case_entry -> 'runtime_config_digest', '^[0-9a-f]{64}$'
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
            RAISE EXCEPTION 'D02 v10 case manifest authority is invalid';
        END IF;
        expected_digest := mirror_demo_digest(
            'mirror.demo/D02ExecutionConfiguration/v1',
            jsonb_build_object(
                'screening_policy_digest', NEW.screening_policy_digest,
                'runtime_manifest_digest', NEW.runtime_manifest_digest,
                'vision_model_manifest_digest',
                    NEW.vision_model_manifest_digest,
                'topology_digest', NEW.topology_digest,
                'measurement_config_digest', NEW.measurement_config_digest,
                'manual_review_policy_digest',
                    NEW.manual_review_policy_digest,
                'duplicate_policy_digest', NEW.duplicate_policy_digest,
                'phash_implementation_digest',
                    NEW.phash_implementation_digest,
                'geometry_algorithm_version',
                    case_entry ->> 'geometry_algorithm_version',
                'runtime_config_digest',
                    case_entry ->> 'runtime_config_digest',
                'output_policy_version',
                    case_entry ->> 'output_policy_version',
                'output_width', (case_entry ->> 'output_width')::integer,
                'output_height', (case_entry ->> 'output_height')::integer,
                'determinism_level', case_entry ->> 'determinism_level'
            )
        );
        expected_id := substring(
            mirror_demo_digest(
                'mirror.demo/D02GeometryCaseId/v1',
                jsonb_build_object(
                    'source_manifest_digest', NEW.source_manifest_digest,
                    'source_authority_key',
                        source_entry ->> 'source_authority_key',
                    'source_admission_event_id',
                        source_entry ->> 'source_admission_event_id',
                    'source_asset_sha256',
                        source_entry ->> 'source_asset_sha256',
                    'source_p2_candidate_manifest_content_digest',
                        source_entry ->> 'source_p2_candidate_manifest_content_digest',
                    'dimension_authority_manifest_content_digest',
                        source_entry ->> 'dimension_authority_manifest_content_digest',
                    'dimension_key', expected_dimension,
                    'direction', expected_direction,
                    'magnitude_ppm', expected_magnitude,
                    'execution_config_digest', expected_digest
                )
            ) FROM 1 FOR 32
        );
        expected_payload := jsonb_build_object(
            'source_manifest_digest', NEW.source_manifest_digest,
            'source_ordinal', expected_source_ordinal,
            'source_authority_key', source_entry ->> 'source_authority_key',
            'source_admission_event_id',
                source_entry ->> 'source_admission_event_id',
            'source_asset_id', source_entry ->> 'source_asset_id',
            'source_asset_sha256', source_entry ->> 'source_asset_sha256',
            'source_qa_snapshot_digest',
                source_entry ->> 'source_qa_snapshot_digest',
            'source_measurement_projection_digest',
                source_entry ->> 'source_measurement_projection_digest',
            'source_p2_candidate_manifest_content_digest',
                source_entry ->> 'source_p2_candidate_manifest_content_digest',
            'dimension_authority_manifest_content_digest',
                source_entry ->> 'dimension_authority_manifest_content_digest',
            'geometry_ontology_version_digest',
                case_entry ->> 'geometry_ontology_version_digest',
            'dimension_key', expected_dimension,
            'priority_index', expected_priority,
            'direction', expected_direction,
            'direction_index', expected_direction_index,
            'magnitude_ppm', expected_magnitude,
            'magnitude_index', expected_magnitude_index,
            'ordered_control_dimensions', to_jsonb(expected_control_dimensions),
            'warp_plan_digest', case_entry ->> 'warp_plan_digest',
            'geometry_algorithm_version',
                case_entry ->> 'geometry_algorithm_version',
            'runtime_manifest_digest', NEW.runtime_manifest_digest,
            'runtime_config_digest', case_entry ->> 'runtime_config_digest',
            'output_policy_version', case_entry ->> 'output_policy_version',
            'output_width', (case_entry ->> 'output_width')::integer,
            'output_height', (case_entry ->> 'output_height')::integer,
            'determinism_level', case_entry ->> 'determinism_level',
            'execution_config_digest', expected_digest
        );
        IF case_entry ->> 'execution_config_digest' <> expected_digest
            OR case_entry ->> 'case_id' <> expected_id
            OR case_entry ->> 'case_specification_digest' <>
                mirror_demo_digest(
                    'mirror.demo/D02GeometryCaseSpecification/v1',
                    expected_payload
                ) THEN
            RAISE EXCEPTION 'D02 v10 case derived authority is invalid';
        END IF;
    END LOOP;
    IF NEW.case_manifest_digest IS DISTINCT FROM mirror_demo_digest(
        'mirror.demo/D02GeometryCaseManifest/v1',
        payload -> 'ordered_case_manifest'
    ) OR (
        SELECT count(DISTINCT item.value ->> 'case_id')
        FROM jsonb_array_elements(
            payload -> 'ordered_case_manifest'
        ) AS item(value)
    ) <> 48 OR (
        SELECT count(DISTINCT item.value ->> 'case_specification_digest')
        FROM jsonb_array_elements(
            payload -> 'ordered_case_manifest'
        ) AS item(value)
    ) <> 48 THEN
        RAISE EXCEPTION 'D02 v10 case manifest digest or uniqueness is invalid';
    END IF;

    FOR replay_index IN 0..95 LOOP
        m4_record := payload -> 'm4_repeat_evidence' -> replay_index;
        case_index := replay_index / 2;
        expected_repeat := replay_index % 2 + 1;
        case_entry := payload -> 'ordered_case_manifest' -> case_index;
        source_entry := payload -> 'ordered_source_manifest' ->
            ((case_entry ->> 'source_ordinal')::integer - 1);
        PERFORM mirror_demo_d02_require_record(
            m4_record,
            'mirror.demo/D02M4ExecutionRecord/v1',
            ARRAY[
                'schema_version','m4_execution_record_id','case_id',
                'case_specification_digest','replay_index','source_output_id',
                'source_asset_id','source_asset_sha256','result_output_id',
                'result_sha256','result_byte_size','result_mime_type',
                'result_width','result_height','changed_pixel_count',
                'warp_plan_digest','geometry_algorithm_version',
                'runtime_manifest_digest','runtime_config_digest',
                'determinism_level','execution_receipt_digest',
                'execution_succeeded','record_digest'
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
                    'runtime_config_digest',
                        case_entry ->> 'runtime_config_digest',
                    'determinism_level',
                        case_entry ->> 'determinism_level'
                )
            ) FROM 1 FOR 32
        );
        IF m4_record ->> 'm4_execution_record_id' <> expected_id
            OR m4_record ->> 'case_id' <> case_entry ->> 'case_id'
            OR m4_record ->> 'case_specification_digest' <>
                case_entry ->> 'case_specification_digest'
            OR m4_record -> 'replay_index' IS DISTINCT FROM
                to_jsonb(expected_repeat)
            OR m4_record ->> 'source_output_id' <>
                source_entry ->> 'source_output_id'
            OR m4_record ->> 'source_asset_id' <>
                source_entry ->> 'source_asset_id'
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
            OR m4_record ->> 'result_mime_type' <> 'image/jpeg'
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
            OR m4_record ->> 'warp_plan_digest' <>
                case_entry ->> 'warp_plan_digest'
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
            OR m4_record -> 'execution_succeeded' <> 'true'::jsonb THEN
            RAISE EXCEPTION 'D02 v10 M4 authority is invalid';
        END IF;
        first_m4_record :=
            payload -> 'm4_repeat_evidence' -> (case_index * 2);
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
            RAISE EXCEPTION 'D02 v10 M4 replay pair is not deterministic';
        END IF;
    END LOOP;
    IF (
        SELECT count(DISTINCT item.value ->> 'm4_execution_record_id')
        FROM jsonb_array_elements(payload -> 'm4_repeat_evidence') AS item(value)
    ) <> 96 OR (
        SELECT count(DISTINCT item.value ->> 'record_digest')
        FROM jsonb_array_elements(payload -> 'm4_repeat_evidence') AS item(value)
    ) <> 96 THEN
        RAISE EXCEPTION 'D02 v10 M4 uniqueness is invalid';
    END IF;

    FOR case_index IN 0..47 LOOP
        case_entry := payload -> 'ordered_case_manifest' -> case_index;
        peer_case_entry := payload -> 'ordered_case_manifest' -> CASE
            WHEN (case_entry ->> 'magnitude_ppm')::integer = 15000
                THEN case_index + 1
            ELSE case_index - 1
        END;
        first_m4_record :=
            payload -> 'm4_repeat_evidence' -> (case_index * 2);
        result_records := jsonb_build_array(
            payload -> 'result_m3_repeat_evidence' -> (case_index * 3),
            payload -> 'result_m3_repeat_evidence' -> (case_index * 3 + 1),
            payload -> 'result_m3_repeat_evidence' -> (case_index * 3 + 2)
        );
        FOR expected_repeat IN 1..3 LOOP
            result_record :=
                payload -> 'result_m3_repeat_evidence' ->
                (case_index * 3 + expected_repeat - 1);
            PERFORM mirror_demo_d02_validate_result_m3_v10(
                result_record, case_entry, first_m4_record, expected_repeat
            );
        END LOOP;
        source_entry := payload -> 'ordered_source_manifest' ->
            ((case_entry ->> 'source_ordinal')::integer - 1);
        gate_record := payload -> 'measurement_gate_evidence' -> case_index;
        PERFORM mirror_demo_d02_validate_gate_v10(
            gate_record,
            case_entry,
            peer_case_entry,
            source_entry,
            result_records
        );
    END LOOP;
    IF (
        SELECT count(DISTINCT item.value ->> 'result_m3_record_id')
        FROM jsonb_array_elements(
            payload -> 'result_m3_repeat_evidence'
        ) AS item(value)
    ) <> 144 OR (
        SELECT count(DISTINCT item.value ->> 'record_digest')
        FROM jsonb_array_elements(
            payload -> 'result_m3_repeat_evidence'
        ) AS item(value)
    ) <> 144 THEN
        RAISE EXCEPTION 'D02 v10 ResultM3 uniqueness is invalid';
    END IF;

    SELECT jsonb_agg(
        jsonb_build_object(
            'schema_version', 'mirror.demo/D02MeasurementGateRecord/v3'
        ) || stripped_gate || jsonb_build_object(
            'record_digest',
            mirror_demo_digest(
                'mirror.demo/D02MeasurementGateRecord/v3', stripped_gate
            )
        )
        ORDER BY gate_ordinal
    )
    INTO shadow_gates
    FROM (
        SELECT
            gate.value - ARRAY[
                'schema_version','record_digest',
                'result_repeat_certification',
                'result_repeat_certification_digest'
            ]::text[] AS stripped_gate,
            gate.ordinality AS gate_ordinal
        FROM jsonb_array_elements(
            payload -> 'measurement_gate_evidence'
        ) WITH ORDINALITY AS gate(value, ordinality)
    ) AS shadow;
    shadow_row := NEW;
    shadow_row.report_payload := jsonb_set(
        payload,
        ARRAY['measurement_gate_evidence'],
        shadow_gates,
        false
    );
    PERFORM mirror_demo_validate_d02_measurements_v9(shadow_row);
    PERFORM mirror_demo_validate_d02_images_v9(NEW);
    PERFORM mirror_demo_validate_d02_pairs_v9(NEW);
    RETURN NEW;
END;
$function$;
"""


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


_D02_QUALITY_UPGRADE_AUDIT_SQL = r"""
DO $block$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM demo_synthetic_identities
        WHERE schema_version NOT IN (
            'mirror.demo/DemoSyntheticIdentity/v1',
            'mirror.demo/DemoSyntheticIdentity/v2'
        )
    ) THEN
        RAISE EXCEPTION
            'D02 quality upgrade found an unknown identity authority version';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM demo_pair_screening_reports
        WHERE schema_version <> 'mirror.demo/D02PairScreeningReport/v1'
    ) THEN
        RAISE EXCEPTION
            'D02 quality upgrade found an unknown report authority version';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM demo_question_banks
        WHERE schema_version NOT IN (
            'mirror.demo/DemoQuestionBank/v1',
            'mirror.demo/DemoQuestionBank/v2'
        )
    ) OR EXISTS (
        SELECT 1
        FROM demo_question_pairs
        WHERE schema_version NOT IN (
            'mirror.demo/DemoQuestionPair/v1',
            'mirror.demo/DemoQuestionPair/v2'
        )
    ) THEN
        RAISE EXCEPTION
            'D02 quality upgrade found an unknown bank or pair version';
    END IF;
END;
$block$;
"""


_D02_QUALITY_DOWNGRADE_PREFLIGHT_SQL = r"""
DO $block$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM demo_synthetic_identities
        WHERE schema_version = 'mirror.demo/DemoSyntheticIdentity/v3'
    ) THEN
        RAISE EXCEPTION
            'Cannot downgrade populated D02 v3 identity authority';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM demo_pair_screening_reports
        WHERE schema_version = 'mirror.demo/D02PairScreeningReport/v2'
    ) THEN
        RAISE EXCEPTION
            'Cannot downgrade populated D02 Report v2 authority';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM demo_synthetic_identities
        WHERE schema_version NOT IN (
            'mirror.demo/DemoSyntheticIdentity/v1',
            'mirror.demo/DemoSyntheticIdentity/v2'
        )
    ) OR EXISTS (
        SELECT 1
        FROM demo_pair_screening_reports
        WHERE schema_version <> 'mirror.demo/D02PairScreeningReport/v1'
    ) THEN
        RAISE EXCEPTION
            'Cannot downgrade unknown D02 quality authority';
    END IF;
END;
$block$;
"""


def _upgrade_identity_constraints() -> None:
    table_name = "demo_synthetic_identities"
    op.drop_constraint(
        op.f("ck_demo_synthetic_identities_schema_version_shape"),
        table_name,
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_demo_synthetic_identities_source_mode_null_matrix"),
        table_name,
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_demo_synthetic_identities_schema_version_shape"),
        table_name,
        "schema_version IN ('mirror.demo/DemoSyntheticIdentity/v1',"
        "'mirror.demo/DemoSyntheticIdentity/v2',"
        "'mirror.demo/DemoSyntheticIdentity/v3')",
    )
    op.create_check_constraint(
        op.f("ck_demo_synthetic_identities_source_mode_null_matrix"),
        table_name,
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
        "AND import_config_digest IS NOT NULL)",
    )


def _downgrade_identity_constraints() -> None:
    table_name = "demo_synthetic_identities"
    op.drop_constraint(
        op.f("ck_demo_synthetic_identities_source_mode_null_matrix"),
        table_name,
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_demo_synthetic_identities_schema_version_shape"),
        table_name,
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_demo_synthetic_identities_schema_version_shape"),
        table_name,
        "schema_version IN ('mirror.demo/DemoSyntheticIdentity/v1',"
        "'mirror.demo/DemoSyntheticIdentity/v2')",
    )
    op.create_check_constraint(
        op.f("ck_demo_synthetic_identities_source_mode_null_matrix"),
        table_name,
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
        "AND original_formal_identity_id_status = "
        "'UNKNOWN_REDACTED_NOT_RECOVERED' "
        "AND adult_synthetic_attested IS TRUE "
        "AND importer_version = 'demo-d02-identity-importer-v2' "
        "AND import_config_digest IS NOT NULL)",
    )


def _upgrade_report_constraints() -> None:
    table_name = "demo_pair_screening_reports"
    for constraint_name in (
        "ck_demo_pair_screening_reports_exact_schema_version",
        "ck_demo_pair_screening_reports_schema_version_shape",
    ):
        op.drop_constraint(op.f(constraint_name), table_name, type_="check")
    op.create_check_constraint(
        op.f("ck_demo_pair_screening_reports_schema_version_shape"),
        table_name,
        "schema_version IN ('mirror.demo/D02PairScreeningReport/v1',"
        "'mirror.demo/D02PairScreeningReport/v2')",
    )
    op.create_check_constraint(
        op.f("ck_demo_pair_screening_reports_exact_schema_version"),
        table_name,
        "schema_version IN ('mirror.demo/D02PairScreeningReport/v1',"
        "'mirror.demo/D02PairScreeningReport/v2')",
    )


def _downgrade_report_constraints() -> None:
    table_name = "demo_pair_screening_reports"
    for constraint_name in (
        "ck_demo_pair_screening_reports_exact_schema_version",
        "ck_demo_pair_screening_reports_schema_version_shape",
    ):
        op.drop_constraint(op.f(constraint_name), table_name, type_="check")
    op.create_check_constraint(
        op.f("ck_demo_pair_screening_reports_schema_version_shape"),
        table_name,
        "schema_version ~ '^mirror[.]demo/[A-Za-z0-9]+/v1$'",
    )
    op.create_check_constraint(
        op.f("ck_demo_pair_screening_reports_exact_schema_version"),
        table_name,
        "schema_version = 'mirror.demo/D02PairScreeningReport/v1'",
    )


def upgrade() -> None:
    op.execute(_D02_TABLE_LOCK_SQL)
    op.execute(_D02_QUALITY_UPGRADE_AUDIT_SQL)
    _upgrade_identity_constraints()
    _upgrade_report_constraints()

    op.execute(_D02_V10_GUARD_SQL)
    op.execute(_D02_V10_QUALITY_HELPERS_SQL)
    op.execute(_D02_V10_IDENTITY_SQL)
    op.execute(_D02_V10_REPORT_HELPERS_SQL)
    op.execute(_D02_V10_RESULT_GATE_SQL)
    op.execute(_D02_V10_REPORT_SQL)
    op.execute(_D02_V10_WRITE_GUARDS_SQL)

    op.execute(
        "DROP TRIGGER trg_demo_d02_synthetic_identity_validation ON demo_synthetic_identities"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d02_synthetic_identity_validation "
        "BEFORE INSERT ON demo_synthetic_identities "
        "FOR EACH ROW WHEN (NEW.schema_version = "
        "'mirror.demo/DemoSyntheticIdentity/v2') "
        "EXECUTE FUNCTION mirror_demo_validate_d02_synthetic_identity()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d02_synthetic_identity_v10 "
        "BEFORE INSERT ON demo_synthetic_identities "
        "FOR EACH ROW WHEN (NEW.schema_version = "
        "'mirror.demo/DemoSyntheticIdentity/v3') "
        "EXECUTE FUNCTION mirror_demo_validate_d02_synthetic_identity_v10()"
    )

    op.execute(
        "DROP TRIGGER trg_demo_d02_screening_report_validation ON demo_pair_screening_reports"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d02_screening_report_validation "
        "BEFORE INSERT ON demo_pair_screening_reports "
        "FOR EACH ROW WHEN (NEW.schema_version = "
        "'mirror.demo/D02PairScreeningReport/v1') "
        "EXECUTE FUNCTION mirror_demo_validate_d02_screening_report()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d02_screening_report_v10 "
        "BEFORE INSERT ON demo_pair_screening_reports "
        "FOR EACH ROW WHEN (NEW.schema_version = "
        "'mirror.demo/D02PairScreeningReport/v2') "
        "EXECUTE FUNCTION mirror_demo_validate_d02_screening_report_v10()"
    )

    for table_name, suffix in (
        ("demo_synthetic_identities", "identity"),
        ("demo_pair_screening_reports", "report"),
        ("demo_question_banks", "bank"),
        ("demo_question_pairs", "pair"),
    ):
        op.execute(
            f"CREATE TRIGGER trg_demo_d02_write_version_v10_{suffix} "
            f"BEFORE INSERT ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION "
            "mirror_demo_validate_d02_write_version_v10()"
        )


def downgrade() -> None:
    op.execute(_D02_TABLE_LOCK_SQL)
    op.execute(_D02_QUALITY_DOWNGRADE_PREFLIGHT_SQL)

    for table_name, suffix in reversed(
        (
            ("demo_synthetic_identities", "identity"),
            ("demo_pair_screening_reports", "report"),
            ("demo_question_banks", "bank"),
            ("demo_question_pairs", "pair"),
        )
    ):
        op.execute(f"DROP TRIGGER trg_demo_d02_write_version_v10_{suffix} ON {table_name}")

    op.execute("DROP TRIGGER trg_demo_d02_screening_report_v10 ON demo_pair_screening_reports")
    op.execute(
        "DROP TRIGGER trg_demo_d02_screening_report_validation ON demo_pair_screening_reports"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d02_screening_report_validation "
        "BEFORE INSERT ON demo_pair_screening_reports "
        "FOR EACH ROW EXECUTE FUNCTION "
        "mirror_demo_validate_d02_screening_report()"
    )

    op.execute("DROP TRIGGER trg_demo_d02_synthetic_identity_v10 ON demo_synthetic_identities")
    op.execute(
        "DROP TRIGGER trg_demo_d02_synthetic_identity_validation ON demo_synthetic_identities"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d02_synthetic_identity_validation "
        "BEFORE INSERT ON demo_synthetic_identities "
        "FOR EACH ROW EXECUTE FUNCTION "
        "mirror_demo_validate_d02_synthetic_identity()"
    )

    _downgrade_report_constraints()
    _downgrade_identity_constraints()

    op.execute(_D02_V9_GUARD_RESTORE_SQL)
    op.execute("DROP FUNCTION mirror_demo_validate_d02_screening_report_v10()")
    op.execute("DROP FUNCTION mirror_demo_validate_d02_write_version_v10()")
    op.execute("DROP FUNCTION mirror_demo_d02_validate_gate_v10(jsonb,jsonb,jsonb,jsonb,jsonb)")
    op.execute("DROP FUNCTION mirror_demo_d02_validate_result_m3_v10(jsonb,jsonb,jsonb,integer)")
    op.execute("DROP FUNCTION mirror_demo_d02_validate_source_m3_v10(jsonb,jsonb,text)")
    op.execute("DROP FUNCTION mirror_demo_d02_validate_source_entry_v10(jsonb,integer)")
    op.execute("DROP FUNCTION mirror_demo_d02_validate_result_certificate_v10(jsonb,jsonb)")
    op.execute("DROP FUNCTION mirror_demo_validate_d02_synthetic_identity_v10()")
    op.execute(
        "DROP FUNCTION mirror_demo_validate_d02_local_snapshot_v10(demo_synthetic_identities)"
    )
    op.execute("DROP FUNCTION mirror_demo_d02_validate_source_certificate_v10(jsonb,jsonb)")
    op.execute("DROP FUNCTION mirror_demo_d02_validate_observation_v10(jsonb,text)")
