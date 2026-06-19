from __future__ import annotations

import re

from src.query_answer.coverage import normalize
from src.query_answer.models import (
    AnswerContract,
    AnswerContractItem,
    AnswerValidationReport,
    EvidenceAnswer,
    ValidationFinding,
)

YES_NO_FRAMING_PATTERNS = (
    r"\bit(?:'s| is) (?:not )?safe\b",
    r"\bit(?:'s| is) unsafe\b",
    r"\byou can take\b",
    r"\byou should(?:n't| not)? take\b",
    r"\byou (?:can|should)(?:n't| not)? use\b",
    r"\bit'?s fine to\b",
    r"\byou are (?:cleared|allowed) to\b",
)
YES_NO_FRAMING_CAVEAT = (
    "This is not a determination of safety; discuss your specific situation "
    "with a clinician or pharmacist."
)


def validate_and_enforce(
    answer: EvidenceAnswer | None,
    contract: AnswerContract,
) -> tuple[EvidenceAnswer | None, AnswerValidationReport]:
    """Enforce the answer contract against the generated answer.

    The symbolic layer backstops the model here: any must_caveat it dropped is
    appended deterministically rather than left to chance, and unaddressed
    must_mention topics or yes/no framing are recorded as findings instead of
    papered over.
    """

    if answer is None:
        return None, AnswerValidationReport()

    findings: list[ValidationFinding] = []
    limitations = list(answer.limitations)
    enforced: list[str] = []

    for item in contract.items:
        if item.kind != "must_caveat" or _already_covered(item.statement, limitations):
            continue
        limitations.append(item.statement)
        enforced.append(item.statement)
        findings.append(
            ValidationFinding(
                kind="missing_caveat_enforced",
                severity="warning",
                message=(
                    f"Generated answer omitted a required caveat for "
                    f"'{item.topic}'; it was appended deterministically."
                ),
                topic=item.topic,
            )
        )

    combined_text = " ".join(
        [answer.response, answer.evidence_summary, *(b.text for b in answer.bullets)]
    )
    if _has_yes_no_framing(combined_text) and YES_NO_FRAMING_CAVEAT not in limitations:
        limitations.append(YES_NO_FRAMING_CAVEAT)
        enforced.append(YES_NO_FRAMING_CAVEAT)
        findings.append(
            ValidationFinding(
                kind="yes_no_framing",
                severity="warning",
                message="Generated answer used yes/no medical-advice framing.",
            )
        )

    for item in contract.items:
        if item.kind != "must_mention" or not item.evidence_available:
            continue
        if not _topic_addressed(item, answer):
            findings.append(
                ValidationFinding(
                    kind="must_mention_unaddressed",
                    severity="warning",
                    message=(
                        f"Retrieved evidence for '{item.topic}' was available but "
                        "the generated answer did not cite it."
                    ),
                    topic=item.topic,
                )
            )

    updated_answer = answer.model_copy(update={"limitations": limitations})
    report = AnswerValidationReport(
        findings=findings,
        enforced_caveats=enforced,
        passed=not any(finding.severity == "warning" for finding in findings),
    )
    return updated_answer, report


def _already_covered(statement: str, limitations: list[str]) -> bool:
    if statement in limitations:
        return True
    normalized_statement = normalize(statement)
    return any(
        normalized_statement in normalize(existing) for existing in limitations
    )


def _has_yes_no_framing(text: str) -> bool:
    normalized = text.casefold()
    return any(re.search(pattern, normalized) for pattern in YES_NO_FRAMING_PATTERNS)


def _topic_addressed(item: AnswerContractItem, answer: EvidenceAnswer) -> bool:
    if not item.required_sections:
        return True
    return any(
        citation.section in item.required_sections
        for bullet in answer.bullets
        for citation in bullet.citations
    )
