---
id: T-015
titulo: Estreitar as assercoes frouxas do loader, do bot e do resumo
tipo: codigo
nivel: M-
status: integrado
repo: principal
spec: [SPEC-001, R-14, R-20]
depende_de: []
toca: [src/core/bot.py, tests/test_config_loader.py, tests/test_concurso_bot.py]
recursos: []
afinidade:
retornos: 0
atualizado: 2026-11-25T01:07-03:00
branch: t/T-015-estreitar-as-assercoes-frouxas-do-loader
executor: script
executor_impl: agy-neon
corpo_lancado: ece32ea140d3
fora_do_toca: []
ponta: 82db274a2de6e93e55997a739d597cb4999a83d3
executor_rev: glm-go
executor_int: script
---
# T-015 · Estreitar as assercoes frouxas do loader, do bot e do resumo

## Contexto

Tres pareceres apontaram assercao que passa sem provar, em tres lugares diferentes. Nenhum e defeito de
producao; todos deixam mutacao viva.

1. **`config/loader.py`** (`kanban/relatorios/T-006-revisor-1.md`): quatro assercoes frouxas em
   `tests/test_config_loader.py`.
2. **`src/core/bot.py`, contadores e cegueira** (`kanban/relatorios/T-009-revisor-1.md`): dois testes
   contam cartoes enviados mas nao olham os acumuladores no resumo final, e um afirma a ausencia da fonte
   sem chamar `executar()`.
3. **A janela do resumo semanal** (`kanban/relatorios/T-010-revisor-1.md`): a mutacao que troca
   `timedelta(days=7)` por `days=1` **sobreviveu**, porque nenhum teste inspeciona o argumento `desde`
   que vai ao `listar_filtrados`.

Junto vai uma divida de vocabulario: o `GLOSSARIO.md` lista `varredura` como termo a evitar em favor de
`rodada`, e ele entrou em quatro trechos novos.

## Critério de aceite

### Loader (`tests/test_config_loader.py`)

- [ ] O teste de `ufs_sem_corte` usa uma lista **diferente** do padrao da spec. Hoje usa `"pr, sc,rs"`,
      cujo normalizado e identico ao padrao `["PR", "SC", "RS"]`, entao uma mutacao que ignore a chave e
      devolva o padrao sobrevive. Use algo como `"mg, ba"` e afirme o resultado exato.
- [ ] `esferas_sem_corte=[]` (lista vazia explicita) ganha teste dedicado, como `ufs_sem_corte=[]` ja tem.
      Lista vazia e diferente de chave ausente: a vazia manda, a ausente cai no padrao.
- [ ] `test_pci_mcp_cargos_aceita_csv_e_preserva_ordem` usa pelo menos um termo com maiuscula, para matar
      a mutacao de `.lower()`. Hoje todos os termos ja chegam minusculos.
- [ ] `test_pci_mcp_com_slugs_avisa_mas_nao_desliga` afirma `len(avisos) == 2`, nao `assert avisos`, e
      separa os dois casos (`COM_SLUGS` e `COM_NACIONAL`) em vez de agrupa-los.

### Contadores e cegueira (`tests/test_concurso_bot.py`)

- [ ] Existe teste que afirma o efeito de `validos`, `novos_cont` e `atualizados_cont` **no texto do
      resumo final**, nao so a contagem de chamadas ao notificador. Mata as sub-mutacoes M2d e M2e do
      parecer do T-009.
- [ ] `test_mcp_desligado_nao_instancia_scraper` passa a chamar `bot.executar()` antes de afirmar que
      `"pci_mcp"` nao esta nas fontes avaliadas. Afirmar ausencia sem rodar a costura nao prova nada.
- [ ] O selo `sem_evidencia` ganha caso na costura do bot. Hoje so o `nao_verificado` tem, e os dois
      compartilham a mesma linha que monta o card.

### Janela do resumo semanal (`tests/test_concurso_bot.py`)

- [ ] Existe teste que inspeciona o argumento `desde` passado ao `listar_filtrados`: formato
      `AAAA-MM-DD HH:MM:SS` e janela de **sete** dias. Trocar `days=7` por `days=1` tem de quebrar.

### Vocabulario

- [ ] `varredura` sai dos quatro trechos novos, em favor de `rodada`: `src/core/bot.py` nas duas
      ocorrencias novas e `tests/test_concurso_bot.py` nas duas. Confira com
      `grep -rn varredura src/core/bot.py tests/test_concurso_bot.py` e compare com o estado de antes:
      ocorrencia **legada**, que ja estava la antes desta fase, **fica como esta** (trocar tudo seria
      outro ticket, maior, e mexeria em texto que ninguem revisou).

- [ ] A suite inteira continua verde (539 em 24/11/2026) e **nenhum teste existente perde forca**: as
      assercoes trocadas tem de ficar mais estreitas, nunca mais largas.
