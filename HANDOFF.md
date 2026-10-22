# Handoff — IA do monitor parada (22/10/2026, 16h)

> Para o próximo agente. Estado verificado no notebook de produção em 22/10/2026, às 16:04. Revalide antes de agir (§2).

## 1. Resumo

- **Nenhuma varredura completa desde 23/09/2026** (`logs/.last_success_date` = `20260923`).
- A causa é a **LLM**:
  - **Parado:** blog do Gran e lista nacional do PCI, porque dependem de IA. Nada novo dessas fontes chegou desde 23/09.
  - **Funcionando:** PCI por cargo, porque não usa IA. Os 🆕 dele continuam saindo.
- **O código está pronto e publicado.** O notebook roda a branch `fix/ia-sem-login-e-zai`, ainda não mesclada em `main`.
- **O que bloqueia é a conta.** A LLM configurada é o z.ai (`zai/glm-5.3-flash`, via endpoint do Coding Plan). A chave gravada responde `1113 Insufficient balance or no resource package` em todos os endpoints e modelos pagos (§5).
- **Próximo passo:** destravar a credencial por um dos caminhos da §6, rodar `--testar-llm` e depois uma varredura real (§7).

## 2. Acesso e onde as coisas estão

| O quê | Onde |
| :--- | :--- |
| Máquina de produção | Notebook Linux `lucas-inspiron-3583`, Tailscale `100.98.50.59` |
| SSH (do Windows NOACORE) | `ssh -i ~/.ssh/fleet_ed25519 -o IdentitiesOnly=yes lucas@100.98.50.59`. A chave `id_ed25519` é recusada; pelo nome Tailscale dá "Host key verification failed" |
| Repo em produção | `~/monitor_concursos_ti` (venv em `.venv`), branch `fix/ia-sem-login-e-zai` |
| Segredos | `~/concursos-secrets/monitor.env`, **fora do repo**: o repo é montado rw no container do Hermes, alcançável pelo Telegram |
| Agendamento | crontab: `20 * * * *` + `@reboot` → `scripts/run_daily.sh` (marcador diário + `flock` + dead-man) |
| Logs | `~/monitor_concursos_ti/logs/run_YYYYMMDD.log` |

## 3. Linha do tempo do incidente

| Período | O que houve | Evidência |
| :--- | :--- | :--- |
| até 23/09 | Normal | último `exit=0` |
| 24/09 | OAuth do `claude` expirou | 5.706 falhas `claude -p saiu com codigo 1:` no dia |
| 25/09–02/10 | Notebook sem DNS: nada resolvia, nem PCI nem Telegram | `Temporary failure in name resolution` |
| 03/10 | OAuth falhando de novo | 1.026 falhas |
| 04/10–13/10 | Notebook desligado | sem log |
| 14/10–22/10 | OAuth falhando de hora em hora | por dia: ~6.800 falhas, 24 🚨 "Varredura incompleta" e 24 ⏰ "sem rodar" para o Lucas, e 45–48 "✅ Varredura Concluída" no chat de Educação/Soc-Artes (§8.1) |
| 22/10 | Diagnóstico, correções publicadas, troca para o z.ai | este documento |

O erro do `claude` ("Failed to authenticate: OAuth session expired and could not be refreshed") sai no **stdout**, e o backend antigo só lia o stderr. Por isso o log nunca mostrou o motivo.

## 4. O que já foi feito (branch `fix/ia-sem-login-e-zai`, no GitHub e no notebook)

| Commit | Conteúdo |
| :--- | :--- |
| `c8ae67f` | Plano de evolução v2 (`PLANO_EVOLUCAO_AGENTICA.md`) |
| `29075ef` | Falha de credencial vira o alerta 🔑 com fail-fast (sem retry); alertas 🚨, de falha e ⏰ limitados a 1 por dia; token do Telegram apagado dos logs (`FormatterSemSegredos`); backend z.ai via LiteLLM; `main.py --testar-llm` |
| `84c7b7d` | Chave ausente (`InternalServerError: Missing credentials`) também conta como falha de credencial |

**Verificado em produção (varredura das 15:20):**
- Saiu 1 ⏰ e 1 🔑, só no chat de TI; Educação registrou "já enviado hoje".
- A rodada levou 3 minutos, contra 13 antes, porque a IA para na primeira recusa.
- 295 testes passando.

## 5. Estado da LLM agora

Linhas de LLM do `monitor.env` (o valor da chave omitido):

```
# LLM_MODEL=claude-cli:haiku   # trocado pelo z.ai em 22/10/2026 (OAuth do claude expirou)
LLM_MODEL=zai/glm-5.3-flash
LLM_REASONING_EFFORT=low
ZAI_API_KEY=<presente, 49 caracteres, formato id.segredo>
LLM_API_BASE=https://api.z.ai/api/coding/paas/v4
```

O backup de antes da troca está em `~/concursos-secrets/monitor.env.bak-20261022-claude-cli`.

**Diagnóstico** (`scripts/diagnostico_zai.py`, chamadas diretas, sem LiteLLM):

| Endpoint | glm-5.3-flash | glm-5.3 | glm-4.7 | glm-4.5-air | glm-4.7-flash / 4.5-flash (grátis) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| geral `/api/paas/v4` | 429 · 1113 | 1113 | 1113 | 1113 | ✅ respondem, mas ~50 s por chamada, depois "overloaded" e "Rate limit reached" |
| Coding Plan `/api/coding/paas/v4` | 429 · 1113 | 1113 | 1113 | 1113 | — |

