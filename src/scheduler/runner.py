import schedule
import time
import logging
from core.bot import ConcursoBot

class DailyScheduler:
    def __init__(self, bot: ConcursoBot):
        self.bot = bot
        self.logger = logging.getLogger(self.__class__.__name__)

    def agendar_diariamente(self, horario: str = "08:00"):
        """
        Programa a execução para todos os dias em um horário específico.
        Formato do horário: "HH:MM" (ex: "09:30")
        """
        self.logger.info(f"⏰ Agendamento configurado para todos os dias às {horario}.")
        
        # Agenda a tarefa
        schedule.every().day.at(horario).do(self.executar_tarefa)

    def executar_tarefa(self):
        """Encapsula a execução do bot para o scheduler."""
        self.logger.info("🔔 Hora de trabalhar! Iniciando execução agendada...")
        try:
            self.bot.executar()
        except Exception as e:
            self.logger.error(f"❌ Falha durante a execução agendada: {e}")

    def iniciar(self):
        """Mantém o script rodando em um loop infinito."""
        self.logger.info("🚀 Scheduler em execução... O bot está vigiando os concursos.")
        
        try:
            while True:
                # Verifica se há alguma tarefa pendente para rodar
                schedule.run_pending()
                # Dorme por 1 minuto antes de verificar novamente (economiza CPU)
                time.sleep(60)
        except KeyboardInterrupt:
            self.logger.warning("🛑 Scheduler interrompido pelo usuário.")