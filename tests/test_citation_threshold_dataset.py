from __future__ import annotations

import json
from pathlib import Path

from packages.policy_engine.citations import CITATION_THRESHOLD, verify_citation


def test_august_threshold_set_selects_point_nine_five() -> None:
    dataset = Path("data/goldsets/citation_threshold.jsonl")
    rows = [json.loads(line) for line in dataset.read_text().splitlines() if line.strip()]
    assert len(rows) == 24
    assert len({row["obligation_id"] for row in rows}) == 12
    scored = [
        (bool(row["label"]), verify_citation(row["quote"], row["source"]).score)
        for row in rows
    ]

    def metrics(threshold: float) -> tuple[float, float]:
        true_positive = sum(label and score >= threshold for label, score in scored)
        false_positive = sum(not label and score >= threshold for label, score in scored)
        false_negative = sum(label and score < threshold for label, score in scored)
        precision = true_positive / (true_positive + false_positive)
        recall = true_positive / (true_positive + false_negative)
        return precision, recall

    precision, recall = metrics(CITATION_THRESHOLD)
    assert precision >= 0.98
    assert recall == 1.0
    assert metrics(0.94)[0] < 0.98
