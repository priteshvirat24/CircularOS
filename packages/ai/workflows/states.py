"""LangGraph state schemas for workflows."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage


class AgentRunMetric(TypedDict):
    """Metrics for a single agent execution."""
    agent_name: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    duration_ms: int
    error: Optional[str]


class ClauseData(TypedDict):
    """Data for a single clause in processing."""
    id: str
    clause_number: Optional[str]
    heading: Optional[str]
    text_content: str
    classification: Optional[str]  # OBLIGATION, DEFINITION, etc.
    obligations: List[Dict[str, Any]]
    needs_review: bool
    review_reason: Optional[str]


class DocumentExtractionState(TypedDict):
    """State for the full document extraction workflow."""
    # Input
    run_id: str
    document_id: str
    organization_id: Optional[str]
    
    # Document Content
    file_path: str
    title: str
    document_type: Optional[str]
    domain: Optional[str]
    raw_text: str
    
    # Processing state
    clauses: List[ClauseData]
    current_clause_index: int
    
    # Outputs
    extracted_obligations_count: int
    
    # Messaging and errors
    messages: Annotated[List[BaseMessage], operator.add]
    errors: Annotated[List[str], operator.add]
    
    # Metrics
    metrics: Annotated[List[AgentRunMetric], operator.add]


class KnowledgeExtractionState(TypedDict):
    """State for the knowledge extraction and control mapping workflow."""
    # Input
    run_id: str
    organization_id: str
    document_id: str
    
    # State
    obligations: List[Dict[str, Any]]
    current_obligation_index: int
    
    # Context (Control Library)
    available_controls: List[Dict[str, Any]]
    
    # Output
    mapped_controls: Annotated[List[Dict[str, Any]], operator.add]
    
    # Messaging and errors
    messages: Annotated[List[BaseMessage], operator.add]
    errors: Annotated[List[str], operator.add]
    
    # Metrics
    metrics: Annotated[List[AgentRunMetric], operator.add]
