"""Testes para src/scrapers/pci_nacional_scraper.py.

Fixture: tests/fixtures/pci_nacional.html, capturada em 09/09/2026. Ela tem os
quatro casos que importam — Transpetro (so data de fim), AgSUS duas vezes (mesmo
orgao, editais diferentes; um deles com janela que ainda nao abriu) e DEPA
(varios cargos separados por virgula).
"""
import os
from datetime import date

import pytest

from src.scrapers.pci_nacional_scraper import PciNacionalScraper

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pci_nacional.html")

# Data da captura. Fixar evita que a fase dos itens vire `inscricoes_encerradas`
# conforme os prazos da fixture envelhecem e a suite comece a falhar sozinha.
HOJE = date(2026, 9, 9)


@pytest.fixture(scope="module")
def html():
    with open(FIXTURE, encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def itens(html):
    return PciNacionalScraper()._parse(html, hoje=HOJE)


class TestParse:
    def test_extrai_um_item_por_concurso(self, itens):
        assert len(itens) == 4

    def test_todo_item_tem_identidade_utilizavel(self, itens):
        for item in itens:
            assert item["link"].startswith("https://www.pciconcursos.com.br/noticias/")
            assert item["nome"]
            assert item["fonte"] == "pci_nacional"
            assert item["ignorar"] is False

    def test_nao_ha_pci_id_nesta_pagina(self, itens):
        """A listagem nacional nao traz o `nXXXXXX`; a identidade e o link.

        Se um dia o PCI passar a trazer, este teste falha e o `pci_id` (que e a
        chave de dedup mais forte) deve ser aproveitado.
        """
        assert all(item["pci_id"] is None for item in itens)

    def test_link_e_a_chave_de_dedup_nao_o_nome(self, itens):
        """AgSUS aparece duas vezes com editais diferentes: sao dois itens."""
        agsus = [i for i in itens if i["nome"].startswith("AgSUS")]
        assert len(agsus) == 2
        assert agsus[0]["link"] != agsus[1]["link"]

        links = [i["link"] for i in itens]
        assert len(links) == len(set(links))

    def test_uf_e_nula_porque_o_concurso_e_nacional(self, itens):
        assert all(item["uf"] is None for item in itens)


class TestJanelaDeInscricao:
    def test_data_unica_e_o_fim_da_janela(self, itens):
        transpetro = next(i for i in itens if i["nome"].startswith("Transpetro"))
        assert transpetro["data_fim_inscricao"] == "2026-09-14"
        assert transpetro["inicio_inscricao"] is None

    def test_intervalo_herda_o_ano_da_segunda_data(self, itens):
        psicologos = next(i for i in itens if "psicólogos" in i["status"])
        assert psicologos["inicio_inscricao"] == "2026-09-16"
        assert psicologos["data_fim_inscricao"] == "2026-10-16"

    @pytest.mark.parametrize("texto, esperado", [
        ("14/09/2026", (None, "2026-09-14")),
        ("16/09 a 16/10/2026", ("2026-09-16", "2026-10-16")),
        ("Sem data prevista", (None, None)),
        ("31/02/2026", (None, None)),          # data que nao existe
    ])
    def test_formatos(self, texto, esperado):
        assert PciNacionalScraper._janela_de_inscricao(texto, HOJE) == esperado

    def test_janela_que_vira_o_ano_nao_poe_o_inicio_depois_do_fim(self):
        """"20/12 a 15/01/2027": herdar 2027 no inicio inverteria a janela."""
        inicio, fim = PciNacionalScraper._janela_de_inscricao("20/12 a 15/01/2027", HOJE)
        assert inicio == "2026-12-20"
        assert fim == "2027-01-15"
        assert inicio < fim


class TestFase:
    def test_janela_aberta_vence_o_verbo_do_titulo(self, itens):
        """"Transpetro publica editais retificados" casaria `edital_publicado`
        pela pista de titulo, mas o prazo na mesma linha diz que a inscricao
        esta aberta. A janela e fato datado; o verbo, nao."""
        transpetro = next(i for i in itens if i["nome"].startswith("Transpetro"))
        assert "retificados" in transpetro["status"]
        assert transpetro["fase"] == "inscricoes_abertas"

    def test_inscricao_que_ainda_vai_abrir_e_edital_publicado(self, itens):
        psicologos = next(i for i in itens if "psicólogos" in i["status"])
        assert psicologos["fase"] == "edital_publicado"

    def test_prazo_vencido_e_inscricoes_encerradas(self):
        assert PciNacionalScraper._fase("X", None, "2026-01-01", HOJE) == "inscricoes_encerradas"

    def test_sem_janela_cai_no_verbo_do_titulo(self):
        assert PciNacionalScraper._fase(
            "Orgao anuncia concurso publico", None, None, HOJE
        ) == "previsto"

    def test_sem_janela_e_sem_verbo_fica_none(self):
        assert PciNacionalScraper._fase("Nota da redacao", None, None, HOJE) is None


class TestCelulaDeCargos:
    def test_separa_cargos_de_escolaridade(self, itens):
        depa = next(i for i in itens if i["nome"].startswith("DEPA"))
        assert depa["cargos"] == [
            "Aluno do 6º ano do Ensino Fundamental",
            "Aluno do 1º ano do Ensino Médio",
        ]
        assert depa["nivel"] == "Não informada"
        assert depa["vagas"] == "355 vagas"

    def test_varios_cargos_vira_um_item_so(self, itens):
        transpetro = next(i for i in itens if i["nome"].startswith("Transpetro"))
        assert transpetro["cargos"] == ["Vários Cargos"]
        assert transpetro["nivel"] == "Médio / Técnico / Superior"


class TestBlocoParaIa:
    def test_inclui_o_que_a_llm_precisa_pra_julgar_a_area(self, itens):
        item = dict(itens[0], texto_noticia="Vagas para Analista de Sistemas.")
        bloco = PciNacionalScraper.bloco_para_ia(item)

        assert item["nome"] in bloco
        assert item["link"] in bloco
        assert "Analista de Sistemas" in bloco
        assert bloco.startswith("<h3>")

    def test_funciona_sem_a_noticia_carregada(self, itens):
        """Se a noticia nao abriu, o bloco ainda sai com o que a listagem deu."""
        bloco = PciNacionalScraper.bloco_para_ia(itens[0])
        assert itens[0]["link"] in bloco
        assert "<div>" not in bloco


class TestCapturarConcursos:
    def test_pagina_fora_do_ar_devolve_lista_vazia(self, mocker):
        scraper = PciNacionalScraper()
        mocker.patch.object(scraper, "get_html", return_value=None)
        assert scraper.capturar_concursos() == []

    def test_detalhar_sem_link_nao_faz_requisicao(self, mocker):
        scraper = PciNacionalScraper()
        get_html = mocker.patch.object(scraper, "get_html")
        scraper.detalhar({"nome": "X", "link": ""})
        get_html.assert_not_called()

    def test_detalhar_preenche_prazo_que_faltava(self, mocker):
        scraper = PciNacionalScraper()
        mocker.patch.object(
            scraper, "get_html",
            return_value="<p>As inscrições vão de 01/10/2026 a 20/10/2026. "
                         "As provas ocorrem em 15/12/2026.</p>",
        )
        item = {"nome": "X", "link": "https://pci/x", "data_fim_inscricao": None}
        scraper.detalhar(item)

        # Prazo da frase de INSCRICAO, nao a data da prova.
        assert item["data_fim_inscricao"] == "2026-10-20"
        assert "inscrições" in item["texto_noticia"]

    def test_detalhar_nao_sobrescreve_prazo_da_listagem(self, mocker):
        """A listagem e mais confiavel que o regex no corpo da noticia."""
        scraper = PciNacionalScraper()
        mocker.patch.object(
            scraper, "get_html",
            return_value="<p>Inscrições até 31/12/2026.</p>",
        )
        item = {"nome": "X", "link": "https://pci/x", "data_fim_inscricao": "2026-10-20"}
        scraper.detalhar(item)

        assert item["data_fim_inscricao"] == "2026-10-20"
