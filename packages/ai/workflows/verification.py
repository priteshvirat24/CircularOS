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

from langchain_core.callbacks import UsageMetadataCallbackHandler

from packages.ai.prompts import get_prompt
from packages.ai.providers import get_structured_llm
from packages.ai.schemas import (
    CriticAssessment,
    EntailmentAssessment,
    VerificationBatchResult,
)
from packages.evaluation.calibration import load_confidence_params
from packages.policy_engine.citations import (
    CitationVerdict,
    find_citation_span_fast,
    verify_citation,
)
from packages.policy_engine.confidence import (
    ConfidenceBand,
    ConfidenceParams,
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
class InvocationUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int | None:
        if self.prompt_tokens is None or self.completion_tokens is None:
            return None
        return self.prompt_tokens + self.completion_tokens


EMPTY_INVOCATION_USAGE = InvocationUsage()

VERIFICATION_MAX_OUTPUT_TOKENS = 1024
VERIFICATION_MAX_BATCH_CANDIDATES = 20
VERIFICATION_MAX_BATCH_PAYLOAD_CHARS = 14_000


@dataclass(frozen=True)
class VerificationBatchOutcome:
    """Per-obligation outcomes plus the single provider-reported batch usage record."""

    outcomes: tuple[VerificationOutcome, ...]
    usage: InvocationUsage


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
    entailment_usage: InvocationUsage
    critic_usage: InvocationUsage


def citation_span_node(candidate: VerificationCandidate) -> tuple[CitationCheck, ...]:
    """Deterministically verify every claimed citation span."""
    return tuple(
        CitationCheck(
            citation.field_name,
            citation.quote,
            verify_citation(citation.quote, candidate.source_text),
        )
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
    params: ConfidenceParams | None = None,
) -> ConfidenceVerdict:
    """Aggregate visible signals using explicitly loaded or default parameters."""
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
        ),
        params=params or load_confidence_params().params,
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
    *,
    params: ConfidenceParams | None = None,
    entailment_usage: InvocationUsage = EMPTY_INVOCATION_USAGE,
    critic_usage: InvocationUsage = EMPTY_INVOCATION_USAGE,
) -> VerificationOutcome:
    """Run the four verification nodes in their fixed order."""
    citations = citation_span_node(candidate)
    entailment_signal = entailment_gate_node(candidate, entailment)
    critic_signal = adversarial_critic_node(candidate, critic)
    confidence = confidence_aggregation_node(
        candidate, citations, entailment_signal, critic_signal, params
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
        entailment_usage,
        critic_usage,
    )


def run_verification(candidate: VerificationCandidate) -> VerificationOutcome:
    """Invoke Groq free-tier signals once each, then run deterministic decisions."""
    payload = json.dumps(candidate.key_fields(), ensure_ascii=False, sort_keys=True)
    entailment_prompt = get_prompt("entailment_checker")
    entailment_llm = get_structured_llm(EntailmentAssessment, routing_type="critic")
    entailment_callback = UsageMetadataCallbackHandler()
    entailment = cast(
        EntailmentAssessment,
        _invoke_with_free_tier_backoff(
            entailment_llm,
            entailment_prompt.format_messages(
                source_text=candidate.source_text, candidate_json=payload
            ),
            entailment_callback,
        ),
    )
    critic_prompt = get_prompt("regulatory_critic")
    critic_llm = get_structured_llm(CriticAssessment, routing_type="critic")
    critic_callback = UsageMetadataCallbackHandler()
    critic = cast(
        CriticAssessment,
        _invoke_with_free_tier_backoff(
            critic_llm,
            critic_prompt.format_messages(
                source_text=candidate.source_text, candidate_json=payload
            ),
            critic_callback,
        ),
    )
    return verify_with_assessments(
        candidate,
        entailment,
        critic,
        params=load_confidence_params().params,
        entailment_usage=_usage(entailment_callback),
        critic_usage=_usage(critic_callback),
    )


def _citation_context(candidate: VerificationCandidate, radius: int = 0) -> str:
    """Return compact source windows around cited quotes without repeating a whole PDF chunk."""
    windows: list[tuple[int, int]] = []
    for citation in candidate.citations:
        # Reuse the deterministic verifier's source offsets. PDF whitespace and punctuation
        # normalization often make ``str.find`` fail even though the citation is valid; the old
        # behavior then sent an unrelated 1,500-character chunk prefix to the critic.
        span = find_citation_span_fast(citation.quote, candidate.source_text)
        if span is None:
            continue
        start, end = span
        windows.append(
            (max(0, start - radius), min(len(candidate.source_text), end + radius))
        )
    if not windows:
        # Citation failure is a non-overridable deterministic rejection. Keep a small, genuine
        # source sample so the bounded model nodes still run without wasting the free-tier budget.
        return candidate.source_text[: min(len(candidate.source_text), 500)]
    windows.sort()
    merged: list[tuple[int, int]] = []
    for start, end in windows:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return "\n…\n".join(candidate.source_text[start:end] for start, end in merged)


def _batch_payload(candidate: VerificationCandidate, alias: str = "0") -> dict[str, Any]:
    return {
        "i": alias,
        "s": _citation_context(candidate),
        "c": candidate.normalized_obligation,
        "q": {
            key: value
            for key, value in {
                "cnd": candidate.conditions,
                "exc": candidate.exceptions,
                "freq": candidate.frequency,
                "due": candidate.deadline_description,
            }.items()
            if value
        },
    }


