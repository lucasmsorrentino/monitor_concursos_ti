APROVADO
Esteira: revisor · agy-argon (gemini-4-argon) · nível M+ · esforço high · 2026-11-23 17:53 → 2026-11-23 18:00 (7 min)
Resumo: Revisão da entrega do T-005 (schema v6 aditivo e idempotente em `editais`, persistência dos sete campos novos em `atualizar_concurso` e consulta `listar_filtrados`). Todos os 11 itens de aceite e os 14 testes do plano foram cumpridos, o ciclo TDD em três fatias foi verificado em worktree destacado, e 11 mutações (uma por item de aceite) foram mortas pela suíte.
Arquivos: `src/database/manager.py` · `tests/test_database_manager.py` (nenhum fora do «toca»)
Commits: `e9bcc9a test: schema v6 exige sete colunas em banco novo e migrado` · `e72b5d2 feat: schema v6 aditivo com sete colunas no ensure_schema e no create` · `dd35b3f chore: esqueleto dos campos v6 em atualizar_concurso e do listar_filtrados` · `f5e66cf test: gravacao dos campos v6 com coalesce e decisao que vence` · `f840b8b feat: atualizar_concurso grava os sete campos v6 no insert e no update` · `83d85f9 test: listar_filtrados exige so filtrado, da area, desde a data, teto desc` · `a3e1218 feat: listar_filtrados consulta filtrados da area ordenados por teto desc` · `e6b399e docs: schema v6 no cabecalho do manager, regras de gravacao e contrato do listar_filtrados`
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs` → base `296 passed / 0 failed / 0 skipped` (24.59s) · ponta `310 passed / 0 failed / 0 skipped` (24.08s)
Testes que nascem verdes: `test_linha_pre_v6_nao_e_tocada` (guarda declarada pelo implementador: antes do `feat:` da fatia 2 o `UPDATE` não tocava em `elegibilidade`, mantendo `NULL`; pega mutação de backfill indevido em `_ensure_schema`)
Desvios e riscos: `_migrate_to_v3` também recebeu as sete colunas novas para manter simetria com `_create_v3_table` (dentro do `toca`, sem efeito colateral); em `atualizar_concurso`, `COALESCE(?, elegibilidade)` e `COALESCE(?, motivo_filtro)` implementam exatamente a regra de negócio exigida (valor novo no primeiro argumento sobrescreve o antigo; `None` preserva o valor gravado).
Pendências: Decisão de elegibilidade (`src/core/elegibilidade.py`), chamada de `listar_filtrados`, montagem do resumo semanal e fiação no bot ficam para os próximos tickets, conforme a seção «Fora do escopo».

## Spec

1. **Cumprimento do aceite (11/11 itens atendidos):**
   - **Sete colunas novas em `_ensure_schema` guardadas por `PRAGMA table_info`:** cumprido em `src/database/manager.py:147-160` (`uf TEXT`, `regiao TEXT`, `esfera TEXT`, `cargos_total INTEGER`, `salario_teto REAL`, `elegibilidade TEXT`, `motivo_filtro TEXT`), provado por `test_migracao_do_v5_acrescenta_as_colunas` (`tests/test_database_manager.py:233-260`).
   - **Mesmas sete colunas em `_create_v3_table`:** cumprido em `src/database/manager.py:183-189` (e espelhado em `_migrate_to_v3` em `src/database/manager.py:213-219`), provado por `test_creates_table_on_fresh_db` (`tests/test_database_manager.py:75-86`) e `test_banco_novo_tem_as_colunas_do_v6` (`tests/test_database_manager.py:222-231`).
   - **Migração idempotente:** cumprido em `src/database/manager.py:122-160`, provado por `test_migracao_e_idempotente` (`tests/test_database_manager.py:262-277`) abrindo o mesmo banco três vezes seguidas.
   - **Nada se perde na migração do v5:** cumprido sem `DROP` nem backfill nas colunas v6 (`src/database/manager.py:147-160`), provado por `test_migracao_do_v5_acrescenta_as_colunas` (`tests/test_database_manager.py:244-259`), que confere preservação das linhas `SEFIN RO` (`fonte='pci'`, `pci_id='pci-123'`) e `TRF1` (`fonte='gran'`) e `NULL` nas sete colunas novas.
   - **`atualizar_concurso` aceita e grava os sete campos opcionais (`None` por padrão) com `COALESCE` no `UPDATE`:** cumprido em `src/database/manager.py:364-370` (assinatura), `413-417` (`UPDATE`) e `437-444` (`INSERT`), provado por `test_atualizar_concurso_grava_campos_novos` (`tests/test_database_manager.py:305-320`), `test_coalesce_preserva_uf_quando_vem_none` (`322-326`) e `test_coalesce_preserva_salario_teto_quando_vem_none` (`328-335`).
   - **`elegibilidade` e `motivo_filtro` sobrescritos quando vem valor e preservados quando vem `None`:** cumprido em `src/database/manager.py:420-421` (`COALESCE(?, elegibilidade)` e `COALESCE(?, motivo_filtro)` avaliam o parâmetro novo `?` primeiro, sobrescrevendo quando não nulo e mantendo o valor da coluna quando `None`), provado por `test_elegibilidade_e_sobrescrita_quando_vem_valor` (`tests/test_database_manager.py:337-345`) e `test_elegibilidade_e_preservada_quando_vem_none` (`347-353`).
   - **`buscar_registro` devolve as sete colunas novas no dict:** cumprido via `SELECT * FROM editais` e `dict(row)` em `src/database/manager.py:258-300`, provado em `test_atualizar_concurso_grava_campos_novos` (`tests/test_database_manager.py:313-320`) e `test_migracao_do_v5_acrescenta_as_colunas` (`246-259`).
   - **`listar_filtrados(desde: str) -> list[dict]`:** cumprido em `src/database/manager.py:322-351`, filtrando `area = ?`, `elegibilidade = 'filtrado'` e `ultima_atualizacao >= ?`, ordenando por `salario_teto IS NULL, salario_teto DESC` e retornando `nome`, `uf`, `salario_teto`, `motivo_filtro` e `link`. Provado por `test_listar_filtrados_so_traz_filtrado` (`tests/test_database_manager.py:501-519`), `test_listar_filtrados_respeita_desde` (`521-544`) e `test_listar_filtrados_ordena_por_teto_desc_com_null_no_fim` (`565-584`).
   - **`listar_filtrados` não vaza área:** cumprido em `src/database/manager.py:344`, provado por `test_listar_filtrados_nao_vaza_area` (`tests/test_database_manager.py:546-563`).
   - **`listar_filtrados` com `desde` no futuro devolve `[]`:** cumprido em `src/database/manager.py:346,351`, provado por `test_listar_filtrados_futuro_vazio` (`tests/test_database_manager.py:586-590`).
   - **Linha pré-v6 permanece com `elegibilidade` nulo e não entra em `listar_filtrados`:** cumprido em `src/database/manager.py:144-160,345`, provado por `test_linha_pre_v6_nao_e_tocada` (`tests/test_database_manager.py:355-362`) e `test_listar_filtrados_so_traz_filtrado` (`509-514`).
2. **Escopo:** `git diff --stat 16543aae6eca14e52d1de0cbeb519a19f92c7e06..HEAD` toca exclusivamente `src/database/manager.py` (+113/-1) e `tests/test_database_manager.py` (+281/-11), ambos listados em `toca`. Nenhum código especulativo foi introduzido.
3. **Conformidade com a SPEC-001 e ADRs:** confere com `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md:145-156` (seção 3.5 — colunas v6, ausência de backfill e assinatura de `listar_filtrados`), `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md:212-217` (R-10, R-11, R-13) e `docs/adr/0002-elegibilidade-pelo-teto-do-concurso.md:33`. A comparação lexicográfica `ultima_atualizacao >= desde` sobre `AAAA-MM-DD HH:MM:SS` está documentada em comentário (`src/database/manager.py:334-337`), como pedido nas notas do arquiteto.

## Prova

4. **Números reais (medidos pelo revisor vs. afirmados pelo implementador):**
   - Condição de medição: ambiente Windows padrão, Python do `.venv` do repositório, sem variáveis de ambiente adicionais nem filtro de marcadores. Lint não configurado no repositório.
   - **Base (`16543aae6eca14e52d1de0cbeb519a19f92c7e06`):**
     - Implementador afirmou: `296 passed / 0 failed` (`0 skipped`).
     - Revisor mediu (`"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs` e `--collect-only -q` em worktree destacado): `296 passed in 24.59s` (`296 tests collected`, `0 failed`, `0 skipped`).
   - **Ponta (`e6b399e670da0b534e566034ba4788422fa1ef8d`):**
     - Implementador afirmou: `310 passed / 0 failed` (`310 tests collected`, `0 skipped`).
     - Revisor mediu (`"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs` e `--collect-only -q`): `310 passed in 24.08s` (`310 tests collected`, `0 failed`, `0 skipped`).
   - **Fechamento da conta:** `296 (base) + 14 (novos em tests/test_database_manager.py) = 310 (ponta)`.
