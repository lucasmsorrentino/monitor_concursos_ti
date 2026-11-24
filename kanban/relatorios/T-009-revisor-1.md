APROVADO COM RESSALVAS
Esteira: revisor · agy-argon (gemini-4-argon) · nível M+ · esforço high · 2026-11-23 18:34 → 2026-11-23 18:43 (9 min)
Resumo: Revisada e aprovada com ressalvas a ligação da porta `PciMcpScraper` na rodada de `ConcursoBot.executar()` como quarta fonte, entre a página de cargo (`pci_scraper`) e a lista nacional (`nacional_scraper`). O código cumpre todos os 8 itens do critério de aceite de T-009, a SPEC-001 (§3.1, PED-02, R-07) e a ADR-0001, tocando exclusivamente os dois arquivos do `toca`. O ciclo TDD (`chore:` → `test:` → `feat:` → `docs:`) foi comprovado em worktree destacado no commit `e2e0111` (8 falhas pelo motivo certo + 2 guardas declaradas) e 10 de 12 mutações em `HEAD` (`03c9b7b`) foram mortas pela suíte; as ressalvas são asserções nos testes que não observam a saída de `_mensagem_final` para os acumuladores `validos`/`novos_cont`, uma chamada a `bot.executar()` omitida na terceira asserção de `test_mcp_desligado_nao_instancia_scraper` e uma observação sobre `sem_materia_prima` em `src/core/bot.py:646` quando `pci_slugs` for desligado no deploy.
Arquivos: src/core/bot.py · tests/test_concurso_bot.py (todos dentro do «toca»; fora do «toca»: nenhum)
Commits: c2f820b chore: esqueleto da porta do MCP no bot (import e mcp_scraper None) · e2e0111 test: itens do MCP passam pela decisao, saude e dedup na rodada · f2c623f feat: porta do MCP ligada na rodada do bot · 03c9b7b docs: nota de fontes do modulo cita a porta do MCP
Testes: "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs → base (8ec3be4, medida pelo integrar) 383 passed / 0 failed · ponta (03c9b7b) 393 passed / 0 failed (0 skipped)
Testes que nascem verdes: test_mcp_desligado_nao_instancia_scraper e test_mcp_nao_chama_enriquecer (guardas declaradas pelo implementador que já passam sobre o esqueleto `c2f820b` e cujo valor pós-`feat:` foi comprovado pelas mutações M1a e M3)
Desvios e riscos: Ressalvas de código (não bloqueantes, sem defeito no código implementado da porta MCP): (1) `test_mcp_e_gran_na_mesma_rodada_somam_contadores` e `test_itens_do_mcp_passam_pela_decisao` verificam a contagem de cartões enviados por `_decidir_e_notificar` (`notifier.notificar_concurso`), mas não afirmam o efeito dos acumuladores `validos`, `novos_cont` e `atualizados_cont` em `_mensagem_final` (log de resumo / heartbeat), deixando sobreviver as sub-mutações M2d e M2e; (2) `test_mcp_desligado_nao_instancia_scraper` prepara `saude_fontes.avaliar` e afirma `"pci_mcp" not in fontes` sem chamar `bot.executar()`; (3) em `src/core/bot.py:646` (fora do aceite de T-009), `sem_materia_prima = total_blocos == 0 and not self.pci_scraper` não considera `self.mcp_scraper`, o que marcará cegueira se o Gran devolver 0 blocos quando `pci_slugs` estiver desligado no deploy (ADR-0001).
Pendências: Filtro de elegibilidade, selo no cartão, gravação das colunas do schema v6 e resumo semanal no ticket seguinte (`src/core/bot.py`); sugestão opcional de ticket P para estreitar as asserções de contadores/cegueira com `mcp_scraper`.

## Spec

