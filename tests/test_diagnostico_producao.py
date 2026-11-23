"""Testes do script de diagnostico da producao.

Costura: a execucao do proprio script por subprocess, sobre uma arvore falsa
montada em tmp_path (logs/, data/, .env). Pega as secoes, o tratamento de
arquivo ausente e a omicao de segredo. Nao pega o notebook de verdade.

O oracle e a arvore que o teste monta com conteudo literal: o esperado e o
que o teste escreveu (data, codigo de saida, contagens), nunca o que o
script calcula.
"""

import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "diagnostico_producao.sh"

SECOES = [
    "== Identidade ==",
    "== Ultimo sucesso ==",
    "== Saude por dia (ultimos 30 dias) ==",
    "== Erros recorrentes ==",
    "== Falha de credencial ==",
    "== Banco ==",
    "== Agendamento ==",
    "== Config efetiva ==",
]

BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(
    BASH is None,
    reason="bash nao disponivel nesta maquina (suite precisa ficar verde no Windows sem Git Bash)",
)


def _caminho_bash(caminho: Path) -> str:
    """Converte um caminho do Windows para a forma que o bash do Git aceita."""
    return str(caminho).replace("\\", "/")


def _rodar(raiz: Path, env_extra: dict[str, str] | None = None) -> tuple[int, str]:
    """Roda o script apontando para a arvore falsa e devolve (codigo, saida)."""
    env = os.environ.copy()
    # Garante um `python` que funciona no PATH do filho (o fallback do banco);
    # o venv da suite tem o python da propria maquina de testes.
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    # A maquina de dev nao pode injetar config de producao por acidente.
    env.pop("MONITOR_TARGETS_JSON", None)
    env.update(env_extra or {})
    # Caminho ABSOLUTO do bash: sem isso o CreateProcess do Windows acha o
    # bash.exe do WSL em System32 antes do bash do Git no PATH, e o WSL nao
    # entende caminhos C:/ (o script rodaria no bash errado e falharia com 127).
    proc = subprocess.run(
        [BASH, _caminho_bash(SCRIPT), _caminho_bash(raiz)],
        capture_output=True,
        cwd=raiz,
        env=env,
        timeout=120,
    )
    return proc.returncode, proc.stdout.decode("utf-8", errors="replace")


def _criar_logs(raiz: Path) -> Path:
    logs = raiz / "logs"
    logs.mkdir(exist_ok=True)
    return logs


def _criar_log_dia(logs: Path, dias_atras: int, linhas: list[str]) -> Path:
    """Grava logs/run_AAAAMMDD.log com data literal escolhida pelo teste."""
    dia = date.today() - timedelta(days=dias_atras)
    arquivo = logs / f"run_{dia:%Y%m%d}.log"
    arquivo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return arquivo


def _linha_erro(msg: str, hora: str = "03:15:00") -> str:
    dia = date.today() - timedelta(days=1)
    return f"[{dia:%Y-%m-%d} {hora}] [ERROR] [ConcursoBot]: {msg}"


def test_script_sai_com_zero_em_arvore_minima(tmp_path):
    _criar_logs(tmp_path)
    codigo, _ = _rodar(tmp_path)
    assert codigo == 0


def test_imprime_as_oito_secoes(tmp_path):
    _criar_logs(tmp_path)
    _, saida = _rodar(tmp_path)
    for titulo in SECOES:
        assert titulo in saida, f"secao ausente na saida: {titulo}"


def test_le_ultimo_sucesso_e_calcula_dias(tmp_path):
    logs = _criar_logs(tmp_path)
    ha_tres_dias = date.today() - timedelta(days=3)
    (logs / ".last_success_date").write_text(f"{ha_tres_dias:%Y%m%d}", encoding="utf-8")
    _, saida = _rodar(tmp_path)
    assert f"{ha_tres_dias:%Y%m%d}" in saida
    assert "3 dias" in saida


def test_lista_dia_com_exit_zero_e_dia_com_exit_um(tmp_path):
    logs = _criar_logs(tmp_path)
    ontem = date.today() - timedelta(days=1)
    anteontem = date.today() - timedelta(days=2)
    _criar_log_dia(
        logs,
        1,
        [
            f"[{ontem:%Y-%m-%d} 03:00:05] [INFO] [ConcursoBot]: 📊 Ciclo finalizado: 2 novos e 5 atualizações enviadas.",
            f"[{ontem:%Y-%m-%d} 03:10:00] Finalizado com codigo 0",
        ],
    )
    _criar_log_dia(
        logs,
        2,
        [
            f"[{anteontem:%Y-%m-%d} 03:00:05] [ERROR] [GranScraper]: Falha ao abrir a porta.",
            f"[{anteontem:%Y-%m-%d} 03:10:00] Finalizado com codigo 1",
        ],
    )
    _, saida = _rodar(tmp_path)
    assert f"{ontem:%Y%m%d} exit=0" in saida
    assert f"{anteontem:%Y%m%d} exit=1" in saida
    assert f"{ontem:%Y%m%d} exit=0" in saida and "novos=2" in saida
    assert "atualizacoes=5" in saida


def test_dia_sem_log_aparece_como_ausente(tmp_path):
    logs = _criar_logs(tmp_path)
    buraco = date.today() - timedelta(days=2)
    _criar_log_dia(logs, 3, ["[2026-01-01 03:10:00] Finalizado com codigo 0"])
    _criar_log_dia(logs, 1, ["[2026-01-01 03:10:00] Finalizado com codigo 0"])
    _, saida = _rodar(tmp_path)
    assert f"{buraco:%Y%m%d} ausente" in saida


