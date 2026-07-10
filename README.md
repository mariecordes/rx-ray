# rx-ray

**Live app:** [https://rx-ray.vercel.app/](https://rx-ray.vercel.app/)

**A neuro-symbolic medication-evidence explorer — where a symbolic layer
grounds, constrains, and audits an LLM so it can summarize public drug
information without overclaiming.**

`rx-ray` is a personal AI research / portfolio project. It explores a pattern I
care about: instead of letting a language model answer medication questions
freely, a structured symbolic layer decides what evidence exists, the LLM may
only summarize and cite *that* evidence, and a deterministic audit reports what
the system could and couldn't support. The interesting part isn't the answer but the **provenance and the guardrails around it**.

It summarizes and visualizes public data only. It is an educational prototype
and does **not** provide medical advice.

---

## The idea

Medication questions are a good stress test for trustworthy AI: the stakes are
real, the public data is messy and incomplete, and a confident-sounding wrong
answer is worse than no answer. That makes it a natural place to ask whether the
**symbolic layer can keep the neural layer honest**.

`rx-ray`'s answer is a pipeline where every step is inspectable and the symbolic
side sets the boundaries for the neural side:

```text
user question
  -> deterministic query understanding   (structured, reviewable state)
  -> optional LLM refinement of that state
  -> RxNorm drug resolution + local concept network   (symbolic retrieval)
  -> OpenFDA label evidence, targeted by question intent
  -> deterministic coverage audit        (what was / wasn't supported)
  -> answer contract                      (topics to address, caveats to include)
  -> grounded LLM synthesis, citations restricted to a whitelist
  -> deterministic enforcement           (re-adds dropped caveats, drops uncited claims)
  -> LLM faithfulness critic             (audits each citation vs its source + the answer)
```

## What it does

The app has three entry points into the same evidence layer:

1. **Ask a Question** (primary experience): ask a natural-language medication
  question and get a grounded summary, plus a compact view of what the system
  understood, what evidence it used, how faithfully each cited source is
  reflected, and where it falls short. The full evidence packet is one click away.

Behind every answer, the evidence packet exposes:

- **Evidence Map**: an interactive D3 graph linking extracted question concepts
  to resolved medications, label sources, and label sections.
- **Supporting Evidence**: the underlying RxNorm drug network and the specific
  FDA label text, with source provenance for every claim.

2. **Compare**: a handful of curated questions run through three modes side by side: an unconstrained LLM call (neural only), the symbolic layer alone based on purely deterministic rules with no generation, and the full neuro-symbolic pipeline grounding and auditing the model. To avoid LLM cost and reduce page load, this page uses precomputed real pipeline outputs.

3. **Drug Dossier**: search a single medication and inspect its raw evidence
  directly — the RxNorm concept network and public FDA label sections — with no generated answer in between.


## How it works (technical)

**1. Query understanding (symbolic, with optional neural refinement).**
Deterministic rules extract a structured state from the question — primary drug,
other mentioned and current medications, allergies, conditions, patient context,
and intent. An LLM can optionally revise that state, but the structure stays
explicit and reviewable. If no API key is configured, the pipeline falls back to
deterministic extraction with an explicit warning.

**2. Symbolic retrieval.** Resolved medications are looked up in RxNorm
(RXCUIs, concept types, relationships) to build a local concept network. Public
FDA label text is retrieved from OpenFDA, targeted at the label sections that
match the question's intent (e.g. interactions, pregnancy/lactation,
contraindications, indications).

**3. Deterministic coverage audit.** Before any answer is written, a non-LLM
check compares every extracted detail against the retrieved evidence and labels
it `addressed`, `not_found_in_evidence`, `not_retrieved`, or `out_of_scope` - so
the system states out loud what it could and couldn't support, rather than
leaving that to the model's discretion.

**4. Answer contract.** The coverage report is compiled into an explicit contract
the answer must satisfy: which topics it *must address* (because evidence exists)
and which caveats it *must include*. Expectations are set symbolically before the
model writes anything, so compliance becomes a checklist the system can enforce
rather than hope for.

**5. Grounded synthesis with a citation whitelist.** The LLM writes the summary
against that contract, but it may only cite evidence drawn from a whitelist built
out of the retrieved label sections. Citations outside the whitelist are dropped,
and an answer that produces no valid citations (when evidence does exist) triggers
a bounded retry.

