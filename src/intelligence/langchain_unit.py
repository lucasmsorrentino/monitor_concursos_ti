"""Módulo de inteligência artificial — cérebro duplo do sistema.

Contém a classe :class:`IntelligenceUnit`, que expõe duas chains LangChain
operando sobre uma LLM (Ollama local ou API remota via LiteLLM):

1. **Chain de Extração** (HTML → JSON): recebe um bloco de HTML bruto e
   devolve um dicionário estruturado com ``nome``, ``status``, ``link`` e
   uma flag ``ignorar``.
2. **Chain de Análise** (Texto → Texto): compara dois textos de status e
   decide se a mudança é relevante o suficiente para gerar uma notificação.
"""

import json
import logging
import re
import time
from datetime import date
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.intelligence.claude_cli_backend import ClaudeCliAuthError
from src.utils.fases import sanitizar_fase

# Provedores cujo adaptador no LiteLLM nao declara `response_format` nem
# `reasoning_effort` (o `zai/` da 1.95, que roda no notebook). Passados como
# parametro normal, o LiteLLM recusa a chamada (UnsupportedParamsError); em
# `extra_body` eles vao direto no corpo do POST, e a API do z.ai aceita os dois.
_PROVEDORES_VIA_EXTRA_BODY = ("zai/",)

# Classes que o LiteLLM e o SDK da OpenAI levantam para 401/403. Comparadas
# pelo nome para nao importar o litellm (pesado) quando o backend e outro.
_ERROS_DE_CREDENCIAL = {"AuthenticationError", "PermissionDeniedError"}

# Chave ausente e saldo zerado tambem nao se resolvem com retry, mas chegam com
# outras classes: sem chave, o LiteLLM 1.95 levanta InternalServerError
# ("Missing credentials"); "1113" e o codigo de saldo zerado do z.ai.
_MARCAS_SEM_CREDENCIAL = (
    "missing credentials",
    "insufficient balance",
    "余额不足",
    "'code': '1113'",
    '"code":"1113"',
)


def _e_falha_de_credencial(exc: Exception) -> bool:
    """Erro que so uma pessoa conserta: login, chave invalida ou saldo zerado."""
    if isinstance(exc, ClaudeCliAuthError):
        return True
    if _ERROS_DE_CREDENCIAL & {cls.__name__ for cls in type(exc).__mro__}:
        return True
    texto = str(exc).lower()
    return any(marca in texto for marca in _MARCAS_SEM_CREDENCIAL)


