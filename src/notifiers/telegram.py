"""Integracao com a API do Telegram para envio de alertas.

O notifier aceita um unico `chat_id` (legado) e/ou uma lista `chat_ids`
(multi-area). Os valores sao mesclados, vazios/duplicados sao removidos
preservando a ordem. Se o token ou a lista final estiver vazia, o envio
vira no-op e registra aviso — a varredura continua normalmente.

Mensagens de concurso vao com `InlineKeyboardMarkup` (botoes ⭐ Seguir /
❌ Nao tenho interesse), que retornam callback_query ao bot — processados
depois pelo TelegramCallbackProcessor.
"""
import json
import logging

import requests


class TelegramNotifier:
    """Envia mensagens HTML via Bot API do Telegram para N chat_ids."""

    def __init__(self, token: str, chat_id: str | None = None, chat_ids: list[str] | None = None):
        """Inicializa com token do bot e a lista final de destinatarios.

        Args:
            token: Token do bot (vazio → notificacoes desativadas).
            chat_id: Compatibilidade com modo single-area; concatenado em chat_ids.
            chat_ids: Lista de chat IDs alvos. Duplicados e vazios sao removidos.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.token = token
        ids = chat_ids[:] if chat_ids else []
        if chat_id:
            ids.append(chat_id)
        # Remove duplicados preservando ordem.
        self.chat_ids = list(dict.fromkeys([item for item in ids if item]))
        self.base_url = f"https://api.telegram.org/bot{token}/sendMessage"

    def notificar(self, mensagem: str, reply_markup: dict | None = None):
        """Envia a mensagem (HTML) para cada chat configurado.

        Erros de rede sao registrados mas nao levantados — uma falha em um
        chat nao bloqueia os demais, e o pipeline de scraping nao e
        interrompido por indisponibilidade do Telegram.

        Args:
            mensagem: Texto HTML da mensagem.
            reply_markup: Dict opcional com `InlineKeyboardMarkup` (botoes).
        """
        if not self.token or not self.chat_ids:
            self.logger.warning("⚠️ Telegram não configurado. Pulando notificação.")
            return

        for chat_id in self.chat_ids:
            payload = {
                "chat_id": chat_id,
                "text": mensagem,
                "parse_mode": "HTML" # Permite formatação em HTML como negrito, itálico, links, etc.
            }
            if reply_markup is not None:
                payload["reply_markup"] = json.dumps(reply_markup)

            try:
                response = requests.post(self.base_url, data=payload, timeout=25)
                response.raise_for_status()
                self.logger.info(f"✉️ Notificação enviada com sucesso para chat {chat_id}.")
            except Exception as e:
                self.logger.error(f"❌ Falha ao enviar notificação para chat {chat_id}: {e}")

    def notificar_concurso(self, id_interno: int, mensagem: str):
        """Envia uma notificacao de concurso com os botoes ⭐/❌.

        Args:
            id_interno: `id` da linha no banco — usado no callback_data para
                identificar o concurso no clique.
            mensagem: Texto HTML ja formatado.
        """
        reply_markup = {
            "inline_keyboard": [[
                {"text": "⭐ Seguir", "callback_data": f"estado:{id_interno}:seguindo"},
                {"text": "❌ Não tenho interesse", "callback_data": f"estado:{id_interno}:ignorado"},
            ]]
        }
        self.notificar(mensagem, reply_markup=reply_markup)
