APROVADO COM RESSALVAS
Esteira: revisor · agy-argon (gemini-4-argon) · nível M+ · esforço high · 2026-11-23 17:53 → 2026-11-23 17:59 (7 min)
Resumo: Entrega das oito chaves de configuração por área da SPEC-001 (§3.6 e R-14) em `config/loader.py`, testes em `tests/test_config_loader.py` e documentação em `.env.example` revisada e aprovada com ressalvas. O código cumpre todos os 12 itens do critério de aceite nos dois caminhos (multi-área e legado), respeita o ciclo TDD em três fatias (`test:` vermelhos → `feat:` verdes) fechadas por `docs:`, e mata 22 de 27 mutações em worktree destacado; a ressalva de código refere-se a quatro asserções de teste cujos valores de entrada coincidem com o padrão ou agrupam avisos na mesma chamada.
Arquivos: config/loader.py · tests/test_config_loader.py · .env.example (todos dentro do «toca»; fora do «toca»: nenhum)
Commits: e36ac87 test: loader devolve as oito chaves por area com padroes da spec · ef587d3 feat: loader devolve as oito chaves por area com padroes e normalizacao · b0bb5f6 test: valor invalido das chaves por area cai no padrao com aviso · 0bccb85 feat: valor invalido das chaves por area loga aviso e cai no padrao · 8577849 test: porta do mcp sem termos desliga com erro e com porta de html avisa · cbff289 feat: porta do mcp sem termos desliga com erro; com porta de html, aviso · d9c08a2 docs: env.example documenta as oito chaves por area e o exemplo da area TI
Testes: "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs → base (16543aa) 296 passed / 0 failed (0 skipped) · ponta (d9c08a2) 312 passed / 0 failed (0 skipped)
Testes que nascem verdes: nenhum (todos os 16 testes novos nasceram vermelhos nos commits e36ac87, b0bb5f6 e 8577849)
Desvios e riscos: Ressalva de código (nos testes, sem defeito no código de produção): (1) os testes de `ufs_sem_corte` usam `"pr, sc,rs"`, cujo resultado normalizado (`["PR", "SC", "RS"]`) é idêntico ao padrão da spec, permitindo que uma mutação que ignore `UFS_SEM_CORTE` no modo legado ou devolva o padrão para qualquer lista não vazia sobreviva; (2) `esferas_sem_corte=[]` está implementado em `config/loader.py:110`, mas só `ufs_sem_corte=[]` tem teste dedicado; (3) `test_pci_mcp_cargos_aceita_csv_e_preserva_ordem` usa termos já em minúsculas, matando mutação de `.upper()` mas não de `.lower()`; (4) `test_pci_mcp_com_slugs_avisa_mas_nao_desliga` agrupa `COM_SLUGS` e `COM_NACIONAL` e afirma `assert avisos` em vez de `len(avisos) == 2`.
Pendências: Consumir as oito chaves no `ConcursoBot`, `PciMcpScraper`, elegibilidade e resumo semanal (tickets seguintes); sugestão opcional de ticket P para estreitar as 4 asserções em `tests/test_config_loader.py`.

## Spec

