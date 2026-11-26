REPROVADO
Esteira: revisor · codex (gpt-6.2-sol) · nível G- · esforço high · 2026-11-26 13:29 → 2026-11-26 13:40 (11 min)
Resumo: Revisei o T-020 até `e9f57ca`. A suíte passou com 614 testes e os cinco commits `test:` ficaram vermelhos em reprodução independente.
Duas escritas concorrentes ainda podem sobrescrever silenciosamente a chave de outro edital. Há também uma colisão de unicidade evitável na fusão e duas lacunas de teste confirmadas por mutação.

Arquivos: `src/database/manager.py`, `tests/test_database_manager.py`, `docs/adr/0005-identidade-do-concurso.md` e `CLAUDE.md`. Todos estão no `toca`. O diff da base comum à ponta tem 956 inserções e 47 remoções.

Commits:

1. `3deba35` test: identidade pelo pci_id e unicidade que admite dois editais do mesmo orgao
2. `47291be` fix: o pci_id que discorda vence o nome, e a unicidade admite dois editais do mesmo orgao
3. `17537ba` docs: ADR-0005, identidade do concurso e unicidade com o pci_id
4. `fa09826` test: a fusao pelo nome leva todas as grafias do orgao e nunca dois editais
5. `31e9b24` fix: a fusao pelo nome leva todas as grafias do orgao e nunca dois editais
6. `cfdf2b5` test: pci_id vazio conta como nulo na escrita, na busca e na fusao
7. `a4f2d58` fix: pci_id vazio entra como nulo e a fusao nao o trata como chave
8. `58033e2` docs: schema v7 e a fusao de todas as grafias no CLAUDE.md, na ADR-0005 e nas docstrings
9. `ff8e48d` Merge branch 'main' into t/T-020-identidade-do-concurso-o-pci-id-que-disc
10. `0dda815` test: um criterio so de nulidade do pci_id na busca e na fusao
11. `59d67a6` fix: o pci_id tem um criterio so de nulidade, na busca, na fusao e no indice
12. `1482816` docs: o criterio unico de nulidade do pci_id na ADR-0005 e no CLAUDE.md
13. `4ceb387` test: busca empatada escolhe a linha mais antiga, nos tres fallbacks e no pci_id
14. `63e99a4` fix: busca de identidade empatada escolhe a linha de menor id, nunca a do indice
15. `e9f57ca` docs: o desempate pela linha de menor id na ADR-0005, no CLAUDE.md e na docstring da busca

Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs -p no:cacheprovider` → base comum `86be955` 582 passed / 0 failed / 0 skipped · base da quarta rodada `1482816` 607 passed / 0 failed / 0 skipped · ponta `e9f57ca` 614 passed / 0 failed / 0 skipped. Usei `PYTHONDONTWRITEBYTECODE=1`, sem marcadores e sem configurar variáveis do projeto. As bases rodaram em worktrees destacados.

Testes que nascem verdes:

- `3deba35`: rechave por nome, ordem de busca sem chave, preservação das linhas, segunda abertura idempotente e barreira contra nome duplicado sem chave. Guardam comportamentos presentes no v6. A abertura da unicidade e a preservação da sequência exercitam a migração no vermelho.
- `fa09826`: rechaves por link e por entidade, atualização sem chave pelo mesmo nome e a nova montagem do erro de unicidade com gatilho. Os três primeiros guardam comportamentos existentes. O último guarda o log da implementação anterior.
- `cfdf2b5`: rechave de linha legada com chave vazia. A busca já tratava esse valor como ausente.
- `0dda815`: recusa de chave divergente no fallback por link com valor legado de um espaço. O SQL do link já distinguia espaço de vazio.
- `4ceb387`: empate por `pci_id`. O índice padrão já devolvia o menor ID. A mutação em **Prova** mostra o limite dessa guarda.

## Spec

### Exigências

1. **R-80/R-81/R-83 — tornar a rechave segura entre escritores.** Em `src/database/manager.py:546` a busca lê uma linha sem chave antes da primeira escrita. Entre a busca e o `UPDATE`, outra conexão pode atribuir uma chave canônica à linha. O `UPDATE` usa o ID escolhido e sobrescreve a chave sem revalidá-la (`src/database/manager.py:561`, `:569`, `:580`). Em um SQLite em arquivo, iniciei B e o pausei no `BEGIN` implícito, depois da busca da linha legada `id=1`. A gravou o edital `296044`, que confirmei pela busca pública. Liberei B com o edital `296538`. As duas chamadas retornaram `1`. A busca final por `296044` retornou `None`, e `296538` ficou no ID `1` com o prazo de B. A SPEC-003 exige manter a chave discordante fora do casamento e preservar a coexistência (`docs/specs/SPEC-003-identidade-do-concurso-e-cota-da-llm.md:134`, `:136`, `:140`). Faça a decisão de identidade e a escrita na mesma transação protegida contra outro escritor, ou revalide a linha na escrita e refaça a resolução em caso de mudança. Acrescente um teste com duas conexões e sincronização determinística que confira os dois IDs distintos, o prazo de cada edital e a preservação do ID legado para A.
2. **R-82 e ADR-0005 — evitar colisão no estado intermediário da fusão.** Em `src/database/manager.py:675` e `:705`, a linha casada herda o `pci_id` enquanto ainda tem o nome antigo. Com as linhas `(1, "IFSP - SP", NULL)`, `(2, "IFSP - SP", "296538")` e `(3, "IFSP", "296538")`, todas válidas no v7, a atualização sem chave encontra o ID `1` pelo link específico e tenta assumir `IFSP`. Ao herdar a chave do ID `3`, o ID `1` colide com o ID `2` pelo nome antigo. Reproduzi retorno `0`, log de colisão e status antigo nas duas linhas consultadas, sem outro escritor. A combinação final `("IFSP", "296538")` fica disponível assim que a linha que disputa o nome é incorporada. A ADR-0005 manda fundir as linhas elegíveis que disputam o nome novo e preservar o ID casado (`docs/adr/0005-identidade-do-concurso.md:44`, `:50`). Organize a fusão e a gravação de nome e chave finais na mesma transação, sem aplicar a chave com o nome antigo. Teste o cenário pelo link e confira o retorno `1`, o status novo, a chave e o estado `seguindo` herdado da linha `3`, além da linha `2` intacta.

### Conferência do aceite

| Item | Código e prova |
| --- | --- |
| R-80 | Os três fallbacks filtram a chave discordante em `src/database/manager.py:409` e `:446`. Os testes em `tests/test_database_manager.py:671`, `:676` e `:684` cobrem o contrato sequencial. A exigência 1 cobre a concorrência. |
| R-81 | O `UPDATE` grava a chave na linha legada em `src/database/manager.py:569`. Há provas públicas por nome, link e entidade em `tests/test_database_manager.py:690`, `:828` e `:841`. A exigência 1 cobre a rechave concorrente. |
| R-82 | A ordem de identidade foi mantida em `src/database/manager.py:401`–`:449`, com os quatro desempates por menor ID autorizados na decisão de 26/11 às 13:21. Os testes em `tests/test_database_manager.py:704`, `:1159`, `:1171` e `:1185` exercitam os caminhos. A exigência 2 cobre uma colisão ao atualizar após a busca. |
| R-83 | A unicidade por expressão em `src/database/manager.py:290` e a inserção em `:589` deixam coexistir dois editais do mesmo órgão. `tests/test_database_manager.py:716` e `:733` conferem IDs, fases e prazos em atualizações sequenciais. |
| R-84/R-85 | A cópia por coluna e a preservação de `sqlite_sequence` em `src/database/manager.py:248`–`:273` mantêm as linhas inteiras. `tests/test_database_manager.py:1065` compara todos os campos e a contagem, e `:1077` prova que o ID removido no v6 fica reservado. |
| R-86 | O erro nomeado é emitido em `src/database/manager.py:605`, e `tests/test_database_manager.py:958` confere o log junto do retorno `0`. A versão da SPEC-003 em HEAD coincide com a de `main` e atribui o alerta ao R-97 (`docs/specs/SPEC-003-identidade-do-concurso-e-cota-da-llm.md:147`–`:152`, `:205`). |
| Idempotência | A abertura seguinte sai sem recriar em `src/database/manager.py:274`–`:281`. `tests/test_database_manager.py:1093` compara o arquivo byte a byte. |
| ADR-0005 | `docs/adr/0005-identidade-do-concurso.md:65`–`:80` registra as duas opções e a decisão do dono por recriação com índice único por expressão, conforme a seção 4, item 1, da SPEC-003. |
| Suíte e testes preexistentes | Suíte verde. Em relação à base comum, o único teste preexistente alterado preserva o nome e troca a inspeção textual do DDL por inserções que verificam rejeição de duplicatas e aceitação de chaves diferentes (`tests/test_database_manager.py:99`). |

## Prova

A base comum veio de `git merge-base main HEAD`. O implementador da quarta rodada mediu `607 passed in 73.40s` em `1482816` e `614 passed in 74.63s` em `e9f57ca`. Minha execução retornou `582 passed in 136.18s (0:02:16)` na base comum, `607 passed in 137.31s (0:02:17)` na base da rodada e `614 passed in 123.56s (0:02:03)` na ponta. Todas com zero falhas e zero pulos. A coleta na ponta retornou `614 tests collected in 5.08s` com `-m pytest --collect-only -q -p no:cacheprovider`, ante 614 informados pelo implementador. O módulo tinha `41 tests collected in 0.14s` na base comum e 73 casos na ponta. Os 32 casos líquidos são do módulo, 7 da última rodada. As contas fecham em 582 + 32 = 614 e 607 + 7 = 614.

O comando dos vermelhos foi `"<python acima>" -m pytest -q -rs -p no:cacheprovider --tb=line tests/test_database_manager.py`, com cada `test:` em seu próprio worktree destacado.

| Commit | Saída | Motivo observado |
| --- | --- | --- |
| `3deba35` | `9 failed, 45 passed in 2.32s` | A unicidade antiga impede a coexistência e a busca ainda casa a chave discordante. Falham também as asserções sobre prazos preservados, abertura da unicidade na migração e retorno da gravação no cenário do log. |
| `fa09826` | `2 failed, 56 passed in 3.43s` | A fusão anterior deixa uma grafia ocupando o nome ou deixa a chave na outra linha. |
| `cfdf2b5` | `3 failed, 59 passed in 3.45s` | Vazio é persistido como texto ou toma o lugar da chave canônica. |
| `0dda815` | `3 failed, 63 passed in 3.76s` | O espaço é tratado como ausente nos caminhos de nome, por entidade e de fusão. |
| `4ceb387` | `6 failed, 67 passed in 4.09s` | O ID observado foi 2 nos três fallbacks de leitura e nas três atualizações. A contagem coincide com a do implementador. |

Os vermelhos vieram de comportamento, sem falha de coleta ou importação. O histórico mostra cinco pares `test:` → `fix:` em ordem, com `docs:` ao fim de cada rodada de entrega. As novas asserções de identidade e migração usam a API pública e literais independentes. A montagem de bancos legados e do erro de unicidade usa a fronteira SQLite.

### Exigências de teste

1. **O teste do empate por `pci_id` deve falhar se o desempate explícito for removido.** Em worktree destacado, conferi no `git diff` duas mutações de `src/database/manager.py:403`. Com `ORDER BY id DESC`, o teste de `tests/test_database_manager.py:1185` falhou com ID 2 em vez de 1 (`1 failed, 72 deselected in 0.21s`). Ao eliminar só o `ORDER BY`, o mesmo teste passou (`1 passed, 72 deselected in 0.17s`). Em banco descartável com índice de mesma chave e ordenação física `(area, pci_id, id DESC)`, confirmei via `EXPLAIN QUERY PLAN` que o SQLite usou esse índice. A ponta devolveu ID 1, e a mutação sem `ORDER BY` devolveu ID 2. Monte esse ou outro plano com ordem física contrária no teste e mantenha a asserção pela busca pública. Isso protege a independência do plano exigida em `docs/adr/0005-identidade-do-concurso.md:52`–`:56`.
2. **Recuperar a prova de rollback quando a colisão ocorre depois de uma fusão.** O teste inicial do log também conferia que a fusão parcial era desfeita. A troca do cenário em `fa09826` deixou em `tests/test_database_manager.py:958` somente o log e o retorno, num caso de inserção. Removi apenas o `rollback()` de `src/database/manager.py:609`, conferi a mutação com `git diff` e rodei o módulo com `-m pytest -q -rs -p no:cacheprovider tests/test_database_manager.py`. Resultado `73 passed in 1.64s`. Num ensaio com duas grafias fundíveis e um gatilho SQLite que aborta só o `UPDATE` final, a ponta retornou `0` com duas linhas preservadas. A mutação também retornou `0`, mas deixou uma linha visível na mesma conexão. Acrescente esse caso e confira pela API o erro nomeado, a contagem e os registros inalterados após a falha.

## Padrões

- O diff respeita o `toca` e a exceção de migração documentada em `kanban/REGRAS.md:22`–`:26`. Nenhuma dependência foi acrescentada. Os ensaios adicionais usaram SQLite local em arquivo.
- Possível nome misterioso em `src/database/manager.py:298`. `_create_v3_table` passou a criar diretamente o schema v7. Um nome em português que descreva a criação do schema atual distinguiria essa função de `_migrate_to_v3`, que lida com uma migração histórica. Ressalva de manutenção.
- Lint sem comando configurado. `git diff --check 86be955..HEAD` e `git diff --check 1482816..HEAD` saíram limpos.

Desvios e riscos: as duas falhas de comportamento foram reproduzidas em bancos temporários. A medição de produção usada na decisão de desempate veio da nota do arquiteto. As contagens de duplicatas por nome, link e chave citadas nela não medem empates pela heurística de entidade.

Pendências: R-97 no T-026 e reparo das linhas já colididas no T-023. O gate de integração continua dependente do OK do Lucas, e a primeira execução em produção exige backup do banco. Removi os worktrees temporários e mantive `HEAD` e `git status` da branch do ticket como encontrados, com este relatório na pasta ignorada `.esteira/`.
