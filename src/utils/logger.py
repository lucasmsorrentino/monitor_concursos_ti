import logging
import os
import re
from logging.handlers import RotatingFileHandler

# Ancorado na raiz do repo, nao no diretorio de trabalho: rodar o main.py de
# outra pasta antes espalhava um logs/ novo onde quer que o processo estivesse.
REPO_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(REPO_DIR, "logs")

# Token de bot do Telegram ("<id numerico>:<35 caracteres>"). Quando o requests
# levanta erro de rede, a mensagem da excecao traz a URL inteira, e a URL da Bot
# API carrega o token. Foi assim que ele parou em 9 logs entre 25/09 e
# 02/10/2026 (notebook sem DNS), numa pasta que o container do Hermes le — o
# exato vazamento que tirar os segredos do repo (MONITOR_ENV_FILE) devia evitar.
# Sem \b no inicio: na URL o id vem colado em "bot", sem fronteira de palavra.
_RE_TOKEN_TELEGRAM = re.compile(r"(?<!\d)\d{6,12}:[A-Za-z0-9_-]{30,}")


def ocultar_segredos(texto: str) -> str:
    """Troca tokens do Telegram por um marcador antes de o texto ir pro log."""
    return _RE_TOKEN_TELEGRAM.sub("<token-telegram>", texto)


class FormatterSemSegredos(logging.Formatter):
    """Formatter que limpa a linha JA formatada, traceback incluso.

    Limpar no formatter, e nao em cada `logger.warning`, cobre tambem o
    `exc_info=True` e qualquer modulo novo que logue uma excecao do requests.
    """

    def format(self, record: logging.LogRecord) -> str:
        return ocultar_segredos(super().format(record))


def setup_logger():
    # Cria a pasta de logs se não existir
    os.makedirs(LOG_DIR, exist_ok=True)

    # Configuração do formato: [Data/Hora] [Nível] [Módulo] Mensagem
    log_format = FormatterSemSegredos(
        '[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Handler para o arquivo (com rotação para o arquivo não ficar infinito)
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, 'bot_concursos.log'),
        maxBytes=1024 * 1024, # 1MB por arquivo
        backupCount=5,        # Mantém até 5 arquivos antigos
        encoding='utf-8'
    )
    file_handler.setFormatter(log_format)

    # Handler para o console (Terminal)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)

    # Configuração global do logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger