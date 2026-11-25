---
id: T-019
titulo: O concurso filtrado pelo MCP que o Gran acha depois
tipo: codigo
nivel: M-
status: backlog
repo: principal
spec: [SPEC-001, R-12, R-15]
depende_de: [T-015, T-024]
toca: [src/core/bot.py, tests/test_concurso_bot.py]
recursos: []
afinidade:
retornos: 0
---
# T-019 · O concurso filtrado pelo MCP que o Gran acha depois

## Contexto

**Este ticket espera uma decisao de produto do Lucas. Nao libere antes dela** (ver as Notas do arquiteto).

A regra R-12 da SPEC-001 diz que linha gravada como `filtrado`, quando volta a entrar, sai como **NOVO**,
porque o Lucas nunca viu aquele concurso. O implementador do T-010 restringiu a regra a item **avaliado**,
e o revisor confirmou a escolha como defensiva e correta no escopo: item nao avaliado (o do Gran, que nao
traz `regiao`) grava `elegibilidade=None`, e isso **preserva** o `filtrado` que ja estava la. Se R-12
valesse para ele, a mesma linha sairia como NOVO a cada rodada, para sempre.

O preco e um buraco estreito, descrito nos dois relatorios: um concurso filtrado pela porta do MCP, que o
Gran ache **depois** com uma transicao de fase real, sai como **ATUALIZACAO** de algo que o Lucas nunca
viu. Ele recebe «mudou» sobre um concurso que nunca lhe foi apresentado.

Hoje e raro, porque o Gran de TI esta congelado. Raro nao e nunca, e a falha e silenciosa.

## Critério de aceite

O aceite depende da decisao registrada nas Notas do arquiteto. **Nao implemente nada antes de ela estar
escrita aqui**; se nao estiver, volte com `BLOQUEADO`.

Qualquer que seja o caminho escolhido:

- [ ] Existe teste na costura do bot que reproduz o caso exato: linha gravada com
      `elegibilidade='filtrado'` pela porta do MCP, e depois um item do **Gran** (sem `regiao`) para o
      mesmo concurso, com transicao de fase real. O teste nasce **vermelho** contra o codigo de hoje e
      descreve, no nome, o comportamento escolhido.
- [ ] O comportamento de hoje para todos os outros casos **nao muda**. Em particular: item do Gran para
      linha nunca filtrada continua como esta, e a regra R-15 (so porta com `regiao` e avaliada) continua
      valendo, porque e deliberada.
- [ ] Item nao avaliado continua **nao** renotificando em laco. Esse era o motivo da restricao original, e
      qualquer solucao que o reintroduza esta errada.
- [ ] A suite inteira continua verde (539 em 24/11/2026) e os testes do T-010 que travam R-12 e R-15
      continuam passando sem afrouxamento.
- [ ] A decisao escolhida fica registrada no repo, no lugar certo: regra nova na SPEC-001 secao 4.3 se for
      regra, ou ADR se for escolha estrutural. O ticket nao e o lugar de guardar decisao de produto.

## Plano de testes

Costura: `ConcursoBot.executar()` com as portas, o notificador e o banco dublados, a mesma de
`tests/test_concurso_bot.py`. E a unica que alcanca o caso, porque ele depende da ordem das portas dentro
da rodada e do que ja esta gravado no banco. Pega: a matriz de decisao e a mensagem enviada. Nao pega: a
decisao de elegibilidade em si (modulo puro) nem o transporte.

Oráculo: o caso escrito a mao, com o veredito decidido pela regra que o Lucas escolher, literal no teste.

Testes que nascem vermelhos, depois da decisao estar escrita nas Notas do arquiteto. Os nomes abaixo
assumem o caminho escolhido; ajuste o nome ao comportamento decidido, nunca o contrario:

- `test_filtrado_pelo_mcp_que_o_gran_acha_depois_<comportamento_escolhido>` — o caso nominal do
  contexto: linha `filtrado` gravada pela porta do MCP, depois item do Gran sem `regiao` para o mesmo
  concurso, com transicao de fase real.
- `test_item_do_gran_para_linha_filtrada_nao_renotifica_em_laco` — duas rodadas seguidas com o mesmo item
  do Gran, e a segunda nao manda nada. Este e o teste que protege o motivo da restricao original.
- `test_item_do_gran_para_linha_nunca_filtrada_segue_como_hoje` — a guarda de que o resto nao mudou.
  Nasce verde, e declarado como tal.

## Fora do escopo

- Avaliar item do Gran. A R-15 e deliberada e a porta do Gran nao traz `regiao`, `cargos_total` nem teto:
  marcar com selo tudo que vem dela poria aviso em todo card por falta de dado que aquela porta nunca teve.
- Mexer no modulo de elegibilidade. O caso e de **matriz**, nao de decisao.
- Backfill das 1700 linhas que ja estao no banco, ou reavaliar o que ja foi notificado.

## Notas do arquiteto

- **A decisao do Lucas vem primeiro, e sao tres caminhos.** Nenhum e obviamente melhor; o custo e o ruido
  sao diferentes:
  1. **Deixar como esta** e aceitar o buraco, registrando a escolha na SPEC-001. Custo zero, risco
     silencioso que continua. Defensavel enquanto o Gran de TI estiver congelado.
  2. **Mandar como NOVO** quando a linha estava `filtrado`, mesmo para item nao avaliado, **uma vez**, com
     um marcador na linha para nao repetir. Fecha o buraco, custa uma coluna ou um campo de controle, e o
     risco e errar o marcador e cair no laco de renotificacao.
  3. **Mandar com selo** dizendo que o concurso estava filtrado e voltou por outra porta. Nao perde o
     concurso e nao finge que e novo, mas acrescenta uma forma de card.
- **Recomendacao:** o caminho 1 por agora, com uma linha na SPEC-001, e reabrir quando o resumo semanal
  mostrar que o Gran de TI voltou a se mover. Motivo: o Lucas esta em janela de manutencao, o caminho 2
  mexe em estado gravado (que e o tipo de mudanca que da trabalho de verdade) e o sintoma nunca foi
  observado. Mas quem decide e ele, porque o que esta em jogo e o que ele recebe.
- **Depende do T-015** porque os dois tocam `src/core/bot.py` e `tests/test_concurso_bot.py`. Sem a
  dependencia, o mapa acusaria conflito de arquivo.
- **M− porque a regra e conhecida depois da decisao** e o caso cabe num modulo. Se o caminho escolhido for
  o 2, reclassifique para M+: mexer em estado gravado tem mais borda do que parece.
