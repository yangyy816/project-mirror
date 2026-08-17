from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from mirror_api.config import get_settings

pytestmark = pytest.mark.integration


def test_initial_migration_contains_v02_entities_and_no_superseded_placeholders() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0001_phase0_foundation.py"
    ).read_text(encoding="utf-8")
    for table_name in (
        "baseline_face_models",
        "baseline_measurements",
        "self_states",
        "baseline_morphology_descriptors",
        "question_templates",
        "question_instances",
        "questionnaire_routes",
        "desired_delta_profile_versions",
        "desired_delta_dimensions",
        "style_profile_versions",
        "identity_constraint_versions",
        "self_transfer_validation_runs",
        "self_transfer_validation_responses",
    ):
        assert f'"{table_name}"' in migration
    assert "question_pairs" not in migration
    assert "geometry_preferences" not in migration


def test_identity_auth_migration_uses_metadata_index_names() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0002_identity_auth_foundation.py"
    ).read_text(encoding="utf-8")
    for index_name in (
        "ix_phone_verification_challenges_invite_code_id",
        "ix_invite_redemptions_invite_code_id",
        "ix_invite_redemptions_user_id",
        "ix_age_assurance_records_user_id",
        "ix_policy_acceptance_records_user_id",
    ):
        assert migration.count(f'"{index_name}"') == 2


def test_upload_control_migration_does_not_update_immutable_consent_rows() -> None:
    migration = (
        Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0003_upload_control.py"
    ).read_text(encoding="utf-8")
    assert "UPDATE consent_records" not in migration


def test_safe_image_ingestion_migration_is_forward_only_from_upload_control() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0004_safe_image_ingestion.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "0003_upload_control"' in migration
    for table_name in ("asset_ingestion_records", "jobs", "job_attempts", "upload_intents"):
        assert table_name in migration
    assert "mirror_validate_asset_ingestion_record" in migration
    assert "trg_asset_ingestion_records_immutable" in migration


def test_ci_evidence_tracks_current_migration_head() -> None:
    workflow = (Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    expected_argument = "--expected-migration-head 0011_offline_synth_source"
    assert workflow.count(expected_argument) == 3
    assert "--expected-migration-head 0009_generation_batch_pipeline" not in workflow


def test_upgrade_downgrade_reupgrade_and_schema_consistency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")

    root = Path(__file__).resolve().parents[3]
    config = Config(root / "services" / "api" / "alembic.ini")
    config.set_main_option("script_location", str(root / "services" / "api" / "migrations"))
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE synthetic_generation_policies, synthetic_prompt_templates, "
                "synthetic_qa_policies, geometry_ontology_versions, synthetic_identities, assets, "
                "question_bank_versions, users CASCADE"
            )
        )
    engine.dispose()
    command.downgrade(config, "base")
    command.upgrade(config, "0002_identity_auth")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users "
                "(id, phone_hash, status, created_at, updated_at) "
                "VALUES (:id, :phone_hash, 'pending', now(), now())"
            ),
            {"id": "migration-user", "phone_hash": "f" * 64},
        )
        connection.execute(
            text(
                "INSERT INTO consent_records "
                "(id, user_id, consent_type, purpose, scope, policy_version, action, "
                "granted_at, source, created_at) "
                "VALUES (:id, :user_id, 'facial_data_processing', 'legacy-purpose', "
                "CAST(:scope AS json), 'legacy-policy', 'grant', now(), 'migration-test', now())"
            ),
            {"id": "migration-consent", "user_id": "migration-user", "scope": "{}"},
        )
    command.upgrade(config, "0003_upload_control")
    with engine.connect() as connection:
        migrated = connection.execute(
            text(
                "SELECT purpose_version, policy_code, policy_digest, request_id "
                "FROM consent_records WHERE id = 'migration-consent'"
            )
        ).one()
    assert migrated == ("legacy-phase0", "legacy-consent", "0" * 64, "legacy-phase0")
    command.upgrade(config, "0007_account_quarantine_evidence")
    command.upgrade(config, "0008_synth_dataset_foundation")
    command.downgrade(config, "0007_account_quarantine_evidence")
    command.upgrade(config, "0008_synth_dataset_foundation")
    command.upgrade(config, "0009_generation_batch_pipeline")
    command.downgrade(config, "0008_synth_dataset_foundation")
    command.upgrade(config, "0009_generation_batch_pipeline")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO synthetic_identities "
                "(id, bank_version_id, generator_provider, generator_model, prompt_version, "
                "provenance, adult_synthetic_attested, created_at) "
                "VALUES ('migration-legacy-identity', NULL, 'deterministic_fixture', "
                "'fixture-v1', 'fixture-prompt-v1', CAST(:provenance AS json), true, now())"
            ),
            {"provenance": '{"source":"synthetic"}'},
        )
    command.upgrade(config, "0010_synthetic_asset_qa")
    with engine.connect() as connection:
        migrated_identity = connection.execute(
            text(
                "SELECT authority_kind, canonical_asset_id, accepted_qa_run_id, "
                "generator_provider FROM synthetic_identities "
                "WHERE id = 'migration-legacy-identity'"
            )
        ).one()
    assert migrated_identity == ("LEGACY_SKELETON", None, None, "deterministic_fixture")
    command.downgrade(config, "0009_generation_batch_pipeline")
    with engine.connect() as connection:
        restored_identity = connection.execute(
            text(
                "SELECT generator_provider, generator_model, prompt_version "
                "FROM synthetic_identities WHERE id = 'migration-legacy-identity'"
            )
        ).one()
    assert restored_identity == ("deterministic_fixture", "fixture-v1", "fixture-prompt-v1")
    command.upgrade(config, "head")
    command.check(config)
    engine.dispose()
    get_settings.cache_clear()
