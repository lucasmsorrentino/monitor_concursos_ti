"""Testes para src/scrapers/gran_scraper.py — fatiador de HTML."""
import pytest

from src.scrapers.gran_scraper import GranScraper


BLOG_HTML = """
<html><body>
<article>
  <h3>Concurso TRF1 — Analista de TI</h3>
  <p>Edital publicado em 2025.</p>
  <a href="https://example.com/trf1">detalhes</a>
  <h3>Concurso INSS</h3>
  <p>Banca definida.</p>
  <h3>Noticias Recomendadas</h3>
  <ul><li>item generico</li></ul>
</article>
</body></html>
"""

CARREIRA_HTML = """
<html><body>
<h3>Mais Procurados</h3>
<ul>
  <li><a href="https://example.com/concurso/trt">TRT concurso 2025</a></li>
  <li>Anuncio sem palavras relevantes</li>
</ul>
<h3>Edital Publicado</h3>
<ul>
  <li><a href="https://example.com/concurso/tjce">TJCE concurso</a></li>
</ul>
<h3>Gran</h3>
<ul>
  <li>#### GRAN footer</li>
</ul>
</body></html>
"""


class TestDefaultSlicer:
    def test_returns_one_block_per_h3(self, mocker):
        mocker.patch.object(GranScraper, "get_html", return_value=BLOG_HTML)
        scraper = GranScraper("https://blog.example.com/concursos-ti/")

        blocks = scraper.capturar_concursos()

        assert len(blocks) == 3

    def test_block_contains_h3_and_siblings_until_next_h3(self, mocker):
        mocker.patch.object(GranScraper, "get_html", return_value=BLOG_HTML)
        scraper = GranScraper("https://blog.example.com/concursos-ti/")

        blocks = scraper.capturar_concursos()

        assert "<h3>Concurso TRF1" in blocks[0]
        assert "Edital publicado em 2025" in blocks[0]
        assert "https://example.com/trf1" in blocks[0]
        # Nao deve vazar para o proximo h3
        assert "INSS" not in blocks[0]

    def test_returns_empty_list_on_fetch_failure(self, mocker):
        mocker.patch.object(GranScraper, "get_html", return_value=None)
        scraper = GranScraper("https://blog.example.com/concursos-ti/")

        assert scraper.capturar_concursos() == []


class TestCarreiraSlicer:
    def test_extracts_li_items_from_relevant_sections(self, mocker):
        mocker.patch.object(GranScraper, "get_html", return_value=CARREIRA_HTML)
        scraper = GranScraper("https://www.grancursosonline.com.br/cursos/carreira/ti/")

        blocks = scraper.capturar_concursos()

        # 1 li valido de "Mais Procurados" + 1 li valido de "Edital Publicado"
        # A secao "Gran" com ruido e ignorada
        assert len(blocks) == 2
        joined = " ".join(blocks)
        assert "TRT concurso" in joined
        assert "TJCE concurso" in joined
        assert "GRAN footer" not in joined

    def test_drops_li_without_concurso_reference(self, mocker):
        mocker.patch.object(GranScraper, "get_html", return_value=CARREIRA_HTML)
        scraper = GranScraper("https://www.grancursosonline.com.br/cursos/carreira/ti/")

        blocks = scraper.capturar_concursos()

        assert all("Anuncio sem palavras relevantes" not in b for b in blocks)


class TestNormalizar:
    def test_strips_accents_and_lowercases(self):
        assert GranScraper._normalizar("Educação Básica") == "educacao basica"

    def test_collapses_whitespace(self):
        assert GranScraper._normalizar("  muitos   espacos  ") == "muitos espacos"
