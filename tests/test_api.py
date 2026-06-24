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
    IngredientFallbackEvidence,
    LabelSection,
    OpenFDALabelEvidence,
    OpenFDALabelRecord,
    RxNormConcept,
    RxNormEdge,
    RxNormNeighborhood,
)
from src.dossier.openfda_store import OpenFDALabelStore
from src.dossier.rxnorm_store import RxNormParquetStore
from src.query_answer.config import QueryAnswerParameters
from src.query_answer.contract import build_answer_contract
from src.query_answer.coverage import (
    build_evidence_coverage,
    evidence_snippet,
)
from src.query_answer.evidence_map import build_question_evidence_map
from src.query_answer.models import (
    AnswerContract,
    AnswerContractItem,
    ContextTargetedEvidence,
    EvidenceAnswer,
    EvidenceBullet,
    EvidenceCitation,
    RxNormPairContext,
    SecondaryDrugEvidence,
)
from src.query_answer.validation import validate_and_enforce
from src.query_answer.context import (
    build_context_targeted_evidence,
    select_context_targets,
)
from src.query_answer.network import build_question_rxnorm_network
from src.query_answer.secondary import build_secondary_evidence
from src.query_answer.service import QueryAnswerService
from src.query_answer.synthesizer import (
    ANSWER_CITATION_RETRY_PROMPT_KEY,
    MAX_LABEL_SECTIONS,
    MAX_SECTION_ENTRIES,
    AnswerSynthesisResult,
    EvidenceAnswerSynthesizer,
    SOURCE_LINK_LIMITATION,
    STANDARD_SAFETY_NOTE,
    label_section_payloads,
)
from src.query_understanding.extractor import ExtractionResult, HybridQueryExtractor
from src.query_understanding.models import (
    ExtractedDrugMention,
    QueryState,
    QueryUnderstandingResponse,
    ResolvedDrugMention,
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
async def test_query_understanding_does_not_extract_allergy_as_condition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QUERY_EXTRACTION_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("QUERY_EXTRACTION_OPENAI_MODEL", raising=False)

    response = await understand_query(
        QueryUnderstandingRequest(
            query=(
                "I currently take cetirizine for my pollen allergy. can i take "
                "both ibuprofen and aspirin against swollen eyes?"
            ),
            openfda_limit=1,
        ),
        builder=offline_builder(),
    )

    assert response.state.allergies == ["pollen"]
    assert "allergy" not in response.state.conditions
    assert "allergy" not in response.state.patient_context


@pytest.mark.asyncio
async def test_query_understanding_allergy_not_swallowed_by_earlier_determiner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QUERY_EXTRACTION_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("QUERY_EXTRACTION_OPENAI_MODEL", raising=False)

    response = await understand_query(
        QueryUnderstandingRequest(
            query="Can I use a tretinoin cream if I have a CLINDAMYCIN allergy?",
            openfda_limit=1,
        ),
        builder=offline_builder(),
    )

    # The determiner in "a tretinoin cream" must not swallow the allergen span;
    # the real allergen is clindamycin, and tretinoin cream stays the primary.
    assert response.state.allergies == ["CLINDAMYCIN"]
    assert response.state.primary_drug == "tretinoin cream"
    assert any(
        mention.role == "allergy"
        and mention.selected_concept is not None
        and mention.selected_concept.rxcui == "2582"
        for mention in response.resolved_drugs
    )


@pytest.mark.asyncio
async def test_query_understanding_drops_dosage_form_false_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QUERY_EXTRACTION_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("QUERY_EXTRACTION_OPENAI_MODEL", raising=False)

    response = await understand_query(
        QueryUnderstandingRequest(
            query="Can I use a tretinoin cream if I have a CLINDAMYCIN allergy?",
            openfda_limit=1,
        ),
        builder=offline_builder(),
    )

    resolved_texts = {mention.text.casefold() for mention in response.resolved_drugs}
    # The bare dosage-form word "cream" must not become a resolved drug mention.
    assert "cream" not in resolved_texts

    resolved_rxcuis = {
        mention.selected_concept.rxcui
        for mention in response.resolved_drugs
        if mention.selected_concept
    }
    # "cream" exact-matched RXCUI 1305763 ("milk fat, cow") — a false positive.
    assert "1305763" not in resolved_rxcuis
    # The real ingredient and the mentioned drug still resolve.
    assert "10753" in resolved_rxcuis  # tretinoin (IN)
    assert "2582" in resolved_rxcuis  # clindamycin (IN)


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
    assert response.state.intents == ["custom intent"]
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
        response_with_label_evidence(),
        secondary_evidence=[secondary_evidence_fixture()],
    )
    answer = EvidenceAnswerSynthesizer.parse_answer_data(
        {
            "response": "Retrieved labels raise caution about the question.",
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
                        {
                            "source_id": "label-2",
                            "section": "warnings",
                            "snippet": None,
                        },
                    ],
                }
            ],
            "limitations": ["Limited to retrieved public label text."],
            "safety_note": "Model-provided safety note should not be used.",
        },
        EvidenceAnswerSynthesizer.allowed_citations(packet),
    )

    assert answer.response == "Retrieved labels raise caution about the question."
    assert [citation.model_dump() for citation in answer.bullets[0].citations] == [
        {
            "source_id": "label-1",
            "section": "warnings",
            "snippet": "warning text",
            "support_status": None,
        },
        {
            "source_id": "label-2",
            "section": "warnings",
            "snippet": None,
            "support_status": None,
        },
    ]
    assert answer.safety_note == STANDARD_SAFETY_NOTE


def test_query_answer_parameters_load_from_yaml() -> None:
    parameters = load_parameters()

    assert parameters["query_answer"]["default_openfda_limit"] == 10
    assert parameters["query_answer"]["secondary_openfda_limit"] == 3
    assert parameters["query_answer"]["max_secondary_drugs"] == 3
    assert parameters["query_answer"]["interaction_lookup_limit"] == 3
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


def test_evidence_packet_includes_secondary_evidence() -> None:
    packet = EvidenceAnswerSynthesizer.build_evidence_packet(
        response_with_label_evidence(),
        secondary_evidence=[secondary_evidence_fixture()],
    )

    assert packet["secondary_drug_evidence"][0]["resolved_concept"]["name"] == (
        "ibuprofen"
    )
    assert any(
        section["source_id"] == "label-2"
        and section["evidence_scope"] == "secondary"
        for section in packet["label_sections"]
    )
    assert ("label-2", "warnings") in EvidenceAnswerSynthesizer.allowed_citations(
        packet
    )


def _label_sections(count: int, *, section: str) -> dict:
    return {
        section: [
            LabelSection(
                section=section,
                text=f"Distinct {section} text for record {index}.",
                source_id=f"{section}-{index}",
            )
            for index in range(count)
        ]
    }


def test_label_section_payloads_caps_entries_per_section() -> None:
    sections = _label_sections(13, section="warnings")

    payloads = label_section_payloads(sections, evidence_scope="primary")

    assert len(payloads) == MAX_SECTION_ENTRIES


def test_label_section_payloads_deduplicates_near_identical_boilerplate() -> None:
    sections = {
        "warnings": [
            LabelSection(
                section="warnings",
                text="Allergy alert: this drug may cause a severe allergic reaction.",
                source_id=f"warnings-{index}",
            )
            for index in range(5)
        ]
        + [
            LabelSection(
                section="warnings",
                text="Cardiovascular thrombotic events have been reported.",
                source_id="warnings-distinct",
            )
        ]
    }

    payloads = label_section_payloads(sections, evidence_scope="primary")

    texts = {payload["text"] for payload in payloads}
    assert len(payloads) == 2
    assert "Allergy alert" in next(t for t in texts if "Allergy" in t)
    assert any("Cardiovascular" in text for text in texts)


def test_label_section_payloads_guarantees_required_section_survives_truncation() -> (
    None
):
    # Per-section capping alone isn't always enough: a drug with several
    # distinct, well-populated sections ahead of a required one in priority
    # order can still exhaust MAX_LABEL_SECTIONS before reaching it.
    earlier_sections = (
        "boxed_warning",
        "contraindications",
        "warnings",
        "drug_interactions",
        "pregnancy",
        "lactation",
        "pregnancy_or_breast_feeding",
        "indications_and_usage",
        "adverse_reactions",
    )
    sections: dict = {}
    for name in earlier_sections:
        sections.update(_label_sections(MAX_SECTION_ENTRIES, section=name))
    sections.update(_label_sections(2, section="use_in_specific_populations"))

    without_guarantee = label_section_payloads(sections, evidence_scope="primary")
    with_guarantee = label_section_payloads(
        sections,
        evidence_scope="primary",
        required_sections={"use_in_specific_populations"},
    )

    assert not any(
        p["section"] == "use_in_specific_populations" for p in without_guarantee
    )
    assert any(
        p["section"] == "use_in_specific_populations" for p in with_guarantee
    )
    assert len(with_guarantee) <= MAX_LABEL_SECTIONS


