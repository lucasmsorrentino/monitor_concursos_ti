ENTREGUE
Esteira: implementador · agy-neon (gemini-4-neon) · nível M- · esforço medium · 2026-11-24 23:46 → 2026-11-24 23:54 (9 min)
Resumo: Estreitadas as assercoes frouxas de `tests/test_config_loader.py` (lista de UFs diferente do padrao nos caminhos multi-area e legado, teste dedicado para `esferas_sem_corte=[]`, termo com maiuscula em `pci_mcp_cargos`, e separacao dos avisos de `COM_SLUGS` e `COM_NACIONAL` com contagem exata) e de `tests/test_concurso_bot.py` (efeito de `novos_cont`, `atualizados_cont` e `validos` no resumo final e no heartbeat, chamada de `bot.executar()` em `test_mcp_desligado_nao_instancia_scraper`, selo `sem_evidencia` na costura do bot, e argumento `desde` em UTC com janela de 7 dias em `listar_filtrados`). Trocadas as quatro ocorrencias novas de `varredura` por `rodada` em `src/core/bot.py` e `tests/test_concurso_bot.py`, preservando todas as legadas. Nenhuma mudanca de comportamento de producao foi feita e todas as 13 mutacoes testadas foram mortas.
Arquivos: `src/core/bot.py`, `tests/test_config_loader.py`, `tests/test_concurso_bot.py` (todos dentro do `toca`; nenhum arquivo fora do `toca`)
Commits:
- `cf9cc0e` test: estreita assercoes do loader (ufs, esferas vazia, caixa de cargos e avisos)
- `fb01ddc` test: afirma contadores no resumo final, cegueira apos executar, selo sem_evidencia e janela de 7 dias
- `82db274` chore: troca varredura por rodada nos quatro trechos novos
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs` (sem variaveis de ambiente customizadas nem marcadores; lint nao configurado) → base (`2ea449f`) `539 passed / 0 failed` (`49.18s`) · ponta (`82db274`) `545 passed / 0 failed / 0 skipped` (`49.36s`; `--collect-only -q` → `545 tests collected`; conta `539 + 6 novos = 545`)
Testes que nascem verdes: todos os 6 testes novos e 5 testes estreitados nascem verdes por desenho (o codigo de producao ja estava correto; a prova de eficacia esta na tabela de mutacoes abaixo):
- `test_chaves_por_area_no_modo_legado_via_variaveis` (estreitado: `UFS_SEM_CORTE="mg, ba"`)
- `test_ufs_sem_corte_aceita_csv_e_normaliza_caixa` (estreitado: `ufs_sem_corte="mg, ba,sp"`)
- `test_esferas_sem_corte_vazia_manda_e_nao_cai_no_padrao` (novo)
- `test_pci_mcp_cargos_aceita_csv_e_preserva_ordem` (estreitado: `"Analista de Sistemas, informatica"`)
- `test_pci_mcp_com_slugs_avisa_mas_nao_desliga` (estreitado: caso isolado `COM_SLUGS`, `len(avisos) == 1`)
- `test_pci_mcp_com_nacional_avisa_mas_nao_desliga` (novo: caso isolado `COM_NACIONAL`, `len(avisos) == 1`)
- `test_mcp_desligado_nao_instancia_scraper` (estreitado: chama `bot.executar()`, afirma `"gran" in fontes` e `"pci_mcp" not in fontes`)
- `test_contadores_do_mcp_e_do_gran_aparecem_no_resumo_final` (novo)
- `test_validos_do_mcp_e_do_gran_aparecem_no_heartbeat` (novo)
- `test_selo_sem_evidencia_aparece_no_card` (novo)
- `test_o_resumo_semanal_pede_sete_dias_ao_banco` (novo)
Desvios e riscos:
- No Plano de testes do ticket, o nome sugerido para o item de `pci_mcp_cargos` era `test_pci_mcp_cargos_minusculiza_termo_com_maiuscula`, mas `_normalize_pci_mcp_cargos` (`config/loader.py:115-123`) **preserva** a caixa original; o criterio de aceite estava correto ao pedir um termo com maiuscula em `test_pci_mcp_cargos_aceita_csv_e_preserva_ordem` para matar a mutacao `.lower()`. Mantido o nome existente com entrada `"Analista de Sistemas, informatica"`, matando `.lower()` e `.upper()`.
- Para os contadores do bot, `novos_cont`/`atualizados_cont` saem no log de `_mensagem_final` (quando ha novidades) e `validos` sai no heartbeat (quando nao ha novidades); por isso foram criados dois testes complementares (`test_contadores_do_mcp_e_do_gran_aparecem_no_resumo_final` e `test_validos_do_mcp_e_do_gran_aparecem_no_heartbeat`).
- Em `test_o_resumo_semanal_pede_sete_dias_ao_banco`, alem de `src.core.bot.date`, foi dublado `src.core.bot.datetime` porque `src/core/bot.py:835` usa `datetime.now(timezone.utc)`.
- Nao ha documentacao de modulo ou README a atualizar neste ticket (apenas ajuste de vocabulario nos quatro trechos novos, ja feito em `82db274`).
Pendências: nenhuma.

## Tabela de mutações

Todas as mutações foram aplicadas no código de produção (`config/loader.py` ou `src/core/bot.py`), rodadas contra o teste alvo com `pytest -k <teste> -q --tb=line` e desfeitas em seguida com `git checkout -- <arquivo>`.

| Mutação | Alvo no código | Teste que mata | Resultado |
| :--- | :--- | :--- | :--- |
| `M02c_legacy_ufs_env` | `config/loader.py:324` (`_env_opcional("UFS_SEM_CORTE")` → `_AUSENTE`) | `test_chaves_por_area_no_modo_legado_via_variaveis` | **Morta** (`1 failed`: `['PR', 'SC', 'RS'] != ['MG', 'BA']`) |
| `M07e_ufs_hardcoded_default` | `config/loader.py:102` (devolve `["PR", "SC", "RS"]` para lista não vazia) | `test_ufs_sem_corte_aceita_csv_e_normaliza_caixa` | **Morta** (`1 failed`: `['PR', 'SC', 'RS'] == ['MG', 'BA', 'SP']`) |
| `M07d_esferas_falsy_trap` | `config/loader.py:110` (`valor is None` → `not valor`) | `test_esferas_sem_corte_vazia_manda_e_nao_cai_no_padrao` | **Morta** (`1 failed`) |
| `M08c_cargos_lower` | `config/loader.py:123` (forçar `.lower()` nos termos) | `test_pci_mcp_cargos_aceita_csv_e_preserva_ordem` | **Morta** (`1 failed`: `'analista de sistemas' != 'Analista de Sistemas'`) |
| `M10a_sem_aviso_pci_slugs` | `config/loader.py:246` (`if target["pci_slugs"]:` → `if False:`) | `test_pci_mcp_com_slugs_avisa_mas_nao_desliga` | **Morta** (`1 failed`: `assert 0 == 1`) |
| `M10b_sem_aviso_pci_nacional` | `config/loader.py:248` (`if target["pci_nacional"]:` → `if False:`) | `test_pci_mcp_com_nacional_avisa_mas_nao_desliga` | **Morta** (`1 failed`: `assert 0 == 1`) |
| `M2d_sem_novos_cont` | `src/core/bot.py:284` (remoção de `novos_cont += resultado == "novo"`) | `test_contadores_do_mcp_e_do_gran_aparecem_no_resumo_final` | **Morta** (`1 failed`) |
| `M2d2_sem_atualizados_cont` | `src/core/bot.py:285` (remoção de `atualizados_cont += resultado == "atualizado"`) | `test_contadores_do_mcp_e_do_gran_aparecem_no_resumo_final` | **Morta** (`1 failed`) |
| `M2e_sem_validos` | `src/core/bot.py:281` (remoção de `validos += 1` no laço do MCP) | `test_validos_do_mcp_e_do_gran_aparecem_no_heartbeat` | **Morta** (`1 failed`) |
| `M1a_mcp_sempre_avalia_saude` | `src/core/bot.py:262` (avaliar `"pci_mcp"` na saúde mesmo com `mcp_scraper=None`) | `test_mcp_desligado_nao_instancia_scraper` | **Morta** (`1 failed`) |
| `M4b_sem_selo_no_card` | `src/core/bot.py:1041` (remover linha de `decisao.selo` no card) | `test_selo_sem_evidencia_aparece_no_card` | **Morta** (`1 failed`) |
| `M12_janela_1_dia` | `src/core/bot.py:835` (`timedelta(days=7)` → `timedelta(days=1)`) | `test_o_resumo_semanal_pede_sete_dias_ao_banco` | **Morta** (`1 failed`) |
| `M12b_formato_sem_hora` | `src/core/bot.py:836` (`"%Y-%m-%d %H:%M:%S"` → `"%Y-%m-%d"`) | `test_o_resumo_semanal_pede_sete_dias_ao_banco` | **Morta** (`1 failed`) |

## Conferência de vocabulário (`varredura` → `rodada`)

`git grep -n "varredura" src/core/bot.py tests/test_concurso_bot.py` antes e depois:
- Removidas exatamente as 4 ocorrências novas: `src/core/bot.py:807`, `src/core/bot.py:863`, `tests/test_concurso_bot.py:1333` (era `1331`) e `tests/test_concurso_bot.py:2048` (era `1972`).
- Todas as demais ocorrências legadas (`src/core/bot.py`: 23 linhas; `tests/test_concurso_bot.py`: 8 linhas) permaneceram intocadas.
