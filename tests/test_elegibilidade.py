"""Elegibilidade: as nove regras da SPEC-001 secao 4.2, primeira que casa vence.

O esperado de cada caso foi transcrito a mao da tabela da spec; nada aqui e
recalculado pelo codigo sob teste.
"""

import dataclasses
import itertools

import pytest

from src.core.elegibilidade import (
    SELO_NAO_VERIFICADO,
    Candidato,
    Decisao,
    Politica,
    decidir,
)

# Conjunto fechado de motivos, copiado da SPEC-001 secao 3.4.
MOTIVOS_DA_SPEC = {
    "seguindo",
    "filtro_desligado",
    "nao_verificado",
    "sul",
    "federal",
    "abaixo_do_corte",
    "municipal_inflado",
    "sem_evidencia",
    "acima_do_corte",
}

# Politica da area TI medida em 22/11/2026: corte de R$ 10.000, limite de 10 cargos.
ATIVA = Politica(modo="ativo", corte_fora_sul=10000.0, cargos_total_inflado=10)


def _cand(uf="MG", regiao="SUDESTE", esfera="estadual", teto=12000.0,
          cargos_total=3, seguindo=False):
    return Candidato(uf=uf, regiao=regiao, esfera=esfera, teto=teto,
                     cargos_total=cargos_total, seguindo=seguindo)


# O candidato mais filtravel: fora do Sul, municipal, teto baixo e inflado.
MAIS_FILTRAVEL = _cand(uf="MG", regiao="SUDESTE", esfera="municipal",
                       teto=2000.0, cargos_total=86)


# --- contrato -------------------------------------------------------------

def test_politica_tem_os_padroes_da_spec():
    p = Politica()
    assert p.modo == "desligado"
    assert p.corte_fora_sul == 0.0
    assert p.ufs_sem_corte == ("PR", "SC", "RS")
    assert p.esferas_sem_corte == ("federal",)
    assert p.cargos_total_inflado == 10


def test_tipos_do_contrato_sao_congelados():
    for obj in (_cand(), ATIVA, Decisao(entra=True, motivo="sul")):
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.__setattr__(dataclasses.fields(obj)[0].name, None)


def test_candidato_comeca_sem_estrela_e_decisao_sem_selo():
    assert _cand().seguindo is False
    assert Decisao(entra=True, motivo="sul").selo is None


def test_selo_e_o_texto_da_spec():
    assert SELO_NAO_VERIFICADO == "⚠️ salario nao verificado"


# --- regra 0: seguindo ----------------------------------------------------

def test_seguindo_entra_mesmo_abaixo_do_corte():
    c = _cand(uf="MG", regiao="SUDESTE", esfera="estadual", teto=3000.0,
              seguindo=True)
    assert decidir(c, ATIVA) == Decisao(entra=True, motivo="seguindo")


def test_seguindo_vence_municipal_inflado():
    c = dataclasses.replace(MAIS_FILTRAVEL, seguindo=True)
    assert decidir(c, ATIVA) == Decisao(entra=True, motivo="seguindo")


# --- regra 1: modo --------------------------------------------------------

def test_modo_desligado_deixa_tudo_entrar():
    p = Politica(modo="desligado", corte_fora_sul=10000.0)
    assert decidir(MAIS_FILTRAVEL, p) == Decisao(entra=True,
                                                 motivo="filtro_desligado")


def test_politica_padrao_deixa_tudo_entrar():
    assert decidir(MAIS_FILTRAVEL, Politica()).motivo == "filtro_desligado"


@pytest.mark.parametrize("modo", ["ativo ", "sombra", "", "ATIVO", None])
def test_modo_invalido_se_comporta_como_desligado(modo):
    p = Politica(modo=modo, corte_fora_sul=10000.0)
    assert decidir(MAIS_FILTRAVEL, p) == Decisao(entra=True,
                                                 motivo="filtro_desligado")


# --- regra 2: uf e regiao desconhecidas -----------------------------------

def test_uf_e_regiao_desconhecidas_entram_com_selo():
    c = _cand(uf=None, regiao=None, esfera="municipal", teto=2000.0,
              cargos_total=86)
    assert decidir(c, ATIVA) == Decisao(entra=True, motivo="nao_verificado",
                                        selo=SELO_NAO_VERIFICADO)


# --- regra 3: Sul ---------------------------------------------------------

@pytest.mark.parametrize("uf", ["PR", "SC", "RS"])
def test_uf_do_sul_entra_sem_olhar_teto(uf):
    c = _cand(uf=uf, regiao="SUL", esfera="estadual", teto=2000.0)
    assert decidir(c, ATIVA) == Decisao(entra=True, motivo="sul")


