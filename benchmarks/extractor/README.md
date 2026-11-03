# Extractor benchmark

Scores GLiNER models, and different ways of describing the labels to them, on
a labelled set of queries for one collection.

```bash
uv run python benchmarks/extractor/run.py --errors
uv run python benchmarks/extractor/run.py --setups base,2.5-base+model
```

Options: `--setups` picks setups, `--errors` lists every query with a wrong
label, `--json FILE` saves full results, `--threshold` overrides
`extractor.json`, and `--cases` points at another collection's query file.
To try new descriptions without touching the collection, edit a copy of its
`extractor.json` and pass it with `--config`.

## Setups

A setup is a model plus what the model is told about each label:

| Suffix | What the model gets | Notes |
| --- | --- | --- |
| *(none)* | Label names only | What the service sends when no `model_description` is set |
| `+config` | `description` from `extractor.json` | Written for people, not the model |
| `+model` | `model_description` from `extractor.json` | What the service sends |

Models: `base` (`fastino/gliner2-base-v1`), `large` (`gliner2-large-v1`),
`2.5-base` (`gliner2.5-base-v1`, used by movietrip) and `2.5-small`
(`gliner2.5-small-v1`).

## Scoring

- **Matching:** for each query and label, the extracted values are compared
  with the gold values as sets. Case and surrounding punctuation are ignored.
- **`year`:** only the 4-digit years are compared, since that is all the
  search-object builder reads.
- **Strict on purpose:** "horror movies" doesn't count for gold "horror". The
  resolvers look values up exactly, so that filter would be lost.
- **all-correct:** the number of queries where every label came out right.
- **Timing:** milliseconds per query on CPU, after two warm-up queries. Load
  time includes the first download.

## Query file

`movietrip.json` holds 57 queries, a few of them deliberately tricky:
- a city inside a title ("Midnight in Paris")
- regions that aren't cities or countries ("Sicily", "Utah")
- an ambiguous country word with no context ("turkey dinner")

Gold values must appear in the query text; the script checks this. To
benchmark another collection, add `<collection>.json` with the same shape
and pass `--cases`.

## Results: 2026-11-03, movietrip, threshold 0.35, Apple Silicon CPU

These results led to movietrip's switch to `2.5-base+model`. "Today" below means
the setup before that switch.

| Setup | P | R | F1 | All correct | ms/query |
| --- | --- | --- | --- | --- | --- |
| base (today) | 0.63 | 0.80 | 0.71 | 18/57 | 33 |
| base+config | 0.73 | 0.67 | 0.70 | 22/57 | 75 |
| base+model | 0.69 | 0.80 | 0.74 | 24/57 | 49 |
| large | 0.65 | 0.76 | 0.70 | 15/57 | 79 |
| large+model | 0.77 | 0.79 | 0.78 | 29/57 | 119 |
| 2.5-small | 0.47 | 0.67 | 0.55 | 5/57 | 15 |
| 2.5-small+model | 0.57 | 0.76 | 0.65 | 10/57 | 30 |
| 2.5-base | 0.71 | 0.84 | 0.77 | 23/57 | 29 |
| 2.5-base+config | 0.78 | 0.78 | 0.78 | 27/57 | 73 |
| **2.5-base+model** | **0.80** | **0.84** | **0.82** | **33/57** | **47** |

F1 by label:

| Setup | movie_title | city | country | location_type | genre | year |
| --- | --- | --- | --- | --- | --- | --- |
| base (today) | 0.65 | 0.94 | 0.93 | 0.51 | 0.30 | 1.00 |
| base+model | 0.46 | 0.91 | 0.90 | 0.74 | 0.80 | 1.00 |
| large+model | 0.58 | 0.88 | 0.93 | 0.69 | 0.78 | 1.00 |
| 2.5-base | 0.63 | 0.91 | 0.93 | 0.50 | 0.85 | 1.00 |
| 2.5-base+model | 0.63 | 0.92 | 0.90 | 0.82 | 0.88 | 1.00 |

What the results show:

- **Best setup:** `2.5-base+model`. Queries with every label right go from 18
  to 33, at 47 ms per query instead of 33.
- **Upgrade alone:** `2.5-base` with no descriptions already beats today's
  setup at the same speed. Genre F1 goes from 0.30 to 0.85, because the base
  model tags "horror movies" rather than "horror".
- **Descriptions:** short, model-oriented descriptions (`+model`) help every model. The
  existing `extractor.json` descriptions are written for people and help
  less, or hurt.
- **Weak spots:** `large` costs 2–4× the time for less gain than 2.5-base.
  `2.5-small` is fast but too inaccurate.
- **Titles stay weakest** (about 0.6 F1 everywhere). Most misses are the title
  running into the next word: "Frozen places", "Ocean's Eleven casino",
  "Tokyo Drift scenes".
- **Version parity:** the base model scores identically under gliner2 1.3.2
  and 2.1.0, so upgrading the package doesn't change results by itself.

With 57 queries, a difference of one or two queries is noise. The ranking
above is wider than that.
