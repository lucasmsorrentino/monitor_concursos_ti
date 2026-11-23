"""Porta do PCI Concursos pelo servidor MCP oficial (buscar_por_cargo).

O servidor (`https://mcp.pciconcursos.com.br/mcp`, sem autenticacao, somente
leitura) devolve ja estruturado o que as portas de HTML (`PciScraper`, por
pagina de cargo, e `PciNacionalScraper`, pela lista nacional) liam raspando
pagina — e mais: `regiao`, `cargos_total`, o teto do concurso e as datas de
inscricao JA calculadas. A decisao de trocar a porta esta na ADR-0001; este
modulo e so a porta, ninguem liga no bot aqui.

Transporte
----------

Um POST JSON-RPC 2.0 por termo de cargo, com os cabecalhos
``Content-Type: application/json``, ``Accept: application/json, text/event-stream``
e ``MCP-Protocol-Version: 2025-06-18``. O pedido chama ``tools/call`` com a
ferramenta ``buscar_por_cargo`` e ``arguments`` so com ``cargo``: sem o
parametro ``uf`` a busca cobre todos os estados e os nacionais. O servidor
respondeu ``tools/call`` direto, sem handshake de sessao, nas verificacoes
feitas antes desta porta existir; se passar a exigir, o sintoma aparece na
sonda de contrato antes de virar mudanca aqui.

A resposta chega em duas formas, ambas lidas: JSON direto no corpo, ou SSE com
uma linha ``data: `` carregando o JSON. Nas duas, o payload util e o primeiro
item de ``result.content`` com ``type == "text"``, cujo ``text`` e um JSON em
string que precisa de um segundo ``json.loads`` — o envelope carrega o payload
embutido, e e ai que se erra.

Regras da porta
---------------

- Uniao por ``id`` (o mesmo numero de noticia que o ``PciScraper`` extrai do
  ``nXXXXXX`` da classe CSS, mantido como ``pci_id`` em string): concurso visto
  por varios termos aparece uma vez, acumulando ``cargos`` e ``termos_origem``.
- ``nome`` leva a UF no sufixo (``titulo - UF``), para o ``extrair_uf`` e o
  ``mesma_entidade`` de ``src/utils/text.py`` casarem o mesmo concurso vindo do
  blog do Gran; concurso NACIONAL (``uf`` nula) fica so com o titulo.
- ``fase`` vem das datas calculadas pelo servidor: ``datas.aberto`` =>
  ``inscricoes_abertas``; ``datas.em_breve`` => ``edital_publicado``; sem as
  duas, cai no ``inferir_fase`` do titulo da noticia, em ``pci_comum``.
- ``vagas_salario`` sai cru: o parse do teto mora em outro modulo.
- Termo sem resultado (campo ``message`` com ``data`` vazia) e logado em
  ``info`` e segue; nao se repete a chamada.
- Termo que falha (rede, HTTP diferente de 200, JSON invalido, resposta sem o
  ``content`` esperado) e logado em ``warning`` e a varredura segue com os
  outros termos. Todos os termos falhando levanta excecao, para a fonte poder
  ser diagnosticada como parada.
- Termo com ``meta.total`` no limite de 200 itens do servidor e logado em
  ``warning`` como lista truncada.

O dado do PCI e estruturado e a extracao aqui e deterministica: nada deste
modulo passa pela LLM.
"""
import json
import time

import requests

from src.scrapers.base_scraper import BACKOFF_BASE_S, BaseScraper
from src.scrapers.pci_comum import inferir_fase

URL_SERVIDOR = "https://mcp.pciconcursos.com.br/mcp"
PROTOCOLO_MCP = "2025-06-18"
LIMITE_TRUNCAMENTO = 200
TIMEOUT_S = 15


