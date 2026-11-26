"""Testes de integracao para src/core/bot.py.

Foco no orquestrador — todos os subsistemas (scraper, IA, DB, notifier,
callback processor) sao substituidos por mocks para verificar o fluxo
de decisao por bloco.
"""
from datetime import date, datetime, timedelta, timezone

import pytest

from src.core.bot import ConcursoBot
from src.intelligence.langchain_unit import IntelligenceUnit
from src.scrapers.pci_mcp_scraper import URL_SERVIDOR
from src.utils import saude_fontes


@pytest.fixture
def mock_deps(mocker, tmp_path):
    """Substitui as dependencias do ConcursoBot antes da instanciacao."""
    # Marcadores de "alerta ja enviado hoje" vao pra um tmp por teste; no LOG_DIR
    # real eles persistiriam e o segundo teste do dia nao veria alerta nenhum.
    mocker.patch("src.core.bot.LOG_DIR", str(tmp_path))
    scraper_cls = mocker.patch("src.core.bot.GranScraper")
    db_cls = mocker.patch("src.core.bot.DatabaseManager")
    ai_cls = mocker.patch("src.core.bot.IntelligenceUnit")
    notifier_cls = mocker.patch("src.core.bot.TelegramNotifier")
    cb_proc_cls = mocker.patch("src.core.bot.TelegramCallbackProcessor")

    scraper = scraper_cls.return_value
    db = db_cls.return_value
    ai = ai_cls.return_value
    notifier = notifier_cls.return_value
    cb_proc = cb_proc_cls.return_value

    scraper.url = "https://example.com"
    # Default: LLM autenticada. Num MagicMock o atributo seria truthy.
    ai.falha_autenticacao = None
    ai.cota_volta_em = None
    ai.instrucao_login = "no notebook, <code>claude setup-token</code>"
    # Default: concurso nao existe no DB.
    db.buscar_registro.return_value = None
    # Default: upsert retorna id=42.
    db.atualizar_concurso.return_value = 42

    return {
        "scraper": scraper, "db": db, "ai": ai, "notifier": notifier,
        "cb_proc": cb_proc,
    }


@pytest.fixture
def base_config():
    return {
        "url_alvo": "https://example.com",
        "ollama_model": "llama3.1",
        "token": "TOKEN",
        "chat_id": "111",
        "chat_ids": ["111"],
        "area": "TI",
        "display_name": "Tecnologia",
        "keywords_include": [],
        "keywords_exclude": [],
    }


def _amanha() -> str:
    return (date.today() + timedelta(days=1)).isoformat()


def _ontem() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


class TestKeywordPreFilter:
    def test_include_filter_accepts_matching_block(self, base_config):
        base_config["keywords_include"] = ["concurso"]
        bot = ConcursoBot(base_config)
        assert bot._passa_filtro_palavras("<p>edital de concurso</p>") is True

    def test_include_filter_rejects_non_matching(self, base_config):
        base_config["keywords_include"] = ["mega-sena"]
        bot = ConcursoBot(base_config)
        assert bot._passa_filtro_palavras("<p>edital de concurso</p>") is False

    def test_exclude_filter_rejects_matching(self, base_config):
        base_config["keywords_exclude"] = ["artes"]
        bot = ConcursoBot(base_config)
        assert bot._passa_filtro_palavras("<p>concurso de artes</p>") is False

    def test_empty_filters_accept_everything(self, base_config):
        bot = ConcursoBot(base_config)
        assert bot._passa_filtro_palavras("<p>qualquer coisa</p>") is True


class TestFiltroSobreTextoVisivel:
    """O filtro le o texto que o humano ve, nao o HTML cru.

    Casar substring no HTML tinha dois defeitos que este bloco trava.
    """

    BLOCO_TI_COM_SIDEBAR = """
        <h3>Concurso do TRE-PR: vagas para Analista de Sistemas</h3>
        <p>Edital publicado com vagas de tecnologia da informacao.</p>
        <aside class="relacionados">
          <a href="/concursos-artes/">Concursos de artes e sociologia</a>
        </aside>
    """

    def test_exclude_nao_derruba_edital_por_palavra_na_sidebar(self, base_config):
        """Regressao: edital de TI sumia porque a barra lateral citava artes."""
        base_config["keywords_exclude"] = ["artes", "sociologia"]
        bot = ConcursoBot(base_config)

        assert bot._passa_filtro_palavras(self.BLOCO_TI_COM_SIDEBAR) is True

    def test_exclude_ainda_derruba_quando_a_palavra_esta_no_corpo(self, base_config):
        base_config["keywords_exclude"] = ["artes"]
        bot = ConcursoBot(base_config)

        bloco = "<h3>Concurso para professor de artes</h3><p>Edital publicado.</p>"
        assert bot._passa_filtro_palavras(bloco) is False

    def test_include_nao_casa_dentro_de_atributo_html(self, base_config):
        """`ti` casava em class/href/alt e tornava o include inocuo."""
        base_config["keywords_include"] = ["ti"]
        bot = ConcursoBot(base_config)

        bloco = '<div class="noticia"><a href="/gestao/">Concurso para pedagogo</a></div>'
        assert bot._passa_filtro_palavras(bloco) is False

    def test_html_malformado_nao_explode(self, base_config):
        bot = ConcursoBot(base_config)
        assert bot._passa_filtro_palavras("<h3>sem fechar") is True


class TestPrazoEncerrado:
    def test_none_nao_encerrado(self):
        assert ConcursoBot._prazo_encerrado(None) is False

    def test_string_invalida_nao_encerrado(self):
        assert ConcursoBot._prazo_encerrado("invalido") is False

    def test_ontem_encerrado(self):
        assert ConcursoBot._prazo_encerrado(_ontem()) is True

    def test_hoje_ainda_aberto(self):
        assert ConcursoBot._prazo_encerrado(date.today().isoformat()) is False

    def test_amanha_aberto(self):
        assert ConcursoBot._prazo_encerrado(_amanha()) is False


