import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "teamsync-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    monkeypatch.setenv("APP_ENV", "test")

    from app.config import get_settings
    import app.database as database

    get_settings.cache_clear()
    database.engine.dispose()
    database.settings = get_settings()
    database.engine = database.create_engine(database.settings.database_url, **database._engine_kwargs(database.settings.database_url))
    database.SessionLocal.configure(bind=database.engine)

    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
