# Handoff — IA destravada e heartbeat diário em produção (22/10/2026, 17h05)

> Para o próximo agente. Estado verificado no notebook de produção em 22/10/2026, às 17:02.
> O handoff anterior (16h), com a linha do tempo completa do incidente, está em `git show 281b12f:HANDOFF.md`.

## 1. Resumo

- **Causa raiz da LLM resolvida às 17:01.** A chave z.ai tinha sido gerada na seção do plano **padrão** de API; o crédito do Lucas é o **Coding Plan**, que só vale para chaves criadas em `https://z.ai/manage-apikey/apikey-list` (mesma conta do plano). Chave do plano padrão = válida, mas sem pacote → `1113 Insufficient balance or no resource package` em qualquer endpoint (geral, coding OpenAI e coding Anthropic — todos testados). O Lucas gravou a chave nova em `~/concursos-secrets/monitor.env` (com `read -s`; vale a **última** linha `ZAI_API_KEY`) e `main.py --testar-llm` passou: resposta em 4 s, `exit=0`.
- **Nada mais mudou na configuração**: `LLM_MODEL=zai/glm-5.3-flash`, `LLM_REASONING_EFFORT=low`, `LLM_API_BASE=https://api.z.ai/api/coding/paas/v4`. Era só a chave.
- **Heartbeat diário em produção** (commits `96e3d92` código + `62960b4` docs, na branch `fix/ia-sem-login-e-zai`, deployados no notebook): o "✅ Varredura Concluída" agora sai **1×/dia por área** pelo `_alerta_uma_vez_por_dia` (marcador `logs/.alerta_<area>_heartbeat`). O spam de 45–48/dia no chat de Educação/Soc-Artes (uma área falhando fazia o catch-up horário reenviar o heartbeat das áreas sadias) acabou. Suíte: **296 verdes** (Windows e notebook).
- **Varredura de retomada** lançada às 17:02 (nohup no notebook, PID na época 3082591). Ela notifica o represado desde 23/09 (Gran + lista nacional) que ainda estiver publicado (primeiro 🆕: TCE SP). Se ela falhar, o cron das `20 * * * *` cobre: sucesso grava `logs/.last_success_date` e os ticks seguintes do dia viram no-op de 3 linhas.
- **Conferir depois**: `exit=0` no fim de `logs/run_20261022.log`; `logs/.last_success_date` = `20261022`; nenhum 🔑 no log.

## 2. Acesso e onde as coisas estão

| O quê | Onde |
| :--- | :--- |
| Máquina de produção | Notebook Linux `lucas-inspiron-3583`, Tailscale `100.98.50.59` — **autossuficiente**: nada depende da máquina Windows |
| SSH (do Windows) | `ssh -i ~/.ssh/fleet_ed25519 -o IdentitiesOnly=yes lucas@100.98.50.59` |
| Repo em produção | `~/monitor_concursos_ti` (venv em `.venv`), branch `fix/ia-sem-login-e-zai` |
| Segredos | `~/concursos-secrets/monitor.env`, **fora do repo** (montado rw no container do Hermes) |
| Agendamento | crontab: `20 * * * *` + `@reboot` → `scripts/run_daily.sh` (marcador diário + `flock` + dead-man) |
| Logs | `~/monitor_concursos_ti/logs/run_YYYYMMDD.log` |

## 3. Pendências (por prioridade)

1. **Mesclar `fix/ia-sem-login-e-zai` em `main`** (fast-forward) — pendendo o OK do Lucas. Depois, voltar o notebook para `main`. A operação não depende disso: o notebook roda a branch.
2. **Token do bot do Telegram vazou** em 9 logs antigos (25/09–02/10) dentro de `~/monitor_concursos_ti/logs/`. O Lucas precisa rotacionar no BotFather e atualizar `TELEGRAM_TOKEN` no `monitor.env` **e** em `~/aios-heartbeat.env` no Windows. Opcional, com o OK dele: limpar os logs antigos (`grep -l "/bot[0-9]\+:" logs/*.log`). Logs novos já saem limpos (`FormatterSemSegredos`).
3. **Chave antiga do z.ai** (`579e...`, do plano padrão): ficou como linha morta no `monitor.env` (a última linha é a que vale) e foi colada no chat em 22/10. Inofensiva (sem plano, sem saldo), mas pode ser removida do arquivo e revogada no painel.
4. **Fase 0 do plano** (`PLANO_EVOLUCAO_AGENTICA.md` v2) liberada agora que a varredura voltou a completar.

## 4. Regras que valem aqui

- **Chaves e tokens o Lucas grava**, com `read -s`. O agente não insere credenciais.
- Segredos nunca entram no repo nem nos logs.
- `run_daily.sh` é chamado direto pelo cron: mudança no conteúdo vale na hora; mudança de **horário** exige rodar o instalador e conferir `crontab -l`.
- Código, logs e mensagens em português do Brasil. Ver `CLAUDE.md`.