class TestExecutarFlow:
    def test_new_concurso_triggers_notification_with_buttons(
        self, mock_deps, base_config
    ):
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "TRF1",
            "status": "edital publicado",
            "link": "https://example.com/trf1",
            "data_fim_inscricao": _amanha(),
        }
        mock_deps["db"].buscar_registro.return_value = None
        mock_deps["db"].atualizar_concurso.return_value = 99

        bot = ConcursoBot(base_config)
        bot.executar()

        # notificar_concurso foi chamado (com id interno para botoes).
        mock_deps["notifier"].notificar_concurso.assert_called_once()
        call = mock_deps["notifier"].notificar_concurso.call_args
        assert call.args[0] == 99
        assert "NOVO CONCURSO" in call.args[1]
        assert "TRF1" in call.args[1]
        mock_deps["db"].atualizar_concurso.assert_called_once()
        kwargs = mock_deps["db"].atualizar_concurso.call_args.kwargs
        assert kwargs["status_hash"]
        assert kwargs["data_fim_inscricao"] == _amanha()

    def test_new_concurso_com_prazo_encerrado_nao_notifica(
        self, mock_deps, base_config
    ):
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "TRF1",
            "status": "aberto",
            "link": "https://example.com/trf1",
            "data_fim_inscricao": _ontem(),
        }
        mock_deps["db"].buscar_registro.return_value = None

        bot = ConcursoBot(base_config)
        bot.executar()

        # NAO notifica o novo concurso (prazo encerrou).
        mock_deps["notifier"].notificar_concurso.assert_not_called()
        # Mas salva silenciosamente no DB.
        mock_deps["db"].atualizar_concurso.assert_called_once()
        # So envia o "Varredura Concluida".
        assert mock_deps["notifier"].notificar.call_count == 1
        assert "Varredura Conclu" in mock_deps["notifier"].notificar.call_args.args[0]

    def test_new_listagem_morta_nao_notifica(self, mock_deps, base_config):
        """Sem inscricao ativa e com evento ja passado (ex: 'provas previstas maio/2025')
        = listagem morta: salva silencioso, nunca notifica como NOVO."""
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "FUB",
            "status": "banca definida, provas previstas para maio de 2025",
            "link": "https://example.com/fub",
            "data_fim_inscricao": None,
            "data_referencia": _ontem(),
        }
        mock_deps["db"].buscar_registro.return_value = None

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["notifier"].notificar_concurso.assert_not_called()
        mock_deps["db"].atualizar_concurso.assert_called_once()

    def test_new_previsto_sem_data_notifica(self, mock_deps, base_config):
        """Concurso so 'previsto', sem data alguma, e oportunidade futura valida: notifica."""
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "PRODEPA",
            "status": "comissao formada, edital previsto em breve",
            "link": "https://example.com/prodepa",
            "data_fim_inscricao": None,
            "data_referencia": None,
        }
        mock_deps["db"].buscar_registro.return_value = None
        mock_deps["db"].atualizar_concurso.return_value = 7

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["notifier"].notificar_concurso.assert_called_once()
        assert "NOVO CONCURSO" in mock_deps["notifier"].notificar_concurso.call_args.args[1]

    def test_ignorar_block_is_skipped(self, mock_deps, base_config):
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>lixo</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {"ignorar": True}

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["db"].atualizar_concurso.assert_not_called()
        mock_deps["notifier"].notificar_concurso.assert_not_called()
        # Zero concursos validos = varredura cega: alerta, nao heartbeat de sucesso.
        assert mock_deps["notifier"].notificar.call_count == 1
        msg = mock_deps["notifier"].notificar.call_args.args[0]
        assert "Atenção" in msg
        assert "Varredura Conclu" not in msg

    def test_scrape_vazio_envia_alerta_de_cegueira(self, mock_deps, base_config):
        """Scraper sem blocos (site fora do ar / layout mudou) -> alerta, nunca heartbeat verde."""
        mock_deps["scraper"].capturar_concursos.return_value = []

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["ai"].extrair_dados.assert_not_called()
        mock_deps["notifier"].notificar_concurso.assert_not_called()
        assert mock_deps["notifier"].notificar.call_count == 1
        msg = mock_deps["notifier"].notificar.call_args.args[0]
        assert "Atenção" in msg
        assert "Varredura Conclu" not in msg

    def test_alvo_filtrado_tudo_descartado_envia_heartbeat(self, mock_deps, base_config):
        """Alvo COM keywords_include em pagina generica: filtro descartar tudo e dia
        quieto normal -> heartbeat, nunca alerta de cegueira."""
        base_config["keywords_include"] = ["sociologia"]
        mock_deps["scraper"].capturar_concursos.return_value = [
            "<h3>Concurso PM SP</h3>", "<h3>Concurso Bombeiros MG</h3>",
        ]

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["ai"].extrair_dados.assert_not_called()
        assert mock_deps["notifier"].notificar.call_count == 1
        msg = mock_deps["notifier"].notificar.call_args.args[0]
        assert "Varredura Concluída" in msg
        assert "Atenção" not in msg

    def test_alvo_filtrado_ia_ignora_envia_heartbeat(self, mock_deps, base_config):
        """Alvo COM keywords_include: bloco passa no filtro mas a IA ignora
        (ex: 'artes marciais') -> ainda e dia quieto, heartbeat."""
        base_config["keywords_include"] = ["artes"]
        mock_deps["scraper"].capturar_concursos.return_value = [
            "<h3>Curso de artes marciais</h3>",
        ]
        mock_deps["ai"].extrair_dados.return_value = {"ignorar": True}

        bot = ConcursoBot(base_config)
        bot.executar()

        assert mock_deps["notifier"].notificar.call_count == 1
        msg = mock_deps["notifier"].notificar.call_args.args[0]
        assert "Varredura Concluída" in msg
        assert "Atenção" not in msg

    def test_heartbeat_sai_uma_vez_por_dia(self, mock_deps, base_config):
        """Uma area falhando (ex.: LLM sem login) faz o cron repetir de hora em
        hora, e cada rodada reenviava o 'Varredura Concluída' das areas que
        terminam bem: 45-48 por dia no chat de Educacao/Soc-Artes de 15 a
        22/10/2026. Agora o heartbeat sai 1 vez por dia, por area."""
        base_config["keywords_include"] = ["sociologia"]
        mock_deps["scraper"].capturar_concursos.return_value = [
            "<h3>Concurso PM SP</h3>",
        ]
        mock_deps["notifier"].notificar.return_value = True

        ConcursoBot(base_config).executar()
        segunda = ConcursoBot(base_config)
        segunda.executar()

        mensagens = [c.args[0] for c in mock_deps["notifier"].notificar.call_args_list]
        assert sum(1 for m in mensagens if "Varredura Concluída" in m) == 1
        # Suprimir o heartbeat nao pode virar falha: dia quieto segue sendo dia
        # quieto, senao o catch-up horario voltaria a rodar sem parar.
        assert segunda.falhou is False

    def test_alvo_filtrado_scrape_vazio_ainda_alerta(self, mock_deps, base_config):
        """Mesmo com keywords_include, zero blocos brutos = pagina quebrada -> alerta."""
        base_config["keywords_include"] = ["sociologia"]
        mock_deps["scraper"].capturar_concursos.return_value = []

        bot = ConcursoBot(base_config)
        bot.executar()

        assert mock_deps["notifier"].notificar.call_count == 1
        msg = mock_deps["notifier"].notificar.call_args.args[0]
        assert "Atenção" in msg
        assert "Varredura Conclu" not in msg

    def test_estado_ignorado_pula_completamente(self, mock_deps, base_config):
        """Concurso marcado ❌ pelo usuario nao e notificado nem atualizado."""
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "TRF1",
            "status": "novissimo status",
            "link": "https://example.com/trf1",
            "data_fim_inscricao": _amanha(),
        }
        mock_deps["db"].buscar_registro.return_value = {
            "id": 5, "area": "TI", "nome": "TRF1", "status": "antigo",
            "status_hash": "aaaa", "estado_usuario": "ignorado",
            "data_fim_inscricao": None, "link": "https://example.com/trf1",
        }

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["notifier"].notificar_concurso.assert_not_called()
        mock_deps["db"].atualizar_concurso.assert_not_called()

    def test_legacy_row_sem_fase_backfill_silencioso(self, mock_deps, base_config):
        """Linhas legadas (fase=NULL) sao backfilled sem notificar na 1a varredura."""
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "TRF1",
            # Texto completamente DIFERENTE do armazenado — mesmo assim nao notifica.
            "status": "reformulacao totalmente nova",
            "link": "https://example.com/trf1",
            "data_fim_inscricao": None,
            "fase": "edital_publicado",
        }
        mock_deps["db"].buscar_registro.return_value = {
            "id": 5, "area": "TI", "nome": "TRF1",
            "status": "texto armazenado ha 24h",
            "status_hash": "qualquer", "fase": None,  # legado: sem fase
            "estado_usuario": "ativo", "data_fim_inscricao": None,
            "link": "https://example.com/trf1",
        }

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["notifier"].notificar_concurso.assert_not_called()
        # Backfill: faz update (preenche a fase).
        mock_deps["db"].atualizar_concurso.assert_called_once()

    def test_reescrita_mesma_fase_nao_notifica(self, mock_deps, base_config):
        """O bug central: a IA reformula o status (e ate adiciona detalhe), mas a
        FASE e a mesma -> nada de notificacao. Mata o falso positivo ATI PE/BNDES."""
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "ATI PE",
            "status": "Concurso da ATI-PE com 82 vagas. Banca ainda em definicao.",
            "link": "https://example.com/atipe",
            "data_fim_inscricao": None,
            "fase": "previsto",
        }
        mock_deps["db"].buscar_registro.return_value = {
            "id": 5, "area": "TI", "nome": "ATI PE",
            "status": "Concurso para Analista em Gestao de TI. Banca em definicao.",
            "status_hash": "old", "fase": "previsto",
            "estado_usuario": "ativo", "data_fim_inscricao": None,
            "link": "https://example.com/atipe",
        }

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["notifier"].notificar_concurso.assert_not_called()

    def test_fase_regressao_nao_notifica(self, mock_deps, base_config):
        """Flapping da LLM: fase classificada como menos avancada que a salva
        nao notifica (e a fase avancada e preservada)."""
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "TRF1",
            "status": "texto",
            "link": "https://example.com/trf1",
            "data_fim_inscricao": _amanha(),
            "fase": "banca_definida",  # regressao vs inscricoes_abertas
        }
        mock_deps["db"].buscar_registro.return_value = {
            "id": 5, "area": "TI", "nome": "TRF1", "status": "antigo",
            "status_hash": "old", "fase": "inscricoes_abertas",
            "estado_usuario": "ativo", "data_fim_inscricao": _amanha(),
            "link": "https://example.com/trf1",
        }

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["notifier"].notificar_concurso.assert_not_called()
        # Preserva a fase mais avancada ja vista.
        assert mock_deps["db"].atualizar_concurso.call_args.kwargs["fase"] == "inscricoes_abertas"

    def test_fase_avancou_prazo_aberto_notifica(self, mock_deps, base_config):
        """Avanco real de fase com inscricao aberta -> notifica com a transicao."""
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "TRF1",
            "status": "edital publicado",
            "link": "https://example.com/trf1",
            "data_fim_inscricao": _amanha(),
            "fase": "edital_publicado",
        }
        mock_deps["db"].buscar_registro.return_value = {
            "id": 5, "area": "TI", "nome": "TRF1", "status": "banca definida",
            "status_hash": "old", "fase": "banca_definida",
            "estado_usuario": "ativo", "data_fim_inscricao": _amanha(),
            "link": "https://example.com/trf1",
        }
        mock_deps["db"].atualizar_concurso.return_value = 5

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["notifier"].notificar_concurso.assert_called_once()
        call = mock_deps["notifier"].notificar_concurso.call_args
        assert "ATUALIZA" in call.args[1]
        assert "Banca definida" in call.args[1] and "Edital publicado" in call.args[1]

    def test_data_fim_muda_mesma_fase_notifica(self, mock_deps, base_config):
        """Mudanca de data de fim de inscricao (mesma fase) e relevante -> notifica."""
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "TRF1",
            "status": "inscricoes prorrogadas",
            "link": "https://example.com/trf1",
            "data_fim_inscricao": _amanha(),
            "fase": "inscricoes_abertas",
        }
        mock_deps["db"].buscar_registro.return_value = {
            "id": 5, "area": "TI", "nome": "TRF1", "status": "inscricoes abertas",
            "status_hash": "old", "fase": "inscricoes_abertas",
            "estado_usuario": "ativo", "data_fim_inscricao": _ontem(),
            "link": "https://example.com/trf1",
        }
        mock_deps["db"].atualizar_concurso.return_value = 5

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["notifier"].notificar_concurso.assert_called_once()
        assert "Inscrições até" in mock_deps["notifier"].notificar_concurso.call_args.args[1]

    def test_fase_avancou_pos_prazo_ativo_atualiza_silencioso(
        self, mock_deps, base_config
    ):
        """estado 'ativo' + avanco de fase mas concurso inativo = atualiza DB sem notificar."""
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "TRF1",
            "status": "resultado publicado",
            "link": "https://example.com/trf1",
            "data_fim_inscricao": _ontem(),
            "fase": "concluido",
        }
        mock_deps["db"].buscar_registro.return_value = {
            "id": 5, "area": "TI", "nome": "TRF1", "status": "antigo",
            "status_hash": "old", "fase": "inscricoes_encerradas",
            "estado_usuario": "ativo", "data_fim_inscricao": _ontem(),
            "link": "https://example.com/trf1",
        }

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["db"].atualizar_concurso.assert_called_once()
        mock_deps["notifier"].notificar_concurso.assert_not_called()

    def test_fase_avancou_pos_prazo_seguindo_notifica(
        self, mock_deps, base_config
    ):
        """estado 'seguindo' ignora o prazo — usuario quer updates sempre."""
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "TRF1",
            "status": "resultado publicado",
            "link": "https://example.com/trf1",
            "data_fim_inscricao": _ontem(),
            "fase": "concluido",
        }
        mock_deps["db"].buscar_registro.return_value = {
            "id": 5, "area": "TI", "nome": "TRF1", "status": "antigo",
            "status_hash": "old", "fase": "inscricoes_encerradas",
            "estado_usuario": "seguindo", "data_fim_inscricao": _ontem(),
            "link": "https://example.com/trf1",
        }
        mock_deps["db"].atualizar_concurso.return_value = 5

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["notifier"].notificar_concurso.assert_called_once()

    def test_keyword_prefilter_blocks_llm_call(self, mock_deps, base_config):
        base_config["keywords_include"] = ["concurso"]
        mock_deps["scraper"].capturar_concursos.return_value = [
            "<p>texto sem palavras relevantes</p>"
        ]

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["ai"].extrair_dados.assert_not_called()

    def test_scraper_exception_is_caught(self, mock_deps, base_config):
        mock_deps["scraper"].capturar_concursos.side_effect = RuntimeError("boom")

        bot = ConcursoBot(base_config)
        bot.executar()  # nao deve levantar

    def test_callback_processor_e_invocado_no_inicio(self, mock_deps, base_config):
        mock_deps["scraper"].capturar_concursos.return_value = []

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["cb_proc"].processar_pendentes.assert_called_once()

    def test_falha_no_callback_processor_nao_trava_varredura(
        self, mock_deps, base_config
    ):
        mock_deps["cb_proc"].processar_pendentes.side_effect = RuntimeError("telegram down")
        mock_deps["scraper"].capturar_concursos.return_value = []

        bot = ConcursoBot(base_config)
        bot.executar()  # nao deve levantar

        # Varredura ainda enviou a mensagem de conclusao.
        assert mock_deps["notifier"].notificar.call_count == 1


