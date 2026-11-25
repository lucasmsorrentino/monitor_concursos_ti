ENTREGUE
Esteira: implementador · agy-neon (gemini-4-neon) · nível M- · esforço medium · 2026-11-24 23:46 → 2026-11-24 23:53 (7 min)
Resumo: Adicionados 9 testes (11 casos parametrizados) em `tests/test_elegibilidade.py` pela costura publica `elegibilidade.decidir(candidato, politica)` que matam todas as nove mutacoes sobreviventes em `src/core/elegibilidade.py` (precedencia 0-1, 0-2, 1-2 e 3-4, parametros da `Politica`, `teto=0.0` e `uf`/`regiao` em branco) e removida a constante publica morta `MOTIVOS` de `src/core/elegibilidade.py`. Nenhum teste existente foi alterado, afrouxado, renomeado ou apagado, e a logica de decisao permaneceu intacta.
Arquivos: `tests/test_elegibilidade.py`, `src/core/elegibilidade.py` (ambos no `toca`; nenhum fora do `toca`)
Commits:
- `2f65e1c` test: travar precedencia, politica, teto zero e strings em branco na elegibilidade
- `aa3f48e` refactor: remover constante MOTIVOS sem consumidores em elegibilidade
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs` (condicao: sem variaveis de ambiente, sem marcadores, venv do repo; lint nao configurado) → base (`2ea449f`) 539 passed / 0 failed / 0 skipped · ponta (`aa3f48e`) 550 passed / 0 failed / 0 skipped (`tests/test_elegibilidade.py`: 51 base + 11 novos = 62 passed)
Testes que nascem verdes: Todos os 9 testes novos (11 casos) nascem verdes por desenho do ticket (o codigo de producao ja implementa SPEC-001 secao 4.2 corretamente; a prova e a tabela de mutacao abaixo):
- `test_estrela_vence_o_filtro_desligado` → mata `M1_swap_0_1`
- `test_estrela_sem_uf_e_sem_regiao_nao_leva_selo` → mata `M2_swap_0_2`
- `test_filtro_desligado_sem_uf_e_sem_regiao_nao_leva_selo` → mata `M3_swap_1_2`
- `test_federal_do_sul_sai_como_sul` → mata `M4_swap_3_4`
- `test_o_corte_vem_da_politica_nao_de_um_literal` → mata `M10_hardcode_corte`
- `test_o_limite_de_cargos_vem_da_politica` → mata `M11_hardcode_cargos`
- `test_a_isencao_de_esfera_vem_da_politica` → mata `M12_hardcode_esfera`
- `test_teto_zero_nao_e_teto_ausente` → mata `M13_teto_truthy`
- `test_uf_e_regiao_em_branco_contam_como_ausentes` (`""`, `" "`, `"\t"`) → mata `M20_empty_str_not_none`
Desvios e riscos: Sem `docs:` porque a docstring de `src/core/elegibilidade.py` ja documenta as nove regras e o tratamento de texto vazio e nao citava `MOTIVOS`. Sem `git push` conforme regra do projeto. Nota de contagem: o texto do aceite menciona "dez mutacoes acima", mas lista nove mutacoes nomeadas (`M1`, `M2`, `M3`, `M4`, `M10`, `M11`, `M12`, `M13`, `M20`) mais a limpeza da constante `MOTIVOS` (10 itens no total), todos cobertos abaixo.
Pendências: nenhuma.

## Tabela de mutacoes (prova)

Cada mutacao foi aplicada em `src/core/elegibilidade.py`, medida com `pytest tests/test_elegibilidade.py -k <teste> -q --tb=no` e `pytest tests/test_elegibilidade.py -q --tb=no`, e desfeita com `git checkout -- src/core/elegibilidade.py` (62 passed sem mutacao):

| Item / Mutacao | O que muda em `src/core/elegibilidade.py` | Teste que a mata | Falhas (teste alvo) | Falhas (`test_elegibilidade.py`) |
| :--- | :--- | :--- | :---: | :---: |
| `M1_swap_0_1` | Trocar regras 0 e 1 (`seguindo` vs `modo != "ativo"`) | `test_estrela_vence_o_filtro_desligado` | 1 failed | 1 failed / 61 passed |
| `M2_swap_0_2` | Trocar regras 0 e 2 (`seguindo` vs `uf is None and regiao is None`) | `test_estrela_sem_uf_e_sem_regiao_nao_leva_selo` | 1 failed | 3 failed / 59 passed |
| `M3_swap_1_2` | Trocar regras 1 e 2 (`modo != "ativo"` vs `uf is None and regiao is None`) | `test_filtro_desligado_sem_uf_e_sem_regiao_nao_leva_selo` | 1 failed | 1 failed / 61 passed |
| `M4_swap_3_4` | Trocar regras 3 e 4 (`sul` vs `federal`) | `test_federal_do_sul_sai_como_sul` | 1 failed | 1 failed / 61 passed |
| `M10_hardcode_corte` | `p.corte_fora_sul` → `10000.0` | `test_o_corte_vem_da_politica_nao_de_um_literal` | 1 failed | 1 failed / 61 passed |
| `M11_hardcode_cargos` | `p.cargos_total_inflado` → `10` | `test_o_limite_de_cargos_vem_da_politica` | 1 failed | 1 failed / 61 passed |
| `M12_hardcode_esfera` | `_contem(c.esfera, p.esferas_sem_corte)` → `_norm(c.esfera) == "federal"` | `test_a_isencao_de_esfera_vem_da_politica` | 1 failed | 1 failed / 61 passed |
| `M13_teto_truthy` | `c.teto is not None` → `c.teto` | `test_teto_zero_nao_e_teto_ausente` | 1 failed | 1 failed / 61 passed |
| `M20_empty_str_not_none` | Remover `or None` em `_norm` | `test_uf_e_regiao_em_branco_contam_como_ausentes` | 3 failed | 3 failed / 59 passed |
| Constante `MOTIVOS` | Remocao da constante publica sem consumidores (`src/core/elegibilidade.py:33-43`) | `git grep -n "MOTIVOS" src/ tests/` + suite inteira | — | 0 failed / 550 passed |

## Verificacao de `MOTIVOS`

- **Antes (`2ea449f`):** `git grep -n "MOTIVOS" src/ tests/`
  - `src/core/elegibilidade.py:33:MOTIVOS = frozenset({`
  - `tests/test_elegibilidade.py:21:MOTIVOS_DA_SPEC = {`
  - `tests/test_elegibilidade.py:309:            assert decidir(c, p).motivo in MOTIVOS_DA_SPEC`
- **Depois (`aa3f48e`):** `git grep -n "MOTIVOS" src/ tests/`
  - `tests/test_elegibilidade.py:21:MOTIVOS_DA_SPEC = {`
  - `tests/test_elegibilidade.py:373:            assert decidir(c, p).motivo in MOTIVOS_DA_SPEC`
