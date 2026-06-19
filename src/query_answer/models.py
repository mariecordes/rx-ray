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


ClaimSupportStatus = Literal["strong", "partial", "limited", "none"]


class EvidenceBullet(BaseModel):
    """A grounded answer bullet and its supporting citations."""

    text: str
    citations: list[EvidenceCitation] = Field(default_factory=list)
    support_status: ClaimSupportStatus | None = None


class EvidenceAnswer(BaseModel):
    """LLM-generated educational answer grounded in retrieved evidence."""

    response: str = ""
    evidence_summary: str = ""
    summary: str = ""
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


AnswerContractKind = Literal["must_mention", "must_caveat"]


class AnswerContractItem(BaseModel):
    """One deterministic obligation synthesis must satisfy before generation."""

    kind: AnswerContractKind
    topic: str
    intent: str | None = None
    statement: str
    evidence_available: bool
    required_sections: list[str] = Field(default_factory=list)
    coverage_category: str | None = None
    coverage_label: str | None = None
    target_rxcui: str | None = None


AnswerCoverageLevel = Literal["direct", "partial", "limited", "none"]


class AnswerContract(BaseModel):
    """Deterministic must-mention/must-caveat checklist fed into synthesis."""

    items: list[AnswerContractItem] = Field(default_factory=list)
    coverage_level: AnswerCoverageLevel = "none"


ValidationSeverity = Literal["info", "warning"]


class ValidationFinding(BaseModel):
    """A post-generation validation observation about the synthesized answer."""

    kind: str
    severity: ValidationSeverity
    message: str
    topic: str | None = None


class AnswerValidationReport(BaseModel):
    """Outcome of enforcing the answer contract against the generated answer."""

    findings: list[ValidationFinding] = Field(default_factory=list)
    enforced_caveats: list[str] = Field(default_factory=list)
    passed: bool = True


class ClaimCritique(BaseModel):
    """Per-claim support assessment for one generated bullet (Guardrails V3)."""

    bullet_index: int
    support_status: ClaimSupportStatus
    rationale: str = ""
    issues: list[str] = Field(default_factory=list)


CritiqueSource = Literal["llm", "deterministic"]


class AnswerCritique(BaseModel):
    """Outcome of the optional post-generation critic pass (Guardrails V3).

    The deterministic classifier always runs as a floor so every bullet has a
    support_status even when the LLM critic is disabled; the critic, when
    enabled, may override those statuses but never the other way around.
    """

    enabled: bool = False
    source: CritiqueSource = "deterministic"
    claims: list[ClaimCritique] = Field(default_factory=list)
    global_findings: list[ValidationFinding] = Field(default_factory=list)
    regenerated: bool = False
    notes: list[str] = Field(default_factory=list)


class RxNormPairContext(BaseModel):
    """Terminology-only context between primary and secondary RxNorm concepts."""

    primary_rxcui: str
    secondary_rxcui: str
    status: str
    summary: str
    direct_edges: list[RxNormEdge] = Field(default_factory=list)
    shared_neighbors: list[RxNormConcept] = Field(default_factory=list)


class RxNormNetworkCenter(BaseModel):
    """A resolved drug that anchors one cluster of the question network."""

    rxcui: str
    name: str
    tty: str | None = None
    role: str


class QuestionRxNormNetwork(BaseModel):
    """Combined RxNorm terminology network across all resolved drugs.

    Terminology only: a shared node or edge is RxNorm vocabulary overlap, never a
    clinical interaction claim. ``node_membership`` maps each node RXCUI to the
    center RXCUIs whose neighborhood contains it; ``shared_rxcuis`` are the nodes
    reachable from more than one center.
    """

    centers: list[RxNormNetworkCenter] = Field(default_factory=list)
    nodes: list[RxNormConcept] = Field(default_factory=list)
    edges: list[RxNormEdge] = Field(default_factory=list)
    node_membership: dict[str, list[str]] = Field(default_factory=dict)
    shared_rxcuis: list[str] = Field(default_factory=list)
    truncated: bool = False


class QuestionEvidenceMapNode(BaseModel):
    """A node in the question-level evidence map."""

    id: str
    kind: str
    label: str
    subtitle: str | None = None
    role: str | None = None
    rxcui: str | None = None
    label_rxcuis: list[str] = Field(default_factory=list)
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
    interaction_terms: list[str] = Field(default_factory=list)
    context_terms: list[str] = Field(default_factory=list)
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


class ContextTargetedEvidence(BaseModel):
    """Label evidence retrieved because a non-drug query context was mentioned."""

    target_label: str
    target_category: str
    resolved_concept: RxNormConcept
    searched_fields: list[str] = Field(default_factory=list)
    label_evidence: OpenFDALabelEvidence | None = None
    retrieval_modes: list[str] = Field(default_factory=list)


class QueryAnswerResponse(BaseModel):
    """Natural-language query understanding plus optional answer synthesis."""

    understanding: QueryUnderstandingResponse
    answer: EvidenceAnswer | None = None
    secondary_evidence: list[SecondaryDrugEvidence] = Field(default_factory=list)
    context_evidence: list[ContextTargetedEvidence] = Field(default_factory=list)
    question_rxnorm_network: QuestionRxNormNetwork = Field(
        default_factory=QuestionRxNormNetwork
    )
    question_evidence_map: QuestionEvidenceMap = Field(
        default_factory=QuestionEvidenceMap
    )
    coverage: EvidenceCoverageReport = Field(default_factory=EvidenceCoverageReport)
    contract: AnswerContract = Field(default_factory=AnswerContract)
    validation: AnswerValidationReport = Field(default_factory=AnswerValidationReport)
    critique: AnswerCritique = Field(default_factory=AnswerCritique)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
