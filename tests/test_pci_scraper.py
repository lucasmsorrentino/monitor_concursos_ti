"""Testes para src/scrapers/pci_scraper.py.

O parse roda contra uma fixture salva (tests/fixtures/pci_analista_de_sistemas.html,
capturada em 2026-08-08), entao a suite nao depende de rede nem quebra quando o
PCI publica um edital novo.
"""
import os

import pytest

from src.scrapers.pci_scraper import PciScraper

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pci_analista_de_sistemas.html")


@pytest.fixture(scope="module")
def html():
    with open(FIXTURE, encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def itens(html):
    return PciScraper([])._parse(html, "analista-de-sistemas")


class TestParse:
    def test_extrai_todos_os_itens_da_pagina(self, itens):
        # 10 editais na fixture. A string "noticia_desc" aparece 12 vezes no
        # arquivo, mas duas delas sao seletor CSS dentro de um <style> — o
        # seletor `a.noticia_desc` do parser nao cai nessa.
        assert len(itens) == 10

    def test_todo_item_tem_identidade_utilizavel(self, itens):
        for item in itens:
            assert item["pci_id"].isdigit()
            assert item["link"].startswith("https://www.pciconcursos.com.br/noticias/")
            assert item["nome"]
            assert item["fonte"] == "pci"
            assert item["ignorar"] is False

    def test_pci_id_e_unico_na_pagina(self, itens):
        ids = [i["pci_id"] for i in itens]
        assert len(ids) == len(set(ids))

    def test_nome_nao_carrega_o_icone_de_link_externo(self, itens):
        # O <small> com o icone fica dentro do <a>; se vazasse, sujaria o nome
        # e estragaria o casamento por tokens com o que vem do Gran.
        for item in itens:
            assert "\n" not in item["nome"]
            assert item["nome"] == item["nome"].strip()

    def test_extrai_uf_do_sufixo(self, itens):
        ufs = {i["uf"] for i in itens if i["uf"]}
        assert ufs, "nenhuma UF extraida"
        assert all(len(uf) == 2 and uf.isupper() for uf in ufs)

    def test_associa_cargos_do_bloco_seguinte(self, itens):
        com_cargo = [i for i in itens if i["cargos"]]
        assert com_cargo, "nenhum cargo associado"
        assert any("ANALISTA DE SISTEMAS" in i["cargos"] for i in com_cargo)


class TestUniaoEntreSlugs:
    def test_mesmo_edital_em_dois_slugs_vira_um_item_so(self, html, mocker):
        """Um edital de TI aparece em analista E tecnico. Sem uniao por id, o
        mesmo concurso seria processado duas vezes na mesma rodada."""
        s = PciScraper(["analista-de-sistemas", "tecnico-em-informatica"])
        mocker.patch.object(s, "get_html", return_value=html)

        itens = s.capturar_concursos()

        assert len(itens) == 10
        assert len({i["pci_id"] for i in itens}) == 10

    def test_slug_que_falha_nao_derruba_os_outros(self, html, mocker):
        s = PciScraper(["quebrado", "analista-de-sistemas"])
        mocker.patch.object(s, "get_html", side_effect=[None, html])

        assert len(s.capturar_concursos()) == 10


class TestInferirFase:
    @pytest.mark.parametrize("titulo,esperado", [
        ("Prefeitura X - SP publica editais de concursos", "edital_publicado"),
        ("Prefeitura Y - MG retifica concurso publico", "edital_publicado"),
        ("Camara Z - MG abrem concurso publico com diversas vagas", "edital_publicado"),
        ("Orgao W reabre inscricoes de concurso", "inscricoes_abertas"),
        ("Prefeitura K encerra as inscricoes do concurso", "inscricoes_encerradas"),
        ("EMATER - MG anuncia concurso publico com salarios de ate R$ 7.321,75", "previsto"),
        ("Orgao Q autoriza a realizacao de concurso", "previsto"),
        ("CREA-MG: Concurso publico oferece vagas com salarios de ate R$ 13.609", "edital_publicado"),
        ("", None),
        ("Manchete sem verbo reconhecivel", None),
    ])
    def test_infere_pelo_verbo_do_titulo(self, titulo, esperado):
        assert PciScraper._inferir_fase(titulo) == esperado

    def test_verbo_de_anuncio_ganha_da_pista_fraca_de_salario(self):
        """"anuncia ... com salarios de ate" tem os dois sinais ao mesmo tempo.

        Quem manda e o verbo: o concurso foi so anunciado, nao teve edital.
        """
        assert PciScraper._inferir_fase("X anuncia concurso com salarios de ate R$ 9 mil") == "previsto"


class TestExtrairDataFim:
    def test_pega_o_fim_da_janela_e_ignora_isencao_e_prova(self):
        texto = (
            "As inscricoes devem ser feitas de 31 de julho de 2026 a 31 de agosto de 2026, "
            "exclusivamente pelo site. E possivel solicitar isencao ate 5 de agosto de 2026. "
            "As provas estao previstas para 6 de dezembro de 2026."
        )
        assert PciScraper._extrair_data_fim(texto) == "2026-08-31"

    @pytest.mark.parametrize("texto,esperado", [
        ("As inscricoes poderao ser realizadas ate 13/09/2026 pelo site.", "2026-09-13"),
        ("Inscricoes abertas de 01/08/2026 a 30/08/2026.", "2026-08-30"),
        ("As inscricoes vao ate 27 de setembro de 2026.", "2026-09-27"),
        ("O edital saiu. As provas serao em 6 de dezembro de 2026.", None),
        ("Inscricoes ate 31 de fevereiro de 2026.", None),   # data que nao existe
        ("Inscricoes ate 30 de agosto.", None),              # sem ano, nao chuta
        ("", None),
    ])
    def test_variacoes_de_formato(self, texto, esperado):
        assert PciScraper._extrair_data_fim(texto) == esperado


class TestEnriquecer:
    def test_nao_busca_quando_ja_tem_prazo(self, mocker):
        s = PciScraper([])
        get = mocker.patch.object(s, "get_html")

        s.enriquecer({"link": "http://x", "data_fim_inscricao": "2026-09-01"})

        get.assert_not_called()

    def test_preenche_prazo_a_partir_da_noticia(self, mocker):
        s = PciScraper([])
        mocker.patch.object(
            s, "get_html",
            return_value="<p>As inscri&ccedil;&otilde;es vao ate 30 de setembro de 2026.</p>",
        )
        item = {"link": "http://x", "data_fim_inscricao": None, "nome": "Orgao"}

        assert s.enriquecer(item)["data_fim_inscricao"] == "2026-09-30"

    def test_noticia_indisponivel_nao_quebra(self, mocker):
        s = PciScraper([])
        mocker.patch.object(s, "get_html", return_value=None)
        item = {"link": "http://x", "data_fim_inscricao": None, "nome": "Orgao"}

        assert s.enriquecer(item)["data_fim_inscricao"] is None
