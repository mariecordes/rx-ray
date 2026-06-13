from __future__ import annotations

from collections import Counter

from src.dossier.models import (
    LabelSection,
    OpenFDALabelEvidence,
    OpenFDALabelRecord,
    RxNormConcept,
)
from src.query_answer.models import (
    QuestionEvidenceMap,
    QuestionEvidenceMapEdge,
    QuestionEvidenceMapNode,
    RxNormPairContext,
    SecondaryDrugEvidence,
)
from src.query_understanding.models import QueryUnderstandingResponse


INTERACTION_TARGETED_TAG = "interaction_targeted_lookup"


def build_question_evidence_map(
    understanding: QueryUnderstandingResponse,
    secondary_evidence: list[SecondaryDrugEvidence] | None = None,
) -> QuestionEvidenceMap:
    """Build a request-time map from extracted state to retrieved evidence."""

    builder = EvidenceMapBuilder()
    secondary_evidence = secondary_evidence or []

    builder.add_node(
        QuestionEvidenceMapNode(
            id="question",
            kind="question",
            label="User question",
            subtitle=understanding.query,
        )
    )
    _add_state_nodes(builder, understanding)
    _add_resolved_drug_nodes(builder, understanding)
    resolved_concepts = _resolved_concepts(understanding, secondary_evidence)

    primary = (
        understanding.primary_dossier.resolved_drug
        if understanding.primary_dossier and understanding.primary_dossier.resolved_drug
        else None
    )
    if (
        primary
        and understanding.primary_dossier
        and understanding.primary_dossier.label_evidence
    ):
        _add_label_evidence(
            builder,
            concept=primary,
            evidence=understanding.primary_dossier.label_evidence,
            scope="primary",
            source_concept_node_id=rxnorm_node_id(primary.rxcui),
            resolved_concepts=resolved_concepts,
        )

    for item in secondary_evidence:
        concept = item.resolved_concept
        concept_node_id = rxnorm_node_id(concept.rxcui)
        _add_label_evidence(
            builder,
            concept=concept,
            evidence=item.label_evidence,
            scope="secondary",
            source_concept_node_id=concept_node_id,
            resolved_concepts=resolved_concepts,
            interaction_partner_concept=primary,
        )
        # Keep RxNorm pair context available on SecondaryDrugEvidence, but do not
        # render it into the question-level evidence map for now. In practice it
        # reads like terminology diagnostics rather than user-facing evidence and
        # clutters the graph.
        # if item.rxnorm_context and primary:
        #     _add_rxnorm_context(
        #         builder,
        #         primary=primary,
        #         secondary=concept,
        #         context=item.rxnorm_context,
        #     )

    return builder.build()


class EvidenceMapBuilder:
    def __init__(self) -> None:
        self.nodes: dict[str, QuestionEvidenceMapNode] = {}
        self.edges: dict[str, QuestionEvidenceMapEdge] = {}

    def add_node(self, node: QuestionEvidenceMapNode) -> None:
        if node.id in self.nodes:
            existing = self.nodes[node.id]
            self.nodes[node.id] = existing.model_copy(
                update={
                    "tags": merge_tags(existing.tags, node.tags),
                    "label_rxcuis": merge_tags(
                        existing.label_rxcuis,
                        node.label_rxcuis,
                    ),
                    "subtitle": existing.subtitle or node.subtitle,
                }
            )
            return
        self.nodes[node.id] = node

    def add_edge(self, edge: QuestionEvidenceMapEdge) -> None:
        if edge.id in self.edges:
            existing = self.edges[edge.id]
            self.edges[edge.id] = existing.model_copy(
                update={
                    "tags": merge_tags(existing.tags, edge.tags),
                    "interaction_terms": merge_tags(
                        existing.interaction_terms,
                        edge.interaction_terms,
                    ),
                }
            )
            return
        self.edges[edge.id] = edge

    def build(self) -> QuestionEvidenceMap:
        nodes = list(self.nodes.values())
        edges = list(self.edges.values())
        return QuestionEvidenceMap(
            nodes=nodes,
            edges=edges,
            summary_counts={
                "nodes": len(nodes),
                "edges": len(edges),
                **{
                    f"nodes_{kind}": count
                    for kind, count in Counter(node.kind for node in nodes).items()
                },
                **{
                    f"edges_{kind}": count
                    for kind, count in Counter(edge.kind for edge in edges).items()
                },
            },
        )


