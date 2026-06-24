import pytest

from src.dossier.models import (
    DrugDossier,
    LabelSection,
    OpenFDALabelEvidence,
    OpenFDALabelRecord,
    RxNormConcept,
)
from src.query_answer.config import QueryAnswerParameters
from src.query_answer.contract import build_answer_contract
from src.query_answer.coverage import build_evidence_coverage
from src.query_answer.critic import (
    MAX_CRITIC_BULLETS,
    MAX_CRITIC_CITATIONS,
    _critic_input,
    apply_citation_statuses,
    critique_answer,
    finalize_answer_critique,
)
from src.query_answer.models import (
    AnswerContract,
    AnswerCritique,
    CitationCritique,
    EvidenceAnswer,
    EvidenceBullet,
    EvidenceCitation,
)
from src.query_answer.synthesizer import EvidenceAnswerSynthesizer
from src.query_understanding.models import QueryState, QueryUnderstandingResponse

STANDARD_SAFETY_NOTE = (
    "This is an educational summary of retrieved public evidence, not medical advice."
)


def understanding_with_label_evidence() -> QueryUnderstandingResponse:
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


def bullet(
    text: str,
    source_id: str | None,
    section: str | None,
) -> EvidenceBullet:
    citations = (
        [EvidenceCitation(source_id=source_id, section=section)]
        if source_id and section
        else []
    )
    return EvidenceBullet(text=text, citations=citations)


def answer_with_bullets(bullets: list[EvidenceBullet]) -> EvidenceAnswer:
    return EvidenceAnswer(
        response="Some response.",
        bullets=bullets,
        limitations=[],
        safety_note=STANDARD_SAFETY_NOTE,
    )


def test_critic_input_includes_only_response_limitations_and_citations() -> None:
    answer = answer_with_bullets([bullet("Cited.", "label-1", "warnings")])
    evidence_packet = {
        "label_sections": [
            {"source_id": "label-1", "section": "warnings", "text": "Real text."}
        ],
        "label_product_context": [{"description": "not for the critic"}],
        "answer_contract": {"items": []},
        "state": {},
    }

    result = _critic_input(answer, evidence_packet)

    assert set(result.keys()) == {"response", "limitations", "citations"}
    assert result["citations"] == [
        {
            "bullet_index": 0,
            "citation_index": 0,
            "claim_text": "Cited.",
            "source_id": "label-1",
            "section": "warnings",
            "cited_text": "Real text.",
        }
    ]


def test_critic_input_looks_up_cited_text_and_falls_back_when_missing() -> None:
    answer = answer_with_bullets(
        [
            bullet("Matches a section.", "label-1", "warnings"),
            bullet("Cites something not in label_sections.", "label-2", "dosage"),
        ]
    )
    evidence_packet = {
        "label_sections": [
            {"source_id": "label-1", "section": "warnings", "text": "Warning text."}
        ]
    }

    result = _critic_input(answer, evidence_packet)

    assert result["citations"][0]["cited_text"] == "Warning text."
    assert result["citations"][1]["cited_text"] == ""


def test_critic_input_caps_bullets_considered() -> None:
    bullets = [
        bullet(f"Bullet {index}.", f"label-{index}", "warnings")
        for index in range(MAX_CRITIC_BULLETS + 3)
    ]
    answer = answer_with_bullets(bullets)
    evidence_packet = {
        "label_sections": [
            {"source_id": f"label-{index}", "section": "warnings", "text": "Text."}
            for index in range(MAX_CRITIC_BULLETS + 3)
        ]
    }

    result = _critic_input(answer, evidence_packet)

    considered_bullet_indices = {row["bullet_index"] for row in result["citations"]}
    assert max(considered_bullet_indices) < MAX_CRITIC_BULLETS


def test_critic_input_caps_total_flattened_citations() -> None:
    bullets = [
        EvidenceBullet(
            text=f"Bullet {bullet_index}.",
            citations=[
                EvidenceCitation(source_id=f"label-{bullet_index}", section="warnings"),
                EvidenceCitation(
                    source_id=f"label-{bullet_index}", section="contraindications"
                ),
                EvidenceCitation(
                    source_id=f"label-{bullet_index}", section="drug_interactions"
                ),
                EvidenceCitation(
                    source_id=f"label-{bullet_index}", section="adverse_reactions"
                ),
            ],
        )
        for bullet_index in range(3)
    ]
    answer = answer_with_bullets(bullets)

    result = _critic_input(answer, {"label_sections": []})

    assert len(result["citations"]) == MAX_CRITIC_CITATIONS


