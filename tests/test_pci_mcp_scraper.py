"""Testes para src/scrapers/pci_mcp_scraper.py.

A costura e `PciMcpScraper.capturar_concursos()`, com o `requests.post` do
modulo dublado devolvendo as fixtures gravadas de tests/fixtures/pci_mcp/
(resposta real do servidor MCP, capturada em 23/11/2026). A suite nao toca a
rede. Os valores esperados foram lidos a mao das fixtures, nenhum e recalculado
pelo proprio mapeador.
"""
import json
import logging
from pathlib import Path

import pytest
import requests

from src.scrapers.pci_mcp_scraper import PciMcpScraper

FIXTURES = Path(__file__).parent / "fixtures" / "pci_mcp"

# Chaves exatas do item, conforme a secao 3.1 da SPEC-001.
CHAVES_DO_ITEM = {
    "ignorar", "nome", "status", "link", "fase", "data_fim_inscricao",
    "data_referencia", "pci_id", "uf", "cargos", "fonte", "regiao",
    "cargos_total", "vagas_salario", "termos_origem",
}


class RespostaFake:
    """O minimo que o scraper le de uma resposta: status e corpo cru."""

    def __init__(self, texto: str, status_code: int = 200):
        self.status_code = status_code
        self.text = texto


def corpo_de(nome: str) -> str:
    """Corpo cru de uma fixture gravada (JSON direto ou SSE)."""
    return (FIXTURES / nome).read_text(encoding="utf-8")


def payload_de(nome: str) -> dict:
    """Payload interno (meta/data) de uma fixture gravada."""
    envelope = json.loads(corpo_de(nome))
    return json.loads(envelope["result"]["content"][0]["text"])


def envelope_de(payload: dict) -> str:
    """Monta o corpo JSON-RPC de uma resposta do servidor com este payload."""
    envelope = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
            "isError": False,
        },
    }
    return json.dumps(envelope, ensure_ascii=False)


def dublar_post(mocker, corpos: list[str]):
    """Dubla o POST do modulo para devolver estes corpos, um por chamada."""
    return mocker.patch(
        "src.scrapers.pci_mcp_scraper.requests.post",
        side_effect=[RespostaFake(c) for c in corpos],
    )


def item_por_id(itens: list[dict], pci_id: str) -> dict:
    return next(i for i in itens if i["pci_id"] == pci_id)


