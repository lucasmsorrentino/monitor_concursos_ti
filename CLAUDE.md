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

SQLite at `data/concursos.db`. Table `editais` (schema v3):

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PK AUTOINCREMENT | Stable across updates — used in Telegram `callback_data` |
| `area` | TEXT NOT NULL | Area slug (TI, EDUCACAO, ...) |
| `nome` | TEXT NOT NULL | `UNIQUE(area, nome)` — LLM name may vary, dedup also falls back to `link` |
| `status` | TEXT NOT NULL | Raw 2-sentence summary from the extraction chain |
| `link` | TEXT | Canonical identity when specific (different from scraper's index URL) |
| `data_fim_inscricao` | TEXT NULL | ISO `YYYY-MM-DD` or NULL — gates whether new contests trigger notifications |
| `status_hash` | TEXT NULL | sha1[:16] of `status_fingerprint(status)` — deduplicates LLM reformulations |
| `estado_usuario` | TEXT DEFAULT `'ativo'` | `ativo` \| `ignorado` \| `seguindo` — controlled by Telegram inline buttons |
| `ultima_atualizacao` | TIMESTAMP | Auto-updated on every upsert |

Auto-migrates v1 (PK `nome`) and v2 (PK `(area, nome)`) into v3 on startup; legacy v1 rows are tagged with area `TI`. Connection opened with `check_same_thread=False`. Manager in `src/database/manager.py`.

`atualizar_concurso` does explicit UPDATE-if-exists (by `link` if specific, else by `(area, nome)`) before INSERT — this preserves `id` between runs, which is required for the Telegram callback buttons to stay valid.

## User state flow (new/update decisions)

Each row has one of three `estado_usuario` states controlling notifications:

- **`ativo`** (default): notifications until the inscription deadline. After `date.today() > data_fim_inscricao`, updates go silent (DB still refreshes).
- **`ignorado`**: set by clicking ❌ on the Telegram notification. All future scans skip this row (no DB update either).
- **`seguindo`**: set by clicking ⭐. Relevant changes are notified forever, even past the deadline.

Brand-new contests whose deadline has already passed are saved silently (no first notification) — see matrix in `ConcursoBot._decidir_e_notificar`. The cheap dedup step compares `status_fingerprint` hashes before spending an LLM analysis call, which fixes the "keeps repeating" bug from minor reformulations.

Note: legacy rows inserted before v3 migration have `status_hash = NULL` — they count as "hash different" on first post-deploy scan, which may trigger one cycle of no-op analysis/updates before converging.

## Telegram interactive buttons

New concurso messages and relevant-change messages go through `TelegramNotifier.notificar_concurso(id_interno, msg)`, which attaches an inline keyboard with two callback buttons:

- `callback_data=estado:<id>:seguindo` → ⭐ Seguir
- `callback_data=estado:<id>:ignorado` → ❌ Não tenho interesse

Callbacks are processed in batch at the start of each run via `TelegramCallbackProcessor.processar_pendentes()` (called from `ConcursoBot.executar()`). It polls `getUpdates?offset=N` with `allowed_updates=[callback_query]`, applies the state to the DB, sends `answerCallbackQuery` for visual feedback, and calls `editMessageReplyMarkup` to strip the buttons from the original message. Offset is persisted at `data/telegram_offset.json`.

The processor is single-run (no daemon) — clicks are applied at the next scheduled scan. Network errors are swallowed so scraping never blocks on Telegram. Offset always advances even on parse errors to prevent infinite loops.

## Key Design Decisions

- **AI-first extraction**: LLM reads raw HTML semantically, making the system resilient to website layout changes — the scraper intentionally does no field extraction.
- **Three LLM backends**: Ollama (local, no slash), LiteLLM (API, with slash), Claude Code CLI (prefix `claude-cli`). Selection is purely by `LLM_MODEL` string format — no extra env var needed.
- **Keyword pre-filtering** happens before LLM calls to save compute — applied at bot level (`_passa_filtro_palavras`) AND reinforced inside the extraction prompt.
- **Hash-based dedup before LLM analysis**: `status_fingerprint` (lowercase + strip accents + collapse whitespace + border punct + sha1[:16]) catches trivial reformulations without spending a second LLM call.
- **All code, logs, prompts, and Telegram messages are in Brazilian Portuguese** — keep this when editing.
- **BaseScraper** (`src/scrapers/base_scraper.py`) is abstract — extend it for other websites.
- **Graceful degradation**: missing Telegram config logs a warning and skips notifications; bad HTML blocks return `{"ignorar": True}` rather than raising; Telegram callback failures never block the scrape.
