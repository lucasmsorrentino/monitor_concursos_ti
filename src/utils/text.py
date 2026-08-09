"""Utilitarios de normalizacao de texto.

Contem `status_fingerprint`, usado para deduplicar o campo `status` entre
execucoes do bot. A LLM tende a reformular o mesmo conteudo com pequenas
variacoes (case, acentos, espacos, pontuacao), e a comparacao textual
pura dispara falsos positivos de "mudanca". O fingerprint normaliza e
retorna um SHA1 curto estavel.

Contem tambem `normalizar_nome` / `tokens_nome`, a identidade de ORGAO usada
para casar o mesmo concurso vindo de fontes diferentes (Gran e PCI escrevem
"Prefeitura de Ponta Grossa - PR" e "Concurso Prefeitura Ponta Grossa" para a
mesma coisa). Esta era a unica implementacao viva em `scripts/export_known.py`;
foi trazida pra ca para que o dedup entre fontes e o handoff pro Hermes usem
exatamente a mesma regra. Modulo sem dependencia externa de proposito, porque o
export_known roda em stdlib puro.
"""
import hashlib
import re
import unicodedata


_PUNCT_BORDA = re.compile(r"^[^\w]+|[^\w]+$", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")
_NAO_ALFANUM = re.compile(r"[^a-z0-9\s]")

# Palavras sem valor de identificacao de orgao (viram ruido no match por token).
# "para" NAO entra aqui: sem acento, a preposicao e o estado do Para ficam
# identicos, e descartar as duas apagava a unica palavra que distinguia o
# "Instituto Federal ... do Para" do "Instituto Federal ... do Sudeste de Minas
# Gerais". A preposicao sobrando custa quase nada; o falso casamento custa caro.
STOPWORDS_ORGAO = frozenset({
    "concurso", "concursos", "de", "da", "do", "dos", "das", "e", "a", "o",
    "analista", "tecnico", "em", "no", "na", "publico", "processo",
    "seletivo", "edital",
})

# Tipos genericos de orgao: aparecem em centenas de nomes e nao discriminam
# nada sozinhos. Ficam nos tokens (o Hermes usa a lista cheia), mas sao
# descontados na hora de decidir se dois nomes sao o mesmo orgao.
TIPOS_ORGAO = frozenset({
    "prefeitura", "municipio", "camara", "municipal", "estadual", "federal",
    "secretaria", "conselho", "regional", "instituto", "universidade",
    "fundacao", "autarquia", "consorcio", "intermunicipal", "departamento",
    "agencia", "tribunal", "assembleia", "legislativa", "companhia",
    "empresa", "servico", "governo", "estado",
})

_UFS = (
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
)
_UFS_MINUSCULAS = frozenset(uf.lower() for uf in _UFS)

# UF no fim do nome, no formato que o PCI usa: "... - PR".
_UF_SUFIXO = re.compile(
    r"[-–]\s*(" + "|".join(_UFS) + r")\s*$",
    re.IGNORECASE,
)


def strip_accents(s: str) -> str:
    """Remove diacriticos via NFKD. Cobre maiusculas, ü e ñ."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def normalizar_nome(nome: str) -> str:
    """Reduz um nome de orgao a letras, digitos e espaco unico, sem acento."""
    if not nome:
        return ""
    s = _NAO_ALFANUM.sub(" ", strip_accents(nome).lower())
    return _WHITESPACE.sub(" ", s).strip()


def tokens_nome(nome: str) -> list[str]:
    """Tokens significativos do nome do orgao, sem stopwords nem monossilabos."""
    return [
        t for t in normalizar_nome(nome).split()
        if len(t) >= 2 and t not in STOPWORDS_ORGAO
    ]


def extrair_uf(nome: str) -> str | None:
    """Extrai a UF do sufixo do nome, no padrao do PCI ("Camara de Passos - MG")."""
    m = _UF_SUFIXO.search((nome or "").strip())
    return m.group(1).upper() if m else None


def siglas_de(nome: str) -> set[str]:
    """Tokens que aparecem em CAIXA ALTA no nome original, normalizados.

    Serve pra separar sigla de orgao (UEAP, SEFIN, CRA, IFFar nao) de nome
    proprio em Title Case (Para, Sudeste, Minas). Uma fonte cita a sigla e a
    outra nao; isso e variacao de grafia, nao orgao diferente.
    """
    if not nome:
        return set()
    return {
        normalizar_nome(bruto)
        for bruto in re.findall(r"\b[A-ZÀ-Ý]{2,}\b", nome)
        if normalizar_nome(bruto)
    }


def mesma_entidade(nome_a: str, nome_b: str) -> bool:
    """Heuristica de identidade entre nomes de orgao vindos de fontes diferentes.

    O casamento olha so os tokens DISCRIMINANTES, isto e, descontando os tipos
    genericos de orgao. Sem isso "Prefeitura de Ponta Grossa" e "Prefeitura de
    Ponta Pora" compartilhariam {prefeitura, ponta} e passariam por iguais.
    Descontado o generico, sobra {grossa} contra {pora}, e nao casa.

    Se as duas UFs sao conhecidas e diferentes, e sempre orgao diferente —
    resolve o par "Camara de Tres Coracoes - MG" x "Camara de Tres Lagoas - MS".
    """
    ta, tb = set(tokens_nome(nome_a)), set(tokens_nome(nome_b))
    if not ta or not tb:
        return False

    uf_a, uf_b = extrair_uf(nome_a), extrair_uf(nome_b)
    if uf_a and uf_b and uf_a != uf_b:
        return False

    da, db = ta - TIPOS_ORGAO, tb - TIPOS_ORGAO
    # Nome so de tipo generico ("Prefeitura") nao identifica nada: exige igualdade.
    if not da or not db:
        return ta == tb

    if da == db:
        return True

    # Subconjunto so vale quando o que SOBRA e ruido de grafia, nao informacao.
    # Sobra legitima e de dois tipos, e so esses dois:
    #   - sigla de UF:  "Secretaria ... de Alagoas" x "... de Alagoas AL"
    #   - sigla do orgao: "UEAP - Universidade do Estado do Amapa" x
    #                     "Universidade do Estado do Amapa"
    # Sobra de palavra comum significa orgao diferente. Foi assim que o
    # "Instituto Federal ... do Para" casou com o "Instituto Federal ... do
    # Sudeste de Minas Gerais" numa varredura real: a sobra era {sudeste,
    # minas, gerais}, informacao pura.
    #
    # Sigla e detectada pelo CAIXA ALTA no nome original (UEAP, SEFIN, CRA),
    # que separa bem de nome proprio em Title Case (Para, Sudeste, Minas).
    permitido = _UFS_MINUSCULAS | siglas_de(nome_a) | siglas_de(nome_b)
    if da.issubset(db):
        return (db - da) <= permitido
    if db.issubset(da):
        return (da - db) <= permitido

    return False


def status_fingerprint(status: str) -> str:
    """Retorna um hash estavel para o `status` apos normalizacao.

    A normalizacao aplica, em ordem:
      1. lowercase
      2. NFKD + descarte de diacriticos (acentos)
      3. collapse de whitespace em espaco unico
      4. strip de pontuacao nas bordas
      5. SHA1 truncado a 16 caracteres

    Args:
        status: Texto do campo `status` retornado pela LLM.

    Returns:
        str: hash hexadecimal de 16 chars. String vazia retorna `""`.
    """
    if not status:
        return ""

    texto = status.lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = _WHITESPACE.sub(" ", texto).strip()
    texto = _PUNCT_BORDA.sub("", texto)

    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:16]
