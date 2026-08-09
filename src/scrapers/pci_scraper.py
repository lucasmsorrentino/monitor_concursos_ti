"""Scraper do PCI Concursos, por slug de cargo.

Por que existe: ate 08/2026 o bot lia so o blog do Gran Cursos, uma URL por
area. O Gran cobre quase so concursos estaduais e federais de grande porte.
O Hermes registrou em `~/.hermes/concursos-handoff/gaps.md`, em seis rodadas
(29/06 a 25/07), que o PCI listava de 44 a 54 concursos de TI abertos dos quais
o bot conhecia um ou dois — praticamente toda a camada municipal (prefeituras,
camaras, consorcios intermunicipais, conselhos regionais, autarquias) era
invisivel. A recomendacao "ingerir o PCI por slug de cargo" esta escrita
literalmente naqueles relatorios. Isto e ela.

Endpoint: ``https://www.pciconcursos.com.br/cargos/<slug>``, validado em
26/06, 04/07 e 08/08/2026. NAO usar o form "Pesquisa por Cargos" (campo JS sem
endpoint GET) nem ``/pesquisa/?q=``.

Diferenca importante para o :class:`GranScraper`: a pagina de cargo do PCI e
ESTRUTURADA, entao a extracao aqui e deterministica e nao passa pela LLM. Isso
nao e detalhe de estilo. O slug `professor` sozinho lista 1172 concursos; a
~15s por chamada do `claude -p`, mandar isso pra LLM levaria horas por rodada.
Parseando, sao milissegundos.

Formato de cada item na pagina (pares consecutivos de ``ul``):

    <ul class="link-d"><li><a href=".../noticias/<slug>"
       title="<titulo, quase sempre com o salario>"
       class="noticia_desc n294082">EMATER - ... - MG <small>..</small></a></li></ul>
    <ul class="link-i"><li><a href=".../concursos/vagas/<cargo>"
       title="Concursos para ANALISTA DE SISTEMAS">ANALISTA DE SISTEMAS</a></li></ul>

O ``nXXXXXX`` da classe e o id da noticia no PCI. E estavel entre rodadas e
vira a chave canonica de dedup (coluna `pci_id`), bem melhor que casar nome.
"""

import re
from datetime import date
from html import unescape

from bs4 import BeautifulSoup

from src.scrapers.base_scraper import BaseScraper
from src.utils.text import extrair_uf, normalizar_nome

BASE_URL = "https://www.pciconcursos.com.br/cargos/"

_RE_PCI_ID = re.compile(r"\bn(\d+)\b")

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


