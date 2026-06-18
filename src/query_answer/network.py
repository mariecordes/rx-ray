from __future__ import annotations

from src.dossier.builder import DossierBuilder
from src.dossier.models import RxNormConcept, RxNormEdge
from src.dossier.rxnorm_store import INGREDIENT_TTYS
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

    Each drug gets an equal edge budget derived from the global cap divided by
    the number of centers. Edges from each center are interleaved in round-robin
    order so the frontend's display logic naturally distributes visual slots
    fairly across all drugs. Nodes reachable from more than one drug are flagged
    as ``shared_rxcuis`` — this is RxNorm vocabulary overlap, never a clinical
    interaction claim.
    """
    primary = (
        understanding.primary_dossier.resolved_drug
        if understanding.primary_dossier
        and understanding.primary_dossier.resolved_drug
        else None
    )
    if primary is None:
        return QuestionRxNormNetwork()

    # Pass 1: collect all unique center (rxcui, name, tty, role) tuples.
    seen_rxcuis: set[str] = {primary.rxcui}
    center_tuples: list[tuple[str, str, str | None, str]] = [
        (primary.rxcui, primary.name, primary.tty, "primary_drug")
    ]
    for item in secondary_evidence:
        concept = item.resolved_concept
        if concept.rxcui in seen_rxcuis:
            continue
        seen_rxcuis.add(concept.rxcui)
        center_tuples.append((concept.rxcui, concept.name, concept.tty, item.role))

    # Surface the primary's active ingredient(s) as their own centers, so a
    # specific product (e.g. a cream) gets an ingredient-focused neighborhood
    # instead of only its dose-form relatives. Mirrors the Evidence Map, which
    # already shows the ingredient as its own node.
    if (primary.tty or "") not in INGREDIENT_TTYS:
        for ingredient in builder.rxnorm_store.get_ingredient_concepts(primary.rxcui):
            if ingredient.rxcui in seen_rxcuis:
                continue
            seen_rxcuis.add(ingredient.rxcui)
            center_tuples.append(
                (ingredient.rxcui, ingredient.name, ingredient.tty, "ingredient")
            )

    num_centers = len(center_tuples)
    per_center_budget = min(
        parameters.network_max_edges_per_center,
        parameters.network_max_total_edges // max(num_centers, 1),
    )

    # Pass 2: build center list, fetch/cap neighborhoods, track membership.
    centers: list[RxNormNetworkCenter] = []
    center_edge_lists: list[list[RxNormEdge]] = []
    all_nodes: dict[str, RxNormConcept] = {}
    membership: dict[str, list[str]] = {}
    truncated = False
    primary_neighborhood = understanding.primary_dossier.rxnorm_neighborhood

    for rxcui, name, tty, role in center_tuples:
        centers.append(
            RxNormNetworkCenter(rxcui=rxcui, name=name, tty=tty, role=role)
        )

        if rxcui == primary.rxcui:
            neighborhood_nodes = primary_neighborhood.nodes
            edges = primary_neighborhood.edges[:per_center_budget]
            truncated = truncated or primary_neighborhood.truncated
        else:
            neighborhood = builder.rxnorm_store.get_neighborhood(
                rxcui,
                depth=parameters.network_secondary_depth,
                max_edges=per_center_budget,
            )
            neighborhood_nodes = neighborhood.nodes
            edges = neighborhood.edges
            truncated = truncated or neighborhood.truncated

        center_edge_lists.append(edges)

        member_rxcuis = {node.rxcui for node in neighborhood_nodes}
        member_rxcuis.add(rxcui)
        for member_rxcui in member_rxcuis:
            owners = membership.setdefault(member_rxcui, [])
            if rxcui not in owners:
                owners.append(rxcui)

        for node in neighborhood_nodes:
            all_nodes.setdefault(node.rxcui, node)

    for rxcui, name, tty, _ in center_tuples:
        all_nodes.setdefault(
            rxcui, RxNormConcept(rxcui=rxcui, name=name, tty=tty)
        )

    # Interleave edges from each center in round-robin order, deduplicating.
    seen_edge_keys: set[tuple[str, str, str]] = set()
    interleaved: list[RxNormEdge] = []
    max_len = max((len(e) for e in center_edge_lists), default=0)
    for i in range(max_len):
        for edge_list in center_edge_lists:
            if i >= len(edge_list):
                continue
            edge = edge_list[i]
            key = (edge.source_rxcui, edge.target_rxcui, edge.relation)
            if key not in seen_edge_keys:
                seen_edge_keys.add(key)
                interleaved.append(edge)

    kept_edges = interleaved[:parameters.network_max_total_edges]
    if len(interleaved) > parameters.network_max_total_edges:
        truncated = True

    center_ids = {rxcui for rxcui, *_ in center_tuples}
    surviving_ids = set(center_ids)
    for edge in kept_edges:
        surviving_ids.add(edge.source_rxcui)
        surviving_ids.add(edge.target_rxcui)

    shared_ids = {
        rxcui for rxcui, owners in membership.items() if len(owners) > 1
    }
    nodes = sorted(
        (node for rxcui, node in all_nodes.items() if rxcui in surviving_ids),
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