class PciMcpScraper(BaseScraper):
    """Porta do PCI que chama a ferramenta ``buscar_por_cargo`` do servidor MCP."""

    def __init__(self, termos: list[str], tentativas: int = 3):
        super().__init__(URL_SERVIDOR, tentativas=tentativas)
        self.termos = [t.strip() for t in termos if t and t.strip()]
        self.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOLO_MCP,
        })

    def capturar_concursos(self) -> list[dict]:
        """Uniao dos itens de um POST por termo, deduplicada por `id`."""
        por_id: dict[str, dict] = {}
        falharam = 0

        for termo in self.termos:
            try:
                payload = self._chamar(termo)
            except Exception as e:
                self.logger.warning(
                    f"⚠️ MCP: termo {termo!r} falhou ({e}); seguindo com os outros termos."
                )
                falharam += 1
                continue

            if payload.get("message") and not payload.get("data"):
                self.logger.info(
                    f"MCP: termo {termo!r} sem resultado: {payload['message']}"
                )
                continue

            meta = payload.get("meta") or {}
            if meta.get("total", 0) >= LIMITE_TRUNCAMENTO:
                self.logger.warning(
                    f"⚠️ MCP: termo {termo!r} devolveu {meta['total']} itens e o servidor "
                    f"corta em {LIMITE_TRUNCAMENTO}: a lista veio truncada."
                )

            for bruto in payload.get("data") or []:
                item = self._mapear(bruto, termo)
                existente = por_id.get(item["pci_id"])
                if existente:
                    for cargo in item["cargos"]:
                        if cargo not in existente["cargos"]:
                            existente["cargos"].append(cargo)
                    if termo not in existente["termos_origem"]:
                        existente["termos_origem"].append(termo)
                else:
                    por_id[item["pci_id"]] = item

        if self.termos and falharam == len(self.termos):
            raise RuntimeError(
                f"MCP: todos os {len(self.termos)} termo(s) falharam; a fonte pode estar parada."
            )

        self.logger.info(
            f"MCP: {len(por_id)} concurso(s) distinto(s) em {len(self.termos)} termo(s)."
        )
        return list(por_id.values())

    def _chamar(self, termo: str) -> dict:
        """Um POST `buscar_por_cargo` por termo, com tentativa e backoff.

        O laco mora aqui, e nao na BaseScraper, porque o `get_html` e GET de
        HTML: aqui o transporte e POST JSON-RPC 2.0 cuja resposta vem em JSON
        direto ou em SSE, e nenhum dos dois passa pelo `get_html` sem perder
        o cabecalho `Accept` e o corpo do POST.
        """
        corpo = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "buscar_por_cargo", "arguments": {"cargo": termo}},
        }

        for tentativa in range(1, self.tentativas + 1):
            try:
                resposta = requests.post(
                    self.url, json=corpo, headers=self.headers, timeout=TIMEOUT_S
                )
                if resposta.status_code != 200:
                    raise RuntimeError(f"HTTP {resposta.status_code}")
                resposta.encoding = "utf-8"
                return self._extrair_payload(resposta.text)
            except Exception as e:
                if tentativa == self.tentativas:
                    raise
                espera = BACKOFF_BASE_S * (2 ** (tentativa - 1))
                self.logger.warning(
                    f"⚠️ MCP: tentativa {tentativa}/{self.tentativas} falhou para "
                    f"{termo!r}: {e}. Nova tentativa em {espera:.0f}s."
                )
                time.sleep(espera)

    def _extrair_payload(self, corpo: str) -> dict:
        """Payload util da resposta: result.content[0] de tipo text, com JSON dentro."""
        envelope = self._ler_envelope(corpo)
        for parte in (envelope.get("result") or {}).get("content") or []:
            if parte.get("type") == "text":
                return json.loads(parte["text"])
        raise ValueError("resposta sem content de texto")

    @staticmethod
    def _ler_envelope(corpo: str) -> dict:
        """Le o envelope nas duas formas: JSON direto ou SSE (linha `data: `)."""
        try:
            return json.loads(corpo)
        except json.JSONDecodeError:
            pass
        for linha in corpo.splitlines():
            if linha.startswith("data: "):
                return json.loads(linha[len("data: "):])
        raise ValueError("corpo nao e JSON nem SSE")

    @staticmethod
    def _mapear(bruto: dict, termo: str) -> dict:
        """Item bruto do servidor no formato da SPEC-001, secao 3.1."""
        uf = bruto.get("uf")
        titulo = bruto.get("titulo") or ""
        noticia = bruto.get("noticia") or {}
        datas = bruto.get("datas") or {}

        return {
            "ignorar": False,
            "nome": f"{titulo} - {uf}" if uf else titulo,
            "status": noticia.get("titulo") or titulo,
            "link": noticia.get("link"),
            "fase": PciMcpScraper._fase(datas, noticia.get("titulo")),
            "data_fim_inscricao": datas.get("fim") or None,
            "data_referencia": None,
            "pci_id": str(bruto.get("id")),
            "uf": uf,
            "cargos": list(bruto.get("cargos") or []),
            "fonte": "pci_mcp",
            "regiao": bruto.get("regiao"),
            "cargos_total": bruto.get("cargos_total"),
            "vagas_salario": bruto.get("vagas_salario"),
            "termos_origem": [termo],
        }

    @staticmethod
    def _fase(datas: dict, titulo: str | None) -> str | None:
        """Fase vem das datas calculadas pelo servidor; o titulo e o fallback."""
        if datas.get("aberto"):
            return "inscricoes_abertas"
        if datas.get("em_breve"):
            return "edital_publicado"
        return inferir_fase(titulo)