def test_apply_citation_statuses_overrides_only_named_citations() -> None:
    answer = answer_with_bullets(
        [
            EvidenceBullet(
                text="First.",
                citations=[
                    EvidenceCitation(source_id="label-1", section="warnings"),
                    EvidenceCitation(source_id="label-2", section="contraindications"),
                ],
            ),
            bullet("Second.", "label-1", "warnings"),
        ]
    )
    critique = AnswerCritique(
        enabled=True,
        source="llm",
        citations=[
            CitationCritique(
                bullet_index=0, citation_index=1, support_status="contradicted"
            ),
        ],
    )

    updated = apply_citation_statuses(answer, critique)

    assert updated.bullets[0].citations[0].support_status is None
    assert updated.bullets[0].citations[1].support_status == "contradicted"
    assert updated.bullets[1].citations[0].support_status is None


def test_critique_answer_parses_citations_and_findings_with_stub_requester() -> None:
    answer = answer_with_bullets([bullet("Cited.", "label-1", "warnings")])

    def fake_requester(*, messages: list[dict], prompt_config: dict) -> dict:
        return {
            "citations": [
                {
                    "bullet_index": 0,
                    "citation_index": 0,
                    "support_status": "accurate",
                    "rationale": "Faithfully reflects the cited text.",
                    "issues": [],
                }
            ],
            "global_findings": [
                {
                    "kind": "extra_nuance",
                    "severity": "info",
                    "message": "Worth a caveat.",
                }
            ],
            "needs_regeneration": False,
        }

    outcome = critique_answer(
        query="Can I take aspirin?",
        answer=answer,
        evidence_packet={"label_sections": []},
        json_requester=fake_requester,
    )

    assert outcome.needs_regeneration is False
    assert outcome.critique.enabled is True
    assert outcome.critique.source == "llm"
    assert outcome.critique.citations[0].support_status == "accurate"
    assert outcome.critique.global_findings[0].kind == "extra_nuance"


def test_critique_answer_ignores_invalid_citation_indices_and_statuses() -> None:
    answer = answer_with_bullets([bullet("Cited.", "label-1", "warnings")])

    def fake_requester(*, messages: list[dict], prompt_config: dict) -> dict:
        return {
            "citations": [
                {"bullet_index": 5, "citation_index": 0, "support_status": "accurate"},
                {"bullet_index": 0, "citation_index": 9, "support_status": "accurate"},
                {
                    "bullet_index": 0,
                    "citation_index": 0,
                    "support_status": "not-a-real-status",
                },
            ],
            "global_findings": [],
            "needs_regeneration": False,
        }

    outcome = critique_answer(
        query="Can I take aspirin?",
        answer=answer,
        evidence_packet={"label_sections": []},
        json_requester=fake_requester,
    )
    assert outcome.critique.citations == []


def test_finalize_answer_critique_returns_none_when_no_answer() -> None:
    answer, critique, validation = finalize_answer_critique(
        query="Can I take aspirin?",
        understanding=understanding_with_label_evidence(),
        secondary_evidence=None,
        context_evidence=None,
        answer=None,
        contract=AnswerContract(),
        validation="unchanged",
        synthesizer=EvidenceAnswerSynthesizer(),
        parameters=QueryAnswerParameters(enable_answer_critic=False),
    )
    assert answer is None
    assert critique == AnswerCritique()
    assert validation == "unchanged"


def test_finalize_answer_critique_disabled_returns_no_statuses() -> None:
    understanding = understanding_with_label_evidence()
    coverage = build_evidence_coverage(understanding)
    contract = build_answer_contract(understanding, coverage)
    answer = answer_with_bullets([bullet("Cited.", "label-1", "warnings")])

    final_answer, critique, validation = finalize_answer_critique(
        query="Can I take aspirin?",
        understanding=understanding,
        secondary_evidence=None,
        context_evidence=None,
        answer=answer,
        contract=contract,
        validation="unchanged",
        synthesizer=EvidenceAnswerSynthesizer(),
        parameters=QueryAnswerParameters(enable_answer_critic=False),
    )

    assert critique.enabled is False
    assert critique.source == "none"
    assert critique.citations == []
    assert final_answer is not None
    assert final_answer.bullets[0].citations[0].support_status is None
    assert validation == "unchanged"


