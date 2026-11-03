"""Which GLiNER model a collection runs, and that the image prefetches the same one."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from search_intent.extractors.gliner2_extractor import BUILTIN_MODEL, model_name
from search_intent.settings import Settings

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "prefetch_models", ROOT / "scripts" / "prefetch_models.py"
)
prefetch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prefetch)


def _gliner(model: str | None = None) -> dict:
    extractor = {"provider": "gliner2"}
    if model:
        extractor["model"] = model
    return {"extractor": extractor, "entities": {}}


def test_extractor_json_model_wins_over_the_default() -> None:
    assert model_name(_gliner("org/from-json"), "org/from-env") == "org/from-json"


def test_default_applies_when_extractor_json_names_no_model() -> None:
    assert model_name(_gliner(), "org/from-env") == "org/from-env"


@pytest.mark.parametrize("default", [None, ""])
def test_builtin_model_when_neither_is_set(default: str | None) -> None:
    # The Dockerfile's empty build arg arrives as "".
    assert model_name(_gliner(), default) == BUILTIN_MODEL


def test_settings_read_gliner2_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLINER2_MODEL", "org/from-env")
    assert Settings().gliner2_model == "org/from-env"


def test_prefetch_resolves_models_like_the_service(tmp_path: Path) -> None:
    configs = {
        "named": _gliner("org/from-json"),
        "unnamed": _gliner(),
        "regex": {"extractor": {"provider": "regex"}, "entities": {}},
    }
    for name, config in configs.items():
        (tmp_path / name).mkdir()
        (tmp_path / name / "extractor.json").write_text(json.dumps(config))

    assert prefetch.referenced_models(tmp_path, "org/from-env") == {
        "org/from-json",
        "org/from-env",
    }
    assert prefetch.referenced_models(tmp_path) == {"org/from-json", BUILTIN_MODEL}


def test_bundled_collections_prefetch_what_they_load() -> None:
    # movietrip names its model, so GLINER2_MODEL doesn't change what it needs.
    assert prefetch.referenced_models(ROOT / "config", "org/unused") == {
        "fastino/gliner2.5-base-v1"
    }
