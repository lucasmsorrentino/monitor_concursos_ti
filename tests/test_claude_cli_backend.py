"""Testes para src/intelligence/claude_cli_backend.py.

Nao invoca o CLI real — mocka subprocess.run e shutil.which.
"""
import subprocess

import pytest

from src.intelligence.claude_cli_backend import (
    DEFAULT_MODEL_ALIAS,
    ClaudeCliLLM,
    parse_model_spec,
)


class TestParseModelSpec:
    def test_plain_claude_cli_returns_default(self):
        assert parse_model_spec("claude-cli") == DEFAULT_MODEL_ALIAS

    def test_valid_alias_is_returned(self):
        assert parse_model_spec("claude-cli:haiku") == "haiku"
        assert parse_model_spec("claude-cli:sonnet") == "sonnet"
        assert parse_model_spec("claude-cli:opus") == "opus"

    def test_empty_alias_falls_back_to_default(self):
        assert parse_model_spec("claude-cli:") == DEFAULT_MODEL_ALIAS

    def test_unknown_alias_falls_back_to_default(self):
        assert parse_model_spec("claude-cli:gpt4") == DEFAULT_MODEL_ALIAS

    def test_uppercase_alias_is_normalized(self):
        assert parse_model_spec("claude-cli:HAIKU") == "haiku"


class TestClaudeCliLLM:
    def test_invoke_builds_correct_command(self, mocker):
        mocker.patch("shutil.which", return_value="C:/fake/claude.exe")
        completed = mocker.MagicMock(returncode=0, stdout="resposta", stderr="")
        run = mocker.patch("subprocess.run", return_value=completed)

        llm = ClaudeCliLLM(model="haiku", timeout_s=60)
        result = llm.invoke("prompt de teste")

        assert result == "resposta"
        run.assert_called_once()
        args = run.call_args
        cmd = args.args[0]
        assert cmd[0] == "C:/fake/claude.exe"
        assert "-p" in cmd
        assert "--model" in cmd
        assert "haiku" in cmd
        assert "--output-format" in cmd
        assert "--no-session-persistence" in cmd

    def test_prompt_is_passed_via_stdin_not_argv(self, mocker):
        mocker.patch("shutil.which", return_value="claude")
        completed = mocker.MagicMock(returncode=0, stdout="ok", stderr="")
        run = mocker.patch("subprocess.run", return_value=completed)

        llm = ClaudeCliLLM(model="haiku")
        llm.invoke("meu prompt com acentos: ção")

        kwargs = run.call_args.kwargs
        assert kwargs["input"] == "meu prompt com acentos: ção"
        cmd = run.call_args.args[0]
        assert "meu prompt" not in " ".join(cmd)

    def test_timeout_propagated(self, mocker):
        mocker.patch("shutil.which", return_value="claude")
        completed = mocker.MagicMock(returncode=0, stdout="ok", stderr="")
        run = mocker.patch("subprocess.run", return_value=completed)

        llm = ClaudeCliLLM(timeout_s=42)
        llm.invoke("x")

        assert run.call_args.kwargs["timeout"] == 42

    def test_nonzero_exit_raises_runtime_error(self, mocker):
        mocker.patch("shutil.which", return_value="claude")
        completed = mocker.MagicMock(returncode=2, stdout="", stderr="erro interno")
        mocker.patch("subprocess.run", return_value=completed)

        llm = ClaudeCliLLM()
        with pytest.raises(RuntimeError, match="codigo 2"):
            llm.invoke("x")

    def test_file_not_found_raises_with_helpful_message(self, mocker):
        mocker.patch("shutil.which", return_value=None)
        mocker.patch("subprocess.run", side_effect=FileNotFoundError("claude"))

        llm = ClaudeCliLLM()
        with pytest.raises(RuntimeError, match="nao encontrado"):
            llm.invoke("x")

    def test_timeout_expired_raises(self, mocker):
        mocker.patch("shutil.which", return_value="claude")
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=60),
        )

        llm = ClaudeCliLLM(timeout_s=60)
        with pytest.raises(RuntimeError, match="timeout"):
            llm.invoke("x")

    def test_stdout_is_stripped(self, mocker):
        mocker.patch("shutil.which", return_value="claude")
        completed = mocker.MagicMock(returncode=0, stdout="  resposta com espaco  \n", stderr="")
        mocker.patch("subprocess.run", return_value=completed)

        llm = ClaudeCliLLM()

        assert llm.invoke("x") == "resposta com espaco"
