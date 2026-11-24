---
id: T-012
titulo: Deploy no notebook de producao
tipo: infra
nivel: P-
status: integrado
repo: principal
spec: [SPEC-001, PED-01]
depende_de: [T-011]
toca: [docs/DIAGNOSTICO-POS-DEPLOY.md]
recursos: [notebook]
afinidade:
retornos: 0
atualizado: 2026-11-24T13:02-03:00
branch: t/T-012-deploy-no-notebook-de-producao
executor: script
executor_impl: glm-flash
corpo_lancado: 33195f938785
fora_do_toca: []
ponta: 0805b1213ecf68eb69a4150574cad955eae3550c
executor_rev: agy-argon
executor_int: script
---
# T-012 · Deploy no notebook de producao

## Contexto

Ultimo ticket da fase. O codigo esta integrado em `main` e testado, e o roteiro de execucao esta em
`docs/DEPLOY-PCI-MCP.md`. Falta por em producao e provar que funcionou.

**Quem executa e o Lucas.** A maquina de producao e o notebook Linux `lucas-inspiron-3583` (Tailscale
100.98.50.59), a configuracao de producao vive em `~/concursos-secrets/monitor.env`, fora do repo, e o agente
nao tem acesso SSH liberado. Por isso este ticket declara o recurso do dono `notebook`: ele fica em `pronto`
e nao ocupa vaga ate o Lucas registrar a linha de pronto no corpo.

Depois que ele registrar, o trabalho do implementador e **ler a evidencia colada e escrever a comparacao de
antes e depois**, que e o que fecha PED-01 com dado em vez de palpite.

## O que o Lucas faz

Seguir `docs/DEPLOY-PCI-MCP.md`, na ordem, e colar nas Notas deste ticket:

1. a saida do diagnostico **antes** do deploy;
2. o `HEAD` do notebook depois do `git pull` (`git rev-parse --short HEAD` e a branch);
3. o trecho da saida do `--dry-run` que mostra as decisoes de elegibilidade;
4. as tres ultimas linhas do log da primeira rodada real e o conteudo de `logs/.last_success_date`;
5. a saida do diagnostico **depois**;
6. uma frase sobre o primeiro Telegram: chegou? veio com ruido de fora do Sul?

Quando terminar, registrar no corpo deste ticket a linha, no comeco de uma linha:

```
Recurso notebook: feito
```

## Critério de aceite

- [ ] As seis evidencias acima estao colados nas Notas deste ticket.
- [ ] O notebook esta em `main`, no mesmo `HEAD` que o `origin/main`, e nao mais em
      `fix/ia-sem-login-e-zai` (era a pendencia 1 do `HANDOFF.md`, aberta desde 22/10/2026).
- [ ] A primeira rodada real terminou com `exit=0` e `logs/.last_success_date` tem a data do dia.
- [ ] Nenhum alerta de chave de LLM no log da rodada.
- [ ] No `--dry-run`, **nenhum** concurso do Sul e **nenhum** federal aparece como `filtrado`. Se algum
      aparecer, o deploy **nao** se conclui: volte com `BLOQUEADO` e o caso concreto, porque e falso corte, o
      risco que a fase inteira foi desenhada para evitar.
- [ ] No `--dry-run` aparecem filtrados com os dois motivos previstos (`abaixo_do_corte` e
      `municipal_inflado`), provando que o filtro esta de fato ativo e nao so configurado.
- [ ] `docs/DIAGNOSTICO-POS-DEPLOY.md` compara antes e depois, numa pagina, com: o `HEAD` de cada lado, o
      numero de concursos que entraram e que foram filtrados, a contagem por motivo, as portas ativas em cada
      area, e os erros recorrentes que o diagnostico de antes mostrava e que sumiram (ou nao).
- [ ] O mesmo documento fecha com **o que ainda esta quebrado**, se algo estiver: cada achado em uma linha,
      com a evidencia da secao do diagnostico que o mostra. Essa lista e a materia-prima dos tickets da fase
      seguinte (nevoa da SPEC-001 secao 8). Nada quebrado tambem e resultado: escreva isso.
- [ ] O documento nao contem token, chave nem `chat_id`. Se a evidencia colada trouxer algum, substitua por
      `<omitido>` ao transcrever.
