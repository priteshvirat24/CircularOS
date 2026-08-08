"""Fixed, auditable verification sequence for extracted obligations.

Models supply bounded signals only. Citation validity, thresholding, confidence aggregation,
and routing are deterministic Policy Decision Engine decisions.
"""

from __future__ import annotations

import enum
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Literal, cast

from packages.ai.prompts import get_prompt
from packages.ai.providers import get_structured_llm
from packages.ai.schemas import CriticAssessment, EntailmentAssessment
from packages.policy_engine.citations import CitationVerdict, verify_citation
from packages.policy_engine.confidence import (
    ConfidenceBand,
    ConfidenceVerdict,
    ExtractionSignals,
    aggregate_confidence,
    threshold_entailment,
)

_RETRY_AFTER = re.compile(r"try again in ([0-9.]+)s", re.IGNORECASE)


class VerificationRoute(enum.StrEnum):
    AUTO_REGISTER = "auto_register"
    HUMAN_REVIEW = "human_review"
    REJECT = "reject"


@dataclass(frozen=True)
class CandidateCitation:
    field_name: str
    quote: str


@dataclass(frozen=True)
class VerificationCandidate:
    obligation_id: str
    source_text: str
    normalized_obligation: str
    actor: str | None
    action: str | None
    object: str | None
    conditions: list[str] | None
    exceptions: list[str] | None
    frequency: str | None
    deadline_description: str | None
    citations: tuple[CandidateCitation, ...]
    model_self_confidence: float
    difficulty: Literal["easy", "medium", "hard"] | None

    def key_fields(self) -> dict[str, Any]:
        return {
            "normalized_obligation": self.normalized_obligation,
            "actor": self.actor,
            "action": self.action,
            "object": self.object,
            "conditions": self.conditions,
            "exceptions": self.exceptions,
            "frequency": self.frequency,
            "deadline_description": self.deadline_description,
        }


@dataclass(frozen=True)
class CitationCheck:
    field_name: str
    quote: str
    verdict: CitationVerdict


@dataclass(frozen=True)
class VerificationOutcome:
    obligation_id: str
    citation_checks: tuple[CitationCheck, ...]
    entailment_raw: EntailmentAssessment
    entailment_signal: Literal["entailment", "neutral", "contradiction"]
    critic: CriticAssessment
    confidence: ConfidenceVerdict
    route: VerificationRoute
    ordered_nodes: tuple[str, ...]


def citation_span_node(candidate: VerificationCandidate) -> tuple[CitationCheck, ...]:
    """Deterministically verify every claimed citation span."""
    return tuple(
        CitationCheck(citation.field_name, citation.quote, verify_citation(citation.quote, candidate.source_text))
        for citation in candidate.citations
    )


def entailment_gate_node(
    candidate: VerificationCandidate,
    assessment: EntailmentAssessment,
) -> Literal["entailment", "neutral", "contradiction"]:
    """Threshold the model assessment without allowing it to change source facts."""
    del candidate
    return threshold_entailment(assessment.label, assessment.score)


def adversarial_critic_node(
    candidate: VerificationCandidate, assessment: CriticAssessment
) -> CriticAssessment:
    """Expose the single independent critic pass as a bounded signal."""
    del candidate
    return assessment


def confidence_aggregation_node(
    candidate: VerificationCandidate,
    citation_checks: tuple[CitationCheck, ...],
    entailment_signal: Literal["entailment", "neutral", "contradiction"],
    critic: CriticAssessment,
) -> ConfidenceVerdict:
    """Aggregate visible signals using fixed Phase-3 parameters."""
    all_valid = bool(citation_checks) and all(check.verdict.valid for check in citation_checks)
    minimum = min((check.verdict.score for check in citation_checks), default=0.0)
    return aggregate_confidence(
        ExtractionSignals(
            citations_all_valid=all_valid,
            citation_min_score=minimum,
            entailment=entailment_signal,
            critic_has_objection=critic.has_substantive_objection,
            model_self_confidence=candidate.model_self_confidence,
            difficulty=candidate.difficulty,
        )
    )