class IntelligenceUnit:
    """Unidade de inteligência que orquestra extração e análise via LLM.

    Suporta três backends, selecionados pelo formato de ``model_name``:

    - **Ollama** (local): nome simples, ex: ``llama3.1``.
    - **LiteLLM** (API remota): nome com ``/``, ex: ``minimax/MiniMax-M2``,
      ``anthropic/claude-haiku-4-5-20251001``. Requer a API key do provider.
    - **Claude Code CLI** (assinatura local): ``claude-cli`` ou
      ``claude-cli:<alias>`` (ex: ``claude-cli:haiku``). Usa o binario
      ``claude`` autenticado na maquina — mais lento, custo marginal zero.

    Args:
        model_name: Nome do modelo (default: ``'llama3.1'``).
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
        api_base: str | None = None,
        api_key: str | None = None,
        reasoning_effort: str | None = None,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.model_name = model_name
        self.timeout_s = timeout_s
        self.retries = max(0, retries)
        self.retry_delay_s = max(0.0, retry_delay_s)
        self.area_context = area_context
        self.include_keywords = include_keywords or []
        self.exclude_keywords = exclude_keywords or []
        # Preenchido na primeira falha de login do backend. Dai em diante a
        # rodada nao chama mais a LLM: ver `extrair_dados`.
        self.falha_autenticacao: str | None = None
        self._backend = self._detect_backend(model_name)

        if self._backend == "claude_cli":
            self.logger.info(f"Usando Claude Code CLI (modelo: {model_name})")
        elif self._backend == "litellm":
            self.logger.info(f"Usando LiteLLM com modelo remoto: {model_name}")
        else:
            self.logger.info(f"Usando Ollama local com modelo: {model_name}")

        # LLM para Extração de Dados (saída JSON estrita)
        self.llm_json = self._create_llm(
            model_name=model_name,
            base_url=base_url,
            timeout_s=timeout_s,
            temperature=0,
            format="json",
            api_base=api_base,
            api_key=api_key,
            reasoning_effort=reasoning_effort,
        )

        include_keywords = ", ".join(self.include_keywords) if self.include_keywords else "nenhuma"
        exclude_keywords = ", ".join(self.exclude_keywords) if self.exclude_keywords else "nenhuma"
        extraction_system_prompt = f"""
            Você é um extrator de dados de alta precisão. Analise o bloco de HTML de um blog de concursos.

            REGRAS:
            0. Você está filtrando para a área alvo: {self.area_context}.
               Palavras obrigatórias (se houver): {include_keywords}.
               Palavras proibidas (se houver): {exclude_keywords}.
               Se o bloco não tiver aderência à área alvo, responda {{{{"ignorar": true}}}}.
            1. Se o bloco for apenas uma lista genérica (ex: apenas nomes de cidades/cargos sem explicações) ou for "Notícias Recomendadas", responda: {{{{"ignorar": true}}}}
            2. Se for uma notícia de concurso real, extraia as informações.
            3. O link deve ser a URL da notícia detalhada (procure em tags <a>).
               Se o bloco tiver VÁRIOS links para o mesmo concurso, escolha SEMPRE pela ordem:
                 a) o link de `blog.grancursosonline.com.br` com o caminho MAIS CURTO
                    (ex: prefira `/concurso-seduc-al/` a `/concurso-seduc-al-edital-publicado-2026/`);
                 b) nunca use links de `www.grancursosonline.com.br` (página de venda de curso)
                    se existir alternativa do blog.
               Essa escolha precisa ser ESTÁVEL entre execuções: o link identifica o concurso
               no banco de dados, e variar o link duplica notificações.
            4. `data_fim_inscricao` é a ÚLTIMA data possível de inscrição no formato ISO `YYYY-MM-DD`.
               Procure AGRESSIVAMENTE por marcadores como:
                 - "inscrições até DD/MM/YYYY"
                 - "prazo final DD/MM/YYYY"
                 - "período de inscrição: DD/MM a DD/MM/YYYY" (usa a SEGUNDA data)
                 - "encerram-se em DD/MM", "encerram dia DD/MM"
                 - "inscrições de DD/MM a DD/MM" (usa a SEGUNDA data)
                 - "com inscrições abertas até DD/MM/YYYY"
               Se o bloco diz "inscrições encerradas", "prazo encerrado", "inscrições finalizadas"
               e mencionar UMA data passada, use essa data.
               Se NÃO houver NENHUMA data clara, use `null`. Nunca invente.
               Converta DD/MM/YYYY para YYYY-MM-DD. Se o ano estiver ausente, assuma o ano corrente.
            5. `data_referencia` é a data de evento mais relevante do concurso, em ISO `YYYY-MM-DD`.
               Preferencia: data da prova/aplicacao; senao a data de fim de inscricao; senao
               qualquer data de evento citada (ex: "provas previstas para maio de 2025",
               "edital previsto para marco/2026"). Se houver so mes/ano, use o primeiro dia do mes
               (maio de 2025 -> 2025-05-01). Se NAO houver NENHUMA data, use `null`. Nunca invente.
               IMPORTANTE: concursos apenas "previstos"/"em estudo" SEM nenhuma data citada devem ter
               `data_referencia: null` (sao oportunidades futuras validas, nao listagens mortas).
            6. `fase` classifica o estagio do concurso. Escolha EXATAMENTE UMA destas opcoes
               (use o valor literal, em minusculas):
                 - "previsto": autorizado, em estudo, comissao formada; sem banca nem edital.
                 - "banca_definida": banca/organizadora escolhida, edital ainda NAO publicado.
                 - "edital_publicado": edital publicado, mas inscricoes ainda nao abriram.
                 - "inscricoes_abertas": inscricoes abertas neste momento.
                 - "inscricoes_encerradas": inscricoes ja encerradas (aguardando ou em provas).
                 - "concluido": concurso finalizado/antigo (provas ja realizadas, homologado).
               Na duvida entre duas fases adjacentes, escolha a MENOS avancada.
            7. Responda APENAS com JSON válido:
            {{{{
                "ignorar": false,
                "nome": "Nome do Concurso ou Órgão",
                "status": "Resumo do status atual em até 2 frases",
                "link": "https://...",
                "data_fim_inscricao": "YYYY-MM-DD ou null",
                "data_referencia": "YYYY-MM-DD ou null",
                "fase": "uma das 6 opcoes acima"
            }}}}
        """

        # --- PROMPT 1: EXTRAÇÃO (HTML -> JSON) ---
        self.prompt_extracao = ChatPromptTemplate.from_messages([
            ("system", extraction_system_prompt),
            ("human", "Analise este HTML:\n{bloco}")
        ])
        self.chain_extracao = self.prompt_extracao | self.llm_json | StrOutputParser()

        # Havia aqui um segundo prompt ("analise de mudanca") com seu proprio LLM
        # em texto livre. Foi removido em 08/2026: a deteccao de mudanca passou a
        # comparar `fase` + `data_fim_inscricao` (ver src/utils/fases.py) e essa
        # chain nao era mais chamada por ninguem fora dos testes. Ela custava a
        # construcao de um segundo cliente LLM em toda varredura, a troco de nada.

    @staticmethod
    def _detect_backend(model_name: str) -> str:
        """Determina o backend a partir do formato de ``model_name``."""
        if model_name.startswith("claude-cli"):
            return "claude_cli"
        if "/" in model_name:
            return "litellm"
        return "ollama"

    def _create_llm(
        self,
        model_name: str,
        base_url: str,
        timeout_s: float,
        temperature: float,
        format: str | None = None,
        api_base: str | None = None,
        api_key: str | None = None,
        reasoning_effort: str | None = None,
    ):
        """Cria LLM adequada ao backend selecionado."""
        if self._backend == "claude_cli":
            return self._create_claude_cli(model_name, timeout_s)
        if self._backend == "litellm":
            return self._create_litellm(
                model_name, timeout_s, temperature, format,
                api_base=api_base, api_key=api_key, reasoning_effort=reasoning_effort,
            )
        return self._create_ollama(model_name, base_url, timeout_s, temperature, format)

    @property
    def instrucao_login(self) -> str:
        """Como consertar uma falha de credencial deste backend (HTML do Telegram)."""
        if self._backend == "claude_cli":
            return (
                "no notebook, <code>claude setup-token</code> e o token em "
                "<code>CLAUDE_CODE_OAUTH_TOKEN</code> no monitor.env"
            )
        if self._backend == "litellm":
            return (
                f"confira a chave da API e o saldo do provedor de "
                f"<code>{self.model_name}</code> (ex.: <code>ZAI_API_KEY</code> no monitor.env)"
            )
        return "confira se o Ollama está no ar"

    @staticmethod
    def _create_claude_cli(model_name: str, timeout_s: float):
        """Cria o wrapper do Claude Code CLI."""
        from src.intelligence.claude_cli_backend import ClaudeCliLLM, parse_model_spec
        return ClaudeCliLLM(model=parse_model_spec(model_name), timeout_s=timeout_s)

    @staticmethod
    def _create_ollama(
        model_name: str,
        base_url: str,
        timeout_s: float,
        temperature: float,
        format: str | None = None,
    ):
        """Cria OllamaLLM com fallback para diferentes versões do wrapper."""
        from langchain_ollama import OllamaLLM

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

    @staticmethod
    def _create_litellm(
        model_name: str,
        timeout_s: float,
        temperature: float,
        format: str | None = None,
        api_base: str | None = None,
        api_key: str | None = None,
        reasoning_effort: str | None = None,
    ):
        """Cria ChatLiteLLM para APIs remotas (z.ai, MiniMax, OpenAI, etc.).

        ``api_base``/``api_key`` servem a endpoints compativeis com OpenAI
        (``openai/<modelo>``). Sem eles, o LiteLLM le a chave da variavel do
        provedor (``ZAI_API_KEY``, ``ANTHROPIC_API_KEY``...).

        ``reasoning_effort`` importa no GLM-5.3-Flash: ele sempre "pensa" e o
        padrao da API e ``max``, lento e caro para extrair meia duzia de campos.
        """
        import litellm
        from langchain_litellm import ChatLiteLLM

        # Sem isso, todo erro do LiteLLM imprime um banner "Give Feedback / Get
        # Help" no stdout, que o run_daily.sh manda direto pro log do dia, e
        # toda chamada rende duas linhas INFO "completion() model=...".
        litellm.suppress_debug_info = True
        logging.getLogger("LiteLLM").setLevel(logging.WARNING)

        kwargs = {
            "model": model_name,
            "temperature": temperature,
            "timeout": timeout_s,
        }
        if api_base:
            kwargs["api_base"] = api_base
        if api_key:
            kwargs["api_key"] = api_key

        extras = {}
        if format == "json":
            extras["response_format"] = {"type": "json_object"}
        if reasoning_effort:
            extras["reasoning_effort"] = reasoning_effort

        if extras:
            if model_name.startswith(_PROVEDORES_VIA_EXTRA_BODY):
                kwargs["model_kwargs"] = {"extra_body": extras}
            else:
                kwargs["model_kwargs"] = extras

        return ChatLiteLLM(**kwargs)


    @staticmethod
    def _parse_json_response(resposta: str) -> dict:
        """Extrai JSON da resposta da LLM, mesmo que venha envolto em markdown."""
        text = resposta.strip()
        # Tenta parse direto
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Remove code fences (```json ... ``` ou ``` ... ```)
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        # Encontra o primeiro objeto JSON na resposta
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise json.JSONDecodeError("Nenhum JSON encontrado na resposta", text, 0)

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
                  ``{"ignorar": True, "erro": True}``.

        Nota sobre ``erro``: antes a falha devolvia so ``{"ignorar": True}``, o
        que tornava um edital PERDIDO indistinguivel de um bloco irrelevante.
        Nos logs historicos ha 12 desistencias e 3 timeouts do `claude -p` que
        passaram batido assim. Agora quem chama consegue contar as duas coisas
        separadamente e alertar quando a taxa de erro sobe.

        Falha de LOGIN e diferente das outras: nao ha retry e as chamadas
        seguintes nem sobem o processo. Com o OAuth do notebook expirado, cada
        rodada fazia 3 tentativas para cada um dos ~95 itens que precisam de LLM
        (somando as tres areas), de hora em hora — 6.840 processos `claude` por
        dia, todos fadados a falhar.
        """
        if self.falha_autenticacao:
            return {"ignorar": True, "erro": True}

        total_tentativas = self.retries + 1
        for tentativa in range(1, total_tentativas + 1):
            try:
                resposta = self.chain_extracao.invoke({"bloco": bloco_html})
                dados = self._parse_json_response(resposta)
                dados["data_fim_inscricao"] = self._sanitizar_data(
                    dados.get("data_fim_inscricao")
                )
                dados["data_referencia"] = self._sanitizar_data(
                    dados.get("data_referencia")
                )
                dados["fase"] = sanitizar_fase(dados.get("fase"))
                return dados
            except Exception as e:
                if _e_falha_de_credencial(e):
                    self.falha_autenticacao = str(e)
                    self.logger.error(
                        f"🔑 {e}. Pulando as demais chamadas desta rodada: retry nao "
                        f"conserta credencial."
                    )
                    return {"ignorar": True, "erro": True}
                self.logger.warning(
                    f"⚠️ Falha na extração via IA (tentativa {tentativa}/{total_tentativas}): {e}"
                )
                if tentativa < total_tentativas:
                    time.sleep(self.retry_delay_s)

        self.logger.error(
            "❌ Extração falhou após todas as tentativas; bloco perdido (contabilizado como erro)."
        )
        return {"ignorar": True, "erro": True}

    def _sanitizar_data(self, valor) -> str | None:
        """Valida e normaliza a data de fim de inscricao extraida pela LLM.

        Aceita apenas ISO `YYYY-MM-DD`. Valores malformados, vazios,
        strings `null`/`none` ou tipos nao-string viram `None` (comportamento
        seguro: sem prazo conhecido = nao bloqueia notificacao).
        """
        if not valor or not isinstance(valor, str):
            return None
        texto = valor.strip()
        if texto.lower() in ("null", "none", ""):
            return None
        try:
            date.fromisoformat(texto)
            return texto
        except ValueError:
            self.logger.debug(f"data_fim_inscricao malformada descartada: {valor!r}")
            return None
