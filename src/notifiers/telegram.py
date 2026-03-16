import requests

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str | None = None, chat_ids: list[str] | None = None):
        """
        Inicializa o notificador com as credenciais do bot.
        """
        self.token = token
        ids = chat_ids[:] if chat_ids else []
        if chat_id:
            ids.append(chat_id)
        # Remove duplicados preservando ordem.
        self.chat_ids = list(dict.fromkeys([item for item in ids if item]))
        self.base_url = f"https://api.telegram.org/bot{token}/sendMessage"

    def notificar(self, mensagem: str):
        """
        Envia uma mensagem formatada em HTML para o(s) chat(s) configurado(s).
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