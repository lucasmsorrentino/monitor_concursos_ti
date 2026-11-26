ENTREGUE
Esteira: implementador · opus (claude-opus-5-5) · nível G- · esforço high · 2026-11-26 15:31 → 2026-11-26 15:40 (9 min)
Resumo: Esta é a rodada 7 do T-020, com o escopo da nota do arquiteto de 26/11/2026 às 15:30. Ela atende as três exigências do parecer 5, que pedem prova do critério de nulidade do `pci_id`, e corrige o comentário do índice que ainda falava em «matar» a duplicata. Nenhuma linha de lógica mudou: o diff de `src/database/manager.py` só mexe em linhas de comentário (conferido abaixo). Os três testes nascem verdes porque são guardas. Cada um foi provado por mutação, vermelho com a mutação do parecer e verde sem ela, com as duas saídas abaixo.
Arquivos: `tests/test_database_manager.py`, `src/database/manager.py` (só comentário). Os dois estão no `toca`.
Commits:
- `853fc30` test: o criterio de nulidade do pci_id provado no indice e no fallback de nome, pela escrita publica
- `45fc002` docs: o comentario do indice de unicidade conta o resolvedor que conserva as duas linhas
Testes: `PYTHONDONTWRITEBYTECODE=1 "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs -p no:cacheprovider` → base `219215f` 633 passed / 0 failed / 0 skipped (`633 passed in 231.28s`) · ponta `45fc002` 634 passed / 0 failed / 0 skipped (`634 passed in 127.45s`). A coleta na ponta deu `634 tests collected`. A conta fecha: 633 + 1 função nova (`test_chave_com_espaco_no_fim_e_outro_edital_na_unicidade`). As outras duas exigências reescreveram testes que já existiam, sem acrescentar casos. Medido no Windows, com o Python do venv, sem marcadores e sem variável de ambiente além de `PYTHONDONTWRITEBYTECODE`. Lint não configurado.
Testes que nascem verdes: os três desta rodada, por natureza. A nota do arquiteto proíbe mexer em comportamento, e o código entregue já cumpre a regra. São guardas, e a prova de valor deles é a mutação (seção «Prova por mutação»). Por isso não há commit `fix:` nesta rodada: o par é `test:` → `docs:`, e o `test:` não tem vermelho no código entregue, só sob mutação. Isso foi deliberado e segue a nota de 15:30, que troca o vermelho pela prova por mutação.
Desvios e riscos: listados por exigência abaixo. Nenhum desvio de escopo. Para o revisor olhar:
- `test_area_nome_is_unique` agora usa três gatilhos SQL que fazem o papel de «outro escritor» entre a busca e o INSERT. É o mesmo molde de `test_colisao_irresolvivel_vira_erro_no_log_nao_silencio`.
- O teste não foi renomeado, para não esbarrar na regra «nenhum teste renomeado». A docstring explica o que ele afirma hoje.
Pendências: as mesmas de antes, sem nada novo. Reparo das linhas colididas (T-023), alerta do dia (T-026, R-97), concorrência (T-027, R-98) e tabela de decisão da fusão (T-028, R-100). O OK do Lucas e o backup antes da primeira migração em produção continuam como passos da integração.

## Exigências do parecer 5, uma a uma

### 1. O critério de nulidade no índice, pela escrita pública
O que fiz: acrescentei `TestIdentidadePeloPciId::test_chave_com_espaco_no_fim_e_outro_edital_na_unicidade`.
- O teste grava dois editais de mesmo nome por `atualizar_concurso`, com `pci_id="296538"` e `pci_id="296538 "`.
- Afirma dois `id` positivos e distintos.
- Afirma também a leitura de cada um pela sua chave, via `buscar_registro`, com o status próprio.

### 2. O fallback de nome isolado no caso `[nome]`
O que fiz: em `test_pci_id_legado_nao_vazio_recusa_outro_pci_id_nos_tres_fallbacks`, cada caso agora define o nome gravado e a busca.
- O caso `[nome]` grava `IFSP` com chave `" "` e busca `ifsp` com chave `"296538"`, sem link. É o caso mínimo ASCII que o parecer deu.
- Os casos `[link]` e `[entidade]` ficaram com os mesmos dados de antes.
- Os três casos ganharam uma asserção a mais: a linha legada continua legível pela chave original `" "`, com `id`, nome e status intactos.
- A docstring explica por que o caso `[nome]` é ASCII: o `COLLATE NOCASE` só dobra ASCII.
- Isto aperta o teste e não o afrouxa: nenhuma asserção saiu.

### 3. A rejeição da unicidade observada por `atualizar_concurso`
O que fiz: reescrevi a observação de `TestSchemaCreation::test_area_nome_is_unique`, que é o teste da exceção nomeada do aceite. Ele não chama mais `INSERT` nem espera `IntegrityError`. O SQLite só prepara o cenário: três gatilhos `BEFORE INSERT` gravam a linha repetida entre a busca e o INSERT da escrita pública. Pela interface pública, o teste afirma:
- os dois IFSP de chaves distintas coexistem, com `id` distintos e positivos;
- as três tentativas devolvem 0: NULL com NULL (`TRF1`), NULL com `''` (`TRF2`, com o gatilho plantando `''`) e a mesma chave (`IFSP`/`297000`);
- saem três `ERROR` com «COLISAO DE IDENTIDADE»;
- no estado final, `buscar_registro` não acha `TRF1`, `TRF2` nem `297000`: o rollback não deixou meia escrita;
- os dois IFSP continuam com `id` e status originais.

