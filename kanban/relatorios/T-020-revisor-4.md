REPROVADO
Esteira: revisor · codex (gpt-6.2-sol) · nível G- · esforço high · 2026-11-26 13:56 → 2026-11-26 14:06 (11 min)
Resumo: A quinta rodada corrigiu a colisão intermediária da fusão e os dois testes de guarda detectaram as regressões que se propõem a impedir.
O aceite do R-82 permanece incompleto. Um experimento pela API pública mostrou que uma atualização sem chave pode gravar o nome de outro órgão na linha casada pelo link. A consulta seguinte por nome então retorna o edital errado.
Arquivos: src/database/manager.py (+249/-41), tests/test_database_manager.py (+702/-6), docs/adr/0005-identidade-do-concurso.md (+124/-0), CLAUDE.md (+7/-5). Todos no «toca». Diff de 86be955 a 09b4d0a.
Commits:
- 3deba35 test: identidade pelo pci_id e unicidade que admite dois editais do mesmo orgao
- 47291be fix: o pci_id que discorda vence o nome, e a unicidade admite dois editais do mesmo orgao
- 17537ba docs: ADR-0005, identidade do concurso e unicidade com o pci_id
- fa09826 test: a fusao pelo nome leva todas as grafias do orgao e nunca dois editais
- 31e9b24 fix: a fusao pelo nome leva todas as grafias do orgao e nunca dois editais
- cfdf2b5 test: pci_id vazio conta como nulo na escrita, na busca e na fusao
- a4f2d58 fix: pci_id vazio entra como nulo e a fusao nao o trata como chave
- 58033e2 docs: schema v7 e a fusao de todas as grafias no CLAUDE.md, na ADR-0005 e nas docstrings
- ff8e48d Merge branch 'main' into t/T-020-identidade-do-concurso-o-pci-id-que-disc
- 0dda815 test: um criterio so de nulidade do pci_id na busca e na fusao
- 59d67a6 fix: o pci_id tem um criterio so de nulidade, na busca, na fusao e no indice
- 1482816 docs: o criterio unico de nulidade do pci_id na ADR-0005 e no CLAUDE.md
- 4ceb387 test: busca empatada escolhe a linha mais antiga, nos tres fallbacks e no pci_id
- 63e99a4 fix: busca de identidade empatada escolhe a linha de menor id, nunca a do indice
- e9f57ca docs: o desempate pela linha de menor id na ADR-0005, no CLAUDE.md e na docstring da busca
- 95de698 test: a fusao grava nome e chave finais juntos, e a colisao depois dela desfaz tudo
- 21bda8d fix: a fusao grava nome e chave finais no mesmo UPDATE, sem estado intermediario
- 09b4d0a docs: nome e chave finais no mesmo UPDATE da fusao, na ADR-0005, no CLAUDE.md e nas docstrings

Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs -p no:cacheprovider` → base de integração 86be955: 582 passed / 0 failed / 0 skipped · base da rodada e9f57ca: 614 passed / 0 failed / 0 skipped · ponta 09b4d0a: 617 passed / 0 failed / 0 skipped.
Testes que nascem verdes: na quinta rodada, o desempate pelo `pci_id` com índice em ordem inversa e o rollback após fusão. Os dois protegem comportamento anterior e falharam nas respectivas mutações. Guardas das rodadas anteriores discriminadas em Prova.
Desvios e riscos: regressão do R-82 na resolução de conflitos de nome entre órgãos distintos, com efeito na próxima consulta sem chave. A exigência de correção e o caso de teste estão em Spec.
Pendências: reparo das linhas já colididas no T-023, alerta do dia no T-026 (R-97), concorrência no T-027 conforme a decisão registrada em .esteira/revisor.md:433. A integração ainda depende do OK do Lucas e a primeira execução em produção exige backup do banco.

## Spec

**Exigência — R-82.** A SPEC-003 §3.1 (`docs/specs/SPEC-003-identidade-do-concurso-e-cota-da-llm.md:138`) pede preservar o comportamento sem chave. A `docs/adr/0005-identidade-do-concurso.md:44` e a decisão em `.esteira/revisor.md:369` mandam manter o nome atual quando órgãos distintos disputam o nome. Em `src/database/manager.py:680`, a discordância entre chaves dispara um `continue` antes de verificar `mesmo_orgao` na linha 682. Quando esse é o único conflito, o retorno da linha 692 aceita o nome disputado.

Reproduzi por `atualizar_concurso` e `buscar_registro`, com o mesmo Python da suíte, um banco temporário em arquivo e uma conexão. Gravei IFSP - SP (id 1, chave 296538, link /a) e TJPR (id 2, chave 296044, link /b). Em seguida, atualizei com nome TJPR, status `A depois`, link específico /a e `pci_id` omitido. Todas as versões retornaram id 1 na escrita.

| Revisão | Nome do id 1 após a atualização | `buscar_registro("TJPR")` sem chave |
| --- | --- | --- |
| 86be955 e 3deba35 | IFSP - SP | id 2, status `B antes` |
| 47291be | TJPR | id 2, status `B antes` |
| 09b4d0a | TJPR | id 1, status `A depois` |

A regressão do nome aparece em 47291be. Na ponta, o desempate aprovado pelo menor id expõe o efeito da gravação indevida. O id 2 mantém sua chave e seu status, mas uma próxima consulta sem chave pelo nome de TJPR encontra a linha do IFSP.

Em `src/database/manager.py:677`, preserve o nome da linha casada quando um órgão distinto já disputa o novo nome, mesmo quando as duas chaves são preenchidas e discordam. Restrinja o tratamento de chaves discordantes que permite renomear ao caso de dois editais do mesmo órgão. Acrescente em `tests/test_database_manager.py` um teste pela costura pública com as duas linhas acima. Afirme retorno id 1, status novo e nome original no id 1 consultado pela chave, dados originais no id 2 e busca por TJPR sem chave retornando id 2. Valide o vermelho antes do conserto. Em worktree destacado, trocar a ordem dessas duas verificações fez o experimento passar e o módulo registrou `76 passed in 8.35s`. A entrega avaliada permanece em 09b4d0a.

**Demais itens do aceite e retorno da quinta rodada.**

| Item | Código e evidência |
| --- | --- |
| R-80 — chave discordante nos três fallbacks | `src/database/manager.py:402` e `:447`. Casos por nome, link e entidade em `tests/test_database_manager.py:671`, `:676` e `:684`. |
| R-81 — rechave sem perder o id | Filtros em `src/database/manager.py:410` e `:447`, gravação em `:573`. Testes por nome, link e entidade em `tests/test_database_manager.py:690`, `:865` e `:878`. As mutações de link e entidade fizeram cada teste correspondente falhar. |
| R-82 — ordem da busca, desempate e fusão | A busca mantém a sequência em `src/database/manager.py:399` e ordena candidatos pelo menor id. Os testes em `tests/test_database_manager.py:1235`, `:1247` e `:1277` conferem a escolha. No caso de três linhas da quinta rodada, `_fundir` altera os campos fora do índice em `src/database/manager.py:718` e a escrita final persiste nome e chave juntos em `:563`. O teste em `tests/test_database_manager.py:828` confirma id, nome, status, chave herdada, estado `seguindo` e a permanência da linha 2. A regressão de órgãos distintos está na exigência acima. |
| R-83 — coexistência | Índice em `src/database/manager.py:285` e gravação da segunda linha em `:593`. Os testes em `tests/test_database_manager.py:716` e `:733` conferem ids, prazos e fases, incluindo o prazo nas rodadas seguintes. |
| R-84, R-85 e idempotência | `src/database/manager.py:244` copia as colunas e conserva a sequência em uma transação. Os testes em `tests/test_database_manager.py:1141`, `:1153` e `:1169` comparam todas as colunas, a contagem por fonte, o próximo id e os bytes do arquivo na segunda abertura. |
| R-86 — erro nomeado e reversão de fusão | `src/database/manager.py:609` reverte e registra `COLISAO DE IDENTIDADE`. Os testes em `tests/test_database_manager.py:995` e `:1026` exercitam a falha de escrita via API sobre SQLite real. A SPEC-003 em `:147` e `:149` separa o log do alerta do dia. |
| ADR e suíte | `docs/adr/0005-identidade-do-concurso.md:71` registra as duas opções e a escolha do dono. A suíte da ponta passou. A revisão do teste existente de esquema está registrada em Padrões. |

## Prova

Medi com Python 3.12.9 e SQLite 3.45.3 em Windows, `PYTHONDONTWRITEBYTECODE=1`, sem marcadores ou configuração adicional de aplicação. O `git merge-base main HEAD` retornou 86be955. Medi 86be955 e e9f57ca em worktrees destacados.

| Recorte | Minha saída de pytest | Número do implementador |
| --- | --- | --- |
| Base de integração 86be955 | `582 passed in 131.98s (0:02:11)` | — |
| Base da rodada e9f57ca | `614 passed in 130.80s (0:02:10)` | `614 passed in 94.95s` |
| Ponta 09b4d0a | `617 passed in 132.60s (0:02:12)` | `617 passed in 183.36s` |
| Coleta da ponta, `pytest --collect-only -q -p no:cacheprovider` | `617 tests collected in 2.80s` | `617 tests collected in 1.92s` |

A conta fecha em 582 + 35 = 617 no ticket e 614 + 3 = 617 na quinta rodada. A nota de 603 testes em `.esteira/revisor.md:406` refere-se ao merge intermediário ff8e48d.

**Vermelhos de nível G−.** Rodei `python -m pytest -q -rs -p no:cacheprovider tests/test_database_manager.py -k "<testes acrescentados no commit>" --tb=short`, com o Python indicado acima, em cada commit `test:` destacado. O histórico registra os pares `test:` → `fix:` e os commits de documentação. A segunda rodada tem duas fatias de comportamento antes de 58033e2.

| Commit | Saída medida | Falha observada |
| --- | --- | --- |
| 3deba35 | `8 failed, 5 passed, 41 deselected` | Casamento de chave discordante, dois editais gravados no mesmo id e falha em reproduzir o log nomeado. |
| fa09826 | `2 failed, 4 passed, 52 deselected` | Fusão incompleta ou com o id errado preservado. |
| cfdf2b5 | `3 failed, 1 passed, 58 deselected` | Chave vazia gravada ou chave válida perdida. |
| 0dda815 | `3 failed, 1 passed, 62 deselected` | Chave legada de um espaço tratada como ausente. |
| 4ceb387 | `6 failed, 1 passed, 66 deselected` | Os três fallbacks escolheram e atualizaram a linha 2, quando se esperava a 1. |
| 95de698 | `1 failed, 2 passed, 73 deselected` | A fusão retornou 0 em vez de 1 e registrou `UNIQUE constraint failed: index 'idx_editais_identidade'`. Confere com o implementador. |

Guardas anteriores observadas nos commits `test:`: em 3deba35, rechave por nome, busca sem chave, preservação dos campos, idempotência e unicidade sem chave. Em fa09826, rechave por link e por entidade, log nomeado e reaproveitamento da linha sem chave. Em cfdf2b5, rechave da linha legada com vazio. Em 0dda815, recusa da linha com chave de um espaço pelo link. Em 4ceb387, o índice já devolvia o menor id no cenário do empate por chave.

**Mutações na ponta.** Conferi cada alteração com `git diff` em worktree destacado antes do pytest. Usei os mesmos argumentos acima, com `-k` para o alvo indicado. As mutações foram revertidas.

| Alteração e testes | Resultado |
| --- | --- |
| Remover `ORDER BY id`, `-k test_busca_pelo_pci_id_empatada` | `1 failed, 1 passed, 74 deselected`. O teste novo recebeu id 2 em vez de 1. |
| Remover o rollback do `IntegrityError`, `-k test_colisao_depois_de_uma_fusao_desfaz_a_fusao` | `1 failed, 75 deselected`. A API encontrou uma linha em vez de duas. |
| Desativar a rechave por link, `-k test_pci_id_rechaveia` | `1 failed, 1 passed, 74 deselected`. O caso de link recebeu id 2 em vez de 1. |
| Desativar a rechave por entidade, `-k test_pci_id_rechaveia` | `1 failed, 1 passed, 74 deselected`. O caso de entidade recebeu id 2 em vez de 1. |
| Priorizar nome antes do link, suíte inteira | `6 failed, 611 passed`. O teste existente de colisão pelo link e cinco outros testes detectaram a inversão. |

Os testes comportamentais usam a costura pública e resultados esperados literais. O SQL de preparação monta estados do SQLite ou força uma falha na fronteira de persistência. A lacuna do R-82 aparece no experimento de dois órgãos com chaves distintas. O teste existente em `tests/test_database_manager.py:485` cobre a colisão pelo link com linhas sem chave.

## Padrões

A recriação de `editais` em `src/database/manager.py:249` aplica a exceção documentada em `kanban/REGRAS.md:24` e na SPEC-003 §4. A transação, o backup de implantação e a nomenclatura do banco estão documentados na ADR. O diff está restrito aos quatro arquivos do ticket.

O teste existente `test_area_nome_is_unique`, em `tests/test_database_manager.py:99`, preserva o nome e troca a inspeção do DDL pela verificação da restrição efetiva do banco, conforme a SPEC-003 §4. Ele continua exigindo colisão para duas linhas sem chave de mesmo nome e exige colisão para a repetição do mesmo nome e chave, além de aceitar chaves distintas. Os testes da quinta rodada usam a API pública.

Lint não configurado. `git diff --check 86be955..09b4d0a` retornou vazio. Revisão em leitura, com as mutações confinadas a worktrees temporários e sem alteração versionada na branch do ticket.
