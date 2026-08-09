"""Scraper especializado para o blog Gran Cursos Online.

Na arquite
tura AI-First, este módulo atua apenas como **Slicer** (fatiador):
ele usa o BeautifulSoup para dividir a página HTML em blocos independentes
delimitados por tags ``<h3>``, sem extrair textos ou links diretamente.
A interpretação semântica do conteúdo é delegada à ``IntelligenceUnit``.
"""

from bs4 import BeautifulSoup

from src.utils.text import strip_accents
from .base_scraper import BaseScraper


class GranScraper(BaseScraper):
    """Fatiador de HTML para o blog do Gran Cursos Online — seção Concursos TI.

    Herda de :class:`BaseScraper` e implementa ``capturar_concursos()``.
    Não realiza extração de dados; apenas recorta a página em blocos de HTML
    bruto para que a LLM os interprete.
    """

    _CARREIRA_SECOES = (
        "mais procurados",
        "edital publicado",
        "edital em breve",
        "preparacao a medio e a longo prazo",
        "outros concursos",
    )

    _RUIDO_MARCADORES = (
        "#### GRAN",
        "#### SUPORTE",
        "#### CURSOS ONLINE",
        "#### PAGINAS UTEIS",
        "#### CONCURSOS NO",
        "#### CONTEUDO JURIDICO",
    )

    def capturar_concursos(self) -> list[str]:
        """Fatia a página HTML em blocos independentes delimitados por ``<h3>``.

        Cada bloco contém o ``<h3>`` de um concurso e todos os elementos-irmãos
        seguintes até o próximo ``<h3>``, formando um trecho de HTML
        autocontido que será enviado à LLM para extração de dados.

        Returns:
            list[str]: Lista de strings HTML brutas, uma por bloco/concurso.
                       Retorna lista vazia se a página não puder ser obtida.
        """
        html = self.get_html()
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')

        if "/cursos/carreira/" in self.url:
            return self._capturar_por_carreira(soup)

        chunks: list[str] = []
        titulos = soup.find_all('h3')

        for t in titulos:
            # Coleta o <h3> e todos os irmãos seguintes até o próximo <h3>
            conteudo_bloco = [str(t)]
            for irmao in t.find_next_siblings():
                if irmao.name == 'h3':
                    break
                conteudo_bloco.append(str(irmao))

            bloco_completo = "\n".join(conteudo_bloco)
            chunks.append(bloco_completo)

        return chunks

    def _capturar_por_carreira(self, soup: BeautifulSoup) -> list[str]:
        """Extrai blocos limpos das paginas de carreira do Gran.

        Cada <li> dentro de uma secao relevante vira um bloco independente,
        para que o pipeline de IA processe um concurso por vez.
        """
        chunks: list[str] = []

        for heading in soup.find_all(["h3", "h4"]):
            titulo = heading.get_text(" ", strip=True)
            titulo_norm = self._normalizar(titulo)

            # Usa substring match: "concursos mais procurados" contém "mais procurados"
            if not any(secao in titulo_norm for secao in self._CARREIRA_SECOES):
                continue

            for sibling in heading.find_next_siblings():
                if sibling.name in {"h3", "h4"}:
                    break

                bloco_texto = self._normalizar(sibling.get_text(" ", strip=True))

                if not bloco_texto:
                    continue

                if any(self._normalizar(m) in bloco_texto for m in self._RUIDO_MARCADORES):
                    continue

                # Cada <li> vira um bloco independente
                items = sibling.find_all("li")
                if items:
                    for li in items:
                        li_html = str(li)
                        if "concurso/" not in li_html and "concurso" not in li_html.lower():
                            continue
                        chunks.append(f"<h3>{titulo}</h3>\n{li_html}")
                else:
                    bloco_html = str(sibling)
                    if "concurso/" not in bloco_html and "curso" not in bloco_texto:
                        continue
                    chunks.append(f"<h3>{titulo}</h3>\n{bloco_html}")

        return chunks

    @staticmethod
    def _normalizar(texto: str) -> str:
        """Normaliza texto para comparacoes simples de filtro."""
        # strip_accents via unicodedata: a versao anterior era uma cadeia de
        # .replace() que perdia maiusculas acentuadas, u-trema e n-til.
        return " ".join(strip_accents(texto).lower().split())
