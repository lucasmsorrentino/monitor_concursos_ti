---
id: T-007
titulo: Texto do resumo semanal de filtrados
tipo: codigo
nivel: M-
status: integrado
repo: principal
spec: [SPEC-001, R-20]
depende_de: []
toca: [src/core/resumo_filtrados.py, tests/test_resumo_filtrados.py]
recursos: []
afinidade:
retornos: 0
atualizado: 2026-11-23T18:10-03:00
branch: t/T-007-texto-do-resumo-semanal-de-filtrados
executor: script
executor_impl: glm
corpo_lancado: 5349b45cba28
fora_do_toca: []
ponta: 8314869b481c9bac06ed5439cf066dfa05af69ae
executor_rev: agy-argon
executor_int: script
---
# T-007 · Texto do resumo semanal de filtrados

## Contexto

O filtro de elegibilidade entra cortando de verdade na primeira rodada, e o que garante que o corte seja
**auditavel** e um resumo semanal: uma vez por semana, por area, uma mensagem com a contagem por motivo e a
lista do que foi silenciado. Decisao do dono em 22/11/2026, e e o que permite ajustar o corte depois com dados
em vez de palpite (SPEC-001 secao 8).

Este ticket entrega so a montagem do **texto** e o controle de "uma vez por semana", numa funcao pura sobre
uma lista de linhas. Nao le banco, nao manda Telegram, nao e chamado por ninguem ainda.

As regras estao na SPEC-001 secao 4.4.

## Critério de aceite

- [ ] `src/core/resumo_filtrados.py` expoe
      `montar(linhas: list[dict], area_nome: str, limite: int = 30) -> str | None`.
- [ ] **Semana sem nada filtrado nao manda mensagem** (R-21): lista vazia devolve `None`.
- [ ] A mensagem traz, nesta ordem: um titulo com o nome da area; a **contagem total**; a **contagem por
      motivo**, em ordem decrescente de contagem; e a lista das linhas.
- [ ] Cada linha da lista traz o nome do orgao, a UF, o teto formatado em reais brasileiros
      (`R$ 8.628,87`) e o motivo. Teto `None` sai como `teto nao lido`, nunca `None` nem `R$ 0,00`.
- [ ] UF `None` sai como `Nacional`.
- [ ] O motivo aparece em portugues legivel, nao com o identificador cru: `abaixo_do_corte` vira
      "abaixo do corte" e `municipal_inflado` vira "teto de outro cargo". O mapa de rotulos e uma constante do
      modulo, e motivo desconhecido cai no proprio identificador em vez de levantar.
- [ ] Acima de `limite` linhas, lista as `limite` primeiras e fecha com uma linha "e mais N". A contagem do
      topo continua sendo a **total**, nao a listada.
- [ ] A saida e HTML do Telegram no estilo que `src/core/bot.py` ja usa (`<b>`, `\n`), e **todo texto que vem
      das linhas passa por `html.escape`**: nome de orgao com `&` ou `<` nao pode quebrar a mensagem.
- [ ] `src/core/resumo_filtrados.py` expoe tambem
      `marcador_da_semana(hoje: date) -> str`, que devolve a chave da semana ISO (`"2026-S47"`), usada pelo
      controle de "uma vez por semana".
- [ ] `marcador_da_semana` usa semana ISO: 2026-12-28 (segunda da semana 53 ISO de 2026) e 2027-01-03
      (domingo da mesma semana) devolvem a **mesma** chave. E o teste que impede o bug de virada de ano.
- [ ] Modulo puro: sem `sqlite3`, sem `requests`, sem importar `src/core/bot.py` nem
      `src/database/`.

## Plano de testes

Costura: `resumo_filtrados.montar` e `resumo_filtrados.marcador_da_semana`, as duas funcoes publicas do
modulo. Pegam o texto, as contagens, o corte da lista, o escape e a chave de semana. **Nao pegam** de onde as
linhas vieram nem quando a mensagem e enviada.

Oráculo: listas de linhas escritas a mao no teste, e o texto esperado conferido por afirmacoes sobre
substring e contagem (nao por comparacao com um blob inteiro, que quebraria a cada ajuste de formatacao).
Para `marcador_da_semana`, os pares de data vem do calendario ISO, calculado a mao e escrito no teste.

Testes que nascem vermelhos em `tests/test_resumo_filtrados.py`:

- `test_lista_vazia_devolve_none` — `montar([], "TI")` devolve `None`.
- `test_traz_contagem_total` — com 5 linhas, a mensagem contem "5".
- `test_traz_contagem_por_motivo_em_ordem_decrescente` — 3 `abaixo_do_corte` e 1 `municipal_inflado`: o
  rotulo do primeiro aparece **antes** do segundo no texto.
