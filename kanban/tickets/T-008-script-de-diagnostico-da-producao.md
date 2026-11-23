---
id: T-008
titulo: Script de diagnostico da producao
tipo: codigo
nivel: P+
status: entregue
repo: principal
spec: [SPEC-001, PED-01]
depende_de: []
toca: [scripts/diagnostico_producao.sh, docs/DIAGNOSTICO.md]
recursos: []
afinidade:
retornos: 0
atualizado: 2026-11-23T12:10-03:00
branch: t/T-008-script-de-diagnostico-da-producao
executor: glm-flash
executor_impl: glm-flash
corpo_lancado: 843c14c3bc21
fora_do_toca: [tests/test_diagnostico_producao.py]
ponta: 33af9861d224de7e81a09572dff77db67ea7ad36
---
# T-008 · Script de diagnostico da producao

## Contexto

O pedido do Lucas abre com "ele nao tem funcionado muito bem" (PED-01 da SPEC-001). O que se sabe hoje vem do
codigo e do `HANDOFF.md`: a porta do Gran manda um bloco de HTML por LLM e ficou sem completar varredura de
23/09 a 22/10/2026; a porta de cargo do PCI nao lista estatal federal; nenhuma das tres filtra volume. O que
**nao** se sabe e o que os ultimos 30 dias de producao dizem, porque o notebook (`lucas-inspiron-3583`,
Tailscale 100.98.50.59) nao esta alcancavel pelo agente.

Este ticket entrega o script que coleta essa evidencia numa saida unica, para o Lucas rodar no notebook e
colar. A conclusao sobre o que mais esta quebrado nao e deste ticket: e nevoa da SPEC-001 secao 8 e vira
ticket depois.

O script roda **no notebook Linux**, em bash, dentro de `~/monitor_concursos_ti`. A maquina de
desenvolvimento e Windows, entao ele nao pode depender de nada que so exista aqui.

## Critério de aceite

- [ ] `scripts/diagnostico_producao.sh` roda com `bash scripts/diagnostico_producao.sh` a partir da raiz do
      repo, sem argumento obrigatorio, e sai com `0` mesmo quando encontra problema: o diagnostico **relata**,
      nao julga.
- [ ] Imprime, em secoes com titulo, cada um destes blocos:
      1. **Identidade:** data e hora, host, `git rev-parse --short HEAD`, branch, e se a arvore esta limpa.
      2. **Ultimo sucesso:** conteudo de `logs/.last_success_date` e quantos dias isso faz.
      3. **Saude por dia, ultimos 30 dias:** uma linha por `logs/run_AAAAMMDD.log`, com a data, o codigo de
         saida que a ultima linha do arquivo registra, e as contagens de `novos` e `atualizacoes` que a linha
         de "Ciclo finalizado" traz. Dia sem arquivo aparece como ausente.
      4. **Erros recorrentes:** as 15 mensagens de nivel `ERROR` e `CRITICAL` mais frequentes nos 30 dias, com
         a contagem de cada uma, agrupadas pelo texto sem os numeros variaveis.
      5. **Falha de credencial:** quantas vezes o marcador de chave ausente (o alerta com a chave, que o
         `HANDOFF.md` chama de "nenhum 🔑 no log") apareceu, por dia.
      6. **Banco:** total de linhas em `data/concursos.db`, contagem por `area`, por `fonte`, por
         `estado_usuario`, e a `ultima_atualizacao` mais recente.
      7. **Agendamento:** `crontab -l` filtrado pelas linhas do projeto, e se existe processo do monitor
         rodando agora.
      8. **Config efetiva:** quais areas estao configuradas e quais portas estao ligadas em cada uma, lendo o
         `MONITOR_TARGETS_JSON` do ambiente de producao **com os valores de segredo substituidos**.
- [ ] **Nao imprime segredo.** Token, chave de API e `chat_id` saem como `<omitido>`. O script nao le
      `~/concursos-secrets/monitor.env` para mostrar valor: so para saber **quais** chaves existem, imprimindo
      apenas o nome de cada uma. Isto e requisito de aceite, nao recomendacao (`kanban/REGRAS.md`).
- [ ] Nao escreve nada: nao cria arquivo, nao toca o banco, nao manda Telegram, nao roda varredura. Somente
      leitura.
- [ ] Funciona com o que existe num Debian/Ubuntu padrao (`bash`, `grep`, `sed`, `awk`, `sort`, `uniq`,
      `date`, `sqlite3` ou `python3`). Se o `sqlite3` de linha de comando faltar, cai no `python3` com
      `sqlite3` da stdlib em vez de falhar.
- [ ] Arquivo ou pasta que nao existe (sem `logs/`, sem banco, sem crontab) produz a linha "ausente" da secao
      e segue para a proxima. O script nunca morre no meio por falta de arquivo.
- [ ] `docs/DIAGNOSTICO.md` explica, em uma pagina: como rodar, o que cada secao significa, e **o que e sinal
      de problema** em cada uma (por exemplo: `.last_success_date` com mais de 2 dias; o mesmo `ERROR`
      repetindo todo dia; `fonte` com contagem parada; dia faltando no meio da serie).

