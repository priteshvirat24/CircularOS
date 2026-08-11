"""Extract top-level numbered section units from a regulation's text.

The stored clause table is lossy on re-consolidated master circulars (the parser merges
sections into blobs), so the diff engine reconstructs a clean section tree from the document
text using two reliable signals:

  1. The Table of Contents gives authoritative ``{number: title}`` (clean, single source).
  2. The document body gives each section's char span (heading followed by its own ``N.1``
     sub-clause), used for CREATED text and citation offsets.

Both are validated against the real Aug-2024 / Jun-2025 SEBI stockbroker master circulars.
"""

from __future__ import annotations

import re

from packages.diff_engine.normalize import normalize_for_match, strip_footnote_number
from packages.diff_engine.types import SectionUnit

_ROMAN_PART = re.compile(r"^\s*[IVXL]+\.\s")
_TOC_ENTRY = re.compile(r"^\s*(\d{1,3})\.\s*(.*)$")
_PAGE_NO = re.compile(r"^\s*(\d{1,3})\s*$")
_BODY_HEADING = re.compile(
    r"(?m)^[ \t]*(\d{1,3})\.[ \t]*(?:\n[ \t]*)?(\S[^\n]{3,})"
)


def parse_toc(text: str) -> dict[int, str]:
    """Parse the Table of Contents into ``{section_number: title}``.

    Entries are ``N. Title(wrapped across lines) <page-number-line>``; roman-numeral part
    headers are skipped. The TOC region runs from 'TABLE OF CONTENTS' to the first body
    sub-clause marker (the body's first ``1.1.``), which the TOC itself never contains.
    """
    ts = text.find("TABLE OF CONTENTS")
    if ts < 0:
        return {}
    body_start = text.find("1.1.", ts)
    toc = text[ts: body_start if body_start > ts else ts + 12000]

    out: dict[int, str] = {}
    cur: int | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal cur, buf
        if cur is not None:
            title = re.sub(r"\s+", " ", " ".join(buf)).strip()
            if title and cur not in out:
                out[cur] = strip_footnote_number(title)
        cur, buf = None, []

    for line in toc.splitlines():
        if _ROMAN_PART.match(line):
            flush()
            continue
        m = _TOC_ENTRY.match(line)
        if m:
            flush()
            cur = int(m.group(1))
            rest = m.group(2).strip()
            if rest:
                buf.append(rest)
            continue
        if _PAGE_NO.match(line):
            flush()
            continue
        if line.strip() and cur is not None:
            buf.append(line.strip())
    flush()
    return out


def locate_body_spans(text: str) -> dict[int, tuple[int, int]]:
    """Locate each top-level section's body span ``{number: (char_start, char_end)}``.

    A body heading is ``N. Title…``. The authoritative TOC title selects the matching body
    occurrence and disambiguates TOC rows and annexures that restart numbering. This also covers
    source numbering defects where a section is not followed by its own ``N.1`` marker.
    ``char_end`` is the start of the next selected top-level heading.
    """
    toc = parse_toc(text)
    candidates: dict[int, list[tuple[int, str]]] = {}
    for m in _BODY_HEADING.finditer(text):
        num = int(m.group(1))
        candidates.setdefault(num, []).append((m.start(), m.group(2)))

    toc_start = text.find("TABLE OF CONTENTS")
    first_number = min(toc, default=1)
    first_subclause = text.find(
        f"{first_number}.1.", toc_start if toc_start >= 0 else 0
    )
    first_section_candidates = [
        start
        for start, _ in candidates.get(first_number, [])
        if first_subclause < 0 or start < first_subclause
    ]
    body_region_start = max(first_section_candidates, default=0)

    # Annexures restart numbering at 1 and contain their own ``N.1`` children. Choosing the
    # longest same-numbered span therefore maps top-level sections to unrelated annexures.
    # The TOC title is authoritative: choose the heading whose normalized line is the best
    # prefix match, then form spans only from those chosen top-level headings.
    chosen: list[tuple[int, int]] = []
    for num, title in toc.items():
        expected = normalize_for_match(title)

        def score(
            candidate: tuple[int, str], expected_title: str = expected
        ) -> tuple[int, float, int]:
            start, heading = candidate
            actual = re.sub(r"\s+\d+$", "", normalize_for_match(heading)).strip()
            prefix = int(
                expected_title.startswith(actual) or actual.startswith(expected_title)
            )
            expected_tokens = set(expected_title.split())
            actual_tokens = set(actual.split())
            overlap = len(expected_tokens & actual_tokens) / max(
                1, len(expected_tokens | actual_tokens)
            )
            # TOC candidates are already excluded by ``body_region_start``. Prefer the first
            # equally strong body heading so later annexure repetitions cannot win a tie.
            return prefix, overlap, -start

        options = [
            candidate
            for candidate in candidates.get(num, [])
            if candidate[0] >= body_region_start
        ]
        if options:
            start, _ = max(options, key=score)
            chosen.append((num, start))

    chosen.sort(key=lambda item: item[1])
    return {
        num: (start, chosen[index + 1][1] if index + 1 < len(chosen) else len(text))
        for index, (num, start) in enumerate(chosen)
    }


def assign_to_sections(
    sections: list[SectionUnit],
    items: list[tuple[str, object]],
) -> dict[int, list[object]]:
    """Group ``(probe_text, payload)`` items by the section whose body contains the probe.

    Deterministic mapping used to attach extracted obligations to their top-level section when
    the parser's clause numbering is too lossy to key on (each obligation's source clause text is
    matched into a section body). Items matching no section body are dropped from the result.
    """
    out: dict[int, list[object]] = {}
    # Normalize both sides (whitespace/case/quotes) so parser clause text matches the section
    # body despite PDF line-wrapping differences.
    bodies = [(s.number, normalize_for_match(s.body)) for s in sections if s.body]
    for probe_text, payload in items:
        probe = normalize_for_match(probe_text)[:120]
        if len(probe) < 20:
            continue
        for number, body in bodies:
            if probe in body:
                out.setdefault(number, []).append(payload)
                break
    return out


def extract_sections(text: str, max_body_chars: int = 4000) -> list[SectionUnit]:
    """Build the ordered list of ``SectionUnit`` for a document.

    Titles come from the TOC; char spans and body text from ``locate_body_spans``. Sections
    present in the TOC but not locatable in the body still appear (title-only) so the matcher
    can align them; their ``body`` is empty.
    """
    toc = parse_toc(text)
    spans = locate_body_spans(text)
    units: list[SectionUnit] = []
    for num in sorted(toc):
        title = toc[num]
        span = spans.get(num)
        start: int | None
        end: int | None
        if span:
            start, end = span
            body = text[start: min(end, start + max_body_chars)]
        else:
            start = end = None
            body = ""
        units.append(SectionUnit(number=num, title=title, char_start=start,
                                 char_end=end, body=body))
    return units
