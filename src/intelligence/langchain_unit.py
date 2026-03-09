import json
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

class IntelligenceUnit:
    def __init__(self, model_name="llama3.1"):
        # 1. LLM para Extração de Dados (Forçando saída em JSON estrito)
        self.llm_json = OllamaLLM(model=model_name, temperature=0, format="json")
        
        # 2. LLM para Análise de Mudanças (Saída em Texto normal)
        self.llm_text = OllamaLLM(model=model_name, temperature=0)

        # --- PROMPT 1: EXTRAÇÃO (HTML -> JSON) ---
        self.prompt_extracao = ChatPromptTemplate.from_messages([
            ("system", """
            Você é um extrator de dados de alta precisão. Analise o bloco de HTML de um blog de concursos.
            
            REGRAS:
            1. Se o bloco for apenas uma lista genérica (ex: apenas nomes de cidades/cargos sem explicações) ou for "Notícias Recomendadas", responda: {{"ignorar": true}}
            2. Se for uma notícia de concurso real, extraia as informações.
            3. O link deve ser a URL do edital ou da notícia detalhada (procure em tags <a>).
            4. Responda APENAS com JSON válido:
            {{
                "ignorar": false,
                "nome": "Nome do Concurso ou Órgão",
                "status": "Resumo do status atual em até 2 frases",
                "link": "https://..."
            }}
            """),
            ("human", "Analise este HTML:\n{bloco}")
        ])
        self.chain_extracao = self.prompt_extracao | self.llm_json | StrOutputParser()

        # --- PROMPT 2: ANÁLISE DE MUDANÇA (Texto -> Texto) ---
        self.prompt_analise = ChatPromptTemplate.from_messages([
            ("system", """
            Você é um assistente especialista em concursos públicos.
            Compare o STATUS ANTERIOR com o STATUS ATUAL para ver se houve avanço real.

            Regras:
            - Se a mudança for relevante (ex: edital publicado, banca escolhida, inscrições abertas), faça um resumo de NO MÁXIMO 15 palavras.
            - Se for irrelevante (ex: apenas reescrita, mesma informação, erro de digitação corrigido), responda APENAS a palavra: IGNORE
            """),
            ("human", "STATUS ANTERIOR: {antigo}\nSTATUS ATUAL: {novo}")
        ])
        self.chain_analise = self.prompt_analise | self.llm_text | StrOutputParser()


    def extrair_dados(self, bloco_html: str) -> dict:
        """Lê um bloco de HTML e retorna um dicionário JSON limpo."""
        try:
            resposta = self.chain_extracao.invoke({"bloco": bloco_html})
            dados = json.loads(resposta)
            return dados
        except Exception as e:
            print(f"❌ Erro na extração via IA: {e}")
            # Se a IA falhar ou o JSON vier quebrado, mandamos ignorar por segurança
            return {"ignorar": True}


    def analisar_mudanca(self, antigo: str, novo: str) -> str:
        """Compara dois textos e decide se a mudança vale a pena ser notificada."""
        try:
            if antigo.strip() == novo.strip():
                return None
            
            resultado = self.chain_analise.invoke({"antigo": antigo, "novo": novo})
            resposta = resultado.strip()
            
            if "IGNORE" in resposta.upper():
                return None
            
            return resposta
            
        except Exception as e:
            print(f"❌ Erro na análise de mudança via IA: {e}")
            return None

# import json
# from langchain_ollama import OllamaLLM
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.output_parsers import StrOutputParser


# class IntelligenceUnit:
#     def __init__(self, model_name="llama3.1"):
#         self.llm = OllamaLLM(model=model_name, temperature=0, format="json") # Forçamos saída JSON

#         self.prompt = ChatPromptTemplate.from_messages([
#             ("system", """
#             Você é um extrator de dados de alta precisão. Sua tarefa é analisar um bloco de HTML de um blog de concursos e extrair informações.

#             REGRAS CRÍTICAS:
#             1. Se o bloco for apenas uma lista resumida (ex: apenas nomes de cidades ou cargos sem link de detalhes), responda: {{"ignorar": true}}
#             2. Se o bloco for uma notícia detalhada, extraia o Nome do Órgão, o Status Atual e a URL do link 'Saiba Mais'.
#             3. Responda APENAS com JSON no formato:
#             {{
#                 "ignorar": false,
#                 "nome": "Nome do Concurso",
#                 "status": "Resumo do status atual",
#                 "link": "URL completa do link saiba mais"
#             }}
#             """),
#             ("human", "Analise este bloco: {bloco}")
#         ])
#         self.chain = self.prompt | self.llm

#     def extrair_dados(self, bloco_html: str) -> dict:
#         try:
#             # O Llama 3.1 vai ler o HTML e entender onde está o link dinamicamente
#             resposta = self.chain.invoke({"bloco": bloco_html})
#             dados = json.loads(resposta)
#             return dados
#         except Exception as e:
#             return {"ignorar": True}
# class IntelligenceUnit:
#     def __init__(self, model_name="llama3.1"):
#         """
#         Inicializa o modelo Ollama e define a estratégia de análise.
#         Certifique-se de que o Ollama está rodando localmente.
#         """
#         # 1. Configuração do Modelo (pode ser trocado por OpenAI futuramente)
#         self.llm = OllamaLLM(model=model_name, temperature=0) # Temp 0 para ser mais objetivo

#         # 2. Definição do Prompt (O "Cérebro" do bot)
#         self.prompt = ChatPromptTemplate.from_messages([
#             ("system", """
#             Você é um assistente especialista em concursos públicos de TI no Brasil.
#             Sua missão é comparar dois textos de status de um concurso e decidir se houve uma atualização real e importante.

#             Regras de Saída:
#             - Se a mudança for significativa (Ex: edital publicado, banca escolhida, inscrições abertas, prova remarcada), 
#               responda com um resumo de NO MÁXIMO 15 palavras para um alerta de Telegram.
#             - Se a mudança for irrelevante (Ex: apenas mudou uma data de 'última atualização', mudou uma vírgula, 
#               ou o sentido do texto continua exatamente o mesmo), responda APENAS a palavra: IGNORE
#             """),
#             ("human", "STATUS ANTERIOR: {antigo}\nSTATUS ATUAL: {novo}")
#         ])

#         # 3. Criação da Chain (Prompt -> LLM -> Parser de Texto)
#         self.chain = self.prompt | self.llm | StrOutputParser()

#     def analisar_mudanca(self, antigo: str, novo: str) -> str:
#         """
#         Processa a comparação e retorna o resumo da mudança ou None.
#         """
#         try:
#             # Remove ruídos básicos de espaço antes de enviar para a IA
#             if antigo.strip() == novo.strip():
#                 return None
            
#             # Chama a IA para processar a lógica
#             resultado = self.chain.invoke({"antigo": antigo, "novo": novo})
            
#             # Limpa o resultado
#             resposta = resultado.strip()
            
#             if "IGNORE" in resposta.upper():
#                 return None
            
#             return resposta
            
#         except Exception as e:
#             print(f"❌ Erro no processamento da IA: {e}")
#             # IMPORTANTE: Se a IA falhar, retornamos None para o bot NÃO postar lixo
#             print(f"❌ Erro no Ollama: {e}")
#             return None