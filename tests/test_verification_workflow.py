from __future__ import annotations

from dataclasses import replace

from packages.ai.prompts import get_prompt
from packages.ai.schemas import (
    CandidateVerificationAssessment,
    CriticAssessment,
    EntailmentAssessment,
    VerificationBatchResult,
)
from packages.ai.workflows import verification
from packages.ai.workflows.supervisor import PipelineStage, run_deterministic_pipeline
from packages.ai.workflows.verification import (
    CandidateCitation,
    VerificationCandidate,
    VerificationRoute,
    run_verification_batch,
    split_verification_batches,
    verify_with_assessments,
)
from packages.evaluation.calibration import LoadedConfidenceParams
from packages.policy_engine.confidence import DEFAULT_CONFIDENCE_PARAMS


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
    outcome = verify_with_assessments(
        candidate(), entailment(), critic(), params=DEFAULT_CONFIDENCE_PARAMS,
    )
    assert outcome.ordered_nodes == (
        "citation_span_match",
        "entailment_gate",
        "adversarial_critic",
        "confidence_aggregation",
    )
    assert outcome.route is VerificationRoute.AUTO_REGISTER


def test_batch_prompt_version_matches_checkpoint_contract() -> None:
    assert get_prompt("verification_batch_critic").version == "1.3"


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


def test_batch_critic_returns_one_deterministic_outcome_per_requested_id(monkeypatch) -> None:
    first = candidate()
    second = replace(first, obligation_id="obl-2")

    class FakeStructuredModel:
        def invoke(self, messages, config):
            del messages, config
            return VerificationBatchResult(
                assessments=[
                    CandidateVerificationAssessment(
                        obligation_id=str(index),
                        entailment_label="entailment",
                        entailment_score=0.98,
                        entailment_reason_code="supported",
                        critic_has_substantive_objection=False,
                        critic_reason_code="none",
                    )
                    for index, _item in enumerate((first, second))
                ]
            )

    requested: dict[str, object] = {}

    def fake_structured_model(schema, routing_type, **kwargs):
        requested.update(schema=schema, routing_type=routing_type, **kwargs)
        return FakeStructuredModel()

    monkeypatch.setattr(verification, "get_structured_llm", fake_structured_model)
    monkeypatch.setattr(
        verification,
        "load_confidence_params",
        lambda *a, **kw: LoadedConfidenceParams(DEFAULT_CONFIDENCE_PARAMS, False, None, "test"),
    )
    result = run_verification_batch((first, second))
    assert [item.obligation_id for item in result.outcomes] == ["obl-1", "obl-2"]
    assert all(item.route is VerificationRoute.AUTO_REGISTER for item in result.outcomes)
    assert requested["max_tokens"] == 1024


def test_verification_batches_bound_serialized_payload(monkeypatch) -> None:
    items = [
        replace(candidate(), obligation_id=f"obl-{index}", normalized_obligation="x" * 5000)
        for index in range(1, 5)
    ]
    monkeypatch.setattr(verification, "VERIFICATION_MAX_BATCH_PAYLOAD_CHARS", 8_000)

    batches = split_verification_batches(items)

    assert [len(batch) for batch in batches] == [1, 1, 1, 1]
    assert [item.obligation_id for batch in batches for item in batch] == [
        "obl-1",
        "obl-2",
        "obl-3",
        "obl-4",
    ]


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
