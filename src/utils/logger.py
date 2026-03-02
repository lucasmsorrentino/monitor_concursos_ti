import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger():
    # Cria a pasta de logs se não existir
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Configuração do formato: [Data/Hora] [Nível] [Módulo] Mensagem
    log_format = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Handler para o arquivo (com rotação para o arquivo não ficar infinito)
    file_handler = RotatingFileHandler(
        'logs/bot_concursos.log', 
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