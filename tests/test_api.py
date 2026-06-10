import pytest

from apps.api.main import (
    DossierRequest,
    LabelEvidenceRequest,
    QueryAnswerRequest,
    QueryUnderstandingRequest,
    answer_query,
    build_dossier,
    build_label_evidence,
    configure_api_logging,
    health_check,
    understand_query,
)
from src.dossier.builder import DossierBuilder
from src.dossier.models import (
    DrugDossier,
    LabelSection,
    OpenFDALabelEvidence,
    OpenFDALabelRecord,
    RxNormConcept,
)
from src.dossier.openfda_store import OpenFDALabelStore
from src.dossier.rxnorm_store import RxNormParquetStore
from src.query_answer.config import QueryAnswerParameters
from src.query_answer.models import EvidenceAnswer
from src.query_answer.service import QueryAnswerService
from src.query_answer.synthesizer import (
    ANSWER_CITATION_RETRY_PROMPT_KEY,
    AnswerSynthesisResult,
    EvidenceAnswerSynthesizer,
    SOURCE_LINK_LIMITATION,
    STANDARD_SAFETY_NOTE,
)
from src.query_understanding.extractor import ExtractionResult, HybridQueryExtractor
from src.query_understanding.models import (
    ExtractedDrugMention,
    QueryState,
    QueryUnderstandingResponse,
)
from src.query_understanding.service import QueryUnderstandingService
from src.utils import load_parameters


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


@pytest.mark.asyncio
async def test_query_answer_returns_understanding_without_llm_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANSWER_SYNTHESIS_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANSWER_SYNTHESIS_OPENAI_MODEL", raising=False)

    response = await answer_query(
        QueryAnswerRequest(query="Can I take aspirin?", openfda_limit=2),
        builder=offline_builder(),
    )

    assert response.understanding.primary_dossier is not None
    assert response.answer is None
    assert any("not configured" in warning for warning in response.warnings)


@pytest.mark.asyncio
async def test_query_answer_unresolved_primary_returns_no_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANSWER_SYNTHESIS_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANSWER_SYNTHESIS_OPENAI_MODEL", raising=False)

    response = await answer_query(
        QueryAnswerRequest(query="Can I take notarealdrugzzzz?"),
        builder=offline_builder(),
    )

    assert response.understanding.primary_dossier is None
    assert response.answer is None
    assert any(
        "No primary drug could be resolved" in warning for warning in response.warnings
    )


def test_answer_synthesis_filters_citations_to_supplied_evidence() -> None:
    packet = EvidenceAnswerSynthesizer.build_evidence_packet(
        response_with_label_evidence()
    )
    answer = EvidenceAnswerSynthesizer.parse_answer_data(
        {
            "summary": "Retrieved label evidence mentions aspirin warnings.",
            "bullets": [
                {
                    "text": "The warning evidence comes from the supplied label.",
                    "citations": [
                        {
                            "source_id": "label-1",
                            "section": "warnings",
                            "snippet": "warning text",
                        },
                        {
                            "source_id": "made-up",
                            "section": "warnings",
                            "snippet": "invented",
                        },
                    ],
                }
            ],
            "limitations": ["Limited to retrieved public label text."],
            "safety_note": "Model-provided safety note should not be used.",
        },
        EvidenceAnswerSynthesizer.allowed_citations(packet),
    )

    assert [citation.model_dump() for citation in answer.bullets[0].citations] == [
        {
            "source_id": "label-1",
            "section": "warnings",
            "snippet": "warning text",
        }
    ]
    assert answer.safety_note == STANDARD_SAFETY_NOTE


def test_query_answer_parameters_load_from_yaml() -> None:
    parameters = load_parameters()

    assert parameters["query_answer"]["default_openfda_limit"] == 10
    assert parameters["query_answer"]["max_synthesis_retries"] == 1
    assert parameters["query_answer"]["require_citations_when_evidence_exists"] is True


def test_query_answer_request_uses_configured_default_label_limit() -> None:
    request = QueryAnswerRequest(query="Can I take aspirin?")

    assert request.openfda_limit == 10


def test_answer_citation_retry_prompt_template_loads() -> None:
    prompt_config = EvidenceAnswerSynthesizer._load_prompt_config(
        ANSWER_CITATION_RETRY_PROMPT_KEY
    )
    message = EvidenceAnswerSynthesizer._format_retry_message(
        {"bullets": []},
        {("label-1", "warnings")},
    )

    assert prompt_config["message"]["role"] == "user"
    assert message["role"] == "user"
    assert "Validation feedback" in message["content"]
    assert "label-1" in message["content"]
    assert "warnings" in message["content"]


