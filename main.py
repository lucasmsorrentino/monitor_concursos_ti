"""Ponto de entrada do Monitor de Concursos.

Executa uma unica varredura em todas as areas configuradas e encerra.
O agendamento diario e feito externamente (Windows Task Scheduler no Windows,
cron no Linux/Mac) — veja scripts/install_schedule.ps1.

Exit codes:
    0 — execucao concluida (mesmo que sem novidades)
    1 — erro critico, OU qualquer area que falhou no meio da varredura

O segundo caso importa: ate 08/2026 um crash dentro de uma area era logado e
engolido, o processo saia com 0, o run_daily.sh gravava o marker de sucesso e
o dia seguinte parecia saudavel. Agora falha propaga e o catch-up horario
tenta de novo.
"""

import argparse
import logging
import os
import sys
import time

from dotenv import load_dotenv

from config.loader import load_monitor_targets
from src.core.bot import ConcursoBot
from src.core.multi_area_runner import MultiAreaRunner
from src.utils.logger import setup_logger

# O .env vive FORA do repo (~/concursos-secrets/monitor.env). A pasta do repo fica
# montada read-write no container do Hermes, que e alcancavel por Telegram; segredo
# nao mora em pasta que o agente le. Mesmo padrao do AgenteAgenda (~/agenda-secrets).
# Variaveis ja presentes no ambiente ganham do arquivo (override=False, default).
load_dotenv(os.getenv("MONITOR_ENV_FILE") or ".env")
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


def _get_float_env_alias(nomes: tuple[str, ...], default: float) -> float:
    """Primeiro nome definido no ambiente vence; os demais sao aliases legados."""
    for nome in nomes:
        if os.getenv(nome) is not None:
            return _get_float_env(nome, default)
    return default


def _get_int_env_alias(nomes: tuple[str, ...], default: int) -> int:
    for nome in nomes:
        if os.getenv(nome) is not None:
            return _get_int_env(nome, default)
    return default


def build_bots(dry_run: bool = False) -> list[ConcursoBot]:
    """Carrega alvos do .env e instancia um ConcursoBot por area."""
    base_config = {
        "token": os.getenv("TELEGRAM_TOKEN"),
        "ollama_model": os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL", "llama3.1"),
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        # LLM_* e o nome certo: o backend em uso e o `claude -p`, nao o Ollama.
        # OLLAMA_* segue aceito para nao quebrar o .env que ja esta no ar.
        "ollama_timeout_s": _get_float_env_alias(("LLM_TIMEOUT_S", "OLLAMA_TIMEOUT_S"), 120.0),
        "ollama_retries": _get_int_env_alias(("LLM_RETRIES", "OLLAMA_RETRIES"), 2),
        "ollama_retry_delay_s": _get_float_env_alias(
            ("LLM_RETRY_DELAY_S", "OLLAMA_RETRY_DELAY_S"), 2.0
        ),
        # So para backend LiteLLM (LLM_MODEL com "/"). Ver .env.example.
        "llm_api_base": os.getenv("LLM_API_BASE") or None,
        "llm_api_key": os.getenv("LLM_API_KEY") or None,
        "llm_reasoning_effort": os.getenv("LLM_REASONING_EFFORT") or None,
        "dry_run": dry_run,
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


# Bloco curto no formato do blog do Gran, so para provar que a LLM responde com
# o JSON esperado. Nao varre site, nao escreve no banco, nao manda Telegram.
_BLOCO_TESTE_LLM = (
    "<h3>Concurso Prefeitura de Curitiba - PR: edital publicado</h3>"
    "<p>A Prefeitura de Curitiba publicou edital com 12 vagas para Analista de "
    "Sistemas. Inscrições de 03/11/2026 a 30/11/2026, provas em 17/01/2027.</p>"
    '<p><a href="https://blog.grancursosonline.com.br/concurso-prefeitura-curitiba/">'
    "Veja o edital</a></p>"
)


def testar_llm() -> int:
    """Uma chamada real a LLM configurada, com a fiacao de producao.

    Existe para trocar de backend (ou renovar credencial) e saber em segundos
    se funcionou, em vez de esperar uma varredura inteira de ~13 minutos.
    """
    bots = build_bots(dry_run=True)
    if not bots:
        logger.error("Nenhum alvo valido configurado; nao ha como montar a LLM.")
        return 1

    ai = bots[0].ai
    logger.info(f"🧪 Testando a LLM {ai.model_name!r} com um bloco de exemplo...")
    inicio = time.monotonic()
    dados = ai.extrair_dados(_BLOCO_TESTE_LLM)
    duracao = time.monotonic() - inicio

    if dados.get("erro"):
        motivo = ai.falha_autenticacao or "veja os avisos acima"
        logger.error(f"❌ A LLM falhou em {duracao:.1f}s: {motivo}")
        return 1

    logger.info(f"✅ A LLM respondeu em {duracao:.1f}s: {dados}")
    return 0


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor de concursos (varredura unica).")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Varre e mostra o que faria, sem escrever no banco nem notificar. "
             "Serve pra medir o volume da primeira carga antes de soltar.",
    )
    parser.add_argument(
        "--testar-llm",
        action="store_true",
        help="Faz UMA chamada a LLM configurada e sai (0 = ok). Sem varredura.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    if args.testar_llm:
        return testar_llm()

    modo = " (DRY-RUN: sem escrita e sem Telegram)" if args.dry_run else ""
    logger.info(f"Sistema de Monitoramento iniciado (modo single-run){modo}.")

    bots = build_bots(dry_run=args.dry_run)
    if not bots:
        logger.error("Nenhum alvo valido configurado. Verifique URL_ALVO ou MONITOR_TARGETS_JSON.")
        return 1

    try:
        runner = MultiAreaRunner(bots)
        tudo_ok = runner.executar()
    except Exception as e:
        logger.critical(f"Falha catastrofica durante a varredura: {e}", exc_info=True)
        return 1

    if not tudo_ok:
        logger.error("Varredura terminou com falha em pelo menos uma area.")
        return 1

    logger.info("Varredura concluida com sucesso.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
