APROVADO
Esteira: revisor · agy-argon (gemini-4-argon) · nível M- · esforço medium · 2026-11-23 18:09 → 2026-11-23 18:15 (6 min)
Resumo: Revisão da entrega do script `scripts/diagnostico_producao.sh`, da documentação `docs/DIAGNOSTICO.md` e da suíte `tests/test_diagnostico_producao.py`. Os 7 critérios de aceite (8 seções, saída `0`, omissão de segredos em `.env`, `monitor.env` e `MONITOR_TARGETS_JSON`, somente leitura, fallback `sqlite3` → `python3`, degradação para `ausente` e guia de uma página) foram cumpridos e verificados por medição independente na base, no commit vermelho, na ponta e por mutação.
Arquivos:
  - scripts/diagnostico_producao.sh (toca)
  - docs/DIAGNOSTICO.md (toca)
  - tests/test_diagnostico_producao.py (FORA do toca — autorizado pela decisão do arquiteto no ticket e exigido pelo plano de testes)
Commits:
  - b667dce chore: esqueleto do script de diagnostico da producao (secoes nao implementadas)
  - 546f5e1 test: diagnostico da producao precisa reportar as 8 secoes, sobreviver a arvore vazia e omitir segredo
  - ec89a36 feat: diagnostico da producao coleta evidencia dos ultimos 30 dias sem vazar segredo
  - 33af986 docs: guia do diagnostico da producao (como rodar, o que cada secao significa, sinais de problema)
Testes: "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q → base 296 passed / 0 failed · ponta 308 passed / 0 failed (0 skipped; condição: Windows com Git Bash disponível e venv no PATH do subprocesso; lint: não configurado)
Testes que nascem verdes: test_config_efetiva_mostra_areas_e_omite_segredo_do_json (1 guarda adicionada no commit feat `ec89a36` para cobrir omissão de `token` e `chat_ids` dentro de `MONITOR_TARGETS_JSON`, declarada no relatório do implementador e validada por mutação nesta revisão)
Desvios e riscos:
  - Caminho de fallback `PY_BANCO` (Python `sqlite3` em `mode=ro`) só entra quando o binário `sqlite3` não está no `PATH`; nesta máquina o CLI `sqlite3` está presente.
  - Em `tests/test_diagnostico_producao.py:_rodar`, a variável `MONITOR_ENV_FILE` não é isolada para dentro de `tmp_path` (apenas `MONITOR_TARGETS_JSON` é removida do ambiente); se a máquina que rodar a suíte possuir `~/concursos-secrets/monitor.env`, o subprocesso lerá os nomes de chaves desse arquivo real.
  - Em `scripts/diagnostico_producao.sh:393`, `sed -E 's/=.*/=<omitido>/'` mascara qualquer linha `CHAVE=valor`, mas linhas sem `=` (como comentários livres) passariam sem substituição.
Pendências:
  - Executar `bash scripts/diagnostico_producao.sh` no notebook de produção (`lucas-inspiron-3583`) e analisar a saída coletada (SPEC-001 seção 8).

## Spec