def test_answer_synthesis_retries_when_sources_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANSWER_SYNTHESIS_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ANSWER_SYNTHESIS_OPENAI_MODEL", "test-model")
    calls: list[list[dict[str, str]]] = []
    responses = [
        {
            "summary": "Retrieved label evidence mentions aspirin warnings.",
            "bullets": [{"text": "A warning was found.", "citations": []}],
            "limitations": [],
        },
        {
            "summary": "Retrieved label evidence mentions aspirin warnings.",
            "bullets": [
                {
                    "text": "A warning was found.",
                    "citations": [
                        {
                            "source_id": "label-1",
                            "section": "warnings",
                            "snippet": "warning text",
                        }
                    ],
                }
            ],
            "limitations": [],
        },
    ]

    def fake_requester(
        *,
        messages: list[dict[str, str]],
        prompt_config: dict,
    ) -> dict:
        calls.append(messages)
        return responses.pop(0)

    synthesizer = EvidenceAnswerSynthesizer(
        parameters=QueryAnswerParameters(max_synthesis_retries=1),
        json_requester=fake_requester,
    )

    result = synthesizer.synthesize(
        "Can I take aspirin?",
        response_with_label_evidence(),
    )

    assert result.answer is not None
    assert len(calls) == 2
    assert "Validation feedback" in calls[1][-1]["content"]
    assert result.answer.bullets[0].citations[0].source_id == "label-1"
    assert SOURCE_LINK_LIMITATION not in result.answer.limitations


def test_answer_synthesis_adds_limitation_when_retry_still_has_no_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANSWER_SYNTHESIS_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ANSWER_SYNTHESIS_OPENAI_MODEL", "test-model")

    def fake_requester(
        *,
        messages: list[dict[str, str]],
        prompt_config: dict,
    ) -> dict:
        return {
            "summary": "Retrieved label evidence mentions aspirin warnings.",
            "bullets": [{"text": "A warning was found.", "citations": []}],
            "limitations": [],
        }

    synthesizer = EvidenceAnswerSynthesizer(
        parameters=QueryAnswerParameters(max_synthesis_retries=1),
        json_requester=fake_requester,
    )

    result = synthesizer.synthesize(
        "Can I take aspirin?",
        response_with_label_evidence(),
    )

    assert result.answer is not None
    assert SOURCE_LINK_LIMITATION in result.answer.limitations


def test_query_answer_response_includes_evidence_coverage() -> None:
    understanding = response_with_label_evidence()
    service = QueryAnswerService(
        builder=offline_builder(),
        understanding_service=FakeUnderstandingService(understanding),
        synthesizer=FakeAnswerSynthesizer(),
    )

    response = service.answer("Can I take aspirin?")

    assert response.coverage.summary_counts["addressed"] >= 1
    assert any(
        item.category == "primary_drug"
        and item.label == "aspirin"
        and item.status == "addressed"
        for item in response.coverage.items
    )


def test_evidence_coverage_marks_secondary_and_context_gaps() -> None:
    understanding = response_with_label_evidence().model_copy(
        update={
            "query": "Can I take aspirin with ibuprofen while pregnant?",
            "state": QueryState(
                primary_drug="aspirin",
                all_drugs_mentioned=["aspirin", "ibuprofen"],
                current_medications=["ibuprofen"],
                conditions=["migraine"],
                patient_context=["pregnant"],
                intent="drug_safety_question",
            ),
        }
    )
    service = QueryAnswerService(
        builder=offline_builder(),
        understanding_service=FakeUnderstandingService(understanding),
        synthesizer=FakeAnswerSynthesizer(),
    )

    response = service.answer("Can I take aspirin with ibuprofen while pregnant?")

    coverage_by_label = {item.label: item for item in response.coverage.items}
    assert coverage_by_label["ibuprofen"].status == "not_found_in_evidence"
    assert any(
        item.category == "mentioned_drug"
        and item.label == "ibuprofen"
        and item.status == "not_retrieved"
        for item in response.coverage.items
    )
    assert coverage_by_label["migraine"].status == "not_found_in_evidence"
    assert coverage_by_label["pregnant"].status == "not_found_in_evidence"
    assert response.answer is not None
    assert any(
        "additional mentioned medications" in item
        for item in response.answer.limitations
    )
    assert any("ibuprofen" in item for item in response.answer.limitations)


class FakeUnderstandingService:
    def __init__(self, response: QueryUnderstandingResponse) -> None:
        self.response = response

    def understand(
        self,
        query: str,
        openfda_limit: int | None = None,
    ) -> QueryUnderstandingResponse:
        return self.response


class FakeAnswerSynthesizer:
    def synthesize(
        self,
        query: str,
        understanding: QueryUnderstandingResponse,
    ) -> AnswerSynthesisResult:
        return AnswerSynthesisResult(
            answer=EvidenceAnswer(
                summary="Retrieved evidence mentions aspirin warnings.",
                bullets=[],
                limitations=[],
                safety_note=STANDARD_SAFETY_NOTE,
            )
        )


def response_with_label_evidence() -> "QueryUnderstandingResponse":
    return QueryUnderstandingResponse(
        query="Can I take aspirin?",
        state=QueryState(primary_drug="aspirin", all_drugs_mentioned=["aspirin"]),
        primary_dossier=DrugDossier(
            query="aspirin",
            resolved_drug=RxNormConcept(rxcui="1191", name="aspirin", tty="IN"),
            label_evidence=OpenFDALabelEvidence(
                rxcui="1191",
                labels_found=1,
                label_limit=1,
                label_records=[
                    OpenFDALabelRecord(
                        source_id="label-1",
                        brand_names=["Aspirin"],
                        generic_names=["ASPIRIN"],
                    )
                ],
                sections={
                    "warnings": [
                        LabelSection(
                            section="warnings",
                            text="Aspirin warning text.",
                            source_id="label-1",
                        )
                    ]
                },
            ),
        ),
    )


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
