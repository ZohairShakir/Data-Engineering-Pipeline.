PYTHON ?= python3
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python

ifneq (,$(wildcard ./.env))
include .env
export
endif

.PHONY: setup generate-data db-up db-down db-check run analytics runs \
	test test-python test-integration test-dashboard lint \
	dashboard-install dashboard-build dashboard

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -e ".[dev]"

generate-data:
	$(VENV_PYTHON) -m pipeline generate-data --output data/raw/local

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

db-check:
	$(VENV_PYTHON) -m pipeline check-db

run:
	$(VENV_PYTHON) -m pipeline run

analytics:
	$(VENV_PYTHON) -m pipeline analytics

runs:
	$(VENV_PYTHON) -m pipeline runs

test: test-python test-dashboard

test-python:
	$(VENV_PYTHON) -m pytest -m "not integration"

test-integration:
	$(VENV_PYTHON) -m pytest -m integration

test-dashboard:
	npm test --prefix dashboard

lint:
	$(VENV_PYTHON) -m ruff check .

dashboard-install:
	npm ci --prefix dashboard

dashboard-build:
	npm run build --prefix dashboard

dashboard:
	npm run dev --prefix dashboard
