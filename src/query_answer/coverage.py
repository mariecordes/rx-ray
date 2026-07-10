from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from src.dossier.models import LabelSection
from src.query_answer.models import (
    ContextTargetedEvidence,
    EvidenceCoverageItem,
    EvidenceCoverageReport,
    EvidenceCoverageStatus,
    SecondaryDrugEvidence,
)
from src.query_understanding.models import QueryUnderstandingResponse

SPECIFICITY_LIMITATION = (
    "The user query may be more specific than the resolved medication concept used "
    "for retrieval."
)
INGREDIENT_FALLBACK_LIMITATION = (
    "No product-specific labels were found for the resolved medication, so the "
    "retrieved evidence describes its active ingredient(s) and may cover other "
    "formulations."
)
SECONDARY_MATCH_SECTION_PRIORITY = (
    "drug_interactions",
    "boxed_warning",
    "contraindications",
    "warnings",
    "pregnancy",
    "lactation",
    "pregnancy_or_breast_feeding",
    "indications_and_usage",
    "adverse_reactions",
    "use_in_specific_populations",
)
INTENT_REQUIRED_SECTIONS: dict[str, tuple[str, ...]] = {
    "patient_context_check": (
        "pregnancy",
        "lactation",
        "pregnancy_or_breast_feeding",
        "use_in_specific_populations",
    ),
    "allergy_context_check": (
        "contraindications",
        "warnings",
        "warnings_and_precautions",
    ),
    "side_effect_check": ("adverse_reactions", "warnings"),
    "indication_check": ("indications_and_usage",),
}
INTENT_TOPIC_LABELS: dict[str, str] = {
    "patient_context_check": "pregnancy/lactation",
    "allergy_context_check": "allergy",
    "side_effect_check": "side effect",
    "indication_check": "indication",
    "label_context_check": "label availability",
}


def primary_label_sections(
    understanding: QueryUnderstandingResponse,
) -> dict[str, list[LabelSection]]:
    dossier = understanding.primary_dossier
    return dossier.label_evidence.sections if dossier and dossier.label_evidence else {}


def has_primary_label_text(sections: dict[str, list[LabelSection]]) -> bool:
    evidence_text = "\n".join(
        section.text for entries in sections.values() for section in entries
    )
    return bool(evidence_text.strip())


