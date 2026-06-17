from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.dossier.models import DrugDossier, LabelSection, OpenFDALabelRecord, RxNormEdge
from src.query_answer.config import QueryAnswerParameters, load_query_answer_parameters
from src.query_answer.models import (
    ContextTargetedEvidence,
    EvidenceAnswer,
    EvidenceBullet,
    EvidenceCitation,
    SecondaryDrugEvidence,
)
from src.query_understanding.models import QueryUnderstandingResponse
from src.utils import load_prompts

ANSWER_SYNTHESIS_API_KEY_ENV = "ANSWER_SYNTHESIS_OPENAI_API_KEY"
ANSWER_SYNTHESIS_MODEL_ENV = "ANSWER_SYNTHESIS_OPENAI_MODEL"
ANSWER_SYNTHESIS_PROMPT_KEY = "evidence_answer_synthesis"
ANSWER_CITATION_RETRY_PROMPT_KEY = "evidence_answer_citation_retry"
STANDARD_SAFETY_NOTE = (
    "This is an educational summary of retrieved public evidence, not medical advice."
)
SOURCE_LINK_LIMITATION = (
    "The generated response could not be linked to specific retrieved label sources."
)

PRIORITIZED_SECTIONS = (
    "boxed_warning",
    "contraindications",
    "warnings",
    "drug_interactions",
    "pregnancy",
    "lactation",
    "pregnancy_or_breast_feeding",
    "indications_and_usage",
    "adverse_reactions",
    "use_in_specific_populations",
)
MAX_LABEL_TEXT_CHARS = 1000
MAX_LABEL_SECTIONS = 16
MAX_RXNORM_RELATIONSHIPS = 40


