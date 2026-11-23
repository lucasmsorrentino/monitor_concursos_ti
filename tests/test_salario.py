"""Testes para src/utils/salario.py — teto do concurso a partir do texto do PCI.

Os literais sao de mao, retirados de respostas reais do servidor MCP
(fixtures em tests/fixtures/pci_mcp/) e de noticia do PCI lida em 20/11/2026.
"""
from src.utils.salario import teto_de


class TestTetoDe:
    def test_teto_de_le_formato_brasileiro_com_milhar(self):
        assert teto_de("454 vagas ate R$ 8.628,87") == 8628.87

    def test_teto_de_le_valor_sem_separador_de_milhar(self):
        assert teto_de("Vagas ate R$ 950,00") == 950.0

    def test_teto_de_le_cadastro_de_reserva_nas_duas_grafias(self):
        assert teto_de("Cadastro de reserva ate R$ 14.189,97") == 14189.97
        assert teto_de("Cadastro de Reserva ate R$ 12.937,29") == 12937.29

    def test_teto_de_em_faixa_devolve_o_topo(self):
        assert (
            teto_de("Os vencimentos mensais vao de R$ 1.840,36 a R$ 18.540,71")
            == 18540.71
        )

    def test_teto_de_le_mil_por_extenso(self):
        assert teto_de("salarios de ate R$ 6,6 mil") == 6600.0
        assert teto_de("R$ 12 mil") == 12000.0

    def test_teto_de_ignora_taxa_de_inscricao(self):
        assert teto_de("A taxa e de R$ 65,00 para nivel fundamental") is None

    def test_teto_de_ignora_valor_por_hora(self):
        assert teto_de("Dentista recebe R$ 32,64 por hora") is None

    def test_teto_de_ignora_valor_absurdo(self):
        assert teto_de("R$ 980.000,00") is None

    def test_teto_de_mistura_taxa_e_salario_devolve_o_salario(self):
        assert teto_de("salarios de ate R$ 8.628,87. A taxa e de R$ 80,00") == 8628.87

    def test_teto_de_sem_valor_devolve_none(self):
        assert teto_de(None) is None
        assert teto_de("") is None
        assert teto_de("Vagas") is None
        assert teto_de("a combinar") is None
