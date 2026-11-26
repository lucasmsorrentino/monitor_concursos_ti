APROVADO
Esteira: revisor · agy-neon (gemini-4-neon) · nível M- · esforço medium · 2026-11-26 13:06 → 2026-11-26 13:12 (6 min)
Resumo: A entrega cumpre todos os critérios de aceite do T-022 (SPEC-003 R-89 e R-90, ADR-0004). O `scripts/run_daily.sh` honra `logs/.retry_nao_antes` antes do `flock`, ao lado do marcador do dia, com saída quieta de 1 linha e comportamento fail-open validado por 9 testes independentes em `tests/test_run_daily.py`. O ciclo TDD foi seguido na ordem correta e o vermelho do commit `test:` foi reproduzido em worktree destacado.
Arquivos: `scripts/run_daily.sh` (toca) · `tests/test_run_daily.py` (toca) · `README.md` (FORA do toca — 1 linha na árvore de scripts, justificada no relatório do implementador)
Commits:
- `6edb2e3` chore: run_daily.sh aceita REPO_DIR do ambiente (costura dos testes)
- `ad11a9c` test: run_daily.sh honra marcador de espera antes de rodar o catch-up
- `5b95e71` feat: catch-up horario sai sem rodar antes do reset da cota da LLM
- `b7c7657` docs: espera do reset da cota no cabecalho do run_daily.sh e no README
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs` → base 582 passed / 0 failed (0 skipped, 58.02s; implementador: 582 passed / 0 failed) · ponta 591 passed / 0 failed (0 skipped, 62.65s; implementador: 591 passed / 0 failed). Vermelho (`ad11a9c`): `pytest tests/test_run_daily.py -v` → 4 failed / 5 passed (4.75s; implementador: 4 failed / 5 passed). Lint: (não configurado) — não rodou. Condição: Windows com Git Bash disponível, `MONITOR_ENV_FILE` apontado para arquivo inexistente em `tmp_path`, sem marcadores pytest extras.
Testes que nascem verdes: `test_marcador_de_espera_no_passado_roda`, `test_marcador_de_espera_ilegivel_roda[vazio|lixo|data_invalida]` e `test_marcador_de_espera_ausente_roda` — guardas de fail-open (antes do `feat:`, o script ignorava o marcador e rodava de qualquer forma); declarados corretamente no relatório do implementador.
Desvios e riscos:
- `README.md` fora do `toca` (1 linha de documentação na árvore de scripts), devidamente justificado no relatório do implementador.
- Colocação do bloco de espera antes do dead-man (`scripts/run_daily.sh:70-77`): cumpre literalmente «junto da checagem do marcador do dia» e «antes do `flock`», sem alterar `.last_success_date` nem zerar a contagem de dias sem sucesso. Durante a janela de espera o dead-man não dispara; volta a valer no primeiro tick após o reset, coerente com o alerta de cota (R-88).
- `NAO_ANTES` vazio depende do comportamento do GNU `date -d "" +%s` devolver `00:00:00` do dia local (`<= now`), em vez de um curto-circuito explícito `[[ -n "$NAO_ANTES" ]]`; continua fail-open inclusive exatamente às `00:00:00` porque a comparação `>` é estrita.
Pendências: Nenhuma para este ticket; a escrita de `logs/.retry_nao_antes` fica a cargo do ticket da cota.

## Spec

- **Critérios de aceite:** todos os 6 itens cumpridos e cobertos por testes:
  1. Marcador no futuro sai sem rodar (`scripts/run_daily.sh:70-77`; `tests/test_run_daily.py:101-109` e `164-170`).
  2. Marcador ausente, vazio, ilegível ou com data inválida não impede a varredura (`scripts/run_daily.sh:70-73`; `tests/test_run_daily.py:121-139`).
  3. Marcador no passado não impede a varredura (`scripts/run_daily.sh:73`; `tests/test_run_daily.py:112-118`).
  4. Checagem antes do `flock`, junto do marcador do dia (`scripts/run_daily.sh:70-77`, logo após `58-60` e antes de `115-118`; `tests/test_run_daily.py:109` garante que `.run_daily.lock` nem é criado).
  5. Dead-man preservado: o tick de espera não grava `.last_success_date` nem zera dias sem sucesso (`scripts/run_daily.sh:75` sai antes da linha `131`; `tests/test_run_daily.py:142-151`).
  6. Saída quieta de no máximo uma linha por tick (`scripts/run_daily.sh:74`; `tests/test_run_daily.py:154-161`).
- **Escopo:** `git diff --stat 86be955..HEAD` toca `scripts/run_daily.sh`, `tests/test_run_daily.py` e `README.md` (1 linha de documentação fora do `toca`, justificada no relatório). Nenhum gancho especulativo; `REPO_DIR` via ambiente (`scripts/run_daily.sh:31`) atende diretamente à costura definida no plano de testes e é neutro em produção. `dead-man`, `flock`, `install_schedule.*`, `kanban/` e `.env` intocados.
- **Alinhamento com spec e ADRs:**
  - `docs/specs/SPEC-003-identidade-do-concurso-e-cota-da-llm.md:160-162` (R-89 e R-90): cumpridos.
  - `docs/adr/0004-fuso-do-banco-e-do-log.md:14,28-29`: instante sem fuso assume fuso local da máquina via `date -d`; instante com offset explícito é convertido antes da comparação; log em hora local.
  - Dependência T-021 já presente na base (`d25735a` ancestral de `HEAD`).

## Prova

- **Números medidos vs. relatório do implementador:**
  - Base (`86be955`, medido em worktree destacado): `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs` → **582 passed / 0 failed / 0 skipped** (58.02s). Implementador: 582 passed / 0 failed.
  - Ponta (`b7c7657`): `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs` → **591 passed / 0 failed / 0 skipped** (62.65s). Implementador: 591 passed / 0 failed (0 skipped).
  - Conta fecha: 582 + 9 = 591.
- **TDD:** histórico `6edb2e3` (`chore:`) → `ad11a9c` (`test:`) → `5b95e71` (`feat:`) → `b7c7657` (`docs:`), com documentação separada do código. Vermelho verificado em worktree destacado no commit `ad11a9c` (`pytest tests/test_run_daily.py -v`): **4 failed, 5 passed** (4.75s), todas as 4 falhas por `AssertionError` (sem erro de coleta, importação ou sintaxe).
- **Qualidade dos testes:** exercitam o comportamento pela costura especificada (`scripts/run_daily.sh` via `subprocess` sobre árvore temporária, no molde de `tests/test_diagnostico_producao.py`), usam oráculos literais/relativos independentes e limitam dublês à fronteira (`main.py` e `flock` ausente no Git Bash). Sem testes acoplados à implementação, tautológicos ou com dublês internos. (Observação menor: `tests/test_run_daily.py:160` assume que o arquivo de log existe com 1 linha; se um dia o script sair com 0 linhas, precisaria tolerar arquivo ausente — não afeta a validade da prova atual.)

## Padrões

- **Regras do projeto:** sem segredos, sem dependências novas, sem acesso à rede nos testes, sem IDs `T-NNN` em código, comentários ou README.
- **Notas menores (não bloqueantes):**
  - `tests/test_run_daily.py:78-80`: o comentário na linha 79 tem um acento (`ganhando lá.`) fora da convenção de comentários sem acento e diz «no fim do PATH» enquanto a linha 80 concatena `raiz / "bin"` no início do `env["PATH"]` (ele só passa para depois dos diretórios de sistema quando `scripts/run_daily.sh:46` reescreve `PATH`).
  - `scripts/run_daily.sh:71-72`: `[[ -n "$NAO_ANTES" ]]` tornaria o fail-open para arquivo vazio explícito em vez de depender de `date -d "" +%s` devolver `00:00:00`.
- **Cheiros de código:** nenhum cheiro relevante encontrado no diff.
