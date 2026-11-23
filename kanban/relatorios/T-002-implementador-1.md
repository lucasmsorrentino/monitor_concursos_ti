ENTREGUE
Esteira: implementador · glm (zai-coding-plan/glm-5.3) · nível M+ · esforço high · 2026-11-23 11:16 → 2026-11-23 11:26 (11 min)
Resumo: `esfera_de(nome)` em `src/utils/esfera.py`, funcao pura sem dependencia externa, classifica a esfera do orgao pelo nome com os padroes do aceite e a precedencia declarada (conselho_profissional > municipal > federal > distrital > estadual), comparando insensivel a acento/caixa via `normalizar_nome` de `src/utils/text.py`. Tabela do oraculo em `tests/test_esfera.py` (24 casos), vermelha por `NotImplementedError` do esqueleto antes do verde. Fumaça extra, fora da suíte, rodou os 39 orgaos das fixtures do PCI.
Arquivos: `src/utils/esfera.py`, `tests/test_esfera.py` (todos dentro do `toca`).
Commits:
- 31d56f2 chore: esqueleto de src/utils/esfera.py com a assinatura de esfera_de
- 717fc50 test: esfera_de classifica a esfera do orgao pelo nome (tabela do oraculo)
- 826537d feat: esfera_de com padroes declarados e precedencia entre esferas
- 420f316 docs: contrato do modulo de esfera, precedencia e excecoes declaradas
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q` → base 296 passed / 0 failed · ponta 320 passed / 0 failed (0 pulados; unica diferenca sao os 24 testes novos). Lint: nao configurado no repo, nao rodou. Condicao de medicao: worktree do ticket, venv do repo principal, sem variavel de ambiente especial.
Testes que nascem verdes: nenhum. Os 24 casos nasceram vermelhos pelo motivo certo (`NotImplementedError` do corpo do esqueleto), sem erro de coleta ou importacao.
Desvios e riscos:
- **Duas excecoes ao pe da letra dos padroes, documentadas na docstring** (o revisor deve validar a leitura): (1) "Ministerio" casa federal, mas "Ministerio Publico" nao e ministerio — sem isso o padrao estadual listado "Ministerio Publico do Estado" ficaria inalcançavel (o "ministerio" federal, de precedencia maior, engoliria todos os MP estaduais); efeito colateral: MP da Uniao e MP do Trabalho devolvem None (fail-open, a elegibilidade decide pelo teto). (2) "Camara" casa municipal, menos "Camara Legislativa", que e do DF e cai no padrao distrital.
- **CETESB devolve None**: a fixture real "Companhia Ambiental do Estado de Sao Paulo" nao contem a frase contigua "companhia do estado" (o lista-item "Companhia/Banco do Estado" foi implementado como frase, no mesmo molde de "Instituto do Meio Ambiente do Estado"). Opcoes: manter frase contigua (status quo, mais conservador) ou casar "companhia"+"do estado" a distancia (pega CETESB; risco menor de falso estadual). Recomendo manter e, se o Lucas quiser CETESB, um ticket P de acrescimo de padrao.
- Orgao do DF que traga "Secretaria de Estado" sem "do Distrito Federal" no nome le estadual: o sufixo DF so decide quando nada mais casa, como o ticket declara.
- O vermelho pegou um bug real antes do verde: a sigla "cro" casava dentro de "Microrregiao"; corrigido casando palavra/expressao inteira (espaco nas duas pontas do padrao).
- Fumaça nas fixtures (39 orgaos): 27 municipal, 4 federal, 4 estadual, 1 distrital, 3 None (CETESB acima, CIS e SETEC, entidades privadas — None de proposito).
Pendencias: o que a esfera libera na elegibilidade (outro ticket); padroes fora da lista do aceite (STJ, TSE, DETRAN etc.) ficam None por fechamento de lista — decisao de ampliaçao e do arquiteto.
