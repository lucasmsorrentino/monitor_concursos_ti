ENTREGUE
Esteira: implementador · agy-hydrogen (gemini-4-hydrogen) · nível P- · esforço medium · 2026-11-24 23:58 → 2026-11-25 00:01 (4 min)
Resumo: Criada a ADR-0004 em `docs/adr/0004-fuso-do-banco-e-do-log.md` documentando que o banco SQLite grava `ultima_atualizacao` em UTC (`CURRENT_TIMESTAMP` em `src/database/manager.py`), o log usa hora local (`setup_logger` / `FormatterSemSegredos` em `src/utils/logger.py`), e a assimetria proposital do resumo semanal em `ConcursosBot._enviar_resumo_semanal` (`src/core/bot.py`). Registradas a regra para datas futuras e a definicao do que nao sera feito (sem migracao de dados nem alteracao no log).
Arquivos: `docs/adr/0004-fuso-do-banco-e-do-log.md`
Commits: `f839804` docs: registra ADR do fuso do banco em UTC e log em hora local
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q` → base `539 passed / 0 failed` · ponta `539 passed / 0 failed` (verificacao adicional do ticket: `CURRENT_TIMESTAMP` em `src/database/manager.py` = 7 ocorrencias; `timezone.utc|date.today()` em `src/core/bot.py` = 7 ocorrencias; `T-0` em `docs/adr/0004-fuso-do-banco-e-do-log.md` = 0 ocorrencias)
Testes que nascem verdes: nenhum (ticket `docs`, sem fatia de codigo ou teste novo)
Desvios e riscos: nenhum
Pendências: nenhuma
