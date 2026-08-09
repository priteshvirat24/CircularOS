"""Database-backed runners for extraction and regulatory-diff evaluation."""

from __future__ import annotations

import time
import unicodedata
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api.database import async_session_maker
from apps.api.services.diff_service import _load_obligation_map
from packages.diff_engine import run_diff_pipeline
from packages.diff_engine.evaluate import evaluate_against_changeset
from packages.evaluation.calibration import (
    DEFAULT_PARAMS_PATH,
    ConfidenceTrainingRow,
    export_confidence_params,
    fit_calibration,
)
from packages.evaluation.matching import (
    EvaluationObligation,
    MatchedPair,
    MatcherConfig,
    MatchOutcome,
    match_obligations,
    normalized_similarity,
    spans_overlap,
)
from packages.evaluation.metrics import accuracy_by_group, field_accuracy, precision_recall_f1
from packages.evaluation.uncertainty import ConfusionObservation, bootstrap_f1_ci
from packages.policy_engine.citations import verify_citation
from packages.regulatory_core.models.agents import AgentRun, ExtractionRun, ModelInvocation
from packages.regulatory_core.models.documents import Clause, DocumentPage, RegulatoryDocument
from packages.regulatory_core.models.evaluation import (
    EvaluationDataset,
    EvaluationExample,
    EvaluationResult,
    EvaluationRun,
)
from packages.regulatory_core.models.obligations import Obligation

SINGLE_ANNOTATOR_NOTE = (
    "Ground truth is single-annotator; Cohen's kappa is not computed because no second "
    "annotator labels exist."
)
_REAL_USAGE_AGENT_NAMES = {
    "obligation_extractor",
    "full_section_obligation_extractor",
}
_DIFFICULTY_VALUE = {"easy": 0.0, "medium": 0.5, "hard": 1.0}
_ENTAILMENT_VALUE = {"entailment": 1.0, "neutral": 0.0, "contradiction": -1.0}


@dataclass(frozen=True)
class _DocumentSearchIndex:
    raw_text: str
    normalized_text: str
    original_offsets: tuple[int, ...]

    @classmethod
    def build(cls, raw_text: str) -> _DocumentSearchIndex:
        normalized, offsets = _normalize_with_offsets(raw_text)
        return cls(raw_text, normalized, offsets)

    def locate(self, quote: str) -> tuple[int, int] | None:
        exact_start = self.raw_text.find(quote)
        if exact_start >= 0:
            return exact_start, exact_start + len(quote)
        normalized_quote, _ = _normalize_with_offsets(quote)
        if not normalized_quote:
            return None
        start = self.normalized_text.find(normalized_quote)
        if start < 0:
            return None
        end = start + len(normalized_quote)
        return self.original_offsets[start], self.original_offsets[end - 1] + 1


def _normalize_with_offsets(value: str) -> tuple[str, tuple[int, ...]]:
    characters: list[str] = []
    offsets: list[int] = []
    pending_space: int | None = None
    for original_index, original_character in enumerate(value):
        for character in unicodedata.normalize("NFKC", original_character).casefold():
            separator = character.isspace() or unicodedata.category(character).startswith("P")
            if separator:
                if characters:
                    pending_space = original_index
                continue
            if pending_space is not None:
                characters.append(" ")
                offsets.append(pending_space)
                pending_space = None
            characters.append(character)
            offsets.append(original_index)
    return "".join(characters), tuple(offsets)


def _matcher(
    config: MatcherConfig,
) -> Callable[[Sequence[EvaluationObligation], Sequence[EvaluationObligation]], MatchOutcome]:
    def invoke(
        predictions: Sequence[EvaluationObligation],
        gold: Sequence[EvaluationObligation],
    ) -> MatchOutcome:
        return match_obligations(predictions, gold, config)

    return invoke


