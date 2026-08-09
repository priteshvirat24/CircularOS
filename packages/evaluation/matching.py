"""Deterministic obligation matching for extraction evaluation."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any


@dataclass(frozen=True)
class MatcherConfig:
    """Auditable thresholds used by the obligation matcher."""

    obligation_similarity_threshold: float = 0.55
    actor_alignment_threshold: float = 0.70
    action_alignment_threshold: float = 0.55
    require_source_span_overlap: bool = True
    algorithm: str = "deterministic_global_greedy"
    version: str = "obligation-matcher-v1"

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "algorithm": self.algorithm,
            "obligation_similarity_threshold": self.obligation_similarity_threshold,
            "actor_alignment_threshold": self.actor_alignment_threshold,
            "action_alignment_threshold": self.action_alignment_threshold,
            "require_source_span_overlap": self.require_source_span_overlap,
            "methodology": (
                "normalized actor and action alignment; normalized-obligation similarity; "
                "overlapping source spans; deterministic one-to-one assignment"
            ),
        }


@dataclass(frozen=True)
class EvaluationObligation:
    """Small, persistence-free representation consumed by the matcher."""

    record_id: str
    actor: str | None
    action: str | None
    normalized_obligation: str | None
    source_span: tuple[int, int] | None
    fields: Mapping[str, Any] = field(default_factory=dict)
    source_text: str | None = None


@dataclass(frozen=True)
class MatchedPair:
    prediction: EvaluationObligation
    gold: EvaluationObligation
    prediction_index: int
    gold_index: int
    obligation_similarity: float
    actor_alignment: float
    action_alignment: float


@dataclass(frozen=True)
class MatchOutcome:
    matched_pairs: tuple[MatchedPair, ...]
    unmatched_prediction_indices: tuple[int, ...]
    unmatched_gold_indices: tuple[int, ...]


DEFAULT_MATCHER_CONFIG = MatcherConfig()


_SPACE = re.compile(r"\s+")
_NON_WORD = re.compile(r"[^a-z0-9]+")
_ACTOR_ALIASES = {
    "sb": "stock broker",
    "sbs": "stock broker",
    "cm": "clearing member",
    "cms": "clearing member",
    "tm": "trading member",
    "tms": "trading member",
}


def normalize_text(value: Any) -> str:
    """Unicode/case/punctuation normalization shared by matching and field scoring."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        value = " ".join(str(item) for item in value)
    text = unicodedata.normalize("NFKC", str(value)).casefold().replace("&", " and ")
    return _SPACE.sub(" ", _NON_WORD.sub(" ", text)).strip()


def _tokens(value: Any, *, actor: bool = False) -> tuple[str, ...]:
    tokens: list[str] = []
    for token in normalize_text(value).split():
        expanded = _ACTOR_ALIASES.get(token, token) if actor else token
        for item in expanded.split():
            if len(item) > 3 and item.endswith("s") and not item.endswith("ss"):
                item = item[:-1]
            tokens.append(item)
    return tuple(tokens)


def normalized_similarity(left: Any, right: Any, *, actor: bool = False) -> float:
    """Composite deterministic similarity robust to pluralization and word order."""
    left_tokens = _tokens(left, actor=actor)
    right_tokens = _tokens(right, actor=actor)
    if not left_tokens or not right_tokens:
        return 1.0 if left_tokens == right_tokens else 0.0
    left_text = " ".join(left_tokens)
    right_text = " ".join(right_tokens)
    if left_text == right_text:
        return 1.0
    intersection = len(set(left_tokens) & set(right_tokens))
    union = len(set(left_tokens) | set(right_tokens))
    jaccard = intersection / union if union else 0.0
    sequence = SequenceMatcher(None, left_text, right_text, autojunk=False).ratio()
    containment = intersection / min(len(set(left_tokens)), len(set(right_tokens)))
    return round(max(jaccard, sequence, containment), 6)


def spans_overlap(left: tuple[int, int] | None, right: tuple[int, int] | None) -> bool:
    """Return whether two half-open spans overlap."""
    if left is None or right is None:
        return False
    if left[0] < 0 or right[0] < 0 or left[1] < left[0] or right[1] < right[0]:
        raise ValueError("source spans must be non-negative half-open intervals")
    return max(left[0], right[0]) < min(left[1], right[1])


def _candidate(
    prediction: EvaluationObligation,
    gold: EvaluationObligation,
    config: MatcherConfig,
) -> tuple[float, float, float] | None:
    actor_score = normalized_similarity(prediction.actor, gold.actor, actor=True)
    if actor_score < config.actor_alignment_threshold:
        return None
    action_score = normalized_similarity(prediction.action, gold.action)
    prediction_action = _tokens(prediction.action)
    gold_action = _tokens(gold.action)
    leading_action_aligned = bool(
        prediction_action and gold_action and prediction_action[0] == gold_action[0]
    )
    if action_score < config.action_alignment_threshold or not leading_action_aligned:
        return None
    obligation_score = normalized_similarity(
        prediction.normalized_obligation, gold.normalized_obligation
    )
    if obligation_score < config.obligation_similarity_threshold:
        return None
    if config.require_source_span_overlap and not spans_overlap(
        prediction.source_span, gold.source_span
    ):
        return None
    return obligation_score, actor_score, action_score


def match_obligations(
    predictions: Sequence[EvaluationObligation],
    gold: Sequence[EvaluationObligation],
    config: MatcherConfig = DEFAULT_MATCHER_CONFIG,
) -> MatchOutcome:
    """Return a deterministic, one-to-one matching of predictions to gold obligations.

    Eligible pairs are sorted globally by normalized-obligation similarity, then actor/action
    alignment and stable input indices. This prevents input-order-dependent first-match wins.
    """
    candidates: list[tuple[float, float, float, int, int]] = []
    for prediction_index, prediction in enumerate(predictions):
        for gold_index, gold_item in enumerate(gold):
            scores = _candidate(prediction, gold_item, config)
            if scores is not None:
                candidates.append((*scores, prediction_index, gold_index))
    candidates.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3], item[4]))

    used_predictions: set[int] = set()
    used_gold: set[int] = set()
    pairs: list[MatchedPair] = []
    for obligation_score, actor_score, action_score, prediction_index, gold_index in candidates:
        if prediction_index in used_predictions or gold_index in used_gold:
            continue
        used_predictions.add(prediction_index)
        used_gold.add(gold_index)
        pairs.append(
            MatchedPair(
                predictions[prediction_index],
                gold[gold_index],
                prediction_index,
                gold_index,
                obligation_score,
                actor_score,
                action_score,
            )
        )
    pairs.sort(key=lambda pair: (pair.gold_index, pair.prediction_index))
    return MatchOutcome(
        tuple(pairs),
        tuple(index for index in range(len(predictions)) if index not in used_predictions),
        tuple(index for index in range(len(gold)) if index not in used_gold),
    )
