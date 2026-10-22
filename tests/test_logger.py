"""Testes para src/utils/logger.py — o token do Telegram nunca chega ao log."""
import logging
import sys

import requests

from src.utils.logger import FormatterSemSegredos, ocultar_segredos

# Formato real de token (id numerico + 35 caracteres), mas inventado.
TOKEN = "1234567890:AAF0aaaaBBBBccccDDDDeeeeFFFFgggg_-x"


class TestOcultarSegredos:
    def test_token_dentro_da_url_da_bot_api(self):
        """Caso real de 25/09/2026: o id vem colado em "bot", sem fronteira."""
        texto = (
            "Max retries exceeded with url: "
            f"/bot{TOKEN}/sendMessage (Caused by NameResolutionError(...))"
        )

        limpo = ocultar_segredos(texto)

        assert TOKEN not in limpo
        assert "/bot<token-telegram>/sendMessage" in limpo

    def test_nao_mexe_em_hora_nem_em_texto_comum(self):
        texto = "[2026-09-25 00:22:55] chat 8683596338 recebeu 3 mensagens"
        assert ocultar_segredos(texto) == texto


class TestFormatterSemSegredos:
    def _formatar(self, record):
        return FormatterSemSegredos("%(message)s").format(record)

    def test_limpa_a_mensagem(self):
        record = logging.LogRecord(
            "x", logging.WARNING, __file__, 1, "falha: %s", (f"/bot{TOKEN}/x",), None
        )
        assert TOKEN not in self._formatar(record)

    def test_limpa_o_traceback_do_exc_info(self):
        try:
            raise requests.ConnectionError(f"url: /bot{TOKEN}/sendMessage")
        except requests.ConnectionError:
            record = logging.LogRecord(
                "x", logging.ERROR, __file__, 1, "erro critico", (), sys.exc_info()
            )

        saida = self._formatar(record)

        assert "ConnectionError" in saida
        assert TOKEN not in saida
