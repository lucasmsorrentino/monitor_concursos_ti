"""Integracao com a API do Telegram para envio de alertas.

O notifier aceita um unico `chat_id` (legado) e/ou uma lista `chat_ids`
(multi-area). Os valores sao mesclados, vazios/duplicados sao removidos
preservando a ordem. Se o token ou a lista final estiver vazia, o envio
vira no-op e registra aviso — a varredura continua normalmente.

Mensagens de concurso vao com `InlineKeyboardMarkup` (botoes ⭐ Seguir /
❌ Nao tenho interesse), que retornam callback_query ao bot — processados
depois pelo TelegramCallbackProcessor.

Throttle e retry (08/2026): ate entao o envio era um POST solteiro por
mensagem, sem pausa, sem tratar 429, e a falha era engolida. Isso passava
despercebido com 3 mensagens por dia, mas a entrada do PCI trouxe cargas de
dezenas de mensagens de uma vez, e a Bot API limita a cerca de 1 mensagem por
segundo por chat. Sem throttle, boa parte da primeira carga sumiria em
silencio — o pior modo de falha possivel pra um bot cuja funcao e avisar.
"""
import json
import logging
import time

import requests

# A Bot API tolera ~1 msg/s por chat. 1.1s da folga sem tornar a carga lenta
# demais: 60 mensagens saem em pouco mais de um minuto.
INTERVALO_MIN_S = 1.1
TENTATIVAS = 3
BACKOFF_BASE_S = 2.0


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
        # Ultimo instante de envio por chat, para espacar as mensagens.
        self._ultimo_envio: dict[str, float] = {}

    def notificar(self, mensagem: str, reply_markup: dict | None = None) -> bool:
        """Envia a mensagem (HTML) para cada chat configurado.

        Erros de rede sao registrados mas nao levantados — uma falha em um
        chat nao bloqueia os demais, e o pipeline de scraping nao e
        interrompido por indisponibilidade do Telegram.

        Args:
            mensagem: Texto HTML da mensagem.
            reply_markup: Dict opcional com `InlineKeyboardMarkup` (botoes).

        Returns:
            bool: True se TODOS os destinatarios receberam.
        """
        if not self.token or not self.chat_ids:
            self.logger.warning("⚠️ Telegram não configurado. Pulando notificação.")
            return False

        todos_ok = True
        for chat_id in self.chat_ids:
            payload = {
                "chat_id": chat_id,
                "text": mensagem,
                "parse_mode": "HTML" # Permite formatação em HTML como negrito, itálico, links, etc.
            }
            if reply_markup is not None:
                payload["reply_markup"] = json.dumps(reply_markup)

            todos_ok &= self._enviar_com_retry(chat_id, payload)

        return todos_ok

    def _enviar_com_retry(self, chat_id: str, payload: dict) -> bool:
        """Envia um payload respeitando o intervalo minimo e tratando 429."""
        for tentativa in range(1, TENTATIVAS + 1):
            self._aguardar_vez(chat_id)
            try:
                response = requests.post(self.base_url, data=payload, timeout=25)
                self._ultimo_envio[chat_id] = time.monotonic()

                if response.status_code == 429:
                    espera = self._retry_after(response, tentativa)
                    self.logger.warning(
                        f"⏳ Telegram pediu calma (429) no chat {chat_id}; "
                        f"aguardando {espera:.0f}s (tentativa {tentativa}/{TENTATIVAS})."
                    )
                    time.sleep(espera)
                    continue

                response.raise_for_status()
                self.logger.info(f"✉️ Notificação enviada com sucesso para chat {chat_id}.")
                return True

            except Exception as e:
                self._ultimo_envio[chat_id] = time.monotonic()
                if tentativa == TENTATIVAS:
                    break
                espera = BACKOFF_BASE_S * (2 ** (tentativa - 1))
                self.logger.warning(
                    f"⚠️ Falha ao enviar para chat {chat_id} "
                    f"(tentativa {tentativa}/{TENTATIVAS}): {e}. Retentando em {espera:.0f}s."
                )
                time.sleep(espera)

        # error, e nao debug: mensagem perdida e exatamente o que o bot existe
        # pra evitar. Tem que aparecer no log e contar como falha da varredura.
        self.logger.error(
            f"❌ Notificação NAO entregue ao chat {chat_id} após {TENTATIVAS} tentativas."
        )
        return False

    def _aguardar_vez(self, chat_id: str) -> None:
        """Espaca os envios do mesmo chat em pelo menos INTERVALO_MIN_S."""
        ultimo = self._ultimo_envio.get(chat_id)
        if ultimo is None:
            return
        restante = INTERVALO_MIN_S - (time.monotonic() - ultimo)
        if restante > 0:
            time.sleep(restante)

    @staticmethod
    def _retry_after(response, tentativa: int) -> float:
        """Le o `retry_after` que o Telegram manda no 429; cai no backoff se ausente."""
        try:
            corpo = response.json()
            valor = (corpo.get("parameters") or {}).get("retry_after")
            if valor:
                return float(valor) + 0.5
        except Exception:
            pass
        return BACKOFF_BASE_S * (2 ** (tentativa - 1))

    def notificar_concurso(self, id_interno: int, mensagem: str) -> bool:
        """Envia uma notificacao de concurso com os botoes ⭐/❌.

        Args:
            id_interno: `id` da linha no banco — usado no callback_data para
                identificar o concurso no clique.
            mensagem: Texto HTML ja formatado.

        Returns:
            bool: True se todos os destinatarios receberam.
        """
        reply_markup = {
            "inline_keyboard": [[
                {"text": "⭐ Seguir", "callback_data": f"estado:{id_interno}:seguindo"},
                {"text": "❌ Não tenho interesse", "callback_data": f"estado:{id_interno}:ignorado"},
            ]]
        }
        return self.notificar(mensagem, reply_markup=reply_markup)
