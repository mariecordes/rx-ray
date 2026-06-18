from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from src.utils import load_prompts
from src.query_understanding.models import ExtractedDrugMention, QueryState


CONDITION_PATTERNS: dict[str, tuple[str, ...]] = {
    "acne": (r"\bacne\b",),
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
    "breastfeeding": (r"\bbreastfeeding\b", r"\blactating\b", r"\bnursing\b"),
    "female": (r"\bfemale\b", r"\bwoman\b", r"\bwomen\b", r"\bgirl\b"),
    "male": (r"\bmale\b", r"\bman\b", r"\bmen\b", r"\bboy\b"),
    "infant": (r"\binfant\b", r"\bbaby\b"),
    "child": (r"\bchild\b", r"\bchildren\b", r"\bkid\b"),
    "adolescent": (r"\badolescent\b", r"\bteen(?:ager)?\b"),
    "adult": (r"\badult\b", r"\bolder adult\b"),
    "senior": (r"\belderly\b", r"\bsenior\b"),
}

DRUG_FRAGMENT_PATTERN = r"([a-zA-Z0-9][a-zA-Z0-9 /\-]+)"

# Bounded 1–3 token noun phrase for the "<allergen> allergy" construction. The
# greedy DRUG_FRAGMENT_PATTERN spans spaces, so "a tretinoin cream if I have a
# CLINDAMYCIN allergy" anchored on the first determiner and captured "tretinoin
# cream" as the allergen. Bounding the span forces the engine to backtrack to
# the determiner nearest "allergy", yielding the real allergen.
ALLERGEN_FRAGMENT_PATTERN = (
    r"((?:[a-zA-Z0-9][a-zA-Z0-9/\-]*\s+){0,2}[a-zA-Z0-9][a-zA-Z0-9/\-]*)"
)

