from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.dossier.models import (
    DrugDossier,
    OpenFDALabelEvidence,
    ResolutionCandidate,
    RxNormConcept,
)

DrugMentionRole = Literal[
    "primary_drug",
    "current_medication",
    "allergy",
    "mentioned_drug",
]


class QueryState(BaseModel):
    """Inspectable symbolic state extracted from a user question."""

    primary_drug: str | None = None
    current_medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    patient_context: list[str] = Field(default_factory=list)
    intent: str | None = None


class ExtractedDrugMention(BaseModel):
    """A drug-like text span and its role before RxNorm resolution."""

    text: str
    role: DrugMentionRole


class ResolvedDrugMention(BaseModel):
    """A drug-like query mention resolved against RxNorm."""

    text: str
    role: DrugMentionRole
    candidates: list[ResolutionCandidate] = Field(default_factory=list)
    selected_concept: RxNormConcept | None = None


class SecondaryLabelEvidence(BaseModel):
    """Compact label evidence preview for non-primary resolved drugs."""

    mention: str
    role: DrugMentionRole
    resolved_concept: RxNormConcept | None = None
    label_evidence: OpenFDALabelEvidence | None = None


class QueryUnderstandingResponse(BaseModel):
    """Structured query understanding output for frontend inspection."""

    query: str
    extraction_mode: Literal["deterministic", "llm", "hybrid"] = "deterministic"
    state: QueryState = Field(default_factory=QueryState)
    resolved_drugs: list[ResolvedDrugMention] = Field(default_factory=list)
    primary_dossier: DrugDossier | None = None
    secondary_label_evidence: list[SecondaryLabelEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

