ENTREGUE
Esteira: implementador · glm-flash (zai-coding-plan/glm-5.3-flash) · nível P+ · esforço high · 2026-11-23 11:16 → 2026-11-23 11:24 (9 min)
Resumo: Implementado o `teto_de(texto: str | None) -> float | None` em `src/utils/salario.py`: le o maior valor em reais do texto livre do PCI (formato brasileiro, faixa com topo, "mil" por extenso), com banda de sanidade R$ 500,00–R$ 80.000,00 e fail-open para `None`. TDD em 4 commits (esqueleto → vermelho → verde → docs), branch do ticket pushada.
Arquivos: `src/utils/salario.py` (toca), `tests/test_salario.py` (toca). Nenhum arquivo fora do «toca». `.esteira/` nao commitado (regra comum).
Commits:
- `2e20bb2` chore: esqueleto de src/utils/salario.py com a assinatura do teto_de
- `51d2bab` test: teto_de le os formatos de salario que o texto do pci usa
- `3b39c3e` feat: teto_de extrai o maior salario do texto, com banda de sanidade
- `5462e73` docs: contrato do teto_de no docstring do modulo
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q` → base 296 passed / 0 failed · rodada vermelha 10 failed (todos `NotImplementedError`, falha nascida do corpo do codigo sob teste — sem erro de coleta/importacao/sintaxe) · ponta 306 passed / 0 failed. Condicao: sem variaveis de ambiente especiais, sem marcadores; `pytest.ini` com `--strict-markers`, nenhum teste pulado (`-rs` sem saida de skip; coleta via `--collect-only -q` = 296 na base). Lint: nao configurado no projeto, nada a rodar.
Testes que nascem verdes: nenhum — os 10 do plano do ticket nascem vermelhos contra o esqueleto `NotImplementedError` e so ficam verdes no `feat:`.
Desvios e riscos:
- Nenhum desvio entre ticket e SPEC-001 §3.2 / GLOSSARIO / ADR-0002; a banda de sanidade e refinamento declarado da spec (nota do arquiteto), registrada no docstring com o apontamento para a secao.
- Valor montado como string e convertido uma unica vez (`float("8628.87")`) para nao sofrer drift de soma em ponto flutuante contra os literais do oraculo.
- A regex so le valores precedidos de "R$"; texto que cite salario sem o simbolo (ex.: "vencimento de 8.628,87") nao e lido — nao aparece no corpus do campo `vagas_salario` nem nas fixtures. Revisor deve olhar o `_RE_MIL.match(texto, m.end())`: o multiplicador "mil" exige a palavra colada ao numero.
- Custo do ticket ficou em P+ como o arquiteto previu: regex com alternativa ancorada em grupos de milhar (`\d{1,3}(?:\.\d{3})+|\d+`) para nao truncar numeros de 4+ digitos sem separador.
Pendências: consumidor do `teto_de` (elegibilidade e coluna `salario_teto`) fica para os proximos tickets da SPEC-001; somar beneficio e salario por cargo seguem fora de escopo (ADR-0002).