class TestFalhaPropaga:
    """Uma varredura quebrada nao pode se passar por varredura limpa.

    Ate 08/2026 o `except` do loop logava e seguia, o main.py devolvia 0, o
    run_daily.sh gravava o marker de sucesso e o dia seguinte parecia saudavel.
    O bot ficou morto 23 dias assim.
    """

    def test_excecao_no_scraper_marca_falha(self, mock_deps, base_config):
        mock_deps["scraper"].capturar_concursos.side_effect = RuntimeError("site fora")

        bot = ConcursoBot(base_config)
        bot.executar()

        assert bot.falhou is True

    def test_alerta_de_excecao_sai_uma_vez_por_dia(self, mock_deps, base_config):
        mock_deps["scraper"].capturar_concursos.side_effect = RuntimeError("site fora")
        mock_deps["notifier"].notificar.return_value = True

        ConcursoBot(base_config).executar()
        ConcursoBot(base_config).executar()

        mensagens = [c.args[0] for c in mock_deps["notifier"].notificar.call_args_list]
        assert sum(1 for m in mensagens if "Falha na varredura" in m) == 1

    def test_varredura_limpa_nao_marca_falha(self, mock_deps, base_config):
        """Concurso extraido e sem novidade: dia quieto de verdade, nao falha."""
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False, "nome": "TRF1", "status": "edital publicado",
            "link": "https://example.com/trf1", "data_fim_inscricao": _amanha(),
            "data_referencia": None, "fase": "edital_publicado",
        }
        mock_deps["db"].buscar_registro.return_value = {
            "id": 1, "fase": "edital_publicado", "estado_usuario": "ativo",
            "data_fim_inscricao": _amanha(), "nome": "TRF1",
        }
        mock_deps["notifier"].notificar.return_value = True

        bot = ConcursoBot(base_config)
        bot.executar()

        assert bot.falhou is False

    def test_varredura_cega_marca_falha(self, mock_deps, base_config):
        mock_deps["scraper"].capturar_concursos.return_value = []
        mock_deps["notifier"].notificar.return_value = True

        bot = ConcursoBot(base_config)
        bot.executar()

        assert bot.falhou is True

    def test_telegram_nao_entregue_marca_falha(self, mock_deps, base_config):
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {"ignorar": True}
        mock_deps["notifier"].notificar.return_value = False  # nao entregou

        bot = ConcursoBot(base_config)
        bot.executar()

        assert bot.falhou is True


class TestErroDeExtracao:
    """Bloco perdido pela LLM e contado, nao confundido com bloco irrelevante."""

    def _blocos(self, n):
        return [f"<h3>bloco {i}</h3>" for i in range(n)]

    def test_muitos_erros_alertam_em_vez_de_reportar_sucesso(self, mock_deps, base_config):
        mock_deps["scraper"].capturar_concursos.return_value = self._blocos(10)
        # 5 perdidos, 5 irrelevantes: metade da pagina se perdeu.
        mock_deps["ai"].extrair_dados.side_effect = (
            [{"ignorar": True, "erro": True}] * 5 + [{"ignorar": True}] * 5
        )
        mock_deps["notifier"].notificar.return_value = True

        bot = ConcursoBot(base_config)
        bot.executar()

        assert bot.falhou is True
        texto = mock_deps["notifier"].notificar.call_args.args[0]
        assert "incompleta" in texto.lower()

    def test_poucos_erros_nao_disparam_alerta(self, mock_deps, base_config):
        mock_deps["scraper"].capturar_concursos.return_value = self._blocos(20)
        # 1 perdido em 20 validos = 5%, abaixo do limite de 20%.
        mock_deps["ai"].extrair_dados.side_effect = (
            [{"ignorar": True, "erro": True}]
            + [{"ignorar": False, "nome": f"Orgao {i}", "status": "s",
                "link": "https://example.com/x", "data_fim_inscricao": None,
                "data_referencia": None} for i in range(19)]
        )
        mock_deps["db"].buscar_registro.return_value = {
            "id": 1, "fase": "edital_publicado", "estado_usuario": "ativo",
            "data_fim_inscricao": None, "nome": "Orgao",
        }
        mock_deps["notifier"].notificar.return_value = True

        bot = ConcursoBot(base_config)
        bot.executar()

        assert bot.falhou is False

    def test_alerta_de_degradado_sai_uma_vez_por_dia(self, mock_deps, base_config):
        """Causa persistente + catch-up horario rendiam 24 alertas iguais por dia."""
        mock_deps["scraper"].capturar_concursos.return_value = self._blocos(10)
        mock_deps["ai"].extrair_dados.return_value = {"ignorar": True, "erro": True}
        mock_deps["notifier"].notificar.return_value = True

        primeira = ConcursoBot(base_config)
        primeira.executar()
        segunda = ConcursoBot(base_config)
        segunda.executar()

        mensagens = [c.args[0] for c in mock_deps["notifier"].notificar.call_args_list]
        assert sum(1 for m in mensagens if "incompleta" in m.lower()) == 1
        # Silenciar o aviso nao pode silenciar a falha: o catch-up depende dela.
        assert segunda.falhou is True


class TestLlmSemLogin:
    """OAuth do `claude` expirado: de 14/10 a 22/10/2026 isso chegou como
    "Varredura incompleta" de hora em hora, sem pista nenhuma da causa."""

    def _preparar(self, mock_deps, base_config):
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>a</h3>", "<h3>b</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {"ignorar": True, "erro": True}
        mock_deps["ai"].falha_autenticacao = "claude -p sem autenticacao: OAuth expirado"
        mock_deps["notifier"].notificar.return_value = True

    def test_alerta_diz_que_e_login_e_nao_varredura_incompleta(self, mock_deps, base_config):
        self._preparar(mock_deps, base_config)

        bot = ConcursoBot(base_config)
        bot.executar()

        mensagens = [c.args[0] for c in mock_deps["notifier"].notificar.call_args_list]
        assert len(mensagens) == 1
        assert "sem acesso" in mensagens[0]
        assert "setup-token" in mensagens[0]
        assert not any("incompleta" in m.lower() for m in mensagens)

    def test_continua_marcando_falha_para_o_catch_up(self, mock_deps, base_config):
        self._preparar(mock_deps, base_config)

        bot = ConcursoBot(base_config)
        bot.executar()

        assert bot.falhou is True

    def test_alerta_e_um_so_por_dia_para_todas_as_areas(self, mock_deps, base_config):
        """O login e da maquina: Educacao e Soc/Artes nao repetem o aviso do TI."""
        self._preparar(mock_deps, base_config)

        ConcursoBot(base_config).executar()
        ConcursoBot({**base_config, "area": "EDUCACAO", "display_name": "Educação"}).executar()
        ConcursoBot(base_config).executar()

        mensagens = [c.args[0] for c in mock_deps["notifier"].notificar.call_args_list]
        assert sum(1 for m in mensagens if "sem acesso" in m) == 1


class TestCotaDaLlmEsgotada:
    """25/11/2026: a cota semanal acabou e o aviso foi so "Varredura incompleta".

    A ``IntelligenceUnit`` aqui e a de verdade; so a chamada a LLM e dublada.
    """

    # Mensagem real do provedor, copiada do log de producao de 25/11/2026.
    MENSAGEM = (
        "litellm.RateLimitError: RateLimitError: ZaiException - Weekly/Monthly Limit "
        "Exhausted. Your limit will reset at 2026-11-26 08:11:28"
    )

    def _bot(self, mocker, config, respostas=None):
        """Bot cuja LLM esgota a cota depois de entregar as ``respostas``."""
        mocker.patch.object(IntelligenceUnit, "_create_ollama", return_value=mocker.MagicMock())
        ai = IntelligenceUnit(model_name="llama3.1", retries=2, retry_delay_s=0)
        ai.chain_extracao = mocker.MagicMock()
        ai.chain_extracao.invoke.side_effect = (
            list(respostas or []) + [RuntimeError(self.MENSAGEM)] * 100
        )
        bot = ConcursoBot(config)
        bot.ai = ai
        return bot

    def _preparar(self, mock_deps, blocos=2):
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"] * blocos
        mock_deps["notifier"].notificar.return_value = True

    def _mensagens(self, mock_deps):
        return [c.args[0] for c in mock_deps["notifier"].notificar.call_args_list]

    def test_alerta_de_cota_nomeia_a_causa_e_a_hora_de_volta(
        self, mock_deps, base_config, mocker
    ):
        self._preparar(mock_deps)

        self._bot(mocker, base_config).executar()

        mensagens = self._mensagens(mock_deps)
        assert len(mensagens) == 1
        assert "cota" in mensagens[0].lower()
        assert "26/11/2026" in mensagens[0]
        assert "08:11:28" in mensagens[0]
        assert "sem fuso" in mensagens[0]
        assert "incompleta" not in mensagens[0].lower()
        # Cota nao e credencial: nada de mandar relogar.
        assert "setup-token" not in mensagens[0]
        assert "credencial" not in mensagens[0].lower()

    def test_alerta_de_cota_sai_uma_vez_por_dia(self, mock_deps, base_config, mocker):
        """A cota e uma so para as tres areas e o catch-up repete de hora em hora."""
        self._preparar(mock_deps)
        educacao = {**base_config, "area": "EDUCACAO", "display_name": "Educação"}

        self._bot(mocker, base_config).executar()
        self._bot(mocker, educacao).executar()
        repetida = self._bot(mocker, base_config)
        repetida.executar()

        mensagens = self._mensagens(mock_deps)
        assert sum(1 for m in mensagens if "cota" in m.lower()) == 1
        assert len(mensagens) == 1
        # Silenciar o aviso nao pode silenciar a falha: o catch-up depende dela.
        assert repetida.falhou is True

    def test_alerta_de_cota_nao_e_calado_pelo_alerta_de_login_do_mesmo_dia(
        self, mock_deps, base_config, mocker
    ):
        self._preparar(mock_deps)
        mock_deps["ai"].extrair_dados.return_value = {"ignorar": True, "erro": True}
        mock_deps["ai"].falha_autenticacao = "claude -p sem autenticacao: OAuth expirado"
        ConcursoBot(base_config).executar()

        self._bot(mocker, base_config).executar()

        mensagens = self._mensagens(mock_deps)
        assert sum(1 for m in mensagens if "sem acesso" in m) == 1
        assert sum(1 for m in mensagens if "cota" in m.lower()) == 1

    def test_cota_marca_falha_mesmo_com_perda_abaixo_do_limite(
        self, mock_deps, base_config, mocker
    ):
        """A cota acaba no ultimo bloco: 1 perdido em 20 ficaria abaixo dos 20%."""
        self._preparar(mock_deps, blocos=20)
        valido = (
            '{"ignorar": false, "nome": "Orgao", "status": "s", '
            '"link": "https://example.com/x", "fase": "edital_publicado"}'
        )
        # Ja conhecido e sem mudanca: os 19 validos nao geram card.
        mock_deps["db"].buscar_registro.return_value = {
            "id": 1, "fase": "edital_publicado", "estado_usuario": "ativo",
            "data_fim_inscricao": None, "nome": "Orgao",
        }

        bot = self._bot(mocker, base_config, respostas=[valido] * 19)
        bot.executar()

        assert bot.falhou is True
        mensagens = self._mensagens(mock_deps)
        assert len(mensagens) == 1
        assert "cota" in mensagens[0].lower()


