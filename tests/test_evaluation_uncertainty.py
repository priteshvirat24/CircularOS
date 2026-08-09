from __future__ import annotations

import pytest

from packages.evaluation.uncertainty import ConfusionObservation, bootstrap_f1_ci


def test_bootstrap_interval_is_deterministic_and_contains_estimate() -> None:
    observations = [
        ConfusionObservation(true_positives=1),
        ConfusionObservation(true_positives=1),
        ConfusionObservation(false_positives=1),
        ConfusionObservation(false_negatives=1),
    ]

    first = bootstrap_f1_ci(observations, resamples=1000, seed=7)
    second = bootstrap_f1_ci(observations, resamples=1000, seed=7)

    assert first == second
    assert first.estimate == pytest.approx(2 / 3)
    assert first.lower <= first.estimate <= first.upper
    assert first.resamples == 1000


def test_bootstrap_perfect_predictions_have_degenerate_interval() -> None:
    interval = bootstrap_f1_ci(
        [ConfusionObservation(true_positives=1) for _ in range(8)],
        resamples=1000,
    )
    assert interval.estimate == interval.lower == interval.upper == 1.0


def test_bootstrap_validates_inputs() -> None:
    with pytest.raises(ValueError, match="at least one"):
        bootstrap_f1_ci([])
    with pytest.raises(ValueError, match="positive"):
        bootstrap_f1_ci([ConfusionObservation(true_positives=1)], resamples=0)

