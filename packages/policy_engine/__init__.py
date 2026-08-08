"""Policy Decision Engine — pure, deterministic, zero-I/O verdicts.

Every regulatory verdict of record (change classification, materiality) is computed
here by named rules over structured data, so a regulator can read and audit the exact
logic. No DB, network, filesystem, or LLM imports live in this package — it is 100%
unit-testable and reproducible.

    "The LLM proposes; deterministic logic disposes."
"""

from packages.policy_engine.changes import (
    ChangeKind,
    ChangeVerdict,
    MaterialityLevel,
    MaterialityVerdict,
    ObligationFields,
    assess_materiality,
    classify_change,
)

__all__ = [
    "ObligationFields",
    "ChangeKind",
    "ChangeVerdict",
    "MaterialityLevel",
    "MaterialityVerdict",
    "classify_change",
    "assess_materiality",
]
