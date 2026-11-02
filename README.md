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
- GLiNER / GLiNER2-compatible extractor interface
- JSON-based project configuration
- Search object generation
- API request generation
- Static and HTTP entity resolvers
- Near-me fallback for queries that name no place
- Redis caching support
- Optional API execution mode
- Inbound JWT authentication
- Outbound API authentication
- Root-level Python plugin system
- Project-agnostic core
- Docker-ready structure

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_ORG/search-intent.git
cd search-intent
```

### 2. Create environment file

```bash
cp .env.example .env
```

Edit `.env`:

```env
SEARCH_INTENT_ENV=development
SEARCH_INTENT_HOST=0.0.0.0
SEARCH_INTENT_PORT=8080
SEARCH_INTENT_CONFIG_DIR=./config/default
SEARCH_INTENT_PLUGIN_DIR=./plugins

TARGET_API_BASE_URL=https://api.example.com
TARGET_API_TOKEN=change_me

REDIS_URL=redis://localhost:6379/0
```

### 3. Install dependencies

```bash
pip install -e .
```

### 4. Run the service

```bash
uvicorn search_intent.main:app --host 0.0.0.0 --port 8080 --reload
```

### 5. Test it

```bash
curl -X POST http://localhost:8080/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Harry Potter places in London",
    "locale": "en"
  }'
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

---

## Project Structure

```text
search-intent/
  README.md
  LICENSE
  pyproject.toml
  Dockerfile
  docker-compose.yml
  .env.example

  search_intent/
    main.py

    api/
      routes_parse.py
      routes_generate.py
      routes_search.py
      routes_health.py

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
      manager.py
      redis_cache.py
      memory_cache.py

    config/
      loader.py
      validator.py

    plugins/
      base_auth.py
      base_api.py
      base_resolver.py
      base_extractor.py
      base_cache.py

  config/
    project.json
    extractor.json
    search-map.json
    intent-map.json
    search-object-schema.json
    api-map.json
    resolver-map.json
    cache.json
    auth-inbound.json

  plugins/
    auth/
      jwt_auth.py

    api/
      api_plugin.py

    resolver/
      resolver_plugin.py

    extractor/
      extractor_plugin.py

  examples/
    ecommerce/
      config/

    movie_locations/
      config/

    documents/
      config/
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
  movietrip/    # MovieTrip parse profile
```

A collection folder holds:

```text
config/default/
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

Example configs can live in:

```text
examples/
```

You can copy one example into the active config directory:

```bash
cp -r examples/ecommerce/config ./config
```

To browse, edit, create and test collections in a browser, use the
[sandbox](#sandbox).

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

---

## `extractor.json`

Defines how Search Intent extracts entities and intent-related information from user queries.

```json
{
  "version": "1.0.0",
  "extractor": {
    "provider": "gliner2",
    "model": "fastino/gliner2-base-v1",
    "mode": "combined_schema",
    "thresholds": {
      "entity": 0.35,
      "classification": 0.45
    }
  },
  "entities": {
    "product": {
      "label": "product",
      "description": "Product name or product type",
      "examples": ["running shoes", "laptop", "winter jacket"]
    },
    "brand": {
      "label": "brand",
      "description": "Product brand or manufacturer",
      "examples": ["Nike", "Apple", "Samsung"]
    },
    "color": {
      "label": "color",
      "description": "Product color",
      "examples": ["red", "black", "white"]
    },
    "price": {
      "label": "price",
      "description": "Price, price limit, or price range",
      "examples": ["under $100", "between 50 and 200"]
    }
  }
}
```

The core engine does not hardcode business labels. Entity labels come from JSON config.

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

---

## `search-object-schema.json`

Defines the normalized internal search object.

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
      "target": "brand_ids",
      "cache_ttl_seconds": 2592000
    },
    "category": {
      "type": "http",
      "method": "GET",
      "url_from_env": "TARGET_CATEGORY_RESOLVER_URL",
      "query": {
        "q": "{{ value }}"
      },
      "result_path": "$.items[*].id",
      "target": "category_ids",
      "cache_ttl_seconds": 2592000
    }
  }
}
```

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
    "plugin": {
      "module": "plugins.auth.jwt_auth",
      "class": "JwtInboundAuthPlugin"
    },
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

For production, prefer RS256/ES256 with JWKS.

---

## Environment Variables

Do not put secrets in JSON config.

Use environment variables for:

- JWT secrets
- API tokens
- API keys
- Redis URL
- target API base URL
- model path
- environment-specific values

Example `.env.example`:

