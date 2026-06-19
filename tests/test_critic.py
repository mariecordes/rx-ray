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
    apply_critique_statuses,
    apply_deterministic_statuses,
    critique_answer,
    deterministic_support_status,
    run_guardrails_v3,
)
from src.query_answer.models import (
    AnswerContract,
    AnswerContractItem,
    AnswerCritique,
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


def contract_with_addressed_warnings() -> AnswerContract:
    return AnswerContract(
        items=[
            AnswerContractItem(
                kind="must_mention",
                topic="allergy_context_check",
                intent="allergy_context_check",
                statement="Address what the retrieved allergy label sections say.",
                evidence_available=True,
                required_sections=["warnings"],
                coverage_category="intent",
                coverage_label="allergy_context_check",
            )
        ],
        coverage_level="direct",
    )


def bullet(text: str, source_id: str | None, section: str | None) -> EvidenceBullet:
    citations = (
        [EvidenceCitation(source_id=source_id, section=section)]
        if source_id and section
        else []
    )
    return EvidenceBullet(text=text, citations=citations)


def answer_with_bullets(bullets: list[EvidenceBullet]) -> EvidenceAnswer:
    return EvidenceAnswer(
        response="Some response.",
        evidence_summary="Some summary.",
        summary="Some summary.",
        bullets=bullets,
        limitations=[],
        safety_note=STANDARD_SAFETY_NOTE,
    )


def test_deterministic_support_status_none_without_citations() -> None:
    status = deterministic_support_status(set(), False, AnswerContract())
    assert status == "none"


def test_deterministic_support_status_limited_when_citation_section_not_addressed() -> (
    None
):
    contract = contract_with_addressed_warnings()
    status = deterministic_support_status({"adverse_reactions"}, True, contract)
    assert status == "limited"


def test_deterministic_support_status_strong_when_addressed_and_no_gap() -> None:
    contract = contract_with_addressed_warnings()
    status = deterministic_support_status({"warnings"}, True, contract)
    assert status == "strong"


def test_deterministic_support_status_partial_when_unresolved_gap_present() -> None:
    contract = contract_with_addressed_warnings().model_copy(
        update={
            "items": [
                *contract_with_addressed_warnings().items,
                AnswerContractItem(
                    kind="must_caveat",
                    topic="missing_context",
                    statement="The retrieved labels did not explicitly mention X.",
                    evidence_available=False,
                ),
            ]
        }
    )
    status = deterministic_support_status({"warnings"}, True, contract)
    assert status == "partial"


def test_deterministic_support_status_ignores_structural_interaction_caveat() -> None:
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
            ),
            AnswerContractItem(
                kind="must_caveat",
                topic="interaction_terminology",
                intent="interaction_check",
                statement=(
                    "RxNorm terminology overlap is not evidence of a clinical "
                    "interaction."
                ),
                evidence_available=True,
                coverage_category="intent",
                coverage_label="interaction_check",
            ),
        ],
        coverage_level="direct",
    )
    status = deterministic_support_status({"drug_interactions"}, True, contract)
    assert status == "strong"


def test_apply_deterministic_statuses_sets_status_per_bullet() -> None:
    contract = contract_with_addressed_warnings()
    answer = answer_with_bullets(
        [
            bullet("Cited and addressed.", "label-1", "warnings"),
            bullet("Not cited.", None, None),
        ]
    )
    updated = apply_deterministic_statuses(answer, contract)
    assert updated.bullets[0].support_status == "strong"
    assert updated.bullets[1].support_status == "none"


def test_apply_critique_statuses_overrides_only_named_indices() -> None:
    answer = answer_with_bullets(
        [
            bullet("First.", "label-1", "warnings").model_copy(
                update={"support_status": "strong"}
            ),
            bullet("Second.", "label-1", "warnings").model_copy(
                update={"support_status": "strong"}
            ),
        ]
    )
    critique = AnswerCritique(
        enabled=True,
        source="llm",
        claims=[],
    )
    unchanged = apply_critique_statuses(answer, critique)
    assert unchanged.bullets[0].support_status == "strong"

    from src.query_answer.models import ClaimCritique

    critique_with_override = critique.model_copy(
        update={
            "claims": [
                ClaimCritique(bullet_index=0, support_status="limited"),
            ]
        }
    )
    overridden = apply_critique_statuses(answer, critique_with_override)
    assert overridden.bullets[0].support_status == "limited"
    assert overridden.bullets[1].support_status == "strong"


def test_critique_answer_parses_claims_and_findings_with_stub_requester() -> None:
    answer = answer_with_bullets(
        [bullet("Cited.", "label-1", "warnings")]
    )

    def fake_requester(*, messages: list[dict], prompt_config: dict) -> dict:
        return {
            "claims": [
                {
                    "index": 0,
                    "support_status": "strong",
                    "rationale": "Well supported.",
                    "issues": [],
                }
            ],
            "global_findings": [
                {
                    "kind": "missing_caveat",
                    "severity": "warning",
                    "message": "A caveat was missing.",
                }
            ],
            "needs_regeneration": True,
        }

    outcome = critique_answer(
        query="Can I take aspirin?",
        answer=answer,
        evidence_packet={"label_sections": []},
        json_requester=fake_requester,
    )

    assert outcome.needs_regeneration is True
    assert outcome.critique.enabled is True
    assert outcome.critique.source == "llm"
    assert outcome.critique.claims[0].support_status == "strong"
    assert outcome.critique.global_findings[0].kind == "missing_caveat"


def test_critique_answer_ignores_invalid_claim_indices_and_statuses() -> None:
    answer = answer_with_bullets([bullet("Cited.", "label-1", "warnings")])

    def fake_requester(*, messages: list[dict], prompt_config: dict) -> dict:
        return {
            "claims": [
                {"index": 5, "support_status": "strong"},
                {"index": 0, "support_status": "not-a-real-status"},
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
    assert outcome.critique.claims == []


def test_run_guardrails_v3_returns_none_when_no_answer() -> None:
    answer, critique, validation = run_guardrails_v3(
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


def test_run_guardrails_v3_disabled_returns_deterministic_floor() -> None:
    understanding = understanding_with_label_evidence()
    coverage = build_evidence_coverage(understanding)
    contract = build_answer_contract(understanding, coverage)
    answer = answer_with_bullets([bullet("Cited.", "label-1", "warnings")])

    final_answer, critique, validation = run_guardrails_v3(
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
    assert critique.source == "deterministic"
    assert len(critique.claims) == 1
    assert final_answer is not None
    assert final_answer.bullets[0].support_status is not None
    assert validation == "unchanged"


def test_run_guardrails_v3_enabled_without_regeneration(
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
            "claims": [{"index": 0, "support_status": "strong"}],
            "global_findings": [],
            "needs_regeneration": False,
        }

    final_answer, critique, _validation = run_guardrails_v3(
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
    assert final_answer.bullets[0].support_status == "strong"
    assert synth_calls == []


def test_run_guardrails_v3_regenerates_exactly_once(
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
            "evidence_summary": "Regenerated summary.",
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
            "claims": [{"index": 0, "support_status": "limited"}],
            "global_findings": [],
            "needs_regeneration": True,
        }

    final_answer, critique, _validation = run_guardrails_v3(
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


def test_run_guardrails_v3_skips_regeneration_when_max_is_zero(
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
            "claims": [{"index": 0, "support_status": "limited"}],
            "global_findings": [],
            "needs_regeneration": True,
        }

    final_answer, critique, _validation = run_guardrails_v3(
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
