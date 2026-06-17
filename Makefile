# rx-ray developer commands.
# A fresh clone can get running with:  make setup  →  make api  (+ make web)

PYTHON ?= python3
VENV   := .venv
BIN    := $(VENV)/bin

.PHONY: setup setup-backend setup-frontend env verify-data api web test lint check

## setup: install backend + frontend deps, create .env, verify runtime data
setup: setup-backend setup-frontend env verify-data
	@echo ""
	@echo "✅ Setup complete. Start the app in two terminals:"
	@echo "   make api   # backend on http://localhost:8000"
	@echo "   make web   # frontend on http://localhost:3000"

setup-backend:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -e ".[dev,llm]"

setup-frontend:
	cd apps/frontend && npm install

## env: create .env from the example if it does not exist yet
env:
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

## verify-data: confirm the committed RxNorm runtime parquets are present
verify-data:
	@$(BIN)/python -c "from src.dossier.rxnorm_store import default_rxnorm_paths; c, r = default_rxnorm_paths(); assert c.exists() and r.exists(), 'Missing RxNorm parquet data'; print(f'RxNorm runtime data OK: {c.parent}')"

## api: run the FastAPI backend with reload
api:
	$(BIN)/uvicorn apps.api.main:app --reload --port 8000

## web: run the Next.js frontend dev server
web:
	cd apps/frontend && npm run dev

## test: run the backend test suite
test:
	$(BIN)/python -m pytest -q

## lint: ruff (backend) + typecheck/eslint (frontend)
lint:
	$(BIN)/ruff check apps/api/main.py src/dossier src/query_understanding src/query_answer tests
	cd apps/frontend && npm run typecheck && npm run lint

## check: lint + tests
check: lint test
