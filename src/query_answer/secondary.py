from __future__ import annotations

from src.dossier.builder import DossierBuilder
from src.dossier.models import (
    LabelSection,
    OpenFDALabelEvidence,
    OpenFDALabelRecord,
    RxNormConcept,
    RxNormEdge,
)
from src.query_answer.config import QueryAnswerParameters
from src.query_answer.models import RxNormPairContext, SecondaryDrugEvidence
from src.query_understanding.models import (
    QueryState,
    QueryUnderstandingResponse,
    ResolvedDrugMention,
)


SECONDARY_ROLES = {"allergy", "current_medication", "mentioned_drug"}


def build_secondary_evidence(
    understanding: QueryUnderstandingResponse,
    builder: DossierBuilder,
    parameters: QueryAnswerParameters,
) -> list[SecondaryDrugEvidence]:
    primary = (
        understanding.primary_dossier.resolved_drug
        if understanding.primary_dossier and understanding.primary_dossier.resolved_drug
        else None
    )
    if primary is None or parameters.max_secondary_drugs <= 0:
        return []

    secondary_mentions = select_secondary_mentions(
        understanding.resolved_drugs,
        understanding.state,
        primary,
        max_items=parameters.max_secondary_drugs,
    )
    is_interaction_intent = "interaction_check" in understanding.state.intents

    secondary_evidence: list[SecondaryDrugEvidence] = []
    for mention in secondary_mentions:
        concept = mention.selected_concept
        if concept is None:
            continue

        standard = builder.openfda_store.get_label_evidence(
            concept.rxcui,
            fallback_name=concept.name,
            limit=parameters.secondary_openfda_limit,
        )
        standard = tag_label_evidence(
            standard,
            "standard_secondary_label_lookup",
        )
        targeted_evidence: list[OpenFDALabelEvidence] = []
        if is_interaction_intent and parameters.interaction_lookup_limit > 0:
            targeted_evidence.append(
                tag_label_evidence(
                    builder.openfda_store.get_interaction_label_evidence(
                        concept.rxcui,
                        interaction_name=primary.name,
                        fallback_name=concept.name,
                        limit=parameters.interaction_lookup_limit,
                    ),
                    "interaction_targeted_lookup",
                )
            )
            targeted_evidence.append(
                tag_label_evidence(
                    builder.openfda_store.get_interaction_label_evidence(
                        primary.rxcui,
                        interaction_name=concept.name,
                        fallback_name=primary.name,
                        limit=parameters.interaction_lookup_limit,
                    ),
                    "interaction_targeted_lookup",
                )
            )

        interaction_evidence = merge_label_evidence(
            concept.rxcui,
            targeted_evidence,
            retrieval_mode="interaction_targeted_lookup",
            label_limit=parameters.interaction_lookup_limit,
        )
        merged = merge_label_evidence(
            concept.rxcui,
            [standard, interaction_evidence],
            retrieval_mode=combined_retrieval_mode(standard, interaction_evidence),
            label_limit=parameters.secondary_openfda_limit,
        )

        secondary_evidence.append(
            SecondaryDrugEvidence(
                mention_text=mention.text,
                role=mention.role,
                resolved_concept=concept,
                label_evidence=merged,
                interaction_label_evidence=interaction_evidence,
                retrieval_modes=retrieval_modes(standard, interaction_evidence),
                rxnorm_context=rxnorm_pair_context(builder, primary, concept),
            )
        )

    return secondary_evidence


def select_secondary_mentions(
    resolved_drugs: list[ResolvedDrugMention],
    state: QueryState,
    primary: RxNormConcept,
    *,
    max_items: int,
) -> list[ResolvedDrugMention]:
    selected: list[ResolvedDrugMention] = []
    seen: set[str] = {primary.rxcui}
    allowed_mentions = state_drug_keys(state)
    for mention in resolved_drugs:
        concept = mention.selected_concept
        if mention.role not in SECONDARY_ROLES or concept is None:
            continue
        if not mention_matches_state(mention, allowed_mentions):
            continue
        if concept.rxcui in seen:
            continue
        seen.add(concept.rxcui)
        selected.append(mention)
        if len(selected) >= max_items:
            break
    return selected


def state_drug_keys(state: QueryState) -> set[str]:
    return {
        normalized
        for value in [
            *state.all_drugs_mentioned,
            *state.current_medications,
            *state.allergies,
        ]
        if (normalized := normalize_drug_key(value))
    }


