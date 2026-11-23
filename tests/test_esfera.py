"""Testes para src/utils/esfera.py.

Oraculo: tabela escrita a mao. Os nomes vem das fixtures em
tests/fixtures/pci_mcp/ (resposta real do servidor MCP) e dos exemplos da
SPEC-001, secao 3.3; o esperado de cada linha e julgamento humano, nao saida
do codigo. A costura e a funcao publica `esfera_de`: recebe o nome do orgao,
devolve a esfera.

Os casos de precedencia usam nomes construidos para ativar, no mesmo nome,
dois padroes de esferas diferentes (o orgao real raramente junta os dois):
o que se prova e a ordem declarada no aceite, e o esperado vem dela, nao do
codigo. Os demais casos cobrem, um a um, os padroes de cada esfera, as duas
excecoes declaradas e o fallback da UF DF.
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


# Precedencia declarada no aceite:
# conselho_profissional > municipal > federal > distrital > estadual.
# Cada par ativa dois padroes de esferas diferentes no mesmo nome.
@pytest.mark.parametrize(
    "nome, esperado",
    [
        pytest.param(
            "Conselho Regional de Medicina e Camara Municipal de Sao Paulo - SP",
            "conselho_profissional",
            id="conselho_vence_municipal",
        ),
        pytest.param(
            "Conselho Federal de Contabilidade e Banco do Brasil",
            "conselho_profissional",
            id="conselho_vence_federal",
        ),
        pytest.param(
            "CRC - Conselho Regional de Contabilidade e Tribunal de Justica de Sao Paulo - SP",
            "conselho_profissional",
            id="conselho_vence_estadual",
        ),
        pytest.param(
            "Camara Municipal de Sao Paulo e Justica Federal - SP",
            "municipal",
            id="municipal_vence_federal",
        ),
        pytest.param(
            "Fundo Municipal do Distrito Federal - DF",
            "municipal",
            id="municipal_vence_distrital",
        ),
        pytest.param(
            "Secretaria Municipal de Saude e Tribunal de Justica de Minas Gerais - MG",
            "municipal",
            id="municipal_vence_estadual",
        ),
        pytest.param(
            "TRF1 - Tribunal Regional Federal da 1a Regiao - DF",
            "federal",
            id="federal_vence_sufixo_df",
        ),
        pytest.param(
            "Justica Federal e Tribunal de Justica de Santa Catarina - SC",
            "federal",
            id="federal_vence_estadual",
        ),
        pytest.param(
            "Secretaria de Estado de Saude do Distrito Federal - DF",
            "distrital",
            id="distrital_vence_estadual",
        ),
    ],
)
def test_esfera_de_precedencia_entre_esferas(nome, esperado):
    assert esfera_de(nome) == esperado


# Distrital: o padrao "Distrital" e o fallback pela UF DF no sufixo.
@pytest.mark.parametrize(
    "nome",
    [
        "Policia Penal Distrital",
        "Camara Legislativa Distrital",
    ],
)
def test_esfera_de_distrital_pelo_padrao_distrital(nome):
    assert esfera_de(nome) == "distrital"


@pytest.mark.parametrize(
    "nome",
    [
        "SLU - Servico de Limpeza Urbana - DF",
        "CAAC - Companhia de Aguas - DF",
    ],
)
def test_esfera_de_distrital_pela_uf_df_quando_nada_decide(nome):
    # O texto nao casa padrao algum: so a UF DF no sufixo decide distrital.
    assert esfera_de(nome) == "distrital"


# Municipais: cada padrao decide por conta propria, sem carona de outro.
@pytest.mark.parametrize(
    "nome",
    [
        "SEMSA - Secretaria Municipal de Saude de Nova Lima - MG",
        "Fundo Municipal de Saude de Cascavel - PR",
        "Municipio de Nova Trento - SC",
        # Padrao longo sem a substring "municipio de": so ele decide.
        "Instituto de Previdencia do Municipio - SP",
    ],
)
def test_esfera_de_municipal_padroes_do_aceite(nome):
    assert esfera_de(nome) == "municipal"


def test_esfera_de_camara_legislativa_nao_e_municipal():
    # Excecao declarada: "Camara" casa municipal, menos "Camara Legislativa",
    # que e do Distrito Federal.
    assert esfera_de("CLDF - Camara Legislativa do Distrito Federal - DF") == "distrital"


# Federais: tribunais, policia e justica que faltavam na tabela.
@pytest.mark.parametrize(
    "nome",
    [
        "TRE-SC - Tribunal Regional Eleitoral de Santa Catarina - SC",
        "DPF - Departamento da Policia Federal - DF",
        "DPRF - Departamento de Policia Rodoviaria Federal - DF",
        "JFSC - Justica Federal de Santa Catarina - SC",
    ],
)
def test_esfera_de_federal_tribunais_policia_e_justica(nome):
    assert esfera_de(nome) == "federal"


# Federais: as estatais pelo nome.
@pytest.mark.parametrize(
    "nome",
    [
        "Correios - Empresa Brasileira de Correios e Telegrafos",
        "Dataprev - Empresa de Tecnologia e Informacoes da Previdencia",
        "Transpetro - Petrobras Transporte S.A.",
        "Petrobras - Petroleo Brasileiro S.A.",
        "Caixa Economica Federal",
        "Banco do Brasil S.A.",
        "Serpro - Servico Federal de Processamento de Dados",
        "Embrapa - Empresa Brasileira de Pesquisa Agropecuaria",
        "Infraero - Empresa Brasileira de Infraestrutura Aeroportuaria",
        "Conab - Companhia Nacional de Abastecimento",
    ],
)
def test_esfera_de_federal_estatais(nome):
    assert esfera_de(nome) == "federal"


# Excecao declarada: "Ministerio Publico" nao e ministerio, nao casa federal.
def test_esfera_de_ministerio_publico_estadual_e_estadual():
    assert (
        esfera_de("MPSC - Ministerio Publico do Estado de Santa Catarina - SC")
        == "estadual"
    )


def test_esfera_de_ministerio_publico_da_uniao_nao_decide():
    # MP da Uniao nao casa padrao algum: fail-open, devolve None.
    assert esfera_de("MPU - Ministerio Publico da Uniao") is None


# Estaduais: os padroes que faltavam na tabela.
@pytest.mark.parametrize(
    "nome",
    [
        "UEPG - Universidade Estadual de Ponta Grossa - PR",
        "TJSC - Tribunal de Justica de Santa Catarina - SC",
        "PMSC - Policia Militar de Santa Catarina - SC",
        "DPSC - Defensoria Publica do Estado de Santa Catarina - SC",
        "ALESC - Assembleia Legislativa de Santa Catarina - SC",
        "IMA - Instituto do Meio Ambiente do Estado de Santa Catarina - SC",
        "CODES - Companhia do Estado de Sergipe - SE",
    ],
)
def test_esfera_de_estadual_padroes_do_aceite(nome):
    assert esfera_de(nome) == "estadual"


# Conselho profissional: a sigla decide sozinha, sem "Conselho Regional"/
# "Conselho Federal" no mesmo nome.
@pytest.mark.parametrize(
    "nome",
    [
        "CRM - RS",
        "CRO - SP",
        "CREA - PR",
        "CRC - MG",
        "CRP/06 - SP",
        "CRA - RS",
        "COREN - RS",
        "OAB - Ordem dos Advogados do Brasil - SP",
    ],
)
def test_esfera_de_conselho_pela_sigla(nome):
    assert esfera_de(nome) == "conselho_profissional"
