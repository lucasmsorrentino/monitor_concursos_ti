"""Scraper da lista de concursos NACIONAIS do PCI Concursos.

Por que existe: em 06/07/2026 saiu o edital da Dataprev — 1.823 vagas, 1.793
delas de Analista de Tecnologia da Informacao, banca FGV, inscricoes ate
06/08. O bot nao viu. Revisando as fontes em 09/09/2026:

- `blog.grancursosonline.com.br/concursos-ti/` e um artigo curado com
  `dateModified` travado em 12/06/2026. O edital saiu DEPOIS. Nunca teve como.
- `pciconcursos.com.br/cargos/<slug>` nao listou a Dataprev em nenhum dos seis
  garimpos rodados dentro da janela de inscricao (06/07, 11/07, 13/07, 25/07,
  27/07, 01/08), embora "ANALISTA DE TECNOLOGIA DA INFORMACAO" esteja na
  taxonomia do proprio slug `tecnologia-da-informacao`.

O que as duas fontes tem em comum e o ponto cego: **concurso nacional de
estatal federal**. Esta pagina e onde ele mora — hoje lista Transpetro, AgSUS
e DEPA, exatamente a mesma prateleira da Dataprev.

Endpoint: ``https://www.pciconcursos.com.br/concursos/nacional/`` (validado em
09/09/2026). Estrutura, um ``div.ca`` por concurso:

    <div class="ca">
      <a href=".../noticias/<slug>" rel="bookmark" title="<titulo da noticia>">
        Transpetro - Petrobras Transporte S.A.</a>
      <div class="cb"><img .../></div>
      <div class="cc"> </div>
      <div class="cd">Vagas até R$ 15.034,81<br><span>Vários Cargos<br>
        <span>Médio / Técnico / Superior</span></span></div>
      <div class="ce"><span>14/09/2026</span></div>
    </div>

Duas diferencas em relacao a pagina de cargo que mudam o desenho:

1. **Nao ha o `nXXXXXX`**, entao nao ha `pci_id`. A identidade e o link da
   noticia — que e exatamente o mesmo link canonico que as paginas de cargo
   usam, entao um concurso visto pelas duas portas casa por `link` no
   :meth:`DatabaseManager.buscar_registro` sem virar linha duplicada.
2. **O prazo esta na listagem** (coluna "Inscrição até"), ao contrario da
   pagina de cargo, que nunca traz. Isso deixa fase e prazo deterministicos
   sem abrir a noticia.

O que NAO da pra decidir aqui e a area: a coluna de cargos costuma dizer so
"Vários Cargos". Por isso o :class:`ConcursoBot` manda o item novo (e so o
novo) para a LLM decidir se e da area — sao poucos itens por dia, o oposto do
slug `professor`, que tem 1172 e por isso jamais poderia passar por LLM.
"""

import re
from datetime import date

from bs4 import BeautifulSoup

from src.scrapers.base_scraper import BaseScraper
from src.scrapers.pci_comum import extrair_data_fim, inferir_fase, montar_iso, para_texto

URL_NACIONAL = "https://www.pciconcursos.com.br/concursos/nacional/"

