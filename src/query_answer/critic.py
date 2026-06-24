from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.query_answer.config import QueryAnswerParameters
from src.query_answer.models import (
    AnswerContract,
    AnswerCritique,
    CitationCritique,
    CitationSupportStatus,
    ContextTargetedEvidence,
    EvidenceAnswer,
    SecondaryDrugEvidence,
    ValidationFinding,
)
from src.query_answer.synthesizer import (
    EvidenceAnswerSynthesizer,
    list_value,
)
from src.query_answer.validation import validate_and_enforce
from src.query_understanding.models import QueryUnderstandingResponse

ANSWER_CRITIC_API_KEY_ENV = "ANSWER_CRITIC_OPENAI_API_KEY"
ANSWER_CRITIC_MODEL_ENV = "ANSWER_CRITIC_OPENAI_MODEL"
ANSWER_SYNTHESIS_API_KEY_ENV = "ANSWER_SYNTHESIS_OPENAI_API_KEY"
ANSWER_SYNTHESIS_MODEL_ENV = "ANSWER_SYNTHESIS_OPENAI_MODEL"
ANSWER_CRITIC_PROMPT_KEY = "evidence_answer_critic"

# Bullets are already hard-capped to 5 upstream (parse_answer_data); these are
# a defensive backstop so a misbehaving model can't blow up the critic prompt.
MAX_CRITIC_BULLETS = 7
MAX_CRITIC_CITATIONS = 10

VALID_SUPPORT_STATUSES: tuple[CitationSupportStatus, ...] = (
    "accurate",
    "not_reflected",
    "contradicted",
    "misrepresented",
    "misrepresented_used",
)