class TestMapeamentoDoItem:
    def test_capturar_mapeia_item_completo(self, mocker):
        """O item 296654 (Prefeitura de Italva) sai campo a campo como na SPEC-001 3.1."""
        dublar_post(mocker, [corpo_de("tools_call_analista_de_sistemas.json")])

        itens = PciMcpScraper(["analista de sistemas"]).capturar_concursos()
        italva = item_por_id(itens, "296654")

        assert set(italva) == CHAVES_DO_ITEM
        assert italva["nome"] == "Prefeitura de Italva - RJ"
        assert italva["status"] == "Prefeitura de Italva - RJ abre concurso público com salários de até R$ 12.132,37"
        assert italva["pci_id"] == "296654"
        assert italva["uf"] == "RJ"
        assert italva["regiao"] == "SUDESTE"
        assert italva["cargos"] == ["ANALISTA DE SISTEMAS"]
        assert italva["cargos_total"] == 53
        assert italva["vagas_salario"] == "137 vagas até R$ 12.132,37"
        assert italva["fonte"] == "pci_mcp"
        assert italva["ignorar"] is False
        assert italva["data_referencia"] is None
        assert italva["termos_origem"] == ["analista de sistemas"]

    def test_capturar_usa_link_da_noticia(self, mocker):
        """`link` e o noticia.link da resposta, nao um link montado."""
        dublar_post(mocker, [corpo_de("tools_call_analista_de_sistemas.json")])

        itens = PciMcpScraper(["analista de sistemas"]).capturar_concursos()

        assert item_por_id(itens, "296654")["link"] == (
            "https://www.pciconcursos.com.br/noticias/"
            "prefeitura-de-italva-rj-abre-concurso-publico-com-salarios-de-ate-12132"
        )

    def test_nome_sem_uf_fica_so_o_titulo(self, mocker):
        """O concurso NACIONAL do TRF3 (uf null) nao ganha sufixo, nem ' - None'."""
        dublar_post(mocker, [corpo_de("tools_call_analista_de_sistemas.json")])

        itens = PciMcpScraper(["analista de sistemas"]).capturar_concursos()

        trf3 = item_por_id(itens, "296157")
        assert trf3["nome"] == "TRF3 - Tribunal Regional Federal da 3ª Região"
        assert trf3["uf"] is None
        assert trf3["regiao"] == "NACIONAL"

    def test_fase_vem_de_aberto(self, mocker):
        """Item com datas.aberto verdadeiro sai em inscricoes_abertas."""
        dublar_post(mocker, [corpo_de("tools_call_analista_de_sistemas.json")])

        itens = PciMcpScraper(["analista de sistemas"]).capturar_concursos()

        assert item_por_id(itens, "296654")["fase"] == "inscricoes_abertas"

    def test_fase_vem_de_em_breve(self, mocker):
        """Item com datas.em_breve verdadeiro sai em edital_publicado."""
        dublar_post(mocker, [corpo_de("tools_call_analista_de_sistemas.json")])

        itens = PciMcpScraper(["analista de sistemas"]).capturar_concursos()

        assert item_por_id(itens, "295546")["fase"] == "edital_publicado"

    def test_fase_cai_no_titulo_sem_as_duas_datas(self, mocker):
        """Sem aberto e sem em_breve, a fase vem do titulo pela funcao de pci_comum."""
        payload = payload_de("tools_call_analista_de_sistemas.json")
        italva = next(i for i in payload["data"] if i["id"] == 296654)
        italva["datas"]["aberto"] = False
        italva["datas"]["em_breve"] = False
        dublar_post(mocker, [envelope_de(payload)])

        itens = PciMcpScraper(["analista de sistemas"]).capturar_concursos()

        # "Prefeitura de Italva - RJ abre concurso publico ..." -> edital_publicado
        assert item_por_id(itens, "296654")["fase"] == "edital_publicado"

    def test_titulo_que_nao_infere_edital_publicado_usa_em_breve(self, mocker):
        """datas.em_breve decide sozinha quando o titulo nao infere fase nenhuma."""
        # Titulo real do item 296235 da fixture tecnico ("suspende concurso"):
        # nenhuma pista de fase casa nele. Montado sobre o item 295546, cujas
        # datas reais carregam em_breve sem aberto, a fase so sai do sub-ramo
        # datas.em_breve; sem ele, o fallback do titulo devolveria None.
        payload = payload_de("tools_call_analista_de_sistemas.json")
        santa_luzia = next(i for i in payload["data"] if i["id"] == 295546)
        santa_luzia["noticia"]["titulo"] = (
            "Prefeitura de São Julião - PI suspende concurso público"
        )
        dublar_post(mocker, [envelope_de(payload)])

        itens = PciMcpScraper(["analista de sistemas"]).capturar_concursos()

        assert item_por_id(itens, "295546")["fase"] == "edital_publicado"

    def test_data_fim_vem_de_datas_fim(self, mocker):
        """data_fim_inscricao e datas.fim, ja ISO, sem reparse."""
        dublar_post(mocker, [corpo_de("tools_call_analista_de_sistemas.json")])

        itens = PciMcpScraper(["analista de sistemas"]).capturar_concursos()

        assert item_por_id(itens, "296654")["data_fim_inscricao"] == "2026-12-16"

    @pytest.mark.parametrize(
        "trato",
        [
            pytest.param("vazia", id="fim-vazia"),
            pytest.param("ausente", id="fim-ausente"),
        ],
    )
    def test_data_fim_vazia_e_ausente_viram_none(self, mocker, trato):
        """datas.fim que chega vazia ou nem chega sai como None, nao como string."""
        payload = payload_de("tools_call_analista_de_sistemas.json")
        italva = next(i for i in payload["data"] if i["id"] == 296654)
        if trato == "vazia":
            italva["datas"]["fim"] = ""
        else:
            del italva["datas"]["fim"]
        dublar_post(mocker, [envelope_de(payload)])

        itens = PciMcpScraper(["analista de sistemas"]).capturar_concursos()

        assert item_por_id(itens, "296654")["data_fim_inscricao"] is None