def build_evidence_coverage(
    understanding: QueryUnderstandingResponse,
    secondary_evidence: list[SecondaryDrugEvidence] | None = None,
    context_evidence: list[ContextTargetedEvidence] | None = None,
) -> EvidenceCoverageReport:
    """Build deterministic coverage metadata from extracted state and evidence."""

    secondary_evidence = secondary_evidence or []
    context_evidence = context_evidence or []
    secondary_by_name = {
        normalize(item.resolved_concept.name): item for item in secondary_evidence
    }
    secondary_by_mention = {
        normalize(item.mention_text): item for item in secondary_evidence
    }
    dossier = understanding.primary_dossier
    sections = primary_label_sections(understanding)
    has_label_text = has_primary_label_text(sections)
    primary_name = (
        dossier.resolved_drug.name
        if dossier and dossier.resolved_drug
        else None
    )
    is_ingredient_fallback = bool(
        dossier and dossier.label_evidence_scope == "ingredient_fallback"
    )
    ingredient_fallback_names = [
        item.ingredient.name
        for item in (dossier.ingredient_fallback if dossier else [])
    ]
    items: list[EvidenceCoverageItem] = []

    # Query understanding can fall back to building the dossier around a
    # *different* mentioned drug when the stated primary drug itself never
    # resolves (see QueryUnderstandingService._select_primary). Detect that
    # by RXCUI identity, not by comparing name strings — a normal resolution
    # commonly renames "tretinoin cream" to "tretinoin 1 MG/ML Topical
    # Cream", which is the same concept, not a fallback substitution.
    primary_drug_mention = next(
        (
            mention
            for mention in understanding.resolved_drugs
            if mention.role == "primary_drug"
        ),
        None,
    )
    if primary_drug_mention is None:
        # resolved_drugs wasn't populated (e.g. a QueryUnderstandingResponse
        # built directly rather than via the service) — there's no positive
        # evidence of a fallback substitution, so trust primary_dossier as
        # the direct resolution rather than assuming one happened.
        primary_drug_resolved_directly = True
    else:
        primary_drug_resolved_directly = bool(
            primary_drug_mention.selected_concept
            and dossier
            and dossier.resolved_drug
            and primary_drug_mention.selected_concept.rxcui
            == dossier.resolved_drug.rxcui
        )

    def resolved_dossier_item(category: str, label: str) -> EvidenceCoverageItem:
        assert primary_name is not None
        return EvidenceCoverageItem(
            category=category,
            label=label,
            status="addressed" if has_label_text else "not_found_in_evidence",
            reason=(
                primary_addressed_reason(
                    primary_name,
                    is_ingredient_fallback,
                    ingredient_fallback_names,
                )
                if has_label_text
                else f"Resolved to {primary_name}, but no label text was retrieved."
            ),
            target_rxcui=(
                dossier.resolved_drug.rxcui
                if dossier and dossier.resolved_drug
                else None
            ),
        )

    if understanding.state.primary_drug:
        if primary_name and primary_drug_resolved_directly:
            items.append(
                resolved_dossier_item("primary_drug", understanding.state.primary_drug)
            )
        elif primary_name:
            # The stated primary drug itself didn't resolve, but query
            # understanding fell back to a different mentioned drug's
            # dossier. Report both honestly instead of crediting the
            # fallback drug's evidence to the drug that was never found.
            items.append(
                EvidenceCoverageItem(
                    category="primary_drug",
                    label=understanding.state.primary_drug,
                    status="not_retrieved",
                    reason=(
                        f"{understanding.state.primary_drug} was not recognized "
                        "as a specific medication, so no evidence specific to "
                        "it was retrieved."
                    ),
                )
            )
            items.append(resolved_dossier_item("mentioned_drug", primary_name))
        else:
            items.append(
                EvidenceCoverageItem(
                    category="primary_drug",
                    label=understanding.state.primary_drug,
                    status="not_retrieved",
                    reason="No primary medication dossier was resolved.",
                )
            )

    for drug in unique_values(understanding.state.all_drugs_mentioned):
        if same_concept(drug, understanding.state.primary_drug) or same_concept(
            drug, primary_name
        ):
            continue
        secondary = find_secondary_evidence(
            drug,
            secondary_by_name,
            secondary_by_mention,
        )
        if secondary and has_secondary_label_text(secondary):
            items.append(
                EvidenceCoverageItem(
                    category="mentioned_drug",
                    label=drug,
                    status="addressed",
                    reason=(
                        "Drug label evidence was retrieved for "
                        f"{secondary.resolved_concept.name}."
                    ),
                    target_rxcui=secondary.resolved_concept.rxcui,
                )
            )
            continue
        items.append(
            EvidenceCoverageItem(
                category="mentioned_drug",
                label=drug,
                status="not_retrieved",
                reason="Drug label evidence was not retrieved.",
            )
        )

    for drug in unique_values(understanding.state.current_medications):
        secondary = find_secondary_evidence(
            drug,
            secondary_by_name,
            secondary_by_mention,
        )
        if secondary and has_secondary_label_text(secondary):
            items.append(
                EvidenceCoverageItem(
                    category="current_medication",
                    label=drug,
                    status="addressed",
                    reason=(
                        "Drug label evidence was retrieved for the current "
                        f"medication {secondary.resolved_concept.name}."
                    ),
                    target_rxcui=secondary.resolved_concept.rxcui,
                )
            )
            continue
        items.append(
            coverage_from_text(
                category="current_medication",
                label=drug,
                sections=sections,
                has_label_text=has_label_text,
                not_found_reason=(
                    "The retrieved labels did not explicitly mention the "
                    f"current medication {drug}."
                ),
            )
        )

    for allergy in unique_values(understanding.state.allergies):
        context_item = coverage_from_context_evidence(
            category="allergy",
            label=allergy,
            context_evidence=context_evidence,
        )
        if context_item:
            items.append(context_item)
            continue
        items.append(
            coverage_from_text(
                category="allergy",
                label=allergy,
                sections=sections,
                has_label_text=has_label_text,
                not_found_reason=(
                    "The retrieved labels did not explicitly mention "
                    f"the allergy {allergy}."
                ),
            )
        )

    for condition in unique_values(understanding.state.conditions):
        context_item = coverage_from_context_evidence(
            category="condition",
            label=condition,
            context_evidence=context_evidence,
        )
        if context_item:
            items.append(context_item)
            continue
        items.append(
            coverage_from_text(
                category="condition",
                label=condition,
                sections=sections,
                has_label_text=has_label_text,
                not_found_reason=(
                    "The retrieved labels did not explicitly mention "
                    f"the condition {condition}."
                ),
            )
        )

    for context in unique_values(understanding.state.patient_context):
        context_item = coverage_from_context_evidence(
            category="patient_context",
            label=context,
            context_evidence=context_evidence,
        )
        if context_item:
            items.append(context_item)
            continue
        items.append(
            patient_context_coverage(
                context,
                sections,
                has_label_text,
            )
        )

    for intent in unique_values(understanding.state.intents):
        intent_result = intent_evidence_status(
            intent,
            sections,
            secondary_evidence,
            understanding,
        )
        items.append(
            EvidenceCoverageItem(
                category="intent",
                label=intent,
                status=intent_result.status,
                reason=intent_coverage_reason(
                    intent, intent_result.status, intent_result.matched_sections
                ),
                matched_evidence=(
                    intent_result.match.snippet if intent_result.match else None
                ),
                source_id=(
                    intent_result.match.source_id if intent_result.match else None
                ),
                section=(
                    intent_result.match.section if intent_result.match else None
                ),
                matched_sections=intent_result.matched_sections,
                target_rxcui=intent_result.target_rxcui,
            )
        )

    counts = Counter(item.status for item in items)
    return EvidenceCoverageReport(
        items=items,
        summary_counts={
            status: counts.get(status, 0) for status in coverage_statuses()
        },
    )