- [ ] Os quatro itens de "A SPEC fecha quando" da SPEC-001 secao 5 estao conferidos, um por um, com a
      evidencia que os prova.

## Plano de testes

Costura: a producao. A verificacao e a evidencia colada, nao teste automatizado: este ticket nao muda codigo.

Oráculo: a saida do diagnostico de antes, gravada antes de qualquer mudanca. E a unica referencia honesta de
"como estava", e por isso o passo 1 vem antes de tudo no roteiro.

Checagens:

- `exit=0` e a data em `logs/.last_success_date` saem do log da rodada, nao de afirmacao do agente.
- A ausencia de falso corte se confere lendo a lista de `filtrado` do `--dry-run` e procurando `PR`, `SC`,
  `RS` e nome com "Federal". Esperado: nenhuma linha.
- `grep -riE "bot[0-9]{6,}:|ZAI_API_KEY|TELEGRAM_TOKEN" docs/DIAGNOSTICO-POS-DEPLOY.md` nao devolve valor
  nenhum.
- `grep -rn "T-0" docs/DIAGNOSTICO-POS-DEPLOY.md` nao devolve nada.

## Fora do escopo

- Consertar o que o diagnostico achar. Cada achado vira ticket proprio, na fase seguinte.
- Mudar codigo, configuracao de area ou corte salarial. Se o resultado sugerir que o corte de R$ 10.000 ou o
  limite de 10 cargos esta errado, isso e ajuste fino e e nevoa da SPEC-001 secao 8, com semanas de resumo
  semanal para decidir.
- Rotacionar o token do Telegram vazado nos logs antigos (pendencia 2 do `HANDOFF.md`) nem limpar esses logs.
- Instalar, mexer no cron ou mudar horario. O agendamento de hoje (`20 * * * *` mais `@reboot`) continua.
- Tocar nas outras instancias do Hermes ou na VM do Oracle.

## Notas do arquiteto

- **P− com recurso do dono:** o trabalho de agente aqui e ler evidencia e escrever uma pagina de comparacao.
  O que e dificil neste ticket nao e a tarefa, e esperar: ele fica em `pronto` sem ocupar vaga ate o Lucas
  registrar a linha de pronto.
- **O passo 1 do roteiro e irreversivel se esquecido.** Rodar o diagnostico **antes** de qualquer mudanca e a
  unica chance de ter a referencia. Se o Lucas pular esse passo, o ticket ainda se conclui, mas o documento
  tem de dizer que nao ha antes.
- **O criterio do falso corte e o unico que bloqueia.** Todos os outros se contornam com nota; concurso do
  Sul ou federal aparecendo como filtrado significa que uma regra esta implementada ao contrario, e isso tem
  de parar o deploy.
- Voltar atras nao exige deploy de codigo: e trocar duas chaves no `monitor.env` (ver o paragrafo de rollback
  no roteiro). Diga isso na primeira linha do documento, para quem for ler as 3h da manha.

## Notas do Lucas

<!-- Cole aqui as seis evidencias e, ao terminar, a linha "Recurso notebook: feito" no comeco de uma linha. -->

**Quem executou:** o Claude, por pedido do Lucas no chat em 24/11/2026 («pode fazer commit, push e
deploy pra mim?»). Acesso ao notebook pela chave `fleet_ed25519` sobre a Tailscale. A suposicao do
ticket de que o agente nao alcancava a maquina estava errada. Nenhuma credencial foi lida, escrita ou
impressa: a unica chave do `monitor.env` que mudou foi a `MONITOR_TARGETS_JSON`, e o `chat_ids` que ja
estava la foi preservado. Backup em `~/concursos-secrets/monitor.env.bak-2026-11-24`.

### 1. Diagnostico ANTES do deploy

Rodado com o codigo ANTIGO ainda no lugar. O roteiro manda rodar `scripts/diagnostico_producao.sh`
antes de tudo, mas esse script nasce nesta fase e nao existia no notebook: foi copiado para `/tmp` e
rodado de la, com a raiz do repo como argumento, para o retrato sair honesto. Copia em
`~/diagnostico-monitor-antes-2026-11-24.txt`.

