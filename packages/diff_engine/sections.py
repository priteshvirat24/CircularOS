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

from packages.diff_engine.normalize import strip_footnote_number
from packages.diff_engine.types import SectionUnit

_ROMAN_PART = re.compile(r"^\s*[IVXL]+\.\s")
_TOC_ENTRY = re.compile(r"^\s*(\d{1,3})\.\s*(.*)$")
_PAGE_NO = re.compile(r"^\s*(\d{1,3})\s*$")
_BODY_HEADING = re.compile(r"(?m)^[ \t]*(\d{1,3})\.[ \t]+([A-Z][^\n]{3,})")


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

    A body heading is ``N. Title…`` followed, within ~900 chars, by its own first sub-clause
    ``N.1`` — this discriminates real body headings from TOC entries (followed by page numbers)
    and from sub-clauses. ``char_end`` is the start of the next detected top-level heading.
    """
    starts: list[tuple[int, int]] = []  # (number, char_start)
    for m in _BODY_HEADING.finditer(text):
        num = int(m.group(1))
        window = text[m.end(): m.end() + 900]
        if not re.search(r"\b%d\.1[.\s]" % num, window):
            continue
        starts.append((num, m.start()))

    spans: dict[int, tuple[int, int]] = {}
    for i, (num, start) in enumerate(starts):
        end = starts[i + 1][1] if i + 1 < len(starts) else len(text)
        # Keep the longest (real body over any short part-intro duplicate) per number.
        if num not in spans or (end - start) > (spans[num][1] - spans[num][0]):
            spans[num] = (start, end)
    return spans


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
