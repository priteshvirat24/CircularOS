from __future__ import annotations

from packages.ai.schemas import CriticAssessment, EntailmentAssessment
from packages.ai.workflows.supervisor import PipelineStage, run_deterministic_pipeline
from packages.ai.workflows.verification import (
    CandidateCitation,
    VerificationCandidate,
    VerificationRoute,
    verify_with_assessments,
)


def candidate(*, quote: str = "Members shall retain records.") -> VerificationCandidate:
    return VerificationCandidate(
        obligation_id="obl-1",
        source_text="Scope. Members shall retain records. End.",
        normalized_obligation="Members must retain records.",
        actor="Members",
        action="retain",
        object="records",
        conditions=None,
        exceptions=None,
        frequency=None,
        deadline_description=None,
        citations=(CandidateCitation("action", quote),),
        model_self_confidence=0.95,
        difficulty="easy",
    )


def entailment(label: str = "entailment", score: float = 0.98) -> EntailmentAssessment:
    return EntailmentAssessment(label=label, score=score, reasoning="source supports signal")


def critic(has_objection: bool = False) -> CriticAssessment:
    return CriticAssessment(
        has_substantive_objection=has_objection,
        objection="wrong scope" if has_objection else None,
        reasoning="one independent pass",
    )


def test_fixed_node_order_and_high_confidence_auto_registration() -> None:
    outcome = verify_with_assessments(candidate(), entailment(), critic())
    assert outcome.ordered_nodes == (
        "citation_span_match",
        "entailment_gate",
        "adversarial_critic",
        "confidence_aggregation",
    )
    assert outcome.route is VerificationRoute.AUTO_REGISTER


def test_invalid_citation_is_non_overridable_rejection() -> None:
    outcome = verify_with_assessments(candidate(quote="Invented citation"), entailment(), critic())
    assert outcome.route is VerificationRoute.REJECT
    assert outcome.confidence.score == 0.0


def test_contradiction_is_non_overridable_rejection() -> None:
    outcome = verify_with_assessments(
        candidate(), entailment("contradiction", 0.99), critic(False)
    )
    assert outcome.route is VerificationRoute.REJECT


def test_weak_entailment_signal_becomes_neutral() -> None:
    outcome = verify_with_assessments(candidate(), entailment("contradiction", 0.20), critic())
    assert outcome.entailment_signal == "neutral"
    assert outcome.route is VerificationRoute.HUMAN_REVIEW


def test_deterministic_supervisor_runs_real_workers_in_order() -> None:
    seen: list[str] = []

    def verify(context: dict) -> dict:
        seen.append("verification")
        return {"verified": context["document_id"]}

    def registry(context: dict) -> dict:
        seen.append("registry")
        assert context["verified"] == "doc-1"
        return {"registered": True}

    result = run_deterministic_pipeline(
        {"document_id": "doc-1"},
        {PipelineStage.VERIFICATION: verify, PipelineStage.REGISTRY: registry},
    )
    assert result.completed is True
    assert seen == ["verification", "registry"]
    assert result.context["registered"] is True


def test_deterministic_supervisor_stops_after_failure() -> None:
    def fail(context: dict) -> dict:
        raise RuntimeError(f"cannot verify {context['document_id']}")

    result = run_deterministic_pipeline(
        {"document_id": "doc-1"},
        {PipelineStage.VERIFICATION: fail, PipelineStage.REGISTRY: lambda _: {}},
    )
    assert result.completed is False
    assert result.stages[-1].stage is PipelineStage.VERIFICATION
    assert result.stages[-1].status == "failed"
