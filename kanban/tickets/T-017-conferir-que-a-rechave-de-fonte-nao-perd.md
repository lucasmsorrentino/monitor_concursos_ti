---
id: T-017
titulo: Conferir que a rechave de fonte nao perdeu concurso
tipo: spike
nivel: M-
status: integrado
repo: principal
spec: [SPEC-001]
depende_de: []
toca: [docs/CONTABILIDADE-POS-DEPLOY.md]
recursos: []
afinidade:
retornos: 1
atualizado: 2026-11-25T01:09-03:00
branch: t/T-017-conferir-que-a-rechave-de-fonte-nao-perd
executor: script
executor_impl: agy-neon
corpo_lancado: ec05e442cb94
fora_do_toca: []
ponta: 0f3e7145ebe447e498db2c611cea857725106c13
executor_rev: glm-go
executor_int: script
---
# T-017 · Conferir que a rechave de fonte nao perdeu concurso

## Contexto

No deploy de 24/11/2026 a contabilidade nao fechou de primeira, e esta registrada assim em
`docs/DIAGNOSTICO-POS-DEPLOY.md`: o log do dia soma **61 novos**, enquanto o banco foi de 1629 para 1700
linhas (**+71**), com a fonte `pci_mcp` nascendo com **101** linhas e as portas antigas **perdendo 30**
(`pci` de 1439 para 1411, `pci_nacional` de 9 para 8, `gran` de 181 para 180).

Linha de banco nao se apaga neste sistema. Entao 30 linhas que **existiam** mudaram de fonte: a porta do
MCP encontrou concursos que as portas de HTML ja tinham trazido e reescreveu a chave de fonte deles. A
leitura provavel, escrita como **hipotese** pelo implementador e confirmada como hipotese pelo revisor, e
que os filtrados salvos em silencio mais a rechave explicam a diferenca.

Hipotese nao e resposta, e o que esta em jogo e serio: se a unificacao por `id` casou dois concursos
diferentes como um, o Lucas perdeu um concurso **e nunca vai saber**. E silencio outra vez.

## Critério de aceite

Este e um `spike`: o entregavel e evidencia, nao codigo. Fecha com `docs/CONTABILIDADE-POS-DEPLOY.md`
respondendo, com numero e consulta ao lado de cada resposta:

- [ ] **As 30 linhas que mudaram de fonte sao as mesmas 30 que o MCP trouxe?** Liste-as, por `id`, com a
      fonte de antes e a de agora. Se o numero nao fechar em 30, diga quanto deu e por que.
- [ ] **Nenhuma linha foi perdida:** o total de 1700 se decompoe em 1629 de antes mais os novos do dia,
      sem subtracao. Mostre a conta.
- [ ] **Nenhum casamento errado:** para cada uma das 30 rechaveadas, o nome e o link de antes e o de agora
      descrevem o **mesmo** concurso. Qualquer par duvidoso vai na lista de duvidosos, com os dois nomes
      lado a lado, para o Lucas julgar.
- [ ] **Os 61 do log contra os +71 do banco:** mostre de onde vem a diferenca, com a contagem de filtrados
      salvos em silencio na rodada (56 no dia) e o que mais entrar na conta.
- [ ] **O documento fecha dizendo se a rechave e desejada ou e defeito.** Se for defeito, cada caso vira
      ticket proprio na fase seguinte, com o `id` do concurso.
- [ ] O documento nao contem token, chave nem `chat_id`, e nao cita `T-0NNN`.

## Plano de testes

Costura: a producao, pelo banco `~/monitor_concursos_ti/data/concursos.db` no notebook, **somente
leitura**. Nao ha teste automatizado: a verificacao e a evidencia, como manda o plano de spike.

Oráculo: os dois diagnosticos de 24/11/2026 guardados no notebook
(`~/diagnostico-monitor-antes-2026-11-24.txt` e `~/diagnostico-monitor-depois-2026-11-24.txt`) e o log
`logs/run_20261124.log`. Sao a unica referencia honesta do «antes», e ja estao colados nas notas do
ticket do deploy.

A pergunta a responder, em uma frase: **a porta do MCP reescreveu a fonte de 30 concursos que ja
existiam, e esses 30 sao de fato os mesmos concursos?**

Evidencia que fecha: a lista das 30 linhas com `id`, nome, link, fonte antiga e fonte nova, tirada do
banco por consulta, mais a conta de 1629 para 1700.

## Fora do escopo

- **Escrever no banco.** Nada de `UPDATE`, `DELETE`, migracao ou conserto. Se achar defeito, descreva;
  consertar e outro ticket, depois que o Lucas decidir.
- Mudar codigo. Nenhum arquivo de `src/` entra no `toca`.
- Resolver o fuso do banco (UTC) contra o do log (hora local). Isso e o ticket do ADR, e aqui so importa
  para ler os horarios certo: a rodada que o log marca as 12:49:58 aparece no banco como 15:49:58.

## Notas do arquiteto

- **`spike` e nao `codigo` porque nao se sabe a resposta.** Se o ticket fosse de codigo, o implementador
  seria empurrado a consertar algo antes de entender o que aconteceu.
- **M− pelo julgamento, nao pelo volume.** Rodar as consultas e facil; decidir se dois nomes descrevem o
  mesmo concurso nao e, e e por isso que o duvidoso vai para o Lucas em vez de ser resolvido no chute.
- **Acesso ao notebook:** `ssh -i ~/.ssh/fleet_ed25519 lucas@100.98.50.59`, pela Tailscale, a partir do
  desktop. A chave padrao `id_ed25519` nao e aceita. O banco de producao fica em
  `~/monitor_concursos_ti/data/concursos.db`. Abra com `sqlite3` em modo leitura
  (`file:...?mode=ro`) para nao haver chance de escrita acidental; o cron roda de hora em hora, no minuto
  20, e o `run_daily.sh` tem `flock`, mas o seu `sqlite3` nao passa por ele.
- Nao e preciso parar o cron. Se o retrato se mover entre consultas, diga em que momento cada numero foi
  medido: o documento relata, nao precisa congelar o mundo.

## Histórico
- 2026-11-24 23:43 backlog → pronto · liberado: OK do Lucas no chat, 24/11/2026: libera a onda 0
- 2026-11-24 23:54 pronto → fazendo · implementador · agy-neon M- medium
- 2026-11-25 00:05 fazendo → pronto · laço: sem cota em antigravity, espera
- 2026-11-25 00:28 pronto → fazendo · implementador · glm-go M-
- 2026-11-25 00:48 fazendo → entregue · implementador: ENTREGUE · relatório T-017-implementador-1.md · 20 min
- 2026-11-25 00:48 entregue → revisando · revisor · agy-neon M+ high
- 2026-11-25 00:56 revisando → pronto · revisor: REPROVADO · relatório T-017-revisor-1.md · 8 min
- 2026-11-25 00:56 pronto → fazendo · implementador · agy-neon M- medium
- 2026-11-25 01:00 fazendo → entregue · implementador: ENTREGUE · relatório T-017-implementador-2.md · 5 min
- 2026-11-25 01:00 entregue → revisando · revisor · glm-go M+ high
- 2026-11-25 01:05 revisando → aprovado · revisor: APROVADO · relatório T-017-revisor-2.md · 5 min
- 2026-11-25 01:09 aprovado → integrando · integrador · script
- 2026-11-25 01:09 integrando → integrado · integrador: INTEGRADO · relatório T-017-integrador-1.md · 0 min
