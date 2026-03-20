import os
import logging
from dotenv import load_dotenv
from src.utils.logger import setup_logger
from src.core.bot import ConcursoBot
from src.core.multi_area_runner import MultiAreaRunner
from src.scheduler.runner import DailyScheduler 
from config.loader import load_monitor_targets

# Carrega as variáveis do arquivo .env
load_dotenv()
setup_logger() # Inicializa o sistema de logs
logger = logging.getLogger(__name__)


def _get_int_env(name: str, default: int) -> int:
    """Lê inteiro do .env com fallback seguro para evitar ValueError."""
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        logger.warning(f"Valor inválido para {name}; usando padrão {default}.")
        return default


def _get_float_env(name: str, default: float) -> float:
    """Lê float do .env com fallback seguro para evitar ValueError."""
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        logger.warning(f"Valor inválido para {name}; usando padrão {default}.")
        return default

def main():
    logger.info("🎬 Sistema de Monitoramento Iniciado.") 
    base_config = {
        "token": os.getenv("TELEGRAM_TOKEN"),
        "ollama_model": os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL", "llama3.1"),
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        "ollama_timeout_s": _get_float_env("OLLAMA_TIMEOUT_S", 120.0),
        "ollama_retries": _get_int_env("OLLAMA_RETRIES", 2),
        "ollama_retry_delay_s": _get_float_env("OLLAMA_RETRY_DELAY_S", 2.0),
        "horario_execucao": os.getenv("HORARIO_EXECUCAO", "08:00")
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

    if not bots:
        logger.error("❌ Nenhum alvo valido configurado. Verifique URL_ALVO ou MONITOR_TARGETS_JSON.")
        return

    runner = MultiAreaRunner(bots)
    
    try:
        scheduler = DailyScheduler(runner)
        
        scheduler.agendar_diariamente(base_config["horario_execucao"])
        
        # (Opcional) Executa uma vez ao ligar para garantir que está funcionando
        logger.info("🔄 Executando primeira varredura de inicialização...")
        runner.executar()

        # Início do Loop Infinito (O programa "para" aqui e fica esperando o horário)
        scheduler.iniciar()

    except Exception as e:
        logger.critical(f"Falha catastrófica no sistema: {e}", exc_info=True)


if __name__ == "__main__":
    main()