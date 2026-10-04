# ltts — команды разработки и запуска. `make` без аргументов покажет список.
# Переопределяются: make serve PORT=9000, make say TEXT="Привет" VOICE=piper:denis, LTTS_HOME=... make serve

PORT  ?= 8765
TEXT  ?= Привет! Это локальный синтез речи.
VOICE ?=
LANG_ ?= auto
LTTS  := uv run ltts

.DEFAULT_GOAL := help
.PHONY: help install install-no-rhvoice sync setup rhvoice serve open say say-en voices doctor download mcp mcp-add lint build clean

help: ## показать команды
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------- установка ----------

install: ## поставить ltts глобально (uv tool) + голоса + RHVoice
	./install.sh

install-no-rhvoice: ## то же, без сборки RHVoice
	./install.sh --no-rhvoice

sync: ## dev-окружение (.venv) из репозитория
	uv sync

setup: sync ## скачать голоса по умолчанию и собрать RHVoice (dev)
	$(LTTS) setup

rhvoice: sync ## собрать только RHVoice (если ещё не собран) + русские голоса
	bash src/ltts/scripts/build-rhvoice.sh

# ---------- запуск ----------

serve: sync ## веб-морда + API на http://127.0.0.1:8765 (PORT=... чтобы сменить)
	$(LTTS) serve --port $(PORT)

open: sync ## то же и открыть в браузере
	$(LTTS) serve --port $(PORT) --open

say: sync ## озвучить и проиграть: make say TEXT="..." VOICE=engine:voice LANG_=auto|ru|en
	$(LTTS) say "$(TEXT)" $(if $(VOICE),-v $(VOICE)) --lang $(LANG_) --play --json

say-en: sync ## проверить английский
	$(LTTS) say "Hello! This is a local text to speech engine." $(if $(VOICE),-v $(VOICE)) --play --json

voices: sync ## список голосов
	$(LTTS) voices

doctor: sync ## что установлено и что сломано
	$(LTTS) doctor

download: sync ## скачать голоса: make download VOICES="rhvoice:tatiana piper:amy"
	$(LTTS) download $(VOICES)

mcp: sync ## MCP-сервер в stdio (для отладки)
	$(LTTS) mcp

mcp-add: ## подключить к Claude Code (нужен установленный ltts — make install)
	claude mcp add ltts -- ltts mcp

# ---------- разработка ----------

lint: ## ruff
	uvx ruff check src --select E,F,W,B --ignore E501

build: ## собрать wheel в dist/
	uv build

clean: ## удалить сборочный мусор (голоса и модели не трогает)
	rm -rf dist .ruff_cache
	find src -name __pycache__ -type d -exec rm -rf {} +
