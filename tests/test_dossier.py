from pathlib import Path

import pytest

from src.dossier.builder import DossierBuilder
from src.dossier.openfda_store import OpenFDALabelStore
from src.dossier.rxnorm_store import RxNormParquetStore


pytestmark = pytest.mark.skipif(
    not Path("data/01_raw/rxnconso_raw.parquet").exists()
    or not Path("data/01_raw/rxnrel_raw.parquet").exists(),
    reason="RxNorm parquet files are required for dossier integration tests.",
)


def test_rxnorm_resolves_aspirin() -> None:
    store = RxNormParquetStore()

    candidates = store.resolve("aspirin")

    assert candidates
    assert candidates[0].concept.rxcui == "1191"
    assert candidates[0].match_type == "exact"


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