class CriticJsonRequester(Protocol):
    def __call__(
        self,
        *,
        messages: list[dict[str, str]],
        prompt_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Return parsed JSON from a critic model call."""


@dataclass
class CritiqueOutcome:
    critique: AnswerCritique
    needs_regeneration: bool = False
    notes: list[str] = field(default_factory=list)


def apply_citation_statuses(
    answer: EvidenceAnswer,
    critique: AnswerCritique,
) -> EvidenceAnswer:
    overrides = {
        (citation.bullet_index, citation.citation_index): citation.support_status
        for citation in critique.citations
    }
    if not overrides:
        return answer
    bullets = []
    for bullet_index, bullet in enumerate(answer.bullets):
        citations = [
            citation.model_copy(
                update={"support_status": overrides[(bullet_index, citation_index)]}
            )
            if (bullet_index, citation_index) in overrides
            else citation
            for citation_index, citation in enumerate(bullet.citations)
        ]
        bullets.append(bullet.model_copy(update={"citations": citations}))
    return answer.model_copy(update={"bullets": bullets})


def critique_answer(
    *,
    query: str,
    answer: EvidenceAnswer,
    evidence_packet: dict[str, Any],
    json_requester: CriticJsonRequester | None = None,
) -> CritiqueOutcome:
    """Run the optional LLM critic over a generated answer's citations.

    For each citation actually used in the answer, the critic checks whether
    the claim text faithfully reflects the real cited label-section text, and
    whether the final response correctly uses that information. It may only
    judge against the supplied cited_text; it cannot invent citations or facts.
    """

    prompt_config = EvidenceAnswerSynthesizer._load_prompt_config(
        ANSWER_CRITIC_PROMPT_KEY
    )
    messages = EvidenceAnswerSynthesizer._format_messages(
        prompt_config.get("messages", []),
        query=query,
        generated_answer=json.dumps(_critic_input(answer, evidence_packet), indent=2),
    )
    data = _request_critic_json(
        messages=messages,
        prompt_config=prompt_config,
        json_requester=json_requester,
    )
    return _parse_critique(data, answer)


def finalize_answer_critique(
    *,
    query: str,
    understanding: QueryUnderstandingResponse,
    secondary_evidence: list[SecondaryDrugEvidence] | None,
    context_evidence: list[ContextTargetedEvidence] | None,
    answer: EvidenceAnswer | None,
    contract: AnswerContract,
    validation: Any,
    synthesizer: EvidenceAnswerSynthesizer,
    parameters: QueryAnswerParameters,
    critic_json_requester: CriticJsonRequester | None = None,
) -> tuple[EvidenceAnswer | None, AnswerCritique, Any]:
    """Run the optional LLM critic, with one bounded regeneration if needed.

    The critic is the only source of citation support_status (opt-in via
    parameters.enable_answer_critic, on by default; off in demo mode, where no
    synthesis LLM is configured). When it's off or unavailable, citations
    simply carry no support_status rather than falling back to a structural
    guess.
    """

    if answer is None:
        return None, AnswerCritique(), validation

    critic_available = critic_json_requester is not None or _critic_llm_configured()
    if not parameters.enable_answer_critic or not critic_available:
        return answer, AnswerCritique(enabled=False, source="none"), validation

    evidence_packet = synthesizer.build_evidence_packet(
        understanding,
        secondary_evidence=secondary_evidence or [],
        context_evidence=context_evidence or [],
        contract=contract,
    )
    outcome = critique_answer(
        query=query,
        answer=answer,
        evidence_packet=evidence_packet,
        json_requester=critic_json_requester,
    )
    answer = apply_citation_statuses(answer, outcome.critique)
    critique = outcome.critique

    if outcome.needs_regeneration and parameters.critic_max_regenerations > 0:
        feedback = _format_critic_feedback(outcome.critique)
        regen_result = synthesizer.synthesize(
            query,
            understanding,
            secondary_evidence=secondary_evidence,
            context_evidence=context_evidence,
            contract=contract,
            critic_feedback=feedback,
        )
        if regen_result.answer is not None:
            regenerated_answer, regenerated_validation = validate_and_enforce(
                regen_result.answer, contract
            )
            recheck = critique_answer(
                query=query,
                answer=regenerated_answer,
                evidence_packet=evidence_packet,
                json_requester=critic_json_requester,
            )
            answer = apply_citation_statuses(regenerated_answer, recheck.critique)
            validation = regenerated_validation
            critique = recheck.critique.model_copy(update={"regenerated": True})

    return answer, critique, validation


def _critic_input(
    answer: EvidenceAnswer,
    evidence_packet: dict[str, Any],
) -> dict[str, Any]:
    """Build the minimal critic payload: response, limitations, and -- for each
    citation actually used -- its claim text and the real cited label-section
    text (the same text, same truncation, the synthesis model was shown).

    Deliberately excludes the full evidence_packet, label_product_context, and
    answer_contract: the critic only needs enough to judge whether a claim and
    the response are faithful to what was actually retrieved and cited.
    """

    cited_text_by_key = {
        (section.get("source_id"), section.get("section")): section.get("text", "")
        for section in evidence_packet.get("label_sections", [])
    }
    rows: list[dict[str, Any]] = []
    for bullet_index, bullet in enumerate(answer.bullets[:MAX_CRITIC_BULLETS]):
        for citation_index, citation in enumerate(bullet.citations):
            if len(rows) >= MAX_CRITIC_CITATIONS:
                break
            rows.append(
                {
                    "bullet_index": bullet_index,
                    "citation_index": citation_index,
                    "claim_text": bullet.text,
                    "source_id": citation.source_id,
                    "section": citation.section,
                    "cited_text": cited_text_by_key.get(
                        (citation.source_id, citation.section), ""
                    ),
                }
            )
        if len(rows) >= MAX_CRITIC_CITATIONS:
            break
    return {
        "response": answer.response,
        "limitations": answer.limitations,
        "citations": rows,
    }


def _request_critic_json(
    *,
    messages: list[dict[str, str]],
    prompt_config: dict[str, Any],
    json_requester: CriticJsonRequester | None,
) -> dict[str, Any]:
    if json_requester is not None:
        return json_requester(messages=messages, prompt_config=prompt_config)

    from openai import OpenAI  # type: ignore[import-not-found]

    client = OpenAI(api_key=_critic_api_key())
    response = client.chat.completions.create(
        model=_critic_model(),
        response_format=prompt_config.get("response_format", {"type": "json_object"}),
        messages=messages,
        temperature=0,
    )
    content = response.choices[0].message.content or "{}"
    data = json.loads(content)
    if not isinstance(data, dict):
        return {}
    return data


def _parse_critique(data: dict[str, Any], answer: EvidenceAnswer) -> CritiqueOutcome:
    citations: list[CitationCritique] = []
    for item in list_value(data.get("citations")):
        bullet_index = _parse_index(item.get("bullet_index"))
        citation_index = _parse_index(item.get("citation_index"))
        if bullet_index is None or citation_index is None:
            continue
        if bullet_index < 0 or bullet_index >= len(answer.bullets):
            continue
        bullet_citations = answer.bullets[bullet_index].citations
        if citation_index < 0 or citation_index >= len(bullet_citations):
            continue
        status = str(item.get("support_status", "")).strip()
        if status not in VALID_SUPPORT_STATUSES:
            continue
        citations.append(
            CitationCritique(
                bullet_index=bullet_index,
                citation_index=citation_index,
                support_status=status,  # type: ignore[arg-type]
                rationale=str(item.get("rationale", "")).strip(),
                issues=[
                    str(issue).strip()
                    for issue in item.get("issues") or []
                    if str(issue).strip()
                ],
            )
        )

    global_findings = [
        ValidationFinding(
            kind=str(finding.get("kind", "critic_finding")).strip()
            or "critic_finding",
            severity="warning" if finding.get("severity") == "warning" else "info",
            message=str(finding.get("message", "")).strip(),
            topic=(
                str(finding.get("topic")).strip() if finding.get("topic") else None
            ),
        )
        for finding in list_value(data.get("global_findings"))
        if str(finding.get("message", "")).strip()
    ]

    critique = AnswerCritique(
        enabled=True,
        source="llm",
        citations=citations,
        global_findings=global_findings,
    )
    return CritiqueOutcome(
        critique=critique,
        needs_regeneration=bool(data.get("needs_regeneration")),
    )


def _parse_index(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_critic_feedback(critique: AnswerCritique) -> str:
    lines: list[str] = []
    for citation in critique.citations:
        if citation.support_status == "accurate" and not citation.issues:
            continue
        detail = (
            f"- Bullet {citation.bullet_index}, citation {citation.citation_index}: "
            f"support={citation.support_status}"
        )
        if citation.issues:
            detail += f"; issues={', '.join(citation.issues)}"
        if citation.rationale:
            detail += f"; {citation.rationale}"
        lines.append(detail)
    for finding in critique.global_findings:
        lines.append(f"- {finding.kind}: {finding.message}")
    return "\n".join(lines) if lines else "No specific citation issues were flagged."


def _critic_api_key() -> str | None:
    return os.getenv(ANSWER_CRITIC_API_KEY_ENV) or os.getenv(
        ANSWER_SYNTHESIS_API_KEY_ENV
    )


def _critic_model() -> str | None:
    return os.getenv(ANSWER_CRITIC_MODEL_ENV) or os.getenv(ANSWER_SYNTHESIS_MODEL_ENV)


def _critic_llm_configured() -> bool:
    return bool(_critic_api_key() and _critic_model())


__all__ = [
    "CriticJsonRequester",
    "CritiqueOutcome",
    "apply_citation_statuses",
    "critique_answer",
    "finalize_answer_critique",
]
