"""Pure bootstrap uncertainty for extraction F1."""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from packages.evaluation.metrics import metrics_from_confusion


@dataclass(frozen=True)
class ConfusionObservation:
    """One resampling unit's contribution to TP/FP/FN."""

    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    def __post_init__(self) -> None:
        if min(self.true_positives, self.false_positives, self.false_negatives) < 0:
            raise ValueError("confusion contributions cannot be negative")


@dataclass(frozen=True)
class BootstrapInterval:
    estimate: float
    lower: float
    upper: float
    confidence_level: float
    resamples: int
    seed: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "estimate": self.estimate,
            "lower": self.lower,
            "upper": self.upper,
            "confidence_level": self.confidence_level,
            "resamples": self.resamples,
            "seed": self.seed,
        }


def bootstrap_f1_ci(
    observations: Sequence[ConfusionObservation],
    *,
    resamples: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> BootstrapInterval:
    """Percentile bootstrap interval over evaluation observations."""
    if not observations:
        raise ValueError("at least one observation is required")
    if resamples <= 0:
        raise ValueError("resamples must be positive")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be between 0 and 1")

    total_tp = sum(item.true_positives for item in observations)
    total_fp = sum(item.false_positives for item in observations)
    total_fn = sum(item.false_negatives for item in observations)
    estimate = metrics_from_confusion(total_tp, total_fp, total_fn)[2]

    random_source = random.Random(seed)
    values: list[float] = []
    for _ in range(resamples):
        sample = random_source.choices(observations, k=len(observations))
        tp = sum(item.true_positives for item in sample)
        fp = sum(item.false_positives for item in sample)
        fn = sum(item.false_negatives for item in sample)
        values.append(metrics_from_confusion(tp, fp, fn)[2])
    tail = (1.0 - confidence_level) / 2.0
    lower, upper = np.quantile(np.asarray(values), [tail, 1.0 - tail]).tolist()
    return BootstrapInterval(
        estimate, float(lower), float(upper), confidence_level, resamples, seed
    )
