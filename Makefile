# Developer shortcuts for FlyBrain Agent. See docs/DEVELOPMENT.md for details.

PYTHON       ?= python3
BACKEND_DIR  := backend
FRONTEND_DIR := frontend
VENV         := $(BACKEND_DIR)/.venv
VENV_PY      := $(VENV)/bin/python

.PHONY: help install install-backend install-frontend backend frontend \
        test test-backend typecheck-frontend lint smoke smoke-backend smoke-frontend smoke-data \
        smoke-circuit normalize normalize-fixture inspect extract clean

help:
	@echo "make install            install backend (.venv) and frontend (node_modules) dependencies"
	@echo "make backend            run FastAPI on http://127.0.0.1:8000"
	@echo "make frontend           run Vite dev server on http://127.0.0.1:5173"
	@echo "make test               backend unit tests + frontend typecheck"
	@echo "make smoke              backend /health smoke + frontend Playwright smoke"
	@echo "make lint               ruff check on backend"
	@echo "make normalize          raw MaleCNS v1.0 files (data/raw) -> data/processed (parquet + provenance)"
	@echo "make inspect            DATA.md §7 report for data/processed"
	@echo "make smoke-data         inspect the synthetic fixture (+ production data when present)"
	@echo "make smoke-circuit      fixture circuit extraction (+ technical MaleCNS extraction when data present)"
	@echo "make extract ARGS=...   run scripts/extract_circuit.py with ARGS"

install: install-backend install-frontend

install-backend:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -e "$(BACKEND_DIR)[dev]"

install-frontend:
	cd $(FRONTEND_DIR) && npm install

backend:
	cd $(BACKEND_DIR) && .venv/bin/python -m app

frontend:
	cd $(FRONTEND_DIR) && npm run dev

test: test-backend typecheck-frontend

test-backend:
	cd $(BACKEND_DIR) && .venv/bin/python -m pytest

typecheck-frontend:
	cd $(FRONTEND_DIR) && npm run typecheck

lint:
	cd $(BACKEND_DIR) && .venv/bin/ruff check .

smoke: smoke-backend smoke-data smoke-circuit smoke-frontend

smoke-backend:
	$(VENV_PY) scripts/smoke_test.py

smoke-frontend:
	cd $(FRONTEND_DIR) && npm run test:e2e

smoke-data:
	$(VENV_PY) scripts/inspect_dataset.py --fixture --keep-dangling
	$(VENV_PY) scripts/inspect_dataset.py --allow-missing

smoke-circuit:
	$(VENV_PY) scripts/smoke_circuit.py

extract:
	$(VENV_PY) scripts/extract_circuit.py $(ARGS)

normalize:
	$(VENV_PY) scripts/normalize_dataset.py --adapter malecns

normalize-fixture:
	$(VENV_PY) scripts/normalize_dataset.py --adapter fixture --out-dir data/processed/fixture

inspect:
	$(VENV_PY) scripts/inspect_dataset.py

clean:
	rm -rf $(BACKEND_DIR)/.pytest_cache $(BACKEND_DIR)/.ruff_cache \
	       $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/test-results $(FRONTEND_DIR)/playwright-report
	find $(BACKEND_DIR) -name __pycache__ -type d -prune -exec rm -rf {} +
