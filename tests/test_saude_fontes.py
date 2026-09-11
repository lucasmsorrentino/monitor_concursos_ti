"""Testes para src/utils/saude_fontes.py e src/utils/memoria_json.py.

O caso que este modulo existe para pegar: o alvo de TI do Gran
(`blog.grancursosonline.com.br/concursos-ti/`) devolveu os MESMOS 45 blocos de
06/07 a 09/09/2026 — 89 dias congelado — e o bot reportava dia normal, porque
a segunda fonte (PCI) trazia novidade e o alerta de cegueira era agregado.
"""
from datetime import date, timedelta

import pytest

from src.utils import memoria_json, saude_fontes


@pytest.fixture(autouse=True)
def estado_isolado(mocker, tmp_path):
    """Estado em tmp: o arquivo real vive em data/ e nao pode ser tocado."""
    mocker.patch.object(memoria_json, "DATA_DIR", str(tmp_path))


def _dias_atras(n: int) -> date:
    return date.today() - timedelta(days=n)


class TestDigest:
    def test_ordem_dos_itens_nao_conta_como_mudanca(self):
        """A ordem na pagina muda sozinha (destaque, patrocinio) sem que o
        conteudo mude. Se contasse, fonte parada nunca seria detectada."""
        assert saude_fontes.digest(["a", "b", "c"]) == saude_fontes.digest(["c", "a", "b"])

    def test_conteudo_diferente_muda_o_digest(self):
        assert saude_fontes.digest(["a", "b"]) != saude_fontes.digest(["a", "b", "c"])


class TestAvaliar:
    def test_primeira_rodada_nao_acusa_nada(self):
        d = saude_fontes.avaliar("TI", "gran", ["bloco"])
        assert d.saudavel
        assert d.dias_sem_mudanca == 0
        assert d.itens == 1

    def test_fonte_vazia_e_sinalizada(self):
        d = saude_fontes.avaliar("TI", "gran", [])
        assert d.vazia is True
        assert d.parada is False
        assert d.saudavel is False

    def test_conteudo_identico_por_muitos_dias_e_fonte_parada(self):
        blocos = ["bloco 1", "bloco 2"]
        saude_fontes.avaliar("TI", "gran", blocos, hoje=_dias_atras(40))

        d = saude_fontes.avaliar("TI", "gran", blocos, dias_parada=21)

        assert d.parada is True
        assert d.dias_sem_mudanca == 40
        assert d.saudavel is False

    def test_conteudo_novo_zera_o_contador(self):
        saude_fontes.avaliar("TI", "gran", ["velho"], hoje=_dias_atras(40))

        d = saude_fontes.avaliar("TI", "gran", ["novo"], dias_parada=21)

        assert d.parada is False
        assert d.dias_sem_mudanca == 0

    def test_abaixo_do_limite_ainda_esta_saudavel(self):
        saude_fontes.avaliar("TI", "gran", ["x"], hoje=_dias_atras(10))
        assert saude_fontes.avaliar("TI", "gran", ["x"], dias_parada=21).saudavel

    def test_dia_de_site_fora_nao_reinicia_o_contador_de_parada(self):
        """Um dia vazio no meio nao pode mascarar 40 dias de estagnacao."""
        blocos = ["igual"]
        saude_fontes.avaliar("TI", "gran", blocos, hoje=_dias_atras(40))
        saude_fontes.avaliar("TI", "gran", [], hoje=_dias_atras(1))   # site fora

        d = saude_fontes.avaliar("TI", "gran", blocos, dias_parada=21)

        assert d.parada is True
        assert d.dias_sem_mudanca == 40

    def test_areas_e_fontes_sao_independentes(self):
        saude_fontes.avaliar("TI", "gran", ["a"], hoje=_dias_atras(40))
        saude_fontes.avaliar("TI", "pci", ["b"], hoje=_dias_atras(40))

        assert saude_fontes.avaliar("TI", "gran", ["a"], dias_parada=21).parada
        assert not saude_fontes.avaliar("TI", "pci", ["b", "c"], dias_parada=21).parada
        assert not saude_fontes.avaliar("EDUCACAO", "gran", ["a"], dias_parada=21).parada


class TestMemoriaJson:
    def test_arquivo_inexistente_devolve_vazio(self):
        assert memoria_json.carregar("nao_existe") == {}

    def test_ida_e_volta(self):
        memoria_json.salvar("teste", {"a": 1})
        assert memoria_json.carregar("teste") == {"a": 1}

    def test_json_corrompido_nao_derruba_a_varredura(self, tmp_path):
        (tmp_path / "quebrado.json").write_text("{isso nao e json", encoding="utf-8")
        assert memoria_json.carregar("quebrado") == {}

    def test_conteudo_que_nao_e_dicionario_e_descartado(self, tmp_path):
        (tmp_path / "lista.json").write_text("[1, 2, 3]", encoding="utf-8")
        assert memoria_json.carregar("lista") == {}

    def test_falha_de_escrita_nao_levanta(self, mocker):
        mocker.patch("builtins.open", side_effect=OSError("disco cheio"))
        memoria_json.salvar("teste", {"a": 1})   # nao deve explodir
