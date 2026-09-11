"""Estado pequeno que precisa sobreviver entre varreduras, em JSON.

O banco guarda editais. Sobrou uma classe de estado que nao e edital e nao
justifica tabela: "quando esta fonte mudou pela ultima vez" e "que link ja
foi julgado fora da area". Sao dicionarios de poucos KB, lidos e escritos uma
vez por rodada.

Regra de ouro deste modulo: **nunca derrubar a varredura**. Arquivo corrompido,
disco cheio ou permissao negada viram log e dicionario vazio — o pior caso e o
bot reavaliar algo que ja tinha avaliado, nunca parar de varrer.
"""

import json
import logging
import os

REPO_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(REPO_DIR, "data")

logger = logging.getLogger(__name__)


def caminho(nome: str) -> str:
    """Caminho do arquivo de estado `nome`, ancorado na raiz do repo."""
    return os.path.join(DATA_DIR, f"{nome}.json")


def carregar(nome: str) -> dict:
    """Le o dicionario salvo em `nome`. Devolve {} se nao existe ou quebrou."""
    arquivo = caminho(nome)
    try:
        with open(arquivo, encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Estado {nome!r} ilegivel ({e}); comecando do zero.")
        return {}


def salvar(nome: str, dados: dict) -> None:
    """Grava `dados` em `nome`, de forma atomica. Falha e logada, nao levantada."""
    arquivo = caminho(nome)
    temporario = f"{arquivo}.tmp"
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(temporario, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2, sort_keys=True)
        # Troca atomica: uma varredura interrompida no meio da escrita nao pode
        # deixar um JSON pela metade, que na proxima rodada viraria estado vazio.
        os.replace(temporario, arquivo)
    except OSError as e:
        logger.warning(f"Nao consegui gravar o estado {nome!r}: {e}")
