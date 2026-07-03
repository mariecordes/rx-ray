from src.dossier.models import RxNormConcept
from src.evals.metrics import evaluate_question
from src.evals.models import (
    CoverageAssertion,
    EvalExpectation,
    EvalQuestion,
    EvalRunResult,
)
from src.evals.report import build_report
from src.query_answer.models import (
    EvidenceAnswer,
    EvidenceBullet,
    EvidenceCitation,
    EvidenceCoverageItem,
    EvidenceCoverageReport,
    QueryAnswerResponse,
    ValidationFinding,
)
from src.query_answer.models import AnswerValidationReport
from src.query_understanding.models import (
    QueryState,
    QueryUnderstandingResponse,
    ResolvedDrugMention,
)


def make_response(**overrides) -> QueryAnswerResponse:
    understanding = QueryUnderstandingResponse(
        query="Can I take ibuprofen if I'm allergic to aspirin?",
        state=QueryState(
            primary_drug="ibuprofen",
            all_drugs_mentioned=["ibuprofen", "aspirin"],
            allergies=["aspirin"],
            intents=["interaction_check", "allergy_context_check"],
        ),
        resolved_drugs=[
            ResolvedDrugMention(
                text="ibuprofen",
                role="primary_drug",
                selected_concept=RxNormConcept(rxcui="5640", name="ibuprofen"),
            ),
            ResolvedDrugMention(
                text="aspirin",
                role="mentioned_drug",
                selected_concept=RxNormConcept(rxcui="1191", name="aspirin"),
            ),
        ],
    )
    defaults = dict(
        understanding=understanding,
        answer=EvidenceAnswer(
            response="The retrieved labels raise caution.",
            bullets=[
                EvidenceBullet(
                    text="Labels warn about combining NSAIDs.",
                    citations=[
                        EvidenceCitation(
                            source_id="src1",
                            section="warnings",
                            support_status="accurate",
                        )
                    ],
                )
            ],
            limitations=["No drug_interactions text mentioning naproxen retrieved."],
            safety_note="Educational information only.",
        ),
        coverage=EvidenceCoverageReport(
            items=[
                EvidenceCoverageItem(
                    category="allergy",
                    label="aspirin",
                    status="addressed",
                    reason="matched warnings text",
                ),
                EvidenceCoverageItem(
                    category="intent",
                    label="interaction_check",
                    status="not_retrieved",
                    reason="no interaction section retrieved",
                ),
            ]
        ),
    )
    defaults.update(overrides)
    return QueryAnswerResponse(**defaults)


def make_question(**expected) -> EvalQuestion:
    return EvalQuestion(
        id="q_test",
        question="Can I take ibuprofen if I'm allergic to aspirin?",
        category="interaction_2",
        expected=EvalExpectation(**expected),
    )


def check_names(result):
    return {check.name: check.passed for check in result.checks}


def test_expected_terms_resolve_via_concept_or_mention_text():
    question = make_question(drugs=["ibuprofen", "aspirin"])
    result = evaluate_question(question, make_response())
    assert check_names(result)["drugs_resolved"] is True
    assert result.field_scores["drugs"].recall == 1.0


def test_missing_expected_drug_fails_resolution_check():
    question = make_question(drugs=["ibuprofen", "naproxen"])
    result = evaluate_question(question, make_response())
    assert check_names(result)["drugs_resolved"] is False
    assert result.field_scores["drugs"].matched == 1


def test_state_field_checks_cover_allergies_and_intents():
    question = make_question(
        allergies=["aspirin"], intents=["interaction_check"]
    )
    result = evaluate_question(question, make_response())
    names = check_names(result)
    assert names["allergies_extracted"] is True
    assert names["intents_extracted"] is True


def test_normalized_containment_matches_specific_concepts():
    question = make_question(patient_context=["8-year-old"])
    response = make_response()
    response.understanding.state.patient_context = ["8 year old child"]
    result = evaluate_question(question, response)
    assert check_names(result)["patient_context_extracted"] is True


def test_coverage_assertion_checks_status_membership():
    question = make_question(
        coverage=[
            CoverageAssertion(
                category="allergy", label="aspirin", status_in=["addressed"]
            ),
            CoverageAssertion(
                category="intent",
                label="interaction_check",
                status_in=["addressed"],
            ),
        ]
    )
    result = evaluate_question(question, make_response())
    names = check_names(result)
    assert names["coverage:allergy:aspirin"] is True
    assert names["coverage:intent:interaction_check"] is False


def test_trap_unresolved_fails_when_fictional_drug_resolves():
    question = make_question(unresolved=["zortivan"])
    response = make_response()
    response.understanding.resolved_drugs.append(
        ResolvedDrugMention(
            text="Zortivan",
            role="mentioned_drug",
            selected_concept=RxNormConcept(rxcui="999", name="zortivan"),
        )
    )
    result = evaluate_question(question, response)
    assert check_names(result)["trap_terms_unresolved"] is False


def test_trap_unresolved_passes_when_mention_has_no_concept():
    question = make_question(unresolved=["zortivan"])
    response = make_response()
    response.understanding.resolved_drugs.append(
        ResolvedDrugMention(text="Zortivan", role="mentioned_drug")
    )
    result = evaluate_question(question, response)
    assert check_names(result)["trap_terms_unresolved"] is True


def test_limitation_substring_check():
    question = make_question(must_have_limitation_mentioning=["naproxen", "gout"])
    result = evaluate_question(question, make_response())
    check = next(
        c for c in result.checks if c.name == "limitations_mention_expected_gaps"
    )
    assert check.passed is False
    assert "gout" in check.detail
    assert "naproxen" not in check.detail


def test_yes_no_framing_check_reads_validation_findings():
    question = make_question()
    response = make_response(
        validation=AnswerValidationReport(
            findings=[
                ValidationFinding(
                    kind="yes_no_framing",
                    severity="warning",
                    message="Generated answer used yes/no framing.",
                )
            ]
        )
    )
    result = evaluate_question(question, response)
    assert check_names(result)["no_yes_no_framing"] is False


def test_report_aggregates_pass_rates_and_guardrails():
    question = make_question(drugs=["ibuprofen"])
    results = [
        evaluate_question(question, make_response(), repeat=0),
        evaluate_question(question, make_response(), repeat=1),
    ]
    report = build_report(
        EvalRunResult(
            mode="combined",
            questions_file="evals/questions.yml",
            repeats=2,
            started_at="2026-07-03T00:00:00+00:00",
            results=results,
        )
    )
    assert report["questions"] == 1
    assert report["headline"]["questions_passed"] == 1
    assert report["headline"]["verdict_flips"] == 0
    assert report["guardrails"]["critic_flagged_citations"] == 0.0
    assert report["per_category"]["interaction_2"]["passed"] == 1
