"""Testes para src/intelligence/langchain_unit.py.

Os testes nao chamam LLM real — usam mocks via pytest-mock para
substituir os construtores de backend antes de instanciar o IntelligenceUnit
e para simular respostas do chain.
"""
import json

import pytest

from src.intelligence.claude_cli_backend import ClaudeCliAuthError
from src.intelligence.langchain_unit import IntelligenceUnit


@pytest.fixture
def ollama_unit(mocker):
    """IntelligenceUnit com Ollama mockado — usado pelo grosso dos testes."""
    mocker.patch.object(IntelligenceUnit, "_create_ollama", return_value=mocker.MagicMock())
    return IntelligenceUnit(model_name="llama3.1", retries=1, retry_delay_s=0)


class TestBackendDetection:
    def test_plain_name_is_ollama(self):
        assert IntelligenceUnit._detect_backend("llama3.1") == "ollama"
        assert IntelligenceUnit._detect_backend("qwen2.5:7b") == "ollama"

    def test_slashed_name_is_litellm(self):
        assert IntelligenceUnit._detect_backend("anthropic/claude-haiku") == "litellm"
        assert IntelligenceUnit._detect_backend("openai/gpt-4o") == "litellm"

    def test_claude_cli_prefix(self):
        assert IntelligenceUnit._detect_backend("claude-cli") == "claude_cli"
        assert IntelligenceUnit._detect_backend("claude-cli:haiku") == "claude_cli"


class TestBackendWiring:
    def test_ollama_backend_calls_create_ollama(self, mocker):
        spy = mocker.patch.object(IntelligenceUnit, "_create_ollama", return_value=mocker.MagicMock())
        IntelligenceUnit(model_name="llama3.1", retries=0, retry_delay_s=0)
        assert spy.call_count == 1  # so llm_json (llm_text saiu com a chain de analise)

    def test_litellm_backend_calls_create_litellm(self, mocker):
        mocker.patch.object(IntelligenceUnit, "_create_ollama", return_value=mocker.MagicMock())
        spy = mocker.patch.object(
            IntelligenceUnit, "_create_litellm", return_value=mocker.MagicMock()
        )
        IntelligenceUnit(model_name="anthropic/claude-haiku-4-5", retries=0, retry_delay_s=0)
        assert spy.call_count == 1

    def test_claude_cli_backend_calls_create_claude_cli(self, mocker):
        mocker.patch.object(IntelligenceUnit, "_create_ollama", return_value=mocker.MagicMock())
        spy = mocker.patch.object(
            IntelligenceUnit, "_create_claude_cli", return_value=mocker.MagicMock()
        )
        IntelligenceUnit(model_name="claude-cli:haiku", retries=0, retry_delay_s=0)
        assert spy.call_count == 1


class TestParseJsonResponse:
    def test_raw_json(self):
        raw = '{"ignorar": false, "nome": "X"}'
        assert IntelligenceUnit._parse_json_response(raw) == {"ignorar": False, "nome": "X"}

    def test_markdown_fenced_json(self):
        raw = '```json\n{"ignorar": true}\n```'
        assert IntelligenceUnit._parse_json_response(raw) == {"ignorar": True}

    def test_markdown_fenced_without_language(self):
        raw = '```\n{"nome": "Teste"}\n```'
        assert IntelligenceUnit._parse_json_response(raw) == {"nome": "Teste"}

    def test_json_embedded_in_prose(self):
        raw = 'Aqui esta o resultado: {"nome": "X", "status": "aberto"} pronto.'
        assert IntelligenceUnit._parse_json_response(raw) == {"nome": "X", "status": "aberto"}

    def test_invalid_raises(self):
        with pytest.raises(json.JSONDecodeError):
            IntelligenceUnit._parse_json_response("sem json aqui")


