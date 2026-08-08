"""Text normalization for diffing (PDF layout drift → clean, comparable text).

Two functions:
- ``normalize_for_match`` — aggressive: casefold, collapse whitespace, standardize quotes/
  dashes. Used only for *matching* (never persisted as a citation).
- ``clean_document_text`` — light: drop standalone page-number lines and repeated header
  noise while preserving readable body text for CREATED spans.
"""

from __future__ import annotations

import re

_PAGE_NUM_LINE = re.compile(r"^\s*\d{1,4}\s*$")
_QUOTES = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "−": "-",
}


def _fold_punct(s: str) -> str:
    for k, v in _QUOTES.items():
        s = s.replace(k, v)
    return s


def normalize_for_match(text: str) -> str:
    """Casefold + collapse whitespace + standardize quotes/dashes. For matching only."""
    if not text:
        return ""
    s = _fold_punct(text)
    s = re.sub(r"\s+", " ", s).strip().casefold()
    return s


def strip_footnote_number(title: str) -> str:
    """Drop a trailing footnote/page superscript glued to a title (e.g. '…Members42')."""
    return re.sub(r"\d+\s*$", "", title).strip()


def canonical_title(title: str) -> str:
    """Canonical form of a section title for *comparison* (not display).

    Folds smart quotes/dashes, collapses whitespace, strips a trailing footnote number and any
    leading/trailing punctuation — so a dropped opening quote or a stray footnote never reads
    as a substantive change, while an internal wording change (e.g. '…Members/ Sub-Brokers' →
    '…Members') still does.
    """
    s = _fold_punct(title or "")
    s = re.sub(r"\s+", " ", s).strip()
    s = strip_footnote_number(s)
    s = s.strip(" \t\"'.,:;–-()")
    return s.casefold()


def clean_document_text(text: str) -> str:
    """Remove standalone page-number lines; keep the rest of the body readable."""
    if not text:
        return ""
    lines = [ln for ln in text.splitlines() if not _PAGE_NUM_LINE.match(ln)]
    return "\n".join(lines)


def paragraphs(text: str) -> list[str]:
    """Split into normalized non-empty paragraph blocks for the Level-1 anchor diff."""
    blocks = re.split(r"\n\s*\n", text or "")
    out = []
    for b in blocks:
        n = normalize_for_match(b)
        if n:
            out.append(n)
    return out
