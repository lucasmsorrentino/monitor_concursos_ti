from bs4 import BeautifulSoup
from .base_scraper import BaseScraper

class GranScraper(BaseScraper):
    def capturar_concursos(self):
        html = self.get_html()
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        lista_concursos = []

        # No blog do Gran Cursos TI, os concursos geralmente ficam em títulos H3
        # e o status logo no parágrafo abaixo.
        titulos = soup.find_all('h3')

        for titulo in titulos:
            nome_concurso = titulo.text.strip()
            
            # Filtro básico: ignorar títulos muito curtos ou irrelevantes
            if len(nome_concurso) < 5 or "CONCURSOS" in nome_concurso.upper():
                continue

            # Tenta pegar o status no parágrafo imediatamente seguinte
            proximo_p = titulo.find_next('p')
            status_texto = proximo_p.text.strip() if proximo_p else "Status não detalhado"

            # Limita o tamanho do texto do status para não sobrecarregar o banco/IA
            status_resumo = (status_texto[:300] + '...') if len(status_texto) > 300 else status_texto

            lista_concursos.append({
                "nome": nome_concurso,
                "status": status_resumo,
                "link": self.url # Poderíamos extrair o link específico se houver
            })

        print(f"✅ Scraper: {len(lista_concursos)} concursos encontrados no Gran Cursos.")
        return lista_concursos