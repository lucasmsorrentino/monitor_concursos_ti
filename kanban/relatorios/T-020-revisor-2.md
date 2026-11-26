REPROVADO
Esteira: revisor · codex (gpt-6.2-sol) · nível G- · esforço high · 2026-11-26 13:00 → 2026-11-26 13:09 (9 min)
Resumo: A segunda rodada corrige a fusão de múltiplas grafias sem chave, normaliza a string vazia e cobre as rechaves por link e por entidade. A suíte passou com 590 testes.
A revisão reproduziu dois defeitos fora desses cenários. Uma atualização sem `pci_id` passou a gravar no outro edital após a migração. Uma fusão com `pci_id` legado composto de espaço fez desaparecer uma chave canônica válida.

Arquivos: `CLAUDE.md`, `docs/adr/0005-identidade-do-concurso.md`, `src/database/manager.py` e `tests/test_database_manager.py`, todos dentro do `toca`.

Commits:

1. `3deba35` test: identidade pelo pci_id e unicidade que admite dois editais do mesmo orgao
2. `47291be` fix: o pci_id que discorda vence o nome, e a unicidade admite dois editais do mesmo orgao
3. `17537ba` docs: ADR-0005, identidade do concurso e unicidade com o pci_id
4. `fa09826` test: a fusao pelo nome leva todas as grafias do orgao e nunca dois editais
5. `31e9b24` fix: a fusao pelo nome leva todas as grafias do mesmo orgao, nunca dois editais
6. `cfdf2b5` test: pci_id vazio conta como nulo na escrita, na busca e na fusao
7. `a4f2d58` fix: pci_id vazio entra como nulo e a fusao nao o trata como chave
8. `58033e2` docs: schema v7 e a fusao de todas as grafias no CLAUDE.md, na ADR-0005 e nas docstrings

Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs -p no:cacheprovider` → base de integração `d5fdae7` 569 passed / 0 failed / 0 skipped · base da rodada `17537ba` 582 passed / 0 failed / 0 skipped · ponta `58033e2` 590 passed / 0 failed / 0 skipped.

Testes que nascem verdes: Na primeira rodada, `test_pci_id_casa_com_linha_sem_pci_id_e_rechaveia` e `test_item_sem_pci_id_mantem_a_ordem_de_hoje` guardam os fallbacks simples. `test_migracao_preserva_id_estado_usuario_e_contagem` e `test_migracao_rodada_duas_vezes_nao_muda_nada` passam também com o schema antigo. `test_unicidade_continua_barrando_nome_repetido_sem_pci_id` guardava a restrição já existente. Na segunda rodada, os dois testes de rechave guardam fallbacks já implementados e falharam sob mutação. `test_linha_legada_com_pci_id_vazio_e_rechaveada` guarda o casamento de `''`. `test_nome_repetido_sem_pci_id_volta_para_a_mesma_linha` guarda a repetição pela API pública. O novo cenário de `test_colisao_irresolvivel_vira_erro_no_log_nao_silencio` guarda o log que a primeira rodada já implementava.

## Spec

1. **Exigência — R-82. Preserve a linha que uma atualização sem `pci_id` encontrava antes da migração.** Reproduzi em dois bancos v6 equivalentes, com `UNIQUE(area, nome)` e sem o índice auxiliar de PCI, configuração que o schema da base admite. As linhas eram `(1, "ifsp", "100", "ativo")` e `(2, "IFSP", "900", "seguindo")`, com o mesmo link específico. Na base, a busca por nome, pelo link e por entidade retornou o ID 2. Após a migração na ponta, as três retornaram o ID 1. `atualizar_concurso("IFSP", "novo", "")` devolveu 2 na base e alterou apenas o status de `900`. Na ponta devolveu 1 e alterou apenas o de `100`. No SQLite 3.45.3, `EXPLAIN QUERY PLAN` confirmou que a busca por nome passou de `sqlite_autoindex_editais_1` para `idx_editais_pci`, e o primeiro resultado passou a depender da ordem do índice de PCI. Em `src/database/manager.py:386`, `:397` e `:417`, dê às buscas sem chave um desempate explícito que preserve o resultado legado reproduzido. Em `tests/test_database_manager.py`, acrescente um caso com as duas grafias e IDs em ordem oposta à dos nomes, em banco v6 migrado. Afirme pelas APIs públicas o ID escolhido nos três fallbacks, o status novo no ID 2 e o status original no ID 1. O teste atual de R-82 tem um único candidato e a nova regressão de fusão tem um link que desambigua a linha de partida. Referências `main:docs/specs/SPEC-003-identidade-do-concurso-e-cota-da-llm.md:138`, `src/database/manager.py:268`, `tests/test_database_manager.py:704` e `:775`.
2. **Exigência — R-80/R-83. Aplique o mesmo critério de nulidade à busca e à fusão.** A base gravou `pci_id=" "` pela API pública. A migração preservou o valor. Na ponta, o link específico entre nomes de órgãos diferentes recusou essa linha para o item `296538`, enquanto o fallback por entidade aceitou a mesma linha e substituiu seu ID de PCI. Em outra cópia, com a linha `IFSP - SP` de `pci_id="296044"`, atualizei pelo link da linha legada, sem chave no item. O retorno foi 1, o registro sobrevivente manteve `" "` e a busca por `296044` devolveu `None`. O Python classifica o espaço como ausente, aceita a fusão e autoriza o descarte da outra linha. Já o `NULLIF(pci_id, '')` conserva o espaço e deixa de herdar a chave válida. Em `src/database/manager.py`, alinhe o critério ao da ADR e do índice, que equiparam `''` a `NULL`, preservando valores legados não vazios. Em `tests/test_database_manager.py`, cubra a recusa do identificador discordante nos três fallbacks e a preservação de ambos os IDs e chaves após a atualização sem `pci_id`. Os testes de `''` continuam cobrindo normalização e rechave. Referências `main:docs/specs/SPEC-003-identidade-do-concurso-e-cota-da-llm.md:134` e `:140`, `docs/adr/0005-identidade-do-concurso.md:31` e `:37`, `src/database/manager.py:94`, `:384`, `:420`, `:638` e `:680`, `tests/test_database_manager.py:853` e `:886`.
3. **R-80/R-81 para chaves regulares e para `NULL`/`''`.** Os testes dos três fallbacks discordantes estão em `tests/test_database_manager.py:671`, `:676` e `:684`. Os de rechave por nome, link e entidade estão em `:690`, `:828` e `:841`. Os testes em `:853` e `:872` confirmam a normalização de `''` na escrita e a rechave da linha legada. A fusão das três grafias pedida pelo arquiteto também passa e mantém o ID casado e o status novo. Referências `main:docs/specs/SPEC-003-identidade-do-concurso-e-cota-da-llm.md:134`, `src/database/manager.py:375`, `:518` e `:632`, `tests/test_database_manager.py:775`.
4. **R-83, R-84, R-85 e idempotência.** Os testes de coexistência e rodadas sucessivas afirmam IDs distintos, prazos, fases e preservação do estado ao renomear. A migração copia os campos e conserva `sqlite_sequence` em transação. Os testes do banco v6 verificam os registros completos e as contagens, a emissão do próximo ID sem reciclar o anterior e a igualdade do arquivo após a segunda abertura. A ADR registra as duas opções, a escolha do dono e o backup. Referências `main:docs/specs/SPEC-003-identidade-do-concurso-e-cota-da-llm.md:140` e `:185`, `src/database/manager.py:211`, `tests/test_database_manager.py:716`, `:733`, `:755`, `:1013`, `:1025` e `:1041`, `docs/adr/0005-identidade-do-concurso.md:53` e `:84`.
5. **R-86 e escopo.** A restrição que sobra no teste dispara `COLISAO DE IDENTIDADE` em nível ERROR e devolve 0. A fixture instala um gatilho SQLite para produzir a colisão e chama a API pública. A cópia da SPEC no worktree ainda contém a redação anterior na linha 147. A versão normativa em `main` (`86be955`) e a nota vigente do arquiteto atribuem o log ao R-86 e o alerta do dia ao R-97, no T-026. O diff respeita o `toca`. Referências `main:docs/specs/SPEC-003-identidade-do-concurso-e-cota-da-llm.md:147` e `:205`, `main:kanban/tickets/T-020-identidade-do-concurso-o-pci-id-que-disc.md:149`, `src/database/manager.py:580`, `tests/test_database_manager.py:906`.

## Prova

Usei o executável acima, sem marcadores, filtros ou variáveis de configuração do projeto. Defini `PYTHONDONTWRITEBYTECODE=1` e desliguei o cache do pytest para evitar artefatos nos worktrees. A base veio de `git merge-base main HEAD`. Medi a base e o ponto de partida da segunda rodada em worktrees destacados.

| Revisão | Alegação do implementador | Saída medida |
| --- | --- | --- |
| `d5fdae7`, base da primeira rodada | 569 passed | `569 passed in 93.97s (0:01:33)` |
| `17537ba`, ponta da primeira rodada e base da segunda | 582 passed | `582 passed in 95.30s (0:01:35)` |
| `58033e2`, ponta atual | 590 passed | `590 passed in 114.42s (0:01:54)` |

Todas as suítes completas tiveram 0 falhas e 0 pulos. Com `-m pytest --collect-only -q -p no:cacheprovider` na ponta, a saída foi `590 tests collected in 1.59s`. A conta fecha em 569 + 13 + 8 = 590, com a troca de um teste da primeira rodada por outro na segunda. A troca foi pedida pelo arquiteto para que o teste de repetição passe pela API pública. A guarda da restrição continua em `test_area_nome_is_unique`. Nenhum teste da base de integração foi removido ou renomeado. A asserção de DDL desse teste foi substituída pela restrição decidida pelo dono na SPEC-003.

Para os três commits `test:` usei o mesmo executável e `-m pytest -q -rs -p no:cacheprovider --tb=short tests/test_database_manager.py` em worktrees destacados.

| Commit | Alegação do implementador | Saída medida e causa |
| --- | --- | --- |
| `3deba35` | 9 failed, 45 passed | `9 failed, 45 passed in 4.90s`. Asserções de identidade, coexistência, prazo, renomeio, colisão e abertura da unicidade. A restrição do schema anterior também provocou `IntegrityError` no teste de schema. |
| `fa09826` | 2 failed, 56 passed | `2 failed, 56 passed in 5.40s`. O cenário de três grafias devolveu 0 no lugar de 1. O outro deixou o edital de nome exato no ID 3. |
| `cfdf2b5` | 3 failed, 59 passed | `3 failed, 59 passed in 3.38s`. O vazio foi gravado como `''`, apagou uma chave gravada ou impediu sua herança. |

As falhas foram reproduzidas após coleta e importação. Para a mutação da rechave, desativei apenas os fallbacks de link e entidade para entradas com `pci_id` em um worktree destacado de `58033e2`, conferi a alteração por `git diff` e rodei o mesmo comando do módulo. Saída medida `2 failed, 60 passed in 1.22s`. O implementador informou `2 failed, 56 passed` na ponta da primeira fatia da rodada, quatro testes antes. Falharam os dois casos pedidos, cada um retornando 2 em vez do ID original 1. Na ponta intacta, o módulo teve `62 passed in 0.94s`. A montagem dos bancos e do gatilho ocorre na fronteira de persistência. As asserções comportamentais usam as interfaces públicas e valores esperados independentes.

## Padrões

- A recriação é a exceção autorizada por `kanban/REGRAS.md:22`. A docstring de `_ensure_schema` e o `CLAUDE.md` agora descrevem o v7 e a exceção. O diff preserva as dependências do projeto e os testes novos usam bancos locais e fixtures sem rede. Referências `src/database/manager.py:132`, `CLAUDE.md:150`, `:156` e `:180`.
- Ressalva de processo já commitado. Os pares `test:` → `fix:` estão na ordem e cada rodada termina em `docs:`. Os commits de implementação também ajustaram docstrings e comentários de contrato. A ressalva fica na revisão de processo, conforme `kanban/REGRAS.md:28`.
- Lint ausente da configuração do projeto. `git diff --check d5fdae7..HEAD` e `git diff --check 17537ba..HEAD` passaram.

Desvios e riscos: A mudança de desempate pode alterar a linha escolhida por uma fonte sem chave em bancos legados. A nulidade aplicada de formas diferentes pode perder o `pci_id` de um edital em uma fusão. Os dois efeitos foram observados em bancos temporários pelas APIs públicas.

Pendências: Atender às duas exigências de Spec. O alerta do dia (R-97) fica no T-026 e o reparo das linhas já colididas fica no T-023. A integração segue sujeita ao OK do dono e a primeira execução em produção requer backup. Os seis worktrees temporários foram removidos e o estado versionado do worktree do ticket continua limpo.
