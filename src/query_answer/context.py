from __future__ import annotations

from dataclasses import dataclass

from src.dossier.builder import DossierBuilder
from src.dossier.models import DrugDossier, OpenFDALabelEvidence, RxNormConcept
from src.query_answer.config import QueryAnswerParameters
from src.query_answer.models import ContextTargetedEvidence, SecondaryDrugEvidence
from src.query_answer.secondary import (
    merge_label_evidence,
    merge_tags,
    tag_label_evidence,
)
from src.query_understanding.models import QueryState, QueryUnderstandingResponse


CONTEXT_TARGETED_TAG = "context_targeted_lookup"

CONDITION_FIELDS = (
    "indications_and_usage",
    "warnings",
    "contraindications",
    "adverse_reactions",
)
ALLERGY_FIELDS = (
    "contraindications",
    "warnings",
    "active_ingredient",
    "inactive_ingredient",
)
PATIENT_CONTEXT_FIELDS = {
    "pregnant": (
        "pregnancy",
        "pregnancy_or_breast_feeding",
        "use_in_specific_populations",
    ),
    "pregnancy": (
        "pregnancy",
        "pregnancy_or_breast_feeding",
        "use_in_specific_populations",
    ),
    "breastfeeding": ("lactation", "pregnancy_or_breast_feeding"),
    "lactation": ("lactation", "pregnancy_or_breast_feeding"),
    "nursing": ("lactation", "pregnancy_or_breast_feeding"),
    "child": ("pediatric_use", "use_in_specific_populations"),
    "children": ("pediatric_use", "use_in_specific_populations"),
    "pediatric": ("pediatric_use", "use_in_specific_populations"),
    "elderly": ("geriatric_use", "use_in_specific_populations"),
    "geriatric": ("geriatric_use", "use_in_specific_populations"),
}
DEFAULT_PATIENT_CONTEXT_FIELDS = ("use_in_specific_populations", "warnings")


@dataclass(frozen=True)
class ContextTarget:
    label: str
    category: str
    fields: tuple[str, ...]
    search_label: str


def build_context_targeted_evidence(
    understanding: QueryUnderstandingResponse,
    secondary_evidence: list[SecondaryDrugEvidence],
    builder: DossierBuilder,
    parameters: QueryAnswerParameters,
) -> list[ContextTargetedEvidence]:
    if (
        not parameters.context_lookup_enabled
        or parameters.context_lookup_limit <= 0
        or parameters.max_context_targets <= 0
    ):
        return []

    concepts = evidence_concepts(understanding, secondary_evidence)
    if not concepts:
        return []

    targets = select_context_targets(
        understanding.state,
        concepts,
        max_items=parameters.max_context_targets,
    )
    results: list[ContextTargetedEvidence] = []
    for target in targets:
        for concept in concepts:
            evidence = builder.openfda_store.get_context_label_evidence(
                concept.rxcui,
                target=target.search_label,
                section_fields=list(target.fields),
                fallback_name=concept.name,
                limit=parameters.context_lookup_limit,
            )
            evidence = tag_label_evidence(evidence, CONTEXT_TARGETED_TAG)
            if not evidence.labels_found:
                continue
            results.append(
                ContextTargetedEvidence(
                    target_label=target.label,
                    target_category=target.category,
                    resolved_concept=concept,
                    searched_fields=list(target.fields),
                    label_evidence=evidence,
                    retrieval_modes=["context_targeted_lookup"],
                )
            )
    return results


def evidence_concepts(
    understanding: QueryUnderstandingResponse,
    secondary_evidence: list[SecondaryDrugEvidence],
) -> list[RxNormConcept]:
    concepts: list[RxNormConcept] = []
    seen: set[str] = set()
    primary = (
        understanding.primary_dossier.resolved_drug
        if understanding.primary_dossier and understanding.primary_dossier.resolved_drug
        else None
    )
    if primary:
        append_concept(concepts, seen, primary)
    for item in secondary_evidence:
        append_concept(concepts, seen, item.resolved_concept)
    return concepts


def append_concept(
    concepts: list[RxNormConcept],
    seen: set[str],
    concept: RxNormConcept,
) -> None:
    if concept.rxcui in seen:
        return
    seen.add(concept.rxcui)
    concepts.append(concept)


