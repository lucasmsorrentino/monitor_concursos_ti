REPROVADO
Esteira: revisor · codex (gpt-6.2-sol) · nível G- · esforço high · 2026-11-26 15:18 → 2026-11-26 15:29 (11 min)
Resumo: Revisei a sexta rodada do T-020, com o R-99 no lugar da fusão. A escrita com um único escritor passou no cenário que antes perdia a atualização. A suíte completa passou, mas duas mutações do critério de nulidade passaram pelos 83 testes do banco e produziram resultados incorretos em chamadas públicas.
Arquivos: `CLAUDE.md`, `docs/adr/0005-identidade-do-concurso.md`, `src/database/manager.py` e `tests/test_database_manager.py`. Todos dentro do `toca` no diff `ce24615..219215f`.
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

Testes: `& 'C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe' -m pytest -q -rs -p no:cacheprovider` → base `ce24615` 591 passed / 0 failed / 0 skipped · ponta `219215f` 633 passed / 0 failed / 0 skipped. Lint sem configuração.
Testes que nascem verdes: na rodada 6, nome livre, conflito com outro órgão sem chave e preservação de linhas nos cenários de rechave com nome ocupado e de nome de outro órgão. A prova abaixo lista as guardas históricas.
Desvios e riscos: lacunas na prova do critério único de nulidade e uma verificação fora da interface pública. O commit histórico `0dda815` nasceu verde nos quatro casos. Ver exigências em Prova.
Pendências: reparo das linhas colididas (T-023), alerta do dia (T-026, R-97), concorrência (T-027, R-98) e tabela de decisão da fusão (T-028, R-100). A autorização do Lucas e o backup antes da primeira migração em produção continuam como passos da integração.

## Spec

- **Escopo.** A branch está em `219215f`, merge da ponta entregue `34e75d3` com a `main` em `ce24615`. O diff do merge contra o segundo pai contém só os quatro arquivos do ticket, com o mesmo conteúdo entregue nesses quatro. As mudanças na SPEC e em `kanban/` vieram da base. O ticket declara zero dependências. Usei a SPEC-003 da base atual.
- **R-80, R-81 e R-82.** A busca dá precedência ao `pci_id`, restringe os três fallbacks a linhas sem chave quando o item tem chave e conserva a sequência link específico, nome e entidade para o item sem chave. A rechave grava a chave no mesmo ID, conforme a decisão sobre identificadores da ADR-0001, linhas 3–6. Código em `src/database/manager.py:397–447` e `:537–575`. Evidência em `tests/test_database_manager.py:672–715` e `:777–833`, incluindo rechave por nome, link e entidade. SPEC-003, linhas 134–139.
- **Desempate e nulidade.** As quatro buscas usam `ORDER BY id`. Os testes de empate exercitam leitura, escrita e um índice concorrente com ordem decrescente. `_pci_id_ou_none`, `NULLIF` e `COALESCE` aplicam o critério de aceitar como ausente apenas `NULL` ou `''`. O comportamento observado na ponta atende à regra. A cobertura de dois pontos está em Prova. Código em `src/database/manager.py:89–116`, `:280–289` e `:397–447`, testes em `tests/test_database_manager.py:802–858` e `:1319–1391`. ADR-0005, linhas 37–45, e aceite em `.esteira/revisor.md:290–293`.
- **R-83.** Os dois editais do IFSP ficam com IDs distintos e preservam seus prazos e fase em gravações sucessivas. A unicidade por expressão em `src/database/manager.py:285–288` sustenta o caso. Testes em `tests/test_database_manager.py:717–754`. SPEC-003, linhas 140–141 e 213–222.
- **R-84, R-85 e idempotência.** A migração cria a tabela, copia as colunas com os IDs, restaura a sequência, instala os índices e confirma a transação em `src/database/manager.py:227–277`. As duas linhas do v6 são lidas integralmente após a migração, com as marcas do usuário e as contagens preservadas. O próximo ID continua acima do ID já usado e removido, e a segunda abertura mantém os bytes do arquivo. Testes em `tests/test_database_manager.py:1235–1273`. SPEC-003, linhas 142–146 e 219–222.
- **R-86 e R-99.** A exceção de integridade provoca rollback e `ERROR COLISAO DE IDENTIDADE`. Na troca de nome, um nome livre é aceito e qualquer conflito de nome preserva o atual, com `WARNING COLISAO DE NOME` conforme a decisão do arquiteto. `atualizar_concurso` grava somente a linha casada ou insere uma linha, e `_fundir` saiu. Código em `src/database/manager.py:537–654`, testes em `tests/test_database_manager.py:887–955` e `:1011–1157`. O teste obrigatório de regressão usa as duas chaves do parecer, os mesmos vínculos entre os links e o item sem chave. O IFSP conserva o ID 1 e o nome `IFSP - SP`, e a busca por TJPR devolve o ID 2. O teste ficou vermelho em `f9a9337`, com `'TJPR' == 'IFSP - SP'`, e verde na ponta. SPEC-003, linhas 147–148 e 163–170, e decisão em `.esteira/revisor.md:523`.
- **ADR-0005.** Registra as duas opções, a escolha do dono, a prioridade `seguindo > ignorado > ativo` e o requisito R-100 para a futura tabela de decisão, nas linhas 70–101. A menção literal ao T-028 pedida em `.esteira/revisor.md:308–309` cede à regra sobre IDs de quadro em `kanban/REGRAS.md:30–31`. A remissão ao R-100 identifica o requisito, conforme a decisão em `.esteira/revisor.md:525`. SPEC-003, linhas 171–177 e 213–222.

