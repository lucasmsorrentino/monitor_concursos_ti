# ADR-0003 — Sonda barata separada do conserto, e conserto com gate em vez de deploy automatico

**Data:** 23/11/2026
**Estado:** proposta ao dono
**Supera:** o `PLANO_EVOLUCAO_AGENTICA.md` secao 7 (autocorrecao de seletores) em parte: o criterio de
entrada de la continua valendo para `browser-use` e Playwright, que seguem fora.

## Contexto

O pedido e um cron barato, amostral, que conserte o codigo sozinho. Antes de desenhar isso, a historia do
projeto foi medida. Em cinco meses, oito incidentes:

| Quando | O que | Classe | Patch automatico resolveria? |
| :--- | :--- | :--- | :--- |
| 01/07 a 08/08/2026 | nove dias sem nenhuma rodada, notebook desligado as 03h | agendamento | nao |
| 16/07 a 08/08/2026 | `exit=127` todo dia, venv quebrada, em silencio | ambiente | em parte (venv se reconstroi) |
| 12/06 a 22/10/2026 | artigo curado do Gran congelado, 132 dias | fonte parada | nao |
| 06/07 a 06/08/2026 | Dataprev aberta e fora de todas as portas | cobertura | nao |
| 24/09, 03/10, 14/10/2026 | login OAuth do `claude` expirado | credencial | nao |
| 25/09 a 02/10/2026 | notebook sem DNS | rede | nao |
| 22/10/2026 | chave z.ai sem saldo (erro 1113) | credencial | nao |
| sem data | `/cursos/carreira/` passou a exigir JS | contrato | decisao de produto, nao patch |
| — | seletor quebrado | — | **zero ocorrencias** |

**Nenhum** dos oito teria sido consertado por um agente editando codigo. Um (a venv) teria sido consertado por
um agente editando o **ambiente**. Todos os outros pedem chave, rede, maquina ligada ou uma decisao de
cobertura, e nenhum deles e trabalho de agente.

Duas coisas mudam esse quadro para frente, e as duas sao novas:

1. a SPEC-001 faz de um **contrato JSON externo** (o servidor MCP do PCI) a unica porta do PCI. Campo que o
   PCI renomeie quebra o mapeamento, e essa e a primeira classe de falha do projeto que um patch conserta de
   verdade, porque a prova cabe numa fixture;
2. a propria esteira passa a mexer no parser com agente. Regressao nossa, com a fonte intacta, tambem se
   conserta com prova.

## Decisao

1. **A sonda e barata e nao tem LLM.** Uma noite de sonda e uma chamada ao MCP, um punhado de HEAD, um ping de
   20 tokens por provedor de LLM e a suite marcada `contrato`. A amostragem e dupla: uma porta profunda por
   noite, em rodizio, e poucos itens por porta. Custo constante, medido em segundos.
2. **Ver e consertar sao modulos separados, e a sonda nunca depende da peca que mais quebra.** A credencial da
   LLM caiu quatro vezes em cinco meses. Uma sonda que precisasse dela morreria junto com o que deveria
   vigiar. Sem LLM na camada que ve, a sonda continua avisando mesmo quando tudo o mais esta fora do ar.
3. **A sonda de ambiente roda na producao; a sonda de contrato roda onde os agentes vivem.** As fontes sao
   publicas e respondem igual de qualquer maquina, entao conferir contrato nao precisa do notebook. Ambiente,
   cron, banco e credencial so existem no notebook. Sao duas sondas, com dois cron de madrugada escalonados.
4. **O conserto automatico vale para duas classes, e so.** `contrato` (campo que a fonte mudou) e `regressao`
   (suite vermelha com a fonte intacta). As outras sete classes viram alerta com diagnostico, porque nao ha o
   que consertar em codigo.
5. **O teste do conserto nasce da sonda, nunca do agente.** A sonda grava a resposta crua como fixture e
   escreve o teste vermelho a partir do contrato declarado. O agente recebe o vermelho e nao pode tocar
   `tests/`. E o que faz o verde valer alguma coisa: o gate fraco da v1 ("N > 0 registros") aprovava o seletor
   `a`.
6. **O conserto entrega branch com gate, nao deploy.** Nove condicoes, todas automaticas. Producao continua
   entrando por `git pull`, que hoje ja e passo do dono.

## Alternativas recusadas

- **Agente de autocorrecao de seletores com `browser-use` e Playwright** (plano antigo, secao 7). Continua
  fora, pelo mesmo motivo de 22/10: Chromium headless mais dependencia nova num notebook, para cobrir uma
  classe de falha com zero ocorrencias. O criterio de entrada de la nao mudou.
- **Sonda que repete a rodada inteira.** Ler todas as portas e todos os itens toda noite custaria uma rodada
  inteira por dia e, no Gran, 45 chamadas de LLM de 15 s. Amostragem com piso declarado por campo pega a
  mesma queda por uma fracao do custo.
- **Conserto que mescla em `main` e deixa a producao puxar sozinha.** Fica como chave de configuracao
  (`SONDA_CONSERTO=auto` mais `MONITOR_AUTO_PULL=1`), desligada por padrao. Producao nao tem segunda chance e
  um patch ruim some do radar por um dia inteiro, que e a janela do dead-man.
- **Deixar o conserto para o Hermes.** Os cinco cron do Hermes estao pausados desde 17/10 e a instancia da VM
  esta desligada desde 03/09. Por ora, a sonda e um cron do proprio projeto; o Hermes pode virar o despachante
  depois, quando o cerebro dele estiver de pe com cron religado.

## Consequencias

- A sonda acha mais coisa do que conserta, e isso e o resultado esperado, nao uma falha de desenho. Sete das
  nove classes terminam num alerta com causa nomeada, que e exatamente o que faltou nos incidentes de 2026:
  o dono recebia "varredura incompleta" de hora em hora sem nenhuma pista da causa.
- O conserto automatico comeca sem nenhum caso real para mostrar. Por isso a aceitacao exige o **ensaio do
  sintoma plantado**: uma fixture editada a mao tem de atravessar o caminho inteiro. Um healer que nunca curou
  nada nao esta provado.
- A sonda de contrato roda numa maquina que nem sempre esta ligada. Noite perdida e noite perdida, e isso e
  aceitavel porque a sonda e amostral por natureza: o rodizio continua de onde parou. A alternativa (a VM ARM
  do OCI, sempre ligada) fica anotada como questao em aberto.
- Duas sondas significam dois lugares para olhar quando a propria sonda quebrar. Mitigacao: as duas escrevem
  o mesmo formato de relatorio e as duas alertam no mesmo chat.
