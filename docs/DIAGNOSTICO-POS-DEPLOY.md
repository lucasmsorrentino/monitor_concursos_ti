# Diagnóstico pós-deploy — PCI pelo servidor MCP e corte fora do Sul

> **Como voltar atrás (para quem está lendo às 3h da manhã):** não há código a reverter nem deploy a
> desfazer. Edite o objeto da área TI no `~/concursos-secrets/monitor.env`: `filtro_salarial` para
> `"desligado"` e `pci_mcp` para `false`, reposindo `pci_slugs` e `pci_nacional` com os valores do
> backup `monitor.env.bak-2026-11-24`. Na rodada seguinte do cron — no máximo uma hora depois — tudo
> volta a se comportar como antes da fase: nada se renotifica e as colunas novas do banco ficam
> gravadas, simplesmente ignoradas. Detalhe completo: seção "Como voltar atrás" de
> `docs/DEPLOY-PCI-MCP.md`.

Deploy de 24/11/2026 no notebook de produção `lucas-inspiron-3583` (Tailscale 100.98.50.59),
segundo o roteiro `docs/DEPLOY-PCI-MCP.md`, executado na ordem. Este documento compara o
diagnóstico de antes (12:14, com o código ainda antigo no lugar) com o de depois (12:50) e lê o
ensaio `--dry-run` e a primeira rodada real do dia. As evidências brutas são as seis coladas nas
notas do ticket no quadro; cópias dos diagnósticos em
`~/diagnostico-monitor-{antes,depois}-2026-11-24.txt` no notebook.

## Antes × depois

| | Antes (24/11 · 12:14) | Depois (24/11 · 12:50) |
| :--- | :--- | :--- |
| `HEAD` · branch | `0a237b6` · `fix/ia-sem-login-e-zai` | `1dd9437` · `main` (em dia com `origin/main`) |
| Último sucesso | `20261124` · idade 0 dias | `20261124` · idade 0 dias |
| Banco (linhas) | 1629 | 1700 (+71) |
| Por área | TI 321 · EDUCACAO 925 · SOCIOLOGIA_ARTES 383 | TI 363 (+42) · EDUCACAO 943 (+18) · SOCIOLOGIA_ARTES 394 (+11) |
| Por fonte | pci 1439 · gran 181 · pci_nacional 9 | pci 1411 (−28) · gran 180 (−1) · pci_nacional 8 (−1) · **pci_mcp 101 (nova)** |
| Erros recorrentes (30 d) | 1× timeout na porta de cargos "professor" do PCI | a mesma 1 ocorrência; nenhuma nova entre os dois retratos |
| Credencial (30 d) | 0 ocorrências | 0 ocorrências |
| Cron | `20 * * * *` + `@reboot` | inalterado |

**Concursos que entraram × filtrados.** Antes da troca, o dia 24/11 tinha 9 novos e 1 atualização
(rodada das 03:32, código antigo). No retrato de depois, o dia vai em 61 novos e 23 atualizações: a
rodada real feita às 12:49 rodou três ciclos — um por área — com a TI recebendo 25 novos e 21
atualizações (a carga inicial do MCP, não o ritmo de todo dia), e EDUCACAO e SOCIOLOGIA_ARTES 17/1
e 10/0. A conta do dia fecha: 52 + 9 novos = 61; 22 + 1 atualizações = 23.

- **Ensaio `--dry-run` (12:20):** `exit=0`; **56 filtrados = 36 `abaixo_do_corte` + 20
  `municipal_inflado`**; nenhum outro motivo.
- **Primeira rodada real (12:49, forçada removendo o marcador do dia, porque o código antigo já
  tinha concluído com sucesso hoje):** `exit=0`; mesma distribuição (36 + 20), nenhum motivo fora
  dos dois previstos; `logs/.last_success_date` = `20261124`; zero alerta de credencial no log;
  zero falha de envio ao Telegram; resumo semanal dos filtrados enviado às 12:39:53, com o
  marcador `logs/.resumo_TI_filtrados` em `2026-S48`.

**Falso corte (o critério que bloqueia): nenhum.** Nos dois greps — por motivo e por nome/UF —
sobre a lista de filtrados do ensaio e da rodada real, nenhuma linha de PR, SC ou RS e nenhum nome
com "Federal". Do Sul e federais entraram: Blumenau-SC, IMA-SC e Câmara de São Francisco do Sul-SC
salvos e notificados; TRT 4-RS; UFMS, IFSP, IFG e IFFar.

