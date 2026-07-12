"""Celery tasks for executing LangGraph AI workflows."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import structlog
from celery import shared_task
from sqlalchemy import select

from apps.api.database import async_session_maker
from apps.worker.main import app
from packages.regulatory_core.models.agents import (
    AgentRun, ExtractionRun, ModelInvocation, WorkflowEvent, WorkflowStatus,
)
from packages.regulatory_core.models.documents import (
    Clause, DocumentStatus, RegulatoryDocument, DocumentType, RegulatoryDomain
)
from packages.regulatory_core.models.obligations import (
    Obligation, ObligationStatus, ReviewTask
)
from packages.ai.workflows.extraction import build_extraction_graph
from packages.ai.workflows.states import DocumentExtractionState, ClauseData

logger = structlog.get_logger()


async def run_extraction_workflow_async(document_id: str) -> None:
    """Execute the full document intelligence LangGraph."""
    async with async_session_maker() as db:
        doc = await db.get(RegulatoryDocument, uuid.UUID(document_id))
        if not doc:
            logger.error("document_not_found", document_id=document_id)
            return

        # 1. Create ExtractionRun record
        run = ExtractionRun(
            organization_id=doc.organization_id,
            document_id=doc.id,
            workflow_type="full",
            status=WorkflowStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        
        # Load clauses
        clauses_result = await db.execute(
            select(Clause)
            .where(Clause.document_id == doc.id)
            .order_by(Clause.order_index)
        )
        db_clauses = clauses_result.scalars().all()
        
        # Build initial state
        initial_clauses: list[ClauseData] = []
        for c in db_clauses:
            initial_clauses.append({
                "id": str(c.id),
                "clause_number": c.clause_number,
                "heading": c.heading,
                "text_content": c.text_content,
                "classification": None,
                "obligations": [],
                "needs_review": False,
                "review_reason": None,
            })
            
        # Get full text for doc classification
        full_text = "\n\n".join(c.text_content for c in db_clauses if c.text_content)
            
        initial_state: DocumentExtractionState = {
            "run_id": str(run.id),
            "document_id": str(doc.id),
            "organization_id": str(doc.organization_id) if doc.organization_id else None,
            "file_path": doc.file_path or "",
            "title": doc.title,
            "document_type": None,
            "domain": None,
            "raw_text": full_text,
            "clauses": initial_clauses,
            "current_clause_index": 0,
            "extracted_obligations_count": 0,
            "messages": [],
            "errors": [],
            "metrics": [],
        }
        
        await db.flush()
        
        try:
            # 2. Execute Graph
            graph = build_extraction_graph()
            config = {"configurable": {"thread_id": str(run.id)}}
            
            # Run the graph
            final_state = await asyncio.to_thread(
                graph.invoke, initial_state, config
            )
            
            # 3. Process Results
            
            # Update Document with Classification
            if final_state.get("domain"):
                try:
                    doc.regulatory_domain = RegulatoryDomain(final_state["domain"].lower())
                except ValueError:
                    pass
            if final_state.get("document_type"):
                try:
                    doc.document_type = DocumentType(final_state["document_type"].upper())
                except ValueError:
                    pass
                    
            # Save obligations and update clauses
            approved_count = 0
            review_pending = 0
            
            for state_clause in final_state.get("clauses", []):
                # Update clause classification in DB
                db_clause = next((c for c in db_clauses if str(c.id) == state_clause["id"]), None)
                if db_clause and state_clause.get("classification"):
                    try:
                        from packages.regulatory_core.models.documents import ClauseType
                        db_clause.clause_type = ClauseType(state_clause["classification"].lower())
                    except ValueError:
                        pass
                
                # Save obligations
                for obs_dict in state_clause.get("obligations", []):
                    obl = Obligation(
                        document_id=doc.id,
                        clause_id=uuid.UUID(state_clause["id"]),
                        extraction_run_id=run.id,
                        source_text=state_clause["text_content"],
                        normalized_obligation=obs_dict.get("normalized_obligation", ""),
                        actor=obs_dict.get("actor", "Unknown"),
                        action=obs_dict.get("action", "Unknown"),
                        object=obs_dict.get("object"),
                        conditions=obs_dict.get("conditions"),
                        exceptions=obs_dict.get("exceptions"),
                        frequency=obs_dict.get("frequency"),
                        deadline_description=obs_dict.get("deadline_description"),
                        extraction_method="agentic_workflow",
                        model="gpt-4o",
                    )
                    
                    try:
                        from packages.regulatory_core.models.obligations import RiskLevel
                        if risk_str := obs_dict.get("risk_level"):
                            obl.risk_level = RiskLevel(risk_str.lower())
                    except ValueError:
                        pass
                    
                    # Handle Review logic
                    if state_clause.get("needs_review"):
                        obl.status = ObligationStatus.CANDIDATE
                        obl.review_status = "pending"
                        review_pending += 1
                        
                        # Create Review Task
                        task = ReviewTask(
                            task_type="extraction_review",
                            obligation_id=obl.id,
                            priority="high",
                            status="pending",
                            context={"reason": state_clause.get("review_reason")},
                        )
                        db.add(task)
                    else:
                        obl.status = ObligationStatus.APPROVED
                        obl.review_status = "auto_approved"
                        approved_count += 1
                        
                    db.add(obl)
            
            # Save metrics
            total_cost = 0.0
            total_tokens = 0
            for metric in final_state.get("metrics", []):
                agent_run = AgentRun(
                    extraction_run_id=run.id,
                    agent_name=metric["agent_name"],
                    status="completed" if not metric.get("error") else "failed",
                    duration_ms=metric["duration_ms"],
                    model_name=metric["model"],
                    prompt_tokens=metric["prompt_tokens"],
                    completion_tokens=metric["completion_tokens"],
                    total_tokens=metric["prompt_tokens"] + metric["completion_tokens"],
                    cost_usd=metric["cost_usd"],
                    error_message=metric.get("error"),
                )
                db.add(agent_run)
                
                if metric.get("cost_usd"):
                    total_cost += metric["cost_usd"]
                if metric.get("prompt_tokens") and metric.get("completion_tokens"):
                    total_tokens += metric["prompt_tokens"] + metric["completion_tokens"]
                    
            # Finalize run
            run.status = WorkflowStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
            run.total_clauses = len(initial_clauses)
            run.total_obligations = final_state.get("extracted_obligations_count", 0)
            run.approved_obligations = approved_count
            run.review_pending = review_pending
            run.total_tokens = total_tokens
            run.total_cost_usd = total_cost
            
            doc.status = DocumentStatus.EXTRACTED
            
            await db.commit()
            logger.info("extraction_workflow_completed", run_id=str(run.id), obligations=run.total_obligations)

        except Exception as e:
            logger.exception("extraction_workflow_failed", run_id=str(run.id))
            run.status = WorkflowStatus.FAILED
            run.error_message = str(e)
            run.completed_at = datetime.now(timezone.utc)
            doc.status = DocumentStatus.FAILED
            doc.processing_error = f"Workflow failed: {str(e)}"
            await db.commit()


@app.task(bind=True, max_retries=3)
def run_extraction_workflow_task(self, document_id: str) -> None:
    """Celery task to run the AI document extraction graph."""
    try:
        asyncio.run(run_extraction_workflow_async(document_id))
    except Exception as exc:
        logger.error("task_failed_retrying", task="run_extraction_workflow", error=str(exc))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