1. **O aceite foi cumprido?** Sim. Todos os 12 itens do critério de aceite foram implementados em `config/loader.py` e `.env.example` e verificados em `tests/test_config_loader.py`:
   - **Item 1 (As oito chaves da SPEC-001 §3.6 com padrões exatos):** `_config_por_area` (`config/loader.py:186-233`) devolve `pci_mcp` (`False`), `pci_mcp_cargos` (`[]`), `filtro_salarial` (`"desligado"`), `corte_fora_sul` (`0.0`), `ufs_sem_corte` (`["PR", "SC", "RS"]`), `esferas_sem_corte` (`["federal"]`), `cargos_total_inflado` (`10`) e `resumo_filtrados` (`"nunca"`). Provado por `test_alvo_sem_as_chaves_novas_recebe_os_padroes` (`tests/test_config_loader.py:240-243`) contra o dicionário literal `PADROES_SECAO_3_6` (`tests/test_config_loader.py:202-211`).
   - **Item 2 (Dois caminhos do loader — multi-área e legado):** aplicado no loop de `MONITOR_TARGETS_JSON` (`config/loader.py:308-309`) e no fallback legado via `_env_opcional` para `PCI_MCP`, `PCI_MCP_CARGOS`, `FILTRO_SALARIAL`, `CORTE_FORA_SUL`, `UFS_SEM_CORTE`, `ESFERAS_SEM_CORTE`, `CARGOS_TOTAL_INFLADO` e `RESUMO_FILTRADOS` (`config/loader.py:319-344`). Provado por `test_padroes_valem_no_modo_legado` (`tests/test_config_loader.py:245-250`) e `test_chaves_por_area_no_modo_legado_via_variaveis` (`tests/test_config_loader.py:252-274`).
   - **Item 3 (`filtro_salarial` aceita `"desligado"` e `"ativo"` sem caixa/bordas; inválido loga `warning` e cai em `"desligado"`):** implementado em `_normalize_escolha` (`config/loader.py:126-144,205-212`) e provado por `test_filtro_salarial_aceita_ativo` (`tests/test_config_loader.py:276-285`) e `test_filtro_salarial_invalido_cai_em_desligado` (`tests/test_config_loader.py:349-360`).
   - **Item 4 (`resumo_filtrados` aceita `"nunca"` e `"semanal"`; inválido loga `warning` e cai em `"nunca"`):** implementado em `_normalize_escolha` (`config/loader.py:225-232`) e provado por `test_chaves_por_area_no_modo_legado_via_variaveis` (`tests/test_config_loader.py:261,273`) e `test_resumo_filtrados_invalido_cai_em_nunca` (`tests/test_config_loader.py:362-369`).
   - **Item 5 (`corte_fora_sul` aceita número ou string e sai como `float`; não numérico ou negativo loga `warning` e cai em `0.0`):** implementado em `_normalize_corte_fora_sul` (`config/loader.py:147-164`, incluindo guarda `math.isfinite`) e provado por `test_corte_aceita_numero_e_string` (`tests/test_config_loader.py:287-300`) e `test_corte_invalido_cai_em_zero` (`tests/test_config_loader.py:371-382`).
   - **Item 6 (`cargos_total_inflado` sai como `int`; não inteiro ou `< 1` loga `warning` e cai em `10`):** implementado em `_normalize_cargos_total_inflado` (`config/loader.py:167-183`) e provado por `test_cargos_total_inflado_invalido_cai_em_dez` (`tests/test_config_loader.py:384-396`).
   - **Item 7 (`ufs_sem_corte` em maiúscula, `esferas_sem_corte` em minúscula, lista ou CSV, lista vazia explícita respeitada e chave ausente no padrão):** implementado em `_normalize_ufs_sem_corte` e `_normalize_esferas_sem_corte` com sentinela `_AUSENTE` (`config/loader.py:79-112`) e provado por `test_ufs_sem_corte_aceita_csv_e_normaliza_caixa`, `test_ufs_sem_corte_vazia_explicita_e_respeitada` e `test_esferas_sem_corte_normaliza_para_minuscula` (`tests/test_config_loader.py:302-321`).
   - **Item 8 (`pci_mcp_cargos` aceita lista ou CSV, descarta vazios e preserva ordem e caixa):** implementado em `_normalize_pci_mcp_cargos` e `_split_csv_ou_lista` (`config/loader.py:88-91,115-123`) e provado por `test_pci_mcp_cargos_aceita_csv_e_preserva_ordem` (`tests/test_config_loader.py:323-328`).
   - **Item 9 (`pci_mcp` ligado com `pci_mcp_cargos` vazia loga `error` e devolve `pci_mcp` como `False`):** implementado em `_config_por_area` (`config/loader.py:195-201`) e provado por `test_pci_mcp_sem_cargos_e_desligado_com_erro` (`tests/test_config_loader.py:400-411`).
   - **Item 10 (`pci_mcp` ligado junto com `pci_slugs` ou `pci_nacional` loga `warning` citando reserva/ADR-0001 e duplicação sem desligar nada):** implementado em `_avisar_portas_reserva` (`config/loader.py:236-257,309,344`) e provado por `test_pci_mcp_com_slugs_avisa_mas_nao_desliga` (`tests/test_config_loader.py:413-439`).
   - **Item 11 (`.env.example` documenta as oito chaves e traz exemplo completo da área TI):** bloco comentado em `.env.example:114-142` (e variáveis legadas em `.env.example:171-179`), com JSON válido em linha única contendo `pci_mcp: true`, `filtro_salarial: "ativo"`, `corte_fora_sul: 10000` e exatamente os 13 termos de cargo das notas do arquiteto.
   - **Item 12 (Alvo sem as oito chaves funciona como hoje; uma área filtrando não afeta a outra):** provado pela suíte existente de `TestLoadMonitorTargetsMultiArea` / `TestLoadMonitorTargetsLegacy` e por `test_uma_area_filtrando_nao_afeta_a_outra` (`tests/test_config_loader.py:330-337`).
2. **Passou do escopo?** Não. `git diff --stat 16543aae6eca14e52d1de0cbeb519a19f92c7e06..HEAD` toca apenas os três arquivos do campo `toca`:
   - `.env.example` (+39 linhas)
   - `config/loader.py` (+206, -2 linhas)
   - `tests/test_config_loader.py` (+253 linhas)
   Nenhum arquivo fora do `toca` foi alterado.
