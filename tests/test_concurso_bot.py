"""Testes de integracao para src/core/bot.py.

Foco no orquestrador — todos os subsistemas (scraper, IA, DB, notifier)
sao substituidos por mocks para verificar o fluxo de decisao por bloco.
"""
import pytest

from src.core.bot import ConcursoBot


@pytest.fixture
def mock_deps(mocker):
    """Substitui as dependencias do ConcursoBot antes da instanciacao."""
    scraper_cls = mocker.patch("src.core.bot.GranScraper")
    db_cls = mocker.patch("src.core.bot.DatabaseManager")
    ai_cls = mocker.patch("src.core.bot.IntelligenceUnit")
    notifier_cls = mocker.patch("src.core.bot.TelegramNotifier")

    scraper = scraper_cls.return_value
    db = db_cls.return_value
    ai = ai_cls.return_value
    notifier = notifier_cls.return_value

    # Default: url sem alteracao (usado em mensagem "tudo na mesma")
    scraper.url = "https://example.com"

    return {"scraper": scraper, "db": db, "ai": ai, "notifier": notifier}


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


class TestExecutarFlow:
    def test_new_concurso_triggers_notification_and_db_insert(
        self, mock_deps, base_config, mocker
    ):
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "TRF1",
            "status": "edital publicado",
            "link": "https://example.com/trf1",
        }
        mock_deps["db"].buscar_status_antigo.return_value = None

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["notifier"].notificar.assert_called_once()
        msg = mock_deps["notifier"].notificar.call_args.args[0]
        assert "NOVO CONCURSO" in msg
        assert "TRF1" in msg
        mock_deps["db"].atualizar_concurso.assert_called_once_with(
            "TRF1",
            "edital publicado",
            "https://example.com/trf1",
            url_indice="https://example.com",
        )

    def test_ignorar_block_is_skipped(self, mock_deps, base_config):
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>lixo</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {"ignorar": True}

        bot = ConcursoBot(base_config)
        bot.executar()

        # Somente a mensagem de "varredura concluida" (nao teve novidades).
        mock_deps["db"].atualizar_concurso.assert_not_called()
        assert mock_deps["notifier"].notificar.call_count == 1
        msg = mock_deps["notifier"].notificar.call_args.args[0]
        assert "Varredura Conclu" in msg

    def test_unchanged_status_sends_no_update_notification(
        self, mock_deps, base_config
    ):
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "TRF1",
            "status": "mesmo status",
            "link": "https://example.com",
        }
        mock_deps["db"].buscar_status_antigo.return_value = "mesmo status"

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["db"].atualizar_concurso.assert_not_called()
        mock_deps["ai"].analisar_mudanca.assert_not_called()
        # So a mensagem de "varredura concluida"
        assert mock_deps["notifier"].notificar.call_count == 1

    def test_relevant_change_triggers_update_notification(
        self, mock_deps, base_config
    ):
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "TRF1",
            "status": "banca definida",
            "link": "https://example.com",
        }
        mock_deps["db"].buscar_status_antigo.return_value = "edital publicado"
        mock_deps["ai"].analisar_mudanca.return_value = "Banca CEBRASPE anunciada."

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["db"].atualizar_concurso.assert_called_once()
        mock_deps["notifier"].notificar.assert_called_once()
        msg = mock_deps["notifier"].notificar.call_args.args[0]
        assert "ATUALIZA" in msg
        assert "Banca CEBRASPE anunciada" in msg

    def test_irrelevant_change_skips_notification_and_db(
        self, mock_deps, base_config
    ):
        mock_deps["scraper"].capturar_concursos.return_value = ["<h3>bloco</h3>"]
        mock_deps["ai"].extrair_dados.return_value = {
            "ignorar": False,
            "nome": "TRF1",
            "status": "texto levemente reescrito",
            "link": "https://example.com",
        }
        mock_deps["db"].buscar_status_antigo.return_value = "texto original"
        mock_deps["ai"].analisar_mudanca.return_value = None

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["db"].atualizar_concurso.assert_not_called()
        # Apenas a mensagem final de "varredura concluida"
        assert mock_deps["notifier"].notificar.call_count == 1
        assert "Varredura Conclu" in mock_deps["notifier"].notificar.call_args.args[0]

    def test_keyword_prefilter_blocks_llm_call(self, mock_deps, base_config):
        base_config["keywords_include"] = ["concurso"]
        mock_deps["scraper"].capturar_concursos.return_value = [
            "<p>texto sem palavras relevantes</p>"
        ]

        bot = ConcursoBot(base_config)
        bot.executar()

        mock_deps["ai"].extrair_dados.assert_not_called()

    def test_mixed_cycle_novo_plus_unchanged(self, mock_deps, base_config):
        mock_deps["scraper"].capturar_concursos.return_value = [
            "<h3>b1</h3>", "<h3>b2</h3>"
        ]
        mock_deps["ai"].extrair_dados.side_effect = [
            {"ignorar": False, "nome": "NOVO", "status": "x", "link": ""},
            {"ignorar": False, "nome": "ANTIGO", "status": "y", "link": ""},
        ]
        mock_deps["db"].buscar_status_antigo.side_effect = [None, "y"]

        bot = ConcursoBot(base_config)
        bot.executar()

        # 1 notificacao de novo + 0 mensagem de "tudo na mesma" (porque teve novo)
        assert mock_deps["notifier"].notificar.call_count == 1
        assert "NOVO CONCURSO" in mock_deps["notifier"].notificar.call_args.args[0]
        # Apenas NOVO foi salvo
        mock_deps["db"].atualizar_concurso.assert_called_once()

    def test_scraper_exception_is_caught(self, mock_deps, base_config):
        mock_deps["scraper"].capturar_concursos.side_effect = RuntimeError("boom")

        bot = ConcursoBot(base_config)
        bot.executar()  # nao deve levantar