1. **O aceite foi cumprido?** Sim. Todos os 8 itens do critério de aceite foram implementados em `src/core/bot.py` e verificados em `tests/test_concurso_bot.py`:
   - **Item 1 (`ConcursoBot.__init__` instancia `self.mcp_scraper = PciMcpScraper(<termos>)` quando `pci_mcp` é verdadeiro e `None` quando não):** implementado em `src/core/bot.py:117-121` (`PciMcpScraper(config.get('pci_mcp_cargos') or []) if config.get('pci_mcp') else None`), seguindo o padrão condicional de `self.pci_scraper` e `self.nacional_scraper`. Provado por `test_mcp_desligado_nao_instancia_scraper` (`tests/test_concurso_bot.py:1140-1153`) e `test_mcp_ligado_instancia_com_os_termos` (`tests/test_concurso_bot.py:1155-1169`).
   - **Item 2 (`executar()` posiciona a fonte entre a fonte 2 e a fonte 3, alimentando `validos`, `links_pci_vistos`, `_decidir_e_notificar(item, url_indice=item["link"])`, `novos_cont` e `atualizados_cont`):** implementado em `src/core/bot.py:246-270`, imediatamente após `if self.pci_scraper:` (`src/core/bot.py:218-237`) e antes de `if self.nacional_scraper:` (`src/core/bot.py:272-278`). Provado por `test_itens_do_mcp_passam_pela_decisao` (`tests/test_concurso_bot.py:1171-1189`), `test_links_do_mcp_entram_no_conjunto_de_vistos` (`tests/test_concurso_bot.py:1256-1293`), `test_mcp_e_gran_na_mesma_rodada_somam_contadores` (`tests/test_concurso_bot.py:1325-1343`) e `test_dedup_entre_mcp_e_gran_pelo_pci_id` (`tests/test_concurso_bot.py:1345-1399`).
   - **Item 3 (Não chama `enriquecer`):** o laço em `src/core/bot.py:264-269` consome diretamente o dict de `itens_mcp`, que já traz `data_fim_inscricao` (`docs/adr/0001-mcp-como-unica-porta-do-pci.md:5-6`). Provado por `test_mcp_nao_chama_enriquecer` (`tests/test_concurso_bot.py:1191-1200`).
   - **Item 4 (Diagnóstico de saúde com nome `"pci_mcp"` e assinatura `f"{i['pci_id']}|{i['status']}"` entregue a `_alertar_fontes_doentes` — R-07):** implementado em `src/core/bot.py:260-262` e repassado em `src/core/bot.py:290`. Provado por `test_mcp_registra_a_fonte_na_saude` (`tests/test_concurso_bot.py:1202-1244`).
   - **Item 5 (`_url_da_fonte("pci_mcp")` devolve o endereço do servidor MCP):** implementado em `src/core/bot.py:506-507` (`if fonte == "pci_mcp" and self.mcp_scraper: return self.mcp_scraper.url`). Provado por `test_url_da_fonte_do_mcp` (`tests/test_concurso_bot.py:1246-1254`) e pela conferência de `URL_SERVIDOR` no alerta de `test_mcp_registra_a_fonte_na_saude` (`tests/test_concurso_bot.py:1244`).
   - **Item 6 (Falha total de `capturar_concursos` marca `self.falhou = True`, loga erro e deixa as outras fontes seguirem):** implementado no bloco `try / except Exception as e / else` em `src/core/bot.py:247-269`. Provado por `test_falha_total_do_mcp_marca_a_area_e_segue` (`tests/test_concurso_bot.py:1295-1323`).
   - **Item 7 (Área com `pci_mcp` desligado mantém comportamento inalterado):** com `pci_mcp` ausente ou falso, `self.mcp_scraper` é `None` (`src/core/bot.py:117-121`) e o bloco `if self.mcp_scraper:` (`src/core/bot.py:246`) não executa. Provado por `test_mcp_desligado_nao_instancia_scraper` e pelos 67 testes pré-existentes de `tests/test_concurso_bot.py`.
   - **Item 8 (Suíte inteira verde sem alterar teste existente):** nenhum teste existente foi modificado (`git diff 8ec3be4..HEAD tests/test_concurso_bot.py` contém apenas adições) e todos os 393 testes passam.
2. **Passou do escopo?** Não. `git diff --stat 8ec3be4..HEAD` mostra alterações apenas nos dois arquivos do campo `toca`:
   - `src/core/bot.py` (+50, -3 linhas)
   - `tests/test_concurso_bot.py` (+311 linhas)
   Nenhum arquivo fora do `toca` foi editado. Filtro de elegibilidade, selo, colunas do schema v6, resumo semanal, `src/scrapers/pci_mcp_scraper.py` e `config/loader.py` não foram tocados.
