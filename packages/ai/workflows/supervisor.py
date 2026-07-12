"""LangGraph Supervisor Pattern Orchestrator.

The supervisor acts as the central router, determining which subgraph
(Document Intelligence vs Knowledge Extraction) should run based on the
context and user input.
"""

from __future__ import annotations

import operator
from typing import Annotated, Literal, Optional, TypedDict, List

import structlog
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from packages.ai.providers import get_llm
from packages.ai.workflows.extraction import build_extraction_graph
from packages.ai.workflows.knowledge import build_knowledge_graph

logger = structlog.get_logger()


class SupervisorState(TypedDict):
    """State for the top-level supervisor orchestrator."""
    run_id: str
    organization_id: str
    
    # User Intent / Instructions
    user_request: str
    
    # Subgraph routing state
    next_subgraph: Optional[str]
    completed_subgraphs: Annotated[List[str], operator.add]
    
    # Payloads for subgraphs
    document_id: Optional[str]
    
    # History
    messages: Annotated[List[BaseMessage], operator.add]
    errors: Annotated[List[str], operator.add]


def supervisor_agent(state: SupervisorState) -> dict:
    """Agent node: Decide which subgraph to call next."""
    logger.info("agent_node_start", node="supervisor")
    
    # Fast routing model
    llm = get_llm("fast")
    
    sys_prompt = """You are a Supervisor Agent coordinating a Regulatory Intelligence Platform.
You have access to the following subgraphs:
- "document_extraction": Parses PDFs and extracts structured regulatory obligations.
- "knowledge_extraction": Maps extracted obligations to a compliance control framework.
- "FINISH": Ends the workflow.

Based on the user's request and the already completed subgraphs, decide what to do next.

Completed subgraphs: {completed}

Respond ONLY with the exact name of the next subgraph to call, or "FINISH". Do not use json or markdown blocks.
"""
    
    messages = [
        SystemMessage(content=sys_prompt.format(completed=state.get("completed_subgraphs", []))),
        HumanMessage(content=state["user_request"])
    ]
    
    try:
        response = llm.invoke(messages).content.strip()
        
        valid_options = ["document_extraction", "knowledge_extraction", "FINISH"]
        if response not in valid_options:
            logger.warning("invalid_supervisor_routing", response=response)
            response = "FINISH"
            
        return {"next_subgraph": response}
    except Exception as e:
        logger.error("supervisor_error", error=str(e))
        return {"next_subgraph": "FINISH", "errors": [str(e)]}


def build_supervisor_graph() -> StateGraph:
    """Build and compile the Supervisor LangGraph."""
    workflow = StateGraph(SupervisorState)
    
    # We would integrate the subgraphs as nodes here using standard LangGraph pattern:
    # workflow.add_node("document_extraction", build_extraction_graph())
    # workflow.add_node("knowledge_extraction", build_knowledge_graph())
    
    # For now, represent them as dummy nodes for the architecture
    def dummy_doc_node(state):
        return {"completed_subgraphs": ["document_extraction"]}
        
    def dummy_knowledge_node(state):
        return {"completed_subgraphs": ["knowledge_extraction"]}
        
    workflow.add_node("supervisor", supervisor_agent)
    workflow.add_node("document_extraction", dummy_doc_node)
    workflow.add_node("knowledge_extraction", dummy_knowledge_node)
    
    workflow.set_entry_point("supervisor")
    
    # Routing edges
    workflow.add_conditional_edges(
        "supervisor",
        lambda x: x["next_subgraph"],
        {
            "document_extraction": "document_extraction",
            "knowledge_extraction": "knowledge_extraction",
            "FINISH": END
        }
    )
    
    # Loop back to supervisor after subgraph finishes
    workflow.add_edge("document_extraction", "supervisor")
    workflow.add_edge("knowledge_extraction", "supervisor")
    
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)
