"""Deterministic citation span verification.

The verifier is deliberately conservative: exact and normalized substrings are preferred;
the fuzzy fallback only accepts token-set similarity at or above ``CITATION_THRESHOLD``.
That threshold is fixed at 0.95, the most-recall operating point satisfying the 0.98
precision floor on ``data/goldsets/citation_threshold.jsonl``. A quote that is not found is
invalid without exception; no model signal can override that verdict.
"""

from __future__ import annotations

import enum
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

CITATION_THRESHOLD = 0.95


class MatchType(enum.StrEnum):
    EXACT = "exact"
    NORMALIZED = "normalized"
    FUZZY = "fuzzy"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class CitationVerdict:
    valid: bool
    match_type: MatchType
    span: tuple[int, int] | None
    score: float
    explanation: str


@dataclass(frozen=True)
class _NormalizedText:
    text: str
    original_offsets: tuple[int, ...]


_QUOTE_MAP = str.maketrans({"‘": "'", "’": "'", "‚": "'", "“": '"', "”": '"'})
_DASHES = {"‐", "‑", "‒", "–", "—", "―", "−"}


def _normalize_with_offsets(value: str) -> _NormalizedText:
    chars: list[str] = []
    offsets: list[int] = []
    pending_space_offset: int | None = None

    for original_index, original_char in enumerate(value):
        expanded = unicodedata.normalize("NFKC", original_char).translate(_QUOTE_MAP)
        for char in expanded.casefold():
            if char in _DASHES:
                char = "-"
            is_separator = char.isspace() or unicodedata.category(char).startswith("P")
            if is_separator:
                if chars:
                    pending_space_offset = original_index
                continue
            if pending_space_offset is not None:
                chars.append(" ")
                offsets.append(pending_space_offset)
                pending_space_offset = None
            chars.append(char)
            offsets.append(original_index)

    return _NormalizedText("".join(chars), tuple(offsets))


def _token_set_ratio(left: list[str], right: list[str]) -> float:
    left_set = " ".join(sorted(set(left)))
    right_set = " ".join(sorted(set(right)))
    if not left_set or not right_set:
        return 0.0
    return SequenceMatcher(None, left_set, right_set, autojunk=False).ratio()


def _normalized_span(normalized: _NormalizedText, start: int, end: int) -> tuple[int, int]:
    return normalized.original_offsets[start], normalized.original_offsets[end - 1] + 1


def verify_citation(quote: str, source_text: str) -> CitationVerdict:
    """Verify a claimed quote against source text and return the first matched span."""
    if not quote or not quote.strip():
        return CitationVerdict(
            False,
            MatchType.NOT_FOUND,
            None,
            0.0,
            "citation quote is empty; NOT_FOUND is invalid",
        )
    if not source_text:
        return CitationVerdict(
            False,
            MatchType.NOT_FOUND,
            None,
            0.0,
            "source text is empty; citation is NOT_FOUND and invalid",
        )

    exact_start = source_text.find(quote)
    if exact_start >= 0:
        return CitationVerdict(
            True,
            MatchType.EXACT,
            (exact_start, exact_start + len(quote)),
            1.0,
            "citation is an exact substring of the source",
        )

    normalized_quote = _normalize_with_offsets(quote)
    normalized_source = _normalize_with_offsets(source_text)
    if not normalized_quote.text or len(normalized_quote.text) > len(normalized_source.text):
        return CitationVerdict(
            False,
            MatchType.NOT_FOUND,
            None,
            0.0,
            "citation is absent from the source; NOT_FOUND is invalid",
        )

    normalized_start = normalized_source.text.find(normalized_quote.text)
    if normalized_start >= 0:
        normalized_end = normalized_start + len(normalized_quote.text)
        return CitationVerdict(
            True,
            MatchType.NORMALIZED,
            _normalized_span(normalized_source, normalized_start, normalized_end),
            1.0,
            "citation matches after case, whitespace, quote, dash, and punctuation normalization",
        )

    quote_tokens = normalized_quote.text.split()
    source_matches = list(re.finditer(r"\S+", normalized_source.text))
    source_tokens = [match.group() for match in source_matches]
    if not quote_tokens or not source_tokens:
        return CitationVerdict(
            False,
            MatchType.NOT_FOUND,
            None,
            0.0,
            "citation is absent from the source; NOT_FOUND is invalid",
        )

    best_score = 0.0
    best_span: tuple[int, int] | None = None
    quote_len = len(quote_tokens)
    for window_len in sorted({max(1, quote_len - 1), quote_len, quote_len + 1}):
        if window_len > len(source_tokens):
            continue
        for start in range(0, len(source_tokens) - window_len + 1):
            score = _token_set_ratio(quote_tokens, source_tokens[start : start + window_len])
            normalized_start = source_matches[start].start()
            normalized_end = source_matches[start + window_len - 1].end()
            span = _normalized_span(normalized_source, normalized_start, normalized_end)
            if score > best_score or (
                score == best_score and (best_span is None or span < best_span)
            ):
                best_score = score
                best_span = span

    rounded_score = round(best_score, 6)
    if best_span is not None and best_score >= CITATION_THRESHOLD:
        return CitationVerdict(
            True,
            MatchType.FUZZY,
            best_span,
            rounded_score,
            f"citation fuzzy token-set score {rounded_score:.3f} meets threshold {CITATION_THRESHOLD:.2f}",
        )
    return CitationVerdict(
        False,
        MatchType.NOT_FOUND,
        None,
        rounded_score,
        f"best citation score {rounded_score:.3f} is below threshold {CITATION_THRESHOLD:.2f}; NOT_FOUND is invalid",
    )
