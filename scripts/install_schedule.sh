#!/usr/bin/env bash
# Instala o agendamento diario via cron (equivalente Linux do install_schedule.ps1).
#
# Estrategia: o cron chama scripts/run_daily.sh de hora em hora entre 08:05 e
# 22:05. O proprio run_daily.sh garante UMA varredura por dia (marker de
# sucesso) — os ticks seguintes sao catch-up para o caso de o computador
# estar desligado/suspenso no primeiro horario.
#
# Uso:
#   ./scripts/install_schedule.sh            # instala (idempotente)
#   ./scripts/install_schedule.sh --remove   # remove a entrada
#   crontab -l                               # inspecionar

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO_DIR/scripts/run_daily.sh"
TAG="# monitor_concursos_ti"
ENTRY="5 8-22 * * * $SCRIPT $TAG"

chmod +x "$SCRIPT"

ATUAL="$(crontab -l 2>/dev/null || true)"
SEM_ENTRADA="$(printf '%s\n' "$ATUAL" | grep -vF "$TAG" || true)"

if [[ "${1:-}" == "--remove" ]]; then
    printf '%s\n' "$SEM_ENTRADA" | crontab -
    echo "Entrada do monitor removida do crontab."
    exit 0
fi

printf '%s\n%s\n' "$SEM_ENTRADA" "$ENTRY" | sed '/^$/d' | crontab -
echo "Agendamento instalado:"
echo "  $ENTRY"
echo "Uma varredura por dia, primeira tentativa 08:05, catch-up de hora em hora ate 22:05."