class TestPrimeiraCargaPci:
    def _config_pci(self, base_config, modo):
        base_config["pci_slugs"] = ["analista-de-sistemas"]
        base_config["pci_primeira_carga"] = modo
        return base_config

    def _itens(self, n):
        return [{
            "ignorar": False, "nome": f"Prefeitura {i} - MG", "status": "abre concurso",
            "link": f"https://pci/{i}", "fase": "edital_publicado",
            "data_fim_inscricao": "2099-01-01", "data_referencia": None,
            "pci_id": str(i), "uf": "MG" if i % 2 else "SP", "cargos": [],
            "fonte": "pci",
        } for i in range(n)]

    def test_resumo_uf_agrupa_em_vez_de_um_ping_por_edital(
        self, mock_deps, base_config, mocker
    ):
        pci_cls = mocker.patch("src.core.bot.PciScraper")
        pci = pci_cls.return_value
        pci.capturar_concursos.return_value = self._itens(6)
        pci.enriquecer.side_effect = lambda i: i
        mock_deps["scraper"].capturar_concursos.return_value = []
        mock_deps["db"].contar_por_fonte.return_value = 0   # PCI nunca rodou
        mock_deps["db"].buscar_registro.return_value = None
        mock_deps["notifier"].notificar.return_value = True

        bot = ConcursoBot(self._config_pci(base_config, "resumo_uf"))
        bot.executar()

        # Nenhum card individual; so o aviso de abertura + 1 mensagem por UF.
        # O teste zera o Gran de proposito pra isolar o PCI, entao o aviso de
        # "fonte gran sem retorno" tambem sai — e esperado e nao conta aqui.
        mock_deps["notifier"].notificar_concurso.assert_not_called()
        da_carga = [
            chamada.args[0]
            for chamada in mock_deps["notifier"].notificar.call_args_list
            if "Fonte sem retorno" not in chamada.args[0]
        ]
        assert len(da_carga) == 3   # intro + MG + SP

    def test_silencioso_nao_manda_nada(self, mock_deps, base_config, mocker):
        pci_cls = mocker.patch("src.core.bot.PciScraper")
        pci = pci_cls.return_value
        pci.capturar_concursos.return_value = self._itens(4)
        pci.enriquecer.side_effect = lambda i: i
        mock_deps["scraper"].capturar_concursos.return_value = []
        mock_deps["db"].contar_por_fonte.return_value = 0
        mock_deps["db"].buscar_registro.return_value = None
        mock_deps["notifier"].notificar.return_value = True

        bot = ConcursoBot(self._config_pci(base_config, "silencioso"))
        bot.executar()

        mock_deps["notifier"].notificar_concurso.assert_not_called()
        # Semeou os 4 no banco mesmo sem notificar.
        assert mock_deps["db"].atualizar_concurso.call_count == 4

    def test_individual_manda_um_card_por_edital(self, mock_deps, base_config, mocker):
        pci_cls = mocker.patch("src.core.bot.PciScraper")
        pci = pci_cls.return_value
        pci.capturar_concursos.return_value = self._itens(4)
        pci.enriquecer.side_effect = lambda i: i
        mock_deps["scraper"].capturar_concursos.return_value = []
        mock_deps["db"].contar_por_fonte.return_value = 0
        mock_deps["db"].buscar_registro.return_value = None
        mock_deps["notifier"].notificar_concurso.return_value = True

        bot = ConcursoBot(self._config_pci(base_config, "individual"))
        bot.executar()

        assert mock_deps["notifier"].notificar_concurso.call_count == 4

    def test_segunda_rodada_nao_e_primeira_carga(self, mock_deps, base_config, mocker):
        pci_cls = mocker.patch("src.core.bot.PciScraper")
        pci = pci_cls.return_value
        pci.capturar_concursos.return_value = self._itens(3)
        pci.enriquecer.side_effect = lambda i: i
        mock_deps["scraper"].capturar_concursos.return_value = []
        mock_deps["db"].contar_por_fonte.return_value = 50   # PCI ja rodou
        mock_deps["db"].buscar_registro.return_value = None
        mock_deps["notifier"].notificar_concurso.return_value = True

        bot = ConcursoBot(self._config_pci(base_config, "resumo_uf"))
        bot.executar()

        # Fora da primeira carga, edital novo sai como card, mesmo em resumo_uf.
        assert mock_deps["notifier"].notificar_concurso.call_count == 3

    def test_pci_nao_enriquece_o_que_ja_esta_no_banco(self, mock_deps, base_config, mocker):
        pci_cls = mocker.patch("src.core.bot.PciScraper")
        pci = pci_cls.return_value
        pci.capturar_concursos.return_value = self._itens(3)
        mock_deps["scraper"].capturar_concursos.return_value = []
        mock_deps["db"].contar_por_fonte.return_value = 10
        mock_deps["db"].buscar_registro.return_value = {
            "id": 1, "fase": "edital_publicado", "estado_usuario": "ativo",
            "data_fim_inscricao": "2099-01-01", "nome": "Prefeitura 0 - MG",
        }
        mock_deps["notifier"].notificar.return_value = True

        bot = ConcursoBot(self._config_pci(base_config, "individual"))
        bot.executar()

        # Ja conhecido = nao gasta uma requisicao na noticia.
        pci.enriquecer.assert_not_called()


class TestDryRun:
    def test_dry_run_nao_escreve_nem_notifica(self, mock_deps, base_config):
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False, "nome": "TRF1", "status": "edital publicado",
            "link": "https://example.com/trf1", "data_fim_inscricao": _amanha(),
            "data_referencia": None,
        }
        mock_deps["db"].buscar_registro.return_value = None
        base_config["dry_run"] = True

        bot = ConcursoBot(base_config)
        bot.executar()

        # Escrever em dry-run marcaria os editais como vistos e a rodada real
        # seguinte nao notificaria nada.
        mock_deps["db"].atualizar_concurso.assert_not_called()
        mock_deps["notifier"].notificar_concurso.assert_not_called()
        mock_deps["notifier"].notificar.assert_not_called()


class TestFonteNacional:
    """Terceira fonte: a lista de concursos NACIONAIS do PCI.

    Existe por causa da Dataprev — 1.823 vagas, 1.793 de TI, inscricoes de
    06/07 a 06/08/2026 — que nem o artigo do Gran nem os slugs de cargo do PCI
    listaram enquanto estavam abertas.
    """

    LINK = "https://www.pciconcursos.com.br/noticias/dataprev-abre-concurso"

    def _item(self, **extra):
        base = {
            "ignorar": False,
            "nome": "DATAPREV - Empresa de Tecnologia e Informações da Previdência",
            "status": "Dataprev abre concurso público com 1.823 vagas",
            "link": self.LINK,
            "fase": "inscricoes_abertas",
            "data_fim_inscricao": _amanha(),
            "data_referencia": None,
            "pci_id": None,
            "uf": None,
            "cargos": ["Vários Cargos"],
            "nivel": "Superior",
            "vagas": "1823 vagas",
            "inicio_inscricao": None,
            "fonte": "pci_nacional",
        }
        base.update(extra)
        return base

    def _montar(self, mock_deps, base_config, mocker, itens):
        nacional_cls = mocker.patch("src.core.bot.PciNacionalScraper")
        nacional = nacional_cls.return_value
        nacional.url = "https://www.pciconcursos.com.br/concursos/nacional/"
        nacional.capturar_concursos.return_value = itens
        nacional.detalhar.side_effect = lambda i: i
        nacional.bloco_para_ia.side_effect = lambda i: f"<h3>{i['nome']}</h3>"

        mock_deps["scraper"].capturar_concursos.return_value = []
        mock_deps["notifier"].notificar.return_value = True
        mock_deps["notifier"].notificar_concurso.return_value = True

        base_config["pci_nacional"] = True
        return nacional

    def test_concurso_da_area_vira_notificacao_de_novo(
        self, mock_deps, base_config, mocker
    ):
        self._montar(mock_deps, base_config, mocker, [self._item()])
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False, "nome": "Concurso Dataprev", "status": "1823 vagas de TI",
            "link": self.LINK, "fase": "inscricoes_abertas",
            "data_fim_inscricao": _amanha(), "data_referencia": None,
        }

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["notifier"].notificar_concurso.assert_called_once()
        assert "NOVO" in mock_deps["notifier"].notificar_concurso.call_args.args[1]

    def test_o_link_vem_da_listagem_nao_do_que_a_llm_devolveu(
        self, mock_deps, base_config, mocker
    ):
        """A LLM decide UMA coisa: se e da area. Deixar ela escolher o link e
        exatamente o que duplica linha no banco entre uma rodada e outra."""
        self._montar(mock_deps, base_config, mocker, [self._item()])
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False, "nome": "Concurso Dataprev", "status": "s",
            "link": "https://site-inventado-pela-llm.com/x",
            "fase": "inscricoes_abertas", "data_fim_inscricao": _amanha(),
            "data_referencia": None,
        }

        bot = ConcursoBot(base_config)
        bot.executar()

        assert mock_deps["db"].atualizar_concurso.call_args.args[2] == self.LINK

    def test_o_nome_vem_da_listagem_nao_da_llm(self, mock_deps, base_config, mocker):
        """"SIGLA - Nome por extenso" e o formato que `mesma_entidade` casa com
        o que vem do Gran. A LLM devolve "DATAPREV - Concurso 2026"."""
        item = self._item()
        self._montar(mock_deps, base_config, mocker, [item])
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False, "nome": "DATAPREV - Concurso 2026", "status": "s",
            "link": self.LINK, "fase": "inscricoes_abertas",
            "data_fim_inscricao": _amanha(), "data_referencia": None,
        }

        bot = ConcursoBot(base_config)
        bot.executar()

        assert mock_deps["db"].atualizar_concurso.call_args.args[0] == item["nome"]

    def test_prazo_da_listagem_vence_o_da_llm(self, mock_deps, base_config, mocker):
        prazo_listagem = _amanha()
        self._montar(
            mock_deps, base_config, mocker,
            [self._item(data_fim_inscricao=prazo_listagem)],
        )
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False, "nome": "X", "status": "s", "link": self.LINK,
            "fase": "inscricoes_abertas", "data_fim_inscricao": "2099-12-31",
            "data_referencia": None,
        }

        bot = ConcursoBot(base_config)
        bot.executar()

        kwargs = mock_deps["db"].atualizar_concurso.call_args.kwargs
        assert kwargs["data_fim_inscricao"] == prazo_listagem

    def test_fora_da_area_nao_notifica_e_nao_grava(
        self, mock_deps, base_config, mocker
    ):
        self._montar(mock_deps, base_config, mocker, [self._item()])
        mock_deps["ai"].extrair_dados.return_value = {"ignorar": True}

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["notifier"].notificar_concurso.assert_not_called()
        mock_deps["db"].atualizar_concurso.assert_not_called()

    def test_descartado_nao_volta_pra_llm_no_dia_seguinte(
        self, mock_deps, base_config, mocker
    ):
        """Sem o memo de descarte, cada item fora da area custaria uma chamada
        de LLM por dia, para sempre, pra chegar sempre na mesma conclusao."""
        self._montar(mock_deps, base_config, mocker, [self._item()])
        mock_deps["ai"].extrair_dados.return_value = {"ignorar": True}

        ConcursoBot(base_config).executar()
        assert mock_deps["ai"].extrair_dados.call_count == 1

        ConcursoBot(base_config).executar()          # rodada seguinte
        assert mock_deps["ai"].extrair_dados.call_count == 1

    def test_prazo_novo_reabre_o_julgamento(self, mock_deps, base_config, mocker):
        """Prazo diferente pode ser edital novo do mesmo orgao."""
        nacional = self._montar(mock_deps, base_config, mocker, [self._item()])
        mock_deps["ai"].extrair_dados.return_value = {"ignorar": True}

        ConcursoBot(base_config).executar()

        nacional.capturar_concursos.return_value = [
            self._item(data_fim_inscricao="2099-01-01")
        ]
        ConcursoBot(base_config).executar()

        assert mock_deps["ai"].extrair_dados.call_count == 2

    def test_ja_no_banco_nao_abre_a_noticia_nem_chama_a_llm(
        self, mock_deps, base_config, mocker
    ):
        nacional = self._montar(mock_deps, base_config, mocker, [self._item()])
        mock_deps["db"].buscar_registro.return_value = {
            "id": 7, "fase": "inscricoes_abertas", "estado_usuario": "ativo",
            "data_fim_inscricao": _amanha(), "nome": "Dataprev",
        }

        bot = ConcursoBot(base_config)
        bot.executar()

        nacional.detalhar.assert_not_called()
        mock_deps["ai"].extrair_dados.assert_not_called()

    def test_item_ja_visto_pelo_slug_de_cargo_e_pulado(
        self, mock_deps, base_config, mocker
    ):
        """O mesmo link pode chegar pelas duas portas do PCI na mesma rodada."""
        nacional = self._montar(mock_deps, base_config, mocker, [self._item()])

        pci_cls = mocker.patch("src.core.bot.PciScraper")
        pci_cls.return_value.capturar_concursos.return_value = [{
            "ignorar": False, "nome": "Dataprev", "status": "s", "link": self.LINK,
            "fase": "inscricoes_abertas", "data_fim_inscricao": _amanha(),
            "data_referencia": None, "pci_id": "999", "uf": None, "cargos": [],
            "fonte": "pci",
        }]
        pci_cls.return_value.enriquecer.side_effect = lambda i: i
        base_config["pci_slugs"] = ["tecnologia-da-informacao"]
        mock_deps["db"].contar_por_fonte.return_value = 5   # nao e primeira carga

        bot = ConcursoBot(base_config)
        bot.executar()

        nacional.detalhar.assert_not_called()
        mock_deps["ai"].extrair_dados.assert_not_called()
        assert mock_deps["notifier"].notificar_concurso.call_count == 1

    def test_dry_run_nao_persiste_descarte(self, mock_deps, base_config, mocker):
        """Persistir em dry-run faria a rodada real seguinte pular o item."""
        self._montar(mock_deps, base_config, mocker, [self._item()])
        mock_deps["ai"].extrair_dados.return_value = {"ignorar": True}
        base_config["dry_run"] = True

        ConcursoBot(base_config).executar()
        base_config["dry_run"] = False
        ConcursoBot(base_config).executar()

        assert mock_deps["ai"].extrair_dados.call_count == 2

    def test_desligado_por_padrao(self, mock_deps, base_config, mocker):
        nacional_cls = mocker.patch("src.core.bot.PciNacionalScraper")
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>b</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {"ignorar": True}
        mock_deps["notifier"].notificar.return_value = True

        ConcursoBot(base_config).executar()

        nacional_cls.assert_not_called()


