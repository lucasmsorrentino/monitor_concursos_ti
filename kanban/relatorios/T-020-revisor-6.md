APROVADO COM RESSALVAS
Esteira: revisor · agy-neon (gemini-4-neon) · nível G- · esforço high · 2026-11-26 15:41 → 2026-11-26 15:50 (9 min)
Resumo: Revisei a entrega completa do T-020 (com foco nas quatro exigências da rodada 7 sobre `219215f..45fc002` e conferência integral contra a `merge-base` `ce24615`). Os critérios de aceite (R-80 a R-86, R-99, desempate por menor `id`, critério único de nulidade, migração v7 idempotente e ADR-0005/CLAUDE.md) estão cumpridos, nenhuma linha de lógica mudou na rodada 7 e todas as mutações exigidas e adicionais foram pegas pela suíte. Ficam apenas duas ressalvas pequenas e não bloqueantes em `tests/test_database_manager.py`.
Arquivos: `CLAUDE.md`, `docs/adr/0005-identidade-do-concurso.md`, `src/database/manager.py`, `tests/test_database_manager.py` (todos dentro do `toca` em `ce24615..45fc002`; na rodada 7 `219215f..45fc002`, apenas `tests/test_database_manager.py` e comentários em `src/database/manager.py`).
Commits:
- `3deba35` test: identidade pelo pci_id e unicidade que admite dois editais do mesmo orgao
- `47291be` fix: o pci_id que discorda vence o nome, e a unicidade admite dois editais do mesmo orgao
- `17537ba` docs: ADR-0005, identidade do concurso e unicidade com o pci_id
- `fa09826` test: a fusao pelo nome leva todas as grafias do orgao e nunca dois editais
- `31e9b24` fix: a fusao pelo nome leva todas as grafias do mesmo orgao, nunca dois editais
- `cfdf2b5` test: pci_id vazio conta como nulo na escrita, na busca e na fusao
- `a4f2d58` fix: pci_id vazio entra como nulo e a fusao nao o trata como chave
- `58033e2` docs: schema v7 e a fusao de todas as grafias no CLAUDE.md, na ADR-0005 e nas docstrings
- `ff8e48d` Merge branch 'main' into t/T-020-identidade-do-concurso-o-pci-id-que-disc
- `0dda815` test: um criterio so de nulidade do pci_id na busca e na fusao
- `59d67a6` fix: o pci_id tem um criterio so de nulidade, na busca, na fusao e no indice
- `1482816` docs: o criterio unico de nulidade do pci_id na ADR-0005 e no CLAUDE.md
- `4ceb387` test: busca empatada escolhe a linha mais antiga, nos tres fallbacks e no pci_id
- `63e99a4` fix: busca de identidade empatada escolhe a linha de menor id, nunca a do indice
- `e9f57ca` docs: o desempate pela linha de menor id na ADR-0005, no CLAUDE.md e na docstring da busca
- `95de698` test: a fusao grava nome e chave finais juntos, e a colisao depois dela desfaz tudo
- `21bda8d` fix: a fusao grava nome e chave finais no mesmo UPDATE, sem estado intermediario
- `09b4d0a` docs: nome e chave finais no mesmo UPDATE da fusao, na ADR-0005, no CLAUDE.md e nas docstrings
- `42369c1` Merge branch 'main' into t/T-020-identidade-do-concurso-o-pci-id-que-disc
- `f9a9337` test: o nome novo so vence quando ninguem o ocupa, e nenhum caminho funde linha
- `d871bbe` fix: o nome so muda quando ninguem o ocupa, e a fusao de linhas sai do banco
- `34e75d3` docs: o nome conservador sem fusao na ADR-0005, no CLAUDE.md e na docstring do modulo
- `219215f` chore: atualiza a base
- `853fc30` test: o criterio de nulidade do pci_id provado no indice e no fallback de nome, pela escrita publica
- `45fc002` docs: o comentario do indice de unicidade conta o resolvedor que conserva as duas linhas
Testes: `PYTHONDONTWRITEBYTECODE=1 "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs -p no:cacheprovider` → base `ce24615` 591 passed / 0 failed / 0 skipped · ponta `45fc002` 634 passed / 0 failed / 0 skipped (na base da rodada 7 `219215f`: 633 coletados, 83 passed em `tests/test_database_manager.py` vs 84 na ponta). Lint: não configurado.
Testes que nascem verdes: os três da rodada 7 (`853fc30`) — `test_chave_com_espaco_no_fim_e_outro_edital_na_unicidade`, o caso `[nome]` ajustado em `test_pci_id_legado_nao_vazio_recusa_outro_pci_id_nos_tres_fallbacks` e a reescrita pública de `test_area_nome_is_unique` — por serem guardas sobre comportamento já entregue e congelado pela nota do arquiteto de 26/11 15:30; todos provados por mutação abaixo.
Desvios e riscos: nenhum desvio de escopo ou defeito de comportamento. A migração v7 recria a tabela `editais` sob a exceção documentada do dono (`kanban/REGRAS.md:24-26`, `SPEC-003` seção 4 item 1); o gate humano (`OK do Lucas:`) e o backup prévio do banco em produção seguem como passos obrigatórios antes do deploy.
Pendências: reparo das linhas já colididas (T-023), alerta do dia para `COLISAO DE IDENTIDADE` (T-026, R-97), concorrência/transação contra segundo escritor (T-027, R-98) e tabela de decisão da regra de nome e fusão (T-028, R-100).