class TestExtrairDados:
    def test_returns_parsed_dict_on_success(self, ollama_unit, mocker):
        ollama_unit.chain_extracao = mocker.MagicMock()
        ollama_unit.chain_extracao.invoke.return_value = (
            '{"ignorar": false, "nome": "TRF1", "status": "aberto", "link": "https://x", "data_fim_inscricao": "2026-12-31"}'
        )

        result = ollama_unit.extrair_dados("<h3>bloco</h3>")

        assert result == {
            "ignorar": False, "nome": "TRF1", "status": "aberto",
            "link": "https://x", "data_fim_inscricao": "2026-12-31",
            "data_referencia": None, "fase": None,
        }

    def test_sanitiza_data_malformada_para_none(self, ollama_unit, mocker):
        ollama_unit.chain_extracao = mocker.MagicMock()
        ollama_unit.chain_extracao.invoke.return_value = (
            '{"ignorar": false, "nome": "TRF1", "status": "aberto", "link": "https://x", "data_fim_inscricao": "31/12/2026"}'
        )

        result = ollama_unit.extrair_dados("<h3>bloco</h3>")

        assert result["data_fim_inscricao"] is None

    def test_sanitiza_data_null_string(self, ollama_unit, mocker):
        ollama_unit.chain_extracao = mocker.MagicMock()
        ollama_unit.chain_extracao.invoke.return_value = (
            '{"ignorar": false, "nome": "TRF1", "status": "aberto", "link": "https://x", "data_fim_inscricao": "null"}'
        )

        result = ollama_unit.extrair_dados("<h3>bloco</h3>")

        assert result["data_fim_inscricao"] is None

    def test_sanitiza_data_ausente(self, ollama_unit, mocker):
        ollama_unit.chain_extracao = mocker.MagicMock()
        ollama_unit.chain_extracao.invoke.return_value = (
            '{"ignorar": false, "nome": "TRF1", "status": "aberto", "link": "https://x"}'
        )

        result = ollama_unit.extrair_dados("<h3>bloco</h3>")

        assert result["data_fim_inscricao"] is None

    def test_retries_on_decode_error_then_succeeds(self, ollama_unit, mocker):
        ollama_unit.chain_extracao = mocker.MagicMock()
        ollama_unit.chain_extracao.invoke.side_effect = ["nao_e_json", '{"ignorar": true}']

        result = ollama_unit.extrair_dados("<h3>x</h3>")

        assert result == {"ignorar": True, "data_fim_inscricao": None, "data_referencia": None, "fase": None}
        assert ollama_unit.chain_extracao.invoke.call_count == 2

    def test_returns_ignorar_true_after_all_retries_fail(self, ollama_unit, mocker):
        ollama_unit.chain_extracao = mocker.MagicMock()
        ollama_unit.chain_extracao.invoke.side_effect = RuntimeError("LLM down")

        result = ollama_unit.extrair_dados("<h3>x</h3>")

        # `erro` separa edital PERDIDO de bloco irrelevante; o bot conta os dois
        # e alerta quando a taxa de perda passa de LIMITE_ERRO_EXTRACAO.
        assert result == {"ignorar": True, "erro": True}