def test_evidence_packet_keeps_drug_interactions_when_contract_requires_it() -> None:
    sections = {
        **_label_sections(2, section="boxed_warning"),
        **_label_sections(2, section="contraindications"),
        **_label_sections(13, section="warnings"),
        **_label_sections(2, section="drug_interactions"),
    }
    dossier = DrugDossier(
        query="ibuprofen",
        resolved_drug=RxNormConcept(rxcui="5640", name="ibuprofen", tty="IN"),
        label_evidence=OpenFDALabelEvidence(
            rxcui="5640",
            labels_found=1,
            label_limit=1,
            label_records=[OpenFDALabelRecord(source_id="boxed_warning-0")],
            sections=sections,
        ),
    )
    understanding_with_dossier = QueryUnderstandingResponse(
        query="Can I take ibuprofen if I'm allergic to aspirin?",
        state=QueryState(primary_drug="ibuprofen", all_drugs_mentioned=["ibuprofen"]),
        primary_dossier=dossier,
    )
    contract = AnswerContract(
        items=[
            AnswerContractItem(
                kind="must_mention",
                topic="interaction_check",
                intent="interaction_check",
                statement="Address what the retrieved drug interaction sections say.",
                evidence_available=True,
                required_sections=["drug_interactions"],
                coverage_category="intent",
                coverage_label="interaction_check",
            )
        ]
    )

    packet = EvidenceAnswerSynthesizer.build_evidence_packet(
        understanding_with_dossier,
        contract=contract,
    )

    assert any(
        section["section"] == "drug_interactions"
        for section in packet["label_sections"]
    )


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


def test_query_answer_response_includes_question_evidence_map() -> None:
    understanding = response_with_label_evidence()
    service = QueryAnswerService(
        builder=offline_builder(),
        understanding_service=FakeUnderstandingService(understanding),
        synthesizer=FakeAnswerSynthesizer(),
    )

    response = service.answer("Can I take aspirin?")

    node_kinds = {node.kind for node in response.question_evidence_map.nodes}
    edge_kinds = {edge.kind for edge in response.question_evidence_map.edges}
    assert {"question", "query_concept", "resolved_medication", "label_source"} <= (
        node_kinds
    )
    assert {"has_role", "resolved_as", "has_label_source"} <= edge_kinds
    assert response.question_evidence_map.summary_counts["nodes"] >= 4


def test_query_answer_response_includes_secondary_evidence() -> None:
    understanding = response_with_secondary_mention()
    service = QueryAnswerService(
        builder=fake_secondary_builder(),
        understanding_service=FakeUnderstandingService(understanding),
        synthesizer=FakeAnswerSynthesizer(),
    )

    response = service.answer("Can I take aspirin with ibuprofen?")

    assert len(response.secondary_evidence) == 1
    secondary = response.secondary_evidence[0]
    assert secondary.resolved_concept.name == "ibuprofen"
    assert secondary.label_evidence is not None
    assert secondary.label_evidence.labels_found == 1
    assert "standard_secondary_label_lookup" in secondary.retrieval_modes
    assert any(
        node.kind == "resolved_medication" and node.rxcui == "5640"
        for node in response.question_evidence_map.nodes
    )


def test_query_answer_response_includes_secondary_evidence_for_drug_allergy() -> None:
    ibuprofen_concept = RxNormConcept(rxcui="5640", name="ibuprofen", tty="IN")
    aspirin_concept = RxNormConcept(rxcui="1191", name="aspirin", tty="IN")
    understanding = QueryUnderstandingResponse(
        query="Can I take ibuprofen for migraine if I have an aspirin allergy?",
        state=QueryState(
            primary_drug="ibuprofen",
            all_drugs_mentioned=["ibuprofen", "aspirin"],
            allergies=["aspirin"],
            conditions=["migraine"],
            intents=["allergy_context_check", "safety_context_check"],
        ),
        resolved_drugs=[
            ResolvedDrugMention(
                text="ibuprofen",
                role="primary_drug",
                selected_concept=ibuprofen_concept,
            ),
            ResolvedDrugMention(
                text="aspirin",
                role="allergy",
                selected_concept=aspirin_concept,
            ),
        ],
        primary_dossier=DrugDossier(
            query="ibuprofen",
            resolved_drug=ibuprofen_concept,
            label_evidence=OpenFDALabelEvidence(
                rxcui="5640",
                labels_found=1,
                label_records=[
                    OpenFDALabelRecord(source_id="label-primary"),
                ],
                sections={
                    "warnings": [
                        LabelSection(
                            section="warnings",
                            text="Ibuprofen warning text.",
                            source_id="label-primary",
                        )
                    ]
                },
            ),
        ),
    )
    service = QueryAnswerService(
        builder=fake_aspirin_secondary_builder(),
        understanding_service=FakeUnderstandingService(understanding),
        synthesizer=FakeAnswerSynthesizer(),
    )

    response = service.answer(
        "Can I take ibuprofen for migraine if I have an aspirin allergy?"
    )

    assert len(response.secondary_evidence) == 1
    secondary = response.secondary_evidence[0]
    assert secondary.role == "allergy"
    assert secondary.resolved_concept.name == "aspirin"
    assert secondary.label_evidence is not None
    assert secondary.label_evidence.labels_found == 1
    assert any(
        item.category == "mentioned_drug"
        and item.label == "aspirin"
        and item.status == "addressed"
        for item in response.coverage.items
    )
    assert any(
        node.kind == "resolved_medication" and node.rxcui == "1191"
        for node in response.question_evidence_map.nodes
    )


def test_context_targets_dedupe_and_skip_medication_terms() -> None:
    state = QueryState(
        primary_drug="tretinoin",
        all_drugs_mentioned=["tretinoin"],
        conditions=["acne", "acne", "tretinoin"],
        allergies=["benzoyl peroxide"],
        patient_context=["pregnant", "x"],
    )

    targets = select_context_targets(
        state,
        [RxNormConcept(rxcui="9033", name="tretinoin", tty="IN")],
        max_items=5,
    )

    assert [(target.category, target.label) for target in targets] == [
        ("patient_context", "pregnant"),
        ("allergy", "benzoyl peroxide"),
        ("condition", "acne"),
    ]
    assert targets[1].search_label == "benzoyl peroxide allergy"
    assert targets[2].search_label == "acne"


def test_context_targeted_evidence_triggers_condition_lookup() -> None:
    class TrackingOpenFDAStore(OpenFDALabelStore):
        def __init__(self) -> None:
            super().__init__(allow_live=False, use_cache=False)
            self.context_calls: list[
                tuple[str, str, tuple[str, ...], str | None, int]
            ] = []

        def get_context_label_evidence(
            self,
            rxcui: str,
            *,
            target: str,
            section_fields: list[str],
            fallback_name: str | None = None,
            limit: int = 3,
        ) -> OpenFDALabelEvidence:
            self.context_calls.append(
                (rxcui, target, tuple(section_fields), fallback_name, limit)
            )
            return OpenFDALabelEvidence(
                rxcui=rxcui,
                labels_found=1,
                label_limit=limit,
                retrieval_mode="context_targeted_lookup",
                label_records=[
                    OpenFDALabelRecord(
                        source_id="label-acne",
                        brand_names=["Tretinoin"],
                    )
                ],
                sections={
                    "indications_and_usage": [
                        LabelSection(
                            section="indications_and_usage",
                            text="Tretinoin is indicated for acne.",
                            source_id="label-acne",
                        )
                    ]
                },
            )

    store = TrackingOpenFDAStore()
    builder = DossierBuilder(
        rxnorm_store=RxNormParquetStore(),
        openfda_store=store,
    )
    understanding = QueryUnderstandingResponse(
        query="Can I use tretinoin for acne?",
        state=QueryState(
            primary_drug="tretinoin",
            all_drugs_mentioned=["tretinoin"],
            conditions=["acne"],
        ),
        primary_dossier=DrugDossier(
            query="tretinoin",
            resolved_drug=RxNormConcept(rxcui="9033", name="tretinoin", tty="IN"),
            label_evidence=OpenFDALabelEvidence(rxcui="9033"),
        ),
    )

    evidence = build_context_targeted_evidence(
        understanding,
        [],
        builder,
        QueryAnswerParameters(context_lookup_limit=2, max_context_targets=5),
    )

    assert store.context_calls == [
        (
            "9033",
            "acne",
            (
                "indications_and_usage",
                "warnings",
                "contraindications",
                "adverse_reactions",
            ),
            "tretinoin",
            2,
        )
    ]
    assert len(evidence) == 1
    assert evidence[0].target_label == "acne"
    assert evidence[0].label_evidence is not None
    assert evidence[0].label_evidence.label_records[0].provenance_tags == [
        "context_targeted_lookup"
    ]


