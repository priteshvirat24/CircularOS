"""Section extraction + end-to-end engine tests on a compact, realistic fixture.

The fixture mimics the real re-consolidation pattern: a new section is inserted, shifting every
later section's number by one (a renumber that must NOT be reported), one section's title is
narrowed (a real MODIFIED), and a genuinely new section appears at the end (a CREATED).
"""

from __future__ import annotations

from packages.diff_engine import run_diff_pipeline
from packages.diff_engine.sections import extract_sections, parse_toc
from packages.policy_engine.changes import MaterialityLevel

OLD_DOC = """MASTER CIRCULAR

TABLE OF CONTENTS
I. SUPERVISION
16. Annual System Audit of Stock Brokers
16
17. Review of norms relating to trading by Members/ Sub-Brokers
17
18. Cyber Security framework for Stock Brokers
18

I. SUPERVISION

16. Annual System Audit of Stock Brokers
16.1. The stock broker shall undergo an annual system audit.
16.2. The audit report shall be submitted to the exchange.

17. Review of norms relating to trading by Members/ Sub-Brokers
17.1. Stock Exchanges are directed to review the norms.

18. Cyber Security framework for Stock Brokers
18.1. Brokers shall report cyber incidents within 6 hours.
"""

NEW_DOC = """MASTER CIRCULAR

TABLE OF CONTENTS
I. SUPERVISION
16. Annual System Audit of Stock Brokers
16
17. Framework for Monitoring and Supervision of System Audit through Technology
17
18. Review of norms relating to trading by Members
18
19. Cyber Security framework for Stock Brokers
19

I. SUPERVISION

16. Annual System Audit of Stock Brokers
16.1. The stock broker shall undergo an annual system audit.
16.2. The audit report shall be submitted to the exchange.

17. Framework for Monitoring and Supervision of System Audit through Technology
17.1. Stock Exchanges shall develop a web portal to monitor the audit lifecycle.

18. Review of norms relating to trading by Members
18.1. Stock Exchanges are directed to review the norms.

19. Cyber Security framework for Stock Brokers
19.1. Brokers shall report cyber incidents within 6 hours.
"""


def test_parse_toc_recovers_numbers_and_titles():
    toc = parse_toc(OLD_DOC)
    assert toc[16] == "Annual System Audit of Stock Brokers"
    assert toc[17].startswith("Review of norms relating to trading by Members")
    assert toc[18] == "Cyber Security framework for Stock Brokers"


def test_extract_sections_locates_bodies():
    secs = {s.number: s for s in extract_sections(NEW_DOC)}
    assert set(secs) == {16, 17, 18, 19}
    assert "web portal" in secs[17].body
    assert secs[16].char_start is not None


def test_engine_created_modified_and_suppresses_renumber():
    res = run_diff_pipeline(OLD_DOC, NEW_DOC)

    created = [c for c in res.changes if c.change_type == "created"]
    modified = [c for c in res.changes if c.change_type == "modified"]

    # §17 (new "Framework for Monitoring…") is CREATED and high-risk (monitor/supervis/audit).
    assert len(created) == 1
    assert created[0].new_ref == "§17"
    assert created[0].materiality is MaterialityLevel.HIGH

    # Old §17 "…Members/ Sub-Brokers" → new §18 "…Members" is a MODIFIED (scope narrowed), LOW.
    assert len(modified) == 1
    assert modified[0].old_ref == "§17" and modified[0].new_ref == "§18"
    assert modified[0].materiality is MaterialityLevel.LOW
    assert modified[0].changed_fields  # non-empty

    # The Cyber-Security renumber (§18 → §19, identical title) must NOT be reported.
    assert res.summary["cosmetic_suppressed"] >= 2  # §16 unchanged + §18→§19 renumber
    assert all(not (c.old_ref == "§18" and c.new_ref == "§19") for c in res.changes)


def test_engine_summary_counts_and_matcher_metadata():
    res = run_diff_pipeline(OLD_DOC, NEW_DOC)
    assert res.summary["created"] == 1
    assert res.summary["modified"] == 1
    assert res.matcher["algorithm"] == "hungarian"
    assert res.text_diff.identical_ratio > 0.0


def test_real_pair_meets_goldset_exit_gate():
    """End-to-end on the real Aug-2024 → Jun-2025 SEBI pair vs the labeled change-set.

    Exit gate: all 6 gold CREATED + the 1 MODIFIED are surfaced, and ZERO of the 12 labeled
    cosmetic renumberings are reported as substantive changes. Skips if the PDFs aren't present.
    """
    import json
    import os

    import pytest

    aug = "data/goldsets/circulars/stockbrokers_master_2024-08-09.pdf"
    jun = "data/goldsets/circulars/stockbrokers_master_2025-06-17.pdf"
    changeset = "data/goldsets/changeset.jsonl"
    if not all(os.path.exists(p) for p in (aug, jun, changeset)):
        pytest.skip("real corpus PDFs / changeset not present")

    import fitz

    from packages.diff_engine.evaluate import evaluate_against_changeset

    def ft(p):
        d = fitz.open(p)
        t = "\n".join(pg.get_text() for pg in d)
        d.close()
        return t

    new_text = ft(jun)
    res = run_diff_pipeline(ft(aug), new_text)
    gold = [json.loads(ln) for ln in open(changeset) if ln.strip()]
    m = evaluate_against_changeset(res, gold, new_text)

    assert m["created_detected"] == m["gold"]["created"], m["created_missed"]
    assert m["modified_detected"] == m["gold"]["modified"], m["modified_missed"]
    assert m["cosmetic_false_positives"] == [], m["cosmetic_false_positives"]


def test_embedding_backend_degrades_gracefully():
    def broken(_a, _b):
        raise RuntimeError("embedding provider down")

    res = run_diff_pipeline(OLD_DOC, NEW_DOC, embed_similarity=broken)
    assert "lexical" in res.matcher["similarity_backend"]
    assert res.notes  # degradation is surfaced, not silent
