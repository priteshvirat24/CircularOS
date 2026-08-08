"""Optimal assignment for clause/section matching (MATHEMATICAL_FOUNDATIONS.md §2).

The diff match is a **Linear Assignment Problem**, not a greedy nearest-neighbour walk:
a locally-best early match can consume a partner another item needed more, so greedy is
provably suboptimal. We solve it optimally with the Hungarian algorithm (Kuhn–Munkres,
``scipy.optimize.linear_sum_assignment``), with a per-side **null option** costing ``1 − τ``
so that an unmatched old item becomes REMOVED and an unmatched new item becomes CREATED.

``greedy_matching`` exists only as a baseline for the demonstrable-win test — the engine uses
``hungarian_matching``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment  # type: ignore[import-untyped]


@dataclass(frozen=True)
class Assignment:
    """Result of a matching. ``pairs`` are matched (old_i, new_j, similarity); unmatched
    indices become REMOVED (old) / CREATED (new)."""

    pairs: list[tuple[int, int, float]]
    unmatched_old: list[int]
    unmatched_new: list[int]


def _validate(cost: np.ndarray) -> None:
    if cost.ndim != 2:
        raise ValueError("cost matrix must be 2-D")


_FORBIDDEN = 1.0e6  # a cost no optimal assignment will ever choose (real costs ∈ [0, 1])


def hungarian_matching(cost: np.ndarray, tau: float) -> Assignment:
    """Optimal one-to-one assignment with a per-item null option at cost ``1 − τ``.

    ``cost[i, j] = 1 − sim(old_i, new_j)``. Edges with similarity < τ (cost ≥ ``1 − τ``) are
    *forbidden*, and every item gets a personal dummy that absorbs it at the null cost when it
    is better off unmatched (→ an unmatched old is REMOVED, an unmatched new is CREATED).

    Construction (square, size ``m + n``): personal diagonal dummies with a forbidden
    off-diagonal, and a free dummy↔dummy block, so the assignment minimizes exactly
    ``Σ matched cost + (1 − τ)·#unmatched`` with a hard τ threshold — the classic
    assignment-with-outliers reduction. Solved optimally by Kuhn–Munkres.
    """
    _validate(cost)
    m, n = cost.shape
    null_cost = 1.0 - tau
    if m == 0 or n == 0:
        return Assignment([], list(range(m)), list(range(n)))

    size = m + n
    big = np.full((size, size), _FORBIDDEN, dtype=float)
    # Real edges: keep only those above the τ threshold (cost < null_cost); forbid the rest.
    allowed = cost < null_cost
    big[:m, :n] = np.where(allowed, cost, _FORBIDDEN)
    # Personal dummy columns for old items (rows 0..m), diagonal at null_cost.
    for i in range(m):
        big[i, n + i] = null_cost
    # Personal dummy rows for new items (cols 0..n), diagonal at null_cost.
    for j in range(n):
        big[m + j, j] = null_cost
    # Dummy row × dummy column block is free.
    big[m:, n:] = 0.0

    row_ind, col_ind = linear_sum_assignment(big)

    pairs: list[tuple[int, int, float]] = []
    matched_old, matched_new = set(), set()
    for r, c in zip(row_ind, col_ind, strict=True):
        if r < m and c < n and cost[r, c] < null_cost:
            pairs.append((r, c, float(1.0 - cost[r, c])))
            matched_old.add(r)
            matched_new.add(c)
    unmatched_old = [i for i in range(m) if i not in matched_old]
    unmatched_new = [j for j in range(n) if j not in matched_new]
    return Assignment(pairs, unmatched_old, unmatched_new)


def greedy_matching(cost: np.ndarray, tau: float) -> Assignment:
    """Baseline: repeatedly take the globally-cheapest remaining cell above threshold.

    Included only to demonstrate that greedy is suboptimal versus Hungarian — the engine
    never uses this for its verdicts.
    """
    _validate(cost)
    m, n = cost.shape
    null_cost = 1.0 - tau
    used_old, used_new = set(), set()
    pairs: list[tuple[int, int, float]] = []

    cells = sorted(
        ((cost[i, j], i, j) for i in range(m) for j in range(n)),
        key=lambda t: t[0],
    )
    for c, i, j in cells:
        if c >= null_cost:
            break
        if i in used_old or j in used_new:
            continue
        pairs.append((i, j, float(1.0 - c)))
        used_old.add(i)
        used_new.add(j)
    unmatched_old = [i for i in range(m) if i not in used_old]
    unmatched_new = [j for j in range(n) if j not in used_new]
    return Assignment(pairs, unmatched_old, unmatched_new)


def assignment_cost(cost: np.ndarray, assignment: Assignment, tau: float) -> float:
    """Total cost of an assignment (matched cells + null_cost per unmatched item).

    Lower is better; used by tests to prove Hungarian ≤ greedy.
    """
    null_cost = 1.0 - tau
    total = 0.0
    for i, j, _sim in assignment.pairs:
        total += float(cost[i, j])
    total += null_cost * (len(assignment.unmatched_old) + len(assignment.unmatched_new))
    return total
