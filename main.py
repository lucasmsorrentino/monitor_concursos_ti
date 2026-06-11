"""Ponto de entrada do Monitor de Concursos.

Executa uma unica varredura em todas as areas configuradas e encerra.
O agendamento diario e feito externamente (Windows Task Scheduler no Windows,
cron no Linux/Mac) — veja scripts/install_schedule.ps1.

Exit codes:
    0 — execucao concluida (mesmo que sem novidades)
    1 — erro critico (sem alvos validos, falha catastrofica)
"""

import logging
import os
import sys

from dotenv import load_dotenv

from config.loader import load_monitor_targets
from src.core.bot import ConcursoBot
from src.core.multi_area_runner import MultiAreaRunner
from src.utils.logger import setup_logger

load_dotenv()
setup_logger()
logger = logging.getLogger(__name__)


def _get_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        logger.warning(f"Valor invalido para {name}; usando padrao {default}.")
        return default


def _get_float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        logger.warning(f"Valor invalido para {name}; usando padrao {default}.")
        return default


def build_bots() -> list[ConcursoBot]:
    """Carrega alvos do .env e instancia um ConcursoBot por area."""
    base_config = {
        "token": os.getenv("TELEGRAM_TOKEN"),
        "ollama_model": os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL", "llama3.1"),
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        "ollama_timeout_s": _get_float_env("OLLAMA_TIMEOUT_S", 120.0),
        "ollama_retries": _get_int_env("OLLAMA_RETRIES", 2),
        "ollama_retry_delay_s": _get_float_env("OLLAMA_RETRY_DELAY_S", 2.0),
    }

    targets = load_monitor_targets(logger)
    bots: list[ConcursoBot] = []

    for target in targets:
        config = {
            **base_config,
            **target,
            "chat_id": (target.get("chat_ids") or [None])[0],
        }

        if not config.get("url_alvo"):
            logger.warning(f"URL ausente para area {config.get('area', 'N/A')}; alvo ignorado.")
            continue

        if not config.get("token") or not config.get("chat_ids"):
            logger.warning(
                f"Telegram incompleto para area {config.get('area', 'N/A')}; notificacoes serao puladas."
            )

        bots.append(ConcursoBot(config))

    return bots


def main() -> int:
    logger.info("Sistema de Monitoramento iniciado (modo single-run).")

    bots = build_bots()
    if not bots:
        logger.error("Nenhum alvo valido configurado. Verifique URL_ALVO ou MONITOR_TARGETS_JSON.")
        return 1

    try:
        runner = MultiAreaRunner(bots)
        runner.executar()
        logger.info("Varredura concluida com sucesso.")
        return 0
    except Exception as e:
        logger.critical(f"Falha catastrofica durante a varredura: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
