from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.dossier.models import OpenFDALabelEvidence, RxNormConcept, RxNormEdge
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
    source_id: str | None = None
    section: str | None = None
    target_rxcui: str | None = None


class EvidenceCoverageReport(BaseModel):
    """Coverage checklist for the retrieved evidence behind an answer."""

    items: list[EvidenceCoverageItem] = Field(default_factory=list)
    summary_counts: dict[str, int] = Field(default_factory=dict)


class RxNormPairContext(BaseModel):
    """Terminology-only context between primary and secondary RxNorm concepts."""

    primary_rxcui: str
    secondary_rxcui: str
    status: str
    summary: str
    direct_edges: list[RxNormEdge] = Field(default_factory=list)
    shared_neighbors: list[RxNormConcept] = Field(default_factory=list)


class QuestionEvidenceMapNode(BaseModel):
    """A node in the question-level evidence map."""

    id: str
    kind: str
    label: str
    subtitle: str | None = None
    role: str | None = None
    rxcui: str | None = None
    source_id: str | None = None
    section: str | None = None
    evidence_scope: str | None = None
    tags: list[str] = Field(default_factory=list)


class QuestionEvidenceMapEdge(BaseModel):
    """A careful provenance edge in the question-level evidence map."""

    id: str
    source: str
    target: str
    kind: str
    label: str
    rxcui: str | None = None
    source_id: str | None = None
    section: str | None = None
    evidence_scope: str | None = None
    tags: list[str] = Field(default_factory=list)


class QuestionEvidenceMap(BaseModel):
    """Request-time map connecting extracted state to retrieved evidence."""

    nodes: list[QuestionEvidenceMapNode] = Field(default_factory=list)
    edges: list[QuestionEvidenceMapEdge] = Field(default_factory=list)
    summary_counts: dict[str, int] = Field(default_factory=dict)


class SecondaryDrugEvidence(BaseModel):
    """Compact evidence bundle for a non-primary resolved medication."""

    mention_text: str
    role: str
    resolved_concept: RxNormConcept
    label_evidence: OpenFDALabelEvidence | None = None
    interaction_label_evidence: OpenFDALabelEvidence | None = None
    retrieval_modes: list[str] = Field(default_factory=list)
    rxnorm_context: RxNormPairContext | None = None


class QueryAnswerResponse(BaseModel):
    """Natural-language query understanding plus optional answer synthesis."""

    understanding: QueryUnderstandingResponse
    answer: EvidenceAnswer | None = None
    secondary_evidence: list[SecondaryDrugEvidence] = Field(default_factory=list)
    question_evidence_map: QuestionEvidenceMap = Field(
        default_factory=QuestionEvidenceMap
    )
    coverage: EvidenceCoverageReport = Field(default_factory=EvidenceCoverageReport)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
