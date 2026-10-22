# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Monitor de Concursos is a hybrid AI-first & deterministic web scraping system that monitors public competition postings across three complementary sources: **Gran Cursos Online** (blog), **PCI Concursos by cargo** (`/cargos/<slug>`), and **PCI Concursos Nacional** (`/concursos/nacional/`). It combines deterministic parsing for high-volume structured listings with LLM extraction (via LangChain, three selectable backends) for prose blocks and area classification — including a controlled-vocabulary contest `fase` — then sends relevant notifications via Telegram. Supports multi-area monitoring (`TI`, `EDUCACAO`, `SOCIOLOGIA_ARTES`, ...) with per-area Telegram chat routing.

See `PLANO_EVOLUCAO_AGENTICA.md` (v2, 22/10/2026) for the planned evolution: Gran via the WordPress REST API (replaces the frozen curated articles, no Playwright), deep-dive cargo/salary/benefits extraction, and a fail-open regional salary eligibility rule rolled out in shadow mode first. `browser-use` self-healing selectors are deferred to the backlog with an explicit entry criterion.

## Running

```bash
# Setup (Linux/Mac; on Windows Git Bash use .venv/Scripts/activate)
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure .env from .env.example, then run a single scan
python main.py
python main.py --dry-run                  # simulate without DB writes or Telegram
```

`main.py` is **single-run**: one scan across all configured areas, then exit (0 on success, 1 on error). Daily scheduling is done by the OS:

