import os
import logging
from dotenv import load_dotenv
from src.utils.logger import setup_logger
from src.core.bot import ConcursoBot
from src.scheduler.runner import DailyScheduler 

# Carrega as variáveis do arquivo .env
load_dotenv()
setup_logger() # Inicializa o sistema de logs
logger = logging.getLogger(__name__)

def main():
    logger.info("🎬 Sistema de Monitoramento Iniciado.") 
    
    config = {
        "token": os.getenv("TELEGRAM_TOKEN"),
        "chat_id": os.getenv("TELEGRAM_CHAT_ID"),
        "ollama_model": os.getenv("OLLAMA_MODEL", "llama3.1"),
        "url_alvo": os.getenv("URL_ALVO"),
        "horario_execucao": os.getenv("HORARIO_EXECUCAO", "08:00") # Novo parâmetro
    }

    # Validação simples
    if not config["token"] or not config["chat_id"]:
        logger.error("❌ Erro: TELEGRAM_TOKEN ou CHAT_ID não configurados no arquivo .env")
        return
    
    try:
        # 1. Cria a instância do Bot
        bot = ConcursoBot(config)
        
        # 2. Cria o Scheduler e passa o bot para ele
        scheduler = DailyScheduler(bot)
        
        # 3. Define o horário e inicia o loop infinito
        scheduler.agendar_diariamente(config["horario_execucao"])
        
        # (Opcional) Executa uma vez ao ligar para garantir que está funcionando
        logger.info("🔄 Executando primeira varredura de inicialização...")
        bot.executar()

        # Início do Loop Infinito (O programa "para" aqui e fica esperando o horário)
        scheduler.iniciar()

    except Exception as e:
        logger.critical(f"Falha catastrófica no sistema: {e}", exc_info=True)


if __name__ == "__main__":
    main()