def test_context_targeted_evidence_uses_allergy_phrase_for_search() -> None:
    class TrackingOpenFDAStore(OpenFDALabelStore):
        def __init__(self) -> None:
            super().__init__(allow_live=False, use_cache=False)
            self.context_calls: list[str] = []

        def get_context_label_evidence(
            self,
            rxcui: str,
            *,
            target: str,
            section_fields: list[str],
            fallback_name: str | None = None,
            limit: int = 3,
        ) -> OpenFDALabelEvidence:
            self.context_calls.append(target)
            return OpenFDALabelEvidence(rxcui=rxcui, label_limit=limit)

    store = TrackingOpenFDAStore()
    builder = DossierBuilder(
        rxnorm_store=RxNormParquetStore(),
        openfda_store=store,
    )
    understanding = QueryUnderstandingResponse(
        query="Can I take ibuprofen with an aspirin allergy?",
        state=QueryState(
            primary_drug="ibuprofen",
            all_drugs_mentioned=["ibuprofen"],
            allergies=["aspirin"],
        ),
        primary_dossier=DrugDossier(
            query="ibuprofen",
            resolved_drug=RxNormConcept(rxcui="5640", name="ibuprofen", tty="IN"),
            label_evidence=OpenFDALabelEvidence(rxcui="5640"),
        ),
    )

    build_context_targeted_evidence(
        understanding,
        [],
        builder,
        QueryAnswerParameters(context_lookup_limit=2, max_context_targets=5),
    )

    assert store.context_calls == ["aspirin allergy"]


def test_query_answer_response_merges_context_evidence_into_primary_labels() -> None:
    class ContextOpenFDAStore(OpenFDALabelStore):
        def __init__(self) -> None:
            super().__init__(allow_live=False, use_cache=False)

        def get_context_label_evidence(
            self,
            rxcui: str,
            *,
            target: str,
            section_fields: list[str],
            fallback_name: str | None = None,
            limit: int = 3,
        ) -> OpenFDALabelEvidence:
            return OpenFDALabelEvidence(
                rxcui=rxcui,
                labels_found=1,
                label_limit=limit,
                retrieval_mode="context_targeted_lookup",
                label_records=[
                    OpenFDALabelRecord(
                        source_id="label-acne",
                        brand_names=["Tretinoin"],
                        provenance_tags=["context_targeted_lookup"],
                    )
                ],
                sections={
                    "indications_and_usage": [
                        LabelSection(
                            section="indications_and_usage",
                            text="Tretinoin label text mentions acne.",
                            source_id="label-acne",
                            provenance_tags=["context_targeted_lookup"],
                        )
                    ]
                },
            )

    understanding = response_with_label_evidence().model_copy(
        update={
            "query": "Can I use aspirin for acne?",
            "state": QueryState(
                primary_drug="aspirin",
                all_drugs_mentioned=["aspirin"],
                conditions=["acne"],
            ),
        }
    )
    service = QueryAnswerService(
        builder=DossierBuilder(
            rxnorm_store=RxNormParquetStore(),
            openfda_store=ContextOpenFDAStore(),
        ),
        understanding_service=FakeUnderstandingService(understanding),
        synthesizer=FakeAnswerSynthesizer(),
    )

    response = service.answer("Can I use aspirin for acne?")

    assert len(response.context_evidence) == 1
    label_evidence = response.understanding.primary_dossier.label_evidence
    assert label_evidence is not None
    assert any(
        record.source_id == "label-acne"
        and "context_targeted_lookup" in record.provenance_tags
        for record in label_evidence.label_records
    )
    assert any(
        item.category == "condition"
        and item.label == "acne"
        and item.status == "addressed"
        for item in response.coverage.items
    )


def test_context_coverage_requires_actual_text_match() -> None:
    class ContextOpenFDAStore(OpenFDALabelStore):
        def __init__(self) -> None:
            super().__init__(allow_live=False, use_cache=False)

        def get_context_label_evidence(
            self,
            rxcui: str,
            *,
            target: str,
            section_fields: list[str],
            fallback_name: str | None = None,
            limit: int = 3,
        ) -> OpenFDALabelEvidence:
            return OpenFDALabelEvidence(
                rxcui=rxcui,
                labels_found=1,
                label_limit=limit,
                retrieval_mode="context_targeted_lookup",
                label_records=[
                    OpenFDALabelRecord(
                        source_id="label-1",
                        brand_names=["Ibuprofen"],
                        provenance_tags=["context_targeted_lookup"],
                    )
                ],
                sections={
                    "warnings": [
                        LabelSection(
                            section="warnings",
                            text="This warning text mentions a rash only.",
                            source_id="label-1",
                            provenance_tags=["context_targeted_lookup"],
                        )
                    ]
                },
            )

    understanding = QueryUnderstandingResponse(
        query="Can I take ibuprofen with an aspirin allergy?",
        state=QueryState(
            primary_drug="ibuprofen",
            all_drugs_mentioned=["ibuprofen"],
            allergies=["aspirin"],
        ),
        primary_dossier=DrugDossier(
            query="ibuprofen",
            resolved_drug=RxNormConcept(rxcui="5640", name="ibuprofen", tty="IN"),
            label_evidence=OpenFDALabelEvidence(rxcui="5640"),
        ),
    )
    service = QueryAnswerService(
        builder=DossierBuilder(
            rxnorm_store=RxNormParquetStore(),
            openfda_store=ContextOpenFDAStore(),
        ),
        understanding_service=FakeUnderstandingService(understanding),
        synthesizer=FakeAnswerSynthesizer(),
    )

    response = service.answer("Can I take ibuprofen with an aspirin allergy?")

    assert any(
        item.category == "allergy"
        and item.label == "aspirin"
        and item.status == "not_found_in_evidence"
        for item in response.coverage.items
    )


def test_context_merge_preserves_tags_on_duplicate_primary_label() -> None:
    class ContextOpenFDAStore(OpenFDALabelStore):
        def __init__(self) -> None:
            super().__init__(allow_live=False, use_cache=False)

        def get_context_label_evidence(
            self,
            rxcui: str,
            *,
            target: str,
            section_fields: list[str],
            fallback_name: str | None = None,
            limit: int = 3,
        ) -> OpenFDALabelEvidence:
            return OpenFDALabelEvidence(
                rxcui=rxcui,
                labels_found=1,
                label_limit=limit,
                retrieval_mode="context_targeted_lookup",
                label_records=[
                    OpenFDALabelRecord(
                        source_id="label-1",
                        brand_names=["Aspirin"],
                        provenance_tags=["context_targeted_lookup"],
                    )
                ],
                sections={
                    "warnings": [
                        LabelSection(
                            section="warnings",
                            text="Aspirin warning text.",
                            source_id="label-1",
                            provenance_tags=["context_targeted_lookup"],
                        )
                    ]
                },
            )

    understanding = response_with_label_evidence().model_copy(
        update={
            "state": QueryState(
                primary_drug="aspirin",
                all_drugs_mentioned=["aspirin"],
                conditions=["acne"],
            )
        }
    )
    service = QueryAnswerService(
        builder=DossierBuilder(
            rxnorm_store=RxNormParquetStore(),
            openfda_store=ContextOpenFDAStore(),
        ),
        understanding_service=FakeUnderstandingService(understanding),
        synthesizer=FakeAnswerSynthesizer(),
    )

    response = service.answer("Can I use aspirin for acne?")
    label_evidence = response.understanding.primary_dossier.label_evidence
    assert label_evidence is not None
    assert label_evidence.label_records[0].source_id == "label-1"
    assert "context_targeted_lookup" in label_evidence.label_records[0].provenance_tags
    assert (
        "context_targeted_lookup"
        in label_evidence.sections["warnings"][0].provenance_tags
    )


def test_question_evidence_map_links_context_concepts_to_labels() -> None:
    understanding = response_with_label_evidence().model_copy(
        update={
            "state": QueryState(
                primary_drug="aspirin",
                all_drugs_mentioned=["aspirin"],
                conditions=["acne"],
            )
        }
    )
    context_evidence = ContextTargetedEvidence(
        target_label="acne",
        target_category="condition",
        resolved_concept=RxNormConcept(rxcui="1191", name="aspirin", tty="IN"),
        searched_fields=["indications_and_usage"],
        retrieval_modes=["context_targeted_lookup"],
        label_evidence=OpenFDALabelEvidence(
            rxcui="1191",
            labels_found=1,
            retrieval_mode="context_targeted_lookup",
            label_records=[
                OpenFDALabelRecord(
                    source_id="label-acne",
                    brand_names=["Aspirin"],
                    provenance_tags=["context_targeted_lookup"],
                )
            ],
            sections={
                "indications_and_usage": [
                    LabelSection(
                        section="indications_and_usage",
                        text="Label text mentions acne.",
                        source_id="label-acne",
                        provenance_tags=["context_targeted_lookup"],
                    )
                ]
            },
        ),
    )
    merged_dossier = understanding.primary_dossier.model_copy(
        update={"label_evidence": context_evidence.label_evidence}
    )
    understanding = understanding.model_copy(update={"primary_dossier": merged_dossier})

    evidence_map = build_question_evidence_map(
        understanding,
        context_evidence=[context_evidence],
    )

    context_edges = [
        edge for edge in evidence_map.edges if edge.kind.startswith("context_lookup")
    ]
    assert {edge.kind for edge in context_edges} == {"context_lookup_source"}
    assert all(edge.context_terms == ["acne"] for edge in context_edges)
    assert any(
        node.kind == "label_source"
        and "context_targeted_lookup" in node.tags
        for node in evidence_map.nodes
    )


