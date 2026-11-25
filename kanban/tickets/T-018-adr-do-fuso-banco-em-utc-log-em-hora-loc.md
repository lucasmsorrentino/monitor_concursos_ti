---
id: T-018
titulo: ADR do fuso: banco em UTC, log em hora local
tipo: docs
nivel: P-
status: integrado
repo: principal
spec: [SPEC-001, R-20, R-22]
depende_de: []
toca: [docs/adr/0004-fuso-do-banco-e-do-log.md]
recursos: []
afinidade:
retornos: 0
atualizado: 2026-11-25T01:09-03:00
branch: t/T-018-adr-do-fuso-banco-em-utc-log-em-hora-loc
executor: script
executor_impl: agy-hydrogen
corpo_lancado: 1583ce1e6a57
fora_do_toca: []
ponta: f839804a6b258d9cabf19a23267206f7a46a863b
executor_rev: glm-go
executor_int: script
---
# T-018 · ADR do fuso: banco em UTC, log em hora local

## Contexto

Os horarios do sistema nao batem entre si, e isso apareceu na comparacao do deploy
(`docs/DIAGNOSTICO-POS-DEPLOY.md`): a rodada que o log marca as **12:49:58** aparece no banco, na coluna
`ultima_atualizacao`, como **15:49:58**; a das **00:32** local aparece como **03:32**. A diferenca de tres
horas e exatamente o deslocamento de Curitiba para UTC.

O comportamento e consistente e tem explicacao: o `CURRENT_TIMESTAMP` do SQLite grava em UTC e o
formatador de log usa a hora local da maquina. Nao e defeito, e provavelmente ja foi escolha de alguem.
Mas nao esta escrito em lugar nenhum, e ja custou tempo uma vez: o corte de sete dias do resumo semanal
teve de ser calculado em UTC **por causa disso**, e quem escreveu aquele codigo precisou descobrir sozinho.

A decisao vale uma ADR, nao um conserto. Enquanto nao estiver escrita, a proxima pessoa (ou o proximo
agente) vai comparar as duas colunas de novo e achar que uma delas esta errada.

## Critério de aceite

- [ ] Nasce `docs/adr/0004-fuso-do-banco-e-do-log.md`, no formato das ADRs que ja existem em `docs/adr/`.
- [ ] A ADR responde, com o arquivo e o nome da funcao ou coluna ao lado de cada afirmacao: **quem grava
      em UTC** (as colunas de data do banco e qual mecanismo), **quem grava em hora local** (o log e qual
      formatador) e **quem le qual**.
- [ ] Registra a consequencia concreta que ja existe no codigo: o corte de sete dias do resumo semanal se
      calcula em UTC porque a coluna esta em UTC, enquanto o dia da semana do marcador usa a data local.
      Essa assimetria e proposital e a ADR tem de dizer isso.
- [ ] Diz o que fazer daqui para frente, em uma regra curta: data nova que vai ao banco usa UTC, texto que
      vai ao Lucas usa hora local, e comparacao entre os dois converte antes.
- [ ] Diz **o que nao se vai fazer**: nao ha migracao de dado, nao se reescreve coluna antiga, e o log
      continua em hora local porque quem le o log e humano.
- [ ] A ADR nao contem token, chave nem `chat_id`, e nao cita `T-0NNN`.

## Plano de testes

Costura: nenhuma. Ticket de documentacao, sem fatia de codigo, entao nao ha teste novo.

Oráculo: o proprio codigo. Cada afirmacao da ADR se confere lendo o arquivo citado:
`src/utils/logger.py` para o formato do log, `src/database/manager.py` para as colunas de data e
`src/core/bot.py` para o corte do resumo semanal e o marcador da semana.

Verificacao, em vez de teste:

- `grep -rn "CURRENT_TIMESTAMP" src/database/manager.py` acha o mecanismo que a ADR descreve;
- `grep -rn "timezone.utc\|date.today()" src/core/bot.py` acha as duas pontas da assimetria;
- `grep -rn "T-0" docs/adr/0004-fuso-do-banco-e-do-log.md` nao devolve nada.

## Fora do escopo

- **Mudar qualquer horario.** Nem no banco, nem no log, nem no codigo. Se a leitura do codigo sugerir que
  a escolha de hoje e errada, escreva isso na secao de consequencias da ADR e pare: mudar fuso em sistema
  com 1700 linhas gravadas e outro ticket, e e decisao do Lucas.
- Migrar coluna, normalizar dado antigo ou acrescentar coluna de fuso.
- Tocar no `FormatterSemSegredos`.

## Notas do arquiteto

- **P− porque o trabalho e ler tres arquivos e escrever uma pagina**, com o formato das outras tres ADRs
  ao lado para copiar.
- Essa e a saida mais barata para o achado: a alternativa seria um ticket de conserto que mexe em data em
  producao, e nao ha sintoma que justifique isso. Escrever a decisao impede a redescoberta, que foi o
  custo real.

## Histórico
- 2026-11-24 23:43 backlog → pronto · liberado: OK do Lucas no chat, 24/11/2026: libera a onda 0
- 2026-11-24 23:58 pronto → fazendo · implementador · agy-hydrogen P- medium
- 2026-11-25 00:01 fazendo → entregue · implementador: ENTREGUE · relatório T-018-implementador-1.md · 4 min
- 2026-11-25 00:22 entregue → revisando · revisor · glm-go M-
- 2026-11-25 00:28 revisando → aprovado · revisor: APROVADO · relatório T-018-revisor-1.md · 7 min
- 2026-11-25 01:09 aprovado → integrando · integrador · script
- 2026-11-25 01:09 integrando → integrado · integrador: INTEGRADO · relatório T-018-integrador-1.md · 0 min