5. **Verificação do ciclo TDD em worktree destacado (`git worktree add --detach`):**
   - Fatia 1 — `e9bcc9a` (`test:`): `4 failed, 26 passed in 0.51s` (`AssertionError` na comparação de `PRAGMA table_info(editais)` com `COLUNAS_V6` / `COLUNAS_NOVAS_V6`) → `e72b5d2` (`feat:`): `30 passed in 0.36s`.
   - Esqueleto — `dd35b3f` (`chore:`): adiciona os 7 kwargs em `atualizar_concurso` e `listar_filtrados` com `raise NotImplementedError`.
   - Fatia 2 — `f5e66cf` (`test:`): `5 failed, 31 passed in 0.64s` (`AssertionError` nos valores devolvidos por `buscar_registro`; `test_linha_pre_v6_nao_e_tocada` nasce verde como guarda, declarada no relatório) → `f840b8b` (`feat:`): `36 passed in 0.40s`.
   - Fatia 3 — `83d85f9` (`test:`): `5 failed, 36 passed in 0.68s` (`NotImplementedError` em `listar_filtrados`) → `a3e1218` (`feat:`): `41 passed in 0.49s`.
   - Documentação — `e6b399e` (`docs:`): altera apenas docstrings em `src/database/manager.py`, separado de mudanças de código.
