from __future__ import annotations

from src.dossier.builder import DossierBuilder
from src.dossier.models import RxNormConcept, RxNormEdge, RxNormNeighborhood
from src.query_answer.config import QueryAnswerParameters
from src.query_answer.models import (
    QuestionRxNormNetwork,
    RxNormNetworkCenter,
    SecondaryDrugEvidence,
)
from src.query_understanding.models import QueryUnderstandingResponse


def build_question_rxnorm_network(
    understanding: QueryUnderstandingResponse,
    secondary_evidence: list[SecondaryDrugEvidence],
    builder: DossierBuilder,
    parameters: QueryAnswerParameters,
) -> QuestionRxNormNetwork:
    """Merge each resolved drug's RxNorm neighborhood into one shared network.

    The primary keeps its already-built deeper neighborhood; secondaries are
    expanded shallowly. Nodes reachable from more than one drug are flagged as
    ``shared_rxcuis`` so the UI can surface terminology overlap. This is
    terminology context only and never asserts a clinical interaction.
    """

    primary = (
        understanding.primary_dossier.resolved_drug
        if understanding.primary_dossier
        and understanding.primary_dossier.resolved_drug
        else None
    )
    if primary is None:
        return QuestionRxNormNetwork()

    centers: list[RxNormNetworkCenter] = [
        RxNormNetworkCenter(
            rxcui=primary.rxcui,
            name=primary.name,
            tty=primary.tty,
            role="primary_drug",
        )
    ]
    neighborhoods: list[tuple[str, RxNormNeighborhood]] = [
        (primary.rxcui, understanding.primary_dossier.rxnorm_neighborhood)
    ]
    seen_centers = {primary.rxcui}

    for item in secondary_evidence:
        concept = item.resolved_concept
        if concept.rxcui in seen_centers:
            continue
        seen_centers.add(concept.rxcui)
        centers.append(
            RxNormNetworkCenter(
                rxcui=concept.rxcui,
                name=concept.name,
                tty=concept.tty,
                role=item.role,
            )
        )
        neighborhoods.append(
            (
                concept.rxcui,
                builder.rxnorm_store.get_neighborhood(
                    concept.rxcui,
                    depth=parameters.network_secondary_depth,
                    max_edges=parameters.network_max_edges_per_center,
                ),
            )
        )

    merged_nodes: dict[str, RxNormConcept] = {}
    membership: dict[str, list[str]] = {}
    merged_edges: dict[tuple[str, str, str], RxNormEdge] = {}
    truncated = False

    for center_rxcui, neighborhood in neighborhoods:
        truncated = truncated or neighborhood.truncated
        member_ids = {node.rxcui for node in neighborhood.nodes}
        member_ids.add(center_rxcui)
        for rxcui in member_ids:
            centers_for_node = membership.setdefault(rxcui, [])
            if center_rxcui not in centers_for_node:
                centers_for_node.append(center_rxcui)
        for node in neighborhood.nodes:
            merged_nodes.setdefault(node.rxcui, node)
        for edge in neighborhood.edges:
            key = (edge.source_rxcui, edge.target_rxcui, edge.relation)
            merged_edges.setdefault(key, edge)

    for center in centers:
        merged_nodes.setdefault(
            center.rxcui,
            RxNormConcept(rxcui=center.rxcui, name=center.name, tty=center.tty),
        )

    center_ids = {center.rxcui for center in centers}
    shared_ids = {
        rxcui for rxcui, owners in membership.items() if len(owners) > 1
    }

    kept_edges, edges_truncated = _budget_edges(
        list(merged_edges.values()),
        center_ids=center_ids,
        shared_ids=shared_ids,
        max_total_edges=parameters.network_max_total_edges,
    )
    truncated = truncated or edges_truncated

    surviving_ids = set(center_ids)
    for edge in kept_edges:
        surviving_ids.add(edge.source_rxcui)
        surviving_ids.add(edge.target_rxcui)

    nodes = sorted(
        (
            node
            for rxcui, node in merged_nodes.items()
            if rxcui in surviving_ids
        ),
        key=lambda node: node.name.casefold(),
    )
    node_membership = {
        rxcui: owners
        for rxcui, owners in membership.items()
        if rxcui in surviving_ids
    }
    shared_rxcuis = sorted(rxcui for rxcui in shared_ids if rxcui in surviving_ids)

    return QuestionRxNormNetwork(
        centers=centers,
        nodes=nodes,
        edges=kept_edges,
        node_membership=node_membership,
        shared_rxcuis=shared_rxcuis,
        truncated=truncated,
    )


def _budget_edges(
    edges: list[RxNormEdge],
    *,
    center_ids: set[str],
    shared_ids: set[str],
    max_total_edges: int,
) -> tuple[list[RxNormEdge], bool]:
    """Cap edges, keeping center- then shared-incident edges first."""

    if len(edges) <= max_total_edges:
        return edges, False

    def priority(edge: RxNormEdge) -> int:
        endpoints = {edge.source_rxcui, edge.target_rxcui}
        if endpoints & center_ids:
            return 0
        if endpoints & shared_ids:
            return 1
        return 2

    ordered = sorted(enumerate(edges), key=lambda pair: (priority(pair[1]), pair[0]))
    kept = [edge for _, edge in ordered[:max_total_edges]]
    return kept, True
