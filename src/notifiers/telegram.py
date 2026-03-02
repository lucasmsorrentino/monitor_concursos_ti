import requests

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        """
        Inicializa o notificador com as credenciais do bot.
        """
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}/sendMessage"

    def notificar(self, mensagem: str):
        """
        Envia uma mensagem formatada em Markdown para o chat configurado.
        """
        if not self.token or not self.chat_id:
            print("⚠️ Telegram não configurado. Pulando notificação.")
            return

        payload = {
            "chat_id": self.chat_id,
            "text": mensagem,
            "parse_mode": "Markdown" # Permite negrito, itálico, etc.
        }

        try:
            response = requests.post(self.base_url, data=payload, timeout=10)
            response.raise_for_status()
            print("✉️ Notificação enviada com sucesso para o Telegram!")
        except Exception as e:
            print(f"❌ Falha ao enviar notificação para o Telegram: {e}")