from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.utils import load_parameters


@dataclass(frozen=True)
class QueryAnswerParameters:
    default_openfda_limit: int = 10
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
