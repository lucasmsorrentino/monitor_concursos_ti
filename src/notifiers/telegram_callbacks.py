"""Processador de callbacks do Telegram (botoes ⭐ Seguir / ❌ Ignorar).

Como o `main.py` e single-run (roda 1x/dia via Task Scheduler), o processamento
de cliques e feito em batch antes do scraping de cada varredura:

    GET getUpdates?offset=N → parse callback_query → UPDATE estado_usuario
      → answerCallbackQuery (feedback visual) → editMessageReplyMarkup (remove botoes)

O offset e persistido em `data/telegram_offset.json` para nao reprocessar
updates ja consumidos. Em qualquer erro de parse, o offset avanca mesmo assim —
evita loop infinito se algum update vier corrompido.
"""
import json
import logging
import os

import requests


_OFFSET_PATH_PADRAO = "data/telegram_offset.json"
_ESTADOS_VALIDOS = {"seguindo", "ignorado", "ativo"}


class TelegramCallbackProcessor:
    """Processa callback_queries pendentes em batch."""

    def __init__(
        self,
        token: str,
        db,
        offset_path: str = _OFFSET_PATH_PADRAO,
        session: requests.Session | None = None,
        timeout_s: float = 10.0,
    ):
        """Configura o processador.

        Args:
            token: Token do bot Telegram.
            db: Instancia de `DatabaseManager` — recebe `atualizar_estado_usuario`.
            offset_path: Caminho do arquivo JSON que guarda o offset entre runs.
            session: `requests.Session` injetavel (default: `requests.Session()`).
            timeout_s: Timeout das chamadas HTTP.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.token = token
        self.db = db
        self.offset_path = offset_path
        self.session = session or requests.Session()
        self.timeout_s = timeout_s
        self.base = f"https://api.telegram.org/bot{token}"

    def processar_pendentes(self) -> int:
        """Consome todos os callback_queries pendentes e aplica os estados.

        Returns:
            int: Quantidade de callbacks processados nesta rodada.
        """
        if not self.token:
            self.logger.warning("⚠️ Token Telegram ausente; callbacks nao serao processados.")
            return 0

        offset = self._carregar_offset()
        try:
            updates = self._get_updates(offset)
        except Exception as e:
            self.logger.error(f"❌ Falha ao consultar getUpdates: {e}")
            return 0

        processados = 0
        for update in updates:
            update_id = update.get("update_id")
            if update_id is None:
                continue

            callback = update.get("callback_query")
            if callback:
                try:
                    self._tratar_callback(callback)
                    processados += 1
                except Exception as e:
                    self.logger.warning(f"⚠️ Falha ao processar callback {update_id}: {e}")

            # Avanca offset independente de sucesso — evita loop.
            self._salvar_offset(update_id + 1)

        if processados:
            self.logger.info(f"✅ {processados} callback(s) do Telegram aplicados.")
        return processados

    def _tratar_callback(self, callback: dict) -> None:
        """Aplica um callback_query individual: parse → DB → feedback → limpa botoes."""
        callback_id = callback.get("id")
        data = callback.get("data", "")

        id_concurso, estado = self._parse_data(data)
        texto_feedback: str

        if id_concurso is None or estado is None:
            texto_feedback = "Comando invalido."
        else:
            ok = self.db.atualizar_estado_usuario(id_concurso, estado)
            if ok:
                texto_feedback = (
                    "Marcado como seguindo ⭐" if estado == "seguindo"
                    else "Nao sera mais notificado ❌"
                )
            else:
                texto_feedback = "Concurso nao encontrado."

        # Feedback visual (popup no cliente do usuario).
        if callback_id:
            try:
                self.session.post(
                    f"{self.base}/answerCallbackQuery",
                    data={"callback_query_id": callback_id, "text": texto_feedback},
                    timeout=self.timeout_s,
                )
            except Exception as e:
                self.logger.debug(f"answerCallbackQuery falhou: {e}")

        # Remove os botoes da mensagem original para evitar cliques repetidos.
        message = callback.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")
        if chat_id and message_id:
            try:
                self.session.post(
                    f"{self.base}/editMessageReplyMarkup",
                    data={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "reply_markup": json.dumps({"inline_keyboard": []}),
                    },
                    timeout=self.timeout_s,
                )
            except Exception as e:
                self.logger.debug(f"editMessageReplyMarkup falhou: {e}")

    @staticmethod
    def _parse_data(data: str) -> tuple[int | None, str | None]:
        """Extrai (id, estado) de uma callback_data no formato `estado:<id>:<estado>`."""
        if not data or not isinstance(data, str):
            return None, None
        partes = data.split(":")
        if len(partes) != 3 or partes[0] != "estado":
            return None, None
        try:
            id_ = int(partes[1])
        except ValueError:
            return None, None
        estado = partes[2]
        if estado not in _ESTADOS_VALIDOS:
            return None, None
        return id_, estado

    def _get_updates(self, offset: int) -> list[dict]:
        """Chama `getUpdates` restrito a callback_query, short-poll."""
        params = {
            "offset": offset,
            "timeout": 0,
            "allowed_updates": json.dumps(["callback_query"]),
        }
        resp = self.session.get(f"{self.base}/getUpdates", params=params, timeout=self.timeout_s)
        resp.raise_for_status()
        body = resp.json()
        if not body.get("ok"):
            raise RuntimeError(f"getUpdates retornou erro: {body}")
        return body.get("result", []) or []

    def _carregar_offset(self) -> int:
        if not os.path.exists(self.offset_path):
            return 0
        try:
            with open(self.offset_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            valor = int(data.get("offset", 0))
            return max(0, valor)
        except Exception as e:
            self.logger.warning(f"⚠️ Offset corrompido em {self.offset_path}; resetando para 0. {e}")
            return 0

    def _salvar_offset(self, offset: int) -> None:
        os.makedirs(os.path.dirname(self.offset_path) or ".", exist_ok=True)
        try:
            with open(self.offset_path, "w", encoding="utf-8") as f:
                json.dump({"offset": int(offset)}, f)
        except Exception as e:
            self.logger.warning(f"⚠️ Falha ao persistir offset: {e}")
