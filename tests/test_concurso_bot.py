"""Testes de integracao para src/core/bot.py.

Foco no orquestrador — todos os subsistemas (scraper, IA, DB, notifier,
callback processor) sao substituidos por mocks para verificar o fluxo
de decisao por bloco.
"""
from datetime import date, timedelta

import pytest

from src.core.bot import ConcursoBot
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