def mention_matches_state(
    mention: ResolvedDrugMention,
    allowed_mentions: set[str],
) -> bool:
    concept = mention.selected_concept
    candidates = [
        mention.text,
        concept.name if concept else "",
    ]
    return any(normalize_drug_key(value) in allowed_mentions for value in candidates)


def normalize_drug_key(value: str) -> str:
    return " ".join(value.casefold().replace("-", " ").split())


def rxnorm_pair_context(
    builder: DossierBuilder,
    primary: RxNormConcept,
    secondary: RxNormConcept,
) -> RxNormPairContext:
    primary_neighborhood = builder.rxnorm_store.get_neighborhood(
        primary.rxcui,
        depth=1,
        max_edges=200,
    )
    secondary_neighborhood = builder.rxnorm_store.get_neighborhood(
        secondary.rxcui,
        depth=1,
        max_edges=200,
    )
    direct_edges = [
        edge
        for edge in [*primary_neighborhood.edges, *secondary_neighborhood.edges]
        if {edge.source_rxcui, edge.target_rxcui} == {primary.rxcui, secondary.rxcui}
    ]
    if direct_edges:
        return RxNormPairContext(
            primary_rxcui=primary.rxcui,
            secondary_rxcui=secondary.rxcui,
            status="direct_relationship",
            summary=(
                "A direct RxNorm terminology relationship was found between "
                "the primary and secondary concepts."
            ),
            direct_edges=dedupe_edges(direct_edges),
        )

    primary_neighbor_ids = neighbor_ids(primary_neighborhood.edges, primary.rxcui)
    secondary_neighbor_ids = neighbor_ids(
        secondary_neighborhood.edges,
        secondary.rxcui,
    )
    shared_ids = (primary_neighbor_ids & secondary_neighbor_ids) - {
        primary.rxcui,
        secondary.rxcui,
    }
    if shared_ids:
        concepts = builder.rxnorm_store.get_concepts(set(sorted(shared_ids)[:5]))
        return RxNormPairContext(
            primary_rxcui=primary.rxcui,
            secondary_rxcui=secondary.rxcui,
            status="shared_neighbor",
            summary=(
                "The primary and secondary concepts share nearby RxNorm "
                "terminology neighbors. This is terminology context, not "
                "clinical interaction evidence."
            ),
            shared_neighbors=sorted(
                concepts.values(),
                key=lambda concept: concept.name.casefold(),
            ),
        )

    return RxNormPairContext(
        primary_rxcui=primary.rxcui,
        secondary_rxcui=secondary.rxcui,
        status="no_context",
        summary=(
            "No direct or shared one-hop RxNorm terminology context was found. "
            "RxNorm terminology context is not clinical interaction evidence."
        ),
    )


def neighbor_ids(edges: list[RxNormEdge], center_rxcui: str) -> set[str]:
    ids: set[str] = set()
    for edge in edges:
        if edge.source_rxcui == center_rxcui:
            ids.add(edge.target_rxcui)
        if edge.target_rxcui == center_rxcui:
            ids.add(edge.source_rxcui)
    return ids


def dedupe_edges(edges: list[RxNormEdge]) -> list[RxNormEdge]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[RxNormEdge] = []
    for edge in edges:
        key = (edge.source_rxcui, edge.target_rxcui, edge.relation)
        if key in seen:
            continue
        seen.add(key)
        unique.append(edge)
    return unique


