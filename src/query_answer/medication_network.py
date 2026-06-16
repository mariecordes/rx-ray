from __future__ import annotations

import logging

from src.dossier.builder import DossierBuilder
from src.dossier.models import RxNormConcept, RxNormEdge, RxNormNeighborhood
from src.query_answer.config import QueryAnswerParameters
from src.query_answer.models import (
    MedicationNetwork,
    MedicationNetworkRoot,
    SecondaryDrugEvidence,
)
from src.query_understanding.models import QueryUnderstandingResponse

logger = logging.getLogger(__name__)


def build_medication_network(
    understanding: QueryUnderstandingResponse,
    secondary_evidence: list[SecondaryDrugEvidence],
    builder: DossierBuilder,
    parameters: QueryAnswerParameters,
) -> MedicationNetwork:
    """Build a combined RxNorm terminology network for resolved query medications."""

    roots = medication_network_roots(understanding, secondary_evidence)
    if not roots:
        return MedicationNetwork()

    nodes_by_rxcui = {root.concept.rxcui: root.concept for root in roots}
    edges_by_key: dict[tuple[str, str, str], RxNormEdge] = {}
    truncated = False

    for root in roots:
        try:
            neighborhood = builder.rxnorm_store.get_neighborhood(
                root.concept.rxcui,
                depth=parameters.medication_network_depth,
                max_edges=parameters.medication_network_edges_per_root,
            )
        except Exception as exc:
            logger.warning(
                "Medication network lookup failed for RXCUI %s: %s",
                root.concept.rxcui,
                exc,
            )
            continue

        truncated = truncated or neighborhood.truncated
        for node in neighborhood.nodes:
            nodes_by_rxcui.setdefault(node.rxcui, node)
        for edge in neighborhood.edges:
            edges_by_key.setdefault(edge_key(edge), edge)

    neighborhood = RxNormNeighborhood(
        nodes=sorted(nodes_by_rxcui.values(), key=lambda node: node.name.casefold()),
        edges=sorted(
            edges_by_key.values(),
            key=lambda edge: (
                edge.source_name.casefold(),
                edge.relation,
                edge.target_name.casefold(),
            ),
        ),
        depth=parameters.medication_network_depth,
        truncated=truncated,
    )
    return MedicationNetwork(
        roots=roots,
        neighborhood=neighborhood,
        summary_counts={
            "roots": len(roots),
            "nodes": len(neighborhood.nodes),
            "edges": len(neighborhood.edges),
        },
        truncated=truncated,
    )


def medication_network_roots(
    understanding: QueryUnderstandingResponse,
    secondary_evidence: list[SecondaryDrugEvidence],
) -> list[MedicationNetworkRoot]:
    roots_by_rxcui: dict[str, MedicationNetworkRoot] = {}

    primary = (
        understanding.primary_dossier.resolved_drug
        if understanding.primary_dossier
        else None
    )
    if primary:
        add_root(roots_by_rxcui, primary, "primary medication")

    for item in secondary_evidence:
        role = display_role(item.role)
        add_root(roots_by_rxcui, item.resolved_concept, role)

    return list(roots_by_rxcui.values())


def add_root(
    roots_by_rxcui: dict[str, MedicationNetworkRoot],
    concept: RxNormConcept,
    role: str,
) -> None:
    existing = roots_by_rxcui.get(concept.rxcui)
    if existing:
        if role not in existing.roles:
            existing.roles.append(role)
        return
    roots_by_rxcui[concept.rxcui] = MedicationNetworkRoot(
        concept=concept,
        roles=[role],
    )


def display_role(role: str) -> str:
    return {
        "current_medication": "current medication",
        "mentioned_drug": "mentioned medication",
        "primary_drug": "primary medication",
        "allergy": "allergy medication",
    }.get(role, role.replace("_", " "))


def edge_key(edge: RxNormEdge) -> tuple[str, str, str]:
    endpoints = sorted([edge.source_rxcui, edge.target_rxcui])
    return (endpoints[0], endpoints[1], edge.relation)
