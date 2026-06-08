from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from src.dossier.models import DrugDossier, LabelSection, OpenFDALabelRecord, RxNormEdge
from src.query_answer.models import (
    EvidenceAnswer,
    EvidenceBullet,
    EvidenceCitation,
)
from src.query_understanding.models import QueryUnderstandingResponse
from src.utils import load_prompts

ANSWER_SYNTHESIS_API_KEY_ENV = "ANSWER_SYNTHESIS_OPENAI_API_KEY"
ANSWER_SYNTHESIS_MODEL_ENV = "ANSWER_SYNTHESIS_OPENAI_MODEL"
ANSWER_SYNTHESIS_PROMPT_KEY = "evidence_answer_synthesis"
STANDARD_SAFETY_NOTE = (
    "This is an educational summary of retrieved public evidence, not medical advice."
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


class EvidenceAnswerSynthesizer:
    """Generate a compact grounded answer from query understanding evidence."""

    def synthesize(
        self,
        query: str,
        understanding: QueryUnderstandingResponse,
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

        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError:
            return AnswerSynthesisResult(
                warnings=[
                    "The OpenAI package is not installed; no evidence summary "
                    "was generated."
                ]
            )

        prompt_config = self._load_prompt()
        evidence_packet = self.build_evidence_packet(understanding)
        messages = self._format_messages(
            prompt_config.get("messages", []),
            query=query,
            evidence_packet=json.dumps(evidence_packet, indent=2),
        )

        client = OpenAI(api_key=os.getenv(ANSWER_SYNTHESIS_API_KEY_ENV))
        try:
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
        except Exception as exc:  # pragma: no cover - requires live LLM config
            return AnswerSynthesisResult(errors=[f"Answer synthesis failed: {exc}"])

        allowed_citations = self.allowed_citations(evidence_packet)
        return AnswerSynthesisResult(
            answer=self.parse_answer_data(data, allowed_citations)
        )

    @staticmethod
    def build_evidence_packet(
        understanding: QueryUnderstandingResponse,
    ) -> dict[str, Any]:
        dossier = understanding.primary_dossier
        if dossier is None:
            return {}

        label_evidence = dossier.label_evidence
        return {
            "query": understanding.query,
            "state": understanding.state.model_dump(),
            "resolved_primary_drug": (
                dossier.resolved_drug.model_dump() if dossier.resolved_drug else None
            ),
            "rxnorm_relationship_summary": rxnorm_relationship_summary(dossier),
            "label_sources": [
                label_record_payload(record)
                for record in (label_evidence.label_records if label_evidence else [])
            ],
            "label_sections": label_section_payloads(
                label_evidence.sections if label_evidence else {}
            ),
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
        return EvidenceAnswer(
            summary=str(data.get("summary", "")).strip(),
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
        prompt_library = load_prompts()
        prompt_config = prompt_library.get(ANSWER_SYNTHESIS_PROMPT_KEY)
        if not isinstance(prompt_config, dict):
            raise ValueError(
                f"Missing prompt configuration: {ANSWER_SYNTHESIS_PROMPT_KEY}"
            )
        return prompt_config

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
            for key, value in values.items():
                content = content.replace("{" + key + "}", value)
            formatted.append({"role": role, "content": content})
        return formatted


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


def label_record_payload(record: OpenFDALabelRecord) -> dict[str, Any]:
    return {
        "source_id": record.source_id,
        "brand_names": record.brand_names[:3],
        "generic_names": record.generic_names[:3],
        "manufacturer_names": record.manufacturer_names[:3],
        "routes": record.routes[:3],
        "product_types": record.product_types[:3],
        "rxcuis": record.rxcuis[:5],
    }


def label_section_payloads(
    sections: dict[str, list[LabelSection]],
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for section_name in PRIORITIZED_SECTIONS:
        for label_section in sections.get(section_name, []):
            if len(payloads) >= MAX_LABEL_SECTIONS:
                return payloads
            payloads.append(
                {
                    "section": section_name,
                    "source_id": label_section.source_id,
                    "text": truncate_text(label_section.text, MAX_LABEL_TEXT_CHARS),
                }
            )
    return payloads


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
        if not source_id or not section:
            continue
        citations.append(
            EvidenceCitation(
                source_id=source_id,
                section=section,
                snippet=str(item.get("snippet", "")).strip() or None,
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