def merge_label_evidence(
    rxcui: str,
    evidences: list[OpenFDALabelEvidence],
    *,
    retrieval_mode: str,
    label_limit: int,
) -> OpenFDALabelEvidence:
    records: list[OpenFDALabelRecord] = []
    sections: dict[str, list[LabelSection]] = {}
    errors: list[str] = []
    seen_keys: set[str] = set()
    included_source_ids: set[str | None] = set()
    seen_section_keys: set[tuple[str, str | None, str]] = set()
    record_index_by_key: dict[str, int] = {}
    section_index_by_key: dict[tuple[str, str | None, str], tuple[str, int]] = {}

    for evidence in evidences:
        errors.extend(evidence.errors)
        for record in evidence.label_records:
            key = stable_record_key(record)
            if key in seen_keys:
                existing_index = record_index_by_key[key]
                records[existing_index] = records[existing_index].model_copy(
                    update={
                        "provenance_tags": merge_tags(
                            records[existing_index].provenance_tags,
                            record.provenance_tags,
                        )
                    }
                )
                continue
            seen_keys.add(key)
            record_index_by_key[key] = len(records)
            included_source_ids.add(record.source_id)
            records.append(record)
        for section_name, entries in evidence.sections.items():
            for entry in entries:
                if entry.source_id not in included_source_ids:
                    continue
                section_key = (section_name, entry.source_id, entry.text)
                if section_key in seen_section_keys:
                    existing_section, existing_index = section_index_by_key[
                        section_key
                    ]
                    existing_entry = sections[existing_section][existing_index]
                    sections[existing_section][existing_index] = (
                        existing_entry.model_copy(
                            update={
                                "provenance_tags": merge_tags(
                                    existing_entry.provenance_tags,
                                    entry.provenance_tags,
                                )
                            }
                        )
                    )
                    continue
                seen_section_keys.add(section_key)
                section_entries = sections.setdefault(section_name, [])
                section_index_by_key[section_key] = (
                    section_name,
                    len(section_entries),
                )
                section_entries.append(entry)

    summary_metadata = build_summary_metadata(records)
    return OpenFDALabelEvidence(
        rxcui=rxcui,
        labels_found=len(records),
        label_limit=label_limit,
        retrieval_mode=retrieval_mode if records else "none",
        label_records=records,
        summary_metadata=summary_metadata,
        sections=sections,
        section_flags={
            f"has_{name}": bool(values) for name, values in sections.items()
        },
        errors=errors,
    )


def tag_label_evidence(
    evidence: OpenFDALabelEvidence,
    tag: str,
) -> OpenFDALabelEvidence:
    if not evidence.labels_found:
        return evidence
    return evidence.model_copy(
        update={
            "label_records": [
                record.model_copy(
                    update={
                        "provenance_tags": merge_tags(
                            record.provenance_tags,
                            [tag],
                        )
                    }
                )
                for record in evidence.label_records
            ],
            "sections": {
                section_name: [
                    entry.model_copy(
                        update={
                            "provenance_tags": merge_tags(
                                entry.provenance_tags,
                                [tag],
                            )
                        }
                    )
                    for entry in entries
                ]
                for section_name, entries in evidence.sections.items()
            },
        }
    )


def merge_tags(existing: list[str], new: list[str]) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for tag in [*existing, *new]:
        if not tag or tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
    return tags


def stable_record_key(record: OpenFDALabelRecord) -> str:
    for value in [record.source_id, record.id, record.set_id]:
        if value:
            return value
    for values in [record.spl_ids, record.spl_set_ids]:
        if values:
            return "|".join(sorted(values))
    return "|".join(
        [
            ",".join(record.brand_names),
            ",".join(record.generic_names),
            ",".join(record.manufacturer_names),
        ]
    )


def build_summary_metadata(
    records: list[OpenFDALabelRecord],
) -> dict[str, list[str]]:
    return {
        "manufacturers": sorted(
            {value for record in records for value in record.manufacturer_names}
        ),
        "brand_names": sorted(
            {value for record in records for value in record.brand_names}
        ),
        "generic_names": sorted(
            {value for record in records for value in record.generic_names}
        ),
        "label_ids": sorted({record.id for record in records if record.id}),
        "label_set_ids": sorted(
            {record.set_id for record in records if record.set_id}
        ),
        "spl_ids": sorted({value for record in records for value in record.spl_ids}),
        "spl_set_ids": sorted(
            {value for record in records for value in record.spl_set_ids}
        ),
    }


def retrieval_modes(
    standard: OpenFDALabelEvidence,
    interaction: OpenFDALabelEvidence,
) -> list[str]:
    modes: list[str] = []
    if standard.labels_found:
        modes.append("standard_secondary_label_lookup")
        if standard.retrieval_mode == "cache":
            modes.append("cache")
    if interaction.labels_found:
        modes.append("interaction_targeted_lookup")
    if not modes:
        modes.append("none")
    return modes


def combined_retrieval_mode(
    standard: OpenFDALabelEvidence,
    interaction: OpenFDALabelEvidence,
) -> str:
    modes = retrieval_modes(standard, interaction)
    if modes == ["none"]:
        return "none"
    return "+".join(modes)
