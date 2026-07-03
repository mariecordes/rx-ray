from __future__ import annotations

import statistics
from collections import defaultdict

from src.evals.models import EvalRunResult, QuestionResult


def build_report(run: EvalRunResult) -> dict:
    """Aggregate a run into the JSON report structure."""

    by_question: dict[str, list[QuestionResult]] = defaultdict(list)
    for result in run.results:
        by_question[result.question_id].append(result)

    per_question = [_question_summary(results) for results in by_question.values()]
    per_category: dict[str, dict] = {}
    for summary in per_question:
        bucket = per_category.setdefault(
            summary["category"], {"questions": 0, "passed": 0}
        )
        bucket["questions"] += 1
        bucket["passed"] += 1 if summary["passed_all_repeats"] else 0
        bucket["pass_rate"] = bucket["passed"] / bucket["questions"]

    return {
        "mode": run.mode,
        "started_at": run.started_at,
        "repeats": run.repeats,
        "questions": len(per_question),
        "headline": _headline(run, per_question),
        "field_scores": _field_score_means(run.results),
        "match_quality": _match_quality_counts(run.results),
        "guardrails": _guardrail_rates(run.results),
        "per_category": per_category,
        "per_question": per_question,
    }


def render_markdown(report: dict) -> str:
    headline = report["headline"]
    lines = [
        "# rx-ray evaluation report",
        "",
        f"Mode `{report['mode']}` · {report['questions']} questions × "
        f"{report['repeats']} repeat(s) · started {report['started_at']}",
        "",
        "## Headline",
        "",
        f"- Questions passing all behavioral checks in every repeat: "
        f"**{headline['questions_passed']}/{report['questions']}**",
        f"- Behavioral checks passed: **{headline['checks_passed']}/"
        f"{headline['checks_total']}** ({headline['check_pass_rate']:.0%})",
        f"- Verdict flips across repeats: {headline['verdict_flips']}",
        f"- Latency p50/p95: {headline['latency_p50_s']:.1f}s / "
        f"{headline['latency_p95_s']:.1f}s",
        f"- Errors: {headline['errors']}",
        "",
        "Guardrail intervention rates measure how often the deterministic",
        "layer had to correct the neural layer — the quantity the",
        "architecture exists to control, not an error rate of the system.",
        "",
        "## Guardrail interventions (share of answered runs)",
        "",
    ]
    for kind, rate in sorted(report["guardrails"].items()):
        lines.append(f"- `{kind}`: {rate:.0%}")

    lines += ["", "## Extraction & resolution (macro means)", ""]
    lines.append("| field | precision | recall | f1 |")
    lines.append("|---|---|---|---|")
    for field, scores in report["field_scores"].items():
        lines.append(
            f"| {field} | {_fmt(scores['precision'])} | "
            f"{_fmt(scores['recall'])} | {_fmt(scores['f1'])} |"
        )

    lines += [
        "",
        "## Extraction match quality",
        "",
        "Set comparison per field: `exact` = expected matched, nothing extra ·",
        "`extra` = expected matched but extractor added more · `partial` = some",
        "expected matched · `none` = nothing matched. Checks gate on recall",
        "(expectations are minimum requirements), so `extra` never fails a",
        "question — this table makes it visible instead.",
        "",
        "| field | exact | extra | partial | none |",
        "|---|---|---|---|---|",
    ]
    for field, counts in report["match_quality"].items():
        lines.append(
            f"| {field} | {counts.get('exact', 0)} | {counts.get('extra', 0)} | "
            f"{counts.get('partial', 0)} | {counts.get('none', 0)} |"
        )

    lines += ["", "## Per category", ""]
    lines.append("| category | questions | passed | pass rate |")
    lines.append("|---|---|---|---|")
    for category, bucket in sorted(report["per_category"].items()):
        lines.append(
            f"| {category} | {bucket['questions']} | {bucket['passed']} | "
            f"{bucket['pass_rate']:.0%} |"
        )

    lines += ["", "## Per question", ""]
    lines.append("| id | passed | failed checks |")
    lines.append("|---|---|---|")
    for summary in report["per_question"]:
        failed = ", ".join(summary["failed_checks"]) or "—"
        passed = "✅" if summary["passed_all_repeats"] else "❌"
        lines.append(f"| {summary['question_id']} | {passed} | {failed} |")

    return "\n".join(lines) + "\n"


def _question_summary(results: list[QuestionResult]) -> dict:
    verdicts = [result.passed for result in results]
    failed_checks = sorted(
        {
            check.name
            for result in results
            for check in result.checks
            if not check.passed
        }
    )
    for result in results:
        if result.error:
            failed_checks.append(f"error: {result.error}")
    return {
        "question_id": results[0].question_id,
        "category": results[0].category,
        "passed_all_repeats": all(verdicts),
        "verdict_flipped": len(set(verdicts)) > 1,
        "failed_checks": failed_checks,
    }


def _headline(run: EvalRunResult, per_question: list[dict]) -> dict:
    checks = [check for result in run.results for check in result.checks]
    latencies = sorted(result.elapsed_s for result in run.results)
    return {
        "questions_passed": sum(1 for q in per_question if q["passed_all_repeats"]),
        "checks_total": len(checks),
        "checks_passed": sum(1 for check in checks if check.passed),
        "check_pass_rate": (
            sum(1 for check in checks if check.passed) / len(checks) if checks else 0.0
        ),
        "verdict_flips": sum(1 for q in per_question if q["verdict_flipped"]),
        "latency_p50_s": _percentile(latencies, 0.5),
        "latency_p95_s": _percentile(latencies, 0.95),
        "errors": sum(1 for result in run.results if result.error),
    }


def _field_score_means(results: list[QuestionResult]) -> dict:
    values: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"precision": [], "recall": [], "f1": []}
    )
    for result in results:
        for field, score in result.field_scores.items():
            for metric in ("precision", "recall", "f1"):
                value = getattr(score, metric)
                if value is not None:
                    values[field][metric].append(value)
    return {
        field: {
            metric: (statistics.mean(items) if items else None)
            for metric, items in metrics.items()
        }
        for field, metrics in values.items()
    }


def _match_quality_counts(results: list[QuestionResult]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"exact": 0, "extra": 0, "partial": 0, "none": 0}
    )
    for result in results:
        for field, score in result.field_scores.items():
            if score.match_quality is not None:
                counts[field][score.match_quality] += 1
    return dict(counts)


def _guardrail_rates(results: list[QuestionResult]) -> dict[str, float]:
    answered = [result for result in results if result.answer_generated]
    if not answered:
        return {}
    rates: dict[str, float] = {}
    for kind in (
        "missing_caveat_enforced",
        "uncited_bullet_relocated",
        "yes_no_framing",
        "must_mention_unaddressed",
    ):
        hits = sum(1 for r in answered if kind in r.validation_finding_kinds)
        rates[kind] = hits / len(answered)
    rates["critic_regenerated"] = sum(
        1 for r in answered if r.critic_regenerated
    ) / len(answered)
    flagged = sum(
        count
        for r in answered
        for status, count in r.critic_status_counts.items()
        if status != "accurate"
    )
    total = sum(count for r in answered for count in r.critic_status_counts.values())
    rates["critic_flagged_citations"] = flagged / total if total else 0.0
    return rates


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, max(0, round(q * (len(sorted_values) - 1))))
    return sorted_values[index]


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


__all__ = ["build_report", "render_markdown"]
