# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Monitor de Concursos is an AI-first web scraping system that monitors job/competition postings on Gran Cursos Online. It uses a local LLM (Llama 3.1 via Ollama + LangChain) to semantically extract and analyze HTML blocks instead of brittle CSS selectors, then sends relevant notifications via Telegram. Supports multi-area monitoring (TI, Sociologia, Artes) with per-area Telegram chat routing.

## Running

```bash
# Setup (Windows Git Bash)
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt

# Configure .env from .env.example, then run a single scan
python main.py
```

`main.py` is **single-run**: one scan across all configured areas, then exit (0 on success, 1 on error). Daily scheduling is done via Windows Task Scheduler — see `scripts/install_schedule.ps1` (registers a task that calls `scripts/run_daily.bat`).

Ollama is only required if `LLM_MODEL` is a plain name like `llama3.1`. See "LLM backends" below.

## Tests

```bash
pip install -r requirements-dev.txt
pytest                                    # full suite (88 tests)
pytest tests/test_concurso_bot.py -v      # one file
pytest -k "TestExecutarFlow"              # by name pattern
pytest --cov=src --cov=config             # with coverage
```

All external dependencies are mocked — tests do not require Ollama, an API key, `claude` CLI, or network. `tests/conftest.py` inserts the project root into `sys.path` so `from src.core.bot import ...` works.

## Architecture

**Pipeline flow**: `main.py` builds one `ConcursoBot` per target from `config/loader.py` → `MultiAreaRunner` → each `ConcursoBot` → `GranScraper` → `IntelligenceUnit` → `DatabaseManager` → `TelegramNotifier`

1. **GranScraper** (`src/scrapers/gran_scraper.py`) slices page HTML into blocks — does NO data extraction. Default mode slices by `<h3>` tags; URLs containing `/cursos/carreira/` use a separate path that slices by `<h3>`/`<h4>` section headings plus `<li>` items and filters hardcoded section names (see `_CARREIRA_SECOES` / `_RUIDO_MARCADORES`).
2. **ConcursoBot** (`src/core/bot.py`) orchestrates per-area: cheap keyword pre-filter (`_passa_filtro_palavras`) → LLM extraction → DB lookup → optional LLM analysis for changed entries → notification. At the end of each cycle, if nothing new was found it still sends a "varredura concluída" confirmation to Telegram — be aware when testing.
3. **IntelligenceUnit** (`src/intelligence/langchain_unit.py`) runs two LangChain chains over the backend selected by `_detect_backend(model_name)`:
   - **Extraction chain** (JSON mode): HTML block → `{ignorar, nome, status, link}`. The system prompt receives `area_context` + include/exclude keywords so the LLM rejects off-area blocks.
   - **Analysis chain** (text mode): old vs new status → summary or literal `IGNORE`
   - Both chains retry on failure (`OLLAMA_RETRIES`, `OLLAMA_RETRY_DELAY_S`) and surface JSON wrapped in markdown fences via `_parse_json_response`.
4. **MultiAreaRunner** (`src/core/multi_area_runner.py`) runs the bots sequentially each cycle.
5. **Scheduling is external.** `main.py` does NOT have an internal loop. `src/scheduler/runner.py` (`DailyScheduler`) still exists as a legacy helper but is not wired into `main.py` — use Windows Task Scheduler via `scripts/install_schedule.ps1` instead.

## LLM backends

`IntelligenceUnit._detect_backend(model_name)` picks one of three paths:

| `LLM_MODEL` format | Backend | Entry point |
| --- | --- | --- |
| `llama3.1`, `qwen2.5:7b` (no `/`, no `claude-cli` prefix) | Ollama local | `_create_ollama` |
| `anthropic/claude-haiku-4-5-...`, `openai/gpt-4o`, any `provider/model` | LiteLLM (API) | `_create_litellm` |
| `claude-cli` or `claude-cli:haiku` \| `:sonnet` \| `:opus` | Claude Code CLI | `_create_claude_cli` → `src/intelligence/claude_cli_backend.py` |

The Claude CLI backend (`ClaudeCliLLM`) wraps `claude -p --model <alias> --output-format text --no-session-persistence`, piping the prompt on stdin (NOT argv — avoids Windows cmd length limits and escaping issues with Portuguese). It does not support JSON mode, relying on prompt instructions + `_parse_json_response` to handle fenced or inline JSON.

## Configuration

Config is via `.env`. Two modes:

- **Multi-area** (recommended): `MONITOR_TARGETS_JSON` — JSON array of area configs with `area`, `url`, `chat_ids`, `keywords_include`, `keywords_exclude`. **Must be on a single line** — python-dotenv does not support multiline values, so pretty-printing the JSON will silently break loading and fall through to legacy mode.
- **Legacy single-area**: `URL_ALVO` + `TELEGRAM_CHAT_ID` + `KEYWORDS_INCLUDE` + `KEYWORDS_EXCLUDE`. Used as fallback when `MONITOR_TARGETS_JSON` is missing or fails to parse.

Model selection: `LLM_MODEL` takes precedence over `OLLAMA_MODEL` (main.py uses `os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL", "llama3.1")`). Routing rules in the "LLM backends" section above.

Config loading logic is in `config/loader.py`.

## Database

SQLite at `data/concursos.db`. Table `editais` with composite primary key `(area, nome)`. Auto-migrates from the old single-area schema (PK on `nome` only) into `editais_v2` and renames it back on startup — legacy rows are tagged with area `TI`. Connection is opened with `check_same_thread=False`. Manager in `src/database/manager.py`.

## Key Design Decisions

- **AI-first extraction**: LLM reads raw HTML semantically, making the system resilient to website layout changes — the scraper intentionally does no field extraction.
- **Three LLM backends**: Ollama (local, no slash), LiteLLM (API, with slash), Claude Code CLI (prefix `claude-cli`). Selection is purely by `LLM_MODEL` string format — no extra env var needed.
- **Keyword pre-filtering** happens before LLM calls to save compute — applied at bot level (`_passa_filtro_palavras`) AND reinforced inside the extraction prompt.
- **All code, logs, prompts, and Telegram messages are in Brazilian Portuguese** — keep this when editing.
- **BaseScraper** (`src/scrapers/base_scraper.py`) is abstract — extend it for other websites.
- **Graceful degradation**: missing Telegram config logs a warning and skips notifications; bad HTML blocks return `{"ignorar": True}` rather than raising.