def route_verification(
    citations: tuple[CitationCheck, ...],
    entailment_signal: Literal["entailment", "neutral", "contradiction"],
    confidence: ConfidenceVerdict,
) -> VerificationRoute:
    """Apply non-overridable routing gates."""
    if not citations or any(not check.verdict.valid for check in citations):
        return VerificationRoute.REJECT
    if entailment_signal == "contradiction":
        return VerificationRoute.REJECT
    if confidence.band is ConfidenceBand.HIGH and entailment_signal == "entailment":
        return VerificationRoute.AUTO_REGISTER
    return VerificationRoute.HUMAN_REVIEW


def verify_with_assessments(
    candidate: VerificationCandidate,
    entailment: EntailmentAssessment,
    critic: CriticAssessment,
) -> VerificationOutcome:
    """Run the four verification nodes in their fixed order."""
    citations = citation_span_node(candidate)
    entailment_signal = entailment_gate_node(candidate, entailment)
    critic_signal = adversarial_critic_node(candidate, critic)
    confidence = confidence_aggregation_node(
        candidate, citations, entailment_signal, critic_signal
    )
    route = route_verification(citations, entailment_signal, confidence)
    return VerificationOutcome(
        candidate.obligation_id,
        citations,
        entailment,
        entailment_signal,
        critic_signal,
        confidence,
        route,
        ("citation_span_match", "entailment_gate", "adversarial_critic", "confidence_aggregation"),
    )


def run_verification(candidate: VerificationCandidate) -> VerificationOutcome:
    """Invoke Groq free-tier signals once each, then run deterministic decisions."""
    payload = json.dumps(candidate.key_fields(), ensure_ascii=False, sort_keys=True)
    entailment_prompt = get_prompt("entailment_checker")
    entailment_llm = get_structured_llm(EntailmentAssessment, routing_type="critic")
    entailment = cast(
        EntailmentAssessment,
        _invoke_with_free_tier_backoff(
            entailment_llm,
            entailment_prompt.format_messages(
                source_text=candidate.source_text, candidate_json=payload
            ),
        ),
    )
    critic_prompt = get_prompt("regulatory_critic")
    critic_llm = get_structured_llm(CriticAssessment, routing_type="critic")
    critic = cast(
        CriticAssessment,
        _invoke_with_free_tier_backoff(
            critic_llm,
            critic_prompt.format_messages(
                source_text=candidate.source_text, candidate_json=payload
            ),
        ),
    )
    return verify_with_assessments(candidate, entailment, critic)


def _invoke_with_free_tier_backoff(llm: Any, messages: Any) -> Any:
    """Honor Groq's explicit retry window without falling back to a paid provider."""
    for attempt in range(1, 7):
        try:
            return llm.invoke(messages)
        except Exception as exc:
            match = _RETRY_AFTER.search(str(exc))
            if match is None or attempt == 6:
                raise
            time.sleep(float(match.group(1)) + 1.0)
    raise RuntimeError("free-tier retry loop exhausted")


def outcome_as_dict(outcome: VerificationOutcome) -> dict[str, Any]:
    """Serialize a verification outcome for JSONB provenance."""
    return {
        "obligation_id": outcome.obligation_id,
        "ordered_nodes": list(outcome.ordered_nodes),
        "citation_checks": [
            {
                "field_name": check.field_name,
                "quote": check.quote,
                "valid": check.verdict.valid,
                "match_type": check.verdict.match_type.value,
                "span": list(check.verdict.span) if check.verdict.span else None,
                "score": check.verdict.score,
                "explanation": check.verdict.explanation,
            }
            for check in outcome.citation_checks
        ],
        "entailment_raw": outcome.entailment_raw.model_dump(),
        "entailment_signal": outcome.entailment_signal,
        "critic": outcome.critic.model_dump(),
        "confidence": {
            "score": outcome.confidence.score,
            "band": outcome.confidence.band.value,
            "contributing_factors": list(outcome.confidence.contributing_factors),
            "explanation": outcome.confidence.explanation,
            "params_version": outcome.confidence.params_version,
        },
        "route": outcome.route.value,
    }