- [ ] O relatorio traz a tabela das mutacoes, com o teste que mata cada uma.

## Plano de testes

Costura: duas. `config.loader` pela funcao que monta a config por area, e `ConcursoBot.executar()` com as
portas, o notificador e o banco dublados, as duas ja usadas pelos arquivos de teste citados. Pega: a
normalizacao das chaves, os acumuladores que aparecem no resumo final, o selo no card e o argumento que
vai ao banco. Nao pega: o transporte HTTP, a decisao de elegibilidade em si (modulo puro, coberto) e o
texto do resumo semanal (`tests/test_resumo_filtrados.py`).

Oráculo: a tabela de padroes da SPEC-001 secao 3.6 para o loader, lida a mao, e valores escritos a mao
nos testes do bot. O `desde` esperado se calcula a mao no teste, com o relogio dublado, nunca chamando a
mesma expressao que o codigo usa.

Testes que nascem vermelhos, um por item do aceite. Para o `desde`, dublar `src.core.bot.date` como
os testes de `TestResumoSemanal` ja fazem e afirmar a string exata.

Em `tests/test_config_loader.py`:

- `test_ufs_sem_corte_usa_a_lista_dada_e_nao_o_padrao`
- `test_esferas_sem_corte_vazia_manda_e_nao_cai_no_padrao`
- `test_pci_mcp_cargos_minusculiza_termo_com_maiuscula`
- `test_pci_mcp_com_slugs_e_com_nacional_avisam_dois_avisos` (separado em dois testes, um por caso)

Em `tests/test_concurso_bot.py`:

- `test_contadores_do_mcp_e_do_gran_aparecem_no_resumo_final`
- `test_mcp_desligado_nao_aparece_nas_fontes_depois_de_executar`
- `test_selo_sem_evidencia_aparece_no_card`
- `test_o_resumo_semanal_pede_sete_dias_ao_banco`

A troca de `varredura` por `rodada` nao tem teste proprio: e texto, e a conferencia e o `grep` do aceite.

## Fora do escopo

- Mudar comportamento de producao. A unica mudanca em `src/core/bot.py` autorizada aqui e **texto**: duas
  palavras de comentario ou log. Se alguma assercao nova ficar vermelha contra o codigo de hoje, pare e
  volte com `BLOQUEADO`: seria defeito, nao fraqueza de teste.
- Generalizar o `_alerta_uma_vez_por_dia` para aceitar periodo. A nota do arquiteto do T-010 pediu dois
  helpers separados de proposito.
- Trocar `varredura` por `rodada` no texto legado, fora dos quatro trechos novos.

## Notas do arquiteto

- **M− porque sao tres arquivos e nove itens**, e a parte dos contadores exige entender o que o resumo
  final imprime. Nenhum item e difícil sozinho; o volume e o custo.
- **Este ticket toca `src/core/bot.py` e `tests/test_concurso_bot.py`, e por isso o T-019 depende dele.**
  Os dois mexeriam no mesmo arquivo; rodar em paralelo daria conflito. Este vem primeiro porque e menor e
  nao depende de decisao de produto.
- **Todo teste deste ticket nasce VERDE, e isso e o desenho, nao desleixo.** O codigo de producao
  esta certo; o que falta e a trava que impede a regressao. Por isso o TDD aqui se inverte: a prova
  nao e um log vermelho, e a **tabela de mutacao**. Para cada teste novo, aplique a mutacao nomeada
  no aceite, rode so o teste novo e mostre que ele **falha**; depois desfaca a mutacao com
  `git checkout -- <arquivo>` e mostre que ele passa. Declare os testes como nascidos verdes no
  relatorio, com a mutacao de cada um ao lado. Revisor: confira a tabela, nao procure o vermelho.
- **Nao afrouxe nem apague teste que ja existe** para fazer o seu passar. Se um teste antigo conflitar
  com o aceite, pare e volte com `BLOQUEADO`.

## Histórico
- 2026-11-24 23:43 backlog → pronto · liberado: OK do Lucas no chat, 24/11/2026: libera a onda 0
- 2026-11-24 23:46 pronto → fazendo · implementador · agy-neon M- medium
- 2026-11-24 23:54 fazendo → entregue · implementador: ENTREGUE · relatório T-015-implementador-1.md · 9 min
- 2026-11-24 23:58 entregue → revisando · revisor · glm-go M+ high
- 2026-11-25 00:07 revisando → aprovado · revisor: APROVADO COM RESSALVAS · relatório T-015-revisor-1.md · 10 min
- 2026-11-25 01:06 aprovado → integrando · integrador · script
- 2026-11-25 01:07 integrando → integrado · integrador: INTEGRADO · relatório T-015-integrador-1.md · 1 min
