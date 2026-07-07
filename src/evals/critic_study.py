from __future__ import annotations

from collections import Counter
from typing import Any

# Mirrors the frontend derivation in generated-response.tsx: each 5-tier
# critic status encodes (source-match axis, answer-use axis). Keep in sync.
CRITIC_STATUS_AXES: dict[str, tuple[str, str]] = {
    "accurate": ("matches", "reflected"),
    "not_reflected": ("matches", "not_reflected"),
    "contradicted": ("matches", "contradicted"),
    "misrepresented": ("misreads", "not_reflected"),
    "misrepresented_used": ("misreads", "reflected"),
}

SOURCE_AXIS_VALUES = ("matches", "misreads")
ANSWER_AXIS_VALUES = ("reflected", "not_reflected", "contradicted")

# Human sheet vocabulary → axis values.
HUMAN_SOURCE_LABELS = {"yes": "matches", "no": "misreads"}


class LabelSheetError(ValueError):
    """Raised when the label sheet can't be scored as-is."""


def human_axes(item: dict[str, Any]) -> tuple[str, str]:
    """Normalize one labeled sheet item to (source_axis, answer_axis)."""

    source_raw = str(item.get("claim_matches_source", "")).strip().lower()
    answer_raw = str(item.get("answer_reflects_claim", "")).strip().lower()
    source = HUMAN_SOURCE_LABELS.get(source_raw, source_raw)
    if source not in SOURCE_AXIS_VALUES:
        raise LabelSheetError(
            f"item {item.get('item')}: claim_matches_source must be yes/no, "
            f"got {item.get('claim_matches_source')!r}"
        )
    if answer_raw not in ANSWER_AXIS_VALUES:
        raise LabelSheetError(
            f"item {item.get('item')}: answer_reflects_claim must be one of "
            f"{ANSWER_AXIS_VALUES}, got {item.get('answer_reflects_claim')!r}"
        )
    return source, answer_raw


def critic_axes(status: str) -> tuple[str, str]:
    if status not in CRITIC_STATUS_AXES:
        raise LabelSheetError(f"unknown critic status {status!r}")
    return CRITIC_STATUS_AXES[status]


def cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's κ over (rater_a, rater_b) label pairs.

    Returns None when expected agreement is 1 (degenerate marginals — both
    raters used a single identical label throughout), where κ is undefined.
    """

    if not pairs:
        return None
    n = len(pairs)
    observed = sum(1 for a, b in pairs if a == b) / n
    counts_a = Counter(a for a, _ in pairs)
    counts_b = Counter(b for _, b in pairs)
    labels = set(counts_a) | set(counts_b)
    expected = sum(
        (counts_a.get(label, 0) / n) * (counts_b.get(label, 0) / n)
        for label in labels
    )
    if expected >= 1.0:
        return None
    return (observed - expected) / (1 - expected)


def score_study(
    sheet_items: list[dict[str, Any]],
    key_items: list[dict[str, Any]],
    *,
    allow_partial: bool = False,
) -> dict[str, Any]:
    """Score human labels against critic verdicts.

    The human labels are treated as ground truth: "flagged" precision/recall
    read as "when the critic deviates from accurate, is the human's judgment
    also non-clean, and does the critic catch the items the human flags".
    """

    key_by_item = {item["item"]: item for item in key_items}
    skipped: list[int] = []
    unlabeled: list[int] = []
    rows: list[dict[str, Any]] = []

    for item in sheet_items:
        item_id = item.get("item")
        if item.get("skip"):
            skipped.append(item_id)
            continue
        if not str(item.get("claim_matches_source", "")).strip() and not str(
            item.get("answer_reflects_claim", "")
        ).strip():
            unlabeled.append(item_id)
            continue
        key = key_by_item.get(item_id)
        if key is None:
            raise LabelSheetError(f"item {item_id}: missing from key file")
        human_source, human_answer = human_axes(item)
        critic_source, critic_answer = critic_axes(key["critic_status"])
        rows.append(
            {
                "item": item_id,
                "question_id": item.get("question_id"),
                "human": (human_source, human_answer),
                "critic": (critic_source, critic_answer),
                "critic_status": key["critic_status"],
                "critic_rationale": key.get("critic_rationale", ""),
                "labeler_notes": item.get("labeler_notes", ""),
            }
        )

    if unlabeled and not allow_partial:
        preview = ", ".join(str(i) for i in unlabeled[:10])
        raise LabelSheetError(
            f"{len(unlabeled)} unlabeled item(s) (e.g. {preview}); finish "
            "labeling or pass --allow-partial"
        )

    source_pairs = [(r["critic"][0], r["human"][0]) for r in rows]
    answer_pairs = [(r["critic"][1], r["human"][1]) for r in rows]

    critic_flagged = [r["critic_status"] != "accurate" for r in rows]
    human_flagged = [
        r["human"] != ("matches", "reflected") for r in rows
    ]
    true_pos = sum(1 for c, h in zip(critic_flagged, human_flagged) if c and h)
    flagged_precision = (
        true_pos / sum(critic_flagged) if sum(critic_flagged) else None
    )
    flagged_recall = true_pos / sum(human_flagged) if sum(human_flagged) else None

    disagreements = [
        r
        for r in rows
        if r["human"][0] != r["critic"][0] or r["human"][1] != r["critic"][1]
    ]

    return {
        "n_labeled": len(rows),
        "n_skipped": len(skipped),
        "n_unlabeled": len(unlabeled),
        "source_axis": _axis_report(source_pairs, SOURCE_AXIS_VALUES),
        "answer_axis": _axis_report(answer_pairs, ANSWER_AXIS_VALUES),
        "flagged": {
            "critic_flagged": sum(critic_flagged),
            "human_flagged": sum(human_flagged),
            "true_positives": true_pos,
            "precision": flagged_precision,
            "recall": flagged_recall,
        },
        "disagreements": disagreements,
    }


def render_markdown(report: dict[str, Any], *, sheet_name: str) -> str:
    lines = [
        "# Critic accuracy study (D3b)",
        "",
        f"Sheet `{sheet_name}` · {report['n_labeled']} labeled items "
        f"({report['n_skipped']} skipped, {report['n_unlabeled']} unlabeled)",
        "",
        "Human labels are the reference. Limitation: single annotator, so κ",
        "measures human–critic agreement, not inter-annotator reliability.",
        "",
        "## Agreement per axis",
        "",
        "| axis | raw agreement | Cohen's κ |",
        "|---|---|---|",
        _axis_row("source match (claim vs cited text)", report["source_axis"]),
        _axis_row("answer use (response vs claim)", report["answer_axis"]),
        "",
        "## Critic 'flagged' vs human judgment",
        "",
        f"- Critic flagged: {report['flagged']['critic_flagged']} · human "
        f"flagged: {report['flagged']['human_flagged']} · overlap: "
        f"{report['flagged']['true_positives']}",
        f"- Precision (critic flag confirmed by human): "
        f"{_fmt(report['flagged']['precision'])}",
        f"- Recall (human flag caught by critic): "
        f"{_fmt(report['flagged']['recall'])}",
    ]

    for axis_key, values, title in (
        ("source_axis", SOURCE_AXIS_VALUES, "Source-match confusion"),
        ("answer_axis", ANSWER_AXIS_VALUES, "Answer-use confusion"),
    ):
        lines += ["", f"## {title} (rows: critic · columns: human)", ""]
        lines.append("| critic \\ human | " + " | ".join(values) + " |")
        lines.append("|---" * (len(values) + 1) + "|")
        matrix = report[axis_key]["confusion"]
        for critic_value in values:
            row = matrix.get(critic_value, {})
            cells = " | ".join(str(row.get(v, 0)) for v in values)
            lines.append(f"| {critic_value} | {cells} |")

    if report["disagreements"]:
        lines += ["", "## Disagreements (error-analysis material)", ""]
        for r in report["disagreements"]:
            lines.append(
                f"- item {r['item']} ({r['question_id']}): critic "
                f"`{r['critic_status']}` → {r['critic']}, human {r['human']}"
                + (f" — notes: {r['labeler_notes']}" if r["labeler_notes"] else "")
            )

    return "\n".join(lines) + "\n"


def _axis_report(
    pairs: list[tuple[str, str]], values: tuple[str, ...]
) -> dict[str, Any]:
    agreement = (
        sum(1 for a, b in pairs if a == b) / len(pairs) if pairs else None
    )
    confusion: dict[str, dict[str, int]] = {v: {} for v in values}
    for critic_value, human_value in pairs:
        row = confusion.setdefault(critic_value, {})
        row[human_value] = row.get(human_value, 0) + 1
    return {
        "agreement": agreement,
        "kappa": cohen_kappa(pairs),
        "confusion": confusion,
    }


def _axis_row(label: str, axis: dict[str, Any]) -> str:
    return f"| {label} | {_fmt(axis['agreement'])} | {_fmt(axis['kappa'])} |"


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


__all__ = [
    "CRITIC_STATUS_AXES",
    "LabelSheetError",
    "cohen_kappa",
    "critic_axes",
    "human_axes",
    "render_markdown",
    "score_study",
]
