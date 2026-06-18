from pathlib import Path
from unittest.mock import patch

import pytest
import requests

from src.dossier.builder import DossierBuilder
from src.dossier.openfda_store import OpenFDALabelStore
from src.dossier.rxnorm_store import RxNormParquetStore


def _rxnorm_data_available() -> bool:
    try:
        store = RxNormParquetStore()
    except FileNotFoundError:
        return False
    return store.rxnconso_path.exists() and store.rxnrel_path.exists()


pytestmark = pytest.mark.skipif(
    not _rxnorm_data_available(),
    reason="RxNorm parquet files are required for dossier integration tests.",
)


def test_rxnorm_resolves_aspirin() -> None:
    store = RxNormParquetStore()

    candidates = store.resolve("aspirin")

    assert candidates
    assert candidates[0].concept.rxcui == "1191"
    assert candidates[0].match_type == "exact"


def test_resolve_returns_preferred_concept_not_matched_synonym() -> None:
    store = RxNormParquetStore()

    # "cream" exact-matches an SPL active-substance synonym (TTY SU) of
    # RXCUI 1305763, but the concept's preferred RxNorm term is the
    # ingredient "milk fat, cow" (TTY IN).
    cream = store.resolve("cream", limit=1)
    assert cream
    assert cream[0].concept.rxcui == "1305763"
    assert cream[0].concept.tty == "IN"
    assert cream[0].match_type == "exact"

    # "tretinoin cream" matches an SPL drug-product synonym (TTY DP) but should
    # display the clean RXNORM Semantic Clinical Drug name, not the synonym.
    cream_drug = store.resolve("tretinoin cream", limit=1)
    assert cream_drug
    assert cream_drug[0].concept.rxcui == "198300"
    assert cream_drug[0].concept.tty == "SCD"


def test_builds_offline_rxnorm_dossier() -> None:
    builder = DossierBuilder(
        rxnorm_store=RxNormParquetStore(),
        openfda_store=OpenFDALabelStore(allow_live=False, use_cache=False),
    )

    dossier = builder.build("aspirin", include_openfda=True, max_edges=20)

    assert dossier.resolved_drug is not None
    assert dossier.resolved_drug.rxcui == "1191"
    assert dossier.rxnorm_neighborhood.nodes
    assert dossier.label_evidence is not None
    assert dossier.label_evidence.labels_found == 0
    assert dossier.label_evidence.label_limit == 5


def test_openfda_section_normalization() -> None:
    store = OpenFDALabelStore(allow_live=False)

    evidence = store._normalize_labels(
        "1191",
        [
            {
                "id": "label-1",
                "set_id": "label-set-1",
                "effective_time": "20250101",
                "openfda": {
                    "brand_name": ["Example Aspirin"],
                    "generic_name": ["aspirin"],
                    "manufacturer_name": ["Example Manufacturer"],
                    "spl_id": ["spl-1"],
                    "spl_set_id": ["spl-set-1"],
                },
                "warnings_and_precautions": ["Warning text"],
                "drug_interactions": ["Interaction text"],
                "pregnancy": ["Pregnancy text"],
            }
        ],
        retrieval_mode="test",
        label_limit=5,
    )

    assert evidence.labels_found == 1
    assert evidence.label_limit == 5
    assert evidence.section_flags["has_warnings"]
    assert evidence.section_flags["has_drug_interactions"]
    assert evidence.section_flags["has_pregnancy"]
    assert evidence.sections["warnings"][0].text == "Warning text"
    assert evidence.sections["warnings"][0].source_id == "label-1"
    assert evidence.label_records[0].source_id == "label-1"
    assert evidence.label_records[0].id == "label-1"
    assert evidence.label_records[0].set_id == "label-set-1"
    assert evidence.label_records[0].spl_ids == ["spl-1"]
    assert evidence.label_records[0].spl_set_ids == ["spl-set-1"]
    assert evidence.label_records[0].brand_names == ["Example Aspirin"]
    assert evidence.summary_metadata["label_ids"] == ["label-1"]
    assert evidence.summary_metadata["label_set_ids"] == ["label-set-1"]
    assert evidence.summary_metadata["spl_ids"] == ["spl-1"]
    assert evidence.summary_metadata["spl_set_ids"] == ["spl-set-1"]


def label_fixture(label_id: str) -> dict[str, object]:
    return {
        "id": label_id,
        "set_id": f"{label_id}-set",
        "openfda": {
            "brand_name": [f"Brand {label_id}"],
            "generic_name": ["aspirin"],
            "manufacturer_name": [f"Manufacturer {label_id}"],
        },
        "warnings": [f"Warning text {label_id}"],
    }


def test_openfda_cache_refreshes_when_cached_labels_are_below_limit(
    tmp_path: Path,
) -> None:
    class RefreshingOpenFDAStore(OpenFDALabelStore):
        def __init__(self) -> None:
            super().__init__(cache_dir=tmp_path, use_cache=True, allow_live=True)
            self.queries: list[tuple[str, int]] = []

        def _query(self, search: str, limit: int) -> list[dict[str, object]]:
            self.queries.append((search, limit))
            return [label_fixture(f"live-{index}") for index in range(limit)]

    store = RefreshingOpenFDAStore()
    store._write_cache("1191", [label_fixture(f"cached-{index}") for index in range(5)])

    evidence = store.get_label_evidence("1191", fallback_name="aspirin", limit=10)

    assert evidence.retrieval_mode == "live_rxcui"
    assert evidence.labels_found == 10
    assert evidence.label_limit == 10
    assert store.queries == [("openfda.rxcui:1191", 10)]
    assert len(store._read_cache("1191") or []) == 10


