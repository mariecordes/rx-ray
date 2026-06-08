# rx-ray

rx-ray is a neuro-symbolic medication information prototype. It combines
structured public medication data, local symbolic graph retrieval, FDA label
evidence, and LLM-assisted query understanding into an interactive educational
drug explorer.

This is a personal data-science portfolio project. It summarizes and visualizes
public data, but it does not provide medical advice.

## What It Does

The current demo has two entry points on one page:

- **Ask a Question**: enter a natural-language medication question. The app
  extracts an inspectable state, such as primary drug, mentioned drugs, current
  medications, allergies, conditions, patient details, and intent.
- **Drug Explorer**: search directly for one medication and inspect its
  RxNorm network and public FDA label evidence.

For a resolved primary medication, rx-ray builds a request-time dossier:

```text
user query
  -> deterministic query extraction
  -> optional LLM revision of extracted state
  -> RxNorm drug mention resolution
  -> primary drug dossier
  -> RxNorm local relationship network
  -> OpenFDA label evidence, live with local cache
```

## Current Features

- Natural-language query understanding with deterministic rules and optional
  OpenAI revision.
- Inspectable symbolic state for the user question.
- RxNorm-backed drug resolution and local relationship retrieval from parquet
  files.
- Interactive force-directed **Drug Network** for the resolved medication.
- Public FDA **Drug Labels** section with warnings, indications, interactions,
  pregnancy/lactation, population-specific text, and source provenance.
- Graph-linked label highlighting: selecting a graph node can look up related
  label evidence and highlight or add matching sources.
- FastAPI backend with Next.js/React/TypeScript/Tailwind frontend.

## Data Sources

- **RxNorm**: medication terminology, RXCUIs, concept types, and relationships.
  The app currently reads local parquet exports from `data/01_raw/`.
- **OpenFDA drug labels**: public FDA label text retrieved through the OpenFDA
  drug label API.
- **OpenAI API, optional**: used only for query-extraction revision in the
  current milestone, not for answer synthesis.

OpenFDA label lookup uses live-with-cache behavior by default. If a label is not
already cached, the backend queries OpenFDA and stores the raw response under:

```text
data/cache/openfda_labels/
```

## Repository Layout

```text
apps/api/                  FastAPI app and request models
apps/frontend/             Next.js frontend
conf/base/prompts.yml      Prompt library for LLM-assisted extraction
src/dossier/               Drug dossier builder, RxNorm store, OpenFDA store
src/query_understanding/   State extraction, LLM revision, RxNorm resolution
notebooks/                 Early exploration and RxNorm KG prototyping
scripts/                   Utility scripts, including dossier JSON export
tests/                     Backend tests
```

## Setup

Create and activate a Python environment, then install the project:

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev,llm]"
```

Install frontend dependencies:

```bash
cd apps/frontend
npm install
```

Create a local `.env` from the example:

```bash
cp .env.example .env
```

Important environment variables:

```bash
# OpenFDA
OPENFDA_BASE_URL="https://api.fda.gov/drug/label.json"

# Optional query-extraction LLM revision
QUERY_EXTRACTION_OPENAI_API_KEY=...
QUERY_EXTRACTION_OPENAI_MODEL=...
```

The old generic `OPENAI_API_KEY` / `OPENAI_MODEL` names are intentionally not
used for query understanding, so later answer-synthesis models can have
separate configuration.

## Run Locally

Start the backend:

```bash
.venv/bin/uvicorn apps.api.main:app --reload --port 8000
```

Start the frontend in a second terminal:

```bash
cd apps/frontend
npm run dev
```

The frontend proxies API requests to `BACKEND_URL`, defaulting to:

```text
http://localhost:8000
```

Open the frontend at the URL printed by Next.js, usually:

```text
http://localhost:3000
```

If you change `.env`, restart the backend.

## API Endpoints

- `GET /health`: backend status.
- `POST /query-understanding`: extracts state from a natural-language query,
  resolves drug mentions, and returns a primary dossier when possible.
- `POST /dossier`: builds a dossier for one direct drug search.
- `POST /label-evidence`: fetches OpenFDA label evidence for a selected RxNorm
  concept.

## Build A Dossier From The CLI

Build an offline dossier:

```bash
.venv/bin/python scripts/build_dossier.py aspirin --offline
```

Build and write JSON:

```bash
.venv/bin/python scripts/build_dossier.py aspirin \
  --output data/04_dossiers/aspirin.json
```

Useful options:

```bash
--depth 1
--max-edges 75
--openfda-limit 5
--no-openfda
```

Omit `--offline` to allow live OpenFDA lookup and caching.

## Tests And Checks

Backend tests:

```bash
.venv/bin/python -m pytest
```

Python lint for the active backend modules:

```bash
.venv/bin/ruff check apps/api/main.py src/dossier src/query_understanding tests
```

Frontend checks:

```bash
cd apps/frontend
npm run typecheck
./node_modules/.bin/eslint src
```

Note: on this local macOS setup, `next build` may fail because the installed
Next/SWC binary has a code-signature issue. TypeScript and ESLint checks are
currently the reliable frontend validation path.

## Project Direction

The current milestone is the evidence explorer and query-understanding layer.
Planned next steps include:

- grounded LLM answer synthesis using the extracted state and retrieved
  evidence,
- clearer reasoning/execution traces for query processing,
- richer multi-drug workflows, especially for interaction-style questions,
- evaluation views for comparing neural-only, symbolic-only, and combined
  responses.

## Safety Note

rx-ray is an educational prototype. It can help inspect public medication
terminology and label text, but it should not be used to make medical decisions.
For medical questions, consult a qualified clinician or pharmacist.
