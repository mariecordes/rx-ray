"""Run the rx-ray evaluation harness (roadmap D3a).

Examples:
    .venv/bin/python scripts/run_eval.py --mode symbolic          # keyless
    .venv/bin/python scripts/run_eval.py --repeats 3 --update-latest
    .venv/bin/python scripts/run_eval.py --only q10 q28 --mode combined
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")

from src.evals.report import build_report, render_markdown  # noqa: E402
from src.evals.runner import load_questions_file, run_eval  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the rx-ray eval harness.")
    parser.add_argument(
        "--questions",
        type=Path,
        default=REPO_ROOT / "evals" / "questions.yml",
    )
    parser.add_argument(
        "--mode",
        choices=["combined", "combined_extraction_only", "symbolic", "neural"],
        default="combined",
    )
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="Question id prefixes to include (e.g. q10 q28).",
    )
    parser.add_argument(
        "--category",
        nargs="*",
        default=None,
        help="Question categories to include (e.g. trap interaction_2).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Run output dir (default evals/runs/<utc timestamp>_<mode>).",
    )
    parser.add_argument(
        "--update-latest",
        action="store_true",
        help="Also refresh the committed evals/results/latest.{json,md}.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    questions = load_questions_file(args.questions)
    if args.only:
        questions = [
            q for q in questions if any(q.id.startswith(p) for p in args.only)
        ]
    if args.category:
        questions = [q for q in questions if q.category in args.category]
    if not questions:
        print("No questions selected.", file=sys.stderr)
        return 2

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.out or REPO_ROOT / "evals" / "runs" / f"{timestamp}_{args.mode}"
    run = run_eval(
        questions,
        mode=args.mode,
        repeats=args.repeats,
        out_dir=out_dir,
    )
    run.questions_file = str(args.questions.relative_to(REPO_ROOT))

    report = build_report(run)
    markdown = render_markdown(report)
    (out_dir / "results.json").write_text(json.dumps(report, indent=2))
    (out_dir / "results.md").write_text(markdown)
    print(markdown)
    print(f"Run written to {out_dir}")

    if args.update_latest:
        results_dir = REPO_ROOT / "evals" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        (results_dir / "latest.json").write_text(json.dumps(report, indent=2))
        (results_dir / "latest.md").write_text(markdown)
        print(f"Updated {results_dir}/latest.json and latest.md")

    headline = report["headline"]
    return 0 if headline["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
