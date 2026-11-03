"""End-to-end tests for the MovieTrip parse-only config (config/movietrip).

MovieTrip only uses POST /v1/parse: send free-text, get back intent + entities.
No API mapping, resolvers, or caching is exercised in production for this
config, so these tests focus solely on /v1/parse behavior.

The profile extracts with GLiNER2.5 (fastino/gliner2.5-base-v1, prompted with
each entity's model_description), so these tests pin what the model returns.
Gliner2Extractor ignores the regex-only options in extractor.json
(``ambiguous_terms``/``context_words``, ``extract_quoted``,
``extract_residual``), so some outputs below are the model's own span choices
rather than what those options describe. A failure here usually means the
model, its threshold, or the label set changed: check the new output before
updating the expectation.
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
        "/v1/parse", json={"query": "museum places in Edinburgh"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "search_places"
    assert body["objects"] == ["places"]
    assert body["entities"]["location_type"] == ["museum"]
    assert body["entities"]["city"] == ["Edinburgh"]


def test_parse_scenes_intent(movietrip_client: TestClient) -> None:
    resp = movietrip_client.post(
        "/v1/parse", json={"query": "museum scenes filmed in Edinburgh"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "search_scenes"
    assert body["objects"] == ["scenes"]
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


def test_parse_ambiguous_location_type_with_context(
    movietrip_client: TestClient,
) -> None:
    resp = movietrip_client.post(
        "/v1/parse", json={"query": "James Bond bank location in Rome"}
    )
    assert resp.status_code == 200
    body = resp.json()
    # "bank" itself is tagged, so it resolves to the bank place type.
    assert body["entities"]["location_type"] == ["bank"]
    assert body["entities"]["city"] == ["Rome"]


def test_parse_ambiguous_genre_without_context(
    movietrip_client: TestClient,
) -> None:
    resp = movietrip_client.post(
        "/v1/parse", json={"query": "War and Peace is a classic novel"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "global_search"
    # "War" is not taken as a genre; the phrase reads as a title.
    assert body["entities"] == {"movie_title": ["War and Peace"]}


def test_parse_ambiguous_genre_with_context(
    movietrip_client: TestClient,
) -> None:
    resp = movietrip_client.post(
        "/v1/parse", json={"query": "western movies filmed in Rome"}
    )
    assert resp.status_code == 200
    body = resp.json()
    # Just the genre word, so it resolves to the western genre id.
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


def test_parse_ambiguous_country_without_context(
    movietrip_client: TestClient,
) -> None:
    resp = movietrip_client.post(
        "/v1/parse", json={"query": "I bought a china plate yesterday"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "global_search"
    # Lowercase "china" in "china plate" is not read as the country.
    assert body["entities"] == {}


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


def test_generate_quoted_unknown_title_becomes_q(movietrip_client: TestClient) -> None:
    resp = movietrip_client.post(
        "/v1/generate",
        json={"query": "the scenes of 'Inferno' movie", "limit": 1},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "search_scenes"
    assert body["search_object"]["entities"]["movie_title"] == ["Inferno"]
    assert body["api_request"]["body"] == {
        "q": "Inferno",
        "types": ["scenes"],
        "lang": "en",
        "limit": 1,
    }


def test_generate_unquoted_unknown_title_becomes_q(
    movietrip_client: TestClient,
) -> None:
    resp = movietrip_client.post(
        "/v1/generate",
        json={"query": "the scenes of Inferno movie", "limit": 1},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "search_scenes"
    # The title comes out without the trailing "movie".
    assert body["search_object"]["entities"] == {"movie_title": ["Inferno"]}
    assert body["api_request"]["body"] == {
        "q": "Inferno",
        "types": ["scenes"],
        "lang": "en",
        "limit": 1,
    }


def test_generate_year_range_filters(movietrip_client: TestClient) -> None:
    resp = movietrip_client.post(
        "/v1/generate",
        json={
            "query": "I need all movies started from 2012 to 2016",
            "limit": 10,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "search_movies"
    # GLiNER2 returns the range as two bare years; parse_year pools them.
    assert body["search_object"]["entities"]["year"] == ["2016", "2012"]
    assert "movie_title" not in body["search_object"]["entities"]
    assert body["api_request"]["body"] == {
        "types": ["movies"],
        "lang": "en",
        "limit": 10,
        "filters": {"year_from": 2012, "year_to": 2016},
    }


def test_parse_falls_back_to_global_search(movietrip_client: TestClient) -> None:
    resp = movietrip_client.post("/v1/parse", json={"query": "James Bond"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "global_search"
    assert body["entities"]["movie_title"] == ["James Bond"]


def test_parse_validation_rejects_empty_query(movietrip_client: TestClient) -> None:
    resp = movietrip_client.post("/v1/parse", json={"query": ""})
    assert resp.status_code == 422


def test_generate_scopes_placeless_query_to_user_location(
    movietrip_client: TestClient,
) -> None:
    # No city or country in the query, but the caller knows where the user is:
    # the request is scoped to a box around them instead of the whole planet.
    resp = movietrip_client.post(
        "/v1/generate",
        json={
            "query": "cafe places near me",
            "user_location": {"lat": 40.1792, "lng": 44.4991},
        },
    )
    assert resp.status_code == 200
    body = resp.json()

    geo = body["search_object"]["geo"]
    assert geo["applied"] is True
    assert geo["trigger"] == "explicit_cue"
    # Snapped to ~1.1 km before it reaches the generated request.
    assert (geo["lat"], geo["lng"]) == (40.18, 44.5)

    filters = body["api_request"]["body"]["filters"]
    assert filters["minLat"] == geo["bbox"]["min_lat"]
    assert filters["maxLng"] == geo["bbox"]["max_lng"]


def test_generate_reads_user_location_from_proxy_headers(
    movietrip_client: TestClient,
) -> None:
    resp = movietrip_client.post(
        "/v1/generate",
        json={"query": "cafe places nearby"},
        headers={"cf-iplatitude": "51.5074", "cf-iplongitude": "-0.1278"},
    )
    assert resp.status_code == 200
    geo = resp.json()["search_object"]["geo"]
    assert geo["source"] == "header"
    assert (geo["lat"], geo["lng"]) == (51.51, -0.13)


def test_generate_without_a_user_location_stays_global(
    movietrip_client: TestClient,
) -> None:
    resp = movietrip_client.post("/v1/generate", json={"query": "cafe places nearby"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["search_object"]["geo"] is None
    assert "minLat" not in body["api_request"]["body"].get("filters", {})


def test_generate_ignores_user_location_when_the_query_names_a_city(
    movietrip_client: TestClient,
) -> None:
    resp = movietrip_client.post(
        "/v1/generate",
        json={
            "query": "places in Paris",
            "user_location": {"lat": 40.1792, "lng": 44.4991},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["search_object"]["geo"] is None
    assert body["api_request"]["body"]["filters"] == {"city_id": 359}
