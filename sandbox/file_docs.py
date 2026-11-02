"""What each config file is for, shown next to the file in the sandbox.

Kept in step with search_intent.config.loader.CONFIG_FILES; a test fails if
a config file has no entry here. AGENTS.md and the README go deeper.
"""

from __future__ import annotations

from typing import Any

# purpose: a few words for the sidebar.
# summary: what the file does and where it sits in the pipeline.
# keys:    the fields worth knowing, as (key, meaning).
# notes:   gotchas that aren't obvious from the keys.
FILE_DOCS: dict[str, dict[str, Any]] = {
    "project": {
        "purpose": "Name and locales",
        "summary": (
            "Identifies the collection. The service reports `name` on /health and uses "
            "it in logs."
        ),
        "keys": [
            ("name", "Required. Usually the same as the folder name."),
            ("display_name", "Human-readable name."),
            ("version", "Your own version label for this collection."),
            ("default_locale", "The collection's main locale."),
            ("supported_locales", "Locales this collection is written for."),
        ],
        "notes": [
            "The locale fields are informational today: a request without `locale` is "
            "treated as `en` whatever they say.",
        ],
    },
    "extractor": {
        "purpose": "Entities to pull out",
        "summary": (
            "Step 2 of the pipeline. Defines the entities to find in a query (city, "
            "brand, price…) and how to find them. Each key under `entities` is a label "
            "that other files refer to."
        ),
        "keys": [
            ("extractor.provider", "`regex` (no model, uses examples) or `gliner2` (ML model)."),
            ("extractor.model", "GLiNER2 model name, e.g. `fastino/gliner2-base-v1`."),
            ("extractor.thresholds.entity", "GLiNER2 confidence cut-off (default 0.35)."),
            ("entities.<label>.examples", "Regex only: words matched as whole words, any case."),
            (
                "entities.<label>.ambiguous_terms + context_words",
                "Regex only: an example that is also a common word counts only when a "
                "context word is within `context_window` tokens (default 2).",
            ),
            ("entities.<label>.extract_quoted", "Regex only: quoted text becomes a value."),
            (
                "entities.<label>.extract_residual",
                "Regex only: text left after other matches and `residual_stopwords` "
                "becomes the value (for open-ended titles).",
            ),
        ],
        "notes": [
            "GLiNER2 is given only the label names, so `description`, `examples` and the "
            "regex-only options have no effect with it. Name labels in plain words.",
            "Special labels: `price` becomes `filters.price {min,max}`, `year` becomes "
            "`filters.year_from`/`year_to`, and the first `movie_title` becomes `filters.q`.",
        ],
    },
    "intent-map": {
        "purpose": "What the user wants",
        "summary": (
            "Step 1 of the pipeline. Picks the query's intent by keyword and, from it, "
            "which objects to search."
        ),
        "keys": [
            ("intents", "Required, at least one."),
            (
                "intents.<name>.keywords",
                "Substrings looked for in the query, ignoring case. The intent with the "
                "most matches wins.",
            ),
            (
                "intents.<name>.default_objects",
                "Becomes the search object's `objects`. Each must exist in search-map.json.",
            ),
            ("intents.<name>.description", "For people; not used in code."),
        ],
        "notes": [
            "When no keyword matches, the first intent with an empty `keywords` list wins "
            "(else the first intent). Keep one, conventionally `global_search`.",
        ],
    },
    "search-map": {
        "purpose": "Searchable object types",
        "summary": (
            "Lists the kinds of things that can be searched (products, places, movies…). "
            "Intents refer to these by name."
        ),
        "keys": [
            ("objects", "Required, at least one. Must include every object an intent names."),
            ("objects.<name>.aliases", "Other words for the object."),
            ("objects.<name>.entities", "Entity labels that apply to the object."),
            ("objects.<name>.searchable_fields", "Fields the target API searches."),
        ],
        "notes": [
            "Only the object names are used by code today. `aliases`, `entities` and "
            "`searchable_fields` describe the object for people.",
        ],
    },
    "search-object-schema": {
        "purpose": "Sort and paging defaults",
        "summary": (
            "Default sort and pagination for every search object. The `schema` part "
            "documents the search object's shape."
        ),
        "keys": [
            ("defaults.sort", "e.g. `{\"by\": \"relevance\", \"direction\": \"desc\"}`."),
            (
                "defaults.pagination",
                "e.g. `{\"limit\": 20, \"offset\": 0}`. A request's limit/offset override it.",
            ),
            ("schema", "JSON Schema of the search object, for reference."),
        ],
        "notes": [
            "Without this file, sort is empty and pagination is limit 20, offset 0.",
            "Only `defaults` is applied; `schema` is not checked at runtime.",
        ],
    },
    "resolver-map": {
        "purpose": "Values to IDs",
        "summary": (
            "Step 3 of the pipeline. Turns extracted values into your system's IDs, e.g. "
            "\"London\" → 15. Each key is an entity label from extractor.json."
        ),
        "keys": [
            ("resolvers.<label>.type", "`static` (lookup table here) or `http` (call an API)."),
            ("resolvers.<label>.target", "Filter name the IDs go to, e.g. `city_ids`."),
            (
                "resolvers.<label>.map",
                "Static: value → ID or list of IDs. Lookup ignores case.",
            ),
            (
                "resolvers.<label>.url_from_env / result_path",
                "HTTP: env var holding the URL, and the JSONPath that picks IDs from "
                "the response.",
            ),
        ],
        "notes": [
            "`cache_ttl_seconds` is accepted but unused: resolved IDs are cached for the "
            "`resolved_entity` TTL in cache.json.",
            "A resolved label is replaced by its `target` in filters. Values a resolver "
            "can't find are dropped.",
            "Labels with no resolver go into filters as-is: `filters.<label> = [values]`.",
        ],
    },
    "api-map": {
        "purpose": "Request to your API",
        "summary": (
            "Last step. Builds the target API request from the search object, and decides "
            "whether /v1/search sends it."
        ),
        "keys": [
            (
                "api.mode",
                "`generate_only` (default, never sent), `execute` or "
                "`generate_and_execute` (/v1/search sends it).",
            ),
            ("api.base_url / base_url_from_env", "Base URL, or the env var that holds it."),
            (
                "api.auth",
                "Outbound auth: `bearer_token` with `token_from_env`, or `api_key` with "
                "`key_from_env` and `header`.",
            ),
            ("endpoints", "Required, at least one: `method`, `path`, `headers`, `query`, `body`."),
            ("intent_endpoint_map", "Intent → endpoint. Unmapped intents use the first endpoint."),
            (
                "endpoints.<name>.options",
                "`remove_null_values`, `remove_empty_arrays`, `remove_empty_objects` prune "
                "the body.",
            ),
        ],
        "notes": [
            "Placeholders: `\"{{ search_object.filters }}\"` alone keeps the value's type; "
            "inside a longer string it's text. `{{ a | b }}` takes the first non-empty "
            "value, `.first` the first list item.",
            "Never put tokens or keys here; use the `*_from_env` fields.",
        ],
    },
    "cache": {
        "purpose": "Caching",
        "summary": "Caches search objects and resolved IDs in memory or Redis.",
        "keys": [
            ("cache.enabled", "Turn caching on or off."),
            ("cache.backend", "`memory`, or `redis` (needs `REDIS_URL`; falls back to memory)."),
            ("cache.namespace / project_version.value", "Prefix every key; bump the version to "
             "invalidate everything."),
            ("cache.keys.<kind>", "Key `pattern` and `ttl_seconds` per kind of cached value."),
        ],
        "notes": [
            "The sandbox always runs with caching off, so edits show up straight away.",
        ],
    },
    "auth-inbound": {
        "purpose": "Who may call the service",
        "summary": "Optional JWT auth for requests coming into the service.",
        "keys": [
            ("inbound_auth.enabled", "Off means anyone can call the API."),
            ("inbound_auth.type / plugin", "Auth type (`jwt`) and the plugin that checks it."),
            ("inbound_auth.token_source", "Where the token is read, e.g. Authorization."),
            ("inbound_auth.jwt", "Algorithm, and env vars for secret, issuer and audience."),
            ("inbound_auth.authorization", "Permissions the token must carry."),
        ],
        "notes": [
            "The sandbox skips inbound auth entirely.",
            "Secrets come from env vars (`*_from_env`), never this file.",
        ],
    },
    "geo": {
        "purpose": "Location fallback",
        "summary": (
            "Scopes a query that names no place to a box around the user, e.g. \"cafe "
            "places\" searches near them. A query that names a city or country is never "
            "re-scoped."
        ),
        "keys": [
            ("geo.enabled", "Off unless set. No file means no geo fallback."),
            ("geo.radius_km", "Radius for a query that named no place."),
            ("geo.cue_radius_km", "Smaller radius when the query says \"near me\"."),
            ("geo.cues", "Phrases that ask for a nearby search."),
            ("geo.blocking_filters / blocking_entities", "Filters or labels that mean the "
             "query already named a place."),
            ("geo.headers / header_fallback", "Proxy headers to read the position from when the "
             "request body has none."),
            ("geo.retry_without_geo_when_empty", "Re-run without the box when it found nothing."),
        ],
        "notes": [
            "The box lands in `search_object.geo.bbox`; api-map.json decides which API "
            "fields it maps to. In the tester, set Lat and Lng to try it.",
        ],
    },
}
