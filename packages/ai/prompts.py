"""Prompts module for LLM interactions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from langchain_core.messages import SystemMessage, HumanMessage

from apps.api.config import get_settings


@dataclass
class PromptTemplate:
    """A versioned prompt template."""
    name: str
    version: str
    system_prompt: str
    human_prompt: str
    description: str
    
    def format_messages(self, **kwargs) -> List[Any]:
        """Format the prompt template with arguments."""
        try:
            formatted_system = self.system_prompt.format(**kwargs)
            formatted_human = self.human_prompt.format(**kwargs)
            
            messages = []
            if formatted_system:
                messages.append(SystemMessage(content=formatted_system))
            messages.append(HumanMessage(content=formatted_human))
            return messages
        except KeyError as e:
            raise ValueError(f"Missing required argument for prompt '{self.name}': {e}")


# Registry of all system prompts
PROMPT_REGISTRY: Dict[str, PromptTemplate] = {}

def register_prompt(prompt: PromptTemplate) -> None:
    """Register a prompt template."""
    PROMPT_REGISTRY[f"{prompt.name}@{prompt.version}"] = prompt
    # Also register as latest if no version specified
    PROMPT_REGISTRY[prompt.name] = prompt


def get_prompt(name: str, version: Optional[str] = None) -> PromptTemplate:
    """Get a prompt from the registry."""
    key = f"{name}@{version}" if version else name
    if key not in PROMPT_REGISTRY:
        raise ValueError(f"Prompt '{key}' not found in registry")
    return PROMPT_REGISTRY[key]


# ---------------------------------------------------------------------------
# Pre-defined Prompts
# ---------------------------------------------------------------------------

register_prompt(PromptTemplate(
    name="document_classifier",
    version="1.0",
    description="Classifies a regulatory document by domain and type",
    system_prompt="""You are an expert regulatory compliance analyst for the Indian Securities Market (SEBI, NSE, BSE, RBI).
Your task is to analyze the provided regulatory document text and classify its domain and type accurately.

Categories:
- Domain: SEBI, RBI, MCA, NSE, BSE, CDSL, NSDL, IRDAI, PFRDA, OTHER
- Type: CIRCULAR, MASTER_CIRCULAR, NOTIFICATION, MASTER_DIRECTION, GUIDELINE, REGULATION, RULE, ACT, ORDER, CONSULTATION_PAPER, OTHER

Respond ONLY with the requested JSON schema.""",
    human_prompt="""Please classify the following regulatory document based on its title and text sample:

TITLE: {title}

TEXT SAMPLE (First page):
{text_sample}

Identify the issuing authority (domain) and the document type."""
))

register_prompt(PromptTemplate(
    name="clause_classifier",
    version="1.0",
    description="Classifies individual document clauses to determine if they contain obligations",
    system_prompt="""You are an expert regulatory compliance analyst. 
Your task is to classify whether a specific clause from a regulatory document contains a compliance obligation, definition, exemption, or informational text.

An OBLIGATION implies a mandatory action, requirement, prohibition, or compliance standard that a regulated entity must adhere to (look for 'shall', 'must', 'is required to', 'ensure').
A DEFINITION defines terms used in the regulation.
An EXEMPTION removes an obligation under certain conditions.
INFORMATIONAL is background context, preamble, or procedural text.

Respond ONLY with the requested JSON schema.""",
    human_prompt="""Document Context: {document_context}
Clause Heading: {heading}

Clause Text:
{text_content}

Classify this clause."""
))

register_prompt(PromptTemplate(
    name="obligation_extractor",
    version="1.0",
    description="Extracts structured obligations from regulatory clauses",
    system_prompt="""You are an expert regulatory compliance analyst for the Indian Securities Market.
Your task is to extract structured, machine-actionable compliance obligations from the provided regulatory text.

Extract the following:
1. Normalized Obligation: A clear, concise, active-voice statement of what must be done.
2. Actor: Who must perform the action (e.g., 'Stock Broker', 'Depository Participant', 'Listed Entity').
3. Action: The verb phrase of what must be done (e.g., 'submit report', 'maintain records').
4. Object: What the action is performed upon.
5. Conditions: Any conditions that trigger the obligation.
6. Exceptions: Any exceptions to the obligation.
7. Frequency: One-time, daily, weekly, monthly, quarterly, half-yearly, yearly, on-occurrence.
8. Deadline: Specific deadline if mentioned (e.g., 'within 15 days of quarter end').

For citations, you must accurately quote the EXACT text snippet that supports each field.

Respond ONLY with the requested JSON schema.""",
    human_prompt="""Document: {document_title}
Clause: {clause_number} - {clause_heading}

Clause Text:
{text_content}

Extract all compliance obligations from this text."""
))