3. **Bate com a spec?** Sim. Conferido contra `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md` (§2 linhas 48-55, §3.1 linhas 62-92, §4.1 R-04 linha 183 e R-07 linhas 189-190) e `docs/adr/0001-mcp-como-unica-porta-do-pci.md` (linhas 1-27).
   - **Ressalvas de código (para avaliação do arquiteto):**
     1. Em `src/core/bot.py:646` (trecho legado fora do aceite de T-009), `sem_materia_prima = total_blocos == 0 and not self.pci_scraper` verifica apenas `self.pci_scraper`. Quando `pci_slugs` for desligado em produção e `pci_mcp` ficar como única porta do PCI (`docs/adr/0001-mcp-como-unica-porta-do-pci.md:9-11`), uma rodada em que o Gran devolva `0` blocos e o MCP devolva itens válidos (`validos > 0`) ainda entrará em `varredura_cega` (`src/core/bot.py:647-666`).
     2. Em `tests/test_concurso_bot.py:1140-1153` (`test_mcp_desligado_nao_instancia_scraper`), o teste faz patch de `saude_fontes.avaliar` e verifica `"pci_mcp" not in fontes`, mas não invoca `bot.executar()`, de modo que `avaliar.call_args_list` é sempre vazia naquele teste.
     3. Em `tests/test_concurso_bot.py:1171-1189` e `1325-1343`, os testes verificam os cartões emitidos por `_decidir_e_notificar`, mas não afirmam o valor acumulado de `novos_cont` e `validos` consumido por `_mensagem_final` (`src/core/bot.py:287-289,674-706`).
     - **Sugestão de ticket novo (opcional, a critério do arquiteto):**
       - Título: `Considerar mcp_scraper em sem_materia_prima e afirmar contadores de _mensagem_final nos testes da porta MCP`
       - Nível: `P`
       - `toca`: `[src/core/bot.py, tests/test_concurso_bot.py]`

## Prova

4. **Os números são reais?** Sim. Medições feitas pelo revisor no venv do repositório, sem variáveis de ambiente ou marcadores extras:
   - Base (`8ec3be4a00c9a55bae9016e144de25bc386842d9`, confirmada por `git merge-base main HEAD`): medida pelo `integrar` em `8ec3be4` como `383 passed in 48.24s` (mesma base informada no prompt e no relatório do implementador).
   - Ponta (`03c9b7bffbd97c49e926bf5c36af08cd3a7cd31d`):
     - Comando: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs`
     - Implementador afirmou: `393 passed / 0 failed (0 pulados; mesmos 383 + os 10 novos)`
     - Revisor mediu: `393 passed in 49.28s` (0 failed, 0 skipped).
   - Conta: `383 + 10 = 393`. A conta fecha exatamente. Lint não configurado no repositório.
5. **O TDD foi de verdade?** Sim. O histórico `8ec3be4..HEAD` segue a ordem `chore:` (`c2f820b`) → `test:` (`e2e0111`) → `feat:` (`f2c623f`) → `docs:` (`03c9b7b`), com documentação separada do código.
   - Prova do vermelho no commit `e2e0111` em worktree destacado (`"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest tests/test_concurso_bot.py -k "TestFonteMcp" -q`):
     - Resultado: `8 failed, 2 passed, 67 deselected in 1.23s`.
     - Os 8 testes falharam por asserção de comportamento (`AssertionError` em instanciação de `PciMcpScraper`, contagem de chamadas a `_decidir_e_notificar`, registro de `"pci_mcp"` na saúde, `_url_da_fonte("pci_mcp")`, `nacional.detalhar.assert_not_called()`, `bot.falhou is True`, soma de cartões Gran+MCP e fusão de `pci_id == "296654"` no banco).
     - Os 2 testes que nasceram verdes (`test_mcp_desligado_nao_instancia_scraper` e `test_mcp_nao_chama_enriquecer`) foram declarados como guardas no relatório do implementador e tiveram seu valor comprovado pelas mutações `M1a` e `M3` abaixo.
