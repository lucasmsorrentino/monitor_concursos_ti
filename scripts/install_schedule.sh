#!/usr/bin/env bash
# Instala o agendamento via cron (equivalente Linux do install_schedule.ps1).
#
# DE HORA EM HORA, nao mais uma vez por dia. O run_daily.sh e idempotente: se a
# varredura de hoje ja concluiu com sucesso, o tick sai em tres linhas. O flock
# impede duas varreduras simultaneas.
#
# Por que mudou (2026-08-08): cron nao tem catch-up, entao horario perdido era
# dia perdido. Entre 01/07 e 08/08, NOVE dias nao tiveram varredura nenhuma, com
# correlacao de 100% com o notebook desligado as 03h BRT (conferido em
# `journalctl --list-boots`). Rodar de hora em hora faz a primeira hora com a
# maquina ligada pegar o dia. Mesmo padrao `--if-needed` do ~/aios-sync/sync.sh.
#
# A entrada @reboot complementa: quando a maquina volta depois de dias fora, a
# varredura (e o alerta de atraso do dead-man) sai na hora, sem esperar o :MM.
#
# Uso:
#   ./scripts/install_schedule.sh            # instala de hora em hora, no minuto 20
#   ./scripts/install_schedule.sh 40         # outro minuto da hora
#   ./scripts/install_schedule.sh --remove   # remove as entradas
#   crontab -l                               # inspecionar

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO_DIR/scripts/run_daily.sh"
TAG="# monitor_concursos_ti"
MINUTO="${1:-20}"

chmod +x "$SCRIPT"

ATUAL="$(crontab -l 2>/dev/null || true)"
SEM_ENTRADA="$(printf '%s\n' "$ATUAL" | grep -vF "$TAG" || true)"

if [[ "$MINUTO" == "--remove" ]]; then
    printf '%s\n' "$SEM_ENTRADA" | sed '/^$/d' | crontab -
    echo "Entradas do monitor removidas do crontab."
    exit 0
fi

if [[ ! "$MINUTO" =~ ^([0-9]|[1-5][0-9])$ ]]; then
    echo "Minuto invalido: '$MINUTO' (use 0-59, ex: 20)" >&2
    exit 1
fi

ENTRY_HORARIA="$MINUTO * * * * $SCRIPT $TAG"
ENTRY_BOOT="@reboot $SCRIPT $TAG (boot)"

printf '%s\n%s\n%s\n' "$SEM_ENTRADA" "$ENTRY_HORARIA" "$ENTRY_BOOT" | sed '/^$/d' | crontab -
echo "Agendamento instalado (catch-up de hora em hora + no boot):"
echo "  $ENTRY_HORARIA"
echo "  $ENTRY_BOOT"
echo
echo "O tick so faz trabalho se a varredura de hoje ainda nao concluiu."