class TestFalhaDeLogin:
    """Login caido nao se conserta com retry: uma chamada basta para saber."""

    def test_nao_retenta_e_registra_o_motivo(self, ollama_unit, mocker):
        ollama_unit.chain_extracao = mocker.MagicMock()
        ollama_unit.chain_extracao.invoke.side_effect = ClaudeCliAuthError("OAuth expirado")

        result = ollama_unit.extrair_dados("<h3>x</h3>")

        assert result == {"ignorar": True, "erro": True}
        assert ollama_unit.chain_extracao.invoke.call_count == 1
        assert "OAuth expirado" in ollama_unit.falha_autenticacao

    def test_chamadas_seguintes_nem_sobem_a_llm(self, ollama_unit, mocker):
        ollama_unit.chain_extracao = mocker.MagicMock()
        ollama_unit.chain_extracao.invoke.side_effect = ClaudeCliAuthError("OAuth expirado")

        for _ in range(5):
            result = ollama_unit.extrair_dados("<h3>x</h3>")

        # Continua contando como erro (o bot precisa saber que ficou sem leitura).
        assert result == {"ignorar": True, "erro": True}
        assert ollama_unit.chain_extracao.invoke.call_count == 1

    def test_comeca_sem_falha(self, ollama_unit):
        assert ollama_unit.falha_autenticacao is None

    def test_chave_invalida_da_api_tambem_para_a_rodada(self, ollama_unit, mocker):
        """401 do LiteLLM/OpenAI SDK: mesma classe de problema que o OAuth vencido."""

        class AuthenticationError(Exception):
            pass

        ollama_unit.chain_extracao = mocker.MagicMock()
        ollama_unit.chain_extracao.invoke.side_effect = AuthenticationError("ZaiException - 401")

        ollama_unit.extrair_dados("<h3>x</h3>")
        ollama_unit.extrair_dados("<h3>y</h3>")

        assert ollama_unit.chain_extracao.invoke.call_count == 1
        assert "401" in ollama_unit.falha_autenticacao

    def test_saldo_zerado_do_zai_tambem_para_a_rodada(self, ollama_unit, mocker):
        ollama_unit.chain_extracao = mocker.MagicMock()
        ollama_unit.chain_extracao.invoke.side_effect = RuntimeError(
            "RateLimitError: Insufficient balance or no resource package. Please recharge."
        )

        ollama_unit.extrair_dados("<h3>x</h3>")

        assert ollama_unit.chain_extracao.invoke.call_count == 1
        assert ollama_unit.falha_autenticacao

    def test_chave_ausente_tambem_para_a_rodada(self, ollama_unit, mocker):
        """Mensagem real do LiteLLM 1.95 no notebook, 22/10/2026, sem ZAI_API_KEY."""

        class InternalServerError(Exception):
            pass

        ollama_unit.chain_extracao = mocker.MagicMock()
        ollama_unit.chain_extracao.invoke.side_effect = InternalServerError(
            "ZaiException - Missing credentials. Please pass an `api_key`, ... or set "
            "the `ZAI_API_KEY` or `ZAI_ADMIN_KEY` environment variable."
        )

        ollama_unit.extrair_dados("<h3>x</h3>")

        assert ollama_unit.chain_extracao.invoke.call_count == 1
        assert ollama_unit.falha_autenticacao

    def test_erro_passageiro_continua_com_retry(self, ollama_unit, mocker):
        ollama_unit.chain_extracao = mocker.MagicMock()
        ollama_unit.chain_extracao.invoke.side_effect = RuntimeError("503 overloaded")

        ollama_unit.extrair_dados("<h3>x</h3>")

        assert ollama_unit.chain_extracao.invoke.call_count == 2   # retries=1
        assert ollama_unit.falha_autenticacao is None


class TestBackendLiteLLM:
    """Parametros que chegam ao ChatLiteLLM (sem rede: so a construcao)."""

    def test_zai_manda_json_e_esforco_em_extra_body(self):
        """O adaptador `zai/` do LiteLLM nao declara esses dois parametros."""
        llm = IntelligenceUnit._create_litellm(
            "zai/glm-5.3-flash", 60, 0, format="json", reasoning_effort="low"
        )

        assert llm.model_kwargs == {
            "extra_body": {"response_format": {"type": "json_object"}, "reasoning_effort": "low"}
        }

    def test_outros_provedores_seguem_com_parametro_normal(self):
        llm = IntelligenceUnit._create_litellm("anthropic/claude-haiku-4-5", 60, 0, format="json")

        assert llm.model_kwargs == {"response_format": {"type": "json_object"}}

    def test_endpoint_compativel_com_openai_recebe_base_e_chave(self):
        llm = IntelligenceUnit._create_litellm(
            "openai/glm-5.3-flash", 60, 0,
            api_base="https://exemplo.test/v1", api_key="chave-de-teste",
        )

        assert llm.api_base == "https://exemplo.test/v1"
        assert llm.api_key == "chave-de-teste"

    def test_instrucao_de_conserto_depende_do_backend(self, mocker):
        mocker.patch.object(IntelligenceUnit, "_create_litellm", return_value=mocker.MagicMock())
        mocker.patch.object(IntelligenceUnit, "_create_claude_cli", return_value=mocker.MagicMock())

        api = IntelligenceUnit(model_name="zai/glm-5.3-flash", retries=0)
        cli = IntelligenceUnit(model_name="claude-cli:haiku", retries=0)

        assert "ZAI_API_KEY" in api.instrucao_login
        assert "setup-token" in cli.instrucao_login
