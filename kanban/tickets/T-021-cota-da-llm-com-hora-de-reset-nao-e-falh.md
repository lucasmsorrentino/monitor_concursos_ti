---
id: T-021
titulo: Cota da LLM com hora de reset nao e falha generica
tipo: codigo
nivel: M-
status: integrado
repo: principal
spec: [SPEC-003, R-87, R-88]
depende_de: []
toca: [src/intelligence/langchain_unit.py, src/core/bot.py, tests/test_intelligence_unit.py, tests/test_concurso_bot.py]
recursos: []
afinidade:
retornos: 0
atualizado: 2026-11-25T17:13-03:00
branch: t/T-021-cota-da-llm-com-hora-de-reset-nao-e-falh
executor: script
executor_impl: sonnet
corpo_lancado: 9c1e6f3950f7
sessao: e3abf92d-d6de-4803-9761-87a907c4b9a0
fora_do_toca: [CLAUDE.md, README.md]
ponta: 12362ca36c84d488ba2c2af7b7670a28c84963cb
executor_rev: agy-neon
executor_int: script
---
# T-021 · Cota da LLM com hora de reset nao e falha generica

## Contexto

Em 25/11/2026 a cota semanal da LLM esgotou as 00:20:11 e o provedor devolveu `RateLimitError` **com o
instante de volta na mensagem**. O `_e_falha_de_credencial` em `src/intelligence/langchain_unit.py` ja trata
a familia «causa que retry nao conserta» (login vencido, chave invalida, saldo zerado), curto-circuitando as
chamadas seguintes da rodada e nomeando a causa no alerta. `RateLimitError` nao esta nessa lista, entao a
cota esgotada gastou tres tentativas por item em cada uma das 13 varreduras do dia: 4.643 mensagens de falha
no log, e o Lucas recebeu o alerta generico de «varredura incompleta» sem saber que a causa era cota.

Essa e a mesma licenca que o repo ja aprendeu em 14/10/2026, quando o OAuth expirado rendeu 24 avisos
genericos por dia sem pista do motivo. O conserto de entao nomeou **uma** causa; esta e a segunda.

## Critério de aceite
- [ ] Erro de cota que traz instante de reset curto-circuita o resto da rodada na primeira ocorrencia, do
      mesmo jeito que a falha de credencial ja faz (R-87)
- [ ] O instante de reset e extraido da mensagem e fica legivel por quem chama
- [ ] Erro de cota **sem** instante de reset legivel continua no caminho de hoje, com as tres tentativas,
      porque ali o retry ainda pode resolver (fail-open)
- [ ] O alerta nomeia a causa e a hora de volta, em vez do generico «varredura incompleta», uma vez por dia
      (R-88)
- [ ] A area continua marcada como `falhou`: o catch-up segue desejado, e quem o suspende e outro ticket
- [ ] Suite verde; nenhum teste existente afrouxado

## Plano de testes
Costura: o metodo publico da `IntelligenceUnit` que faz o laco de tentativas, para o curto-circuito; e
`ConcursoBot.executar()` com o notificador dublado, para o alerta. Pega: a contagem de tentativas, o atributo
de causa e o texto do alerta. Nao pega: a chamada HTTP de verdade, que nunca entra na suite.
Oráculo: a mensagem real do provedor, copiada do log de producao de 25/11:
`litellm.RateLimitError: RateLimitError: ZaiException - Weekly/Monthly Limit Exhausted. Your limit will reset
at 2026-11-26 08:11:28`.

Testes que nascem vermelhos:

- `test_cota_esgotada_com_reset_nao_tenta_tres_vezes`
- `test_cota_esgotada_curto_circuita_as_chamadas_seguintes_da_rodada`
- `test_cota_esgotada_expoe_o_instante_de_reset`
- `test_cota_sem_instante_de_reset_mantem_as_tres_tentativas`
- `test_alerta_de_cota_nomeia_a_causa_e_a_hora_de_volta`
- `test_alerta_de_cota_sai_uma_vez_por_dia`

## Fora do escopo
- Suspender o catch-up horario. E outro ticket, que depende deste.
- Trocar o backend de LLM, ou qualquer politica de provedor: decisao de operacao, nao de codigo.
- Mexer no `LIMITE_ERRO_EXTRACAO` ou na regra dos 20%.

## Notas do arquiteto

**Por que M−:** regra conhecida, um modulo, e o padrao ja existe no mesmo arquivo (`_e_falha_de_credencial`,
`falha_autenticacao`, `instrucao_login`). Copie a forma que esta la, nao invente outra.

**Cota nao e credencial.** Nao reuse o `falha_autenticacao` nem o alerta `llm_sem_login`: o conserto e
diferente (esperar, nao relogar), e juntar os dois devolve o problema de 14/10, que era alerta que nao nomeia
a causa. Atributo proprio e chave de alerta propria.

O parse do instante deve ser tolerante: a mensagem vem do provedor e pode mudar de forma sem aviso. Sem
instante legivel, caia no caminho de hoje. **Nunca levante excecao a partir do parse.**

**O fuso do instante nao vem declarado pelo provedor.** Nao tente adivinhar aqui: devolva o que a mensagem
diz e deixe a decisao de fuso para quem usa o valor, que a trata como advisory.

## Histórico
- 2026-11-25 16:48 backlog → pronto · liberado: Lucas liberou no chat em 25/11/2026
- 2026-11-25 16:49 pronto → fazendo · implementador · sonnet M-
- 2026-11-25 17:02 fazendo → entregue · implementador: ENTREGUE · relatório T-021-implementador-1.md · 13 min · fora do toca: 2 arquivo(s)
- 2026-11-25 17:02 entregue → revisando · revisor · agy-neon M+ high
- 2026-11-25 17:11 revisando → aprovado · revisor: APROVADO · relatório T-021-revisor-1.md · 10 min
- 2026-11-25 17:11 aprovado → integrando · integrador · script
- 2026-11-25 17:13 integrando → integrado · integrador: INTEGRADO · relatório T-021-integrador-1.md · 2 min
