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

LIMITE CONHECIDO (medido em 09/09/2026): esta porta NAO cobre concurso
nacional de estatal federal. O concurso da Dataprev ficou com inscricoes
abertas de 06/07 a 06/08/2026 e nao apareceu em nenhum dos seis garimpos do
Hermes rodados dentro da janela, apesar de "ANALISTA DE TECNOLOGIA DA
INFORMACAO" estar na taxonomia do proprio slug `tecnologia-da-informacao`.
Quem cobre esse caso e o :class:`~src.scrapers.pci_nacional_scraper.PciNacionalScraper`.

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

from bs4 import BeautifulSoup

from src.scrapers.base_scraper import BaseScraper
from src.scrapers.pci_comum import (
    datas_da_frase,
    extrair_data_fim,
    inferir_fase,
    montar_iso,
    para_texto,
)
from src.utils.text import extrair_uf

BASE_URL = "https://www.pciconcursos.com.br/cargos/"

_RE_PCI_ID = re.compile(r"\bn(\d+)\b")


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

    # --- delegacao para pci_comum -------------------------------------------
    # Ficam como metodos para nao quebrar chamadas existentes (inclusive nos
    # testes); a implementacao unica vive em src/scrapers/pci_comum.py, porque
    # o scraper da pagina nacional precisa exatamente das mesmas regras.

    _inferir_fase = staticmethod(inferir_fase)
    _para_texto = staticmethod(para_texto)
    _extrair_data_fim = staticmethod(extrair_data_fim)
    _datas_da_frase = staticmethod(datas_da_frase)
    _montar_iso = staticmethod(montar_iso)
