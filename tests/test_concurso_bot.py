"""Testes de integracao para src/core/bot.py.

Foco no orquestrador — todos os subsistemas (scraper, IA, DB, notifier,
callback processor) sao substituidos por mocks para verificar o fluxo
de decisao por bloco.
"""
from datetime import date, timedelta

import pytest

from src.core.bot import ConcursoBot


@pytest.fixture
def mock_deps(mocker):
    """Substitui as dependencias do ConcursoBot antes da instanciacao."""
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

    def test_ignorar_block_is_skipped(self, mock_deps, base_config):
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>lixo</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {"ignorar": True}

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["db"].atualizar_concurso.assert_not_called()
        mock_deps["notifier"].notificar_concurso.assert_not_called()
        assert mock_deps["notifier"].notificar.call_count == 1

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

    def test_legacy_row_sem_hash_backfill_silencioso(self, mock_deps, base_config):
        """Linhas legadas (status_hash=NULL) sao SEMPRE backfilled sem notificar na 1a varredura."""
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "TRF1",
            # Texto completamente DIFERENTE do armazenado — mesmo assim nao notifica.
            "status": "reformulacao totalmente nova",
            "link": "https://example.com/trf1",
            "data_fim_inscricao": None,
        }
        mock_deps["db"].buscar_registro.return_value = {
            "id": 5, "area": "TI", "nome": "TRF1",
            "status": "texto armazenado ha 24h",
            "status_hash": None,  # legado
            "estado_usuario": "ativo", "data_fim_inscricao": None,
            "link": "https://example.com/trf1",
        }

        bot = ConcursoBot(base_config)
        bot.executar()

        # NAO chama analise (evita falsos positivos pos-migracao).
        mock_deps["ai"].analisar_mudanca.assert_not_called()
        # NAO notifica.
        mock_deps["notifier"].notificar_concurso.assert_not_called()
        # Backfill: faz update (preenche status_hash).
        mock_deps["db"].atualizar_concurso.assert_called_once()

    def test_hash_identico_skipa_sem_chamar_analise(self, mock_deps, base_config):
        """Corrige a repeticao: texto reformulado com mesmo fingerprint nao dispara."""
        from src.utils.text import status_fingerprint
        status_antigo = "Edital publicado"
        # Variacoes triviais: case, whitespace e pontuacao de borda.
        status_novo = "  EDITAL   publicado.  "
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "TRF1",
            "status": status_novo,
            "link": "https://example.com/trf1",
            "data_fim_inscricao": None,
        }
        mock_deps["db"].buscar_registro.return_value = {
            "id": 5, "area": "TI", "nome": "TRF1", "status": status_antigo,
            "status_hash": status_fingerprint(status_antigo),
            "estado_usuario": "ativo", "data_fim_inscricao": None,
            "link": "https://example.com/trf1",
        }

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["ai"].analisar_mudanca.assert_not_called()
        mock_deps["notifier"].notificar_concurso.assert_not_called()

    def test_hash_diferente_analise_ignore_atualiza_silencioso(
        self, mock_deps, base_config
    ):
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "TRF1",
            "status": "texto completamente diferente",
            "link": "https://example.com/trf1",
            "data_fim_inscricao": None,
        }
        mock_deps["db"].buscar_registro.return_value = {
            "id": 5, "area": "TI", "nome": "TRF1", "status": "outro texto",
            "status_hash": "old", "estado_usuario": "ativo",
            "data_fim_inscricao": None, "link": "https://example.com/trf1",
        }
        mock_deps["ai"].analisar_mudanca.return_value = None  # IGNORE

        bot = ConcursoBot(base_config)
        bot.executar()

        # Atualiza DB com hash novo, mas nao notifica.
        mock_deps["db"].atualizar_concurso.assert_called_once()
        mock_deps["notifier"].notificar_concurso.assert_not_called()

    def test_mudanca_relevante_notifica_quando_prazo_aberto(
        self, mock_deps, base_config
    ):
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "TRF1",
            "status": "banca definida",
            "link": "https://example.com/trf1",
            "data_fim_inscricao": _amanha(),
        }
        mock_deps["db"].buscar_registro.return_value = {
            "id": 5, "area": "TI", "nome": "TRF1", "status": "edital publicado",
            "status_hash": "old", "estado_usuario": "ativo",
            "data_fim_inscricao": _amanha(), "link": "https://example.com/trf1",
        }
        mock_deps["ai"].analisar_mudanca.return_value = "Banca CEBRASPE anunciada."
        mock_deps["db"].atualizar_concurso.return_value = 5

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["notifier"].notificar_concurso.assert_called_once()
        call = mock_deps["notifier"].notificar_concurso.call_args
        assert "ATUALIZA" in call.args[1]
        assert "Banca CEBRASPE anunciada" in call.args[1]

    def test_mudanca_relevante_pos_prazo_ativo_atualiza_silencioso(
        self, mock_deps, base_config
    ):
        """estado 'ativo' + prazo encerrado = atualiza DB mas nao notifica."""
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "TRF1",
            "status": "resultado publicado",
            "link": "https://example.com/trf1",
            "data_fim_inscricao": _ontem(),
        }
        mock_deps["db"].buscar_registro.return_value = {
            "id": 5, "area": "TI", "nome": "TRF1", "status": "antigo",
            "status_hash": "old", "estado_usuario": "ativo",
            "data_fim_inscricao": _ontem(), "link": "https://example.com/trf1",
        }
        mock_deps["ai"].analisar_mudanca.return_value = "Resultado publicado hoje."

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["db"].atualizar_concurso.assert_called_once()
        mock_deps["notifier"].notificar_concurso.assert_not_called()

    def test_mudanca_relevante_pos_prazo_seguindo_notifica(
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
        }
        mock_deps["db"].buscar_registro.return_value = {
            "id": 5, "area": "TI", "nome": "TRF1", "status": "antigo",
            "status_hash": "old", "estado_usuario": "seguindo",
            "data_fim_inscricao": _ontem(), "link": "https://example.com/trf1",
        }
        mock_deps["ai"].analisar_mudanca.return_value = "Resultado publicado."
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
