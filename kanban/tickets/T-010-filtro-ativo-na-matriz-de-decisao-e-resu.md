---
id: T-010
titulo: Filtro ativo na matriz de decisao e resumo semanal
tipo: codigo
nivel: G-
status: backlog
repo: principal
spec: [SPEC-001, PED-03, PED-04, R-11]
depende_de: [T-001, T-002, T-003, T-005, T-007, T-009]
toca: [src/core/bot.py, tests/test_concurso_bot.py]
recursos: []
afinidade:
retornos: 0
---
# T-010 · Filtro ativo na matriz de decisao e resumo semanal

## Contexto

Este e o ticket que cumpre o pedido: **parar de mandar concurso que nao paga, fora do Sul**, so na area TI
(PED-03 e PED-04). Todas as pecas chegam prontas: a porta do MCP ja alimenta a rodada, o banco tem as colunas,
o `decidir` sabe decidir, o `teto_de` e o `esfera_de` sabem ler, o `montar` sabe escrever o resumo e o loader
sabe ler a configuracao. Falta liga-las na matriz de decisao do `ConcursoBot`.

As regras estao na SPEC-001 secoes 4.2, 4.3 e 4.4. O porque de cada isencao esta em
`docs/adr/0002-elegibilidade-pelo-teto-do-concurso.md`.

**O erro aqui e silencio**, e silencio nao quebra teste nenhum: um concurso que devia chegar e nao chega so
aparece semanas depois. Por isso cada regra do aceite tem teste proprio e a regra 0 (a estrela do Lucas) e
intocavel.

## Critério de aceite

### A decisao

- [ ] `_decidir_e_notificar` monta um `Candidato` (SPEC-001 secao 3.4) a partir do item e do registro, e chama
      `elegibilidade.decidir` com a `Politica` do alvo, montada da config no `__init__`:
      `uf` do campo `uf` do item, ou de `extrair_uf(nome)` quando o item nao traz;
      `regiao` do campo `regiao`;
      `esfera` de `esfera_de(nome)`;
      `teto` de `teto_de(item["vagas_salario"])`;
      `cargos_total` do campo;
      `seguindo` verdadeiro quando o registro no banco tem `estado_usuario == "seguindo"`.
- [ ] **So item de porta que carrega `regiao` e avaliado** (R-15 da SPEC-001). Hoje e a do MCP. Item do Gran,
      da pagina de cargo ou da lista nacional **nao** e avaliado, **nao** recebe selo e **nao** grava
      `elegibilidade`: ele entra como entra hoje. Motivo: so a porta do MCP traz `regiao`, `cargos_total` e o
      teto, e marcar com selo tudo que vem do Gran poria `⚠️` em cada card por falta de dado que aquela porta
      nunca teve.
- [ ] A chamada acontece **depois** da checagem de `estado_usuario == "ignorado"` (que continua saindo com
      `skip` sem tocar o banco) e **antes** de qualquer decisao de novo, inativo ou transicao.
- [ ] **Item filtrado nao notifica** (R-11): salva em silencio com `elegibilidade='filtrado'` e o
      `motivo_filtro` da decisao, loga em `info` o nome, o motivo e o teto, e devolve `"skip"`. Nao entra em
      `novos_cont` nem em `atualizados_cont`, e nao entra no coletor da primeira carga.
- [ ] **Item que entra** grava `elegibilidade='elegivel'` e o `motivo_filtro` da decisao, e segue pela matriz
      de hoje sem nenhuma outra mudanca de comportamento.
- [ ] As sete colunas do v6 sao gravadas em toda chamada de `salvar`, para item avaliado: `uf`, `regiao`,
      `esfera`, `cargos_total`, `salario_teto`, `elegibilidade`, `motivo_filtro`.
- [ ] **Linha filtrada que passa a entrar sai como NOVO** (R-12): quando o registro existe com
      `elegibilidade == 'filtrado'` e a decisao de agora e `entra`, a matriz trata o caso como **inedito**
      (o caminho de novo concurso), e nao como atualizacao, porque o Lucas nunca viu esse concurso.
- [ ] **Linha que entrava e passa a filtrada** (R-13): nada se renotifica, nada se apaga, so se grava o novo
      `elegibilidade` e `motivo_filtro`.
- [ ] **O selo aparece no card:** decisao com `selo` preenchido (motivos `nao_verificado` e `sem_evidencia`)
      acrescenta uma linha com o selo na mensagem de novo concurso. Decisao sem selo nao muda a mensagem.
