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

    def executar(self) -> bool:
        """Roda todas as areas em sequencia.

        Returns:
            bool: True se TODAS as areas terminaram sem falha. Uma area que
            falha nao interrompe as outras, mas contamina o resultado — o
            main.py devolve exit != 0 e o run_daily.sh nao grava o marker de
            sucesso, entao o catch-up da hora seguinte tenta de novo.
        """
        if not self.bots:
            self.logger.warning("Nenhum bot configurado para executar.")
            return False

        self.logger.info(f"🔁 Iniciando ciclo multi-area com {len(self.bots)} alvo(s).")
        falharam = []
        for bot in self.bots:
            self.logger.info(f"▶️ Executando area: {bot.area_name}")
            bot.executar()
            if bot.falhou:
                falharam.append(bot.area_name)

        if falharam:
            self.logger.error(f"❌ Areas com falha nesta varredura: {', '.join(falharam)}.")
            return False
        return True
