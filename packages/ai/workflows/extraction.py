"""Document Intelligence and Knowledge Extraction Subgraph.

This graph processes a regulatory document to:
1. Classify the document
2. Classify individual clauses
3. Extract structured obligations
4. Flag complex items for human review
"""

from __future__ import annotations

import json
import time
from typing import Any, Literal, cast

import structlog
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from apps.api.config import get_settings
from packages.ai.prompts import get_prompt
from packages.ai.providers import get_structured_llm
from packages.ai.schemas import (
    ClauseClassification,
    ClauseExtractionResult,
    DocumentClassification,
)
from packages.ai.workflows.states import AgentRunMetric, ClauseData, DocumentExtractionState

logger = structlog.get_logger()


def _sum_usage(callback: UsageMetadataCallbackHandler) -> tuple[int, int]:
    """Sum real input/output token counts recorded by a usage callback.

    Returns (0, 0) if the provider did not report usage metadata.
    """
    input_tokens = 0
    output_tokens = 0
    for usage in getattr(callback, "usage_metadata", {}).values():
        input_tokens += usage.get("input_tokens", 0)
        output_tokens += usage.get("output_tokens", 0)
    return input_tokens, output_tokens


def classify_document(state: DocumentExtractionState) -> dict:
    """Agent node: Classify the overall document."""
    logger.info("agent_node_start", node="classify_document", run_id=state["run_id"])
    start_time = time.monotonic()

    # Get prompt and LLM
    prompt = get_prompt("document_classifier")
    llm = get_structured_llm(DocumentClassification, routing_type="fast")

    # Take just the first 4000 chars for classification to save tokens
    text_sample = state["raw_text"][:4000]

    messages = prompt.format_messages(title=state["title"], text_sample=text_sample)

    usage_cb = UsageMetadataCallbackHandler()
    try:
        result = cast(
            DocumentClassification,
            llm.invoke(messages, config={"callbacks": [usage_cb]}),
        )

        duration = int((time.monotonic() - start_time) * 1000)
        prompt_tokens, completion_tokens = _sum_usage(usage_cb)
        metric = AgentRunMetric(
            agent_name="document_classifier",
            model=get_settings().fast_model_name or "provider-default-fast",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=0.0,
            duration_ms=duration,
            error=None,
        )

        return {"domain": result.domain, "document_type": result.document_type, "metrics": [metric]}
    except Exception as e:
        logger.error("agent_node_error", node="classify_document", error=str(e))
        return {"errors": [f"Document classification failed: {str(e)}"]}


def classify_clauses(state: DocumentExtractionState) -> dict:
    """Agent node: Batch classify all clauses to identify obligations."""
    logger.info("agent_node_start", node="classify_clauses", run_id=state["run_id"])

    prompt = get_prompt("clause_classifier")
    llm = get_structured_llm(ClauseClassification, routing_type="fast")

    document_context = f"Title: {state['title']}\nType: {state['document_type']}"

    updated_clauses = state["clauses"].copy()
    metrics = []

    # In a real implementation, we would use asyncio.gather here for parallelization
    # Doing sequentially for simplicity in this artifact
    for clause in updated_clauses:
        if not clause["text_content"].strip():
            continue

        start_time = time.monotonic()
        usage_cb = UsageMetadataCallbackHandler()
        messages = prompt.format_messages(
            document_context=document_context,
            heading=clause["heading"] or "None",
            text_content=clause["text_content"],
        )

        try:
            result = cast(
                ClauseClassification,
                llm.invoke(messages, config={"callbacks": [usage_cb]}),
            )

            clause["classification"] = result.clause_type

            duration = int((time.monotonic() - start_time) * 1000)
            prompt_tokens, completion_tokens = _sum_usage(usage_cb)
            metrics.append(
                AgentRunMetric(
                    agent_name="clause_classifier",
                    model=get_settings().fast_model_name or "provider-default-fast",
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost_usd=0.0,
                    duration_ms=duration,
                    error=None,
                )
            )

        except Exception as e:
            logger.error("clause_classification_error", clause_id=clause["id"], error=str(e))
            clause["classification"] = "UNKNOWN"

    return {"clauses": updated_clauses, "metrics": metrics, "current_clause_index": 0}