## Prova

| Revisão | Implementador | Saída medida |
| --- | --- | --- |
| Merge-base com a integração, `ce24615` | Base do implementador era `42369c1` | `591 passed in 293.10s (0:04:53)` |
| Base da rodada 6, `42369c1` | `626 passed in 159.71s` | `626 passed in 210.44s (0:03:30)` |
| Ponta, `219215f` | `633 passed in 146.18s` em `34e75d3` | `633 passed in 293.88s (0:04:53)` |

Windows, Python do venv informado, `PYTHONDONTWRITEBYTECODE=1`, cache do pytest desabilitado e sem seleção por marcadores. A coleta com `-m pytest --collect-only -q -p no:cacheprovider` devolveu `633 tests collected in 3.79s` na ponta. A conta é `591 + 42 = 633`, com 30 funções de teste acrescentadas e 12 casos adicionais de parametrização. A conta da rodada também fecha, `626 + 11 − 4 = 633`. O teste existente `test_area_nome_is_unique` foi alterado dentro da exceção de escopo para a troca de unicidade. O diff contra a integração preserva as demais funções de teste preexistentes.

Conferi as quatro exclusões da rodada 6 contra `42369c1` e contra `main`. As quatro afirmavam fusão e nasceram no ticket:

- `test_item_sem_pci_id_funde_todas_as_grafias_do_nome_novo`
- `test_fusao_pelo_nome_nao_junta_dois_editais_de_pci_id_distintos`
- `test_fusao_grava_nome_e_chave_finais_juntos_sem_colidir_no_meio`
- `test_linha_legada_com_pci_id_vazio_herda_o_pci_id_na_fusao`

`test_colisao_depois_de_uma_fusao_desfaz_a_fusao` passou a `test_colisao_na_escrita_deixa_as_duas_linhas_como_estavam` com o corpo preservado. A expectativa final de `test_renomear_para_o_nome_do_outro_edital_nao_funde_as_linhas` passou a exigir o nome anterior, conforme R-99. Ambos nasceram na branch.

### Vermelhos e guardas

Rodei cada commit `test:` em worktree destacado, com o mesmo Python e `-m pytest -q --tb=line -p no:cacheprovider tests/test_database_manager.py -k '<seletor>'`. As falhas vieram de asserções de comportamento ou, na antiga restrição, do SQLite recusando os dois editais com o mesmo nome. Zero falhas de coleta, importação ou sintaxe nesses ensaios.

