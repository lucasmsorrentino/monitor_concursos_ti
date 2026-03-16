"""Executor de varredura multi-area.

Encapsula uma lista de bots e executa todos em sequencia em cada ciclo.
"""

import logging
from src.core.bot import ConcursoBot


class MultiAreaRunner:
    """Executa um ciclo completo para todos os bots configurados."""

    def __init__(self, bots: list[ConcursoBot]):
        self.bots = bots
        self.logger = logging.getLogger(self.__class__.__name__)

    def executar(self) -> None:
        if not self.bots:
            self.logger.warning("Nenhum bot configurado para executar.")
            return

        self.logger.info(f"🔁 Iniciando ciclo multi-area com {len(self.bots)} alvo(s).")
        for bot in self.bots:
            self.logger.info(f"▶️ Executando area: {bot.area_name}")
            bot.executar()
