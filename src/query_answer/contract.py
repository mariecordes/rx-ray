from __future__ import annotations

from src.query_answer.coverage import (
    INGREDIENT_FALLBACK_LIMITATION,
    INTENT_REQUIRED_SECTIONS,
    INTENT_TOPIC_LABELS,
    SPECIFICITY_LIMITATION,
    format_human_list,
    has_primary_label_text,
    primary_label_sections,
    secondary_drug_limitation,
    specificity_differs,
)
from src.query_answer.models import (
    AnswerContract,
    AnswerContractItem,
    AnswerCoverageLevel,
    EvidenceCoverageReport,
)
from src.query_understanding.models import QueryUnderstandingResponse

INTERACTION_TERMINOLOGY_CAVEAT = (
    "RxNorm terminology overlap is not evidence of a clinical interaction."
)


def build_answer_contract(
    understanding: QueryUnderstandingResponse,
    coverage: EvidenceCoverageReport,
) -> AnswerContract:
    """Build the deterministic must-mention/must-caveat contract for synthesis."""

    items: list[AnswerContractItem] = []
    intent_items_by_label = {
        item.label: item for item in coverage.items if item.category == "intent"
    }

    for intent, item in intent_items_by_label.items():
        topic = INTENT_TOPIC_LABELS.get(intent)
        if topic is None and intent == "interaction_check":
            topic = "drug interaction"
        if topic is None:
            continue
        if intent == "interaction_check":
            required_sections = ["drug_interactions"]
        elif item.matched_sections:
            required_sections = list(item.matched_sections)
        else:
            required_sections = list(INTENT_REQUIRED_SECTIONS.get(intent, ()))
        if item.status == "addressed":
            items.append(
                AnswerContractItem(
                    kind="must_mention",
                    topic=intent,
                    intent=intent,
                    statement=f"Address what the retrieved {topic} label sections say.",
                    evidence_available=True,
                    required_sections=required_sections,
                    coverage_category="intent",
                    coverage_label=intent,
                )
            )
        elif item.status == "not_found_in_evidence":
            items.append(
                AnswerContractItem(
                    kind="must_caveat",
                    topic=intent,
                    intent=intent,
                    statement=(
                        f"The retrieved labels did not include {topic} information; "
                        "this question is not answerable from retrieved evidence."
                    ),
                    evidence_available=False,
                    required_sections=required_sections,
                    coverage_category="intent",
                    coverage_label=intent,
                )
            )

    if "interaction_check" in intent_items_by_label:
        items.append(
            AnswerContractItem(
                kind="must_caveat",
                topic="interaction_terminology",
                intent="interaction_check",
                statement=INTERACTION_TERMINOLOGY_CAVEAT,
                evidence_available=True,
                coverage_category="intent",
                coverage_label="interaction_check",
            )
        )

    dossier = understanding.primary_dossier
    if dossier and dossier.label_evidence_scope == "ingredient_fallback":
        ingredient_names = [
            entry.ingredient.name for entry in dossier.ingredient_fallback
        ]
        concept_name = dossier.resolved_drug.name if dossier.resolved_drug else None
        if concept_name and ingredient_names:
            statement = (
                f"No product-specific labels were found for {concept_name}; the "
                "retrieved evidence describes its active ingredient"
                f"{'s' if len(ingredient_names) != 1 else ''} "
                f"({format_human_list(ingredient_names)}) and may cover other "
                "formulations."
            )
        else:
            statement = INGREDIENT_FALLBACK_LIMITATION
        items.append(
            AnswerContractItem(
                kind="must_caveat",
                topic="ingredient_fallback",
                statement=statement,
                evidence_available=True,
            )
        )

    primary = understanding.state.primary_drug
    resolved = dossier.resolved_drug.name if dossier and dossier.resolved_drug else None
    if primary and resolved and specificity_differs(primary, resolved):
        items.append(
            AnswerContractItem(
                kind="must_caveat",
                topic="specificity",
                statement=f"{SPECIFICITY_LIMITATION} ({primary} -> {resolved})",
                evidence_available=True,
            )
        )

    non_primary_drugs = [
        coverage_item.label
        for coverage_item in coverage.items
        if coverage_item.category == "mentioned_drug"
        and coverage_item.status == "not_retrieved"
    ]
    if non_primary_drugs:
        items.append(
            AnswerContractItem(
                kind="must_caveat",
                topic="secondary_not_retrieved",
                statement=secondary_drug_limitation(non_primary_drugs),
                evidence_available=False,
                coverage_category="mentioned_drug",
            )
        )

    missing_context = [
        coverage_item.label
        for coverage_item in coverage.items
        if coverage_item.category
        in {"current_medication", "allergy", "condition", "patient_context"}
        and coverage_item.status in {"not_found_in_evidence", "not_retrieved"}
    ]
    if missing_context:
        items.append(
            AnswerContractItem(
                kind="must_caveat",
                topic="missing_context",
                statement=(
                    "The retrieved labels did not explicitly mention "
                    f"{format_human_list(missing_context[:5])}."
                ),
                evidence_available=False,
            )
        )

    sections = primary_label_sections(understanding)
    coverage_level = _coverage_level(items, has_primary_label_text(sections))
    return AnswerContract(items=items, coverage_level=coverage_level)


def required_label_sections(contract: AnswerContract) -> set[str]:
    """All label sections required by intents the contract marked addressed.

    Used both by the deterministic support-status floor (critic.py) and by
    evidence-packet construction (synthesizer.py) to make sure a section the
    contract is relying on isn't silently truncated out of what the LLM
    actually sees.
    """

    sections: set[str] = set()
    for item in contract.items:
        if (
            item.coverage_category == "intent"
            and item.evidence_available
            and item.required_sections
        ):
            sections.update(item.required_sections)
    return sections


def _coverage_level(
    items: list[AnswerContractItem],
    has_label_text: bool,
) -> AnswerCoverageLevel:
    if not has_label_text:
        return "none"

    # Per-intent obligations have topic == intent; excludes derived caveats
    # (e.g. interaction_terminology) that don't reflect actual coverage.
    # label_context_check is excluded too: it's near-universally "addressed"
    # whenever any label text exists, so it would mask real gaps.
    intent_items = [
        item
        for item in items
        if item.coverage_category == "intent"
        and item.topic == item.intent
        and item.intent != "label_context_check"
    ]
    if not intent_items:
        return "limited"
    if all(item.evidence_available for item in intent_items):
        return "direct"
    if any(item.evidence_available for item in intent_items):
        return "partial"
    return "limited"
