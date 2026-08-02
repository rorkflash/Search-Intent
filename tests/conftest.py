"""Shared test fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from search_intent.main import create_app


@pytest.fixture()
def client() -> TestClient:
    # TestClient runs lifespan startup/shutdown via the context manager.
    app = create_app()
    with TestClient(app) as c:
        yield c
