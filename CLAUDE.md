# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Monitor de Concursos is an AI-first web scraping system that monitors job/competition postings on Gran Cursos Online. It uses a local LLM (Llama 3.1 via Ollama + LangChain) to semantically extract and analyze HTML blocks instead of brittle CSS selectors, then sends relevant notifications via Telegram. Supports multi-area monitoring (TI, Sociologia, Artes) with per-area Telegram chat routing.

## Running

```bash
# Setup
python -m venv .venv
source .venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt

# Ollama must be running with the model pulled
ollama serve
ollama pull llama3.1

# Configure .env from .env.example, then run
python main.py
```

There is no test suite. No linter or formatter is configured.

## Architecture

**Pipeline flow**: `main.py` → `MultiAreaRunner` → `ConcursoBot` (per area) → `GranScraper` → `IntelligenceUnit` → `DatabaseManager` → `TelegramNotifier`

1. **GranScraper** (`src/scrapers/gran_scraper.py`) slices page HTML by `<h3>` tags — does NO data extraction
2. **ConcursoBot** (`src/core/bot.py`) orchestrates: keyword pre-filter → LLM extraction → DB lookup → notification
3. **IntelligenceUnit** (`src/intelligence/langchain_unit.py`) runs two LangChain chains:
   - **Extraction chain** (JSON mode): HTML block → `{ignorar, nome, status, link}`
   - **Analysis chain** (text mode): old vs new status → relevance decision
4. **MultiAreaRunner** (`src/core/multi_area_runner.py`) runs multiple ConcursoBots sequentially, one per configured area
5. **DailyScheduler** (`src/scheduler/runner.py`) runs an immediate scan then enters infinite loop checking every 60s for the configured execution time

## Configuration

Config is via `.env`. Two modes:

- **Multi-area** (recommended): `MONITOR_TARGETS_JSON` — JSON array of area configs with `area`, `url`, `chat_ids`, `keywords_include`, `keywords_exclude`
- **Legacy single-area**: `URL_ALVO` + `TELEGRAM_CHAT_ID` + `KEYWORDS_INCLUDE` + `KEYWORDS_EXCLUDE`

Config loading logic is in `config/loader.py`.

## Database

SQLite at `data/concursos.db`. Table `editais` with composite primary key `(area, nome)`. Auto-migrates from old single-area schema on startup. Manager in `src/database/manager.py`.

## Key Design Decisions

- **AI-first extraction**: LLM reads raw HTML semantically, making the system resilient to website layout changes
- **Dual LLM backend**: supports Ollama (local) or any LiteLLM-compatible API (e.g. `minimax/MiniMax-M2`) via the `LLM_MODEL` env var — model names with a `/` automatically route through LiteLLM
- **Keyword pre-filtering** happens before LLM calls to save compute
- **All code and logs are in Portuguese** (Brazilian Portuguese)
- **BaseScraper** (`src/scrapers/base_scraper.py`) is abstract — extend it for other websites
- **Graceful degradation**: missing Telegram config skips notifications; bad HTML blocks are ignored
