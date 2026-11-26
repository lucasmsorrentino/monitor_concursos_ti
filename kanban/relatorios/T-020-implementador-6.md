ENTREGUE
Esteira: implementador · opus (claude-opus-5-5) · nível G- · esforço high · 2026-11-26 15:02 → 2026-11-26 15:16 (14 min)
Resumo: Rodada 6, de escopo novo, conforme a decisão do dono de 26/11/2026. A branch foi reduzida ao que estava provado. `_resolver_nome_sem_colisao` passa a cumprir o R-99: o nome novo só vence quando nenhuma outra linha da área o ocupa (COLLATE NOCASE). Havendo conflito, a linha mantém o nome atual e o log registra `COLISAO DE NOME` em WARNING, com os dois ids. O `_fundir` saiu do arquivo, junto com `_PRIORIDADE_ESTADO` e o import de `fase_mais_avancada`. Nenhum caminho do `atualizar_concurso` funde ou apaga linha. A migração, a ordem de identidade, o desempate pelo menor id, o critério único de nulidade e o log `COLISAO DE IDENTIDADE` ficaram intocados. A regra de `estado_usuario` que o `_fundir` carregava (`seguindo` > `ignorado` > `ativo`) está registrada na ADR-0005 como o que a fusão futura tem de preservar.
Arquivos: src/database/manager.py, tests/test_database_manager.py, docs/adr/0005-identidade-do-concurso.md, CLAUDE.md. Todos estão no «toca».
Commits:
- f9a9337 test: o nome novo so vence quando ninguem o ocupa, e nenhum caminho funde linha
- d871bbe fix: o nome so muda quando ninguem o ocupa, e a fusao de linhas sai do banco
- 34e75d3 docs: o nome conservador sem fusao na ADR-0005, no CLAUDE.md e na docstring do modulo
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs -p no:cacheprovider`
- base 42369c1: 626 passed / 0 failed / 0 skipped (`626 passed in 159.71s`);
- ponta 34e75d3: 633 passed / 0 failed / 0 skipped (`633 passed in 146.18s`). `pytest --collect-only -q` → `633 tests collected`.
- A conta fecha: 626 + 11 casos novos − 4 testes de fusão apagados = 633.
- Medido em Windows, com o Python do .venv do repo principal, sem variáveis de ambiente nem marcadores. Lint não configurado. `git diff --check` saiu vazio.

Vermelho do commit test (f9a9337): rodei `pytest tests/test_database_manager.py -k "TestNomeConservador or test_renomear_para_o_nome_do_outro_edital"` com o código antigo. Saída: `8 failed, 4 passed, 75 deselected`. Todas as falhas são asserções, nenhuma é de coleta ou importação:
- `test_nome_em_conflito_mantem_o_nome_atual_e_loga[mesmo_orgao]`: `(1, 'IFSP', 'novo') == (1, 'IFSP - SP', 'novo')`. A fusão renomeou a linha e apagou a 2.
- `test_nome_em_conflito_so_de_caixa_tambem_mantem_o_nome_atual`: `('IFSP', 'novo') == ('IFSP - SP', 'novo')`.
- `test_nenhum_caminho_funde_ou_apaga_linha`, quatro casos com contagem por fonte menor depois da escrita:
  - `[duas_grafias_sem_chave]`: `{'gran': 1} == {'gran': 2}`;
  - `[tres_grafias_sem_chave]`: `{'gran': 1} == {'gran': 3}`;
  - `[casada_com_chave_e_grafia_sem_chave]`: `{'gran': 0, 'pci_mcp': 1}`;
  - `[casada_sem_chave_e_grafia_com_chave]`: `{'gran': 1, 'pci_mcp': 0}`.
- `test_nome_nao_vira_de_outro_orgao_o_caso_do_parecer_5`: `(1, 'TJPR', 'A depois') == (1, 'IFSP - SP', 'A depois')`. É o quarto defeito, reproduzido.
- `test_renomear_para_o_nome_do_outro_edital_nao_funde_as_linhas`, com a expectativa ajustada (ver Desvios): o técnico assumiu o nome do substituto.

Testes que nascem verdes: são quatro guardas, todos no commit test.
- `test_nome_novo_vence_quando_ninguem_ocupa`: é o caminho de troca de nome que o código antigo já fazia, e o R-99 o mantém.
- `test_nome_em_conflito_mantem_o_nome_atual_e_loga[outro_orgao]`: o código antigo já preservava o nome quando o conflito era de outro órgão sem chave. O caso existe para afirmar que o resultado é igual ao do caso `mesmo_orgao`, como pede o plano de testes.
- `test_nenhum_caminho_funde_ou_apaga_linha[rechave_com_nome_de_outro_edital]` e `[nome_de_outro_orgao]`: o código antigo não fundia nesses dois. Hoje eles só protegem a contagem. O `[nome_de_outro_orgao]` não pega o rename indevido, porque quem afirma o nome é o teste do parecer 5, que nasceu vermelho.

Desvios e riscos:
- **Testes apagados porque afirmavam fusão.** Todos tinham sido acrescentados nesta branch, nenhum vem da `main`, e os quatro falharam com o código novo:
  - `test_item_sem_pci_id_funde_todas_as_grafias_do_nome_novo`;
  - `test_fusao_pelo_nome_nao_junta_dois_editais_de_pci_id_distintos`;
  - `test_fusao_grava_nome_e_chave_finais_juntos_sem_colidir_no_meio`;
  - `test_linha_legada_com_pci_id_vazio_herda_o_pci_id_na_fusao`.
- **Teste renomeado, também desta branch.** `test_colisao_depois_de_uma_fusao_desfaz_a_fusao` virou `test_colisao_na_escrita_deixa_as_duas_linhas_como_estavam`. O corpo e as asserções não mudaram, só a docstring. Ele continua verde e vale como guarda do R-86: a escrita que falha sai nomeada e não deixa o banco pela metade. Só o nome citava uma fusão que não existe mais.
- **Teste com expectativa alterada, também desta branch.** `test_renomear_para_o_nome_do_outro_edital_nao_funde_as_linhas` afirmava que o técnico assumia o nome do substituto (outro edital do mesmo órgão). O R-99 proíbe isso. A última asserção passou a esperar `IFSP_NOME_SEM_UF`. As asserções de não-fusão, da estrela e do prazo do substituto ficaram como estavam.
- Nenhum teste da `main` foi afrouxado, renomeado ou apagado nesta rodada.
- **Ticket contra regra do projeto, sobre a ADR «remeter ao T-028».** O aceite (`.esteira/implementador.md:262-263`) pede que a ADR-0005 remeta ao T-028. As regras do projeto (`.esteira/implementador.md:185-186`) proíbem IDs do quadro em doc do repo, e elas mandam mais que o ticket. A ADR remete ao requisito, «SPEC-003, R-100», que é o requisito do T-028, e não cita o ID do ticket. A SPEC-003 já cita T-020 e T-028 (linhas 247-248). Isso é anterior a esta rodada e não foi mexido.
- **Nível do log de conflito de nome.** O R-99 diz «a colisao entra no log (R-86)». O R-86 fala de colisão «que o codigo nao consiga resolver», com «erro nomeado». O conflito de nome é resolvido: a escrita acontece e só o nome não muda. Por isso escolhi WARNING com nome próprio, `COLISAO DE NOME`, distinto do ERROR `COLISAO DE IDENTIDADE` da escrita perdida. O caminho disparou 109 vezes na história, e ERROR aqui seria ruído. O teste aceita WARNING ou acima, então subir para ERROR é uma linha, se o revisor ou o dono preferir.
- **O revisor deve olhar o `UPDATE`.** O `pci_id_final` saiu, e o `UPDATE` voltou a gravar `COALESCE(<pci_id do item>, pci_id)`, como na `main`. Raciocínio de por que não há colisão possível com um escritor só: a linha casada recebe só o nome atual ou um nome livre. Ela recebe chave nova só na rechave, e, se outra linha já tivesse a mesma chave, a busca pelo `pci_id` a teria achado antes. O cenário `[rechave_com_nome_de_outro_edital]` exercita isso.
- O que fica com o R-99: duplicata legada do mesmo órgão continua no banco, como já está em produção. É a dívida declarada na SPEC-003.

Pendências:
- **T-028 (R-100).** Primeiro a tabela de decisão do nome e da fusão na ADR-0005, depois o código, preservando a regra do `estado_usuario` registrada lá.
- **T-023.** Reparo das linhas que já colidiram.
- **T-026 (R-97).** Alerta do dia para a colisão.
- **T-027 (R-98).** Concorrência.
- **Integração.** Segue o gate «OK do Lucas:», e a primeira execução em produção exige backup de `data/concursos.db`.
- **Push.** Não foi feito, pela regra do projeto. O trabalho fica nos commits locais da branch.
