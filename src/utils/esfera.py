"""Classificacao da esfera do orgao pelo nome do orgao (SPEC-001, secao 3.3).

O PCI so da o nome do orgao, e a elegibilidade isenta do corte salarial a
esfera `federal` (ADR-0002: universidade e instituto federal pagam a tabela
federal, fora do alcance do corte de TI). Este modulo e so o classificador:
funcao pura, sem dependencia externa, sem olhar de onde o nome veio nem o que
a esfera libera na elegibilidade.

A comparacao e insensivel a acento e a caixa: o nome passa por
`normalizar_nome` (de `src/utils/text.py`) antes de qualquer casamento.

Precedencia quando padroes de esferas diferentes casam no mesmo nome,
declarada no aceite do modulo:

    conselho_profissional > municipal > federal > distrital > estadual

Ela resolve os pares reais: "Conselho Regional ... da 5a Regiao" nao e
estadual; "Instituto de Previdencia do Municipio de ..." nao e estadual;
"Universidade do Estado de Minas Gerais" nao e federal (o que casa e
"universidade federal", expressao inteira, nao a palavra "universidade").

Duas excecoes ao pe da letra dos padroes, para as listas cumprirem o que
declaram:

- "Ministerio" casa federal (ministerio de Estado), mas "Ministerio Publico"
  nao e ministerio: fica fora do federal. O MP estadual casa pelo padrao
  proprio ("ministerio publico do estado"); MP da Uniao ou do Trabalho nao
  casa nada e devolve None — fail-open, a elegibilidade decide pelo teto.
- "Camara" casa municipal, menos "Camara Legislativa", que e do Distrito
  Federal: cai no padrao distrital ("do distrito federal").

A UF DF no sufixo do nome so decide distrital quando nenhum padrao decidiu
antes ("TRF1 - Tribunal Regional Federal da 1a Regiao - DF" e federal).
Nome que nao casa nada devolve None — inclusive None e string vazia. Esfera
desconhecida nao isenta do corte nem condena: quem decide e a elegibilidade.
"""

from src.utils.text import extrair_uf, normalizar_nome

# Padroes casados sobre o nome ja normalizado (sem acento, em minusculas,
# com espaco nas duas pontas para casar palavra/expressao inteira).

_PADROES_CONSELHO = (
    "conselho regional",
    "conselho federal",
    "crm",
    "cro",
    "crea",
    "crc",
    "crp",
    "cra",
    "coren",
    "oab",
)

_PADROES_MUNICIPAL = (
    "prefeitura",
    "consorcio intermunicipal",
    "municipio de",
    "secretaria municipal",
    "instituto de previdencia do municipio",
    "fundo municipal",
)

# "Ministerio" fica fora da tupla porque nao e uma expressao como as outras:
# valeria de menos (Ministerio da Saude) e e a unica que precisa de excecao
# ("Ministerio Publico" nao e ministerio).
_PADROES_FEDERAL = (
    "universidade federal",
    "fundacao universidade federal",
    "universidade tecnologica federal",
    "instituto federal",
    "tribunal regional federal",
    "tribunal regional do trabalho",
    "tribunal regional eleitoral",
    "policia federal",
    "policia rodoviaria federal",
    "justica federal",
    "caixa economica federal",
    "banco do brasil",
    "correios",
    "dataprev",
    "transpetro",
    "petrobras",
    "serpro",
    "embrapa",
    "infraero",
    "conab",
)

_PADROES_DISTRITAL = (
    "do distrito federal",
    "distrital",
)

_PADROES_ESTADUAL = (
    "universidade do estado",
    "universidade estadual",
    "secretaria de estado",
    "tribunal de contas do estado",
    "tribunal de justica",
    "policia civil",
    "policia militar",
    "defensoria publica do estado",
    "ministerio publico do estado",
    "assembleia legislativa",
    "instituto do meio ambiente do estado",
    "companhia do estado",
    "banco do estado",
)


def _algum(bloco: str, padroes: tuple[str, ...]) -> bool:
    # Espaco nas duas pontas do padrao tambem: casamento por palavra/expressao
    # inteira, para sigla nao casar dentro de palavra ("cro" em "microrregiao").
    return any(f" {padrao} " in bloco for padrao in padroes)


def _e_conselho(bloco: str) -> bool:
    return _algum(bloco, _PADROES_CONSELHO)


def _e_municipal(bloco: str) -> bool:
    if " camara " in bloco and " camara legislativa " not in bloco:
        return True
    return _algum(bloco, _PADROES_MUNICIPAL)


def _e_federal(bloco: str) -> bool:
    if _algum(bloco, _PADROES_FEDERAL):
        return True
    # Ministerio de Estado (Ministerio da Saude), nunca Ministerio Publico:
    # o MP nao e ministerio, e o estadual se casa pelo padrao proprio dele.
    return " ministerio " in bloco and " ministerio publico " not in bloco


def _e_distrital(bloco: str) -> bool:
    return _algum(bloco, _PADROES_DISTRITAL)


def _e_estadual(bloco: str) -> bool:
    return _algum(bloco, _PADROES_ESTADUAL)


def esfera_de(nome: str | None) -> str | None:
    """Devolve a esfera do orgao, ou None quando o nome nao decide."""
    if not nome:
        return None
    bloco = f" {normalizar_nome(nome)} "

    # Precedencia declarada no aceite:
    # conselho_profissional > municipal > federal > distrital > estadual.
    if _e_conselho(bloco):
        return "conselho_profissional"
    if _e_municipal(bloco):
        return "municipal"
    if _e_federal(bloco):
        return "federal"
    if _e_distrital(bloco):
        return "distrital"
    if _e_estadual(bloco):
        return "estadual"

    # UF DF no sufixo so quando nada mais decide.
    if extrair_uf(nome) == "DF":
        return "distrital"
    return None