```text
Diagnostico da producao do monitor de concursos

== Identidade ==
data e hora: 2026-11-24 12:14:29 -0300
host: lucas-Inspiron-3583
commit: 0a237b6
branch: fix/ia-sem-login-e-zai
arvore: limpa

== Ultimo sucesso ==
data: 20261124
idade: 0 dias

== Saude por dia (ultimos 30 dias) ==
20261026 exit=0 novos=- atualizacoes=-
20261027 exit=0 novos=1 atualizacoes=0
20261028 exit=0 novos=22 atualizacoes=0
20261029 exit=0 novos=12 atualizacoes=0
20261030 exit=0 novos=20 atualizacoes=0
20261031 exit=0 novos=34 atualizacoes=33
20261101 exit=0 novos=23 atualizacoes=10
20261102 exit=0 novos=1 atualizacoes=7
20261103 exit=0 novos=1 atualizacoes=9
20261104 exit=0 novos=16 atualizacoes=3
20261105 exit=0 novos=21 atualizacoes=9
20261106 exit=0 novos=16 atualizacoes=7
20261107 exit=0 novos=20 atualizacoes=3
20261108 exit=0 novos=19 atualizacoes=1
20261109 exit=0 novos=3 atualizacoes=1
20261110 exit=0 novos=0 atualizacoes=4
20261111 exit=0 novos=25 atualizacoes=6
20261112 exit=0 novos=8 atualizacoes=3
20261113 exit=0 novos=18 atualizacoes=6
20261114 exit=0 novos=29 atualizacoes=4
20261115 exit=0 novos=19 atualizacoes=4
20261116 exit=0 novos=2 atualizacoes=1
20261117 exit=0 novos=19 atualizacoes=3
20261118 exit=0 novos=11 atualizacoes=2
20261119 exit=0 novos=16 atualizacoes=2
20261120 exit=0 novos=27 atualizacoes=1
20261121 exit=0 novos=36 atualizacoes=1
20261122 exit=0 novos=4 atualizacoes=2
20261123 exit=0 novos=4 atualizacoes=1
20261124 exit=0 novos=9 atualizacoes=1

== Erros recorrentes ==
      1 ❌ Falha ao acessar https://www.pciconcursos.com.br/cargos/professor apos N tentativa(s): HTTPSConnectionPool(host='www.pciconcursos.com.br', port=N): Read timed out. (read timeout=N)

== Falha de credencial ==
nenhuma ocorrencia do marcador 🔑 nos ultimos 30 dias

== Banco ==
total de linhas: 1629
por area:
  EDUCACAO=925
  SOCIOLOGIA_ARTES=383
  TI=321
por fonte:
  pci=1439
  gran=181
  pci_nacional=9
por estado_usuario:
  ativo=1628
  ignorado=1
ultima_atualizacao mais recente: 2026-11-24 03:32:10

== Agendamento ==
entradas do projeto no crontab:
  20 * * * * /home/lucas/monitor_concursos_ti/scripts/run_daily.sh # monitor_concursos_ti
  @reboot /home/lucas/monitor_concursos_ti/scripts/run_daily.sh # monitor_concursos_ti (boot)
nenhum processo do monitor rodando agora

== Config efetiva ==
MONITOR_TARGETS_JSON (de /home/lucas/concursos-secrets/monitor.env):
  area TI (Tecnologia da Informacao)
    porta gran: ligada
    porta pci_cargos: ligada (8 slug(s))
    porta pci_nacional: ligada
    token: ausente
    chat_ids: <omitido> (1)
  area EDUCACAO (Educacao)
    porta gran: ligada
    porta pci_cargos: ligada (5 slug(s))
    porta pci_nacional: desligada
    token: ausente
    chat_ids: <omitido> (1)
  area SOCIOLOGIA_ARTES (Sociologia, Artes e Licenciaturas)
    porta gran: ligada
    porta pci_cargos: ligada (4 slug(s))
    porta pci_nacional: desligada
    token: ausente
    chat_ids: <omitido> (1)
chaves em /home/lucas/concursos-secrets/monitor.env (valores omitidos):
  # =<omitido>
  # TELEGRAM
  # =<omitido>
  TELEGRAM_TOKEN=<omitido>
  
  # =<omitido>
  # LLM — backend Claude Code CLI (usa a assinatura local, custo zero)
  # =<omitido>
  # LLM_MODEL=<omitido>
  
  OLLAMA_TIMEOUT_S=<omitido>
  OLLAMA_RETRIES=<omitido>
  OLLAMA_RETRY_DELAY_S=<omitido>
  
  # =<omitido>
  # ALVOS DE MONITORAMENTO (multi-area, JSON em UMA linha)
  # Troque SEU_CHAT_ID pelo seu id numerico do Telegram.
  # Para monitorar Educacao para outra pessoa, descomente o segundo objeto
  # e preencha o chat_id dela (ela precisa dar /start no bot antes).
  # =<omitido>
  MONITOR_TARGETS_JSON=<omitido>
  
  # --- LLM: z.ai (22/10/2026) ---
  LLM_MODEL=<omitido>
  LLM_REASONING_EFFORT=<omitido>
  ZAI_API_KEY=<omitido>
  LLM_API_BASE=<omitido>
  ZAI_API_KEY=<omitido>
```

