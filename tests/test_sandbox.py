"""Tests for the sandbox app (sandbox/), run against a temp copy of config/default."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sandbox.file_docs import FILE_DOCS
from sandbox.server import create_app
from search_intent.config.loader import CONFIG_FILES

DEFAULT = Path(__file__).resolve().parent.parent / "config" / "default"


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    shutil.copytree(DEFAULT, tmp_path / "default")
    return tmp_path


@pytest.fixture()
def sandbox(root: Path) -> TestClient:
    with TestClient(create_app(root)) as c:
        yield c


def _run(client: TestClient, name: str, query: str, mode: str = "generate") -> dict:
    resp = client.post(f"/api/collections/{name}/run", json={"query": query, "mode": mode})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_lists_collections_with_validation(sandbox: TestClient) -> None:
    resp = sandbox.get("/api/collections")
    assert resp.status_code == 200
    [default] = resp.json()
    assert default["name"] == "default"
    assert default["protected"] is True
    assert default["validation"] == {"ok": True, "error": None, "warnings": []}
    files = {f["stem"]: f for f in default["files"]}
    assert files["project"]["present"] and files["project"]["required"]
    assert not files["geo"]["present"]


def test_every_config_file_is_described(sandbox: TestClient) -> None:
    # A new entry in CONFIG_FILES needs a description in sandbox/file_docs.py.
    assert set(FILE_DOCS) == set(CONFIG_FILES)
    for stem, doc in FILE_DOCS.items():
        assert doc["purpose"] and doc["summary"], stem

    [default] = sandbox.get("/api/collections").json()
    assert all(f["doc"]["purpose"] for f in default["files"])


def test_serves_the_ui(sandbox: TestClient) -> None:
    resp = sandbox.get("/")
    assert resp.status_code == 200
    assert "Search Intent Sandbox" in resp.text


def test_generate_returns_output_and_parse_stage(sandbox: TestClient) -> None:
    body = _run(sandbox, "default", "red Nike shoes under $100")
    assert body["mode"] == "generate"
    assert body["stages"]["entities"]["brand"] == ["Nike"]
    assert body["output"]["search_object"]["filters"]["brand_ids"] == [42]
    assert body["output"]["api_request"]["url"] == "https://dummyjson.com/products/search"


def test_parse_mode_has_no_separate_stage(sandbox: TestClient) -> None:
    body = _run(sandbox, "default", "red Nike shoes", mode="parse")
    assert body["stages"] is None
    assert body["output"]["intent"] == "search_products"


def test_saved_edit_shows_up_in_the_next_run(sandbox: TestClient, root: Path) -> None:
    # Warm the pipeline (and what would be its cache) before editing.
    assert _run(sandbox, "default", "red Nike shoes")["output"]["search_object"]["resolved"][
        "brand_ids"
    ] == [42]

    path = root / "default" / "resolver-map.json"
    data = json.loads(path.read_text())
    data["resolvers"]["brand"]["map"]["nike"] = 99
    resp = sandbox.put(
        "/api/collections/default/files/resolver-map", json={"text": json.dumps(data, indent=2)}
    )
    assert resp.status_code == 200
    assert resp.json()["validation"]["ok"] is True

    assert _run(sandbox, "default", "red Nike shoes")["output"]["search_object"]["resolved"][
        "brand_ids"
    ] == [99]


def test_edit_on_disk_shows_up_in_the_next_run(sandbox: TestClient, root: Path) -> None:
    _run(sandbox, "default", "red Nike shoes")

    path = root / "default" / "resolver-map.json"
    path.write_text(path.read_text().replace('"nike": 42', '"nike": 77'))

    assert _run(sandbox, "default", "red Nike shoes")["output"]["search_object"]["resolved"][
        "brand_ids"
    ] == [77]


def test_save_keeps_the_text_as_sent(sandbox: TestClient, root: Path) -> None:
    text = '{"name": "default", "display_name": "Shop",   "version": "1.0.0"}'
    resp = sandbox.put("/api/collections/default/files/project", json={"text": text})
    assert resp.status_code == 200
    assert (root / "default" / "project.json").read_text() == text + "\n"


def test_invalid_json_is_refused_and_file_untouched(sandbox: TestClient, root: Path) -> None:
    before = (root / "default" / "project.json").read_text()
    resp = sandbox.put("/api/collections/default/files/project", json={"text": '{"name": '})
    assert resp.status_code == 400
    assert "Invalid JSON" in resp.json()["detail"]
    assert (root / "default" / "project.json").read_text() == before


def test_structural_error_is_saved_and_reported(sandbox: TestClient) -> None:
    resp = sandbox.put(
        "/api/collections/default/files/intent-map", json={"text": '{"intents": {}}'}
    )
    assert resp.status_code == 200
    validation = resp.json()["validation"]
    assert validation["ok"] is False
    assert "intent-map.json" in validation["error"]

    run = sandbox.post("/api/collections/default/run", json={"query": "shoes"})
    assert run.status_code == 422


def test_create_blank_collection_loads_and_runs(sandbox: TestClient, root: Path) -> None:
    resp = sandbox.post("/api/collections", json={"name": "shop-2"})
    assert resp.status_code == 201
    assert resp.json()["validation"]["ok"] is True
    assert json.loads((root / "shop-2" / "project.json").read_text())["name"] == "shop-2"

    body = _run(sandbox, "shop-2", "anything at all")
    assert body["output"]["intent"] == "global_search"
    assert body["output"]["api_request"]["query"] == {"q": "anything at all"}


def test_duplicate_collection_renames_project(sandbox: TestClient, root: Path) -> None:
    resp = sandbox.post("/api/collections", json={"name": "shop-copy", "copy_from": "default"})
    assert resp.status_code == 201
    project = json.loads((root / "shop-copy" / "project.json").read_text())
    assert project["name"] == "shop-copy"
    assert (root / "shop-copy" / "resolver-map.json").read_text() == (
        root / "default" / "resolver-map.json"
    ).read_text()

    assert sandbox.post("/api/collections", json={"name": "shop-copy"}).status_code == 409


@pytest.mark.parametrize("name", ["../escape", "Upper", "has space", "", ".hidden"])
def test_bad_collection_names_are_refused(sandbox: TestClient, name: str) -> None:
    resp = sandbox.post("/api/collections", json={"name": name})
    assert resp.status_code == 400


def test_unknown_file_and_collection(sandbox: TestClient) -> None:
    assert sandbox.get("/api/collections/default/files/secrets").status_code == 404
    assert sandbox.get("/api/collections/nope").status_code == 404


def test_optional_file_can_be_added_and_removed(sandbox: TestClient, root: Path) -> None:
    geo = '{"geo": {"enabled": false}}'
    assert sandbox.put("/api/collections/default/files/geo", json={"text": geo}).status_code == 200
    assert (root / "default" / "geo.json").is_file()

    resp = sandbox.delete("/api/collections/default/files/geo")
    assert resp.status_code == 200
    assert not (root / "default" / "geo.json").exists()

    assert sandbox.delete("/api/collections/default/files/project").status_code == 400


def test_delete_collection(sandbox: TestClient, root: Path) -> None:
    sandbox.post("/api/collections", json={"name": "scratch"})
    assert sandbox.delete("/api/collections/scratch").status_code == 204
    assert not (root / "scratch").exists()

    assert sandbox.delete("/api/collections/default").status_code == 400
