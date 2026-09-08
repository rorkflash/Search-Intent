"""Zero-dependency fallback extractor.

Matches entities using the example vocabulary from extractor.json plus a few
built-in patterns (price expressions). It is intentionally simple: it lets the
service run end-to-end with no ML model. For production-quality extraction use
the GLiNER2 extractor.

Ambiguous vocabulary (config-driven): some example terms double as common
English words (e.g. "bank", "club", "sport") and would false-positive if
matched on their own. Per entity, config can list such terms under
``ambiguous_terms`` together with ``context_words`` (and optionally
``context_window``, default 2). An ambiguous term only counts as a match when
one of the context words appears within ``context_window`` tokens of it, e.g.
"bank location" matches but "bank of America" does not.

Open-ended titles (config-driven): entities may set ``extract_quoted`` and/or
``extract_residual``. Residual mode strips already-matched entities plus
``residual_stopwords``, then treats leftover text as the entity value — so
unknown movie titles work without dumping a full catalog into ``examples``.
"""

from __future__ import annotations

import re
from typing import Any

from .base import ExtractionResult, Extractor

# Price expressions: "under $100", "between 50 and 200", "$2500", "max 100".
_PRICE_RE = re.compile(
    r"(under|below|less than|max|up to|over|above|more than|min|from|between)?\s*"
    r"\$?\s*(\d+(?:[.,]\d+)?)\s*(?:(?:and|to|-)\s*\$?\s*(\d+(?:[.,]\d+)?))?",
    re.IGNORECASE,
)

_TOKEN_RE = re.compile(r"\S+")
_WS_RE = re.compile(r"\s+")
_DEFAULT_CONTEXT_WINDOW = 2
# Single- or double-quoted spans, e.g. 'Inferno' / "The Godfather".
_QUOTED_RE = re.compile(r"[\"']([^\"']+)[\"']")
# Year / year-range phrases for entities labeled "year".
_YEAR_RE = re.compile(
    r"(?:"
    r"(?:(?:from|between|starting(?:\s+from)?)\s+)?"
    r"(18\d{2}|19\d{2}|20\d{2})\s*(?:-|–|to|and|until)\s*(18\d{2}|19\d{2}|20\d{2})"
    r"|"
    r"(?:(?:from|since|after|starting(?:\s+from)?|before|until|up to|in|year)\s+)"
    r"(18\d{2}|19\d{2}|20\d{2})"
    r")",
    re.IGNORECASE,
)
# Grammar words trimmed only from residual edges so titles like
# "Lord of the Rings" keep internal "of"/"the".
_DEFAULT_EDGE_STOPWORDS = ("the", "a", "an", "of", "to", "for", "in", "on", "at")


