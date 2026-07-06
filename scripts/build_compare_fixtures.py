"""Build the precomputed fixtures for the /compare page (roadmap D4).

Runs the showcase questions through all three modes — neural (one
unconstrained LLM call), symbolic (deterministic pipeline, no synthesis),
combined (full production pipeline) — computes the deterministic property
scorecard, and writes trimmed results to
apps/frontend/src/data/compare-fixtures.json (committed; the page imports it
statically, so the live deployment serves the comparison with zero
per-visitor LLM cost).

Ordering note: build_service("symbolic") strips the extraction-LLM env vars
for the whole process, so all LLM-dependent phases run BEFORE the symbolic
phase.

Cost: ~8 questions x (1 neural + 1 full combined pipeline) ≈ cents.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")

import os  # noqa: E402

from src.evals.compare import build_scorecard, personal_advice_hits  # noqa: E402
from src.evals.neural import generate_neural_answer  # noqa: E402
from src.evals.runner import build_service, load_questions_file  # noqa: E402
from src.query_answer.models import QueryAnswerResponse  # noqa: E402

SHOWCASE_IDS = [
    "q28_trap_fictional_drug",  # default on the page: the money shot
    "q31_trap_leading_yes_no",
    "q29_trap_false_premise",
    "q09_interaction_ibuprofen_aspirin",
    "q17_allergy_amoxicillin_penicillin",
    "q20_pregnancy_acetaminophen",
    "q33_gap_loratadine_metformin_interaction",
    "q38_complex_elderly_warfarin_metformin_ibuprofen",
]

WATCH_HINTS = {
    "q28_trap_fictional_drug": (
        "Zortivan does not exist. Watch which modes notice."
    ),
    "q31_trap_leading_yes_no": "A question fishing for personal permission.",
    "q29_trap_false_premise": (
        "Acetaminophen has no anxiety indication — does the premise survive?"
    ),
    "q09_interaction_ibuprofen_aspirin": (
        "A genuinely label-documented interaction."
    ),
    "q17_allergy_amoxicillin_penicillin": (
        "High-stakes allergy cross-reactivity."
    ),
    "q20_pregnancy_acetaminophen": (
        "Patient-context targeting (pregnancy sections)."
    ),
    "q33_gap_loratadine_metformin_interaction": (
        "No documented interaction — honesty about absence."
    ),
    "q38_complex_elderly_warfarin_metformin_ibuprofen": (
        "Real-world phrasing: third person, three drugs, age context."
    ),
}

OUT_PATH = REPO_ROOT / "apps" / "frontend" / "src" / "data" / "compare-fixtures.json"


def trim_combined(response: QueryAnswerResponse) -> dict:
    answer = response.answer
    if answer is None:
        return {"response": "", "bullets": [], "limitations": [], "safety_note": ""}
    return {
        "response": answer.response,
        "bullets": [
            {
                "text": bullet.text,
                "citations": [
                    {
                        "source_id": c.source_id,
                        "section": c.section,
                        "support_status": c.support_status,
                    }
                    for c in bullet.citations
                ],
            }
            for bullet in answer.bullets
        ],
        "limitations": list(answer.limitations),
        "safety_note": answer.safety_note,
    }


def trim_symbolic(response: QueryAnswerResponse, service) -> dict:
    state = response.understanding.state
    packet = service.synthesizer.build_evidence_packet(
        response.understanding,
        secondary_evidence=response.secondary_evidence,
        context_evidence=response.context_evidence,
        contract=response.contract,
    )
    section_counts: dict[str, int] = {}
    source_labels: dict[str, str] = {}
    for entry in packet.get("label_sections", []):
        section = entry.get("section", "")
        section_counts[section] = section_counts.get(section, 0) + 1
        source_id = entry.get("source_id")
        if source_id and source_id not in source_labels:
            drug = entry.get("drug_name") or "label"
            source_labels[source_id] = f"{drug} label {len(source_labels) + 1}"
    return {
        "state": {
            "drugs": list(state.all_drugs_mentioned),
            "current_medications": list(state.current_medications),
            "allergies": list(state.allergies),
            "conditions": list(state.conditions),
            "patient_context": list(state.patient_context),
            "intents": list(state.intents),
        },
        "resolved": [
            {
                "text": m.text,
                "role": m.role,
                "rxcui": m.selected_concept.rxcui if m.selected_concept else None,
                "name": m.selected_concept.name if m.selected_concept else None,
                "tty": m.selected_concept.tty if m.selected_concept else None,
            }
            for m in response.understanding.resolved_drugs
        ],
        "coverage": [
            {
                "category": item.category,
                "label": item.label,
                "status": item.status,
                "reason": item.reason,
            }
            for item in response.coverage.items
        ],
        "section_counts": section_counts,
        "source_labels": source_labels,
    }


def main() -> int:
    questions = {
        q.id: q
        for q in load_questions_file(REPO_ROOT / "evals" / "questions.yml")
    }
    missing = [qid for qid in SHOWCASE_IDS if qid not in questions]
    if missing:
        print(f"Unknown showcase ids: {missing}", file=sys.stderr)
        return 2

    # Phase 1: everything that needs LLM env config.
    print("Phase 1/2: neural + combined runs (LLM)...", flush=True)
    neural_texts: dict[str, str] = {}
    combined_responses: dict[str, QueryAnswerResponse] = {}
    combined_service = build_service("combined")
    for qid in SHOWCASE_IDS:
        question = questions[qid]
        print(f"  [neural  ] {qid}", flush=True)
        neural_texts[qid] = generate_neural_answer(question.question)
        print(f"  [combined] {qid}", flush=True)
        combined_responses[qid] = combined_service.answer(question.question)

    # Phase 2: symbolic (strips extraction-LLM env for this process).
    print("Phase 2/2: symbolic runs (deterministic)...", flush=True)
    symbolic_service = build_service("symbolic")
    fixtures = []
    for qid in SHOWCASE_IDS:
        question = questions[qid]
        print(f"  [symbolic] {qid}", flush=True)
        symbolic_response = symbolic_service.answer(question.question)
        fixtures.append(
            {
                "id": qid,
                "question": question.question,
                "category": question.category,
                "hint": WATCH_HINTS.get(qid, ""),
                "neural": {
                    "text": neural_texts[qid],
                    "advice_phrases": personal_advice_hits(neural_texts[qid]),
                },
                "symbolic": trim_symbolic(symbolic_response, symbolic_service),
                "combined": trim_combined(combined_responses[qid]),
                "scorecard": build_scorecard(
                    question,
                    neural_text=neural_texts[qid],
                    symbolic_response=symbolic_response,
                    combined_response=combined_responses[qid],
                ),
            }
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(
                    timespec="seconds"
                ),
                "synthesis_model": os.getenv("ANSWER_SYNTHESIS_OPENAI_MODEL", ""),
                "questions": fixtures,
            },
            indent=2,
        )
        + "\n"
    )
    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"Wrote {OUT_PATH} ({size_kb:.0f} KB, {len(fixtures)} questions)")
    if size_kb > 400:
        print("WARNING: fixture file larger than the ~300 KB target", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
