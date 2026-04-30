"""Utilitarios de normalizacao de texto.

Contem `status_fingerprint`, usado para deduplicar o campo `status` entre
execucoes do bot. A LLM tende a reformular o mesmo conteudo com pequenas
variacoes (case, acentos, espacos, pontuacao), e a comparacao textual
pura dispara falsos positivos de "mudanca". O fingerprint normaliza e
retorna um SHA1 curto estavel.
"""
import hashlib
import re
import unicodedata


_PUNCT_BORDA = re.compile(r"^[^\w]+|[^\w]+$", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")


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
