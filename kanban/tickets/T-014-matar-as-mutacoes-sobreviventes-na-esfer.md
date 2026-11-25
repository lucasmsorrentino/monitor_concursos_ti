---
id: T-014
titulo: Matar as mutacoes sobreviventes na esfera e na porta do MCP
tipo: codigo
nivel: M-
status: integrado
repo: principal
spec: [SPEC-001, R-04]
depende_de: []
toca: [tests/test_esfera.py, tests/test_pci_mcp_scraper.py]
recursos: []
afinidade:
retornos: 0
atualizado: 2026-11-25T01:08-03:00
branch: t/T-014-matar-as-mutacoes-sobreviventes-na-esfer
executor: script
executor_impl: glm-go
corpo_lancado: 5d6b19c8a24f
fora_do_toca: []
ponta: 105c19efc50a5f2e260e644c6651c71993c769ed
executor_rev: agy-neon
executor_int: script
---
# T-014 · Matar as mutacoes sobreviventes na esfera e na porta do MCP

## Contexto

Dois modulos da fase passada ficaram com mutacao viva, e os dois alimentam a decisao de elegibilidade:

1. **`src/utils/esfera.py`** (parecer em `kanban/relatorios/T-002-revisor-2.md`): a inversao isolada de
   `_e_federal` com `_e_distrital`, a remocao do termo `"transpetro"` e a remocao de
   `"universidade federal"` sobrevivem a suite. A esfera decide a isencao federal, que e o que mantem
   UFMS, IFSP e IFG chegando: errar a esfera e cortar concurso federal em silencio.
2. **`src/scrapers/pci_mcp_scraper.py`** (parecer em `kanban/relatorios/T-004-revisor-1.md`): tres
   sub-ramos ja implementados sobrevivem a mutacao de remocao, porque o plano de testes do T-004 nao
   pediu caso isolado para eles.

Nenhum dos dois e defeito: o codigo esta certo e rodando em producao desde 24/11/2026. Falta a trava.

## Critério de aceite

### Esfera (`tests/test_esfera.py`)

- [ ] Inverter `_e_federal` com `_e_distrital` quebra pelo menos um teste. Hoje nao quebra: falta um caso
      cuja resposta **so** sai certa com a ordem correta das duas checagens.
- [ ] Remover o termo `"transpetro"` da lista fechada quebra um teste. Precisa de um caso nominal com o
      nome real do orgao.
- [ ] Remover `"universidade federal"` da lista quebra um teste. Hoje nao quebra porque
      `"fundacao universidade federal"` cobre o caso que esta testado: use um nome que tenha
      `universidade federal` **sem** `fundacao`, como aparece no PCI.
- [ ] O caso de fail-open continua travado: nome que a lista fechada nao reconhece devolve `None`, e
      `None` nao filtra nada. O `CETESB - Companhia Ambiental do Estado de Sao Paulo - SP` e o exemplo do
      parecer e serve de caso nominal.

### Porta do MCP (`tests/test_pci_mcp_scraper.py`)

- [ ] `datas.em_breve` quando o titulo nao infere `"edital_publicado"`: caso isolado, e remover o sub-ramo
      quebra o teste.
- [ ] `datas.fim` vazio ou ausente virando `None`: caso isolado para cada um dos dois (vazio e ausente).
- [ ] `resposta.status_code != 200`: caso isolado, com a saida que o scraper devolve nesse caminho.
- [ ] A suite inteira continua verde (539 em 24/11/2026) e nenhum teste existente foi afrouxado.
- [ ] O relatorio traz a tabela das sete mutacoes, cada uma com o teste que a mata.

## Plano de testes

Costura: duas, uma por modulo. `esfera.esfera_de(nome)` e `PciMcpScraper._mapear` / `.buscar()`, as
mesmas que `tests/test_esfera.py` e `tests/test_pci_mcp_scraper.py` ja usam. Pega: a classificacao pelo
nome e o mapeamento do item do MCP. Nao pega: o transporte HTTP de verdade (os testes dublam a resposta,
como ja fazem) nem a decisao de elegibilidade.

Oráculo: para a esfera, a lista fechada da SPEC-001 secao 3.3, lida a mao, e nomes de orgao reais, de
`tests/fixtures/pci_mcp/`. Para a porta, as fixtures de resposta que ja estao no repo. Nenhum esperado
sai de chamar a funcao sob teste.

Testes que nascem verdes (ver a nota do arquiteto), um por mutacao:

- `test_federal_e_distrital_nao_se_confundem` (inversao `_e_federal` / `_e_distrital`)
- `test_transpetro_e_federal` (remocao de `"transpetro"`)
- `test_universidade_federal_sem_fundacao_e_federal` (remocao de `"universidade federal"`)
- `test_orgao_fora_da_lista_fechada_devolve_none` (fail-open)
- `test_titulo_que_nao_infere_edital_publicado_usa_em_breve`
- `test_data_fim_vazia_e_ausente_viram_none` (parametrizado)
- `test_resposta_fora_do_200`

## Fora do escopo

- **Ampliar a lista fechada da esfera.** STJ, TSE, MPU e DETRAN estao em aberto desde o T-002 e sao
  decisao de produto do Lucas, com dado do resumo semanal. Nao acrescente termo nenhum.
- O casamento nao contiguo de `"Companhia ... do Estado"`, tambem decisao de produto em aberto.
- Mudar o comportamento de qualquer um dos dois modulos. So trava de teste.

## Notas do arquiteto

- **M− porque sao sete casos em dois modulos**, e tres deles (os da esfera) exigem escolher um nome de
  orgao que isole a regra. Escolher o nome e o trabalho; escrever o teste e mecanico.
- Nao tem conflito de arquivo com nenhum outro ticket desta fase: so toca os dois arquivos de teste.
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
- 2026-11-24 23:46 pronto → fazendo · implementador · glm-go M-
- 2026-11-24 23:58 fazendo → entregue · implementador: ENTREGUE · relatório T-014-implementador-1.md · 13 min
- 2026-11-25 00:01 entregue → revisando · revisor · agy-neon M+ high
- 2026-11-25 00:06 revisando → aprovado · revisor: APROVADO · relatório T-014-revisor-1.md · 6 min
- 2026-11-25 01:08 aprovado → integrando · integrador · script
- 2026-11-25 01:08 integrando → integrado · integrador: INTEGRADO · relatório T-014-integrador-1.md · 1 min
