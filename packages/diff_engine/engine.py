"""The diff engine orchestrator — a deterministic L1→L4 sequence (no LLM decides flow).

``run_diff_pipeline(old_text, new_text)`` extracts sections, runs the text pre-filter, aligns
structurally, recovers renumbered/reworded pairs with the Hungarian optimal assignment, and
emits a materiality-scored change-list. Pure with respect to I/O: it takes text in and returns
a ``DiffResult`` — the worker task owns all DB reads/writes.
"""

from __future__ import annotations

from packages.diff_engine.matching import Assignment, hungarian_matching
from packages.diff_engine.obligation_diff import diff_created, diff_pair, diff_removed
from packages.diff_engine.sections import extract_sections
from packages.diff_engine.semantic_diff import (
    SimilarityFn,
    build_cost_matrix,
    safe_similarity_backend,
)
from packages.diff_engine.structural_diff import align_sections
from packages.diff_engine.text_diff import text_diff
from packages.diff_engine.types import ChangeRow, DiffResult
from packages.policy_engine.changes import MaterialityLevel

# Similarity floor for a Level-3 semantic match. Calibrated on the real Aug→Jun gold pair:
# the true MODIFIED (§31→§32, "…Members/ Sub-Brokers" → "…Members") sits at sim≈0.79, while
# every genuine CREATED's best partner is ≤0.26 — so 0.75 separates them with wide margin.
DEFAULT_TAU = 0.75

_MATERIAL = {MaterialityLevel.MEDIUM, MaterialityLevel.HIGH}


def run_diff_pipeline(
    old_text: str,
    new_text: str,
    tau: float = DEFAULT_TAU,
    embed_similarity: SimilarityFn | None = None,
) -> DiffResult:
    notes: list[str] = []
    sim_fn, backend = safe_similarity_backend(embed_similarity)
    if "unavailable" in backend:
        notes.append("Embedding backend unavailable — degraded to lexical similarity.")

    # ── Section extraction ──────────────────────────────────────────────────
    old_secs = extract_sections(old_text)
    new_secs = extract_sections(new_text)

    # ── Level 1: text pre-filter ────────────────────────────────────────────
    td = text_diff(old_text, new_text)

    # ── Level 2: structural alignment by title (+number) ────────────────────
    struct = align_sections(old_secs, new_secs)
    matched: list[tuple[int, int, float]] = [(i, j, 1.0) for (i, j, _rel) in struct.matched]

    # ── Level 3: Hungarian optimal assignment over the residual ─────────────
    lo, ln = struct.leftover_old, struct.leftover_new
    if lo and ln:
        cost = build_cost_matrix([old_secs[i].title for i in lo],
                                 [new_secs[j].title for j in ln], sim_fn)
        assign: Assignment = hungarian_matching(cost, tau)
        for a, b, s in assign.pairs:
            matched.append((lo[a], ln[b], s))
        created_idx = [ln[b] for b in assign.unmatched_new]
        removed_idx = [lo[a] for a in assign.unmatched_old]
    else:
        created_idx = list(ln)
        removed_idx = list(lo)

    # ── Level 4: obligation-level classification + materiality ──────────────
    changes: list[ChangeRow] = []
    cosmetic_suppressed = 0
    for i, j, s in matched:
        row = diff_pair(old_secs[i], new_secs[j], s)
        if row is None:
            cosmetic_suppressed += 1
        else:
            changes.append(row)
    for j in created_idx:
        changes.append(diff_created(new_secs[j]))
    for i in removed_idx:
        changes.append(diff_removed(old_secs[i]))

    # Stable, useful ordering: material first, then by type then ref.
    _type_order = {"created": 0, "modified": 1, "removed": 2}
    changes.sort(key=lambda c: (not c.requires_confirmation,
                                _type_order.get(c.change_type, 9),
                                (c.new_ref or c.old_ref or "")))

    summary = {
        "created": sum(1 for c in changes if c.change_type == "created"),
        "modified": sum(1 for c in changes if c.change_type == "modified"),
        "removed": sum(1 for c in changes if c.change_type == "removed"),
        "material": sum(1 for c in changes if c.materiality in _MATERIAL),
        "cosmetic_suppressed": cosmetic_suppressed,
    }

    return DiffResult(
        changes=changes,
        summary=summary,
        text_diff=td,
        old_section_count=len(old_secs),
        new_section_count=len(new_secs),
        matcher={"algorithm": "hungarian", "tau": tau, "similarity_backend": backend},
        notes=notes,
    )
