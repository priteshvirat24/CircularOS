"""Level 3 — semantic matching of unmatched units via optimal assignment.

Similarity is pluggable. The default backend is a deterministic **lexical composite**
(token-set Jaccard + character 3-gram cosine) — reproducible, offline, and more reliable than
embeddings on near-identical section headings (the dominant case in a re-consolidation). An
optional embedding backend can be supplied; if it raises, we degrade gracefully to lexical
and flag the affected units for review (per the design's failure-mode requirement).

The *matching* is fuzzy (similarity); the *decision* is deterministic (a tuned threshold τ
plus the Hungarian assignment). An LLM is never the arbiter of whether two clauses match.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import numpy as np

from packages.diff_engine.matching import Assignment, hungarian_matching
from packages.diff_engine.normalize import normalize_for_match

SimilarityFn = Callable[[str, str], float]

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(s: str) -> set[str]:
    return set(_WORD.findall(normalize_for_match(s)))


def _char_ngrams(s: str, n: int = 3) -> set[str]:
    s = normalize_for_match(s)
    if len(s) < n:
        return {s} if s else set()
    return {s[i: i + n] for i in range(len(s) - n + 1)}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def lexical_similarity(a: str, b: str) -> float:
    """Deterministic composite in [0, 1]: 0.5·token-set Jaccard + 0.5·char-3gram Jaccard."""
    if not a and not b:
        return 1.0
    tok = _jaccard(_tokens(a), _tokens(b))
    ng = _jaccard(_char_ngrams(a), _char_ngrams(b))
    return 0.5 * tok + 0.5 * ng


def build_cost_matrix(old: list[str], new: list[str], sim: SimilarityFn) -> np.ndarray:
    """``cost[i, j] = 1 − sim(old_i, new_j)``."""
    m, n = len(old), len(new)
    cost = np.ones((m, n), dtype=float)
    for i in range(m):
        for j in range(n):
            cost[i, j] = 1.0 - sim(old[i], new[j])
    return cost


def match_texts(
    old: list[str],
    new: list[str],
    tau: float,
    sim: SimilarityFn | None = None,
) -> Assignment:
    """Optimal assignment between two lists of texts at threshold ``tau``."""
    sim = sim or lexical_similarity
    cost = build_cost_matrix(old, new, sim)
    return hungarian_matching(cost, tau)


def safe_similarity_backend(embed_fn: SimilarityFn | None) -> tuple[SimilarityFn, str]:
    """Return ``(similarity_fn, backend_name)``, degrading to lexical on any failure.

    ``embed_fn`` is an optional embedding-based similarity. If it is None or raises on a probe,
    we fall back to the deterministic lexical similarity and report which backend is live.
    """
    if embed_fn is None:
        return lexical_similarity, "lexical"
    try:
        _ = embed_fn("probe a", "probe b")
        return embed_fn, "embedding"
    except Exception:  # noqa: BLE001 — any provider failure ⇒ graceful lexical fallback
        return lexical_similarity, "lexical(embedding_unavailable)"
