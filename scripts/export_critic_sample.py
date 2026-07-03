"""Export a blind critic label sheet from eval-harness run outputs (D3b).

Reads the raw per-question JSONs written by scripts/run_eval.py (combined
mode — citations need critic statuses), samples citations stratified by
critic status (all flagged + accurate up to --target), and writes a BLIND
sheet plus a sealed key file with the critic's verdicts.

Example:
    .venv/bin/python scripts/export_critic_sample.py \
        --runs evals/runs/20260703T150000Z_combined --name sheet_2026-07-04
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")

from src.query_answer.models import QueryAnswerResponse  # noqa: E402
from src.query_answer.synthesizer import EvidenceAnswerSynthesizer  # noqa: E402


class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):  # noqa: ANN001
        return True


def collect_citations(run_dirs: list[Path]) -> tuple[list[dict], list[dict]]:
    """Return (flagged, accurate) citation records across all run files."""

    synthesizer = EvidenceAnswerSynthesizer()
    flagged: list[dict] = []
    accurate: list[dict] = []

    for run_dir in run_dirs:
        for path in sorted(run_dir.glob("q*.json")):
            data = json.loads(path.read_text())
            response = QueryAnswerResponse.model_validate(data["response"])
            if response.answer is None:
                continue
            # Rebuild the evidence packet to recover the exact cited text
            # (same content, same truncation) the synthesis model was shown.
            packet = synthesizer.build_evidence_packet(
                response.understanding,
                secondary_evidence=response.secondary_evidence,
                context_evidence=response.context_evidence,
                contract=response.contract,
            )
            cited_text = {
                (s.get("source_id"), s.get("section")): s.get("text", "")
                for s in packet.get("label_sections", [])
            }
            critique_by_idx = {
                (c.bullet_index, c.citation_index): c
                for c in response.critique.citations
            }
            for bi, bullet in enumerate(response.answer.bullets):
                for ci, citation in enumerate(bullet.citations):
                    if citation.support_status is None:
                        continue
                    critique = critique_by_idx.get((bi, ci))
                    record = {
                        "question_id": data["question_id"],
                        "question": data["question"],
                        "response": response.answer.response,
                        "limitations": list(response.answer.limitations),
                        "claim": bullet.text,
                        "cited_source": {
                            "source_id": citation.source_id,
                            "section": citation.section,
                        },
                        "cited_text": cited_text.get(
                            (citation.source_id, citation.section), ""
                        ),
                        "_status": citation.support_status,
                        "_rationale": critique.rationale if critique else "",
                    }
                    if citation.support_status != "accurate":
                        flagged.append(record)
                    else:
                        accurate.append(record)
    return flagged, accurate


def main() -> int:
    parser = argparse.ArgumentParser(description="Export blind label sheet.")
    parser.add_argument("--runs", type=Path, nargs="+", required=True)
    parser.add_argument("--name", required=True, help="e.g. sheet_2026-07-04")
    parser.add_argument(
        "--out-dir", type=Path, default=REPO_ROOT / "evals" / "critic_labels"
    )
    parser.add_argument("--target", type=int, default=75)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    sheet_path = args.out_dir / f"{args.name}.yml"
    key_path = args.out_dir / f"{args.name}.key.yml"
    for path in (sheet_path, key_path):
        if path.exists():
            print(f"Refusing to overwrite {path}", file=sys.stderr)
            return 2

    flagged, accurate = collect_citations(args.runs)
    if not flagged and not accurate:
        print("No critic-scored citations found in the given runs.", file=sys.stderr)
        return 2

    rng = random.Random(args.seed)
    rng.shuffle(accurate)
    sample = flagged + accurate[: max(0, args.target - len(flagged))]
    rng.shuffle(sample)

    sheet_items, key_items = [], []
    for i, record in enumerate(sample, start=1):
        hidden = {k: record.pop(k) for k in ("_status", "_rationale")}
        sheet_items.append(
            {
                "item": i,
                **record,
                "claim_matches_source": "",
                "answer_reflects_claim": "",
                "skip": False,
                "labeler_notes": "",
            }
        )
        key_items.append(
            {
                "item": i,
                "question_id": record["question_id"],
                "critic_status": hidden["_status"],
                "critic_rationale": hidden["_rationale"],
            }
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    header = (
        "# BLIND critic label sheet — see evals/LABELING_GUIDE.md.\n"
        "# Do NOT open the matching .key.yml until all items are labeled.\n"
        f"# {len(sheet_items)} items ({len(flagged)} flagged + "
        f"{len(sheet_items) - len(flagged)} accurate before shuffling; "
        "order is randomized).\n\n"
    )
    sheet_path.write_text(
        header
        + yaml.dump(
            sheet_items,
            Dumper=NoAliasDumper,
            sort_keys=False,
            allow_unicode=True,
            width=88,
        )
    )
    key_path.write_text(
        f"# Critic verdicts for {args.name}.yml — open only after labeling.\n\n"
        + yaml.dump(
            key_items,
            Dumper=NoAliasDumper,
            sort_keys=False,
            allow_unicode=True,
            width=88,
        )
    )
    print(
        f"Sheet: {sheet_path} ({len(sheet_items)} items; {len(flagged)} "
        f"flagged, {len(sample) - len(flagged)} accurate)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