def primary_addressed_reason(
    primary_name: str,
    is_ingredient_fallback: bool,
    ingredient_fallback_names: list[str],
) -> str:
    if is_ingredient_fallback and ingredient_fallback_names:
        return (
            f"No product-specific labels were found for {primary_name}; retrieved "
            "evidence is for its active ingredient"
            f"{'s' if len(ingredient_fallback_names) != 1 else ''} "
            f"({format_human_list(ingredient_fallback_names)})."
        )
    return f"Drug label evidence was retrieved for {primary_name}."


def find_secondary_evidence(
    label: str,
    secondary_by_name: dict[str, SecondaryDrugEvidence],
    secondary_by_mention: dict[str, SecondaryDrugEvidence],
) -> SecondaryDrugEvidence | None:
    key = normalize(label)
    return secondary_by_mention.get(key) or secondary_by_name.get(key)


def has_secondary_label_text(item: SecondaryDrugEvidence) -> bool:
    evidence = item.label_evidence
    if evidence is None:
        return False
    return any(entries for entries in evidence.sections.values())


def has_interaction_evidence(
    primary_sections: dict[str, list[LabelSection]],
    secondary_evidence: list[SecondaryDrugEvidence],
) -> bool:
    if primary_sections.get("drug_interactions"):
        return True
    for item in secondary_evidence:
        evidence = item.label_evidence
        if evidence and evidence.sections.get("drug_interactions"):
            return True
        interaction = item.interaction_label_evidence
        if interaction and interaction.sections.get("drug_interactions"):
            return True
    return False


@dataclass(frozen=True)
class IntentEvidenceResult:
    status: EvidenceCoverageStatus
    matched_sections: list[str]
    match: CoverageEvidenceMatch | None = None
    target_rxcui: str | None = None


def intent_evidence_status(
    intent: str,
    sections: dict[str, list[LabelSection]],
    secondary_evidence: list[SecondaryDrugEvidence],
    understanding: QueryUnderstandingResponse,
) -> IntentEvidenceResult:
    """Deterministically check whether retrieved evidence addresses an intent."""

    dossier = understanding.primary_dossier
    primary_rxcui = (
        dossier.resolved_drug.rxcui if dossier and dossier.resolved_drug else None
    )

    if intent == "interaction_check":
        primary_match = first_section_evidence(sections, "drug_interactions")
        if primary_match:
            return IntentEvidenceResult(
                "addressed", ["drug_interactions"], primary_match, primary_rxcui
            )
        for item in secondary_evidence:
            for evidence in (item.label_evidence, item.interaction_label_evidence):
                if evidence is None:
                    continue
                match = first_section_evidence(evidence.sections, "drug_interactions")
                if match:
                    return IntentEvidenceResult(
                        "addressed",
                        ["drug_interactions"],
                        match,
                        item.resolved_concept.rxcui,
                    )
        return IntentEvidenceResult("not_found_in_evidence", [])

    if intent == "label_context_check":
        if has_primary_label_text(sections):
            label_match = first_nonempty_section_evidence(sections)
            return IntentEvidenceResult(
                "addressed", [], label_match, primary_rxcui
            )
        return IntentEvidenceResult("not_found_in_evidence", [])

    required_sections = INTENT_REQUIRED_SECTIONS.get(intent)
    if required_sections is None:
        return IntentEvidenceResult("out_of_scope", [])

    matched = [name for name in required_sections if sections.get(name)]
    if matched:
        match = first_section_evidence(sections, matched[0])
        return IntentEvidenceResult("addressed", matched, match, primary_rxcui)

    if intent == "allergy_context_check":
        for allergy in understanding.state.allergies:
            allergy_match = find_match_in_sections(allergy, sections)
            if allergy_match:
                return IntentEvidenceResult(
                    "addressed", [], allergy_match, primary_rxcui
                )

    return IntentEvidenceResult("not_found_in_evidence", [])


