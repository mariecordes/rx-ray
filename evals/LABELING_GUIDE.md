# Critic accuracy study — labeling guide (D3b)

## What you're doing and why

Since D2e, the LLM critic is the **only** source of the per-citation support
badges shown in the UI. This study measures the critic itself: you label a
sample of citations by hand, blind to the critic's verdicts, and a scoring
script then reports human–critic agreement (Cohen's κ), plus precision/recall
of the critic's "flagged" decisions treating your labels as ground truth.

**Budget: ~1–2 hours for ~60–80 items.** Work in one or two sittings; note in
the sheet if you take a long break mid-way (drift is worth knowing about).

## The blind protocol (important)

- Label only from `sheet_*.yml`. It contains **no critic output**.
- The critic's verdicts live in the matching `sheet_*.key.yml`. **Do not open
  it until you're done labeling.** Opening it first invalidates the study.
- Don't re-run the app or look up the answer in the UI while labeling — the UI
  shows the critic's badges.
- **Ignore base rates.** The sheet oversamples critic-flagged citations by
  design, and the sheet header discloses the flagged/accurate split. Do not
  let that anchor you: a mostly-flagged sheet does *not* mean most items
  deserve negative labels — measuring how often the critic's flags are wrong
  is the point of the study. Judge every item purely on its own claim,
  cited text, and response.

## What each item contains

```yaml
- item: 12
  question_id: q11_interaction_sertraline_ibuprofen
  question: the user's question
  response: the final answer paragraph shown to the user
  claim: one generated bullet's text
  cited_source: {source_id: ..., section: drug_interactions}
  cited_text: the actual label-section text the model was shown for this citation
  # ── your labels ──
  claim_matches_source: ""      # yes | no
  answer_reflects_claim: ""     # reflected | not_reflected | contradicted
  skip: false                   # true only for broken items (see edge cases)
  labeler_notes: ""
```

The same claim can appear in multiple items (one per citation) — judge each
citation independently against **its own** `cited_text`.

## Axis 1 — `claim_matches_source`

*Does the claim faithfully reflect what the cited text actually says?*

- **yes** — everything the claim asserts is stated in, or is a fair careful
  summary of, the `cited_text`. Softening is fine (label says "may cause severe
  bleeding", claim says "the label warns about bleeding" → **yes**).
- **no** — the claim asserts something the cited text does not say, overstates
  it, drops a qualifier that changes the meaning, or attributes to this source
  something that presumably came from elsewhere.

Decision rules:
- Judge ONLY against `cited_text` — not against your own medical knowledge, and
  not against other sources in the sheet. A medically-true claim that this
  particular cited text doesn't support is a **no**.
- Generalization direction matters: claim narrower than source → **yes**;
  claim broader/stronger than source → **no**.
- A claim of absence ("the label does not list X") is **yes** only if X indeed
  does not appear in the `cited_text`.

## Axis 2 — `answer_reflects_claim`

*Does the final `response` paragraph correctly use this claim?*

- **reflected** — the substance of the claim is present in the response
  (paraphrase is fine; it doesn't need to quote the bullet).
- **not_reflected** — the claim's substance is absent from the response. The
  bullet exists, but the paragraph the user actually reads never conveys it.
- **contradicted** — the response says something that actively conflicts with
  the claim.

Decision rules:
- Judge the claim vs the `response` text only (limitations are shown for
  context but reflection in `response` is what counts).
- Judge Axis 2 against the claim **as written**, even if you gave Axis 1 a
  "no" — the two axes are independent.
- A response that conveys a *weaker hedged version* of the claim is still
  **reflected**; only actual conflict is **contradicted**.

## Edge cases

- **Empty `cited_text`** → `skip: true`, note "empty cited_text". (That's a
  pipeline bug worth knowing about, not a labeling judgment.)
- **Claim is really two claims** and the cited text supports only one → Axis 1
  is **no** (the claim as a whole overstates the source); note it.
- **Genuinely torn after ~60 seconds** → pick your best answer and write the
  tension into `labeler_notes`. Do not leave labels empty; the notes become
  the error-analysis material.
- **You recognize the item from development** (the regression queries are in
  the set) → label it anyway, note "familiar query".

## After labeling

Run the scorer against your labeled sheet:

```bash
.venv/bin/python scripts/score_critic_labels.py \
    --sheet evals/critic_labels/sheet_2026-07-04.yml
```

It maps the critic's 5-tier status onto these same two axes (the same
derivation the frontend badges use), then reports per-axis agreement,
Cohen's κ, precision/recall of "flagged", confusion matrices, and a
disagreements list for error analysis, written to
`sheet_<date>.scoring.{md,json}` next to the sheet. If you stopped partway,
add `--allow-partial`.

Stated limitation (goes into the report verbatim): single annotator — κ here
measures human–critic agreement, not inter-annotator reliability.
