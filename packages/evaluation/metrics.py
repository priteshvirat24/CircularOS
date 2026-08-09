"""Pure extraction metrics with no database or model dependencies."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from packages.evaluation.matching import (
    EvaluationObligation,
    MatchedPair,
    MatchOutcome,
    normalize_text,
    normalized_similarity,
)

Matcher = Callable[[Sequence[EvaluationObligation], Sequence[EvaluationObligation]], MatchOutcome]


@dataclass(frozen=True)
class ExtractionMetrics:
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    matched_pairs: tuple[MatchedPair, ...]

    @property
    def confusion(self) -> dict[str, int]:
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
        }


def metrics_from_confusion(
    true_positives: int, false_positives: int, false_negatives: int
) -> tuple[float, float, float]:
    """Compute P/R/F1, defining an empty-vs-empty comparison as perfect."""
    if min(true_positives, false_positives, false_negatives) < 0:
        raise ValueError("confusion counts cannot be negative")
    precision_denominator = true_positives + false_positives
    recall_denominator = true_positives + false_negatives
    precision = (
        true_positives / precision_denominator
        if precision_denominator
        else float(recall_denominator == 0)
    )
    recall = (
        true_positives / recall_denominator
        if recall_denominator
        else float(precision_denominator == 0)
    )
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def precision_recall_f1(
    predictions: Sequence[EvaluationObligation],
    gold: Sequence[EvaluationObligation],
    matcher: Matcher,
) -> ExtractionMetrics:
    """Match one-to-one and compute the standard extraction confusion and P/R/F1."""
    outcome = matcher(predictions, gold)
    true_positives = len(outcome.matched_pairs)
    false_positives = len(outcome.unmatched_prediction_indices)
    false_negatives = len(outcome.unmatched_gold_indices)
    precision, recall, f1 = metrics_from_confusion(true_positives, false_positives, false_negatives)
    return ExtractionMetrics(
        true_positives,
        false_positives,
        false_negatives,
        precision,
        recall,
        f1,
        outcome.matched_pairs,
    )


def _field_value(record: EvaluationObligation, name: str) -> Any:
    if name == "actor":
        return record.actor
    if name == "action":
        return record.action
    return record.fields.get(name)


def _normalized_field(value: Any) -> str | tuple[str, ...]:
    if isinstance(value, (list, tuple, set)):
        return tuple(sorted(normalize_text(item) for item in value if normalize_text(item)))
    return normalize_text(value)


def field_accuracy(
    matched_pairs: Sequence[MatchedPair],
    fields: Sequence[str] = ("actor", "action", "deadline", "frequency", "evidence"),
) -> dict[str, float | None]:
    """Compute exact normalized field accuracy over matched pairs only."""
    if not matched_pairs:
        return {name: None for name in fields}
    result: dict[str, float | None] = {}
    for name in fields:
        if name in {"actor", "action"}:
            correct = sum(
                normalized_similarity(
                    _field_value(pair.prediction, name),
                    _field_value(pair.gold, name),
                    actor=name == "actor",
                )
                == 1.0
                for pair in matched_pairs
            )
        else:
            correct = sum(
                _normalized_field(_field_value(pair.prediction, name))
                == _normalized_field(_field_value(pair.gold, name))
                for pair in matched_pairs
            )
        result[name] = correct / len(matched_pairs)
    return result


def accuracy_by_group(
    outcomes: Sequence[tuple[str, bool]], groups: Sequence[str] = ("easy", "medium", "hard")
) -> Mapping[str, dict[str, int | float | None]]:
    """Return transparent per-band accuracy and denominators."""
    result: dict[str, dict[str, int | float | None]] = {}
    for group in groups:
        selected = [passed for label, passed in outcomes if label == group]
        correct = sum(selected)
        result[group] = {
            "correct": correct,
            "total": len(selected),
            "accuracy": correct / len(selected) if selected else None,
        }
    return result
