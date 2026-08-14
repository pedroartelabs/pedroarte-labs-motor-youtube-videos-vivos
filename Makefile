# ---------------------------------------------------------------------------
# PEDRO_ARTE_YOUTUBE_LIVING_BOOK_ENGINE
# ---------------------------------------------------------------------------
# `uv` é o gerenciador recomendado. Quando ele não estiver disponível, os alvos
# recaem automaticamente para `python -m venv` + `pip`, sem alterar o resultado.
# ---------------------------------------------------------------------------

SHELL := /bin/sh
PY ?= python
VENV := .venv

ifeq ($(OS),Windows_NT)
	VENV_BIN := $(VENV)/Scripts
	VENV_PY  := $(VENV_BIN)/python.exe
else
	VENV_BIN := $(VENV)/bin
	VENV_PY  := $(VENV_BIN)/python
endif

HAS_UV := $(shell command -v uv 2>/dev/null)

.DEFAULT_GOAL := help
.PHONY: help install dev lint format typecheck test coverage validate sample \
        api mcp docs docker-build ci clean run doctor schemas hooks

help: ## Lista os alvos disponíveis
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Instala o pacote e as dependências de runtime
ifdef HAS_UV
	uv sync --extra api
else
	$(PY) -m venv $(VENV)
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -e ".[api]"
endif

dev: ## Instala tudo, incluindo ferramentas de desenvolvimento
ifdef HAS_UV
	uv sync --extra api --extra dev --extra docs
else
	$(PY) -m venv $(VENV)
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -e ".[api,dev,docs]"
endif

hooks: ## Instala os hooks de pre-commit
	$(VENV_PY) -m pre_commit install

lint: ## Executa o linter
	$(VENV_PY) -m ruff check src tests scripts

format: ## Formata o código
	$(VENV_PY) -m ruff format src tests scripts
	$(VENV_PY) -m ruff check --fix src tests scripts

typecheck: ## Executa a verificação estática de tipos
	$(VENV_PY) -m mypy

test: ## Executa a suíte de testes
	$(VENV_PY) -m pytest

coverage: ## Executa os testes com relatório de cobertura
	$(VENV_PY) -m pytest --cov=pedroarte_youtube_engine --cov-report=term-missing --cov-report=xml

schemas: ## Valida os JSON Schemas publicados em schemas/
	$(VENV_PY) scripts/validate_schemas.py

validate: lint typecheck schemas ## Lint + tipos + schemas

sample: ## Executa o exemplo sintético completo, sem credenciais externas
	$(VENV_PY) -m pedroarte_youtube_engine.interfaces.cli.main run \
		--input examples/sample_living_book/input \
		--output outputs \
		--config config/development.yaml

run: ## Executa o motor sobre a pasta ./input
	$(VENV_PY) -m pedroarte_youtube_engine.interfaces.cli.main run --input ./input --output ./outputs

doctor: ## Diagnostica o ambiente
	$(VENV_PY) -m pedroarte_youtube_engine.interfaces.cli.main doctor

api: ## Sobe a API HTTP opcional
	$(VENV_PY) -m pedroarte_youtube_engine.interfaces.cli.main api serve

mcp: ## Sobe o servidor MCP (stdio)
	$(VENV_PY) -m pedroarte_youtube_engine.interfaces.cli.main mcp serve

docs: ## Constrói a documentação estática
	$(VENV_PY) -m mkdocs build --strict

docker-build: ## Constrói a imagem Docker
	docker build -t pedroarte-youtube-engine:0.1.0 .

ci: lint typecheck schemas coverage ## Pipeline local equivalente ao CI

clean: ## Remove artefatos de build e caches
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache .hypothesis htmlcov coverage.xml .coverage site
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
