from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.dossier.builder import DossierBuilder
from src.dossier.openfda_store import OpenFDALabelStore
from src.dossier.rxnorm_store import RxNormParquetStore
from src.evals.metrics import evaluate_question
from src.evals.models import (
    EvalMode,
    EvalQuestion,
    EvalRunResult,
    QuestionResult,
    load_questions,
)
from src.query_answer.service import QueryAnswerService
from src.query_answer.synthesizer import (
    AnswerSynthesisResult,
    EvidenceAnswerSynthesizer,
)

logger = logging.getLogger(__name__)


class NullSynthesizer(EvidenceAnswerSynthesizer):
    """Symbolic-only mode: extraction, retrieval, coverage — no LLM synthesis.

    Returning answer=None also disables the critic (finalize_answer_critique
    exits early), so a symbolic run is fully deterministic and keyless.
    """

    def synthesize(self, *args, **kwargs) -> AnswerSynthesisResult:
        return AnswerSynthesisResult(
            warnings=["symbolic-only eval mode: LLM synthesis disabled"]
        )


def load_questions_file(path: Path) -> list[EvalQuestion]:
    return load_questions(yaml.safe_load(path.read_text()))


def build_service(mode: EvalMode) -> QueryAnswerService:
    builder = DossierBuilder(
        rxnorm_store=RxNormParquetStore(),
        openfda_store=OpenFDALabelStore(use_cache=True, allow_live=True),
    )
    if mode == "symbolic":
        # Fully deterministic: also drop the extraction-LLM config for this
        # process, so a symbolic run behaves identically with or without keys.
        os.environ.pop("QUERY_EXTRACTION_OPENAI_API_KEY", None)
        os.environ.pop("QUERY_EXTRACTION_OPENAI_MODEL", None)
        return QueryAnswerService(builder=builder, synthesizer=NullSynthesizer())
    if mode == "extraction":
        # LLM query-state revision only: cheapest LLM mode, one extraction
        # call per question — no synthesis, no critic, no citations.
        return QueryAnswerService(builder=builder, synthesizer=NullSynthesizer())
    if mode == "neural":
        raise NotImplementedError("neural mode lands with roadmap package D4")
    return QueryAnswerService(builder=builder)


def run_eval(
    questions: list[EvalQuestion],
    *,
    mode: EvalMode = "combined",
    repeats: int = 1,
    out_dir: Path | None = None,
    service: QueryAnswerService | None = None,
) -> EvalRunResult:
    """Run every question ``repeats`` times and score each response.

    Raw responses are written per question/repeat when ``out_dir`` is given,
    so failures don't lose completed work and post-hoc analysis (e.g. the D3b
    critic sample export) can reuse the run.
    """

    service = service or build_service(mode)
    run = EvalRunResult(
        mode=mode,
        questions_file="",
        repeats=repeats,
        started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)

    for question in questions:
        for repeat in range(repeats):
            started = time.time()
            try:
                response = service.answer(question.question)
            except Exception as exc:  # noqa: BLE001 — one bad question must not sink a run
                logger.exception("eval question %s failed", question.id)
                run.results.append(
                    QuestionResult(
                        question_id=question.id,
                        category=question.category,
                        mode=mode,
                        repeat=repeat,
                        elapsed_s=round(time.time() - started, 2),
                        error=repr(exc),
                    )
                )
                continue
            elapsed = time.time() - started
            result = evaluate_question(
                question,
                response,
                mode=mode,
                repeat=repeat,
                elapsed_s=elapsed,
            )
            run.results.append(result)
            if out_dir is not None:
                raw_path = out_dir / f"{question.id}.r{repeat}.json"
                raw_path.write_text(
                    json.dumps(
                        {
                            "question_id": question.id,
                            "question": question.question,
                            "mode": mode,
                            "repeat": repeat,
                            "elapsed_s": round(elapsed, 2),
                            "response": response.model_dump(mode="json"),
                        },
                        indent=2,
                    )
                )
            status = "pass" if result.passed else "FAIL"
            logger.info(
                "eval %s r%s: %s in %.0fs", question.id, repeat, status, elapsed
            )

    return run


__all__ = ["NullSynthesizer", "build_service", "load_questions_file", "run_eval"]
