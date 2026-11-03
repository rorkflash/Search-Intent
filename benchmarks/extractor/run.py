"""Compare GLiNER models and prompting on a labelled set of queries.

    uv run python benchmarks/extractor/run.py           # every setup
    uv run python benchmarks/extractor/run.py --setups base,2.5-base+model --errors

To try other descriptions or a threshold without touching the collection, copy
its extractor.json, edit the copy and pass it with --config.

Scores compare extracted values with the gold values as sets per label
(ignoring case and surrounding punctuation); `year` compares the 4-digit years
only, which is all the search-object builder reads.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

MODELS = {
    "base": "fastino/gliner2-base-v1",
    "large": "fastino/gliner2-large-v1",
    "2.5-base": "fastino/gliner2.5-base-v1",
    "2.5-small": "fastino/gliner2.5-small-v1",
}
# What the model is told about each label: its name only, extractor.json's
# `description` (written for people), or its `model_description` (what the
# service sends).
PROMPTS = {"": "labels", "+config": "description", "+model": "model_description"}
SETUPS = [m + p for m in MODELS for p in PROMPTS]

_YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
_EDGE = " \t.,;:!?\"'“”‘’"


def normalize(label: str, values: list[str]) -> set[str]:
    if label == "year":
        return {y for v in values for y in _YEAR_RE.findall(v)}
    out = set()
    for v in values:
        v = re.sub(r"\s+", " ", v.replace("’", "'")).strip(_EDGE).lower()
        if v:
            out.add(v)
    return out


def load_model(name: str) -> Any:
    from gliner2 import AutoExtractor

    return AutoExtractor.from_pretrained(name)


def extract(model: Any, query: str, entity_types: Any, threshold: float) -> dict[str, list[str]]:
    result = model.extract_entities(query, entity_types, threshold=threshold)
    found: dict[str, list[str]] = {}
    for label, items in (result.get("entities") or {}).items():
        for item in items or []:
            text = item.get("text") if isinstance(item, dict) else item
            if text:
                found.setdefault(label, []).append(str(text))
    return found


def entity_types(prompt: str, labels: list[str], config: dict) -> Any:
    if prompt == "labels":
        return labels
    return {label: config["entities"][label].get(prompt) or label for label in labels}


def run_setup(
    setup: str, model: Any, labels: list[str], config: dict, cases: dict, threshold: float
) -> dict[str, Any]:
    prompt = PROMPTS[setup[setup.index("+"):] if "+" in setup else ""]
    types = entity_types(prompt, labels, config)
    for case in cases["cases"][:2]:  # warm-up, not timed
        extract(model, case["query"], types, threshold)

    counts = {label: {"tp": 0, "fp": 0, "fn": 0} for label in labels}
    timings, errors, all_correct = [], [], 0
    for case in cases["cases"]:
        start = time.perf_counter()
        predicted = extract(model, case["query"], types, threshold)
        timings.append((time.perf_counter() - start) * 1000)

        wrong = {}
        for label in labels:
            gold = normalize(label, case["entities"].get(label, []))
            pred = normalize(label, predicted.get(label, []))
            c = counts[label]
            c["tp"] += len(gold & pred)
            c["fp"] += len(pred - gold)
            c["fn"] += len(gold - pred)
            if gold != pred:
                wrong[label] = {"expected": sorted(gold), "got": sorted(pred)}
        if wrong:
            errors.append({"query": case["query"], "wrong": wrong})
        else:
            all_correct += 1

    return {
        "setup": setup,
        "per_label": {label: _prf(c) for label, c in counts.items()},
        "micro": _prf({k: sum(c[k] for c in counts.values()) for k in ("tp", "fp", "fn")}),
        "queries_all_correct": all_correct,
        "queries": len(cases["cases"]),
        "ms_median": round(statistics.median(timings), 1),
        "ms_p95": round(sorted(timings)[int(0.95 * (len(timings) - 1))], 1),
        "errors": errors,
    }


def _prf(c: dict[str, int]) -> dict[str, float]:
    p = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else 1.0
    r = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"p": round(p, 3), "r": round(r, 3), "f1": round(f, 3), **c}


def print_report(results: list[dict], labels: list[str], show_errors: bool) -> None:
    head = (
        f"{'setup':<18}{'P':>7}{'R':>7}{'F1':>7}{'all-correct':>14}"
        f"{'ms med':>9}{'p95':>8}{'load s':>8}"
    )
    print("\n" + head + "\n" + "-" * len(head))
    for r in results:
        m = r["micro"]
        correct = f"{r['queries_all_correct']}/{r['queries']}"
        print(
            f"{r['setup']:<18}{m['p']:>7.2f}{m['r']:>7.2f}{m['f1']:>7.2f}{correct:>14}"
            f"{r['ms_median']:>9}{r['ms_p95']:>8}{r['load_s']:>8}"
        )

    print("\nF1 by label")
    print(f"{'setup':<18}" + "".join(f"{label[:13]:>14}" for label in labels))
    for r in results:
        print(f"{r['setup']:<18}" + "".join(f"{r['per_label'][lb]['f1']:>14.2f}" for lb in labels))

    if show_errors:
        for r in results:
            print(f"\n== {r['setup']}: {len(r['errors'])} queries with a wrong label")
            for e in r["errors"]:
                parts = "; ".join(
                    f"{lb} expected {w['expected']} got {w['got']}" for lb, w in e["wrong"].items()
                )
                print(f"  {e['query']!r}: {parts}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cases", default=str(HERE / "movietrip.json"))
    parser.add_argument("--config", help="extractor.json (default: config/<collection>/)")
    parser.add_argument("--setups", help=f"comma-separated, from: {', '.join(SETUPS)}")
    parser.add_argument("--threshold", type=float, help="default: from extractor.json")
    parser.add_argument("--errors", action="store_true", help="list every query with a wrong label")
    parser.add_argument("--json", help="also write full results to this file")
    args = parser.parse_args()

    # Same model cache as the service (MODEL_CACHE_DIR, default ./models).
    os.environ.setdefault("HF_HOME", os.environ.get("MODEL_CACHE_DIR", str(REPO / "models")))

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    config_path = Path(args.config or REPO / "config" / cases["collection"] / "extractor.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    labels = list(config["entities"])
    threshold = args.threshold or config["extractor"].get("thresholds", {}).get("entity", 0.35)

    _check_gold(cases, labels)
    setups = args.setups.split(",") if args.setups else SETUPS
    unknown = [s for s in setups if s not in SETUPS]
    if unknown:
        parser.error(f"unknown setups: {', '.join(unknown)}")

    print(f"{len(cases['cases'])} queries, labels {labels}, threshold {threshold}", file=sys.stderr)
    results, loaded = [], {}
    for setup in setups:
        name = MODELS[setup.split("+")[0]]
        if name not in loaded:
            print(f"loading {name} ...", file=sys.stderr)
            start = time.perf_counter()
            loaded[name] = (load_model(name), round(time.perf_counter() - start, 1))
        model, load_s = loaded[name]
        print(f"running {setup} ...", file=sys.stderr)
        result = run_setup(setup, model, labels, config, cases, threshold)
        result["load_s"] = load_s
        results.append(result)

    print_report(results, labels, args.errors)
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


def _check_gold(cases: dict, labels: list[str]) -> None:
    """Gold values must be labels the config knows and text found in the query."""
    for case in cases["cases"]:
        for label, values in case["entities"].items():
            if label not in labels:
                sys.exit(f"unknown label {label!r} in {case['query']!r}")
            for v in values:
                if v.lower() not in case["query"].lower():
                    sys.exit(f"gold {v!r} is not in the query {case['query']!r}")


if __name__ == "__main__":
    main()
