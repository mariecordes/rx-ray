import pytest

from apps.api.main import (
    DossierRequest,
    LabelEvidenceRequest,
    build_dossier,
    build_label_evidence,
    health_check,
)
from src.dossier.builder import DossierBuilder
from src.dossier.models import OpenFDALabelEvidence
from src.dossier.openfda_store import OpenFDALabelStore
from src.dossier.rxnorm_store import RxNormParquetStore


pytestmark = pytest.mark.skipif(
    not RxNormParquetStore().rxnconso_path.exists()
    or not RxNormParquetStore().rxnrel_path.exists(),
    reason="RxNorm parquet files are required for dossier API tests.",
)


def offline_builder() -> DossierBuilder:
    return DossierBuilder(
        rxnorm_store=RxNormParquetStore(),
        openfda_store=OpenFDALabelStore(allow_live=False, use_cache=False),
    )


@pytest.mark.asyncio
async def test_health_check() -> None:
    response = await health_check()

    assert response.status == "ok"
    assert response.version == "0.1.0"


@pytest.mark.asyncio
async def test_dossier_endpoint_success() -> None:
    response = await build_dossier(
        DossierRequest(drug="aspirin", max_edges=10),
        builder=offline_builder(),
    )

    assert response.resolved_drug is not None
    assert response.resolved_drug.rxcui == "1191"
    assert response.label_evidence is not None
    assert response.label_evidence.label_limit == 5
    assert response.label_evidence.labels_found == 0


@pytest.mark.asyncio
async def test_dossier_endpoint_unresolved_drug() -> None:
    response = await build_dossier(
        DossierRequest(drug="notarealdrugzzzz"),
        builder=offline_builder(),
    )

    assert response.resolved_drug is None
    assert response.notes == ["No RxNorm concept could be resolved for this query."]


@pytest.mark.asyncio
async def test_label_evidence_endpoint_uses_rxcui_and_fallback_name() -> None:
    class FakeOpenFDAStore:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str | None, int]] = []

        def get_label_evidence(
            self,
            rxcui: str,
            fallback_name: str | None = None,
            limit: int = 5,
        ) -> OpenFDALabelEvidence:
            self.calls.append((rxcui, fallback_name, limit))
            return OpenFDALabelEvidence(
                rxcui=rxcui,
                label_limit=limit,
                retrieval_mode="test",
            )

    fake_store = FakeOpenFDAStore()
    builder = DossierBuilder(
        rxnorm_store=RxNormParquetStore(),
        openfda_store=fake_store,  # type: ignore[arg-type]
    )

    response = await build_label_evidence(
        LabelEvidenceRequest(rxcui=" 123 ", name=" Example Drug ", limit=3),
        builder=builder,
    )

    assert response.rxcui == "123"
    assert response.label_limit == 3
    assert response.retrieval_mode == "test"
    assert fake_store.calls == [("123", "Example Drug", 3)]


@pytest.mark.asyncio
async def test_label_evidence_endpoint_offline_no_results() -> None:
    response = await build_label_evidence(
        LabelEvidenceRequest(rxcui="1191", name="aspirin"),
        builder=offline_builder(),
    )

    assert response.rxcui == "1191"
    assert response.labels_found == 0
    assert response.label_limit == 3
    assert response.retrieval_mode == "none"
    assert response.label_records == []
