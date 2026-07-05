# Evaluating rx-ray

rx-ray's thesis is that a symbolic layer (RxNorm terminology + retrieved FDA
label evidence + deterministic coverage checks) can constrain and audit an LLM
so it cannot overclaim. This document describes how that claim is **measured**
rather than asserted: a behavioral evaluation harness (D3a), a human labeling
study of the LLM critic (D3b), and a three-way mode comparison (D4).

Everything here is reproducible from the repo; commands are listed per
section. Raw run outputs land in `evals/runs/` (gitignored); the committed
headline results live in `evals/results/latest.{json,md}`.

---

## 1. The question set

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

## 2. The harness (D3a)

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

## 3. Headline results

_To be filled from `evals/results/latest.md` after the headline combined run
(`--repeats 3`) that closes D3a._

<!-- TODO(D3a close-out): headline table (questions passed, check pass rate,
verdict flips, latency), extraction P/R/F1 table, guardrail intervention
rates, per-category table. -->

### Three-mode progression (single-repeat development runs)

| Mode | Questions passing | Checks passing |
|---|---|---|
| symbolic | 28/42 | 86% |
| combined_extraction_only | 39/42 | 98% |
| combined | 39/42 | 98% |

The extraction-LLM layer recovers 11 questions over the symbolic floor
(intent phrasings like "can X *cause*…", role assignment for current
medications, condition extraction); the synthesis/critic layers add
answer-side guarantees rather than extraction fixes.

### Selected findings from development runs

The harness caught real defects during its own construction:

- **Pronoun resolves to a real drug** (deterministic mode): in *"Is it okay
  to take paracetamol while pregant?"*, the scanner captured "it" as a drug
  mention and resolved it to **itraconazole** — the same failure family as
  the B5 "CREAM" stray-node bug. (Tracked for a scanner stopword fix.)
- **LLM revision can regress state**: the revision layer fixed 11 questions
  but rewrote a correctly-extracted `pollen` allergy to `unspecified`
  (q18) — the neural layer giveth and taketh away, which is precisely why
  the deterministic layer audits it.
- **Resolver synonym gap**: "paracetamol" fails to resolve to acetaminophen
  even after LLM revision normalizes the rest of the question.

## 4. Critic accuracy study (D3b)

Since the D2e guardrail work, an LLM critic is the *only* source of the
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

### Results

_To be filled from `evals/critic_labels/sheet_2026-07-04.scoring.md` once
labeling is complete._

<!-- TODO(D3b): per-axis agreement + κ table, flagged precision/recall,
confusion matrices, 3–5 sentence error analysis from the disagreements. -->

## 5. Neural vs symbolic vs combined (D4)

_Planned._ The harness gains a `neural` mode (one neutral, un-sabotaged LLM
call — no retrieval, no whitelist, no validation) and a property table
comparing the three modes on: provenance rate, personal-advice /
definitive-language rate, trap handling (does the unconstrained model answer
a question about a drug that does not exist?), limitations per answer, and
safety-note presence. There is deliberately no single shared quality score —
neural-only has no citations *by construction*, and grading answer quality
with another unvalidated LLM judge would undercut section 4.

Showcase deliverable: `notebooks/06_neural_symbolic_combined.ipynb` with six
questions side by side across all three modes.

<!-- TODO(D4): comparison table + 2–3 headline contrast numbers. -->

## 6. Design principles (why the eval looks like this)

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