@dataclass
class AnswerSynthesisResult:
    answer: EvidenceAnswer | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class AnswerJsonRequester(Protocol):
    def __call__(
        self,
        *,
        messages: list[dict[str, str]],
        prompt_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Return parsed JSON from an answer-synthesis model call."""


class EvidenceAnswerSynthesizer:
    """Generate a compact grounded answer from query understanding evidence."""

    def __init__(
        self,
        parameters: QueryAnswerParameters | None = None,
        json_requester: AnswerJsonRequester | None = None,
    ) -> None:
        self.parameters = parameters or load_query_answer_parameters()
        self.json_requester = json_requester

    def synthesize(
        self,
        query: str,
        understanding: QueryUnderstandingResponse,
        secondary_evidence: list[SecondaryDrugEvidence] | None = None,
        context_evidence: list[ContextTargetedEvidence] | None = None,
    ) -> AnswerSynthesisResult:
        if understanding.primary_dossier is None:
            return AnswerSynthesisResult(
                warnings=[
                    "No primary medication dossier was available, so no evidence "
                    "summary was generated."
                ]
            )
        if not self._llm_configured():
            return AnswerSynthesisResult(
                warnings=[
                    f"{ANSWER_SYNTHESIS_API_KEY_ENV}/{ANSWER_SYNTHESIS_MODEL_ENV} "
                    "are not configured; no evidence summary was generated."
                ]
            )

        prompt_config = self._load_prompt()
        evidence_packet = self.build_evidence_packet(
            understanding,
            secondary_evidence=secondary_evidence or [],
            context_evidence=context_evidence or [],
        )
        messages = self._format_messages(
            prompt_config.get("messages", []),
            query=query,
            evidence_packet=json.dumps(evidence_packet, indent=2),
        )

        try:
            data = self._request_answer_json(
                messages=messages,
                prompt_config=prompt_config,
            )
        except ImportError:
            return AnswerSynthesisResult(
                warnings=[
                    "The OpenAI package is not installed; no evidence summary "
                    "was generated."
                ]
            )
        except Exception as exc:  # pragma: no cover - requires live LLM config
            return AnswerSynthesisResult(errors=[f"Answer synthesis failed: {exc}"])

        allowed_citations = self.allowed_citations(evidence_packet)
        answer = self.parse_answer_data(data, allowed_citations)
        if self._needs_source_retry(answer, allowed_citations):
            try:
                retry_answer = self._retry_with_citation_feedback(
                    query=query,
                    data=data,
                    evidence_packet=evidence_packet,
                    prompt_config=prompt_config,
                    allowed_citations=allowed_citations,
                )
            except Exception as exc:  # pragma: no cover - requires live LLM failure
                return AnswerSynthesisResult(
                    answer=self._with_source_link_limitation(answer),
                    errors=[f"Answer citation repair failed: {exc}"],
                )
            answer = retry_answer or self._with_source_link_limitation(answer)

        return AnswerSynthesisResult(answer=answer)

    def _request_answer_json(
        self,
        *,
        messages: list[dict[str, str]],
        prompt_config: dict[str, Any],
    ) -> dict[str, Any]:
        if self.json_requester is not None:
            return self.json_requester(
                messages=messages,
                prompt_config=prompt_config,
            )

        from openai import OpenAI  # type: ignore[import-not-found]

        client = OpenAI(api_key=os.getenv(ANSWER_SYNTHESIS_API_KEY_ENV))
        response = client.chat.completions.create(
            model=os.getenv(ANSWER_SYNTHESIS_MODEL_ENV),
            response_format=prompt_config.get(
                "response_format",
                {"type": "json_object"},
            ),
            messages=messages,
            temperature=0,
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        if not isinstance(data, dict):
            return {}
        return data

    def _retry_with_citation_feedback(
        self,
        *,
        query: str,
        data: dict[str, Any],
        evidence_packet: dict[str, Any],
        prompt_config: dict[str, Any],
        allowed_citations: set[tuple[str, str]],
    ) -> EvidenceAnswer | None:
        for _ in range(self.parameters.max_synthesis_retries):
            messages = self._format_messages(
                prompt_config.get("messages", []),
                query=query,
                evidence_packet=json.dumps(evidence_packet, indent=2),
            )
            messages.append(
                self._format_retry_message(data, allowed_citations)
            )
            retry_data = self._request_answer_json(
                messages=messages,
                prompt_config=prompt_config,
            )
            retry_answer = self.parse_answer_data(retry_data, allowed_citations)
            if not self._needs_source_retry(retry_answer, allowed_citations):
                return retry_answer
            data = retry_data
        return None

    def _needs_source_retry(
        self,
        answer: EvidenceAnswer,
        allowed_citations: set[tuple[str, str]],
    ) -> bool:
        if not self.parameters.require_citations_when_evidence_exists:
            return False
        if not allowed_citations:
            return False
        return not any(bullet.citations for bullet in answer.bullets)

    @staticmethod
    def _with_source_link_limitation(answer: EvidenceAnswer) -> EvidenceAnswer:
        if SOURCE_LINK_LIMITATION in answer.limitations:
            return answer
        return answer.model_copy(
            update={
                "limitations": [*answer.limitations, SOURCE_LINK_LIMITATION],
            }
        )

    @staticmethod
    def build_evidence_packet(
        understanding: QueryUnderstandingResponse,
        secondary_evidence: list[SecondaryDrugEvidence] | None = None,
        context_evidence: list[ContextTargetedEvidence] | None = None,
    ) -> dict[str, Any]:
        dossier = understanding.primary_dossier
        if dossier is None:
            return {}

        label_evidence = dossier.label_evidence
        secondary_evidence = secondary_evidence or []
        context_evidence = context_evidence or []
        primary_sources = [
            label_record_payload(record, evidence_scope="primary")
            for record in (label_evidence.label_records if label_evidence else [])
        ]
        secondary_sources = [
            label_record_payload(
                record,
                evidence_scope="secondary",
                drug_name=item.resolved_concept.name,
                rxcui=item.resolved_concept.rxcui,
            )
            for item in secondary_evidence
            for record in (
                item.label_evidence.label_records if item.label_evidence else []
            )
        ]
        primary_sections = label_section_payloads(
            label_evidence.sections if label_evidence else {},
            evidence_scope="primary",
        )
        secondary_sections = [
            payload
            for item in secondary_evidence
            for payload in label_section_payloads(
                item.label_evidence.sections if item.label_evidence else {},
                evidence_scope="secondary",
                drug_name=item.resolved_concept.name,
                rxcui=item.resolved_concept.rxcui,
                retrieval_modes=item.retrieval_modes,
            )
        ]
        return {
            "query": understanding.query,
            "state": understanding.state.model_dump(),
            "resolved_primary_drug": (
                dossier.resolved_drug.model_dump() if dossier.resolved_drug else None
            ),
            "label_evidence_scope": dossier.label_evidence_scope,
            "ingredient_fallback": [
                {
                    "ingredient": item.ingredient.model_dump(),
                    "labels_found": (
                        item.label_evidence.labels_found
                        if item.label_evidence
                        else 0
                    ),
                }
                for item in dossier.ingredient_fallback
            ],
            "rxnorm_relationship_summary": rxnorm_relationship_summary(dossier),
            "secondary_drug_evidence": [
                secondary_evidence_payload(item) for item in secondary_evidence
            ],
            "context_targeted_evidence": [
                context_evidence_payload(item) for item in context_evidence
            ],
            "label_sources": [*primary_sources, *secondary_sources],
            "label_sections": [*primary_sections, *secondary_sections],
            "retrieval_notes": dossier.notes,
        }

    @staticmethod
    def allowed_citations(evidence_packet: dict[str, Any]) -> set[tuple[str, str]]:
        return {
            (str(section["source_id"]), str(section["section"]))
            for section in evidence_packet.get("label_sections", [])
            if section.get("source_id") and section.get("section")
        }

    @staticmethod
    def parse_answer_data(
        data: dict[str, Any],
        allowed_citations: set[tuple[str, str]],
    ) -> EvidenceAnswer:
        bullets = [
            EvidenceBullet(
                text=str(item.get("text", "")).strip(),
                citations=[
                    citation
                    for citation in parse_citations(item.get("citations"))
                    if (citation.source_id, citation.section) in allowed_citations
                ],
            )
            for item in list_value(data.get("bullets"))
            if str(item.get("text", "")).strip()
        ]
        response = str(data.get("response") or data.get("summary") or "").strip()
        evidence_summary = str(
            data.get("evidence_summary") or data.get("summary") or ""
        ).strip()
        return EvidenceAnswer(
            response=response,
            evidence_summary=evidence_summary,
            summary=evidence_summary or response,
            bullets=bullets[:5],
            limitations=string_list(data.get("limitations")),
            safety_note=STANDARD_SAFETY_NOTE,
        )

    @staticmethod
    def _llm_configured() -> bool:
        return bool(
            os.getenv(ANSWER_SYNTHESIS_API_KEY_ENV)
            and os.getenv(ANSWER_SYNTHESIS_MODEL_ENV)
        )

    @staticmethod
    def _load_prompt() -> dict[str, Any]:
        return EvidenceAnswerSynthesizer._load_prompt_config(
            ANSWER_SYNTHESIS_PROMPT_KEY
        )

    @staticmethod
    def _load_prompt_config(prompt_key: str) -> dict[str, Any]:
        prompt_library = load_prompts()
        prompt_config = prompt_library.get(prompt_key)
        if not isinstance(prompt_config, dict):
            raise ValueError(f"Missing prompt configuration: {prompt_key}")
        return prompt_config

    @staticmethod
    def _format_retry_message(
        previous_response: dict[str, Any],
        allowed_citations: set[tuple[str, str]],
    ) -> dict[str, str]:
        prompt_config = EvidenceAnswerSynthesizer._load_prompt_config(
            ANSWER_CITATION_RETRY_PROMPT_KEY
        )
        message = prompt_config.get("message")
        if not isinstance(message, dict):
            raise ValueError(
                f"Missing prompt message: {ANSWER_CITATION_RETRY_PROMPT_KEY}"
            )
        role = str(message.get("role", "user"))
        content = str(message.get("content", ""))
        allowed = [
            {"source_id": source_id, "section": section}
            for source_id, section in sorted(allowed_citations)
        ]
        return {
            "role": role,
            "content": EvidenceAnswerSynthesizer._replace_prompt_placeholders(
                content,
                {
                    "allowed_citations": json.dumps(allowed, indent=2),
                    "previous_response": json.dumps(previous_response, indent=2),
                },
            ),
        }

    @staticmethod
    def _format_messages(
        messages: list[dict[str, str]],
        **values: str,
    ) -> list[dict[str, str]]:
        formatted: list[dict[str, str]] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if not role or content is None:
                continue
            formatted.append(
                {
                    "role": role,
                    "content": EvidenceAnswerSynthesizer._replace_prompt_placeholders(
                        content,
                        values,
                    ),
                }
            )
        return formatted

    @staticmethod
    def _replace_prompt_placeholders(
        content: str,
        values: dict[str, str],
    ) -> str:
        for key, value in values.items():
            content = content.replace("{" + key + "}", value)
        return content


def rxnorm_relationship_summary(dossier: DrugDossier) -> dict[str, Any]:
    edges = dossier.rxnorm_neighborhood.edges[:MAX_RXNORM_RELATIONSHIPS]
    relation_counts = Counter(
        edge.relation for edge in dossier.rxnorm_neighborhood.edges
    )
    return {
        "depth": dossier.rxnorm_neighborhood.depth,
        "returned_relationships": len(dossier.rxnorm_neighborhood.edges),
        "truncated": dossier.rxnorm_neighborhood.truncated,
        "relation_counts": dict(relation_counts.most_common(12)),
        "sample_relationships": [rxnorm_edge_payload(edge) for edge in edges],
    }


def rxnorm_edge_payload(edge: RxNormEdge) -> dict[str, Any]:
    return {
        "source_rxcui": edge.source_rxcui,
        "source_name": edge.source_name,
        "source_type": edge.source_tty,
        "relation": edge.relation,
        "target_rxcui": edge.target_rxcui,
        "target_name": edge.target_name,
        "target_type": edge.target_tty,
    }


def label_record_payload(
    record: OpenFDALabelRecord,
    *,
    evidence_scope: str,
    drug_name: str | None = None,
    rxcui: str | None = None,
) -> dict[str, Any]:
    return {
        "evidence_scope": evidence_scope,
        "drug_name": drug_name,
        "rxcui": rxcui,
        "source_id": record.source_id,
        "brand_names": record.brand_names[:3],
        "generic_names": record.generic_names[:3],
        "manufacturer_names": record.manufacturer_names[:3],
        "routes": record.routes[:3],
        "product_types": record.product_types[:3],
        "rxcuis": record.rxcuis[:5],
        "provenance_tags": record.provenance_tags,
    }


def label_section_payloads(
    sections: dict[str, list[LabelSection]],
    *,
    evidence_scope: str,
    drug_name: str | None = None,
    rxcui: str | None = None,
    retrieval_modes: list[str] | None = None,
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for section_name in PRIORITIZED_SECTIONS:
        for label_section in sections.get(section_name, []):
            if len(payloads) >= MAX_LABEL_SECTIONS:
                return payloads
            payloads.append(
                {
                    "evidence_scope": evidence_scope,
                    "drug_name": drug_name,
                    "rxcui": rxcui,
                    "retrieval_modes": retrieval_modes or [],
                    "section": section_name,
                    "source_id": label_section.source_id,
                    "text": truncate_text(label_section.text, MAX_LABEL_TEXT_CHARS),
                    "provenance_tags": label_section.provenance_tags,
                }
            )
    return payloads


def secondary_evidence_payload(item: SecondaryDrugEvidence) -> dict[str, Any]:
    label_evidence = item.label_evidence
    return {
        "mention_text": item.mention_text,
        "role": item.role,
        "resolved_concept": item.resolved_concept.model_dump(),
        "retrieval_modes": item.retrieval_modes,
        "labels_found": label_evidence.labels_found if label_evidence else 0,
        "interaction_labels_found": (
            item.interaction_label_evidence.labels_found
            if item.interaction_label_evidence
            else 0
        ),
        "rxnorm_context": (
            item.rxnorm_context.model_dump() if item.rxnorm_context else None
        ),
    }


def context_evidence_payload(item: ContextTargetedEvidence) -> dict[str, Any]:
    label_evidence = item.label_evidence
    return {
        "target_label": item.target_label,
        "target_category": item.target_category,
        "drug_name": item.resolved_concept.name,
        "rxcui": item.resolved_concept.rxcui,
        "searched_fields": item.searched_fields,
        "retrieval_modes": item.retrieval_modes,
        "labels_found": label_evidence.labels_found if label_evidence else 0,
    }


def truncate_text(text: str, max_chars: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def parse_citations(value: Any) -> list[EvidenceCitation]:
    citations: list[EvidenceCitation] = []
    for item in list_value(value):
        source_id = str(item.get("source_id", "")).strip()
        section = str(item.get("section", "")).strip()
        snippet_value = item.get("snippet")
        snippet = (
            str(snippet_value).strip()
            if snippet_value is not None
            else None
        )
        if not source_id or not section:
            continue
        citations.append(
            EvidenceCitation(
                source_id=source_id,
                section=section,
                snippet=snippet or None,
            )
        )
    return citations


def list_value(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