# Datas da coluna "Inscrição até": "14/09/2026" ou "16/09 a 16/10/2026".
_RE_DATA_CELULA = re.compile(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?")

# Quanto da noticia vai junto no bloco da LLM. O cargo aparece nos primeiros
# paragrafos; mandar a pagina inteira so encarece o prompt.
LIMITE_TEXTO_NOTICIA = 5000


class PciNacionalScraper(BaseScraper):
    """Le a lista de concursos nacionais abertos do PCI.

    ``capturar_concursos`` devolve dicts no mesmo formato do
    :class:`PciScraper` — ``ignorar``, ``nome``, ``status``, ``link``,
    ``fase``, ``data_fim_inscricao`` — com ``pci_id`` sempre ``None`` e os
    extras ``cargos``, ``nivel`` e ``vagas`` para alimentar o bloco da LLM.
    """

    def __init__(self, tentativas: int = 3):
        super().__init__(URL_NACIONAL, tentativas=tentativas)

    def capturar_concursos(self) -> list[dict]:
        """Devolve um item por concurso nacional aberto, deduplicado por link."""
        html = self.get_html()
        if not html:
            self.logger.warning("PCI nacional: pagina nao retornou HTML.")
            return []

        itens = self._parse(html)
        self.logger.info(f"PCI nacional: {len(itens)} concurso(s) na listagem.")
        return itens

    def _parse(self, html: str, hoje: date | None = None) -> list[dict]:
        """Extrai os itens da listagem. Deterministico, sem LLM."""
        hoje = hoje or date.today()
        soup = BeautifulSoup(html, "html.parser")
        por_link: dict[str, dict] = {}

        for card in soup.select("div.ca"):
            ancora = card.find("a", href=True)
            if not ancora:
                continue

            link = ancora["href"].strip()
            nome = " ".join(ancora.get_text(" ", strip=True).split())
            if not link or not nome:
                continue

            titulo = " ".join((ancora.get("title") or "").split())
            vagas, cargos, nivel = self._ler_celula_cargos(card)
            inicio, fim = self._janela_de_inscricao(self._texto_de(card, "ce"), hoje)

            item = {
                "ignorar": False,
                "nome": nome,
                "status": titulo or nome,
                "link": link,
                "fase": self._fase(titulo, inicio, fim, hoje),
                "data_fim_inscricao": fim,
                "data_referencia": None,
                "pci_id": None,
                "uf": None,          # nacional, por definicao nao tem UF
                "cargos": cargos,
                "nivel": nivel,
                "vagas": vagas,
                "inicio_inscricao": inicio,
                "fonte": "pci_nacional",
            }

            # Mesmo orgao pode ter dois editais na pagina (AgSUS tem dois hoje):
            # a chave e o link da noticia, nao o nome do orgao.
            por_link.setdefault(link, item)

        return list(por_link.values())

    @staticmethod
    def _texto_de(card, classe: str) -> str:
        """Texto de uma das celulas do card (`cd`, `ce`), ou string vazia."""
        celula = card.find("div", class_=classe)
        return " ".join(celula.get_text(" ", strip=True).split()) if celula else ""

    @staticmethod
    def _ler_celula_cargos(card) -> tuple[str, list[str], str]:
        """Quebra o `div.cd` em (vagas/salario, cargos, escolaridade).

        A celula aninha spans: o texto solto e vagas/salario, o span externo e
        a lista de cargos e o span interno a escolaridade.
        """
        celula = card.find("div", class_="cd")
        if not celula:
            return "", [], ""

        externo = celula.find("span")
        if not externo:
            return " ".join(celula.get_text(" ", strip=True).split()), [], ""

        interno = externo.find("span")
        nivel = " ".join(interno.get_text(" ", strip=True).split()) if interno else ""

        # get_text nos filhos diretos: o texto do span externo MENOS o interno.
        texto_cargos = " ".join(
            parte.strip()
            for parte in externo.find_all(string=True, recursive=False)
            if parte.strip()
        )
        cargos = [c.strip() for c in texto_cargos.split(",") if c.strip()]

        vagas = " ".join(
            parte.strip()
            for parte in celula.find_all(string=True, recursive=False)
            if parte.strip()
        )
        return vagas, cargos, nivel

    @staticmethod
    def _janela_de_inscricao(texto: str, hoje: date) -> tuple[str | None, str | None]:
        """(inicio, fim) em ISO a partir da coluna "Inscrição até".

        Formatos vistos: "14/09/2026" (so o fim) e "16/09 a 16/10/2026" (janela
        completa, com o ano so na segunda data). Quando falta o ano, herda o da
        ultima data que tem — e so entao cai no ano corrente.
        """
        achadas = _RE_DATA_CELULA.findall(texto or "")
        if not achadas:
            return None, None

        anos = [ano for _, _, ano in achadas if ano]
        ano_ref = anos[-1] if anos else str(hoje.year)

        datas = [iso for iso in (montar_iso(d, m, a or ano_ref) for d, m, a in achadas) if iso]
        if not datas:
            return None, None

        fim = datas[-1]
        inicio = datas[0] if len(datas) > 1 else None

        # Janela que vira o ano ("20/12 a 15/01/2027"): herdar o ano da segunda
        # data joga o inicio para depois do fim. Recua um ano.
        if inicio and inicio > fim:
            inicio = montar_iso(inicio[8:10], inicio[5:7], int(inicio[:4]) - 1)

        return inicio, fim

    @staticmethod
    def _fase(titulo: str, inicio: str | None, fim: str | None, hoje: date) -> str | None:
        """Fase pela janela de inscricao; o verbo do titulo e so o plano B.

        Aqui a janela ganha do titulo, ao contrario do :class:`PciScraper`.
        A coluna "Inscrição até" e um fato datado; o verbo, nao. "Transpetro
        publica editais retificados" casaria `edital_publicado` pela pista de
        titulo, quando o prazo na propria linha diz que as inscricoes estao
        abertas ate 14/09.
        """
        iso_hoje = hoje.isoformat()

        if inicio and inicio > iso_hoje:
            return "edital_publicado"      # edital na rua, inscricao ainda nao abriu
        if fim:
            return "inscricoes_encerradas" if fim < iso_hoje else "inscricoes_abertas"
        return inferir_fase(titulo)

    def detalhar(self, item: dict) -> dict:
        """Abre a noticia UMA vez e guarda o texto (e o prazo, se faltava).

        Chamado so para item que ainda nao esta no banco. O texto e o que
        permite a LLM decidir se o concurso e da area, ja que a listagem
        costuma dizer apenas "Vários Cargos".
        """
        if not item.get("link"):
            return item

        html = self.get_html(item["link"])
        if not html:
            self.logger.warning(f"PCI nacional: noticia de {item['nome']!r} nao abriu.")
            return item

        texto = para_texto(html)
        item["texto_noticia"] = texto[:LIMITE_TEXTO_NOTICIA]

        if not item.get("data_fim_inscricao"):
            prazo = extrair_data_fim(texto)
            if prazo:
                item["data_fim_inscricao"] = prazo
                self.logger.debug(f"PCI nacional: prazo {prazo} para {item['nome']!r}.")

        return item

    @staticmethod
    def bloco_para_ia(item: dict) -> str:
        """Monta o bloco compacto que vai para a `IntelligenceUnit`.

        Formato de bloco de blog (um `<h3>` e paragrafos) porque e o que o
        prompt de extracao espera. Os campos deterministicos vao explicitos no
        topo para a LLM nao ter que garimpa-los no corpo da noticia.
        """
        linhas = [f"<h3>{item.get('nome', '')}</h3>"]

        for rotulo, valor in (
            ("Notícia", item.get("status")),
            ("Cargos", ", ".join(item.get("cargos") or []) or None),
            ("Escolaridade", item.get("nivel")),
            ("Vagas e salário", item.get("vagas")),
            ("Inscrições até", item.get("data_fim_inscricao")),
        ):
            if valor:
                linhas.append(f"<p><b>{rotulo}:</b> {valor}</p>")

        link = item.get("link", "")
        linhas.append(f'<p><a href="{link}">{link}</a></p>')

        texto = item.get("texto_noticia")
        if texto:
            linhas.append(f"<div>{texto}</div>")

        return "\n".join(linhas)
