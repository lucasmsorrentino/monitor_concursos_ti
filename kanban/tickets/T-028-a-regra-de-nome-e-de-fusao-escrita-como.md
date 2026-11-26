---
id: T-028
titulo: A regra de nome e de fusao, escrita como tabela de decisao
tipo: codigo
nivel: G-
status: backlog
repo: principal
spec: [SPEC-003, R-100]
depende_de: [T-020, T-026]
toca: [src/database/manager.py, tests/test_database_manager.py, docs/adr/0005-identidade-do-concurso.md, CLAUDE.md]
recursos: []
afinidade:
retornos: 0
---
# T-028 · A regra de nome e de fusao, escrita como tabela de decisao

## Contexto

O T-020 troca a unicidade da tabela `editais`, de `UNIQUE(area, nome)` para um indice por expressao sobre
`(area, nome, COALESCE(pci_id, ''))`. Trocar a unicidade **cria estados novos alcancaveis**: duas linhas de
mesmo nome e chaves diferentes passam a coexistir legalmente, e o `_resolver_nome_sem_colisao` passa a ser
chamado em situacoes que antes o proprio banco impedia.

Esses estados nunca foram enumerados. O T-020 levou **cinco revisoes e quatro defeitos distintos** na mesma
funcao, e o diagnostico do arquiteto em 26/11/2026 (SPEC-003 secao 4 item 6) e que a causa raiz nao e nenhuma
das quatro guardas: e que a regra nunca foi escrita como regra. Nao havia requisito dizendo o que a funcao
deve fazer em cada estado, e por isso cada rodada consertou o caso que o revisor trouxe e o caso seguinte
ficou.

Este ticket escreve a regra. Por decisao do dono, o T-020 fica com o **R-99**, que e conservador: o nome novo
so vence quando ninguem o ocupa, e nao existe fusao em caminho nenhum. Este ticket substitui o R-99 pelo
R-100, e **a primeira entrega e a tabela, nao o codigo**.

## Critério de aceite
- [ ] A ADR-0005 ganha a **tabela de decisao enumerada**, e ela e o primeiro commit do ticket (`docs:`),
      antes de qualquer teste ou codigo (R-100)
- [ ] A tabela fecha o espaco de estados pelo produto dos eixos abaixo. **Nenhuma combinacao fica sem
      linha**, e cada linha diz tres coisas: o nome final, se funde (e qual linha sobrevive) e o que vai
      para o log:
      - **eixo 1** existe linha em conflito pelo `nome` novo na area (COLLATE NOCASE): nao / sim
      - **eixo 2** a chave da linha em conflito, contra a chave do item: as duas nulas / iguais / so a linha
        em conflito tem chave / so o item tem chave / as duas tem chave e sao diferentes
      - **eixo 3** `mesma_entidade(nome_novo, nome_atual)`: sim / nao
      - **eixo 4** quantas linhas estao em conflito: uma / mais de uma
- [ ] Cada linha da tabela tem **um teste nomeado**, e o nome do teste aparece na propria tabela, numa
      coluna. Linha sem teste e aceite nao cumprido
- [ ] **O invariante, que e o aceite mais importante:** a funcao nunca devolve o nome novo deixando atras de
      si um conflito que ela nao fundiu. Vale um teste de propriedade sobre a bateria de cenarios da tabela,
      afirmando o invariante em todos de uma vez, alem dos testes linha a linha
- [ ] Onde a tabela disser que funde, a fusao preserva o que o `_fundir` da `main` preservava, e isso esta
      escrito na ADR-0005 pelo T-020: `estado_usuario` pela prioridade `seguindo` > `ignorado` > `ativo`,
      vindo de qualquer das duas linhas; `fase` pela mais avancada; `data_fim_inscricao`, `link`, `pci_id` e
      `fonte` por `COALESCE` do que a linha mantida nao tiver. **Perder uma estrela do Lucas numa fusao
      automatica e falha de aceite, nao detalhe de implementacao**
- [ ] O nome final e a chave final entram no banco **no mesmo `UPDATE`**, sem estado intermediario que colida
      com o indice de unicidade (regra ja provada no T-020, rodada 5)
- [ ] O desempate explicito pelo menor `id` nas buscas de identidade continua valendo e nao e reescrito
      (regra ja provada no T-020, rodada 4)
- [ ] O criterio unico de nulidade do `pci_id` (`NULL` ou vazio; qualquer outro valor e chave) continua
      valendo, o mesmo na busca, na escrita, na fusao e no indice