def test_question_evidence_map_marks_interaction_targeted_label_sources() -> None:
    fixture = secondary_evidence_fixture()
    assert fixture.label_evidence is not None
    tagged_evidence = fixture.label_evidence.model_copy(
        update={
            "label_records": [
                record.model_copy(
                    update={
                        "provenance_tags": ["interaction_targeted_lookup"],
                        "rxcuis": ["5640", "1191"],
                    }
                )
                for record in fixture.label_evidence.label_records
            ],
            "sections": {
                "drug_interactions": [
                    section.model_copy(
                        update={"provenance_tags": ["interaction_targeted_lookup"]}
                    )
                    for section in fixture.label_evidence.sections[
                        "drug_interactions"
                    ]
                ]
            },
        }
    )
    secondary = fixture.model_copy(
        update={
            "label_evidence": tagged_evidence,
            "retrieval_modes": ["interaction_targeted_lookup"],
        }
    )

    evidence_map = build_question_evidence_map(
        response_with_secondary_mention(),
        secondary_evidence=[secondary],
    )

    interaction_edges = [
        edge
        for edge in evidence_map.edges
        if edge.kind == "interaction_lookup_source"
    ]
    assert interaction_edges
    assert all(edge.source_id == "label-2" for edge in interaction_edges)
    assert all(edge.section is None for edge in interaction_edges)
    assert any(
        edge.kind == "has_label_section" and edge.section == "drug_interactions"
        for edge in evidence_map.edges
    )
    assert any(
        node.kind == "label_source" and node.label_rxcuis == ["5640", "1191"]
        for node in evidence_map.nodes
    )
    assert any(
        node.kind == "label_section" and node.label_rxcuis == ["5640", "1191"]
        for node in evidence_map.nodes
    )
    edge_text = " ".join(
        value for edge in evidence_map.edges for value in [edge.kind, edge.label]
    )
    assert "interacts_with" not in edge_text
    assert "clinical interaction" not in edge_text.lower()


def test_question_evidence_map_shares_interaction_label_source_across_medications(
) -> None:
    interaction_evidence = OpenFDALabelEvidence(
        rxcui="5640",
        labels_found=1,
        label_limit=3,
        retrieval_mode="interaction_targeted_lookup",
        label_records=[
            OpenFDALabelRecord(
                source_id="label-1",
                brand_names=["Aspirin"],
                generic_names=["ASPIRIN"],
                provenance_tags=["interaction_targeted_lookup"],
            )
        ],
        sections={
            "drug_interactions": [
                LabelSection(
                    section="drug_interactions",
                    text="Aspirin label text mentioning ibuprofen.",
                    source_id="label-1",
                    provenance_tags=["interaction_targeted_lookup"],
                )
            ]
        },
    )
    secondary = secondary_evidence_fixture().model_copy(
        update={
            "label_evidence": interaction_evidence,
            "interaction_label_evidence": interaction_evidence,
            "retrieval_modes": ["interaction_targeted_lookup"],
        }
    )

    evidence_map = build_question_evidence_map(
        response_with_secondary_mention(),
        secondary_evidence=[secondary],
    )

    label_source_nodes = [
        node
        for node in evidence_map.nodes
        if node.kind == "label_source" and node.source_id == "label-1"
    ]
    assert len(label_source_nodes) == 1
    label_source_id = label_source_nodes[0].id
    assert any(
        edge.kind == "has_label_source"
        and edge.source == "rxnorm:1191"
        and edge.target == label_source_id
        for edge in evidence_map.edges
    )
    assert any(
        edge.kind == "interaction_lookup_source"
        and edge.source == "rxnorm:5640"
        and edge.target == label_source_id
        for edge in evidence_map.edges
    )


def test_question_evidence_map_labels_sources_without_openfda_metadata() -> None:
    interaction_evidence = OpenFDALabelEvidence(
        rxcui="5640",
        labels_found=1,
        label_limit=3,
        retrieval_mode="interaction_targeted_lookup",
        label_records=[
            OpenFDALabelRecord(
                source_id="label-without-openfda",
                provenance_tags=["interaction_targeted_lookup"],
            )
        ],
        sections={
            "drug_interactions": [
                LabelSection(
                    section="drug_interactions",
                    text="Unidentified label text mentioning another medication.",
                    source_id="label-without-openfda",
                    provenance_tags=["interaction_targeted_lookup"],
                )
            ]
        },
    )
    secondary = secondary_evidence_fixture().model_copy(
        update={
            "label_evidence": interaction_evidence,
            "interaction_label_evidence": interaction_evidence,
            "retrieval_modes": ["interaction_targeted_lookup"],
        }
    )

    evidence_map = build_question_evidence_map(
        response_with_secondary_mention(),
        secondary_evidence=[secondary],
    )

    label_source_node = next(
        node
        for node in evidence_map.nodes
        if node.kind == "label_source"
        and node.source_id == "label-without-openfda"
    )
    assert label_source_node.label == "Unidentified drug label"
    assert label_source_node.subtitle == "OpenFDA product metadata unavailable"


def test_question_evidence_map_omits_rxnorm_context_for_visual_clarity() -> None:
    secondary = secondary_evidence_fixture().model_copy(
        update={
            "rxnorm_context": RxNormPairContext(
                primary_rxcui="1191",
                secondary_rxcui="5640",
                status="shared_neighbor",
                summary=(
                    "The primary and secondary concepts share nearby RxNorm "
                    "terminology neighbors. This is terminology context, not "
                    "clinical interaction evidence."
                ),
            )
        }
    )
    evidence_map = build_question_evidence_map(
        response_with_secondary_mention(),
        secondary_evidence=[secondary],
    )

    assert all(node.kind != "rxnorm_context" for node in evidence_map.nodes)
    assert all(edge.kind != "has_terminology_context" for edge in evidence_map.edges)
    assert all(edge.kind != "interacts_with" for edge in evidence_map.edges)


def test_secondary_evidence_triggers_interaction_targeted_lookups() -> None:
    class TrackingOpenFDAStore(OpenFDALabelStore):
        def __init__(self) -> None:
            super().__init__(allow_live=False, use_cache=False)
            self.standard_calls: list[tuple[str, str | None, int]] = []
            self.interaction_calls: list[tuple[str, str, str | None, int]] = []

        def get_label_evidence(
            self,
            rxcui: str,
            fallback_name: str | None = None,
            limit: int = 5,
        ) -> OpenFDALabelEvidence:
            self.standard_calls.append((rxcui, fallback_name, limit))
            return OpenFDALabelEvidence(rxcui=rxcui, label_limit=limit)

        def get_interaction_label_evidence(
            self,
            rxcui: str,
            interaction_name: str,
            fallback_name: str | None = None,
            limit: int = 3,
        ) -> OpenFDALabelEvidence:
            self.interaction_calls.append(
                (rxcui, interaction_name, fallback_name, limit)
            )
            if rxcui == "5640":
                evidence = secondary_evidence_fixture().label_evidence
                assert evidence is not None
                return evidence.model_copy(
                    update={
                        "retrieval_mode": "interaction_targeted_lookup",
                        "label_limit": limit,
                    }
                )
            return OpenFDALabelEvidence(rxcui=rxcui, label_limit=limit)

    store = TrackingOpenFDAStore()
    builder = DossierBuilder(
        rxnorm_store=RxNormParquetStore(),
        openfda_store=store,
    )

    evidence = build_secondary_evidence(
        response_with_secondary_mention(),
        builder,
        QueryAnswerParameters(
            secondary_openfda_limit=2,
            interaction_lookup_limit=4,
            max_secondary_drugs=3,
        ),
    )

    assert store.standard_calls == [("5640", "ibuprofen", 2)]
    assert store.interaction_calls == [
        ("5640", "aspirin", "ibuprofen", 4),
        ("1191", "ibuprofen", "aspirin", 4),
    ]
    assert len(evidence) == 1
    assert evidence[0].label_evidence is not None
    assert evidence[0].label_evidence.labels_found == 1
    assert evidence[0].label_evidence.label_records[0].provenance_tags == [
        "interaction_targeted_lookup"
    ]
    assert evidence[0].label_evidence.sections["warnings"][0].provenance_tags == [
        "interaction_targeted_lookup"
    ]
    assert "interaction_targeted_lookup" in evidence[0].retrieval_modes
    assert evidence[0].rxnorm_context is not None
    assert "terminology" in evidence[0].rxnorm_context.summary.lower()