def select_context_targets(
    state: QueryState,
    concepts: list[RxNormConcept],
    *,
    max_items: int,
) -> list[ContextTarget]:
    medication_keys = {
        normalized
        for value in [
            state.primary_drug,
            *state.all_drugs_mentioned,
            *state.current_medications,
            *(concept.name for concept in concepts),
        ]
        if value and (normalized := normalize_context_key(value))
    }
    selected: list[ContextTarget] = []
    seen: set[str] = set()

    for category, values, fields_for_value in [
        ("patient_context", state.patient_context, patient_context_fields),
        ("allergy", state.allergies, lambda _value: ALLERGY_FIELDS),
        ("condition", state.conditions, lambda _value: CONDITION_FIELDS),
    ]:
        for value in values:
            label = clean_context_label(value)
            key = normalize_context_key(label)
            if (
                not label
                or len(key) <= 1
                or key in seen
                or key in medication_keys
            ):
                continue
            seen.add(key)
            selected.append(
                ContextTarget(
                    label=label,
                    category=category,
                    fields=tuple(fields_for_value(label)),
                    search_label=context_search_label(category, label),
                )
            )
            if len(selected) >= max_items:
                return selected
    return selected


def patient_context_fields(value: str) -> tuple[str, ...]:
    return PATIENT_CONTEXT_FIELDS.get(
        normalize_context_key(value),
        DEFAULT_PATIENT_CONTEXT_FIELDS,
    )


def clean_context_label(value: str) -> str:
    return " ".join(value.strip().split())


def context_search_label(category: str, label: str) -> str:
    if category == "allergy":
        normalized = normalize_context_key(label)
        if "allergy" not in normalized:
            return f"{label} allergy"
    return label


def normalize_context_key(value: str) -> str:
    return " ".join(value.casefold().replace("-", " ").split())


def merge_context_evidence_into_understanding(
    understanding: QueryUnderstandingResponse,
    context_evidence: list[ContextTargetedEvidence],
) -> QueryUnderstandingResponse:
    dossier = understanding.primary_dossier
    if not dossier or not dossier.resolved_drug:
        return understanding
    context_items = [
        item
        for item in context_evidence
        if item.resolved_concept.rxcui == dossier.resolved_drug.rxcui
    ]
    if not context_items:
        return understanding

    updated_dossier = merge_context_evidence_into_dossier(dossier, context_items)
    return understanding.model_copy(update={"primary_dossier": updated_dossier})


def merge_context_evidence_into_dossier(
    dossier: DrugDossier,
    context_items: list[ContextTargetedEvidence],
) -> DrugDossier:
    if not dossier.resolved_drug or not dossier.label_evidence:
        return dossier
    merged = merge_label_evidence(
        dossier.resolved_drug.rxcui,
        [
            dossier.label_evidence,
            *[
                item.label_evidence
                for item in context_items
                if item.label_evidence is not None
            ],
        ],
        retrieval_mode=combined_context_mode(
            dossier.label_evidence,
            context_items,
        ),
        label_limit=dossier.label_evidence.label_limit,
    )
    return dossier.model_copy(update={"label_evidence": merged})


def merge_context_evidence_into_secondary(
    secondary_evidence: list[SecondaryDrugEvidence],
    context_evidence: list[ContextTargetedEvidence],
) -> list[SecondaryDrugEvidence]:
    updated: list[SecondaryDrugEvidence] = []
    for item in secondary_evidence:
        context_items = [
            context
            for context in context_evidence
            if context.resolved_concept.rxcui == item.resolved_concept.rxcui
        ]
        if not context_items or not item.label_evidence:
            updated.append(item)
            continue
        merged = merge_label_evidence(
            item.resolved_concept.rxcui,
            [
                item.label_evidence,
                *[
                    context.label_evidence
                    for context in context_items
                    if context.label_evidence is not None
                ],
            ],
            retrieval_mode=combined_context_mode(item.label_evidence, context_items),
            label_limit=item.label_evidence.label_limit,
        )
        updated.append(
            item.model_copy(
                update={
                    "label_evidence": merged,
                    "retrieval_modes": merge_tags(
                        item.retrieval_modes,
                        ["context_targeted_lookup"],
                    ),
                }
            )
        )
    return updated


def combined_context_mode(
    base: OpenFDALabelEvidence,
    context_items: list[ContextTargetedEvidence],
) -> str:
    modes = [base.retrieval_mode] if base.retrieval_mode != "none" else []
    if any(
        item.label_evidence and item.label_evidence.labels_found
        for item in context_items
    ):
        modes.append("context_targeted_lookup")
    return "+".join(merge_tags([], modes)) or "none"
