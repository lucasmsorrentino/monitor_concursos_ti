"""Porta do PCI Concursos pelo servidor MCP oficial.

Esqueleto: a docstring de contrato completa e a implementacao vem nos commits
seguintes, no ciclo TDD deste ticket.
"""

import requests

from src.scrapers.base_scraper import BaseScraper

URL_SERVIDOR = "https://mcp.pciconcursos.com.br/mcp"


class PciMcpScraper(BaseScraper):
    """Porta do PCI que chama a ferramenta ``buscar_por_cargo`` do servidor MCP."""

    def __init__(self, termos: list[str], tentativas: int = 3):
        super().__init__(URL_SERVIDOR, tentativas=tentativas)
        self.termos = list(termos)

    def capturar_concursos(self) -> list[dict]:
        """Uniao dos itens de um POST por termo, deduplicada por `id`."""
        raise NotImplementedError
