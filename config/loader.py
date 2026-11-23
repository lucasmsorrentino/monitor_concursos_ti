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


def _normalize_slugs(value: list[str] | str | None) -> list[str]:
    """Normaliza `pci_slugs` em lista de slugs limpos, aceitando CSV."""
    if value is None:
        return []
    items = value.split(",") if isinstance(value, str) else value
    return [str(item).strip().strip("/").lower() for item in items if str(item).strip()]


def _normalize_bool(value, padrao: bool = False) -> bool:
    """Le booleano vindo de JSON (true) ou de .env legado ("1", "sim", "true")."""
    if value is None:
        return padrao
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "sim", "yes", "on"}


def _normalize_modo_carga(value, area: str, logger: logging.Logger) -> str:
    """Valida `pci_primeira_carga`; cai no padrao seguro se vier bobagem.

    O padrao e `individual`, que preserva o comportamento historico de um card
    por edital. Modo invalido nao pode virar silencio acidental.
    """
    modos = {"individual", "resumo_uf", "silencioso"}
    if value is None:
        return "individual"
    modo = str(value).strip().lower()
    if modo in modos:
        return modo
    logger.warning(
        f"pci_primeira_carga invalido para {area}: {value!r} "
        f"(validos: {sorted(modos)}). Usando 'individual'."
    )
    return "individual"


# Marcador de chave ausente: distingue "nao veio" de null explicito no JSON,
# porque lista vazia ([] e falsy) e escolha valida e tem de ser respeitada.
_AUSENTE = object()


def _env_opcional(nome: str):
    """Le variavel de ambiente como chave opcional: ausente vira _AUSENTE."""
    valor = os.getenv(nome)
    return _AUSENTE if valor is None else valor


def _split_csv_ou_lista(valor) -> list[str]:
    """Aceita lista do JSON ou CSV do .env, descartando itens vazios."""
    items = valor.split(",") if isinstance(valor, str) else valor
    return [str(item).strip() for item in items if str(item).strip()]


def _normalize_ufs_sem_corte(valor) -> list[str]:
    """Normaliza `ufs_sem_corte`: UFs em maiuscula, aceitando lista ou CSV.

    Lista vazia explicita significa "ninguem isento" e e respeitada;
    chave ausente usa o padrao (as tres UFs do Sul).
    """
    if valor is None or valor is _AUSENTE:
        return ["PR", "SC", "RS"]
    return [item.upper() for item in _split_csv_ou_lista(valor)]


def _normalize_esferas_sem_corte(valor) -> list[str]:
    """Normaliza `esferas_sem_corte`: esferas em minuscula, lista ou CSV.

    Lista vazia explicita significa "nenhuma esfera isenta" e e respeitada.
    """
    if valor is None or valor is _AUSENTE:
        return ["federal"]
    return [item.lower() for item in _split_csv_ou_lista(valor)]


def _normalize_pci_mcp_cargos(valor) -> list[str]:
    """Normaliza `pci_mcp_cargos` preservando a ordem e a caixa escritas.

    O servidor MCP normaliza a busca sozinho; caixa e ordem sao de quem
    configura e e isso que sai no log.
    """
    if valor is None or valor is _AUSENTE:
        return []
    return _split_csv_ou_lista(valor)


def _normalize_escolha(valor, padrao: str) -> str:
    """Normaliza chave de texto da config por area: sem caixa, sem bordas."""
    if valor is None or valor is _AUSENTE:
        return padrao
    return str(valor).strip().lower()


def _normalize_corte_fora_sul(valor) -> float:
    """Converte `corte_fora_sul` em float, aceitando numero ou string de numero."""
    if valor is None or valor is _AUSENTE:
        return 0.0
    return float(str(valor).strip())


def _normalize_cargos_total_inflado(valor) -> int:
    """Converte `cargos_total_inflado` em int, aceitando numero ou string."""
    if valor is None or valor is _AUSENTE:
        return 10
    return int(float(str(valor).strip()))


