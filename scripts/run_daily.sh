#!/usr/bin/env bash
# Executa uma varredura diaria do monitor (equivalente Linux do run_daily.bat).
#
# Chamado DE HORA EM HORA pelo cron, nao mais so as 03h (ver install_schedule.sh):
# - Marker de sucesso diario: se a varredura de HOJE ja concluiu com sucesso,
#   sai imediatamente — os ticks restantes do dia sao no-op de 3 linhas.
# - flock impede duas varreduras simultaneas (MultipleInstances=IgnoreNew).
# - stdout/stderr vao para logs/run_YYYYMMDD.log (um arquivo por dia).
#
# Por que de hora em hora: entre 01/07 e 08/08/2026, NOVE dias nao tiveram
# varredura nenhuma. Cruzando com `journalctl --list-boots`, a correlacao com o
# notebook desligado as 03h BRT foi de 100%. Cron nao tem catch-up: horario
# perdido e dia perdido. Mesmo padrao `--if-needed` do ~/aios-sync/sync.sh,
# descrito em references/runbook-conserto-sync.md no vault.
#
# Dead-man's-switch: se a ultima varredura bem-sucedida for antiga demais, avisa
# no Telegram ANTES de comecar. O alarme dispara quando a maquina VOLTA, que e a
# unica hora em que ela pode avisar. Sem isso, o bot ficou morto de 16/07 a
# 08/08 (venv quebrada, exit=127 todo dia) sem ninguem perceber, porque um dia
# sem novidade e um dia quebrado produzem o mesmo silencio.

set -u

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$REPO_DIR/logs"
HOJE="$(date +%Y%m%d)"
LOG_FILE="$LOG_DIR/run_$HOJE.log"
MARKER="$LOG_DIR/.last_success_date"
LOCK="$LOG_DIR/.run_daily.lock"
# Dia do ultimo aviso do dead-man. Sem ele o aviso saia em TODO tick: de 14/10 a
# 22/10/2026 foram 24 "ficou N dias sem rodar" por dia, junto com o alerta do
# proprio bot sobre a mesma falha.
DEAD_MAN_MARK="$LOG_DIR/.last_dead_man_alert"

# Cron tem PATH minimo; o backend claude-cli precisa do `claude` em ~/.local/bin.
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# Segredos ficam FORA do repo: a pasta esta montada rw no container do Hermes, que
# e alcancavel por Telegram. Ver references/hermes-charter.md no vault.
export MONITOR_ENV_FILE="${MONITOR_ENV_FILE:-$HOME/concursos-secrets/monitor.env}"

# Dias tolerados sem varredura antes de alertar. Sobrescrevivel por ambiente.
: "${MONITOR_MAX_DIAS_SEM_RODAR:=2}"

mkdir -p "$LOG_DIR"

# Ja rodou com sucesso hoje? Entao este tick do cron e so catch-up — sai quieto.
if [[ -f "$MARKER" && "$(cat "$MARKER")" == "$HOJE" ]]; then
    exit 0
fi

# --- dead-man's-switch -------------------------------------------------------
# Le TELEGRAM_TOKEN/chat do arquivo de segredos (fora do repo) so pra alertar.
alerta_atraso() {
    local dias="$1"
    local env_file="$MONITOR_ENV_FILE"
    [[ -r "$env_file" ]] || return 0

    local token chat
    token="$(grep -m1 '^TELEGRAM_TOKEN=' "$env_file" | cut -d= -f2- | tr -d '"'"'"' \r')"
    # Primeiro chat_id que aparecer no JSON de alvos serve: o aviso e operacional.
    chat="$(grep -m1 -oE '"chat_ids"\s*:\s*\[\s*"[0-9]+"' "$env_file" | grep -oE '[0-9]+$')"
    [[ -z "$chat" ]] && chat="$(grep -m1 '^TELEGRAM_CHAT_ID=' "$env_file" | cut -d= -f2- | tr -d '"'"'"' \r')"
    [[ -z "$token" || -z "$chat" ]] && return 0

    # "sem varredura completa", e nao "sem rodar": o caso comum e o bot rodar
    # de hora em hora e falhar (ex.: login da LLM caido), nao a maquina desligada.
    curl -s -m 20 -o /dev/null \
        --data-urlencode "text=⏰ O monitor de concursos está há ${dias} dia(s) sem uma varredura completa (último sucesso: ${2}). Ele segue tentando de hora em hora; a causa aparece nos alertas da própria varredura." \
        -d "chat_id=${chat}" \
        "https://api.telegram.org/bot${token}/sendMessage" || true
}

if [[ -f "$MARKER" ]]; then
    ULTIMO="$(cat "$MARKER")"
    if [[ "$ULTIMO" =~ ^[0-9]{8}$ ]]; then
        DIAS=$(( ( $(date +%s) - $(date -d "$ULTIMO" +%s) ) / 86400 ))
        if (( DIAS > MONITOR_MAX_DIAS_SEM_RODAR )) \
            && [[ "$(cat "$DEAD_MAN_MARK" 2>/dev/null)" != "$HOJE" ]]; then
            echo "[dead-man] ultima varredura ok em $ULTIMO ($DIAS dias atras); alertando." >> "$LOG_FILE"
            alerta_atraso "$DIAS" "$ULTIMO"
            echo "$HOJE" > "$DEAD_MAN_MARK"
        fi
    fi
fi

# Lock nao-bloqueante: se um run ainda esta em andamento, ignora este tick.
exec 9>"$LOCK"
if ! flock -n 9; then
    exit 0
fi

{
    echo "===== run_daily.sh $(date '+%Y-%m-%d %H:%M:%S') ====="
    cd "$REPO_DIR" || exit 1
    "$REPO_DIR/.venv/bin/python" main.py
    EXIT=$?
    echo "===== exit=$EXIT $(date '+%Y-%m-%d %H:%M:%S') ====="
    # Ponte pro Hermes: exporta o que o bot conhece pra ~/.hermes (a skill
    # concursos-ti-brasil le isso e so reporta o que esta FORA do bot).
    # `|| true` garante que isso nunca derrube o run do bot.
    "$REPO_DIR/.venv/bin/python" "$REPO_DIR/scripts/export_known.py" || true
    if [[ $EXIT -eq 0 ]]; then
        echo "$HOJE" > "$MARKER"
    fi
    exit $EXIT
} >> "$LOG_FILE" 2>&1
