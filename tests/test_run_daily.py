"""Testes do gate de espera do catch-up horario no scripts/run_daily.sh.

Costura: a execucao do proprio script por subprocess, com REPO_DIR apontando
para uma arvore falsa em tmp_path (no molde de tests/test_diagnostico_producao.py,
que ja testa script de shell neste repo). Pega a decisao de rodar ou nao, o
codigo de saida e o que o tick escreve no log. Nao pega o main.py, que e
dublado por um executavel falso dentro da arvore; nem o flock de verdade,
que o Git Bash do Windows nao tem (o duble so faz o comando existir).

O oracle sao instantes literais escritos a mao pelo teste, relativos a um
agora fixado na hora da montada da arvore — nunca algo recalculado do jeito
que o script calcula.
"""

import os
import shutil
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "run_daily.sh"

BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(
    BASH is None,
    reason="bash nao disponivel nesta maquina (suite precisa ficar verde no Windows sem Git Bash)",
)

MARCA_ESPERA = "logs/.retry_nao_antes"
MARCA_SUCESSO = "logs/.last_success_date"


def _caminho_bash(caminho: Path) -> str:
    """Converte um caminho do Windows para a forma que o bash do Git aceita."""
    return str(caminho).replace("\\", "/")


def _instante(deslocamento: timedelta) -> str:
    """Instante ISO literal, sem fuso explicito (vale fuso local, ADR-0004)."""
    return (datetime.now() + deslocamento).isoformat(timespec="seconds")


def _instante_com_fuso(deslocamento: timedelta) -> str:
    """Instante ISO literal com o offset do fuso local declarado no fim."""
    return (datetime.now().astimezone() + deslocamento).isoformat(timespec="seconds")


def _arvore_falsa(tmp_path: Path) -> Path:
    """Monta logs/, o main.py dublado e um flock de mentira; devolve a raiz.

    O flock e ferramenta de sistema (fronteira), ausente no Git Bash do
    Windows; sem ele o script sai antes de main em todo tick que roda.
    """
    (tmp_path / "logs").mkdir()
    falso_python = tmp_path / ".venv" / "bin" / "python"
    falso_python.parent.mkdir(parents=True)
    falso_python.write_text(
        "#!/usr/bin/env bash\n"
        "printf 'chamado: %s\\n' \"$*\" >> \"$REPO_DIR/logs/main_rodou.log\"\n"
        "exit 0\n",
        encoding="utf-8",
    )
    falso_flock = tmp_path / "bin" / "flock"
    falso_flock.parent.mkdir(parents=True)
    falso_flock.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    falso_python.chmod(0o755)
    falso_flock.chmod(0o755)
    return tmp_path


def _rodar(raiz: Path) -> tuple[int, str]:
    """Roda o script apontando para a arvore falsa e devolve (codigo, saida)."""
    env = os.environ.copy()
    env["REPO_DIR"] = _caminho_bash(raiz)
    # O flock de mentira fica no fim do PATH: o script recoloca os diretorios
    # de sistema na frente, e o flock real do Linux continuaria ganhando lá.
    env["PATH"] = _caminho_bash(raiz / "bin") + os.pathsep + env.get("PATH", "")
    # A maquina de dev nao pode injetar segredo nem alvo de producao no teste.
    env["MONITOR_ENV_FILE"] = _caminho_bash(raiz / "monitor.env.inexistente")
    env.pop("MONITOR_TARGETS_JSON", None)
    proc = subprocess.run(
        [BASH, _caminho_bash(SCRIPT)],
        capture_output=True,
        cwd=raiz,
        env=env,
        timeout=120,
    )
    saida = proc.stdout.decode("utf-8", errors="replace") + proc.stderr.decode(
        "utf-8", errors="replace"
    )
    return proc.returncode, saida


def _main_rodou(raiz: Path) -> bool:
    return (raiz / "logs" / "main_rodou.log").exists()


def test_marcador_de_espera_no_futuro_sai_sem_rodar(tmp_path):
    raiz = _arvore_falsa(tmp_path)
    (raiz / MARCA_ESPERA).write_text(_instante(timedelta(hours=1)) + "\n", encoding="utf-8")
    codigo, _ = _rodar(raiz)
    assert codigo == 0
    assert not _main_rodou(raiz)
    # Antes do flock: o tick de espera nem chega a criar o arquivo de lock,
    # igual ao caminho do marcador do dia.
    assert not (raiz / "logs" / ".run_daily.lock").exists()


def test_marcador_de_espera_no_passado_roda(tmp_path):
    raiz = _arvore_falsa(tmp_path)
    (raiz / MARCA_ESPERA).write_text(_instante(timedelta(hours=-1)) + "\n", encoding="utf-8")
    codigo, _ = _rodar(raiz)
    assert codigo == 0
    assert _main_rodou(raiz)
    assert "main.py" in (raiz / "logs" / "main_rodou.log").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "conteudo",
    ["", "isto nao e um instante", "2026-13-45T99:99:99"],
    ids=["vazio", "lixo", "data_invalida"],
)
def test_marcador_de_espera_ilegivel_roda(tmp_path, conteudo):
    """Fail-open: marcador vazio, ilegivel ou com data invalida nao impede."""
    raiz = _arvore_falsa(tmp_path)
    (raiz / MARCA_ESPERA).write_text(conteudo, encoding="utf-8")
    codigo, _ = _rodar(raiz)
    assert codigo == 0
    assert _main_rodou(raiz)


def test_marcador_de_espera_ausente_roda(tmp_path):
    raiz = _arvore_falsa(tmp_path)
    codigo, _ = _rodar(raiz)
    assert codigo == 0
    assert _main_rodou(raiz)


def test_marcador_de_espera_nao_marca_sucesso_do_dia(tmp_path):
    """O tick de espera nao conta como varredura: o marcador do dia fica como estava."""
    raiz = _arvore_falsa(tmp_path)
    ha_dois_dias = (date.today() - timedelta(days=2)).strftime("%Y%m%d")
    (raiz / MARCA_SUCESSO).write_text(ha_dois_dias, encoding="utf-8")
    (raiz / MARCA_ESPERA).write_text(_instante(timedelta(hours=1)) + "\n", encoding="utf-8")
    codigo, _ = _rodar(raiz)
    assert codigo == 0
    assert not _main_rodou(raiz)
    assert (raiz / MARCA_SUCESSO).read_text(encoding="utf-8") == ha_dois_dias


def test_tick_de_espera_adiciona_no_maximo_uma_linha_por_rodada(tmp_path):
    """A saida quieta nao enche o log: um tick de espera soma no maximo uma linha."""
    raiz = _arvore_falsa(tmp_path)
    (raiz / MARCA_ESPERA).write_text(_instante(timedelta(hours=1)) + "\n", encoding="utf-8")
    _rodar(raiz)
    log_hoje = raiz / "logs" / f"run_{date.today():%Y%m%d}.log"
    linhas = log_hoje.read_text(encoding="utf-8").splitlines()
    assert len(linhas) <= 1


def test_marcador_com_fuso_explicito_no_futuro_tambem_segura_o_tick(tmp_path):
    """Instante com offset declarado (ex.: -03:00) e honrado, nao ignorado."""
    raiz = _arvore_falsa(tmp_path)
    (raiz / MARCA_ESPERA).write_text(_instante_com_fuso(timedelta(hours=1)) + "\n", encoding="utf-8")
    codigo, _ = _rodar(raiz)
    assert codigo == 0
    assert not _main_rodou(raiz)