async def _document_text_and_pages(
    db: AsyncSession, document_id: uuid.UUID
) -> tuple[str, dict[int, tuple[int, int, str]]]:
    pages = (
        await db.execute(
            select(DocumentPage.page_number, DocumentPage.text_content)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        )
    ).all()
    parts: list[str] = []
    page_ranges: dict[int, tuple[int, int, str]] = {}
    cursor = 0
    for page_number, content in pages:
        text = content or ""
        if parts:
            parts.append("\n")
            cursor += 1
        start = cursor
        parts.append(text)
        cursor += len(text)
        page_ranges[page_number] = (start, cursor, text)
    return "".join(parts), page_ranges


def _locate_in_page(
    quote: str,
    page_number: int | None,
    page_ranges: Mapping[int, tuple[int, int, str]],
) -> tuple[int, int] | None:
    if page_number is None or page_number not in page_ranges:
        return None
    page_start, _, page_text = page_ranges[page_number]
    verdict = verify_citation(quote, page_text)
    if verdict.span is None:
        return None
    return page_start + verdict.span[0], page_start + verdict.span[1]


def _gold_span(quote: str, search_index: _DocumentSearchIndex) -> tuple[int, int] | None:
    return search_index.locate(quote)


def _prediction_span(
    obligation: Obligation,
    clause: Clause,
    page_ranges: Mapping[int, tuple[int, int, str]],
) -> tuple[int, int] | None:
    citation_spans = [
        span
        for citation in obligation.citations
        if (
            span := _locate_in_page(
                citation.cited_text,
                citation.page_number or clause.page_start,
                page_ranges,
            )
        )
        is not None
    ]
    if citation_spans:
        return min(span[0] for span in citation_spans), max(span[1] for span in citation_spans)
    start_page = clause.page_start
    if start_page is not None and start_page in page_ranges:
        start = page_ranges[start_page][0]
        end_page = clause.page_end or start_page
        end = page_ranges.get(end_page, page_ranges[start_page])[1]
        return start, end
    return None


def _prediction_record(
    obligation: Obligation,
    clause: Clause,
    page_ranges: Mapping[int, tuple[int, int, str]],
) -> EvaluationObligation:
    return EvaluationObligation(
        record_id=str(obligation.id),
        actor=obligation.actor,
        action=obligation.action,
        normalized_obligation=obligation.normalized_obligation,
        source_span=_prediction_span(obligation, clause, page_ranges),
        fields={
            "deadline": obligation.deadline_description,
            "frequency": obligation.frequency,
            "evidence": obligation.evidence_requirements,
            "object": obligation.object,
        },
        source_text=obligation.source_text,
    )


def _gold_record(
    example: EvaluationExample,
    span: tuple[int, int] | None,
) -> EvaluationObligation:
    expected = example.expected_output
    return EvaluationObligation(
        record_id=str(example.id),
        actor=expected.get("actor"),
        action=expected.get("action"),
        normalized_obligation=expected.get("normalized_obligation"),
        source_span=span,
        fields={
            "deadline": expected.get("deadline"),
            "frequency": expected.get("frequency"),
            "evidence": expected.get("evidence_requirement"),
            "object": expected.get("object"),
        },
        source_text=example.input_data.get("exact_quote"),
    )


def _record_payload(record: EvaluationObligation) -> dict[str, Any]:
    return {
        "id": record.record_id,
        "actor": record.actor,
        "action": record.action,
        "normalized_obligation": record.normalized_obligation,
        "source_span": list(record.source_span) if record.source_span else None,
        "fields": dict(record.fields),
    }


def _failure_reason(
    gold: EvaluationObligation,
    predictions: Sequence[EvaluationObligation],
    config: MatcherConfig,
) -> str:
    overlapping = [
        prediction
        for prediction in predictions
        if spans_overlap(prediction.source_span, gold.source_span)
    ]
    if not overlapping:
        return "no extracted candidate cited an overlapping source span"
    closest = max(
        overlapping,
        key=lambda prediction: normalized_similarity(
            prediction.normalized_obligation, gold.normalized_obligation
        ),
    )
    actor = normalized_similarity(closest.actor, gold.actor, actor=True)
    action = normalized_similarity(closest.action, gold.action)
    obligation = normalized_similarity(closest.normalized_obligation, gold.normalized_obligation)
    if actor < config.actor_alignment_threshold:
        return (
            f"closest source-overlapping candidate had actor alignment {actor:.3f} below threshold"
        )
    if action < config.action_alignment_threshold:
        return f"closest source-overlapping candidate had action alignment {action:.3f} below threshold"
    return (
        f"closest source-overlapping candidate had normalized-obligation similarity "
        f"{obligation:.3f} below threshold"
    )


