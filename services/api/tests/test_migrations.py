from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

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

    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)
