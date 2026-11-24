APROVADO COM RESSALVAS
Esteira: revisor · agy-neon (gemini-4-neon) · nível G- · esforço high · 2026-11-23 20:18 → 2026-11-23 20:26 (9 min)
Resumo: A entrega liga o filtro salarial na matriz de decisao de `ConcursoBot`, adiciona o resumo semanal de filtrados com marcador de semana ISO em `LOG_DIR` e corrige a checagem de cegueira para incluir `self.mcp_scraper` (decisao do arquiteto). Todos os criterios de aceite, a SPEC-001 (secoes 3.4–3.6, 4.2–4.4), a SPEC-002 (secao 1) e a ADR-0002 foram cumpridos, com 539 testes verdes e 11 de 12 mutacoes mortas. Fica ressalva menor de cobertura sobre o argumento `desde` (janela de 7 dias / formato UTC) passado a `listar_filtrados`, cuja mutacao sobreviveu, e ressalva leve de vocabulario (`varredura` em comentarios/logs novos).
Arquivos: `src/core/bot.py`, `tests/test_concurso_bot.py` (ambos dentro do `toca`; nenhum arquivo fora do `toca`)
Commits:
- `bda1c63` test: Gran vazio com a porta do MCP trazendo item nao e varredura cega
- `2a09bd2` fix: porta do MCP conta como materia-prima na checagem de cegueira
- `1760527` test: filtro salarial decide na matriz, grava a elegibilidade e poe o selo no card
- `5ff9189` test: contador de novos em zero lido pelo heartbeat, sem contar o aviso de fonte
- `17cf3b3` feat: filtro salarial na matriz de decisao, com selo no card e filtrado que volta como novo
- `825943a` test: resumo semanal dos filtrados sai uma vez por semana por area
- `d88e92b` feat: resumo semanal dos filtrados no fim da rodada, com marcador da semana ISO
- `e59387e` docs: matriz de decisao e fluxo da rodada citam o filtro salarial e o resumo semanal
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q` → base `517 passed / 0 failed` (medida pelo `integrar` em `9c12e9e`, confirmada como `git merge-base main HEAD`) · ponta `539 passed / 0 failed / 0 skipped` (`-rs -q` sem pulados; `--collect-only -q` → `539 tests collected`). Condicao: sem variaveis de ambiente adicionais nem marcadores.
Testes que nascem verdes: 4 guardas declaradas e confirmadas na reproducao do vermelho — `test_ignorado_continua_saindo_antes_do_filtro`, `test_item_do_gran_nao_e_avaliado`, `test_item_da_pagina_de_cargo_nao_e_avaliado` (em `1760527`/`5ff9189`) e `test_resumo_desligado_nao_consulta_o_banco` (em `825943a`). As tres primeiras mataram as respectivas mutacoes (M1 e M2).
Desvios e riscos:
- Risco residual ja sinalizado pelo implementador: R-12 (`inedito` para linha `'filtrado'`) so se aplica a item avaliado (`decisao is not None` em `src/core/bot.py:1008-1010`), para evitar que item nao avaliado (Gran) renotifique NOVO toda rodada ja que `COALESCE(None, 'filtrado')` preserva `'filtrado'`. Caso um concurso filtrado pelo MCP apareca depois no Gran com transicao real, sairia como ATUALIZACAO sem que o Lucas tenha visto o NOVO. Escolha defensiva adequada no escopo atual; decisao de produto fica aberta se o arquiteto quiser fechar o cruzamento entre portas.
- Mutacao M12 (`timedelta(days=7)` → `timedelta(days=1)` em `src/core/bot.py:835`) sobreviveu porque `TestResumoSemanal` nao inspeciona o argumento `desde` recebido por `listar_filtrados`. O codigo esta correto (UTC, `%Y-%m-%d %H:%M:%S`, 7 dias), mas sem trava de regressao no teste.
- O ajuste de teste `5ff9189` antes do `feat:` (troca de `len(mensagens) == 1` para `any("não encontrei nenhuma alteração" in m for m in mensagens)`) nao afrouxou o aceite: em `src/core/bot.py:721-754`, esse texto so sai quando `novos == 0 and atualizados == 0`.
Pendências:
- Atualizacao de `CLAUDE.md` (tabela da matriz de decisao e fluxo de fim de rodada) para citar o filtro salarial e o resumo semanal — fora do `toca`, fica para o ticket de docs/deploy.
- Sugestao de ticket opcional (ressalva de codigo/testes): **"Travar contrato da janela de 7 dias do resumo semanal e selo `sem_evidencia` no bot"** · nivel `P` · `toca: [tests/test_concurso_bot.py, src/core/bot.py]` (adicionar assercao sobre `desde` em `TestResumoSemanal` no formato `AAAA-MM-DD HH:MM:SS` com janela de 7 dias, cobrir selo por `sem_evidencia` na costura do bot e trocar `"varredura"` por `"rodada"` nos trechos novos de `src/core/bot.py:807,863` e `tests/test_concurso_bot.py:1331,1973`).

---

## Spec

### 1. Cumprimento do criterio de aceite

Todos os itens do aceite do ticket e a decisao adicional do arquiteto (2026-11-23 18:44) estao cumpridos:

- **Montagem de `Politica` no `__init__` e de `Candidato` em `_decidir_e_notificar`**:
  - `src/core/bot.py:132,323-345` (`_politica_de`) monta `Politica` imutavel uma vez no `__init__`, respeitando lista vazia explicita em `ufs_sem_corte`/`esferas_sem_corte` e caindo nos padroes de `Politica()` quando a chave esta ausente.
  - `src/core/bot.py:1104-1128` (`_avaliar_elegibilidade`) monta `Candidato` com `uf=dados.get("uf") or extrair_uf(nome)`, `regiao`, `esfera=esfera_de(nome)`, `teto=teto_de(dados.get("vagas_salario"))`, `cargos_total`, e `seguindo=bool(registro) and registro.get("estado_usuario") == "seguindo"`, e chama `decidir(candidato, self.politica)`.
  - Provado por `test_uf_sai_do_nome_quando_o_item_nao_traz`, `test_do_sul_notifica_mesmo_com_teto_baixo`, `test_federal_notifica_mesmo_abaixo_do_corte`, `test_estrelado_notifica_mesmo_filtravel`.
- **R-15 — so porta que carrega `regiao` e avaliada** (`SPEC-001` secao 4.3, linhas 219–222):
  - `src/core/bot.py:1118` (`if "regiao" not in dados: return None`). Conferido com `git grep -n "regiao" src/`: apenas `src/scrapers/pci_mcp_scraper.py:203` inclui a chave `"regiao"` no item (mesmo quando `None`, permitindo o caso `nao_verificado`). Gran, pagina de cargo e lista nacional nao trazem `"regiao"` e passam sem avaliacao, sem selo e sem gravar colunas v6.
  - Provado por `test_item_do_gran_nao_e_avaliado` e `test_item_da_pagina_de_cargo_nao_e_avaliado`.
- **Ordem dentro de `_decidir_e_notificar`**:
  - `estado_usuario == 'ignorado'` sai em `src/core/bot.py:962-964` sem tocar o banco; a avaliacao de elegibilidade ocorre em `src/core/bot.py:969-992`, antes de `inativo`, `inedito` e transicoes (`src/core/bot.py:994+`).
  - Provado por `test_ignorado_continua_saindo_antes_do_filtro`.
- **R-11 — item filtrado salva em silencio e devolve `"skip"`** (`SPEC-001` secao 4.3, linhas 213–214):
  - `src/core/bot.py:982-992` grava `elegibilidade="filtrado"`, `motivo_filtro=decisao.motivo` e todas as 7 colunas v6, loga em `info` nome, motivo e teto (`src/core/bot.py:986-989`), retorna `"skip"` antes de `_coletor_carga` (`src/core/bot.py:1024`) e nao incrementa `novos_cont` nem `atualizados_cont`.
  - Provado por `test_filtrado_nao_notifica_e_salva_em_silencio` e `test_municipal_inflado_nao_notifica`.
- **Item que entra e sete colunas v6** (`SPEC-001` secao 3.5, linhas 147–148):
  - `src/core/bot.py:955,973-981` passa `uf`, `regiao`, `esfera`, `cargos_total`, `salario_teto`, `elegibilidade`, `motivo_filtro` em toda chamada a `salvar(...)` para item avaliado — nomes conferidos contra `DatabaseManager.atualizar_concurso` (`src/database/manager.py:364-370`).
- **R-12 — filtrado que passa a entrar sai como NOVO** (`SPEC-001` secao 4.3, linhas 215–216):
  - `src/core/bot.py:1008-1010` (`inedito = registro is None or (decisao is not None and registro.get('elegibilidade') == 'filtrado')`).
  - Provado por `test_filtrado_que_passa_a_entrar_sai_como_novo`.
- **R-13 — elegivel que passa a filtrado nao renotifica nem apaga** (`SPEC-001` secao 4.3, linha 217):
  - `src/core/bot.py:982-992` preserva `fase_mais_avancada(fase_antiga, fase_nova)`, atualiza `elegibilidade='filtrado'` e `motivo_filtro`, e retorna `"skip"`.
  - Provado por `test_elegivel_que_passa_a_filtrado_nao_renotifica`.
- **Selo no card** (`SPEC-001` secao 4.2, linha 206):
  - `src/core/bot.py:1041` acrescenta `html.escape(decisao.selo)` quando `decisao and decisao.selo`; sem selo, nao altera a mensagem.
  - Provado por `test_selo_aparece_no_card` (`nao_verificado`) e `test_sem_selo_nao_poe_linha_extra` (`acima_do_corte`). Observacao menor: o segundo motivo com selo (`sem_evidencia`) compartilha exatamente a mesma linha `bot.py:1041` e ja e testado em `test_elegibilidade.py`, mas nao tem teste proprio na costura do bot.
- **R-14 — area com `filtro_salarial` desligado nao muda nada** (`SPEC-001` secao 4.3, linha 218):
  - Provado por `test_area_com_filtro_desligado_nao_filtra_nada`.
- **Resumo semanal (R-20, R-21, R-22, `--dry-run`, resiliencia a falha)** (`SPEC-001` secao 4.4, linhas 226–231):
  - Chamado em `src/core/bot.py:307` apos `_mensagem_final` e `_alertar_fontes_doentes`.
  - Implementado em `src/core/bot.py:797-865` (`_enviar_resumo_semanal`), com marcador proprio em `LOG_DIR/.resumo_<area>_filtrados` contendo `resumo_filtrados.marcador_da_semana(date.today())` (sem alterar `_alerta_uma_vez_por_dia`), corte UTC de 7 dias (`%Y-%m-%d %H:%M:%S`), respeito a `--dry-run`, silencio sem marcador quando lista vazia, envio via `self.notifier.notificar(texto)` (nao `_notificar`, evitando setar `self.falhou` em recusa) e `except Exception` que loga em `error` sem derrubar a rodada.
  - Provado pelos 7 testes de `TestResumoSemanal`.
- **Decisao do arquiteto (2026-11-23 18:44 — `sem_materia_prima` com `self.mcp_scraper`, SPEC-002 secao 1)**:
  - `src/core/bot.py:691-693` inclui `and not self.mcp_scraper`.
  - Provado por `TestFonteMcp::test_gran_vazio_com_mcp_trazendo_item_nao_e_cegueira`.

### 2. Escopo

Comando: `git diff --stat 9c12e9e..HEAD`
```text
 src/core/bot.py            | 215 ++++++++++++++++++-
 tests/test_concurso_bot.py | 501 +++++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 708 insertions(+), 8 deletions(-)