class TestUniaoEntreTermos:
    def test_uniao_por_id_nao_repete_concurso(self, mocker):
        """Santa Luzia (295546) vem dos dois termos e sai uma vez, acumulando cargos."""
        dublar_post(mocker, [
            corpo_de("tools_call_analista_de_sistemas.json"),
            corpo_de("tools_call_tecnico_em_informatica.json"),
        ])

        itens = PciMcpScraper(["analista de sistemas", "tecnico em informatica"]).capturar_concursos()

        # 9 itens do primeiro termo + 30 do segundo - 1 concurso repetido.
        assert len(itens) == 38
        santa_luzia = item_por_id(itens, "295546")
        assert santa_luzia["cargos"] == ["ANALISTA DE SISTEMAS", "TÉCNICO EM INFORMÁTICA"]
        assert santa_luzia["termos_origem"] == ["analista de sistemas", "tecnico em informatica"]

    def test_le_resposta_em_sse(self, mocker):
        """A mesma carga em SSE devolve o mesmo resultado que em JSON direto."""
        dublar_post(mocker, [corpo_de("tools_call_analista_de_sistemas.sse.txt")])
        via_sse = PciMcpScraper(["analista de sistemas"]).capturar_concursos()

        dublar_post(mocker, [corpo_de("tools_call_analista_de_sistemas.json")])
        via_json = PciMcpScraper(["analista de sistemas"]).capturar_concursos()

        assert len(via_sse) == 9
        assert sorted(via_sse, key=lambda i: i["pci_id"]) == sorted(via_json, key=lambda i: i["pci_id"])

    def test_termo_sem_resultado_nao_quebra(self, mocker, caplog):
        """Resposta com message e data vazia nao contribui item e nao levanta."""
        dublar_post(mocker, [corpo_de("tools_call_sem_resultado.json")])

        with caplog.at_level(logging.INFO):
            itens = PciMcpScraper(["engenheiro de software"], tentativas=1).capturar_concursos()

        assert itens == []
        assert any("engenheiro de software" in r.message for r in caplog.records)