class PciScraper(BaseScraper):
    """Varre uma lista de slugs de cargo no PCI e devolve editais estruturados.

    Ao contrario dos outros scrapers, ``capturar_concursos`` devolve dicts JA
    no formato que a :class:`IntelligenceUnit` produziria, com ``ignorar``,
    ``nome``, ``status``, ``link``, ``fase`` e ``data_fim_inscricao``, mais os
    extras ``pci_id`` e ``uf``.
    """

    def __init__(self, slugs: list[str], tentativas: int = 3):
        super().__init__(BASE_URL, tentativas=tentativas)
        self.slugs = [s.strip() for s in slugs if s and s.strip()]

    def capturar_concursos(self) -> list[dict]:
        """Une os itens de todos os slugs, deduplicando por `pci_id`.

        Um mesmo concurso aparece em varios slugs (um edital de TI costuma
        listar analista E tecnico), entao a uniao por id e obrigatoria — sem
        ela o mesmo edital seria processado varias vezes na mesma rodada.
        """
        por_id: dict[str, dict] = {}

        for slug in self.slugs:
            html = self.get_html(f"{BASE_URL}{slug}")
            if not html:
                self.logger.warning(f"PCI: slug {slug!r} nao retornou HTML; seguindo.")
                continue

            itens = self._parse(html, slug)
            self.logger.info(f"PCI: slug {slug!r} rendeu {len(itens)} item(ns).")

            for item in itens:
                existente = por_id.get(item["pci_id"])
                if existente:
                    # Mesmo edital visto por outro cargo: acumula o cargo e segue.
                    for cargo in item["cargos"]:
                        if cargo not in existente["cargos"]:
                            existente["cargos"].append(cargo)
                else:
                    por_id[item["pci_id"]] = item

        self.logger.info(
            f"PCI: {len(por_id)} concurso(s) distinto(s) em {len(self.slugs)} slug(s)."
        )
        return list(por_id.values())

    def _parse(self, html: str, slug: str) -> list[dict]:
        """Extrai os itens de uma pagina de cargo. Deterministico, sem LLM."""
        soup = BeautifulSoup(html, "html.parser")
        itens = []

        for a in soup.select("a.noticia_desc"):
            pci_id = self._extrair_pci_id(a.get("class") or [])
            link = (a.get("href") or "").strip()
            if not pci_id or not link:
                continue

            # O <small> so carrega o icone de link externo; fora do nome.
            for small in a.find_all("small"):
                small.decompose()
            nome = " ".join(a.get_text(" ", strip=True).split())
            if not nome:
                continue

            titulo = " ".join((a.get("title") or "").split())

            itens.append({
                "ignorar": False,
                "nome": nome,
                "status": titulo or nome,
                "link": link,
                "fase": self._inferir_fase(titulo),
                "data_fim_inscricao": self._extrair_data_fim(titulo),
                "data_referencia": None,
                "pci_id": pci_id,
                "uf": extrair_uf(nome),
                "cargos": self._cargos_do_item(a),
                "fonte": "pci",
                "slug_origem": slug,
            })

        return itens

    @staticmethod
    def _extrair_pci_id(classes) -> str | None:
        """Pega o `nXXXXXX` do atributo class do link da noticia."""
        for c in classes:
            m = _RE_PCI_ID.fullmatch(c)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _cargos_do_item(a) -> list[str]:
        """Cargos listados no `ul.link-i` que segue o `ul.link-d` deste item."""
        bloco = a.find_parent("ul", class_="link-d")
        if not bloco:
            return []
        vizinho = bloco.find_next_sibling("ul", class_="link-i")
        if not vizinho:
            return []
        return [
            " ".join(link.get_text(" ", strip=True).split())
            for link in vizinho.select("a")
            if link.get_text(strip=True)
        ]

    @staticmethod
    def _inferir_fase(titulo: str) -> str | None:
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

    def enriquecer(self, item: dict) -> dict:
        """Abre a noticia do item e preenche `data_fim_inscricao`.

        Chamado SO para item novo. A pagina de cargo nunca traz o prazo (medido:
        0 de 55 itens), e o prazo e o que decide se um edital esta ativo em
        `_decidir_e_notificar`. Depois da carga inicial isso e um punhado de
        requisicoes por dia.
        """
        if item.get("data_fim_inscricao") or not item.get("link"):
            return item

        html = self.get_html(item["link"])
        if not html:
            return item

        prazo = self._extrair_data_fim(self._para_texto(html))
        if prazo:
            item["data_fim_inscricao"] = prazo
            self.logger.debug(f"PCI: prazo {prazo} para {item['nome']!r}.")
        return item

    @staticmethod
    def _para_texto(html: str) -> str:
        """HTML para texto corrido, preservando a pontuacao das frases."""
        limpo = _RE_TAGS.sub(" ", html)
        texto = _RE_QUALQUER_TAG.sub(" ", limpo)
        return re.sub(r"\s+", " ", unescape(texto))

    @classmethod
    def _extrair_data_fim(cls, texto: str) -> str | None:
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
            datas = cls._datas_da_frase(frase)
            if datas:
                return max(datas)
        return None

    @classmethod
    def _datas_da_frase(cls, frase: str) -> list[str]:
        """Todas as datas ISO validas de uma frase, extenso e numerica."""
        achadas = []

        for dia, mes_txt, ano in _RE_DATA_EXTENSO.findall(frase):
            mes = _MESES.get(normalizar_nome(mes_txt))
            if mes and ano:
                iso = cls._montar_iso(dia, mes, ano)
                if iso:
                    achadas.append(iso)

        for dia, mes, ano in _RE_DATA_NUM.findall(frase):
            if ano:
                iso = cls._montar_iso(dia, mes, ano)
                if iso:
                    achadas.append(iso)

        return achadas

    @staticmethod
    def _montar_iso(dia, mes, ano) -> str | None:
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
