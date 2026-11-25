#!/usr/bin/env bash
# Diagnostico da producao do monitor de concursos.
#
# Coleta a evidencia dos ultimos 30 dias numa saida unica, para o operador
# rodar no notebook e colar de volta. Somente leitura: nao escreve arquivo,
# nao toca no banco, nao manda mensagem, nao roda varredura. Sai sempre com
# 0 — o diagnostico RELATA, nao julga.
#
# Uso (a partir da raiz do repo):
#   bash scripts/diagnostico_producao.sh
# Opcional: caminho de raiz alternativo (usado pelos testes):
#   bash scripts/diagnostico_producao.sh /caminho/da/raiz
#
# Garantias:
# - Nunca morre no meio por arquivo ausente: cada secao degrada para
#   "ausente" e a seguinte roda.
# - Nunca imprime segredo: token, chave e chat_id viram <omitido>. O arquivo
#   de segredos e lido so para listar NOMES de chave e para extrair a
#   estrutura do MONITOR_TARGETS_JSON, sempre com o valor substituido.

set -u

# Semantica de BYTES para grep/sed: logs sao texto com emoji e acentos; com
# locale UTF-8 o "." de regex nao atravessa bytes que nao formam caractere
# valido, e o match muda de maquina para maquina. C deixa o comportamento
# identico em qualquer Debian. Os acentos dos dados atravessam intactos.
export LC_ALL=C

RAIZ="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
RAIZ="$(cd "$RAIZ" 2>/dev/null && pwd)" || true
LOG_DIR="$RAIZ/logs"
BANCO="$RAIZ/data/concursos.db"
ENV_LOCAL="$RAIZ/.env"
# Mesmo caminho que o run_daily.sh exporta para a producao.
ENV_PRODUCAO="${MONITOR_ENV_FILE:-$HOME/concursos-secrets/monitor.env}"
JANELA=30
HOJE="$(date +%Y%m%d)"
HOJE_S="$(date -d "$HOJE" +%s 2>/dev/null || date +%s)"
LIMITE="$(date -d "@$((HOJE_S - (JANELA - 1) * 86400))" +%Y%m%d)"

titulo() { echo; echo "== $1 =="; }
ausente() { echo "ausente: $1"; }

# Marcador de credencial recusada pela IA (U+1F511), construido por bytes:
# o padrao nunca atravessa uma conversao de encoding entre processos.
MARCA_CHAVE=$'\xf0\x9f\x94\x91'

# --- python utilizavel -------------------------------------------------------
# O alias `python3` do Windows (Microsoft Store) existe mas nao roda; probe
# com um comando trivial e so aceita quem responde de verdade.
acha_python() {
    local cand
    for cand in python3 python; do
        if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "pass" >/dev/null 2>&1; then
            printf '%s' "$cand"
            return 0
        fi
    done
    return 1
}
PY="$(acha_python 2>/dev/null || true)"

read -r -d '' PY_CONFIG <<'PYEOF' || true
import json
import sys

try:
    dados = json.load(sys.stdin)
except Exception:
    print("  invalido: JSON ilegivel")
    sys.exit(0)

if isinstance(dados, dict):
    dados = [dados]

for item in dados:
    if not isinstance(item, dict):
        continue
    area = str(item.get("area") or "?")
    display = str(item.get("display_name") or area)
    print(f"  area {area} ({display})")
    if item.get("url"):
        print("    porta gran: ligada")
    else:
        print("    porta gran: sem url configurada")
    slugs = item.get("pci_slugs") or []
    if slugs:
        print(f"    porta pci_cargos: ligada ({len(slugs)} slug(s))")
    else:
        print("    porta pci_cargos: desligada")
    if item.get("pci_nacional"):
        print("    porta pci_nacional: ligada")
    else:
        print("    porta pci_nacional: desligada")
    raw_termos = item.get("pci_mcp_cargos")
    if isinstance(raw_termos, list):
        n_termos = len([t for t in raw_termos if str(t).strip()])
    elif isinstance(raw_termos, str):
        n_termos = len([t for t in raw_termos.split(",") if t.strip()])
    else:
        n_termos = 0
    if item.get("pci_mcp"):
        print(f"    porta pci_mcp: ligada ({n_termos} termo(s))")
    else:
        print("    porta pci_mcp: desligada")
    filtro = item.get("filtro_salarial")
    if not filtro:
        filtro = "desligado"
    print(f"    filtro_salarial: {filtro}")
    corte = item.get("corte_fora_sul")
    if corte is None or corte == "":
        corte = 0
    print(f"    corte_fora_sul: {corte}")
    resumo = item.get("resumo_filtrados")
    if not resumo:
        resumo = "nunca"
    print(f"    resumo_filtrados: {resumo}")
    if item.get("token"):
        print("    token: <omitido>")
    else:
        print("    token: ausente")
    chats = item.get("chat_ids") or []
    if chats:
        print(f"    chat_ids: <omitido> ({len(chats)})")
    else:
        print("    chat_ids: ausente")
