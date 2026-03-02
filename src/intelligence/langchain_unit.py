from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

class IntelligenceUnit:
    def __init__(self, model_name="llama3"):
        """
        Inicializa o modelo Ollama e define a estratégia de análise.
        Certifique-se de que o Ollama está rodando localmente.
        """
        # 1. Configuração do Modelo (pode ser trocado por OpenAI futuramente)
        self.llm = OllamaLLM(model=model_name, temperature=0) # Temp 0 para ser mais objetivo

        # 2. Definição do Prompt (O "Cérebro" do bot)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """
            Você é um assistente especialista em concursos públicos de TI no Brasil.
            Sua missão é comparar dois textos de status de um concurso e decidir se houve uma atualização real e importante.

            Regras de Saída:
            - Se a mudança for significativa (Ex: edital publicado, banca escolhida, inscrições abertas, prova remarcada), 
              responda com um resumo de NO MÁXIMO 15 palavras para um alerta de Telegram.
            - Se a mudança for irrelevante (Ex: apenas mudou uma data de 'última atualização', mudou uma vírgula, 
              ou o sentido do texto continua exatamente o mesmo), responda APENAS a palavra: IGNORE
            """),
            ("human", "STATUS ANTERIOR: {antigo}\nSTATUS ATUAL: {novo}")
        ])

        # 3. Criação da Chain (Prompt -> LLM -> Parser de Texto)
        self.chain = self.prompt | self.llm | StrOutputParser()

    def analisar_mudanca(self, antigo: str, novo: str) -> str:
        """
        Processa a comparação e retorna o resumo da mudança ou None.
        """
        try:
            # Remove ruídos básicos de espaço antes de enviar para a IA
            if antigo.strip() == novo.strip():
                return None
            
            # Chama a IA para processar a lógica
            resultado = self.chain.invoke({"antigo": antigo, "novo": novo})
            
            # Limpa o resultado
            resposta = resultado.strip()
            
            if "IGNORE" in resposta.upper():
                return None
            
            return resposta
            
        except Exception as e:
            print(f"❌ Erro no processamento da IA: {e}")
            return f"Atualização detectada (IA offline): {novo[:50]}..."