"""Testes para src/intelligence/langchain_unit.py.

Os testes nao chamam LLM real — usam mocks via pytest-mock para
substituir os construtores de backend antes de instanciar o IntelligenceUnit
e para simular respostas do chain.
"""
import json

import pytest

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
        assert spy.call_count == 2  # llm_json + llm_text

    def test_litellm_backend_calls_create_litellm(self, mocker):
        mocker.patch.object(IntelligenceUnit, "_create_ollama", return_value=mocker.MagicMock())
        spy = mocker.patch.object(
            IntelligenceUnit, "_create_litellm", return_value=mocker.MagicMock()
        )
        IntelligenceUnit(model_name="anthropic/claude-haiku-4-5", retries=0, retry_delay_s=0)
        assert spy.call_count == 2

    def test_claude_cli_backend_calls_create_claude_cli(self, mocker):
        mocker.patch.object(IntelligenceUnit, "_create_ollama", return_value=mocker.MagicMock())
        spy = mocker.patch.object(
            IntelligenceUnit, "_create_claude_cli", return_value=mocker.MagicMock()
        )
        IntelligenceUnit(model_name="claude-cli:haiku", retries=0, retry_delay_s=0)
        assert spy.call_count == 2


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
            '{"ignorar": false, "nome": "TRF1", "status": "aberto", "link": "https://x"}'
        )

        result = ollama_unit.extrair_dados("<h3>bloco</h3>")

        assert result == {"ignorar": False, "nome": "TRF1", "status": "aberto", "link": "https://x"}

    def test_retries_on_decode_error_then_succeeds(self, ollama_unit, mocker):
        ollama_unit.chain_extracao = mocker.MagicMock()
        ollama_unit.chain_extracao.invoke.side_effect = ["nao_e_json", '{"ignorar": true}']

        result = ollama_unit.extrair_dados("<h3>x</h3>")

        assert result == {"ignorar": True}
        assert ollama_unit.chain_extracao.invoke.call_count == 2

    def test_returns_ignorar_true_after_all_retries_fail(self, ollama_unit, mocker):
        ollama_unit.chain_extracao = mocker.MagicMock()
        ollama_unit.chain_extracao.invoke.side_effect = RuntimeError("LLM down")

        result = ollama_unit.extrair_dados("<h3>x</h3>")

        assert result == {"ignorar": True}


class TestAnalisarMudanca:
    def test_returns_none_for_identical_status(self, ollama_unit):
        assert ollama_unit.analisar_mudanca("mesmo texto", "mesmo texto") is None

    def test_returns_none_when_llm_returns_ignore(self, ollama_unit, mocker):
        ollama_unit.chain_analise = mocker.MagicMock()
        ollama_unit.chain_analise.invoke.return_value = "IGNORE"

        assert ollama_unit.analisar_mudanca("v1", "v2") is None

    def test_returns_none_when_ignore_mixed_case(self, ollama_unit, mocker):
        ollama_unit.chain_analise = mocker.MagicMock()
        ollama_unit.chain_analise.invoke.return_value = "  ignore  "

        assert ollama_unit.analisar_mudanca("v1", "v2") is None

    def test_returns_summary_for_relevant_change(self, ollama_unit, mocker):
        ollama_unit.chain_analise = mocker.MagicMock()
        ollama_unit.chain_analise.invoke.return_value = "Edital publicado hoje."

        assert ollama_unit.analisar_mudanca("v1", "v2") == "Edital publicado hoje."

    def test_retries_on_exception_then_returns_none(self, ollama_unit, mocker):
        ollama_unit.chain_analise = mocker.MagicMock()
        ollama_unit.chain_analise.invoke.side_effect = RuntimeError("timeout")

        assert ollama_unit.analisar_mudanca("v1", "v2") is None

    def test_whitespace_only_difference_is_treated_as_identical(self, ollama_unit):
        assert ollama_unit.analisar_mudanca("  texto  ", "texto") is None
