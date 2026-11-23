"""Testes para config/loader.py — carregamento de alvos de monitoramento."""
import json
import logging

import pytest

from config.loader import _normalize_keywords, _parse_chat_ids, load_monitor_targets


@pytest.fixture
def logger():
    return logging.getLogger("test_loader")


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    """Garante isolamento entre testes removendo variaveis relevantes."""
    for var in (
        "TELEGRAM_TOKEN",
        "TELEGRAM_CHAT_ID",
        "MONITOR_TARGETS_JSON",
        "URL_ALVO",
        "KEYWORDS_INCLUDE",
        "KEYWORDS_EXCLUDE",
        "PCI_SLUGS",
        "PCI_NACIONAL",
        "PCI_PRIMEIRA_CARGA",
        "PCI_MCP",
        "PCI_MCP_CARGOS",
        "FILTRO_SALARIAL",
        "CORTE_FORA_SUL",
        "UFS_SEM_CORTE",
        "ESFERAS_SEM_CORTE",
        "CARGOS_TOTAL_INFLADO",
        "RESUMO_FILTRADOS",
    ):
        monkeypatch.delenv(var, raising=False)


class TestParseChatIds:
    def test_returns_list_from_csv(self):
        assert _parse_chat_ids("111,222,333", None) == ["111", "222", "333"]

    def test_trims_whitespace_and_drops_empties(self):
        assert _parse_chat_ids(" 111 , , 222 ", None) == ["111", "222"]

    def test_falls_back_when_raw_empty(self):
        assert _parse_chat_ids("", "fallback") == ["fallback"]
        assert _parse_chat_ids(None, "fallback") == ["fallback"]

    def test_empty_without_fallback_returns_empty_list(self):
        assert _parse_chat_ids(None, None) == []


class TestNormalizeKeywords:
    def test_handles_none(self):
        assert _normalize_keywords(None) == []

    def test_splits_csv_string_and_lowercases(self):
        assert _normalize_keywords("TI, Tecnologia, Sistemas") == [
            "ti", "tecnologia", "sistemas"
        ]

    def test_accepts_list_and_drops_empties(self):
        assert _normalize_keywords(["TI", "", "  ", "Sistemas"]) == ["ti", "sistemas"]


class TestLoadMonitorTargetsMultiArea:
    def test_parses_json_blob(self, monkeypatch, logger):
        blob = json.dumps([
            {
                "area": "TI",
                "display_name": "Tecnologia",
                "url": "https://example.com/ti",
                "chat_ids": ["111"],
                "keywords_include": ["ti"],
                "keywords_exclude": ["artes"],
            }
        ])
        monkeypatch.setenv("TELEGRAM_TOKEN", "token_global")
        monkeypatch.setenv("MONITOR_TARGETS_JSON", blob)

        targets = load_monitor_targets(logger)

        assert len(targets) == 1
        t = targets[0]
        assert t["area"] == "TI"
        assert t["display_name"] == "Tecnologia"
        assert t["url_alvo"] == "https://example.com/ti"
        assert t["token"] == "token_global"
        assert t["chat_ids"] == ["111"]
        assert t["keywords_include"] == ["ti"]
        assert t["keywords_exclude"] == ["artes"]

    def test_skips_target_without_url(self, monkeypatch, logger):
        blob = json.dumps([
            {"area": "TI", "url": "https://example.com/ti", "chat_ids": ["111"]},
            {"area": "BROKEN", "chat_ids": ["222"]},
        ])
        monkeypatch.setenv("MONITOR_TARGETS_JSON", blob)

        targets = load_monitor_targets(logger)

        assert len(targets) == 1
        assert targets[0]["area"] == "TI"

    def test_accepts_chat_ids_as_csv_string(self, monkeypatch, logger):
        blob = json.dumps([
            {"area": "A", "url": "https://e.com", "chat_ids": "111, 222 , 333"}
        ])
        monkeypatch.setenv("MONITOR_TARGETS_JSON", blob)

        targets = load_monitor_targets(logger)

        assert targets[0]["chat_ids"] == ["111", "222", "333"]

    def test_uses_per_target_token_override(self, monkeypatch, logger):
        blob = json.dumps([
            {
                "area": "A",
                "url": "https://e.com",
                "chat_ids": ["111"],
                "token": "token_especifico",
            }
        ])
        monkeypatch.setenv("TELEGRAM_TOKEN", "token_global")
        monkeypatch.setenv("MONITOR_TARGETS_JSON", blob)

        targets = load_monitor_targets(logger)

        assert targets[0]["token"] == "token_especifico"

    def test_falls_back_to_legacy_chat_id_env(self, monkeypatch, logger):
        blob = json.dumps([{"area": "A", "url": "https://e.com"}])
        monkeypatch.setenv("MONITOR_TARGETS_JSON", blob)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "legacy_chat")

        targets = load_monitor_targets(logger)

        assert targets[0]["chat_ids"] == ["legacy_chat"]

    def test_generates_area_name_when_missing(self, monkeypatch, logger):
        blob = json.dumps([
            {"url": "https://e.com/a", "chat_ids": ["111"]},
            {"url": "https://e.com/b", "chat_ids": ["222"]},
        ])
        monkeypatch.setenv("MONITOR_TARGETS_JSON", blob)

        targets = load_monitor_targets(logger)

        assert [t["area"] for t in targets] == ["AREA_1", "AREA_2"]

    def test_malformed_json_falls_back_to_legacy(self, monkeypatch, logger):
        monkeypatch.setenv("MONITOR_TARGETS_JSON", "{not json")
        monkeypatch.setenv("URL_ALVO", "https://legacy.com")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "legacy_chat")

        targets = load_monitor_targets(logger)

        assert len(targets) == 1
        assert targets[0]["area"] == "TI"
        assert targets[0]["url_alvo"] == "https://legacy.com"
        assert targets[0]["chat_ids"] == ["legacy_chat"]


