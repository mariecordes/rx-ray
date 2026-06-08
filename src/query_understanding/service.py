from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher

from src.dossier.builder import DossierBuilder
from src.dossier.models import ResolutionCandidate
from src.dossier.rxnorm_store import (
    RxNormParquetStore,
    compact_drug_search_text,
    normalize_drug_search_text,
)
from src.query_understanding.extractor import ExtractionResult, HybridQueryExtractor
from src.query_understanding.models import (
    ExtractedDrugMention,
    QueryUnderstandingResponse,
    ResolvedDrugMention,
)

logger = logging.getLogger(__name__)


class QueryUnderstandingService:
    """Resolve natural-language medication questions into symbolic state."""

    def __init__(
        self,
        builder: DossierBuilder,
        extractor: HybridQueryExtractor | None = None,
    ) -> None:
        self.builder = builder
        self.extractor = extractor or HybridQueryExtractor()

    @property
    def rxnorm_store(self) -> RxNormParquetStore:
        return self.builder.rxnorm_store

    def understand(
        self,
        query: str,
        openfda_limit: int = 5,
    ) -> QueryUnderstandingResponse:
        extraction = self.extractor.extract(query)
        resolved_drugs = self._resolve_extraction(query, extraction)
        unresolved_mentions = self._unresolved_mention_texts(resolved_drugs)

        if unresolved_mentions:
            repaired = self.extractor.revise_with_resolution_feedback(
                query,
                extraction,
                {
                    "unresolved_drug_like_mentions": unresolved_mentions,
                    "instruction": (
                        "Remove or correct unresolved drug-like spans. If the "
                        "rule-based extraction is unreliable, create the state "
                        "and drug_mentions from scratch from the original query."
                    ),
                },
            )
            if repaired is not None:
                extraction = repaired
                resolved_drugs = self._resolve_extraction(query, extraction)
                unresolved_mentions = self._unresolved_mention_texts(resolved_drugs)

        warnings = [*extraction.warnings]
        errors = [*extraction.errors]

        primary = self._select_primary(resolved_drugs, extraction.state.primary_drug)
        if primary is None:
            warnings.append(
                "No primary drug could be resolved. Try naming the drug more directly."
            )

        primary_dossier = None
        if primary and primary.selected_concept:
            primary_dossier = self.builder.build(
                primary.selected_concept.name,
                depth=2,
                max_edges=400,
                include_openfda=True,
                openfda_limit=openfda_limit,
            )

        if unresolved_mentions:
            warnings.append(
                "Some drug-like mentions could not be resolved: "
                + ", ".join(unresolved_mentions)
                + "."
            )

        logger.info(
            "Query understanding completed: mode=%s primary_drug=%s "
            "resolved_mentions=%s unresolved_mentions=%s",
            extraction.mode,
            extraction.state.primary_drug,
            len([mention for mention in resolved_drugs if mention.selected_concept]),
            unresolved_mentions,
        )

        return QueryUnderstandingResponse(
            query=query,
            extraction_mode=extraction.mode,  # type: ignore[arg-type]
            state=extraction.state,
            resolved_drugs=resolved_drugs,
            primary_dossier=primary_dossier,
            warnings=warnings,
            errors=errors,
        )

    def _resolve_extraction(
        self,
        query: str,
        extraction: ExtractionResult,
    ) -> list[ResolvedDrugMention]:
        mentions = self._complete_mentions(query, extraction.mentions)
        return [self._resolve_mention(mention) for mention in mentions]

    @staticmethod
    def _unresolved_mention_texts(
        resolved_drugs: list[ResolvedDrugMention],
    ) -> list[str]:
        return [
            mention.text
            for mention in resolved_drugs
            if mention.selected_concept is None
        ]

    def _complete_mentions(
        self,
        query: str,
        extracted_mentions: list[ExtractedDrugMention],
    ) -> list[ExtractedDrugMention]:
        mentions = list(extracted_mentions)
        existing = {mention.text.casefold() for mention in mentions}
        for candidate in self._scan_query_for_drug_mentions(query):
            if candidate.text.casefold() in existing:
                continue
            existing.add(candidate.text.casefold())
            mentions.append(candidate)
        return mentions

    def _scan_query_for_drug_mentions(self, query: str) -> list[ExtractedDrugMention]:
        tokens = re_tokenize(query)
        mentions: list[ExtractedDrugMention] = []
        occupied: set[int] = set()
        for length in range(4, 0, -1):
            for start in range(0, len(tokens) - length + 1):
                indexes = set(range(start, start + length))
                if occupied & indexes:
                    continue
                phrase = " ".join(tokens[start : start + length])
                if not self._looks_like_drug_phrase(phrase):
                    continue
                candidates = self._resolve_text(phrase, limit=1)
                if not candidates or candidates[0].score < 80:
                    continue
                occupied |= indexes
                mentions.append(
                    ExtractedDrugMention(text=phrase, role="mentioned_drug")
                )
        return mentions

    @staticmethod
    def _looks_like_drug_phrase(phrase: str) -> bool:
        normalized = phrase.casefold()
        stop_phrases = {
            "can",
            "i",
            "take",
            "use",
            "try",
            "for",
            "with",
            "against",
            "and",
            "or",
            "if",
            "have",
            "has",
            "should",
            "could",
            "want",
            "need",
            "safe",
            "okay",
            "ok",
            "pregnant",
            "pregnancy",
            "child",
            "children",
            "kid",
            "infant",
            "baby",
            "adult",
            "senior",
            "elderly",
            "migraine",
            "acne",
            "pain",
            "fever",
            "headache",
            "allergy",
            "allergies",
            "allergic",
        }
        phrase_tokens = normalized.split()
        if any(token in stop_phrases for token in phrase_tokens):
            return False
        return normalized not in stop_phrases and len(normalized) >= 3

    def _resolve_mention(self, mention: ExtractedDrugMention) -> ResolvedDrugMention:
        candidates = self._resolve_text(mention.text)
        return ResolvedDrugMention(
            text=mention.text,
            role=mention.role,
            candidates=candidates,
            selected_concept=candidates[0].concept if candidates else None,
        )

    def _resolve_text(self, text: str, limit: int = 5) -> list[ResolutionCandidate]:
        candidates = self.rxnorm_store.resolve(text, limit=limit)
        if candidates:
            return candidates

        variants = self._lookup_variants(text)
        for variant in variants:
            if variant.casefold() == text.casefold():
                continue
            candidates = self.rxnorm_store.resolve(variant, limit=limit)
            if candidates:
                return candidates

        return self._fuzzy_resolve(text, limit=limit)

    @staticmethod
    def _lookup_variants(text: str) -> list[str]:
        normalized = normalize_drug_search_text(text)
        compact = compact_drug_search_text(text)
        variants = [normalized]
        if compact and compact != normalized.replace(" ", ""):
            variants.append(compact)
        variants.append(text.replace("-", " "))
        variants.append(text.replace(" ", "-"))
        return [variant for variant in dict.fromkeys(variants) if variant]

    def _fuzzy_resolve(self, text: str, limit: int = 5) -> list[ResolutionCandidate]:
        normalized = normalize_drug_search_text(text)
        if len(normalized) < 5:
            return []

        preferred = self.rxnorm_store.preferred_names
        prefix = normalized[:3]
        subset = preferred[preferred["STR_SEARCH"].str.startswith(prefix)].copy()
        if subset.empty:
            return []

        subset = subset.head(1000)
        subset["fuzzy_score"] = subset["STR_SEARCH"].map(
            lambda value: SequenceMatcher(None, normalized, str(value)).ratio()
        )
        subset = subset[subset["fuzzy_score"] >= 0.86]
        if subset.empty:
            return []

        subset = subset.sort_values(
            ["fuzzy_score", "name_len", "STR"],
            ascending=[False, True, True],
        ).head(limit)

        return [
            ResolutionCandidate(
                concept=self.rxnorm_store.get_concepts({str(row.RXCUI)})[
                    str(row.RXCUI)
                ],
                match_type="fuzzy",
                score=round(float(row.fuzzy_score) * 70, 2),
            )
            for row in subset.itertuples(index=False)
        ]

    @staticmethod
    def _select_primary(
        resolved_drugs: list[ResolvedDrugMention],
        extracted_primary: str | None,
    ) -> ResolvedDrugMention | None:
        if extracted_primary:
            primary_key = extracted_primary.casefold()
            match = next(
                (
                    mention
                    for mention in resolved_drugs
                    if mention.text.casefold() == primary_key
                    and mention.selected_concept is not None
                ),
                None,
            )
            if match:
                return match

        role_match = next(
            (
                mention
                for mention in resolved_drugs
                if mention.role == "primary_drug" and mention.selected_concept
            ),
            None,
        )
        if role_match:
            return role_match

        return next(
            (
                mention
                for mention in resolved_drugs
                if mention.role != "allergy" and mention.selected_concept
            ),
            None,
        )


def re_tokenize(query: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9][a-zA-Z0-9\-]*", query)
