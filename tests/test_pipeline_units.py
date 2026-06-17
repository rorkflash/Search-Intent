"""Unit tests for core pipeline pieces that need no running app."""

from __future__ import annotations

from search_intent.core import normalize, parse_price
from search_intent.core.intent_detector import IntentDetector
from search_intent.extractors import build_extractor
from search_intent.mappers import template_engine

EXTRACTOR_CONFIG = {
    "extractor": {"provider": "regex", "thresholds": {"entity": 0.35}},
    "entities": {
        "brand": {"examples": ["Nike", "Apple"]},
        "color": {"examples": ["red", "black"]},
        "price": {"examples": ["under $100"]},
    },
}


def test_normalize_collapses_whitespace():
    assert normalize("  red   Nike   shoes ") == "red Nike shoes"


def test_parse_price_max():
    assert parse_price(["under $100"]) == {"max": 100.0}


def test_parse_price_range():
    assert parse_price(["between 50 and 200"]) == {"min": 50.0, "max": 200.0}


def test_regex_extractor_finds_entities():
    extractor = build_extractor(EXTRACTOR_CONFIG)
    result = extractor.extract("red Nike shoes under $100")
    assert result.entities["brand"] == ["Nike"]
    assert result.entities["color"] == ["red"]
    assert result.entities["price"] == ["under $100"]


def test_intent_detector_keyword_match():
    detector = IntentDetector(
        {
            "intents": {
                "search_products": {
                    "keywords": ["buy", "shoes"],
                    "default_objects": ["product"],
                },
                "global_search": {"keywords": [], "default_objects": ["product"]},
            }
        }
    )
    result = detector.detect("buy red shoes")
    assert result.intent == "search_products"
    assert result.confidence > 0.5


def test_template_engine_preserves_types():
    context = {"search_object": {"filters": {"brand_ids": [42]}, "query": "x"}}
    rendered = template_engine.render(
        {"filters": "{{ search_object.filters }}", "q": "id-{{ search_object.query }}"},
        context,
    )
    assert rendered["filters"] == {"brand_ids": [42]}
    assert rendered["q"] == "id-x"