def test_agrupa_erros_repetidos_com_contagem(tmp_path):
    logs = _criar_logs(tmp_path)
    linhas = [
        _linha_erro(f"Falha ao processar {n} blocos do blog do Gran")
        for n in (3, 5, 7, 9, 11)
    ]
    linhas.append("[2026-01-01 03:10:00] Finalizado com codigo 1")
    _criar_log_dia(logs, 1, linhas)
    _, saida = _rodar(tmp_path)
    assert "5 Falha ao processar N blocos do blog do Gran" in saida


def test_conta_linhas_do_banco_por_area_e_fonte(tmp_path):
    (tmp_path / "data").mkdir()
    banco = tmp_path / "data" / "concursos.db"
    conexao = sqlite3.connect(banco)
    conexao.execute(
        "CREATE TABLE editais ("
        " id INTEGER PRIMARY KEY,"
        " area TEXT NOT NULL,"
        " fonte TEXT,"
        " estado_usuario TEXT NOT NULL DEFAULT 'ativo',"
        " ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    conexao.executemany(
        "INSERT INTO editais (area, fonte, estado_usuario, ultima_atualizacao)"
        " VALUES (?, ?, 'ativo', '2026-06-10 03:00:00')",
        [("TI", "gran"), ("TI", "gran"), ("EDUCACAO", "pci")],
    )
    conexao.commit()
    conexao.close()

    _criar_logs(tmp_path)
    _, saida = _rodar(tmp_path)
    assert "total de linhas: 3" in saida
    assert "TI=2" in saida
    assert "EDUCACAO=1" in saida
    assert "gran=2" in saida
    assert "pci=1" in saida


def test_nao_imprime_token(tmp_path):
    (tmp_path / ".env").write_text(
        "TELEGRAM_TOKEN=123456:ABCDEF\nTELEGRAM_CHAT_ID=987654321\n",
        encoding="utf-8",
    )
    _criar_logs(tmp_path)
    codigo, saida = _rodar(tmp_path)
    assert codigo == 0
    assert "123456" not in saida
    assert "TELEGRAM_TOKEN=<omitido>" in saida
    assert "987654321" not in saida
    assert "TELEGRAM_CHAT_ID=<omitido>" in saida


def test_sem_logs_nem_banco_nao_quebra(tmp_path):
    codigo, saida = _rodar(tmp_path)
    assert codigo == 0
    assert "ausente" in saida


def test_nao_escreve_nada(tmp_path):
    logs = _criar_logs(tmp_path)
    _criar_log_dia(logs, 1, ["[2026-01-01 03:10:00] Finalizado com codigo 0"])
    (tmp_path / ".env").write_text("TELEGRAM_TOKEN=123456:ABCDEF\n", encoding="utf-8")

    def _arvore() -> list[str]:
        return sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))

    antes = _arvore()
    codigo, _ = _rodar(tmp_path)
    depois = _arvore()
    assert codigo == 0
    assert antes == depois


def test_conta_chave_ausente_por_dia(tmp_path):
    """Secao de credencial: o marcador 🔑 de chave recusada aparece por dia."""
    logs = _criar_logs(tmp_path)
    ontem = date.today() - timedelta(days=1)
    _criar_log_dia(
        logs,
        1,
        [
            f"[{ontem:%Y-%m-%d} 03:05:00] [ERROR] [LangChainUnit]: 🔑 Credencial recusada pela IA. Pulando as demais chamadas desta rodada.",
            f"[{ontem:%Y-%m-%d} 03:06:00] [ERROR] [ConcursoBot]: 🔑 [TI] LLM recusou a credencial; 4 item(ns) ficaram de fora.",
            f"[{ontem:%Y-%m-%d} 03:10:00] Finalizado com codigo 1",
        ],
    )
    _, saida = _rodar(tmp_path)
    assert f"{ontem:%Y%m%d}: 2" in saida


def test_config_efetiva_mostra_areas_e_omite_segredo_do_json(tmp_path):
    """Guarda: no MONITOR_TARGETS_JSON, token e chat_id nunca saem com valor."""
    _criar_logs(tmp_path)
    alvos = (
        '[{"area": "TI", "display_name": "Tecnologia", "url": "https://exemplo.blog",'
        ' "token": "654321:XYZTOKEN", "chat_ids": ["111222333"],'
        ' "pci_slugs": ["desenvolvimento-de-sistemas"], "pci_nacional": true},'
        ' {"area": "EDUCACAO", "url": "https://exemplo.blog/edu", "pci_nacional": false}]'
    )
    _, saida = _rodar(tmp_path, env_extra={"MONITOR_TARGETS_JSON": alvos})
    assert "area TI (Tecnologia)" in saida
    assert "porta gran: ligada" in saida
    assert "porta pci_cargos: ligada (1 slug(s))" in saida
    assert "porta pci_nacional: ligada" in saida
    assert "area EDUCACAO" in saida
    assert "porta pci_nacional: desligada" in saida
    assert "XYZTOKEN" not in saida
    assert "111222333" not in saida
    assert "token: <omitido>" in saida
    assert "chat_ids: <omitido> (1)" in saida
