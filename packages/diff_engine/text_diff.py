"""Level 1 — normalized paragraph-level anchor diff (the cheap pre-filter).

Master circulars are largely consolidations: most text is byte-identical. This level uses a
``difflib`` longest-common-subsequence pass over normalized paragraphs to cheaply measure how
much is unchanged and how many blocks actually differ, so a human (and the report) can see the
signal-to-noise up front. It short-circuits identical regions rather than re-embedding them.
"""

from __future__ import annotations

from difflib import SequenceMatcher

from packages.diff_engine.normalize import paragraphs
from packages.diff_engine.types import TextDiffResult


def text_diff(old_text: str, new_text: str) -> TextDiffResult:
    old_blocks = paragraphs(old_text)
    new_blocks = paragraphs(new_text)
    sm = SequenceMatcher(a=old_blocks, b=new_blocks, autojunk=False)

    identical = 0
    changed_old = 0
    changed_new = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            identical += (i2 - i1)
        else:
            changed_old += (i2 - i1)
            changed_new += (j2 - j1)

    total_old = len(old_blocks)
    total_new = len(new_blocks)
    denom = max(total_old, total_new, 1)
    identical_ratio = identical / denom

    return TextDiffResult(
        identical_ratio=round(identical_ratio, 4),
        changed_old_blocks=changed_old,
        changed_new_blocks=changed_new,
        total_old_blocks=total_old,
        total_new_blocks=total_new,
    )
