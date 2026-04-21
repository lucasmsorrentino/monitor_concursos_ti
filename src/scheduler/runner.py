"""Agendador diario legado baseado na lib `schedule`.

Nao e mais usado pelo `main.py` (que roda em modo single-run). Mantido
para compatibilidade com cenarios em que o usuario prefere um processo
residente em vez de delegar ao Windows Task Scheduler. Para o uso padrao,
veja `scripts/install_schedule.ps1`.
"""
import logging
import time

import schedule


class DailyScheduler:
    """Wrapper fino sobre `schedule` para disparar um runner 1x/dia."""

    def __init__(self, runner):
        """Recebe qualquer objeto com metodo `executar()` (ex: MultiAreaRunner)."""
        self.runner = runner
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
            self.runner.executar()
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