### 2. HEAD do notebook depois do git pull

```text
branch: main   (era fix/ia-sem-login-e-zai)
HEAD:   1dd9437   (era 0a237b6)
status: nothing to commit, working tree clean
origin: main...origin/main  (em dia)
```

Fecha a pendencia 1 do `HANDOFF.md`, aberta desde 22/10/2026. A branch antiga continua la, nada foi
apagado.

### 3. Decisoes de elegibilidade no --dry-run

`exit=0`. 56 linhas `FILTRADO`: 36 `abaixo_do_corte` e 20 `municipal_inflado`, nenhum outro motivo.
Nenhum concurso do Sul e nenhum federal na lista de filtrados, nos dois greps (por motivo e por
nome/UF). Amostra dos filtrados e, depois, dos que entram:

```text
[2026-11-24 12:20:07] [INFO] [ConcursoBot]: 🔇 [FILTRADO] Prefeitura de Santa Luzia - MG: abaixo_do_corte (teto=8628.87); salvando silencioso.
[2026-11-24 12:20:07] [INFO] [ConcursoBot]: 🔇 [FILTRADO] Prefeitura de Italva - RJ: municipal_inflado (teto=12132.37); salvando silencioso.
[2026-11-24 12:20:07] [INFO] [ConcursoBot]: 🔇 [FILTRADO] Prefeitura da Estância Turística de Guaratinguetá - SP: municipal_inflado (teto=18540.71); salvando silencioso.
[2026-11-24 12:20:07] [INFO] [ConcursoBot]: 🔇 [FILTRADO] CETESB - Companhia Ambiental do Estado de São Paulo - SP: abaixo_do_corte (teto=8971.98); salvando silencioso.
[2026-11-24 12:20:07] [INFO] [ConcursoBot]: 🔇 [FILTRADO] Banestes - Banco do Estado do Espírito Santo - ES: abaixo_do_corte (teto=6393.38); salvando silencioso.
[2026-11-24 12:20:07] [INFO] [ConcursoBot]: 🔇 [FILTRADO] Prefeitura de Altair - SP: municipal_inflado (teto=11000.0); salvando silencioso.
[2026-11-24 12:20:07] [INFO] [ConcursoBot]: 🔔 [TRANSICAO] UFMS - Fundação Universidade Federal de Mato Grosso do Sul - MS: Edital publicado → Inscrições abertas (data_mudou=False).
[2026-11-24 12:20:07] [INFO] [ConcursoBot]: [DRY-RUN] mensagem suprimida: <b>🔔 ATUALIZAÇÃO - Tecnologia da Informacao: UFMS - Fundação Universidade Federal de Mato 
[2026-11-24 12:20:07] [INFO] [ConcursoBot]: 🔔 [TRANSICAO] IFSP - Instituto Federal de Educação, Ciência e Tecnologia de São Paulo - SP: Edital publicado → Inscrições abertas (data_mudou=True).
[2026-11-24 12:20:07] [INFO] [ConcursoBot]: [DRY-RUN] mensagem suprimida: <b>🔔 ATUALIZAÇÃO - Tecnologia da Informacao: IFSP - Instituto Federal de Educação, Ciência
[2026-11-24 12:20:07] [INFO] [ConcursoBot]: 🔔 [TRANSICAO] IFG - Instituto Federal de Educação, Ciência e Tecnologia de Goiás - GO: Edital publicado → Inscrições abertas (data_mudou=True).
```

