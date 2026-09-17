# Developer shortcuts for FlyBrain Agent. See docs/DEVELOPMENT.md for details.

PYTHON       ?= python3
BACKEND_DIR  := backend
FRONTEND_DIR := frontend
VENV         := $(BACKEND_DIR)/.venv
VENV_PY      := $(VENV)/bin/python

.PHONY: help install install-backend install-frontend backend frontend \
        test test-backend typecheck-frontend lint smoke smoke-backend smoke-frontend smoke-data \
        smoke-circuit smoke-simulation smoke-escape smoke-web smoke-embodiment smoke-threat-lab smoke-intervention normalize normalize-fixture inspect \
        extract simulate build-escape-config demo demo-check demo-smoke screenshots build-frontend clean

help:
	@echo "make demo               ONE-COMMAND DEMO: validate, start backend + frontend, print URLs (Ctrl+C stops)"
	@echo "make demo-check         validate the installation and the escape_v1 artifact only"
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
	@echo "make smoke-simulation   fixture propagation demo (+ technical MaleCNS simulation when circuit present)"
	@echo "make simulate ARGS=...  run scripts/run_simulation.py with ARGS"
	@echo "make build-escape-config  rebuild escape_v1 config + circuit artifact from the canonical graph"
	@echo "make smoke-escape       TECHNICAL CONNECTOME-GROUNDED ESCAPE DEMO (escape_v1)"
	@echo "make smoke-web          WEB DEMO SMOKE: escape API over REST + WebSocket + inspector API"
	@echo "make smoke-embodiment   TECHNICAL EMBODIMENT SMOKE: closed loop with the SIMPLIFIED COMPUTATIONAL BODY (P7.0)"
	@echo "make smoke-threat-lab   VIRTUAL THREAT LAB SMOKE: /embodiment/config + /embodiment/run replay over HTTP (P7.1)"
	@echo "make smoke-intervention NEURAL INTERVENTION SMOKE: CONTROL vs SILENCE_LPLC2 over the A/B API (P7.2)"
	@echo "make demo-smoke         start both servers, verify they answer, stop (release/CI check)"
	@echo "make screenshots        refresh docs/screenshots/release-*.png with Playwright"
	@echo "make build-frontend     production build of the frontend (frontend/dist)"

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
	cd $(BACKEND_DIR) && .venv/bin/ruff check . ../scripts && .venv/bin/ruff format --check . ../scripts

build-frontend:
	cd $(FRONTEND_DIR) && npm run build

smoke: smoke-backend smoke-data smoke-circuit smoke-simulation smoke-escape smoke-web smoke-embodiment smoke-threat-lab smoke-intervention smoke-frontend

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

smoke-simulation:
	$(VENV_PY) scripts/smoke_simulation.py

simulate:
	$(VENV_PY) scripts/run_simulation.py $(ARGS)

build-escape-config:
	$(VENV_PY) scripts/build_escape_config.py

smoke-escape:
	$(VENV_PY) scripts/smoke_escape.py

smoke-web:
	$(VENV_PY) scripts/smoke_web_demo.py

smoke-embodiment:
	$(VENV_PY) scripts/smoke_embodiment.py

smoke-threat-lab:
	$(VENV_PY) scripts/smoke_threat_lab.py

smoke-intervention:
	$(VENV_PY) scripts/smoke_intervention.py

demo:
	$(VENV_PY) scripts/run_demo.py

demo-check:
	$(VENV_PY) scripts/run_demo.py --check

demo-smoke:
	$(VENV_PY) scripts/run_demo.py --smoke

screenshots:
	cd $(FRONTEND_DIR) && FLYBRAIN_SCREENSHOT_DIR=../docs/screenshots npx playwright test tests/release-screenshots.spec.ts tests/smoke-inspector.spec.ts tests/smoke-threat-lab.spec.ts tests/smoke-intervention.spec.ts

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