6. **Qualidade dos testes e prova por mutação (em worktree destacado sobre `HEAD`):**
   - Os 14 testes exercitam a costura pública (`DatabaseManager`, `atualizar_concurso`, `buscar_registro`, `listar_filtrados`) sobre banco SQLite real em `tmp_path` e usam `PRAGMA table_info(editais)` e literais escritos à mão como oráculo independente. Em `test_listar_filtrados_respeita_desde`, o `UPDATE` direto em SQL é usado apenas no arranjo de `ultima_atualizacao` (que a interface pública não parametriza), enquanto ação e asserção passam por `listar_filtrados`.
   - Mutações executadas e mortas:
     - **M1 (omitir `motivo_filtro` em `_ensure_schema`):** `2 failed` (`test_migracao_do_v5_acrescenta_as_colunas`, `test_migracao_e_idempotente`).
     - **M2 (omitir `salario_teto` em `_create_v3_table`):** `24 failed` (incluindo `test_creates_table_on_fresh_db` e `test_banco_novo_tem_as_colunas_do_v6`).
     - **M3 (inverter guarda `if "uf" not in column_names` em `_ensure_schema`):** `4 failed` (incluindo `test_migracao_do_v5_acrescenta_as_colunas`, `test_migracao_e_idempotente`).
     - **M4 (trocar `uf = COALESCE(?, uf)` por `uf = ?`):** `1 failed` (`test_coalesce_preserva_uf_quando_vem_none`).
     - **M5 (trocar `salario_teto = COALESCE(?, salario_teto)` por `salario_teto = ?`):** `1 failed` (`test_coalesce_preserva_salario_teto_quando_vem_none`).
     - **M6a (inverter `COALESCE(?, elegibilidade)` para `COALESCE(elegibilidade, ?)`):** `1 failed` (`test_elegibilidade_e_sobrescrita_quando_vem_valor`).
     - **M6b (trocar `elegibilidade = COALESCE(?, elegibilidade)` por `elegibilidade = ?`):** `1 failed` (`test_elegibilidade_e_preservada_quando_vem_none`).
     - **M7 (remover filtro `elegibilidade = 'filtrado'` em `listar_filtrados`):** `1 failed` (`test_listar_filtrados_so_traz_filtrado`).
     - **M8 (neutralizar filtro `ultima_atualizacao >= ?` com `(? IS NOT NULL)`):** `2 failed` (`test_listar_filtrados_respeita_desde`, `test_listar_filtrados_futuro_vazio`).
     - **M9 (neutralizar filtro `area = ?` com `(? IS NOT NULL)`):** `2 failed` (incluindo `test_listar_filtrados_nao_vaza_area`).
     - **M10a/M10b (inverter ordenação de `salario_teto` para `ASC` ou `IS NOT NULL` primeiro):** `1 failed` cada (`test_listar_filtrados_ordena_por_teto_desc_com_null_no_fim`).
     - **M11 (backfill indevido `DEFAULT 'elegivel'` em `_ensure_schema`):** `2 failed` (`test_migracao_do_v5_acrescenta_as_colunas`, `test_linha_pre_v6_nao_e_tocada`).

## Padrões

7. **Regras do projeto (`kanban/REGRAS.md` e `GLOSSARIO.md`):**
   - Vocabulário alinhado ao `GLOSSARIO.md` (`area`, `teto do concurso` / `salario_teto`, `esfera`, `elegibilidade`, `rodada`).
   - Código, docstrings e mensagens de commit em português do Brasil; identificadores e comentários sem acento.
   - Migração de schema estritamente aditiva e idempotente dentro de `_ensure_schema` (`ALTER TABLE ... ADD COLUMN` guardado por `PRAGMA table_info`).
   - Nenhum ID de ticket (`T-NNN`) em código, comentário, docstring ou mensagem de commit; sem dependências novas, sem acesso à rede nos testes e sem `git push`.
8. **Cheiros de código:**
   - Nenhum cheiro acionável identificado. A lista longa de parâmetros opcionais em `atualizar_concurso` (`src/database/manager.py:353-371`) decorre diretamente do contrato exigido pelo critério de aceite 5 do ticket.
