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
