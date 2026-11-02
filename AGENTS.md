# Agent guide: Search Intent

Search Intent turns a free-text search query into a structured request for
another API. All business knowledge lives in JSON config, not in code. This
file explains how to add or change a **collection**: one folder under
`config/` that configures the service for one product.

- `config/default/` is the example shop. It targets DummyJSON and uses the
  regex extractor. `tests/test_api.py` depends on it, so leave it alone unless
  the task is about it.
- `config/movietrip/` is the MovieTrip profile, which uses GLiNER2. It's a
  good model for a real collection.

The service loads one collection at startup, picked by
`SEARCH_INTENT_CONFIG_DIR`. The sandbox (`sandbox/`) loads all of them, which
is the fastest way to test a change (see "Test it" below).

## How a query flows through the config

```text
query
  → normalize
  → intent-map.json      keyword match → intent + objects
  → extractor.json       entities: label → values
  → resolver-map.json    values → IDs (optional, per label)
  → search object        filters, sort, pagination (search-object-schema.json)
  → geo.json             anchor placeless queries on the user (optional)
  → api-map.json         render the target API request
```

`/v1/parse` stops after extraction. `/v1/generate` returns the search object
and the API request. `/v1/search` also sends that request.

## Create a collection

1. **Pick a name.** It must be lowercase letters, digits, `-` and `_`. It
   becomes the folder name.
2. **Start from a copy.** Copying the collection closest to the new one is
   usually less work than starting blank:

   ```bash
   cp -r config/movietrip config/<name>
   ```

   Then set `"name"` and `"display_name"` in `config/<name>/project.json`.
   The sandbox's **New** button does both steps, and it can also create a
   blank collection from minimal starter files.