def test_uf_do_sul_entra_mesmo_com_regiao_desconhecida():
    c = _cand(uf="RS", regiao=None, esfera="municipal", teto=2000.0)
    assert decidir(c, ATIVA).motivo == "sul"


def test_regiao_sul_entra_quando_uf_e_none():
    c = _cand(uf=None, regiao="SUL", esfera="municipal", teto=2000.0)
    assert decidir(c, ATIVA) == Decisao(entra=True, motivo="sul")


@pytest.mark.parametrize("regiao", ["sul", "Sul", "SÚL", "súl", " Sul "])
def test_regiao_sul_casa_sem_caixa_nem_acento(regiao):
    c = _cand(uf=None, regiao=regiao, esfera="municipal", teto=2000.0)
    assert decidir(c, ATIVA).motivo == "sul"


def test_uf_minuscula_casa_o_sul():
    c = _cand(uf="pr", regiao=None, esfera="municipal", teto=2000.0)
    assert decidir(c, ATIVA) == Decisao(entra=True, motivo="sul")


def test_ufs_sem_corte_da_politica_em_minuscula_tambem_casam():
    p = dataclasses.replace(ATIVA, ufs_sem_corte=("pr",))
    c = _cand(uf="PR", regiao=None, esfera="municipal", teto=2000.0)
    assert decidir(c, p).motivo == "sul"


def test_ufs_sem_corte_vem_da_politica():
    p = dataclasses.replace(ATIVA, ufs_sem_corte=("SP",))
    sp = _cand(uf="SP", regiao="SUDESTE", esfera="estadual", teto=2000.0)
    pr = _cand(uf="PR", regiao="SUDESTE", esfera="estadual", teto=2000.0)
    assert decidir(sp, p).motivo == "sul"
    assert decidir(pr, p).motivo == "abaixo_do_corte"


def test_sul_vence_municipal_inflado():
    # Prefeitura de Ararangua (SC) da fixture: 55 cargos.
    c = _cand(uf="SC", regiao="SUL", esfera="municipal", teto=15000.0,
              cargos_total=55)
    assert decidir(c, ATIVA) == Decisao(entra=True, motivo="sul")


def test_nacional_nao_e_sul():
    c = _cand(uf=None, regiao="NACIONAL", esfera="federal", teto=5000.0)
    assert decidir(c, ATIVA) == Decisao(entra=True, motivo="federal")


# --- regra 4: federal -----------------------------------------------------

def test_federal_entra_mesmo_abaixo_do_corte():
    # UFMS da fixture.
    c = _cand(uf="MS", regiao="CENTRO-OESTE", esfera="federal", teto=5215.39)
    assert decidir(c, ATIVA) == Decisao(entra=True, motivo="federal")


def test_federal_vence_abaixo_do_corte():
    c = _cand(uf="MG", esfera="federal", teto=1000.0, cargos_total=1)
    assert decidir(c, ATIVA).motivo == "federal"


def test_esfera_maiuscula_casa_federal():
    c = _cand(uf="MG", esfera="FEDERAL", teto=1000.0)
    assert decidir(c, ATIVA).motivo == "federal"


def test_conselho_profissional_nao_e_federal():
    c = _cand(uf="MG", esfera="conselho_profissional", teto=5000.0)
    assert decidir(c, ATIVA) == Decisao(entra=False, motivo="abaixo_do_corte")


# --- regra 5: abaixo do corte ---------------------------------------------

def test_abaixo_do_corte_e_filtrado():
    c = _cand(uf="MG", regiao="SUDESTE", esfera="municipal", teto=8628.87,
              cargos_total=3)
    assert decidir(c, ATIVA) == Decisao(entra=False, motivo="abaixo_do_corte")


def test_teto_exatamente_no_corte_entra():
    # Prefeitura de Luislandia: teto R$ 10.000.
    c = _cand(uf="MG", regiao="SUDESTE", esfera="municipal", teto=10000.0,
              cargos_total=3)
    assert decidir(c, ATIVA) == Decisao(entra=True, motivo="acima_do_corte")


def test_abaixo_do_corte_vence_municipal_inflado():
    c = _cand(uf="MG", esfera="municipal", teto=9000.0, cargos_total=86)
    assert decidir(c, ATIVA).motivo == "abaixo_do_corte"


# --- regra 6: municipal inflado -------------------------------------------

def test_municipal_inflado_e_filtrado():
    # Guaratingueta, medida de 22/11/2026.
    c = _cand(uf="SP", regiao="SUDESTE", esfera="municipal", teto=18540.71,
              cargos_total=86)
    assert decidir(c, ATIVA) == Decisao(entra=False, motivo="municipal_inflado")


