import pytest

from apps.api.main import (
    DossierRequest,
    LabelEvidenceRequest,
    QueryUnderstandingRequest,
    build_dossier,
    build_label_evidence,
    configure_api_logging,
    health_check,
    understand_query,
)
from src.dossier.builder import DossierBuilder
from src.dossier.models import OpenFDALabelEvidence
from src.dossier.openfda_store import OpenFDALabelStore
from src.dossier.rxnorm_store import RxNormParquetStore
from src.query_understanding.extractor import ExtractionResult, HybridQueryExtractor
from src.query_understanding.models import ExtractedDrugMention, QueryState
from src.query_understanding.service import QueryUnderstandingService


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


def test_api_logging_setup_is_idempotent() -> None:
    configure_api_logging()
    configure_api_logging()

    import logging

    logger = logging.getLogger("src.query_understanding")
    rx_ray_handlers = [
        handler
        for handler in logger.handlers
        if getattr(handler, "_rx_ray_api_handler", False)
    ]

    assert logger.level == logging.INFO
    assert len(rx_ray_handlers) == 1


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


@pytest.mark.asyncio
async def test_query_understanding_extracts_state_and_primary_dossier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QUERY_EXTRACTION_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("QUERY_EXTRACTION_OPENAI_MODEL", raising=False)

    response = await understand_query(
        QueryUnderstandingRequest(
            query=(
                "I take ibuprofen for migraine and want to use tretinoin for "
                "acne. I am pregnant."
            ),
            openfda_limit=2,
        ),
        builder=offline_builder(),
    )

    assert response.extraction_mode == "deterministic"
    assert response.state.primary_drug == "tretinoin"
    assert response.state.all_drugs_mentioned == ["ibuprofen", "tretinoin"]
    assert response.state.current_medications == ["ibuprofen"]
    assert "migraine" in response.state.conditions
    assert "acne" in response.state.conditions
    assert "pregnancy" in response.state.patient_context
    assert response.primary_dossier is not None
    assert response.primary_dossier.resolved_drug is not None
    assert response.primary_dossier.resolved_drug.name == "tretinoin"
    assert any(
        mention.text == "ibuprofen" and mention.role == "current_medication"
        for mention in response.resolved_drugs
    )
    assert response.secondary_label_evidence


@pytest.mark.asyncio
async def test_query_understanding_allergy_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QUERY_EXTRACTION_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("QUERY_EXTRACTION_OPENAI_MODEL", raising=False)

    response = await understand_query(
        QueryUnderstandingRequest(
            query="I am allergic to aspirin and currently taking ibuprofen.",
        ),
        builder=offline_builder(),
    )

    assert response.state.allergies == ["aspirin"]
    assert response.state.current_medications == ["ibuprofen"]
    assert any(
        mention.text == "aspirin" and mention.role == "allergy"
        for mention in response.resolved_drugs
    )


@pytest.mark.asyncio
async def test_query_understanding_child_question_uses_drug_not_patient_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QUERY_EXTRACTION_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("QUERY_EXTRACTION_OPENAI_MODEL", raising=False)

    response = await understand_query(
        QueryUnderstandingRequest(query="Can a child take aspirin?"),
        builder=offline_builder(),
    )

    assert response.state.primary_drug == "aspirin"
    assert response.state.all_drugs_mentioned == ["aspirin"]
    assert "child" in response.state.patient_context
    assert response.primary_dossier is not None
    assert response.primary_dossier.resolved_drug is not None
    assert response.primary_dossier.resolved_drug.name == "aspirin"


@pytest.mark.asyncio
async def test_query_understanding_hypothetical_drug_is_not_current_medication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QUERY_EXTRACTION_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("QUERY_EXTRACTION_OPENAI_MODEL", raising=False)

    response = await understand_query(
        QueryUnderstandingRequest(
            query="Can I take aspirin if I have an allergy against ibuprofen?"
        ),
        builder=offline_builder(),
    )

    assert response.state.primary_drug == "aspirin"
    assert response.state.current_medications == []
    assert response.state.allergies == ["ibuprofen"]
    assert not any("ibuprofen against" in warning for warning in response.warnings)


@pytest.mark.asyncio
async def test_query_understanding_repairs_unresolved_mentions_with_llm_feedback(
) -> None:
    class FakeRepairingExtractor:
        def __init__(self) -> None:
            self.feedback: dict | None = None

        def extract(self, query: str) -> ExtractionResult:
            return ExtractionResult(
                state=QueryState(primary_drug="aspirin"),
                mentions=[
                    ExtractedDrugMention(text="aspirin", role="primary_drug"),
                    ExtractedDrugMention(
                        text="ibuprofen against",
                        role="mentioned_drug",
                    ),
                ],
            )

        def revise_with_resolution_feedback(
            self,
            query: str,
            extraction: ExtractionResult,
            resolution_feedback: dict,
        ) -> ExtractionResult:
            self.feedback = resolution_feedback
            return ExtractionResult(
                state=QueryState(
                    primary_drug="ASA",
                    all_drugs_mentioned=["ASA", "ibuprofen"],
                    allergies=["ibuprofen"],
                ),
                mentions=[
                    ExtractedDrugMention(text="aspirin", role="primary_drug"),
                    ExtractedDrugMention(text="ibuprofen", role="allergy"),
                ],
                mode="hybrid",
            )

    fake_extractor = FakeRepairingExtractor()
    service = QueryUnderstandingService(
        builder=offline_builder(),
        extractor=fake_extractor,  # type: ignore[arg-type]
    )

    response = service.understand(
        "Can I take aspirin if I have an allergy against ibuprofen?"
    )

    assert response.extraction_mode == "hybrid"
    assert response.state.primary_drug == "ASA"
    assert response.state.all_drugs_mentioned == ["ASA", "ibuprofen"]
    assert response.state.allergies == ["ibuprofen"]
    assert response.primary_dossier is not None
    assert response.primary_dossier.resolved_drug is not None
    assert response.primary_dossier.resolved_drug.name == "aspirin"
    assert not any("ibuprofen against" in warning for warning in response.warnings)
    assert fake_extractor.feedback is not None
    assert fake_extractor.feedback["unresolved_drug_like_mentions"] == [
        "ibuprofen against"
    ]