def intent_coverage_reason(
    intent: str,
    status: EvidenceCoverageStatus,
    matched_sections: list[str],
) -> str:
    if intent == "interaction_check":
        if status == "addressed":
            return (
                "Drug-interactions label text was retrieved for at least "
                "one mentioned medication."
            )
        return (
            "No drug-interactions label text was retrieved for the "
            "mentioned medication pair."
        )

    if intent == "label_context_check":
        if status == "addressed":
            return "Label text was retrieved for the primary medication."
        return "No label text was retrieved for the primary medication."

    topic = INTENT_TOPIC_LABELS.get(intent)
    if topic is None:
        return (
            "Intent is recognized for context, but is not checked against "
            "specific retrieved label sections."
        )
    if status == "addressed":
        return (
            f"Retrieved label sections ({', '.join(matched_sections)}) address "
            f"this {topic} question."
        )
    return f"No retrieved label sections addressed this {topic} question."


def coverage_from_context_evidence(
    *,
    category: str,
    label: str,
    context_evidence: list[ContextTargetedEvidence],
) -> EvidenceCoverageItem | None:
    for item in context_evidence:
        if item.target_category != category or not same_concept(
            item.target_label,
            label,
        ):
            continue
        evidence = item.label_evidence
        if evidence is None or not any(evidence.sections.values()):
            continue
        match = find_match_in_sections(label, evidence.sections)
        if not match:
            continue
        return EvidenceCoverageItem(
            category=category,
            label=label,
            status="addressed",
            reason="The retrieved label text explicitly mentions this item.",
            matched_evidence=match.snippet,
            source_id=match.source_id,
            section=match.section,
            target_rxcui=item.resolved_concept.rxcui,
        )
    return None


def coverage_from_text(
    *,
    category: str,
    label: str,
    sections: dict[str, list[LabelSection]],
    has_label_text: bool,
    not_found_reason: str,
) -> EvidenceCoverageItem:
    if not has_label_text:
        return EvidenceCoverageItem(
            category=category,
            label=label,
            status="not_retrieved",
            reason="No label text was retrieved for coverage matching.",
        )
    match = find_match_in_sections(label, sections)
    if match:
        return EvidenceCoverageItem(
            category=category,
            label=label,
            status="addressed",
            reason="The retrieved label text explicitly mentions this item.",
            matched_evidence=match.snippet,
            source_id=match.source_id,
            section=match.section,
        )
    return EvidenceCoverageItem(
        category=category,
        label=label,
        status="not_found_in_evidence",
        reason=not_found_reason,
    )


def patient_context_coverage(
    label: str,
    sections: dict[str, list[LabelSection]],
    has_label_text: bool,
) -> EvidenceCoverageItem:
    if not has_label_text:
        return EvidenceCoverageItem(
            category="patient_context",
            label=label,
            status="not_retrieved",
            reason="No label text was retrieved for coverage matching.",
        )
    related_sections = patient_context_sections(label, sections)
    if related_sections:
        source_match = first_section_source(related_sections[0], sections)
        return EvidenceCoverageItem(
            category="patient_context",
            label=label,
            status="addressed",
            reason="A relevant label section was retrieved for this patient context.",
            matched_evidence=", ".join(related_sections),
            source_id=source_match.source_id if source_match else None,
            section=source_match.section if source_match else related_sections[0],
        )
    match = find_match_in_sections(label, sections)
    if match:
        return EvidenceCoverageItem(
            category="patient_context",
            label=label,
            status="addressed",
            reason="The retrieved label text explicitly mentions this patient context.",
            matched_evidence=match.snippet,
            source_id=match.source_id,
            section=match.section,
        )
    return EvidenceCoverageItem(
        category="patient_context",
        label=label,
        status="not_found_in_evidence",
        reason=(
            "The retrieved labels did not explicitly mention the patient "
            f"context {label}."
        ),
    )


