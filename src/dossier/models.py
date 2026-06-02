from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class RxNormConcept(BaseModel):
    """A resolved RxNorm concept."""

    rxcui: str
    name: str
    tty: str | None = None
    sab: str | None = None


class ResolutionCandidate(BaseModel):
    """A ranked candidate for a user-supplied drug string."""

    concept: RxNormConcept
    match_type: str
    score: float


class RxNormEdge(BaseModel):
    """A typed RxNorm relationship between two concepts."""

    source_rxcui: str
    source_name: str
    source_tty: str | None = None
    target_rxcui: str
    target_name: str
    target_tty: str | None = None
    relation: str
    source: str = "rxnorm"


class RxNormNeighborhood(BaseModel):
    """The local symbolic graph around the resolved drug."""

    nodes: list[RxNormConcept] = Field(default_factory=list)
    edges: list[RxNormEdge] = Field(default_factory=list)
    depth: int = 1
    truncated: bool = False


class LabelSection(BaseModel):
    """A normalized OpenFDA label section with provenance."""

    section: str
    text: str
    source_id: str | None = None
    effective_time: str | None = None
    source: str = "openfda"


class OpenFDALabelRecord(BaseModel):
    """Document-level OpenFDA label metadata used for provenance."""

    source_id: str | None = None
    id: str | None = None
    set_id: str | None = None
    spl_ids: list[str] = Field(default_factory=list)
    spl_set_ids: list[str] = Field(default_factory=list)
    effective_time: str | None = None
    version: str | None = None
    brand_names: list[str] = Field(default_factory=list)
    generic_names: list[str] = Field(default_factory=list)
    manufacturer_names: list[str] = Field(default_factory=list)
    product_ndcs: list[str] = Field(default_factory=list)
    product_types: list[str] = Field(default_factory=list)
    routes: list[str] = Field(default_factory=list)
    substance_names: list[str] = Field(default_factory=list)
    rxcuis: list[str] = Field(default_factory=list)


class OpenFDALabelEvidence(BaseModel):
    """OpenFDA label text organized into sections useful for the app/LLM."""

    rxcui: str
    labels_found: int = 0
    label_limit: int | None = None
    retrieval_mode: str = "none"
    label_records: list[OpenFDALabelRecord] = Field(default_factory=list)
    summary_metadata: dict[str, Any] = Field(default_factory=dict)
    sections: dict[str, list[LabelSection]] = Field(default_factory=dict)
    section_flags: dict[str, bool] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class DrugDossier(BaseModel):
    """Request-time evidence bundle for one user drug query."""

    query: str
    generated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    resolved_drug: RxNormConcept | None = None
    resolution_candidates: list[ResolutionCandidate] = Field(default_factory=list)
    rxnorm_neighborhood: RxNormNeighborhood = Field(default_factory=RxNormNeighborhood)
    label_evidence: OpenFDALabelEvidence | None = None
    notes: list[str] = Field(default_factory=list)

    def to_jsonable(self) -> dict[str, Any]:
        """Return a plain JSON-ready representation."""

        return self.model_dump(mode="json")