def test_query_understanding_preserves_llm_cleaned_drug_list() -> None:
    class FakeCleanExtractor:
        def extract(self, query: str) -> ExtractionResult:
            return ExtractionResult(
                state=QueryState(
                    primary_drug="aspirin",
                    all_drugs_mentioned=["aspirin", "ibuprofen"],
                    conditions=["asthma", "migraine"],
                ),
                mentions=[
                    ExtractedDrugMention(text="aspirin", role="primary_drug"),
                    ExtractedDrugMention(text="ibuprofen", role="mentioned_drug"),
                ],
                mode="hybrid",
            )

        def revise_with_resolution_feedback(
            self,
            query: str,
            extraction: ExtractionResult,
            resolution_feedback: dict,
        ) -> ExtractionResult | None:
            return None

    service = QueryUnderstandingService(
        builder=offline_builder(),
        extractor=FakeCleanExtractor(),  # type: ignore[arg-type]
    )

    response = service.understand(
        "i have asthma but a migraine. can i take aspirin or ibuprofin?"
    )

    assert response.extraction_mode == "hybrid"
    assert response.state.all_drugs_mentioned == ["aspirin", "ibuprofen"]
    assert "asthma" not in response.state.all_drugs_mentioned
    assert "but" not in response.state.all_drugs_mentioned


def test_query_understanding_does_not_rewrite_hybrid_state_parameters() -> None:
    class FakeHybridExtractor:
        def extract(self, query: str) -> ExtractionResult:
            return ExtractionResult(
                state=QueryState(
                    primary_drug="ASA",
                    all_drugs_mentioned=["ASA"],
                    current_medications=["home aspirin phrase"],
                    allergies=["ibuprofen allergy phrase"],
                    conditions=["custom condition"],
                    patient_context=["custom patient context"],
                    intent="custom intent",
                ),
                mentions=[
                    ExtractedDrugMention(text="aspirin", role="primary_drug"),
                    ExtractedDrugMention(text="ibuprofen", role="allergy"),
                ],
                mode="hybrid",
            )

        def revise_with_resolution_feedback(
            self,
            query: str,
            extraction: ExtractionResult,
            resolution_feedback: dict,
        ) -> ExtractionResult | None:
            return None

    service = QueryUnderstandingService(
        builder=offline_builder(),
        extractor=FakeHybridExtractor(),  # type: ignore[arg-type]
    )

    response = service.understand("Can I take aspirin with an ibuprofen allergy?")

    assert response.state.primary_drug == "ASA"
    assert response.state.all_drugs_mentioned == ["ASA"]
    assert response.state.current_medications == ["home aspirin phrase"]
    assert response.state.allergies == ["ibuprofen allergy phrase"]
    assert response.state.conditions == ["custom condition"]
    assert response.state.patient_context == ["custom patient context"]
    assert response.state.intent == "custom intent"
    assert response.primary_dossier is not None


@pytest.mark.asyncio
async def test_query_understanding_unresolved_query_returns_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QUERY_EXTRACTION_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("QUERY_EXTRACTION_OPENAI_MODEL", raising=False)

    response = await understand_query(
        QueryUnderstandingRequest(query="Can I take notarealdrugzzzz?"),
        builder=offline_builder(),
    )

    assert response.primary_dossier is None
    assert response.warnings
    assert "No primary drug could be resolved" in response.warnings[0]


def test_rxnorm_resolver_handles_punctuation_variation() -> None:
    candidates = RxNormParquetStore().resolve("ibu-profen")

    assert candidates
    assert candidates[0].concept.name == "ibuprofen"
    assert candidates[0].match_type in {"compact_exact", "normalized_exact"}


def test_query_extraction_prompt_template_loads() -> None:
    prompt_config = HybridQueryExtractor._load_revision_prompt()
    messages = HybridQueryExtractor._format_messages(
        prompt_config["messages"],
        query="Can a child take aspirin?",
        deterministic_extraction='{"state": {}}',
    )

    assert prompt_config["response_format"] == {"type": "json_object"}
    assert messages[0]["role"] == "system"
    assert "create the corrected extraction from scratch" in messages[0]["content"]
    assert "Can a child take aspirin?" in messages[1]["content"]
    assert '{"state": {}}' in messages[1]["content"]


def test_query_extraction_splits_packed_list_items() -> None:
    parsed = HybridQueryExtractor._string_list(
        ["adult, breastfeeding", "penicillin; latex", "adult"]
    )

    assert parsed == ["adult", "breastfeeding", "penicillin", "latex"]


def test_query_extraction_extracts_multiple_patient_context_items() -> None:
    result = HybridQueryExtractor()._extract_deterministic(
        "Can a breastfeeding 30-year-old woman take aspirin?"
    )

    assert result.state.patient_context == ["breastfeeding", "female", "adult"]
