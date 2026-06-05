from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from src.query_understanding.models import ExtractedDrugMention, QueryState


CONDITION_PATTERNS: dict[str, tuple[str, ...]] = {
    "acne": (r"\bacne\b",),
    "allergy": (r"\ballerg(?:y|ies|ic)\b",),
    "cold": (r"\bcold\b",),
    "cough": (r"\bcough\b",),
    "fever": (r"\bfever\b",),
    "flu": (r"\bflu\b", r"\binfluenza\b"),
    "headache": (r"\bheadache\b",),
    "migraine": (r"\bmigraines?\b",),
    "nausea": (r"\bnausea\b",),
    "pain": (r"\bpain\b",),
    "rash": (r"\brash\b",),
}

PATIENT_CONTEXT_PATTERNS: dict[str, tuple[str, ...]] = {
    "pregnancy": (
        r"\bpregnan(?:t|cy)\b",
        r"\btrying to conceive\b",
        r"\bexpecting\b",
    ),
    "lactation": (r"\bbreastfeeding\b", r"\blactating\b", r"\bnursing\b"),
    "pediatric": (r"\bchild\b", r"\bkid\b", r"\binfant\b", r"\bbaby\b"),
    "older adult": (r"\belderly\b", r"\bolder adult\b", r"\bsenior\b"),
}

DRUG_FRAGMENT_PATTERN = r"([a-zA-Z0-9][a-zA-Z0-9 /\-]+)"

MENTION_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        "allergy",
        rf"\b(?:allergic|allergy|allergies)\s+(?:to|against)\s+"
        rf"{DRUG_FRAGMENT_PATTERN}",
    ),
    (
        "current_medication",
        rf"\b(?:already\s+)?(?:currently\s+)?(?:taking|on)\s+"
        rf"{DRUG_FRAGMENT_PATTERN}",
    ),
    (
        "current_medication",
        rf"\bi\s+(?:already\s+|currently\s+)?(?:take|use)\s+"
        rf"{DRUG_FRAGMENT_PATTERN}",
    ),
    (
        "primary_drug",
        rf"\b(?:want\s+to|would\s+like\s+to|need\s+to)\s+"
        rf"(?:take|use|try)\s+{DRUG_FRAGMENT_PATTERN}",
    ),
    (
        "primary_drug",
        rf"\b(?:can|should|could)\s+i\s+(?:take|use|try)\s+"
        rf"{DRUG_FRAGMENT_PATTERN}",
    ),
    (
        "primary_drug",
        rf"\b(?:is|are)\s+{DRUG_FRAGMENT_PATTERN}\s+(?:safe|okay|ok)\b",
    ),
)

FRAGMENT_STOP_PATTERN = re.compile(
    r"\b(?:if|while|because|before|after|for|with|but|and|or|now|when|that|"
    r"can|should|could|is|are|i|i'm|im|i’ve|ive|i have|have)\b",
    re.IGNORECASE,
)


