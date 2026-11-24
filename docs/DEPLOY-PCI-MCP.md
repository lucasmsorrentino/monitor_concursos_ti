# Deploy — PCI pelo servidor MCP e filtro salarial, no notebook de produção

Roteiro para o Lucas executar sozinho, no notebook, com calma. Segue a ordem de execução: um comando
por bloco, com **o que você deve ver** depois dele. Se um passo não mostrar o que está escrito, pare
nele — os passos seguintes assumem que este deu certo.

O que essa rodada muda: o PCI passa a ser lido pelo servidor MCP oficial (`pci_mcp`), que é a porta
padrão da área TI; as duas portas de HTML do PCI ficam como reserva, desligadas por configuração; e a
elegibilidade entra ativa na TI, silenciando concurso fora do Sul com teto abaixo de R$ 10.000 e
municipal inflado, com resumo semanal dos filtrados. As áreas EDUCACAO e SOCIOLOGIA_ARTES não mudam
em nada. O porquê de cada escolha está nas ADRs (`docs/adr/0001` e `docs/adr/0002`) e na spec
(`docs/specs/SPEC-001`) — este roteiro não as repete, só executa.

## Onde cada coisa mora

| O quê | Onde |
| :--- | :--- |
| Máquina de produção | Notebook Linux `lucas-inspiron-3583`, Tailscale `100.98.50.59` |
| Repo em produção | `~/monitor_concursos_ti` (venv em `.venv`) |
| Branch depois do deploy | `main` (hoje o notebook está em `fix/ia-sem-login-e-zai`) |
| Segredos | `~/concursos-secrets/monitor.env`, **fora do repo** |
| Agendamento | crontab `20 * * * *` + `@reboot` → `scripts/run_daily.sh` |
| Log do dia | `~/monitor_concursos_ti/logs/run_AAAAMMDD.log` |
| Marcador de sucesso | `~/monitor_concursos_ti/logs/.last_success_date` (formato AAAAMMDD) |
| Diagnóstico da máquina | `bash scripts/diagnostico_producao.sh` (somente leitura; sai sempre com 0) |

---

## 1. Antes — o retrato da máquina

Rode no notebook, a partir da raiz do repo, e guarde a saída (é o "antes" para comparar no fim):

```bash
cd ~/monitor_concursos_ti
bash scripts/diagnostico_producao.sh | tee ~/diagnostico-monitor-antes-$(date +%F).txt
```

**O que você deve ver:** as seções `== identidade ==`, `== ultimo sucesso ==`, `== saude por dia ==`,
`== erros recorrentes ==`, `== credencial ==`, `== banco ==`, `== agendamento ==` e `== config ==`,
e o comando terminando sem erro (o script é somente leitura: não escreve arquivo, não toca no banco,
não manda mensagem e sai com 0 mesmo quando algo está ausente). A cópia fica em
`~/diagnostico-monitor-antes-AAAAMMDD.txt`.

## 2. Trazer o código — Windows primeiro, depois o notebook

A `main` local do Windows já está integrada, mas o `origin/main` do GitHub está atrasado desde
22/10/2026. Sem o push, o `git pull` no notebook não traz nada.

No **Windows**, na pasta do repo principal:

```bash
cd "C:\Users\Lucas\Documents\automation\monitor_concursos"
git push origin main
```

**O que você deve ver:** um bloco como `Para https://github.com/lucasmsorrentino/monitor_concursos_ti.git`
seguido de `1eb1a1f..<novo hash>  main -> main`. Se disser `Everything up-to-date`, o push já tinha
sido feito e está tudo bem — desde que o passo do notebook abaixo mostre os commits novos.

No **notebook**:

```bash
cd ~/monitor_concursos_ti
git fetch origin
```

**O que você deve ver:** uma lista de `..` atualizações de `main` (ou silêncio, se já estava em dia).

```bash
git checkout main
```

**O que você deve ver:** `Switched to branch 'main'` e `Your branch is behind 'origin/main'`. É aqui
que o notebook sai de `fix/ia-sem-login-e-zai` e volta para `main` — era a pendência número 1 do
`HANDOFF.md`. A branch antiga continua lá, nada é apagado.

