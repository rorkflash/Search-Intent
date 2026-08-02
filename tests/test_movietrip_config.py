"""End-to-end tests for the MovieTrip parse-only config (config/movietrip).

MovieTrip only uses POST /v1/parse: send free-text, get back intent + entities.
No API mapping, resolvers, or caching is exercised in production for this
config, so these tests focus solely on /v1/parse behavior.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from search_intent.main import create_app


@pytest.fixture()
def movietrip_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("SEARCH_INTENT_CONFIG_DIR", "config/movietrip")
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_health_reports_movietrip_project(movietrip_client: TestClient) -> None:
    resp = movietrip_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["project"] == "movietrip"


def test_parse_movie_places_query(movietrip_client: TestClient) -> None:
    resp = movietrip_client.post(
        "/v1/parse", json={"query": "Harry Potter places in London"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "search_places"
    assert body["objects"] == ["place"]
    assert body["entities"]["movie_title"] == ["Harry Potter"]
    assert body["entities"]["city"] == ["London"]


def test_parse_movie_query(movietrip_client: TestClient) -> None:
    resp = movietrip_client.post(
        "/v1/parse", json={"query": "fantasy movies like Lord of the Rings"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "search_movies"
    assert body["objects"] == ["movie"]
    assert body["entities"]["genre"] == ["fantasy"]
    assert body["entities"]["movie_title"] == ["Lord of the Rings"]


def test_parse_location_type_and_city(movietrip_client: TestClient) -> None:
    resp = movietrip_client.post(
        "/v1/parse", json={"query": "castle scenes filmed in Edinburgh"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "search_places"
    assert body["entities"]["location_type"] == ["castle"]
    assert body["entities"]["city"] == ["Edinburgh"]


def test_parse_falls_back_to_global_search(movietrip_client: TestClient) -> None:
    resp = movietrip_client.post("/v1/parse", json={"query": "James Bond"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "global_search"
    assert body["entities"]["movie_title"] == ["James Bond"]


def test_parse_validation_rejects_empty_query(movietrip_client: TestClient) -> None:
    resp = movietrip_client.post("/v1/parse", json={"query": ""})
    assert resp.status_code == 422
