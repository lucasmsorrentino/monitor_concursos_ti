ENTREGUE
Esteira: implementador · opus (claude-opus-5-5) · nível G- · esforço high · 2026-11-23 11:16 → 2026-11-23 11:21 (5 min)
Resumo: `src/core/elegibilidade.py` expoe `Candidato`, `Politica`, `Decisao` (frozen, campos e padroes da SPEC-001 3.4 sem renomear), `decidir`, `SELO_NAO_VERIFICADO` e `MOTIVOS`. `decidir` aplica as nove regras da SPEC-001 4.2 na ordem, a primeira que casa vence; so as regras 5 e 6 recusam; selo so nas 2 e 7. Modo diferente de "ativo" exato cai na regra 1 (fail-open). UF, regiao e esfera comparam sem caixa e sem acento (NFKD + casefold + strip). O unico import e da stdlib (`unicodedata`, `dataclasses`).
Arquivos: src/core/elegibilidade.py, tests/test_elegibilidade.py (ambos no «toca»)
Commits:
  51ca5cf chore: esqueleto do modulo de elegibilidade (tipos do contrato e decidir)
  4d840f1 test: as nove regras da elegibilidade, precedencia, selo e fail-open do modo
  4a24c07 feat: decidir aplica as nove regras da elegibilidade, primeira que casa vence
  e2bcc92 docs: contrato e precedencia da elegibilidade na docstring do modulo
Testes: "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q, sem variavel de ambiente nem marcador
  base (768f60d): 296 passed / 0 failed / 0 skipped
  vermelho (4d840f1, so tests/test_elegibilidade.py): 47 failed / 4 passed; os 47 falham todos com NotImplementedError (agrupado via `--tb=line | sort | uniq -c` → «47 NotImplementedError»)
  ponta (e2bcc92): 347 passed / 0 failed / 0 skipped; `pytest --collect-only -q` → «347 tests collected» (296 + 51 novos)
  Lint: nao configurado no projeto, nao rodou.
Testes que nascem verdes: 4 guardas do contrato, que so dependem dos tipos e da constante do esqueleto: `test_politica_tem_os_padroes_da_spec`, `test_tipos_do_contrato_sao_congelados`, `test_candidato_comeca_sem_estrela_e_decisao_sem_selo`, `test_selo_e_o_texto_da_spec`. Estao la para travar o contrato que os outros tickets consomem.
Desvios e riscos:
  - Todos os 21 testes do plano estao la com o nome do plano; acrescentei casos (regiao "Súl"/" Sul ", esfera "FEDERAL"/"Municipal", conselho_profissional nao e federal, cargos_total=11, abaixo_do_corte vence municipal_inflado, ufs_sem_corte da Politica em minuscula, matrizes de `entra` e `selo` sobre 6.000 candidatos x 3 politicas).
  - Interpretacao (spec silenciosa, escolhi o lado fail-open): UF/regiao/esfera em texto vazio ou so espaco contam como desconhecidos (`uf=""` e `regiao=""` caem na regra 2, com selo). `modo` NAO e normalizado: "ATIVO" e "ativo " viram `filtro_desligado`, como o aceite exige para "ativo ".
  - `MOTIVOS` (frozenset) exportado pelo modulo para a fiacao; os testes nao o usam: o conjunto esperado esta transcrito a mao da spec.
  - Revisor: olhar a ordem das regras 5→6→7 (a 6 dispara com teto=None, de proposito, conforme as notas do arquiteto) e a comparacao estrita `teto < corte` e `cargos_total > limite`.
Pendências: nenhuma deste ticket. A fiacao no bot, o parse do teto e a classificacao da esfera ficam com os outros tickets.
