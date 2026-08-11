from __future__ import annotations

import pytest

from packages.evaluation.matching import (
    EvaluationObligation,
    MatcherConfig,
    match_obligations,
    match_obligations_coverage,
    spans_overlap,
)
from packages.evaluation.metrics import field_accuracy, precision_recall_f1


def item(
    record_id: str,
    actor: str,
    action: str,
    obligation: str,
    span: tuple[int, int],
    **fields: object,
) -> EvaluationObligation:
    return EvaluationObligation(record_id, actor, action, obligation, span, fields)


def matcher(predictions, gold):
    return match_obligations(
        predictions,
        gold,
        MatcherConfig(obligation_similarity_threshold=0.60),
    )


def test_known_answer_two_tp_one_fp_one_fn() -> None:
    gold = [
        item("g1", "Stock Brokers", "maintain records", "Brokers must maintain records", (0, 40)),
        item("g2", "Exchange", "submit report", "Exchange must submit quarterly report", (50, 100)),
        item("g3", "Auditor", "retain evidence", "Auditor must retain evidence", (110, 150)),
    ]
    predictions = [
        item("p1", "Stock Broker", "maintain record", "Stock brokers shall maintain records", (5, 35)),
        item("p2", "Exchange", "submit reports", "Exchange shall submit a quarterly report", (55, 95)),
        item("p3", "Depository", "publish notice", "Depository shall publish notice", (160, 190)),
    ]

    result = precision_recall_f1(predictions, gold, matcher)

    assert result.confusion == {
        "true_positives": 2,
        "false_positives": 1,
        "false_negatives": 1,
    }
    assert result.precision == pytest.approx(2 / 3)
    assert result.recall == pytest.approx(2 / 3)
    assert result.f1 == pytest.approx(2 / 3)


def test_match_requires_actor_action_similarity_threshold_and_span_overlap() -> None:
    gold = [item("g", "Stock Broker", "retain records", "retain client records", (10, 20))]
    wrong_actor = [item("p", "Auditor", "retain records", "retain client records", (10, 20))]
    wrong_action = [item("p", "Stock Broker", "delete records", "retain client records", (10, 20))]
    wrong_span = [item("p", "Stock Broker", "retain records", "retain client records", (20, 30))]

    assert not matcher(wrong_actor, gold).matched_pairs
    assert not matcher(wrong_action, gold).matched_pairs
    assert not matcher(wrong_span, gold).matched_pairs
    assert spans_overlap((10, 20), (19, 25))
    assert not spans_overlap((10, 20), (20, 25))


def test_matching_is_one_to_one_and_deterministic() -> None:
    gold = [
        item("g1", "Broker", "submit report", "submit the report", (0, 20)),
        item("g2", "Broker", "submit report", "submit the report promptly", (0, 20)),
    ]
    predictions = [item("p1", "Broker", "submit report", "submit the report", (0, 20))]

    outcome = matcher(predictions, gold)

    assert [(pair.prediction.record_id, pair.gold.record_id) for pair in outcome.matched_pairs] == [
        ("p1", "g1")
    ]
    assert outcome.unmatched_gold_indices == (1,)


def test_coverage_matcher_one_gold_three_predictions() -> None:
    """1 gold annotation matched by 3 predictions → 1 TP, 0 FP, 0 FN."""
    gold = [
        item("g1", "Stock Broker", "maintain records", "Broker must maintain records", (0, 50)),
    ]
    predictions = [
        item("p1", "Stock Broker", "maintain records", "Broker shall maintain transaction records", (5, 45)),
        item("p2", "Stock Broker", "maintain records", "Broker shall maintain client records", (10, 40)),
        item("p3", "Stock Broker", "maintain records", "Broker must maintain records of orders", (0, 35)),
    ]
    config = MatcherConfig(obligation_similarity_threshold=0.50)
    outcome = match_obligations_coverage(predictions, gold, config)

    assert len(outcome.covered_gold_indices) == 1
    assert len(outcome.uncovered_gold_indices) == 0
    assert len(outcome.absorbed_prediction_indices) == 3
    assert len(outcome.unmatched_prediction_indices) == 0
    tp = len(outcome.covered_gold_indices)
    fp = len(outcome.unmatched_prediction_indices)
    fn = len(outcome.uncovered_gold_indices)
    assert tp == 1
    assert fp == 0
    assert fn == 0
    assert outcome.granularity_ratio == 3.0
    assert len(outcome.primary_pairs) == 1


def test_coverage_matcher_mixed_case() -> None:
    """2 gold, 5 predictions: 1 gold matched by 3, 1 gold unmatched, 2 predictions unmatched."""
    gold = [
        item("g1", "Stock Broker", "maintain records", "Broker must maintain records", (0, 50)),
        item("g2", "Auditor", "conduct audit", "Auditor must conduct internal audit", (100, 150)),
    ]
    predictions = [
        item("p1", "Stock Broker", "maintain records", "Broker shall maintain transaction records", (5, 45)),
        item("p2", "Stock Broker", "maintain records", "Broker shall maintain client records", (10, 40)),
        item("p3", "Stock Broker", "maintain records", "Broker must maintain records of orders", (0, 35)),
        item("p4", "Exchange", "publish notice", "Exchange shall publish compliance notice", (60, 90)),
        item("p5", "Depository", "submit report", "Depository shall submit annual report", (200, 250)),
    ]
    config = MatcherConfig(obligation_similarity_threshold=0.50)
    outcome = match_obligations_coverage(predictions, gold, config)

    assert len(outcome.covered_gold_indices) == 1
    assert len(outcome.uncovered_gold_indices) == 1
    assert 1 in outcome.uncovered_gold_indices
    assert len(outcome.absorbed_prediction_indices) == 3
    assert len(outcome.unmatched_prediction_indices) == 2
    tp = len(outcome.covered_gold_indices)
    fp = len(outcome.unmatched_prediction_indices)
    fn = len(outcome.uncovered_gold_indices)
    assert tp == 1
    assert fp == 2
    assert fn == 1
    assert outcome.granularity_ratio == 3.0


def test_field_accuracy_known_answer_and_missing_values() -> None:
    gold = [
        item("g1", "Stock Brokers", "maintain records", "x", (0, 10), deadline="T+1", frequency=None, evidence=["log"]),
        item("g2", "Exchange", "submit report", "y", (20, 30), deadline=None, frequency="quarterly", evidence=None),
    ]
    predictions = [
        item("p1", "Stock Broker", "maintain record", "x", (0, 10), deadline="T+1", frequency=None, evidence=["log"]),
        item("p2", "Exchange", "submit report", "y", (20, 30), deadline="T+2", frequency="monthly", evidence=None),
    ]
    pairs = matcher(predictions, gold).matched_pairs

    accuracy = field_accuracy(pairs)

    assert accuracy["actor"] == 1.0
    assert accuracy["action"] == 1.0
    assert accuracy["deadline"] == 0.5
    assert accuracy["frequency"] == 0.5
    assert accuracy["evidence"] == 1.0
    assert field_accuracy([])["actor"] is None

