#!/usr/bin/env python3
"""Exporta o que o bot JA conhece para o Hermes (skill concursos-ti-brasil).

O Hermes roda em container e so enxerga /opt/data (= ~/.hermes). Este script
e a unica ponte: despeja a tabela `editais` num JSON dentro de ~/.hermes, de
onde o Hermes le pra saber o que NAO precisa re-descobrir.

Uma so direcao: bot -> Hermes. Nunca le nada do Hermes, nunca falha o run do
bot (o run_daily.sh chama com `|| true`). Stdlib pura, sem dependencias.
"""

import json
import os
import re
import sqlite3
import sys
import unicodedata
from datetime import datetime, timezone

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_DIR, "data", "concursos.db")
OUT_DIR = os.path.expanduser("~/.hermes/concursos-handoff")
OUT_PATH = os.path.join(OUT_DIR, "bot_known.json")

# Palavras sem valor de identificacao de orgao (viram ruido no match por token).
STOP = {
    "concurso", "de", "da", "do", "dos", "das", "e", "a", "o", "para",
    "analista", "tecnico", "em", "no", "na",
}


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def _norm(nome: str) -> str:
    s = _strip_accents(nome).lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(nome: str) -> list[str]:
    return [t for t in _norm(nome).split() if len(t) >= 2 and t not in STOP]


def main() -> int:
    if not os.path.exists(DB_PATH):
        print(f"[export_known] DB nao encontrado: {DB_PATH}", file=sys.stderr)
        return 1

    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT area, nome, fase, estado_usuario, link, data_fim_inscricao "
        "FROM editais ORDER BY area, nome"
    ).fetchall()
    con.close()

    by_area: dict[str, list[dict]] = {}
    for area, nome, fase, estado, link, data_fim in rows:
        by_area.setdefault(area, []).append(
            {
                "nome": nome,
                "nome_norm": _norm(nome),
                "tokens": _tokens(nome),
                "fase": fase,
                "estado": estado,
                "link": link,
                "data_fim_inscricao": data_fim,
            }
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "monitor_concursos_ti (blog Gran Cursos Online)",
        "note": (
            "Lista do que o bot ja monitora. O Hermes usa pra so reportar o que "
            "esta FORA daqui (descoberta complementar via PCI) e pra registrar "
            "orgaos/fontes que o bot nao pega em gaps.md."
        ),
        "areas": {a: {"count": len(v), "known": v} for a, v in by_area.items()},
        "total": len(rows),
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    tmp = OUT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT_PATH)
    print(f"[export_known] {len(rows)} editais -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
