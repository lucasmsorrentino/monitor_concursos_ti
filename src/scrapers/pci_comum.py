"""Peças compartilhadas entre os scrapers do PCI Concursos.

Existem duas portas de entrada no PCI e elas precisam concordar:

- ``/cargos/<slug>`` (:class:`~src.scrapers.pci_scraper.PciScraper`) — cobre a
  camada municipal e estadual, mas NAO listou o concurso da Dataprev em nenhum
  dos seis garimpos rodados entre 06/07 e 01/08/2026, com as inscricoes abertas
  o tempo todo.
- ``/concursos/nacional/``
  (:class:`~src.scrapers.pci_nacional_scraper.PciNacionalScraper`) — a lista de
  concursos NACIONAIS abertos, que e onde estatais federais como Dataprev,
  Transpetro e Correios aparecem.

Inferir fase pelo verbo do titulo e achar o prazo dentro da frase de inscricao
e identico nos dois casos, entao mora aqui em vez de ser copiado.
"""

import re
from datetime import date
from html import unescape

from src.utils.text import normalizar_nome

_MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11,
    "dezembro": 12,
}

_RE_TAGS = re.compile(r"<(script|style)\b.*?</\1>", re.DOTALL | re.IGNORECASE)
_RE_QUALQUER_TAG = re.compile(r"<[^>]+>")

# Prazo por extenso: "31 de agosto de 2026". A noticia do PCI escreve assim.
_RE_DATA_EXTENSO = re.compile(
    r"(\d{1,2})\s+de\s+([a-z]+)(?:\s+de\s+(\d{4}))?",
    re.IGNORECASE,
)
# Prazo numerico: "31/08/2026" ou "31/08".
_RE_DATA_NUM = re.compile(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?")

# Frases que carregam o prazo DE INSCRICAO, e nao o de isencao, recurso ou prova.
_RE_FRASE_INSCRICAO = re.compile(r"[^.!?]*inscri[^.!?]*[.!?]", re.IGNORECASE)

# Pistas FORTES: o verbo do titulo diz a fase. Ordem importa, a primeira que
# casar vence, entao a fase mais avancada vem antes.
_PISTAS_FASE = (
    ("inscricoes_encerradas", ("encerra as inscricoes", "inscricoes encerradas",
                               "encerra inscricoes", "ultimo dia de inscricao")),
    ("inscricoes_abertas", ("abre inscricoes", "inscricoes abertas", "reabre inscricoes",
                            "reabre as inscricoes", "recebe inscricoes", "prorroga as inscricoes",
                            "prorroga inscricoes", "inscricoes prorrogadas")),
    # `previsto` vem ANTES de edital_publicado de proposito: "anuncia concurso
    # com salarios de ate R$ X" tem o verbo de anuncio e a pista fraca de
    # salario ao mesmo tempo, e quem manda e o verbo.
    ("previsto", ("anuncia concurso", "anuncia concursos", "autoriza concurso",
                  "preve concurso", "tera concurso", "autoriza a realizacao")),
    ("edital_publicado", ("publica edital", "publica editais", "edital de concurso",
                          "abre concurso", "abre concursos", "abrem concurso", "abrem concursos",
                          "abre processo seletivo", "abre processos seletivos",
                          "abrem processo seletivo", "abre selecao", "abrem selecao",
                          "abre selecoes", "retifica", "lanca edital", "lanca editais",
                          "lancam edital", "lancam editais", "lanca concurso", "lancam concurso",
                          "divulga edital", "divulga editais")),
    ("banca_definida", ("define banca", "banca organizadora", "contrata banca", "banca definida")),
)

# Pistas FRACAS: aparecem em titulo de qualquer fase e nao servem para
# discriminar. So valem como ultimo recurso, quando nenhum verbo casou —
# indicam que ja existe edital com cargos e salario publicados.
_PISTAS_FRACAS = (
    "oferece vagas", "com vagas para", "concurso publico oferece",
    "processo seletivo oferece", "com salarios de ate", "com salarios iniciais de ate",
    "com remuneracoes de ate", "com vagas imediatas", "vagas e cadastro de reserva",
)


def inferir_fase(titulo: str) -> str | None:
    """Deduz a fase pelo verbo do titulo da noticia. None quando nao da."""
    if not titulo:
        return None
    t = normalizar_nome(titulo)
    for fase, pistas in _PISTAS_FASE:
        if any(p in t for p in pistas):
            return fase
    if any(p in t for p in _PISTAS_FRACAS):
        return "edital_publicado"
    return None


def para_texto(html: str) -> str:
    """HTML para texto corrido, preservando a pontuacao das frases."""
    limpo = _RE_TAGS.sub(" ", html)
    texto = _RE_QUALQUER_TAG.sub(" ", limpo)
    return re.sub(r"\s+", " ", unescape(texto))


def extrair_data_fim(texto: str) -> str | None:
    """Ultima data citada na frase que fala de inscricao, em ISO.

    Restringir a frase e essencial: as noticias trazem varios prazos
    proximos ("inscricoes de 31/07 a 31/08 ... isencao ate 5 de agosto ...
    provas em 6 de dezembro"). Pegar a maior data do texto todo devolveria a
    data da prova. Dentro da frase de inscricao, a ULTIMA data e o fim da
    janela — vale tanto para "de X a Y" quanto para "ate Y".
    """
    if not texto:
        return None

    for frase in _RE_FRASE_INSCRICAO.findall(texto):
        datas = datas_da_frase(frase)
        if datas:
            return max(datas)
    return None


def datas_da_frase(frase: str) -> list[str]:
    """Todas as datas ISO validas de uma frase, extenso e numerica."""
    achadas = []

    for dia, mes_txt, ano in _RE_DATA_EXTENSO.findall(frase):
        mes = _MESES.get(normalizar_nome(mes_txt))
        if mes and ano:
            iso = montar_iso(dia, mes, ano)
            if iso:
                achadas.append(iso)

    for dia, mes, ano in _RE_DATA_NUM.findall(frase):
        if ano:
            iso = montar_iso(dia, mes, ano)
            if iso:
                achadas.append(iso)

    return achadas


def montar_iso(dia, mes, ano) -> str | None:
    """Valida (dia, mes, ano) de verdade e devolve ISO, ou None."""
    try:
        d, m, a = int(dia), int(mes), int(ano)
    except (TypeError, ValueError):
        return None

    if a < 100:
        a += 2000
    if not (2020 <= a <= 2099):
        return None

    try:
        return date(a, m, d).isoformat()   # rejeita 31/02 e afins
    except ValueError:
        return None