def test_finalize_answer_critique_enabled_without_regeneration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANSWER_SYNTHESIS_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ANSWER_SYNTHESIS_OPENAI_MODEL", "test-model")
    understanding = understanding_with_label_evidence()
    coverage = build_evidence_coverage(understanding)
    contract = build_answer_contract(understanding, coverage)
    answer = answer_with_bullets([bullet("Cited.", "label-1", "warnings")])

    synth_calls: list[dict] = []

    def synth_requester(*, messages: list[dict], prompt_config: dict) -> dict:
        synth_calls.append({})
        raise AssertionError("synthesize should not be called when no regeneration")

    synthesizer = EvidenceAnswerSynthesizer(json_requester=synth_requester)

    def critic_requester(*, messages: list[dict], prompt_config: dict) -> dict:
        return {
            "citations": [
                {"bullet_index": 0, "citation_index": 0, "support_status": "accurate"}
            ],
            "global_findings": [],
            "needs_regeneration": False,
        }

    final_answer, critique, _validation = finalize_answer_critique(
        query="Can I take aspirin?",
        understanding=understanding,
        secondary_evidence=None,
        context_evidence=None,
        answer=answer,
        contract=contract,
        validation="unchanged",
        synthesizer=synthesizer,
        parameters=QueryAnswerParameters(enable_answer_critic=True),
        critic_json_requester=critic_requester,
    )

    assert critique.enabled is True
    assert critique.source == "llm"
    assert critique.regenerated is False
    assert final_answer.bullets[0].citations[0].support_status == "accurate"
    assert synth_calls == []


def test_finalize_answer_critique_regenerates_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANSWER_SYNTHESIS_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ANSWER_SYNTHESIS_OPENAI_MODEL", "test-model")
    understanding = understanding_with_label_evidence()
    coverage = build_evidence_coverage(understanding)
    contract = build_answer_contract(understanding, coverage)
    answer = answer_with_bullets([bullet("Weakly cited.", "label-1", "warnings")])

    synth_calls: list[list[dict]] = []

    def synth_requester(*, messages: list[dict], prompt_config: dict) -> dict:
        synth_calls.append(messages)
        return {
            "response": "Regenerated.",
            "bullets": [
                {
                    "text": "Regenerated bullet.",
                    "citations": [{"source_id": "label-1", "section": "warnings"}],
                }
            ],
            "limitations": [],
        }

    synthesizer = EvidenceAnswerSynthesizer(json_requester=synth_requester)

    critic_calls = {"count": 0}

    def critic_requester(*, messages: list[dict], prompt_config: dict) -> dict:
        critic_calls["count"] += 1
        return {
            "citations": [
                {
                    "bullet_index": 0,
                    "citation_index": 0,
                    "support_status": "misrepresented",
                }
            ],
            "global_findings": [],
            "needs_regeneration": True,
        }

    final_answer, critique, _validation = finalize_answer_critique(
        query="Can I take aspirin?",
        understanding=understanding,
        secondary_evidence=None,
        context_evidence=None,
        answer=answer,
        contract=contract,
        validation="unchanged",
        synthesizer=synthesizer,
        parameters=QueryAnswerParameters(
            enable_answer_critic=True, critic_max_regenerations=1
        ),
        critic_json_requester=critic_requester,
    )

    assert len(synth_calls) == 1, "exactly one regeneration should occur"
    assert critic_calls["count"] == 2, "critic runs once before and once after regen"
    assert critique.regenerated is True
    assert final_answer.bullets[0].text == "Regenerated bullet."


def test_finalize_answer_critique_skips_regeneration_when_max_is_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANSWER_SYNTHESIS_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ANSWER_SYNTHESIS_OPENAI_MODEL", "test-model")
    understanding = understanding_with_label_evidence()
    coverage = build_evidence_coverage(understanding)
    contract = build_answer_contract(understanding, coverage)
    answer = answer_with_bullets([bullet("Weakly cited.", "label-1", "warnings")])

    def synth_requester(*, messages: list[dict], prompt_config: dict) -> dict:
        raise AssertionError("synthesize should not be called when max is zero")

    synthesizer = EvidenceAnswerSynthesizer(json_requester=synth_requester)

    def critic_requester(*, messages: list[dict], prompt_config: dict) -> dict:
        return {
            "citations": [
                {
                    "bullet_index": 0,
                    "citation_index": 0,
                    "support_status": "misrepresented",
                }
            ],
            "global_findings": [],
            "needs_regeneration": True,
        }

    final_answer, critique, _validation = finalize_answer_critique(
        query="Can I take aspirin?",
        understanding=understanding,
        secondary_evidence=None,
        context_evidence=None,
        answer=answer,
        contract=contract,
        validation="unchanged",
        synthesizer=synthesizer,
        parameters=QueryAnswerParameters(
            enable_answer_critic=True, critic_max_regenerations=0
        ),
        critic_json_requester=critic_requester,
    )

    assert critique.regenerated is False
    assert final_answer.bullets[0].text == "Weakly cited."
