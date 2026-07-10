# Evaluating rx-ray

rx-ray's thesis is that a symbolic layer (RxNorm terminology + retrieved FDA
label evidence + deterministic coverage checks) can constrain and audit an LLM
so it cannot overclaim. This document describes how that claim is **measured**
rather than asserted: (1.) a behavioral evaluation harness (roadmap item D3a), (2.) a human labeling study of the LLM critic (roadmap item D3b), and (3.) a three-way mode comparison (roadmap item D4).

Everything here is reproducible from the repo; commands are listed per
section. Raw run outputs land in `evals/runs/` (gitignored); the committed
headline results live in `evals/results/latest.{json,md}`.

---

## The question set

[`evals/questions.yml`](../evals/questions.yml) — 42 curated questions across
12 categories:

| Category | n | What it probes |
|---|---|---|
| indication | 4 | basic single-drug retrieval + coverage |
| side_effect | 4 | incl. phrasings that miss deterministic intent patterns ("can X cause…") |
| interaction (2-drug) | 5 | incl. documented regression queries from the guardrail work (D2b–D2e) |
| interaction (3-drug) | 2 | secondary-evidence budget under load |
| allergy | 4 | allergen role assignment, non-medication allergens |
| pregnancy_lactation | 3 | patient-context targeting |
| patient_context | 2 | age/condition qualifiers |
| formulation | 3 | specific-concept priority + ingredient fallback (B2 test set) |
| **trap** | 5 | fictional drug, false premise, out-of-scope, leading yes/no, no-product-label concept |
| **expected_gap** | 4 | answerable-looking questions whose labels lack the asked-about link — the honest "no evidence" path |
| complex | 3 | all state fields at once, third-person phrasing, multi-intent |
| typo | 3 | aspirational robustness probes (misspelled drugs/context) |

Design rules (documented in the file header):

- **Expectations are behavioral and structured** — what resolved, what the
  coverage report said, which guardrails fired — never golden answer text, so
  checks are robust to LLM nondeterminism.
- **Expectation terms use the extractor's normalized vocabulary** (e.g.
  `pregnancy`, `child`, `senior`), calibrated via offline runs.
- **Coverage assertions follow a documented policy**: every interaction
  question asserts intent coverage; strict `[addressed]` where the interaction
  is prominently label-documented, an escape hatch only where label coverage
  is genuinely uncertain.
- **Traps make abstention a first-class metric**: the system passes by
  *refusing* correctly (fictional drug must not resolve; the gap must be
  named in the limitations).
- **Typo questions encode desired behavior, not current behavior** — their
  failures quantify a known robustness gap rather than regressions.

## 1. The harness

`src/evals/` consumes the pipeline's existing structured output
(`QueryAnswerResponse`: extracted state, resolved concepts, coverage report,
answer contract, validation findings, critique). **No production code paths
are modified for evaluation.**

### Run modes

| Mode | LLM calls / question | What it isolates |
|---|---|---|
| `symbolic` | 0 (keyless, deterministic) | the symbolic floor: extraction, resolution, retrieval, coverage |
| `combined_extraction_only` | 1 (extraction revision) | what LLM state-revision adds on top of the symbolic floor |
| `combined` | 3+ (extraction + synthesis + critic, bounded retry/regeneration) | the full production pipeline incl. answer-side guardrails |
| `neural` | 1 (planned, D4) | the unconstrained LLM, no retrieval or guardrails |

```bash
make eval-offline                                  # symbolic, free
.venv/bin/python scripts/run_eval.py --mode combined_extraction_only
make eval                                          # combined + refresh evals/results/latest.*
# useful flags: --repeats 3  --only q10 q28  --category trap complex
```

### Metrics

- **Extraction & resolution**: per-field precision / recall / F1 (drugs,
  current medications, allergies, conditions, patient context, intents),
  with drugs scored per resolved mention.
- **Match quality per field**: `exact` / `extra` / `partial` / `none`, with
  explicit missing/unexpected term lists. Pass/fail checks gate on **recall**
  (expectations are minimum requirements); extras never fail a question but
  are surfaced in an aggregate table and a per-question 🟢🔵🟡🔴 matrix for
  at-a-glance failure localization.
- **Coverage assertions**: normalized label lookup + status membership test
  against the deterministic coverage report — no LLM, no fuzzy scoring.
- **Abstention**: trap terms must not resolve; expected-gap questions must
  carry the gap in their limitations.
- **Guardrail intervention rates** (combined mode): enforced caveats,
  relocated uncited bullets, yes/no-framing catches, must-mention misses,
  critic flag rate, regeneration rate. These measure how often the
  deterministic layer had to correct the neural layer — the quantity the
  architecture exists to control, not an error rate of the system.
- **Stability**: `--repeats N` reports verdict flips and worst-of-repeats
  match quality; LLM nondeterminism is reported, not averaged away.

