"""Base comum aos scrapers.

Concentra o acesso HTTP para que Gran e PCI compartilhem o mesmo tratamento de
rede: User-Agent de navegador, retry com backoff e log estruturado.
"""

from abc import ABC, abstractmethod
import logging
import time

import requests

# Um soluco de rede antes dava 0 blocos, e 0 blocos dispara o alerta de cegueira
# (bot.py: varredura_cega). Ou seja: instabilidade passageira chegava no Telegram
# como "o site mudou de layout". Tentar de novo custa segundos e mata o falso positivo.
TENTATIVAS_PADRAO = 3
BACKOFF_BASE_S = 2.0


class BaseScraper(ABC):
    def __init__(self, url, tentativas: int = TENTATIVAS_PADRAO):
        self.url = url
        self.tentativas = max(1, tentativas)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }

    @abstractmethod
    def capturar_concursos(self):
        """
        Este método deve ser implementado por todas as subclasses.
        Deve retornar uma lista de dicionários: [{'nome': ..., 'status': ..., 'link': ...}]
        """
        pass

    def get_html(self, url: str | None = None):
        """Busca o HTML da pagina, com retry e backoff exponencial.

        Args:
            url: sobrescreve ``self.url``. O PciScraper usa isso para varrer
                 varios slugs de cargo reaproveitando a mesma politica de rede.

        Returns:
            O corpo da resposta, ou ``None`` se todas as tentativas falharem.
        """
        alvo = url or self.url

        for tentativa in range(1, self.tentativas + 1):
            try:
                response = requests.get(alvo, headers=self.headers, timeout=15)
                response.raise_for_status()
                response.encoding = 'utf-8'
                return response.text
            except Exception as e:
                if tentativa == self.tentativas:
                    # error, nao print: o print sumia do bot_concursos.log e so
                    # aparecia no log do dia, invisivel a qualquer filtro de nivel.
                    self.logger.error(
                        f"❌ Falha ao acessar {alvo} apos {self.tentativas} tentativa(s): {e}"
                    )
                    return None

                espera = BACKOFF_BASE_S * (2 ** (tentativa - 1))
                self.logger.warning(
                    f"⚠️ Tentativa {tentativa}/{self.tentativas} falhou para {alvo}: {e}. "
                    f"Nova tentativa em {espera:.0f}s."
                )
                time.sleep(espera)

        return None
