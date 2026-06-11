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
        )
        if item.rxnorm_context and primary:
            _add_rxnorm_context(
                builder,
                primary=primary,
                secondary=concept,
                context=item.rxnorm_context,
            )

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
                    "subtitle": existing.subtitle or node.subtitle,
                }
            )
            return
        self.nodes[node.id] = node

    def add_edge(self, edge: QuestionEvidenceMapEdge) -> None:
        if edge.id in self.edges:
            existing = self.edges[edge.id]
            self.edges[edge.id] = existing.model_copy(
                update={"tags": merge_tags(existing.tags, edge.tags)}
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
            concept_id = state_node_id(role, value)
            builder.add_node(
                QuestionEvidenceMapNode(
                    id=concept_id,
                    kind="query_concept",
                    label=value,
                    subtitle=display_role(role),
                    role=role,
                )
            )
            builder.add_edge(
                QuestionEvidenceMapEdge(
                    id=f"question->{concept_id}",
                    source="question",
                    target=concept_id,
                    kind="has_role",
                    label=f"Extracted as {display_role(role)}",
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
                role=mention.role,
                rxcui=concept.rxcui,
            )
        )
        state_id = state_node_id(mention.role, mention.text)
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
                role="primary_drug",
                rxcui=primary.rxcui,
            )
        )
        if understanding.state.primary_drug:
            state_id = state_node_id("primary_drug", understanding.state.primary_drug)
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
) -> None:
    if evidence is None:
        return

    sections_by_source = _sections_by_source(evidence)
    for record in evidence.label_records:
        source_id = record.source_id
        if not source_id:
            continue
        source_node_id = label_source_node_id(scope, concept.rxcui, source_id)
        builder.add_node(
            QuestionEvidenceMapNode(
                id=source_node_id,
                kind="label_source",
                label=source_label(record),
                subtitle=source_subtitle(record),
                rxcui=concept.rxcui,
                source_id=source_id,
                evidence_scope=scope,
                tags=record.provenance_tags,
            )
        )
        builder.add_edge(
            QuestionEvidenceMapEdge(
                id=f"{source_concept_node_id}->{source_node_id}:has_label_source",
                source=source_concept_node_id,
                target=source_node_id,
                kind="has_label_source",
                label="Label source retrieved",
                rxcui=concept.rxcui,
                source_id=source_id,
                evidence_scope=scope,
                tags=record.provenance_tags,
            )
        )

        for section_name, entries in sections_by_source.get(source_id, {}).items():
            section_tags = merge_tags(
                [],
                [tag for entry in entries for tag in entry.provenance_tags],
            )
            section_node_id = label_section_node_id(
                scope,
                concept.rxcui,
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
                    rxcui=concept.rxcui,
                    source_id=source_id,
                    section=section_name,
                    evidence_scope=scope,
                    tags=section_tags,
                )
            )
            is_interaction_targeted = INTERACTION_TARGETED_TAG in section_tags
            builder.add_edge(
                QuestionEvidenceMapEdge(
                    id=f"{source_node_id}->{section_node_id}:{section_name}",
                    source=source_node_id,
                    target=section_node_id,
                    kind=(
                        "mentions_in_interaction_section"
                        if is_interaction_targeted
                        else "has_label_section"
                    ),
                    label=(
                        "Label interaction section mentions another medication"
                        if is_interaction_targeted
                        else "Label section retrieved"
                    ),
                    rxcui=concept.rxcui,
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


def state_node_id(role: str, value: str) -> str:
    return f"query-concept:{role}:{slug(value)}"


def rxnorm_node_id(rxcui: str) -> str:
    return f"rxnorm:{rxcui}"


def label_source_node_id(scope: str, rxcui: str, source_id: str) -> str:
    return f"label-source:{scope}:{rxcui}:{source_id}"


def label_section_node_id(
    scope: str,
    rxcui: str,
    source_id: str,
    section: str,
) -> str:
    return f"label-section:{scope}:{rxcui}:{source_id}:{section}"


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
