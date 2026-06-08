from __future__ import annotations

import logging

from src.dossier.builder import DossierBuilder
from src.query_answer.models import QueryAnswerResponse
from src.query_answer.synthesizer import EvidenceAnswerSynthesizer
from src.query_understanding.service import QueryUnderstandingService

logger = logging.getLogger(__name__)


class QueryAnswerService:
    """Run query understanding, evidence retrieval, and answer synthesis."""

    def __init__(
        self,
        builder: DossierBuilder,
        understanding_service: QueryUnderstandingService | None = None,
        synthesizer: EvidenceAnswerSynthesizer | None = None,
    ) -> None:
        self.understanding_service = understanding_service or QueryUnderstandingService(
            builder=builder
        )
        self.synthesizer = synthesizer or EvidenceAnswerSynthesizer()

    def answer(
        self,
        query: str,
        openfda_limit: int = 5,
    ) -> QueryAnswerResponse:
        understanding = self.understanding_service.understand(
            query,
            openfda_limit=openfda_limit,
        )
        synthesis = self.synthesizer.synthesize(query, understanding)
        warnings = [*understanding.warnings, *synthesis.warnings]
        errors = [*understanding.errors, *synthesis.errors]

        logger.info(
            "Query answer completed: answer_generated=%s warnings=%s errors=%s",
            synthesis.answer is not None,
            len(warnings),
            len(errors),
        )

        return QueryAnswerResponse(
            understanding=understanding,
            answer=synthesis.answer,
            warnings=warnings,
            errors=errors,
        )
