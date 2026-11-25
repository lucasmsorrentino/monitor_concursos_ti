---
id: T-013
titulo: Matar as nove mutacoes que sobreviveram na decisao de elegibilidade
tipo: codigo
nivel: M-
status: integrado
repo: principal
spec: [SPEC-001]
depende_de: []
toca: [src/core/elegibilidade.py, tests/test_elegibilidade.py]
recursos: []
afinidade:
retornos: 0
atualizado: 2026-11-25T01:08-03:00
branch: t/T-013-matar-as-nove-mutacoes-que-sobreviveram
executor: script
executor_impl: agy-neon
corpo_lancado: 73cd1be8ba73
fora_do_toca: []
ponta: aa3f48ec9e03474939f28f8815991f36a910c654
executor_rev: glm-go
executor_int: script
---
# T-013 · Matar as nove mutacoes que sobreviveram na decisao de elegibilidade

## Contexto

O `src/core/elegibilidade.py` e o modulo que decide silencio: ele diz quais concursos o Lucas **nao**
vai receber. O revisor do T-003 aplicou 20 mutacoes nele e **nove sobreviveram** aos 51 testes. Entre
elas estao tres trocas de ordem entre as regras 0, 1 e 2 e uma entre 3 e 4, ou seja: a precedencia que
protege a estrela do usuario, o modo desligado e o concurso do Sul **nao esta travada por teste**.

Isso importa mais do que parece. A SPEC-001 secao 4.2 define nove regras numa lista em que **a primeira
que casa vence**, e a ordem e a regra. Um refator que reordene a lista passa verde hoje. O sintoma seria
silencio: um concurso que devia chegar e nao chega, e ninguem fica sabendo por semanas. E exatamente o
padrao que a SPEC-002 secao 1 descreve.

O parecer esta em `kanban/relatorios/T-003-revisor-1.md`, secao «Prova», com a tabela das 20 mutacoes.

## Critério de aceite

Cada item abaixo e uma mutacao que hoje sobrevive. O aceite e: existe teste em
`tests/test_elegibilidade.py` que **falha** com a mutacao aplicada e passa sem ela.

- [ ] `M1_swap_0_1` (trocar as regras 0 e 1): candidato com `seguindo=True` e politica com
      `modo="desligado"` tem de sair pela regra 0, com motivo `seguindo`, nao por `filtro_desligado`.
- [ ] `M2_swap_0_2` (trocar as regras 0 e 2): candidato com `seguindo=True` e `uf=None` e `regiao=None`
      sai por `seguindo`, **sem selo**. Com a troca, receberia selo de nao verificado.
- [ ] `M3_swap_1_2` (trocar as regras 1 e 2): politica com `modo="desligado"` e candidato com `uf=None`
      e `regiao=None` sai por `filtro_desligado`, **sem selo**.
- [ ] `M4_swap_3_4` (trocar as regras 3 e 4): concurso federal **que tambem e do Sul** sai com motivo
      `sul`, nao `federal`. Precisa de um caso com `uf` em PR, SC ou RS **e** esfera federal.
- [ ] `M10_hardcode_corte`: o corte vem de `politica.corte_fora_sul`, nao de um literal. Prove com
      politica de corte diferente de 10000 (ex.: 3000) e um teto entre os dois valores.
- [ ] `M11_hardcode_cargos`: o limite de cargos vem de `politica.cargos_total_inflado`, nao de um
      literal. Prove com limite diferente de 10 (ex.: 3).
- [ ] `M12_hardcode_esfera`: a isencao de esfera vem de `politica.esferas_sem_corte`, nao do literal
      `"federal"`. Prove com uma politica que isente `"estadual"` em vez de `"federal"`.
- [ ] `M13_teto_truthy`: a regra distingue teto **ausente** (`None`) de teto **zero** (`0.0`). Prove com
      `teto=0.0`, que hoje passaria pelo mesmo caminho de `None`.
- [ ] `M20_empty_str_not_none`: `uf=""`, `regiao=""` e valor so com espacos contam como ausentes, caindo
      na regra 2 com selo. O implementador do T-003 declarou esse comportamento e nenhum teste o cobre.
- [ ] A constante publica `MOTIVOS` (`src/core/elegibilidade.py`) sai, ou ganha consumidor. Hoje nao e
      usada em lugar nenhum: o `tests/test_elegibilidade.py` tem o seu proprio `MOTIVOS_DA_SPEC`, escrito
      a mao da spec, que e o oraculo correto. Confira com `grep -rn MOTIVOS src/ tests/` antes e depois.
- [ ] A suite inteira continua verde (539 testes em 24/11/2026) e **nenhum teste existente foi afrouxado,
      renomeado ou apagado**.
- [ ] O relatorio traz a tabela das dez mutacoes acima, cada uma com o teste que a mata e o numero de
      falhas que ela produz.

## Plano de testes