def router_should_extract(
    state: DocumentExtractionState,
) -> Literal["extract_obligations", "finalize_extraction"]:
    """Conditional edge: check if there are more clauses to extract."""
    idx = state["current_clause_index"]
    clauses = state["clauses"]

    if idx >= len(clauses):
        return "finalize_extraction"

    # Find next clause that contains obligations
    while idx < len(clauses):
        if clauses[idx].get("classification") == "OBLIGATION":
            return "extract_obligations"
        idx += 1

    return "finalize_extraction"


def extract_obligations(state: DocumentExtractionState) -> dict:
    """Agent node: Extract structured obligations from a single clause."""
    idx = state["current_clause_index"]

    # Fast-forward if we landed here but the clause isn't an obligation
    # (should be handled by router, but defense in depth)
    while (
        idx < len(state["clauses"]) and state["clauses"][idx].get("classification") != "OBLIGATION"
    ):
        idx += 1

    if idx >= len(state["clauses"]):
        return {"current_clause_index": idx}

    clause = state["clauses"][idx]
    logger.info("agent_node_start", node="extract_obligations", clause_id=clause["id"])

    prompt = get_prompt("obligation_extractor")
    # Use the REASONING model for complex extraction
    llm = get_structured_llm(ClauseExtractionResult, routing_type="reasoning")

    start_time = time.monotonic()
    messages = prompt.format_messages(
        document_title=state["title"],
        clause_number=clause["clause_number"] or "None",
        clause_heading=clause["heading"] or "None",
        text_content=clause["text_content"],
    )

    updated_clause = cast(ClauseData, dict(clause))
    metrics = []
    usage_cb = UsageMetadataCallbackHandler()

    try:
        result = cast(
            ClauseExtractionResult,
            llm.invoke(messages, config={"callbacks": [usage_cb]}),
        )

        # Convert pydantic models to dicts
        obligations = [json.loads(o.model_dump_json()) for o in result.obligations]

        updated_clause["obligations"] = obligations
        updated_clause["needs_review"] = result.needs_human_review
        updated_clause["review_reason"] = result.review_reason

        duration = int((time.monotonic() - start_time) * 1000)
        # Real token counts from the provider via the usage callback.
        # Cost accounting (per-model pricing) is a later phase, so cost_usd
        # stays 0.0 rather than a fabricated figure.
        prompt_tokens, completion_tokens = _sum_usage(usage_cb)
        metrics.append(
            AgentRunMetric(
                agent_name="obligation_extractor",
                model=get_settings().reasoning_model_name or "provider-default-reasoning",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=0.0,
                duration_ms=duration,
                error=None,
            )
        )

    except Exception as e:
        logger.error("obligation_extraction_error", clause_id=clause["id"], error=str(e))
        updated_clause["obligations"] = []
        updated_clause["needs_review"] = True
        updated_clause["review_reason"] = f"Extraction failed: {str(e)}"

    # Update the clauses list
    updated_clauses = state["clauses"].copy()
    updated_clauses[idx] = updated_clause

    return {"clauses": updated_clauses, "current_clause_index": idx + 1, "metrics": metrics}


def finalize_extraction(state: DocumentExtractionState) -> dict:
    """Agent node: Summarize results and mark completion."""
    logger.info("agent_node_start", node="finalize_extraction", run_id=state["run_id"])

    total_obligations = 0
    for clause in state["clauses"]:
        total_obligations += len(clause.get("obligations", []))

    return {"extracted_obligations_count": total_obligations}


def build_extraction_graph() -> Any:
    """Build and compile the Document Extraction LangGraph."""
    workflow = StateGraph(DocumentExtractionState)

    # Add nodes
    workflow.add_node("classify_document", classify_document)
    workflow.add_node("classify_clauses", classify_clauses)
    workflow.add_node("extract_obligations", extract_obligations)
    workflow.add_node("finalize_extraction", finalize_extraction)

    # Define edges
    workflow.set_entry_point("classify_document")
    workflow.add_edge("classify_document", "classify_clauses")

    # Route from clause classification to either extraction loop or end
    workflow.add_conditional_edges(
        "classify_clauses",
        router_should_extract,
        {
            "extract_obligations": "extract_obligations",
            "finalize_extraction": "finalize_extraction",
        },
    )

    # Loop over all obligations
    workflow.add_conditional_edges(
        "extract_obligations",
        router_should_extract,
        {
            "extract_obligations": "extract_obligations",
            "finalize_extraction": "finalize_extraction",
        },
    )

    workflow.add_edge("finalize_extraction", END)

    # We use in-memory saver for development, but in production
    # we would use AsyncPostgresSaver pointing to our database
    memory = MemorySaver()

    return workflow.compile(checkpointer=memory)
