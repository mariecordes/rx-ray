from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from src.dossier.models import LabelSection
from src.query_answer.models import (
    EvidenceAnswer,
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


def build_evidence_coverage(
    understanding: QueryUnderstandingResponse,
    secondary_evidence: list[SecondaryDrugEvidence] | None = None,
) -> EvidenceCoverageReport:
    """Build deterministic coverage metadata from extracted state and evidence."""

    secondary_evidence = secondary_evidence or []
    secondary_by_name = {
        normalize(item.resolved_concept.name): item for item in secondary_evidence
    }
    secondary_by_mention = {
        normalize(item.mention_text): item for item in secondary_evidence
    }
    dossier = understanding.primary_dossier
    sections = (
        dossier.label_evidence.sections
        if dossier and dossier.label_evidence
        else {}
    )
    evidence_text = "\n".join(
        section.text for entries in sections.values() for section in entries
    )
    has_label_text = bool(evidence_text.strip())
    primary_name = (
        dossier.resolved_drug.name
        if dossier and dossier.resolved_drug
        else None
    )
    items: list[EvidenceCoverageItem] = []

    if understanding.state.primary_drug:
        if primary_name:
            items.append(
                EvidenceCoverageItem(
                    category="primary_drug",
                    label=understanding.state.primary_drug,
                    status="addressed" if has_label_text else "not_found_in_evidence",
                    reason=(
                        "Retrieved evidence is tied to the resolved primary "
                        f"concept: {primary_name}."
                        if has_label_text
                        else (
                            f"Resolved to {primary_name}, "
                            "but no label text was retrieved."
                        )
                    ),
                )
            )
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
            match = first_secondary_label_match(secondary)
            items.append(
                EvidenceCoverageItem(
                    category="mentioned_drug",
                    label=drug,
                    status="addressed",
                    reason=(
                        "Secondary label evidence was retrieved for "
                        f"{secondary.resolved_concept.name}."
                    ),
                    matched_evidence=match.snippet if match else None,
                    source_id=match.source_id if match else None,
                    section=match.section if match else None,
                )
            )
            continue
        items.append(
            EvidenceCoverageItem(
                category="mentioned_drug",
                label=drug,
                status="not_retrieved",
                reason=(
                    "V1 retrieves full evidence only for the primary "
                    "resolved medication."
                ),
            )
        )

    for drug in unique_values(understanding.state.current_medications):
        secondary = find_secondary_evidence(
            drug,
            secondary_by_name,
            secondary_by_mention,
        )
        if secondary and has_secondary_label_text(secondary):
            match = first_secondary_label_match(secondary)
            items.append(
                EvidenceCoverageItem(
                    category="current_medication",
                    label=drug,
                    status="addressed",
                    reason=(
                        "Secondary label evidence was retrieved for the "
                        f"current medication {secondary.resolved_concept.name}."
                    ),
                    matched_evidence=match.snippet if match else None,
                    source_id=match.source_id if match else None,
                    section=match.section if match else None,
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
        items.append(
            patient_context_coverage(
                context,
                sections,
                evidence_text,
                has_label_text,
            )
        )

    for intent in unique_values(understanding.state.intents):
        intent_status: EvidenceCoverageStatus = "out_of_scope"
        intent_reason = (
            "Intent is recognized for context, but V1 does not yet "
            "check whether the retrieved evidence fully addresses it."
        )
        if intent == "interaction_check":
            if has_interaction_evidence(sections, secondary_evidence):
                intent_status = "addressed"
                intent_reason = (
                    "Drug-interactions label text was retrieved for at least "
                    "one mentioned medication. This is evidence coverage, not "
                    "a clinical interaction conclusion."
                )
            else:
                intent_status = "not_found_in_evidence"
                intent_reason = (
                    "No drug-interactions label text was retrieved for the "
                    "mentioned medication pair."
                )
        items.append(
            EvidenceCoverageItem(
                category="intent",
                label=intent,
                status=intent_status,
                reason=intent_reason,
            )
        )

    counts = Counter(item.status for item in items)
    return EvidenceCoverageReport(
        items=items,
        summary_counts={
            status: counts.get(status, 0) for status in coverage_statuses()
        },
    )


def add_coverage_limitations(
    answer: EvidenceAnswer | None,
    coverage: EvidenceCoverageReport,
    understanding: QueryUnderstandingResponse,
) -> EvidenceAnswer | None:
    if answer is None:
        return None

    limitations = list(answer.limitations)
    non_primary_drugs = [
        item.label
        for item in coverage.items
        if item.category == "mentioned_drug" and item.status == "not_retrieved"
    ]
    if non_primary_drugs:
        append_once(
            limitations,
            secondary_drug_limitation(non_primary_drugs),
        )

    missing_context = [
        item.label
        for item in coverage.items
        if item.category
        in {"current_medication", "allergy", "condition", "patient_context"}
        and item.status in {"not_found_in_evidence", "not_retrieved"}
    ]
    if missing_context:
        append_once(
            limitations,
            "The retrieved labels did not explicitly mention "
            f"{format_human_list(missing_context[:5])}.",
        )

    primary = understanding.state.primary_drug
    resolved = (
        understanding.primary_dossier.resolved_drug.name
        if understanding.primary_dossier and understanding.primary_dossier.resolved_drug
        else None
    )
    if primary and resolved and specificity_differs(primary, resolved):
        append_once(
            limitations,
            f"{SPECIFICITY_LIMITATION} ({primary} -> {resolved})",
        )

    return answer.model_copy(update={"limitations": limitations})


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


def first_secondary_label_match(
    item: SecondaryDrugEvidence,
) -> CoverageEvidenceMatch | None:
    evidence = item.label_evidence
    if evidence is None:
        return None
    section_names = [
        *SECONDARY_MATCH_SECTION_PRIORITY,
        *[
            name
            for name in evidence.sections
            if name not in SECONDARY_MATCH_SECTION_PRIORITY
        ],
    ]
    for section_name in section_names:
        entry = next(iter(evidence.sections.get(section_name, [])), None)
        if entry is None:
            continue
        return CoverageEvidenceMatch(
            snippet=section_preview(entry.text),
            source_id=entry.source_id,
            section=section_name,
        )
    return None


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
    evidence_text: str,
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


def find_match(label: str, evidence_text: str) -> str | None:
    normalized_label = normalize(label)
    if not normalized_label:
        return None
    normalized_text = normalize(evidence_text)
    if normalized_label not in normalized_text:
        return None
    pattern = re.compile(re.escape(label), flags=re.IGNORECASE)
    match = pattern.search(evidence_text)
    if match:
        return evidence_snippet(evidence_text, match.start(), match.end())
    return label


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


def append_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


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