1. **Cumprimento do aceite:**
   - **Execução a partir da raiz e saída `0` (`scripts/diagnostico_producao.sh:29,411`):** resolve `RAIZ` a partir de `BASH_SOURCE[0]/..` quando sem argumento, aceita raiz alternativa para teste e encerra com `exit 0`. Provado por `test_script_sai_com_zero_em_arvore_minima` e `test_sem_logs_nem_banco_nao_quebra`.
   - **8 seções exigidas (`scripts/diagnostico_producao.sh:140-396`):**
     1. *Identidade* (`secao_identidade`, linhas 140–157): data/hora, host, commit curto, branch e estado da árvore git.
     2. *Último sucesso* (`secao_ultimo_sucesso`, linhas 160–176): lê `logs/.last_success_date` e calcula idade em dias. Provado por `test_le_ultimo_sucesso_e_calcula_dias`.
     3. *Saúde por dia, últimos 30 dias* (`secao_saude_por_dia`, linhas 181–226): percorre a janela de 30 dias, extrai código de saída (`Finalizado com codigo N` ou `exit=N`) e soma `novos` e `atualizacoes` das linhas `Ciclo finalizado:` (compatível com `src/core/bot.py:631` e `logs/run_20260610.log:404,409`), marcando dia sem arquivo como `ausente`. Provado por `test_lista_dia_com_exit_zero_e_dia_com_exit_um` e `test_dia_sem_log_aparece_como_ausente`.
     4. *Erros recorrentes* (`secao_erros_recorrentes`, linhas 247–268): filtra `ERROR` e `CRITICAL` nos logs da janela de 30 dias, mascara eventuais tokens antigos no formato `<id>:<hash>` (`src/utils/logger.py:17`, pendência 2 do `HANDOFF.md:28`), normaliza números variáveis para `N` e agrega o top 15 com `sort | uniq -c | sort -rn | head -15`. Provado por `test_agrupa_erros_repetidos_com_contagem`.
     5. *Falha de credencial* (`secao_credencial`, linhas 274–297): conta ocorrências diárias do marcador `🔑` (`$'\xf0\x9f\x94\x91'`, emitido em `src/core/bot.py:554`). Provado por `test_conta_chave_ausente_por_dia`.
     6. *Banco* (`secao_banco`, linhas 302–331): consulta `data/concursos.db` em modo somente leitura (`sqlite3 -readonly` ou `python3` com `mode=ro`), exibindo total de linhas, contagens por `area`, `fonte` e `estado_usuario`, e `MAX(ultima_atualizacao)`. Provado por `test_conta_linhas_do_banco_por_area_e_fonte`.
     7. *Agendamento* (`secao_agendamento`, linhas 334–361): filtra `crontab -l` por `monitor_concursos|run_daily` e verifica processos ativos com `pgrep -af 'main\.py|run_daily\.sh'`. Provado por `test_imprime_as_oito_secoes`.
     8. *Config efetiva* (`secao_config`, linhas 368–396): interpreta `MONITOR_TARGETS_JSON` (do ambiente ou de `MONITOR_ENV_FILE`) imprimindo áreas e portas com `token` e `chat_ids` substituídos por `<omitido>`, e lista as chaves de `.env` e `monitor.env` com `=<omitido>`. Provado por `test_nao_imprime_token` e `test_config_efetiva_mostra_areas_e_omite_segredo_do_json`.
   - **Somente leitura e degradação graciosa:** nunca cria nem altera arquivos (inclusive usando `-readonly` / `?mode=ro` no SQLite para não criar journal/wal/shm) e degrada para `ausente:` quando faltam pastas, arquivos ou utilitários. Provado por `test_nao_escreve_nada` e `test_sem_logs_nem_banco_nao_quebra`.
   - **Documentação (`docs/DIAGNOSTICO.md:1-96`):** explica em uma página como rodar, o significado de cada uma das 8 seções e os sinais de problema exigidos pelo aceite.
2. **Escopo (`toca`):**
   - `git diff --stat 16543aae6eca14e52d1de0cbeb519a19f92c7e06..HEAD` toca exatamente 3 arquivos: `docs/DIAGNOSTICO.md`, `scripts/diagnostico_producao.sh` e `tests/test_diagnostico_producao.py`.
   - `tests/test_diagnostico_producao.py` está fora do `toca` original, justificado no relatório do implementador e abonado pela decisão do arquiteto registrada no ticket. Nenhum comportamento fora do escopo foi introduzido.
3. **Conformidade com a Spec e ADRs:**
   - Alinhado com `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md` (PED-01, linha 13; Seção 1, linhas 34–40; Seção 8, linhas 275–277) e com `HANDOFF.md` (linhas 12, 20–23, 28).

## Prova

