"""Testes para src/notifiers/telegram.py."""
import requests

from src.notifiers.telegram import TelegramNotifier


class TestInit:
    def test_merges_chat_ids_list_and_single(self):
        n = TelegramNotifier("TOKEN", chat_id="extra", chat_ids=["111", "222"])
        assert n.chat_ids == ["111", "222", "extra"]

    def test_dedupes_preserving_order(self):
        n = TelegramNotifier("TOKEN", chat_id="111", chat_ids=["111", "222"])
        assert n.chat_ids == ["111", "222"]

    def test_drops_empty_entries(self):
        n = TelegramNotifier("TOKEN", chat_id=None, chat_ids=["", "111", None])
        assert n.chat_ids == ["111"]

    def test_builds_base_url(self):
        n = TelegramNotifier("TOKEN_XYZ")
        assert n.base_url == "https://api.telegram.org/botTOKEN_XYZ/sendMessage"


class TestNotificar:
    def test_noop_when_token_missing(self, mocker):
        post = mocker.patch("src.notifiers.telegram.requests.post")
        n = TelegramNotifier("", chat_ids=["111"])

        n.notificar("ola")

        post.assert_not_called()

    def test_noop_when_no_chat_ids(self, mocker):
        post = mocker.patch("src.notifiers.telegram.requests.post")
        n = TelegramNotifier("TOKEN")

        n.notificar("ola")

        post.assert_not_called()

    def test_sends_to_each_chat_id(self, mocker):
        post = mocker.patch("src.notifiers.telegram.requests.post")
        post.return_value.raise_for_status = mocker.MagicMock()
        n = TelegramNotifier("TOKEN", chat_ids=["111", "222"])

        n.notificar("mensagem")

        assert post.call_count == 2
        payloads = [call.kwargs["data"] for call in post.call_args_list]
        assert payloads[0]["chat_id"] == "111"
        assert payloads[1]["chat_id"] == "222"
        assert all(p["text"] == "mensagem" for p in payloads)
        assert all(p["parse_mode"] == "HTML" for p in payloads)

    def test_posts_to_correct_url(self, mocker):
        post = mocker.patch("src.notifiers.telegram.requests.post")
        post.return_value.raise_for_status = mocker.MagicMock()
        n = TelegramNotifier("TOKEN_XYZ", chat_ids=["111"])

        n.notificar("ola")

        args, kwargs = post.call_args
        assert args[0] == "https://api.telegram.org/botTOKEN_XYZ/sendMessage"
        assert kwargs["timeout"] == 25

    def test_http_error_is_caught_not_raised(self, mocker):
        post = mocker.patch("src.notifiers.telegram.requests.post")
        post.return_value.raise_for_status.side_effect = requests.HTTPError("boom")
        n = TelegramNotifier("TOKEN", chat_ids=["111"])

        n.notificar("ola")  # nao deve levantar

    def test_error_in_one_chat_does_not_block_next(self, mocker):
        post = mocker.patch("src.notifiers.telegram.requests.post")
        call_side_effects = [
            requests.ConnectionError("first fails"),
            mocker.MagicMock(raise_for_status=mocker.MagicMock()),
        ]
        post.side_effect = call_side_effects
        n = TelegramNotifier("TOKEN", chat_ids=["111", "222"])

        n.notificar("ola")

        assert post.call_count == 2


class TestNotificarConcurso:
    def test_inclui_reply_markup_com_dois_botoes(self, mocker):
        import json as _json
        post = mocker.patch("src.notifiers.telegram.requests.post")
        post.return_value.raise_for_status = mocker.MagicMock()
        n = TelegramNotifier("TOKEN", chat_ids=["111"])

        n.notificar_concurso(42, "<b>novo concurso</b>")

        payload = post.call_args.kwargs["data"]
        assert "reply_markup" in payload
        markup = _json.loads(payload["reply_markup"])
        botoes = markup["inline_keyboard"][0]
        assert len(botoes) == 2
        assert botoes[0]["callback_data"] == "estado:42:seguindo"
        assert botoes[1]["callback_data"] == "estado:42:ignorado"

    def test_reply_markup_ausente_quando_nao_passado(self, mocker):
        post = mocker.patch("src.notifiers.telegram.requests.post")
        post.return_value.raise_for_status = mocker.MagicMock()
        n = TelegramNotifier("TOKEN", chat_ids=["111"])

        n.notificar("mensagem simples")

        assert "reply_markup" not in post.call_args.kwargs["data"]
