"""Pure logistic confidence aggregation over extraction signals.

Defaults provide an explicit, inspectable operating structure only; Phase 4.5 fits and
calibrates coefficients on the full gold set. Citation failure remains a hard gate above the
probabilistic model and always forces score zero.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass
from typing import Literal

ENTAILMENT_THRESHOLD = 0.65


class ConfidenceBand(enum.StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class ExtractionSignals:
    citations_all_valid: bool
    citation_min_score: float
    entailment: Literal["entailment", "neutral", "contradiction"]
    critic_has_objection: bool
    model_self_confidence: float
    difficulty: Literal["easy", "medium", "hard"] | None


@dataclass(frozen=True)
class ConfidenceParams:
    intercept: float
    citation_score_weight: float
    entailment_weight: float
    critic_objection_weight: float
    self_confidence_weight: float
    difficulty_weight: float
    high_threshold: float = 0.80
    medium_threshold: float = 0.55
    version: str = "phase3-default-unfitted"


DEFAULT_CONFIDENCE_PARAMS = ConfidenceParams(
    intercept=-2.0,
    citation_score_weight=2.4,
    entailment_weight=1.2,
    critic_objection_weight=-1.4,
    self_confidence_weight=1.6,
    difficulty_weight=-0.8,
)


@dataclass(frozen=True)
class ConfidenceVerdict:
    score: float
    band: ConfidenceBand
    contributing_factors: tuple[str, ...]
    explanation: str
    params_version: str


_ENTAILMENT_VALUE = {"entailment": 1.0, "neutral": 0.0, "contradiction": -1.0}
_DIFFICULTY_VALUE = {"easy": 0.0, "medium": 0.5, "hard": 1.0, None: 0.5}


def threshold_entailment(
    label: Literal["entailment", "neutral", "contradiction"],
    score: float,
    threshold: float = ENTAILMENT_THRESHOLD,
) -> Literal["entailment", "neutral", "contradiction"]:
    """Turn an LLM label into a deterministic signal; weak labels become neutral."""
    if not 0.0 <= score <= 1.0:
        raise ValueError("entailment score must be between 0 and 1")
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("entailment threshold must be between 0 and 1")
    return label if score >= threshold else "neutral"


def _validate(signals: ExtractionSignals, params: ConfidenceParams) -> None:
    if not 0.0 <= signals.citation_min_score <= 1.0:
        raise ValueError("citation_min_score must be between 0 and 1")
    if not 0.0 <= signals.model_self_confidence <= 1.0:
        raise ValueError("model_self_confidence must be between 0 and 1")
    if not 0.0 <= params.medium_threshold <= params.high_threshold <= 1.0:
        raise ValueError("confidence thresholds must satisfy 0 <= medium <= high <= 1")


def aggregate_confidence(
    signals: ExtractionSignals,
    params: ConfidenceParams = DEFAULT_CONFIDENCE_PARAMS,
) -> ConfidenceVerdict:
    """Return a deterministic probability, band, and factor-level explanation."""
    _validate(signals, params)
    if not signals.citations_all_valid:
        return ConfidenceVerdict(
            0.0,
            ConfidenceBand.LOW,
            ("hard gate: at least one key citation is NOT_FOUND",),
            "unverifiable citation forces confidence to zero",
            params.version,
        )
    if signals.entailment == "contradiction":
        return ConfidenceVerdict(
            0.0,
            ConfidenceBand.LOW,
            ("hard gate: key-field entailment is contradiction",),
            "contradicted extraction cannot be auto-registered",
            params.version,
        )

    features = (
        ("intercept", 1.0, params.intercept),
        ("citation score", signals.citation_min_score, params.citation_score_weight),
        ("entailment", _ENTAILMENT_VALUE[signals.entailment], params.entailment_weight),
        (
            "critic objection",
            1.0 if signals.critic_has_objection else 0.0,
            params.critic_objection_weight,
        ),
        ("model self-confidence", signals.model_self_confidence, params.self_confidence_weight),
        ("difficulty", _DIFFICULTY_VALUE[signals.difficulty], params.difficulty_weight),
    )
    logit = sum(value * weight for _, value, weight in features)
    probability = 1.0 / (1.0 + math.exp(-logit))
    score = round(probability, 6)
    if score >= params.high_threshold:
        band = ConfidenceBand.HIGH
    elif score >= params.medium_threshold:
        band = ConfidenceBand.MEDIUM
    else:
        band = ConfidenceBand.LOW
    factors = tuple(
        f"{name}: {value:.3f} × {weight:+.3f} = {value * weight:+.3f}"
        for name, value, weight in features
    )
    return ConfidenceVerdict(
        score,
        band,
        factors,
        f"logistic probability {score:.3f} maps to {band.value} using {params.version}",
        params.version,
    )