class TestFonteMcp:
    """Quarta fonte: a porta do PCI pelo servidor MCP (estruturada, sem LLM).

    A porta entra ENTRE a pagina de cargo e a lista nacional, de proposito:
    e a lista nacional quem le o conjunto de links do PCI ja vistos na rodada,
    e o MCP o alimenta — entrando depois dela, os links chegariam tarde
    (ADR-0001). Sem filtro ainda; o filtro e do ticket seguinte.
    """

    TERMO = "analista de sistemas"

    def _item(self, i=1, **extra):
        """Item no formato da SPEC-001, secao 3.1, escrito a mao."""
        base = {
            "ignorar": False,
            "nome": f"Orgao {i} - MG",
            "status": f"Concurso {i} com inscricoes abertas",
            "link": f"https://www.pciconcursos.com.br/noticias/orgao-{i}",
            "fase": "inscricoes_abertas",
            "data_fim_inscricao": _amanha(),
            "data_referencia": None,
            "pci_id": str(296653 + i),
            "uf": "MG",
            "cargos": ["ANALISTA DE SISTEMAS"],
            "fonte": "pci_mcp",
            "regiao": "SUDESTE",
            "cargos_total": 3,
            "vagas_salario": "10 vagas ate R$ 5.000,00",
            "termos_origem": [self.TERMO],
        }
        base.update(extra)
        return base

    def _montar(self, mock_deps, base_config, mocker, itens):
        """Liga a porta do MCP com o duble devolvendo `itens`; Gran zerado."""
        mcp_cls = mocker.patch("src.core.bot.PciMcpScraper")
        mcp = mcp_cls.return_value
        mcp.url = URL_SERVIDOR
        mcp.capturar_concursos.return_value = itens

        mock_deps["scraper"].capturar_concursos.return_value = []
        mock_deps["notifier"].notificar.return_value = True
        mock_deps["notifier"].notificar_concurso.return_value = True

        base_config["pci_mcp"] = True
        base_config["pci_mcp_cargos"] = [self.TERMO]
        return mcp

    def test_mcp_desligado_nao_instancia_scraper(
        self, mock_deps, base_config, mocker
    ):
        mcp_cls = mocker.patch("src.core.bot.PciMcpScraper")
        avaliar = mocker.patch("src.core.bot.saude_fontes.avaliar")
        mock_deps["scraper"].capturar_concursos.return_value = []

        bot = ConcursoBot(base_config)
        bot.executar()

        assert bot.mcp_scraper is None
        mcp_cls.assert_not_called()
        # Diagnostico de saude rodou na costura e nao inclui a porta desligada.
        fontes = [c.args[1] for c in avaliar.call_args_list]
        assert "gran" in fontes
        assert "pci_mcp" not in fontes

    def test_mcp_ligado_instancia_com_os_termos(
        self, mock_deps, base_config, mocker
    ):
        mcp_cls = mocker.patch("src.core.bot.PciMcpScraper")
        base_config["pci_mcp"] = True
        base_config["pci_mcp_cargos"] = [
            "tecnico em informatica", "analista de sistemas",
        ]

        bot = ConcursoBot(base_config)

        mcp_cls.assert_called_once_with(
            ["tecnico em informatica", "analista de sistemas"]
        )
        assert bot.mcp_scraper is mcp_cls.return_value

    def test_itens_do_mcp_passam_pela_decisao(
        self, mock_deps, base_config, mocker
    ):
        itens = [self._item(i) for i in (1, 2, 3)]
        self._montar(mock_deps, base_config, mocker, itens)
        mock_deps["db"].buscar_registro.return_value = None

        bot = ConcursoBot(base_config)
        decisao = mocker.spy(bot, "_decidir_e_notificar")
        bot.executar()

        assert decisao.call_count == 3
        assert [c.kwargs["url_indice"] for c in decisao.call_args_list] == [
            i["link"] for i in itens
        ]
        # Tres itens novos: tres cards de NOVO (o contador de novos fecha 3).
        cards = mock_deps["notifier"].notificar_concurso.call_args_list
        assert len(cards) == 3
        assert all("NOVO CONCURSO" in c.args[1] for c in cards)

    def test_mcp_nao_chama_enriquecer(self, mock_deps, base_config, mocker):
        mcp = self._montar(mock_deps, base_config, mocker, [self._item(1)])
        mock_deps["db"].buscar_registro.return_value = None

        ConcursoBot(base_config).executar()

        # O MCP ja devolve `data_fim_inscricao`: nada de abrir a noticia por
        # item novo (ADR-0001) — a requisicao extra era o custo da pagina de
        # cargo, metade do motivo da troca de porta.
        mcp.enriquecer.assert_not_called()

    def test_mcp_registra_a_fonte_na_saude(
        self, mock_deps, base_config, mocker
    ):
        itens = [self._item(1), self._item(2)]
        self._montar(mock_deps, base_config, mocker, itens)
        # O Gran entrega um bloco ja conhecido: sem cegueira agregada, para o
        # alerta por fonte nao ser silenciado pelo agregado.
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>b</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False, "nome": "Orgao X", "status": "s",
            "link": "https://example.com/x", "fase": "previsto",
            "data_fim_inscricao": None, "data_referencia": None,
        }
        mock_deps["db"].buscar_registro.return_value = {
            "id": 1, "fase": "previsto", "estado_usuario": "ativo",
            "data_fim_inscricao": None, "nome": "Orgao X",
        }

        capturadas = {}

        def avaliar_fake(area, fonte, assinaturas, **kw):
            capturadas[fonte] = list(assinaturas)
            doente = fonte == "pci_mcp"
            return saude_fontes.Diagnostico(
                fonte, 45, 89 if doente else 0, False, doente
            )

        mocker.patch("src.core.bot.saude_fontes.avaliar", side_effect=avaliar_fake)

        ConcursoBot(base_config).executar()

        # Assinatura no mesmo formato da fonte 2: `pci_id|status`.
        assert capturadas.get("pci_mcp") == [
            "296654|Concurso 1 com inscricoes abertas",
            "296655|Concurso 2 com inscricoes abertas",
        ]
        mensagens = [
            c.args[0] for c in mock_deps["notifier"].notificar.call_args_list
        ]
        alerta = [m for m in mensagens if "Fonte parada" in m]
        assert len(alerta) == 1
        assert "pci_mcp" in alerta[0]
        assert URL_SERVIDOR in alerta[0]

    def test_url_da_fonte_do_mcp(self, mock_deps, base_config):
        # Sem dublar o PciMcpScraper (instanciar nao faz rede): o endereco
        # afirmado e o do servidor real, o mesmo da ADR-0001.
        base_config["pci_mcp"] = True
        base_config["pci_mcp_cargos"] = ["analista de sistemas"]

        bot = ConcursoBot(base_config)

        assert bot._url_da_fonte("pci_mcp") == "https://mcp.pciconcursos.com.br/mcp"

    def test_links_do_mcp_entram_no_conjunto_de_vistos(
        self, mock_deps, base_config, mocker
    ):
        """A lista nacional roda DEPOIS e le o conjunto: mesmo link nao
        reprocessa (sem abrir noticia, sem LLM)."""
        item_mcp = self._item(1)
        self._montar(mock_deps, base_config, mocker, [item_mcp])
        mock_deps["db"].buscar_registro.return_value = None

        nacional_cls = mocker.patch("src.core.bot.PciNacionalScraper")
        nacional = nacional_cls.return_value
        nacional.url = "https://www.pciconcursos.com.br/concursos/nacional/"
        nacional.capturar_concursos.return_value = [{
            "ignorar": False,
            "nome": "Orgao 1",
            "status": "Concurso com inscricoes abertas",
            "link": item_mcp["link"],
            "fase": "inscricoes_abertas",
            "data_fim_inscricao": _amanha(),
            "data_referencia": None,
            "pci_id": None,
            "uf": "MG",
            "cargos": ["Vários Cargos"],
            "nivel": "Superior",
            "vagas": "10 vagas",
            "inicio_inscricao": None,
            "fonte": "pci_nacional",
        }]
        nacional.detalhar.side_effect = lambda i: i
        nacional.bloco_para_ia.side_effect = lambda i: f"<h3>{i['nome']}</h3>"
        base_config["pci_nacional"] = True

        ConcursoBot(base_config).executar()

        nacional.detalhar.assert_not_called()
        mock_deps["ai"].extrair_dados.assert_not_called()
        # O item do MCP, ele sim, virou card.
        assert mock_deps["notifier"].notificar_concurso.call_count == 1

    def test_falha_total_do_mcp_marca_a_area_e_segue(
        self, mock_deps, base_config, mocker
    ):
        mcp = self._montar(mock_deps, base_config, mocker, [])
        mcp.capturar_concursos.side_effect = RuntimeError(
            "MCP: todos os 1 termo(s) falharam; a fonte pode estar parada."
        )
        # O Gran e varrido na frente e a nacional roda depois: a rodada nao
        # pode parar no meio por causa da porta nova.
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False, "nome": "TRF1", "status": "edital publicado",
            "link": "https://example.com/trf1", "data_fim_inscricao": _amanha(),
            "data_referencia": None,
        }
        mock_deps["db"].buscar_registro.return_value = None

        nacional_cls = mocker.patch("src.core.bot.PciNacionalScraper")
        nacional = nacional_cls.return_value
        nacional.url = "https://www.pciconcursos.com.br/concursos/nacional/"
        nacional.capturar_concursos.return_value = []
        base_config["pci_nacional"] = True

        bot = ConcursoBot(base_config)
        bot.executar()  # nao levanta para fora

        mock_deps["ai"].extrair_dados.assert_called_once()   # o Gran foi varrido
        nacional.capturar_concursos.assert_called_once()     # a fonte seguinte seguiu
        assert bot.falhou is True                            # ...mas conta como falha

    def test_gran_vazio_com_mcp_trazendo_item_nao_e_cegueira(
        self, mock_deps, base_config, mocker
    ):
        """Gran com 0 blocos, pagina de cargo desligada e a porta do MCP com item.

        E o deploy da porta do MCP como unica porta do PCI: `pci_slugs` sai,
        e um dia em que o blog do Gran nao devolve nada nao e rodada cega
        enquanto o MCP trouxe materia-prima.
        """
        self._montar(mock_deps, base_config, mocker, [self._item(1)])
        base_config["keywords_include"] = ["ti"]
        mock_deps["db"].buscar_registro.return_value = None

        bot = ConcursoBot(base_config)
        bot.executar()

        assert bot.pci_scraper is None
        assert bot.falhou is False
        mensagens = [c.args[0] for c in mock_deps["notifier"].notificar.call_args_list]
        assert not any("Atenção" in m for m in mensagens)

    def test_mcp_e_gran_na_mesma_rodada_somam_contadores(
        self, mock_deps, base_config, mocker
    ):
        self._montar(mock_deps, base_config, mocker, [self._item(1), self._item(2)])
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False, "nome": "TRF1", "status": "edital publicado",
            "link": "https://example.com/trf1", "data_fim_inscricao": _amanha(),
            "data_referencia": None, "fase": "edital_publicado",
        }
        mock_deps["db"].buscar_registro.return_value = None

        ConcursoBot(base_config).executar()

        # 1 novo do Gran + 2 novos do MCP: os contadores somam as duas fontes.
        cards = mock_deps["notifier"].notificar_concurso.call_args_list
        assert len(cards) == 3
        assert sum("TRF1" in c.args[1] for c in cards) == 1
        assert sum("Orgao" in c.args[1] for c in cards) == 2

    def test_contadores_do_mcp_e_do_gran_aparecem_no_resumo_final(
        self, mock_deps, base_config, mocker, caplog
    ):
        """Os acumuladores `novos_cont` e `atualizados_cont` somam Gran e MCP
        no texto do resumo final de `_mensagem_final`."""
        self._montar(mock_deps, base_config, mocker, [self._item(1), self._item(2)])
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False, "nome": "TRF1", "status": "edital publicado",
            "link": "https://example.com/trf1", "data_fim_inscricao": _amanha(),
            "data_referencia": None, "fase": "edital_publicado",
        }

        def _buscar(nome, **_kw):
            if nome == "Orgao 2 - MG":
                return {
                    "id": 10, "fase": "banca_definida", "estado_usuario": "ativo",
                    "data_fim_inscricao": _amanha(), "nome": nome,
                }
            return None

        mock_deps["db"].buscar_registro.side_effect = _buscar

        with caplog.at_level("INFO"):
            ConcursoBot(base_config).executar()

        # 1 novo do Gran + 1 novo do MCP = 2 novos; 1 avanco de fase do MCP = 1 atualizacao.
        logs = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
        assert any("2 novos e 1 atualizações enviadas" in msg for msg in logs)

    def test_validos_do_mcp_e_do_gran_aparecem_no_heartbeat(
        self, mock_deps, base_config, mocker
    ):
        """Sem novidades, o acumulador `validos` soma Gran e MCP no heartbeat."""
        self._montar(mock_deps, base_config, mocker, [self._item(1), self._item(2)])
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False, "nome": "TRF1", "status": "edital publicado",
            "link": "https://example.com/trf1", "data_fim_inscricao": _amanha(),
            "data_referencia": None, "fase": "edital_publicado",
        }

        def _buscar(nome, **_kw):
            fase = "edital_publicado" if nome == "TRF1" else "inscricoes_abertas"
            return {
                "id": 10, "fase": fase, "estado_usuario": "ativo",
                "data_fim_inscricao": _amanha(), "nome": nome,
            }

        mock_deps["db"].buscar_registro.side_effect = _buscar

        ConcursoBot(base_config).executar()

        mock_deps["notifier"].notificar_concurso.assert_not_called()
        mensagens = [c.args[0] for c in mock_deps["notifier"].notificar.call_args_list]
        assert any("Analisei <b>3</b> concursos" in m for m in mensagens)

    def test_dedup_entre_mcp_e_gran_pelo_pci_id(
        self, mock_deps, base_config, mocker, tmp_path
    ):
        """O mesmo concurso chega pelo Gran e pelo MCP: grava uma linha so.

        Banco de verdade em disco temporario — o casamento entre fontes e do
        DatabaseManager (`mesma_entidade`), e a costura precisa atravessa-lo.
        """
        from src.database.manager import DatabaseManager as BancoReal

        self._montar(mock_deps, base_config, mocker, [self._item(
            1,
            nome="Tribunal Regional Eleitoral do Paraná - PR",
            status="Inscrições abertas para o TRE-PR",
            link="https://www.pciconcursos.com.br/noticias/tre-pr",
            pci_id="296654",
        )])
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "TRE-PR - Tribunal Regional Eleitoral do Paraná",
            "status": "edital publicado",
            "link": "https://example.com/tre-pr",
            "data_fim_inscricao": _amanha(),
            "data_referencia": None,
            "fase": "inscricoes_abertas",
        }

        caminho_banco = tmp_path / "concursos.db"
        mocker.patch(
            "src.core.bot.DatabaseManager",
            side_effect=lambda area: BancoReal(area=area, db_path=str(caminho_banco)),
        )

        bot = ConcursoBot(base_config)
        bot.executar()

        # Um card so: o item do MCP encontrou a linha que o Gran gravou.
        assert mock_deps["notifier"].notificar_concurso.call_count == 1

        conferencia = BancoReal(area="TI", db_path=str(caminho_banco))
        try:
            linha_do_gran = conferencia.buscar_registro(
                "TRE-PR - Tribunal Regional Eleitoral do Paraná"
            )
            linha_do_mcp = conferencia.buscar_registro(
                "Tribunal Regional Eleitoral do Paraná - PR", pci_id="296654"
            )
            assert linha_do_gran is not None and linha_do_mcp is not None
            assert linha_do_gran["id"] == linha_do_mcp["id"]   # uma linha so
            # E o dado do MCP chegou nela: so a porta nova conhece o pci_id.
            assert linha_do_gran["pci_id"] == "296654"
        finally:
            conferencia.fechar_conexao()
            bot.db.fechar_conexao()


