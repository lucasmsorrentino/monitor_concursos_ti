#!/usr/bin/env bash
# Instala o agendamento diario via cron (equivalente Linux do install_schedule.ps1).
#
# Uma execucao por dia, de madrugada (03:00 por padrao). O run_daily.sh
# mantem um marker de sucesso diario e um flock, entao rodadas manuais no
# mesmo dia nao duplicam varredura nem colidem com o cron.
#
# Atencao: cron nao tem catch-up — se o computador estiver desligado ou
# suspenso no horario, a varredura do dia nao acontece.
#
# Uso:
#   ./scripts/install_schedule.sh            # instala as 03:00 (idempotente)
#   ./scripts/install_schedule.sh 04:30      # instala em outro horario
#   ./scripts/install_schedule.sh --remove   # remove a entrada
#   crontab -l                               # inspecionar

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO_DIR/scripts/run_daily.sh"
TAG="# monitor_concursos_ti"
HORARIO="${1:-03:00}"

chmod +x "$SCRIPT"

ATUAL="$(crontab -l 2>/dev/null || true)"
SEM_ENTRADA="$(printf '%s\n' "$ATUAL" | grep -vF "$TAG" || true)"

if [[ "$HORARIO" == "--remove" ]]; then
    printf '%s\n' "$SEM_ENTRADA" | crontab -
    echo "Entrada do monitor removida do crontab."
    exit 0
fi

if [[ ! "$HORARIO" =~ ^([01]?[0-9]|2[0-3]):[0-5][0-9]$ ]]; then
    echo "Horario invalido: '$HORARIO' (use HH:MM, ex: 03:00)" >&2
    exit 1
fi

HORA="${HORARIO%%:*}"
MINUTO="${HORARIO##*:}"
ENTRY="$MINUTO $HORA * * * $SCRIPT $TAG"

printf '%s\n%s\n' "$SEM_ENTRADA" "$ENTRY" | sed '/^$/d' | crontab -
echo "Agendamento instalado (1x por dia):"
echo "  $ENTRY"
