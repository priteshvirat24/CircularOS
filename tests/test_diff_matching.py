"""Tests for the optimal-assignment matcher — the mathematical centerpiece.

The headline test constructs a real cross-renumbering scenario where the greedy matcher makes
a locally-best first pick that blocks the globally-correct correspondence, and asserts that the
Hungarian matcher recovers it at strictly lower total cost.
"""

from __future__ import annotations

import numpy as np

from packages.diff_engine.matching import (
    assignment_cost,
    greedy_matching,
    hungarian_matching,
)
from packages.diff_engine.semantic_diff import build_cost_matrix, lexical_similarity


def test_hungarian_beats_greedy_on_cross_renumbering():
    # Real scenario: two adjacent SEBI sections whose text was lightly reworded AND swapped in
    # order during consolidation. Greedy grabs the single cheapest cell (o0→n0) first, which
    # forces the expensive o1→n1; Hungarian sees the cross pairing is globally cheaper.
    #        n0     n1
    cost = np.array([
        [0.10, 0.15],   # o0
        [0.20, 0.60],   # o1
    ])
    tau = 0.3  # null_cost = 0.70; all real cells are cheaper, so nothing goes to null.

    g = greedy_matching(cost, tau)
    h = hungarian_matching(cost, tau)

    g_pairs = {(i, j) for i, j, _ in g.pairs}
    h_pairs = {(i, j) for i, j, _ in h.pairs}

    assert g_pairs == {(0, 0), (1, 1)}          # greedy's locally-best, globally-wrong pairing
    assert h_pairs == {(0, 1), (1, 0)}          # optimal cross correspondence
    assert assignment_cost(cost, h, tau) < assignment_cost(cost, g, tau)


def test_null_option_leaves_dissimilar_items_unmatched():
    # o1 matches nothing well → it must go to the null option (→ REMOVED), not force a bad pair.
    cost = np.array([
        [0.05, 0.90],   # o0 clearly matches n0
        [0.95, 0.92],   # o1 matches neither above threshold
    ])
    tau = 0.5  # null_cost = 0.5; cells ≥ 0.5 are rejected.
    h = hungarian_matching(cost, tau)
    assert {(i, j) for i, j, _ in h.pairs} == {(0, 0)}
    assert h.unmatched_old == [1]
    assert h.unmatched_new == [1]


def test_hungarian_cost_never_worse_than_greedy_random():
    rng = np.random.default_rng(42)
    tau = 0.6
    for _ in range(50):
        cost = rng.random((6, 5))
        g = greedy_matching(cost, tau)
        h = hungarian_matching(cost, tau)
        assert assignment_cost(cost, h, tau) <= assignment_cost(cost, g, tau) + 1e-9


def test_empty_sides():
    assert hungarian_matching(np.zeros((0, 3)), 0.5).unmatched_new == [0, 1, 2]
    assert hungarian_matching(np.zeros((2, 0)), 0.5).unmatched_old == [0, 1]


def test_cost_matrix_from_real_titles():
    old = ["Execution of Power of Attorney (PoA) by the Client"]
    new = ["Execution of Power of Attorney (PoA) by the Client", "A brand new section"]
    cost = build_cost_matrix(old, new, lexical_similarity)
    assert cost[0, 0] < 0.01           # identical title → ~0 cost
    assert cost[0, 1] > 0.7            # unrelated → high cost