MENTION_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        "allergy",
        rf"\b(?:allergic|allergy|allergies)\s+(?:to|against)\s+"
        rf"{DRUG_FRAGMENT_PATTERN}",
    ),
    (
        "allergy",
        rf"\b(?:my|a|an|the)\s+{ALLERGEN_FRAGMENT_PATTERN}\s+allerg(?:y|ies)\b",
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
        rf"\b(?:can|should|could)\s+(?:a\s+)?(?:child|kid|infant|baby|"
        rf"senior|older\s+adult|pregnant\s+person)\s+(?:take|use|try)\s+"
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

QUERY_EXTRACTION_API_KEY_ENV = "QUERY_EXTRACTION_OPENAI_API_KEY"
QUERY_EXTRACTION_MODEL_ENV = "QUERY_EXTRACTION_OPENAI_MODEL"
QUERY_EXTRACTION_PROMPT_KEY = "query_extraction_revision"

INVALID_STATE_TERMS: dict[str, tuple[str, ...]] = {
    "conditions": ("allergy", "allergies", "allergic"),
    "patient_context": ("allergy", "allergies", "allergic"),
}


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

        llm_result = self._revise_with_llm(query, deterministic)
        if llm_result is None:
            deterministic.warnings.append(
                f"{QUERY_EXTRACTION_API_KEY_ENV}/{QUERY_EXTRACTION_MODEL_ENV} "
                "are configured, but LLM extraction was unavailable; "
                "deterministic extraction was used."
            )
            return deterministic

        return ExtractionResult(
            state=llm_result.state,
            mentions=llm_result.mentions,
            mode="hybrid",
            warnings=[*deterministic.warnings, *llm_result.warnings],
            errors=llm_result.errors,
        )

    def _extract_deterministic(self, query: str) -> ExtractionResult:
        normalized = query.casefold()
        state = QueryState(
            conditions=self._extract_terms(normalized, CONDITION_PATTERNS),
            patient_context=self._extract_patient_context(query),
            intents=self._infer_intents(normalized),
        )
        mentions: list[ExtractedDrugMention] = []

        for role, pattern in MENTION_PATTERNS:
            for match in re.finditer(pattern, query, flags=re.IGNORECASE):
                if role == "current_medication" and self._is_hypothetical_use(
                    query,
                    match.start(),
                ):
                    continue
                fragment = self._clean_drug_fragment(match.group(1))
                if fragment:
                    mentions.append(ExtractedDrugMention(text=fragment, role=role))

        mentions = self._dedupe_mentions(mentions)
        state.all_drugs_mentioned = self._mention_texts(mentions)
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

        return ExtractionResult(state=self._sanitize_state(state), mentions=mentions)

    def _revise_with_llm(
        self,
        query: str,
        deterministic: ExtractionResult,
        resolution_feedback: dict[str, Any] | None = None,
    ) -> ExtractionResult | None:
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError:
            return None

        api_key = os.getenv(QUERY_EXTRACTION_API_KEY_ENV)
        model = os.getenv(QUERY_EXTRACTION_MODEL_ENV)
        if not api_key or not model:
            return None

        prompt_config = self._load_revision_prompt()
        deterministic_payload = json.dumps(
            {
                "state": deterministic.state.model_dump(),
                "drug_mentions": [
                    mention.model_dump() for mention in deterministic.mentions
                ],
                "resolution_feedback": resolution_feedback or {},
            },
            indent=2,
        )
        messages = self._format_messages(
            prompt_config.get("messages", []),
            query=query,
            deterministic_extraction=deterministic_payload,
        )

        client = OpenAI(api_key=api_key)
        try:
            response = client.chat.completions.create(
                model=model,
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
            return ExtractionResult(
                state=QueryState(),
                mode="llm",
                errors=[f"LLM extraction failed: {exc}"],
            )

        return ExtractionResult(
            state=self._parse_llm_state(data.get("state")),
            mentions=self._parse_llm_mentions(data.get("drug_mentions")),
            warnings=self._string_list(data.get("warnings")),
            mode="llm",
        )

    def revise_with_resolution_feedback(
        self,
        query: str,
        extraction: ExtractionResult,
        resolution_feedback: dict[str, Any],
    ) -> ExtractionResult | None:
        if not self._llm_configured():
            return None
        revised = self._revise_with_llm(
            query,
            extraction,
            resolution_feedback=resolution_feedback,
        )
        if revised is None:
            return None
        return ExtractionResult(
            state=revised.state,
            mentions=revised.mentions,
            mode="hybrid",
            warnings=[*extraction.warnings, *revised.warnings],
            errors=[*extraction.errors, *revised.errors],
        )

    @staticmethod
    def _llm_configured() -> bool:
        return bool(
            os.getenv(QUERY_EXTRACTION_API_KEY_ENV)
            and os.getenv(QUERY_EXTRACTION_MODEL_ENV)
        )

    @staticmethod
    def _load_revision_prompt() -> dict[str, Any]:
        prompt_library = load_prompts()
        prompt_config = prompt_library.get(QUERY_EXTRACTION_PROMPT_KEY)
        if not isinstance(prompt_config, dict):
            raise ValueError(
                f"Missing prompt configuration: {QUERY_EXTRACTION_PROMPT_KEY}"
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
            formatted.append(
                {
                    "role": role,
                    "content": HybridQueryExtractor._replace_prompt_placeholders(
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

    @classmethod
    def _extract_patient_context(cls, query: str) -> list[str]:
        normalized = query.casefold()
        terms = cls._extract_terms(normalized, PATIENT_CONTEXT_PATTERNS)
        age_group = cls._infer_age_group(normalized)
        if age_group:
            terms.append(age_group)
        return cls._dedupe_strings(terms)

    @staticmethod
    def _infer_age_group(normalized_query: str) -> str | None:
        match = re.search(
            r"\b(\d{1,3})\s*(?:-| )?(?:years?|yrs?)\s*(?:-| )?old\b",
            normalized_query,
        )
        if not match:
            match = re.search(r"\b(\d{1,3})\s*(?:yo|y/o)\b", normalized_query)
        if not match:
            return None

        age = int(match.group(1))
        if age <= 1:
            return "infant"
        if 2 <= age <= 11:
            return "child"
        if 12 <= age <= 17:
            return "adolescent"
        if 18 <= age <= 64:
            return "adult"
        return "senior"

    @staticmethod
    def _dedupe_strings(values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(value)
        return deduped

    @staticmethod
    def _infer_intents(normalized_query: str) -> list[str]:
        intents: list[str] = []
        if re.search(
            r"\binteract(?:ion|ions)?\b|\btogether\b|\bat the same time\b",
            normalized_query,
        ):
            intents.append("interaction_check")
        if re.search(
            r"\b(?:taking|take|use|using|on)\b.*\b(?:can|should|could|safe|ok|okay)\b"
            r"|\b(?:can|should|could|safe|ok|okay)\b.*\b(?:taking|take|use|using|on)\b",
            normalized_query,
        ):
            intents.append("interaction_check")
        if re.search(r"\bpregnan(?:t|cy)\b|\bbreastfeeding\b", normalized_query):
            intents.append("patient_context_check")
        if re.search(r"\ballerg(?:y|ies|ic)\b", normalized_query):
            intents.append("allergy_context_check")
        if re.search(r"\b(can|should|could)\s+i\b|\bsafe\b|\bokay\b", normalized_query):
            intents.append("safety_context_check")
        if normalized_query.strip():
            intents.append("label_context_check")
        return HybridQueryExtractor._dedupe_strings(intents)

    @staticmethod
    def _clean_drug_fragment(fragment: str) -> str:
        fragment = re.split(r"[,.?;:]", fragment, maxsplit=1)[0]
        stop_match = FRAGMENT_STOP_PATTERN.search(fragment)
        if stop_match and stop_match.start() > 0:
            fragment = fragment[: stop_match.start()]
        fragment = re.sub(r"\s+", " ", fragment).strip(" -/")
        fragment = re.sub(r"^(?:my|a|an|the)\s+", "", fragment, flags=re.IGNORECASE)
        return fragment

    @staticmethod
    def _is_hypothetical_use(query: str, match_start: int) -> bool:
        prefix = query[max(0, match_start - 16) : match_start].casefold()
        return bool(re.search(r"\b(?:can|should|could)\s+$", prefix))

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

    @staticmethod
    def _mention_texts(mentions: list[ExtractedDrugMention]) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for mention in mentions:
            key = mention.text.casefold()
            if key in seen:
                continue
            seen.add(key)
            values.append(mention.text)
        return values

    @classmethod
    def _sanitize_state(cls, state: QueryState) -> QueryState:
        """Remove known wrong-bucket terms while preserving the LLM's choices."""

        return state.model_copy(
            update={
                "conditions": cls._filter_invalid_state_terms(
                    "conditions",
                    state.conditions,
                ),
                "patient_context": cls._filter_invalid_state_terms(
                    "patient_context",
                    state.patient_context,
                ),
            }
        )

    @classmethod
    def _filter_invalid_state_terms(
        cls,
        field_name: str,
        values: list[str],
    ) -> list[str]:
        invalid_terms = INVALID_STATE_TERMS.get(field_name, ())
        if not invalid_terms:
            return values

        filtered: list[str] = []
        for value in values:
            normalized = value.casefold()
            if any(
                re.search(rf"\b{re.escape(term)}\b", normalized)
                for term in invalid_terms
            ):
                continue
            filtered.append(value)
        return cls._dedupe_strings(filtered)

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _parse_llm_state(self, value: Any) -> QueryState:
        if not isinstance(value, dict):
            return QueryState()

        return self._sanitize_state(QueryState(
            primary_drug=self._optional_string(value.get("primary_drug")),
            all_drugs_mentioned=self._string_list(value.get("all_drugs_mentioned")),
            current_medications=self._string_list(value.get("current_medications")),
            allergies=self._string_list(value.get("allergies")),
            conditions=self._string_list(value.get("conditions")),
            patient_context=self._string_list(value.get("patient_context")),
            intent=self._optional_string(value.get("intent")),
            intents=self._state_intents(value),
        ))

    def _state_intents(self, value: dict[str, Any]) -> list[str]:
        intents = self._string_list(value.get("intents"))
        legacy_intent = self._optional_string(value.get("intent"))
        if legacy_intent:
            intents = [legacy_intent, *intents]
        return self._dedupe_strings(intents)

    @classmethod
    def _string_list(cls, value: Any) -> list[str]:
        values: list[str] = []
        if isinstance(value, str):
            values = [value]
        elif isinstance(value, list):
            values = [item for item in value if isinstance(item, str)]

        parsed: list[str] = []
        seen: set[str] = set()
        for item in values:
            for part in re.split(r"[;,]", item):
                cleaned = re.sub(r"\s+", " ", part).strip()
                key = cleaned.casefold()
                if not cleaned or key in seen:
                    continue
                seen.add(key)
                parsed.append(cleaned)
        return parsed

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