Costura: `elegibilidade.decidir(candidato, politica)`, a mesma de `tests/test_elegibilidade.py`. E um
modulo puro, sem banco, rede nem relogio: a funcao e a interface publica e nao ha nada mais alto que
alcance a precedencia das regras. Pega: a decisao, o motivo e o selo. Nao pega: a fiacao no bot (coberta
em `tests/test_concurso_bot.py`), o parse do teto (`tests/test_salario.py`) e a classificacao da esfera
(`tests/test_esfera.py`).

Oráculo: a tabela da SPEC-001 secao 4.2, lida a mao. O motivo esperado de cada caso vai **escrito no
teste** como literal. Nenhum esperado sai de chamar `decidir`, nem de reimplementar a precedencia no
teste.

Testes, um por mutacao do aceite (nomes sugeridos, o implementador pode melhorar):

- `test_estrela_vence_o_filtro_desligado` (M1)
- `test_estrela_sem_uf_e_sem_regiao_nao_leva_selo` (M2)
- `test_filtro_desligado_sem_uf_e_sem_regiao_nao_leva_selo` (M3)
- `test_federal_do_sul_sai_como_sul` (M4)
- `test_o_corte_vem_da_politica_nao_de_um_literal` (M10)
- `test_o_limite_de_cargos_vem_da_politica` (M11)
- `test_a_isencao_de_esfera_vem_da_politica` (M12)
- `test_teto_zero_nao_e_teto_ausente` (M13)
- `test_uf_e_regiao_em_branco_contam_como_ausentes` (M20), parametrizado com `""`, `" "` e `"\t"`

## Fora do escopo

- **Mudar a decisao.** As nove regras estao fechadas na SPEC-001 secao 4.2 e ja estao em producao desde
  24/11/2026. Este ticket **so** acrescenta trava de teste e tira uma constante morta. Se um teste novo
  revelar que o codigo esta errado, pare e volte com `BLOQUEADO` com o caso concreto: isso seria defeito
  em producao, nao fraqueza de teste, e muda o ticket.
- Mexer em `src/core/bot.py`, `src/utils/salario.py`, `src/utils/esfera.py` ou na config.
- Reescrever os 51 testes que ja existem, ou trocar o estilo deles.

## Notas do arquiteto

- **M− e nao P+ porque sao nove casos de borda numa lista de precedencia**, e tres deles pedem que o
  autor entenda por que a ordem importa antes de escrever o caso. Nao e mecanico.
- **Este e o ticket mais importante da fase.** Se o Lucas quiser cortar a fase ao minimo, corte tudo
  menos este. O risco que ele fecha e silencio no modulo que decide silencio.
- A `Politica` e imutavel e os defaults dela sao os da spec. Para os casos M10, M11 e M12, construa uma
  `Politica` com valor **diferente** do padrao: um teste que usa o padrao nao distingue «veio da politica»
  de «esta escrito no codigo». Foi essa a causa das tres mutacoes sobreviverem.
- **Todo teste deste ticket nasce VERDE, e isso e o desenho, nao desleixo.** O codigo de producao
  esta certo; o que falta e a trava que impede a regressao. Por isso o TDD aqui se inverte: a prova
  nao e um log vermelho, e a **tabela de mutacao**. Para cada teste novo, aplique a mutacao nomeada
  no aceite, rode so o teste novo e mostre que ele **falha**; depois desfaca a mutacao com
  `git checkout -- <arquivo>` e mostre que ele passa. Declare os testes como nascidos verdes no
  relatorio, com a mutacao de cada um ao lado. Revisor: confira a tabela, nao procure o vermelho.
- **Nao afrouxe nem apague teste que ja existe** para fazer o seu passar. Se um teste antigo conflitar
  com o aceite, pare e volte com `BLOQUEADO`.
- O caso M4 (federal do Sul) merece atencao: nao e borda inventada. UFPR, UFSC, IFPR, IFSC e UTFPR sao
  federais **e** do Sul, e aparecem no PCI toda semana. O motivo gravado muda o que o resumo semanal diz.

## Histórico
- 2026-11-24 23:43 backlog → pronto · liberado: OK do Lucas no chat, 24/11/2026: libera a onda 0
- 2026-11-24 23:46 pronto → fazendo · implementador · agy-neon M- medium
- 2026-11-24 23:53 fazendo → entregue · implementador: ENTREGUE · relatório T-013-implementador-1.md · 7 min
- 2026-11-25 00:07 entregue → revisando · revisor · glm-go M+ high
- 2026-11-25 00:13 revisando → aprovado · revisor: APROVADO COM RESSALVAS · relatório T-013-revisor-1.md · 7 min
- 2026-11-25 01:07 aprovado → integrando · integrador · script
- 2026-11-25 01:08 integrando → integrado · integrador: INTEGRADO · relatório T-013-integrador-1.md · 1 min