def _add_state_nodes(
    builder: EvidenceMapBuilder,
    understanding: QueryUnderstandingResponse,
) -> None:
    for role, values in [
        ("primary_drug", [understanding.state.primary_drug]),
        ("mentioned_drug", understanding.state.all_drugs_mentioned),
        ("current_medication", understanding.state.current_medications),
        ("allergy", understanding.state.allergies),
        ("condition", understanding.state.conditions),
        ("patient_context", understanding.state.patient_context),
    ]:
        for value in unique_values([item for item in values if item]):
            concept_id = state_node_id(value)
            builder.add_node(
                QuestionEvidenceMapNode(
                    id=concept_id,
                    kind="query_concept",
                    label=value,
                    subtitle=display_role(role),
                    role=role,
                    tags=[role],
                )
            )
            builder.add_edge(
                QuestionEvidenceMapEdge(
                    id=f"question->{concept_id}:has_role",
                    source="question",
                    target=concept_id,
                    kind="has_role",
                    label="Extracted from user question",
                    tags=[role],
                )
            )


def _add_resolved_drug_nodes(
    builder: EvidenceMapBuilder,
    understanding: QueryUnderstandingResponse,
) -> None:
    seen_rxcuis: set[str] = set()
    for mention in understanding.resolved_drugs:
        concept = mention.selected_concept
        if concept is None:
            continue
        seen_rxcuis.add(concept.rxcui)
        concept_node_id = rxnorm_node_id(concept.rxcui)
        builder.add_node(
            QuestionEvidenceMapNode(
                id=concept_node_id,
                kind="resolved_medication",
                label=concept.name,
                subtitle=concept.tty or "RxNorm concept",
                rxcui=concept.rxcui,
                tags=[mention.role],
            )
        )
        state_id = state_node_id(mention.text)
        if state_id in builder.nodes:
            builder.add_edge(
                QuestionEvidenceMapEdge(
                    id=f"{state_id}->{concept_node_id}:resolved_as",
                    source=state_id,
                    target=concept_node_id,
                    kind="resolved_as",
                    label="Resolved as RxNorm concept",
                    rxcui=concept.rxcui,
                )
            )

    primary = (
        understanding.primary_dossier.resolved_drug
        if understanding.primary_dossier and understanding.primary_dossier.resolved_drug
        else None
    )
    if primary and primary.rxcui not in seen_rxcuis:
        concept_node_id = rxnorm_node_id(primary.rxcui)
        builder.add_node(
            QuestionEvidenceMapNode(
                id=concept_node_id,
                kind="resolved_medication",
                label=primary.name,
                subtitle=primary.tty or "RxNorm concept",
                rxcui=primary.rxcui,
                tags=["primary_drug"],
            )
        )
        if understanding.state.primary_drug:
            state_id = state_node_id(understanding.state.primary_drug)
            if state_id in builder.nodes:
                builder.add_edge(
                    QuestionEvidenceMapEdge(
                        id=f"{state_id}->{concept_node_id}:resolved_as",
                        source=state_id,
                        target=concept_node_id,
                        kind="resolved_as",
                        label="Resolved as RxNorm concept",
                        rxcui=primary.rxcui,
                    )
                )