## Spec

- **Escopo.** `git diff --stat ce24615..HEAD` toca apenas os quatro arquivos do `toca` (`CLAUDE.md`, `docs/adr/0005-identidade-do-concurso.md`, `src/database/manager.py`, `tests/test_database_manager.py`). No recorte da rodada 7 (`219215f..HEAD`), `src/database/manager.py` só teve linhas de comentário alteradas (linhas 281–288), confirmando a proibição de mexer em comportamento da nota de 26/11 15:30.
- **R-80, R-81 e R-82 (ordem de identidade e rechave).** `buscar_registro` (`src/database/manager.py:380-453`) prioriza `pci_id`, restringe os três fallbacks (`link`, `(area, nome) COLLATE NOCASE` e `_buscar_por_entidade`) a linhas sem `pci_id` quando o item traz chave, permite a rechave de linhas sem `pci_id` (`COALESCE(?, pci_id)` em `src/database/manager.py:568`) e mantém a ordem original para itens sem chave. Coberto em `tests/test_database_manager.py:706-750`, `:811-835` e `:855-900` (`SPEC-003` linhas 134–139; `docs/adr/0001-mcp-como-unica-porta-do-pci.md:3-7`).
- **Desempate explícito pelo menor `id`.** `_DESEMPATE = " ORDER BY id"` (`src/database/manager.py:108`) está presente nas quatro buscas de identidade (`:403`, `:413`, `:423`, `:444`) e na verificação de conflito de nome (`:648`). Coberto em `TestDesempateDasBuscas` (`tests/test_database_manager.py:1377-1449`), incluindo índice com ordem contrária `id DESC` (`:1429-1449`).
- **Critério único de nulidade do `pci_id`.** `_pci_id_ou_none` (`src/database/manager.py:111-118`), `_PCI_ID_SQL = "NULLIF(pci_id, '')"` (`:97`) e o índice `ON editais(area, nome, COALESCE(pci_id, ''))` (`:291`) concordam em tratar apenas `NULL` e `''` como ausência de chave, gravando `''` como `NULL` (`:543`). As três lacunas da rodada anterior estão fechadas:
  1. `test_chave_com_espaco_no_fim_e_outro_edital_na_unicidade` (`tests/test_database_manager.py:902-916`) prova pela escrita pública que `"296538"` e `"296538 "` geram dois IDs distintos e legíveis por suas chaves.
  2. `test_pci_id_legado_nao_vazio_recusa_outro_pci_id_nos_tres_fallbacks` (`tests/test_database_manager.py:869-900`) usa `"IFSP"` / `"ifsp"` (ASCII) no caso `[nome]`, isolando o fallback de `COLLATE NOCASE` do de entidade, e confirma integridade da linha legada `" "`.
  3. `test_area_nome_is_unique` (`tests/test_database_manager.py:100-160`) observa a rejeição do índice pela interface pública `atualizar_concurso` com gatilhos `BEFORE INSERT`, cobrindo `NULL` com `NULL`, `NULL` com `''`, mesma chave e coexistência de chaves distintas (`SPEC-003` linhas 140–148 e 213–226; `ADR-0005` linhas 37–43).
