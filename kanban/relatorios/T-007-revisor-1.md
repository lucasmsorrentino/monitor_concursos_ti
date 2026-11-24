APROVADO
Esteira: revisor · agy-argon (gemini-4-argon) · nível M+ · esforço high · 2026-11-23 18:03 → 2026-11-23 18:10 (7 min)
Resumo: Revisão da entrega do T-007 (`src/core/resumo_filtrados.py` e `tests/test_resumo_filtrados.py`). Todos os 11 itens do critério de aceite e as regras `R-20`, `R-21` e `R-22` da `SPEC-001` seção 4.4 foram cumpridos dentro do escopo (`toca`), com ciclo TDD comprovado em worktree destacado (vermelho nos dois commits `test:` por `NotImplementedError`) e 12 mutações capturadas pela suíte.
Arquivos: `src/core/resumo_filtrados.py`, `tests/test_resumo_filtrados.py` (nenhum arquivo fora do `toca`)
Commits: 9cb413f chore: esqueleto do resumo semanal de filtrados · 945e26c test: resumo semanal exige contagens, rotulos, corte e escape · e2f8e9e feat: monta o texto do resumo semanal de filtrados · ad3cf48 test: marcador da semana usa semana ISO inclusive na virada do ano · 8314869 feat: marcador da semana com ano e semana ISO
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs` → base 296 passed / 0 failed / 0 skipped (24.64s) · ponta 313 passed / 0 failed / 0 skipped (24.32s)
Testes que nascem verdes: `test_modulo_e_puro_sem_banco_rede_ou_bot` (guarda estática via `ast` que proíbe imports de banco, rede e bot; nasce verde porque o esqueleto em `9cb413f` já nascia puro importando apenas `datetime.date`, declarada no relatório do implementador)
Desvios e riscos: Nenhum desvio que comprometa o aceite. Não houve commit `docs:` separado porque não há documentação fora das docstrings do módulo novo no `toca`.
Pendências: `listar_filtrados` no banco e fiação do envio semanal + gravação do marcador em arquivo no `ConcursoBot` (escopo de outros tickets da `SPEC-001`).

## Spec

1. **Critério de aceite cumprido integralmente:**
   - **Assinatura de `montar`:** `src/core/resumo_filtrados.py:57` expõe `montar(linhas: list[dict], area_nome: str, limite: int = 30) -> str | None`. Provado por `test_corta_em_trinta_e_diz_quantas_faltam` (`tests/test_resumo_filtrados.py:87-93`) e `test_limite_customizado` (`tests/test_resumo_filtrados.py:96-101`).
   - **Lista vazia devolve `None` (`R-21`):** `src/core/resumo_filtrados.py:70-71`. Provado por `test_lista_vazia_devolve_none` (`tests/test_resumo_filtrados.py:26-27`).
   - **Ordem das seções (título com área, contagem total, contagem por motivo decrescente, lista de linhas):** `src/core/resumo_filtrados.py:73-82` (`Counter.most_common()`). Provado por `test_nome_da_area_aparece` (`tests/test_resumo_filtrados.py:111-113`), `test_traz_contagem_total` (`tests/test_resumo_filtrados.py:30-33`), `test_traz_contagem_por_motivo_em_ordem_decrescente` (`tests/test_resumo_filtrados.py:36-40`) e `test_secoes_na_ordem_do_aceite` (`tests/test_resumo_filtrados.py:116-128`).
   - **Formato de cada linha e teto `None`:** `src/core/resumo_filtrados.py:25,31-39,47-54` formata reais sem `locale` (`R$ 8.628,87`, `R$ 1.000.000,00`) e emite `"teto nao lido"` quando `salario_teto is None`. Provado por `test_linha_traz_orgao_uf_teto_e_motivo` (`tests/test_resumo_filtrados.py:43-57`), `test_teto_none_sai_como_nao_lido` (`tests/test_resumo_filtrados.py:60-64`) e `test_formata_teto_no_padrao_brasileiro` (`tests/test_resumo_filtrados.py:77-84`).
   - **UF `None` sai como `Nacional`:** `src/core/resumo_filtrados.py:28,50`. Provado por `test_uf_none_sai_como_nacional` (`tests/test_resumo_filtrados.py:67-69`).
   - **Rótulos de motivo legíveis e fallback para desconhecido:** constante `ROTULOS_MOTIVO` em `src/core/resumo_filtrados.py:18-21` e `_rotulo_de` em `src/core/resumo_filtrados.py:42-44`. Provado por `test_linha_traz_orgao_uf_teto_e_motivo` e `test_motivo_desconhecido_nao_levanta` (`tests/test_resumo_filtrados.py:72-74`).
   - **Corte em `limite` com `"e mais N"` e contagem total preservada no topo:** `src/core/resumo_filtrados.py:73,77,82-84`. Provado por `test_corta_em_trinta_e_diz_quantas_faltam` (`tests/test_resumo_filtrados.py:87-93`) e `test_limite_customizado` (`tests/test_resumo_filtrados.py:96-101`).
   - **HTML do Telegram e `html.escape` nos dados das linhas:** `src/core/resumo_filtrados.py:49-53,76-77` segue o padrão de `src/core/bot.py:305-320`. Provado por `test_escapa_html_do_nome` (`tests/test_resumo_filtrados.py:104-108`).
   - **`marcador_da_semana(hoje: date) -> str` com semana ISO na virada do ano:** `src/core/resumo_filtrados.py:88-96` usa `hoje.isocalendar()` (`ano_iso, semana, _`). Provado por `test_marcador_da_semana_e_estavel_na_mesma_semana` (`tests/test_resumo_filtrados.py:131-135`), `test_marcador_da_semana_muda_na_semana_seguinte` (`tests/test_resumo_filtrados.py:138-142`) e `test_marcador_da_semana_na_virada_do_ano` (`tests/test_resumo_filtrados.py:145-148`, onde `2026-12-28` e `2027-01-03` devolvem `"2026-S53"`).
   - **Módulo puro:** `src/core/resumo_filtrados.py:11-13` importa apenas `collections.Counter`, `datetime.date` e `html`. Provado por `test_modulo_e_puro_sem_banco_rede_ou_bot` (`tests/test_resumo_filtrados.py:151-165`).
2. **Escopo:** `git diff --stat 16543aae6eca14e52d1de0cbeb519a19f92c7e06..HEAD` toca exclusivamente `src/core/resumo_filtrados.py` (+96) e `tests/test_resumo_filtrados.py` (+165). Zero arquivo fora do `toca`.
3. **Aderência à Spec e ADRs:**
   - `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md:142-143` (seção 3.4) e `194-205` (seção 4.2): os dois únicos motivos que filtram são `abaixo_do_corte` e `municipal_inflado`, cobertos por `ROTULOS_MOTIVO`.
   - `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md:147-155` (seção 3.5): chaves lidas (`nome`, `uf`, `salario_teto`, `motivo_filtro`) batem com o schema v6 de `listar_filtrados`.
   - `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md:224-232` (seção 4.4, `R-20`, `R-21`, `R-22`) e `docs/adr/0002-elegibilidade-pelo-teto-do-concurso.md:33`: cumpridos sem divergência.

## Prova

4. **Medição independente dos testes (sem variáveis de ambiente extras, sem marcadores, Python 3.12 do `.venv` no Windows):**
   - **Base (`16543aae6eca14e52d1de0cbeb519a19f92c7e06`, `git merge-base main HEAD`):**
     - Comando: `& "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs`
     - Medido pelo revisor: `296 passed in 24.64s` (0 failed, 0 skipped) · Afirmado pelo implementador: `296 passed / 0 failed · 0 pulados`.
   - **Ponta (`8314869b481c9bac06ed5439cf066dfa05af69ae`, `HEAD`):**
     - Comando: `& "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs`
     - Medido pelo revisor: `313 passed in 24.32s` (0 failed, 0 skipped) · Afirmado pelo implementador: `313 passed / 0 failed · 0 pulados`.
   - **Fechamento da conta:** `296 (base) + 17 (novos em tests/test_resumo_filtrados.py) = 313 (ponta)`.
   - **Lint:** não configurado no repositório (`(não configurado)`), não aplicável.
