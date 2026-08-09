#!/usr/bin/env python3
"""Evaluate the hand-labelled August citation threshold set."""

from __future__ import annotations

import json
from pathlib import Path

from packages.policy_engine.citations import CITATION_THRESHOLD, verify_citation

DATASET = Path("data/goldsets/citation_threshold.jsonl")
PRECISION_FLOOR = 0.98


def main() -> None:
    rows = [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]
    scored = [
        (bool(row["label"]), verify_citation(row["quote"], row["source"]).score)
        for row in rows
    ]
    operating_points: list[dict[str, float | int]] = []
    for step in range(90, 101):
        threshold = step / 100
        true_positive = sum(label and score >= threshold for label, score in scored)
        false_positive = sum(not label and score >= threshold for label, score in scored)
        false_negative = sum(label and score < threshold for label, score in scored)
        precision = true_positive / (true_positive + false_positive) if true_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive else 0.0
        operating_points.append(
            {
                "threshold": threshold,
                "precision": round(precision, 6),
                "recall": round(recall, 6),
                "tp": true_positive,
                "fp": false_positive,
                "fn": false_negative,
            }
        )
    eligible = [point for point in operating_points if point["precision"] >= PRECISION_FLOOR]
    best_recall = max(point["recall"] for point in eligible)
    selected = min(
        (point for point in eligible if point["recall"] == best_recall),
        key=lambda point: point["threshold"],
    )
    print(
        json.dumps(
            {
                "dataset": str(DATASET),
                "real_august_obligations": len({row["obligation_id"] for row in rows}),
                "cases": len(rows),
                "precision_floor": PRECISION_FLOOR,
                "configured_threshold": CITATION_THRESHOLD,
                "selected_operating_point": selected,
                "operating_points": operating_points,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
