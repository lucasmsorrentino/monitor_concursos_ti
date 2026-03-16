"""Carregador de configuracao para modo single-area e multi-area.

Suporta dois formatos:
1) Legado (single-area): usa URL_ALVO + TELEGRAM_CHAT_ID.
2) Multi-area: usa MONITOR_TARGETS_JSON com lista de alvos.
"""

from __future__ import annotations

import json
import logging
import os


def _parse_chat_ids(raw_value: str | None, fallback: str | None) -> list[str]:
    """Converte chat_ids em lista, aceitando CSV no .env."""
    if raw_value:
        chat_ids = [item.strip() for item in raw_value.split(",") if item.strip()]
        if chat_ids:
            return chat_ids
    return [fallback] if fallback else []


def _normalize_keywords(value: list[str] | str | None) -> list[str]:
    """Normaliza lista de palavras-chave em lowercase sem vazios."""
    if value is None:
        return []
    if isinstance(value, str):
        items = value.split(",")
    else:
        items = value
    return [item.strip().lower() for item in items if str(item).strip()]


def load_monitor_targets(logger: logging.Logger) -> list[dict]:
    """Carrega alvos de monitoramento com fallback seguro para modo legado."""
    token = os.getenv("TELEGRAM_TOKEN")
    json_blob = os.getenv("MONITOR_TARGETS_JSON", "").strip()

    if json_blob:
        try:
            raw_targets = json.loads(json_blob)
            targets: list[dict] = []
            for index, item in enumerate(raw_targets, start=1):
                area = str(item.get("area") or f"AREA_{index}").strip()
                display_name = str(item.get("display_name") or area).strip()
                url = str(item.get("url") or "").strip()
                if not url:
                    logger.warning(f"Alvo {area} sem URL; ignorando.")
                    continue

                target_token = str(item.get("token") or token or "").strip()
                target_chat_ids = item.get("chat_ids")
                if isinstance(target_chat_ids, str):
                    chat_ids = _parse_chat_ids(target_chat_ids, None)
                elif isinstance(target_chat_ids, list):
                    chat_ids = [str(chat).strip() for chat in target_chat_ids if str(chat).strip()]
                else:
                    chat_ids = _parse_chat_ids(None, str(item.get("chat_id") or "").strip())

                if not target_chat_ids and not chat_ids:
                    legacy_chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
                    chat_ids = [legacy_chat] if legacy_chat else []

                target = {
                    "area": area,
                    "display_name": display_name,
                    "url_alvo": url,
                    "token": target_token,
                    "chat_ids": chat_ids,
                    "keywords_include": _normalize_keywords(item.get("keywords_include")),
                    "keywords_exclude": _normalize_keywords(item.get("keywords_exclude")),
                }
                targets.append(target)

            if targets:
                return targets
        except json.JSONDecodeError as exc:
            logger.error(f"MONITOR_TARGETS_JSON invalido: {exc}. Usando modo legado.")

    legacy_url = os.getenv("URL_ALVO", "").strip()
    legacy_chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    return [{
        "area": "TI",
        "display_name": "TI",
        "url_alvo": legacy_url,
        "token": token,
        "chat_ids": [legacy_chat] if legacy_chat else [],
        "keywords_include": _normalize_keywords(os.getenv("KEYWORDS_INCLUDE")),
        "keywords_exclude": _normalize_keywords(os.getenv("KEYWORDS_EXCLUDE")),
    }]
