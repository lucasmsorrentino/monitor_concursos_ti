ENTREGUE
Esteira: implementador · opus (claude-opus-5-5) · nível G- · esforço high · 2026-11-23 20:01 → 2026-11-23 20:18 (18 min)
Resumo: o filtro salarial foi ligado na matriz de decisao do `ConcursoBot`. A `Politica` e montada uma vez no `__init__`. So o item que carrega `regiao` (a porta do MCP) e avaliado, e isso acontece depois do `ignorado` e antes de novo/inativo/transicao. O item filtrado e salvo em silencio com as sete colunas do v6 e devolve `skip`. A linha que estava `filtrado` e agora entra sai como NOVO (R-12). O selo vai no card de novo concurso. O resumo semanal sai no fim de `executar()`, com marcador da semana ISO em `LOG_DIR`. A ressalva do arquiteto tambem foi corrigida: a porta do MCP passa a contar como materia-prima na checagem de cegueira.
Arquivos: src/core/bot.py, tests/test_concurso_bot.py (os dois dentro do «toca»)
Commits:
  bda1c63 test: Gran vazio com a porta do MCP trazendo item nao e varredura cega
  2a09bd2 fix: porta do MCP conta como materia-prima na checagem de cegueira
  1760527 test: filtro salarial decide na matriz, grava a elegibilidade e poe o selo no card
  5ff9189 test: contador de novos em zero lido pelo heartbeat, sem contar o aviso de fonte
  17cf3b3 feat: filtro salarial na matriz de decisao, com selo no card e filtrado que volta como novo
  825943a test: resumo semanal dos filtrados sai uma vez por semana por area
  d88e92b feat: resumo semanal dos filtrados no fim da rodada, com marcador da semana ISO
  e59387e docs: matriz de decisao e fluxo da rodada citam o filtro salarial e o resumo semanal
Testes: "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q → base 517 passed / 0 failed (medida pelo integrar em 9c12e9e, que e a minha base; nao medi de novo) · ponta 539 passed / 0 failed / 0 skipped (`-rs` sem pulados; `--collect-only -q` → "539 tests collected"). Sem variavel de ambiente nem marcador. Sao 22 testes novos: 1 de cegueira, 14 de filtro e 7 de resumo. O aceite cita «296 testes»; e numero antigo, a base real e 517.
  Vermelhos vistos antes do verde:
  - cegueira: `assert bot.falhou is False` falhou com True.
  - filtro: 11 de 14 vermelhos por asserção (notificar_concurso chamado, KeyError em `elegibilidade`/`motivo_filtro` nos kwargs da gravacao porque a coluna nao era passada, selo ausente).
  - resumo: 6 de 7 vermelhos por asserção (nenhum resumo enviado, nenhum erro logado).
  Nenhum vermelho veio de coleta ou importacao.
  Mutacao manual depois do verde (sed e depois `git checkout`): desligar R-12 → 1 falha; avaliar todas as portas (sem R-15) → 2; tirar o selo → 1; ignorar a estrela → 1; voltar a cegueira antiga → falha. Todos os mutantes morreram.
Testes que nascem verdes (guardas, declaradas):
  - test_ignorado_continua_saindo_antes_do_filtro, test_item_do_gran_nao_e_avaliado, test_item_da_pagina_de_cargo_nao_e_avaliado: travam o comportamento de hoje, que o feat nao podia mudar. A ordem `ignorado` → filtro fica coberta porque o item e filtravel: com a ordem trocada, o banco seria tocado. A mutacao de R-15 derrubou os testes do Gran e da pagina de cargo.
  - test_resumo_desligado_nao_consulta_o_banco: antes do feat nada consultava o banco.
Desvios e riscos:
  - O commit 5ff9189 ajusta um teste meu antes do feat. `test_filtrado_nao_notifica...` exigia exatamente 1 mensagem em `notificar`, mas a rodada com o Gran vazio tambem manda o aviso de fonte sem retorno. Agora a prova de «novos = 0» e a presenca do heartbeat «nao encontrei nenhuma alteracao», que so sai com novos e atualizados em 0. A asserção ficou tao forte quanto antes para o que o aceite pede; o revisor deve conferir.
  - Duas mudancas do plano de testes, para nao acoplar o teste a implementacao:
    - test_ignorado: o plano pedia conferir que «`decidir` nao e chamado», o que e conferencia de chamada de codigo do projeto. Em vez disso, o teste observa que o banco nao e tocado com um item filtravel, e pega a mesma troca de ordem.
    - test_falha_no_resumo: o plano pedia dublar o `montar` para levantar. Em vez disso, uma linha do banco com `salario_teto` ilegivel ("8.628,87" em texto) faz o `montar` real levantar.
  - Os testes de resumo dublam o relogio (`src.core.bot.date`) em vez de escrever o arquivo do marcador. «Uma vez na semana» roda segunda, segunda e sexta da mesma semana ISO: um marcador diario reprovaria esse teste.
  - Decisao minha que o ticket nao fechava: R-12 (filtrado que volta sai como NOVO) so vale para item AVALIADO. Item nao avaliado (Gran) passa `elegibilidade=None`, que preserva o 'filtrado' gravado. Se R-12 valesse para ele, a mesma linha sairia como NOVO a cada rodada. Fica um risco residual: um concurso filtrado pelo MCP e achado pelo Gran com transicao real sai como ATUALIZACAO de algo que o Lucas nunca viu. E raro: o Gran de TI esta congelado.
  - «Porta que carrega `regiao`» foi implementado como `"regiao" in dados` (a chave presente, mesmo com valor None). E o que permite o selo `nao_verificado` para item do MCP com uf e regiao nulas. Hoje so o `PciMcpScraper` poe essa chave (`grep regiao src/scrapers src/intelligence`).
  - Item filtrado grava `fase_mais_avancada(fase do registro, fase nova)`, para a fase vista nao regredir em linha que passa a filtrada.
  - O resumo manda pelo `notifier.notificar` direto, nao pelo `_notificar`, porque aquele marca `falhou` quando o envio falha. Envio recusado e logado em warning, nao grava o marcador e a proxima rodada tenta de novo (teste test_envio_do_resumo_que_falha_nao_marca_a_rodada_e_tenta_de_novo, acrescentado ao plano).
  - O corte de `listar_filtrados` usa `datetime.now(timezone.utc) - 7 dias`, porque `CURRENT_TIMESTAMP` do SQLite e UTC. O dia da semana do marcador usa `date.today()` local, como os marcadores diarios.
  - Marcador: `LOG_DIR/.resumo_<area>_filtrados`, contendo a chave da semana ISO (ex.: "2026-S48"). O `_alerta_uma_vez_por_dia` ficou intocado.
  - `_politica_de` respeita lista vazia explicita em `ufs_sem_corte`/`esferas_sem_corte`, como o loader. Chave ausente cai no padrao da `Politica`.
  - Sem push, conforme as regras do projeto.
Pendencias:
  - O CLAUDE.md (tabela da matriz de decisao, secao "Decision matrix", e o fluxo de fim de ciclo) nao cita o filtro salarial nem o resumo semanal. Esta fora do «toca»; fica para o ticket de docs/deploy.
  - Nenhum teste cobre o risco residual de cruzamento de fontes descrito acima (linha filtrada pelo MCP que o Gran ve com transicao). Se o arquiteto quiser fechar o caso, precisa de regra de produto.