### Headline results (combined mode, 42 questions × 3 repeats, July 2026)

Full report: [`evals/results/latest.md`](../evals/results/latest.md)
(committed output of `make eval`).

| metric | value |
|---|---|
| Questions passing all behavioral checks in every repeat | **40/42** |
| Behavioral checks passed | **499/504 (99%)** |
| Verdict flips across repeats | 1 |
| Abstention: trap questions passing (every repeat) | **5/5** |
| Yes/no personal-advice framing | **0%** |
| Errors | 0 |

Guardrail intervention rates (share of answered runs): critic flagged 17%
of citations, 42% of answers regenerated once after a critic flag, 12% had
a required caveat re-appended deterministically, 26% had an uncited bullet
relocated to limitations. Extraction (macro): drugs F1 0.99, conditions
1.00, allergies 1.00, intents recall 1.00.

Both persistent failures are documented known gaps, not surprises: **q41**
("paracetamol" doesn't resolve — resolver synonym gap) and **q18** (the
LLM-revision layer intermittently rewrites a correctly-extracted `pollen`
allergy to `unspecified`; this is also the single verdict flip —
repeat-stability surfacing that the regression is nondeterministic).

### Three-mode progression

All three modes measured against the same system state as the headline run;
committed reports linked per row.

| Mode | Questions passing | Checks passing | Repeats | Report |
|---|---|---|---|---|
| symbolic | 28/42 | 86% | 1 (deterministic) | [`latest_symbolic.md`](../evals/results/latest_symbolic.md) |
| combined_extraction_only | 39/42 | 99% | 3 (2 verdict flips) | [`latest_combined_extraction_only.md`](../evals/results/latest_combined_extraction_only.md) |
| combined | **40/42** | 99% | 3 (1 verdict flip) | [`latest.md`](../evals/results/latest.md) |

The extraction-LLM layer recovers 11 questions over the symbolic floor
(intent phrasings like "can X *cause*…", role assignment for current
medications, condition extraction). The full pipeline's checks-passing rate
holds at 99% even though it carries the answer-side checks the cheaper
modes can't run at all (limitations wording, guardrail floors); its +1
question over extraction-only is within run-to-run nondeterminism (q29
flickers in extraction mode), so the honest reading is: the neural
extraction layer buys extraction quality, the synthesis/critic layers buy
audited, cited answers at no loss of behavioral compliance.

### Selected findings from development runs

The harness caught real defects during its own construction:

- **Pronoun resolves to a real drug** (deterministic mode): in *"Is it okay
  to take paracetamol while pregant?"*, the scanner captured "it" as a drug
  mention and resolved it to **itraconazole** - the same failure family as
  the B5 "CREAM" stray-node bug. (Tracked for a scanner stopword fix.)
- **LLM revision can regress state**: the revision layer fixed 11 questions
  but rewrote a correctly-extracted `pollen` allergy to `unspecified`
  (q18) - the neural layer giveth and taketh away, which is precisely why
  the deterministic layer audits it.
- **Resolver synonym gap**: "paracetamol" fails to resolve to acetaminophen
  even after LLM revision normalizes the rest of the question.

## 2. Critic accuracy study

Since the roadmap package D2e guardrail work, an LLM critic is the *only* source of the
per-citation support badges shown in the UI — an LLM judging an LLM. This
study measures the judge.

**Design** (see [`evals/LABELING_GUIDE.md`](../evals/LABELING_GUIDE.md) for
the full labeling protocol):

- Citations from a full combined run are exported to a **blind** label sheet
  (`scripts/export_critic_sample.py`): all critic-flagged citations plus
  accurate ones sampled to target, order shuffled, critic verdicts sealed in
  a separate key file.
- A human labels two axes per citation, matching the two axes the UI derives
  from the critic's 5-tier status:

  | critic status | source-match axis | answer-use axis |
  |---|---|---|
  | `accurate` | matches | reflected |
  | `not_reflected` | matches | not_reflected |
  | `contradicted` | matches | contradicted |
  | `misrepresented` | misreads | not_reflected |
  | `misrepresented_used` | misreads | reflected |

- `scripts/score_critic_labels.py` reports per-axis raw agreement, Cohen's κ
  (chance-corrected — necessary because the label distribution is skewed),
  precision/recall of "flagged" treating the human labels as ground truth,
  confusion matrices, and a disagreements list for error analysis.

**Stated limitations**: single annotator, so κ measures human–critic
agreement, not inter-annotator reliability; the sheet oversamples flagged
citations by design, so sheet composition is not the population flag rate.

### Results (one-off experiment, July 2026)

