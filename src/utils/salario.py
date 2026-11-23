"""Teto do concurso extraido do texto livre que o PCI publica.

O PCI nunca publica o salario do cargo (ADR-0002): a unica evidencia salarial
e o teto do concurso, que chega como texto livre no campo `vagas_salario` do
MCP ("454 vagas ate R$ 8.628,87", "Vagas ate R$ 21.825,31", "Cadastro de
reserva ate R$ 14.189,97") e em noticia do edital ("Os vencimentos mensais
vao de R$ 1.840,36 a R$ 18.540,71", "salarios de ate R$ 6,6 mil").

`teto_de` le esse texto e devolve o maior valor em reais, ou None quando nao
ha valor aproveitavel. Fail-open: entrada vazia, ilegivel ou sem valor dentro
da banda de sanidade devolve None, nunca excecao — quem consome decide o que
fazer com teto desconhecido (o concurso entra, marcado).

Modulo sem dependencia externa de proposito (so `re` da stdlib), como
`src/utils/text.py`.
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
    """Devolve o maior valor em reais citado no texto, ou None.

    Le o formato brasileiro ("R$ 8.628,87" vira 8628.87), faixa com topo
    ("de R$ 1.840,36 a R$ 18.540,71" devolve 18540.71) e o multiplicador
    "mil" ("R$ 6,6 mil" devolve 6600.0). Banda de sanidade (SPEC-001,
    secao 3.2): valor abaixo de R$ 500,00 ou acima de R$ 80.000,00 e
    ignorado, para taxa de inscricao e valor por hora nao virarem salario
    mensal. Texto em que so ha valores fora da banda devolve None.

    Args:
        texto: conteudo do campo `vagas_salario` ou trecho de noticia do
            PCI. None e string vazia devolvem None.

    Returns:
        float | None: o maior valor dentro da banda de sanidade, ou None
        quando nao ha valor aproveitavel.
    """
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
