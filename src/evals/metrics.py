from __future__ import annotations

from src.evals.models import (
    BehaviorCheck,
    EvalQuestion,
    FieldScore,
    QuestionResult,
)
from src.query_answer.coverage import normalize
from src.query_answer.models import QueryAnswerResponse


def evaluate_question(
    question: EvalQuestion,
    response: QueryAnswerResponse,
    *,
    mode: str = "combined",
    repeat: int = 0,
    elapsed_s: float = 0.0,
) -> QuestionResult:
    """Score one pipeline response against a question's behavioral expectations.

    Deterministic and pure: every check reads structured pipeline output
    (extracted state, resolved concepts, coverage report, validation findings,
    critique) — never answer prose beyond the limitation-substring check.
    """

    expected = question.expected
    state = response.understanding.state
    checks: list[BehaviorCheck] = []
    field_scores: dict[str, FieldScore] = {}

    field_scores["drugs"] = _score_resolved_drugs(expected.drugs, response)
    if expected.drugs:
        checks.append(_recall_check("drugs_resolved", field_scores["drugs"]))

    for field_name, expected_terms, extracted_terms in (
        (
            "current_medications",
            expected.current_medications,
            state.current_medications,
        ),
        ("allergies", expected.allergies, state.allergies),
        ("conditions", expected.conditions, state.conditions),
        ("patient_context", expected.patient_context, state.patient_context),
        ("intents", expected.intents, state.intents),
    ):
        field_scores[field_name] = _score_terms(expected_terms, extracted_terms)
        if expected_terms:
            checks.append(
                _recall_check(f"{field_name}_extracted", field_scores[field_name])
            )

    if expected.unresolved:
        checks.append(_unresolved_check(expected.unresolved, response))

    for assertion in expected.coverage:
        checks.append(_coverage_check(assertion, response))

    # Limitation wording only exists on a generated answer; in symbolic mode
    # (answer=None by design) the check is skipped rather than auto-failed.
    if expected.must_have_limitation_mentioning and response.answer is not None:
        checks.append(
            _limitation_check(expected.must_have_limitation_mentioning, response)
        )

    if expected.forbid_yes_no_framing:
        finding_kinds = [f.kind for f in response.validation.findings]
        checks.append(
            BehaviorCheck(
                name="no_yes_no_framing",
                passed="yes_no_framing" not in finding_kinds,
                detail=(
                    "validation flagged yes/no medical-advice framing"
                    if "yes_no_framing" in finding_kinds
                    else ""
                ),
            )
        )

    answer = response.answer
    critic_status_counts: dict[str, int] = {}
    citation_count = 0
    if answer is not None:
        for bullet in answer.bullets:
            for citation in bullet.citations:
                citation_count += 1
                if citation.support_status:
                    critic_status_counts[citation.support_status] = (
                        critic_status_counts.get(citation.support_status, 0) + 1
                    )

    coverage_status_counts: dict[str, int] = {}
    for item in response.coverage.items:
        coverage_status_counts[item.status] = (
            coverage_status_counts.get(item.status, 0) + 1
        )

    return QuestionResult(
        question_id=question.id,
        category=question.category,
        mode=mode,  # type: ignore[arg-type]
        repeat=repeat,
        elapsed_s=round(elapsed_s, 2),
        checks=checks,
        field_scores=field_scores,
        coverage_status_counts=coverage_status_counts,
        validation_finding_kinds=[f.kind for f in response.validation.findings],
        enforced_caveat_count=len(response.validation.enforced_caveats),
        critic_status_counts=critic_status_counts,
        critic_regenerated=response.critique.regenerated,
        answer_generated=answer is not None,
        bullet_count=len(answer.bullets) if answer else 0,
        citation_count=citation_count,
        limitation_count=len(answer.limitations) if answer else 0,
    )


def _terms_match(expected: str, actual: str) -> bool:
    """Normalized containment either way, so 'tretinoin' matches
    'tretinoin 1 MG/ML Topical Cream' and '8-year-old' matches '8 year old'."""

    left, right = normalize(expected), normalize(actual)
    if not left or not right:
        return False
    return left in right or right in left


def _score_terms(expected: list[str], extracted: list[str]) -> FieldScore:
    missing = [
        term
        for term in expected
        if not any(_terms_match(term, item) for item in extracted)
    ]
    unexpected = [
        item
        for item in extracted
        if not any(_terms_match(term, item) for term in expected)
    ]
    matched = len(expected) - len(missing)
    extracted_matched = len(extracted) - len(unexpected)
    precision = extracted_matched / len(extracted) if extracted else None
    recall = matched / len(expected) if expected else None
    f1 = None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)
    return FieldScore(
        expected=len(expected),
        matched=matched,
        extracted=len(extracted),
        precision=precision,
        recall=recall,
        f1=f1,
        missing=missing,
        unexpected=unexpected,
        match_quality=_match_quality(len(expected), matched, unexpected),
    )


