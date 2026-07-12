"""Agent workflow and execution trace routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from packages.regulatory_core.models.auth import User
from packages.regulatory_core.models.agents import (
    AgentRun, AgentStep, ExtractionRun, ModelInvocation, WorkflowEvent, WorkflowStatus,
)

router = APIRouter()


@router.get("/runs")
async def list_extraction_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    document_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List workflow/extraction runs."""
    query = select(ExtractionRun)
    
    if status_filter:
        try:
            query = query.where(ExtractionRun.status == WorkflowStatus(status_filter))
        except ValueError:
            pass
    
    if document_id:
        query = query.where(ExtractionRun.document_id == document_id)
    
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    query = query.order_by(ExtractionRun.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    runs = result.scalars().all()
    
    return {
        "runs": [
            {
                "id": str(r.id),
                "document_id": str(r.document_id),
                "workflow_type": r.workflow_type,
                "status": r.status.value,
                "current_stage": r.current_stage,
                "total_clauses": r.total_clauses,
                "total_obligations": r.total_obligations,
                "approved_obligations": r.approved_obligations,
                "total_tokens": r.total_tokens,
                "total_cost_usd": r.total_cost_usd,
                "duration_seconds": r.duration_seconds,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in runs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/runs/{run_id}")
async def get_extraction_run(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed extraction run with agent traces."""
    run = await db.get(ExtractionRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Extraction run not found")
    
    # Get agent runs
    agents_result = await db.execute(
        select(AgentRun)
        .where(AgentRun.extraction_run_id == run_id)
        .order_by(AgentRun.started_at)
    )
    agents = agents_result.scalars().all()
    
    # Get events
    events_result = await db.execute(
        select(WorkflowEvent)
        .where(WorkflowEvent.extraction_run_id == run_id)
        .order_by(WorkflowEvent.timestamp)
    )
    events = events_result.scalars().all()
    
    return {
        "id": str(run.id),
        "document_id": str(run.document_id),
        "workflow_type": run.workflow_type,
        "status": run.status.value,
        "current_stage": run.current_stage,
        "total_clauses": run.total_clauses,
        "total_obligations": run.total_obligations,
        "approved_obligations": run.approved_obligations,
        "rejected_obligations": run.rejected_obligations,
        "review_pending": run.review_pending,
        "total_tokens": run.total_tokens,
        "total_cost_usd": run.total_cost_usd,
        "duration_seconds": run.duration_seconds,
        "error_message": run.error_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "agents": [
            {
                "id": str(a.id),
                "agent_name": a.agent_name,
                "agent_type": a.agent_type,
                "status": a.status.value,
                "duration_ms": a.duration_ms,
                "model_name": a.model_name,
                "total_tokens": a.total_tokens,
                "cost_usd": a.cost_usd,
                "retry_count": a.retry_count,
                "validation_passed": a.validation_passed,
                "error_message": a.error_message,
                "started_at": a.started_at.isoformat() if a.started_at else None,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            }
            for a in agents
        ],
        "events": [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "agent_name": e.agent_name,
                "data": e.data,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in events
        ],
    }


@router.get("/runs/{run_id}/agents/{agent_run_id}")
async def get_agent_run_detail(
    run_id: uuid.UUID,
    agent_run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed agent run with individual steps."""
    agent_run = await db.get(AgentRun, agent_run_id)
    if not agent_run or agent_run.extraction_run_id != run_id:
        raise HTTPException(status_code=404, detail="Agent run not found")
    
    # Get steps
    steps_result = await db.execute(
        select(AgentStep)
        .where(AgentStep.agent_run_id == agent_run_id)
        .order_by(AgentStep.step_index)
    )
    steps = steps_result.scalars().all()
    
    # Get model invocations
    invocations_result = await db.execute(
        select(ModelInvocation)
        .where(ModelInvocation.agent_run_id == agent_run_id)
        .order_by(ModelInvocation.created_at)
    )
    invocations = invocations_result.scalars().all()
    
    return {
        "id": str(agent_run.id),
        "agent_name": agent_run.agent_name,
        "status": agent_run.status.value,
        "input_summary": agent_run.input_summary,
        "output_summary": agent_run.output_summary,
        "duration_ms": agent_run.duration_ms,
        "retry_count": agent_run.retry_count,
        "validation_passed": agent_run.validation_passed,
        "validation_details": agent_run.validation_details,
        "steps": [
            {
                "step_index": s.step_index,
                "step_type": s.step_type,
                "tool_name": s.tool_name,
                "input_data": s.input_data,
                "output_data": s.output_data,
                "duration_ms": s.duration_ms,
                "error": s.error,
            }
            for s in steps
        ],
        "model_invocations": [
            {
                "provider": i.provider,
                "model_name": i.model_name,
                "task_type": i.task_type,
                "prompt_tokens": i.prompt_tokens,
                "completion_tokens": i.completion_tokens,
                "cost_usd": i.cost_usd,
                "latency_ms": i.latency_ms,
                "was_structured": i.was_structured,
                "validation_passed": i.validation_passed,
            }
            for i in invocations
        ],
    }