This study was run once, as a designed experiment against a frozen system
state — the pipeline as of the 2026-07-04 combined run over the 42-question
set — and is recorded here rather than continuously re-run. Sheet:
`evals/critic_labels/sheet_2026-07-04.yml` (75 citations = **all 58** the
critic flagged in that run + 17 sampled `accurate`), labeled blind, scored
with `scripts/score_critic_labels.py`; full output in
`sheet_2026-07-04.scoring.{md,json}`.

| metric | value |
|---|---|
| Source-match axis: raw agreement / Cohen's κ | 0.75 / **0.49** |
| Answer-use axis: raw agreement / Cohen's κ | 0.71 / **0.45** |
| "Flagged" precision (critic flag confirmed by human) | **0.76** (44/58) |
| "Flagged" recall (human flag caught by critic) | **0.96** (44/46) |

**Analysis.** The critic is a strong *flagger* and a moderate *diagnoser*:
it almost never misses a problem the human sees (2 misses in 46), and three
quarters of its flags are confirmed — but agreement on *what exactly* is
wrong is only moderate (κ ≈ 0.45–0.49). The 36 fine-grained disagreements
bucket cleanly:

1. **Paraphrase-blindness — 20/36.** The critic says the response doesn't
   reflect a claim when it does, in hedged or paraphrased form. The labeling
   protocol explicitly credits hedged conveyance; the critic prompt contains
   no such instruction. This is the dominant error and also a driver of
   unnecessary regenerations.
2. **Over-called "misreads" — 9/36.** The critic judges each citation in
   isolation, so a claim legitimately synthesized from multiple sources
   looks "broader than the source" against any single one (documented
   labeler note on item 26). A designed-in blind spot of the per-citation
   taxonomy, shared by this study's own labeling protocol.
3. **Under-called "misreads" — 10/36.** The critic credits a source the
   human judged misread; in 8 of the 10 the item was still flagged via the
   answer-use axis, so only 2 problems escaped flagging entirely.

**Caveats.** Single annotator; the recall estimate rests on only 17
critic-`accurate` items (the sheet oversamples flags by design), so 0.96 is
the low-confidence number; sheet composition ≠ population flag rate (26% of
citations in the underlying run).

**Derived next steps** (reference roadmap for further info):
  1. **D2h — joint multi-citation judgment**: give the critic each bullet with *all* its cited texts plus an explicit hedged-counts-as-reflected rule — directly targets buckets 1 and 2 (≈80% of disagreements) and folds in D2g. 
  2. **C5 — retrieval expansion**, from the review finding that answers narrated truncated evidence instead of obtaining fuller text. 
  3. Already landed during the study: synthesis-prompt rules moving evidence-scope statements to limitations and banning retrieval-mechanics narration. 
  4. The product conclusion: flag-level badges are trustworthy enough to display; fine-grained five-tier wording is not — consistent with the earlier D2f decision to render two coarse axes instead of the raw tier.

## 3. Neural vs symbolic vs combined

The harness gains a `neural` mode (one neutral, un-sabotaged LLM call - no retrieval, no whitelist, no validation) and a property table comparing the three modes on: provenance rate, personal-advice / definitive-language rate, trap handling (does the unconstrained model answer a question about a drug that does not exist?), limitations per answer, and safety-note presence. There is deliberately no single shared quality score: neural-only has no citations *by construction*, and grading answer quality with another unvalidated LLM judge would undercut section 4.

Showcase deliverable: a **[`/compare` page](https://rx-ray.vercel.app/compare) in the app** rendering ~8 curated questions (traps included) across all three modes side by side, from precomputed fixtures generated by `scripts/build_compare_fixtures.py` — so the demonstration runs on the live deployment with no per-visitor LLM cost, defaulting to the fictional-drug trap. Every neural output is displayed behind an explicit "unconstrained model — shown to demonstrate what rx-ray prevents" framing, and each column reuses the Ask page's own components (query understanding, coverage audit, evidence-based answer, sources, caveats) so the comparison is visually legible as the same pipeline, not a lookalike.

A static comparison table with 2–3 headline contrast numbers was planned but dropped: the interactive page already lets a reader inspect the difference directly on any of the 8 questions, which does more for intuition than a handful of aggregate numbers would.

## Design principles (why the eval looks like this)

- **Behavioral expectations over golden text**: assertions on structured
  facts survive model swaps and nondeterminism; snapshot text does not.
- **Recall-gated checks, visibility for the rest**: expectations are minimum
  requirements; over-extraction is surfaced (match-quality tiers) rather
  than punished, because the extractor legitimately adds intents beyond the
  asked-about ones.
- **The judge gets judged before it gets trusted**: no LLM-graded quality
  metrics anywhere in the harness until the critic itself has measured
  agreement with a human (section 4) — the same rule will apply to any
  future hallucination grader for D4.
- **Failures are kept when they're informative**: typo and probe questions
  that fail by design stay in the set as quantified gaps, not deleted noise.
