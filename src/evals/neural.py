from __future__ import annotations

import os
from typing import Any, Protocol

from src.query_answer.synthesizer import EvidenceAnswerSynthesizer

NEURAL_PROMPT_KEY = "neural_only_answer"
API_KEY_ENV = "ANSWER_SYNTHESIS_OPENAI_API_KEY"
MODEL_ENV = "ANSWER_SYNTHESIS_OPENAI_MODEL"


class NeuralTextRequester(Protocol):
    def __call__(
        self,
        *,
        messages: list[dict[str, str]],
        prompt_config: dict[str, Any],
    ) -> str:
        """Return the plain-text model answer."""


def neural_llm_configured() -> bool:
    return bool(os.getenv(API_KEY_ENV) and os.getenv(MODEL_ENV))


def generate_neural_answer(
    question: str,
    *,
    requester: NeuralTextRequester | None = None,
) -> str:
    """One unconstrained LLM call: no retrieval, no whitelist, no guardrails.

    Evaluation-only (D4). Uses the deliberately neutral `neural_only_answer`
    prompt — see the neutrality requirement comment in conf/base/prompts.yml.
    """

    prompt_config = EvidenceAnswerSynthesizer._load_prompt_config(NEURAL_PROMPT_KEY)
    messages = EvidenceAnswerSynthesizer._format_messages(
        prompt_config.get("messages", []),
        query=question,
    )
    if requester is not None:
        return requester(messages=messages, prompt_config=prompt_config)

    from openai import OpenAI  # type: ignore[import-not-found]

    client = OpenAI(api_key=os.getenv(API_KEY_ENV))
    response = client.chat.completions.create(
        model=os.getenv(MODEL_ENV),
        messages=messages,
        temperature=0,
    )
    return response.choices[0].message.content or ""


__all__ = ["NeuralTextRequester", "generate_neural_answer", "neural_llm_configured"]
