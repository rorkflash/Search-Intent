"""Shared test fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from search_intent.main import create_app


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Pinned so a local .env pointing at another collection can't redirect it.
    monkeypatch.setenv("SEARCH_INTENT_CONFIG_DIR", "config/default")
    # TestClient runs lifespan startup/shutdown via the context manager.
    app = create_app()
    with TestClient(app) as c:
        yield c