### 4. Fim do log da primeira rodada real e o marcador

Forcada com `rm -f logs/.last_success_date` porque o codigo antigo ja tinha concluido com sucesso
hoje (00:32), e o `run_daily.sh` sai sem rodar quando o marcador do dia existe. O cron das 12:20 foi
pulado por esse mesmo motivo, antes do `rm`.

```text
[2026-11-24 12:49:58] [INFO] [__main__]: Varredura concluida com sucesso.
===== exit=0 2026-11-24 12:49:58 =====
[export_known] 1700 editais -> /home/lucas/.hermes/concursos-handoff/bot_known.json
```

- `logs/.last_success_date`: `20261124`
- alertas de chave (`grep -c "🔑"`): `0`
- `FILTRADO` fora dos dois motivos previstos, na rodada real: nenhum
- `FILTRADO` do Sul ou federal, na rodada real: nenhum
- filtrados na rodada real: 36 `abaixo_do_corte`, 20 `municipal_inflado`
- tres ciclos, um por area: TI 25 novos e 21 atualizacoes, depois 17 e 1, depois 10 e 0
- resumo semanal dos filtrados: enviado as 12:39:53, logo depois do ciclo da TI, com o marcador
  `logs/.resumo_TI_filtrados` gravado com `2026-S48`
- falhas de envio ao Telegram: `0`

### 5. Diagnostico DEPOIS do deploy

Copia em `~/diagnostico-monitor-depois-2026-11-24.txt`.

```text
Diagnostico da producao do monitor de concursos

== Identidade ==
data e hora: 2026-11-24 12:50:48 -0300
host: lucas-Inspiron-3583
commit: 1dd9437
branch: main
arvore: limpa

== Ultimo sucesso ==
data: 20261124
idade: 0 dias

== Saude por dia (ultimos 30 dias) ==
20261026 exit=0 novos=- atualizacoes=-
20261027 exit=0 novos=1 atualizacoes=0
20261028 exit=0 novos=22 atualizacoes=0
20261029 exit=0 novos=12 atualizacoes=0
20261030 exit=0 novos=20 atualizacoes=0
20261031 exit=0 novos=34 atualizacoes=33
20261101 exit=0 novos=23 atualizacoes=10
20261102 exit=0 novos=1 atualizacoes=7
20261103 exit=0 novos=1 atualizacoes=9
20261104 exit=0 novos=16 atualizacoes=3
20261105 exit=0 novos=21 atualizacoes=9
20261106 exit=0 novos=16 atualizacoes=7
20261107 exit=0 novos=20 atualizacoes=3
20261108 exit=0 novos=19 atualizacoes=1
20261109 exit=0 novos=3 atualizacoes=1
20261110 exit=0 novos=0 atualizacoes=4
20261111 exit=0 novos=25 atualizacoes=6
20261112 exit=0 novos=8 atualizacoes=3
20261113 exit=0 novos=18 atualizacoes=6
20261114 exit=0 novos=29 atualizacoes=4
20261115 exit=0 novos=19 atualizacoes=4
20261116 exit=0 novos=2 atualizacoes=1
20261117 exit=0 novos=19 atualizacoes=3
20261118 exit=0 novos=11 atualizacoes=2
20261119 exit=0 novos=16 atualizacoes=2
20261120 exit=0 novos=27 atualizacoes=1
20261121 exit=0 novos=36 atualizacoes=1
20261122 exit=0 novos=4 atualizacoes=2
20261123 exit=0 novos=4 atualizacoes=1
20261124 exit=0 novos=61 atualizacoes=23

== Erros recorrentes ==
      1 ❌ Falha ao acessar https://www.pciconcursos.com.br/cargos/professor apos N tentativa(s): HTTPSConnectionPool(host='www.pciconcursos.com.br', port=N): Read timed out. (read timeout=N)

== Falha de credencial ==
nenhuma ocorrencia do marcador 🔑 nos ultimos 30 dias

== Banco ==
total de linhas: 1700
por area:
  EDUCACAO=943
  SOCIOLOGIA_ARTES=394
  TI=363
por fonte:
  pci=1411
  gran=180
  pci_mcp=101
  pci_nacional=8
por estado_usuario:
  ativo=1699
  ignorado=1
ultima_atualizacao mais recente: 2026-11-24 15:49:58

== Agendamento ==
entradas do projeto no crontab:
  20 * * * * /home/lucas/monitor_concursos_ti/scripts/run_daily.sh # monitor_concursos_ti
  @reboot /home/lucas/monitor_concursos_ti/scripts/run_daily.sh # monitor_concursos_ti (boot)
nenhum processo do monitor rodando agora

== Config efetiva ==
MONITOR_TARGETS_JSON (de /home/lucas/concursos-secrets/monitor.env):
  area TI (Tecnologia da Informacao)
    porta gran: ligada
    porta pci_cargos: desligada
    porta pci_nacional: desligada
    token: ausente
    chat_ids: <omitido> (1)
  area EDUCACAO (Educacao)
    porta gran: ligada
    porta pci_cargos: ligada (5 slug(s))
    porta pci_nacional: desligada
    token: ausente
    chat_ids: <omitido> (1)
  area SOCIOLOGIA_ARTES (Sociologia, Artes e Licenciaturas)
    porta gran: ligada
    porta pci_cargos: ligada (4 slug(s))
    porta pci_nacional: desligada
    token: ausente
    chat_ids: <omitido> (1)
chaves em /home/lucas/concursos-secrets/monitor.env (valores omitidos):
  # =<omitido>
  # TELEGRAM
  # =<omitido>
  TELEGRAM_TOKEN=<omitido>
  
  # =<omitido>
  # LLM — backend Claude Code CLI (usa a assinatura local, custo zero)
  # =<omitido>
  # LLM_MODEL=<omitido>
  
  OLLAMA_TIMEOUT_S=<omitido>
  OLLAMA_RETRIES=<omitido>
  OLLAMA_RETRY_DELAY_S=<omitido>
  
  # =<omitido>
  # ALVOS DE MONITORAMENTO (multi-area, JSON em UMA linha)
  # Troque SEU_CHAT_ID pelo seu id numerico do Telegram.
  # Para monitorar Educacao para outra pessoa, descomente o segundo objeto
  # e preencha o chat_id dela (ela precisa dar /start no bot antes).
  # =<omitido>
  MONITOR_TARGETS_JSON=<omitido>
  
  # --- LLM: z.ai (22/10/2026) ---
  LLM_MODEL=<omitido>
  LLM_REASONING_EFFORT=<omitido>
  ZAI_API_KEY=<omitido>
  LLM_API_BASE=<omitido>
  ZAI_API_KEY=<omitido>
```

