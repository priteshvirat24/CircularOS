"""Pydantic schemas for LLM structured output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DocumentClassification(BaseModel):
    """Schema for document classification output."""

    domain: str = Field(
        description="The regulatory domain or issuing authority (e.g., SEBI, RBI, NSE)"
    )
    document_type: str = Field(
        description="The type of document (e.g., CIRCULAR, NOTIFICATION, REGULATION)"
    )
    subject: str = Field(description="A concise summary of the document's subject or title")
    applicable_to: list[str] = Field(description="List of regulated entity types this applies to")
    confidence_score: float = Field(description="Confidence in this classification (0.0 to 1.0)")
    reasoning: str = Field(description="Brief explanation of the classification")


class ClauseClassification(BaseModel):
    """Schema for classifying a single clause."""

    clause_type: str = Field(
        description="One of: OBLIGATION, DEFINITION, EXEMPTION, INFORMATIONAL, AMENDMENT"
    )
    contains_obligation: bool = Field(
        description="True if this clause contains at least one compliance obligation"
    )
    confidence_score: float = Field(description="Confidence in this classification (0.0 to 1.0)")
    reasoning: str = Field(description="Brief explanation of why this classification was chosen")


class Citation(BaseModel):
    """A citation mapping an extracted field to the source text."""

    field_name: str = Field(
        description="The field this citation supports (e.g., 'actor', 'deadline')"
    )
    exact_quote: str = Field(
        description="The EXACT text from the source clause that supports this extraction"
    )


class ExtractedObligation(BaseModel):
    """A single compliance obligation extracted from text."""

    normalized_obligation: str = Field(
        description="Clear, concise, active-voice statement of what must be done"
    )
    actor: str = Field(description="Who must perform the action (e.g., 'Stock Broker')")
    action: str = Field(description="The verb phrase of what must be done (e.g., 'submit report')")
    object: str | None = Field(description="What the action is performed upon")
    conditions: str | None = Field(description="Conditions that trigger the obligation")
    exceptions: str | None = Field(description="Exceptions to the obligation")
    frequency: str | None = Field(
        description="Frequency (e.g., 'one-time', 'daily', 'quarterly', 'on-occurrence')"
    )
    deadline_description: str | None = Field(
        description="Description of the deadline (e.g., 'within 15 days of quarter end')"
    )
    risk_level: str = Field(
        description="One of: LOW, MEDIUM, HIGH, CRITICAL based on regulatory impact"
    )
    self_confidence: float = Field(
        description="Extractor's own confidence in this candidate from 0.0 to 1.0"
    )
    difficulty: str = Field(description="Extraction difficulty: easy, medium, or hard")
    citations: list[Citation] = Field(
        description="Citations proving where this information was found in the text"
    )


class ClauseExtractionResult(BaseModel):
    """Result of extracting obligations from a clause."""

    obligations: list[ExtractedObligation] = Field(
        description="List of obligations found in this clause"
    )
    needs_human_review: bool = Field(
        description="True if the extraction is complex, ambiguous, or low confidence"
    )
    review_reason: str | None = Field(
        description="Reason why human review is needed, if applicable"
    )


class EntailmentAssessment(BaseModel):
    """One model signal for whether source text supports an extraction."""

    label: Literal["entailment", "neutral", "contradiction"]
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(description="Short source-grounded reason for the label")


class CriticAssessment(BaseModel):
    """Independent adversarial review signal."""

    has_substantive_objection: bool
    objection: str | None = Field(
        description="Specific objection, or null when no substantive objection exists"
    )
    reasoning: str = Field(description="Short explanation grounded only in the supplied source")
