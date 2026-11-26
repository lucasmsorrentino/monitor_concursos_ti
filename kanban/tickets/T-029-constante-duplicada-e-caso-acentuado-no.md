---
id: T-029
titulo: Constante duplicada e caso acentuado no teste da ordem sem pci_id
tipo: codigo
nivel: P+
status: backlog
repo: principal
spec: [SPEC-003, R-82]
depende_de: [T-020, T-026, T-028, T-027]
toca: [tests/test_database_manager.py]
recursos: []
afinidade:
retornos: 0
---
# T-029 · Constante duplicada e caso acentuado no teste da ordem sem pci_id

## Contexto

Duas ressalvas do revisor na ultima revisao do ticket da identidade (`kanban/RESSALVAS.md`), as duas no
`tests/test_database_manager.py` e nenhuma de comportamento:

1. A constante `URL_INDICE_GRAN` esta definida **duas vezes** no nivel de modulo, com o mesmo valor.
2. Em `test_item_sem_pci_id_mantem_a_ordem_de_hoje`, o passo `db.buscar_registro(IFSP_NOME.upper())` passa
   texto **acentuado** (`Educacao`, `Ciencia`, `Sao`, no original com acento). O `COLLATE NOCASE` do SQLite
   so dobra ASCII, entao `.upper()` muda a letra acentuada e a busca **nao** casa pelo nome: ela escorrega
   para o fallback de entidade. O teste passa, mas nao prova o que o nome dele diz.

O item 2 e **o mesmo defeito, em outro lugar**. O revisor anterior apontou exatamente isso no caso `[nome]`
de outro teste, aquele foi corrigido, e este ficou. E a razao pela qual ele importa: teste que afirma exercer
um caminho e exerce outro foi o que deixou duas mutacoes passarem pela suite inteira.

O R-82 continua provado sem este conserto, porque a busca por nome `COLLATE NOCASE` sem chave esta coberta em
ASCII por `test_busca_por_nome_ignora_capitalizacao` e pela classe de desempate. Por isso isto e P+, e nao
bloqueou a aprovacao.

## Critério de aceite
- [ ] `URL_INDICE_GRAN` tem **uma** definicao no arquivo, e os dois usos apontam para ela
- [ ] O passo por nome de `test_item_sem_pci_id_mantem_a_ordem_de_hoje` usa um nome **ASCII**, de modo que o
      `COLLATE NOCASE` alcance a variacao de caixa de verdade e a busca case **pelo nome**, nao pela entidade
- [ ] O teste continua afirmando o que o nome dele promete: item **sem** `pci_id` mantem a ordem de
      identidade de hoje (R-82), pelos tres caminhos que ele ja cobria
- [ ] **Nenhuma assercao e removida nem afrouxada.** Se um caminho deixar de ser alcancavel com nome ASCII,
      acrescente o caso, nao apague o antigo
- [ ] A prova de que o passo por nome agora exerce o nome: com a mutacao `NULLIF(TRIM(pci_id), '')` aplicada
      **so** no fallback de nome da busca, este teste tem de **falhar**. O relatorio traz a saida vermelha
      com a mutacao e a verde sem ela
- [ ] Suite inteira verde, com a contagem antes e depois

## Plano de testes
Costura: a mesma de hoje, `DatabaseManager.buscar_registro` e `DatabaseManager.atualizar_concurso`, sobre
banco temporario em arquivo. Pega: a ordem de identidade do item sem chave. Nao pega: nada novo, porque este
ticket nao acrescenta comportamento.
Oráculo: o proprio R-82 e o comportamento ja aprovado na branch da identidade. **Nao releia o esperado do
codigo:** o valor esperado de cada passo e o que o R-82 manda.

Nao ha teste novo que nasca vermelho, porque nao ha comportamento novo. A prova deste ticket e a **mutacao**
descrita no aceite: o teste consertado falha sob ela, e o teste de hoje nao falha. Mostre as duas saidas, e a
do teste de hoje sob a mesma mutacao, como contraprova.

## Fora do escopo
- Qualquer linha de `src/`. Este ticket nao toca codigo de producao.
- Reescrever outros testes do arquivo, mesmo que pareçam ter o mesmo problema. Se achar mais casos, liste-os
  no relatorio e **nao** conserte: o arquiteto decide se viram ticket.
- Renomear, mover ou apagar teste existente.

## Notas do arquiteto

**Por que P+ e nao P−:** a edicao e mecanica, mas escolher o nome ASCII certo pede entender por que o
`COLLATE NOCASE` do SQLite nao dobra acento, e pede conferir que os tres passos do teste continuam alcancando
os caminhos que eles afirmam. Nao e copiar um padrao.

**Por que depende de tanta coisa:** so para nao disputar o `tests/test_database_manager.py` com os tickets do
alerta, da tabela de decisao e da transacao, que mexem no mesmo arquivo. Nao ha dependencia de conteudo. Se o
quadro estiver livre, pode andar antes.

**O padrao para a retro:** `.upper()` em nome acentuado dentro de teste que depende de `COLLATE NOCASE` e uma
armadilha com dois casos conhecidos neste arquivo. Vale checagem automatica, nao vigilancia.
