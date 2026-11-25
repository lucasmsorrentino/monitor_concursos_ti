ENTREGUE
Esteira: implementador · agy-hydrogen (gemini-4-hydrogen) · nível P- · esforço medium · 2026-11-24 23:53 → 2026-11-24 23:58 (5 min)
Resumo: O bloco `== Config efetiva ==` de `scripts/diagnostico_producao.sh` passou a imprimir, por area, a porta `pci_mcp` (`ligada (N termo(s))` ou `desligada`) e os parametros do filtro salarial (`filtro_salarial`, `corte_fora_sul` e `resumo_filtrados`) com os padroes da SPEC-001 secao 3.6 (`desligado`, `0`, `nunca`) quando ausentes. Os cinco testes do plano foram adicionados em `tests/test_diagnostico_producao.py` e validados em ciclo TDD. Nao ha documentacao a atualizar fora do codigo/testes do escopo.
Arquivos: scripts/diagnostico_producao.sh, tests/test_diagnostico_producao.py
Commits: e0319c2 test: exige porta pci_mcp e filtro salarial na config efetiva do diagnostico; e3978cb feat: imprime porta pci_mcp e filtro salarial na config efetiva do diagnostico
Testes: "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q → base 539 passed / 0 failed · ponta 544 passed / 0 failed (verificado tambem `bash scripts/diagnostico_producao.sh | grep -ciE 'bot[0-9]{6,}:|ZAI_API_KEY=[^<]'` devolvendo `0`)
Testes que nascem verdes: `test_config_quebrada_degrada_e_o_script_sai_com_zero` (guarda: o bloco `PY_CONFIG` ja degradava JSON invalido com `invalido: JSON ilegivel` e saida 0 antes da mudanca)
Desvios e riscos: Nenhum desvio de escopo. Nao ha o que documentar em `docs/` para este ticket.
Pendências: Nenhuma.