- **Windows**: `scripts/install_schedule.ps1` registers a Task Scheduler task calling `scripts/run_daily.bat`.
- **Linux**: `scripts/install_schedule.sh [MINUTO]` installs an **hourly** crontab entry (minute 20 by default) plus an `@reboot` one, both calling `scripts/run_daily.sh`. The script keeps a daily success marker (every tick after the day's first success is a 3-line no-op), a `flock` against overlap, and a dead-man's-switch that pings Telegram when the last successful scan is older than `MONITOR_MAX_DIAS_SEM_RODAR` days.

  **Editing the script is not deploying it.** The hourly design landed 08/08/2026, but the installer was never re-run, so the live crontab stayed `00 03 * * *` for a month — no catch-up, no `@reboot`, and the "retry next hour" wording in every alert was fiction. 35 of the 90 days ending 09/09/2026 had no scan at all. After changing scheduling, run the installer and confirm with `crontab -l`.

Ollama is only required if `LLM_MODEL` is a plain name like `llama3.1`. See "LLM backends" below.

## Tests

```bash
pip install -r requirements-dev.txt
pytest                                    # full suite (295 tests)
pytest tests/test_concurso_bot.py -v      # one file
pytest -k "TestExecutarFlow"              # by name pattern
pytest --cov=src --cov=config             # with coverage
```

All external dependencies are mocked — tests do not require Ollama, an API key, `claude` CLI, or network. `tests/conftest.py` inserts the project root into `sys.path` so `from src.core.bot import ...` works.

## Architecture

**Pipeline flow**: `main.py` builds one `ConcursoBot` per target from `config/loader.py` → `MultiAreaRunner` → each `ConcursoBot` → **sources** (`GranScraper`, `PciScraper`, `PciNacionalScraper`) → `IntelligenceUnit` (Gran + new nacional items) → `DatabaseManager` → `TelegramNotifier`

**Three sources, one decision path.** They differ only in how a candidate becomes a data dict:

| | Gran | PCI by cargo | PCI nacional |
| --- | --- | --- | --- |
| URL | one blog page per area | `/cargos/<slug>` | `/concursos/nacional/` |
| Page shape | prose in HTML | structured list | structured list |
| Needs the LLM? | **yes**, one call per block | **no**, deterministic parse | **only for a NEW item**, to judge area fit |
| Volume | ~45 blocks | 50–1000+ items | ~4–15 items |
| Covers | large state/federal | municipal, autarquias, conselhos | **estatal federal** (Dataprev, Transpetro, Correios) |

The `professor` slug alone lists 1000+ concursos, which is why the cargo pages must stay deterministic — LLM at CLI latency would take hours. The nacional page is the opposite: a dozen items whose cargo column usually just says "Vários Cargos", so the LLM is the only way to tell whether it is this area's concurso, and it is affordable. Everything downstream of the data dict — decision matrix, dedup, buttons — is shared.

**Why the third source exists (09/2026)**: the Dataprev concurso (1,823 vagas, 1,793 of them Analista de TI, inscriptions 06/07–06/08/2026) never reached the user. Post-mortem found it appeared in *neither* existing source — the Gran TI article was frozen (below) and six Hermes sweeps of the PCI cargo slugs inside the inscription window never listed it. `/concursos/nacional/` is where that class of concurso lives.

1. **GranScraper** (`src/scrapers/gran_scraper.py`) slices page HTML into blocks — does NO data extraction. Default mode slices by `<h3>` tags; URLs containing `/cursos/carreira/` use a separate path that slices by `<h3>`/`<h4>` section headings plus `<li>` items and filters hardcoded section names (see `_CARREIRA_SECOES` / `_RUIDO_MARCADORES`).
2. **PciScraper** (`src/scrapers/pci_scraper.py`) reads `https://www.pciconcursos.com.br/cargos/<slug>` for each slug in `pci_slugs`, parsing the `ul.link-d` + `ul.link-i` pairs into finished data dicts. The `nXXXXXX` in the anchor's CSS class is the PCI news id — stable across runs, stored as `pci_id`, and the strongest dedup key available. The cargo page never carries the registration deadline, so `enriquecer()` fetches the news page once **per new item only** and extracts the deadline by regex, scoped to the sentence mentioning "inscrições" (a news page also mentions isenção and prova dates; taking the max over the whole text would return the exam date).
2b. **PciNacionalScraper** (`src/scrapers/pci_nacional_scraper.py`) reads `https://www.pciconcursos.com.br/concursos/nacional/`, one `div.ca` per concurso. Two differences from the cargo pages shape the design: there is **no `nXXXXXX`**, so `pci_id` is None and identity is the news `link` (the same canonical URL the cargo pages use, so the two doors dedup against each other); and the **deadline is in the listing** ("Inscrição até"), so fase and prazo are deterministic without opening the news. `_fase` derives from that window and only falls back to the title verb — the opposite precedence from `PciScraper`, because "Transpetro publica editais retificados" would score `edital_publicado` while the deadline on the same row says inscriptions are open. Per-target flag `pci_nacional`, default off. Shared date/fase helpers live in `src/scrapers/pci_comum.py`.

3. **ConcursoBot** (`src/core/bot.py`) orchestrates per-area: pending Telegram callbacks → per source, candidate → data dict → DB lookup → **fase-based decision matrix** (`_decidir_e_notificar`, no second LLM call) → notification. The keyword pre-filter (`_passa_filtro_palavras`) applies to Gran blocks and runs on **visible text**, not raw HTML — see "Key Design Decisions".
   - The nacional source (`_varrer_nacional`) costs nothing in steady state: an item already in the DB is refreshed from the listing with no request and no LLM; an item judged off-area is remembered for 30 days in `data/pci_nacional_descartados.json` (keyed by area+link, re-judged if the deadline changes) so the same "not TI" is not re-derived daily. Only a genuinely new item opens the news page and spends one LLM call. The LLM decides **only area fit** — `link`, `fase` and `data_fim_inscricao` keep the listing's deterministic values, because letting the LLM pick the link is what duplicates rows.
   - End-of-cycle: a 🔑 *LLM without login* alert when the Claude CLI lost its credential (`IntelligenceUnit.falha_autenticacao`), else a 🚨 *degraded* alert when ≥20% of blocks were lost in extraction (`LIMITE_ERRO_EXTRACAO`), else a ⚠️ blind-scan alert when the scan produced no candidates at all, else heartbeat. Degraded is checked first: 10 blocks with 5 lost is loss, not blindness. Blind = zero raw blocks with no alternate source, OR zero candidates on a target WITHOUT `keywords_include`. Filtered targets on generic pages treat zero valid as a normal quiet day.
   - Every bot alert is rate-limited to **one per area per day** (`_alerta_uma_vez_por_dia`, marker in `logs/.alerta_<area>_<tipo>`): blind scan, degraded, crash, sick source. The cron runs hourly and a failed run is retried, so any persistent cause would otherwise send 24 identical messages — which is exactly what the degraded alert did from 14/10 to 22/10/2026 before it was limited. The 🔑 login alert is limited **globally** (`por_area=False`, marker `logs/.alerta_global_<tipo>`): the credential belongs to the machine, and the Educação/Soc-Artes chats must not get copies of a terminal instruction. The dead-man's-switch in `run_daily.sh` has its own daily marker (`logs/.last_dead_man_alert`) for the same reason.
   - **Per-source diagnosis** (`_alertar_fontes_doentes`, backed by `src/utils/saude_fontes.py`) runs *after* `_mensagem_final` and only when the aggregate stayed quiet — the aggregate alert wins, so one problem never sends two messages. It flags a source that returned **nothing** (🕳️) or that has returned **identical content for more than `dias_fonte_parada` days** (🧊, default 21). Neither sets `bot.falhou`: a frozen or dead source is not fixed by retrying, and marking failure would make the hourly catch-up burn LLM on the other sources all day. State lives in `data/saude_fontes.json`, keyed `<area>::<fonte>`; the digest is built from **visible text** (Gran) or ids/links (PCI) and is order-insensitive, so a reshuffled page does not read as an update.
   - `bot.falhou` is set by any failure. `MultiAreaRunner.executar()` returns False if any area failed, `main.py` exits 1, and `run_daily.sh` then does NOT write the success marker — so the next hourly tick retries.
4. **IntelligenceUnit** (`src/intelligence/langchain_unit.py`) runs the extraction chain over the backend selected by `_detect_backend(model_name)`: HTML block → `{ignorar, nome, status, link, data_fim_inscricao, data_referencia, fase}`. The system prompt receives `area_context` + include/exclude keywords so the LLM rejects off-area blocks. `fase` is one of 6 literals (see "Fase vocabulary"); `data_referencia` is the most relevant event date (ISO; month/year → first day; null when no date). Both are sanitized post-parse (`sanitizar_fase`, `_sanitizar_data`). Retries on failure (`LLM_RETRIES`, `LLM_RETRY_DELAY_S`), and surfaces JSON wrapped in markdown fences via `_parse_json_response`. On final failure it returns `{"ignorar": True, "erro": True}` — the `erro` flag is what lets the bot tell a *lost* edital from an irrelevant block.
5. **MultiAreaRunner** (`src/core/multi_area_runner.py`) runs the bots sequentially each cycle and aggregates failure.
6. **Scheduling is external.** `main.py` does NOT have an internal loop. On Linux, cron runs `scripts/run_daily.sh` **hourly**; the daily marker + `flock` make every tick after the first success a no-op. Hourly is deliberate — see "Key Design Decisions".

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
| `zai/glm-5.3-flash`, `anthropic/claude-haiku-4-5-...`, `openai/gpt-4o`, any `provider/model` | LiteLLM (API) | `_create_litellm` |
| `claude-cli` or `claude-cli:haiku` \| `:sonnet` \| `:opus` | Claude Code CLI | `_create_claude_cli` → `src/intelligence/claude_cli_backend.py` |

The Claude CLI backend (`ClaudeCliLLM`) wraps `claude -p --model <alias> --output-format text --no-session-persistence`, piping the prompt on stdin (NOT argv — avoids Windows cmd length limits and escaping issues with Portuguese). It does not support JSON mode, relying on prompt instructions + `_parse_json_response` to handle fenced or inline JSON.

**z.ai (GLM) via LiteLLM** (`LLM_MODEL=zai/glm-5.3-flash`, key in `ZAI_API_KEY`). Two things are not obvious:
- LiteLLM's `zai/` adapter (1.95 on the notebook) does not declare `response_format` or `reasoning_effort`, and refuses the call if they come as normal params. `_create_litellm` sends both in `extra_body` for providers listed in `_PROVEDORES_VIA_EXTRA_BODY`.
- GLM-5.3-Flash cannot turn thinking off, and the API default is `reasoning_effort=max`. Set `LLM_REASONING_EFFORT=low`.

Optional `LLM_API_BASE` / `LLM_API_KEY` point `openai/<model>` at any OpenAI-compatible endpoint. Subscriptions sold for coding agents (OpenCode Go, GLM Coding Plan) treat other traffic as abuse in their terms, so they are documented as not recommended. `python main.py --testar-llm` makes one real call with the production wiring and exits 0/1. Use it after changing model or credential instead of waiting for a ~13 min scan.

**Credential failure.** `claude` prints auth errors ("Failed to authenticate: OAuth session expired and could not be refreshed") on **stdout** with exit 1 and an empty stderr. `ClaudeCliLLM` raises `ClaudeCliAuthError` for those. `_e_falha_de_credencial` also catches LiteLLM/OpenAI `AuthenticationError`/`PermissionDeniedError` a missing key (LiteLLM raises it as `InternalServerError: Missing credentials`) and z.ai's insufficient balance (code 1113). `IntelligenceUnit` then stops calling the LLM for the rest of the run (no retry — a credential is not fixed by retrying), and the bot sends the 🔑 alert, with the fix for the active backend (`instrucao_login`), instead of "Varredura incompleta". The run still sets `bot.falhou`, so the hourly catch-up recovers within an hour of a new login.

Incident that motivated this: **no successful scan from 23/09 to 22/10/2026.** The OAuth session on the notebook expired on 24/09 (again on 03/10 and from 14/10 on); in between, 25/09–02/10, the notebook had no DNS at all. The log only said `claude -p saiu com codigo 1:` followed by nothing, ~6,800 times a day. The durable fix is a long-lived token: run `claude setup-token` on the notebook and put it in `CLAUDE_CODE_OAUTH_TOKEN` inside `~/concursos-secrets/monitor.env` (`main.py` loads it into the environment the `claude` subprocess inherits). Interactive `/login` sessions expire and need a refresh that can fail.

## Configuration

**Logs never carry the Telegram token.** `src/utils/logger.py` installs `FormatterSemSegredos`, which redacts `<id>:<token>` from every formatted line, tracebacks included. Before it, a network error put the Bot API URL — token included — into 9 log files (25/09–02/10/2026), in a folder the Hermes container mounts. Rotate the token if logs from before this fix were ever readable elsewhere.

Config is via a dotenv file. **It does NOT live in the repo folder** — the repo is mounted read-write into the Hermes agent container, which is reachable over Telegram (prompt-injection surface), so secrets stay outside anything the agent can read. Same pattern as `~/agenda-secrets` for the AgenteAgenda bot.

`main.py` loads `MONITOR_ENV_FILE` if set, falling back to `.env` for local development. `scripts/run_daily.sh` exports `MONITOR_ENV_FILE=$HOME/concursos-secrets/monitor.env`. Two modes:

- **Multi-area** (recommended): `MONITOR_TARGETS_JSON` — JSON array of area configs with `area`, `url`, `chat_ids`, `keywords_include`, `keywords_exclude`, `pci_slugs`, `pci_primeira_carga`. **Must be on a single line** — python-dotenv does not support multiline values, so pretty-printing the JSON will silently break loading and fall through to legacy mode.
- **Legacy single-area**: `URL_ALVO` + `TELEGRAM_CHAT_ID` + `KEYWORDS_INCLUDE` + `KEYWORDS_EXCLUDE` (+ `PCI_SLUGS`, `PCI_PRIMEIRA_CARGA`). Used as fallback when `MONITOR_TARGETS_JSON` is missing or fails to parse.

**PCI fields** (per target):

- `pci_slugs` — cargo slugs to fetch. Empty/absent disables PCI for that area. Live values as of 2026-08-08: TI 8 slugs (60 órgãos), EDUCACAO 5 (220), SOCIOLOGIA_ARTES 4 (56).
- `pci_nacional` — `true` turns on the `/concursos/nacional/` source for that target. **Default off.** Live value as of 2026-09-09: TI only. Turning it on for another area costs one LLM call per new item on that page (~4–15 items today), once.
- `dias_fonte_parada` — days of identical content before a source is reported frozen (default 21, see `src/utils/saude_fontes.py`).
- `pci_primeira_carga` — what to do the FIRST time PCI runs in an area, when dozens or hundreds of editais arrive at once. `individual` (default, one card each), `resumo_uf` (one message per state), `silencioso` (seed the DB only). Detected from the DB (`contar_por_fonte('pci') == 0`), not from a flag file. From the second run on, always the normal one-card-per-novelty flow. Invalid values fall back to `individual` with a warning — a typo must never turn into silence.

Model selection: `LLM_MODEL` takes precedence over `OLLAMA_MODEL` (main.py uses `os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL", "llama3.1")`). Routing rules in the "LLM backends" section above. Timeout/retry vars are `LLM_TIMEOUT_S` / `LLM_RETRIES` / `LLM_RETRY_DELAY_S`; the old `OLLAMA_*` names still work as aliases (the backend in production is `claude -p`, so the Ollama naming was misleading).

Config loading logic is in `config/loader.py`.

## Database

SQLite at `data/concursos.db` (path anchored to the repo root via `__file__`, not relative to cwd). Table `editais` (schema v5):

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
| `fonte` | TEXT NULL | v5. `gran` \| `pci` \| `pci_nacional`. Pre-v5 rows backfilled to `gran` (the only source that existed). First-load detection counts `pci` only |
| `pci_id` | TEXT NULL | v5. PCI news id, the strongest dedup key. Indexed on `(area, pci_id)`. Always NULL for `pci_nacional` — that page does not carry the id, so those rows dedup by `link` |
| `ultima_atualizacao` | TIMESTAMP | Auto-updated on every upsert |

**Identity resolution** (`buscar_registro`, strongest first) — one order shared by lookup and upsert:

1. `pci_id` — stable across runs.
2. Specific `link` (different from the scraper's index URL).
3. `(area, nome)` COLLATE NOCASE — the LLM varies capitalization.
4. `mesma_entidade(nome_a, nome_b)` (`src/utils/text.py`) — the only step that crosses sources, since Gran and PCI spell the same órgão differently ("Prefeitura de Ponta Grossa - PR" vs "Concurso Prefeitura Ponta Grossa"). It compares only **discriminating** tokens, subtracting generic org types (`TIPOS_ORGAO`), and refuses a match when both names carry a UF and the UFs differ. Without that, "Prefeitura de Ponta Grossa" and "Prefeitura de Ponta Porã" would share `{prefeitura, ponta}` and merge.

When a name collision turns out to be the same órgão, `_fundir` merges the rows instead of leaving both. The user's `estado_usuario` wins by priority (`seguindo` > `ignorado` > `ativo`) from either row — an automatic merge must never discard a manual ⭐.

Auto-migrates v1 (PK `nome`) → v2 (PK `(area, nome)`) → v3 (`id` autoincrement) → v4 (adds `fase`) → v5 (adds `fonte`, `pci_id` and `(area, pci_id)` index) on startup; legacy v1 rows are tagged with area `TI`. `atualizar_concurso` uses `COALESCE(?, fase)` so updates without a fase never erase a stored one. Connection opened with `check_same_thread=False`. Manager in `src/database/manager.py`.

`atualizar_concurso` does explicit UPDATE-if-exists (by `pci_id` / `link` if specific, else by `(area, nome)` / `mesma_entidade`) before INSERT — this preserves `id` between runs, which is required for the Telegram callback buttons to stay valid.

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
- **A source can rot while the scan looks fine**: the blind-scan alert is aggregate, so once a second source existed the first could return zero — or return the same thing forever — in silence. That is exactly what happened: `concursos-ti/` is a curated article whose `dateModified` is stuck at 12/06/2026, and it served the same 45 blocks from 06/07 to 09/09. Per-source health (`saude_fontes`) is the answer, and it deliberately does not mark the run as failed.
- **Never mask a blind scan**: zero raw blocks always alerts ⚠️. Zero valid extractions alerts only on targets without `keywords_include`; on filtered targets in generic pages that is a normal quiet day (heartbeat), because the include filter discarding everything is expected.
- **Three LLM backends**: Ollama (local, no slash), LiteLLM (API, with slash), Claude Code CLI (prefix `claude-cli`). Selection is purely by `LLM_MODEL` string format — no extra env var needed.
- **Keyword pre-filtering** happens before LLM calls to save compute — applied at bot level (`_passa_filtro_palavras`) AND reinforced inside the extraction prompt.
- **All code, logs, prompts, and Telegram messages are in Brazilian Portuguese** — keep this when editing.
- **BaseScraper** (`src/scrapers/base_scraper.py`) is abstract — extend it for other websites.
- **Graceful degradation**: missing Telegram config logs a warning and skips notifications; bad HTML blocks return `{"ignorar": True}` rather than raising; Telegram callback failures never block the scrape.
- **Dedup gap (mitigated)**: when a block contains both a blog link and a course-page link, the LLM may pick a different one across runs, creating a duplicate row. Mitigations: extraction prompt rule 3 forces a stable choice (shortest `blog.grancursosonline.com.br` path, never the `www` course page), and the `(area, nome)` DB fallback is `COLLATE NOCASE` (LLM capitalization varies, e.g. "SEDUC AL" vs "Seduc AL"). Residual risk: the LLM invents a substantially different `nome` AND link in the same run.
- **Frozen Gran targets**: the blog's area pages are curated articles, not feeds, and Gran does update them — but not always. Checked 09/09/2026: `concursos-ti/` `dateModified` 12/06 (89 days), `concursos-educacao/` 08/08, `concursos-abertos/` 08/09. Before blaming the scraper for missing a concurso, `curl` the target and grep `dateModified`. `concursos-abertos/` is NOT a usable TI substitute: its 135 blocks carry banca, dates, vagas and salário but **no cargo**, which is why the filtered SOCIOLOGIA_ARTES target on it has produced exactly one `gran` row in three months.
- **Dead carreira pages**: `/cursos/carreira/*` pages became JS-rendered in June 2026 (empty HTML to scrapers) — do not use them as targets. Blog listing pages (`concursos-ti/`, `concursos-educacao/`, `concursos-abertos/`) remain static and scrapeable; coverage for filtered niches (Sociologia/Artes/Licenciaturas) comes from a filtered target on `concursos-abertos/`.
