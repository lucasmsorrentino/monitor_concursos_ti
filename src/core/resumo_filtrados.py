"""Montagem do texto do resumo semanal de concursos filtrados.

Cortar concurso da notificacao so e auditavel se der para conferir o que foi
silenciado: uma vez por semana, por area, sai uma mensagem com a contagem por
motivo e a lista do que ficou de fora. Este modulo monta o texto a partir de
linhas prontas (nome do orgao, uf, salario_teto, motivo_filtro) e entrega a
chave da semana ISO para o controle de "uma vez por semana". Nao le banco,
nao fala com o Telegram e nao e chamado por ninguem ainda.
"""

from collections import Counter
from datetime import date
import html

# Rotulo legivel de cada motivo que filtra, para a mensagem nao mostrar o
# identificador cru. Motivo fora do mapa entra com o proprio identificador:
# e um resumo, nao um validador.
ROTULOS_MOTIVO = {
    "abaixo_do_corte": "abaixo do corte",
    "municipal_inflado": "teto de outro cargo",
}

# Teto ausente nao pode virar "None" nem "R$ 0,00": e evidencia de leitura
# que faltou, nao teto zero.
TETO_NAO_LIDO = "teto nao lido"

# UF ausente significa concurso nacional.
UF_NACIONAL = "Nacional"


def _formatar_real(valor: float) -> str:
    """Formata teto em reais no padrao brasileiro (R$ 1.000.000,00).

    Sem `locale`, que depende do sistema: a producao e Linux e o
    desenvolvimento e Windows, e o troca-troca de separador e feito a mao a
    partir de f"{valor:,.2f}", que e deterministico.
    """
    inteiro, centavos = f"{valor:,.2f}".split(".")
    return f"R$ {inteiro.replace(',', '.')},{centavos}"


def _rotulo_de(motivo) -> str:
    """Rotulo legivel do motivo; identificador desconhecido entra cru."""
    return ROTULOS_MOTIVO.get(motivo, motivo)


def _linha_de_texto(linha: dict) -> str:
    """Monta uma linha da lista: orgao, UF, teto e motivo, tudo escapado."""
    nome = html.escape(str(linha.get("nome", "?")))
    uf = html.escape(linha.get("uf") or UF_NACIONAL)
    teto = linha.get("salario_teto")
    valor = _formatar_real(teto) if teto is not None else TETO_NAO_LIDO
    motivo = html.escape(str(_rotulo_de(linha.get("motivo_filtro"))))
    return f"• {nome} ({uf}) — {valor} — {motivo}"


def montar(linhas: list[dict], area_nome: str, limite: int = 30) -> str | None:
    """Monta a mensagem HTML do resumo semanal de filtrados de uma area.

    A mensagem traz, nesta ordem: titulo com o nome da area; contagem total;
    contagem por motivo, em ordem decrescente; e a lista das linhas, no maximo
    `limite`, com o resto resumido em "e mais N" — e a contagem do topo segue
    sendo a total, nao a listada. Cada linha mostra nome do orgao, UF, teto em
    reais no padrao brasileiro e o motivo com rotulo legivel; teto ausente sai
    como "teto nao lido" e UF ausente como "Nacional". Todo texto que vem das
    linhas passa por html.escape.

    Semana sem nada filtrado nao manda mensagem: lista vazia devolve None.
    """
    if not linhas:
        return None

    total = len(linhas)
    contagens = Counter(_rotulo_de(linha.get("motivo_filtro")) for linha in linhas)
    partes = [
        f"🔇 <b>{area_nome}: filtrados da semana</b>\n\n",
        f"Silenciei <b>{total}</b> concurso(s) nos ultimos 7 dias.\n\n",
        "Por motivo:\n",
    ]
    partes.extend(f"• {rotulo}: {qtd}\n" for rotulo, qtd in contagens.most_common())
    partes.append("\n")
    partes.extend(_linha_de_texto(linha) + "\n" for linha in linhas[:limite])
    if total > limite:
        partes.append(f"\ne mais {total - limite}")
    return "".join(partes)


def marcador_da_semana(hoje: date) -> str:
    """Devolve a chave da semana ISO da data, no formato "2026-S47".

    E o marcador do controle de "uma vez por semana" do resumo. Usa o ano e a
    semana ISO (date.isocalendar()), nao o ano civil: 2027-01-03 e domingo da
    semana 53 do ano ISO 2026 e precisa devolver a mesma chave de 2026-12-28.
    """
    raise NotImplementedError("marcador_da_semana ainda nao esta implementado")