```
Apenas os dois arquivos do campo `toca` foram modificados. Nenhum arquivo da secao «Fora do escopo» foi alterado e nao ha ganchos nem opcoes nao pedidas.

### 3. Aderencia a SPEC e ADRs

- Alinhado com `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md` (secoes 3.4, 3.5, 3.6, 4.2, 4.3, 4.4), `docs/specs/SPEC-002-sonda-e-conserto-automatico.md` (secao 1) e `docs/adr/0002-elegibilidade-pelo-teto-do-concurso.md`.
- Nenhuma discordancia encontrada entre spec, ADR e codigo.

---

## Prova

### 4. Numeros medidos vs. relatorio do implementador

| Medida | Comando | Implementador | Revisor |
| :--- | :--- | :--- | :--- |
| Base (`9c12e9e`) | `git merge-base main HEAD` (base do `integrar`) | `517 passed / 0 failed` | `9c12e9e8` confirmado; vale `517 passed` do prompt |
| Ponta (`e59387e`) | `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q` | `539 passed / 0 failed` | `539 passed in 60.84s` (`0 failed`) |
| Pulados | `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -rs -q` | `0 skipped` | `539 passed in 58.27s` (`0 skipped`) |
| Coleta | `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest --collect-only -q` | `539 tests collected` | `539 tests collected in 1.07s` |
| Conta | `base + novos = ponta` | `517 + 22 = 539` | `517 + 22 = 539` (1 cegueira + 14 filtro + 7 resumo) |
| Lint | `(nao configurado)` | — | `(nao configurado)` |

Condicao de medicao: sem variaveis de ambiente customizadas e sem marcadores `-m`. Todos os numeros do implementador conferem integralmente.

### 5. Verificacao do TDD (nivel G- — vermelho provado em cada `test:`)

Log `git log --format="%h %s" 9c12e9e..HEAD` mostra tres pares limpos `test:` → `fix:`/`feat:` e um commit `docs:` separado no final (`e59387e` toca apenas docstrings em `src/core/bot.py`).

Cada commit `test:` foi verificado em worktree destacado temporario (`git worktree add --detach _worktrees/r10 <hash>`, removido apos o teste):

- `bda1c63` (`pytest tests/test_concurso_bot.py -k test_gran_vazio_com_mcp_trazendo_item_nao_e_cegueira -q --tb=line`): **1 failed** (`assert True is False` em `bot.falhou`). Vermelho pelo motivo certo.
- `1760527` (`pytest tests/test_concurso_bot.py -k TestFiltroSalarial -q --tb=line`): **11 failed, 3 passed** (falhas por `notificar_concurso` chamado, `KeyError` em `elegibilidade`/`motivo_filtro`, selo ausente e R-12; as 3 que passaram sao exatamente as guardas declaradas). Nenhuma falha de coleta ou importacao.
- `5ff9189` (`pytest tests/test_concurso_bot.py -k TestFiltroSalarial -q --tb=line`): **11 failed, 3 passed** (mesmo conjunto de falhas de assercao; ajusta a assercao de `novos == 0` antes do `feat:` sem enfraquece-la).
- `825943a` (`pytest tests/test_concurso_bot.py -k TestResumoSemanal -q --tb=line`): **6 failed, 1 passed** (falhas por `len(_resumos) == 0` e ausencia de log `ERROR`; a que passou e a guarda declarada `test_resumo_desligado_nao_consulta_o_banco`). Nenhuma falha de coleta ou importacao.

### 6. Qualidade dos testes e prova por mutacao

- **Costura e defeitos**: todos os 22 testes exercitam a interface publica `ConcursoBot.executar()`, dublando apenas a fronteira (scrapers, `DatabaseManager`, `TelegramNotifier`, `IntelligenceUnit`, `TelegramCallbackProcessor`, `LOG_DIR` e o relogio `src.core.bot.date`). Nenhum teste e acoplado a implementacao, tautologico ou usa duble fora da fronteira (inclusive os dois desvios do plano de testes — `test_ignorado` e `test_falha_no_resumo` — melhoraram o desacoplamento). Os itens de teste vem de casos reais das fixtures em `tests/fixtures/pci_mcp/` com vereditos decididos a mao pela tabela da SPEC-001 secao 4.2.
- **Mutacoes executadas** em worktree destacado sobre `HEAD` (`e59387e`), com `git diff --stat` conferido antes de cada rodada de `pytest tests/test_concurso_bot.py -k "TestFiltroSalarial or TestResumoSemanal or test_gran_vazio_com_mcp_trazendo_item_nao_e_cegueira" -q`:
  - **M1** (desligar `ignorado` antes do filtro): **morto** — 1 falha (`test_ignorado_continua_saindo_antes_do_filtro`)
  - **M2** (desligar R-15, avaliar item sem `"regiao"`): **morto** — 2 falhas (`test_item_do_gran_nao_e_avaliado`, `test_item_da_pagina_de_cargo_nao_e_avaliado`)
  - **M3** (desligar R-12, filtrado que volta nao sai como novo): **morto** — 1 falha (`test_filtrado_que_passa_a_entrar_sai_como_novo`)
  - **M4** (remover selo do card): **morto** — 1 falha (`test_selo_aparece_no_card`)
  - **M5** (forcar `seguindo=False`): **morto** — 1 falha (`test_estrelado_notifica_mesmo_filtravel`)
  - **M6** (remover `and not self.mcp_scraper` de `sem_materia_prima`): **morto** — 4 falhas (incl. `test_gran_vazio_com_mcp_trazendo_item_nao_e_cegueira`)
  - **M7** (marcador do resumo diario `date.today().isoformat()` em vez de semana ISO): **morto** — 1 falha (`test_resumo_semanal_sai_uma_vez_na_semana`)
  - **M8** (remover guarda `if self.dry_run` no resumo): **morto** — 1 falha (`test_dry_run_nao_manda_resumo_nem_marca`)
  - **M9** (remover fallback `or extrair_uf(nome)`): **morto** — 1 falha (`test_uf_sai_do_nome_quando_o_item_nao_traz`)
  - **M10** (gravar marcador mesmo quando `notifier.notificar` retorna `False`): **morto** — 1 falha (`test_envio_do_resumo_que_falha_nao_marca_a_rodada_e_tenta_de_novo`)
  - **M11** (gravar marcador quando `montar` devolve `None` / semana vazia): **morto** — 1 falha (`test_semana_sem_filtrados_nao_manda_nem_marca`)
  - **M12** (alterar janela do resumo de `timedelta(days=7)` para `timedelta(days=1)` em `src/core/bot.py:835`): **sobreviveu** (`22 passed`). Ressalva de codigo/testes registrada abaixo (nao bloqueia o aceite porque o codigo esta correto e o plano de testes do ticket nao pedia essa assercao).

---

## Padrões

### 7. Regras do projeto e vocabulario

- **Idioma, segredos, dependencias, rede, migracao, git**: tudo em conformidade. Nenhum segredo, nenhuma dependencia nova, nenhuma chamada de rede nos testes, nenhum `T-NNN` no diff ou nas mensagens de commit (`git diff 9c12e9e..HEAD` verificado por regex `T-\d{3}`), nenhum `push`.
- **Ressalva leve de vocabulario (`GLOSSARIO.md:17-19`)**: o termo `varredura` (listado em `_Evite_` de **Rodada**) aparece em trechos recem-escritos de `src/core/bot.py:807,863` ("a varredura e o trabalho", "A varredura nao e afetada") e `tests/test_concurso_bot.py:1331,1973` ("varredura cega", "A varredura fez o trabalho dela"). Parte vem da redacao do proprio ticket e de termos legados de `bot.py`, mas nos trechos novos preferir `rodada`.

### 8. Cheiros de codigo

- **Possivel codigo duplicado** (dispensado por diretriz do ticket): a leitura/gravacao do marcador de arquivo em `_enviar_resumo_semanal` (`src/core/bot.py:821-831,854-859`) espelha `_alerta_uma_vez_por_dia` (`src/core/bot.py:777-786,790-795`). As Notas do arquiteto no ticket pedem explicitamente dois helpers separados para nao misturar regimes diario e semanal; a orientacao vence o cheiro.
- **Possivel mudanca divergente / metodo longo** (pre-existente, sem agravamento indevido): `ConcursoBot._decidir_e_notificar` atingiu 224 linhas (`src/core/bot.py:879-1102`) em um arquivo de 1210 linhas. O implementador manteve a integracao enxuta extraindo `_politica_de`, `_avaliar_elegibilidade` e `_enviar_resumo_semanal`, evitando inchar ainda mais a matriz.