class TestTermoQueFalha:
    def test_um_termo_que_falha_nao_derruba_os_outros(self, mocker, caplog):
        """Erro de rede num termo vira warning; os outros termos entregam."""
        post = mocker.patch(
            "src.scrapers.pci_mcp_scraper.requests.post",
            side_effect=[
                requests.exceptions.ConnectionError("sem rede"),
                RespostaFake(corpo_de("tools_call_analista_de_sistemas.json")),
            ],
        )

        with caplog.at_level(logging.WARNING):
            itens = PciMcpScraper(["quebrado", "analista de sistemas"], tentativas=1).capturar_concursos()

        assert len(itens) == 9
        assert post.call_count == 2
        assert any("quebrado" in r.message for r in caplog.records if r.levelno == logging.WARNING)

    def test_todos_os_termos_falhando_levanta(self, mocker):
        """Todos os termos falhando e falha da fonte: levanta, nao devolve vazio."""
        mocker.patch(
            "src.scrapers.pci_mcp_scraper.requests.post",
            side_effect=requests.exceptions.ConnectionError("sem rede"),
        )

        with pytest.raises(RuntimeError, match="todos"):
            PciMcpScraper(["quebrado", "tambem quebrado"], tentativas=1).capturar_concursos()

    def test_json_invalido_conta_como_falha_do_termo(self, mocker):
        """Corpo que nao e JSON (nem SSE) e falha do termo, nao da rodada."""
        dublar_post(mocker, [
            "<html>gateway timeout</html>",
            corpo_de("tools_call_analista_de_sistemas.json"),
        ])

        itens = PciMcpScraper(["quebrado", "analista de sistemas"], tentativas=1).capturar_concursos()

        assert len(itens) == 9

    def test_resposta_sem_content_de_texto_conta_como_falha(self, mocker):
        """Envelope sem content de texto e falha do termo, nao da rodada."""
        envelope_vazio = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"content": []}})
        dublar_post(mocker, [
            envelope_vazio,
            corpo_de("tools_call_analista_de_sistemas.json"),
        ])

        itens = PciMcpScraper(["quebrado", "analista de sistemas"], tentativas=1).capturar_concursos()

        assert len(itens) == 9

    def test_resposta_fora_do_200(self, mocker, caplog):
        """HTTP 500 com corpo valido e falha do termo: nao entra item nenhum dele."""
        # O corpo da resposta de erro carrega o payload real da fixture
        # tecnico de proposito: sem a checagem do status, os 30 itens dela
        # seriam lidos como se a chamada tivesse dado certo e a uniao cresce
        # para 38; com ela, o termo falha em warning e a varredura segue.
        mocker.patch(
            "src.scrapers.pci_mcp_scraper.requests.post",
            side_effect=[
                RespostaFake(
                    corpo_de("tools_call_tecnico_em_informatica.json"),
                    status_code=500,
                ),
                RespostaFake(corpo_de("tools_call_analista_de_sistemas.json")),
            ],
        )

        with caplog.at_level(logging.WARNING):
            itens = PciMcpScraper(["quebrado", "analista de sistemas"], tentativas=1).capturar_concursos()

        assert len(itens) == 9
        assert any(
            "HTTP 500" in r.message
            for r in caplog.records
            if r.levelno == logging.WARNING
        )

    def test_avisa_truncamento_em_200(self, mocker, caplog):
        """meta.total no limite do servidor gera warning de truncamento."""
        payload = payload_de("tools_call_analista_de_sistemas.json")
        payload["meta"]["total"] = 200
        dublar_post(mocker, [envelope_de(payload)])

        with caplog.at_level(logging.WARNING):
            PciMcpScraper(["professor"], tentativas=1).capturar_concursos()

        assert any(
            "truncad" in r.message
            for r in caplog.records
            if r.levelno == logging.WARNING
        )


class TestConstrucaoEDoPedido:
    def test_termo_vazio_e_descartado(self, mocker):
        """Termo vazio ou so espaco nao gera chamada: um POST pelos tres termos."""
        post = dublar_post(mocker, [corpo_de("tools_call_analista_de_sistemas.json")])

        itens = PciMcpScraper(["", "  ", "informatica"]).capturar_concursos()

        assert post.call_count == 1
        assert len(itens) == 9

    def test_posta_para_o_endpoint_do_servidor(self, mocker):
        """O POST vai para o endpoint do servidor MCP, que e o `self.url` da porta."""
        post = dublar_post(mocker, [corpo_de("tools_call_analista_de_sistemas.json")])

        scraper = PciMcpScraper(["informatica"])
        assert scraper.url == "https://mcp.pciconcursos.com.br/mcp"
        scraper.capturar_concursos()

        assert post.call_args.args[0] == "https://mcp.pciconcursos.com.br/mcp"

    def test_nao_envia_parametro_uf(self, mocker):
        """O pedido e tools/call de buscar_por_cargo com so `cargo`, sem `uf`."""
        post = dublar_post(mocker, [corpo_de("tools_call_analista_de_sistemas.json")])

        PciMcpScraper(["informatica"]).capturar_concursos()

        corpo = post.call_args.kwargs["json"]
        assert corpo["jsonrpc"] == "2.0"
        assert corpo["method"] == "tools/call"
        assert corpo["params"]["name"] == "buscar_por_cargo"
        assert corpo["params"]["arguments"] == {"cargo": "informatica"}
        assert "uf" not in corpo["params"]["arguments"]
        headers = post.call_args.kwargs["headers"]
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json, text/event-stream"
        assert headers["MCP-Protocol-Version"] == "2025-06-18"
