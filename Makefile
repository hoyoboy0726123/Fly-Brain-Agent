# Developer shortcuts for FlyBrain Agent. See docs/DEVELOPMENT.md for details.

PYTHON       ?= python3
BACKEND_DIR  := backend
FRONTEND_DIR := frontend
VENV         := $(BACKEND_DIR)/.venv
VENV_PY      := $(VENV)/bin/python

.PHONY: help install install-backend install-frontend backend frontend \
        test test-backend typecheck-frontend lint smoke smoke-backend smoke-frontend clean

help:
	@echo "make install            install backend (.venv) and frontend (node_modules) dependencies"
	@echo "make backend            run FastAPI on http://127.0.0.1:8000"
	@echo "make frontend           run Vite dev server on http://127.0.0.1:5173"
	@echo "make test               backend unit tests + frontend typecheck"
	@echo "make smoke              backend /health smoke + frontend Playwright smoke"
	@echo "make lint               ruff check on backend"

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

smoke: smoke-backend smoke-frontend

smoke-backend:
	$(VENV_PY) scripts/smoke_test.py

smoke-frontend:
	cd $(FRONTEND_DIR) && npm run test:e2e

clean:
	rm -rf $(BACKEND_DIR)/.pytest_cache $(BACKEND_DIR)/.ruff_cache \
	       $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/test-results $(FRONTEND_DIR)/playwright-report
	find $(BACKEND_DIR) -name __pycache__ -type d -prune -exec rm -rf {} +
