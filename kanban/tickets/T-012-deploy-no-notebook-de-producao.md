---
id: T-012
titulo: Deploy no notebook de producao
tipo: infra
nivel: P-
status: backlog
repo: principal
spec: [SPEC-001, PED-01]
depende_de: [T-011]
toca: [docs/DIAGNOSTICO-POS-DEPLOY.md]
recursos: [notebook]
afinidade:
retornos: 0
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