## Plano de testes

Costura: a execucao do proprio script, por `subprocess`, sobre uma arvore falsa montada em `tmp_path` com
`logs/` e um banco de teste. Pega as secoes, o tratamento de arquivo ausente e a omissao de segredo.
**Nao pega** o notebook de verdade.

Oráculo: a arvore falsa e montada pelo teste com conteudo literal (dois logs de dias diferentes, um com
`exit=0` e outro com `exit=1`, um banco com tres linhas conhecidas, um texto com token falso). O esperado e o
que o teste escreveu, nao o que o script calcula.

Testes que nascem vermelhos em `tests/test_diagnostico_producao.py`:

- `test_script_sai_com_zero_em_arvore_minima` — arvore so com `logs/` vazio: codigo de saida `0`.
- `test_imprime_as_oito_secoes` — a saida contem o titulo de cada uma das oito secoes.
- `test_le_ultimo_sucesso_e_calcula_dias` — com `logs/.last_success_date` numa data conhecida, a saida traz
  essa data e um numero de dias coerente com ela.
- `test_lista_dia_com_exit_zero_e_dia_com_exit_um` — dois logs montados a mao: a saida mostra os dois codigos.
- `test_dia_sem_log_aparece_como_ausente` — serie com um buraco no meio: a saida marca o dia ausente.
- `test_agrupa_erros_repetidos_com_contagem` — log com a mesma mensagem de `ERROR` cinco vezes, variando so um
  numero: a saida traz uma linha com contagem 5.
- `test_conta_linhas_do_banco_por_area_e_fonte` — banco de teste com 2 de TI e 1 de EDUCACAO: as contagens
  aparecem.
- `test_nao_imprime_token` — arvore com um `.env` contendo `TELEGRAM_TOKEN=123456:ABCDEF`: a saida **nao**
  contem `123456`, e contem `TELEGRAM_TOKEN` com `<omitido>`.
- `test_sem_logs_nem_banco_nao_quebra` — arvore vazia: codigo `0` e as secoes marcadas como ausentes.
- `test_nao_escreve_nada` — compara a lista de arquivos da arvore antes e depois: identica.

## Fora do escopo

- Rodar no notebook. Quem roda e o Lucas, no ticket de deploy, que tem o recurso do dono.
- Concluir **por que** nao funcionou. A conclusao e nevoa da SPEC-001 secao 8 e vira ticket quando a saida
  existir.
- Consertar o que o diagnostico achar. Cada achado vira ticket proprio.
- Mandar o diagnostico por Telegram ou agendar no cron. E uma ferramenta de mao.
- Diagnostico das duas outras instancias do Hermes ou da VM do Oracle. So este projeto.

## Notas do arquiteto

- **P+ e nao P−:** e script de shell com ferramentas padrao, e o padrao de `scripts/run_daily.sh` esta no
  repo para copiar o estilo. O sinal `+` e por dois detalhes que custam caro se errarem: a omissao de segredo
  (que e aceite, nao conselho) e nunca morrer por arquivo ausente, porque quem roda esta num notebook,
  sozinho, e nao vai depurar bash.
- Leia o formato real dos logs antes de escrever os `grep`: as linhas sao
  `[AAAA-MM-DD HH:MM:SS] [NIVEL] [Classe]: mensagem`, e o fim de cada arquivo traz uma linha de "Finalizado
  com codigo N" gravada pelo chamador. Um exemplo completo esta em `logs/run_20260610.log`, no proprio repo.
- A linha de contagem que a secao 3 precisa e a de "Ciclo finalizado", no formato que
  `src/core/bot.py` emite.
- O `FormatterSemSegredos` (`src/utils/logger.py`) ja limpa os logs **novos**. Os antigos, de 25/09 a 02/10,
  tem token vazado (pendencia 2 do `HANDOFF.md`): e mais um motivo para o filtro de segredo do script ser
  aceite e ter teste proprio.
- O teste roda o script por `subprocess`. No Windows isso exige o bash do Git; se o ambiente de teste nao
  tiver, marque os testes para pular com `pytest.mark.skipif` em vez de deixar a suite vermelha na maquina de
  desenvolvimento. A suite tem de ficar verde nos dois sistemas.

**Decisão do arquiteto (2026-11-23 12:11):** O tests/test_diagnostico_producao.py saiu fora do toca, e o erro e do arquiteto: o toca deste ticket foi declarado com o script e o doc, sem o arquivo de teste, que o proprio plano de testes exigia. Nos outros onze tickets o teste esta declarado. Nao conte como desvio do implementador; o arquivo esta no lugar certo do repo.

## Histórico
- 2026-11-23 11:16 backlog → pronto · liberado: OK do Lucas em 23/11/2026
- 2026-11-23 11:38 pronto → fazendo · implementador · glm-flash P+ high
- 2026-11-23 12:10 fazendo → entregue · implementador: ENTREGUE · relatório T-008-implementador-1.md · 33 min · fora do toca: 1 arquivo(s)
