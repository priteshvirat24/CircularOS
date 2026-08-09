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
from packages.policy_engine.citations import (
    CITATION_THRESHOLD,
    CitationVerdict,
    MatchType,
    verify_citation,
)
from packages.policy_engine.confidence import (
    DEFAULT_CONFIDENCE_PARAMS,
    ENTAILMENT_THRESHOLD,
    ConfidenceBand,
    ConfidenceParams,
    ConfidenceVerdict,
    ExtractionSignals,
    aggregate_confidence,
    threshold_entailment,
)
from packages.policy_engine.impact import (
    ImpactChange,
    ImpactSet,
    OrgGraph,
    OrgNode,
    OrgNodeKind,
    resolve_blast_radius,
)

__all__ = [
    "ObligationFields",
    "ChangeKind",
    "ChangeVerdict",
    "MaterialityLevel",
    "MaterialityVerdict",
    "classify_change",
    "assess_materiality",
    "CITATION_THRESHOLD",
    "CitationVerdict",
    "MatchType",
    "verify_citation",
    "DEFAULT_CONFIDENCE_PARAMS",
    "ENTAILMENT_THRESHOLD",
    "ConfidenceBand",
    "ConfidenceParams",
    "ConfidenceVerdict",
    "ExtractionSignals",
    "aggregate_confidence",
    "threshold_entailment",
    "ImpactChange",
    "ImpactSet",
    "OrgGraph",
    "OrgNode",
    "OrgNodeKind",
    "resolve_blast_radius",
]