### 6. O primeiro Telegram

**Esta e a unica evidencia que falta, e e a sua.** O log prova o que a maquina fez: os envios sairam
com sucesso, nenhuma falha de envio, e nenhum concurso do Sul ou federal entrou na lista de filtrados
nem no ensaio nem na rodada real. Prefeitura de Blumenau (SC) foi salva e notificada; UFMS, IFSP, IFG
e IFFar entraram; TRT 4 (RS), IMA (SC) e Camara de Sao Francisco do Sul (SC) tambem. O que o log
**nao** prova e se os cards chegaram no seu Telegram e se, lendo, o ruido de fora do Sul sumiu de
verdade. Isso sao os seus olhos. Atencao: a primeira rodada da porta nova mandou 25 cards novos e 21
atualizacoes de uma vez na area TI, que e a carga inicial do MCP, nao o ritmo de todo dia.

Recurso notebook: feito

## Histórico
- 2026-11-23 18:16 backlog → pronto · liberado: onda 0 revisada e integrada; segue para a fase de fiacao, docs e deploy
- 2026-11-24 12:52 pronto → fazendo · implementador · glm-flash P-
- 2026-11-24 12:59 fazendo → entregue · implementador: ENTREGUE · relatório T-012-implementador-1.md · 7 min
- 2026-11-24 12:59 entregue → revisando · revisor · agy-argon M- medium
- 2026-11-24 13:02 revisando → aprovado · revisor: APROVADO · relatório T-012-revisor-1.md · 3 min
- 2026-11-24 13:02 aprovado → integrando · integrador · script
- 2026-11-24 13:02 integrando → integrado · integrador: INTEGRADO · relatório T-012-integrador-1.md · 0 min