3. **Edit the files** in the order below.
4. **Check that it loads, then test real queries** (see "Validate" and "Test
   it" below).
5. **Add a test file**, `tests/test_<name>_config.py`.

## The files, in the order to edit them

`project`, `extractor`, `intent-map`, `search-map` and `api-map` are required.
The rest are optional; a missing optional file counts as empty.

### `project.json`

`name` is required. `default_locale` and `supported_locales` describe the
collection.

### `extractor.json`: what to pull out of the query

```json
{
  "extractor": { "provider": "regex" },
  "entities": {
    "city": { "label": "city", "description": "City name", "examples": ["London", "Paris"] }
  }
}
```

- **Keys:** the keys of `entities` are the entity labels used everywhere
  else. They must match the keys in `resolver-map.json`.
- **`provider: "regex"`** needs no model. It matches each entity's `examples`
  as whole words, ignoring case. It also supports these per-entity options:
  - `ambiguous_terms` with `context_words` (and optionally `context_window`,
    default 2): an example that doubles as a common word only counts when a
    context word is nearby.
  - `extract_quoted`: quoted spans in the query become values.
  - `extract_residual` with `residual_stopwords` and `residual_cues`:
    leftover text becomes the value. This is how unknown titles get through.
- **`provider: "gliner2"`** uses the model named in `model`. It is given only
  the entity **keys** as labels, so `description`, `examples` and all of the
  regex options above have no effect. Name the keys in plain words that
  describe the value (`movie_title`, not `mt`). Tune `thresholds.entity`
  instead.
- **Special labels** that the search-object builder treats differently:
  - `price`: phrases like "under $100" become `filters.price = {min, max}`.
  - `year`: phrases like "from 2012 to 2016" become `filters.year_from` and
    `filters.year_to`.
  - `movie_title`: its first value becomes `filters.q`.

  Any other label becomes `filters[<label>] = [values]`, unless a resolver
  maps it to IDs. When nothing at all is extracted, `filters.q` is set to the
  whole query.

### `intent-map.json`: what the user wants

```json
{
  "intents": {
    "search_places": { "keywords": ["place", "places"], "default_objects": ["places"] },
    "global_search": { "keywords": [], "default_objects": ["places", "movies"] }
  }
}
```

- **Required:** `intents` must not be empty.
- **Matching:** the intent with the most keywords found in the query (as
  substrings, ignoring case) wins.
- **Fallback:** when no keyword matches, the first intent with an empty
  `keywords` list wins, or the first intent if none has one. Always include a
  keyword-less fallback, conventionally `global_search`.
- **Objects:** `default_objects` becomes the search object's `objects`. Every
  name listed must exist in `search-map.json`.

### `search-map.json`: the searchable object types

- **Required:** `objects` must not be empty, and it must define every object
  named in an intent's `default_objects`.
- **Other fields:** `aliases`, `entities` and `searchable_fields` describe the
  object but aren't used in code yet.

### `resolver-map.json` (optional): extracted value → ID

```json
{
  "resolvers": {
    "city": { "type": "static", "target": "city_ids", "map": { "london": 15, "cambridge": [3, 4] } }
  }
}
```

- **Keys:** each key is an entity label from `extractor.json`.
- **Result:** the IDs go to `filters[<target>]`, and the raw values are no
  longer added to `filters` under the label itself.
- **`static`:** looks the value up in `map`, ignoring case. A value can map to
  a list of IDs. Values not in `map` are dropped.
- **`http`:** calls a URL read from an env var (`url_from_env`) and picks the
  IDs with the JSONPath in `result_path`. Never put the URL or a token in
  JSON.

### `api-map.json`: the request to send

- **Required:** at least one entry in `endpoints`.
- **Routing:** `intent_endpoint_map` picks the endpoint for each intent;
  unmapped intents use the first endpoint. Every endpoint it names must exist.
- **`api.mode`:** one of these values:
  - `generate_only` (the default): the request is built but never sent.
  - `execute` or `generate_and_execute`: `/v1/search` sends the request.
- **Base URL:** `base_url` sets it directly; `base_url_from_env` names an env
  var that holds it.
- **Outbound auth:** `auth` takes `{"type": "bearer_token", "token_from_env":
  ...}` or `{"type": "api_key", "key_from_env": ..., "header": ...}`.
- **Placeholders:** `headers`, `query` and `body` values can use `{{ ... }}`
  with paths into the search object:
  - A value that is only a placeholder, like `"{{ search_object.filters }}"`,
    keeps the original type (object, list or number).
  - A placeholder inside a longer string is substituted as text.
  - `{{ a | b }}` uses the first value that isn't empty.
  - `.first` takes the first item of a list, as in
    `{{ search_object.filters.city_ids.first }}`.
- **Pruning:** set `options.remove_null_values`, `remove_empty_arrays` and
  `remove_empty_objects` to drop unfilled fields from the body.

### Other optional files

| File | Purpose | Reference |
| --- | --- | --- |
| `search-object-schema.json` | `defaults.sort` and `defaults.pagination` (otherwise limit 20, offset 0) | README |
| `geo.json` | Scopes queries that name no place to the user's location | README `geo.json` section, `config/movietrip/geo.json` |
| `cache.json` | Redis or in-memory cache settings | `config/default/cache.json` |
| `auth-inbound.json` | Turns on JWT auth for incoming requests | README `auth-inbound.json` section |

## Validate

This loads the collection exactly as the service does at startup. It prints
the warnings (an empty list is clean) or raises the error that would stop the
service from starting:

```bash
uv run python -c "from search_intent.config import load_config, validate_config; print(validate_config(load_config('config/<name>')))"
```

Treat every warning as a bug. Warnings report unknown objects in
`default_objects` and unknown endpoints in `intent_endpoint_map`.

## Test it

**With the sandbox (no restart between edits).** Start it in the background:

```bash
uv run python -m sandbox --no-browser
```

Then use its HTTP API on `http://127.0.0.1:8090`:

```bash
# validation status of a collection
curl -s http://127.0.0.1:8090/api/collections/<name>

# run a query: mode is parse | generate | search
curl -s -X POST http://127.0.0.1:8090/api/collections/<name>/run \
  -H 'Content-Type: application/json' \
  -d '{"query": "Harry Potter places in London", "mode": "generate"}'
```

- **Edits:** you can edit the files on disk directly. The next run notices
  the change and rebuilds the collection, so there's no need to restart.
- **No cache:** caching is off in the sandbox, so results always reflect the
  current config.
- **Output:** for `generate` and `search`, the response includes `stages`,
  which shows the intent and extracted entities.
- **Prefer `generate`:** `search` calls the target API for real.
- **Model load:** the first GLiNER2 run in a process takes about 10 s while
  the model loads.

**With the service:**

```bash
SEARCH_INTENT_CONFIG_DIR=./config/<name> uv run python -m search_intent
```

```bash
curl -s -X POST http://localhost:8080/v1/generate -H 'Content-Type: application/json' -d '{"query": "..."}'
```

**Automated tests.** Copy the fixture from `tests/test_movietrip_config.py`
and point it at your collection:

```python
@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SEARCH_INTENT_CONFIG_DIR", "config/<name>")
    with TestClient(create_app()) as c:
        yield c
```

Cover at least one query per intent, each special label you rely on, and
every ambiguous term (once with context, once without).

```bash
uv run --extra dev pytest tests/test_<name>_config.py -q
```

```bash
uv run --extra dev ruff check .
```

## Rules

- **Config only.** Business vocabulary, labels and IDs go in JSON, never in
  `search_intent/`. If a collection seems to need a code change, say so
  rather than adding a special case.
- **No secrets in JSON.** URLs that vary by environment, tokens and keys go
  in env vars (`*_from_env`), documented in `.env.example`.
- **Keep the formatting.** Edit JSON files in place with 2-space indentation.
  Don't rewrite whole files, so `git diff` stays readable.
- **Don't break the others.** Changing one collection must not touch another.
  Run the full suite (`uv run --extra dev pytest -q`) before you finish.