- [ ] **Area com `filtro_salarial` desligado nao muda em nada** (R-14): `Politica.modo` fica `"desligado"`, o
      `decidir` devolve `filtro_desligado` para tudo, nada e filtrado e nenhum selo aparece. Vale para
      EDUCACAO e SOCIOLOGIA_ARTES.

### O resumo semanal

- [ ] Com `resumo_filtrados == "semanal"`, no fim de `executar()` (depois da mensagem final e do alerta de
      fontes doentes), o bot busca os filtrados dos ultimos 7 dias com `listar_filtrados`, monta o texto com
      `resumo_filtrados.montar` e manda **uma vez por semana por area** (R-20).
- [ ] O controle de uma vez por semana e marcador em arquivo (R-22), no mesmo lugar e no mesmo estilo dos
      marcadores que `_alerta_uma_vez_por_dia` ja grava, mas com a chave da semana ISO que
      `resumo_filtrados.marcador_da_semana` devolve. Nao depende de o cron acertar o dia: a primeira rodada da
      semana manda, as outras nao.
- [ ] **Semana sem nada filtrado nao manda nada** (R-21) e **nao grava o marcador**, para a semana seguinte
      nao comecar silenciada.
- [ ] Em `--dry-run` nada e enviado e nenhum marcador e gravado, como ja vale para o resto.
- [ ] Falha ao montar ou mandar o resumo e logada e **nao derruba a rodada**: o resumo e informativo, a
      varredura e o trabalho.

- [ ] A suite inteira continua verde (296 testes em 23/11/2026).

## Plano de testes

Costura: `ConcursoBot.executar()`, com as portas, o `TelegramNotifier` e o banco dublados, como
`tests/test_concurso_bot.py` ja faz. E a interface publica mais alta que alcanca tudo o que o aceite cobra:
filtro aplicado, silencio, gravacao, o card com selo, e o resumo. Pega a rodada inteira; **nao pega** o
transporte HTTP, nem a decisao em si (ja coberta no modulo puro), nem o texto do resumo (idem).

Oráculo: itens de entrada escritos a mao, montados a partir das fixtures reais em `tests/fixtures/pci_mcp/`,
com o veredito de cada um decidido a mao pela tabela da SPEC-001 secao 4.2 e escrito no teste. As chamadas ao
notificador e ao banco sao observadas pelos dubles. Nenhum esperado sai de chamar `decidir`.

Testes que nascem vermelhos em `tests/test_concurso_bot.py`:

- `test_filtrado_nao_notifica_e_salva_em_silencio` — item do MCP, MG, municipal, teto 8628.87, filtro ativo
  com corte 10000: o notificador **nao** e chamado, o banco recebe `elegibilidade='filtrado'` e
  `motivo_filtro='abaixo_do_corte'`, e o contador de novos fecha em 0.
- `test_municipal_inflado_nao_notifica` — SP, municipal, teto 18540.71, 86 cargos: filtrado com
  `motivo_filtro='municipal_inflado'`.
- `test_do_sul_notifica_mesmo_com_teto_baixo` — SC, municipal, teto 8889.30, 56 cargos (a Prefeitura de Luiz
  Alves da fixture): notifica, e grava `elegibilidade='elegivel'` com motivo `sul`.
- `test_federal_notifica_mesmo_abaixo_do_corte` — MS, "UFMS - Fundacao Universidade Federal...", teto
  5215.39: notifica, motivo `federal`.
- `test_estrelado_notifica_mesmo_filtravel` — registro com `estado_usuario='seguindo'` e item que seria
  filtrado: notifica, motivo `seguindo`.
- `test_ignorado_continua_saindo_antes_do_filtro` — registro com `estado_usuario='ignorado'`: devolve `skip`,
  o banco **nao** e tocado, e `decidir` nao e chamado.
- `test_item_do_gran_nao_e_avaliado` — item do Gran sem `regiao`: notifica, sem selo, e a gravacao passa
  `elegibilidade=None`.
- `test_item_da_pagina_de_cargo_nao_e_avaliado` — idem para `fonte='pci'`.
- `test_filtrado_que_passa_a_entrar_sai_como_novo` — registro existente com `elegibilidade='filtrado'` e
  decisao `entra`: a mensagem enviada e a de **novo concurso**, nao a de atualizacao.