3. **Bate com a spec?** Sim. Conferido contra `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md:157-169` (§3.6), `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md:218` (R-14 / PED-04), `docs/adr/0001-mcp-como-unica-porta-do-pci.md:9-11` e `docs/adr/0002-elegibilidade-pelo-teto-do-concurso.md:34`.
   - A distinção entre chave ausente (`_AUSENTE`, silenciosa) e `null` explícito no JSON (loga `warning` em `filtro_salarial`, `resumo_filtrados`, `corte_fora_sul` e `cargos_total_inflado` e cai no padrão) harmoniza o item 12 do aceite com os casos `None` do plano de testes (`tests/test_config_loader.py:355,377`).
   - O rejeite de `nan`/`inf` via `math.isfinite` em `_normalize_corte_fora_sul` (`config/loader.py:157`) evita que `float("nan")` ou `float("inf")` contornem o fail-open.

## Prova

4. **Os números são reais?** Sim. Medições executadas pelo revisor no venv do repositório, com isolamento de variáveis pelo fixture autouse `_clear_env`, sem marcadores extras:
   - Comando: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs`
   - **Base** (`16543aae6eca14e52d1de0cbeb519a19f92c7e06`, em worktree destacado): implementador afirmou `296 passed / 0 failed` · revisor mediu `296 passed in 24.63s` (0 failed, 0 skipped).
   - **Ponta** (`d9c08a233239bb81ad083b6ddd1f2affdff9faae`): implementador afirmou `312 passed / 0 failed (0 pulados)` · revisor mediu `312 passed in 25.57s` (0 failed, 0 skipped).
   - **Conta:** `296 + 16 = 312`. A conta fecha exatamente. Lint não configurado no repositório.
5. **O TDD foi de verdade?** Sim. O histórico `16543aa..HEAD` traz três pares `test:` → `feat:` seguidos de `docs:`. Todos os três commits `test:` foram verificados em worktree destacado com `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest tests/test_config_loader.py -q`:
   - `e36ac87` (`test:` fatia 1): `10 failed, 17 passed in 0.35s` (todos os 10 testes novos falham por `KeyError` nas chaves novas) → `ef587d3` (`feat:` fatia 1): `27 passed in 0.15s`.
   - `b0bb5f6` (`test:` fatia 2): `4 failed, 27 passed in 0.37s` (os 4 testes de fail-open falham por `AssertionError`/`ValueError`) → `0bccb85` (`feat:` fatia 2): `31 passed in 0.17s`.
   - `8577849` (`test:` fatia 3): `2 failed, 31 passed in 0.32s` (os 2 testes de erro/aviso da porta MCP falham por `AssertionError`) → `cbff289` (`feat:` fatia 3): `33 passed in 0.18s`.
   - `d9c08a2` (`docs:`): apenas documentação (`.env.example` e docstring de topo em `config/loader.py`).
6. **Os testes provam comportamento?** Sim. Todos os 16 testes novos usam a costura pública `load_monitor_targets` com `monkeypatch.setenv` e `caplog`, oráculo literal (`PADROES_SECAO_3_6`) e zero dublês fora da fronteira.
   - **Bateria de 27 mutações em worktree destacado sobre `HEAD` (`d9c08a2`), conferidas com `git diff --shortstat` antes de rodar `pytest tests/test_config_loader.py -q`:**
     - `M01a_default_ufs` (`["PR", "SC", "RS"]` → `["PR", "SC"]` em `config/loader.py:101`): **morta** (`2 failed, 31 passed`).
     - `M01b_default_esferas` (`["federal"]` → `[]` em `config/loader.py:111`): **morta** (`2 failed, 31 passed`).
     - `M01c_default_inflado` (`10` → `20` em `config/loader.py:173`): **morta** (`2 failed, 31 passed`).
     - `M01d_default_corte` (`0.0` → `10000.0` em `config/loader.py:154`): **morta** (`2 failed, 31 passed`).
     - `M02a_legacy_missing_dict` (remoção de `**legacy_config_area` em `config/loader.py:342`): **morta** (`6 failed, 27 passed`).
     - `M02b_legacy_filtro_env` (`_env_opcional("FILTRO_SALARIAL")` → `_AUSENTE` em `config/loader.py:322`): **morta** (`1 failed, 32 passed`).
     - `M03a_escolha_no_strip_lower` (remoção de `.strip().lower()` em `config/loader.py:137`): **morta** (`2 failed, 31 passed`).
     - `M03b_escolha_no_warning` (remoção de `logger.warning` em `config/loader.py:140`): **morta** (`2 failed, 31 passed`).
     - `M04a_resumo_semanal` (`"semanal"` → `"mensal"` em `config/loader.py:229`): **morta** (`1 failed, 32 passed`).
     - `M05a_corte_negativo_aceito` (`corte >= 0` → `corte >= -100` em `config/loader.py:157`): **morta** (`1 failed, 32 passed`).
     - `M05b_corte_no_warning` (remoção de `logger.warning` em `config/loader.py:161`): **morta** (`1 failed, 32 passed`).
     - `M06a_inflado_zero_aceito` (`numero >= 1` → `numero >= 0` em `config/loader.py:176`): **morta** (`1 failed, 32 passed`).
     - `M06b_inflado_float_aceito` (remoção de `numero.is_integer()` em `config/loader.py:176`): **morta** (`1 failed, 32 passed`).
     - `M06c_inflado_no_warning` (remoção de `logger.warning` em `config/loader.py:180`): **morta** (`1 failed, 32 passed`).
     - `M07a_ufs_upper` (remoção de `.upper()` em `config/loader.py:102`): **morta** (`2 failed, 31 passed`).
     - `M07b_esferas_lower` (remoção de `.lower()` em `config/loader.py:112`): **morta** (`2 failed, 31 passed`).
     - `M07c_ufs_falsy_trap` (`valor is None` → `not valor` em `config/loader.py:100`): **morta** (`1 failed, 32 passed`).
     - `M08a_cargos_order_reversed` (inversão da lista em `config/loader.py:123`): **morta** (`2 failed, 31 passed`).
     - `M08b_cargos_upper` (forçar `.upper()` em `config/loader.py:123`): **morta** (`2 failed, 31 passed`).
     - `M09a_mcp_sem_cargos_nao_desliga` (remoção de `pci_mcp = False` em `config/loader.py:201`): **morta** (`1 failed, 32 passed`).
     - `M09b_mcp_sem_cargos_warning_em_vez_de_error` (`logger.error` → `logger.warning` em `config/loader.py:196`): **morta** (`1 failed, 32 passed`).
     - `M10a_sem_aviso_portas_reserva` (remoção de `_avisar_portas_reserva` em `config/loader.py:309`): **morta** (`1 failed, 32 passed`).
   - **Ressalva de código (sub-mutações que sobreviveram por escolha de literal/contagem nos testes, embora o código em `config/loader.py` esteja correto):**
     1. `M02c_legacy_ufs_env` e `M07e_ufs_hardcoded_default_when_nonempty`: sobreviveram porque `test_ufs_sem_corte_aceita_csv_e_normaliza_caixa` (`tests/test_config_loader.py:304`, seguindo o exemplo do plano) e `test_chaves_por_area_no_modo_legado_via_variaveis` (`tests/test_config_loader.py:258`) passam `"pr, sc,rs"`, que normalizado coincide com o padrão `["PR", "SC", "RS"]`.
     2. `M07d_esferas_falsy_trap`: sobreviveu porque `esferas_sem_corte=[]` não tem caso de teste dedicado como `ufs_sem_corte=[]` (`tests/test_config_loader.py:309-314`).
     3. `M08c_cargos_lower`: sobreviveu porque `test_pci_mcp_cargos_aceita_csv_e_preserva_ordem` (`tests/test_config_loader.py:325`) usa apenas minúsculas (`"analista de sistemas, informatica"`).
     4. `M10b_sem_aviso_pci_nacional`: sobreviveu porque `test_pci_mcp_com_slugs_avisa_mas_nao_desliga` (`tests/test_config_loader.py:434-439`) coloca os dois alvos (`COM_SLUGS` e `COM_NACIONAL`) na mesma chamada e verifica `assert avisos` em vez de `assert len(avisos) == 2`.
     - **Sugestão de ticket novo (opcional, a critério do arquiteto):**
       - Título: `Estreitar assercoes de UFs nao-padrao, esferas vazia, caixa de cargos e contagem de avisos em test_config_loader`
       - Nível: `P`
       - `toca`: `[tests/test_config_loader.py]`

## Padrões

7. **Regras e padrões do projeto (`kanban/REGRAS.md`, `GLOSSARIO.md`, `docs/adr/0001-mcp-como-unica-porta-do-pci.md`, `docs/adr/0002-elegibilidade-pelo-teto-do-concurso.md`):** Cumpridos integralmente.
   - Vocabulário do `GLOSSARIO.md` respeitado (`area`, `porta`, `rodada`, `elegibilidade`, `corte fora do Sul`, `esfera`, `fail-open`).
   - Código, docstrings, logs e commits em português do Brasil; identificadores e comentários sem acento.
   - Nenhum ID de ticket (`T-NNN`) em código, docstring, comentário, `.env.example` ou mensagem de commit.
   - Sem segredo, sem dependência nova e sem acesso à rede.
8. **Cheiros de código:** Nenhum cheiro identificado. As funções de normalização em `config/loader.py` seguem o padrão já existente no módulo (`_normalize_slugs`, `_normalize_bool`, `_normalize_modo_carga`), com responsabilidade única e nomes diretos.
