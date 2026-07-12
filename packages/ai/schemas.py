"""Pydantic schemas for LLM structured output."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentClassification(BaseModel):
    """Schema for document classification output."""
    domain: str = Field(description="The regulatory domain or issuing authority (e.g., SEBI, RBI, NSE)")
    document_type: str = Field(description="The type of document (e.g., CIRCULAR, NOTIFICATION, REGULATION)")
    subject: str = Field(description="A concise summary of the document's subject or title")
    applicable_to: List[str] = Field(description="List of regulated entity types this applies to")
    confidence_score: float = Field(description="Confidence in this classification (0.0 to 1.0)")
    reasoning: str = Field(description="Brief explanation of the classification")


class ClauseClassification(BaseModel):
    """Schema for classifying a single clause."""
    clause_type: str = Field(description="One of: OBLIGATION, DEFINITION, EXEMPTION, INFORMATIONAL, AMENDMENT")
    contains_obligation: bool = Field(description="True if this clause contains at least one compliance obligation")
    confidence_score: float = Field(description="Confidence in this classification (0.0 to 1.0)")
    reasoning: str = Field(description="Brief explanation of why this classification was chosen")


class Citation(BaseModel):
    """A citation mapping an extracted field to the source text."""
    field_name: str = Field(description="The field this citation supports (e.g., 'actor', 'deadline')")
    exact_quote: str = Field(description="The EXACT text from the source clause that supports this extraction")


class ExtractedObligation(BaseModel):
    """A single compliance obligation extracted from text."""
    normalized_obligation: str = Field(description="Clear, concise, active-voice statement of what must be done")
    actor: str = Field(description="Who must perform the action (e.g., 'Stock Broker')")
    action: str = Field(description="The verb phrase of what must be done (e.g., 'submit report')")
    object: Optional[str] = Field(description="What the action is performed upon")
    conditions: Optional[str] = Field(description="Conditions that trigger the obligation")
    exceptions: Optional[str] = Field(description="Exceptions to the obligation")
    frequency: Optional[str] = Field(description="Frequency (e.g., 'one-time', 'daily', 'quarterly', 'on-occurrence')")
    deadline_description: Optional[str] = Field(description="Description of the deadline (e.g., 'within 15 days of quarter end')")
    risk_level: str = Field(description="One of: LOW, MEDIUM, HIGH, CRITICAL based on regulatory impact")
    citations: List[Citation] = Field(description="Citations proving where this information was found in the text")


class ClauseExtractionResult(BaseModel):
    """Result of extracting obligations from a clause."""
    obligations: List[ExtractedObligation] = Field(description="List of obligations found in this clause")
    needs_human_review: bool = Field(description="True if the extraction is complex, ambiguous, or low confidence")
    review_reason: Optional[str] = Field(description="Reason why human review is needed, if applicable")
