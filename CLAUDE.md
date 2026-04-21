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

**Pipeline flow**: `main.py` builds one `ConcursoBot` per target from `config/loader.py` → `MultiAreaRunner` → each `ConcursoBot` → `GranScraper` → `IntelligenceUnit` → `DatabaseManager` → `TelegramNotifier`

1. **GranScraper** (`src/scrapers/gran_scraper.py`) slices page HTML into blocks — does NO data extraction. Default mode slices by `<h3>` tags; URLs containing `/cursos/carreira/` use a separate path that slices by `<h3>`/`<h4>` section headings plus `<li>` items and filters hardcoded section names (see `_CARREIRA_SECOES` / `_RUIDO_MARCADORES`).
2. **ConcursoBot** (`src/core/bot.py`) orchestrates per-area: cheap keyword pre-filter (`_passa_filtro_palavras`) → LLM extraction → DB lookup → optional LLM analysis for changed entries → notification. At the end of each cycle, if nothing new was found it still sends a "varredura concluída" confirmation to Telegram — be aware when testing.
3. **IntelligenceUnit** (`src/intelligence/langchain_unit.py`) runs two LangChain chains built on either Ollama or LiteLLM:
   - **Extraction chain** (JSON mode): HTML block → `{ignorar, nome, status, link}`. The system prompt receives `area_context` + include/exclude keywords so the LLM rejects off-area blocks.
   - **Analysis chain** (text mode): old vs new status → summary or literal `IGNORE`
   - Both chains retry on failure (`OLLAMA_RETRIES`, `OLLAMA_RETRY_DELAY_S`) and surface JSON wrapped in markdown fences via `_parse_json_response`.
4. **MultiAreaRunner** (`src/core/multi_area_runner.py`) runs the bots sequentially each cycle.
5. **DailyScheduler** (`src/scheduler/runner.py`) registers `schedule.every().day.at(horario)`, then `iniciar()` is a blocking loop calling `schedule.run_pending()` every 60s. `main.py` also triggers one immediate scan before entering the loop.

## Configuration

Config is via `.env`. Two modes:

- **Multi-area** (recommended): `MONITOR_TARGETS_JSON` — JSON array of area configs with `area`, `url`, `chat_ids`, `keywords_include`, `keywords_exclude`. **Must be on a single line** — python-dotenv does not support multiline values, so pretty-printing the JSON will silently break loading and fall through to legacy mode.
- **Legacy single-area**: `URL_ALVO` + `TELEGRAM_CHAT_ID` + `KEYWORDS_INCLUDE` + `KEYWORDS_EXCLUDE`. Used as fallback when `MONITOR_TARGETS_JSON` is missing or fails to parse.

Model selection: `LLM_MODEL` takes precedence over `OLLAMA_MODEL` (main.py uses `os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL", "llama3.1")`). A `/` in the model name auto-routes through LiteLLM (e.g. `minimax/MiniMax-M2`), otherwise the local Ollama path is used.

Config loading logic is in `config/loader.py`.

## Database

SQLite at `data/concursos.db`. Table `editais` with composite primary key `(area, nome)`. Auto-migrates from the old single-area schema (PK on `nome` only) into `editais_v2` and renames it back on startup — legacy rows are tagged with area `TI`. Connection is opened with `check_same_thread=False`. Manager in `src/database/manager.py`.

## Key Design Decisions

- **AI-first extraction**: LLM reads raw HTML semantically, making the system resilient to website layout changes — the scraper intentionally does no field extraction.
- **Dual LLM backend**: Ollama (local) or any LiteLLM-compatible API; selected purely by whether the model name contains `/`.
- **Keyword pre-filtering** happens before LLM calls to save compute — applied at bot level (`_passa_filtro_palavras`) AND reinforced inside the extraction prompt.
- **All code, logs, prompts, and Telegram messages are in Brazilian Portuguese** — keep this when editing.
- **BaseScraper** (`src/scrapers/base_scraper.py`) is abstract — extend it for other websites.
- **Graceful degradation**: missing Telegram config logs a warning and skips notifications; bad HTML blocks return `{"ignorar": True}` rather than raising.
