"""Score a labeled critic sheet against the sealed key (roadmap D3b).

Example:
    .venv/bin/python scripts/score_critic_labels.py \
        --sheet evals/critic_labels/sheet_2026-07-02.yml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.evals.critic_study import (  # noqa: E402
    LabelSheetError,
    render_markdown,
    score_study,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Score critic label sheet.")
    parser.add_argument("--sheet", type=Path, required=True)
    parser.add_argument(
        "--key",
        type=Path,
        default=None,
        help="Key file (default: <sheet>.key.yml next to the sheet).",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Score even if some items are unlabeled.",
    )
    args = parser.parse_args()

    key_path = args.key or args.sheet.parent / (
        args.sheet.name.removesuffix(".yml") + ".key.yml"
    )
    sheet_items = yaml.safe_load(args.sheet.read_text())
    key_items = yaml.safe_load(key_path.read_text())

    try:
        report = score_study(
            sheet_items, key_items, allow_partial=args.allow_partial
        )
    except LabelSheetError as exc:
        print(f"Cannot score: {exc}", file=sys.stderr)
        return 2

    markdown = render_markdown(report, sheet_name=args.sheet.name)
    out_base = args.sheet.parent / (
        args.sheet.name.removesuffix(".yml") + ".scoring"
    )
    Path(f"{out_base}.md").write_text(markdown)
    serializable = dict(report)
    Path(f"{out_base}.json").write_text(json.dumps(serializable, indent=2))
    print(markdown)
    print(f"Written to {out_base}.md and {out_base}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
