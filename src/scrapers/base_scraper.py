from abc import ABC, abstractmethod
import requests

class BaseScraper(ABC):
    def __init__(self, url):
        self.url = url
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }

    @abstractmethod
    def capturar_concursos(self):
        """
        Este método deve ser implementado por todas as subclasses.
        Deve retornar uma lista de dicionários: [{'nome': ..., 'status': ..., 'link': ...}]
        """
        pass

    def get_html(self):
        """Método utilitário para buscar o HTML da página."""
        try:
            response = requests.get(self.url, headers=self.headers, timeout=15)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.text
        except Exception as e:
            print(f"❌ Erro ao acessar {self.url}: {e}")
            return None