from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.utils import load_parameters


@dataclass(frozen=True)
class QueryAnswerParameters:
    default_openfda_limit: int = 10
    secondary_openfda_limit: int = 3
    max_secondary_drugs: int = 3
    interaction_lookup_limit: int = 3
    max_synthesis_retries: int = 1
    require_citations_when_evidence_exists: bool = True


def load_query_answer_parameters() -> QueryAnswerParameters:
    parameters = load_parameters()
    query_answer = parameters.get("query_answer", {})
    if not isinstance(query_answer, dict):
        query_answer = {}

    return QueryAnswerParameters(
        default_openfda_limit=bounded_int(
            query_answer.get("default_openfda_limit"),
            default=10,
            minimum=1,
            maximum=25,
        ),
        secondary_openfda_limit=bounded_int(
            query_answer.get("secondary_openfda_limit"),
            default=3,
            minimum=1,
            maximum=10,
        ),
        max_secondary_drugs=bounded_int(
            query_answer.get("max_secondary_drugs"),
            default=3,
            minimum=0,
            maximum=5,
        ),
        interaction_lookup_limit=bounded_int(
            query_answer.get("interaction_lookup_limit"),
            default=3,
            minimum=0,
            maximum=10,
        ),
        max_synthesis_retries=bounded_int(
            query_answer.get("max_synthesis_retries"),
            default=1,
            minimum=0,
            maximum=3,
        ),
        require_citations_when_evidence_exists=bool(
            query_answer.get("require_citations_when_evidence_exists", True)
        ),
    )


def bounded_int(
    value: Any,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, minimum), maximum)
