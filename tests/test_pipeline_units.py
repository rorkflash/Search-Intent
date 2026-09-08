"""Unit tests for core pipeline pieces that need no running app."""

from __future__ import annotations

from search_intent.core import normalize, parse_price, parse_year
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


def test_parse_year_range():
    assert parse_year(["from 2012 to 2016"]) == {"year_from": 2012, "year_to": 2016}


def test_parse_year_since():
    assert parse_year(["since 2010"]) == {"year_from": 2010}


def test_regex_extractor_finds_entities():
    extractor = build_extractor(EXTRACTOR_CONFIG)
    result = extractor.extract("red Nike shoes under $100")
    assert result.entities["brand"] == ["Nike"]
    assert result.entities["color"] == ["red"]
    assert result.entities["price"] == ["under $100"]


AMBIGUOUS_EXTRACTOR_CONFIG = {
    "extractor": {"provider": "regex", "thresholds": {"entity": 0.35}},
    "entities": {
        "location_type": {
            "examples": ["bank", "museum"],
            "ambiguous_terms": ["bank"],
            "context_words": ["location", "place"],
            "context_window": 2,
        },
    },
}


def test_regex_extractor_skips_ambiguous_term_without_context():
    extractor = build_extractor(AMBIGUOUS_EXTRACTOR_CONFIG)
    result = extractor.extract("bank of America movie")
    assert "location_type" not in result.entities


def test_regex_extractor_matches_ambiguous_term_with_nearby_context():
    extractor = build_extractor(AMBIGUOUS_EXTRACTOR_CONFIG)
    result = extractor.extract("find a bank location nearby")
    assert result.entities["location_type"] == ["bank"]


def test_regex_extractor_still_matches_unambiguous_term_freely():
    extractor = build_extractor(AMBIGUOUS_EXTRACTOR_CONFIG)
    result = extractor.extract("museum scenes from Inception")
    assert result.entities["location_type"] == ["museum"]


def test_regex_extractor_captures_quoted_title():
    extractor = build_extractor(
        {
            "extractor": {"provider": "regex"},
            "entities": {
                "movie_title": {
                    "examples": ["Inception"],
                    "extract_quoted": True,
                }
            },
        }
    )
    result = extractor.extract("the scenes of 'Inferno' movie")
    assert result.entities["movie_title"] == ["Inferno"]


RESIDUAL_TITLE_CONFIG = {
    "extractor": {"provider": "regex"},
    "entities": {
        "genre": {"examples": ["action", "fantasy"]},
        "city": {"examples": ["Paris"]},
        "movie_title": {
            "examples": [],
            "extract_residual": True,
            "residual_cues": ["movie", "movies", "scene", "scenes"],
            "residual_stopwords": [
                "movie",
                "movies",
                "scene",
                "scenes",
                "filmed",
                "like",
                "from",
                "set",
            ],
        },
    },
}


def test_regex_extractor_residual_unquoted_title():
    extractor = build_extractor(RESIDUAL_TITLE_CONFIG)
    result = extractor.extract("the scenes of Inferno movie")
    assert result.entities["movie_title"] == ["Inferno"]


def test_regex_extractor_residual_keeps_multiword_title():
    extractor = build_extractor(RESIDUAL_TITLE_CONFIG)
    result = extractor.extract("fantasy movies like Lord of the Rings")
    assert result.entities["genre"] == ["fantasy"]
    assert result.entities["movie_title"] == ["Lord of the Rings"]


def test_regex_extractor_residual_skips_when_no_title_cue():
    extractor = build_extractor(RESIDUAL_TITLE_CONFIG)
    result = extractor.extract("planning a trip to Paris next month")
    assert "movie_title" not in result.entities
    assert result.entities["city"] == ["Paris"]


def test_template_engine_fallback_picks_first_non_empty():
    context = {"search_object": {"filters": {}, "query": "Inferno scenes"}}
    rendered = template_engine.render(
        {"q": "{{ search_object.filters.movie_title.first | search_object.query }}"},
        context,
    )
    assert rendered["q"] == "Inferno scenes"


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