- **R-83, R-84, R-85 e idempotência da migração v7.** `_abrir_unicidade` (`src/database/manager.py:227-277`) recria a tabela apenas quando `PRAGMA index_list` acusa `origin = 'u'`, em transação única (`BEGIN`..`commit`), preservando todas as colunas, `id` e `sqlite_sequence`, sem apagar, fundir ou dividir linhas; na segunda abertura retorna sem gravar nada no arquivo. Coberto em `TestIdentidadePeloPciId` (`:751-788`) e `TestMigracaoDaUnicidade` (`:1290-1340`) (`SPEC-003` linhas 140–146 e 213–226).
- **R-86 e R-99 (log nomeado e nome conservador sem fusão).** `sqlite3.IntegrityError` em `atualizar_concurso` (`src/database/manager.py:604-614`) faz rollback, loga `ERROR COLISAO DE IDENTIDADE` e devolve `0`. `_resolver_nome_sem_colisao` (`:620-659`) aceita nome novo só quando livre na área (`COLLATE NOCASE`); qualquer conflito mantém o nome atual e loga `WARNING COLISAO DE NOME` (nível endossado pela decisão do arquiteto em `.esteira/revisor.md:524`). `_fundir` saiu do arquivo. Coberto em `test_colisao_irresolvivel_vira_erro_no_log_nao_silencio`, `test_colisao_na_escrita_deixa_as_duas_linhas_como_estavam` e `TestNomeConservador` (`:1066-1216`), incluindo `test_nome_nao_vira_de_outro_orgao_o_caso_do_parecer_5` (`:1189-1215`) (`SPEC-003` linhas 147–148, 163–170 e 241–253).
- **ADR-0005, CLAUDE.md e comentários.** `docs/adr/0005-identidade-do-concurso.md` documenta as duas opções da `SPEC-003` §4.1, a escolha do dono, a regra de prioridade `seguindo > ignorado > ativo` (linhas 79–84) e remete ao requisito `R-100` (sem citar IDs do quadro, cumprindo `kanban/REGRAS.md:30-31` e a decisão em `.esteira/revisor.md:526`). `CLAUDE.md` (linhas 152–182) reflete o schema v7, `idx_editais_identidade`, nulidade única, desempate e R-99. O comentário em `src/database/manager.py:281-288` foi corrigido (item 4 da rodada 7) e não fala mais em «matar» duplicata.

## Prova

### Contagens medidas vs alegadas