PYEOF

read -r -d '' PY_BANCO <<'PYEOF' || true
import sqlite3
import sys

try:
    con = sqlite3.connect("file:" + sys.argv[1].replace("\\", "/") + "?mode=ro", uri=True)
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM editais")
    total = cur.fetchone()[0]
except Exception:
    print("total de linhas: ausente (banco ilegivel)")
    sys.exit(0)

print(f"total de linhas: {total}")
print("por area:")
for area, n in cur.execute(
    "SELECT area, COUNT(*) FROM editais GROUP BY area ORDER BY COUNT(*) DESC, area"
):
    print(f"  {area}={n}")
print("por fonte:")
for fonte, n in cur.execute(
    "SELECT COALESCE(fonte, '(vazio)'), COUNT(*) FROM editais GROUP BY fonte ORDER BY COUNT(*) DESC"
):
    print(f"  {fonte}={n}")
print("por estado_usuario:")
for estado, n in cur.execute(
    "SELECT COALESCE(estado_usuario, '(vazio)'), COUNT(*) FROM editais GROUP BY estado_usuario ORDER BY COUNT(*) DESC"
):
    print(f"  {estado}={n}")
cur.execute("SELECT MAX(ultima_atualizacao) FROM editais")
print(f"ultima_atualizacao mais recente: {cur.fetchone()[0]}")
PYEOF

# --- 1. identidade -----------------------------------------------------------
secao_identidade() {
    titulo "Identidade"
    echo "data e hora: $(date '+%Y-%m-%d %H:%M:%S %z' 2>/dev/null || date '+%Y-%m-%d %H:%M:%S')"
    echo "host: $(hostname 2>/dev/null || echo 'ausente')"
    if git -C "$RAIZ" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        echo "commit: $(git -C "$RAIZ" rev-parse --short HEAD 2>/dev/null || echo 'ausente')"
        echo "branch: $(git -C "$RAIZ" rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'ausente')"
        local sujos
        sujos="$(git -C "$RAIZ" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
        if [ "${sujos:-0}" = "0" ]; then
            echo "arvore: limpa"
        else
            echo "arvore: suja (${sujos} arquivo(s))"
        fi
    else
        ausente "repositorio git em $RAIZ"
    fi
}

# --- 2. ultimo sucesso -------------------------------------------------------
secao_ultimo_sucesso() {
    titulo "Ultimo sucesso"
    local marcador="$LOG_DIR/.last_success_date"
    if [ ! -f "$marcador" ]; then
        ausente "$LOG_DIR/.last_success_date"
        return 0
    fi
    local conteudo dias
    conteudo="$(tr -d ' \r\n\t' < "$marcador")"
    echo "data: ${conteudo:-ausente}"
    if [[ "${conteudo:-}" =~ ^[0-9]{8}$ ]]; then
        dias=$(( ( $(date +%s) - $(date -d "$conteudo" +%s 2>/dev/null || echo 0) ) / 86400 ))
        echo "idade: ${dias} dias"
    else
        echo "conteudo nao e uma data AAAAMMDD"
    fi
}

# --- 3. saude por dia --------------------------------------------------------
# Codigos de saida que o chamador grava no fim do arquivo; as duas formas
# existem no repo: "Finalizado com codigo N" e "===== exit=N ... =====".
codigo_de_saida_do_arquivo() {
    local f="$1" linha
    linha="$(grep -hE 'exit=[0-9]+|Finalizado com codigo [0-9]+' "$f" 2>/dev/null | tail -n 1)"
    case "$linha" in
        *exit=*)           printf '%s' "$linha" | sed -n 's/.*exit=\([0-9]\{1,\}\).*/\1/p' ;;
        *Finalizado*)      printf '%s' "$linha" | sed -n 's/.*Finalizado com codigo \([0-9]\{1,\}\).*/\1/p' ;;
        *)                 echo '?' ;;
    esac
    return 0
}

# Soma as linhas "Ciclo finalizado: N novos e M atualizacoes enviadas." do
# dia (uma por area em runs multi-area). Captura o campo 1 (novos) ou 2.
contagem_ciclo() {
    local f="$1" campo="$2"
    local linhas
    linhas="$(grep -h 'Ciclo finalizado:' "$f" 2>/dev/null)"
    if [ -z "$linhas" ]; then
        echo '-'
        return 0
    fi
    printf '%s\n' "$linhas" \
        | sed -n "s/.*Ciclo finalizado: \([0-9]\{1,\}\) novos e \([0-9]\{1,\}\) atualiz.*/\1 \2/p" \
        | awk -v c="$campo" '{ s += $c } END { printf "%d", s }'
    return 0
}

