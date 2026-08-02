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
    assert body["objects"] == ["places"]
    assert body["entities"]["movie_title"] == ["Harry Potter"]
    assert body["entities"]["city"] == ["London"]


def test_parse_movie_query(movietrip_client: TestClient) -> None:
    resp = movietrip_client.post(
        "/v1/parse", json={"query": "fantasy movies like Lord of the Rings"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "search_movies"
    assert body["objects"] == ["movies"]
    assert body["entities"]["genre"] == ["fantasy"]
    assert body["entities"]["movie_title"] == ["Lord of the Rings"]


def test_parse_location_type_and_city(movietrip_client: TestClient) -> None:
    resp = movietrip_client.post(
        "/v1/parse", json={"query": "museum scenes filmed in Edinburgh"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "search_places"
    assert body["entities"]["location_type"] == ["museum"]
    assert body["entities"]["city"] == ["Edinburgh"]


def test_parse_ignores_ambiguous_location_type_without_context(
    movietrip_client: TestClient,
) -> None:
    resp = movietrip_client.post(
        "/v1/parse", json={"query": "James Bond and the Bank of England heist"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "location_type" not in body["entities"]


def test_parse_matches_ambiguous_location_type_with_context(
    movietrip_client: TestClient,
) -> None:
    resp = movietrip_client.post(
        "/v1/parse", json={"query": "James Bond bank location in Rome"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["entities"]["location_type"] == ["bank"]
    assert body["entities"]["city"] == ["Rome"]


def test_parse_ignores_ambiguous_genre_without_context(
    movietrip_client: TestClient,
) -> None:
    resp = movietrip_client.post(
        "/v1/parse", json={"query": "War and Peace is a classic novel"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "genre" not in body["entities"]


def test_parse_matches_ambiguous_genre_with_context(
    movietrip_client: TestClient,
) -> None:
    resp = movietrip_client.post(
        "/v1/parse", json={"query": "western movies filmed in Rome"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["entities"]["genre"] == ["western"]
    assert body["entities"]["city"] == ["Rome"]


def test_parse_country_entity(movietrip_client: TestClient) -> None:
    resp = movietrip_client.post(
        "/v1/parse", json={"query": "movies filmed in France"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "search_movies"
    assert body["entities"]["country"] == ["France"]


def test_parse_ignores_ambiguous_country_without_context(
    movietrip_client: TestClient,
) -> None:
    resp = movietrip_client.post(
        "/v1/parse", json={"query": "I bought a china plate yesterday"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "country" not in body["entities"]


def test_parse_matches_ambiguous_country_with_context(
    movietrip_client: TestClient,
) -> None:
    resp = movietrip_client.post(
        "/v1/parse", json={"query": "planning a trip to China this fall"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["entities"]["country"] == ["China"]


def test_parse_ignores_ambiguous_city_without_context(
    movietrip_client: TestClient,
) -> None:
    resp = movietrip_client.post(
        "/v1/parse", json={"query": "the weather is really nice today"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "city" not in body["entities"]


def test_parse_matches_ambiguous_city_with_context(
    movietrip_client: TestClient,
) -> None:
    resp = movietrip_client.post(
        "/v1/parse", json={"query": "planning a trip to Nice next month"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["entities"]["city"] == ["Nice"]


def test_generate_resolves_city_to_single_id(movietrip_client: TestClient) -> None:
    resp = movietrip_client.post("/v1/generate", json={"query": "places in Paris"})
    assert resp.status_code == 200
    resolved = resp.json()["search_object"]["resolved"]
    assert resolved["city_ids"] == [359]


def test_generate_resolves_ambiguous_city_to_multiple_ids(
    movietrip_client: TestClient,
) -> None:
    # "Cambridge" exists as a real city in both the US and the UK; the
    # resolver maps it to both ids rather than guessing one.
    resp = movietrip_client.post("/v1/generate", json={"query": "places in Cambridge"})
    assert resp.status_code == 200
    resolved = resp.json()["search_object"]["resolved"]
    assert resolved["city_ids"] == [632, 691]


def test_generate_resolves_country_to_id(movietrip_client: TestClient) -> None:
    resp = movietrip_client.post(
        "/v1/generate", json={"query": "movies filmed in France"}
    )
    assert resp.status_code == 200
    resolved = resp.json()["search_object"]["resolved"]
    assert resolved["country_ids"] == [86]


def test_parse_falls_back_to_global_search(movietrip_client: TestClient) -> None:
    resp = movietrip_client.post("/v1/parse", json={"query": "James Bond"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "global_search"
    assert body["entities"]["movie_title"] == ["James Bond"]


def test_parse_validation_rejects_empty_query(movietrip_client: TestClient) -> None:
    resp = movietrip_client.post("/v1/parse", json={"query": ""})
    assert resp.status_code == 422
