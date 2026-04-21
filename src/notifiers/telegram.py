"""Integracao com a API do Telegram para envio de alertas.

O notifier aceita um unico `chat_id` (legado) e/ou uma lista `chat_ids`
(multi-area). Os valores sao mesclados, vazios/duplicados sao removidos
preservando a ordem. Se o token ou a lista final estiver vazia, o envio
vira no-op e registra aviso — a varredura continua normalmente.
"""
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
        self.token = token
        ids = chat_ids[:] if chat_ids else []
        if chat_id:
            ids.append(chat_id)
        # Remove duplicados preservando ordem.
        self.chat_ids = list(dict.fromkeys([item for item in ids if item]))
        self.base_url = f"https://api.telegram.org/bot{token}/sendMessage"

    def notificar(self, mensagem: str):
        """Envia a mensagem (HTML) para cada chat configurado.

        Erros de rede sao registrados mas nao levantados — uma falha em um
        chat nao bloqueia os demais, e o pipeline de scraping nao e
        interrompido por indisponibilidade do Telegram.
        """
        if not self.token or not self.chat_ids:
            print("⚠️ Telegram não configurado. Pulando notificação.")
            return

        for chat_id in self.chat_ids:
            payload = {
                "chat_id": chat_id,
                "text": mensagem,
                "parse_mode": "HTML" # Permite formatação em HTML como negrito, itálico, links, etc.
            }

            try:
                response = requests.post(self.base_url, data=payload, timeout=10)
                response.raise_for_status()
                print(f"✉️ Notificação enviada com sucesso para chat {chat_id}.")
            except Exception as e:
                print(f"❌ Falha ao enviar notificação para chat {chat_id}: {e}")