APROVADO COM RESSALVAS
Esteira: revisor · agy-argon (gemini-4-argon) · nível M- · esforço medium · 2026-11-23 18:00 → 2026-11-23 18:03 (4 min)
Resumo: `src/utils/salario.py` entrega `teto_de(texto: str | None) -> float | None` conforme a SPEC-001 (§3.2), `GLOSSARIO.md`, ADR-0002 e os oito itens do critério de aceite de T-001. Os 10 testes de `tests/test_salario.py` cobrem todas as costuras e casos de borda do plano com literais independentes, passando de 296 testes na base para 306 na ponta (0 falhas, 0 pulados). Há apenas uma ressalva de processo: o implementador fez `git push` da branch para o `origin`, violando a regra do projeto «Nao faca push».
Arquivos: `src/utils/salario.py` (no `toca`), `tests/test_salario.py` (no `toca`). Fora do `toca`: nenhum.
Commits:
- `2e20bb2` chore: esqueleto de src/utils/salario.py com a assinatura do teto_de
- `51d2bab` test: teto_de le os formatos de salario que o texto do pci usa
- `3b39c3e` feat: teto_de extrai o maior salario do texto, com banda de sanidade
- `5462e73` docs: contrato do teto_de no docstring do modulo
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q` → base 296 passed / 0 failed · ponta 306 passed / 0 failed
Testes que nascem verdes: nenhum
Desvios e riscos: Ressalva de processo (para retro, não gera ticket): o implementador executou `git push` para `origin/t/T-001-teto-do-concurso-a-partir-do-texto-do-pc`, contrariando a regra do projeto «Nao faca push. O trabalho fica em commit local, na branch do worktree».
Pendências: Consumidores de `teto_de` (elegibilidade e persistência na coluna `salario_teto`) ficam para os demais tickets da SPEC-001.

## Spec

1. **Critério de aceite cumprido Integralmente:**
   - Assinatura e retorno do maior valor ou `None`: `src/utils/salario.py:37-69` (`teto_de(texto: str | None) -> float | None`).
   - Formato brasileiro com e sem separador de milhar e vírgula decimal (`"R$ 8.628,87"` → `8628.87`, `"R$ 950,00"` → `950.0`): `src/utils/salario.py:29,59-63`, provado por `tests/test_salario.py:10-14`.
   - Enunciados reais de `vagas_salario` (com vagas, sem vagas e `"Cadastro de reserva"` / `"Cadastro de Reserva"`): provados por `tests/test_salario.py:10-19`.
   - Faixa devolvendo o topo (`"Os vencimentos mensais vao de R$ 1.840,36 a R$ 18.540,71"` → `18540.71`): `src/utils/salario.py:69` (`max(valores)`), provado por `tests/test_salario.py:20-24`.
   - Multiplicador `"mil"` por extenso aplicado antes da banda de sanidade (`"salarios de ate R$ 6,6 mil"` → `6600.0`, `"R$ 12 mil"` → `12000.0`): `src/utils/salario.py:34,64-65`, provado por `tests/test_salario.py:26-28`.
   - Banda de sanidade (`500.00 <= valor <= 80000.00`) ignorando taxa de inscrição, valor/hora e valor absurdo, e devolvendo `None` quando só há valores fora da banda: `src/utils/salario.py:23-24,66-69`, provado por `tests/test_salario.py:30-40`.
   - Fail-open para `None`, `""`, `"Vagas"` e `"a combinar"` sem exceção: `src/utils/salario.py:55-56,69`, provado por `tests/test_salario.py:42-46`.
   - Sem dependência externa (apenas `import re` da stdlib): `src/utils/salario.py:17`.
2. **Escopo:** `git diff --stat 768f60de452c8379cdd13f9948d1ef192615405b..HEAD` toca exclusivamente `src/utils/salario.py` (+69) e `tests/test_salario.py` (+46), batendo exatamente com o campo `toca` do ticket. Nenhum código especulativo foi introduzido.
3. **Aderência à Spec e ADRs:**
   - Confere com `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md:94-103` (§3.2 `src/utils/salario.py`), incluindo a banda de sanidade de `R$ 500,00` a `R$ 80.000,00`.
   - Confere com `docs/adr/0002-elegibilidade-pelo-teto-do-concurso.md:7-14,34` e com o conceito de **Teto do concurso** e **Fail-open** de `GLOSSARIO.md:26-30,51-54`.

## Prova

4. **Números reais medidos na revisão:**
   - Condição de medição: Windows, venv do repositório, sem variáveis de ambiente extras nem filtros de marcadores (`pytest.ini` com `--strict-markers`), sem testes pulados (`-rs`). Lint não configurado no repositório.
   - Base (`768f60de452c8379cdd13f9948d1ef192615405b`, medida em worktree destacado):
     - Comando: `& "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs`
     - Resultado medido pelo revisor: `296 passed in 23.57s` (implementador afirmou: `296 passed / 0 failed`).
   - Ponta (`5462e73fa87fa8536af68ff91d3c6759a6f34ae1`):
     - Comando: `& "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs` e `--collect-only -q`
     - Resultado medido pelo revisor: `306 passed in 24.85s` / `306 tests collected` (implementador afirmou: `306 passed / 0 failed`).
   - Conta fecha: 296 (base) + 10 novos em `tests/test_salario.py` = 306 (ponta).
5. **Ciclo TDD (nível P+):**
   - `git log --format="%h %s" 768f60de..HEAD` mostra a sequência limpa `2e20bb2` (`chore:` esqueleto com `NotImplementedError`) → `51d2bab` (`test:` 10 testes) → `3b39c3e` (`feat:` implementação) → `5462e73` (`docs:` docstrings). Documentação e código em commits separados.
6. **Qualidade dos testes:**
   - Os 10 testes em `tests/test_salario.py` testam exclusivamente pela costura pública `salario.teto_de`, usam literais independentes (sem tautologia), não usam dublês e não acoplam em detalhes internos (`_RE_VALOR`, `_RE_MIL`, `_TETO_MINIMO`, `_TETO_MAXIMO`).
   - Qualquer inversão de limite da banda (`< 500` ou `> 80000`), remoção do multiplicador `1000.0` ou troca de `max` por `min`/primeiro elemento quebra diretamente `test_teto_de_ignora_taxa_de_inscricao`, `test_teto_de_ignora_valor_absurdo`, `test_teto_de_le_mil_por_extenso` ou `test_teto_de_em_faixa_devolve_o_topo`.

## Padrões

7. **Regras do projeto:**
   - Código, comentários, docstrings e mensagens de commit em português do Brasil, sem acentos nos identificadores e comentários (`src/utils/salario.py`, `tests/test_salario.py`).
   - Nenhum ID de ticket (`T-001`) em código, docstring ou comentário.
   - Estilo espelha `src/scrapers/pci_comum.py` (regex compiladas no topo do módulo com comentários explicando as frases reais do PCI).
   - **Ressalva de processo (retro):** o implementador declarou no próprio relatório («branch do ticket pushada») e `git branch -vv` confirma `origin/t/T-001-teto-do-concurso-a-partir-do-texto-do-pc` apontando para `5462e73`. Isso viola a regra explícita do projeto: «Nao faca push. O trabalho fica em commit local, na branch do worktree». Como é ato de processo já consumado e não afeta o código nem o estado do repositório local, registra-se como ressalva de processo para a retrospectiva.
8. **Cheiros de código:**
   - Nenhum cheiro identificado no diff.
