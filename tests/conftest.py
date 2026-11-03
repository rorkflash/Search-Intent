"""Shared test fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from search_intent.main import create_app
from search_intent.settings import Settings


@pytest.fixture(autouse=True)
def _isolate_from_local_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Importing search_intent.main runs load_dotenv(), which walks up to a
    # developer's .env (e.g. REDIS_URL, SEARCH_INTENT_CONFIG_DIR) and copies it
    # into os.environ; Settings also reads .env from the cwd. Either way tests
    # would hit a live Redis — serving search objects cached by an earlier run
    # or another extractor — or load the wrong profile. Start every test from
    # the built-in defaults instead.
    for field in Settings.model_fields.values():
        if field.alias:
            monkeypatch.delenv(field.alias, raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)


@pytest.fixture()
def client() -> TestClient:
    # TestClient runs lifespan startup/shutdown via the context manager.
    app = create_app()
    with TestClient(app) as c:
        yield c