def _match_quality(
    expected_count: int, matched: int, unexpected: list[str]
) -> str | None:
    """Grade the set comparison; None when there is nothing to grade."""

    if expected_count == 0:
        return "extra" if unexpected else None
    if matched == expected_count:
        return "extra" if unexpected else "exact"
    return "partial" if matched else "none"


def _recall_check(name: str, score: FieldScore) -> BehaviorCheck:
    passed = score.expected == score.matched
    detail = "" if passed else (
        f"matched {score.matched}/{score.expected} expected terms"
    )
    return BehaviorCheck(name=name, passed=passed, detail=detail)


def _resolved_drug_names(response: QueryAnswerResponse) -> list[str]:
    """Names a resolved drug is reachable under: mention text + concept name."""

    names: list[str] = []
    for mention in response.understanding.resolved_drugs:
        if mention.selected_concept is None:
            continue
        names.append(mention.text)
        names.append(mention.selected_concept.name)
    return names


def _score_resolved_drugs(
    expected: list[str], response: QueryAnswerResponse
) -> FieldScore:
    """Score expected drugs against resolved mentions (one unit per mention,
    matchable via mention text or preferred concept name) so counts and the
    unexpected list aren't inflated by name/synonym pairs."""

    mentions = [
        (m.text, m.selected_concept.name)
        for m in response.understanding.resolved_drugs
        if m.selected_concept is not None
    ]

    def mention_matches(term: str, mention: tuple[str, str]) -> bool:
        return _terms_match(term, mention[0]) or _terms_match(term, mention[1])

    missing = [
        term
        for term in expected
        if not any(mention_matches(term, mention) for mention in mentions)
    ]
    unexpected = [
        mention[0]
        for mention in mentions
        if not any(mention_matches(term, mention) for term in expected)
    ]
    matched = len(expected) - len(missing)
    extracted_matched = len(mentions) - len(unexpected)
    precision = extracted_matched / len(mentions) if mentions else None
    recall = matched / len(expected) if expected else None
    f1 = None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)
    return FieldScore(
        expected=len(expected),
        matched=matched,
        extracted=len(mentions),
        precision=precision,
        recall=recall,
        f1=f1,
        missing=missing,
        unexpected=unexpected,
        match_quality=_match_quality(len(expected), matched, unexpected),
    )


def _unresolved_check(
    unresolved: list[str], response: QueryAnswerResponse
) -> BehaviorCheck:
    resolved_names = _resolved_drug_names(response)
    wrongly_resolved = [
        term
        for term in unresolved
        if any(_terms_match(term, name) for name in resolved_names)
    ]
    return BehaviorCheck(
        name="trap_terms_unresolved",
        passed=not wrongly_resolved,
        detail=(
            f"trap terms resolved to RxNorm concepts: {', '.join(wrongly_resolved)}"
            if wrongly_resolved
            else ""
        ),
    )


def _coverage_check(assertion, response: QueryAnswerResponse) -> BehaviorCheck:
    name = f"coverage:{assertion.category}:{assertion.label}"
    matches = [
        item
        for item in response.coverage.items
        if item.category == assertion.category
        and _terms_match(assertion.label, item.label)
    ]
    if not matches:
        return BehaviorCheck(
            name=name,
            passed=False,
            detail="no coverage item with this category and label",
        )
    statuses = {item.status for item in matches}
    passed = bool(statuses & set(assertion.status_in)) if assertion.status_in else True
    return BehaviorCheck(
        name=name,
        passed=passed,
        detail=(
            ""
            if passed
            else f"status {sorted(statuses)} not in {sorted(assertion.status_in)}"
        ),
    )


def _limitation_check(
    substrings: list[str], response: QueryAnswerResponse
) -> BehaviorCheck:
    limitations = response.answer.limitations if response.answer else []
    missing = [
        substring
        for substring in substrings
        if not any(_terms_match(substring, text) for text in limitations)
    ]
    return BehaviorCheck(
        name="limitations_mention_expected_gaps",
        passed=not missing,
        detail=(
            f"no limitation mentions: {', '.join(missing)}" if missing else ""
        ),
    )


__all__ = ["evaluate_question"]
