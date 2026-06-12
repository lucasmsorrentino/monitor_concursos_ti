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