secao_saude_por_dia() {
    titulo "Saude por dia (ultimos ${JANELA} dias)"
    if [ ! -d "$LOG_DIR" ]; then
        ausente "$LOG_DIR"
        return 0
    fi
    local i d f codigo
    for i in $(seq $((JANELA - 1)) -1 0); do
        d="$(date -d "@$((HOJE_S - i * 86400))" +%Y%m%d)"
        f="$LOG_DIR/run_$d.log"
        if [ ! -f "$f" ]; then
            echo "$d ausente"
            continue
        fi
        codigo="$(codigo_de_saida_do_arquivo "$f")"
        echo "$d exit=${codigo:-?} novos=$(contagem_ciclo "$f" 1) atualizacoes=$(contagem_ciclo "$f" 2)"
    done
    return 0
}

# --- arquivos da janela de 30 dias ------------------------------------------
# So logs com data no nome dentro da janela (nome sem data entra: evidencia
# nao se descarta sem criterio).
logs_da_janela() {
    [ -d "$LOG_DIR" ] || return 0
    local f base d
    for f in "$LOG_DIR"/run_*.log; do
        [ -f "$f" ] || continue
        base="${f##*/}"
        d=""
        [[ "$base" =~ ^run_([0-9]{8})\.log$ ]] && d="${BASH_REMATCH[1]}"
        if [ -z "$d" ] || [ "$d" -ge "$LIMITE" ]; then
            printf '%s\n' "$f"
        fi
    done
    return 0
}

# --- 4. erros recorrentes ----------------------------------------------------
secao_erros_recorrentes() {
    titulo "Erros recorrentes"
    if [ ! -d "$LOG_DIR" ]; then
        ausente "$LOG_DIR"
        return 0
    fi
    local f msg acum=""
    while IFS= read -r f; do
        msg="$(grep -hE '\] \[(ERROR|CRITICAL)\] \[' "$f" 2>/dev/null \
            | sed -E \
                -e 's/^\[[^]]*\] *\[(ERROR|CRITICAL)\] *\[[^]]*\]: *//' \
                -e 's/[0-9]{5,}:[A-Za-z0-9_-]{20,}/<omitido>/g' \
                -e 's/[0-9]+/N/g')"
        [ -n "$msg" ] && acum+="$msg"$'\n'
    done < <(logs_da_janela)
    if [ -z "$acum" ]; then
        echo "nenhum ERROR/CRITICAL nos ultimos ${JANELA} dias"
        return 0
    fi
    printf '%s' "$acum" | sort | uniq -c | sort -rn | head -15
    return 0
}

# --- 5. falha de credencial --------------------------------------------------
# O marcador de chave recusada (o emoji de chave, ver MARCA_CHAVE) aparece no
# log quando a IA recusa a credencial (ver src/intelligence/langchain_unit.py
# e src/core/bot.py).
secao_credencial() {
    titulo "Falha de credencial"
    if [ ! -d "$LOG_DIR" ]; then
        ausente "$LOG_DIR"
        return 0
    fi
    local f base d n achou=0
    while IFS= read -r f; do
        base="${f##*/}"
        d="$base"
        [[ "$base" =~ ^run_([0-9]{8})\.log$ ]] && d="${BASH_REMATCH[1]}"
        n="$(grep -c "$MARCA_CHAVE" "$f" 2>/dev/null)"
        n="${n:-0}"
        [[ "$n" =~ ^[0-9]+$ ]] || n=0
        if [ "$n" -gt 0 ]; then
            echo "$d: $n"
            achou=1
        fi
    done < <(logs_da_janela)
    if [ "$achou" = 0 ]; then
        echo "nenhuma ocorrencia do marcador ${MARCA_CHAVE} nos ultimos ${JANELA} dias"
    fi
    return 0
}

