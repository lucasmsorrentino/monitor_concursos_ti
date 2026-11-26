ENTREGUE
Esteira: implementador · opus (claude-opus-5-5) · nível G- · esforço high · 2026-11-26 13:41 → 2026-11-26 13:53 (13 min)
Resumo: Quinta rodada, só o ACHADO 2 (decisão do arquiteto de 26/11 13:41). `_fundir` deixou de gravar `pci_id`: ela só mexe em colunas fora da unicidade (estado, fase, prazo, link, fonte). `_resolver_nome_sem_colisao` devolve `(nome, pci_id)` finais, e `atualizar_concurso` grava os dois no mesmo `UPDATE` da linha casada, depois das fusões. A chave herdada nunca é aplicada com o nome antigo. Também acrescentei as duas exigências de teste do parecer (mutação do desempate pelo `pci_id` e rollback depois de fusão). São só testes, sem mexer em concorrência, no WAL, na ordem de identidade ou no desempate.
Arquivos: src/database/manager.py, tests/test_database_manager.py, docs/adr/0005-identidade-do-concurso.md, CLAUDE.md (todos no «toca»)
Commits:
- 95de698 test: a fusao grava nome e chave finais juntos, e a colisao depois dela desfaz tudo
- 21bda8d fix: a fusao grava nome e chave finais no mesmo UPDATE, sem estado intermediario
- 09b4d0a docs: nome e chave finais no mesmo UPDATE da fusao, na ADR-0005, no CLAUDE.md e nas docstrings
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs -p no:cacheprovider` → base e9f57ca 614 passed / 0 failed / 0 skipped (`614 passed in 94.95s`) · ponta 09b4d0a 617 passed / 0 failed / 0 skipped (`617 passed in 183.36s`). Coleta na ponta: `617 tests collected in 1.92s`. As contas fecham: 614 + 3 novos = 617. Medi sem variáveis de ambiente do projeto e sem marcadores. Lint não configurado. `git diff --check` limpo antes do commit de docs.
Vermelho do commit `test:` (`-k "nome_e_chave_finais or desfaz_a_fusao or nao_depende_do_indice"`): `1 failed, 2 passed`. A falha é `test_fusao_grava_nome_e_chave_finais_juntos_sem_colidir_no_meio`, com `assert 0 == 1` e o log `COLISAO DE IDENTIDADE ... (UNIQUE constraint failed: index 'idx_editais_identidade')`. É exatamente o empate no meio da fusão, e não falha de coleta.

Cada exigência do retorno:
- ACHADO 2 (R-82, ADR-0005, colisão no estado intermediário da fusão): consertado em 21bda8d. O teste `test_fusao_grava_nome_e_chave_finais_juntos_sem_colidir_no_meio` usa as três linhas do parecer, `(1, "IFSP - SP", NULL)`, `(2, "IFSP - SP", 296538)` e `(3, "IFSP", 296538, seguindo)`, e atualiza pelo link específico. Ele afirma retorno 1, nome "IFSP", status "novo", chave 296538 e `seguindo` herdado da linha 3. A linha 2 fica intacta (id, nome, status, chave), e no fim sobra uma linha `pci_mcp` e uma `gran`.
- ACHADO 1 (concorrência): fora desta rodada por decisão do arquiteto (virou o T-027, R-98). Não toquei.
- Exigência de teste 1 (o empate pelo `pci_id` tem de falhar sem o desempate): `test_busca_pelo_pci_id_empatada_nao_depende_do_indice` cria um índice `(area, pci_id, id DESC)`. Conferi a mutação `_DESEMPATE = ""`, com diff de 1 linha e revertida em seguida: `1 failed, 1 passed`, `assert (2, 'mais nova') == (1, 'mais antiga')`. O teste antigo é o que passa. Sem a mutação: `2 passed`. Pelo `EXPLAIN QUERY PLAN`, num banco de rascunho, as duas consultas usam `idx_ordem_contraria`: a sem `ORDER BY` devolve o id 2 e a com `ORDER BY id` devolve o 1. Primeiro escrevi o teste com `ANALYZE`, e a mutação sobreviveu. Tirei o `ANALYZE` antes do commit.
- Exigência de teste 2 (prova de rollback depois de fusão): `test_colisao_depois_de_uma_fusao_desfaz_a_fusao` monta duas grafias do Gran e um gatilho que aborta só o `UPDATE` final (`RAISE(ABORT, 'UNIQUE constraint failed ...')`). Pela API, ele afirma retorno 0, o erro nomeado, duas linhas `gran` e as duas linhas com id, nome e status originais. Conferi a mutação que troca o `rollback()` do `except sqlite3.IntegrityError` por `pass`, com diff de 1 linha e revertida em seguida: `1 failed`.
- Busca do mesmo padrão no repo (outra escrita que grave coluna da unicidade antes do nome final): `grep -rn "pci_id = COALESCE\|SET nome\|nome = ?" src/ | grep -v "WHERE\|AND nome"` retorna só `src/database/manager.py:566: SET nome = ?,` e `:573: pci_id = COALESCE(?, pci_id),`. As duas linhas são o `UPDATE` final único de `atualizar_concurso`. Nenhum outro ponto grava `nome` ou `pci_id`.

Testes que nascem verdes: dois, os dois guardas pedidos pelo revisor. Cada um foi provado por mutação, com os números acima.
- `test_busca_pelo_pci_id_empatada_nao_depende_do_indice`: o desempate pelo menor id já existia desde 63e99a4.
- `test_colisao_depois_de_uma_fusao_desfaz_a_fusao`: o rollback já existia.

Desvios e riscos:
- O tipo de retorno de `_resolver_nome_sem_colisao`, que é privada, passou de `str` para `(str, str | None)`. O único chamador é `atualizar_concurso`.
- O valor da chave final agora sai do Python (`pci_id_da_linha`, já normalizado por `_pci_id_ou_none`), não do `COALESCE(NULLIF(pci_id,''), ?)` da fusão. O critério de nulidade é o mesmo nas duas formas. Linha legada com `''` continua herdando, e com `' '` continua sendo chave. Os testes da rodada 3 seguem verdes.
- No retorno «não é o mesmo órgão», `mesmo_orgao` não varia dentro do laço. Por isso esse retorno só acontece antes de qualquer fusão e não perde chave herdada. Deixei um comentário no código.
- A docstring foi para o commit `docs:`, separada do código. As linhas de comentário que explicam o `UPDATE` ficaram no `fix:`.

Pendências: concorrência no T-027 (R-98). Alerta do dia no T-026 (R-97). Reparo das linhas já colididas no T-023. O gate «OK do Lucas:» segue aberto, e a primeira execução em produção exige backup do banco. O `CLAUDE.md` ainda diz «full suite (539 tests)», número antigo fora do escopo deste ticket.
