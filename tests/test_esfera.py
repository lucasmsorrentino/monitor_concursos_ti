"""Testes para src/utils/esfera.py.

Oraculo: tabela escrita a mao. Os nomes vem das fixtures em
tests/fixtures/pci_mcp/ (resposta real do servidor MCP) e dos exemplos da
SPEC-001, secao 3.3; o esperado de cada linha e julgamento humano, nao saida
do codigo. A costura e a funcao publica `esfera_de`: recebe o nome do orgao,
devolve a esfera.
"""
import pytest

from src.utils.esfera import esfera_de


@pytest.mark.parametrize(
    "nome",
    [
        "Prefeitura de Ijui - RS",
        "Camara de Cuiaba - MT",
        "Prefeitura e Camara de Coronel Freitas - SC",
        "Consorcio Intermunicipal de Saude da Microrregiao de Itabira - MG",
    ],
)
def test_esfera_de_municipal(nome):
    assert esfera_de(nome) == "municipal"


@pytest.mark.parametrize(
    "nome",
    [
        "UFMS - Fundacao Universidade Federal de Mato Grosso do Sul - MS",
        "IFSP - Instituto Federal de Educacao, Ciencia e Tecnologia de Sao Paulo - SP",
        "UTFPR - Universidade Tecnologica Federal do Parana - PR",
    ],
)
def test_esfera_de_federal_universidade_e_instituto(nome):
    assert esfera_de(nome) == "federal"


@pytest.mark.parametrize(
    "nome",
    [
        "TRF3 - Tribunal Regional Federal da 3a Regiao",
        "TRT 4 - Tribunal Regional do Trabalho da 4a Regiao - RS",
        "Ministerio da Saude",
    ],
)
def test_esfera_de_federal_tribunal_e_ministerio(nome):
    assert esfera_de(nome) == "federal"


@pytest.mark.parametrize(
    "nome",
    [
        "UEMG - Universidade do Estado de Minas Gerais - MG",
        "TCEES - Tribunal de Contas do Estado do Espirito Santo - ES",
        "PCAC - Policia Civil do Estado do Acre - AC",
        "SECITECI - Secretaria de Estado de Ciencia, Tecnologia e Inovacao de Mato Grosso - MT",
        "Banestes - Banco do Estado do Espirito Santo - ES",
    ],
)
def test_esfera_de_estadual(nome):
    assert esfera_de(nome) == "estadual"


def test_esfera_de_distrital():
    assert esfera_de("DPDF - Defensoria Publica do Distrito Federal - DF") == "distrital"


@pytest.mark.parametrize(
    "nome",
    [
        "CRP/05 - Conselho Regional de Psicologia da 5a Regiao - RJ",
        "Conselho Federal de Enfermagem",
    ],
)
def test_esfera_de_conselho_profissional(nome):
    assert esfera_de(nome) == "conselho_profissional"


def test_esfera_de_precedencia_conselho_vence_estadual():
    # "Conselho Regional" e "do Estado" no mesmo nome: e conselho profissional,
    # nao orgao estadual.
    nome = "CRC - Conselho Regional de Contabilidade do Estado de Sao Paulo"
    assert esfera_de(nome) == "conselho_profissional"


def test_esfera_de_precedencia_municipal_vence_estadual():
    # "Instituto" poderia ler como de estado; "do Municipio" decide municipal.
    nome = "IPREJUN - Instituto de Previdencia do Municipio de Jundiai - SP"
    assert esfera_de(nome) == "municipal"


def test_esfera_de_ignora_acento_e_caixa():
    assert esfera_de("prefeitura de ijuí - rs") == "municipal"


@pytest.mark.parametrize("nome", ["APS - Associacao das Pioneiras Sociais", None, ""])
def test_esfera_de_desconhecido(nome):
    assert esfera_de(nome) is None