# --- 6. banco ----------------------------------------------------------------
# Consulta em modo somente-leitura (`-readonly` / `mode=ro`): leitura de
# banco nao pode criar journal, nem wal, nem shm.
secao_banco() {
    titulo "Banco"
    if [ ! -f "$BANCO" ]; then
        ausente "$BANCO"
        return 0
    fi
    if command -v sqlite3 >/dev/null 2>&1; then
        echo "arquivo: $BANCO"
        echo "total de linhas: $(sqlite3 -readonly "$BANCO" 'SELECT COUNT(*) FROM editais;' 2>/dev/null || echo 'ausente')"
        echo "por area:"
        sqlite3 -readonly "$BANCO" \
            "SELECT '  ' || area || '=' || COUNT(*) FROM editais GROUP BY area ORDER BY COUNT(*) DESC, area;" \
            2>/dev/null || true
        echo "por fonte:"
        sqlite3 -readonly "$BANCO" \
            "SELECT '  ' || COALESCE(fonte, '(vazio)') || '=' || COUNT(*) FROM editais GROUP BY fonte ORDER BY COUNT(*) DESC;" \
            2>/dev/null || true
        echo "por estado_usuario:"
        sqlite3 -readonly "$BANCO" \
            "SELECT '  ' || COALESCE(estado_usuario, '(vazio)') || '=' || COUNT(*) FROM editais GROUP BY estado_usuario ORDER BY COUNT(*) DESC;" \
            2>/dev/null || true
        echo "ultima_atualizacao mais recente: $(sqlite3 -readonly "$BANCO" 'SELECT MAX(ultima_atualizacao) FROM editais;' 2>/dev/null || echo 'ausente')"
    elif [ -n "$PY" ]; then
        PYTHONUTF8=1 "$PY" -c "$PY_BANCO" "$BANCO" 2>/dev/null \
            || echo "total de linhas: ausente (banco ilegivel)"
    else
        ausente "sqlite3 e python3 (impossivel consultar $BANCO)"
    fi
    return 0
}

# --- 7. agendamento ----------------------------------------------------------
secao_agendamento() {
    titulo "Agendamento"
    if command -v crontab >/dev/null 2>&1; then
        local entradas
        entradas="$(crontab -l 2>/dev/null | grep -Ei 'monitor_concursos|run_daily' || true)"
        if [ -n "$entradas" ]; then
            echo "entradas do projeto no crontab:"
            echo "$entradas" | sed 's/^/  /'
        else
            echo "nenhuma entrada do projeto no crontab"
        fi
    else
        ausente "crontab"
    fi
    if command -v pgrep >/dev/null 2>&1; then
        local procs
        procs="$(pgrep -af 'main\.py|run_daily\.sh' 2>/dev/null || true)"
        if [ -n "$procs" ]; then
            echo "processo do monitor rodando agora:"
            echo "$procs" | sed 's/^/  /'
        else
            echo "nenhum processo do monitor rodando agora"
        fi
    else
        ausente "pgrep"
    fi
    return 0
}

# --- 8. config efetiva -------------------------------------------------------
# Mostra a estrutura do MONITOR_TARGETS_JSON (areas e portas) com token e
# chat_id substituidos. O JSON vem do ambiente; na falta dele, e extraido do
# arquivo de segredos de producao — mas so a estrutura sai, nunca o valor.
# Por fim, lista os NOMES das chaves de segredo encontradas (nunca valores).
secao_config() {
    titulo "Config efetiva"
    local blob="${MONITOR_TARGETS_JSON:-}" origem="variavel de ambiente"
    if [ -z "$blob" ] && [ -f "$ENV_PRODUCAO" ]; then
        blob="$(grep -m1 '^MONITOR_TARGETS_JSON=' "$ENV_PRODUCAO" 2>/dev/null \
            | cut -d= -f2- \
            | sed -e "s/^'//" -e "s/'\$//" -e 's/^"//' -e 's/"$//' \
            | tr -d '\r')"
        origem="$ENV_PRODUCAO"
    fi
    if [ -n "$blob" ]; then
        if [ -n "$PY" ]; then
            echo "MONITOR_TARGETS_JSON (de $origem):"
            printf '%s' "$blob" | PYTHONUTF8=1 "$PY" -c "$PY_CONFIG" 2>/dev/null \
                || echo "  invalido: nao foi possivel interpretar o JSON"
        else
            echo "MONITOR_TARGETS_JSON presente, mas sem python para interpreta-lo; nada impresso para nao vazar segredo."
        fi
    else
        ausente "MONITOR_TARGETS_JSON (ambiente e $ENV_PRODUCAO)"
    fi
    local arquivo
    for arquivo in "$ENV_LOCAL" "$ENV_PRODUCAO"; do
        [ -f "$arquivo" ] || continue
        echo "chaves em $arquivo (valores omitidos):"
        sed -E 's/=.*/=<omitido>/' "$arquivo" | tr -d '\r' | sed 's/^/  /'
    done
    return 0
}

main() {
    echo "Diagnostico da producao do monitor de concursos"
    secao_identidade
    secao_ultimo_sucesso
    secao_saude_por_dia
    secao_erros_recorrentes
    secao_credencial
    secao_banco
    secao_agendamento
    secao_config
}

main
exit 0
