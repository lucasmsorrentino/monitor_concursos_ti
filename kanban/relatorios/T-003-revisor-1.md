APROVADO COM RESSALVAS
Esteira: revisor · agy-neon (gemini-4-neon) · nível G- · esforço high · 2026-11-23 18:00 → 2026-11-23 18:08 (9 min)
Resumo: A entrega cumpre integralmente os 9 itens de aceite de T-003, o contrato da SPEC-001 (secoes 3.4 e 4.2) e a ADR-0002, com TDD real comprovado em worktree destacado e 347/347 testes verdes sem regressao. O codigo de `src/core/elegibilidade.py` esta limpo e sem defeitos funcionais. As ressalvas sao lacunas de cobertura reveladas por mutacao em `tests/test_elegibilidade.py` (precedencia entre regras `entra=True`, variacao de campos da `Politica`, `teto=0.0` e strings vazias em `uf`/`regiao`) e possivel generalidade especulativa na constante `MOTIVOS` nao utilizada.
Arquivos: `src/core/elegibilidade.py`, `tests/test_elegibilidade.py` (ambos no `toca`; `fora_do_toca`: nenhum)
Commits:
- `51ca5cf` chore: esqueleto do modulo de elegibilidade (tipos do contrato e decidir)
- `4d840f1` test: as nove regras da elegibilidade, precedencia, selo e fail-open do modo
- `4a24c07` feat: decidir aplica as nove regras da elegibilidade, primeira que casa vence
- `e2bcc92` docs: contrato e precedencia da elegibilidade na docstring do modulo
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs` (sem variaveis de ambiente nem marcadores) → base (`768f60d`) 296 passed / 0 failed / 0 skipped · ponta (`e2bcc92`) 347 passed / 0 failed / 0 skipped (`pytest --collect-only -q`: 296 base + 51 novos = 347)
Testes que nascem verdes: 4 guardas de contrato verificadas no commit vermelho `4d840f1` (`test_politica_tem_os_padroes_da_spec`, `test_tipos_do_contrato_sao_congelados`, `test_candidato_comeca_sem_estrela_e_decisao_sem_selo`, `test_selo_e_o_texto_da_spec`), devidamente declaradas pelo implementador.
Desvios e riscos:
- Ressalva de codigo: 9 de 20 mutacoes aplicadas em `src/core/elegibilidade.py` sobreviveram a suite (detalhes em **Prova**), incluindo troca de ordem entre regras 0↔2 e 1↔2 (que vazaria selo em `seguindo=True` ou `modo="desligado"` quando `uf=regiao=None`) e hardcoding de `corte_fora_sul=10000.0`, `cargos_total_inflado=10` e `esferas_sem_corte=("federal",)`.
- Ressalva de codigo: possivel generalidade especulativa na constante publica `MOTIVOS` (`src/core/elegibilidade.py:33-43`), nao solicitada na SPEC-001 secao 3.4 nem no ticket e sem consumidores no modulo ou nos testes.
- Ressalva de relatorio (nao vira ticket): o implementador declarou em «Desvios e riscos» que `uf=""` e `regiao=""` caem na regra 2 com selo, mas nenhum teste em `tests/test_elegibilidade.py` cobre string vazia ou espacos em `uf`/`regiao` (mutacao `M20` sobreviveu).
Pendências: sugestao de ticket pequeno de endurecimento dos testes e limpeza de `MOTIVOS` (ver final do relatorio); fiacao no bot, parse do teto e classificacao da esfera permanecem nos respectivos tickets.

## Spec

1. **Aceite cumprido (9/9 itens verificados):**
   - **Tipos congelados e assinatura (`SPEC-001:116-140`):** `Candidato`, `Politica`, `Decisao` (`@dataclass(frozen=True)`) e `decidir(c: Candidato, p: Politica) -> Decisao` declarados em `src/core/elegibilidade.py:46-70, 88` com nomes, tipos, tuplas e padroes identicos a spec. Provados por `tests/test_elegibilidade.py:50-67`.
   - **As nove regras na ordem, primeira que casa vence, conjunto fechado de motivos (`SPEC-001:142-143, 194-204`):** implementadas na sequencia exata 0→8 em `src/core/elegibilidade.py:88-109`. Cada regra tem testes dedicados em `tests/test_elegibilidade.py:76-285` e invariante de conjunto fechado em `tests/test_elegibilidade.py:306-309`.
   - **Apenas regras 5 e 6 devolvem `entra=False` (`SPEC-001:201-202`, `ADR-0002:12-14`):** unicos `Decisao(False, ...)` em `src/core/elegibilidade.py:103, 106`. Provados pelos casos individuais e pela matriz em `tests/test_elegibilidade.py:312-317`.
   - **Selo exato nas regras 2 e 7, `None` nas demais (`SPEC-001:206`):** `SELO_NAO_VERIFICADO = "⚠️ salario nao verificado"` em `src/core/elegibilidade.py:31`, aplicado apenas em `src/core/elegibilidade.py:97, 108`. Codepoints conferidos (`U+26A0 U+FE0F U+0020`), identicos a `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md:206`. Provado por `tests/test_elegibilidade.py:70-71, 108-112, 262-272, 320-326`.
   - **`Politica.modo` fail-open (`SPEC-001:163, 197`, `kanban/REGRAS.md:20-21`):** `if p.modo != "ativo":` em `src/core/elegibilidade.py:91-92` (sem normalizar `modo`, de modo que `"ativo "`, `"ATIVO"`, `"sombra"`, `""` e `None` disparam a regra 1). Provado por `tests/test_elegibilidade.py:89-103`.
   - **Constante do selo exposta:** `SELO_NAO_VERIFICADO` exportada em `src/core/elegibilidade.py:31` e importada pelos testes em `tests/test_elegibilidade.py:13`.
   - **Comparacao de UF e esfera insensivel a caixa:** `_norm` + `_contem` em `src/core/elegibilidade.py:72-86, 94, 98, 100, 104`. Provada por `tests/test_elegibilidade.py:139-147, 183-185, 238-240`.
   - **`regiao` casa `"SUL"` sem caixa nem acento e `"NACIONAL"` nao e Sul (`SPEC-001:199, 207`):** `_norm` usa NFKD removendo `unicodedata.combining` + `strip().casefold()` (`src/core/elegibilidade.py:76-80, 95, 98`). Provado por `tests/test_elegibilidade.py:128-136, 165-167`.
   - **Sem dependencia externa nem acoplamento a bot/banco/scrapers:** apenas `from __future__ import annotations`, `unicodedata` e `dataclasses` em `src/core/elegibilidade.py:26-29`.

2. **Escopo (`git diff --stat 768f60d..HEAD`):**
   - `src/core/elegibilidade.py` (+109) e `tests/test_elegibilidade.py` (+326). Ambos no campo `toca`; zero arquivos fora do `toca`.
   - Ponto de atencao: `src/core/elegibilidade.py:33-43` exporta `MOTIVOS` (`frozenset`), nao especificado em `SPEC-001:113-143` nem pedido no aceite do ticket (embora declarado pelo implementador em «Desvios e riscos»). Nao altera comportamento; tratado como possivel generalidade especulativa em **Padrões**.

3. **Aderencia a SPEC-001 e ADR-0002:**
   - Regras 5 (`teto < corte_fora_sul`, estrito), 6 (`esfera == "municipal"` e `cargos_total > cargos_total_inflado`, estrito, disparando inclusive com `teto=None`) e 7 (`teto is None`) batem com `SPEC-001:201-203` e `ADR-0002:12-18, 31-34`.
   - Conselho profissional nao conta como federal (`ADR-0002:17-18`, `GLOSSARIO.md:34`), coberto em `tests/test_elegibilidade.py:188-190`.
   - Sem erros engolidos em silencio nem numeros magicos fora da spec.

## Prova

1. **Medicoes reais vs alegado pelo implementador** (condicao: sem variaveis de ambiente, sem marcadores, venv do repo):

| Medida | Comando | Implementador | Revisor (medido) | Status |
| :--- | :--- | :--- | :--- | :--- |
| Base (`768f60d`, worktree destacado) | `python -m pytest -q -rs` / `--collect-only -q` | 296 passed / 0 failed / 0 skipped | 296 passed / 0 failed / 0 skipped (`296 tests collected`) | Bate |
| Vermelho (`4d840f1`, worktree destacado, so `test_elegibilidade.py`) | `python -m pytest tests/test_elegibilidade.py -q --tb=line` | 47 failed (`NotImplementedError`) / 4 passed | 47 failed (`NotImplementedError` em `src/core/elegibilidade.py:49`) / 4 passed | Bate |
| Vermelho (`4d840f1`, suite inteira) | `python -m pytest -q --tb=no` | (nao informado) | 47 failed, 300 passed (296 base + 4 guardas) | Consistente |
| Ponta (`e2bcc92`) | `python -m pytest -q -rs` / `--collect-only -q` | 347 passed / 0 failed / 0 skipped (`347 tests collected`) | 347 passed / 0 failed / 0 skipped (`347 tests collected`; `test_elegibilidade.py`: `51 tests collected`) | Bate |
| Lint | `(nao configurado)` | nao rodou | nao configurado no repo, nao rodou | Bate |

   A conta fecha exatamente: `296 (base) + 51 (novos) = 347 (ponta)`.

2. **TDD (nivel G−: prova de vermelho de cada `test:`):**
   - Historico linear limpo em `768f60d..HEAD`: `51ca5cf` (`chore:` esqueleto) → `4d840f1` (`test:`, 326 linhas so em `tests/test_elegibilidade.py`) → `4a24c07` (`feat:`, +38/-1 so em `src/core/elegibilidade.py`) → `e2bcc92` (`docs:`, +24/-1 so docstring em `src/core/elegibilidade.py`).
   - Doc e codigo estao em commits separados; o unico `test:` (`4d840f1`) foi verificado em worktree destacado e falhou pelo motivo certo (`47 NotImplementedError`, nenhum erro de coleta/importacao/sintaxe), com as 4 guardas declaradas passando no esqueleto.

3. **Qualidade dos testes e prova por mutacao (worktree destacado em `HEAD`, conferido com `git diff --stat` antes de rodar `pytest tests/test_elegibilidade.py -q --tb=no`):**
   - Todos os 21 casos nomeados no Plano de testes do ticket estao presentes com os nomes pedidos (+30 casos/parametrizacoes adicionais).
   - Nenhum teste sofre de acoplamento a implementacao (testa apenas a costura publica `elegibilidade.decidir` e os tipos do contrato), tautologia (oraculo transcrito a mao da SPEC-001 4.2, inclusive `MOTIVOS_DA_SPEC` independente de `MOTIVOS`) ou duble fora da fronteira (sem dubles).
   - **Resultado das 20 mutacoes reais em `src/core/elegibilidade.py`:**
     - **11 KILLED** (todas as regras de recusa/silencio, fronteiras e selo direto):
       - `M5_swap_4_5` (trocar regras 4↔5): KILLED (4 failed)
       - `M6_swap_5_6` (trocar regras 5↔6): KILLED (1 failed)
       - `M7_swap_6_7` (trocar regras 6↔7): KILLED (1 failed)
       - `M8_corte_le` (`<` → `<=` na regra 5): KILLED (1 failed)
       - `M9_cargos_ge` (`>` → `>=` na regra 6): KILLED (1 failed)
       - `M14_no_selo_r2` (tirar selo da regra 2): KILLED (2 failed)
       - `M15_no_selo_r7` (tirar selo da regra 7): KILLED (3 failed)
       - `M16_selo_r8` (colocar selo na regra 8): KILLED (7 failed)
       - `M17_no_regiao_sul` (remover `or regiao == "sul"`): KILLED (6 failed)
       - `M18_norm_modo` (normalizar `p.modo`): KILLED (2 failed)
       - `M19_or_uf_regiao` (`and` → `or` na regra 2): KILLED (11 failed)
     - **9 SURVIVED** (ressalva de cobertura em `tests/test_elegibilidade.py`):
       - `M1_swap_0_1` (trocar regras 0↔1: `seguindo=True` com `modo="desligado"`): 51 passed
       - `M2_swap_0_2` (trocar regras 0↔2: `seguindo=True` com `uf=None, regiao=None` receberia selo): 51 passed
       - `M3_swap_1_2` (trocar regras 1↔2: `modo="desligado"` com `uf=None, regiao=None` receberia selo): 51 passed
       - `M4_swap_3_4` (trocar regras 3↔4: federal do Sul devolveria `"federal"` em vez de `"sul"`): 51 passed
       - `M10_hardcode_corte` (`p.corte_fora_sul` → `10000.0`): 51 passed
       - `M11_hardcode_cargos` (`p.cargos_total_inflado` → `10`): 51 passed
       - `M12_hardcode_esfera` (`_contem(c.esfera, p.esferas_sem_corte)` → `_norm(c.esfera) == "federal"`): 51 passed
       - `M13_teto_truthy` (`c.teto is not None` → `c.teto`, falharia para `teto=0.0`): 51 passed
       - `M20_empty_str_not_none` (remover `or None` em `_norm`, quebrando `uf=""`/`regiao=""`): 51 passed

## Padrões

1. **Regras do projeto (`kanban/REGRAS.md` e `GLOSSARIO.md`):**
   - PT-BR em codigo, docstrings, comentarios e commits; identificadores e comentarios sem acento (unicas ocorrencias nao-ASCII sao o emoji `⚠️` obrigatorio em `SELO_NAO_VERIFICADO` e as entradas `"SÚL"`/`"súl"` no teste de normalizacao).
   - Zero referencias a `T-NNN` em codigo, testes ou mensagens de commit.
   - Zero segredos, zero dependencias novas, zero chamadas de rede, zero arquivos proibidos tocados.
   - Vocabulario de `GLOSSARIO.md` respeitado (`elegibilidade`, `teto do concurso`, `esfera`, `corte fora do Sul`, `municipal inflado`, `fail-open`, `area`).

2. **Cheiros de código:**
   - **Possivel generalidade especulativa** em `src/core/elegibilidade.py:33-43`: `MOTIVOS` (`frozenset`) e exportado sem estar na SPEC-001 secao 3.4 nem ser consumido pelo proprio modulo ou pelos testes. Conserto: apagar `MOTIVOS` ate existir consumidor real (ou passar a usa-lo se um ticket futuro exigir a lista exportada).
   - **Pequena redundancia de normalizacao** (nota leve) em `src/core/elegibilidade.py:94, 98`: `uf` ja passa por `_norm(c.uf)` na linha 94 e e re-normalizado dentro de `_contem(uf, p.ufs_sem_corte)` na linha 98. Conserto opcional: manter simples como esta ou normalizar uma vez fora de `_contem` (nao e prioritario).

## Sugestao de ticket para as ressalvas de codigo

- **Titulo:** Elegibilidade: endurecer testes de precedencia/parametros da Politica e revisar exportacao de `MOTIVOS`
- **Nivel:** P
- **Toca:** `[tests/test_elegibilidade.py, src/core/elegibilidade.py]`
- **Escopo sugerido:** acrescentar em `tests/test_elegibilidade.py` casos cobrindo (a) precedencia 0↔1, 0↔2, 1↔2 e 3↔4 (especialmente `seguindo=True` e `modo="desligado"` com `uf=None, regiao=None` sem selo), (b) variacao de `corte_fora_sul`, `cargos_total_inflado` e `esferas_sem_corte` na `Politica`, (c) `teto=0.0` e `uf=""`/`regiao=""` com espacos; avaliar remocao de `MOTIVOS` em `src/core/elegibilidade.py:33-43` caso nenhum ticket de fiacao o importe.