class TestAlertaPorFonte:
    """Uma fonte pode estar morta enquanto o agregado parece um dia normal."""

    def test_fonte_parada_alerta_mesmo_com_a_outra_viva(
        self, mock_deps, base_config, mocker
    ):
        """O caso Dataprev: `concursos-ti/` congelado em 12/06/2026 enquanto o
        PCI trazia novidade todo dia, e o bot reportava sucesso."""
        mocker.patch(
            "src.core.bot.saude_fontes.avaliar",
            side_effect=lambda area, fonte, ass, **kw: saude_fontes.Diagnostico(
                fonte, 45, 89, False, fonte == "gran"
            ),
        )
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>b</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False, "nome": "Orgao", "status": "s",
            "link": "https://example.com/x", "fase": "previsto",
            "data_fim_inscricao": None, "data_referencia": None,
        }
        mock_deps["db"].buscar_registro.return_value = {
            "id": 1, "fase": "previsto", "estado_usuario": "ativo",
            "data_fim_inscricao": None, "nome": "Orgao",
        }
        mock_deps["notifier"].notificar.return_value = True

        bot = ConcursoBot(base_config)
        bot.executar()

        mensagens = [c.args[0] for c in mock_deps["notifier"].notificar.call_args_list]
        assert any("Fonte parada" in m and "89 dias" in m for m in mensagens)

    def test_fonte_parada_nao_marca_falha_da_rodada(
        self, mock_deps, base_config, mocker
    ):
        """Retry nao conserta pagina congelada; marcar falha so faria o
        catch-up horario queimar LLM nas outras fontes o dia inteiro."""
        mocker.patch(
            "src.core.bot.saude_fontes.avaliar",
            return_value=saude_fontes.Diagnostico("gran", 45, 89, False, True),
        )
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>b</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False, "nome": "Orgao", "status": "s",
            "link": "https://example.com/x", "fase": "previsto",
            "data_fim_inscricao": None, "data_referencia": None,
        }
        mock_deps["db"].buscar_registro.return_value = {
            "id": 1, "fase": "previsto", "estado_usuario": "ativo",
            "data_fim_inscricao": None, "nome": "Orgao",
        }
        mock_deps["notifier"].notificar.return_value = True

        bot = ConcursoBot(base_config)
        bot.executar()

        assert bot.falhou is False

    def test_alerta_agregado_tem_precedencia(self, mock_deps, base_config):
        """Varredura cega ja explica o problema; nao manda a segunda mensagem."""
        mock_deps["scraper"].capturar_concursos.return_value = []
        mock_deps["notifier"].notificar.return_value = True

        bot = ConcursoBot(base_config)
        bot.executar()

        mensagens = [c.args[0] for c in mock_deps["notifier"].notificar.call_args_list]
        assert len(mensagens) == 1
        assert "Atenção" in mensagens[0]

    def test_alerta_de_fonte_sai_uma_vez_por_dia(self, mock_deps, base_config, mocker):
        mocker.patch(
            "src.core.bot.saude_fontes.avaliar",
            return_value=saude_fontes.Diagnostico("gran", 0, 0, True, False),
        )
        mock_deps["scraper"].capturar_concursos.return_value = []
        mock_deps["ai"].extrair_dados.return_value = {"ignorar": True}
        mock_deps["notifier"].notificar.return_value = True
        base_config["keywords_include"] = ["ti"]

        pci_cls = mocker.patch("src.core.bot.PciScraper")
        pci_cls.return_value.capturar_concursos.return_value = []
        base_config["pci_slugs"] = ["x"]
        mock_deps["db"].contar_por_fonte.return_value = 5

        ConcursoBot(base_config).executar()
        ConcursoBot(base_config).executar()

        mensagens = [c.args[0] for c in mock_deps["notifier"].notificar.call_args_list]
        assert sum(1 for m in mensagens if "Fonte sem retorno" in m) == 1


# ---------------------------------------------------------------------------
# Filtro salarial na matriz de decisao (SPEC-001, secoes 4.2 e 4.3)
# ---------------------------------------------------------------------------

SELO = "salario nao verificado"   # texto do selo, SPEC-001 secao 4.2


def _item_mcp(nome, uf, regiao, vagas_salario, cargos_total, pci_id="1", **extra):
    """Item da porta do MCP no formato da SPEC-001, secao 3.1, escrito a mao.

    Os valores dos testes abaixo vem de concursos reais das fixtures em
    tests/fixtures/pci_mcp/ (orgao, UF, regiao, teto, cargos_total).
    """
    base = {
        "ignorar": False,
        "nome": nome,
        "status": f"{nome} abre concurso",
        "link": f"https://www.pciconcursos.com.br/noticias/concurso-{pci_id}",
        "fase": "inscricoes_abertas",
        "data_fim_inscricao": _amanha(),
        "data_referencia": None,
        "pci_id": pci_id,
        "uf": uf,
        "cargos": ["ANALISTA DE SISTEMAS"],
        "fonte": "pci_mcp",
        "regiao": regiao,
        "cargos_total": cargos_total,
        "vagas_salario": vagas_salario,
        "termos_origem": ["analista de sistemas"],
    }
    base.update(extra)
    return base