## Portas por área (config efetiva)

| Área | Antes | Depois |
| :--- | :--- | :--- |
| TI | gran ligada · pci_cargos ligada (8 slugs) · pci_nacional ligada | gran ligada · pci_cargos desligada · pci_nacional desligada · **pci_mcp ligada (padrão)** |
| EDUCACAO | gran ligada · pci_cargos ligada (5 slugs) · pci_nacional desligada | inalterada |
| SOCIOLOGIA_ARTES | gran ligada · pci_cargos ligada (4 slugs) · pci_nacional desligada | inalterada |

O bloco "Config efetiva" do diagnóstico não imprime `pci_mcp` nem `filtro_salarial`: a prova de que
a porta nova e a elegibilidade estão ativas é indireta — fonte `pci_mcp` com 101 linhas no banco e
as 56 linhas `FILTRADO` do ensaio.

## "A SPEC fecha quando" (seção 5 da SPEC-001), um por um

1. **Suíte inteira verde, testes novos cobrindo cada regra numerada** — nesta rodada, no mesmo
   commit que o notebook (`1dd9437`): `pytest -q`, **539 passed, 0 failed** (os 296 verdes de
   23/11 viraram 539 com a fiação da fase). ✔
2. **Rodada `--dry-run` na área TI, com MCP ligado e corte ativo, mostrando filtrado para municipal
   inflado e teto abaixo do corte, e entrada para Sul, federal e teto acima** — evidência do
   ensaio: 36 `abaixo_do_corte` + 20 `municipal_inflado`; entraram UFMS, IFSP, IFG e os concursos
   do Sul citados acima. ✔
3. **Nenhum concurso do Sul e nenhum federal filtrado** — os dois greps voltam vazios, no ensaio e
   na rodada real. ✔
4. **Deploy com rodada completa `exit=0` e primeiro Telegram sem o ruído de fora do Sul** — a
   metade da máquina está provada (`exit=0`, marcador do dia, zero falha de envio); a metade
   humana — cards chegando e sem ruído — depende da confirmação do Lucas. ◐ (único em aberto)

## O que ainda está quebrado ou em aberto

Cada linha é matéria-prima de ticket da fase seguinte; a evidência fica na seção indicada.

- **O timeout recorrente do PCI não sumiu** — a mesma 1 ocorrência (porta de cargos "professor",
  read timeout) aparece nos dois retratos; nenhuma nova na janela do deploy, e a porta seguiu
  ligada só em EDUCACAO e SOCIOLOGIA_ARTES. (Evidência: "Erros recorrentes" dos dois diagnósticos.)
- **O retrato de config não prova a porta nova** — o bloco "Config efetiva" de
  `scripts/diagnostico_producao.sh` não imprime `pci_mcp` nem `filtro_salarial`; vale uma linha a
  mais no script. (Evidência: "Config efetiva" do diagnóstico de depois.)
- **A contabilidade log × banco não fecha de primeira** — 61 "novos" no dia contra +101 linhas
  `pci_mcp` e −30 nas portas antigas (+71 líquido). Leitura provável: filtrados salvos em silêncio
  e linhas que mudaram de chave de fonte explicam a diferença; conferir que a unificação por `id`
  não perdeu concurso. (Evidência: "Saúde por dia" e "Banco" dos dois diagnósticos.)
- **Horas do banco e do log não batem** — `ultima_atualizacao` registra 15:49:58 para a rodada que
  o log marca às 12:49:58 (e a rodada das 00:32 local aparece como 03:32 no banco): consistente com
  o banco em UTC e o log em hora local. Provável escolha já feita, mas vale decidir e anotar uma
  vez. (Evidência: "Banco" dos dois diagnósticos; última linha do log da rodada real.)
- **Primeiro Telegram sem confirmação humana** — o log prova zero falha de envio; só o Lucas
  confirma que os cards chegaram e sem ruído de fora do Sul. (Evidência: seção 6 das notas do
  ticket, a única que não vem da máquina.)
- **Token vazado em logs antigos segue sem rotação** — pendência 2 do `HANDOFF.md`, fora do escopo
  desta rodada. (Evidência: `HANDOFF.md`, item 2.)
