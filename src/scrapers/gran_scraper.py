"""Scraper especializado para o blog Gran Cursos Online.

Na arquite
tura AI-First, este módulo atua apenas como **Slicer** (fatiador):
ele usa o BeautifulSoup para dividir a página HTML em blocos independentes
delimitados por tags ``<h3>``, sem extrair textos ou links diretamente.
A interpretação semântica do conteúdo é delegada à ``IntelligenceUnit``.
"""

from bs4 import BeautifulSoup
from .base_scraper import BaseScraper


class GranScraper(BaseScraper):
    """Fatiador de HTML para o blog do Gran Cursos Online — seção Concursos TI.

    Herda de :class:`BaseScraper` e implementa ``capturar_concursos()``.
    Não realiza extração de dados; apenas recorta a página em blocos de HTML
    bruto para que a LLM os interprete.
    """

    def capturar_concursos(self) -> list[str]:
        """Fatia a página HTML em blocos independentes delimitados por ``<h3>``.

        Cada bloco contém o ``<h3>`` de um concurso e todos os elementos-irmãos
        seguintes até o próximo ``<h3>``, formando um trecho de HTML
        autocontido que será enviado à LLM para extração de dados.

        Returns:
            list[str]: Lista de strings HTML brutas, uma por bloco/concurso.
                       Retorna lista vazia se a página não puder ser obtida.
        """
        html = self.get_html()
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        chunks: list[str] = []
        titulos = soup.find_all('h3')

        for t in titulos:
            # Coleta o <h3> e todos os irmãos seguintes até o próximo <h3>
            conteudo_bloco = [str(t)]
            for irmao in t.find_next_siblings():
                if irmao.name == 'h3':
                    break
                conteudo_bloco.append(str(irmao))

            bloco_completo = "\n".join(conteudo_bloco)
            chunks.append(bloco_completo)

        return chunks
    
        #     nome_concurso = titulo.text.strip()
            
        #     # Filtro inteligente: ignora se estiver na blacklist ou for muito curto
        #     if any(termo in nome_concurso.upper() for termo in blacklist) or len(nome_concurso) < 10:
        #         continue
        #     # if len(nome_concurso) < 5 or "CONCURSOS" in nome_concurso.upper():
        #     #     continue

        #     # Tenta pegar o status no parágrafo imediatamente seguinte
        #     proximo_p = titulo.find_next('p')
        #     status_texto = proximo_p.text.strip() if proximo_p else "Status não detalhado"

        #     # Limita o tamanho do texto do status para não sobrecarregar o banco/IA
        #     status_resumo = (status_texto[:300] + '...') if len(status_texto) > 300 else status_texto


        #     # -----------------------------------
        #     # # --- CAPTURANDO O LINK ESPECÍFICO ---
        #     # # Procura se existe um link (tag 'a') dentro do H3 ou logo abaixo dele
        #     # link_elemento = titulo.find('a') 
            
        #     # # Se achou o 'a' e ele tem um 'href', nós o salvamos. Se não, usamos o geral.
        #     # if link_elemento and link_elemento.has_attr('href'):
        #     #     link_concurso = link_elemento['href']
        #     # else:
        #     #     link_concurso = self.url 
        #     # # ----------------------------------------------
            
        #     # --- BUSCA INTELIGENTE PELO LINK ---
        #     link_concurso = None
            
        #     # 1. Tenta achar o link DENTRO do título
        #     link_tag = titulo.find('a')
            
        #     # 2. Se não achou, tenta ver se o título está DENTRO de um link (pai)
        #     if not link_tag:
        #         link_tag = titulo.find_parent('a')
                
        #     # 3. Se ainda não achou, procura o primeiro link nos elementos irmãos (abaixo do título)
        #     if not link_tag:
        #         # Procura um link nos próximos elementos até encontrar um ou cansar
        #         proximo = titulo.find_next(['a', 'p'])
        #         if proximo.name == 'a':
        #             link_tag = proximo
        #         elif proximo.name == 'p':
        #             link_tag = proximo.find('a')

        #     # Atribui o link se encontrou, caso contrário usa a URL base
        #     if link_tag and link_tag.get('href'):
        #         link_concurso = link_tag.get('href')
                
        #         # Garante que o link seja absoluto (se vier apenas /noticia/...)
        #         if link_concurso.startswith('/'):
        #             link_concurso = "https://blog.grancursosonline.com.br" + link_concurso
        #     else:
        #         link_concurso = self.url
        #     # -----------------------------------


        #     lista_concursos.append({
        #         "nome": nome_concurso,
        #         "status": status_resumo,
        #         "link": link_concurso # envia o link específico!
        #     })

        # print(f"✅ Scraper: {len(lista_concursos)} concursos encontrados no Gran Cursos.")
        # return lista_concursos