```env
# App
SEARCH_INTENT_ENV=development
SEARCH_INTENT_HOST=0.0.0.0
SEARCH_INTENT_PORT=8080
SEARCH_INTENT_CONFIG_DIR=./config/default
SEARCH_INTENT_PLUGIN_DIR=./plugins

# Inbound JWT
SEARCH_INTENT_JWT_SECRET=change_me_for_local_dev_only
SEARCH_INTENT_JWT_ISSUER=search-intent-gateway
SEARCH_INTENT_JWT_AUDIENCE=search-intent
SEARCH_INTENT_JWKS_URL=https://auth.example.com/.well-known/jwks.json

# Target API
TARGET_API_BASE_URL=https://api.example.com
TARGET_API_TOKEN=change_me
TARGET_API_KEY=change_me

# Resolvers
TARGET_BRAND_RESOLVER_URL=https://api.example.com/brands/resolve
TARGET_CATEGORY_RESOLVER_URL=https://api.example.com/categories/resolve

# Cache
REDIS_URL=redis://localhost:6379/0

# Models
MODEL_CACHE_DIR=./models
GLINER2_MODEL=fastino/gliner2-base-v1
```

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
  "status": "ok"
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
    "intent": 0.91,
    "entities": 0.87
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

Response:

```json
{
  "query": "red Nike shoes under $100",
  "locale": "en",
  "intent": "search_products",
  "search_object": {
    "objects": ["product"],
    "entities": {
      "product": ["shoes"],
      "brand": ["Nike"],
      "color": ["red"],
      "price": ["under $100"]
    },
    "resolved": {
      "brand_ids": [42],
      "category_ids": [7]
    },
    "filters": {
      "brand_ids": [42],
      "category_ids": [7],
      "color": ["red"],
      "price": {
        "max": 100
      }
    },
    "pagination": {
      "limit": 20,
      "offset": 0
    }
  },
  "api_request": {
    "method": "POST",
    "url": "https://api.example.com/api/search",
    "headers": {
      "Content-Type": "application/json"
    },
    "body": {
      "objects": ["product"],
      "query": "red Nike shoes under $100",
      "filters": {
        "brand_ids": [42],
        "category_ids": [7],
        "color": ["red"],
        "price": {
          "max": 100
        }
      },
      "pagination": {
        "limit": 20,
        "offset": 0
      }
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

```json
{
  "search_object": {},
  "api_request": {},
  "api_response": {}
}
```

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
- The tester runs `parse`, `generate` or `search`, with caching off so a saved
  edit shows up in the next run. For `generate` and `search` it also shows the
  parse stage (intent and extracted entities) next to the output. `search`
  calls the collection's target API for real.
- Inbound auth is skipped and files are writable over HTTP, so the sandbox is
  for local development only. It binds to localhost and is not part of the
  Docker image.

---

## Caching

Search Intent can cache:

```text
entities
resolved entities
search objects
generated API requests
target API responses
```

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

Use JSON config first. Use plugins only when config is not enough.

Plugins live in the root-level `plugins/` directory:

```text
plugins/
  auth/
    jwt_auth.py

  api/
    api_plugin.py

  resolver/
    resolver_plugin.py

  extractor/
    extractor_plugin.py

  cache/
    cache_plugin.py
```

Base plugin interfaces live in:

```text
search_intent/plugins/
```

Plugin example in config:

```json
{
  "plugin": {
    "enabled": true,
    "module": "plugins.api.api_plugin",
    "class": "ProjectApiPlugin"
  }
}
```

Use plugins for:

- custom auth
- custom API signing
- complex API payloads
- custom entity resolution
- custom extraction post-processing
- custom cache keys
- response post-processing

Plugins are trusted local code. Do not load arbitrary plugin paths from user input.

---

## Example Use Cases

### E-Commerce

Input:

```text
"red Nike running shoes under $100"
```

Generated filters:

```json
{
  "brand": "Nike",
  "color": "red",
  "category": "running shoes",
  "price": {
    "max": 100
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

Input:

```text
"Harry Potter places in London"
```

Generated filters:

```json
{
  "movie_title": "Harry Potter",
  "city": "London"
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
- GLiNER / GLiNER2-compatible extractor interface
- rule-based intent fallback
- SearchObject builder
- API mapper
- static resolver
- HTTP resolver
- Redis cache support
- inbound JWT plugin
- outbound API auth
- root-level plugin system
- example configs

### v0.2.0

- structured extraction mode
- relation extraction support
- better confidence scoring
- resolver ranking
- OpenAPI documentation polish
- config validation CLI
- plugin scaffolding CLI

### v0.3.0

- query evaluation suite
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
- Prefer RS256/ES256 + JWKS for production JWT verification.
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

Before opening a pull request:

```bash
pytest
ruff check .
```

---

## License

Recommended license:

```text
Apache-2.0
```

or:

```text
MIT
```

Choose Apache-2.0 if you want a permissive license with explicit patent protection. Choose MIT if you want the simplest permissive license.

---

## Status

Search Intent is in early design/prototype stage.

The goal is to provide a practical open-source bridge between natural-language search and strict backend API contracts.

```text
Open text query
  → SearchObject
  → ApiRequest
  → Your API
```