# Vereditos decididos a mao pela tabela da SPEC-001 secao 4.2, com corte 10000.
SANTA_LUZIA_MG = dict(   # municipal, MG, teto < corte -> regra 5, abaixo_do_corte
    nome="Prefeitura de Santa Luzia - MG", uf="MG", regiao="SUDESTE",
    vagas_salario="454 vagas até R$ 8.628,87", cargos_total=72, pci_id="295546",
)
GUARATINGUETA_SP = dict(  # municipal, SP, teto > corte, 86 cargos -> regra 6
    nome="Prefeitura da Estância Turística de Guaratinguetá - SP", uf="SP",
    regiao="SUDESTE", vagas_salario="107 vagas até R$ 18.540,71",
    cargos_total=86, pci_id="296373",
)
LUIZ_ALVES_SC = dict(     # SC -> regra 3, sul
    nome="Prefeitura de Luiz Alves - SC", uf="SC", regiao="SUL",
    vagas_salario="10 vagas até R$ 8.889,30", cargos_total=56, pci_id="296100",
)
UFMS_MS = dict(           # federal -> regra 4
    nome="UFMS - Fundação Universidade Federal de Mato Grosso do Sul - MS",
    uf="MS", regiao="CENTRO-OESTE", vagas_salario="154 vagas até R$ 5.215,39",
    cargos_total=49, pci_id="296303",
)
SEM_LOCAL = dict(         # uf e regiao nulas -> regra 2, nao_verificado, com selo
    nome="Concurso Nacional Unificado", uf=None, regiao=None,
    vagas_salario="900 vagas até R$ 9.000,00", cargos_total=40, pci_id="296999",
)
TJMG = dict(              # estadual, MG, teto > corte, poucos cargos -> regra 8
    nome="Tribunal de Justiça de Minas Gerais - MG", uf="MG", regiao="SUDESTE",
    vagas_salario="30 vagas até R$ 15.000,00", cargos_total=3, pci_id="296500",
)
SEM_TETO = dict(          # estadual, MG, teto desconhecido -> regra 7, sem_evidencia, com selo
    nome="Tribunal de Justiça de Minas Gerais - MG", uf="MG", regiao="SUDESTE",
    vagas_salario="30 vagas - salário a combinar", cargos_total=3, pci_id="296501",
)


class TestFiltroSalarial:
    """O filtro salarial ligado na matriz de decisao, pela rodada inteira.

    O erro aqui e silencio: um concurso que devia chegar e nao chega nao
    quebra nada. Cada regra de borda tem teste proprio.
    """

    def _montar(self, mock_deps, base_config, mocker, itens, filtro="ativo"):
        mcp_cls = mocker.patch("src.core.bot.PciMcpScraper")
        mcp = mcp_cls.return_value
        mcp.url = URL_SERVIDOR
        mcp.capturar_concursos.return_value = itens

        mock_deps["scraper"].capturar_concursos.return_value = []
        mock_deps["notifier"].notificar.return_value = True
        mock_deps["notifier"].notificar_concurso.return_value = True

        base_config["pci_mcp"] = True
        base_config["pci_mcp_cargos"] = ["analista de sistemas"]
        if filtro is not None:
            base_config["filtro_salarial"] = filtro
            base_config["corte_fora_sul"] = 10000.0
            base_config["cargos_total_inflado"] = 10
        return mcp

    @staticmethod
    def _cards(mock_deps):
        return [c.args[1] for c in mock_deps["notifier"].notificar_concurso.call_args_list]

    @staticmethod
    def _gravacao(mock_deps):
        """Os argumentos nomeados da ultima gravacao no banco."""
        return mock_deps["db"].atualizar_concurso.call_args.kwargs

    def test_filtrado_nao_notifica_e_salva_em_silencio(
        self, mock_deps, base_config, mocker
    ):
        self._montar(mock_deps, base_config, mocker, [_item_mcp(**SANTA_LUZIA_MG)])

        ConcursoBot(base_config).executar()

        mock_deps["notifier"].notificar_concurso.assert_not_called()
        gravado = self._gravacao(mock_deps)
        assert gravado["elegibilidade"] == "filtrado"
        assert gravado["motivo_filtro"] == "abaixo_do_corte"
        # As sete colunas do v6 vao junto.
        assert gravado["uf"] == "MG"
        assert gravado["regiao"] == "SUDESTE"
        assert gravado["esfera"] == "municipal"
        assert gravado["cargos_total"] == 72
        assert gravado["salario_teto"] == 8628.87
        # Contador de novos fecha em 0: a rodada termina no heartbeat de
        # "nenhuma alteracao", que so sai quando novos e atualizados sao 0.
        # (A outra mensagem possivel e o aviso de fonte do Gran vazio.)
        mensagens = [c.args[0] for c in mock_deps["notifier"].notificar.call_args_list]
        assert any("não encontrei nenhuma alteração" in m for m in mensagens)

    def test_municipal_inflado_nao_notifica(self, mock_deps, base_config, mocker):
        self._montar(mock_deps, base_config, mocker, [_item_mcp(**GUARATINGUETA_SP)])

        ConcursoBot(base_config).executar()

        mock_deps["notifier"].notificar_concurso.assert_not_called()
        gravado = self._gravacao(mock_deps)
        assert gravado["elegibilidade"] == "filtrado"
        assert gravado["motivo_filtro"] == "municipal_inflado"
        assert gravado["salario_teto"] == 18540.71
        assert gravado["cargos_total"] == 86

    def test_do_sul_notifica_mesmo_com_teto_baixo(self, mock_deps, base_config, mocker):
        self._montar(mock_deps, base_config, mocker, [_item_mcp(**LUIZ_ALVES_SC)])

        ConcursoBot(base_config).executar()

        cards = self._cards(mock_deps)
        assert len(cards) == 1 and "NOVO CONCURSO" in cards[0]
        gravado = self._gravacao(mock_deps)
        assert gravado["elegibilidade"] == "elegivel"
        assert gravado["motivo_filtro"] == "sul"
        assert gravado["uf"] == "SC"
        assert gravado["regiao"] == "SUL"
        assert gravado["esfera"] == "municipal"
        assert gravado["cargos_total"] == 56
        assert gravado["salario_teto"] == 8889.30

    def test_federal_notifica_mesmo_abaixo_do_corte(
        self, mock_deps, base_config, mocker
    ):
        self._montar(mock_deps, base_config, mocker, [_item_mcp(**UFMS_MS)])

        ConcursoBot(base_config).executar()

        assert len(self._cards(mock_deps)) == 1
        gravado = self._gravacao(mock_deps)
        assert gravado["elegibilidade"] == "elegivel"
        assert gravado["motivo_filtro"] == "federal"
        assert gravado["esfera"] == "federal"

    def test_estrelado_notifica_mesmo_filtravel(self, mock_deps, base_config, mocker):
        # A fase avancou: com a estrela, transicao real sempre chega.
        self._montar(mock_deps, base_config, mocker, [_item_mcp(**SANTA_LUZIA_MG)])
        mock_deps["db"].buscar_registro.return_value = {
            "id": 7, "estado_usuario": "seguindo", "fase": "edital_publicado",
            "data_fim_inscricao": _amanha(), "elegibilidade": "elegivel",
        }

        ConcursoBot(base_config).executar()

        cards = self._cards(mock_deps)
        assert len(cards) == 1
        gravado = self._gravacao(mock_deps)
        assert gravado["elegibilidade"] == "elegivel"
        assert gravado["motivo_filtro"] == "seguindo"

    def test_ignorado_continua_saindo_antes_do_filtro(
        self, mock_deps, base_config, mocker
    ):
        # Item filtravel: se o filtro rodasse antes do `ignorado`, ele gravaria
        # `filtrado` no banco de um concurso que o usuario descartou.
        self._montar(mock_deps, base_config, mocker, [_item_mcp(**SANTA_LUZIA_MG)])
        mock_deps["db"].buscar_registro.return_value = {
            "id": 7, "estado_usuario": "ignorado", "fase": "edital_publicado",
            "data_fim_inscricao": _amanha(), "elegibilidade": None,
        }

        ConcursoBot(base_config).executar()

        mock_deps["db"].atualizar_concurso.assert_not_called()
        mock_deps["notifier"].notificar_concurso.assert_not_called()

    def test_item_do_gran_nao_e_avaliado(self, mock_deps, base_config, mocker):
        # Avaliado, este item cairia em `sem_evidencia` (MG, sem teto) e levaria selo.
        self._montar(mock_deps, base_config, mocker, [])
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False, "nome": "Prefeitura de Santa Luzia - MG",
            "status": "edital publicado", "link": "https://example.com/santa-luzia",
            "data_fim_inscricao": _amanha(), "data_referencia": None,
            "fase": "inscricoes_abertas",
        }

        ConcursoBot(base_config).executar()

        cards = self._cards(mock_deps)
        assert len(cards) == 1 and "NOVO CONCURSO" in cards[0]
        assert SELO not in cards[0] and "⚠️" not in cards[0]
        gravado = self._gravacao(mock_deps)
        for coluna in ("uf", "regiao", "esfera", "cargos_total", "salario_teto",
                       "elegibilidade", "motivo_filtro"):
            assert gravado.get(coluna) is None, coluna

    def test_item_da_pagina_de_cargo_nao_e_avaliado(
        self, mock_deps, base_config, mocker
    ):
        self._montar(mock_deps, base_config, mocker, [])
        pci_cls = mocker.patch("src.core.bot.PciScraper")
        pci_cls.return_value.capturar_concursos.return_value = [{
            "ignorar": False, "nome": "Prefeitura de Santa Luzia - MG",
            "status": "Concurso aberto", "link": "https://www.pciconcursos.com.br/noticias/x",
            "fase": "inscricoes_abertas", "data_fim_inscricao": _amanha(),
            "data_referencia": None, "pci_id": "295546", "uf": "MG",
            "cargos": ["ANALISTA DE SISTEMAS"], "fonte": "pci",
        }]
        base_config["pci_slugs"] = ["analista-de-sistemas"]
        mock_deps["db"].contar_por_fonte.return_value = 5   # nao e primeira carga

        ConcursoBot(base_config).executar()

        cards = self._cards(mock_deps)
        assert len(cards) == 1 and "⚠️" not in cards[0]
        gravado = self._gravacao(mock_deps)
        assert gravado.get("elegibilidade") is None
        assert gravado.get("motivo_filtro") is None

    def test_filtrado_que_passa_a_entrar_sai_como_novo(
        self, mock_deps, base_config, mocker
    ):
        # Mesma fase e mesma data: sem a regra, seria refresh silencioso.
        item = _item_mcp(**LUIZ_ALVES_SC)
        self._montar(mock_deps, base_config, mocker, [item])
        mock_deps["db"].buscar_registro.return_value = {
            "id": 7, "estado_usuario": "ativo", "fase": "inscricoes_abertas",
            "data_fim_inscricao": item["data_fim_inscricao"],
            "elegibilidade": "filtrado", "motivo_filtro": "abaixo_do_corte",
        }

        ConcursoBot(base_config).executar()

        cards = self._cards(mock_deps)
        assert len(cards) == 1
        assert "NOVO CONCURSO" in cards[0]
        assert "ATUALIZAÇÃO" not in cards[0]
        assert self._gravacao(mock_deps)["elegibilidade"] == "elegivel"

    def test_elegivel_que_passa_a_filtrado_nao_renotifica(
        self, mock_deps, base_config, mocker
    ):
        # A fase avancou: sem o filtro, sairia uma ATUALIZACAO.
        self._montar(mock_deps, base_config, mocker, [_item_mcp(**SANTA_LUZIA_MG)])
        mock_deps["db"].buscar_registro.return_value = {
            "id": 7, "estado_usuario": "ativo", "fase": "edital_publicado",
            "data_fim_inscricao": None, "elegibilidade": "elegivel",
            "motivo_filtro": "acima_do_corte",
        }

        ConcursoBot(base_config).executar()

        mock_deps["notifier"].notificar_concurso.assert_not_called()
        gravado = self._gravacao(mock_deps)
        assert gravado["elegibilidade"] == "filtrado"
        assert gravado["motivo_filtro"] == "abaixo_do_corte"

    def test_selo_aparece_no_card(self, mock_deps, base_config, mocker):
        self._montar(mock_deps, base_config, mocker, [_item_mcp(**SEM_LOCAL)])

        ConcursoBot(base_config).executar()

        cards = self._cards(mock_deps)
        assert len(cards) == 1
        assert "⚠️ " + SELO in cards[0]
        assert self._gravacao(mock_deps)["motivo_filtro"] == "nao_verificado"

    def test_selo_sem_evidencia_aparece_no_card(self, mock_deps, base_config, mocker):
        self._montar(mock_deps, base_config, mocker, [_item_mcp(**SEM_TETO)])

        ConcursoBot(base_config).executar()

        cards = self._cards(mock_deps)
        assert len(cards) == 1
        assert "⚠️ " + SELO in cards[0]
        gravado = self._gravacao(mock_deps)
        assert gravado["elegibilidade"] == "elegivel"
        assert gravado["motivo_filtro"] == "sem_evidencia"
        assert gravado["salario_teto"] is None

    def test_sem_selo_nao_poe_linha_extra(self, mock_deps, base_config, mocker):
        self._montar(mock_deps, base_config, mocker, [_item_mcp(**TJMG)])

        ConcursoBot(base_config).executar()

        cards = self._cards(mock_deps)
        assert len(cards) == 1
        assert "⚠️" not in cards[0]
        assert self._gravacao(mock_deps)["motivo_filtro"] == "acima_do_corte"

    def test_uf_sai_do_nome_quando_o_item_nao_traz(
        self, mock_deps, base_config, mocker
    ):
        # Sem uf no campo e sem regiao, o sufixo "- SC" do nome decide: Sul.
        item = _item_mcp(**dict(LUIZ_ALVES_SC, uf=None, regiao=None))
        self._montar(mock_deps, base_config, mocker, [item])

        ConcursoBot(base_config).executar()

        cards = self._cards(mock_deps)
        assert len(cards) == 1 and "⚠️" not in cards[0]
        gravado = self._gravacao(mock_deps)
        assert gravado["motivo_filtro"] == "sul"
        assert gravado["uf"] == "SC"

    def test_area_com_filtro_desligado_nao_filtra_nada(
        self, mock_deps, base_config, mocker
    ):
        itens = [_item_mcp(**SANTA_LUZIA_MG), _item_mcp(**GUARATINGUETA_SP),
                 _item_mcp(**SEM_LOCAL)]
        self._montar(mock_deps, base_config, mocker, itens, filtro=None)

        ConcursoBot(base_config).executar()

        cards = self._cards(mock_deps)
        assert len(cards) == 3
        assert all("NOVO CONCURSO" in c for c in cards)
        assert not any("⚠️" in c for c in cards)
        gravacoes = [c.kwargs for c in mock_deps["db"].atualizar_concurso.call_args_list]
        assert all(g["elegibilidade"] == "elegivel" for g in gravacoes)
        assert all(g["motivo_filtro"] == "filtro_desligado" for g in gravacoes)


