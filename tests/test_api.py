"""End-to-end API tests against the bundled example-shop config.

The root config targets DummyJSON (https://dummyjson.com) in
generate_and_execute mode so parse, generate, resolve, cache, and search
can all be exercised without a private backend.
"""

from __future__ import annotations


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["project"] == "example-shop"


def test_parse(client):
    resp = client.post("/v1/parse", json={"query": "red Nike shoes under $100"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "search_products"
    assert body["entities"]["brand"] == ["Nike"]
    assert body["entities"]["color"] == ["red"]
    assert body["entities"]["price"] == ["under $100"]


def test_generate_builds_api_request(client):
    resp = client.post("/v1/generate", json={"query": "red Nike shoes under $100"})
    assert resp.status_code == 200
    body = resp.json()

    so = body["search_object"]
    # Nike -> brand_ids 42 via the static resolver.
    assert so["resolved"]["brand_ids"] == [42]
    assert so["filters"]["brand_ids"] == [42]
    assert so["filters"]["price"] == {"max": 100.0}
    assert so["filters"]["color"] == ["red"]

    req = body["api_request"]
    assert req["method"] == "GET"
    assert req["url"] == "https://dummyjson.com/products/search"
    assert req["query"]["q"] == "red Nike shoes under $100"
    assert req["query"]["limit"] == 20
    assert req["query"]["skip"] == 0
    assert req["body"] is None


def test_generate_resolves_category_slug(client):
    resp = client.post("/v1/generate", json={"query": "laptops"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["search_object"]["resolved"]["category_slugs"] == ["laptops"]
    assert body["api_request"]["url"] == "https://dummyjson.com/products/search"


def test_generate_cache_hit_on_second_call(client):
    payload = {"query": "black Adidas shoes"}
    first = client.post("/v1/generate", json=payload).json()
    second = client.post("/v1/generate", json=payload).json()
    assert first["cache"]["hit"] is False
    assert second["cache"]["hit"] is True


def test_search_executes_dummyjson(client):
    resp = client.post(
        "/v1/search",
        json={"query": "phone", "limit": 3},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "search_products"
    assert body["api_request"]["url"] == "https://dummyjson.com/products/search"
    assert body["api_request"]["query"]["q"] == "phone"
    assert body["api_request"]["query"]["limit"] == 3
    assert body["api_response"] is not None
    assert "products" in body["api_response"]
    assert isinstance(body["api_response"]["products"], list)
    assert len(body["api_response"]["products"]) > 0


def test_validation_rejects_empty_query(client):
    resp = client.post("/v1/parse", json={"query": ""})
    assert resp.status_code == 422
