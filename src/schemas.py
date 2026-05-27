"""Shared pydantic schemas used across pipeline modules."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ListingInput(BaseModel):
    title: str
    description: str = ""
    category: str = ""
    platform: str = ""
    has_authorization: bool = False


class ParsedListing(BaseModel):
    normalized_title: str
    normalized_description: str
    brand_terms: list[str] = Field(default_factory=list)
    product_terms: list[str] = Field(default_factory=list)
    inferred_category: str = ""


class EvidenceItem(BaseModel):
    evidence_id: str
    evidence_type: str
    source: str
    title: str = ""
    snippet: str
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrademarkMatch(BaseModel):
    mark: str
    status: str = ""
    owner: str = ""
    serial_number: str = ""
    registration_number: str = ""
    classes: list[str] = Field(default_factory=list)
    similarity: float = 0.0
    evidence: EvidenceItem | None = None


class ClaimMatch(BaseModel):
    patent_id: str
    claim_id: str = ""
    claim_text: str = ""
    similarity: float = 0.0
    evidence: EvidenceItem | None = None


class LitigationRecord(BaseModel):
    case_id: str
    court: str = ""
    filing_date: str = ""
    plaintiff: str = ""
    defendant: str = ""
    patent_ids: list[str] = Field(default_factory=list)
    outcome: str = ""
    evidence: EvidenceItem | None = None


class RiskResult(BaseModel):
    risk_type: str
    risk_level: str
    triggered_rules: list[str] = Field(default_factory=list)
    reason: str = ""
    evidences: list[EvidenceItem] = Field(default_factory=list)


class FinalAnswer(BaseModel):
    summary: str
    overall_risk_level: str
    risk_results: list[RiskResult] = Field(default_factory=list)
    rewrite_suggestions: list[str] = Field(default_factory=list)
    disclaimers: list[str] = Field(default_factory=list)