```bash
git pull
git log --oneline -5
git status
```

**O que você deve ver:** um `Fast-forward` com a lista dos commits trazidos; no log, o topo da `main`
com os commits da fase (o hash exato pode ser outro — o que importa é **não** ser mais `1eb1a1f` e o
`git status` terminar em `nothing to commit, working tree clean`).

## 3. Dependências — não há nenhuma nova

Esta fase **não adiciona dependência nenhuma**: a porta do MCP usa o `requests` que já está no
`requirements.txt`. `pip install` só é necessário se a venv estiver incompleta por outro motivo. Para
conferir:

```bash
cd ~/monitor_concursos_ti
.venv/bin/python -c "import requests; print('requests', requests.__version__)"
```

**O que você deve ver:** `requests 2.<versão>` (qualquer versão atual serve; não instale nada).

## 4. Configuração — o trecho da TI no arquivo de segredos

O arquivo de segredos é editado por você, no notebook. Este documento mostra **somente** o trecho do
`MONITOR_TARGETS_JSON`; `TELEGRAM_TOKEN`, `ZAI_API_KEY` e as demais chaves do arquivo não aparecem
aqui e não precisam ser coladas em lugar nenhum. Chave e token quem grava é você.

Primeiro, uma cópia de segurança (fica na sua home, fora do repo):

```bash
cp ~/concursos-secrets/monitor.env ~/concursos-secrets/monitor.env.bak-$(date +%F)
ls ~/concursos-secrets/
```

**O que você deve ver:** na listagem, o `monitor.env` original e o novo `monitor.env.bak-AAAAMMDD`.

Abra o arquivo e edite **somente o objeto da área TI** dentro da linha `MONITOR_TARGETS_JSON`:

```bash
nano ~/concursos-secrets/monitor.env
```

O objeto da TI passa a ser este (emplaceie o objeto inteiro; `chat_ids` mantém o valor que já está no
seu arquivo — o que está abaixo é só o formato):

```json
{"area": "TI", "display_name": "Tecnologia da Informacao", "url": "https://blog.grancursosonline.com.br/concursos-ti/", "chat_ids": ["SEU_CHAT_ID"], "keywords_include": ["ti", "tecnologia", "informacao", "sistemas"], "keywords_exclude": ["sociologia", "artes", "pedagogia"], "pci_mcp": true, "pci_mcp_cargos": ["analista de sistemas", "tecnologia da informacao", "desenvolvedor", "programador", "tecnico em informatica", "informatica", "analista de dados", "ciencia da computacao", "banco de dados", "redes", "suporte tecnico", "computacao", "software"], "filtro_salarial": "ativo", "corte_fora_sul": 10000, "ufs_sem_corte": ["PR", "SC", "RS"], "esferas_sem_corte": ["federal"], "cargos_total_inflado": 10, "resumo_filtrados": "semanal"}
```

O que mudou no objeto da TI:

- **`pci_mcp: true`** com os **13 termos de cargo** em `pci_mcp_cargos` — a porta nova, padrão do PCI;
- **`filtro_salarial: "ativo"`** com **`corte_fora_sul: 10000`** — a elegibilidade ligada na TI;
- **`resumo_filtrados: "semanal"`** — o resumo do que foi filtrado, uma vez por semana;
- **`pci_slugs` e `pci_nacional` saem do objeto** (removidos; vazio e desligado é o padrão) — as
  portas de HTML viram reserva, desligáveis de volta a qualquer hora (seção 7);
- `ufs_sem_corte`, `esferas_sem_corte` e `cargos_total_inflado` estão escritos com os valores padrão
  — se o seu arquivo não os tiver, podem ficar de fora; estão aí para não ter dúvida.

As áreas **EDUCACAO e SOCIOLOGIA_ARTES ficam exatamente como estão**: nenhuma chave nova, `pci_slugs`
e o resto do que já está lá continuam. Fora do objeto da TI, não mexa em nada — em particular, as
linhas de `TELEGRAM_TOKEN`, `LLM_MODEL`, `ZAI_API_KEY` e companhia não mudam.

