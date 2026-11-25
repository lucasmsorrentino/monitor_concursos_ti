APROVADO COM RESSALVAS
Esteira: revisor · glm-go (opencode-go/glm-5.3) · nível M+ · esforço high · 2026-11-25 00:07 → 2026-11-25 00:13 (7 min)
Resumo: A entrega cumpre o aceite do T-013 por inteiro: os 9 testes novos (11 casos) matam as nove mutações sobreviventes, a constante morta `MOTIVOS` saiu sem quebrar consumidor algum, e nenhum teste existente foi tocado. Reapliquei as nove mutações num worktree destacado e medi cada falha eu mesmo; todas batem com a tabela do implementador. As ressalvas são só de processo (par `test:` → `refactor:` sem `feat:`/`fix:`, e ausência do `docs:`), já justificadas e não bloqueiam.
Arquivos: `tests/test_elegibilidade.py` (toca), `src/core/elegibilidade.py` (toca). Nenhum fora do `toca`.
Commits: `2f65e1c` test: travar precedencia, politica, teto zero e strings em branco na elegibilidade · `aa3f48e` refactor: remover constante MOTIVOS sem consumidores em elegibilidade
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs` (condicao: venv do repo, sem variaveis de ambiente, sem marcadores) → base `2ea449f` 539 passed / 0 failed / 0 skipped (medida minha em worktree destacado; igual a do implementador) · ponta `aa3f48e` 550 passed / 0 failed / 0 skipped (medida minha). Conta fecha: 539 + 11 casos novos = 550. Lint: nao configurado.
Testes que nascem verdes: todos os 9 testes novos (11 casos), por desenho do ticket — o arquiteto inverteu o TDD neste ticket: o codigo de producao ja cumpre SPEC-001 secao 4.2 e a prova e a tabela de mutacao, nao o log vermelho. Confirmei a tabela (bloco Prova), nao o vermelho.
Desvios e riscos: ver ressalvas no fim de cada bloco; nenhuma ressalva de codigo.
Pendências: nenhuma.

## Spec: entregou o que foi pedido?

1. **Aceite, item a item.** Li o aceite antes do diff e achei, para cada mutação, o teste que a mata e o código que a cumpre:
   - `M1`: `test_estrela_vence_o_filtro_desligado` (`tests/test_elegibilidade.py:87`) — `seguindo=True` com `modo="desligado"` sai `seguindo`, não `filtro_desligado`.
   - `M2`: `test_estrela_sem_uf_e_sem_regiao_nao_leva_selo` (`:93`) — sai `seguindo` sem selo.
   - `M3`: `test_filtro_desligado_sem_uf_e_sem_regiao_nao_leva_selo` (`:118`) — sai `filtro_desligado` sem selo.
   - `M4`: `test_federal_do_sul_sai_como_sul` (`:197`) — `uf="PR"`, `regiao="SUL"`, `esfera="federal"` sai `sul`.
   - `M10`: `test_o_corte_vem_da_politica_nao_de_um_literal` (`:254`) — `corte_fora_sul=3000.0` com teto 5000 (entre 3000 e 10000) e teto 2500.
   - `M11`: `test_o_limite_de_cargos_vem_da_politica` (`:314`) — `cargos_total_inflado=3`, casos no limite (3) e acima (5).
   - `M12`: `test_a_isencao_de_esfera_vem_da_politica` (`:226`) — isenta `"estadual"`; o federal deixa de ser isento e cai no corte.
   - `M13`: `test_teto_zero_nao_e_teto_ausente` (`:262`) — `teto=0.0` sai `abaixo_do_corte`, não `sem_evidencia`.
   - `M20`: `test_uf_e_regiao_em_branco_contam_como_ausentes` (`:134`), parametrizado com `""`, `" "`, `"\t"`, com selo.
   - `MOTIVOS`: constante removida de `src/core/elegibilidade.py`. `git grep -n "MOTIVOS" src/ tests/` (depois) só acha `MOTIVOS_DA_SPEC` no teste, o oráculo escrito à mão da spec; grep no repo inteiro idem. A suíte verde na ponta (550) prova que nenhum importador quebrou.
   - Suite verde e nada afrouxado: o diff de `tests/test_elegibilidade.py` é só adição (+64/-0); nenhum teste renomeado, afrouxado ou apagado.
   - A tabela das mutações está no relatório do implementador, com 10 linhas, cada uma com o teste e as falhas.
2. **Escopo.** `git diff --stat 2ea449f..HEAD` toca exatamente `src/core/elegibilidade.py` (−12 linhas, a constante) e `tests/test_elegibilidade.py` (+64) — os dois do `toca`. Nenhum comportamento novo, nenhum ganho especulativo.
3. **Contra a spec.** Os esperados são literais transcritos da tabela da SPEC-001 seção 4.2 (regras 0–8, `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md:194-208`); conferi caso a caso e batem. Motivo `"federal"` para esfera isenta que não é federal é o vocabulário fechado da spec (`:143`), não erro do teste. A ADR-0002 (federal isento, municipal inflado, fail-open) é respeitada — o diff não muda comportamento algum. O selo é o texto da spec (`:206`). Nota de metadata: o campo `spec:` do ticket cita R-01/R-02, que são regras da porta do MCP (seção 4.1), sem relação com elegibilidade; provável engano do ticket, sem efeito na entrega.

## Prova: o verde vale?

4. **Números reais, medidos por mim.**
   - Ponta (`aa3f48e`, worktree do ticket): `pytest -q -rs` → **550 passed / 0 failed / 0 skipped** (implementador: 550 — igual).
   - Base (`2ea449f`, worktree destacado `_w13b`, depois removido): `pytest -q --tb=no -rs` → **539 passed / 0 failed / 0 skipped** (implementador: 539 — igual).
   - Conta fecha: 539 + 11 casos novos = 550; `tests/test_elegibilidade.py` passou de 51 para 62.
5. **TDD.** `git log 2ea449f..HEAD`: `2f65e1c test:` → `aa3f48e refactor:`. O arquiteto inverteu a prova neste ticket (testes nascem verdes; a prova é a mutação), então não havia vermelho a provar — segui a nota e conferi a tabela, item 6 abaixo. Verdelho de `MOTIVOS` conferido por grep antes/depois.
6. **Mutação por mutação, medida por mim** em worktree destacado em HEAD (`_w13m`, depois removido), cada mutação confirmada com `git diff --stat` antes de confiar no vermelho, medida com `pytest tests/test_elegibilidade.py -q --tb=no -rf` e desfeita com `git checkout -- src/core/elegibilidade.py`. Sem mutação: 62 passed.

   | Mutação | O que apliquei | Teste que falhou | Minha medida | Tabela do implementador |
   | :-- | :-- | :-- | :-- | :-- |
   | `M1_swap_0_1` | regras 0 e 1 trocadas | `test_estrela_vence_o_filtro_desligado` | 1 failed / 61 passed | 1/61 — igual |
   | `M2_swap_0_2` | regra 2 na frente (2,1,0) | `test_estrela_sem_uf_e_sem_regiao_nao_leva_selo` | 3 failed / 59 passed | 3/59 — igual |
   | `M3_swap_1_2` | regras 1 e 2 trocadas (0,2,1) | `test_filtro_desligado_sem_uf_e_sem_regiao_nao_leva_selo` | 1 failed / 61 passed | 1/61 — igual |
   | `M4_swap_3_4` | esfera antes do Sul | `test_federal_do_sul_sai_como_sul` | 1 failed / 61 passed | 1/61 — igual |
   | `M10_hardcode_corte` | `p.corte_fora_sul` → `10000.0` | `test_o_corte_vem_da_politica_nao_de_um_literal` | 1 failed / 61 passed | 1/61 — igual |
   | `M11_hardcode_cargos` | `p.cargos_total_inflado` → `10` | `test_o_limite_de_cargos_vem_da_politica` | 1 failed / 61 passed | 1/61 — igual |
   | `M12_hardcode_esfera` | `_contem(...)` → `_norm(c.esfera) == "federal"` | `test_a_isencao_de_esfera_vem_da_politica` | 1 failed / 61 passed | 1/61 — igual |
   | `M13_teto_truthy` | `c.teto is not None` → `c.teto` | `test_teto_zero_nao_e_teto_ausente` | 1 failed / 61 passed | 1/61 — igual |
   | `M20_empty_str_not_none` | `or None` removido do `_norm` | `test_uf_e_regiao_em_branco_contam_como_ausentes` (3 casos) | 3 failed / 59 passed | 3/59 — igual |

   Nota sobre M2: apliquei também a variante de troca (1,2,0), que dá 2 failed / 60 passed; as duas leituras de «trocar 0 e 2» matam o teste alvo. A da tabela (2 na frente) é a que reproduz as 3 falhas.

   **Qualidade dos testes.** Todos afirmam pela costura pública `decidir(candidato, politica)`, o esperado é literal (nada recalculado pelo código), e não há dublê algum — módulo puro. Sem os três defeitos: nenhum teste de função privada, nenhum tautológico, nenhum dublê. As mutações acima provam que cada um pega o erro que alega pegar.

## Padrões: está escrito como o projeto escreve?

7. **Regras do projeto.** Commits em português do Brasil, sem ID de quadro em código (`T-013` não aparece no diff), sem dependência nova, sem segredo, sem rede no teste, sem push. A remoção da constante é só subtração; nada de schema, config ou `bot.py`. Nenhuma regra violada.
8. **Cheiros.** Nenhum no diff. Os testes novos reutilizam os helpers do arquivo (`_cand`, `MAIS_FILTRAVEL`, `dataclasses.replace`) no mesmo estilo das seções vizinhas; os comentários citam exemplos reais (UFPR, UFSC, IFPR), como o resto do arquivo.

## Ressalvas (processo e relatório, não de codigo)

- **Sem commit `docs:`** e o par fechou como `test:` → `refactor:` (não `feat:`/`fix:`): desvio de processo já commitado, justificado (os testes nascem verdes por desenho; a docstring de `src/core/elegibilidade.py:1-24` já documenta as nove regras e o texto vazio, e nunca citou `MOTIVOS`). Consertar exigiria reescrever história, o que é proibido; pesa só na retro.
- **Campo `spec:` do ticket cita R-01/R-02** (regras da porta do MCP), provável engano de metadata do ticket; sem efeito no que foi entregado.

Ressalva de codigo vira sugestao de ticket novo: nenhuma — nada a sugerir.