@dataclass
class ExtractionResult:
    state: QueryState
    mentions: list[ExtractedDrugMention] = field(default_factory=list)
    mode: str = "deterministic"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class HybridQueryExtractor:
    """Extract a medication query state with optional LLM enrichment."""

    def extract(self, query: str) -> ExtractionResult:
        deterministic = self._extract_deterministic(query)
        if not self._llm_configured():
            return deterministic

        llm_result = self._extract_with_llm(query)
        if llm_result is None:
            deterministic.warnings.append(
                "OPENAI_API_KEY/OPENAI_MODEL are configured, but LLM extraction "
                "was unavailable; deterministic extraction was used."
            )
            return deterministic

        merged_state = self._merge_states(deterministic.state, llm_result.state)
        merged_mentions = self._dedupe_mentions(
            [*deterministic.mentions, *llm_result.mentions]
        )
        return ExtractionResult(
            state=merged_state,
            mentions=merged_mentions,
            mode="hybrid",
            warnings=[*deterministic.warnings, *llm_result.warnings],
            errors=llm_result.errors,
        )

    def _extract_deterministic(self, query: str) -> ExtractionResult:
        normalized = query.casefold()
        state = QueryState(
            conditions=self._extract_terms(normalized, CONDITION_PATTERNS),
            patient_context=self._extract_terms(
                normalized,
                PATIENT_CONTEXT_PATTERNS,
            ),
            intent=self._infer_intent(normalized),
        )
        mentions: list[ExtractedDrugMention] = []

        for role, pattern in MENTION_PATTERNS:
            for match in re.finditer(pattern, query, flags=re.IGNORECASE):
                fragment = self._clean_drug_fragment(match.group(1))
                if fragment:
                    mentions.append(ExtractedDrugMention(text=fragment, role=role))

        mentions = self._dedupe_mentions(mentions)
        state.current_medications = [
            mention.text for mention in mentions if mention.role == "current_medication"
        ]
        state.allergies = [
            mention.text for mention in mentions if mention.role == "allergy"
        ]
        primary = next(
            (mention.text for mention in mentions if mention.role == "primary_drug"),
            None,
        )
        if primary is None:
            primary = next(
                (
                    mention.text
                    for mention in mentions
                    if mention.role not in {"current_medication", "allergy"}
                ),
                None,
            )
        state.primary_drug = primary

        return ExtractionResult(state=state, mentions=mentions)

    def _extract_with_llm(self, query: str) -> ExtractionResult | None:
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError:
            return None

        model = os.getenv("OPENAI_MODEL")
        if not model:
            return None

        client = OpenAI()
        try:
            response = client.chat.completions.create(
                model=model,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Extract medication-query state as JSON only. "
                            "Use keys primary_drug, current_medications, allergies, "
                            "conditions, patient_context, intent, and drug_mentions. "
                            "drug_mentions must be a list of objects with text "
                            "and role."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                temperature=0,
            )
            content = response.choices[0].message.content or "{}"
            data = json.loads(content)
        except Exception as exc:  # pragma: no cover - requires live LLM config
            return ExtractionResult(
                state=QueryState(),
                mode="llm",
                errors=[f"LLM extraction failed: {exc}"],
            )

        return ExtractionResult(
            state=QueryState(
                primary_drug=self._optional_string(data.get("primary_drug")),
                current_medications=self._string_list(
                    data.get("current_medications")
                ),
                allergies=self._string_list(data.get("allergies")),
                conditions=self._string_list(data.get("conditions")),
                patient_context=self._string_list(data.get("patient_context")),
                intent=self._optional_string(data.get("intent")),
            ),
            mentions=self._parse_llm_mentions(data.get("drug_mentions")),
            mode="llm",
        )

    @staticmethod
    def _llm_configured() -> bool:
        return bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_MODEL"))

    @staticmethod
    def _extract_terms(
        normalized_query: str,
        patterns: dict[str, tuple[str, ...]],
    ) -> list[str]:
        terms: list[str] = []
        for term, term_patterns in patterns.items():
            if any(re.search(pattern, normalized_query) for pattern in term_patterns):
                terms.append(term)
        return terms

    @staticmethod
    def _infer_intent(normalized_query: str) -> str | None:
        if re.search(r"\binteract(?:ion|ions)?\b|\btogether\b", normalized_query):
            return "interaction_check"
        if re.search(r"\bpregnan(?:t|cy)\b|\bbreastfeeding\b", normalized_query):
            return "patient_context_check"
        if re.search(r"\ballerg(?:y|ies|ic)\b", normalized_query):
            return "allergy_context_check"
        if re.search(r"\b(can|should|could)\s+i\b|\bsafe\b|\bokay\b", normalized_query):
            return "safety_context"
        return "label_context" if normalized_query.strip() else None

    @staticmethod
    def _clean_drug_fragment(fragment: str) -> str:
        fragment = re.split(r"[,.?;:]", fragment, maxsplit=1)[0]
        stop_match = FRAGMENT_STOP_PATTERN.search(fragment)
        if stop_match and stop_match.start() > 0:
            fragment = fragment[: stop_match.start()]
        fragment = re.sub(r"\s+", " ", fragment).strip(" -/")
        return fragment

    @staticmethod
    def _dedupe_mentions(
        mentions: Iterable[ExtractedDrugMention],
    ) -> list[ExtractedDrugMention]:
        deduped: list[ExtractedDrugMention] = []
        seen: set[tuple[str, str]] = set()
        for mention in mentions:
            key = (mention.role, mention.text.casefold())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(mention)
        return deduped

    def _merge_states(self, deterministic: QueryState, llm: QueryState) -> QueryState:
        return QueryState(
            primary_drug=llm.primary_drug or deterministic.primary_drug,
            current_medications=self._merge_lists(
                deterministic.current_medications,
                llm.current_medications,
            ),
            allergies=self._merge_lists(deterministic.allergies, llm.allergies),
            conditions=self._merge_lists(deterministic.conditions, llm.conditions),
            patient_context=self._merge_lists(
                deterministic.patient_context,
                llm.patient_context,
            ),
            intent=llm.intent or deterministic.intent,
        )

    @staticmethod
    def _merge_lists(first: list[str], second: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for value in [*first, *second]:
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            merged.append(value)
        return merged

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @classmethod
    def _string_list(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, list):
            return [
                item.strip()
                for item in value
                if isinstance(item, str) and item.strip()
            ]
        return []

    def _parse_llm_mentions(self, value: Any) -> list[ExtractedDrugMention]:
        if not isinstance(value, list):
            return []

        mentions: list[ExtractedDrugMention] = []
        allowed_roles = {
            "primary_drug",
            "current_medication",
            "allergy",
            "mentioned_drug",
        }
        for item in value:
            if not isinstance(item, dict):
                continue
            text = self._optional_string(item.get("text"))
            role = self._optional_string(item.get("role")) or "mentioned_drug"
            if text and role in allowed_roles:
                mentions.append(ExtractedDrugMention(text=text, role=role))
        return self._dedupe_mentions(mentions)