def test_interaction_lookup_uses_ingredient_not_product_name() -> None:
    class TrackingStore(OpenFDALabelStore):
        def __init__(self) -> None:
            super().__init__(allow_live=False, use_cache=False)
            self.interaction_calls: list[tuple[str, str, str | None]] = []

        def get_label_evidence(
            self, rxcui: str, fallback_name: str | None = None, limit: int = 5
        ) -> OpenFDALabelEvidence:
            return OpenFDALabelEvidence(rxcui=rxcui, label_limit=limit)

        def get_interaction_label_evidence(
            self,
            rxcui: str,
            interaction_name: str,
            fallback_name: str | None = None,
            limit: int = 3,
        ) -> OpenFDALabelEvidence:
            self.interaction_calls.append((rxcui, interaction_name, fallback_name))
            return OpenFDALabelEvidence(rxcui=rxcui, label_limit=limit)

    cream = RxNormConcept(
        rxcui="198300", name="tretinoin 1 MG/ML Topical Cream", tty="SCD"
    )
    clindamycin = RxNormConcept(rxcui="2582", name="clindamycin", tty="IN")
    understanding = QueryUnderstandingResponse(
        query="Can I use tretinoin cream with clindamycin?",
        state=QueryState(
            primary_drug="tretinoin cream",
            all_drugs_mentioned=["tretinoin cream", "clindamycin"],
            intents=["interaction_check"],
        ),
        resolved_drugs=[
            ResolvedDrugMention(
                text="clindamycin",
                role="mentioned_drug",
                candidates=[],
                selected_concept=clindamycin,
            )
        ],
        primary_dossier=DrugDossier(query="tretinoin cream", resolved_drug=cream),
    )

    store = TrackingStore()
    build_secondary_evidence(
        understanding,
        DossierBuilder(rxnorm_store=RxNormParquetStore(), openfda_store=store),
        QueryAnswerParameters(interaction_lookup_limit=3, max_secondary_drugs=3),
    )

    # The cream product is searched as its ingredient "tretinoin", never as the
    # full product string (which also carries the query-breaking slash).
    terms = {term for _, term, _ in store.interaction_calls}
    assert "tretinoin" in terms
    assert all(
        "Topical Cream" not in term and "/" not in term
        for _, term, _ in store.interaction_calls
    )
    # The primary's own labels are searched for the secondary ingredient.
    assert ("198300", "clindamycin", "tretinoin") in store.interaction_calls


def test_secondary_evidence_uses_multi_intent_interaction_signal() -> None:
    understanding = response_with_secondary_mention().model_copy(
        update={
            "state": QueryState(
                primary_drug="aspirin",
                all_drugs_mentioned=["aspirin", "ibuprofen"],
                current_medications=["ibuprofen"],
                intents=["safety_context_check", "interaction_check"],
            )
        }
    )

    class TrackingOpenFDAStore(OpenFDALabelStore):
        def __init__(self) -> None:
            super().__init__(allow_live=False, use_cache=False)
            self.interaction_calls = 0

        def get_label_evidence(
            self,
            rxcui: str,
            fallback_name: str | None = None,
            limit: int = 5,
        ) -> OpenFDALabelEvidence:
            return OpenFDALabelEvidence(rxcui=rxcui, label_limit=limit)

        def get_interaction_label_evidence(
            self,
            rxcui: str,
            interaction_name: str,
            fallback_name: str | None = None,
            limit: int = 3,
        ) -> OpenFDALabelEvidence:
            self.interaction_calls += 1
            return OpenFDALabelEvidence(rxcui=rxcui, label_limit=limit)

    store = TrackingOpenFDAStore()

    build_secondary_evidence(
        understanding,
        DossierBuilder(rxnorm_store=RxNormParquetStore(), openfda_store=store),
        QueryAnswerParameters(),
    )

    assert store.interaction_calls == 2


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
        "Only the primary medication dossier was retrieved" in item
        for item in response.answer.limitations
    )
    assert any(
        "ibuprofen was recognized" in item
        for item in response.answer.limitations
    )
    assert any(
        "did not explicitly mention ibuprofen, migraine, and pregnant" in item
        for item in response.answer.limitations
    )


def test_coverage_flags_ingredient_fallback_broadening() -> None:
    concept = RxNormConcept(
        rxcui="198300", name="tretinoin 1 MG/ML Topical Cream", tty="SCD"
    )
    ingredient = RxNormConcept(rxcui="10753", name="tretinoin", tty="IN")
    label_evidence = OpenFDALabelEvidence(
        rxcui="198300",
        labels_found=1,
        label_limit=5,
        retrieval_mode="ingredient_fallback",
        label_records=[
            OpenFDALabelRecord(
                source_id="L1",
                generic_names=["TRETINOIN"],
                provenance_tags=["ingredient_fallback"],
            )
        ],
        sections={
            "warnings": [
                LabelSection(
                    section="warnings",
                    text="Avoid excessive sun exposure.",
                    source_id="L1",
                )
            ]
        },
        section_flags={"has_warnings": True},
    )
    understanding = QueryUnderstandingResponse(
        query="Can I use tretinoin cream?",
        state=QueryState(primary_drug="tretinoin cream"),
        primary_dossier=DrugDossier(
            query="tretinoin cream",
            resolved_drug=concept,
            label_evidence=label_evidence,
            label_evidence_scope="ingredient_fallback",
            ingredient_fallback=[
                IngredientFallbackEvidence(
                    ingredient=ingredient,
                    label_evidence=label_evidence,
                )
            ],
        ),
    )

    coverage = build_evidence_coverage(understanding)
    primary = next(
        item for item in coverage.items if item.category == "primary_drug"
    )
    assert primary.status == "addressed"
    assert "active ingredient" in primary.reason
    assert "tretinoin" in primary.reason

    answer = EvidenceAnswer(
        response="Summary.",
        bullets=[],
        limitations=[],
        safety_note="note",
    )
    contract = build_answer_contract(understanding, coverage)
    updated, _validation = validate_and_enforce(answer, contract)
    assert updated is not None
    assert any(
        "active ingredient" in limitation and "tretinoin" in limitation
        for limitation in updated.limitations
    )


def test_evidence_coverage_marks_secondary_as_addressed() -> None:
    understanding = response_with_secondary_mention()
    service = QueryAnswerService(
        builder=fake_secondary_builder(),
        understanding_service=FakeUnderstandingService(understanding),
        synthesizer=FakeAnswerSynthesizer(),
    )

    response = service.answer("Can I take aspirin with ibuprofen?")

    mentioned_item = next(
        item
        for item in response.coverage.items
        if item.category == "mentioned_drug" and item.label == "ibuprofen"
    )
    medication_item = next(
        item
        for item in response.coverage.items
        if item.category == "current_medication" and item.label == "ibuprofen"
    )
    assert mentioned_item.status == "addressed"
    assert mentioned_item.target_rxcui == "5640"
    assert mentioned_item.source_id is None
    assert mentioned_item.section is None
    assert mentioned_item.matched_evidence is None
    assert medication_item.status == "addressed"
    assert medication_item.target_rxcui == "5640"
    assert medication_item.source_id is None
    assert medication_item.section is None
    assert medication_item.matched_evidence is None
    assert response.answer is not None
    assert not any(
        "ibuprofen was recognized but not retrieved" in item
        for item in response.answer.limitations
    )


def test_query_extraction_infers_side_effect_and_indication_intents() -> None:
    side_effect_result = HybridQueryExtractor()._extract_deterministic(
        "What are the side effects of aspirin?"
    )
    assert "side_effect_check" in side_effect_result.state.intents

    indication_result = HybridQueryExtractor()._extract_deterministic(
        "What is aspirin used for?"
    )
    assert "indication_check" in indication_result.state.intents


def test_query_extraction_does_not_infer_safety_context_check() -> None:
    result = HybridQueryExtractor()._extract_deterministic(
        "Can I safely take aspirin?"
    )

    assert "safety_context_check" not in result.state.intents
    assert "label_context_check" in result.state.intents


def test_evidence_coverage_checks_side_effect_and_indication_intents() -> None:
    addressed = response_with_label_evidence().model_copy(
        update={
            "state": QueryState(
                primary_drug="aspirin",
                all_drugs_mentioned=["aspirin"],
                intents=["side_effect_check", "indication_check"],
            ),
        }
    )
    addressed.primary_dossier.label_evidence.sections.update(
        {
            "indications_and_usage": [
                LabelSection(
                    section="indications_and_usage",
                    text="Indicated for pain relief.",
                    source_id="label-1",
                )
            ],
        }
    )
    coverage = build_evidence_coverage(addressed)
    coverage_by_label = {item.label: item for item in coverage.items}
    # side_effect_check is satisfied by the pre-existing "warnings" section.
    assert coverage_by_label["side_effect_check"].status == "addressed"
    assert coverage_by_label["indication_check"].status == "addressed"

    not_addressed = response_with_label_evidence().model_copy(
        update={
            "state": QueryState(
                primary_drug="aspirin",
                all_drugs_mentioned=["aspirin"],
                intents=["indication_check"],
            ),
        }
    )
    coverage_missing = build_evidence_coverage(not_addressed)
    missing_item = next(
        item for item in coverage_missing.items if item.label == "indication_check"
    )
    assert missing_item.status == "not_found_in_evidence"


