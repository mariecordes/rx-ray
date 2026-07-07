import pytest

from src.evals.critic_study import (
    CRITIC_STATUS_AXES,
    LabelSheetError,
    cohen_kappa,
    render_markdown,
    score_study,
)


def sheet_item(item, source="yes", answer="reflected", **overrides):
    base = {
        "item": item,
        "question_id": f"q{item:02d}",
        "claim_matches_source": source,
        "answer_reflects_claim": answer,
        "skip": False,
        "labeler_notes": "",
    }
    base.update(overrides)
    return base


def key_item(item, status="accurate", rationale=""):
    return {
        "item": item,
        "question_id": f"q{item:02d}",
        "critic_status": status,
        "critic_rationale": rationale,
    }


def test_status_axes_cover_all_five_tiers():
    assert set(CRITIC_STATUS_AXES) == {
        "accurate",
        "not_reflected",
        "contradicted",
        "misrepresented",
        "misrepresented_used",
    }


def test_kappa_perfect_agreement_is_one():
    pairs = [("a", "a"), ("b", "b"), ("a", "a"), ("b", "b")]
    assert cohen_kappa(pairs) == pytest.approx(1.0)


def test_kappa_chance_level_is_zero():
    # Rater B says "a"/"b" independently of rater A with the same marginals.
    pairs = [("a", "a"), ("a", "b"), ("b", "a"), ("b", "b")]
    assert cohen_kappa(pairs) == pytest.approx(0.0)


def test_kappa_degenerate_marginals_is_none():
    assert cohen_kappa([("a", "a"), ("a", "a")]) is None
    assert cohen_kappa([]) is None


def test_score_study_full_agreement():
    sheet = [
        sheet_item(1),
        sheet_item(2, source="no", answer="not_reflected"),
        sheet_item(3, answer="contradicted"),
    ]
    key = [
        key_item(1, "accurate"),
        key_item(2, "misrepresented"),
        key_item(3, "contradicted"),
    ]
    report = score_study(sheet, key)
    assert report["n_labeled"] == 3
    assert report["source_axis"]["agreement"] == pytest.approx(1.0)
    assert report["answer_axis"]["agreement"] == pytest.approx(1.0)
    assert report["flagged"]["precision"] == pytest.approx(1.0)
    assert report["flagged"]["recall"] == pytest.approx(1.0)
    assert report["disagreements"] == []


def test_score_study_critic_misses_human_flag():
    # Human says the claim misreads the source; critic said accurate.
    sheet = [sheet_item(1, source="no"), sheet_item(2)]
    key = [key_item(1, "accurate"), key_item(2, "accurate")]
    report = score_study(sheet, key)
    assert report["flagged"]["critic_flagged"] == 0
    assert report["flagged"]["human_flagged"] == 1
    assert report["flagged"]["precision"] is None  # no critic flags at all
    assert report["flagged"]["recall"] == pytest.approx(0.0)
    assert len(report["disagreements"]) == 1
    assert report["source_axis"]["confusion"]["matches"]["misreads"] == 1


def test_score_study_false_alarm_precision():
    # Critic flags both; human confirms only one.
    sheet = [
        sheet_item(1, answer="not_reflected"),
        sheet_item(2),
    ]
    key = [
        key_item(1, "not_reflected"),
        key_item(2, "not_reflected"),
    ]
    report = score_study(sheet, key)
    assert report["flagged"]["precision"] == pytest.approx(0.5)
    assert report["flagged"]["recall"] == pytest.approx(1.0)


def test_skip_and_unlabeled_handling():
    sheet = [
        sheet_item(1, skip=True),
        sheet_item(2, source="", answer=""),
        sheet_item(3),
    ]
    key = [key_item(1), key_item(2), key_item(3)]
    with pytest.raises(LabelSheetError, match="unlabeled"):
        score_study(sheet, key)
    report = score_study(sheet, key, allow_partial=True)
    assert report["n_labeled"] == 1
    assert report["n_skipped"] == 1
    assert report["n_unlabeled"] == 1


def test_invalid_labels_raise():
    sheet = [sheet_item(1, source="maybe")]
    key = [key_item(1)]
    with pytest.raises(LabelSheetError, match="claim_matches_source"):
        score_study(sheet, key)


def test_render_markdown_includes_kappa_and_confusion():
    sheet = [
        sheet_item(1),
        sheet_item(2, source="no", answer="not_reflected"),
    ]
    key = [key_item(1, "accurate"), key_item(2, "misrepresented")]
    markdown = render_markdown(
        score_study(sheet, key), sheet_name="sheet_test.yml"
    )
    assert "Cohen's κ" in markdown
    assert "Source-match confusion" in markdown
    assert "single annotator" in markdown
