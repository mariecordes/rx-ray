from __future__ import annotations

import re
from collections import Counter

from src.dossier.models import LabelSection
from src.query_answer.models import (
    EvidenceAnswer,
    EvidenceCoverageItem,
    EvidenceCoverageReport,
    EvidenceCoverageStatus,
)
from src.query_understanding.models import QueryUnderstandingResponse

PRIMARY_ONLY_LIMITATION = (
    "Evidence coverage is limited to the primary resolved medication; additional "
    "mentioned medications were not retrieved in this version."
)
SPECIFICITY_LIMITATION = (
    "The user query may be more specific than the resolved medication concept used "
    "for retrieval."
)


def build_evidence_coverage(
    understanding: QueryUnderstandingResponse,
) -> EvidenceCoverageReport:
    """Build deterministic coverage metadata from extracted state and evidence."""

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
                    matched_evidence=primary_name,
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
        items.append(
            coverage_from_text(
                category="current_medication",
                label=drug,
                evidence_text=evidence_text,
                has_label_text=has_label_text,
                not_found_reason=(
                    "The retrieved primary-drug labels did not explicitly "
                    "mention this current medication."
                ),
            )
        )

    for allergy in unique_values(understanding.state.allergies):
        items.append(
            coverage_from_text(
                category="allergy",
                label=allergy,
                evidence_text=evidence_text,
                has_label_text=has_label_text,
                not_found_reason=(
                    "The retrieved primary-drug labels did not explicitly "
                    "mention this allergy."
                ),
            )
        )

    for condition in unique_values(understanding.state.conditions):
        items.append(
            coverage_from_text(
                category="condition",
                label=condition,
                evidence_text=evidence_text,
                has_label_text=has_label_text,
                not_found_reason=(
                    "The retrieved primary-drug labels did not explicitly "
                    "mention this condition."
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

    if understanding.state.intent:
        items.append(
            EvidenceCoverageItem(
                category="intent",
                label=understanding.state.intent,
                status="out_of_scope",
                reason=(
                    "Intent is recognized for context, but V1 does not yet "
                    "check whether the retrieved evidence fully addresses it."
                ),
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
    if any(
        item.category == "mentioned_drug" and item.status == "not_retrieved"
        for item in coverage.items
    ):
        append_once(limitations, PRIMARY_ONLY_LIMITATION)

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
            "Retrieved evidence did not explicitly cover: "
            + ", ".join(missing_context[:5])
            + ".",
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


def coverage_from_text(
    *,
    category: str,
    label: str,
    evidence_text: str,
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
    match = find_match(label, evidence_text)
    if match:
        return EvidenceCoverageItem(
            category=category,
            label=label,
            status="addressed",
            reason="The retrieved label text explicitly mentions this item.",
            matched_evidence=match,
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
        return EvidenceCoverageItem(
            category="patient_context",
            label=label,
            status="addressed",
            reason="A relevant label section was retrieved for this patient context.",
            matched_evidence=", ".join(related_sections),
        )
    match = find_match(label, evidence_text)
    if match:
        return EvidenceCoverageItem(
            category="patient_context",
            label=label,
            status="addressed",
            reason="The retrieved label text explicitly mentions this patient context.",
            matched_evidence=match,
        )
    return EvidenceCoverageItem(
        category="patient_context",
        label=label,
        status="not_found_in_evidence",
        reason=(
            "The retrieved primary-drug labels did not explicitly mention "
            "this patient context."
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
        start = max(0, match.start() - 60)
        end = min(len(evidence_text), match.end() + 60)
        return " ".join(evidence_text[start:end].split())
    return label


def same_concept(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    return normalize(left) == normalize(right)


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


def coverage_statuses() -> tuple[EvidenceCoverageStatus, ...]:
    return ("addressed", "not_found_in_evidence", "not_retrieved", "out_of_scope")
