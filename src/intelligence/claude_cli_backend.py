"""Backend que invoca o Claude Code CLI (`claude -p`) como LLM.

Permite usar a assinatura local do Claude Code (OAuth) em vez de gastar
chamadas de API ou carregar o Ollama. Cada chamada sobe um processo
`claude` novo via subprocess, portanto a latencia e alta (segundos por
chamada). Indicado para execucoes agendadas de baixa frequencia.

Requisitos:
    - Binario `claude` no PATH e autenticado na maquina.
    - Nao ter `ANTHROPIC_API_KEY` exportada com --bare (aqui nao usamos --bare).

Selecao de modelo via `LLM_MODEL`:
    claude-cli           → alias padrao (haiku)
    claude-cli:haiku     → claude-haiku-4-5 (mais rapido/barato)
    claude-cli:sonnet    → claude-sonnet-4-6 (mais preciso)
    claude-cli:opus      → claude-opus-4-7  (maxima qualidade)
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.llms import LLM


DEFAULT_MODEL_ALIAS = "haiku"
VALID_ALIASES = {"haiku", "sonnet", "opus"}

# Frases que o `claude` imprime quando a credencial morreu. Saem no STDOUT, nao
# no stderr — por isso, de 24/09 a 22/10/2026, o log so dizia "claude -p saiu
# com codigo 1:" seguido de nada, cerca de 6.800 vezes por dia, enquanto a causa
# real era "Failed to authenticate: OAuth session expired and could not be
# refreshed".
_MARCAS_AUTENTICACAO = (
    "failed to authenticate",
    "please run /login",
    "invalid api key",
    "oauth token",
    "oauth session",
    "not logged in",
)


class ClaudeCliAuthError(RuntimeError):
    """O `claude` esta sem credencial valida.

    Separada do RuntimeError generico porque retry nao conserta: todas as
    chamadas seguintes vao falhar igual ate alguem refazer o login.
    """


def parse_model_spec(spec: str) -> str:
    """Extrai o alias do modelo de uma spec `claude-cli[:alias]`.

    >>> parse_model_spec("claude-cli")
    'haiku'
    >>> parse_model_spec("claude-cli:sonnet")
    'sonnet'
    """
    if ":" not in spec:
        return DEFAULT_MODEL_ALIAS
    _, alias = spec.split(":", 1)
    alias = alias.strip().lower() or DEFAULT_MODEL_ALIAS
    if alias not in VALID_ALIASES:
        logging.getLogger(__name__).warning(
            f"Alias '{alias}' nao reconhecido; usando '{DEFAULT_MODEL_ALIAS}'."
        )
        return DEFAULT_MODEL_ALIAS
    return alias


class ClaudeCliLLM(LLM):
    """LangChain LLM que invoca `claude -p` via subprocess.

    Envia o prompt pelo stdin (evita limite de tamanho do argumento no
    cmd.exe do Windows e problemas de escape com acentos).
    """

    model: str = DEFAULT_MODEL_ALIAS
    timeout_s: float = 300.0
    executable: str = "claude"

    @property
    def _llm_type(self) -> str:
        return "claude_cli"

    def _call(
        self,
        prompt: str,
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        bin_path = shutil.which(self.executable) or self.executable
        cmd = [
            bin_path,
            "-p",
            "--model", self.model,
            "--output-format", "text",
            "--no-session-persistence",
        ]

        try:
            completed = subprocess.run(
                cmd,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=self.timeout_s,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"claude -p timeout apos {self.timeout_s}s") from exc
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"CLI 'claude' nao encontrado (executavel='{self.executable}'). "
                "Instale o Claude Code e garanta que esteja autenticado e no PATH."
            ) from exc

        if completed.returncode != 0:
            # O motivo pode vir em qualquer um dos dois canais (ver
            # _MARCAS_AUTENTICACAO); stderr vazio nao significa "sem motivo".
            detalhe = (completed.stderr or "").strip() or (completed.stdout or "").strip()
            if any(marca in detalhe.lower() for marca in _MARCAS_AUTENTICACAO):
                raise ClaudeCliAuthError(f"claude -p sem autenticacao: {detalhe[:300]}")
            raise RuntimeError(
                f"claude -p saiu com codigo {completed.returncode}: {detalhe[:500]}"
            )

        return (completed.stdout or "").strip()
