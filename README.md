# rx-ray

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
  -> grounded LLM synthesis, citations restricted to a whitelist
  -> deterministic coverage audit        (what was / wasn't supported)
```

## What it does

The app has two entry points into the same evidence layer:

1. **Ask a Question** (primary experience): ask a natural-language medication
  question and get a grounded summary, plus a compact view of what the system
  understood, what evidence it used, and where it falls short. The full evidence
  packet is one click away.

Behind every answer, the evidence packet exposes:

- **Evidence Map**: an interactive D3 graph linking extracted question concepts
  to resolved medications, label sources, and label sections.
- **Supporting Evidence**: the underlying RxNorm drug network and the specific
  FDA label text, with source provenance for every claim.


2. **Drug Dossier**: search a single medication and inspect its raw evidence
  directly — the RxNorm concept network and public FDA label sections — with no
  generated answer in between.


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

**3. Grounded synthesis with a citation whitelist.** The LLM writes the summary,
but it may only cite evidence drawn from a whitelist built out of the retrieved
label sections. Citations outside the whitelist are dropped, and an answer that
produces no valid citations (when evidence does exist) triggers a bounded retry.

**4. Deterministic coverage audit.** A non-LLM check compares every extracted
detail against the evidence and labels it `addressed`, `not_found_in_evidence`,
`not_retrieved`, or `out_of_scope`. Deterministic limitations are appended when
important state is not covered — so the system states out loud what it could not
support, rather than leaving that to the model's discretion.

## The guardrail layer

This is the core of the project. Rather than trusting prompt instructions alone,
the safety properties are enforced in code:

- **Citation whitelist**: the model cannot cite evidence it wasn't given.
- **Bounded retry**: re-prompts once when evidence exists but the answer cited
  nothing valid.
- **Coverage audit**: a deterministic, "don't overclaim" check that treats
  *"I don't have evidence for that"* as a first-class output.
- **Careful prompting**: labels are described as *retrieved text mentioning*
  another drug, never as a confirmed clinical interaction; the system never
  declares a drug safe or unsafe.
- **Graceful degradation**: every LLM call is behind env config and falls back
  to deterministic behavior, so the app runs (and demos) without an API key.

## Tech stack

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS, D3 force layouts for
  the network and evidence-map visualizations.
- **Backend:** Python FastAPI, with optional OpenAI API integration for query
  refinement and grounded synthesis.
- **Data:** RxNorm Current Prescribable Content (June 2026 release, exported to
  parquet for fast local retrieval) and public drug labels via the OpenFDA
  drug-label API. OpenFDA lookups use live-with-cache behavior, storing raw
  responses under `data/cache/openfda_labels/`.

## Data sources

- **RxNorm Current Prescribable Content** (June 2026 monthly release) —
  medication terminology, RXCUIs, concept types, and relationships, exported to
  local parquet in `data/01_raw/`. This is NLM's
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
- **OpenAI API** — query-state refinement and grounded answer
  synthesis. Never the sole source of factual claims; it summarizes retrieved
  evidence under the citation whitelist.

## Repository layout

```text
apps/api/                  FastAPI app and request models
apps/frontend/             Next.js frontend
conf/base/prompts.yml      Prompt library for LLM-assisted steps
conf/base/parameters.yml   Tunable pipeline parameters
src/dossier/               Dossier builder, RxNorm store, OpenFDA store
src/query_understanding/   State extraction, LLM revision, RxNorm resolution
src/query_answer/          Grounded synthesis, citation whitelist, coverage audit
scripts/                   Utility scripts, including dossier JSON export
tests/                     Backend tests
```

## API endpoints

- `GET /health` — backend status.
- `POST /query-understanding` — extracts state, resolves drug mentions, returns a
  primary dossier when possible.
- `POST /query-answer` — runs understanding, retrieves evidence, and generates a
  grounded summary with a coverage report.
- `POST /dossier` — builds a dossier for one direct drug search.
- `POST /label-evidence` — fetches OpenFDA label evidence for a selected RxNorm
  concept.

## Running locally

> A full setup / bootstrap guide is in progress and will be expanded here.

In short: a Python backend (`pip install -e ".[dev,llm]"`, run with `uvicorn`)
and a Next.js frontend (`npm install && npm run dev`). Copy `.env.example` to
`.env` for configuration; the LLM features are optional and the app runs
deterministically without an API key.

## Safety note

`rx-ray` is an educational prototype. It can help inspect public medication
terminology and label text, but it must not be used to make medical decisions.
For medical questions, consult a qualified clinician or pharmacist.