6. **Os testes provam comportamento?** Sim. Os 10 testes de `TestFonteMcp` exercitam a costura do plano (`ConcursoBot`, `ConcursoBot.executar()` e `_url_da_fonte`), com entradas escritas à mão no formato da `SPEC-001` §3.1, dublês restritos às portas/notificador (e `DatabaseManager` real em `tmp_path` para o teste de dedup entre fontes).
   - **Bateria de 12 mutações em worktree destacado sobre `HEAD` (`03c9b7b`), rodadas com `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest tests/test_concurso_bot.py -k "TestFonteMcp" -q`:**
     - `M1a_incondicional_init` (`if config.get('pci_mcp')` → `if True` em `src/core/bot.py:119`): **morta** (`1 failed`: `test_mcp_desligado_nao_instancia_scraper`).
     - `M1b_termos_ignorados` (`PciMcpScraper(config.get('pci_mcp_cargos') or [])` → `PciMcpScraper([])` em `src/core/bot.py:118`): **morta** (`1 failed`: `test_mcp_ligado_instancia_com_os_termos`).
     - `M2a_sem_links_vistos` (remoção de `links_pci_vistos.add(item["link"])` em `src/core/bot.py:266`): **morta** (`1 failed`: `test_links_do_mcp_entram_no_conjunto_de_vistos`).
     - `M2c_mcp_url_indice_vazio` (`url_indice=item["link"]` → `url_indice=""` em `src/core/bot.py:267`): **morta** (`1 failed`: `test_itens_do_mcp_passam_pela_decisao`).
     - `M3_chama_enriquecer` (adição de `self.mcp_scraper.enriquecer(item)` no loop do MCP em `src/core/bot.py:265`): **morta** (`1 failed`: `test_mcp_nao_chama_enriquecer`).
     - `M4a_assinatura_saude` (`f"{i['pci_id']}|{i['status']}"` → `f"{i['pci_id']}"` em `src/core/bot.py:261`): **morta** (`1 failed`: `test_mcp_registra_a_fonte_na_saude`).
     - `M4b_sem_append_diagnostico` (chamar `_avaliar_fonte` sem `diagnosticos.append` em `src/core/bot.py:260`): **morta** (`1 failed`: `test_mcp_registra_a_fonte_na_saude`).
     - `M5_url_da_fonte` (desativar ramo `if fonte == "pci_mcp"` em `src/core/bot.py:506`): **morta** (`2 failed`: `test_mcp_registra_a_fonte_na_saude`, `test_url_da_fonte_do_mcp`).
     - `M6a_sem_marcar_falhou` (remoção de `self.falhou = True` no `except` do MCP em `src/core/bot.py:254`): **morta** (`1 failed`: `test_falha_total_do_mcp_marca_a_area_e_segue`).
     - `M6b_excecao_vaza_pro_loop` (remoção do `try/except` interno do MCP em `src/core/bot.py:247-259`, deixando a exceção abortar a rodada antes da fonte nacional): **morta** (`1 failed`: `test_falha_total_do_mcp_marca_a_area_e_segue`).
     - `M2d_sem_novos_cont` (remoção de `novos_cont += resultado == "novo"` em `src/core/bot.py:268`) e `M2e_sem_validos` (remoção de `validos += 1` em `src/core/bot.py:265`): **sobreviveram** — correspondem à ressalva de código apontada no bloco Spec.

## Padrões

7. **Regras e padrões do projeto (`kanban/REGRAS.md`, `GLOSSARIO.md`, `docs/adr/0001-mcp-como-unica-porta-do-pci.md`):** Cumpridos integralmente.
   - Código, docstrings, logs e mensagens de commit em português do Brasil; identificadores e comentários sem acento.
   - Vocabulário alinhado ao `GLOSSARIO.md` (`porta`, `rodada`, `area`, `fase`) e convenção existente de `ConcursoBot` (`TestFonteMcp`, `mcp_scraper`).
   - Nenhum ID de ticket (`T-NNN`) em código, comentário, docstring ou mensagem de commit.
   - Sem segredo, sem dependência nova, sem acesso à rede nos testes e sem uso de LLM para dados do PCI.
   - Ordem das fontes existentes e comentários numerados preservados conforme exigido nas notas do arquiteto.
8. **Cheiros de código:** Nenhum cheiro não autorizado. A repetição estrutural do laço de fonte em `ConcursoBot.executar()` (`src/core/bot.py:218-270`) segue explicitamente a orientação das notas do arquiteto no ticket.
