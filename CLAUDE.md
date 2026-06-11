# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Monitor de Concursos is an AI-first web scraping system that monitors job/competition postings on Gran Cursos Online. It uses an LLM (via LangChain, three selectable backends) to semantically extract structured data — including a controlled-vocabulary contest `fase` — from HTML blocks instead of brittle CSS selectors, then sends relevant notifications via Telegram. Supports multi-area monitoring (TI, Educação, ...) with per-area Telegram chat routing.

## Running

```bash
# Setup (Linux/Mac; on Windows Git Bash use .venv/Scripts/activate)
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure .env from .env.example, then run a single scan
python main.py
```

`main.py` is **single-run**: one scan across all configured areas, then exit (0 on success, 1 on error). Daily scheduling is done by the OS:

- **Windows**: `scripts/install_schedule.ps1` registers a Task Scheduler task calling `scripts/run_daily.bat`.
- **Linux**: `scripts/install_schedule.sh` installs a crontab entry calling `scripts/run_daily.sh` hourly 08:05-22:05; the script itself enforces one successful run per day (marker file) with hourly catch-up if the machine was off, plus `flock` against overlap.

Ollama is only required if `LLM_MODEL` is a plain name like `llama3.1`. See "LLM backends" below.

## Tests

```bash
pip install -r requirements-dev.txt
pytest                                    # full suite (144 tests)
pytest tests/test_concurso_bot.py -v      # one file
pytest -k "TestExecutarFlow"              # by name pattern
pytest --cov=src --cov=config             # with coverage
```

All external dependencies are mocked — tests do not require Ollama, an API key, `claude` CLI, or network. `tests/conftest.py` inserts the project root into `sys.path` so `from src.core.bot import ...` works.

## Architecture

**Pipeline flow**: `main.py` builds one `ConcursoBot` per target from `config/loader.py` → `MultiAreaRunner` → each `ConcursoBot` → `GranScraper` → `IntelligenceUnit` → `DatabaseManager` → `TelegramNotifier`

1. **GranScraper** (`src/scrapers/gran_scraper.py`) slices page HTML into blocks — does NO data extraction. Default mode slices by `<h3>` tags; URLs containing `/cursos/carreira/` use a separate path that slices by `<h3>`/`<h4>` section headings plus `<li>` items and filters hardcoded section names (see `_CARREIRA_SECOES` / `_RUIDO_MARCADORES`).
2. **ConcursoBot** (`src/core/bot.py`) orchestrates per-area: pending Telegram callbacks → cheap keyword pre-filter (`_passa_filtro_palavras`) → LLM extraction → DB lookup → **fase-based decision matrix** (`_decidir_e_notificar`, no second LLM call) → notification. End-of-cycle messages: heartbeat "Varredura Concluída" when nothing new, or a ⚠️ blind-scan alert when ZERO valid contests were extracted (site down / layout change) — never a false "nothing new".
3. **IntelligenceUnit** (`src/intelligence/langchain_unit.py`) runs LangChain chains over the backend selected by `_detect_backend(model_name)`:
   - **Extraction chain** (JSON mode): HTML block → `{ignorar, nome, status, link, data_fim_inscricao, data_referencia, fase}`. The system prompt receives `area_context` + include/exclude keywords so the LLM rejects off-area blocks. `fase` is one of 6 literals (see "Fase vocabulary"); `data_referencia` is the most relevant event date (ISO; month/year → first day; null when no date). Both are sanitized post-parse (`sanitizar_fase`, `_sanitizar_data`).
   - **Analysis chain** (text mode, LEGACY): old vs new status → summary or `IGNORE`. Still implemented and tested, but **no longer called by the decision flow** — free-text comparison was the source of false positives.
   - Chains retry on failure (`OLLAMA_RETRIES`, `OLLAMA_RETRY_DELAY_S`) and surface JSON wrapped in markdown fences via `_parse_json_response`.
4. **MultiAreaRunner** (`src/core/multi_area_runner.py`) runs the bots sequentially each cycle.
5. **Scheduling is external.** `main.py` does NOT have an internal loop. `src/scheduler/runner.py` (`DailyScheduler`) is a legacy helper not wired into `main.py` — use Task Scheduler (Windows) or cron via `scripts/install_schedule.sh` (Linux).

## Fase vocabulary (`src/utils/fases.py`)

Ordered controlled vocabulary, the backbone of change detection:

```
previsto → banca_definida → edital_publicado → inscricoes_abertas → inscricoes_encerradas → concluido
```

- `sanitizar_fase(valor)` — normalize/validate, None if unknown.
- `fase_avancou(antiga, nova)` — True only when both valid and nova is strictly later.
- `fase_mais_avancada(a, b)` — anti-flapping: regressions never downgrade the stored fase.
- `label(fase)` — human-readable label for Telegram messages.

Only a fase ADVANCE or a `data_fim_inscricao` change triggers an update notification. LLM rewording (same fase) and fase regressions are silent. A disappearing `data_fim` (new value None) is treated as extraction failure, not a change.

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

