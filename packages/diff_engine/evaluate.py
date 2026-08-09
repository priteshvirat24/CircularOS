"""Score the diff engine against the hand-labeled gold change-set (real numbers, not hardcoded).

Given a ``DiffResult`` and the rows of ``data/goldsets/changeset.jsonl``, compute:
  - detection of gold CREATED / MODIFIED (matched by section ref + text containment), and
  - the headline false-positive guard: how many of the 12 labeled cosmetic renumberings
    (``NOT_A_CHANGE``) were wrongly reported as substantive changes (target: 0).

Pure/deterministic: text in, metrics out. Callable from a script or a test.
"""

from __future__ import annotations

import re

from packages.diff_engine.types import DiffResult


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().casefold()


def _ref_number(ref: str | None) -> int | None:
    """Section number from a ref like '§31' or 'Aug-2024 §31 (TOC)' — the digits after §."""
    if not ref:
        return None
    m = re.search(r"§\s*(\d{1,3})", ref)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d{1,3})\b", ref)  # bare-number fallback ('31')
    return int(m.group(1)) if m else None


def evaluate_against_changeset(
    result: DiffResult, gold: list[dict], new_full_text: str = ""
) -> dict:
    """Return a metrics dict comparing detected changes to the gold change-set.

    ``new_full_text`` (the Jun document text) lets CREATED detection confirm a gold item's
    ``new_text`` falls inside the detected new section's *full* body, even when the persisted
    excerpt is truncated.
    """
    detected = result.changes
    detected_created = [c for c in detected if c.change_type == "created"]
    detected_modified = [c for c in detected if c.change_type == "modified"]

    # Detected change section numbers (new-side for created/modified; old-side for removed).
    created_new_nums = {_ref_number(c.new_ref) for c in detected_created}
    modified_pairs = {(_ref_number(c.old_ref), _ref_number(c.new_ref)) for c in detected_modified}

    created_hits: list[str] = []
    created_misses: list[str] = []
    modified_hits: list[str] = []
    modified_misses: list[str] = []
    cosmetic_false_positives: list[str] = []

    # A CREATED gold row is detected if its new_text appears in a detected CREATED section's
    # body/title, or its section number was flagged CREATED.
    created_bodies = [_norm(c.obligation) + " " + _norm(c.new_text) for c in detected_created]
    new_ft = _norm(new_full_text)

    for row in gold:
        ct = row.get("change_type")
        new_num = _ref_number(row.get("new_ref"))
        old_num = _ref_number(row.get("old_ref"))
        new_text = _norm(row.get("new_text"))

        if ct == "CREATED":
            by_num = new_num in created_new_nums
            by_text = any(new_text and new_text in b for b in created_bodies)
            # Also allow: the gold new_text lives inside a detected CREATED section's full body
            # in the new document (handles sub-obligations of a newly-created section).
            by_fulltext = False
            if not (by_num or by_text) and new_text and new_text in new_ft:
                # containment in a detected created section's char span
                for c in detected_created:
                    span = c.citations.get("new", {}).get("span")
                    if span and span[0] is not None and span[1] is not None:
                        seg = _norm(new_full_text[span[0] : span[1]])
                        if new_text in seg:
                            by_fulltext = True
                            break
            (created_hits if (by_num or by_text or by_fulltext) else created_misses).append(
                row["id"]
            )

        elif ct == "MODIFIED":
            hit = any(
                (old_num in (mp[0], None) or mp[0] == old_num) and mp[1] == new_num
                for mp in modified_pairs
            ) or any(mp[1] == new_num for mp in modified_pairs)
            (modified_hits if hit else modified_misses).append(row["id"])

        elif ct == "NOT_A_CHANGE":
            # A cosmetic pair is a false positive only when that exact old→new alignment is
            # reported as substantive (or its new section is reported CREATED). Merely sharing
            # one section number with an adjacent genuine change is not a match.
            flagged = new_num in created_new_nums or (old_num, new_num) in modified_pairs
            if flagged:
                cosmetic_false_positives.append(row["id"])

    n_created = sum(1 for r in gold if r.get("change_type") == "CREATED")
    n_modified = sum(1 for r in gold if r.get("change_type") == "MODIFIED")
    n_cosmetic = sum(1 for r in gold if r.get("change_type") == "NOT_A_CHANGE")

    return {
        "gold": {"created": n_created, "modified": n_modified, "cosmetic": n_cosmetic},
        "created_detected": len(created_hits),
        "created_missed": created_misses,
        "modified_detected": len(modified_hits),
        "modified_missed": modified_misses,
        "cosmetic_false_positives": cosmetic_false_positives,
        "cosmetic_false_positive_rate": round(len(cosmetic_false_positives) / n_cosmetic, 4)
        if n_cosmetic
        else 0.0,
        "detection_rate_created": round(len(created_hits) / n_created, 4) if n_created else 0.0,
        "detection_rate_modified": round(len(modified_hits) / n_modified, 4) if n_modified else 0.0,
    }
