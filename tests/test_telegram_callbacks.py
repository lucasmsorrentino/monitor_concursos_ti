"""Testes para src/notifiers/telegram_callbacks.py."""
import json

import pytest

from src.notifiers.telegram_callbacks import TelegramCallbackProcessor


@pytest.fixture
def offset_path(tmp_path):
    return str(tmp_path / "offset.json")


@pytest.fixture
def db_mock(mocker):
    db = mocker.MagicMock()
    db.atualizar_estado_usuario.return_value = True
    return db


@pytest.fixture
def session_mock(mocker):
    session = mocker.MagicMock()
    return session


def _make_update(update_id: int, callback_data: str, chat_id: int = 111, msg_id: int = 42) -> dict:
    return {
        "update_id": update_id,
        "callback_query": {
            "id": f"cb{update_id}",
            "data": callback_data,
            "message": {"chat": {"id": chat_id}, "message_id": msg_id},
        },
    }


def _mock_get_updates_response(session_mock, mocker, updates: list[dict]):
    resp = mocker.MagicMock()
    resp.raise_for_status = mocker.MagicMock()
    resp.json.return_value = {"ok": True, "result": updates}
    session_mock.get.return_value = resp


class TestParseData:
    def test_formato_valido(self):
        assert TelegramCallbackProcessor._parse_data("estado:42:seguindo") == (42, "seguindo")

    def test_formato_invalido_prefix(self):
        assert TelegramCallbackProcessor._parse_data("acao:42:seguindo") == (None, None)

    def test_id_nao_numerico(self):
        assert TelegramCallbackProcessor._parse_data("estado:abc:seguindo") == (None, None)

    def test_estado_invalido(self):
        assert TelegramCallbackProcessor._parse_data("estado:42:deletar") == (None, None)

    def test_string_vazia(self):
        assert TelegramCallbackProcessor._parse_data("") == (None, None)

    def test_partes_faltando(self):
        assert TelegramCallbackProcessor._parse_data("estado:42") == (None, None)


class TestProcessarPendentes:
    def test_no_token_retorna_zero(self, db_mock, offset_path):
        proc = TelegramCallbackProcessor("", db_mock, offset_path=offset_path)
        assert proc.processar_pendentes() == 0

    def test_aplica_callback_valido_ao_db(self, db_mock, session_mock, offset_path, mocker):
        _mock_get_updates_response(
            session_mock, mocker, [_make_update(100, "estado:7:seguindo")]
        )
        session_mock.post.return_value = mocker.MagicMock(raise_for_status=mocker.MagicMock())

        proc = TelegramCallbackProcessor(
            "TOKEN", db_mock, offset_path=offset_path, session=session_mock
        )
        assert proc.processar_pendentes() == 1
        db_mock.atualizar_estado_usuario.assert_called_once_with(7, "seguindo")

    def test_offset_avanca_para_update_id_mais_um(
        self, db_mock, session_mock, offset_path, mocker
    ):
        _mock_get_updates_response(
            session_mock, mocker, [_make_update(100, "estado:7:ignorado")]
        )
        session_mock.post.return_value = mocker.MagicMock(raise_for_status=mocker.MagicMock())

        proc = TelegramCallbackProcessor(
            "TOKEN", db_mock, offset_path=offset_path, session=session_mock
        )
        proc.processar_pendentes()

        with open(offset_path, "r") as f:
            assert json.load(f)["offset"] == 101

    def test_answer_callback_e_edit_markup_chamados(
        self, db_mock, session_mock, offset_path, mocker
    ):
        _mock_get_updates_response(
            session_mock, mocker, [_make_update(50, "estado:7:seguindo")]
        )
        session_mock.post.return_value = mocker.MagicMock(raise_for_status=mocker.MagicMock())

        proc = TelegramCallbackProcessor(
            "TOKEN", db_mock, offset_path=offset_path, session=session_mock
        )
        proc.processar_pendentes()

        urls_chamadas = [call.args[0] for call in session_mock.post.call_args_list]
        assert any("answerCallbackQuery" in u for u in urls_chamadas)
        assert any("editMessageReplyMarkup" in u for u in urls_chamadas)

    def test_callback_invalido_avanca_offset_sem_chamar_db(
        self, db_mock, session_mock, offset_path, mocker
    ):
        _mock_get_updates_response(
            session_mock, mocker, [_make_update(200, "lixo")]
        )
        session_mock.post.return_value = mocker.MagicMock(raise_for_status=mocker.MagicMock())

        proc = TelegramCallbackProcessor(
            "TOKEN", db_mock, offset_path=offset_path, session=session_mock
        )
        proc.processar_pendentes()

        db_mock.atualizar_estado_usuario.assert_not_called()
        # Offset deve ter avancado para evitar loop infinito.
        with open(offset_path, "r") as f:
            assert json.load(f)["offset"] == 201

    def test_get_updates_falha_nao_levanta(
        self, db_mock, session_mock, offset_path
    ):
        session_mock.get.side_effect = RuntimeError("network down")

        proc = TelegramCallbackProcessor(
            "TOKEN", db_mock, offset_path=offset_path, session=session_mock
        )
        assert proc.processar_pendentes() == 0  # nao levanta

    def test_offset_corrompido_resetado_para_zero(
        self, db_mock, session_mock, offset_path, mocker
    ):
        with open(offset_path, "w") as f:
            f.write("lixo nao json")
        _mock_get_updates_response(session_mock, mocker, [])

        proc = TelegramCallbackProcessor(
            "TOKEN", db_mock, offset_path=offset_path, session=session_mock
        )
        proc.processar_pendentes()

        # Offset passado para getUpdates deve ser 0.
        params = session_mock.get.call_args.kwargs["params"]
        assert params["offset"] == 0

    def test_multiplos_callbacks_processados_em_sequencia(
        self, db_mock, session_mock, offset_path, mocker
    ):
        _mock_get_updates_response(
            session_mock, mocker,
            [
                _make_update(10, "estado:1:seguindo"),
                _make_update(11, "estado:2:ignorado"),
            ],
        )
        session_mock.post.return_value = mocker.MagicMock(raise_for_status=mocker.MagicMock())

        proc = TelegramCallbackProcessor(
            "TOKEN", db_mock, offset_path=offset_path, session=session_mock
        )
        assert proc.processar_pendentes() == 2
        assert db_mock.atualizar_estado_usuario.call_count == 2
