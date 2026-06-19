from __future__ import annotations

import logging

from src.dossier.builder import DossierBuilder
from src.query_answer.config import load_query_answer_parameters
from src.query_answer.context import (
    build_context_targeted_evidence,
    merge_context_evidence_into_secondary,
    merge_context_evidence_into_understanding,
)
from src.query_answer.contract import build_answer_contract
from src.query_answer.coverage import build_evidence_coverage
from src.query_answer.critic import finalize_answer_critique
from src.query_answer.evidence_map import build_question_evidence_map
from src.query_answer.models import QueryAnswerResponse
from src.query_answer.network import build_question_rxnorm_network
from src.query_answer.secondary import build_secondary_evidence
from src.query_answer.synthesizer import EvidenceAnswerSynthesizer
from src.query_answer.validation import validate_and_enforce
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
        self.builder = builder
        self.understanding_service = understanding_service or QueryUnderstandingService(
            builder=builder
        )
        self.synthesizer = synthesizer or EvidenceAnswerSynthesizer()

    def answer(
        self,
        query: str,
        openfda_limit: int | None = None,
    ) -> QueryAnswerResponse:
        parameters = load_query_answer_parameters()
        label_limit = (
            openfda_limit
            if openfda_limit is not None
            else parameters.default_openfda_limit
        )
        understanding = self.understanding_service.understand(
            query,
            openfda_limit=label_limit,
        )
        secondary_evidence = build_secondary_evidence(
            understanding,
            self.builder,
            parameters,
        )
        context_evidence = build_context_targeted_evidence(
            understanding,
            secondary_evidence,
            self.builder,
            parameters,
        )
        understanding = merge_context_evidence_into_understanding(
            understanding,
            context_evidence,
        )
        secondary_evidence = merge_context_evidence_into_secondary(
            secondary_evidence,
            context_evidence,
        )
        coverage = build_evidence_coverage(
            understanding,
            secondary_evidence=secondary_evidence,
            context_evidence=context_evidence,
        )
        contract = build_answer_contract(understanding, coverage)
        synthesis = self.synthesizer.synthesize(
            query,
            understanding,
            secondary_evidence=secondary_evidence,
            context_evidence=context_evidence,
            contract=contract,
        )
        answer, validation = validate_and_enforce(synthesis.answer, contract)
        answer, critique, validation = finalize_answer_critique(
            query=query,
            understanding=understanding,
            secondary_evidence=secondary_evidence,
            context_evidence=context_evidence,
            answer=answer,
            contract=contract,
            validation=validation,
            synthesizer=self.synthesizer,
            parameters=parameters,
        )
        question_rxnorm_network = build_question_rxnorm_network(
            understanding,
            secondary_evidence,
            self.builder,
            parameters,
        )
        question_evidence_map = build_question_evidence_map(
            understanding,
            secondary_evidence=secondary_evidence,
            context_evidence=context_evidence,
        )
        warnings = [*understanding.warnings, *synthesis.warnings]
        errors = [*understanding.errors, *synthesis.errors]

        logger.info(
            "Query answer completed: answer_generated=%s warnings=%s errors=%s",
            answer is not None,
            len(warnings),
            len(errors),
        )

        return QueryAnswerResponse(
            understanding=understanding,
            answer=answer,
            secondary_evidence=secondary_evidence,
            context_evidence=context_evidence,
            question_rxnorm_network=question_rxnorm_network,
            question_evidence_map=question_evidence_map,
            coverage=coverage,
            contract=contract,
            validation=validation,
            critique=critique,
            warnings=warnings,
            errors=errors,
        )