def test_evidence_coverage_checks_label_context_check_intent() -> None:
    addressed = response_with_label_evidence().model_copy(
        update={
            "state": QueryState(
                primary_drug="aspirin",
                all_drugs_mentioned=["aspirin"],
                intents=["label_context_check"],
            ),
        }
    )
    coverage = build_evidence_coverage(addressed)
    label_item = next(
        item for item in coverage.items if item.label == "label_context_check"
    )
    assert label_item.status == "addressed"

    no_label_understanding = response_with_label_evidence()
    none_understanding = no_label_understanding.model_copy(
        update={
            "state": QueryState(
                primary_drug="aspirin",
                all_drugs_mentioned=["aspirin"],
                intents=["label_context_check"],
            ),
            "primary_dossier": no_label_understanding.primary_dossier.model_copy(
                update={"label_evidence": None}
            ),
        }
    )
    coverage_missing = build_evidence_coverage(none_understanding)
    missing_item = next(
        item
        for item in coverage_missing.items
        if item.label == "label_context_check"
    )
    assert missing_item.status == "not_found_in_evidence"


def test_build_answer_contract_excludes_label_context_check_from_coverage_level() -> (
    None
):
    understanding = response_with_label_evidence().model_copy(
        update={
            "state": QueryState(
                primary_drug="aspirin",
                all_drugs_mentioned=["aspirin"],
                intents=["label_context_check", "indication_check"],
            ),
        }
    )
    coverage = build_evidence_coverage(understanding)

    contract = build_answer_contract(understanding, coverage)

    # label_context_check is addressed (label text exists) but indication_check
    # is not, and label_context_check must not mask that gap.
    assert contract.coverage_level == "limited"


def test_build_answer_contract_emits_must_mention_and_terminology_caveat() -> None:
    understanding = response_with_secondary_mention()
    secondary_evidence = [secondary_evidence_fixture()]
    coverage = build_evidence_coverage(
        understanding, secondary_evidence=secondary_evidence
    )

    contract = build_answer_contract(understanding, coverage)

    interaction_must_mention = next(
        item
        for item in contract.items
        if item.intent == "interaction_check" and item.kind == "must_mention"
    )
    assert interaction_must_mention.evidence_available is True
    assert any(
        item.kind == "must_caveat" and item.topic == "interaction_terminology"
        for item in contract.items
    )


def test_build_answer_contract_emits_must_caveat_for_unretrieved_secondary_drug() -> (
    None
):
    understanding = response_with_secondary_mention()
    coverage = build_evidence_coverage(understanding)

    contract = build_answer_contract(understanding, coverage)

    secondary_caveat = next(
        item for item in contract.items if item.topic == "secondary_not_retrieved"
    )
    assert secondary_caveat.kind == "must_caveat"
    assert secondary_caveat.evidence_available is False
    assert "ibuprofen was recognized but not retrieved" in secondary_caveat.statement


def test_build_answer_contract_coverage_level_boundaries() -> None:
    direct_understanding = response_with_secondary_mention()
    direct_coverage = build_evidence_coverage(
        direct_understanding, secondary_evidence=[secondary_evidence_fixture()]
    )
    direct_contract = build_answer_contract(direct_understanding, direct_coverage)
    assert direct_contract.coverage_level == "direct"

    partial_understanding = direct_understanding.model_copy(
        update={
            "state": direct_understanding.state.model_copy(
                update={"intents": ["interaction_check", "indication_check"]}
            )
        }
    )
    partial_coverage = build_evidence_coverage(
        partial_understanding, secondary_evidence=[secondary_evidence_fixture()]
    )
    partial_contract = build_answer_contract(partial_understanding, partial_coverage)
    assert partial_contract.coverage_level == "partial"

    limited_understanding = response_with_label_evidence()
    limited_coverage = build_evidence_coverage(limited_understanding)
    limited_contract = build_answer_contract(limited_understanding, limited_coverage)
    assert limited_contract.coverage_level == "limited"

    no_label_understanding = response_with_label_evidence()
    none_understanding = no_label_understanding.model_copy(
        update={
            "primary_dossier": no_label_understanding.primary_dossier.model_copy(
                update={"label_evidence": None}
            )
        }
    )
    none_coverage = build_evidence_coverage(none_understanding)
    none_contract = build_answer_contract(none_understanding, none_coverage)
    assert none_contract.coverage_level == "none"


def test_validate_and_enforce_appends_missing_caveat_and_flags_yes_no_framing() -> (
    None
):
    contract = AnswerContract(
        items=[
            AnswerContractItem(
                kind="must_caveat",
                topic="interaction_terminology",
                intent="interaction_check",
                statement=(
                    "RxNorm terminology overlap is not evidence of a clinical "
                    "interaction."
                ),
                evidence_available=True,
            )
        ],
        coverage_level="partial",
    )
    answer = EvidenceAnswer(
        response="You can take both medications together.",
        bullets=[],
        limitations=[],
        safety_note="note",
    )

    updated, validation = validate_and_enforce(answer, contract)

    assert updated is not None
    assert (
        "RxNorm terminology overlap is not evidence of a clinical interaction."
        in updated.limitations
    )
    assert any(
        finding.kind == "missing_caveat_enforced" for finding in validation.findings
    )
    assert any(finding.kind == "yes_no_framing" for finding in validation.findings)
    assert any(
        "discuss your specific situation" in limitation
        for limitation in updated.limitations
    )
    assert validation.passed is False
    assert len(validation.enforced_caveats) == 2


def test_validate_and_enforce_does_not_duplicate_existing_caveat() -> None:
    statement = "RxNorm terminology overlap is not evidence of a clinical interaction."
    contract = AnswerContract(
        items=[
            AnswerContractItem(
                kind="must_caveat",
                topic="interaction_terminology",
                intent="interaction_check",
                statement=statement,
                evidence_available=True,
            )
        ],
    )
    answer = EvidenceAnswer(
        response="Evidence-based response.",
        bullets=[],
        limitations=[statement],
        safety_note="note",
    )

    updated, validation = validate_and_enforce(answer, contract)

    assert updated is not None
    assert updated.limitations == [statement]
    assert validation.findings == []
    assert validation.passed is True


def test_validate_and_enforce_relocates_uncited_bullets_to_limitations() -> None:
    contract = AnswerContract(items=[])
    answer = EvidenceAnswer(
        response="Some response.",
        bullets=[
            EvidenceBullet(
                text="Ibuprofen labels describe an interaction with aspirin.",
                citations=[
                    EvidenceCitation(source_id="label-1", section="drug_interactions")
                ],
            ),
            EvidenceBullet(
                text="The labels do not mention cetirizine in any section.",
                citations=[],
            ),
        ],
        limitations=["Existing limitation."],
        safety_note="note",
    )

    updated, validation = validate_and_enforce(answer, contract)

    assert updated is not None
    assert [bullet.text for bullet in updated.bullets] == [
        "Ibuprofen labels describe an interaction with aspirin."
    ]
    assert updated.limitations == [
        "Existing limitation.",
        "The labels do not mention cetirizine in any section.",
    ]
    assert any(
        finding.kind == "uncited_bullet_relocated" for finding in validation.findings
    )


def test_validate_and_enforce_does_not_duplicate_relocated_bullet_text() -> None:
    contract = AnswerContract(items=[])
    text = "The labels do not mention cetirizine in any section."
    answer = EvidenceAnswer(
        response="Some response.",
        bullets=[EvidenceBullet(text=text, citations=[])],
        limitations=[text],
        safety_note="note",
    )

    updated, validation = validate_and_enforce(answer, contract)

    assert updated is not None
    assert updated.bullets == []
    assert updated.limitations == [text]
    assert not any(
        finding.kind == "uncited_bullet_relocated" for finding in validation.findings
    )


def test_validate_and_enforce_flags_unaddressed_must_mention() -> None:
    contract = AnswerContract(
        items=[
            AnswerContractItem(
                kind="must_mention",
                topic="indication_check",
                intent="indication_check",
                statement="Address what the retrieved indication label sections say.",
                evidence_available=True,
                required_sections=["indications_and_usage"],
            )
        ],
    )
    answer = EvidenceAnswer(
        response="This medication has several uses.",
        bullets=[
            EvidenceBullet(
                text="See warnings.",
                citations=[EvidenceCitation(source_id="label-1", section="warnings")],
            )
        ],
        limitations=[],
        safety_note="note",
    )

    _updated, validation = validate_and_enforce(answer, contract)

    assert any(
        finding.kind == "must_mention_unaddressed" for finding in validation.findings
    )


