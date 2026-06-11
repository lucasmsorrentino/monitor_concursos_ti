"""Vocabulario controlado de fases de concurso.

A deteccao de mudanca do bot compara a FASE (estagio do concurso) em vez do
texto livre do `status`. A LLM reformula o status a cada extracao (muda
palavras, adiciona ou remove detalhes), o que fazia o hash de texto variar e
disparar falsos positivos de "atualizacao". A fase e um rotulo de um conjunto
fechado e ordenado, estavel entre extracoes — reescrita nao muda a fase.

So ha notificacao de atualizacao quando a fase AVANCA ou a data de fim de
inscricao muda. Para amortecer flapping da LLM (classificar o mesmo concurso
ora numa fase, ora na adjacente), apenas avancos contam; regressoes sao
ignoradas e a fase mais avancada ja vista e preservada.
"""

# Ordem de avanco do concurso. O indice define a progressao.
FASES_ORDEM = (
    "previsto",
    "banca_definida",
    "edital_publicado",
    "inscricoes_abertas",
    "inscricoes_encerradas",
    "concluido",
)

FASE_LABEL = {
    "previsto": "Previsto",
    "banca_definida": "Banca definida",
    "edital_publicado": "Edital publicado",
    "inscricoes_abertas": "Inscrições abertas",
    "inscricoes_encerradas": "Inscrições encerradas",
    "concluido": "Concluído",
}

_FASES_SET = set(FASES_ORDEM)


def sanitizar_fase(valor) -> str | None:
    """Normaliza a fase extraida pela LLM; retorna None se invalida/ausente."""
    if not valor or not isinstance(valor, str):
        return None
    fase = valor.strip().lower()
    return fase if fase in _FASES_SET else None


def indice_fase(fase: str | None) -> int:
    """Indice de avanco da fase no vocabulario; -1 se desconhecida/None."""
    try:
        return FASES_ORDEM.index(fase)
    except ValueError:
        return -1


def fase_avancou(antiga: str | None, nova: str | None) -> bool:
    """True se `nova` e uma fase estritamente mais avancada que `antiga`.

    Ambas precisam ser fases validas conhecidas. Regressoes e fases
    desconhecidas/None retornam False (nao geram notificacao).
    """
    i_antiga = indice_fase(antiga)
    i_nova = indice_fase(nova)
    return i_nova >= 0 and i_antiga >= 0 and i_nova > i_antiga


def fase_mais_avancada(a: str | None, b: str | None) -> str | None:
    """Retorna a fase mais avancada entre as duas (preserva o maximo ja visto)."""
    return a if indice_fase(a) >= indice_fase(b) else b


def label(fase: str | None) -> str:
    """Rotulo legivel da fase para mensagens."""
    return FASE_LABEL.get(fase or "", "Fase desconhecida")
