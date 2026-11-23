"""Testes do resumo semanal de filtrados: montagem do texto e marcador de semana.

Oraculo: listas de linhas escritas a mao e afirmacoes por substring e contagem,
nao comparacao com blob inteiro. As datas do marcador vêm do calendario ISO,
calculado a mao: 2026-11-23 e segunda da semana 48; 2026-12-28 e 2027-01-03
sao segunda e domingo da semana 53 do ano ISO 2026.
"""

import ast
from datetime import date
from pathlib import Path

from src.core import resumo_filtrados
from src.core.resumo_filtrados import marcador_da_semana, montar


def _linha(
    nome: str = "Prefeitura de X",
    uf: str = "PI",
    teto: float = 10000.0,
    motivo: str = "abaixo_do_corte",
) -> dict:
    return {"nome": nome, "uf": uf, "salario_teto": teto, "motivo_filtro": motivo}


def test_lista_vazia_devolve_none():
    assert montar([], "TI") is None


def test_traz_contagem_total():
    linhas = [_linha(nome=f"Orgao {n:02d}") for n in range(1, 6)]
    texto = montar(linhas, "TI")
    assert "<b>5</b>" in texto


def test_traz_contagem_por_motivo_em_ordem_decrescente():
    linhas = [_linha(nome=f"Orgao A{m}") for m in range(3)]
    linhas.append(_linha(nome="Orgao B", motivo="municipal_inflado"))
    texto = montar(linhas, "TI")
    assert texto.index("abaixo do corte") < texto.index("teto de outro cargo")


def test_linha_traz_orgao_uf_teto_e_motivo():
    linha = _linha(
        nome="Prefeitura de Canto do Buriti",
        uf="PI",
        teto=16210.0,
        motivo="municipal_inflado",
    )
    texto = montar([linha], "TI")
    for pedaco in (
        "Prefeitura de Canto do Buriti",
        "PI",
        "R$ 16.210,00",
        "teto de outro cargo",
    ):
        assert pedaco in texto


def test_teto_none_sai_como_nao_lido():
    texto = montar([_linha(teto=None)], "TI")
    assert "teto nao lido" in texto
    assert "R$ 0,00" not in texto
    assert "None" not in texto


def test_uf_none_sai_como_nacional():
    texto = montar([_linha(uf=None)], "TI")
    assert "Nacional" in texto


def test_motivo_desconhecido_nao_levanta():
    texto = montar([_linha(motivo="motivo_que_ninguem_previu")], "TI")
    assert "motivo_que_ninguem_previu" in texto


def test_formata_teto_no_padrao_brasileiro():
    linhas = [
        _linha(nome="Orgao medio", teto=8628.87),
        _linha(nome="Orgao grande", teto=1000000.0),
    ]
    texto = montar(linhas, "TI")
    assert "R$ 8.628,87" in texto
    assert "R$ 1.000.000,00" in texto


def test_corta_em_trinta_e_diz_quantas_faltam():
    linhas = [_linha(nome=f"Orgao {n:02d}") for n in range(1, 43)]
    texto = montar(linhas, "TI")
    assert "Orgao 30" in texto
    assert "Orgao 31" not in texto
    assert "e mais 12" in texto
    assert "<b>42</b>" in texto


def test_limite_customizado():
    linhas = [_linha(nome=f"Orgao {n:02d}") for n in range(1, 6)]
    texto = montar(linhas, "TI", limite=2)
    assert "Orgao 02" in texto
    assert "Orgao 03" not in texto
    assert "e mais 3" in texto


def test_escapa_html_do_nome():
    texto = montar([_linha(nome="Prefeitura de A & B <teste>")], "TI")
    assert "A &amp; B" in texto
    assert "&lt;teste&gt;" in texto
    assert "<teste>" not in texto


def test_nome_da_area_aparece():
    texto = montar([_linha()], "Tecnologia da Informacao")
    assert "Tecnologia da Informacao" in texto


def test_secoes_na_ordem_do_aceite():
    linhas = [
        _linha(nome="Orgao 01"),
        _linha(nome="Orgao 02", motivo="municipal_inflado"),
    ]
    texto = montar(linhas, "Tecnologia da Informacao")
    ordem = [
        texto.index("Tecnologia da Informacao"),
        texto.index("<b>2</b>"),
        texto.index("abaixo do corte"),
        texto.index("Orgao 01"),
    ]
    assert ordem == sorted(ordem)


def test_marcador_da_semana_e_estavel_na_mesma_semana():
    # 2026-11-23 e segunda; 2026-11-29 e domingo da mesma semana ISO (48).
    assert marcador_da_semana(date(2026, 11, 23)) == marcador_da_semana(
        date(2026, 11, 29)
    )


def test_marcador_da_semana_muda_na_semana_seguinte():
    # 2026-11-29 e domingo da semana 48; 2026-11-30 ja e segunda da 49.
    assert marcador_da_semana(date(2026, 11, 29)) != marcador_da_semana(
        date(2026, 11, 30)
    )


def test_marcador_da_semana_na_virada_do_ano():
    # Calendario ISO: 2027-01-03 e domingo da semana 53 do ano ISO 2026.
    assert marcador_da_semana(date(2026, 12, 28)) == "2026-S53"
    assert marcador_da_semana(date(2027, 1, 3)) == "2026-S53"


def test_modulo_e_puro_sem_banco_rede_ou_bot():
    fonte = Path(resumo_filtrados.__file__).read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(alias.name for alias in no.names)
        elif isinstance(no, ast.ImportFrom):
            if no.level:  # import relativo: "from . import bot"
                importados.update(alias.name for alias in no.names)
            else:
                base = (no.module or "") + "."
                importados.update(base + alias.name for alias in no.names)
    proibidos = {"sqlite3", "requests", "bot", "database", "src.core", "src.database"}
    assert not importados & proibidos, f"imports proibidos: {importados & proibidos}"