def test_evidence_packet_includes_contract_and_product_context() -> None:
    contract = AnswerContract(
        items=[
            AnswerContractItem(
                kind="must_caveat",
                topic="interaction_terminology",
                intent="interaction_check",
                statement="Terminology overlap is not clinical interaction evidence.",
                evidence_available=True,
            )
        ],
        coverage_level="direct",
    )
    understanding = response_with_label_evidence()
    understanding.primary_dossier.label_evidence.label_records[0] = (
        understanding.primary_dossier.label_evidence.label_records[0].model_copy(
            update={
                "descriptions": ["Aspirin is a salicylate."],
                "purposes": ["Pain reliever"],
                "dosages": ["Take 1 tablet every 4 hours."],
                "active_ingredients": ["ASPIRIN"],
                "inactive_ingredients": ["STARCH"],
            }
        )
    )

    packet = EvidenceAnswerSynthesizer.build_evidence_packet(
        understanding,
        contract=contract,
    )

    assert packet["answer_contract"]["coverage_level"] == "direct"
    assert packet["answer_contract"]["items"][0]["topic"] == "interaction_terminology"
    product_context = packet["label_product_context"][0]
    assert product_context["description"] == "Aspirin is a salicylate."
    assert product_context["purpose"] == "Pain reliever"
    assert product_context["active_ingredients"] == ["ASPIRIN"]

    allowed_citations = EvidenceAnswerSynthesizer.allowed_citations(packet)
    citable_source_ids = {entry["source_id"] for entry in packet["label_sections"]}
    assert all(source_id in citable_source_ids for source_id, _ in allowed_citations)


def test_query_answer_response_carries_contract_and_validation() -> None:
    understanding = response_with_label_evidence()
    service = QueryAnswerService(
        builder=offline_builder(),
        understanding_service=FakeUnderstandingService(understanding),
        synthesizer=FakeAnswerSynthesizer(),
    )

    response = service.answer("Can I take aspirin?")

    assert response.contract.coverage_level in {"direct", "partial", "limited", "none"}
    assert response.validation is not None


def test_query_answer_response_carries_critique_without_critic_configured() -> None:
    class FakeCitedAnswerSynthesizer:
        def synthesize(
            self,
            query: str,
            understanding: QueryUnderstandingResponse,
            secondary_evidence: list[SecondaryDrugEvidence] | None = None,
            context_evidence: list[ContextTargetedEvidence] | None = None,
            contract: AnswerContract | None = None,
        ) -> AnswerSynthesisResult:
            return AnswerSynthesisResult(
                answer=EvidenceAnswer(
                    bullets=[
                        EvidenceBullet(
                            text="Aspirin warning text was retrieved.",
                            citations=[
                                EvidenceCitation(
                                    source_id="label-1", section="warnings"
                                )
                            ],
                        )
                    ],
                    limitations=[],
                    safety_note=STANDARD_SAFETY_NOTE,
                )
            )

    understanding = response_with_label_evidence()
    service = QueryAnswerService(
        builder=offline_builder(),
        understanding_service=FakeUnderstandingService(understanding),
        synthesizer=FakeCitedAnswerSynthesizer(),
    )

    response = service.answer("Can I take aspirin?")

    assert response.critique.enabled is False
    assert response.critique.source == "none"
    assert response.answer is not None
    assert response.answer.bullets[0].citations[0].support_status is None
    assert response.critique.citations == []


def test_secondary_evidence_ignores_resolved_mentions_outside_final_state() -> None:
    understanding = response_with_secondary_mention()
    stray_concept = RxNormConcept(
        rxcui="999",
        name="eyes alive lubricating",
        tty="BN",
    )
    understanding = understanding.model_copy(
        update={
            "resolved_drugs": [
                *understanding.resolved_drugs,
                ResolvedDrugMention(
                    text="eyes",
                    role="mentioned_drug",
                    selected_concept=stray_concept,
                ),
            ]
        }
    )

    class TrackingOpenFDAStore(OpenFDALabelStore):
        def __init__(self) -> None:
            super().__init__(allow_live=False, use_cache=False)
            self.standard_calls: list[tuple[str, str | None, int]] = []

        def get_label_evidence(
            self,
            rxcui: str,
            fallback_name: str | None = None,
            limit: int = 5,
        ) -> OpenFDALabelEvidence:
            self.standard_calls.append((rxcui, fallback_name, limit))
            return OpenFDALabelEvidence(rxcui=rxcui, label_limit=limit)

    store = TrackingOpenFDAStore()
    evidence = build_secondary_evidence(
        understanding,
        DossierBuilder(
            rxnorm_store=RxNormParquetStore(),
            openfda_store=store,
        ),
        QueryAnswerParameters(interaction_lookup_limit=0),
    )

    assert [item.resolved_concept.rxcui for item in evidence] == ["5640"]
    assert store.standard_calls == [("5640", "ibuprofen", 3)]


def test_evidence_coverage_match_includes_source_reference() -> None:
    understanding = response_with_label_evidence().model_copy(
        update={
            "state": QueryState(
                primary_drug="aspirin",
                all_drugs_mentioned=["aspirin"],
                conditions=["aspirin"],
            ),
        }
    )
    service = QueryAnswerService(
        builder=offline_builder(),
        understanding_service=FakeUnderstandingService(understanding),
        synthesizer=FakeAnswerSynthesizer(),
    )

    response = service.answer("Can I take aspirin?")

    condition_item = next(
        item
        for item in response.coverage.items
        if item.category == "condition" and item.label == "aspirin"
    )
    assert condition_item.status == "addressed"
    assert condition_item.source_id == "label-1"
    assert condition_item.section == "warnings"
    assert condition_item.matched_evidence is not None


def test_evidence_snippet_uses_word_boundaries() -> None:
    text = (
        " ".join(f"prefixword{index}" for index in range(20))
        + " "
        "People with acne should follow label directions carefully. "
        "Contact a clinician if symptoms worsen."
    )
    match_start = text.index("acne")
    match_end = match_start + len("acne")

    snippet = evidence_snippet(text, match_start, match_end)

    assert "acne" in snippet
    assert "with acne should" in snippet
    assert snippet.startswith("...")
    assert snippet.endswith("...")
    assert not snippet.startswith("...ord")
    assert not snippet.endswith(" ")


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
        secondary_evidence: list[SecondaryDrugEvidence] | None = None,
        context_evidence: list[ContextTargetedEvidence] | None = None,
        contract: AnswerContract | None = None,
    ) -> AnswerSynthesisResult:
        return AnswerSynthesisResult(
            answer=EvidenceAnswer(
                bullets=[],
                limitations=[],
                safety_note=STANDARD_SAFETY_NOTE,
            )
        )


def fake_secondary_builder() -> DossierBuilder:
    class FakeSecondaryOpenFDAStore(OpenFDALabelStore):
        def __init__(self) -> None:
            super().__init__(allow_live=False, use_cache=False)

        def get_label_evidence(
            self,
            rxcui: str,
            fallback_name: str | None = None,
            limit: int = 5,
        ) -> OpenFDALabelEvidence:
            if rxcui == "5640":
                evidence = secondary_evidence_fixture().label_evidence
                assert evidence is not None
                return evidence.model_copy(update={"label_limit": limit})
            return OpenFDALabelEvidence(rxcui=rxcui, label_limit=limit)

        def get_interaction_label_evidence(
            self,
            rxcui: str,
            interaction_name: str,
            fallback_name: str | None = None,
            limit: int = 3,
        ) -> OpenFDALabelEvidence:
            return OpenFDALabelEvidence(rxcui=rxcui, label_limit=limit)

    return DossierBuilder(
        rxnorm_store=RxNormParquetStore(),
        openfda_store=FakeSecondaryOpenFDAStore(),
    )