def _named_failures(
    examples_by_id: Mapping[str, EvaluationExample],
    gold: Sequence[EvaluationObligation],
    predictions: Sequence[EvaluationObligation],
    matched_pairs: Sequence[MatchedPair],
    unmatched_gold_indices: Sequence[int],
    unmatched_prediction_indices: Sequence[int],
    config: MatcherConfig,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    prioritized = sorted(
        unmatched_gold_indices,
        key=lambda index: (
            "conditional" not in (examples_by_id[gold[index].record_id].tags or []),
            examples_by_id[gold[index].record_id].difficulty != "hard",
            examples_by_id[gold[index].record_id].input_data.get("gold_id", ""),
        ),
    )
    for index in prioritized:
        item = gold[index]
        example = examples_by_id[item.record_id]
        failures.append(
            {
                "failure_type": "false_negative",
                "gold_id": example.input_data.get("gold_id"),
                "clause_ref": example.input_data.get("clause_ref"),
                "difficulty": example.difficulty,
                "tags": example.tags or [],
                "expected_obligation": item.normalized_obligation,
                "reason": _failure_reason(item, predictions, config),
            }
        )
        if len(failures) >= limit:
            return failures
    matched_prediction_ids = {pair.prediction.record_id for pair in matched_pairs}
    for index in unmatched_prediction_indices:
        item = predictions[index]
        if item.record_id in matched_prediction_ids:
            continue
        failures.append(
            {
                "failure_type": "false_positive",
                "prediction_id": item.record_id,
                "predicted_obligation": item.normalized_obligation,
                "reason": "no gold obligation met all actor/action/similarity/span gates",
            }
        )
        if len(failures) >= limit:
            break
    return failures


def _bootstrap_observations_by_gold_example(
    covered_examples: Sequence[EvaluationExample],
    spans_by_example: Mapping[str, tuple[int, int] | None],
    matched_by_gold: Mapping[str, MatchedPair],
    scored_predictions: Sequence[EvaluationObligation],
    unmatched_prediction_indices: Sequence[int],
) -> list[ConfusionObservation]:
    """Allocate confusion contributions to gold examples for gold-set resampling."""
    contributions: dict[str, list[int]] = {
        str(example.id): [0, 0, 0] for example in covered_examples
    }
    for example in covered_examples:
        if not example.expected_output.get("is_obligation"):
            continue
        key = str(example.id)
        if key in matched_by_gold:
            contributions[key][0] = 1
        else:
            contributions[key][2] = 1
    for prediction_index in unmatched_prediction_indices:
        prediction = scored_predictions[prediction_index]
        candidates = sorted(
            str(example.id)
            for example in covered_examples
            if spans_overlap(prediction.source_span, spans_by_example[str(example.id)])
        )
        if candidates:
            contributions[candidates[0]][1] += 1
    return [
        ConfusionObservation(
            true_positives=values[0],
            false_positives=values[1],
            false_negatives=values[2],
        )
        for _, values in sorted(contributions.items())
    ]


def _calibration_row(
    obligation: Obligation,
    correct: bool,
    difficulty: str | None,
) -> ConfidenceTrainingRow | None:
    provenance = obligation.validation_results or {}
    confidence = provenance.get("confidence") or {}
    checks = provenance.get("citation_checks") or []
    if not confidence or not checks:
        return None
    citation_score = min(float(check.get("score", 0.0)) for check in checks)
    entailment = _ENTAILMENT_VALUE.get(str(provenance.get("entailment_signal")), 0.0)
    critic_objection = float(
        bool((provenance.get("critic") or {}).get("has_substantive_objection"))
    )
    factors = obligation.risk_factors or {}
    raw_self_confidence = factors.get("model_self_confidence", 0.5)
    return ConfidenceTrainingRow(
        citation_score=citation_score,
        entailment=entailment,
        critic_objection=critic_objection,
        self_confidence=max(0.0, min(1.0, float(raw_self_confidence))),
        difficulty=_DIFFICULTY_VALUE.get(difficulty or "", 0.5),
        correct=correct,
    )


async def _usage_accounting(
    db: AsyncSession,
    obligations: Sequence[Obligation],
    document_id: uuid.UUID,
) -> dict[str, Any]:
    source_run_ids = {item.extraction_run_id for item in obligations if item.extraction_run_id}
    known_tokens = 0
    known_cost = 0.0
    if source_run_ids:
        rows = (
            await db.execute(
                select(AgentRun.total_tokens, AgentRun.cost_usd).where(
                    AgentRun.extraction_run_id.in_(source_run_ids),
                    AgentRun.agent_name.in_(_REAL_USAGE_AGENT_NAMES),
                )
            )
        ).all()
        known_tokens += sum(int(tokens or 0) for tokens, _ in rows)
        known_cost += sum(float(cost or 0.0) for _, cost in rows)

    verification_run_ids = (
        (
            await db.execute(
                select(ExtractionRun.id).where(
                    ExtractionRun.document_id == document_id,
                    ExtractionRun.workflow_type.like("phase3_verification%"),
                )
            )
        )
        .scalars()
        .all()
    )
    invocations: list[tuple[int | None, float | None]] = []
    if verification_run_ids:
        invocation_rows = (
            await db.execute(
                select(ModelInvocation.total_tokens, ModelInvocation.cost_usd).where(
                    ModelInvocation.extraction_run_id.in_(verification_run_ids)
                )
            )
        ).all()
        invocations = [(row[0], row[1]) for row in invocation_rows]
        known_tokens += sum(int(tokens or 0) for tokens, _ in invocations)
        known_cost += sum(float(cost or 0.0) for _, cost in invocations)
    unreported = sum(tokens is None for tokens, _ in invocations)
    return {
        "provider_reported_tokens": known_tokens,
        "provider_reported_cost_usd": known_cost,
        "complete": unreported == 0,
        "unreported_model_invocations": unreported,
        "note": (
            "All pipeline invocations reported usage metadata."
            if unreported == 0
            else "Historical verification invocations did not persist provider token metadata; "
            "the token value is a real provider-reported lower bound, not an estimate."
        ),
    }


async def _create_run(
    db: AsyncSession,
    dataset: EvaluationDataset,
    run_type: str,
    name: str,
    model_config: Mapping[str, Any] | None,
) -> EvaluationRun:
    run = EvaluationRun(
        dataset_id=dataset.id,
        name=name,
        run_type=run_type,
        status="running",
        model_config_json=dict(model_config or {}),
        started_at=datetime.now(UTC),
    )
    db.add(run)
    await db.commit()
    return run


async def run_extraction_eval(
    dataset_id: str | uuid.UUID,
    model_config: Mapping[str, Any] | None = None,
) -> EvaluationRun:
    """Evaluate the real stored extraction output and persist aggregate/per-example results.

    The current no-spend mode reuses obligations emitted by the real extraction pipeline. When
    Phase 4.5 atomically publishes the full registry, this same function automatically evaluates
    full coverage and activates the full-corpus calibration artifact.
    """
    config_data = dict(model_config or {})
    matcher_config = MatcherConfig(
        obligation_similarity_threshold=float(
            config_data.get("obligation_similarity_threshold", 0.55)
        ),
        actor_alignment_threshold=float(config_data.get("actor_alignment_threshold", 0.70)),
        action_alignment_threshold=float(config_data.get("action_alignment_threshold", 0.55)),
    )
    async with async_session_maker() as db:
        dataset = await db.get(EvaluationDataset, uuid.UUID(str(dataset_id)))
        if dataset is None or dataset.dataset_type != "obligation_extraction":
            raise ValueError("obligation-extraction evaluation dataset not found")
        run = await _create_run(
            db,
            dataset,
            "obligation_extraction",
            "Extraction evaluation (coverage determined at runtime)",
            {**config_data, "reuse_real_stored_pipeline_output": True},
        )
        try:
            started = time.monotonic()
            examples = list(
                (
                    await db.execute(
                        select(EvaluationExample)
                        .where(EvaluationExample.dataset_id == dataset.id)
                        .order_by(EvaluationExample.id)
                    )
                )
                .scalars()
                .all()
            )
            document_ids = {item.source_document_id for item in examples if item.source_document_id}
            if len(document_ids) != 1:
                raise ValueError("extraction dataset must link to exactly one source document")
            document_id = next(iter(document_ids))
            document_text, page_ranges = await _document_text_and_pages(db, document_id)
            search_index = _DocumentSearchIndex.build(document_text)
            obligation_rows = list(
                (
                    await db.execute(
                        select(Obligation)
                        .options(selectinload(Obligation.citations))
                        .where(
                            Obligation.document_id == document_id,
                            Obligation.deleted_at.is_(None),
                        )
                        .order_by(Obligation.created_at, Obligation.id)
                    )
                )
                .scalars()
                .all()
            )
            clauses = {
                clause.id: clause
                for clause in (
                    await db.execute(
                        select(Clause).where(
                            Clause.id.in_([item.clause_id for item in obligation_rows])
                        )
                    )
                )
                .scalars()
                .all()
            }
            predictions = [
                _prediction_record(item, clauses[item.clause_id], page_ranges)
                for item in obligation_rows
            ]
            source_run_ids = {
                item.extraction_run_id for item in obligation_rows if item.extraction_run_id
            }
            coverage_clauses: list[Clause] = []
            if source_run_ids:
                coverage_clauses = list(
                    (
                        await db.execute(
                            select(Clause).where(
                                Clause.document_id == document_id,
                                Clause.extraction_run_id.in_(source_run_ids),
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
            if not coverage_clauses:
                coverage_clauses = list(clauses.values())
            clause_indexes = {
                str(clause.id): _DocumentSearchIndex.build(clause.text_content)
                for clause in coverage_clauses
            }
            spans_by_example = {
                str(example.id): _gold_span(
                    str(example.input_data.get("exact_quote") or ""), search_index
                )
                for example in examples
            }
            source_keys_by_example = {
                str(example.id): frozenset(
                    clause_id
                    for clause_id, clause_index in clause_indexes.items()
                    if clause_index.locate(str(example.input_data.get("exact_quote") or ""))
                    is not None
                )
                for example in examples
            }
            covered_examples = [
                example for example in examples if source_keys_by_example[str(example.id)]
            ]
            covered_spans = [
                span
                for example in covered_examples
                if (span := spans_by_example[str(example.id)]) is not None
            ]
            scored_predictions = [
                prediction
                for prediction in predictions
                if any(
                    spans_overlap(prediction.source_span, gold_span) for gold_span in covered_spans
                )
            ]
            positive_examples = [
                example
                for example in covered_examples
                if bool(example.expected_output.get("is_obligation"))
            ]
            gold = [
                _gold_record(
                    example,
                    spans_by_example[str(example.id)],
                )
                for example in positive_examples
            ]
            invoke_matcher = _matcher(matcher_config)
            extraction_metrics = precision_recall_f1(scored_predictions, gold, invoke_matcher)
            outcome = invoke_matcher(scored_predictions, gold)
            matched_by_gold = {pair.gold.record_id: pair for pair in outcome.matched_pairs}
            matched_prediction_ids = {pair.prediction.record_id for pair in outcome.matched_pairs}
            examples_by_id = {str(example.id): example for example in examples}

            await db.execute(
                delete(EvaluationResult).where(EvaluationResult.evaluation_run_id == run.id)
            )
            group_outcomes: list[tuple[str, bool]] = []
            passed_count = 0
            failed_count = 0
            covered_ids = {str(example.id) for example in covered_examples}
            for example in examples:
                example_id = str(example.id)
                started_example = time.monotonic()
                if example_id not in covered_ids:
                    result = EvaluationResult(
                        evaluation_run_id=run.id,
                        example_id=example.id,
                        predicted_output=None,
                        scores={"corpus_covered": False},
                        passed=None,
                        error="outside PARTIAL corpus coverage",
                        latency_ms=0,
                        tokens_used=0,
                    )
                elif example.expected_output.get("is_obligation"):
                    pair = matched_by_gold.get(example_id)
                    passed = pair is not None
                    passed_count += int(passed)
                    failed_count += int(not passed)
                    if example.difficulty:
                        group_outcomes.append((example.difficulty, passed))
                    result = EvaluationResult(
                        evaluation_run_id=run.id,
                        example_id=example.id,
                        predicted_output=_record_payload(pair.prediction) if pair else None,
                        scores={
                            "corpus_covered": True,
                            "matched": passed,
                            "obligation_similarity": pair.obligation_similarity if pair else None,
                            "actor_alignment": pair.actor_alignment if pair else None,
                            "action_alignment": pair.action_alignment if pair else None,
                        },
                        passed=passed,
                        latency_ms=int((time.monotonic() - started_example) * 1000),
                        tokens_used=0,
                    )
                else:
                    overlapping = [
                        prediction
                        for prediction in scored_predictions
                        if spans_overlap(prediction.source_span, spans_by_example[example_id])
                    ]
                    passed = not overlapping
                    passed_count += int(passed)
                    failed_count += int(not passed)
                    if example.difficulty:
                        group_outcomes.append((example.difficulty, passed))
                    result = EvaluationResult(
                        evaluation_run_id=run.id,
                        example_id=example.id,
                        predicted_output={
                            "overlapping_predictions": [
                                _record_payload(item) for item in overlapping
                            ]
                        },
                        scores={"corpus_covered": True, "negative_control_passed": passed},
                        passed=passed,
                        latency_ms=int((time.monotonic() - started_example) * 1000),
                        tokens_used=0,
                    )
                db.add(result)

            observations = _bootstrap_observations_by_gold_example(
                covered_examples,
                spans_by_example,
                matched_by_gold,
                scored_predictions,
                outcome.unmatched_prediction_indices,
            )
            uncertainty = bootstrap_f1_ci(observations, resamples=1000) if observations else None
            named_failures = _named_failures(
                examples_by_id,
                gold,
                scored_predictions,
                outcome.matched_pairs,
                outcome.unmatched_gold_indices,
                outcome.unmatched_prediction_indices,
                matcher_config,
            )
            usage = await _usage_accounting(db, obligation_rows, document_id)
            coverage_status = "FULL" if len(covered_examples) == len(examples) else "PARTIAL"
            difficulty_by_prediction: dict[str, str | None] = {
                pair.prediction.record_id: examples_by_id[pair.gold.record_id].difficulty
                for pair in outcome.matched_pairs
            }
            scored_prediction_ids = {prediction.record_id for prediction in scored_predictions}
            calibration_rows = [
                row
                for item in obligation_rows
                if str(item.id) in scored_prediction_ids
                if (
                    row := _calibration_row(
                        item,
                        str(item.id) in matched_prediction_ids,
                        difficulty_by_prediction.get(str(item.id)),
                    )
                )
                is not None
            ]
            calibration_metrics: dict[str, Any]
            if len(calibration_rows) >= 4 and len({row.correct for row in calibration_rows}) == 2:
                calibration = fit_calibration(
                    calibration_rows,
                    version=(
                        "phase4.5-full-calibrated-v1"
                        if coverage_status == "FULL"
                        else "phase4-partial-provisional-v1"
                    ),
                )
                artifact_path = Path(config_data.get("confidence_params_path", DEFAULT_PARAMS_PATH))
                if config_data.get("export_calibration", True):
                    export_confidence_params(
                        calibration,
                        artifact_path,
                        status="CALIBRATED" if coverage_status == "FULL" else "PROVISIONAL",
                    )
                calibration_metrics = {
                    "status": "CALIBRATED" if coverage_status == "FULL" else "PROVISIONAL",
                    "ece": calibration.ece,
                    "brier": calibration.brier,
                    "method": calibration.method,
                    "train_size": calibration.train_size,
                    "calibration_size": calibration.calibration_size,
                    "reliability_diagram": list(calibration.reliability),
                    "artifact_path": str(artifact_path),
                }
            else:
                calibration_metrics = {
                    "status": "NOT_FIT",
                    "reason": "available labeled predictions do not contain both outcome classes",
                }

            run.name = f"{coverage_status} extraction evaluation"
            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            run.total_examples = len(covered_examples)
            run.passed_examples = passed_count
            run.failed_examples = failed_count
            run.precision = extraction_metrics.precision
            run.recall = extraction_metrics.recall
            run.f1_score = extraction_metrics.f1
            run.total_tokens = int(usage["provider_reported_tokens"])
            run.total_cost_usd = float(usage["provider_reported_cost_usd"])
            run.metrics = {
                "headline_status": coverage_status,
                "confusion": extraction_metrics.confusion,
                "field_accuracy": field_accuracy(outcome.matched_pairs),
                "difficulty_breakdown": accuracy_by_group(group_outcomes),
                "bootstrap_f1_95_ci": (
                    {**uncertainty.as_dict(), "resampling_unit": "gold example"}
                    if uncertainty
                    else None
                ),
                "matcher_config": matcher_config.as_dict(),
                "named_failures": named_failures,
                "corpus_coverage": {
                    "status": coverage_status,
                    "basis": (
                        "gold exact quotes located inside source clauses represented in the "
                        "stored pipeline output"
                    ),
                    "evaluated_examples": len(covered_examples),
                    "dataset_examples": len(examples),
                    "evaluated_positive_obligations": len(positive_examples),
                    "dataset_positive_obligations": sum(
                        bool(example.expected_output.get("is_obligation")) for example in examples
                    ),
                    "stored_predictions": len(predictions),
                    "scored_predictions": len(scored_predictions),
                    "unscored_predictions_outside_annotated_spans": len(predictions)
                    - len(scored_predictions),
                    "coverage_fraction": (
                        len(covered_examples) / len(examples) if examples else 0.0
                    ),
                    "full_corpus_headline": (
                        "available"
                        if coverage_status == "FULL"
                        else "pending full-corpus run (Phase 4.5)"
                    ),
                },
                "token_cost_accounting": usage,
                "calibration": calibration_metrics,
                "ground_truth_note": SINGLE_ANNOTATOR_NOTE,
                "runtime_seconds": time.monotonic() - started,
            }
            await db.commit()
            return run
        except Exception as exc:
            await db.rollback()
            failed = await db.get(EvaluationRun, run.id)
            if failed is not None:
                failed.status = "failed"
                failed.completed_at = datetime.now(UTC)
                failed.metrics = {"error": str(exc)}
                await db.commit()
            raise


async def run_diff_eval(changeset_dataset_id: str | uuid.UUID) -> EvaluationRun:
    """Run the deterministic real diff and score all section-level change labels."""
    async with async_session_maker() as db:
        dataset = await db.get(EvaluationDataset, uuid.UUID(str(changeset_dataset_id)))
        if dataset is None or dataset.dataset_type != "diff":
            raise ValueError("diff evaluation dataset not found")
        run = await _create_run(
            db,
            dataset,
            "diff",
            "FINAL section-granularity diff evaluation",
            {"model_calls": 0, "deterministic": True},
        )
        try:
            examples = list(
                (
                    await db.execute(
                        select(EvaluationExample)
                        .where(EvaluationExample.dataset_id == dataset.id)
                        .order_by(EvaluationExample.id)
                    )
                )
                .scalars()
                .all()
            )
            metadata = dataset.metadata_json or {}
            old_marker = str(metadata.get("old_document") or "2024-08-09")
            new_marker = str(metadata.get("new_document") or "2025-06-17")
            old_doc = (
                await db.execute(
                    select(RegulatoryDocument).where(RegulatoryDocument.title.contains(old_marker))
                )
            ).scalar_one()
            new_doc = (
                await db.execute(
                    select(RegulatoryDocument).where(RegulatoryDocument.title.contains(new_marker))
                )
            ).scalar_one()
            old_text, _ = await _document_text_and_pages(db, old_doc.id)
            new_text, _ = await _document_text_and_pages(db, new_doc.id)
            old_map = await _load_obligation_map(db, old_doc.id, old_text)
            new_map = await _load_obligation_map(db, new_doc.id, new_text)
            result = run_diff_pipeline(
                old_text,
                new_text,
                old_obligations=old_map,
                new_obligations=new_map,
            )
            gold_rows = [
                {
                    "id": example.input_data["gold_id"],
                    "old_ref": example.input_data.get("old_ref"),
                    "new_ref": example.input_data.get("new_ref"),
                    "old_text": example.input_data.get("old_text"),
                    "new_text": example.input_data.get("new_text"),
                    "change_type": example.expected_output["change_type"],
                }
                for example in examples
            ]
            measured = evaluate_against_changeset(result, gold_rows, new_text)
            missed = set(measured["created_missed"]) | set(measured["modified_missed"])
            false_positive = set(measured["cosmetic_false_positives"])
            await db.execute(
                delete(EvaluationResult).where(EvaluationResult.evaluation_run_id == run.id)
            )
            passed_count = 0
            for example in examples:
                gold_id = example.input_data["gold_id"]
                passed = gold_id not in missed and gold_id not in false_positive
                passed_count += int(passed)
                db.add(
                    EvaluationResult(
                        evaluation_run_id=run.id,
                        example_id=example.id,
                        predicted_output={
                            "detected_changes": [
                                {
                                    "change_type": change.change_type,
                                    "old_ref": change.old_ref,
                                    "new_ref": change.new_ref,
                                }
                                for change in result.changes
                            ]
                        },
                        scores={
                            "matched": passed,
                            "gold_change_type": example.expected_output["change_type"],
                        },
                        passed=passed,
                        tokens_used=0,
                    )
                )
            substantive_total = measured["gold"]["created"] + measured["gold"]["modified"]
            substantive_hits = measured["created_detected"] + measured["modified_detected"]
            detection_rate = substantive_hits / substantive_total if substantive_total else 0.0
            cosmetic_total = measured["gold"]["cosmetic"]
            false_positive_rate = (
                len(measured["cosmetic_false_positives"]) / cosmetic_total
                if cosmetic_total
                else 0.0
            )
            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            run.total_examples = len(examples)
            run.passed_examples = passed_count
            run.failed_examples = len(examples) - passed_count
            run.total_tokens = 0
            run.total_cost_usd = 0.0
            run.metrics = {
                "headline_status": "FINAL",
                "granularity": "top-level numbered section labels",
                "detection_rate": detection_rate,
                "false_positive_rate": false_positive_rate,
                "confusion": {
                    "substantive_detected": substantive_hits,
                    "substantive_missed": substantive_total - substantive_hits,
                    "cosmetic_false_positives": len(measured["cosmetic_false_positives"]),
                    "cosmetic_correctly_suppressed": cosmetic_total
                    - len(measured["cosmetic_false_positives"]),
                },
                "by_change_type": measured,
                "matcher_config": result.matcher,
                "corpus_coverage": {
                    "status": "FULL",
                    "evaluated_examples": len(examples),
                    "dataset_examples": len(examples),
                    "coverage_fraction": 1.0,
                    "granularity": "section-level labeled changeset",
                },
                "token_cost_accounting": {
                    "provider_reported_tokens": 0,
                    "provider_reported_cost_usd": 0.0,
                    "complete": True,
                    "note": "The diff runner is deterministic and made no model calls.",
                },
                "ground_truth_note": SINGLE_ANNOTATOR_NOTE,
            }
            await db.commit()
            return run
        except Exception as exc:
            await db.rollback()
            failed = await db.get(EvaluationRun, run.id)
            if failed is not None:
                failed.status = "failed"
                failed.completed_at = datetime.now(UTC)
                failed.metrics = {"error": str(exc)}
                await db.commit()
            raise