**6. Deterministic enforcement.** After synthesis, a non-LLM validation pass
checks the answer against the contract: it re-appends any required caveat the
model dropped, flags personal "safe / unsafe" framing, and relocates any claim
that lacks a citation out of the sources list and into the stated limitations.

**7. Faithfulness critic.** A second LLM pass audits each citation on its own,
comparing the claim against the exact label text it cites *and* against the final
answer. It scores, per source, whether the claim faithfully represents the
label and whether the answer reflects, omits, or contradicts it. Each source
carries that verdict as a badge, and a serious mismatch triggers a single bounded
regeneration. With no API key configured the critic is skipped and sources simply
carry no badge.

## The guardrail layer

This is the core of the project. Rather than trusting prompt instructions alone,
the safety properties are enforced in code:

- **Citation whitelist**: the model cannot cite evidence it wasn't given.
- **Bounded retry**: re-prompts once when evidence exists but the answer cited
  nothing valid.
- **Coverage audit**: a deterministic, "don't overclaim" check that treats
  *"I don't have evidence for that"* as a first-class output.
- **Answer contract**: coverage is compiled into must-address topics and
  must-include caveats before synthesis, turning "did the model behave" into an
  enforceable checklist.
- **Deterministic enforcement**: a non-LLM pass re-appends any dropped caveat,
  flags personal safe/unsafe framing, and moves uncited claims out of the sources
  and into the stated limitations.
- **Faithfulness critic**: a second LLM pass checks each citation against its
  real source text and the final answer, surfaces the verdict as a per-source
  badge, and triggers one bounded regeneration on a serious mismatch.
- **Careful prompting**: labels are described as *retrieved text mentioning*
  another drug, never as a confirmed clinical interaction; the system never
  declares a drug safe or unsafe.
- **Graceful degradation**: every LLM call is behind env config and falls back
  to deterministic behavior, so the app runs (and demos) without an API key.

## Evaluation

The guardrails are measured, not just asserted, in two complementary ways:

- **A repeatable evaluation harness**: 42 curated questions (including trap
  questions where the correct behavior is to *refuse*) with behavioral,
  structured expectations, run via `make eval` / `make eval-offline` across
  isolated pipeline modes (deterministic-only, extraction-LLM-only, full
  pipeline) so each layer's contribution is measurable.
- **One-off experiments**: designed studies against a frozen system state —
  most notably a blind human labeling study of the LLM faithfulness critic
  (the judge gets judged: flag precision 0.76, flag recall 0.96 vs. human
  labels, with a bucketed error analysis that produced concrete follow-up
  work).

**Headline results** (full pipeline, 42 questions × 3 repeats):

- **40/42** questions pass every behavioral check in every repeat
  (**99%** of 504 checks; 1 verdict flip; 0 errors) — both persistent
  failures are documented known gaps, kept in the set as quantified probes.
- **Abstention holds**: all 5 trap questions (fictional drug, false premise,
  leading yes/no, …) pass in every repeat; personal yes/no advice framing: 0%.
- Extraction: drugs F1 0.99 · conditions 1.00 · allergies 1.00.
- The deterministic layer visibly earns its keep: per run, the critic flagged
  17% of citations, 42% of answers were regenerated after a critic flag, and
  12% had a dropped caveat re-appended deterministically.
- **Each layer's contribution is measured, not assumed** — the same question
  set run per mode: symbolic-only **28/42** → + extraction LLM **39/42** →
  full pipeline **40/42**, with the full pipeline holding 99% of checks
  while also carrying the answer-side checks the cheaper modes can't run.

Methodology, results, and analysis: [docs/EVALUATION.md](docs/EVALUATION.md) ·
full report: [evals/results/latest.md](evals/results/latest.md).