def fake_aspirin_secondary_builder() -> DossierBuilder:
    class FakeAspirinOpenFDAStore(OpenFDALabelStore):
        def __init__(self) -> None:
            super().__init__(allow_live=False, use_cache=False)

        def get_label_evidence(
            self,
            rxcui: str,
            fallback_name: str | None = None,
            limit: int = 5,
        ) -> OpenFDALabelEvidence:
            if rxcui == "1191":
                return OpenFDALabelEvidence(
                    rxcui=rxcui,
                    labels_found=1,
                    label_limit=limit,
                    retrieval_mode="standard_secondary_label_lookup",
                    label_records=[
                        OpenFDALabelRecord(
                            source_id="label-aspirin",
                            brand_names=["Aspirin"],
                            generic_names=["ASPIRIN"],
                            provenance_tags=["standard_secondary_label_lookup"],
                        )
                    ],
                    sections={
                        "warnings": [
                            LabelSection(
                                section="warnings",
                                text="Aspirin warning text.",
                                source_id="label-aspirin",
                                provenance_tags=[
                                    "standard_secondary_label_lookup"
                                ],
                            )
                        ]
                    },
                )
            return OpenFDALabelEvidence(rxcui=rxcui, label_limit=limit)

        def get_interaction_label_evidence(
            self,
            rxcui: str,
            interaction_name: str,
            fallback_name: str | None = None,
            limit: int = 3,
        ) -> OpenFDALabelEvidence:
            return OpenFDALabelEvidence(rxcui=rxcui, label_limit=limit)

    return DossierBuilder(
        rxnorm_store=RxNormParquetStore(),
        openfda_store=FakeAspirinOpenFDAStore(),
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


def response_with_secondary_mention() -> QueryUnderstandingResponse:
    aspirin_concept = RxNormConcept(rxcui="1191", name="aspirin", tty="IN")
    ibuprofen_concept = RxNormConcept(rxcui="5640", name="ibuprofen", tty="IN")
    understanding = response_with_label_evidence()
    return understanding.model_copy(
        update={
            "query": "Can I take aspirin with ibuprofen?",
            "state": QueryState(
                primary_drug="aspirin",
                all_drugs_mentioned=["aspirin", "ibuprofen"],
                current_medications=["ibuprofen"],
                intent="interaction_check",
            ),
            "resolved_drugs": [
                ResolvedDrugMention(
                    text="aspirin",
                    role="primary_drug",
                    selected_concept=aspirin_concept,
                ),
                ResolvedDrugMention(
                    text="ibuprofen",
                    role="mentioned_drug",
                    selected_concept=ibuprofen_concept,
                ),
                ResolvedDrugMention(
                    text="ibuprofen",
                    role="current_medication",
                    selected_concept=ibuprofen_concept,
                ),
            ],
        }
    )


def secondary_evidence_fixture() -> SecondaryDrugEvidence:
    return SecondaryDrugEvidence(
        mention_text="ibuprofen",
        role="mentioned_drug",
        resolved_concept=RxNormConcept(rxcui="5640", name="ibuprofen", tty="IN"),
        label_evidence=OpenFDALabelEvidence(
            rxcui="5640",
            labels_found=1,
            label_limit=3,
            retrieval_mode="standard_secondary_label_lookup",
            label_records=[
                OpenFDALabelRecord(
                    source_id="label-2",
                    brand_names=["Ibuprofen"],
                    generic_names=["IBUPROFEN"],
                    manufacturer_names=["Example Manufacturer"],
                )
            ],
            sections={
                "warnings": [
                    LabelSection(
                        section="warnings",
                        text="Ibuprofen warning text.",
                        source_id="label-2",
                    )
                ],
                "drug_interactions": [
                    LabelSection(
                        section="drug_interactions",
                        text="Ibuprofen interaction text.",
                        source_id="label-2",
                    )
                ],
            },
        ),
        retrieval_modes=["standard_secondary_label_lookup"],
    )


def test_network_adds_primary_ingredient_as_center() -> None:
    cream = RxNormConcept(
        rxcui="198300", name="tretinoin 1 MG/ML Topical Cream", tty="SCD"
    )
    understanding = QueryUnderstandingResponse(
        query="Can I use tretinoin cream?",
        state=QueryState(
            primary_drug="tretinoin cream",
            all_drugs_mentioned=["tretinoin cream"],
        ),
        primary_dossier=DrugDossier(
            query="tretinoin cream",
            resolved_drug=cream,
            rxnorm_neighborhood=RxNormNeighborhood(),
        ),
    )

    network = build_question_rxnorm_network(
        understanding,
        [],
        DossierBuilder(
            rxnorm_store=RxNormParquetStore(),
            openfda_store=OpenFDALabelStore(allow_live=False, use_cache=False),
        ),
        QueryAnswerParameters(),
    )

    center_by_rxcui = {center.rxcui: center for center in network.centers}
    assert center_by_rxcui["198300"].role == "primary_drug"
    # The active ingredient becomes its own highlighted center with its own
    # neighborhood, not just an incidental connected node.
    assert "10753" in center_by_rxcui
    assert center_by_rxcui["10753"].role == "ingredient"


def test_question_rxnorm_network_two_drugs_flags_shared_nodes() -> None:
    aspirin = RxNormConcept(rxcui="1191", name="aspirin", tty="IN")
    ibuprofen = RxNormConcept(rxcui="5640", name="ibuprofen", tty="IN")
    shared = RxNormConcept(rxcui="rx-nsaid", name="NSAID", tty="EPC")

    primary_neighborhood = RxNormNeighborhood(
        nodes=[shared],
        edges=[
            RxNormEdge(
                source_rxcui="1191",
                source_name="aspirin",
                target_rxcui="rx-nsaid",
                target_name="NSAID",
                relation="isa",
            )
        ],
    )
    understanding = QueryUnderstandingResponse(
        query="Can I take aspirin with ibuprofen?",
        state=QueryState(
            primary_drug="aspirin",
            all_drugs_mentioned=["aspirin", "ibuprofen"],
        ),
        primary_dossier=DrugDossier(
            query="aspirin",
            resolved_drug=aspirin,
            rxnorm_neighborhood=primary_neighborhood,
        ),
    )

    ibuprofen_neighborhood = RxNormNeighborhood(
        nodes=[shared],
        edges=[
            RxNormEdge(
                source_rxcui="5640",
                source_name="ibuprofen",
                target_rxcui="rx-nsaid",
                target_name="NSAID",
                relation="isa",
            )
        ],
    )

    class FakeRxNormStore:
        def get_neighborhood(
            self, rxcui: str, *, depth: int, max_edges: int
        ) -> RxNormNeighborhood:
            return ibuprofen_neighborhood if rxcui == "5640" else RxNormNeighborhood()

    secondary = SecondaryDrugEvidence(
        mention_text="ibuprofen",
        role="mentioned_drug",
        resolved_concept=ibuprofen,
    )

    network = build_question_rxnorm_network(
        understanding,
        [secondary],
        DossierBuilder(
            rxnorm_store=FakeRxNormStore(),  # type: ignore[arg-type]
            openfda_store=OpenFDALabelStore(allow_live=False, use_cache=False),
        ),
        QueryAnswerParameters(),
    )

    center_rxcuis = {c.rxcui for c in network.centers}
    assert center_rxcuis == {"1191", "5640"}
    assert "rx-nsaid" in network.shared_rxcuis
    assert "1191" in network.node_membership["rx-nsaid"]
    assert "5640" in network.node_membership["rx-nsaid"]


def test_question_rxnorm_network_single_drug_has_no_shared_nodes() -> None:
    aspirin = RxNormConcept(rxcui="1191", name="aspirin", tty="IN")
    salicylate = RxNormConcept(rxcui="rx-sal", name="salicylate", tty="IN")

    understanding = QueryUnderstandingResponse(
        query="Can I take aspirin?",
        state=QueryState(primary_drug="aspirin", all_drugs_mentioned=["aspirin"]),
        primary_dossier=DrugDossier(
            query="aspirin",
            resolved_drug=aspirin,
            rxnorm_neighborhood=RxNormNeighborhood(
                nodes=[salicylate],
                edges=[
                    RxNormEdge(
                        source_rxcui="1191",
                        source_name="aspirin",
                        target_rxcui="rx-sal",
                        target_name="salicylate",
                        relation="isa",
                    )
                ],
            ),
        ),
    )

    class FakeRxNormStore:
        def get_neighborhood(
            self, rxcui: str, *, depth: int, max_edges: int
        ) -> RxNormNeighborhood:
            return RxNormNeighborhood()

    network = build_question_rxnorm_network(
        understanding,
        [],
        DossierBuilder(
            rxnorm_store=FakeRxNormStore(),  # type: ignore[arg-type]
            openfda_store=OpenFDALabelStore(allow_live=False, use_cache=False),
        ),
        QueryAnswerParameters(),
    )

    assert len(network.centers) == 1
    assert network.centers[0].rxcui == "1191"
    assert network.centers[0].role == "primary_drug"
    assert network.shared_rxcuis == []
    node_rxcuis = {n.rxcui for n in network.nodes}
    assert {"1191", "rx-sal"} <= node_rxcuis


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


def test_query_extraction_sanitizes_wrong_bucket_allergy_terms() -> None:
    state = HybridQueryExtractor()._parse_llm_state(
        {
            "primary_drug": "ibuprofen",
            "allergies": ["pollen"],
            "conditions": ["allergy", "migraine"],
            "patient_context": ["adult", "allergies"],
            "intents": ["allergy_context_check"],
        }
    )

    assert state.allergies == ["pollen"]
    assert state.conditions == ["migraine"]
    assert state.patient_context == ["adult"]


def test_query_understanding_scanner_does_not_fuzzy_match_stop_words(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QUERY_EXTRACTION_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("QUERY_EXTRACTION_OPENAI_MODEL", raising=False)
    service = QueryUnderstandingService(builder=offline_builder())

    response = service.understand(
        "is it a problem to use tretinoin and Benzoyl peroxide "
        "for my acne at the same time?",
        openfda_limit=1,
    )

    resolved_names = {
        mention.selected_concept.name
        for mention in response.resolved_drugs
        if mention.selected_concept
    }
    assert resolved_names == {"tretinoin", "benzoyl peroxide"}
    assert response.state.all_drugs_mentioned == ["Benzoyl peroxide", "tretinoin"]
    assert response.state.intents == ["interaction_check", "label_context_check"]

    response = service.understand(
        "I currently take cetirizine for my pollen allergy. can i take both "
        "ibuprofen and aspirin against swollen eyes?",
        openfda_limit=1,
    )

    resolved_mentions = {
        mention.text: mention.selected_concept.name
        for mention in response.resolved_drugs
        if mention.selected_concept
    }
    assert resolved_mentions == {
        "aspirin": "aspirin",
        "cetirizine": "cetirizine",
        "ibuprofen": "ibuprofen",
    }