**A linha `MONITOR_TARGETS_JSON` continua sendo uma única linha.** O `python-dotenv` não aceita valor
multilinha: se o JSON quebrar em várias linhas, o carregamento falha em silêncio e o bot cai no modo
legado de área única.

Salve e valide o JSON antes de seguir:

```bash
cd ~/monitor_concursos_ti
.venv/bin/python - <<'PY'
import json, os
from dotenv import dotenv_values
vals = dotenv_values(os.path.expanduser("~/concursos-secrets/monitor.env"))
areas = json.loads(vals["MONITOR_TARGETS_JSON"])
ti = next(a for a in areas if a["area"] == "TI")
assert ti["pci_mcp"] is True
assert ti["filtro_salarial"] == "ativo"
assert ti["corte_fora_sul"] == 10000
assert ti["resumo_filtrados"] == "semanal"
assert len(ti["pci_mcp_cargos"]) == 13
assert not ti.get("pci_slugs")
assert not ti.get("pci_nacional")
print("config ok:", [a["area"] for a in areas])
PY
```

**O que você deve ver:** `config ok: ['TI', 'EDUCACAO', 'SOCIOLOGIA_ARTES']`. Qualquer `AssertionError`
ou erro de JSON significa linha quebrada ou objeto da TI mal colado — corrija antes de seguir, porque
config inválida derruba o modo multi-área em silêncio (cai para o legado de uma área só).

## 5. Ensaio — a rodada de mentirinha

O `--dry-run` varre tudo como produção, decide de verdade, e **não grava nada no banco e não envia
nada ao Telegram**. É o ensaio que prova o filtro antes da primeira rodada real:

```bash
cd ~/monitor_concursos_ti
MONITOR_ENV_FILE=$HOME/concursos-secrets/monitor.env .venv/bin/python main.py --dry-run > /tmp/dry-run-monitor.log 2>&1; echo "exit=$?"
```

**O que você deve ver:** `exit=0` (pode demorar alguns minutos; o Gran ainda fala com a LLM).

Agora as conferências do ensaio, no log capturado:

```bash
grep -c "FILTRADO" /tmp/dry-run-monitor.log
```

**O que você deve ver:** um número maior que zero. Na medida de 22/11/2026 havia 44 concursos fora do
Sul com teto abaixo do corte; o número do dia pode ser outro.

```bash
grep "FILTRADO" /tmp/dry-run-monitor.log | grep -vE "abaixo_do_corte|municipal_inflado"
```

**O que você deve ver:** **nada**. Todo concurso filtrado tem de estar marcado com `abaixo_do_corte`
ou `municipal_inflado`. Se aparecer um `sul` ou `federal` aqui, o filtro está julgando mal: pare,
restaure o backup da seção 4 e volte à seção 3 do roteiro para investigar antes de qualquer rodada
real. (O grep que não acha nada sai sem imprimir e com código 1 — isso aqui é o bom resultado.)

```bash
grep -E "🆕|🔔" /tmp/dry-run-monitor.log | head -15
```

**O que você deve ver:** cards de novo concurso e de atualização entrando — entre eles, concursos do
Sul (PR/SC/RS no nome, UFPR, IFSC, prefeituras gaúchas) e federais (IF, universidade federal, TRF).
Conferir de olho: **Sul e federal entrando; municipal inflado e teto abaixo do corte ficando de fora;
nenhum concurso do Sul na lista de filtrados**.

## 6. A primeira rodada real — e o que conferir depois

O cron roda de hora em hora, no minuto 20. Para não esperar o próximo tick, rode o mesmo comando que
o cron roda. O `rm` abaixo é só para a rodada não ser pulada caso o código antigo já tenha concluído
uma varredura com sucesso hoje — o marcador do dia faz o script sair sem rodar:

```bash
cd ~/monitor_concursos_ti
rm -f logs/.last_success_date
scripts/run_daily.sh
```