def _config_por_area(bruto: dict) -> dict:
    """Monta as oito chaves por area (SPEC-001, secao 3.6) dos valores crus.

    `bruto` aceita tanto o objeto do MONITOR_TARGETS_JSON quanto variaveis
    de ambiente do modo legado embrulhadas em _env_opcional, porque a
    chave ausente (_AUSENTE ou null) cai no padrao seguro da spec.
    """
    return {
        "pci_mcp": _normalize_bool(bruto.get("pci_mcp")),
        "pci_mcp_cargos": _normalize_pci_mcp_cargos(
            bruto.get("pci_mcp_cargos", _AUSENTE)
        ),
        "filtro_salarial": _normalize_escolha(
            bruto.get("filtro_salarial", _AUSENTE), "desligado"
        ),
        "corte_fora_sul": _normalize_corte_fora_sul(
            bruto.get("corte_fora_sul", _AUSENTE)
        ),
        "ufs_sem_corte": _normalize_ufs_sem_corte(
            bruto.get("ufs_sem_corte", _AUSENTE)
        ),
        "esferas_sem_corte": _normalize_esferas_sem_corte(
            bruto.get("esferas_sem_corte", _AUSENTE)
        ),
        "cargos_total_inflado": _normalize_cargos_total_inflado(
            bruto.get("cargos_total_inflado", _AUSENTE)
        ),
        "resumo_filtrados": _normalize_escolha(
            bruto.get("resumo_filtrados", _AUSENTE), "nunca"
        ),
    }


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
                    "pci_slugs": _normalize_slugs(item.get("pci_slugs")),
                    # Lista de concursos NACIONAIS do PCI: a unica fonte que
                    # cobre estatal federal (Dataprev, Transpetro, Correios).
                    # Padrao desligado — ligar custa uma chamada de LLM por
                    # item novo, entao e escolha por area.
                    "pci_nacional": _normalize_bool(item.get("pci_nacional")),
                    "pci_primeira_carga": _normalize_modo_carga(
                        item.get("pci_primeira_carga"), area, logger
                    ),
                }
                target.update(_config_por_area(item))
                targets.append(target)

            if targets:
                return targets
        except json.JSONDecodeError as exc:
            logger.error(f"MONITOR_TARGETS_JSON invalido: {exc}. Usando modo legado.")

    legacy_url = os.getenv("URL_ALVO", "").strip()
    legacy_chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    legacy_config_area = _config_por_area({
        "pci_mcp": _env_opcional("PCI_MCP"),
        "pci_mcp_cargos": _env_opcional("PCI_MCP_CARGOS"),
        "filtro_salarial": _env_opcional("FILTRO_SALARIAL"),
        "corte_fora_sul": _env_opcional("CORTE_FORA_SUL"),
        "ufs_sem_corte": _env_opcional("UFS_SEM_CORTE"),
        "esferas_sem_corte": _env_opcional("ESFERAS_SEM_CORTE"),
        "cargos_total_inflado": _env_opcional("CARGOS_TOTAL_INFLADO"),
        "resumo_filtrados": _env_opcional("RESUMO_FILTRADOS"),
    })
    return [{
        "area": "TI",
        "display_name": "TI",
        "url_alvo": legacy_url,
        "token": token,
        "chat_ids": [legacy_chat] if legacy_chat else [],
        "keywords_include": _normalize_keywords(os.getenv("KEYWORDS_INCLUDE")),
        "keywords_exclude": _normalize_keywords(os.getenv("KEYWORDS_EXCLUDE")),
        "pci_slugs": _normalize_slugs(os.getenv("PCI_SLUGS")),
        "pci_nacional": _normalize_bool(os.getenv("PCI_NACIONAL")),
        "pci_primeira_carga": _normalize_modo_carga(
            os.getenv("PCI_PRIMEIRA_CARGA"), "TI", logger
        ),
        **legacy_config_area,
    }]
