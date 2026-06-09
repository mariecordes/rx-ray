from __future__ import annotations

from pydantic import BaseModel, Field

from src.query_understanding.models import QueryUnderstandingResponse


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


class QueryAnswerResponse(BaseModel):
    """Natural-language query understanding plus optional answer synthesis."""

    understanding: QueryUnderstandingResponse
    answer: EvidenceAnswer | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
