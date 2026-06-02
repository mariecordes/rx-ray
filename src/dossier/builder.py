from __future__ import annotations

from src.dossier.models import DrugDossier, OpenFDALabelEvidence
from src.dossier.openfda_store import OpenFDALabelStore
from src.dossier.rxnorm_store import RxNormParquetStore


class DossierBuilder:
    """Assemble a request-time drug dossier from RxNorm and OpenFDA."""

    def __init__(
        self,
        rxnorm_store: RxNormParquetStore | None = None,
        openfda_store: OpenFDALabelStore | None = None,
    ) -> None:
        self.rxnorm_store = rxnorm_store or RxNormParquetStore()
        self.openfda_store = openfda_store or OpenFDALabelStore()

    def build(
        self,
        drug_name: str,
        depth: int = 1,
        max_edges: int = 75,
        include_openfda: bool = True,
        openfda_limit: int = 5,
    ) -> DrugDossier:
        candidates = self.rxnorm_store.resolve(drug_name)
        if not candidates:
            return DrugDossier(
                query=drug_name,
                notes=["No RxNorm concept could be resolved for this query."],
            )

        resolved = candidates[0].concept
        neighborhood = self.rxnorm_store.get_neighborhood(
            resolved.rxcui,
            depth=depth,
            max_edges=max_edges,
        )

        label_evidence: OpenFDALabelEvidence | None = None
        if include_openfda:
            label_evidence = self.openfda_store.get_label_evidence(
                resolved.rxcui,
                fallback_name=resolved.name,
                limit=openfda_limit,
            )

        notes = [
            "Educational prototype output. It summarizes public data and is "
            "not medical advice."
        ]
        if neighborhood.truncated:
            notes.append(
                "RxNorm neighborhood was truncated to keep the dossier compact."
            )
        if label_evidence and label_evidence.labels_found == 0:
            notes.append(
                "No OpenFDA label evidence was retrieved for the resolved RXCUI."
            )

        return DrugDossier(
            query=drug_name,
            resolved_drug=resolved,
            resolution_candidates=candidates,
            rxnorm_neighborhood=neighborhood,
            label_evidence=label_evidence,
            notes=notes,
        )