For a hands-on version of that same ablation, the [Compare](https://rx-ray.vercel.app/compare) page runs curated questions through the isolated modes side by side, so you can see what each layer contributes on a specific example rather than just in the aggregate numbers.

## Tech stack

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS, D3 force layouts for
  the network and evidence-map visualizations.
- **Backend:** Python FastAPI, with optional OpenAI API integration for query
  refinement, grounded synthesis, and a second-pass faithfulness critic.
- **Data:** RxNorm Current Prescribable Content (April 2026 release, exported to
  parquet for fast local retrieval) and public drug labels via the OpenFDA
  drug-label API. OpenFDA lookups use live-with-cache behavior, storing raw
  responses under `data/cache/openfda_labels/`.
- **Deployment:** Railway for the FastAPI backend and Vercel for the Next.js
  frontend.
- **Code:** [github.com/mariecordes/rx-ray](https://github.com/mariecordes/rx-ray)

## Data sources

- **RxNorm Current Prescribable Content** (April 2026 release) — medication
  terminology, RXCUIs, concept types, and relationships. The two runtime tables
  (`rxnconso`, `rxnrel`) are committed under
  `data/01_raw/rxnorm_prescribable/<YYYYMMDD>/` so a fresh clone runs with no
  bulk data download; the app always loads the latest dated release folder. This
  is NLM's
  [license-free subset](https://www.nlm.nih.gov/research/umls/rxnorm/docs/prescribe.html)
  of currently-prescribable US drugs (plus many OTC), built from the `RXNORM`
  and FDA Structured Product Label (`MTHSPL`) sources. It's a deliberate fit
  here: it needs no UMLS license, so it can ship in a public repo, and it's
  drawn from the same FDA SPL data as the OpenFDA labels `rx-ray` already uses — so
  the terminology and the label evidence line up. (The full RxNorm release would
  add licensing friction and historical/non-US noise without closing the real
  gaps; richer symbolic data would come from RxClass/ATC classes or a dedicated
  interaction source instead.)
- **OpenFDA drug labels** — public FDA label text via the [OpenFDA API](https://open.fda.gov/apis/drug/label/).
- **OpenAI API** — query-state refinement, grounded answer synthesis, and a
  second-pass faithfulness critic that audits the answer against its own cited
  sources. Never the sole source of factual claims; it summarizes retrieved
  evidence under the citation whitelist.

## Repository layout

```text
apps/api/                  FastAPI app and request models
apps/frontend/             Next.js frontend
conf/base/prompts.yml      Prompt library for LLM-assisted steps
conf/base/parameters.yml   Tunable pipeline parameters
src/dossier/               Dossier builder, RxNorm store, OpenFDA store
src/query_understanding/   State extraction, LLM revision, RxNorm resolution
src/query_answer/          Coverage audit, answer contract, synthesis, enforcement, critic
scripts/                   Utility scripts, including dossier JSON export
tests/                     Backend tests

# for deployment in Railway only 
Dockerfile                 Backend container image for the live Railway service
railway.json               Railway service config
```

## API endpoints

- `GET /health` — backend status.
- `POST /query-understanding` — extracts state, resolves drug mentions, returns a
  primary dossier when possible.
- `POST /query-answer` — runs understanding, retrieves evidence, and generates a
  grounded summary with a coverage report, answer-contract enforcement, and
  per-source faithfulness critique.
- `POST /dossier` — builds a dossier for one direct drug search.
- `POST /label-evidence` — fetches OpenFDA label evidence for a selected RxNorm
  concept.

## Running locally

A fresh clone runs end-to-end with no extra data wrangling — the minimal RxNorm
runtime data is committed, and OpenFDA labels are fetched live (no API key
needed). Requires Python 3.11+ and Node 20.9+.

```bash
make setup          # install backend + frontend deps, create .env, verify data
make api            # backend on http://localhost:8000
make web            # frontend on http://localhost:3000 (second terminal)
```

`make setup` is a convenience wrapper; you can also run the steps by hand (create
a venv, `pip install -e ".[dev,llm]"`, `cd apps/frontend && npm install`, copy
`.env.example` to `.env`). The LLM features are optional — without an OpenAI key
the pipeline falls back to deterministic behavior. Run `make test` / `make check`
for tests and linting.

Use `http://localhost:3000` for local frontend work. If you intentionally open
the dev server through a LAN host, set `NEXT_ALLOWED_DEV_ORIGINS` in
`apps/frontend/.env.local` to that host and restart `npm run dev`.

## Safety note

`rx-ray` is an educational prototype. It can help inspect public medication
terminology and label text, but it must not be used to make medical decisions.
For medical questions, consult a qualified clinician or pharmacist.
