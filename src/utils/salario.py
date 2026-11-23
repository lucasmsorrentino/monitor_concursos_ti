"""Teto do concurso extraido do texto livre que o PCI publica.

O contrato esta na SPEC-001, secao 3.2: o campo `vagas_salario` do MCP traz
texto livre ("454 vagas ate R$ 8.628,87") e a decisao de elegibilidade
precisa desse valor como numero.
"""


def teto_de(texto: str | None) -> float | None:
    raise NotImplementedError