**Leitura:**
- A chave é **válida**: chave errada daria 401, e uma chave falsa dá "token expired or incorrect".
- Mas a conta dessa chave **não tem saldo nem pacote/plano** que o z.ai reconheça.
- O Lucas diz que tem crédito no z.ai, sem uso. Então o crédito provavelmente está em outra conta ou organização, no open.bigmodel.cn (plataforma chinesa, com chaves separadas), ou num plano vencido ou não ativado.

**Os grátis não servem para produção.** Uma varredura faz ~95 chamadas (TI 49 + Educação 46; Soc/Artes filtra tudo antes da IA). A 50 s cada, com limite de taxa, dá mais de 80 min e muitos erros.

## 6. Caminhos para destravar (decisão do Lucas)

**A. Chave da conta certa / plano ativo no z.ai.** O Lucas confere no painel do z.ai a conta da chave. Se trocar a chave, ele mesmo grava (§9):

```bash
ssh -t -i ~/.ssh/fleet_ed25519 lucas@100.98.50.59 'read -rsp "Chave z.ai: " K && echo && printf "ZAI_API_KEY=%s\n" "$K" >> ~/concursos-secrets/monitor.env && unset K && echo "gravada"'
```

- Vale a última linha `ZAI_API_KEY` do arquivo.
- Se o crédito for **saldo pago por uso** (não Coding Plan), remover a linha `LLM_API_BASE`.
- Nota: a política do Coding Plan restringe o uso a ferramentas suportadas (docs.z.ai/devpack/usage-policy). O Lucas foi avisado em 22/10 e decidiu usar mesmo assim. Não reabrir a discussão.

**B. Voltar ao `claude -p`.** Não tem custo extra, porque usa a assinatura do Lucas.
1. O Lucas roda `claude setup-token` no notebook. É interativo e pede login no navegador.
2. Ele grava o token como `CLAUDE_CODE_OAUTH_TOKEN=...` no `monitor.env`. O `main.py` carrega o arquivo no ambiente, e o subprocesso `claude` herda.
3. Descomentar `LLM_MODEL=claude-cli:haiku` e comentar as linhas do z.ai.

O token de longa duração evita a expiração que causou o incidente.

**C. Saldo pago por uso no z.ai** e remover `LLM_API_BASE`. Estimativa não medida: US$ 2–3/mês com `glm-5.3-flash` e `reasoning_effort=low`.

**D. OpenCode Go:**

```
LLM_MODEL=openai/glm-5.3-flash
LLM_API_BASE=https://opencode.ai/inference/go/openai/v1
LLM_API_KEY=<chave>
```

Os termos dizem que o serviço é feito para agentes de código.

## 7. Como validar depois de destravar

1. Teste rápido, uma chamada real; tem que sair `exit 0` e `✅ A LLM respondeu`:

```bash
cd ~/monitor_concursos_ti && MONITOR_ENV_FILE=~/concursos-secrets/monitor.env .venv/bin/python main.py --testar-llm
```

2. Para descartar código e ver só a conta: `.venv/bin/python scripts/diagnostico_zai.py`.
3. Varredura real: `scripts/run_daily.sh`. O `flock` impede rodar junto com o cron. Ela vai **notificar o represado desde 23/09** (Gran + nacional) que ainda estiver publicado.
4. Conferir:
   - `exit=0` no fim de `logs/run_YYYYMMDD.log`;
   - `logs/.last_success_date` com a data de hoje;
   - nenhum 🔑.

## 8. Pendências (por prioridade)

1. **Heartbeat de hora em hora para a Tatiana (spam).**
   - **Causa:** Sociologia/Artes não usa IA e termina bem, mas a rodada falha (TI/Educação), então não há marcador de sucesso e o cron repete. A cada repetição ela manda "✅ Varredura Concluída" para o chat de Educação/Soc-Artes: 45–48 por dia desde 15/10.
   - **Some** quando a varredura voltar a completar.
   - **Conserto estrutural sugerido:** heartbeat no máximo 1 por dia por área (marcador como o de `_alerta_uma_vez_por_dia`), ou só na primeira rodada do dia.
2. **Token do bot do Telegram vazou** em 9 logs (25/09–02/10) dentro de `~/monitor_concursos_ti/logs/`, pasta montada no Hermes.
   - O Lucas precisa rotacionar no BotFather e atualizar `TELEGRAM_TOKEN` no `monitor.env` **e** em `~/aios-heartbeat.env` no Windows (o heartbeat do AIOS reutiliza esse token).
   - Opcional, com o ok do Lucas: limpar os logs antigos (`grep -l "/bot[0-9]\+:" logs/*.log`).
   - Logs novos já saem limpos.
3. **A chave do z.ai foi colada no chat** em 22/10. Considerar gerar outra.
4. **Mesclar `fix/ia-sem-login-e-zai` em `main`** (fast-forward) com o ok do Lucas. Depois, voltar o notebook para `main`.
5. **Fase 0 do plano** (`PLANO_EVOLUCAO_AGENTICA.md` v2) depende de a varredura voltar a completar.

## 9. Regras que valem aqui

- **Chaves e tokens o Lucas grava**, com o comando `read -s` da §6. O agente não insere credenciais.
- Segredos nunca entram no repo nem nos logs.
- `run_daily.sh` é chamado direto pelo cron: mudança no conteúdo vale na hora. Mudança de **horário** exige rodar o instalador e conferir `crontab -l`.
- Código, logs e mensagens em português do Brasil. Ver `CLAUDE.md`.
