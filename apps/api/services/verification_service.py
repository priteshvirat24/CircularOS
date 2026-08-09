"""Persistence boundary for the Phase-3 verification workflow."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from apps.api.config import get_settings
from apps.api.database import async_session_maker
from packages.ai.workflows.verification import (
    CandidateCitation,
    VerificationCandidate,
    VerificationOutcome,
    VerificationRoute,
    outcome_as_dict,
    run_verification,
)
from packages.regulatory_core.models.agents import (
    ExtractionRun,
    ModelInvocation,
    WorkflowEvent,
    WorkflowStatus,
)
from packages.regulatory_core.models.auth import AuditEvent
from packages.regulatory_core.models.documents import RegulatoryDocument
from packages.regulatory_core.models.obligations import (
    Obligation,
    ObligationStatus,
    ReviewTask,
    ValidationResult,
)

WORKFLOW_TYPE = "phase3_verification_v1"


@dataclass(frozen=True)
class VerificationRunSummary:
    run_id: str
    total: int
    auto_registered: int
    human_review: int
    rejected: int
    citation_passed: int
    citation_rate: float
    corpus_label: str


def _candidate(obligation: Obligation) -> VerificationCandidate:
    factors = obligation.risk_factors or {}
    raw_confidence = factors.get("model_self_confidence", obligation.confidence)
    self_confidence = float(raw_confidence) if raw_confidence is not None else 0.5
    raw_difficulty = factors.get("extraction_difficulty")
    difficulty: Literal["easy", "medium", "hard"] | None = (
        raw_difficulty if raw_difficulty in {"easy", "medium", "hard"} else None
    )
    return VerificationCandidate(
        obligation_id=str(obligation.id),
        source_text=obligation.source_text,
        normalized_obligation=obligation.normalized_obligation,
        actor=obligation.actor,
        action=obligation.action,
        object=obligation.object,
        conditions=obligation.conditions,
        exceptions=obligation.exceptions,
        frequency=obligation.frequency,
        deadline_description=obligation.deadline_description,
        citations=tuple(
            CandidateCitation(citation.field_name, citation.cited_text)
            for citation in obligation.citations
        ),
        model_self_confidence=max(0.0, min(1.0, self_confidence)),
        difficulty=difficulty,
    )


async def _create_or_resume_run(document: RegulatoryDocument, total: int) -> ExtractionRun:
    async with async_session_maker() as db:
        existing = (
            await db.execute(
                select(ExtractionRun)
                .where(
                    ExtractionRun.document_id == document.id,
                    ExtractionRun.workflow_type == WORKFLOW_TYPE,
                    ExtractionRun.status.in_([WorkflowStatus.RUNNING, WorkflowStatus.PAUSED]),
                )
                .order_by(ExtractionRun.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.status = WorkflowStatus.RUNNING
            existing.current_stage = "verification"
            await db.commit()
            return existing
        run = ExtractionRun(
            organization_id=document.organization_id,
            document_id=document.id,
            workflow_type=WORKFLOW_TYPE,
            status=WorkflowStatus.RUNNING,
            current_stage="verification",
            total_obligations=total,
            approved_obligations=0,
            rejected_obligations=0,
            review_pending=0,
            started_at=datetime.now(UTC),
            total_tokens=0,
            total_cost_usd=0.0,
            checkpoint_data={"version": 1, "completed_ids": [], "failures": []},
        )
        db.add(run)
        await db.commit()
        return run


async def _persist_outcome(run_id: UUID, outcome: VerificationOutcome) -> None:
    payload = outcome_as_dict(outcome)
    settings = get_settings()
    async with async_session_maker() as db:
        obligation = (
            await db.execute(
                select(Obligation)
                .options(selectinload(Obligation.citations))
                .where(Obligation.id == UUID(outcome.obligation_id))
            )
        ).scalar_one()
        run = (
            await db.execute(
                select(ExtractionRun).where(ExtractionRun.id == run_id).with_for_update()
            )
        ).scalar_one_or_none()
        if run is None:
            raise RuntimeError(f"verification run disappeared: {run_id}")

        for citation, check in zip(obligation.citations, outcome.citation_checks, strict=True):
            citation.confidence = check.verdict.score
            citation.char_start = check.verdict.span[0] if check.verdict.span else None
            citation.char_end = check.verdict.span[1] if check.verdict.span else None

        citation_passed = bool(outcome.citation_checks) and all(
            check.verdict.valid for check in outcome.citation_checks
        )
        validation_rows = (
            ValidationResult(
                obligation_id=obligation.id,
                extraction_run_id=run.id,
                validator_name="citation_span_match@1.0",
                validator_type="deterministic",
                passed=citation_passed,
                score=min((check.verdict.score for check in outcome.citation_checks), default=0.0),
                message="all claimed citation spans verified"
                if citation_passed
                else "one or more citations were NOT_FOUND",
                details={"checks": payload["citation_checks"], "threshold": 0.95},
            ),
            ValidationResult(
                obligation_id=obligation.id,
                extraction_run_id=run.id,
                validator_name="entailment_checker@1.0",
                validator_type="model_signal_thresholded_deterministically",
                passed=outcome.entailment_signal == "entailment",
                score=outcome.entailment_raw.score,
                message=outcome.entailment_raw.reasoning,
                details={
                    "raw_label": outcome.entailment_raw.label,
                    "thresholded_label": outcome.entailment_signal,
                    "threshold": 0.65,
                    "provider": settings.critic_model_provider,
                    "model": settings.critic_model_name,
                    "prompt": "entailment_checker@1.0",
                },
            ),
            ValidationResult(
                obligation_id=obligation.id,
                extraction_run_id=run.id,
                validator_name="regulatory_critic@1.0",
                validator_type="independent_model_signal",
                passed=not outcome.critic.has_substantive_objection,
                score=None,
                message=outcome.critic.objection or outcome.critic.reasoning,
                details={
                    **outcome.critic.model_dump(),
                    "provider": settings.critic_model_provider,
                    "model": settings.critic_model_name,
                    "prompt": "regulatory_critic@1.0",
                    "passes": 1,
                },
            ),
            ValidationResult(
                obligation_id=obligation.id,
                extraction_run_id=run.id,
                validator_name=f"confidence_aggregation@{outcome.confidence.params_version}",
                validator_type="deterministic",
                passed=outcome.route is VerificationRoute.AUTO_REGISTER,
                score=outcome.confidence.score,
                message=outcome.confidence.explanation,
                details=payload["confidence"],
            ),
        )
        db.add_all(validation_rows)
        invocation_usage = (
            ("entailment", outcome.entailment_usage),
            ("critic", outcome.critic_usage),
        )
        for task_type, usage in invocation_usage:
            db.add(
                ModelInvocation(
                    extraction_run_id=run.id,
                    provider=settings.critic_model_provider or "groq",
                    model_name=settings.critic_model_name or "openai/gpt-oss-120b",
                    task_type=task_type,
                    response_format="pydantic",
                    was_structured=True,
                    validation_passed=True,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                    cost_usd=usage.cost_usd,
                )
            )

        obligation.validation_results = payload
        obligation.confidence = outcome.confidence.score
        obligation.validation_status = outcome.route.value
        if outcome.route is VerificationRoute.AUTO_REGISTER:
            obligation.status = ObligationStatus.VALIDATED
            obligation.review_status = "not_required"
        else:
            obligation.status = (
                ObligationStatus.REJECTED
                if outcome.route is VerificationRoute.REJECT
                else ObligationStatus.REVIEW_PENDING
            )
            obligation.review_status = "pending"
            existing_task = (
                await db.execute(
                    select(ReviewTask.id).where(
                        ReviewTask.obligation_id == obligation.id,
                        ReviewTask.task_type == "obligation_review",
                        ReviewTask.status == "pending",
                    )
                )
            ).scalar_one_or_none()
            if existing_task is None:
                db.add(
                    ReviewTask(
                        organization_id=obligation.organization_id,
                        obligation_id=obligation.id,
                        task_type="obligation_review",
                        priority="high" if outcome.route is VerificationRoute.REJECT else "medium",
                        status="pending",
                        context={
                            "verification_run_id": str(run.id),
                            "route": outcome.route.value,
                            "confidence": payload["confidence"],
                            "failed_citations": [
                                check for check in payload["citation_checks"] if not check["valid"]
                            ],
                            "critic": payload["critic"],
                        },
                    )
                )

        node_outputs = {
            "citation_span_match": payload["citation_checks"],
            "entailment_gate": {
                "raw": payload["entailment_raw"],
                "thresholded": payload["entailment_signal"],
            },
            "adversarial_critic": payload["critic"],
            "confidence_aggregation": payload["confidence"],
        }
        for node in outcome.ordered_nodes:
            db.add(
                WorkflowEvent(
                    extraction_run_id=run.id,
                    event_type="node_completed",
                    agent_name=node,
                    data={"obligation_id": str(obligation.id), "outcome": node_outputs[node]},
                )
            )
        db.add(
            WorkflowEvent(
                extraction_run_id=run.id,
                event_type="routed",
                agent_name="policy_decision_engine",
                data={
                    "obligation_id": str(obligation.id),
                    "route": outcome.route.value,
                    "deterministic": True,
                },
            )
        )
        db.add(
            AuditEvent(
                organization_id=obligation.organization_id,
                action="obligation.verification_routed",
                resource_type="obligation",
                resource_id=str(obligation.id),
                details={
                    "run_id": str(run.id),
                    "route": outcome.route.value,
                    "ordered_nodes": list(outcome.ordered_nodes),
                    "confidence": payload["confidence"],
                },
            )
        )
        checkpoint = dict(run.checkpoint_data or {})
        completed = list(checkpoint.get("completed_ids", []))
        if str(obligation.id) not in completed:
            completed.append(str(obligation.id))
        checkpoint["completed_ids"] = completed
        unreported = int(checkpoint.get("usage_unreported_invocations", 0))
        checkpoint["usage_unreported_invocations"] = unreported + sum(
            usage.total_tokens is None for _, usage in invocation_usage
        )
        run.checkpoint_data = checkpoint
        run.total_tokens = (run.total_tokens or 0) + sum(
            usage.total_tokens or 0 for _, usage in invocation_usage
        )
        run.total_cost_usd = (run.total_cost_usd or 0.0) + sum(
            usage.cost_usd for _, usage in invocation_usage
        )
        run.approved_obligations = (run.approved_obligations or 0) + int(
            outcome.route is VerificationRoute.AUTO_REGISTER
        )
        run.rejected_obligations = (run.rejected_obligations or 0) + int(
            outcome.route is VerificationRoute.REJECT
        )
        run.review_pending = (run.review_pending or 0) + int(
            outcome.route is VerificationRoute.HUMAN_REVIEW
        )
        await db.commit()


async def run_document_verification(
    document_title: str, *, free_tier_cooldown_seconds: float = 12.0
) -> VerificationRunSummary:
    """Verify one existing document corpus without adding extraction/model spend."""
    async with async_session_maker() as db:
        document = (
            await db.execute(
                select(RegulatoryDocument).where(RegulatoryDocument.title == document_title)
            )
        ).scalar_one()
        obligations = (
            (
                await db.execute(
                    select(Obligation)
                    .options(selectinload(Obligation.citations))
                    .where(Obligation.document_id == document.id, Obligation.deleted_at.is_(None))
                    .order_by(Obligation.created_at, Obligation.id)
                )
            )
            .scalars()
            .all()
        )
        candidates = [_candidate(obligation) for obligation in obligations]

    run = await _create_or_resume_run(document, len(candidates))
    completed_ids = set((run.checkpoint_data or {}).get("completed_ids", []))
    pending = [item for item in candidates if item.obligation_id not in completed_ids]
    try:
        for index, item in enumerate(pending):
            outcome = await asyncio.to_thread(run_verification, item)
            await _persist_outcome(run.id, outcome)
            if index < len(pending) - 1 and free_tier_cooldown_seconds > 0:
                await asyncio.sleep(free_tier_cooldown_seconds)
    except Exception as exc:
        async with async_session_maker() as db:
            db_run = await db.get(ExtractionRun, run.id)
            if db_run is not None:
                checkpoint = dict(db_run.checkpoint_data or {})
                failures = list(checkpoint.get("failures", []))
                failures.append({"at": datetime.now(UTC).isoformat(), "error": str(exc)[:2000]})
                checkpoint["failures"] = failures
                db_run.checkpoint_data = checkpoint
                db_run.status = WorkflowStatus.PAUSED
                db_run.current_stage = "provider_interruption"
                db_run.error_message = str(exc)[:4000]
                await db.commit()
        raise

    async with async_session_maker() as db:
        db_run = await db.get(ExtractionRun, run.id)
        if db_run is None:
            raise RuntimeError(f"verification run disappeared: {run.id}")
        db_run.status = WorkflowStatus.COMPLETED
        db_run.current_stage = "partial_corpus_complete"
        db_run.completed_at = datetime.now(UTC)
        if db_run.started_at:
            db_run.duration_seconds = (db_run.completed_at - db_run.started_at).total_seconds()
        db_run.total_cost_usd = 0.0
        summary = VerificationRunSummary(
            str(db_run.id),
            len(candidates),
            db_run.approved_obligations or 0,
            db_run.review_pending or 0,
            db_run.rejected_obligations or 0,
            0,
            0.0,
            "partial August corpus",
        )
        verified = (
            (
                await db.execute(
                    select(Obligation.validation_results).where(
                        Obligation.document_id == document.id,
                        Obligation.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        citation_passed = sum(
            bool(value and value.get("citation_checks"))
            and all(check["valid"] for check in value["citation_checks"])
            for value in verified
        )
        summary = VerificationRunSummary(
            summary.run_id,
            summary.total,
            summary.auto_registered,
            summary.human_review,
            summary.rejected,
            citation_passed,
            round(citation_passed / len(candidates), 6) if candidates else 0.0,
            summary.corpus_label,
        )
        db_run.checkpoint_data = {
            **(db_run.checkpoint_data or {}),
            "summary": summary.__dict__,
        }
        await db.commit()
        return summary
