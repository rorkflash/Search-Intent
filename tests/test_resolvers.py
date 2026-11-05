"""Tests for the resolvers, especially the http resolver's name matching."""

from __future__ import annotations

import pytest

from search_intent.resolvers import HttpResolver, StaticResolver, build_resolvers
from search_intent.resolvers.http_resolver import names_match, normalize_name

# What /v1/movies?q=harry+potter actually answers: the endpoint also matches
# director and actor, so the list holds films that are not the one asked for.
MOVIE_ROWS = [
    {"id": 354, "title": "Harry Potter and the Prisoner of Azkaban"},
    {"id": 345, "title": "Harry Potter and the Order of the Phoenix"},
    {"id": 235, "title": "The Third Man"},
]


def resolver(**spec) -> HttpResolver:
    return HttpResolver("movie_title", {"type": "http", "url": "http://x", **spec})


def test_normalize_name_drops_accents_and_punctuation():
    assert normalize_name("Amélie's Café — 2001!") == "amelie s cafe 2001"


def test_normalize_name_collapses_whitespace():
    assert normalize_name("  Harry   Potter ") == "harry potter"


def test_names_match_exact():
    assert names_match("Sherlock", "sherlock", "exact")
    assert not names_match("Sherlock", "Sherlock Holmes", "exact")


def test_names_match_contains_both_ways():
    # The query may shorten a title, or spell out more of it than the catalog.
    assert names_match("Harry Potter", "Harry Potter and the Goblet of Fire", "contains")
    assert names_match("Sherlock Holmes (2009)", "Sherlock Holmes", "contains")
    assert not names_match("action movies", "The Secret Life of Walter Mitty", "contains")


def test_names_match_prefix():
    assert names_match("Sherlock", "Sherlock Holmes", "prefix")
    assert not names_match("Holmes", "Sherlock Holmes", "prefix")


def test_names_match_ignores_empty_sides():
    assert not names_match("", "Sherlock", "contains")
    assert not names_match("Sherlock", "", "contains")


def test_names_match_rejects_unknown_mode():
    with pytest.raises(ValueError):
        names_match("a", "a", "fuzzy")


def test_filter_candidates_keeps_only_real_title_matches():
    policy = resolver(match={"field": "title", "mode": "contains"})
    assert policy._filter_candidates("Harry Potter", MOVIE_ROWS) == [354, 345]


def test_filter_candidates_drops_a_phrase_that_is_not_a_title():
    policy = resolver(match={"field": "title", "mode": "contains"})
    assert policy._filter_candidates("action movies", MOVIE_ROWS) == []


def test_filter_candidates_dedupes_and_honors_limit():
    policy = resolver(match={"field": "title", "mode": "contains", "limit": 1})
    rows = [*MOVIE_ROWS, {"id": 354, "title": "Harry Potter and the Prisoner of Azkaban"}]
    assert policy._filter_candidates("Harry Potter", rows) == [354]

    unlimited = resolver(match={"field": "title", "mode": "contains"})
    assert unlimited._filter_candidates("Harry Potter", rows) == [354, 345]


def test_filter_candidates_skips_rows_without_the_fields():
    policy = resolver(match={"field": "title", "mode": "contains", "id_field": "movie_id"})
    rows = [
        {"title": "Harry Potter and the Goblet of Fire"},  # no id
        {"movie_id": 1},  # no title
        "Harry Potter",  # not an object at all
        {"movie_id": 7, "title": "Harry Potter and the Chamber of Secrets"},
    ]
    assert policy._filter_candidates("Harry Potter", rows) == [7]


def test_without_a_match_block_result_path_selects_ids():
    plain = resolver(result_path="$.data[*].id")
    assert plain.match_field is None


def test_http_resolver_without_url_resolves_to_nothing():
    plain = HttpResolver("movie_title", {"type": "http", "url_from_env": "NOT_SET_ANYWHERE"})
    assert plain.url is None


def test_build_resolvers_reads_both_types():
    resolvers = build_resolvers(
        {
            "resolvers": {
                "city": {"type": "static", "target": "city_ids", "map": {"london": 15}},
                "movie_title": {
                    "type": "http",
                    "target": "movie_ids",
                    "url": "http://x/v1/movies",
                    "match": {"field": "title", "mode": "contains"},
                },
            }
        }
    )
    assert isinstance(resolvers["city"], StaticResolver)
    assert isinstance(resolvers["movie_title"], HttpResolver)
    assert resolvers["movie_title"].target == "movie_ids"
    assert resolvers["movie_title"].match_mode == "contains"
