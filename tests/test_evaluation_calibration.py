from __future__ import annotations

import json

import numpy as np
import pytest

from packages.evaluation.calibration import (
    ConfidenceTrainingRow,
    apply_isotonic,
    brier_score,
    expected_calibration_error,
    export_confidence_params,
    fit_calibration,
    fit_isotonic,
    fit_logistic_mle,
    load_confidence_params,
    reliability_diagram_data,
)
from packages.policy_engine.confidence import DEFAULT_CONFIDENCE_PARAMS


def fixture_rows() -> list[ConfidenceTrainingRow]:
    rows: list[ConfidenceTrainingRow] = []
    for index in range(40):
        correct = index >= 18
        strength = index / 39
        rows.append(
            ConfidenceTrainingRow(
                citation_score=0.45 + 0.55 * strength,
                entailment=1.0 if correct else (-1.0 if index < 6 else 0.0),
                critic_objection=0.0 if correct else 1.0,
                self_confidence=0.35 + 0.6 * strength,
                difficulty=0.0 if index > 30 else (1.0 if index < 10 else 0.5),
                correct=correct,
            )
        )
    return rows


def test_logistic_mle_and_platt_calibration_run_end_to_end() -> None:
    result = fit_calibration(fixture_rows(), version="fixture-provisional")

    assert result.params.version == "fixture-provisional"
    assert result.train_size + result.calibration_size == 40
    assert 0.0 <= result.ece <= 1.0
    assert 0.0 <= result.brier <= 1.0
    assert sum(int(point["count"]) for point in result.reliability) == result.calibration_size
    assert len(result.raw_probabilities) == result.calibration_size


def test_logistic_fit_requires_both_classes() -> None:
    rows = [ConfidenceTrainingRow(1.0, 1.0, 0.0, 0.9, 0.0, True) for _ in range(5)]
    with pytest.raises(ValueError, match="both correct and incorrect"):
        fit_logistic_mle(rows)


def test_calibration_requires_two_examples_per_class() -> None:
    rows = [
        ConfidenceTrainingRow(1.0, 1.0, 0.0, 0.9, 0.0, True),
        ConfidenceTrainingRow(0.9, 1.0, 0.0, 0.8, 0.0, True),
        ConfidenceTrainingRow(0.8, 0.0, 0.0, 0.7, 0.5, True),
        ConfidenceTrainingRow(0.4, -1.0, 1.0, 0.3, 1.0, False),
    ]
    with pytest.raises(ValueError, match="at least two"):
        fit_calibration(rows)


def test_isotonic_pool_adjacent_violators_is_monotone() -> None:
    calibrator = fit_isotonic([0.1, 0.2, 0.3, 0.4], [0, 1, 0, 1])
    calibrated = apply_isotonic([0.1, 0.2, 0.3, 0.4], calibrator)
    assert np.all(np.diff(calibrated) >= 0)


def test_ece_brier_and_reliability_known_answers() -> None:
    probabilities = [0.0, 1.0, 0.25, 0.75]
    labels = [0, 1, 0, 1]
    assert brier_score(probabilities, labels) == pytest.approx(0.03125)
    assert expected_calibration_error(probabilities, labels, bins=2) == pytest.approx(0.125)
    diagram = reliability_diagram_data(probabilities, labels, bins=2)
    assert sum(int(point["count"]) for point in diagram) == 4


def test_provisional_artifact_is_not_activated_and_calibrated_one_is(tmp_path) -> None:
    result = fit_calibration(fixture_rows(), version="fixture-v1")
    path = tmp_path / "params.json"

    export_confidence_params(result, path, status="PROVISIONAL")
    provisional = load_confidence_params(path)
    assert not provisional.loaded
    assert provisional.params == DEFAULT_CONFIDENCE_PARAMS
    assert provisional.artifact_status == "PROVISIONAL"

    export_confidence_params(result, path, status="CALIBRATED")
    calibrated = load_confidence_params(path)
    assert calibrated.loaded
    assert calibrated.params.version == "fixture-v1"
    assert json.loads(path.read_text())["status"] == "CALIBRATED"


def test_missing_artifact_falls_back_to_explicit_unfitted_defaults(tmp_path) -> None:
    loaded = load_confidence_params(tmp_path / "missing.json")
    assert not loaded.loaded
    assert loaded.params.version == "phase3-default-unfitted"
