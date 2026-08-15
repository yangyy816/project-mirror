from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from mirror_api.config import get_settings
from mirror_api.dependencies import DependencyStatus, probe_dependencies
from mirror_api.main import create_app


@pytest.fixture(scope="session", autouse=True)
def postgresql_schema() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        return
    root = Path(__file__).resolve().parents[3]
    config = Config(root / "services" / "api" / "alembic.ini")
    config.set_main_option("script_location", str(root / "services" / "api" / "migrations"))
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        command.upgrade(config, "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


@pytest.fixture
def client() -> TestClient:
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[probe_dependencies] = lambda: DependencyStatus(
        database="available", redis="available"
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    get_settings.cache_clear()
