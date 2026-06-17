"""End-to-end API tests against the bundled example-shop config."""

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
    assert req["method"] == "POST"
    assert req["url"].endswith("/api/search")
    assert req["body"]["filters"]["brand_ids"] == [42]
    # Empty defaults pruned away by endpoint options.
    assert "objects" in req["body"]


def test_generate_cache_hit_on_second_call(client):
    payload = {"query": "black Adidas shoes"}
    first = client.post("/v1/generate", json=payload).json()
    second = client.post("/v1/generate", json=payload).json()
    assert first["cache"]["hit"] is False
    assert second["cache"]["hit"] is True


def test_validation_rejects_empty_query(client):
    resp = client.post("/v1/parse", json={"query": ""})
    assert resp.status_code == 422
