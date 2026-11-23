"""Teto do concurso extraido do texto livre que o PCI publica.

O contrato esta na SPEC-001, secao 3.2: o campo `vagas_salario` do MCP traz
texto livre ("454 vagas ate R$ 8.628,87") e a decisao de elegibilidade
precisa desse valor como numero.
"""
import re

# Banda de sanidade da SPEC-001, secao 3.2: salario mensal de concurso no
# Brasil vive dentro dessa faixa. Fora dela e taxa de inscricao ("A taxa e de
# R$ 65,00"), valor por hora ("R$ 32,64 por hora") ou numero solto, e nao
# pode virar teto.
_TETO_MINIMO = 500.00
_TETO_MAXIMO = 80000.00

# Valor em reais no formato brasileiro, como o campo `vagas_salario` do MCP
# escreve: "R$ 8.628,87" (milhar com ponto, decimal com virgula). Pega tambem
# "R$ 950,00" e "R$ 12" (sem centavos).
_RE_VALOR = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?")

# Multiplicador "mil" colado ao valor, de noticia do PCI: "salarios de ate
# R$ 6,6 mil" e "R$ 12 mil". Tem que multiplicar ANTES da banda de sanidade,
# senao o 6,6 morre como valor abaixo do piso e o salario real se perde.
_RE_MIL = re.compile(r"\s*mil\b", re.IGNORECASE)


def teto_de(texto: str | None) -> float | None:
    """Devolve o maior valor em reais citado no texto, ou None."""
    if not texto:
        return None

    valores = []
    for m in _RE_VALOR.finditer(texto):
        bruto = m.group(1).replace(".", "")
        if m.group(2):
            bruto = bruto + "." + m.group(2)
        valor = float(bruto)
        if _RE_MIL.match(texto, m.end()):
            valor *= 1000.0
        if _TETO_MINIMO <= valor <= _TETO_MAXIMO:
            valores.append(valor)

    return max(valores) if valores else None