def _add_label_evidence(
    builder: EvidenceMapBuilder,
    *,
    concept: RxNormConcept,
    evidence: OpenFDALabelEvidence | None,
    scope: str,
    source_concept_node_id: str,
    resolved_concepts: list[RxNormConcept],
    interaction_partner_concept: RxNormConcept | None = None,
) -> None:
    if evidence is None:
        return

    sections_by_source = _sections_by_source(evidence)
    for record in evidence.label_records:
        source_id = record.source_id
        if not source_id:
            continue
        source_node_id = label_source_node_id(source_id)
        owner_concepts = matching_label_owner_concepts(record, resolved_concepts)
        if not owner_concepts:
            owner_concepts = [concept]
        owner_rxcui = owner_concepts[0].rxcui if owner_concepts else concept.rxcui
        builder.add_node(
            QuestionEvidenceMapNode(
                id=source_node_id,
                kind="label_source",
                label=source_label(record),
                subtitle=source_subtitle(record),
                rxcui=owner_rxcui,
                label_rxcuis=record.rxcuis,
                source_id=source_id,
                evidence_scope=scope,
                tags=record.provenance_tags,
            )
        )

        for owner in owner_concepts:
            builder.add_edge(
                QuestionEvidenceMapEdge(
                    id=f"{rxnorm_node_id(owner.rxcui)}->{source_node_id}:has_label_source",
                    source=rxnorm_node_id(owner.rxcui),
                    target=source_node_id,
                    kind="has_label_source",
                    label="Label source belongs to medication concept",
                    rxcui=owner.rxcui,
                    source_id=source_id,
                    evidence_scope=scope,
                    tags=record.provenance_tags,
                )
            )

        is_interaction_targeted_record = INTERACTION_TARGETED_TAG in record.provenance_tags
        if is_interaction_targeted_record:
            interaction_terms = unique_values(
                [
                    term
                    for term in [
                        concept.name,
                        interaction_partner_concept.name
                        if interaction_partner_concept
                        else None,
                    ]
                    if term
                ]
            )
            interaction_concepts = [concept]
            if (
                interaction_partner_concept
                and interaction_partner_concept.rxcui != concept.rxcui
            ):
                interaction_concepts.append(interaction_partner_concept)
            for interaction_concept in interaction_concepts:
                builder.add_edge(
                    QuestionEvidenceMapEdge(
                        id=(
                            f"{rxnorm_node_id(interaction_concept.rxcui)}->"
                            f"{source_node_id}:interaction_lookup_source"
                        ),
                        source=rxnorm_node_id(interaction_concept.rxcui),
                        target=source_node_id,
                        kind="interaction_lookup_source",
                        label="Interaction-specific lookup returned this label source",
                        rxcui=interaction_concept.rxcui,
                        source_id=source_id,
                        evidence_scope=scope,
                        interaction_terms=interaction_terms,
                        tags=merge_tags(
                            record.provenance_tags,
                            [INTERACTION_TARGETED_TAG],
                        ),
                    )
                )

        for section_name, entries in sections_by_source.get(source_id, {}).items():
            section_tags = merge_tags(
                [],
                [tag for entry in entries for tag in entry.provenance_tags],
            )
            section_node_id = label_section_node_id(
                source_id,
                section_name,
            )
            subtitle = (
                f"{len(entries)} label text item"
                f"{'s' if len(entries) != 1 else ''}"
            )
            builder.add_node(
                QuestionEvidenceMapNode(
                    id=section_node_id,
                    kind="label_section",
                    label=section_name.replace("_", " "),
                    subtitle=subtitle,
                    rxcui=owner_rxcui,
                    label_rxcuis=record.rxcuis,
                    source_id=source_id,
                    section=section_name,
                    evidence_scope=scope,
                    tags=section_tags,
                )
            )
            builder.add_edge(
                QuestionEvidenceMapEdge(
                    id=f"{source_node_id}->{section_node_id}:{section_name}",
                    source=source_node_id,
                    target=section_node_id,
                    kind="has_label_section",
                    label="Label section belongs to label source",
                    rxcui=owner_rxcui,
                    source_id=source_id,
                    section=section_name,
                    evidence_scope=scope,
                    tags=section_tags,
                )
            )


