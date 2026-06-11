from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.dossier.models import (
    DrugDossier,
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
    all_drugs_mentioned: list[str] = Field(default_factory=list)
    current_medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    patient_context: list[str] = Field(default_factory=list)
    intent: str | None = None
    intents: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def sync_intent_fields(self) -> "QueryState":
        """Keep legacy single-intent and new multi-intent fields in sync."""

        if self.intent and self.intent not in self.intents:
            self.intents = [self.intent, *self.intents]
        if self.intents and not self.intent:
            self.intent = self.intents[0]
        return self


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


class QueryUnderstandingResponse(BaseModel):
    """Structured query understanding output for frontend inspection."""

    query: str
    extraction_mode: Literal["deterministic", "llm", "hybrid"] = "deterministic"
    state: QueryState = Field(default_factory=QueryState)
    resolved_drugs: list[ResolvedDrugMention] = Field(default_factory=list)
    primary_dossier: DrugDossier | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