class RegexExtractor(Extractor):
    def __init__(self, extractor_config: dict[str, Any]) -> None:
        super().__init__(extractor_config)
        # Pre-compile a whole-word matcher per entity from its unambiguous examples.
        self._vocab: dict[str, re.Pattern[str]] = {}
        # Ambiguous examples need a nearby context word to count as a match.
        self._ambiguous_vocab: dict[str, re.Pattern[str]] = {}
        self._context_re: dict[str, re.Pattern[str]] = {}
        self._context_window: dict[str, int] = {}
        # Entities that should also capture quoted spans from the query.
        self._extract_quoted: set[str] = set()
        # Entities that claim leftover query text after other entities/stopwords.
        self._residual_stopwords: dict[str, set[str]] = {}
        self._residual_cues: dict[str, set[str]] = {}
        self._residual_edge_stopwords: dict[str, set[str]] = {}

        for label, spec in self.entities.items():
            examples = spec.get("examples", [])
            ambiguous = {str(a).lower() for a in spec.get("ambiguous_terms", [])}

            plain_terms = sorted(
                {e for e in examples if e and e.lower() not in ambiguous}, key=len, reverse=True
            )
            ambiguous_terms = sorted(
                {e for e in examples if e and e.lower() in ambiguous}, key=len, reverse=True
            )

            if plain_terms:
                joined = "|".join(re.escape(t) for t in plain_terms)
                self._vocab[label] = re.compile(rf"\b({joined})\b", re.IGNORECASE)

            if ambiguous_terms:
                joined = "|".join(re.escape(t) for t in ambiguous_terms)
                self._ambiguous_vocab[label] = re.compile(rf"\b({joined})\b", re.IGNORECASE)
                context_words = spec.get("context_words", [])
                if context_words:
                    ctx_joined = "|".join(re.escape(c) for c in context_words)
                    self._context_re[label] = re.compile(rf"\b({ctx_joined})\b", re.IGNORECASE)
                    self._context_window[label] = int(
                        spec.get("context_window", _DEFAULT_CONTEXT_WINDOW)
                    )
                # No context_words configured -> ambiguous terms never match
                # (safer default than matching every occurrence of a common word).

            if spec.get("extract_quoted"):
                self._extract_quoted.add(label)

            if spec.get("extract_residual"):
                self._residual_stopwords[label] = {
                    str(w).lower() for w in spec.get("residual_stopwords", []) if w
                }
                self._residual_cues[label] = {
                    str(w).lower() for w in spec.get("residual_cues", []) if w
                }
                edge = spec.get("residual_edge_stopwords")
                self._residual_edge_stopwords[label] = (
                    {str(w).lower() for w in edge if w}
                    if edge is not None
                    else set(_DEFAULT_EDGE_STOPWORDS)
                )

    def extract(self, query: str, locale: str = "en") -> ExtractionResult:
        entities: dict[str, list[str]] = {}

        for label, pattern in self._vocab.items():
            if label in {"price", "year"}:
                continue
            found = self._collect(pattern, query, [])
            if found:
                entities[label] = found

        for label, pattern in self._ambiguous_vocab.items():
            if label in {"price", "year"}:
                continue
            context_re = self._context_re.get(label)
            if context_re is None:
                continue
            window = self._context_window[label]
            existing = entities.get(label, [])
            found = self._collect(
                pattern,
                query,
                existing,
                predicate=lambda m: self._has_nearby_context(query, m, context_re, window),
            )
            if found:
                entities[label] = found

        if "year" in self.entities:
            year = self._match_year(query)
            if year:
                entities["year"] = year

        for label in self._extract_quoted:
            existing = entities.get(label, [])
            for quoted in _QUOTED_RE.findall(query):
                value = quoted.strip()
                if value and value.lower() not in (v.lower() for v in existing):
                    existing.append(value)
            if existing:
                entities[label] = existing

        for label in self._residual_stopwords:
            if entities.get(label):
                continue
            residual = self._extract_residual(query, entities, label)
            if residual:
                entities[label] = [residual]

        if "price" in self.entities:
            price = self._match_price(query)
            if price:
                entities["price"] = price

        # Crude but honest confidence: did we find anything at all?
        confidence = 0.8 if entities else 0.0
        return ExtractionResult(entities=entities, confidence=confidence)

    def _extract_residual(
        self, query: str, entities: dict[str, list[str]], label: str
    ) -> str | None:
        cues = self._residual_cues[label]
        if cues:
            lowered = query.lower()
            if not any(re.search(rf"\b{re.escape(c)}\b", lowered) for c in cues):
                return None

        leftover = query
        # Drop quoted spans already handled (or that would confuse residual).
        leftover = _QUOTED_RE.sub(" ", leftover)

        # Remove other extracted entity values (longest first for multi-word).
        other_values = [
            value
            for other_label, values in entities.items()
            if other_label != label
            for value in values
        ]
        for value in sorted(other_values, key=len, reverse=True):
            leftover = re.sub(rf"\b{re.escape(value)}\b", " ", leftover, flags=re.IGNORECASE)

        stopwords = self._residual_stopwords[label]
        if stopwords:
            joined = "|".join(re.escape(w) for w in sorted(stopwords, key=len, reverse=True))
            leftover = re.sub(rf"\b(?:{joined})\b", " ", leftover, flags=re.IGNORECASE)

        leftover = _WS_RE.sub(" ", leftover).strip(" \t.,;:!?")
        leftover = self._trim_edge_stopwords(leftover, self._residual_edge_stopwords[label])
        # Ignore junk leftovers like a lone "I" after stripping grammar words.
        if len(leftover) < 2:
            return None
        return leftover or None

    @staticmethod
    def _trim_edge_stopwords(text: str, edge_stopwords: set[str]) -> str:
        tokens = text.split()
        while tokens and tokens[0].lower().strip(".,;:!?\"'") in edge_stopwords:
            tokens.pop(0)
        while tokens and tokens[-1].lower().strip(".,;:!?\"'") in edge_stopwords:
            tokens.pop()
        return " ".join(tokens)

    @staticmethod
    def _collect(
        pattern: re.Pattern[str],
        query: str,
        found: list[str],
        predicate: Any = None,
    ) -> list[str]:
        for match in pattern.finditer(query):
            if predicate is not None and not predicate(match):
                continue
            value = match.group(1)
            if value.lower() not in (v.lower() for v in found):
                found.append(value)
        return found

    @staticmethod
    def _has_nearby_context(
        query: str, match: re.Match[str], context_re: re.Pattern[str], window: int
    ) -> bool:
        tokens = list(_TOKEN_RE.finditer(query))
        match_idx = next(
            (i for i, tok in enumerate(tokens) if tok.start() <= match.start() < tok.end()),
            None,
        )
        if match_idx is None:
            return False
        lo, hi = max(0, match_idx - window), min(len(tokens), match_idx + window + 1)
        neighborhood = " ".join(tok.group() for tok in tokens[lo:hi])
        return bool(context_re.search(neighborhood))

    @staticmethod
    def _match_price(query: str) -> list[str]:
        match = _PRICE_RE.search(query)
        if not match or not match.group(2):
            return []
        return [match.group(0).strip()]

    @staticmethod
    def _match_year(query: str) -> list[str]:
        match = _YEAR_RE.search(query)
        if not match:
            return []
        return [match.group(0).strip()]