class TestLoadMonitorTargetsLegacy:
    def test_legacy_mode_when_multi_area_absent(self, monkeypatch, logger):
        monkeypatch.setenv("TELEGRAM_TOKEN", "tok")
        monkeypatch.setenv("URL_ALVO", "https://legacy.com/ti")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
        monkeypatch.setenv("KEYWORDS_INCLUDE", "ti, sistemas")
        monkeypatch.setenv("KEYWORDS_EXCLUDE", "artes")

        targets = load_monitor_targets(logger)

        assert len(targets) == 1
        t = targets[0]
        assert t["area"] == "TI"
        assert t["url_alvo"] == "https://legacy.com/ti"
        assert t["chat_ids"] == ["999"]
        assert t["keywords_include"] == ["ti", "sistemas"]
        assert t["keywords_exclude"] == ["artes"]

    def test_legacy_mode_with_no_chat_id_returns_empty_list(self, monkeypatch, logger):
        monkeypatch.setenv("URL_ALVO", "https://legacy.com/ti")

        targets = load_monitor_targets(logger)

        assert targets[0]["chat_ids"] == []

    def test_empty_json_blob_falls_through_to_legacy(self, monkeypatch, logger):
        monkeypatch.setenv("MONITOR_TARGETS_JSON", "   ")
        monkeypatch.setenv("URL_ALVO", "https://legacy.com")

        targets = load_monitor_targets(logger)

        assert targets[0]["url_alvo"] == "https://legacy.com"


# Oraculo: tabela da SPEC-001, secao 3.6, transcrita a mao — o teste nao
# recalcula nada do loader, so confere contra o literal da spec.
PADROES_SECAO_3_6 = {
    "pci_mcp": False,
    "pci_mcp_cargos": [],
    "filtro_salarial": "desligado",
    "corte_fora_sul": 0.0,
    "ufs_sem_corte": ["PR", "SC", "RS"],
    "esferas_sem_corte": ["federal"],
    "cargos_total_inflado": 10,
    "resumo_filtrados": "nunca",
}


def _alvo_minimo(**overrides):
    """Alvo multi-area valido, com as chaves por area sob medida do teste."""
    alvo = {"area": "TI", "url": "https://e.com", "chat_ids": ["111"]}
    alvo.update(overrides)
    return alvo


def _carregar_alvos(monkeypatch, logger, alvos):
    """Carrega MONITOR_TARGETS_JSON com os alvos crus e devolve {area: alvo}."""
    monkeypatch.setenv("MONITOR_TARGETS_JSON", json.dumps(alvos))
    return {t["area"]: t for t in load_monitor_targets(logger)}


def _so_as_oito_chaves(alvo: dict) -> dict:
    return {chave: alvo[chave] for chave in PADROES_SECAO_3_6}


