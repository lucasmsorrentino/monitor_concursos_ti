#!/usr/bin/env bash
# Diagnostico da producao do monitor de concursos.
#
# Esqueleto: as secoes de relatorio ainda nao estao implementadas.
# Coleta evidencia dos ultimos 30 dias numa saida unica, para o operador
# rodar no notebook e colar de volta. Somente leitura: nao escreve arquivo,
# nao toca no banco, nao manda mensagem, nao roda varredura. Sai sempre com
# 0 — o diagnostico RELATA, nao julga.
#
# Uso (a partir da raiz do repo):
#   bash scripts/diagnostico_producao.sh
# Opcional: caminho de raiz alternativo (usado pelos testes):
#   bash scripts/diagnostico_producao.sh /caminho/da/raiz

set -u

RAIZ="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

echo "diagnostico: nao implementado" >&2
exit 2
