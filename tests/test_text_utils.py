"""Testes para src/utils/text.py — normalizacao, fingerprint e identidade de orgao."""
import pytest

from src.utils.text import (
    extrair_uf,
    mesma_entidade,
    siglas_de,
    status_fingerprint,
)


class TestStatusFingerprint:
    def test_identico_gera_mesmo_hash(self):
        assert status_fingerprint("Edital aberto") == status_fingerprint("Edital aberto")

    def test_case_nao_importa(self):
        assert status_fingerprint("Edital Aberto") == status_fingerprint("edital aberto")

    def test_acentos_normalizados(self):
        assert status_fingerprint("inscrições") == status_fingerprint("inscricoes")

    def test_whitespace_colapsado(self):
        assert (
            status_fingerprint("edital   publicado")
            == status_fingerprint("edital publicado")
        )
        assert (
            status_fingerprint("edital\npublicado")
            == status_fingerprint("edital publicado")
        )

    def test_pontuacao_de_borda_removida(self):
        assert (
            status_fingerprint("edital publicado.")
            == status_fingerprint("edital publicado")
        )

    def test_texto_completamente_diferente_gera_hashes_diferentes(self):
        assert (
            status_fingerprint("edital publicado")
            != status_fingerprint("resultado divulgado")
        )

    def test_vazio_retorna_string_vazia(self):
        assert status_fingerprint("") == ""
        assert status_fingerprint(None) == ""

    def test_hash_tem_16_caracteres(self):
        h = status_fingerprint("qualquer coisa")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)


class TestMesmaEntidade:
    """Casamento de orgao entre fontes: Gran e PCI grafam diferente.

    Os casos negativos sao reais, colhidos de varreduras de 08/2026.
    """

    @pytest.mark.parametrize("a,b", [
        ("Prefeitura de Ponta Grossa - PR", "Concurso Prefeitura de Ponta Grossa"),
        ("SEFIN RO", "Concurso SEFIN RO"),
        ("Secretaria de Estado da Educação de Alagoas",
         "Secretaria de Estado da Educacao de Alagoas AL"),
        ("Câmara de Passos - MG", "Camara Municipal de Passos"),
        ("UENP - Universidade Estadual do Norte do Paraná - PR",
         "Universidade Estadual do Norte do Parana UENP"),
        # Sobra e a sigla do orgao, citada por uma fonte e nao pela outra.
        ("Concurso UEAP - Universidade do Estado do Amapá",
         "Universidade do Estado do Amapá"),
    ])
    def test_mesmo_orgao_grafado_diferente(self, a, b):
        assert mesma_entidade(a, b) is True

    @pytest.mark.parametrize("a,b", [
        # Regressao real: fundiu dois Institutos Federais numa varredura de 08/08.
        # Causa dupla: "Pará" virava a stopword "para" ao perder o acento, e o
        # subconjunto aceitava sobra de palavra comum.
        ("Instituto Federal de Educação, Ciência e Tecnologia do Pará",
         "Instituto Federal de Educação, Ciência e Tecnologia do Sudeste de Minas Gerais"),
        ("Instituto Federal de Educação, Ciência e Tecnologia Farroupilha",
         "Instituto Federal de Educação, Ciência e Tecnologia do Pará"),
        # Cidades homonimas em estados diferentes.
        ("Prefeitura de Ponta Grossa - PR", "Prefeitura de Ponta Porã - MS"),
        ("Câmara de Três Corações - MG", "Câmara de Três Lagoas - MS"),
        # Mesmo tipo de orgao, cidade diferente: "prefeitura" nao discrimina.
        ("Prefeitura de Franca - SP", "Prefeitura de Brotas - SP"),
        ("Prefeitura de Lagoa Santa - MG", "Prefeitura de Lagoa da Prata - MG"),
        # Mesma sigla, estados diferentes.
        ("CRA - Conselho Regional de Administracao do Parana - PR",
         "CRA - Conselho Regional de Administracao do RS - RS"),
        # Prefixo identico, sobra informativa.
        ("Universidade Federal de Pernambuco",
         "Universidade Federal de Pernambuco Vale do Sao Francisco"),
    ])
    def test_orgaos_distintos_nao_casam(self, a, b):
        assert mesma_entidade(a, b) is False

    def test_nome_vazio_nunca_casa(self):
        assert mesma_entidade("", "Prefeitura de Franca - SP") is False
        assert mesma_entidade("Prefeitura de Franca - SP", "") is False

    def test_nome_so_de_tipo_generico_exige_igualdade(self):
        assert mesma_entidade("Prefeitura", "Prefeitura de Franca") is False
        assert mesma_entidade("Prefeitura", "Prefeitura") is True


class TestExtrairUf:
    @pytest.mark.parametrize("nome,esperado", [
        ("Câmara de Passos - MG", "MG"),
        ("Prefeitura de Brotas - sp", "SP"),
        ("SEFIN RO", None),          # sem o hifen nao e sufixo de UF
        ("Prefeitura de Franca", None),
        ("", None),
    ])
    def test_le_o_sufixo_de_uf(self, nome, esperado):
        assert extrair_uf(nome) == esperado


class TestSiglasDe:
    def test_pega_so_o_que_esta_em_caixa_alta(self):
        assert siglas_de("UEAP - Universidade do Estado do Amapá") == {"ueap"}

    def test_nome_proprio_em_title_case_nao_e_sigla(self):
        assert siglas_de("Instituto Federal do Sudeste de Minas Gerais") == set()

    def test_sem_sigla_devolve_vazio(self):
        assert siglas_de("Prefeitura de Franca") == set()
        assert siglas_de("") == set()