def test_municipal_com_poucos_cargos_entra():
    c = _cand(uf="SP", regiao="SUDESTE", esfera="municipal", teto=18540.71,
              cargos_total=4)
    assert decidir(c, ATIVA) == Decisao(entra=True, motivo="acima_do_corte")


def test_cargos_total_no_limite_entra():
    c = _cand(uf="SP", esfera="municipal", teto=18540.71, cargos_total=10)
    assert decidir(c, ATIVA) == Decisao(entra=True, motivo="acima_do_corte")


def test_cargos_total_um_acima_do_limite_e_filtrado():
    c = _cand(uf="SP", esfera="municipal", teto=18540.71, cargos_total=11)
    assert decidir(c, ATIVA).motivo == "municipal_inflado"


def test_esfera_municipal_em_maiuscula_infla():
    c = _cand(uf="SP", esfera="Municipal", teto=18540.71, cargos_total=86)
    assert decidir(c, ATIVA).motivo == "municipal_inflado"


def test_inflado_nao_se_aplica_fora_do_municipal():
    # SECITECI da fixture.
    c = _cand(uf="MT", regiao="CENTRO-OESTE", esfera="estadual",
              teto=12937.29, cargos_total=80)
    assert decidir(c, ATIVA) == Decisao(entra=True, motivo="acima_do_corte")


def test_teto_desconhecido_em_municipal_inflado_e_filtrado():
    c = _cand(uf="SP", esfera="municipal", teto=None, cargos_total=50)
    assert decidir(c, ATIVA) == Decisao(entra=False, motivo="municipal_inflado")


def test_cargos_total_none_nao_infla():
    c = _cand(uf="SP", esfera="municipal", teto=18540.71, cargos_total=None)
    assert decidir(c, ATIVA) == Decisao(entra=True, motivo="acima_do_corte")


# --- regra 7: sem evidencia -----------------------------------------------

def test_teto_desconhecido_entra_com_selo():
    c = _cand(uf="SP", regiao="SUDESTE", esfera="estadual", teto=None,
              cargos_total=80)
    assert decidir(c, ATIVA) == Decisao(entra=True, motivo="sem_evidencia",
                                        selo=SELO_NAO_VERIFICADO)


def test_esfera_desconhecida_e_teto_desconhecido_entra_com_selo():
    c = _cand(uf="SP", esfera=None, teto=None, cargos_total=86)
    assert decidir(c, ATIVA) == Decisao(entra=True, motivo="sem_evidencia",
                                        selo=SELO_NAO_VERIFICADO)


# --- regra 8: resto -------------------------------------------------------

def test_teto_acima_do_corte_fora_do_sul_entra():
    c = _cand(uf="SP", regiao="SUDESTE", esfera="estadual", teto=15000.0)
    assert decidir(c, ATIVA) == Decisao(entra=True, motivo="acima_do_corte")


def test_regiao_conhecida_e_uf_none_fora_do_sul_segue_as_regras():
    c = _cand(uf=None, regiao="NORDESTE", esfera="estadual", teto=5000.0)
    assert decidir(c, ATIVA).motivo == "abaixo_do_corte"


# --- matriz ---------------------------------------------------------------

def _matriz():
    ufs = [None, "PR", "pr", "MG", "SP"]
    regioes = [None, "SUL", "Sul", "NACIONAL", "SUDESTE"]
    esferas = [None, "federal", "estadual", "municipal",
               "conselho_profissional", "MUNICIPAL"]
    tetos = [None, 2000.0, 10000.0, 18540.71]
    cargos = [None, 1, 10, 11, 86]
    seguindo = [False, True]
    for uf, reg, esf, teto, ct, seg in itertools.product(
            ufs, regioes, esferas, tetos, cargos, seguindo):
        yield _cand(uf=uf, regiao=reg, esfera=esf, teto=teto,
                    cargos_total=ct, seguindo=seg)


POLITICAS = [ATIVA, Politica(), Politica(modo="sombra", corte_fora_sul=10000.0)]


def test_motivo_sempre_do_conjunto_fechado():
    for p in POLITICAS:
        for c in _matriz():
            assert decidir(c, p).motivo in MOTIVOS_DA_SPEC


def test_so_as_regras_5_e_6_recusam():
    recusas = {"abaixo_do_corte", "municipal_inflado"}
    for p in POLITICAS:
        for c in _matriz():
            d = decidir(c, p)
            assert d.entra is (d.motivo not in recusas), (c, d)


def test_selo_so_nas_regras_2_e_7():
    com_selo = {"nao_verificado", "sem_evidencia"}
    for p in POLITICAS:
        for c in _matriz():
            d = decidir(c, p)
            esperado = SELO_NAO_VERIFICADO if d.motivo in com_selo else None
            assert d.selo == esperado, (c, d)
