from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.query_answer.config import QueryAnswerParameters
from src.query_answer.models import (
    AnswerContract,
    AnswerCritique,
    ClaimCritique,
    ClaimSupportStatus,
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

# Caveats that are emitted structurally whenever an intent is present (e.g. the
# interaction-terminology caveat applies to every interaction question
# regardless of evidence quality) and should not by themselves downgrade a
# well-cited claim from "strong" to "partial".
STRUCTURAL_CAVEAT_TOPICS = {"interaction_terminology"}

VALID_SUPPORT_STATUSES: tuple[ClaimSupportStatus, ...] = (
    "strong",
    "partial",
    "limited",
    "none",
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


def deterministic_support_status(
    bullet_citation_sections: set[str],
    has_citations: bool,
    contract: AnswerContract,
) -> ClaimSupportStatus:
    """Classify one bullet's support status from its citations and the contract.

    This is the always-on floor: it never needs the LLM critic, so every bullet
    has a status even when the critic is disabled (e.g. in demo mode).
    """

    if not has_citations:
        return "none"
    addressed_sections = _addressed_intent_sections(contract)
    if not bullet_citation_sections & addressed_sections:
        return "limited"
    return "partial" if _has_unresolved_gap(contract) else "strong"


def apply_deterministic_statuses(
    answer: EvidenceAnswer,
    contract: AnswerContract,
) -> EvidenceAnswer:
    bullets = [
        bullet.model_copy(
            update={
                "support_status": deterministic_support_status(
                    {citation.section for citation in bullet.citations},
                    bool(bullet.citations),
                    contract,
                )
            }
        )
        for bullet in answer.bullets
    ]
    return answer.model_copy(update={"bullets": bullets})


def apply_critique_statuses(
    answer: EvidenceAnswer,
    critique: AnswerCritique,
) -> EvidenceAnswer:
    overrides = {claim.bullet_index: claim.support_status for claim in critique.claims}
    if not overrides:
        return answer
    bullets = [
        bullet.model_copy(update={"support_status": overrides[index]})
        if index in overrides
        else bullet
        for index, bullet in enumerate(answer.bullets)
    ]
    return answer.model_copy(update={"bullets": bullets})


def critique_answer(
    *,
    query: str,
    answer: EvidenceAnswer,
    evidence_packet: dict[str, Any],
    json_requester: CriticJsonRequester | None = None,
) -> CritiqueOutcome:
    """Run the optional LLM critic over a generated answer's claims.

    The critic may only assign a support_status the supplied evidence backs;
    it cannot invent citations or facts. It overlays statuses onto the
    deterministic floor and signals whether one bounded regeneration is
    warranted.
    """

    prompt_config = EvidenceAnswerSynthesizer._load_prompt_config(
        ANSWER_CRITIC_PROMPT_KEY
    )
    messages = EvidenceAnswerSynthesizer._format_messages(
        prompt_config.get("messages", []),
        query=query,
        evidence_packet=json.dumps(evidence_packet, indent=2),
        generated_answer=json.dumps(_answer_for_critic(answer), indent=2),
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
    """Apply the deterministic support-status floor and, if enabled, the
    optional LLM critic with one bounded regeneration.

    The deterministic floor always runs so every bullet has a support_status.
    The critic is opt-in (parameters.enable_answer_critic) and off by default
    (and in demo mode, where no synthesis LLM is configured).
    """

    if answer is None:
        return None, AnswerCritique(), validation

    answer = apply_deterministic_statuses(answer, contract)
    deterministic_claims = [
        ClaimCritique(
            bullet_index=index,
            support_status=bullet.support_status or "none",
        )
        for index, bullet in enumerate(answer.bullets)
    ]

    critic_available = critic_json_requester is not None or _critic_llm_configured()
    if not parameters.enable_answer_critic or not critic_available:
        return (
            answer,
            AnswerCritique(
                enabled=False,
                source="deterministic",
                claims=deterministic_claims,
            ),
            validation,
        )

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
    answer = apply_critique_statuses(answer, outcome.critique)
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
            regenerated_answer = apply_deterministic_statuses(
                regenerated_answer, contract
            )
            recheck = critique_answer(
                query=query,
                answer=regenerated_answer,
                evidence_packet=evidence_packet,
                json_requester=critic_json_requester,
            )
            answer = apply_critique_statuses(regenerated_answer, recheck.critique)
            validation = regenerated_validation
            critique = recheck.critique.model_copy(update={"regenerated": True})

    return answer, critique, validation


def _addressed_intent_sections(contract: AnswerContract) -> set[str]:
    sections: set[str] = set()
    for item in contract.items:
        if (
            item.coverage_category == "intent"
            and item.evidence_available
            and item.required_sections
        ):
            sections.update(item.required_sections)
    return sections


def _has_unresolved_gap(contract: AnswerContract) -> bool:
    return any(
        item.kind == "must_caveat" and item.topic not in STRUCTURAL_CAVEAT_TOPICS
        for item in contract.items
    )


def _answer_for_critic(answer: EvidenceAnswer) -> dict[str, Any]:
    return {
        "response": answer.response,
        "evidence_summary": answer.evidence_summary,
        "limitations": answer.limitations,
        "claims": [
            {
                "index": index,
                "text": bullet.text,
                "citations": [citation.model_dump() for citation in bullet.citations],
            }
            for index, bullet in enumerate(answer.bullets)
        ],
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
    claims: list[ClaimCritique] = []
    for item in list_value(data.get("claims")):
        index = _parse_index(item.get("index"))
        if index is None or index < 0 or index >= len(answer.bullets):
            continue
        status = str(item.get("support_status", "")).strip()
        if status not in VALID_SUPPORT_STATUSES:
            continue
        claims.append(
            ClaimCritique(
                bullet_index=index,
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
        claims=claims,
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
    for claim in critique.claims:
        if claim.support_status not in {"limited", "none"} and not claim.issues:
            continue
        detail = f"- Claim {claim.bullet_index}: support={claim.support_status}"
        if claim.issues:
            detail += f"; issues={', '.join(claim.issues)}"
        if claim.rationale:
            detail += f"; {claim.rationale}"
        lines.append(detail)
    for finding in critique.global_findings:
        lines.append(f"- {finding.kind}: {finding.message}")
    return "\n".join(lines) if lines else "No specific claim issues were flagged."


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
    "apply_critique_statuses",
    "apply_deterministic_statuses",
    "critique_answer",
    "deterministic_support_status",
    "finalize_answer_critique",
]