Condição de medida: Windows, Python `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe"`, `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, sem seleção por marcadores.

| Ponto | Implementador | Medido pelo revisor | Comando |
| --- | --- | --- | --- |
| Merge-base com `main` (`ce24615`) | *(base da rodada 7 era `219215f`)* | `591 tests collected in 2.83s` · `591 passed in 84.73s (0:01:24)` (0 failed, 0 skipped) | `-m pytest --collect-only -q -p no:cacheprovider` e `-m pytest -q -rs -p no:cacheprovider` em worktree destacado |
| Base da rodada 7 (`219215f`) | `633 passed in 231.28s` | `633 tests collected in 2.94s` · `tests/test_database_manager.py`: `83 passed in 2.28s` | `-m pytest --collect-only -q -p no:cacheprovider` e `-m pytest -q -rs -p no:cacheprovider tests/test_database_manager.py` em worktree destacado |
| Ponta (`45fc002`) | `634 tests collected` · `634 passed in 127.45s` | `634 tests collected in 4.77s` · `634 passed in 102.48s (0:01:42)` (0 failed, 0 skipped) | `-m pytest --collect-only -q -p no:cacheprovider` e `-m pytest -q -rs -p no:cacheprovider` |

A conta fecha nas duas referências:
- Contra `main` (`ce24615`): `591 + 43 = 634` (31 novas funções de teste e 12 casos adicionais de parametrização em `tests/test_database_manager.py`; apenas `test_area_nome_is_unique` foi alterado entre os testes preexistentes, dentro da exceção nomeada do aceite).
- Na rodada 7 (`219215f..45fc002`): `633 + 1 = 634` (`test_chave_com_espaco_no_fim_e_outro_edital_na_unicidade` adicionada; `test_area_nome_is_unique` e `test_pci_id_legado_nao_vazio_recusa_outro_pci_id_nos_tres_fallbacks` endurecidos sem perda de casos).

### Prova do vermelho em cada commit `test:` (nível G−)

Cada commit `test:` foi verificado em worktree destacado com `-m pytest -q --tb=line -p no:cacheprovider tests/test_database_manager.py -k <seletor>` (zero erros de coleta, importação ou sintaxe):

| Commit | Seletor `-k` | Saída medida |
| --- | --- | --- |
| `3deba35` | `TestIdentidadePeloPciId or TestMigracaoDaUnicidade or test_area_nome_is_unique` | `9 failed, 5 passed, 40 deselected in 0.35s` |
| `fa09826` | `test_item_sem_pci_id_funde_todas_as_grafias or test_fusao_pelo_nome or test_pci_id_rechaveia or test_colisao_irresolvivel or test_nome_repetido_sem_pci_id` | `2 failed, 4 passed, 52 deselected in 0.30s` |
| `cfdf2b5` | `pci_id_vazio or herda_o_pci_id_na_fusao` | `3 failed, 1 passed, 58 deselected in 0.32s` |
| `0dda815` | `test_pci_id_legado_nao_vazio_recusa_outro_pci_id_nos_tres_fallbacks or test_atualizacao_sem_pci_id_preserva_as_duas_linhas_e_as_duas_chaves` | `3 failed, 1 passed, 62 deselected in 0.28s` *(nota: no parecer 5 o seletor não casava esses dois nomes, por isso reportou 4 passed; rodando os testes do próprio commit, 3 nasceram vermelhos e só `[link]` era guarda)* |
| `4ceb387` | `empatada or linha_mais_antiga` | `6 failed, 1 passed, 66 deselected in 0.34s` |
| `95de698` | `fusao_grava or colisao_depois or empatada_nao_depende_do_indice` | `1 failed, 2 passed, 73 deselected in 0.30s` |
| `f9a9337` | `TestNomeConservador or test_renomear_para_o_nome_do_outro_edital` | `8 failed, 4 passed, 75 deselected in 0.43s` |
| `853fc30` | `test_chave_com_espaco_no_fim_e_outro_edital_na_unicidade or test_pci_id_legado_nao_vazio_recusa_outro_pci_id_nos_tres_fallbacks or test_area_nome_is_unique` | `5 passed, 79 deselected in 0.27s` *(guardas da rodada 7, provadas por mutação abaixo)* |

### Prova por mutação (worktree destacado em `45fc002`, `git diff` conferido em cada ensaio)

Comando em cada mutação: `PYTHONDONTWRITEBYTECODE=1 <python do venv> -m pytest -q --tb=line -p no:cacheprovider tests/test_database_manager.py -k <seletor>`, seguido de `git checkout -- src/database/manager.py`:

| Mutação aplicada em `src/database/manager.py` | Resultado medido |
| --- | --- |
| 1. `COALESCE(TRIM(pci_id), '')` em `idx_editais_identidade` | `1 failed, 83 deselected` (`test_chave_com_espaco_no_fim_e_outro_edital_na_unicidade`) |
| 2. `NULLIF(TRIM(pci_id), '')` só no fallback de nome (`:423`) | `1 failed, 2 passed, 81 deselected` (`test_pci_id_legado_nao_vazio_recusa_outro_pci_id_nos_tres_fallbacks[nome]`) |
| 3a. Sem `COALESCE` em `idx_editais_identidade` (`ON editais(area, nome, pci_id)`) | `1 failed, 83 deselected` (`test_area_nome_is_unique`) |
| 3b. `COALESCE(pci_id, '-')` em `idx_editais_identidade` (quebra equivalência `NULL`/`''`) | `1 failed, 83 deselected` (`test_area_nome_is_unique`) |
| 4. `_DESEMPATE = ""` | `7 failed, 1 passed, 76 deselected` (`TestDesempateDasBuscas`) |
| 5. `_pci_id_ou_none` usando `.strip() == ""` | `3 failed, 1 passed, 80 deselected` (`[nome]`, `[entidade]` e `preserva_as_duas_linhas`) |
| 6. `so_sem_pci_id = ""` | `7 failed, 13 passed, 64 deselected` (`TestIdentidadePeloPciId`) |
| 7. `_buscar_por_entidade` ignorando `pci_id` | `9 failed, 11 passed, 64 deselected` (`TestIdentidadePeloPciId`) |
| 8. `_resolver_nome_sem_colisao` ignorando `conflito` | `6 failed, 5 passed, 73 deselected` (`TestNomeConservador`) |
| 9. `_abrir_unicidade` sem restaurar `sqlite_sequence` | `1 failed, 3 passed, 80 deselected` (`test_migracao_abre_a_unicidade_para_o_segundo_edital`) |

### Conferência de escritor único (`COALESCE(?, pci_id)` no `UPDATE`)

Verifiquei em bancos SQLite temporários em arquivo os quatro cenários de escritor único sobre `45fc002`:
1. `(1, 'IFSP - SP', NULL)`, `(2, 'IFSP - SP', '296538')`, `(3, 'IFSP', '296538')` com atualização sem chave (`nome='IFSP'`, link do `id=1`) → retornou `1`, manteve `'IFSP - SP'` e `pci_id=None`, contagem `3` intacta.
2. Mesmo estado com `pci_id='296538'` e link do `id=1` → retornou `2`, atualizou apenas `id=2` mantendo `'IFSP - SP'`.
3. Rechave com `pci_id='296538'` inédito e nome ocupado por `id=2` (`'296044'`) → retornou `1`, gravou `pci_id='296538'` mantendo `'IFSP - SP'`, `id=2` intacto.
4. Linha legada com `pci_id=''` e `estado_usuario='seguindo'` rechaveada com nome livre e `pci_id='296538'` → retornou `1`, gravou nome e chave novos preservando `estado_usuario='seguindo'`.

Nenhum teste novo apresenta acoplamento à implementação, tautologia ou dublê fora da fronteira; todos afirmam comportamento pela costura pública (`DatabaseManager.buscar_registro`, `atualizar_concurso`, `contar_por_fonte`) sobre bancos temporários em arquivo.

## Padrões

- **Regras do projeto.** `git diff --check ce24615..HEAD` saiu vazio. Nenhuma ocorrência de `T-NNN` foi introduzida no diff (`git diff ce24615..HEAD` verificado por regex `^\+.*T-\d{3}`). Nenhuma dependência nova, nenhum segredo, nenhuma chamada de rede em testes, nenhum arquivo fora do `toca` modificado. Identificadores e comentários novos em português do Brasil sem acento; exceção de migração da tabela `editais` dentro dos limites de `kanban/REGRAS.md:22-26`.
- **Ressalva de código (possível código duplicado e cobertura de `COLLATE NOCASE` em teste de guarda):**
  - Em `tests/test_database_manager.py:1025` e `:1358`, a constante `URL_INDICE_GRAN` está definida duas vezes com o mesmo valor no nível de módulo → manter uma única definição.
  - Em `tests/test_database_manager.py:746` (`test_item_sem_pci_id_mantem_a_ordem_de_hoje`), `por_nome = db.buscar_registro(IFSP_NOME.upper())` passa texto acentuado (`Educação`, `Ciência`, `São`), que o `COLLATE NOCASE` do SQLite não dobra; assim esse passo cai no fallback de entidade em vez de exercitar a busca por nome (não compromete a prova do R-82 porque a busca por nome `COLLATE NOCASE` sem chave está coberta em ASCII por `test_busca_por_nome_ignora_capitalizacao` e `TestDesempateDasBuscas`).
  - Sugestão de ticket novo (opcional, a critério do arquiteto): **«Limpar constante duplicada e caso ASCII no teste de ordem sem pci_id»**, nível `P`, `toca: [tests/test_database_manager.py]`.

Revisão feita estritamente em leitura; todos os worktrees temporários foram removidos e o worktree do ticket permanece limpo, exceto por este relatório em `.esteira/relatorio-revisor.md`.
