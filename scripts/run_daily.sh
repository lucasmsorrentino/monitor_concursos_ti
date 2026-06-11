#!/usr/bin/env bash
# Executa uma varredura diaria do monitor (equivalente Linux do run_daily.bat).
#
# Desenhado para ser chamado de hora em hora pelo cron (ver install_schedule.sh):
# - Se a varredura de HOJE ja foi concluida com sucesso, sai imediatamente.
#   Isso reproduz o catch-up do Windows Task Scheduler (StartWhenAvailable):
#   se a maquina estava desligada no primeiro horario, roda na proxima hora.
# - flock impede duas varreduras simultaneas (MultipleInstances=IgnoreNew).
# - stdout/stderr vao para logs/run_YYYYMMDD.log (um arquivo por dia).

set -u

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$REPO_DIR/logs"
HOJE="$(date +%Y%m%d)"
LOG_FILE="$LOG_DIR/run_$HOJE.log"
MARKER="$LOG_DIR/.last_success_date"
LOCK="$LOG_DIR/.run_daily.lock"

# Cron tem PATH minimo; o backend claude-cli precisa do `claude` em ~/.local/bin.
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

mkdir -p "$LOG_DIR"

# Ja rodou com sucesso hoje? Entao este tick do cron e so catch-up — sai quieto.
if [[ -f "$MARKER" && "$(cat "$MARKER")" == "$HOJE" ]]; then
    exit 0
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
    if [[ $EXIT -eq 0 ]]; then
        echo "$HOJE" > "$MARKER"
    fi
    exit $EXIT
} >> "$LOG_FILE" 2>&1
