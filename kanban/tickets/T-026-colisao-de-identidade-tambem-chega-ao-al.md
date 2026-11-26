---
id: T-026
titulo: Colisao de identidade tambem chega ao alerta do dia
tipo: codigo
nivel: M-
status: backlog
repo: principal
spec: [SPEC-003, R-97]
depende_de: [T-020]
toca: [src/database/manager.py, src/core/bot.py, tests/test_database_manager.py, tests/test_concurso_bot.py]
recursos: []
afinidade:
retornos: 0
---
# T-026 · Colisao de identidade tambem chega ao alerta do dia

## Contexto

A SPEC-003 R-86 pedia que colisao de identidade que o codigo nao resolve entrasse **no log e no alerta do
dia**. O T-020 entregou o log: o `except sqlite3.IntegrityError` de `atualizar_concurso`, em
`src/database/manager.py`, registra `COLISAO DE IDENTIDADE nao resolvida na area ...` e devolve `0`. O alerta
nao foi entregue, porque o `toca` do T-020 nao inclui o `src/core/bot.py`. O revisor do T-020 apontou isso e
devolveu a decisao de escopo; o dono respondeu «Ticket separado» em 25/11/2026, e o requisito foi partido em
R-86 (log) e R-97 (alerta), registrado na SPEC-003 secao 4 item 5.

O problema concreto que isso deixa aberto: o bot recebe `0` do banco e **nao distingue** colisao de identidade
de falha generica de escrita. As duas chegam como «nao gravou». Enquanto for assim, uma colisao fica so no log
do servidor, que o Lucas nao le todo dia, e a linha afetada passa a rodada inteira sem atualizacao sem que
ninguem saiba. Isso contraria a regra de fail-open do projeto, que e: erro nunca vira silencio.

## Critério de aceite

- [ ] Quando uma rodada tem ao menos uma colisao de identidade nao resolvida, o alerta de fim de rodada
      daquela area nomeia a causa, diz **quantas** linhas colidiram e identifica ate 5 delas por `area`,
      `nome` e `pci_id`, e diz que esses concursos nao foram gravados nesta rodada.
- [ ] O alerta sai **uma vez por dia**, pelo mesmo `_alerta_uma_vez_por_dia` que os outros usam.
- [ ] O alerta e **por area** (`por_area=True`), nao global: a colisao e um dado daquela area, e quem for
      agir precisa saber qual. Isso difere de proposito do alerta de cota do T-021, que e global porque a
      cota e compartilhada pelas tres areas.
- [ ] Rodada sem colisao nao manda alerta nenhum, e nao muda o texto nem a ordem dos alertas que ja existem.
- [ ] Falha generica de escrita no banco (`sqlite3.Error` que nao e de unicidade) **nao** dispara este
      alerta: e outra causa, e confundir as duas esconde problema de disco atras de problema de dado.
- [ ] O sinal de colisao zera no comeco de cada rodada: nada vaza de uma rodada para a seguinte.
- [ ] A linha de log do R-86 continua exatamente como o T-020 a entregou. O alerta e adicional, nao
      substituto.

## Plano de testes

Costura: a mesma de que o T-021 usou para o alerta de cota, a entrada de rodada do `ConcursoBot`, mais a
interface publica `DatabaseManager.atualizar_concurso` para produzir a colisao.
Pega: que uma colisao na rodada chega ao alerta, com o texto certo, uma vez por dia, na area certa.
Nao pega: se a regra de identidade esta correta. Isso e do T-020 e ja tem teste la. Aqui a colisao e
fabricada de proposito.
Oráculo: literais escritos a mao. A contagem vem do fixture, contada a mao, nunca lida do mesmo codigo que
a produz.

- `test_colisao_de_identidade_entra_no_alerta_do_dia`: uma rodada com uma colisao fabricada manda alerta, e
  o texto nomeia a causa.
- `test_alerta_de_colisao_nomeia_area_e_concurso`: o alerta traz `area`, `nome` e `pci_id` da linha afetada.
- `test_alerta_de_colisao_conta_e_corta_em_cinco`: com sete colisoes, o alerta diz sete e nomeia cinco.
- `test_rodada_sem_colisao_nao_alerta`: nenhuma colisao, nenhum alerta novo, e os alertas existentes intactos.
- `test_alerta_de_colisao_sai_uma_vez_por_dia`: duas rodadas no mesmo dia, um alerta so.
- `test_erro_generico_do_banco_nao_vira_alerta_de_colisao`: `sqlite3.Error` simulado que nao e de unicidade
  nao produz este alerta.
- `test_contador_de_colisao_zera_entre_rodadas`: rodada com colisao seguida de rodada limpa nao alerta na
  segunda.

## Fora do escopo

- **Reparar as linhas que ja colidiram.** E o T-023, e exige julgamento sobre qual dado pertence a qual
  edital.
- **Mexer na regra de identidade.** E o T-020. Aqui so se le o resultado dela.
- **O freio de renotificacao.** E o T-024.
- **Mexer no alerta de cota.** O T-021 ja integrou. Nao reaproveite a flag nem o texto dele: causa diferente,
  alerta diferente.

## Notas do arquiteto

Por que M−: a regra e conhecida e o padrao ja existe duas vezes no proprio arquivo, em `falha_autenticacao` e
em `extracao_degradada`. O trabalho e um sinal fino no `manager.py` mais a leitura dele no fim da rodada.

O sinal sugerido, e nao imposto: um acumulador no `DatabaseManager` (uma lista de colisoes da rodada, com
area, nome e pci_id), preenchido no `except sqlite3.IntegrityError` que o T-020 criou, e lido pelo bot no fim
da rodada. Uma lista e nao um booleano porque o alerta precisa nomear as linhas, senao ele avisa de um
problema que o Lucas nao consegue localizar. Se achar costura melhor, proponha no relatorio e justifique.

Dependencia real, nao de arquivo: o caminho da colisao e o log nomeado nascem no T-020. Sem ele integrado,
nao ha o que ler.

Serializacao do `src/core/bot.py`: o T-024 passou a depender deste ticket, para que os dois nao disputem o
arquivo. A cadeia da fase e T-020 → T-026 → T-024 → T-019.

Nao e porta de mao unica e nao tem gate de aprovacao humana: nao transforma dado e nao muda contrato
consumido de fora. Diferente do T-020 nisso.