def split_verification_batches(
    candidates: list[VerificationCandidate],
) -> list[list[VerificationCandidate]]:
    """Greedily bound both rows and serialized payload for Groq free-tier TPM safety."""
    batches: list[list[VerificationCandidate]] = []
    current: list[VerificationCandidate] = []
    current_chars = 0
    for candidate in candidates:
        candidate_chars = len(
            json.dumps(_batch_payload(candidate), ensure_ascii=False, sort_keys=True)
        )
        if current and (
            len(current) >= VERIFICATION_MAX_BATCH_CANDIDATES
            or current_chars + candidate_chars > VERIFICATION_MAX_BATCH_PAYLOAD_CHARS
        ):
            batches.append(current)
            current = []
            current_chars = 0
        current.append(candidate)
        current_chars += candidate_chars
    if current:
        batches.append(current)
    return batches


def run_verification_batch(
    candidates: tuple[VerificationCandidate, ...],
) -> VerificationBatchOutcome:
    """Get both Groq signals once for a bounded batch, then apply every deterministic node."""
    if not candidates:
        raise ValueError("verification batch cannot be empty")
    candidate_ids = [candidate.obligation_id for candidate in candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("verification batch obligation IDs must be unique")
    alias_to_candidate = {str(index): candidate for index, candidate in enumerate(candidates)}
    payload = [
        _batch_payload(candidate, alias)
        for alias, candidate in alias_to_candidate.items()
    ]
    prompt = get_prompt("verification_batch_critic")
    # Groq counts the requested completion allowance toward TPM. Its OpenAI-compatible
    # default is 4,096 tokens, which can make an otherwise small batch exceed the free
    # Llama model's 6,000-TPM ceiling before inference starts. Compact 20-row production
    # responses stay below 1,024 tokens, so bind that explicit cap.
    llm = get_structured_llm(
        VerificationBatchResult,
        routing_type="critic",
        max_tokens=VERIFICATION_MAX_OUTPUT_TOKENS,
    )
    messages = prompt.format_messages(
        candidate_batch_json=json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )
    callbacks: list[UsageMetadataCallbackHandler] = []
    errors: list[str] = []
    by_id = {}
    for attempt in range(1, 4):
        callback = UsageMetadataCallbackHandler()
        callbacks.append(callback)
        try:
            result = cast(
                VerificationBatchResult,
                _invoke_with_free_tier_backoff(llm, messages, callback),
            )
            by_id = {assessment.obligation_id: assessment for assessment in result.assessments}
            if len(by_id) != len(result.assessments) or set(by_id) != set(alias_to_candidate):
                raise RuntimeError(
                    "response aliases did not exactly match requested candidate aliases"
                )
            break
        except Exception as exc:
            errors.append(f"attempt {attempt}: {type(exc).__name__}: {exc}")
            if attempt == 3:
                raise RuntimeError(
                    "Groq batch failed structured-output validation three times: "
                    + " | ".join(errors)
                ) from exc
            time.sleep(float(attempt))
    outcomes = tuple(
        verify_with_assessments(
            candidate,
            EntailmentAssessment(
                label=by_id[str(index)].entailment_label,
                score=by_id[str(index)].entailment_score,
                reasoning=(
                    "Groq batch entailment code: "
                    f"{by_id[str(index)].entailment_reason_code}"
                ),
            ),
            CriticAssessment(
                has_substantive_objection=by_id[str(index)].critic_has_substantive_objection,
                objection=(
                    by_id[str(index)].critic_reason_code
                    if by_id[str(index)].critic_has_substantive_objection
                    else None
                ),
                reasoning=(
                    "Groq batch critic code: "
                    f"{by_id[str(index)].critic_reason_code}"
                ),
            ),
            params=load_confidence_params().params,
        )
        for index, candidate in enumerate(candidates)
    )
    usages = [_usage(callback) for callback in callbacks]
    reported = [usage for usage in usages if usage.total_tokens is not None]
    usage = (
        InvocationUsage(
            prompt_tokens=sum(item.prompt_tokens or 0 for item in reported),
            completion_tokens=sum(item.completion_tokens or 0 for item in reported),
        )
        if reported
        else EMPTY_INVOCATION_USAGE
    )
    return VerificationBatchOutcome(outcomes, usage)


def _invoke_with_free_tier_backoff(
    llm: Any, messages: Any, usage_callback: UsageMetadataCallbackHandler
) -> Any:
    """Honor Groq's explicit retry window without falling back to a paid provider."""
    for attempt in range(1, 7):
        try:
            return llm.invoke(messages, config={"callbacks": [usage_callback]})
        except Exception as exc:
            match = _RETRY_AFTER.search(str(exc))
            if match is None or attempt == 6:
                raise
            time.sleep(float(match.group(1)) + 1.0)
    raise RuntimeError("free-tier retry loop exhausted")


def _usage(callback: UsageMetadataCallbackHandler) -> InvocationUsage:
    values = list(getattr(callback, "usage_metadata", {}).values())
    if not values:
        return InvocationUsage()
    return InvocationUsage(
        prompt_tokens=sum(int(value.get("input_tokens", 0)) for value in values),
        completion_tokens=sum(int(value.get("output_tokens", 0)) for value in values),
        cost_usd=0.0,
    )


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
        "usage": {
            "entailment": {
                "prompt_tokens": outcome.entailment_usage.prompt_tokens,
                "completion_tokens": outcome.entailment_usage.completion_tokens,
                "total_tokens": outcome.entailment_usage.total_tokens,
                "cost_usd": outcome.entailment_usage.cost_usd,
            },
            "critic": {
                "prompt_tokens": outcome.critic_usage.prompt_tokens,
                "completion_tokens": outcome.critic_usage.completion_tokens,
                "total_tokens": outcome.critic_usage.total_tokens,
                "cost_usd": outcome.critic_usage.cost_usd,
            },
        },
    }