- `test_elegivel_que_passa_a_filtrado_nao_renotifica` — registro `elegivel` que agora filtra: nenhuma
  mensagem, e o banco recebe `elegibilidade='filtrado'`.
- `test_selo_aparece_no_card` — item com `uf` e `regiao` nulos: a mensagem enviada contem o selo.
- `test_sem_selo_nao_poe_linha_extra` — item com motivo `acima_do_corte`: a mensagem **nao** contem `⚠️`.
- `test_area_com_filtro_desligado_nao_filtra_nada` — mesma bateria de itens com `filtro_salarial` ausente:
  todos notificam e nenhum selo aparece.
- `test_resumo_semanal_sai_uma_vez_na_semana` — duas rodadas no mesmo dia: o resumo e enviado na primeira e
  nao na segunda.
- `test_resumo_semanal_volta_na_semana_seguinte` — com o marcador da semana anterior no lugar, a rodada manda
  de novo.
- `test_semana_sem_filtrados_nao_manda_nem_marca` — `listar_filtrados` devolvendo vazio: nenhuma mensagem e o
  marcador **nao** e criado.
- `test_resumo_desligado_nao_consulta_o_banco` — `resumo_filtrados` ausente: `listar_filtrados` nao e chamada.
- `test_dry_run_nao_manda_resumo_nem_marca` — em `--dry-run`, nada enviado e nenhum marcador.
- `test_falha_no_resumo_nao_derruba_a_rodada` — `montar` levantando: a rodada termina, o erro e logado, e
  `bot.falhou` **nao** e marcado por isso.

## Fora do escopo

- Mudar a decisao de elegibilidade. As nove regras estao fechadas no modulo puro; se parecer que falta uma,
  volte com `BLOQUEADO`.
- Avaliar item do Gran, da pagina de cargo ou da lista nacional. R-15 e deliberado.
- Mexer em `src/core/elegibilidade.py`, `src/utils/salario.py`, `src/utils/esfera.py`,
  `src/core/resumo_filtrados.py`, `src/database/manager.py`, `config/loader.py` ou
  `src/scrapers/pci_mcp_scraper.py`. Todos chegam prontos e integrados.
- Modo sombra, backfill de linha antiga, reavaliar o que ja foi notificado.
- Alterar o alerta de fonte parada, o heartbeat diario ou a primeira carga.

## Notas do arquiteto

- **G− porque aqui o erro e silencio.** Nenhum teste fica vermelho quando um concurso deixa de ser enviado por
  engano. As quatro regras de borda (`ignorado` antes do filtro, estrela acima de tudo, filtrado que volta
  saindo como novo, porta sem `regiao` nao avaliada) sao as que mais facilmente se implementam ao contrario, e
  cada uma tem teste nominal no plano.
- **A ordem dentro de `_decidir_e_notificar` e parte do aceite:** `ignorado` sai primeiro (nem banco toca),
  depois a elegibilidade, depois a matriz de hoje. Trocar a ordem faz um concurso que o Lucas marcou com `x`
  voltar a ser avaliado e gravado, o que e justamente o que o `ignorado` existe para evitar.
- **R-12 e a regra que exige cuidado no codigo que ja existe.** A matriz de hoje decide "novo" por `registro
  is None`. Uma linha gravada como `filtrado` **existe** no banco, entao sem tratamento ela sairia como
  atualizacao ou como refresh silencioso, e o Lucas nunca veria o concurso. A condicao de inedito passa a ser
  "nao ha registro **ou** o registro estava filtrado".
- O resumo semanal precisa de uma data de corte para `listar_filtrados`. Use 7 dias antes de hoje, no formato
  `AAAA-MM-DD HH:MM:SS`, que e o que a coluna guarda.
- **Marcador separado do `_alerta_uma_vez_por_dia`.** Aquele e diario e por tipo; este e semanal. Nao mude o
  helper existente para aceitar periodo: um helper com dois regimes e mais facil de errar do que dois helpers.
  Se preferir generalizar, mantenha o comportamento diario identico e prove com os testes que ja existem.
- A `Politica` se monta uma vez no `__init__`, nao a cada item: ela e imutavel e vem da config.
- **Porta de mao unica: nao.** Este ticket nao apaga nem transforma dado: ele acrescenta decisao em coluna
  nova. O que ele muda e o que o Lucas **recebe**, e e por isso que o resumo semanal entra junto, no mesmo
  ticket: o silencio nasce auditavel.