SQLite at `data/concursos.db`. Table `editais` (schema v4):

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PK AUTOINCREMENT | Stable across updates — used in Telegram `callback_data` |
| `area` | TEXT NOT NULL | Area slug (TI, EDUCACAO, ...) |
| `nome` | TEXT NOT NULL | `UNIQUE(area, nome)` — LLM name may vary, dedup also falls back to `link` |
| `status` | TEXT NOT NULL | Raw 2-sentence summary from the extraction chain (display only — NOT used for change detection) |
| `link` | TEXT | Canonical identity when specific (different from scraper's index URL) |
| `data_fim_inscricao` | TEXT NULL | ISO `YYYY-MM-DD` or NULL — gates activity + its change triggers notification |
| `status_hash` | TEXT NULL | sha1[:16] of `status_fingerprint(status)` — legacy dedup, superseded by `fase` |
| `fase` | TEXT NULL | Controlled vocabulary (see "Fase vocabulary") — the change-detection key. NULL = pre-v4 row awaiting silent backfill |
| `estado_usuario` | TEXT DEFAULT `'ativo'` | `ativo` \| `ignorado` \| `seguindo` — controlled by Telegram inline buttons |
| `ultima_atualizacao` | TIMESTAMP | Auto-updated on every upsert |

Auto-migrates v1 (PK `nome`) → v2 (PK `(area, nome)`) → v3 (`id` autoincrement) → v4 (adds `fase`, additive `ALTER TABLE`) on startup; legacy v1 rows are tagged with area `TI`. `atualizar_concurso` uses `COALESCE(?, fase)` so updates without a fase never erase a stored one. Connection opened with `check_same_thread=False`. Manager in `src/database/manager.py`.

`atualizar_concurso` does explicit UPDATE-if-exists (by `link` if specific, else by `(area, nome)`) before INSERT — this preserves `id` between runs, which is required for the Telegram callback buttons to stay valid.

## Decision matrix (`ConcursoBot._decidir_e_notificar`)

A contest is **inativo** when its deadline passed (`data_fim_inscricao` in the past) OR it is a **dead listing**: no known inscription window (`data_fim` None) AND the most relevant event date (`data_referencia`) is in the past (e.g. "provas previstas para maio de 2025" still on the page in 2026). A legit "previsto" with no date at all is NOT inativo.

| Case | Action |
| --- | --- |
| `estado_usuario = 'ignorado'` | total skip (not even a DB update) |
| New row + inativo | save silently |
| New row + active/previsto | notify 🆕 NOVO (includes fase + deadline) + save |
| Legacy row (`fase` NULL) | silent fase backfill, no notification |
| No fase advance AND no new `data_fim` | silent refresh (`fase_mais_avancada` preserved) |
| Real transition (fase advanced and/or `data_fim` changed) + `seguindo` | always notify |
| Real transition + inativo (not `seguindo`) | silent update |
| Real transition otherwise | notify 🔔 ATUALIZAÇÃO (shows fase_antiga → fase_nova and/or new deadline) |

Each `estado_usuario` value: **`ativo`** (default) notifies until the deadline; **`ignorado`** (❌ button) silences forever; **`seguindo`** (⭐ button) notifies real transitions forever.

The legacy `analisar_mudanca` LLM chain and `status_hash` comparison are NOT part of this flow anymore — both reacted to LLM rewording and caused false positives. `status_hash` is still populated for diagnostics.

## Telegram interactive buttons

New concurso messages and relevant-change messages go through `TelegramNotifier.notificar_concurso(id_interno, msg)`, which attaches an inline keyboard with two callback buttons:

- `callback_data=estado:<id>:seguindo` → ⭐ Seguir
- `callback_data=estado:<id>:ignorado` → ❌ Não tenho interesse

Callbacks are processed in batch at the start of each run via `TelegramCallbackProcessor.processar_pendentes()` (called from `ConcursoBot.executar()`). It polls `getUpdates?offset=N` with `allowed_updates=[callback_query]`, applies the state to the DB, sends `answerCallbackQuery` for visual feedback, and calls `editMessageReplyMarkup` to strip the buttons from the original message. Offset is persisted at `data/telegram_offset.json`.

The processor is single-run (no daemon) — clicks are applied at the next scheduled scan. Network errors are swallowed so scraping never blocks on Telegram. Offset always advances even on parse errors to prevent infinite loops.

## Key Design Decisions

- **AI-first extraction**: LLM reads raw HTML semantically, making the system resilient to website layout changes — the scraper intentionally does no field extraction.
- **Structured fase over free text**: change detection compares a closed, ordered vocabulary extracted at classification time — never the free-text status, which the LLM rewords every scan. Only advances count; regressions are absorbed (`fase_mais_avancada`). This replaced both the hash comparison and the analysis chain as the decision mechanism.
- **Dead-listing filter**: `data_referencia` distinguishes stale page entries (past event, no inscription window) from genuine upcoming "previsto" contests.
- **Never mask a blind scan**: zero valid extractions sends a ⚠️ alert, not the success heartbeat.
- **Three LLM backends**: Ollama (local, no slash), LiteLLM (API, with slash), Claude Code CLI (prefix `claude-cli`). Selection is purely by `LLM_MODEL` string format — no extra env var needed.
- **Keyword pre-filtering** happens before LLM calls to save compute — applied at bot level (`_passa_filtro_palavras`) AND reinforced inside the extraction prompt.
- **All code, logs, prompts, and Telegram messages are in Brazilian Portuguese** — keep this when editing.
- **BaseScraper** (`src/scrapers/base_scraper.py`) is abstract — extend it for other websites.
- **Graceful degradation**: missing Telegram config logs a warning and skips notifications; bad HTML blocks return `{"ignorar": True}` rather than raising; Telegram callback failures never block the scrape.
- **Known dedup gap**: when a block contains both a blog link and a course-page link, the LLM may pick a different one across runs, creating a duplicate row (each link then exists in the DB, so it self-heals — no further duplicate notifications).
