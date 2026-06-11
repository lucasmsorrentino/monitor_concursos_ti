"""Dedupa a tabela `editais` colapsando variacoes do mesmo edital.

Identifica duplicatas agrupando por `(area, link)` quando `link` e especifico
(nao coincide com as URLs-indice conhecidas do scraper). Dentro de cada grupo,
mantem a linha com `ultima_atualizacao` mais recente e remove as demais.

Linhas sem link especifico ficam intocadas — a PK `(area, nome)` ja as protege.

Uso:
    python scripts/dedupe_db.py                    # dry-run
    python scripts/dedupe_db.py --apply            # aplica
"""
import argparse
import os
import sqlite3
import sys

URL_INDICES_CONHECIDAS = {
    "https://blog.grancursosonline.com.br/concursos-ti/",
    "https://blog.grancursosonline.com.br/concursos-educacao/",
    "https://blog.grancursosonline.com.br/outros/",
}


def _e_link_indice(link: str) -> bool:
    if not link:
        return True
    return link.rstrip("/") + "/" in {u.rstrip("/") + "/" for u in URL_INDICES_CONHECIDAS}


def dedupe(db_path: str, apply: bool) -> int:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT area, nome, status, link, ultima_atualizacao
          FROM editais
         ORDER BY area, link, ultima_atualizacao DESC
        """
    )
    linhas = cur.fetchall()

    # Agrupa por (area, link_canonico). Linhas sem link especifico sao ignoradas.
    grupos: dict[tuple[str, str], list[tuple]] = {}
    for area, nome, status, link, ts in linhas:
        if _e_link_indice(link):
            continue
        chave = (area, link.rstrip("/"))
        grupos.setdefault(chave, []).append((nome, status, link, ts))

    total_remover = 0
    for (area, link_canonico), entradas in grupos.items():
        if len(entradas) < 2:
            continue
        # Primeira entrada e a mais recente (ordenamos por ts DESC).
        vencedor = entradas[0]
        perdedores = entradas[1:]
        print(f"[{area}] {link_canonico}")
        print(f"   mantem: {vencedor[0]} ({vencedor[3]})")
        for nome_p, _, _, ts_p in perdedores:
            print(f"   remove: {nome_p} ({ts_p})")
            total_remover += 1
            if apply:
                cur.execute(
                    "DELETE FROM editais WHERE area = ? AND nome = ? AND ultima_atualizacao = ?",
                    (area, nome_p, ts_p),
                )

    if apply:
        conn.commit()
        print(f"\n[OK] {total_remover} duplicatas removidas.")
    else:
        print(f"\n(dry-run) {total_remover} duplicatas seriam removidas. Rode com --apply para confirmar.")

    conn.close()
    return total_remover


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/concursos.db")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"[ERRO] DB nao encontrado: {args.db}")
        return 1

    dedupe(args.db, args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
