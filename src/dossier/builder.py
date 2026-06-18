from __future__ import annotations

from src.dossier.label_fallback import (
    merge_ingredient_label_evidence,
    tag_label_evidence,
)
from src.dossier.models import (
    DrugDossier,
    IngredientFallbackEvidence,
    OpenFDALabelEvidence,
    RxNormConcept,
)
from src.dossier.openfda_store import OpenFDALabelStore
from src.dossier.rxnorm_store import INGREDIENT_TTYS, RxNormParquetStore

INGREDIENT_FALLBACK_TAG = "ingredient_fallback"


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
        label_evidence_scope = "concept"
        ingredient_fallback: list[IngredientFallbackEvidence] = []
        if include_openfda:
            label_evidence = self.openfda_store.get_label_evidence(
                resolved.rxcui,
                fallback_name=resolved.name,
                limit=openfda_limit,
            )
            if label_evidence.labels_found == 0:
                ingredient_fallback = self._ingredient_fallback_evidence(
                    resolved,
                    openfda_limit=openfda_limit,
                )
                if ingredient_fallback:
                    label_evidence = merge_ingredient_label_evidence(
                        resolved.rxcui,
                        [item.label_evidence for item in ingredient_fallback],
                        label_limit=openfda_limit,
                    )
                    label_evidence_scope = "ingredient_fallback"

        notes = [
            "Educational prototype output. It summarizes public data and is "
            "not medical advice."
        ]
        if neighborhood.truncated:
            notes.append(
                "RxNorm neighborhood was truncated to keep the dossier compact."
            )
        if label_evidence_scope == "ingredient_fallback":
            ingredient_names = ", ".join(
                item.ingredient.name for item in ingredient_fallback
            )
            notes.append(
                f"No product-specific labels were found for {resolved.name}. "
                f"Showing labels for its active ingredient"
                f"{'s' if len(ingredient_fallback) != 1 else ''} "
                f"({ingredient_names}), which may describe other formulations."
            )
        elif label_evidence and label_evidence.labels_found == 0:
            notes.append(
                "No OpenFDA label evidence was retrieved for the resolved RXCUI."
            )

        return DrugDossier(
            query=drug_name,
            resolved_drug=resolved,
            resolution_candidates=candidates,
            rxnorm_neighborhood=neighborhood,
            label_evidence=label_evidence,
            label_evidence_scope=label_evidence_scope,
            ingredient_fallback=ingredient_fallback,
            notes=notes,
        )

    def _ingredient_fallback_evidence(
        self,
        resolved: RxNormConcept,
        *,
        openfda_limit: int,
    ) -> list[IngredientFallbackEvidence]:
        """Retrieve label evidence for the resolved concept's active ingredient(s).

        Only ingredients that actually return labels are kept, so the broadening
        is surfaced only when it produces real evidence.
        """

        if (resolved.tty or "") in INGREDIENT_TTYS:
            return []

        fallback: list[IngredientFallbackEvidence] = []
        for ingredient in self.rxnorm_store.get_ingredient_concepts(resolved.rxcui):
            evidence = self.openfda_store.get_label_evidence(
                ingredient.rxcui,
                fallback_name=ingredient.name,
                limit=openfda_limit,
            )
            if not evidence.labels_found:
                continue
            fallback.append(
                IngredientFallbackEvidence(
                    ingredient=ingredient,
                    label_evidence=tag_label_evidence(
                        evidence,
                        INGREDIENT_FALLBACK_TAG,
                    ),
                )
            )
        return fallback
