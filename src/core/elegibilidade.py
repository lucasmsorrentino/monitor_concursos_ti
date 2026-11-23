"""Elegibilidade: a decisao do bot sobre notificar ou nao um concurso, com o motivo.

Funcao pura sobre primitivos. Quem chama monta o ``Candidato`` (uf, regiao,
esfera, teto do concurso, total de cargos, estrela do usuario) e a ``Politica``
da area; ``decidir`` so decide. O modulo nao conhece o bot, o banco nem os
scrapers.

Regras (SPEC-001 secao 4.2), a primeira que casa vence:

  0. ``seguindo``           -> entra (a estrela nunca se contorna)
  1. modo != "ativo"        -> entra, ``filtro_desligado``
  2. uf e regiao ausentes   -> entra com selo, ``nao_verificado``
  3. uf sem corte ou Sul    -> entra, ``sul`` ("NACIONAL" nao e Sul)
  4. esfera sem corte       -> entra, ``federal``
  5. teto < corte           -> FILTRADO, ``abaixo_do_corte``
  6. municipal e cargos_total > limite -> FILTRADO, ``municipal_inflado``
  7. teto desconhecido      -> entra com selo, ``sem_evidencia``
  8. resto                  -> entra, ``acima_do_corte``

So as regras 5 e 6 recusam. Fail-open: qualquer ``modo`` diferente de
"ativo" (inclusive com espaco ou em maiuscula) cai na regra 1, e campo
ausente nunca filtra por si so. UF, regiao e esfera comparam sem caixa e
sem acento; texto vazio conta como desconhecido.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

SELO_NAO_VERIFICADO = "⚠️ salario nao verificado"

MOTIVOS = frozenset({
    "seguindo",
    "filtro_desligado",
    "nao_verificado",
    "sul",
    "federal",
    "abaixo_do_corte",
    "municipal_inflado",
    "sem_evidencia",
    "acima_do_corte",
})


@dataclass(frozen=True)
class Candidato:
    uf: str | None
    regiao: str | None
    esfera: str | None
    teto: float | None
    cargos_total: int | None
    seguindo: bool = False


@dataclass(frozen=True)
class Politica:
    modo: str = "desligado"               # "desligado" | "ativo"
    corte_fora_sul: float = 0.0
    ufs_sem_corte: tuple[str, ...] = ("PR", "SC", "RS")
    esferas_sem_corte: tuple[str, ...] = ("federal",)
    cargos_total_inflado: int = 10


@dataclass(frozen=True)
class Decisao:
    entra: bool
    motivo: str
    selo: str | None = None


def _norm(valor) -> str | None:
    """Caixa e acento fora; vazio vira desconhecido."""
    if not isinstance(valor, str):
        return None
    sem_acento = "".join(
        ch for ch in unicodedata.normalize("NFKD", valor)
        if not unicodedata.combining(ch)
    )
    return sem_acento.strip().casefold() or None


def _contem(valor: str | None, colecao) -> bool:
    alvo = _norm(valor)
    return alvo is not None and alvo in {_norm(x) for x in colecao}


def decidir(c: Candidato, p: Politica) -> Decisao:
    if c.seguindo:
        return Decisao(True, "seguindo")
    if p.modo != "ativo":
        return Decisao(True, "filtro_desligado")

    uf = _norm(c.uf)
    regiao = _norm(c.regiao)
    if uf is None and regiao is None:
        return Decisao(True, "nao_verificado", SELO_NAO_VERIFICADO)
    if _contem(uf, p.ufs_sem_corte) or regiao == "sul":
        return Decisao(True, "sul")
    if _contem(c.esfera, p.esferas_sem_corte):
        return Decisao(True, "federal")
    if c.teto is not None and c.teto < p.corte_fora_sul:
        return Decisao(False, "abaixo_do_corte")
    if (_norm(c.esfera) == "municipal" and c.cargos_total is not None
            and c.cargos_total > p.cargos_total_inflado):
        return Decisao(False, "municipal_inflado")
    if c.teto is None:
        return Decisao(True, "sem_evidencia", SELO_NAO_VERIFICADO)
    return Decisao(True, "acima_do_corte")