### 4. O comentário que falava em «matar» a duplicata
O que fiz: corrigi o comentário em `_criar_indices` (`src/database/manager.py`, perto da definição de `idx_editais_identidade`). Agora ele diz três coisas:
- quem barra a duplicata sem chave é o índice;
- o `_resolver_nome_sem_colisao` não funde nem apaga linha, só evita dar a uma linha um nome ocupado;
- só NULL e `''` são ausência de chave, sem TRIM, como na busca.

Procurei o mesmo padrão no arquivo inteiro com `grep -n "matar\|elimina\|funde\|fusao\|fundir\|duplicat\|absorv\|junta\|herd" src/database/manager.py`. Sobraram:
- a docstring do módulo (linhas 69–70), já correta: «Nenhum caminho funde ou apaga linha»;
- a nota histórica do critério de nulidade (linha 95): «foi o que aconteceu com a fusao, antes de ela sair», que é verdadeira;
- a docstring de `_resolver_nome_sem_colisao` (linhas 629 e 633), já reescrita na rodada 6 e correta.

Também procurei «matar» e `_fundir` em `docs/adr/0005-identidade-do-concurso.md` e no `CLAUDE.md`. A única ocorrência é a do `CLAUDE.md`, que já descreve o `_fundir` como removido.

Só comentário mudou: `git diff 219215f..HEAD -- src/database/manager.py | grep '^[-+]' | grep -v '^[-+]\s*#'` devolve só as linhas de cabeçalho `---`/`+++`. `git diff --check 219215f..HEAD` saiu vazio.

## Prova por mutação

As mutações rodaram num worktree destacado em `853fc30`, no scratchpad, já removido. Comando base: `PYTHONDONTWRITEBYTECODE=1 <python do venv> -m pytest -q --tb=line -p no:cacheprovider tests/test_database_manager.py -k <seletor>`. Em cada ensaio, o `git diff` confirmou a mutação e o `git checkout` a desfez antes da corrida verde.

**Exigência 1.** Mutação: TRIM no índice.
```
-            "ON editais(area, nome, COALESCE(pci_id, ''))"
+            "ON editais(area, nome, COALESCE(TRIM(pci_id), ''))"
```
- Vermelho com a mutação:
```
...tests\test_database_manager.py:912: assert (1 > 0 and 0 > 0)
FAILED tests/test_database_manager.py::TestIdentidadePeloPciId::test_chave_com_espaco_no_fim_e_outro_edital_na_unicidade
1 failed, 83 deselected in 1.95s
```
- Verde sem ela: `1 passed, 83 deselected in 1.31s`.

**Exigência 2.** Mutação: TRIM só no filtro SQL da busca por nome (linha 419 de `src/database/manager.py`).
```
-            + so_sem_pci_id + _DESEMPATE,
+            + so_sem_pci_id.replace("NULLIF(pci_id, '')", "NULLIF(TRIM(pci_id), '')") + _DESEMPATE,
```
- Vermelho com a mutação:
```
...tests\test_database_manager.py:898: AssertionError: assert {'area': 'TI', 'cargos_total': None, 'data_fim_inscricao': None, 'elegibilidade': None, ...} is None
FAILED tests/test_database_manager.py::TestIdentidadePeloPciId::test_pci_id_legado_nao_vazio_recusa_outro_pci_id_nos_tres_fallbacks[nome]
1 failed, 2 passed, 81 deselected in 0.25s
```
- Verde sem ela: `3 passed, 81 deselected in 0.30s`.
- Contraprova, com os testes de `219215f` contra a mesma mutação: `3 passed, 80 deselected in 0.24s`. A versão anterior do caso `[nome]` não pegava a mutação, como o parecer mediu.

**Exigência 3.** Duas mutações no índice.

Mutação 3a: sem COALESCE, `"ON editais(area, nome, pci_id)"`.
- Vermelho com a mutação:
```
...tests\test_database_manager.py:149: assert {"NULL com ''...sma chave': 0} == {"NULL com ''...sma chave': 0}
FAILED tests/test_database_manager.py::TestSchemaCreation::test_area_nome_is_unique
1 failed, 83 deselected in 0.20s
```
- Itens divergentes com `-vv`:
```
{'NULL com NULL': 4} != {'NULL com NULL': 0}
{"NULL com ''": 6} != {"NULL com ''": 0}
```

Mutação 3b: o índice deixa de tratar `''` como nulo, `"ON editais(area, nome, COALESCE(pci_id, '-'))"`. Ela isola a combinação NULL com `''`.
- Vermelho com a mutação:
```
...tests\test_database_manager.py:149: assert {"NULL com ''...sma chave': 0} == {"NULL com ''...sma chave': 0}
FAILED tests/test_database_manager.py::TestSchemaCreation::test_area_nome_is_unique
1 failed, 83 deselected in 0.24s
```
- Item divergente com `-vv`:
```
{"NULL com ''": 4} != {"NULL com ''": 0}
```

Verde sem as mutações: `1 passed, 83 deselected in 0.29s`.

Contraprova, com todo o `tests/test_database_manager.py` de `219215f` contra a mutação 3b: `83 passed in 3.57s`. Antes desta rodada, nenhum teste do banco pegava a perda da equivalência entre NULL e `''` no índice.

## Testes alterados (nenhum apagado, nenhum renomeado)
- `TestSchemaCreation::test_area_nome_is_unique`: só a forma de observar mudou, da exceção do SQLite para a interface pública. As três rejeições (NULL com NULL, mesma chave e a nova NULL com `''`) e a coexistência das chaves distintas continuam afirmadas. É a exceção nomeada no aceite.
- `TestIdentidadePeloPciId::test_pci_id_legado_nao_vazio_recusa_outro_pci_id_nos_tres_fallbacks`: dados do caso `[nome]` trocados para ASCII, mais uma asserção por caso. Nasceu nesta branch (`0dda815`), não vem da `main`.