def _confere_padroes_da_spec(alvo: dict) -> None:
    """Confere o alvo contra a tabela da secao 3.6, incluindo os tipos."""
    assert _so_as_oito_chaves(alvo) == PADROES_SECAO_3_6
    assert isinstance(alvo["corte_fora_sul"], float)
    assert isinstance(alvo["cargos_total_inflado"], int)
    assert isinstance(alvo["pci_mcp"], bool)


class TestConfigPorArea:
    def test_alvo_sem_as_chaves_novas_recebe_os_padroes(self, monkeypatch, logger):
        alvos = _carregar_alvos(monkeypatch, logger, [_alvo_minimo()])

        _confere_padroes_da_spec(alvos["TI"])

    def test_padroes_valem_no_modo_legado(self, monkeypatch, logger):
        monkeypatch.setenv("URL_ALVO", "https://legacy.com/ti")

        (alvo,) = load_monitor_targets(logger)

        _confere_padroes_da_spec(alvo)

    def test_chaves_por_area_no_modo_legado_via_variaveis(self, monkeypatch, logger):
        monkeypatch.setenv("URL_ALVO", "https://legacy.com/ti")
        monkeypatch.setenv("PCI_MCP", "true")
        monkeypatch.setenv("PCI_MCP_CARGOS", "analista de sistemas, informatica")
        monkeypatch.setenv("FILTRO_SALARIAL", " ativo ")
        monkeypatch.setenv("CORTE_FORA_SUL", "10000.50")
        monkeypatch.setenv("UFS_SEM_CORTE", "pr, sc,rs")
        monkeypatch.setenv("ESFERAS_SEM_CORTE", "FEDERAL,Distrital")
        monkeypatch.setenv("CARGOS_TOTAL_INFLADO", "25")
        monkeypatch.setenv("RESUMO_FILTRADOS", "semanal")

        (alvo,) = load_monitor_targets(logger)

        assert _so_as_oito_chaves(alvo) == {
            "pci_mcp": True,
            "pci_mcp_cargos": ["analista de sistemas", "informatica"],
            "filtro_salarial": "ativo",
            "corte_fora_sul": 10000.5,
            "ufs_sem_corte": ["PR", "SC", "RS"],
            "esferas_sem_corte": ["federal", "distrital"],
            "cargos_total_inflado": 25,
            "resumo_filtrados": "semanal",
        }

    def test_filtro_salarial_aceita_ativo(self, monkeypatch, logger):
        alvos = _carregar_alvos(monkeypatch, logger, [
            _alvo_minimo(area="A1", filtro_salarial="ativo"),
            _alvo_minimo(area="A2", filtro_salarial="ATIVO"),
            _alvo_minimo(area="A3", filtro_salarial=" ativo "),
        ])

        assert alvos["A1"]["filtro_salarial"] == "ativo"
        assert alvos["A2"]["filtro_salarial"] == "ativo"
        assert alvos["A3"]["filtro_salarial"] == "ativo"

    def test_corte_aceita_numero_e_string(self, monkeypatch, logger):
        alvos = _carregar_alvos(monkeypatch, logger, [
            _alvo_minimo(area="A1", corte_fora_sul=10000),
            _alvo_minimo(area="A2", corte_fora_sul="10000"),
            _alvo_minimo(area="A3", corte_fora_sul=10000.5),
            _alvo_minimo(area="A4", corte_fora_sul="10000.50"),
        ])

        for area in ("A1", "A2", "A3", "A4"):
            assert isinstance(alvos[area]["corte_fora_sul"], float)
        assert alvos["A1"]["corte_fora_sul"] == 10000.0
        assert alvos["A2"]["corte_fora_sul"] == 10000.0
        assert alvos["A3"]["corte_fora_sul"] == 10000.5
        assert alvos["A4"]["corte_fora_sul"] == 10000.5

    def test_ufs_sem_corte_aceita_csv_e_normaliza_caixa(self, monkeypatch, logger):
        alvos = _carregar_alvos(monkeypatch, logger, [
            _alvo_minimo(ufs_sem_corte="pr, sc,rs")
        ])

        assert alvos["TI"]["ufs_sem_corte"] == ["PR", "SC", "RS"]

    def test_ufs_sem_corte_vazia_explicita_e_respeitada(self, monkeypatch, logger):
        alvos = _carregar_alvos(monkeypatch, logger, [
            _alvo_minimo(ufs_sem_corte=[])
        ])

        assert alvos["TI"]["ufs_sem_corte"] == []

    def test_esferas_sem_corte_normaliza_para_minuscula(self, monkeypatch, logger):
        alvos = _carregar_alvos(monkeypatch, logger, [
            _alvo_minimo(esferas_sem_corte=["FEDERAL", "Distrital"])
        ])

        assert alvos["TI"]["esferas_sem_corte"] == ["federal", "distrital"]

    def test_pci_mcp_cargos_aceita_csv_e_preserva_ordem(self, monkeypatch, logger):
        alvos = _carregar_alvos(monkeypatch, logger, [
            _alvo_minimo(pci_mcp_cargos="analista de sistemas, informatica")
        ])

        assert alvos["TI"]["pci_mcp_cargos"] == ["analista de sistemas", "informatica"]

    def test_uma_area_filtrando_nao_afeta_a_outra(self, monkeypatch, logger):
        alvos = _carregar_alvos(monkeypatch, logger, [
            _alvo_minimo(area="TI", filtro_salarial="ativo"),
            {"area": "EDUCACAO", "url": "https://e.com/ed", "chat_ids": ["222"]},
        ])

        assert alvos["TI"]["filtro_salarial"] == "ativo"
        assert alvos["EDUCACAO"]["filtro_salarial"] == "desligado"