| Commit | Seletor `-k` | Resumo do pytest e motivo |
| --- | --- | --- |
| `3deba35` | `TestIdentidadePeloPciId or TestMigracaoDaUnicidade or test_area_nome_is_unique` | `9 failed, 5 passed, 40 deselected`. Fallback aceita chave discordante, editais ocupam o mesmo ID e a unicidade antiga permanece. |
| `fa09826` | `test_item_sem_pci_id_funde_todas_as_grafias or test_fusao_pelo_nome or test_pci_id_rechaveia or test_colisao_irresolvivel or test_nome_repetido_sem_pci_id` | `2 failed, 4 passed, 52 deselected`. A fusão histórica deixava uma grafia em conflito ou alterava a linha errada. |
| `cfdf2b5` | `pci_id_vazio or herda_o_pci_id_na_fusao` | `3 failed, 1 passed, 58 deselected`. A escrita antiga gravava vazio, apagava a chave ou falhava em herdá-la na fusão. |
| `0dda815` | `criterio or espaco or pci_id_vazio` | `4 passed, 62 deselected`. Ressalva de processo, com contraprova por mutação abaixo. |
| `4ceb387` | `empatada or linha_mais_antiga` | `6 failed, 1 passed, 66 deselected`. Os três fallbacks liam e escreviam no ID 2 onde o teste exigia o ID 1. |
| `95de698` | `fusao_grava or colisao_depois or empatada_nao_depende_do_indice` | `1 failed, 2 passed, 73 deselected`. A escrita antiga no caso de fusão intermediária devolvia 0. |
| `f9a9337` | `TestNomeConservador or test_renomear_para_o_nome_do_outro_edital` | `8 failed, 4 passed, 75 deselected`. O nome era trocado ou linhas desapareciam. Confere com a alegação do implementador. |

Guardas históricas observadas: `3deba35` já passava em rechave por nome, fallback sem chave, preservação das linhas, segunda abertura e bloqueio de duplicata sem chave pelo SQLite. Em `fa09826`, já passavam a rechave por link e entidade, o cenário do log de colisão e a repetição normal sem chave. `cfdf2b5` já rechaveava a linha legada com vazio. Os quatro casos de `0dda815` já eram verdes. O desempate por chave de `4ceb387` já passava com o índice escolhido pelo SQLite. As guardas de `95de698` foram a reversão quando a escrita falha e o desempate com índice decrescente. Em `f9a9337`, já passavam `test_nome_novo_vence_quando_ninguem_ocupa`, o conflito `[outro_orgao]` sem chave e os casos `[rechave_com_nome_de_outro_edital]` e `[nome_de_outro_orgao]` do teste de preservação de linhas.

### Escrita com um único escritor

Rodei quatro cenários por `python -` com bancos SQLite temporários em arquivo. Plantei as linhas por SQL e observei retorno, contagem, nomes, chaves, status e marcas do usuário pelas interfaces públicas. Os quatro passaram:

1. Estado do defeito anterior: `(1, IFSP - SP, NULL)`, `(2, IFSP - SP, 296538)` e `(3, IFSP, 296538)`. O item sem chave de nome `IFSP` e link da linha 1 recebeu ID 1. Só o status da linha 1 mudou. A chave nula permanece.
2. Mesmo estado e mesmo item com chave `296538`. A busca por chave e o desempate escolheram o ID 2, mesmo com o link do ID 1. O ID 2 conservou seu nome e chave e recebeu a atualização. Os outros dois ficaram intactos.
3. Chave inédita `296538` com nome pretendido ocupado por `296044`. O ID 1 foi rechaveado com seu nome atual e o ID 2 conservou os dados.
4. Chave inédita com nome livre e linha legada com `''`. Nome e chave foram gravados no mesmo ID, com a estrela preservada.

Isso confere a alegação sobre o `COALESCE(?, pci_id)` em `src/database/manager.py:564`: uma chave existente é resolvida antes do fallback, uma chave nova ainda é livre naquela área e o item sem chave preserva a que estava gravada. A checagem de concorrência é o R-98.

### Exigências