# ---------------------------------------------------------------------------
# Resumo semanal dos filtrados (SPEC-001, secao 4.4)
# ---------------------------------------------------------------------------

# Linha como `listar_filtrados` devolve (SPEC-001, secao 3.5).
FILTRADO_SANTA_LUZIA = {
    "nome": "Prefeitura de Santa Luzia - MG", "uf": "MG",
    "salario_teto": 8628.87, "motivo_filtro": "abaixo_do_corte",
    "link": "https://www.pciconcursos.com.br/noticias/concurso-295546",
}

SEGUNDA = date(2026, 11, 23)        # semana ISO 2026-S48
SEXTA = date(2026, 11, 27)          # mesma semana
SEGUNDA_SEGUINTE = date(2026, 11, 30)  # semana ISO 2026-S49


class TestResumoSemanal:
    """Uma vez por semana por area, o que o filtro silenciou vira uma mensagem."""

    @staticmethod
    def _hoje(mocker, dia: date) -> None:
        """Dubla o relogio do bot: `date.today()` passa a devolver `dia`."""
        class _Data(date):
            @classmethod
            def today(cls):
                return cls(dia.year, dia.month, dia.day)

        mocker.patch("src.core.bot.date", _Data)

    def _montar(self, mock_deps, base_config, mocker, filtrados, resumo="semanal"):
        """Rodada saudavel: Gran vazio e a porta do MCP com um item do Sul."""
        mcp_cls = mocker.patch("src.core.bot.PciMcpScraper")
        mcp = mcp_cls.return_value
        mcp.url = URL_SERVIDOR
        mcp.capturar_concursos.return_value = [_item_mcp(**LUIZ_ALVES_SC)]

        mock_deps["scraper"].capturar_concursos.return_value = []
        mock_deps["notifier"].notificar.return_value = True
        mock_deps["notifier"].notificar_concurso.return_value = True
        mock_deps["db"].listar_filtrados.return_value = filtrados

        base_config["pci_mcp"] = True
        base_config["pci_mcp_cargos"] = ["analista de sistemas"]
        if resumo is not None:
            base_config["resumo_filtrados"] = resumo

    @staticmethod
    def _resumos(mock_deps):
        return [
            c.args[0] for c in mock_deps["notifier"].notificar.call_args_list
            if "Santa Luzia" in c.args[0]
        ]

    def test_resumo_semanal_sai_uma_vez_na_semana(
        self, mock_deps, base_config, mocker
    ):
        self._montar(mock_deps, base_config, mocker, [FILTRADO_SANTA_LUZIA])

        self._hoje(mocker, SEGUNDA)
        ConcursoBot(base_config).executar()
        ConcursoBot(base_config).executar()      # mesmo dia
        self._hoje(mocker, SEXTA)
        ConcursoBot(base_config).executar()      # outro dia, mesma semana

        resumos = self._resumos(mock_deps)
        assert len(resumos) == 1
        assert "abaixo do corte" in resumos[0]

    def test_resumo_semanal_volta_na_semana_seguinte(
        self, mock_deps, base_config, mocker
    ):
        self._montar(mock_deps, base_config, mocker, [FILTRADO_SANTA_LUZIA])

        self._hoje(mocker, SEGUNDA)
        ConcursoBot(base_config).executar()      # grava o marcador desta semana
        self._hoje(mocker, SEGUNDA_SEGUINTE)
        ConcursoBot(base_config).executar()

        assert len(self._resumos(mock_deps)) == 2

    def test_semana_sem_filtrados_nao_manda_nem_marca(
        self, mock_deps, base_config, mocker
    ):
        self._montar(mock_deps, base_config, mocker, [])
        self._hoje(mocker, SEGUNDA)

        ConcursoBot(base_config).executar()
        assert self._resumos(mock_deps) == []

        # Sem marcador, o primeiro filtrado da mesma semana ainda sai.
        mock_deps["db"].listar_filtrados.return_value = [FILTRADO_SANTA_LUZIA]
        ConcursoBot(base_config).executar()
        assert len(self._resumos(mock_deps)) == 1

    def test_resumo_desligado_nao_consulta_o_banco(
        self, mock_deps, base_config, mocker
    ):
        self._montar(mock_deps, base_config, mocker, [FILTRADO_SANTA_LUZIA], resumo=None)

        ConcursoBot(base_config).executar()

        mock_deps["db"].listar_filtrados.assert_not_called()
        assert self._resumos(mock_deps) == []

    def test_dry_run_nao_manda_resumo_nem_marca(self, mock_deps, base_config, mocker):
        self._montar(mock_deps, base_config, mocker, [FILTRADO_SANTA_LUZIA])
        self._hoje(mocker, SEGUNDA)

        ConcursoBot(dict(base_config, dry_run=True)).executar()
        mock_deps["notifier"].notificar.assert_not_called()

        # Sem marcador gravado no dry-run, a rodada real da mesma semana manda.
        ConcursoBot(base_config).executar()
        assert len(self._resumos(mock_deps)) == 1

    def test_falha_no_resumo_nao_derruba_a_rodada(
        self, mock_deps, base_config, mocker, caplog
    ):
        # Teto ilegivel vindo do banco faz o `montar` levantar.
        linha_quebrada = dict(FILTRADO_SANTA_LUZIA, salario_teto="8.628,87")
        self._montar(mock_deps, base_config, mocker, [linha_quebrada])

        bot = ConcursoBot(base_config)
        with caplog.at_level("ERROR"):
            bot.executar()

        assert bot.falhou is False
        assert any("resumo" in r.getMessage().lower() for r in caplog.records
                   if r.levelname == "ERROR")
        # A rodada fez o trabalho dela: o item do Sul saiu.
        assert len(mock_deps["notifier"].notificar_concurso.call_args_list) == 1

    def test_envio_do_resumo_que_falha_nao_marca_a_rodada_e_tenta_de_novo(
        self, mock_deps, base_config, mocker
    ):
        self._montar(mock_deps, base_config, mocker, [FILTRADO_SANTA_LUZIA])
        self._hoje(mocker, SEGUNDA)
        # O Telegram recusa so o resumo; o resto da rodada entrega.
        mock_deps["notifier"].notificar.side_effect = (
            lambda msg: "Santa Luzia" not in msg
        )

        bot = ConcursoBot(base_config)
        bot.executar()
        assert bot.falhou is False

        # Nao entregue, nao marca: a rodada seguinte da semana tenta de novo.
        mock_deps["notifier"].notificar.side_effect = None
        ConcursoBot(base_config).executar()
        assert len(self._resumos(mock_deps)) == 2   # a recusada e a entregue

    def test_o_resumo_semanal_pede_sete_dias_ao_banco(
        self, mock_deps, base_config, mocker
    ):
        """O argumento `desde` vai em UTC no formato AAAA-MM-DD HH:MM:SS, 7 dias atras."""
        self._montar(mock_deps, base_config, mocker, [FILTRADO_SANTA_LUZIA])
        self._hoje(mocker, SEGUNDA)

        class _Agora(datetime):
            @classmethod
            def now(cls, tz=None):
                assert tz == timezone.utc
                return cls(2026, 11, 23, 14, 30, 45, tzinfo=timezone.utc)

        mocker.patch("src.core.bot.datetime", _Agora)

        ConcursoBot(base_config).executar()

        # 2026-11-23 menos 7 dias = 2026-11-16 (calculado a mao).
        mock_deps["db"].listar_filtrados.assert_called_once_with("2026-11-16 14:30:45")