- [ ] Nenhuma linha e apagada por caminho que a tabela nao preveja explicitamente
- [ ] Suite inteira verde; nenhum teste do T-020 afrouxado, renomeado ou apagado. O
      `test_nome_nao_vira_de_outro_orgao_o_caso_do_parecer_5` **continua passando**: qualquer tabela que o
      quebre esta errada
- [ ] O `CLAUDE.md` descreve a regra apontando para a tabela da ADR-0005, sem copiar a tabela

## Plano de testes
Costura: `DatabaseManager.atualizar_concurso` e `DatabaseManager.buscar_registro`, sobre banco temporario em
**arquivo**, com o schema que o T-020 deixou (indice por expressao). Pega: o nome final, a fusao, o log e o
invariante. Nao pega: a notificacao, que e do `src/core/bot.py` e nao muda aqui.
Oráculo: a tabela da ADR-0005, escrita a mao neste ticket e revisada antes do codigo. **O oraculo e a tabela,
nao o codigo de hoje:** nenhum valor esperado pode ser lido do comportamento atual da funcao.

Os quatro defeitos do T-020 entram como cenarios obrigatorios, porque cada um deles e uma linha da tabela que
nao existia:

- `test_funde_todos_os_conflitos_nao_um_so` — defeito 1 (rodada 1): varias linhas disputando o nome.
- `test_busca_empatada_escolhe_a_linha_mais_antiga` — defeito 2: ja existe no T-020, aqui e nao-regressao.
- `test_nome_e_chave_finais_no_mesmo_update` — defeito 3 (rodada 5): o cenario das tres linhas pelo link
  especifico, afirmando que nao existe estado intermediario que colida.
- `test_nome_nao_vira_de_outro_orgao_o_caso_do_parecer_5` — defeito 4: ja existe no T-020, aqui e
  nao-regressao, e e o teste que diz se a tabela esta certa.
- `test_invariante_nunca_devolve_nome_novo_com_conflito_nao_fundido` — a propriedade, sobre a bateria inteira.
- um teste por linha da tabela, com o nome que a tabela declara.

## Fora do escopo
- A migracao e a unicidade. Entregues no T-020, nao se mexe nelas aqui.
- A ordem de identidade (`pci_id`, link especifico, `(area, nome)`, entidade) e o `_buscar_por_entidade`.
  Provados em cinco revisoes.
- O alerta do dia da colisao: e o T-026 (R-97).
- Transacao e concorrencia: e o T-027 (R-98), que vem **depois** deste, porque este reescreve a funcao que
  aquele vai envolver.
- Reparar linha que ja colidiu: e o T-023, e pede julgamento do dono.

## Notas do arquiteto

**Por que G−:** nao e volume de codigo, e densidade de consequencia, e tem historia medida. A mesma funcao
reprovou quatro vezes por quatro motivos diferentes. O que muda nesta rodada e que a entrega **comeca** por um
artefato de decisao, e o codigo vira execucao de uma regra ja escrita.

**Por que a tabela vem antes do codigo, e isso nao e formalidade.** Com a tabela, um defeito e uma linha
errada ou faltando, e aparece na revisao do commit `docs:`, que custa pouco. Sem ela, um defeito e uma guarda
na ordem errada, e so aparece quando o revisor acha o caso: foi o que custou cinco rodadas. **Se durante o
codigo aparecer um estado que a tabela nao previu, pare e volte para a tabela.** Nao resolva no codigo: foi
exatamente assim que os quatro defeitos entraram.

**O que a medida de producao diz sobre a urgencia** (26/11/2026, log do notebook, leitura): o caminho
conservador disparou **109 vezes** na historia do bot; a fusao disparou **7 vezes**, a ultima em
**15/09/2026**, e nenhuma depois. O R-99 nao esta segurando enxurrada nenhuma, e este ticket pode ser feito
com calma e direito. O que ele devolve e a limpeza de duplicata legada do mesmo orgao, que hoje fica no banco.
Nao e ticket de incendio.

**Nao herde o codigo das cinco rodadas.** O `_resolver_nome_sem_colisao` que o T-020 deixa e proposital e
simples (R-99). Escreva a funcao nova a partir da tabela, com a forma que a tabela pedir. Se a tabela ficar
com muitas linhas repetidas, isso e sinal de que ela quer ser um dicionario de casos, nao uma cadeia de `if`:
a sequencia de guardas foi o que falhou quatro vezes.

**O historico esta no repo.** `kanban/relatorios/T-020-revisor-1.md` a `T-020-revisor-4.md` e
`T-020-implementador-1.md` a `T-020-implementador-5.md`. Leia os quatro pareceres antes de escrever a tabela:
eles sao os quatro casos reais que ela tem de cobrir.
