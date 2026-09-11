"""Configuracao global do pytest — adiciona a raiz do projeto ao sys.path."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def estado_json_isolado(mocker, tmp_path):
    """Manda todo estado em JSON para um tmp por teste.

    `src/utils/memoria_json.py` grava em `data/` ancorado no repo. Sem isso, a
    suite escreve saude das fontes e descartes de verdade no estado de
    producao — e um teste que finge "45 blocos identicos ha 40 dias" passaria a
    valer para o bot que roda as 03h.
    """
    from src.utils import memoria_json

    mocker.patch.object(memoria_json, "DATA_DIR", str(tmp_path / "estado"))
