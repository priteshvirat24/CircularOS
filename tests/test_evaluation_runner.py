from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from apps.api.database import async_session_maker
from packages.evaluation.runner import run_diff_eval, run_extraction_eval
from packages.regulatory_core.models.agents import (
    AgentRun,
    AgentStatus,
    ExtractionRun,
    WorkflowStatus,
)
from packages.regulatory_core.models.documents import Clause, DocumentPage, RegulatoryDocument
from packages.regulatory_core.models.evaluation import (
    EvaluationDataset,
    EvaluationExample,
    EvaluationResult,
)
from packages.regulatory_core.models.obligations import Obligation, ObligationCitation

OLD_DOC = """MASTER CIRCULAR

TABLE OF CONTENTS
16. Annual System Audit of Stock Brokers
16
17. Review of norms relating to trading by Members/ Sub-Brokers
17
18. Cyber Security framework for Stock Brokers
18

16. Annual System Audit of Stock Brokers
16.1. The stock broker shall undergo an annual system audit.

17. Review of norms relating to trading by Members/ Sub-Brokers
17.1. Stock Exchanges are directed to review the norms.

18. Cyber Security framework for Stock Brokers
18.1. Brokers shall report cyber incidents within 6 hours.
"""

NEW_DOC = """MASTER CIRCULAR

TABLE OF CONTENTS
16. Annual System Audit of Stock Brokers
16
17. Framework for Monitoring and Supervision of System Audit through Technology
17
18. Review of norms relating to trading by Members
18
19. Cyber Security framework for Stock Brokers
19

16. Annual System Audit of Stock Brokers
16.1. The stock broker shall undergo an annual system audit.

17. Framework for Monitoring and Supervision of System Audit through Technology
17.1. Stock Exchanges shall develop a web portal to monitor the audit lifecycle.

18. Review of norms relating to trading by Members
18.1. Stock Exchanges are directed to review the norms.

19. Cyber Security framework for Stock Brokers
19.1. Brokers shall report cyber incidents within 6 hours.
"""


async def test_extraction_runner_persists_full_fixture_contract() -> None:
    marker = uuid.uuid4().hex
    page_text = "Stock Broker shall maintain records. Informational background only."
    async with async_session_maker() as db:
        document = RegulatoryDocument(title=f"eval-fixture-{marker}.pdf")
        db.add(document)
        await db.flush()
        db.add(DocumentPage(document_id=document.id, page_number=1, text_content=page_text))
        clause = Clause(
            document_id=document.id,
            clause_number="1.1",
            text_content=page_text,
            page_start=1,
            page_end=1,
        )
        db.add(clause)
        await db.flush()
        extraction_run = ExtractionRun(
            document_id=document.id,
            workflow_type="full",
            status=WorkflowStatus.COMPLETED,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            total_tokens=12,
            total_cost_usd=0.0,
        )
        db.add(extraction_run)
        await db.flush()
        obligation = Obligation(
            document_id=document.id,
            clause_id=clause.id,
            extraction_run_id=extraction_run.id,
            source_text=page_text,
            normalized_obligation="Stock brokers must maintain records.",
            actor="Stock Broker",
            action="maintain records",
            validation_results={
                "citation_checks": [{"score": 1.0, "valid": True}],
                "entailment_signal": "entailment",
                "critic": {"has_substantive_objection": False},
                "confidence": {"score": 0.9},
            },
            risk_factors={"model_self_confidence": 0.9},
        )
        obligation.citations.append(
            ObligationCitation(
                field_name="action",
                cited_text="Stock Broker shall maintain records",
                clause_id=clause.id,
            )
        )
        db.add(obligation)
        db.add(
            AgentRun(
                extraction_run_id=extraction_run.id,
                agent_name="obligation_extractor",
                status=AgentStatus.COMPLETED,
                prompt_tokens=10,
                completion_tokens=2,
                total_tokens=12,
                cost_usd=0.0,
            )
        )
        dataset = EvaluationDataset(
            name=f"fixture-extraction-{marker}",
            dataset_type="obligation_extraction",
            example_count=2,
        )
        db.add(dataset)
        await db.flush()
        db.add_all(
            [
                EvaluationExample(
                    dataset_id=dataset.id,
                    source_document_id=document.id,
                    input_data={
                        "gold_id": "positive",
                        "clause_ref": "1.1",
                        "exact_quote": "Stock Broker shall maintain records",
                    },
                    expected_output={
                        "is_obligation": True,
                        "normalized_obligation": "Stock broker must maintain records",
                        "actor": "Stock Broker",
                        "action": "maintain records",
                        "deadline": None,
                        "frequency": None,
                        "evidence_requirement": None,
                    },
                    difficulty="easy",
                    tags=[],
                ),
                EvaluationExample(
                    dataset_id=dataset.id,
                    source_document_id=document.id,
                    input_data={
                        "gold_id": "negative",
                        "clause_ref": "1.2",
                        "exact_quote": "Informational background only",
                    },
                    expected_output={"is_obligation": False},
                    difficulty="easy",
                    tags=["negative"],
                ),
            ]
        )
        await db.commit()
        dataset_id = dataset.id

    run = await run_extraction_eval(
        dataset_id,
        {"export_calibration": False, "obligation_similarity_threshold": 0.5},
    )

    assert run.status == "completed"
    assert run.precision == run.recall == run.f1_score == 1.0
    assert run.total_tokens == 12
    assert run.metrics["corpus_coverage"]["status"] == "FULL"
    assert run.metrics["matcher_config"]["obligation_similarity_threshold"] == 0.5
    assert "single-annotator" in run.metrics["ground_truth_note"]
    async with async_session_maker() as db:
        result_count = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(EvaluationResult)
                    .where(EvaluationResult.evaluation_run_id == run.id)
                )
            ).scalar()
            or 0
        )
    assert result_count == 2