class TestConfigPorAreaFailOpen:
    """Valor invalido loga aviso e cai no padrao seguro, nunca no agressivo."""

    def _avisos(self, caplog, chave: str) -> list:
        return [
            rec for rec in caplog.records
            if rec.levelno == logging.WARNING and chave in rec.getMessage()
        ]

    def test_filtro_salarial_invalido_cai_em_desligado(self, monkeypatch, logger, caplog):
        with caplog.at_level(logging.WARNING):
            alvos = _carregar_alvos(monkeypatch, logger, [
                _alvo_minimo(area="A1", filtro_salarial="sombra"),
                _alvo_minimo(area="A2", filtro_salarial="1"),
                _alvo_minimo(area="A3", filtro_salarial=""),
                _alvo_minimo(area="A4", filtro_salarial=None),
            ])

        for area in ("A1", "A2", "A3", "A4"):
            assert alvos[area]["filtro_salarial"] == "desligado"
        assert len(self._avisos(caplog, "filtro_salarial")) >= 1

    def test_resumo_filtrados_invalido_cai_em_nunca(self, monkeypatch, logger, caplog):
        with caplog.at_level(logging.WARNING):
            alvos = _carregar_alvos(monkeypatch, logger, [
                _alvo_minimo(resumo_filtrados="diario")
            ])

        assert alvos["TI"]["resumo_filtrados"] == "nunca"
        assert len(self._avisos(caplog, "resumo_filtrados")) >= 1

    def test_corte_invalido_cai_em_zero(self, monkeypatch, logger, caplog):
        with caplog.at_level(logging.WARNING):
            alvos = _carregar_alvos(monkeypatch, logger, [
                _alvo_minimo(area="A1", corte_fora_sul="dez mil"),
                _alvo_minimo(area="A2", corte_fora_sul=-5),
                _alvo_minimo(area="A3", corte_fora_sul=None),
            ])

        for area in ("A1", "A2", "A3"):
            assert alvos[area]["corte_fora_sul"] == 0.0
            assert isinstance(alvos[area]["corte_fora_sul"], float)
        assert len(self._avisos(caplog, "corte_fora_sul")) >= 1

    def test_cargos_total_inflado_invalido_cai_em_dez(self, monkeypatch, logger, caplog):
        with caplog.at_level(logging.WARNING):
            alvos = _carregar_alvos(monkeypatch, logger, [
                _alvo_minimo(area="A1", cargos_total_inflado="muitos"),
                _alvo_minimo(area="A2", cargos_total_inflado=0),
                _alvo_minimo(area="A3", cargos_total_inflado=-1),
                _alvo_minimo(area="A4", cargos_total_inflado=2.5),
            ])

        for area in ("A1", "A2", "A3", "A4"):
            assert alvos[area]["cargos_total_inflado"] == 10
            assert isinstance(alvos[area]["cargos_total_inflado"], int)
        assert len(self._avisos(caplog, "cargos_total_inflado")) >= 1
