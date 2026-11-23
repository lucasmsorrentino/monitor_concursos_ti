"""Elegibilidade: a decisao do bot sobre notificar ou nao um concurso, com o motivo."""

from __future__ import annotations

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


def decidir(c: Candidato, p: Politica) -> Decisao:
    raise NotImplementedError