**O que você deve ver:** o terminal fica quieto (o script manda tudo direto para o log do dia) e
demora de alguns minutos até ~20 (o Gran fala com a LLM). Terminado, confira, na ordem:

```bash
tail -2 logs/run_$(date +%Y%m%d).log
```

**O que você deve ver:** `===== exit=0 AAAA-MM-DD HH:MM:SS =====`. Esse `exit=0` é o sinal de rodada
completa; `exit=1` significa falha e o catch-up horário vai tentar de novo sozinho — investigue o log
antes de qualquer coisa.

```bash
cat logs/.last_success_date
```

**O que você deve ver:** a data de hoje, no formato AAAAMMDD (ex.: `20261124`).

```bash
grep -c "🔑" logs/run_$(date +%Y%m%d).log
```

**O que você deve ver:** `0` — nenhum alerta de chave. Se der outro número, a credencial da LLM caiu:
o remédio está descrito no `HANDOFF.md`, e a rodada de hoje não é culpada.

```bash
grep "FILTRADO" logs/run_$(date +%Y%m%d).log | grep -vE "abaixo_do_corte|municipal_inflado"
```

**O que você deve ver:** **nada** (mesma conferência do ensaio, agora na rodada real).

E no Telegram: o primeiro card da área TI depois do deploy deve chegar **sem o ruído de fora do Sul**
— sem prefeitura fora do Sul com teto baixo, sem municipal inflado. Concurso do Sul e federal
continuam chegando como sempre chegaram. O resumo semanal dos filtrados (`🔁 Resumo de filtrados`)
chega uma vez por semana, no fim da rodada que fecha a semana; semana sem nada filtrado não manda
mensagem.

## 7. Depois — o retrato de novo, e a comparação

```bash
cd ~/monitor_concursos_ti
bash scripts/diagnostico_producao.sh | tee ~/diagnostico-monitor-depois-$(date +%F).txt
```

**O que você deve ver:** as mesmas seções do "antes", agora com a rodada nova dentro. Compare com o
arquivo `~/diagnostico-monitor-antes-AAAAMMDD.txt` guardado na seção 1 — o que **deve** ter mudado:
o último sucesso apontando para hoje, a porta `pci_mcp` presente na contagem por fonte e nos dias de
saúde, e nenhuma seção de erro nova. Diferença fora disso merece olhar antes de encerrar o dia.

## 8. Como voltar atrás

Se o filtro ou a porta nova precisarem ser desligados, não há deploy de código e não há nada para
mexer no banco: edite de novo o objeto da TI no `~/concursos-secrets/monitor.env` (seção 4), trocando
`filtro_salarial` para `"desligado"` e `pci_mcp` para `false` — e repondo `pci_slugs` e
`pci_nacional` com os valores de antes, que estão no backup `monitor.env.bak-AAAAMMDD` feito na
seção 4. Nada mais muda: as colunas novas do banco (região, teto, elegibilidade e motivo) ficam
gravadas e são simplesmente ignoradas com o filtro desligado; o que já foi visto continua visto
(nada se renotifica), e a rodada seguinte — no máximo uma hora depois, pelo cron — volta a se
comportar como antes da fase. Para conferir o retorno, rode o ensaio da seção 5 de novo: nele não
aparece linha de `FILTRADO` e as portas de HTML do PCI voltam a aparecer na varredura.

## 9. O que o Lucas faz — e o que ele não faz

- **Faz você:** editar o arquivo de segredos no nano, gravar e trocar credenciais quando precisar
  (com `read -s`, como no `HANDOFF.md` — quem grava chave é você), rodar os comandos deste roteiro e
  julgar o que chega no Telegram.
- **Não faz ninguém:** nenhum passo deste roteiro pede que um agente escreva, cole ou mova credencial
  (regra do `kanban/REGRAS.md`). Segredo nenhum entra no repo nem no log — o formatador de logs já
  limpa token da saída, e este documento mostra só nomes de chave, nunca valores. Se um agente pedir
  um token, a resposta é não.
