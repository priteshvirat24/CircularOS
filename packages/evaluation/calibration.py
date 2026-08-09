"""Confidence fitting, calibration, diagnostics, and parameter artifact I/O.

The Policy Decision Engine remains pure: this module owns fitting and file loading, then passes
an explicit ``ConfidenceParams`` value into ``aggregate_confidence``.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize  # type: ignore[import-untyped]

from packages.policy_engine.confidence import (
    DEFAULT_CONFIDENCE_PARAMS,
    ConfidenceParams,
)

DEFAULT_PARAMS_PATH = Path("data/goldsets/confidence_params.json")
FEATURE_NAMES = (
    "citation_score",
    "entailment",
    "critic_objection",
    "self_confidence",
    "difficulty",
)


@dataclass(frozen=True)
class ConfidenceTrainingRow:
    citation_score: float
    entailment: float
    critic_objection: float
    self_confidence: float
    difficulty: float
    correct: bool

    def features(self) -> tuple[float, ...]:
        return (
            self.citation_score,
            self.entailment,
            self.critic_objection,
            self.self_confidence,
            self.difficulty,
        )


@dataclass(frozen=True)
class PlattCalibrator:
    intercept: float
    slope: float


@dataclass(frozen=True)
class IsotonicCalibrator:
    upper_bounds: tuple[float, ...]
    values: tuple[float, ...]


@dataclass(frozen=True)
class CalibrationResult:
    params: ConfidenceParams
    raw_probabilities: tuple[float, ...]
    calibrated_probabilities: tuple[float, ...]
    labels: tuple[int, ...]
    ece: float
    brier: float
    reliability: tuple[dict[str, float | int], ...]
    method: str
    train_size: int
    calibration_size: int
    calibrator: PlattCalibrator | IsotonicCalibrator


@dataclass(frozen=True)
class LoadedConfidenceParams:
    params: ConfidenceParams
    loaded: bool
    artifact_status: str | None
    reason: str


def _validate_rows(rows: Sequence[ConfidenceTrainingRow]) -> None:
    if len(rows) < 4:
        raise ValueError("at least four labeled rows are required")
    labels = {row.correct for row in rows}
    if len(labels) != 2:
        raise ValueError("both correct and incorrect examples are required")
    counts = {label: sum(row.correct is label for row in rows) for label in (False, True)}
    if min(counts.values()) < 2:
        raise ValueError("at least two examples from each outcome class are required")
    for row in rows:
        for name, value in zip(FEATURE_NAMES, row.features(), strict=True):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")


def _matrix(
    rows: Sequence[ConfidenceTrainingRow],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    x = np.asarray([row.features() for row in rows], dtype=np.float64)
    y = np.asarray([float(row.correct) for row in rows], dtype=np.float64)
    return x, y


def _fit_binary_logistic(
    x: NDArray[np.float64], y: NDArray[np.float64], *, l2: float = 1e-4
) -> NDArray[np.float64]:
    if x.ndim != 2 or y.ndim != 1 or len(x) != len(y):
        raise ValueError("invalid logistic fitting shapes")
    design = np.column_stack((np.ones(len(x), dtype=np.float64), x))

    def objective(coefficients: NDArray[np.float64]) -> tuple[float, NDArray[np.float64]]:
        logits = design @ coefficients
        loss = np.logaddexp(0.0, logits).sum() - np.dot(y, logits)
        penalty = 0.5 * l2 * np.dot(coefficients[1:], coefficients[1:])
        probabilities = 1.0 / (1.0 + np.exp(-np.clip(logits, -700.0, 700.0)))
        gradient = design.T @ (probabilities - y)
        gradient[1:] += l2 * coefficients[1:]
        return float(loss + penalty), gradient

    fitted = minimize(
        objective,
        np.zeros(design.shape[1], dtype=np.float64),
        method="L-BFGS-B",
        jac=True,
    )
    if not fitted.success:
        raise RuntimeError(f"logistic MLE failed: {fitted.message}")
    return np.asarray(fitted.x, dtype=np.float64)


def fit_logistic_mle(
    rows: Sequence[ConfidenceTrainingRow], *, version: str = "phase4-provisional"
) -> ConfidenceParams:
    """Fit interpretable logistic coefficients by regularized maximum likelihood."""
    _validate_rows(rows)
    x, y = _matrix(rows)
    coefficients = _fit_binary_logistic(x, y)
    return ConfidenceParams(
        intercept=float(coefficients[0]),
        citation_score_weight=float(coefficients[1]),
        entailment_weight=float(coefficients[2]),
        critic_objection_weight=float(coefficients[3]),
        self_confidence_weight=float(coefficients[4]),
        difficulty_weight=float(coefficients[5]),
        version=version,
    )


def predict_probabilities(
    rows: Sequence[ConfidenceTrainingRow], params: ConfidenceParams
) -> NDArray[np.float64]:
    x, _ = _matrix(rows)
    weights = np.asarray(
        [
            params.citation_score_weight,
            params.entailment_weight,
            params.critic_objection_weight,
            params.self_confidence_weight,
            params.difficulty_weight,
        ],
        dtype=np.float64,
    )
    logits = params.intercept + x @ weights
    return 1.0 / (1.0 + np.exp(-np.clip(logits, -700.0, 700.0)))


def fit_platt(probabilities: Sequence[float], labels: Sequence[int]) -> PlattCalibrator:
    """Fit a monotone one-dimensional logistic transform on model logits."""
    if len(probabilities) != len(labels) or len(probabilities) < 2:
        raise ValueError("probabilities and labels must have the same non-trivial length")
    if len(set(labels)) != 2:
        raise ValueError("Platt fitting requires both label classes")
    clipped = np.clip(np.asarray(probabilities, dtype=np.float64), 1e-6, 1.0 - 1e-6)
    logits = np.log(clipped / (1.0 - clipped))
    y = np.asarray(labels, dtype=np.float64)

    def objective(coefficients: NDArray[np.float64]) -> tuple[float, NDArray[np.float64]]:
        calibrated_logits = coefficients[0] + coefficients[1] * logits
        loss = np.logaddexp(0.0, calibrated_logits).sum() - np.dot(y, calibrated_logits)
        predicted = 1.0 / (1.0 + np.exp(-np.clip(calibrated_logits, -700.0, 700.0)))
        residual = predicted - y
        gradient = np.asarray([residual.sum(), np.dot(residual, logits)])
        return float(loss), gradient

    fitted = minimize(
        objective,
        np.asarray([0.0, 1.0]),
        method="L-BFGS-B",
        jac=True,
        bounds=((None, None), (0.0, None)),
    )
    if not fitted.success:
        raise RuntimeError(f"Platt fitting failed: {fitted.message}")
    return PlattCalibrator(float(fitted.x[0]), float(fitted.x[1]))


def apply_platt(probabilities: Sequence[float], calibrator: PlattCalibrator) -> NDArray[np.float64]:
    clipped = np.clip(np.asarray(probabilities, dtype=np.float64), 1e-6, 1.0 - 1e-6)
    logits = np.log(clipped / (1.0 - clipped))
    calibrated_logits = calibrator.intercept + calibrator.slope * logits
    return 1.0 / (1.0 + np.exp(-np.clip(calibrated_logits, -700.0, 700.0)))


def fit_isotonic(probabilities: Sequence[float], labels: Sequence[int]) -> IsotonicCalibrator:
    """Pool-Adjacent-Violators fit for a non-decreasing step calibration function."""
    if len(probabilities) != len(labels) or not probabilities:
        raise ValueError("probabilities and labels must have the same non-zero length")
    ordered = sorted(zip(probabilities, labels, strict=True), key=lambda item: item[0])
    blocks: list[dict[str, float]] = []
    for probability, label in ordered:
        blocks.append({"upper": float(probability), "sum": float(label), "count": 1.0})
        while len(blocks) >= 2:
            previous = blocks[-2]["sum"] / blocks[-2]["count"]
            current = blocks[-1]["sum"] / blocks[-1]["count"]
            if previous <= current:
                break
            right = blocks.pop()
            left = blocks.pop()
            blocks.append(
                {
                    "upper": right["upper"],
                    "sum": left["sum"] + right["sum"],
                    "count": left["count"] + right["count"],
                }
            )
    return IsotonicCalibrator(
        tuple(block["upper"] for block in blocks),
        tuple(block["sum"] / block["count"] for block in blocks),
    )


def apply_isotonic(
    probabilities: Sequence[float], calibrator: IsotonicCalibrator
) -> NDArray[np.float64]:
    values: list[float] = []
    for probability in probabilities:
        index = next(
            (
                candidate
                for candidate, upper in enumerate(calibrator.upper_bounds)
                if probability <= upper
            ),
            len(calibrator.values) - 1,
        )
        values.append(calibrator.values[index])
    return np.asarray(values, dtype=np.float64)


def expected_calibration_error(
    probabilities: Sequence[float], labels: Sequence[int], *, bins: int = 10
) -> float:
    if len(probabilities) != len(labels) or not probabilities:
        raise ValueError("probabilities and labels must have the same non-zero length")
    if bins <= 0:
        raise ValueError("bins must be positive")
    p = np.asarray(probabilities, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    indices = np.minimum((np.clip(p, 0.0, 1.0) * bins).astype(int), bins - 1)
    ece = 0.0
    for bin_index in range(bins):
        selected = indices == bin_index
        if selected.any():
            ece += selected.mean() * abs(float(y[selected].mean() - p[selected].mean()))
    return float(ece)


def brier_score(probabilities: Sequence[float], labels: Sequence[int]) -> float:
    if len(probabilities) != len(labels) or not probabilities:
        raise ValueError("probabilities and labels must have the same non-zero length")
    p = np.asarray(probabilities, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    return float(np.mean((p - y) ** 2))


def reliability_diagram_data(
    probabilities: Sequence[float], labels: Sequence[int], *, bins: int = 10
) -> tuple[dict[str, float | int], ...]:
    if len(probabilities) != len(labels) or not probabilities:
        raise ValueError("probabilities and labels must have the same non-zero length")
    p = np.asarray(probabilities, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    indices = np.minimum((np.clip(p, 0.0, 1.0) * bins).astype(int), bins - 1)
    result: list[dict[str, float | int]] = []
    for bin_index in range(bins):
        selected = indices == bin_index
        if selected.any():
            result.append(
                {
                    "bin_lower": bin_index / bins,
                    "bin_upper": (bin_index + 1) / bins,
                    "count": int(selected.sum()),
                    "mean_confidence": float(p[selected].mean()),
                    "empirical_accuracy": float(y[selected].mean()),
                }
            )
    return tuple(result)


def _stratified_split(
    rows: Sequence[ConfidenceTrainingRow], fraction: float
) -> tuple[list[ConfidenceTrainingRow], list[ConfidenceTrainingRow]]:
    if not 0.0 < fraction < 0.5:
        raise ValueError("calibration fraction must be between 0 and 0.5")
    train: list[ConfidenceTrainingRow] = []
    calibration: list[ConfidenceTrainingRow] = []
    for label in (False, True):
        selected = [row for row in rows if row.correct is label]
        count = max(1, round(len(selected) * fraction))
        count = min(count, len(selected) - 1)
        calibration.extend(selected[:: max(1, len(selected) // count)][:count])
        calibration_ids = {id(row) for row in calibration}
        train.extend(row for row in selected if id(row) not in calibration_ids)
    return train, calibration


def _platt_adjusted_params(
    params: ConfidenceParams, calibrator: PlattCalibrator, version: str
) -> ConfidenceParams:
    slope = calibrator.slope
    return ConfidenceParams(
        intercept=calibrator.intercept + slope * params.intercept,
        citation_score_weight=slope * params.citation_score_weight,
        entailment_weight=slope * params.entailment_weight,
        critic_objection_weight=slope * params.critic_objection_weight,
        self_confidence_weight=slope * params.self_confidence_weight,
        difficulty_weight=slope * params.difficulty_weight,
        high_threshold=params.high_threshold,
        medium_threshold=params.medium_threshold,
        version=version,
    )


def fit_calibration(
    rows: Sequence[ConfidenceTrainingRow],
    *,
    method: Literal["platt", "isotonic"] = "platt",
    calibration_fraction: float = 0.20,
    bins: int = 10,
    version: str = "phase4-partial-provisional-v1",
) -> CalibrationResult:
    """Fit base logistic MLE, calibrate held-out scores, and compute ECE/Brier."""
    _validate_rows(rows)
    train, calibration_rows = _stratified_split(rows, calibration_fraction)
    base = fit_logistic_mle(train, version=f"{version}-base")
    raw = predict_probabilities(calibration_rows, base)
    labels = [int(row.correct) for row in calibration_rows]
    if method == "platt":
        platt = fit_platt(raw.tolist(), labels)
        calibrator: PlattCalibrator | IsotonicCalibrator = platt
        calibrated = apply_platt(raw.tolist(), platt)
        exported_params = _platt_adjusted_params(base, platt, version)
    else:
        calibrator = fit_isotonic(raw.tolist(), labels)
        calibrated = apply_isotonic(raw.tolist(), calibrator)
        exported_params = ConfidenceParams(**{**asdict(base), "version": version})
    calibrated_list = calibrated.tolist()
    return CalibrationResult(
        exported_params,
        tuple(float(value) for value in raw),
        tuple(float(value) for value in calibrated),
        tuple(labels),
        expected_calibration_error(calibrated_list, labels, bins=bins),
        brier_score(calibrated_list, labels),
        reliability_diagram_data(calibrated_list, labels, bins=bins),
        method,
        len(train),
        len(calibration_rows),
        calibrator,
    )


def export_confidence_params(
    result: CalibrationResult,
    path: str | Path = DEFAULT_PARAMS_PATH,
    *,
    status: Literal["PROVISIONAL", "CALIBRATED"] = "PROVISIONAL",
) -> Path:
    """Write an auditable artifact; provisional artifacts are never activated."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    calibrator_payload: dict[str, Any] = asdict(result.calibrator)
    payload = {
        "status": status,
        "version": result.params.version,
        "params": asdict(result.params),
        "feature_names": list(FEATURE_NAMES),
        "fit": {
            "method": "regularized-logistic-mle",
            "train_size": result.train_size,
            "calibration_size": result.calibration_size,
        },
        "calibration": {"method": result.method, **calibrator_payload},
        "metrics": {
            "ece": result.ece,
            "brier": result.brier,
            "reliability_diagram": list(result.reliability),
        },
        "honesty": (
            "PROVISIONAL partial-corpus fit; keep phase3 defaults active until the Phase 4.5 "
            "full-corpus refit"
            if status == "PROVISIONAL"
            else "Full-corpus calibrated parameters produced by the Phase 4.5 batch"
        ),
    }
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def load_confidence_params(
    path: str | Path = DEFAULT_PARAMS_PATH,
    *,
    required_status: str = "CALIBRATED",
) -> LoadedConfidenceParams:
    """Load only an activated artifact, otherwise return explicit unfitted defaults."""
    source = Path(path)
    if not source.exists():
        return LoadedConfidenceParams(
            DEFAULT_CONFIDENCE_PARAMS, False, None, "parameter artifact absent; using defaults"
        )
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        status = str(payload.get("status") or "")
        if status != required_status:
            return LoadedConfidenceParams(
                DEFAULT_CONFIDENCE_PARAMS,
                False,
                status or None,
                f"artifact status is {status or 'missing'}, not {required_status}; using defaults",
            )
        params = ConfidenceParams(**payload["params"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid confidence parameter artifact: {source}") from exc
    return LoadedConfidenceParams(params, True, status, "activated calibrated artifact")