4. **Números medidos pelo revisor vs. implementador:**
   - **Base (`16543aae6eca14e52d1de0cbeb519a19f92c7e06`):**
     - Implementador afirmou: `296 passed / 0 failed`
     - Medido pelo revisor (em worktree destacado): `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q` → `296 passed in 23.53s` (`0 failed`, `0 skipped`).
   - **Ponta (`33af9861d224de7e81a09572dff77db67ea7ad36`):**
     - Implementador afirmou: `308 passed / 0 failed (0 skipped nesta máquina)`
     - Medido pelo revisor: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q` → `308 passed in 50.09s` (`0 failed`, `0 skipped`).
     - Módulo isolado: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest tests/test_diagnostico_producao.py -v` → `12 passed in 25.02s`.
   - **Fechamento da conta:** `296 (base) + 12 (novos) = 308 (ponta)`. Números idênticos aos do relatório do implementador.
5. **Verificação do ciclo TDD:**
   - Log `16543aa..HEAD`: `b667dce` (`chore:` esqueleto) → `546f5e1` (`test:` 11 testes) → `ec89a36` (`feat:` implementação + 1 guarda declarada) → `33af986` (`docs:` documentação separada de código).
   - **Prova do vermelho (`546f5e1`):** medido em worktree destacado com `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest tests/test_diagnostico_producao.py -q` → `11 failed in 0.66s`. Todos os 11 testes falharam pelo motivo certo (asserções sobre `codigo == 0` recebendo `2` do esqueleto ou ausência das seções em `stdout`), sem erro de coleta, sintaxe ou importação.
6. **Qualidade dos testes e prova por mutação:**
   - Os 12 testes exercitam a costura real definida no plano (`subprocess.run` chamando `bash scripts/diagnostico_producao.sh <tmp_path>`), usam oráculos literais independentes (datas, logs e linhas SQLite inseridas à mão pelo teste) e não usam dublês fora da fronteira.
   - **Prova por mutação da guarda (`test_config_efetiva_mostra_areas_e_omite_segredo_do_json`):** em worktree destacado na ponta (`33af986`), trocou-se `print("    token: <omitido>")` por `print(f"    token: {item.get('token')}")` em `scripts/diagnostico_producao.sh:96` (confirmado via `git diff`). A execução de `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest tests/test_diagnostico_producao.py -k "test_config_efetiva_mostra_areas_e_omite_segredo_do_json" -q` resultou em `1 failed in 2.57s` (`AssertionError: assert 'XYZTOKEN' not in ...`), comprovando que a guarda detecta vazamento de token no JSON.

## Padrões

7. **Regras do projeto (`kanban/REGRAS.md` e `GLOSSARIO.md`):**
   - **Idioma e acentuação:** código, comentários e identificadores em português do Brasil sem acento; texto voltado ao usuário em `docs/DIAGNOSTICO.md` com acentuação adequada.
   - **Segredos:** nenhum segredo versionado; o script omite valores de `.env`, `monitor.env`, `MONITOR_TARGETS_JSON` e possíveis tokens vazados em linhas `ERROR`/`CRITICAL` de logs antigos.
   - **Dependências e rede:** nenhuma dependência adicionada a `requirements.txt`; nenhum teste toca a rede; `pytest.mark.skipif(BASH is None, ...)` garante que a suíte permaneça verde em ambientes Windows sem Git Bash.
   - **IDs do quadro (`T-NNN`):** `git grep -E "T-[0-9]{3}" -- scripts/ docs/DIAGNOSTICO.md tests/test_diagnostico_producao.py` retornou vazio.
   - **Git:** commits locais na branch `t/T-008-script-de-diagnostico-da-producao`, sem `push` e sem alterações nos arquivos protegidos.
8. **Cheiros de código:**
   - Nenhum cheiro relevante identificado; funções pequenas e coesas, uma por seção do relatório, seguindo o estilo de `scripts/run_daily.sh`.
