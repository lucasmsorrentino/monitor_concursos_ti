"""Módulo de inteligência artificial — cérebro duplo do sistema.

Contém a classe :class:`IntelligenceUnit`, que expõe duas chains LangChain
operando sobre uma LLM local (Ollama):

1. **Chain de Extração** (HTML → JSON): recebe um bloco de HTML bruto e
   devolve um dicionário estruturado com ``nome``, ``status``, ``link`` e
   uma flag ``ignorar``.
2. **Chain de Análise** (Texto → Texto): compara dois textos de status e
   decide se a mudança é relevante o suficiente para gerar uma notificação.
"""

import json
import logging
import time
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


class IntelligenceUnit:
    """Unidade de inteligência que orquestra extração e análise via LLM local.

    Utiliza duas instâncias do ``OllamaLLM`` (Llama 3.1 por padrão):

    - ``llm_json``: configurada com ``format='json'`` para forçar saída JSON
      estrita na chain de extração.
    - ``llm_text``: saída em texto livre para a chain de análise de mudanças.

    Args:
        model_name: Nome do modelo Ollama a ser utilizado (default: ``'llama3.1'``).
    """

    def __init__(
        self,
        model_name: str = "llama3.1",
        base_url: str = "http://127.0.0.1:11434",
        timeout_s: float = 120.0,
        retries: int = 2,
        retry_delay_s: float = 2.0,
        area_context: str = "TI",
        include_keywords: list[str] | None = None,
        exclude_keywords: list[str] | None = None,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.timeout_s = timeout_s
        self.retries = max(0, retries)
        self.retry_delay_s = max(0.0, retry_delay_s)
        self.area_context = area_context
        self.include_keywords = include_keywords or []
        self.exclude_keywords = exclude_keywords or []

        # LLM para Extração de Dados (saída JSON estrita)
        self.llm_json = self._create_llm(
            model_name=model_name,
            base_url=base_url,
            timeout_s=timeout_s,
            temperature=0,
            format="json",
        )

        # LLM para Análise de Mudanças (saída em texto normal)
        self.llm_text = self._create_llm(
            model_name=model_name,
            base_url=base_url,
            timeout_s=timeout_s,
            temperature=0,
        )

        include_keywords = ", ".join(self.include_keywords) if self.include_keywords else "nenhuma"
        exclude_keywords = ", ".join(self.exclude_keywords) if self.exclude_keywords else "nenhuma"
        extraction_system_prompt = f"""
            Você é um extrator de dados de alta precisão. Analise o bloco de HTML de um blog de concursos.

            REGRAS:
            0. Você está filtrando para a área alvo: {self.area_context}.
               Palavras obrigatórias (se houver): {include_keywords}.
               Palavras proibidas (se houver): {exclude_keywords}.
               Se o bloco não tiver aderência à área alvo, responda {{"ignorar": true}}.
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
        """

        # --- PROMPT 1: EXTRAÇÃO (HTML -> JSON) ---
        self.prompt_extracao = ChatPromptTemplate.from_messages([
            ("system", extraction_system_prompt),
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

    @staticmethod
    def _create_llm(
        model_name: str,
        base_url: str,
        timeout_s: float,
        temperature: float,
        format: str | None = None,
    ) -> OllamaLLM:
        """Cria OllamaLLM com fallback para diferentes versões do wrapper."""
        base_kwargs = {
            "model": model_name,
            "temperature": temperature,
            "base_url": base_url,
        }
        if format is not None:
            base_kwargs["format"] = format

        # Versão atual (langchain-ollama) costuma aceitar timeout em client_kwargs.
        try:
            return OllamaLLM(**base_kwargs, client_kwargs={"timeout": timeout_s})
        except TypeError:
            pass

        # Compatibilidade com versões antigas que aceitam request_timeout.
        try:
            return OllamaLLM(**base_kwargs, request_timeout=timeout_s)
        except TypeError:
            return OllamaLLM(**base_kwargs)


    def extrair_dados(self, bloco_html: str) -> dict:
        """Envia um bloco de HTML bruto à LLM e obtém dados estruturados em JSON.

        A chain de extração instrui a LLM a:

        - Retornar ``{"ignorar": true}`` quando o bloco for conteúdo genérico
          (listas de cidades/cargos, "Notícias Recomendadas", etc.).
        - Retornar um JSON com ``nome``, ``status``, ``link`` e ``ignorar: false``
          quando o bloco contiver uma notícia real de concurso.

        Args:
            bloco_html: String HTML bruta de um bloco delimitado por ``<h3>``.

        Returns:
            dict: Dicionário com as chaves ``ignorar``, ``nome``, ``status`` e
                  ``link``. Em caso de falha na LLM ou JSON malformado, retorna
                  ``{"ignorar": True}`` por segurança.
        """
        total_tentativas = self.retries + 1
        for tentativa in range(1, total_tentativas + 1):
            try:
                resposta = self.chain_extracao.invoke({"bloco": bloco_html})
                dados = json.loads(resposta)
                return dados
            except Exception as e:
                self.logger.warning(
                    f"⚠️ Falha na extração via IA (tentativa {tentativa}/{total_tentativas}): {e}"
                )
                if tentativa < total_tentativas:
                    time.sleep(self.retry_delay_s)

        self.logger.error("❌ Extração falhou após todas as tentativas; bloco será ignorado.")
        return {"ignorar": True}


    def analisar_mudanca(self, antigo: str, novo: str) -> str | None:
        """Compara dois textos de status e decide se a mudança é relevante.

        Utiliza a chain de análise para pedir à LLM que avalie se houve
        avanço real no concurso (ex.: edital publicado, banca escolhida)
        ou apenas uma reformulação textual sem valor informativo.

        Args:
            antigo: Texto do status salvo anteriormente no banco.
            novo: Texto do status recém-extraído pela chain de extração.

        Returns:
            str | None: Resumo de até 15 palavras descrevendo a mudança,
                        ou ``None`` se os textos forem idênticos, a mudança
                        for irrelevante (IA retorna IGNORE) ou ocorrer erro.
        """
        if antigo.strip() == novo.strip():
            return None

        total_tentativas = self.retries + 1
        for tentativa in range(1, total_tentativas + 1):
            try:
                resultado = self.chain_analise.invoke({"antigo": antigo, "novo": novo})
                resposta = resultado.strip()

                if "IGNORE" in resposta.upper():
                    return None

                return resposta
            except Exception as e:
                self.logger.warning(
                    f"⚠️ Falha na análise de mudança via IA (tentativa {tentativa}/{total_tentativas}): {e}"
                )
                if tentativa < total_tentativas:
                    time.sleep(self.retry_delay_s)

        self.logger.error("❌ Análise de mudança falhou após todas as tentativas; atualização será ignorada.")
        return None