- `test_linha_traz_orgao_uf_teto_e_motivo` — linha de Prefeitura de Canto do Buriti, PI, teto 16210.0,
  `municipal_inflado`: a mensagem contem o nome, "PI", "R$ 16.210,00" e "teto de outro cargo".
- `test_teto_none_sai_como_nao_lido` — linha com `salario_teto=None` contem "teto nao lido" e **nao** contem
  "R$ 0,00" nem "None".
- `test_uf_none_sai_como_nacional` — linha com `uf=None` contem "Nacional".
- `test_motivo_desconhecido_nao_levanta` — linha com `motivo_filtro="motivo_que_ninguem_previu"` monta e o
  texto contem o identificador cru.
- `test_formata_teto_no_padrao_brasileiro` — 8628.87 sai "R$ 8.628,87" e 1000000.0 sai "R$ 1.000.000,00".
- `test_corta_em_trinta_e_diz_quantas_faltam` — 42 linhas: o texto tem 30 linhas de item, contem "e mais 12",
  e a contagem do topo continua "42".
- `test_limite_customizado` — `limite=2` com 5 linhas lista 2 e diz "e mais 3".
- `test_escapa_html_do_nome` — nome `"Prefeitura de A & B <teste>"` sai escapado, e o texto nao contem
  `"<teste>"` cru.
- `test_nome_da_area_aparece` — `montar(linhas, "Tecnologia da Informacao")` contem a string da area.
- `test_marcador_da_semana_e_estavel_na_mesma_semana` — 2026-11-23 (segunda) e 2026-11-29 (domingo) devolvem
  a mesma chave.
- `test_marcador_da_semana_muda_na_semana_seguinte` — 2026-11-29 e 2026-11-30 devolvem chaves diferentes.
- `test_marcador_da_semana_na_virada_do_ano` — 2026-12-28 e 2027-01-03 devolvem a mesma chave.

## Fora do escopo

- Consultar o banco. `listar_filtrados` e de outro ticket, e esta funcao recebe as linhas prontas.
- Mandar a mensagem, gravar o marcador em arquivo ou decidir que dia da semana e. Isso e da fiacao no bot.
- Resumo de outra coisa que nao filtrados (heartbeat, fonte parada). Ja existem no bot.
- Grafico, anexo ou CSV. E uma mensagem de Telegram.

## Notas do arquiteto

- **M− e nao P:** e montagem de texto, mas tem seis casos de borda que mudam a saida (vazio, teto nulo, UF
  nula, motivo desconhecido, corte com "e mais N", escape) e um de calendario (semana ISO na virada do ano).
  O padrao de montar mensagem HTML ja esta em `src/core/bot.py`, entao nao chega a `+`.
- **Afirme por substring, nao por blob.** Teste que compara a mensagem inteira com um literal quebra a cada
  ajuste de espaco e nao prova nada sobre comportamento. O aceite esta escrito em termos de "o texto contem".
- A semana ISO sai de `date.isocalendar()`, que devolve `(ano_iso, semana, dia)`. Use o **ano ISO**, nao
  `date.year`: e exatamente ai que mora o bug de virada de ano que o aceite cobra. 2027-01-03 e domingo da
  semana 53 do ano ISO 2026.
- A formatacao de real em padrao brasileiro nao sai de `locale` (depende do sistema e o notebook e Linux, a
  maquina de desenvolvimento e Windows). Faca a troca de separador a mao a partir de
  `f"{valor:,.2f}"`, que e deterministico.
- Os rotulos de motivo que o resumo precisa cobrir sao os dois que filtram: `abaixo_do_corte` e
  `municipal_inflado`. Os outros sete motivos nunca aparecem aqui, porque todos entram. Ainda assim trate
  motivo desconhecido sem levantar: e um resumo, nao um validador.

## Histórico
- 2026-11-23 11:16 backlog → pronto · liberado: OK do Lucas em 23/11/2026
- 2026-11-23 11:28 pronto → fazendo · implementador · glm M-
- 2026-11-23 11:38 fazendo → entregue · implementador: ENTREGUE · relatório T-007-implementador-1.md · 10 min
- 2026-11-23 18:03 entregue → revisando · revisor · agy-argon M+ high
- 2026-11-23 18:10 revisando → aprovado · revisor: APROVADO · relatório T-007-revisor-1.md · 7 min
- 2026-11-23 18:10 aprovado → integrando · integrador · script
- 2026-11-23 18:10 integrando → integrado · integrador: INTEGRADO · relatório T-007-integrador-1.md · 0 min