1. **Provar o critério de nulidade no índice pela escrita pública.** Em `tests/test_database_manager.py:717` ou junto dos casos de nulidade, grave dois editais de mesmo nome com `pci_id="296538"` e `pci_id="296538 "`. Afirme dois IDs positivos distintos e a leitura de cada ID pela sua chave. No código entregue obtive `(1, 2)`. Em worktree destacado, mudei o índice de `COALESCE(pci_id, '')` para `COALESCE(TRIM(pci_id), '')` em `src/database/manager.py:287` e confirmei o diff. O comando `-m pytest -q -rs -p no:cacheprovider tests/test_database_manager.py` devolveu `83 passed in 15.88s`, mas a prova pública devolveu `(1, 0)` com `COLISAO DE IDENTIDADE`. Esse teste deve falhar com a mutação e passar com o índice entregue. SPEC-003, linhas 140–141 e 217–219, e ADR-0005, linhas 37–43.
2. **Isolar o fallback de nome no teste de chave com espaço.** Em `tests/test_database_manager.py:835–858`, use para o caso `[nome]` um nome ASCII que o `COLLATE NOCASE` alcance de fato. Um caso mínimo é gravar `IFSP` com chave `" "` e buscar `ifsp` com chave `"296538"`, sem link. Afirme `None` e a leitura da linha pela chave original. Hoje `IFSP_NOME.upper()` também muda letras acentuadas e a busca do teste chega à entidade. A mutação que aplica `TRIM` só ao filtro SQL da busca por nome em `src/database/manager.py:417–419` devolveu `83 passed in 3.51s` em `-m pytest -q -p no:cacheprovider tests/test_database_manager.py`. No caso ASCII, a ponta devolveu `None` e a mutação devolveu o ID 1 com chave `" "`. Como contraprova adicional, `TRIM` no filtro SQL compartilhado foi detectado por `[link]` (`1 failed, 2 passed`), e `strip()` só no Python foi detectado por `[nome]` e `[entidade]` (`2 failed, 1 passed`). SPEC-003, linhas 134–137, e ADR-0005, linhas 37–43.
3. **Mover a comprovação da restrição do teste adaptado para a costura.** Em `tests/test_database_manager.py:100–126`, as asserções sobre `IntegrityError` vêm de um `INSERT` feito pelo próprio teste via SQLite. A exceção do aceite autoriza mudar o teste existente de unicidade. A costura de `.esteira/revisor.md:315–319` e a decisão em `:404` pedem que a observação da rejeição venha de `atualizar_concurso`. Use o SQLite para preparar o cenário, como no gatilho de `tests/test_database_manager.py:887–916`. Exercite também a combinação `NULL` e `''`: um gatilho pode inserir a linha de chave vazia entre a busca e a tentativa pública de inserir uma linha de chave nula. Afirme retorno 0 e erro nomeado, e confirme o estado final pela interface pública. O caso do R-83 acima cobre a coexistência. SPEC-003, linhas 140–148 e 213–222.

## Padrões

- `git diff --check ce24615..HEAD` saiu vazio. O diff segue o escopo, usa SQLite e pytest existentes, e mantém o código novo em português. A recriação v7 é a exceção transacional autorizada em `kanban/REGRAS.md:22–27` e na SPEC-003, linhas 213–222. A suíte usou as fixtures do projeto e os ensaios do banco usaram SQLite local.
- **Ressalva de documentação.** O comentário de `src/database/manager.py:281–284` ainda diz que o resolvedor existe para «matar» a duplicata. Hoje o resolvedor conserva as duas linhas quando há conflito, conforme R-99. Sugestão de ticket P, «Atualizar a explicação da unicidade conservadora», `toca: [src/database/manager.py]`.
- **Ressalva de processo.** O histórico preserva os pares `test:` → `fix:` e os fechamentos `docs:`. O grupo `0dda815` já passava antes de `59d67a6`. A contraprova em Prova define as exigências em commits novos. A ressalva histórica fica para a retro.

A branch foi revisada em leitura. As mutações e execuções históricas ocorreram em worktrees temporários, removidos ao final. O relatório é o único arquivo gravado no worktree do ticket.