5. **Verificação do TDD em worktree destacado (`git worktree add --detach`):**
   - Ordem dos commits (`16543aa..8314869`): `chore:` (esqueleto) → `test:` → `feat:` → `test:` → `feat:`.
   - **Prova do vermelho da fatia 1 (`945e26c`):** `& "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest tests/test_resumo_filtrados.py -q` → `13 failed, 1 passed in 0.31s`. Todas as 13 falhas por `NotImplementedError: montar ainda nao esta implementado` (1 passando: guarda de pureza `test_modulo_e_puro_sem_banco_rede_ou_bot`).
   - **Prova do vermelho da fatia 2 (`ad3cf48`):** `& "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest tests/test_resumo_filtrados.py -q` → `3 failed, 14 passed in 0.33s`. Todas as 3 falhas novas por `NotImplementedError: marcador_da_semana ainda nao esta implementado`.
6. **Qualidade dos testes e prova por mutação na ponta (`8314869`):**
   - Testes afirmam comportamento pela costura pública (`montar` e `marcador_da_semana`), por substring e posição, com oráculos literais independentes e sem dublês.
   - **12 mutações aplicadas em worktree destacado** (conferidas com `git diff -U0` antes de rodar `pytest tests/test_resumo_filtrados.py -q`), todas capturadas pelo vermelho:
     1. `limite: int = 30` → `limite: int = 10` (`resumo_filtrados.py:57`): `1 failed` (`test_corta_em_trinta_e_diz_quantas_faltam`).
     2. `return None` → `return ''` (`resumo_filtrados.py:71`): `1 failed` (`test_lista_vazia_devolve_none`).
     3. `contagens.most_common()` → `reversed(contagens.most_common())` (`resumo_filtrados.py:80`): `1 failed` (`test_traz_contagem_por_motivo_em_ordem_decrescente`).
     4. `if teto is not None else TETO_NAO_LIDO` → `if True else TETO_NAO_LIDO` (`resumo_filtrados.py:52`): `1 failed` (`test_teto_none_sai_como_nao_lido`).
     5. `inteiro.replace(',', '.')` → `inteiro` sem troca (`resumo_filtrados.py:39`): `2 failed` (`test_linha_traz_orgao_uf_teto_e_motivo`, `test_formata_teto_no_padrao_brasileiro`).
     6. `UF_NACIONAL = "Nacional"` → `"None"` (`resumo_filtrados.py:28`): `1 failed` (`test_uf_none_sai_como_nacional`).
     7. `ROTULOS_MOTIVO.get(motivo, motivo)` → `ROTULOS_MOTIVO[motivo]` (`resumo_filtrados.py:44`): `1 failed` (`test_motivo_desconhecido_nao_levanta`).
     8. `if total > limite:` → `if False:` (`resumo_filtrados.py:83`): `2 failed` (`test_corta_em_trinta_e_diz_quantas_faltam`, `test_limite_customizado`).
     9. Remoção de `html.escape` do nome (`resumo_filtrados.py:49`): `1 failed` (`test_escapa_html_do_nome`).
     10. Formato ISO `f"{ano_iso}-S{semana:02d}"` → `f"{ano_iso}-W{semana:02d}"` (`resumo_filtrados.py:96`): `1 failed` (`test_marcador_da_semana_na_virada_do_ano`).
     11. Ano civil `f"{hoje.year}-S{semana:02d}"` em vez de `ano_iso` (`resumo_filtrados.py:96`): `1 failed` (`test_marcador_da_semana_na_virada_do_ano`).
     12. Adição de `import sqlite3` (`resumo_filtrados.py:14`): `1 failed` (`test_modulo_e_puro_sem_banco_rede_ou_bot`).

## Padrões

7. **Regras e padrões do projeto:**
   - Idioma e acentuação: português do Brasil em código, docstrings e mensagens de commit; identificadores e comentários sem acento (`src/core/resumo_filtrados.py`, `tests/test_resumo_filtrados.py`).
   - Vocabulário aderente ao `GLOSSARIO.md` (`area_nome`, `teto`/`salario_teto`, `motivo_filtro`, `municipal_inflado`).
   - Sem segredos, sem dependências novas, sem acesso à rede nos testes, sem menção a IDs `T-NNN` no código ou docstrings, sem `git push`.
8. **Cheiros de código:**
   - Nenhum cheiro identificado; funções curtas, coesas e sem generalidade especulativa.
