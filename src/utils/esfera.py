"""Classificacao da esfera do orgao pelo nome (SPEC-001, secao 3.3)."""

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
