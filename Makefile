PYTHON ?= python3
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python

ifneq (,$(wildcard ./.env))
include .env
export
endif

.PHONY: setup generate-data db-up db-down db-check test lint

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -e ".[dev]"

generate-data:
	PYTHONPATH=src $(PYTHON) -m pipeline generate-data --output data/raw/local

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

db-check:
	$(VENV_PYTHON) -m pipeline check-db

test:
	$(VENV_PYTHON) -m pytest

lint:
	$(VENV_PYTHON) -m ruff check .