def patient_context_sections(
    label: str,
    sections: dict[str, list[LabelSection]],
) -> list[str]:
    normalized = normalize(label)
    section_names: list[str] = []
    if normalized in {"pregnant", "pregnancy"}:
        section_names.extend(["pregnancy", "pregnancy_or_breast_feeding"])
    if normalized in {"breastfeeding", "lactation", "nursing"}:
        section_names.extend(["lactation", "pregnancy_or_breast_feeding"])
    if normalized in {"child", "children", "pediatric"}:
        section_names.append("use_in_specific_populations")
    return [section for section in section_names if sections.get(section)]


@dataclass(frozen=True)
class CoverageEvidenceMatch:
    snippet: str
    source_id: str | None
    section: str


def find_match_in_sections(
    label: str,
    sections: dict[str, list[LabelSection]],
) -> CoverageEvidenceMatch | None:
    normalized_label = normalize(label)
    if not normalized_label:
        return None

    pattern = re.compile(re.escape(label), flags=re.IGNORECASE)
    for section_name, entries in sections.items():
        for entry in entries:
            normalized_text = normalize(entry.text)
            if normalized_label not in normalized_text:
                continue
            match = pattern.search(entry.text)
            if match:
                return CoverageEvidenceMatch(
                    snippet=evidence_snippet(
                        entry.text,
                        match.start(),
                        match.end(),
                    ),
                    source_id=entry.source_id,
                    section=section_name,
                )
    return None


def first_section_source(
    section_name: str,
    sections: dict[str, list[LabelSection]],
) -> CoverageEvidenceMatch | None:
    first_entry = next(iter(sections.get(section_name, [])), None)
    if first_entry is None:
        return None
    return CoverageEvidenceMatch(
        snippet=section_name,
        source_id=first_entry.source_id,
        section=section_name,
    )


def first_section_evidence(
    sections: dict[str, list[LabelSection]],
    section_name: str,
) -> CoverageEvidenceMatch | None:
    for entry in sections.get(section_name, []):
        if not entry.text.strip():
            continue
        return CoverageEvidenceMatch(
            snippet=section_preview(entry.text),
            source_id=entry.source_id,
            section=section_name,
        )
    return None


def first_nonempty_section_evidence(
    sections: dict[str, list[LabelSection]],
) -> CoverageEvidenceMatch | None:
    for section_name in sections:
        match = first_section_evidence(sections, section_name)
        if match:
            return match
    return None


def same_concept(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    return normalize(left) == normalize(right)


def evidence_snippet(text: str, match_start: int, match_end: int) -> str:
    start = max(0, match_start - 90)
    end = min(len(text), match_end + 90)

    if start > 0:
        next_space = text.find(" ", start, match_start)
        if next_space != -1:
            start = next_space + 1

    if end < len(text):
        previous_space = text.rfind(" ", match_end, end)
        if previous_space != -1:
            end = previous_space

    snippet = " ".join(text[start:end].split())
    return f"...{snippet}..."


def section_preview(text: str, max_chars: int = 180) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return f"...{cleaned}..."
    end = cleaned.rfind(" ", 0, max_chars)
    if end == -1:
        end = max_chars
    return f"...{cleaned[:end].strip()}..."


def specificity_differs(primary: str, resolved: str) -> bool:
    normalized_primary = normalize(primary)
    normalized_resolved = normalize(resolved)
    if normalized_primary == normalized_resolved:
        return False
    return (
        normalized_primary in normalized_resolved
        or normalized_resolved in normalized_primary
    )


def normalize(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def unique_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        key = normalize(value)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(value)
    return unique


def format_human_list(values: list[str]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def secondary_drug_limitation(values: list[str]) -> str:
    if len(values) == 1:
        return (
            "Only the primary medication dossier was retrieved; "
            f"{values[0]} was recognized but not retrieved in this version."
        )
    return (
        "Only the primary medication dossier was retrieved; "
        f"{format_human_list(values)} were recognized but not retrieved "
        "in this version."
    )


def coverage_statuses() -> tuple[EvidenceCoverageStatus, ...]:
    return ("addressed", "not_found_in_evidence", "not_retrieved", "out_of_scope")
