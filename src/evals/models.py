from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EvalMode = Literal["combined", "symbolic", "neural"]


class CoverageAssertion(BaseModel):
    """One expected entry in the deterministic coverage report.

    Category vocabulary matches EvidenceCoverageItem.category: primary_drug,
    mentioned_drug, current_medication, allergy, condition, patient_context,
    intent. ``label`` is matched with normalized substring containment.
    """

    category: str
    label: str
    status_in: list[str] = Field(default_factory=list)


class EvalExpectation(BaseModel):
    """Behavioral expectations for one question — structured facts only,
    never golden answer text, so checks are robust to LLM nondeterminism."""

    drugs: list[str] = Field(default_factory=list)
    current_medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    patient_context: list[str] = Field(default_factory=list)
    intents: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    coverage: list[CoverageAssertion] = Field(default_factory=list)
    must_have_limitation_mentioning: list[str] = Field(default_factory=list)
    forbid_yes_no_framing: bool = True


class EvalQuestion(BaseModel):
    id: str
    question: str
    category: str
    notes: str | None = None
    expected: EvalExpectation = Field(default_factory=EvalExpectation)


class BehaviorCheck(BaseModel):
    """One pass/fail behavioral assertion with a human-readable detail."""

    name: str
    passed: bool
    detail: str = ""


class FieldScore(BaseModel):
    """Precision/recall/F1 for one extracted-state field vs expectations."""

    expected: int
    matched: int
    extracted: int
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None


class QuestionResult(BaseModel):
    """Everything measured for one question in one repeat."""

    question_id: str
    category: str
    mode: EvalMode
    repeat: int = 0
    elapsed_s: float = 0.0
    checks: list[BehaviorCheck] = Field(default_factory=list)
    field_scores: dict[str, FieldScore] = Field(default_factory=dict)
    coverage_status_counts: dict[str, int] = Field(default_factory=dict)
    validation_finding_kinds: list[str] = Field(default_factory=list)
    enforced_caveat_count: int = 0
    critic_status_counts: dict[str, int] = Field(default_factory=dict)
    critic_regenerated: bool = False
    answer_generated: bool = False
    bullet_count: int = 0
    citation_count: int = 0
    limitation_count: int = 0
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.error is None and all(check.passed for check in self.checks)


class EvalRunResult(BaseModel):
    """A full harness run: all questions, all repeats, one mode."""

    mode: EvalMode
    questions_file: str
    repeats: int
    started_at: str
    results: list[QuestionResult] = Field(default_factory=list)


def load_questions(raw: dict) -> list[EvalQuestion]:
    return [EvalQuestion(**item) for item in raw.get("questions", [])]


__all__ = [
    "BehaviorCheck",
    "CoverageAssertion",
    "EvalExpectation",
    "EvalMode",
    "EvalQuestion",
    "EvalRunResult",
    "FieldScore",
    "QuestionResult",
    "load_questions",
]