def _add_rxnorm_context(
    builder: EvidenceMapBuilder,
    *,
    primary: RxNormConcept,
    secondary: RxNormConcept,
    context: RxNormPairContext,
) -> None:
    context_node_id = f"rxnorm-context:{primary.rxcui}:{secondary.rxcui}"
    builder.add_node(
        QuestionEvidenceMapNode(
            id=context_node_id,
            kind="rxnorm_context",
            label="RxNorm terminology context",
            subtitle=context.summary,
            rxcui=secondary.rxcui,
            tags=[context.status],
        )
    )
    for concept in [primary, secondary]:
        builder.add_edge(
            QuestionEvidenceMapEdge(
                id=f"{rxnorm_node_id(concept.rxcui)}->{context_node_id}:terminology",
                source=rxnorm_node_id(concept.rxcui),
                target=context_node_id,
                kind="has_terminology_context",
                label="Terminology context only",
                rxcui=concept.rxcui,
                tags=[context.status],
            )
        )


def _sections_by_source(
    evidence: OpenFDALabelEvidence,
) -> dict[str, dict[str, list[LabelSection]]]:
    sections_by_source: dict[str, dict[str, list[LabelSection]]] = {}
    for section_name, entries in evidence.sections.items():
        for entry in entries:
            if not entry.source_id:
                continue
            source_sections = sections_by_source.setdefault(entry.source_id, {})
            source_sections.setdefault(section_name, []).append(entry)
    return sections_by_source


def _resolved_concepts(
    understanding: QueryUnderstandingResponse,
    secondary_evidence: list[SecondaryDrugEvidence],
) -> list[RxNormConcept]:
    concepts: list[RxNormConcept] = []
    seen: set[str] = set()
    for mention in understanding.resolved_drugs:
        if mention.selected_concept:
            _append_concept(concepts, seen, mention.selected_concept)
    if understanding.primary_dossier and understanding.primary_dossier.resolved_drug:
        _append_concept(concepts, seen, understanding.primary_dossier.resolved_drug)
    for item in secondary_evidence:
        _append_concept(concepts, seen, item.resolved_concept)
    return concepts


def _append_concept(
    concepts: list[RxNormConcept],
    seen: set[str],
    concept: RxNormConcept,
) -> None:
    if concept.rxcui in seen:
        return
    seen.add(concept.rxcui)
    concepts.append(concept)


def matching_label_owner_concepts(
    record: OpenFDALabelRecord,
    concepts: list[RxNormConcept],
) -> list[RxNormConcept]:
    record_rxcuis = {value for value in record.rxcuis if value}
    record_names = {
        slug(value)
        for value in [
            *record.brand_names,
            *record.generic_names,
            *record.substance_names,
        ]
        if value
    }
    matches: list[RxNormConcept] = []
    for concept in concepts:
        if concept.rxcui in record_rxcuis or slug(concept.name) in record_names:
            matches.append(concept)
    return matches


def state_node_id(value: str) -> str:
    return f"query-concept:{slug(value)}"


def rxnorm_node_id(rxcui: str) -> str:
    return f"rxnorm:{rxcui}"


def label_source_node_id(source_id: str) -> str:
    return f"label-source:{source_id}"


def label_section_node_id(
    source_id: str,
    section: str,
) -> str:
    return f"label-section:{source_id}:{section}"


def source_label(record: OpenFDALabelRecord) -> str:
    return (
        first(record.brand_names)
        or first(record.generic_names)
        or first(record.manufacturer_names)
        or "Label source"
    )


def source_subtitle(record: OpenFDALabelRecord) -> str | None:
    values = [
        first(record.generic_names),
        first(record.manufacturer_names),
    ]
    return " · ".join(value for value in values if value) or None


def display_role(role: str) -> str:
    return role.replace("_", " ")


def first(values: list[str]) -> str | None:
    return values[0] if values else None


def unique_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        key = slug(value)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(value)
    return unique


def slug(value: str) -> str:
    return "-".join(value.casefold().replace("_", " ").split())


def merge_tags(existing: list[str], new: list[str]) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for tag in [*existing, *new]:
        if not tag or tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
    return tags
