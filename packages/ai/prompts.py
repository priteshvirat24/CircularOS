"""Prompts module for LLM interactions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage


@dataclass
class PromptTemplate:
    """A versioned prompt template."""

    name: str
    version: str
    system_prompt: str
    human_prompt: str
    description: str

    def format_messages(self, **kwargs: Any) -> list[BaseMessage]:
        """Format the prompt template with arguments."""
        try:
            formatted_system = self.system_prompt.format(**kwargs)
            formatted_human = self.human_prompt.format(**kwargs)

            messages: list[BaseMessage] = []
            if formatted_system:
                messages.append(SystemMessage(content=formatted_system))
            messages.append(HumanMessage(content=formatted_human))
            return messages
        except KeyError as exc:
            raise ValueError(f"Missing required argument for prompt '{self.name}': {exc}") from exc


# Registry of all system prompts
PROMPT_REGISTRY: dict[str, PromptTemplate] = {}


def register_prompt(prompt: PromptTemplate) -> None:
    """Register a prompt template."""
    PROMPT_REGISTRY[f"{prompt.name}@{prompt.version}"] = prompt
    # Also register as latest if no version specified
    PROMPT_REGISTRY[prompt.name] = prompt


def get_prompt(name: str, version: str | None = None) -> PromptTemplate:
    """Get a prompt from the registry."""
    key = f"{name}@{version}" if version else name
    if key not in PROMPT_REGISTRY:
        raise ValueError(f"Prompt '{key}' not found in registry")
    return PROMPT_REGISTRY[key]


# ---------------------------------------------------------------------------
# Pre-defined Prompts
# ---------------------------------------------------------------------------

register_prompt(
    PromptTemplate(
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

Identify the issuing authority (domain) and the document type.""",
    )
)

register_prompt(
    PromptTemplate(
        name="entailment_checker",
        version="1.0",
        description="Checks whether source text entails key fields in one obligation candidate",
        system_prompt="""You are a conservative regulatory extraction verifier.
Classify whether the supplied source text supports the candidate's actor, action, object,
conditions, exceptions, frequency, and deadline. Use only the source text. Do not repair the
candidate and do not infer missing facts. Contradiction means at least one material key field
conflicts with the source. Neutral means the source is ambiguous or insufficient.
Respond only with the requested structured schema.""",
        human_prompt="""SOURCE TEXT:
{source_text}

CANDIDATE JSON:
{candidate_json}

Return one entailment, neutral, or contradiction assessment.""",
    )
)

register_prompt(
    PromptTemplate(
        name="regulatory_critic",
        version="1.0",
        description="Independent one-pass adversarial critic for an obligation candidate",
        system_prompt="""You are an independent adversarial regulatory reviewer. Look for one
substantive defect: invented duty, wrong actor/action, omitted condition or exception, scope
inflation, or misleading deadline/frequency. Use only the supplied source. Do not object to
style. If no material defect is supported, report no substantive objection.
Respond only with the requested structured schema.""",
        human_prompt="""SOURCE TEXT:
{source_text}

CANDIDATE JSON:
{candidate_json}

Perform exactly one critic pass.""",
    )
)

register_prompt(
    PromptTemplate(
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

Classify this clause.""",
    )
)

register_prompt(
    PromptTemplate(
        name="obligation_extractor",
        version="1.1",
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
9. Self Confidence: Your confidence from 0.0 to 1.0 in this candidate extraction.
10. Difficulty: One of easy, medium, or hard based on ambiguity and clause complexity.

Consolidate each distinct actor-action-object duty into one obligation. Keep its conditions,
exceptions, frequency, and deadline on that same obligation; do not split those qualifiers into
separate duties. For citations, include only the smallest 1-3 exact source quotes needed to prove
the duty and any material qualifier. Do not duplicate the same quote once per field.
Extract every distinct obligation supported by the supplied text. Do not extract descriptive,
historical, cross-reference-only, or table-of-contents text as an obligation. Do not paraphrase
citations.

Respond ONLY with the requested JSON schema.""",
        human_prompt="""Document: {document_title}
Clause: {clause_number} - {clause_heading}

Clause Text:
{text_content}

Extract all compliance obligations from this text.""",
    )
)

register_prompt(
    PromptTemplate(
        name="verification_batch_critic",
        version="1.3",
        description="Produces bounded entailment and adversarial-critic signals in a batch",
        system_prompt="""Independently verify regulatory candidates extracted by another model.
Input keys: i=batch-local ID, s=source quote, c=claim, q=qualifiers. Return one assessment per i,
in input order, using only s. el: entailment|neutral|contradiction. er:
supported|insufficient|contradicted. Set co=true when c/q invents, reverses, materially omits, or
overstates s. cr: none|invented|reversed|omitted|overstated|ambiguous. Preserve every i; never
drop, duplicate, or merge candidates. Respond only with the requested JSON object.""",
        human_prompt="""Use this shape, repeated once per input:
{{"a":[{{"id":"same i value","el":"entailment","es":0.95,"er":"supported",
"co":false,"cr":"none"}}]}}

Input:
{candidate_batch_json}
""",
    )
)
