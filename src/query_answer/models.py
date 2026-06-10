from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.query_understanding.models import QueryUnderstandingResponse


EvidenceCoverageStatus = Literal[
    "addressed",
    "not_found_in_evidence",
    "not_retrieved",
    "out_of_scope",
]


class EvidenceCitation(BaseModel):
    """Reference to evidence supplied to the answer synthesis prompt."""

    source_id: str
    section: str
    snippet: str | None = None


class EvidenceBullet(BaseModel):
    """A grounded answer bullet and its supporting citations."""

    text: str
    citations: list[EvidenceCitation] = Field(default_factory=list)


class EvidenceAnswer(BaseModel):
    """LLM-generated educational answer grounded in retrieved evidence."""

    summary: str
    bullets: list[EvidenceBullet] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    safety_note: str


class EvidenceCoverageItem(BaseModel):
    """Deterministic coverage status for one extracted state item."""

    category: str
    label: str
    status: EvidenceCoverageStatus
    reason: str
    matched_evidence: str | None = None


class EvidenceCoverageReport(BaseModel):
    """Coverage checklist for the retrieved evidence behind an answer."""

    items: list[EvidenceCoverageItem] = Field(default_factory=list)
    summary_counts: dict[str, int] = Field(default_factory=dict)


class QueryAnswerResponse(BaseModel):
    """Natural-language query understanding plus optional answer synthesis."""

    understanding: QueryUnderstandingResponse
    answer: EvidenceAnswer | None = None
    coverage: EvidenceCoverageReport = Field(default_factory=EvidenceCoverageReport)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
