# Search Intent

**Search Intent** is an open-source microservice that converts natural-language search queries into structured API requests.

It helps you turn a search box like this:

```text
"red shoes under $100 from Nike"
"2 bedroom apartments in Berlin near metro"
"Harry Potter places in London"
"documents about payment API errors"
```

into a clean, predictable request your backend API can execute.

```text
Natural-language query
        ↓
Search Intent
        ↓
Structured Search Object
        ↓
Target API Request
```

Search Intent is **not a search engine**. It is a configurable intent and API-request generation layer that sits in front of your existing search API.

---

## Why Use Search Intent?

Most applications eventually need smarter search.

Users write:

```text
"popular restaurants in Paris open now"
```

But your API expects:

```json
{
  "filters": {
    "city": "Paris",
    "type": "restaurant",
    "open_now": true
  },
  "sort": "popularity"
}
```

Search Intent bridges that gap.

It can be used for:

- e-commerce search
- travel search
- real estate search
- movie/location search
- restaurant search
- document search
- marketplace search
- internal admin search
- SaaS dashboard search
- directory search

---

## Core Idea

Search Intent converts:

```text
open text query
```

into:

```text
SearchIntentCommand
```

Example input:

```json
{
  "query": "Harry Potter places in London",
  "locale": "en"
}
```

Example output:

```json
{
  "intent": "search_places",
  "objects": ["place", "scene", "movie"],
  "entities": {
    "movie_title": ["Harry Potter"],
    "city": ["London"]
  },
  "resolved": {
    "movie_ids": [12],
    "city_ids": [44]
  },
  "api_request": {
    "method": "POST",
    "url": "https://api.example.com/search",
    "body": {
      "scope": ["place", "scene", "movie"],
      "filters": {
        "movie_ids": [12],
        "city_ids": [44]
      },
      "pagination": {
        "limit": 20,
        "offset": 0
      }
    }
  }
}
```

---

## How It Works

```text
Client / Gateway
     ↓
Search Intent API
     ↓
Query Normalizer
     ↓
Intent + Entity Extractor
     ↓
Search Object Builder
     ↓
Entity Resolver
     ↓
Cache Layer
     ↓
API Mapper
     ↓
Generated API Request
     ↓
Optional Target API Execution
```

Search Intent can be used in two modes:

1. **Generate only** — return the generated API request and let your backend execute it.
2. **Generate and execute** — generate the API request, call your target API, and return the response.

---

## Design Philosophy

```text
One running Search Intent service = one project/domain/API contract
```

The codebase is reusable and project-agnostic. Each deployed service instance loads one active project configuration.

Examples:

```text
Shop Search Intent service
  → shop config
  → shop search API

Real Estate Search Intent service
  → real estate config
  → real estate search API

Movie Location Search Intent service
  → movie/location config
  → movie/location API
```

---

## Features

- Natural-language query parsing
- Configurable intent detection
- Configurable entity extraction
- GLiNER2 and GLiNER2.5 extractors, plus a regex extractor that needs no model
- JSON-based project configuration
- Search object generation
- API request generation
- Static and HTTP entity resolvers
- Near-me fallback for queries that name no place
- Redis caching support
- Optional API execution mode
- Inbound JWT authentication
- Outbound API authentication
- Local sandbox for editing and testing collections
- Benchmark for comparing extractor models
- Project-agnostic core
- Docker-ready structure

---

## Quick Start