def test_openfda_cache_is_sliced_to_requested_limit(tmp_path: Path) -> None:
    class CachedOpenFDAStore(OpenFDALabelStore):
        def __init__(self) -> None:
            super().__init__(cache_dir=tmp_path, use_cache=True, allow_live=True)

        def _query(self, search: str, limit: int) -> list[dict[str, object]]:
            raise AssertionError("Cache should satisfy this request.")

    store = CachedOpenFDAStore()
    store._write_cache(
        "1191",
        [label_fixture(f"cached-{index}") for index in range(10)],
    )

    evidence = store.get_label_evidence("1191", fallback_name="aspirin", limit=5)

    assert evidence.retrieval_mode == "cache"
    assert evidence.labels_found == 5
    assert evidence.label_limit == 5
    assert [record.id for record in evidence.label_records] == [
        f"cached-{index}" for index in range(5)
    ]


def test_openfda_interaction_lookup_targets_drug_interactions() -> None:
    class InteractionOpenFDAStore(OpenFDALabelStore):
        def __init__(self) -> None:
            super().__init__(use_cache=False, allow_live=True)
            self.queries: list[tuple[str, int]] = []

        def _query(self, search: str, limit: int) -> list[dict[str, object]]:
            self.queries.append((search, limit))
            if search.startswith("openfda.rxcui:1191"):
                return []
            return [
                {
                    **label_fixture("interaction-label"),
                    "drug_interactions": ["Aspirin interaction text."],
                }
            ]

    store = InteractionOpenFDAStore()

    evidence = store.get_interaction_label_evidence(
        "1191",
        interaction_name="ibuprofen",
        fallback_name="aspirin",
        limit=3,
    )

    assert evidence.retrieval_mode == "interaction_targeted_lookup"
    assert evidence.labels_found == 1
    assert store.queries == [
        ("openfda.rxcui:1191 AND drug_interactions:ibuprofen", 3),
        ("openfda.generic_name:aspirin AND drug_interactions:ibuprofen", 3),
    ]


def test_openfda_interaction_lookup_falls_back_after_strict_query_error(
) -> None:
    class InteractionFallbackOpenFDAStore(OpenFDALabelStore):
        def __init__(self) -> None:
            super().__init__(use_cache=False, allow_live=True)
            self.queries: list[tuple[str, int]] = []

        def _query(self, search: str, limit: int) -> list[dict[str, object]]:
            self.queries.append((search, limit))
            if search.startswith("openfda.rxcui:1418"):
                raise requests.HTTPError("500 Server Error")
            return [
                {
                    **label_fixture("interaction-label"),
                    "drug_interactions": ["Benzoyl peroxide interaction text."],
                }
            ]

    store = InteractionFallbackOpenFDAStore()

    with patch("src.dossier.openfda_store.logger.warning") as warning:
        evidence = store.get_interaction_label_evidence(
            "1418",
            interaction_name="tretinoin",
            fallback_name="benzoyl peroxide",
            limit=3,
        )

    assert evidence.retrieval_mode == "interaction_targeted_lookup"
    assert evidence.labels_found == 1
    assert evidence.errors == []
    warning.assert_called_once()
    assert "OpenFDA interaction lookup recovered" in warning.call_args.args[0]
    assert store.queries == [
        ("openfda.rxcui:1418 AND drug_interactions:tretinoin", 3),
        (
            "openfda.generic_name:benzoyl peroxide "
            "AND drug_interactions:tretinoin",
            3,
        ),
    ]


def test_openfda_context_lookup_searches_target_fields() -> None:
    class ContextOpenFDAStore(OpenFDALabelStore):
        def __init__(self) -> None:
            super().__init__(use_cache=False, allow_live=True)
            self.queries: list[tuple[str, int]] = []

        def _query(self, search: str, limit: int) -> list[dict[str, object]]:
            self.queries.append((search, limit))
            if search.startswith("openfda.rxcui:9033"):
                return []
            return [
                {
                    **label_fixture("context-label"),
                    "indications_and_usage": ["Tretinoin label mentions acne."],
                }
            ]

    store = ContextOpenFDAStore()

    evidence = store.get_context_label_evidence(
        "9033",
        target="acne",
        section_fields=["indications_and_usage", "warnings"],
        fallback_name="tretinoin",
        limit=3,
    )

    assert evidence.retrieval_mode == "context_targeted_lookup"
    assert evidence.labels_found == 1
    assert "indications_and_usage" in evidence.sections
    assert store.queries == [
        ("openfda.rxcui:9033 AND indications_and_usage:acne", 3),
        ("openfda.generic_name:tretinoin AND indications_and_usage:acne", 3),
        ("openfda.rxcui:9033 AND warnings:acne", 3),
        ("openfda.generic_name:tretinoin AND warnings:acne", 3),
    ]
