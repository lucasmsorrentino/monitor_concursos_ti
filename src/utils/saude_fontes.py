"""Diagnostico por FONTE: a fonte trouxe materia-prima, e ela ainda muda?

Por que existe (medido em 09/09/2026): o alvo do Gran da area TI,
`blog.grancursosonline.com.br/concursos-ti/`, e um artigo curado com
`dateModified` travado em **12/06/2026**. Ele devolveu os mesmos 45 blocos em
06/07 e em 09/09 — 89 dias sem uma unica alteracao. Nenhum concurso publicado
depois de 12/06 podia chegar por ali, e o edital da Dataprev saiu em julho.

O bot nao tinha como perceber. O alerta de cegueira era agregado:

    sem_materia_prima = total_blocos == 0 and not self.pci_scraper

Ou seja, depois que o PCI entrou como segunda fonte (08/08), o Gran podia
voltar zero — ou voltar sempre a mesma coisa — para sempre, calado.

Este modulo registra, por (area, fonte), o digest da materia-prima e a data em
que ele mudou pela ultima vez. Duas patologias saem daqui:

- **vazia**: a fonte nao devolveu nada nesta rodada.
- **parada**: a fonte devolve conteudo, mas identico ha dias demais.

O estado vive em `data/saude_fontes.json` (ver :mod:`src.utils.memoria_json`).
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import date

from src.utils import memoria_json

ARQUIVO = "saude_fontes"

# Dias de conteudo identico antes de considerar a fonte parada. Uma pagina de
# listagem viva muda toda semana; 21 dias e folgado o bastante para nao gritar
# por causa de feriado ou de um alvo de nicho, e curto o bastante para pegar os
# 89 dias do concursos-ti/ ainda em junho.
DIAS_PARADA_PADRAO = 21


@dataclass(frozen=True)
class Diagnostico:
    """Resultado da checagem de uma fonte em uma rodada."""

    fonte: str
    itens: int
    dias_sem_mudanca: int
    vazia: bool
    parada: bool

    @property
    def saudavel(self) -> bool:
        return not (self.vazia or self.parada)


def digest(assinaturas) -> str:
    """sha1 curto de um conjunto de assinaturas, estavel entre rodadas.

    Ordena antes de somar: a ordem dos itens na pagina muda sozinha (destaque,
    patrocinio) sem que o conteudo tenha mudado, e isso nao pode contar como
    atualizacao — senao a fonte parada nunca seria detectada.
    """
    texto = "\n".join(sorted(str(a) for a in assinaturas))
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:16]


def avaliar(
    area: str,
    fonte: str,
    assinaturas,
    dias_parada: int = DIAS_PARADA_PADRAO,
    hoje: date | None = None,
) -> Diagnostico:
    """Registra a rodada desta fonte e devolve o diagnostico.

    Args:
        area: slug da area (o mesmo alvo pode ler fontes diferentes).
        fonte: identificador curto da fonte (`gran`, `pci`, `pci_nacional`).
        assinaturas: iteravel com uma marca por item bruto — bloco de HTML,
            `pci_id`, link. E o conteudo que decide se a fonte mudou.
        dias_parada: limite de dias sem mudanca antes de acusar `parada`.
        hoje: injetavel para teste.
    """
    hoje = hoje or date.today()
    itens = list(assinaturas)
    chave = f"{area}::{fonte}"

    estado = memoria_json.carregar(ARQUIVO)
    anterior = estado.get(chave) or {}

    if not itens:
        # Fonte vazia nao atualiza o digest: um dia de site fora nao pode
        # reiniciar o contador de "parada ha N dias" nem mascarar a estagnacao.
        memoria_json.salvar(ARQUIVO, {**estado, chave: {**anterior, "visto_em": hoje.isoformat()}})
        return Diagnostico(fonte, 0, _dias_desde(anterior.get("mudou_em"), hoje), True, False)

    atual = digest(itens)
    mudou_em = anterior.get("mudou_em")

    if anterior.get("digest") != atual:
        mudou_em = hoje.isoformat()

    memoria_json.salvar(ARQUIVO, {
        **estado,
        chave: {
            "digest": atual,
            "mudou_em": mudou_em,
            "visto_em": hoje.isoformat(),
            "itens": len(itens),
        },
    })

    dias = _dias_desde(mudou_em, hoje)
    return Diagnostico(fonte, len(itens), dias, False, dias > dias_parada)


def _dias_desde(iso: str | None, hoje: date) -> int:
    """Dias entre `iso` e hoje. Sem registro anterior, zero (nada a acusar)."""
    if not iso:
        return 0
    try:
        return max(0, (hoje - date.fromisoformat(iso)).days)
    except (TypeError, ValueError):
        logging.getLogger(__name__).warning(f"Data invalida no estado de saude: {iso!r}")
        return 0