The project uses [uv](https://docs.astral.sh/uv/).

### 1. Clone the repository

```bash
git clone https://github.com/rorkflash/Search-Intent.git
cd Search-Intent
```

### 2. Create environment file

```bash
cp .env.example .env
```

The defaults run the bundled example shop (`config/default`), which needs no
model, no Redis and no API keys.

### 3. Install dependencies

```bash
uv sync
```

### 4. Run the service

```bash
uv run python -m search_intent
```

### 5. Test it

```bash
curl -X POST http://localhost:8080/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "red Nike shoes under $100",
    "locale": "en"
  }'
```

### 6. Try another collection

To run the MovieTrip collection, set `SEARCH_INTENT_CONFIG_DIR`. It uses a
GLiNER2.5 model, so the first start downloads about 750 MB into
`MODEL_CACHE_DIR`:

```bash
SEARCH_INTENT_CONFIG_DIR=./config/movietrip uv run python -m search_intent
```

To browse, edit and test every collection in a browser, use the
[sandbox](#sandbox):

```bash
uv run python -m sandbox
```

---

## Docker

```bash
docker compose up --build
```

Health check:

```bash
curl http://localhost:8080/health
```

The image has the models its collections need built in, and it runs without
access to the Hugging Face Hub. `docker-compose.yml` runs `config/default`; set
`SEARCH_INTENT_CONFIG_DIR` to run another collection.

---

## Project Structure

```text
Search-Intent/
  README.md
  AGENTS.md                 # guide to creating a collection (CLAUDE.md imports it)
  LICENSE
  pyproject.toml
  uv.lock
  Dockerfile
  docker-compose.yml
  .env.example

  search_intent/            # the service
    main.py
    settings.py
    models.py

    api/
      routes_parse.py
      routes_generate.py
      routes_search.py
      routes_health.py
      deps.py
      docs.py

    core/
      pipeline.py
      normalizer.py
      intent_detector.py
      search_object_builder.py
      geo.py

    extractors/
      base.py
      gliner2_extractor.py
      regex_extractor.py

    mappers/
      api_mapper.py
      template_engine.py
      request_builder.py
      executor.py

    resolvers/
      base.py
      http_resolver.py
      static_resolver.py

    auth/
      base.py
      middleware.py
      jwt.py

    cache/
      base.py
      manager.py
      redis_cache.py
      memory_cache.py

    config/
      loader.py
      validator.py

    plugins/                # base interfaces for plugins

  config/                   # one folder per collection
    default/                # example shop, targets DummyJSON
    movietrip/              # MovieTrip profile

  sandbox/                  # local web app for collections, not in the image
  benchmarks/extractor/     # compares extractor models on labelled queries
  plugins/auth/jwt_auth.py  # example plugin
  scripts/prefetch_models.py  # bakes models into the Docker image
  tests/
```

---

## Configuration

Search Intent is configured with JSON files.

Each config lives in its own folder under `config/` (a *collection*). The
service loads one of them, picked by `SEARCH_INTENT_CONFIG_DIR`
(default `./config/default`):

```text
config/
  default/      # example shop, targets DummyJSON
  movietrip/    # MovieTrip profile
```

A collection folder holds these files. `project`, `extractor`, `intent-map`,
`search-map` and `api-map` are required, and the rest are optional:

```text
config/<collection>/
  project.json
  extractor.json
  search-map.json
  intent-map.json
  search-object-schema.json
  api-map.json
  resolver-map.json
  cache.json
  auth-inbound.json
  geo.json
```

To add a collection, copy the closest existing one:

```bash
cp -r config/movietrip config/my-collection
```

Then set `name` in its `project.json`. [AGENTS.md](AGENTS.md) walks through the
rest, file by file. To browse, edit, create and test collections in a browser,
use the [sandbox](#sandbox).

---

## `project.json`

Defines basic project metadata.

```json
{
  "name": "example-shop",
  "display_name": "Example Shop",
  "version": "1.0.0",
  "default_locale": "en",
  "supported_locales": ["en"]
}
```

The service reports `name` on `/health`. The locale fields are informational
for now: a request without `locale` is treated as `en`.

---

## `extractor.json`

Defines the entities to find in a query and how to find them. The keys of
`entities` are labels that the other config files refer to. The core engine does
not hardcode business labels.

### With a GLiNER model

```json
{
  "version": "1.0.0",
  "extractor": {
    "provider": "gliner2",
    "model": "fastino/gliner2.5-base-v1",
    "thresholds": {
      "entity": 0.35
    }
  },
  "entities": {
    "product": {
      "label": "product",
      "model_description": "Product name or product type"
    },
    "brand": {
      "label": "brand",
      "model_description": "Product brand or manufacturer"
    },
    "price": {
      "label": "price",
      "model_description": "Price, price limit, or price range"
    }
  }
}
```

- **`model`** can be a GLiNER2 checkpoint (such as `fastino/gliner2-base-v1`)
  or a GLiNER2.5 one (such as `fastino/gliner2.5-base-v1`). Both load through
  `AutoExtractor`. When it's left out, the collection uses the `GLINER2_MODEL`
  env var, or `fastino/gliner2-base-v1` if that isn't set either.
- **What the model sees:** the label name, plus the entity's
  `model_description` when it has one. Keep that to one short line written
  for the model, for example `"Movie genre, such as comedy, horror or
  western"`.
- **`description`** is for people and is not sent to the model.
- **`examples`** and the regex-only options below are ignored.
- **Model cache:** a model already in `MODEL_CACHE_DIR` loads from disk without
  contacting the Hub. To pick up a newer revision, delete it from there.
- **Docker:** the image runs offline and only has the models baked in at build
  time. If a collection relies on `GLINER2_MODEL`, set it as a build arg
  (`docker build --build-arg GLINER2_MODEL=...`), not just at `docker run`.

To compare models or descriptions before changing them, use the
[extractor benchmark](benchmarks/extractor/README.md).

### With the regex extractor

`provider: "regex"` needs no model. It matches each entity's `examples` as whole
words, ignoring case:

```json
{
  "version": "1.0.0",
  "extractor": {
    "provider": "regex"
  },
  "entities": {
    "brand": {
      "label": "brand",
      "description": "Product brand or manufacturer",
      "examples": ["Nike", "Apple", "Samsung"]
    },
    "price": {
      "label": "price",
      "description": "Price, price limit, or price range"
    }
  }
}
```

It also supports per-entity `ambiguous_terms` with `context_words`,
`extract_quoted` and `extract_residual`. [AGENTS.md](AGENTS.md) explains these.

### Special labels

The search-object builder treats three labels differently:

- `price`: phrases like "under $100" become `filters.price`.
- `year`: phrases like "from 2012 to 2016" become `filters.year_from` and
  `filters.year_to`.
- `movie_title`: the first value becomes `filters.q`.

---

## `intent-map.json`

Defines possible user intents.

```json
{
  "version": "1.0.0",
  "intents": {
    "search_products": {
      "description": "User wants to search products.",
      "keywords": ["product", "products", "buy", "find", "show me"],
      "default_objects": ["product"]
    },
    "search_brands": {
      "description": "User wants to search or filter by brands.",
      "keywords": ["brand", "brands"],
      "default_objects": ["brand", "product"]
    },
    "global_search": {
      "description": "General search across all searchable objects.",
      "keywords": [],
      "default_objects": ["product", "brand", "category"]
    }
  }
}
```

---

## `search-map.json`

Defines searchable business objects.

```json
{
  "version": "1.0.0",
  "objects": {
    "product": {
      "aliases": ["product", "item"],
      "entities": ["product", "brand", "color", "price", "category"],
      "searchable_fields": ["title", "description", "sku"]
    },
    "brand": {
      "aliases": ["brand", "manufacturer"],
      "entities": ["brand"],
      "searchable_fields": ["name"]
    },
    "category": {
      "aliases": ["category", "department"],
      "entities": ["category"],
      "searchable_fields": ["name"]
    }
  }
}
```

Every object named in an intent's `default_objects` must be defined here. Only
the object names are used by code today; `aliases`, `entities` and
`searchable_fields` describe the object for people.

---

## `search-object-schema.json`

Defines the normalized internal search object. Only `defaults` is applied at
runtime; `schema` documents the shape and is not checked.

```json
{
  "version": "1.0.0",
  "schema": {
    "type": "object",
    "required": ["query", "locale", "intent", "objects"],
    "properties": {
      "query": { "type": "string" },
      "locale": { "type": "string" },
      "intent": { "type": "string" },
      "objects": {
        "type": "array",
        "items": { "type": "string" }
      },
      "entities": { "type": "object" },
      "resolved": { "type": "object" },
      "filters": { "type": "object" },
      "sort": { "type": "object" },
      "pagination": { "type": "object" }
    }
  },
  "defaults": {
    "sort": {
      "by": "relevance",
      "direction": "desc"
    },
    "pagination": {
      "limit": 20,
      "offset": 0
    }
  }
}
```

---

## `resolver-map.json`

Resolvers convert extracted values into real IDs from your system.

```text
"Nike" → brand_id: 42
"running shoes" → category_id: 7
"London" → city_id: 15
```

Example config:

```json
{
  "version": "1.0.0",
  "resolvers": {
    "brand": {
      "type": "http",
      "method": "GET",
      "url_from_env": "TARGET_BRAND_RESOLVER_URL",
      "query": {
        "q": "{{ value }}"
      },
      "result_path": "$.items[*].id",
      "target": "brand_ids"
    },
    "category": {
      "type": "http",
      "method": "GET",
      "url_from_env": "TARGET_CATEGORY_RESOLVER_URL",
      "query": {
        "q": "{{ value }}"
      },
      "result_path": "$.items[*].id",
      "target": "category_ids"
    }
  }
}
```

Resolved IDs are cached for the `resolved_entity` TTL in `cache.json`.

---

## `api-map.json`

Maps the internal `SearchObject` to your target API request.

```json
{
  "version": "1.0.0",
  "api": {
    "base_url_from_env": "TARGET_API_BASE_URL",
    "mode": "generate_only",
    "auth": {
      "type": "bearer_token",
      "token_from_env": "TARGET_API_TOKEN"
    }
  },
  "endpoints": {
    "search": {
      "method": "POST",
      "path": "/api/search",
      "headers": {
        "Content-Type": "application/json"
      },
      "body": {
        "objects": "{{ search_object.objects }}",
        "query": "{{ search_object.query }}",
        "filters": "{{ search_object.filters }}",
        "sort": "{{ search_object.sort }}",
        "pagination": "{{ search_object.pagination }}"
      },
      "options": {
        "remove_null_values": true,
        "remove_empty_arrays": true,
        "remove_empty_objects": true
      }
    }
  },
  "intent_endpoint_map": {
    "global_search": "search",
    "search_products": "search",
    "search_brands": "search"
  }
}
```

API modes:

```text
generate_only
execute
generate_and_execute
```

---

## `geo.json`

Optional. Anchors a query that names no place on the searcher's own position.

Without it, "cafe places" or "walking tours" has no geographic anchor at all
and the target API searches everything. With a position from the caller, the
query is scoped to a bounding box around the user instead. A query that names
its own city or country is never re-anchored — `"places in Paris"` stays a
search of Paris no matter where the searcher is.

```json
{
  "version": "1.0.0",
  "geo": {
    "enabled": true,
    "radius_km": 50,
    "cue_radius_km": 25,
    "max_radius_km": 500,
    "precision": 2,
    "header_fallback": true,
    "retry_without_geo_when_empty": true,
    "blocking_filters": ["city_ids", "country_ids"],
    "blocking_entities": ["city", "country"],
    "cues": ["near me", "nearby", "around me", "close to me"],
    "headers": {
      "lat": ["x-user-lat", "cf-iplatitude"],
      "lng": ["x-user-lng", "cf-iplongitude"]
    }
  }
}
```

| Key | Meaning |
| --- | --- |
| `enabled` | Off by default; no `geo.json` means the feature does not exist. |
| `radius_km` | Radius for a query that simply named no place. |
| `cue_radius_km` | Radius when the query said "near me" out loud — someone asking that means walking distance, not the surrounding region. |
| `max_radius_km` | Ceiling for a caller-supplied `radius_km`. |
| `precision` | Decimal places the position is snapped to before use (2 ≈ 1.1 km). Keeps the exact position out of the generated request and makes one neighbourhood produce one box. |
| `blocking_filters` | Filters that mean the query named a place (the city/country resolver targets). |
| `blocking_entities` | Entity labels that mean the same, for projects whose place entities do not resolve to ids. |
| `cues` | Phrases that ask for a nearby search explicitly. |
| `headers` | Proxy headers to read a position from when the request body carries none. |
| `header_fallback` | Set to `false` to accept a position only from the request body. |
| `retry_without_geo_when_empty` | In `execute` modes, re-run a geo-scoped search globally when it found nothing (see below). |

The position reaches the service either in the request body:

```json
{
  "query": "cafe places",
  "user_location": { "lat": 40.1792, "lng": 44.4991, "radius_km": 25, "source": "browser" }
}
```

or, for callers that never touch the browser Geolocation API, from the
configured headers (`X-User-Lat` / `X-User-Lng`, or Cloudflare's
`CF-IPLatitude` / `CF-IPLongitude`). The body wins when both are present.

When the fallback applies, the SearchObject gains a `geo` block:

```json
{
  "geo": {
    "applied": true,
    "trigger": "no_location_entity",
    "source": "browser",
    "lat": 40.18,
    "lng": 44.5,
    "radius_km": 50,
    "bbox": { "min_lat": 39.728, "min_lng": 43.913, "max_lat": 40.632, "max_lng": 45.085 }
  }
}
```

`trigger` is `explicit_cue` when the query itself asked for it, and
`no_location_entity` when it simply named no place.

The core writes no geo filter of its own: `api-map.json` decides which target
API fields the box maps onto, exactly like every other field.

```json
"filters": {
  "minLat": "{{ search_object.geo.bbox.min_lat }}",
  "minLng": "{{ search_object.geo.bbox.min_lng }}",
  "maxLat": "{{ search_object.geo.bbox.max_lat }}",
  "maxLng": "{{ search_object.geo.bbox.max_lng }}"
}
```

With no position, those placeholders resolve to null and the endpoint's
`remove_null_values` option drops them, so nothing about the request changes.

**Empty results.** A bounding box is a hard filter, so a geo-scoped search can
find nothing that a global one would have found — someone in Yerevan searching
"Harry Potter places" should still be shown the ones in London. With
`retry_without_geo_when_empty` (default `true`) and an executing `api.mode`,
a scoped search that comes back empty is re-run once without the box, and the
response says so:

```json
"geo": { "applied": false, "fallback": "global", "trigger": "no_location_entity" }
```

**Caching.** The cached search object is the one *before* the position is
applied, so the cache key stays `locale + query` and one user's position never
reaches another user's cached result.

---

## `auth-inbound.json`

Inbound auth validates requests coming into Search Intent.

For local development, you can disable inbound auth:

```json
{
  "version": "1.0.0",
  "inbound_auth": {
    "enabled": false
  }
}
```

For gateway-to-service JWT validation:

```json
{
  "version": "1.0.0",
  "inbound_auth": {
    "enabled": true,
    "type": "jwt",
    "token_source": {
      "type": "header",
      "name": "Authorization",
      "scheme": "Bearer"
    },
    "jwt": {
      "algorithm": "HS256",
      "secret_from_env": "SEARCH_INTENT_JWT_SECRET",
      "issuer_from_env": "SEARCH_INTENT_JWT_ISSUER",
      "audience_from_env": "SEARCH_INTENT_JWT_AUDIENCE",
      "required_claims": ["sub", "exp"]
    },
    "authorization": {
      "enabled": true,
      "required_permissions": ["search:intent:generate"]
    }
  }
}
```

The built-in check verifies the token with a shared secret (HS256 by default).
JWKS is not supported yet, so `SEARCH_INTENT_JWKS_URL` has no effect.
`required_permissions` are checked against the token's `permissions` claim.

---

## Environment Variables

Do not put secrets in JSON config. Copy `.env.example` to `.env` to set these
locally:

| Variable | Purpose |
| --- | --- |
| `SEARCH_INTENT_ENV` | `development` turns on auto-reload with `python -m search_intent` |
| `SEARCH_INTENT_HOST`, `SEARCH_INTENT_PORT` | Where the service listens (default port 8080) |
| `SEARCH_INTENT_CONFIG_DIR` | The collection to load (default `./config/default`) |
| `SEARCH_INTENT_JWT_SECRET`, `_ISSUER`, `_AUDIENCE` | Inbound JWT check, when `auth-inbound.json` enables it |
| `TARGET_API_BASE_URL`, `TARGET_API_TOKEN`, `TARGET_API_KEY` | Target API settings, read through the `*_from_env` names in `api-map.json` |
| `TARGET_BRAND_RESOLVER_URL`, `TARGET_CATEGORY_RESOLVER_URL` | HTTP resolver URLs, read through `url_from_env` in `resolver-map.json` |
| `REDIS_URL` | Redis connection, when `cache.json` selects the `redis` backend |
| `MODEL_CACHE_DIR` | Where models are stored (default `./models`) |
| `GLINER2_MODEL` | GLiNER model for collections whose `extractor.json` names none |

The `*_from_env` fields name any variable you like, so the target API and
resolver names above are just the ones the bundled collections use.

`SEARCH_INTENT_PLUGIN_DIR` and `SEARCH_INTENT_JWKS_URL` are reserved and not read
yet.

Recommended `.gitignore`:

```gitignore
.env
.env.*
!.env.example

models/
__pycache__/
.pytest_cache/
```

---

## HTTP API

### `GET /health`

Health check.

```json
{
  "status": "ok",
  "project": "example-shop"
}
```

### `POST /v1/parse`

Parses a query into intent and entities.

Request:

```json
{
  "query": "red Nike shoes under $100",
  "locale": "en"
}
```

Response:

```json
{
  "query": "red Nike shoes under $100",
  "locale": "en",
  "intent": "search_products",
  "objects": ["product"],
  "entities": {
    "product": ["shoes"],
    "brand": ["Nike"],
    "color": ["red"],
    "price": ["under $100"]
  },
  "confidence": {
    "intent": 0.53,
    "entities": 0.8
  }
}
```

### `POST /v1/generate`

Generates the target API request.

Request:

```json
{
  "query": "red Nike shoes under $100",
  "locale": "en"
}
```

`user_location` is optional and only used when `geo.json` is enabled and the
query names no place — see [`geo.json`](#geojson):

```json
{
  "query": "cafe places near me",
  "locale": "en",
  "user_location": { "lat": 40.1792, "lng": 44.4991 }
}
```

Response, using the bundled `config/default` collection:

```json
{
  "query": "red Nike shoes under $100",
  "locale": "en",
  "intent": "search_products",
  "search_object": {
    "query": "red Nike shoes under $100",
    "locale": "en",
    "intent": "search_products",
    "objects": ["product"],
    "entities": {
      "product": ["shoes"],
      "brand": ["Nike"],
      "color": ["red"],
      "price": ["under $100"]
    },
    "resolved": {
      "brand_ids": [42]
    },
    "filters": {
      "product": ["shoes"],
      "brand_ids": [42],
      "color": ["red"],
      "price": {
        "max": 100.0
      }
    },
    "sort": {
      "by": "relevance",
      "direction": "desc"
    },
    "pagination": {
      "limit": 20,
      "offset": 0
    },
    "geo": null
  },
  "api_request": {
    "method": "GET",
    "url": "https://dummyjson.com/products/search",
    "headers": {
      "Accept": "application/json"
    },
    "body": null,
    "query": {
      "q": "red Nike shoes under $100",
      "limit": 20,
      "skip": 0
    }
  },
  "cache": {
    "hit": false
  }
}
```

### `POST /v1/search`

Generates the API request and optionally executes it against the configured target API.

This endpoint is useful when `api.mode` is:

```text
execute
generate_and_execute
```

Request:

```json
{
  "query": "red Nike shoes under $100",
  "locale": "en"
}
```

Response:

The same fields as `/v1/generate`, plus the target API's reply:

```json
{
  "query": "red Nike shoes under $100",
  "locale": "en",
  "intent": "search_products",
  "search_object": {},
  "api_request": {},
  "api_response": {},
  "cache": {
    "hit": false
  }
}
```

With `api.mode` set to `generate_only`, `api_response` is `null`.

---

## Sandbox

The sandbox is a local web app for working on collections. You can browse and
edit their config files, create new ones (blank or copied from an existing
collection), and send a query to any collection to see the JSON it returns.

```bash
uv run python -m sandbox
```

It opens `http://127.0.0.1:8090/`. Options: `--port`, `--host`,
`--config-root` (default `./config`) and `--no-browser`.

- Edits are written straight to `config/<collection>/*.json`, exactly as typed.
  Review them with `git diff`.
- After each save the collection is checked the way the service loads it, and
  any error or warnings are shown under the editor.
- The tester runs `parse`, `generate` or `search`, with caching off so an
  edit shows up in the next run, including edits made outside the sandbox. For `generate` and `search` it also shows the
  parse stage (intent and extracted entities) next to the output. `search`
  calls the collection's target API for real.
- Inbound auth is skipped and files are writable over HTTP, so the sandbox is
  for local development only. It binds to localhost and is not part of the
  Docker image.
- Each file has a description next to it: what it's for, its main fields and
  common pitfalls.
- The delete button removes a collection's folder for good. A collection that
  isn't committed to git can't be recovered.

---

## Extractor Benchmark

Compares GLiNER models and label descriptions on labelled queries, reporting
accuracy per label and time per query:

```bash
uv run python benchmarks/extractor/run.py --errors
```

See [benchmarks/extractor/README.md](benchmarks/extractor/README.md) for how to
read the results, and for the numbers behind MovieTrip's choice of model.

---

## Caching

Search Intent caches:

```text
search objects
resolved entities
```

`cache.json` can also hold key patterns for `entities`, `api_request` and
`api_response`, but nothing uses those yet.

Example `cache.json`:

```json
{
  "version": "1.0.0",
  "cache": {
    "enabled": true,
    "backend": "redis",
    "namespace": "search-intent",
    "project_version": {
      "strategy": "static",
      "value": "v1"
    },
    "keys": {
      "search_object": {
        "pattern": "{namespace}:{project_version}:{locale}:{query_hash}:search_object",
        "ttl_seconds": 86400
      },
      "entities": {
        "pattern": "{namespace}:{project_version}:{locale}:{query_hash}:entities",
        "ttl_seconds": 604800
      },
      "resolved_entity": {
        "pattern": "{namespace}:{project_version}:{entity_key}:{value_hash}:resolved",
        "ttl_seconds": 2592000
      },
      "api_request": {
        "pattern": "{namespace}:{project_version}:{locale}:{query_hash}:api_request",
        "ttl_seconds": 86400
      },
      "api_response": {
        "pattern": "{namespace}:{project_version}:{locale}:{query_hash}:api_response",
        "ttl_seconds": 300
      }
    }
  }
}
```

---

## Plugins

Plugins are not wired up yet: nothing loads a plugin from config, and a
`"plugin"` block in a JSON file is ignored. Config-driven loading is on the
[roadmap](#roadmap).

What exists today:

- `search_intent/plugins/` has the base interfaces: `BaseInboundAuth`,
  `BaseCache`, `BaseExtractor` and `BaseResolver`.
- `plugins/auth/jwt_auth.py` is an example that subclasses `BaseInboundAuth`.

Use JSON config first. If config isn't enough, subclass a base interface and
wire it in with a code change.

When plugin loading arrives, plugins will be trusted local code. Never load
plugin paths from user input.

---

## Example Use Cases

E-Commerce and Movie Locations show real output from the bundled collections.
Real Estate and Document Search are sketches of what a collection could produce;
no such collections ship with the project.

### E-Commerce

Using `config/default`.

Input:

```text
"red Nike shoes under $100"
```

Generated filters:

```json
{
  "product": ["shoes"],
  "brand_ids": [42],
  "color": ["red"],
  "price": {
    "max": 100.0
  }
}
```

### Real Estate

Input:

```text
"2 bedroom apartments in Berlin near metro under 2500"
```

Generated filters:

```json
{
  "property_type": "apartment",
  "bedrooms": 2,
  "city": "Berlin",
  "near": "metro",
  "price": {
    "max": 2500
  }
}
```

### Movie Locations

Using `config/movietrip`.

Input:

```text
"Harry Potter places in London"
```

Generated filters:

```json
{
  "movie_title": ["Harry Potter"],
  "city_ids": [536],
  "q": "Harry Potter"
}
```

### Document Search

Input:

```text
"payment API timeout errors from last month"
```

Generated filters:

```json
{
  "topic": "payment API",
  "issue": "timeout errors",
  "date_range": "last month"
}
```

---

## Roadmap

### v0.1.0

- FastAPI service
- single active project config
- JSON config loader
- GLiNER2 and GLiNER2.5 extractors, plus a regex extractor
- rule-based intent detection
- SearchObject builder
- API mapper
- static resolver
- HTTP resolver
- Redis cache support
- inbound JWT authentication
- outbound API auth
- local sandbox for collections
- extractor benchmark

### v0.2.0

- config-driven plugin loading
- JWKS support for inbound JWT
- structured extraction mode
- relation extraction support
- better confidence scoring
- resolver ranking
- OpenAPI documentation polish
- config validation CLI
- plugin scaffolding CLI
- more example collections

### v0.3.0

- query evaluation suite, building on the extractor benchmark
- multilingual normalization helpers
- analytics hooks
- response post-processing plugins
- advanced cache invalidation
- deployment templates

---

## Security Notes

- Never commit `.env` files.
- Keep secrets in environment variables or secret managers.
- Do not load plugins from user input.
- Validate all generated API requests before execution.
- Inbound JWT verification uses a shared secret, so keep it strong and rotate it.
- Never expose the sandbox: it edits config files over HTTP with no auth.
- Use `generate_only` mode when Search Intent should not directly call target APIs.

---

## Contributing

Contributions are welcome.

Good first contributions:

- example configs
- extractor adapters
- resolver adapters
- API mapper improvements
- plugin examples
- documentation improvements
- tests
- Docker/deployment templates

To add or change a collection, follow [AGENTS.md](AGENTS.md).

Before opening a pull request:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check .
```

---

## Acknowledgments

- [GLiNER2](https://github.com/fastino-ai/GLiNER2) (Apache-2.0) powers the
  `gliner2` extractor. See the model cards for
  [gliner2-base-v1](https://huggingface.co/fastino/gliner2-base-v1) and
  [gliner2.5-base-v1](https://huggingface.co/fastino/gliner2.5-base-v1).

---

## License

MIT. See [LICENSE](LICENSE).

---

## Status

Search Intent is at an early stage: the service runs, but config formats and
APIs may still change.

The goal is to provide a practical open-source bridge between natural-language search and strict backend API contracts.

```text
Open text query
  → SearchObject
  → ApiRequest
  → Your API
```
