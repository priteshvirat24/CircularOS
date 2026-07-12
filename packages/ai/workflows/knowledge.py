"""Knowledge Extraction Subgraph for Control Mapping.

This graph processes extracted obligations and maps them to standard 
compliance controls (e.g., ISO 27001, SOC2, or custom framework).
"""

from __future__ import annotations

import json
import time
from typing import Literal, Dict, Any, List

import structlog
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from packages.ai.providers import get_llm
from packages.ai.workflows.states import KnowledgeExtractionState, AgentRunMetric
from langchain_core.messages import SystemMessage, HumanMessage

logger = structlog.get_logger()


def router_should_map(state: KnowledgeExtractionState) -> Literal["map_control", "finalize_knowledge"]:
    """Conditional edge: check if there are more obligations to map."""
    if state["current_obligation_index"] >= len(state["obligations"]):
        return "finalize_knowledge"
    return "map_control"


def map_control(state: KnowledgeExtractionState) -> dict:
    """Agent node: Map an obligation to the closest control from the library."""
    idx = state["current_obligation_index"]
    obligation = state["obligations"][idx]
    
    logger.info("agent_node_start", node="map_control", obligation_id=obligation.get("id"))
    
    # We use a standard LLM to do semantic mapping reasoning
    llm = get_llm("reasoning")
    
    controls_context = json.dumps([{
        "id": c.get("id"),
        "code": c.get("control_code"),
        "description": c.get("description")
    } for c in state["available_controls"]], indent=2)
    
    sys_prompt = """You are a Compliance Architect. 
Your task is to map a regulatory obligation to the most relevant internal compliance control from the provided library.
If no control matches well, indicate that a NEW control is required.

Available Controls:
{controls}

Respond ONLY with valid JSON in this format:
{{
  "mapped_control_id": "uuid or null",
  "requires_new_control": boolean,
  "suggested_new_control_name": "string or null",
  "reasoning": "string explanation"
}}"""
    
    human_prompt = f"""Obligation to map:
Actor: {obligation.get("actor")}
Action: {obligation.get("action")}
Object: {obligation.get("object")}
Conditions: {obligation.get("conditions")}
"""
    
    start_time = time.monotonic()
    
    messages = [
        SystemMessage(content=sys_prompt.format(controls=controls_context)),
        HumanMessage(content=human_prompt)
    ]
    
    metrics: List[AgentRunMetric] = []
    mapped_controls = []
    
    try:
        # Request JSON mode from the LLM
        response = llm.invoke(messages).content
        if isinstance(response, str):
            result = json.loads(response.strip("`json \n"))
        else:
            result = {"requires_new_control": True, "reasoning": "Failed to parse"}
            
        mapped_controls.append({
            "obligation_id": obligation.get("id"),
            "mapping_result": result
        })
        
        duration = int((time.monotonic() - start_time) * 1000)
        metrics.append(AgentRunMetric(
            agent_name="control_mapper",
            model="reasoning",
            prompt_tokens=800,
            completion_tokens=150,
            cost_usd=0.005,
            duration_ms=duration,
            error=None
        ))
        
    except Exception as e:
        logger.error("control_mapping_error", error=str(e))
        mapped_controls.append({
            "obligation_id": obligation.get("id"),
            "mapping_result": {"requires_new_control": True, "reasoning": f"Error: {e}"}
        })
        
    return {
        "current_obligation_index": idx + 1,
        "mapped_controls": mapped_controls,
        "metrics": metrics
    }


def finalize_knowledge(state: KnowledgeExtractionState) -> dict:
    """Agent node: Summarize mapping results."""
    logger.info("agent_node_start", node="finalize_knowledge", run_id=state["run_id"])
    return {}


def build_knowledge_graph() -> StateGraph:
    """Build and compile the Knowledge Extraction LangGraph."""
    workflow = StateGraph(KnowledgeExtractionState)
    
    workflow.add_node("map_control", map_control)
    workflow.add_node("finalize_knowledge", finalize_knowledge)
    
    workflow.set_entry_point("map_control")
    
    workflow.add_conditional_edges(
        "map_control",
        router_should_map,
        {
            "map_control": "map_control",
            "finalize_knowledge": "finalize_knowledge"
        }
    )
    
    workflow.add_edge("finalize_knowledge", END)
    
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)