async def test_diff_runner_persists_final_fixture_metrics() -> None:
    marker = uuid.uuid4().hex
    old_marker = f"fixture-{marker}-2024-08-09"
    new_marker = f"fixture-{marker}-2025-06-17"
    async with async_session_maker() as db:
        old = RegulatoryDocument(title=f"{old_marker}.pdf")
        new = RegulatoryDocument(title=f"{new_marker}.pdf")
        db.add_all([old, new])
        await db.flush()
        db.add_all(
            [
                DocumentPage(document_id=old.id, page_number=1, text_content=OLD_DOC),
                DocumentPage(document_id=new.id, page_number=1, text_content=NEW_DOC),
            ]
        )
        dataset = EvaluationDataset(
            name=f"fixture-diff-{marker}",
            dataset_type="diff",
            example_count=3,
            metadata_json={"old_document": old_marker, "new_document": new_marker},
        )
        db.add(dataset)
        await db.flush()
        rows = [
            ("created", None, "§17", "CREATED", "Framework for Monitoring and Supervision"),
            (
                "modified",
                "§17",
                "§18",
                "MODIFIED",
                "Review of norms relating to trading by Members",
            ),
            ("cosmetic", "§18", "§19", "NOT_A_CHANGE", "Cyber Security framework"),
        ]
        for gold_id, old_ref, new_ref, change_type, new_text in rows:
            db.add(
                EvaluationExample(
                    dataset_id=dataset.id,
                    source_document_id=old.id,
                    input_data={
                        "gold_id": gold_id,
                        "old_ref": old_ref,
                        "new_ref": new_ref,
                        "old_text": None,
                        "new_text": new_text,
                    },
                    expected_output={"change_type": change_type},
                    tags=[change_type],
                )
            )
        await db.commit()
        dataset_id = dataset.id

    run = await run_diff_eval(dataset_id)

    assert run.status == "completed"
    assert run.metrics["headline_status"] == "FINAL"
    assert run.metrics["detection_rate"] == 1.0
    assert run.metrics["false_positive_rate"] == 0.0
    assert run.metrics["corpus_coverage"]["status"] == "FULL"
    assert run.total_tokens == 0
