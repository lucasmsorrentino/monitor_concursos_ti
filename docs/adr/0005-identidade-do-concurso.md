# ADR-0005 — Identidade do concurso: o pci_id que discorda vence o nome

**Data:** 25/11/2026
**Estado:** aceita
**Spec:** `docs/specs/SPEC-003-identidade-do-concurso-e-cota-da-llm.md`, secoes 2.1, 2.2, 3.1 e 4 item 1

## Contexto

Em 25/11/2026 o bot mandou 80 notificacoes para quatro concursos: 68 transicoes (IFSP 24, IFMS 24, IFPB 20) e
12 cards de «detectado pela primeira vez» do UNESP. A medida e a cadeia de causa estao na SPEC-003, secao 1.

Nenhuma regra de notificacao estava errada. Estava errada a premissa de que uma linha da tabela `editais` e um
concurso so. Dois editais do mesmo orgao, na mesma area, ocupavam a mesma linha, e cada varredura gravava nela
o prazo de um e depois o do outro. A matriz de decisao via «prazo mudou» duas vezes por varredura, e o
catch-up horario repetia isso a cada hora.

O mecanismo tinha duas metades:

1. **O casamento.** `DatabaseManager.buscar_registro` ja punha o `pci_id` na frente da ordem de identidade.
   Quando o `pci_id` do item nao achava linha, porem, a busca seguia pelos fallbacks (link especifico,
   `(area, nome)` sem caixa, casamento de entidade) e casava com a linha do outro edital do mesmo orgao. A
   chave canonica discordava, e o nome vencia.
2. **A unicidade.** Corrigir so o casamento trocaria spam por silencio: o segundo edital viraria um `INSERT`
   que bate no `UNIQUE(area, nome)` da tabela, cai no `except sqlite3.Error` de `atualizar_concurso` e devolve
   `0`. O concurso deixaria de renotificar e continuaria sem entrar.

## Decisao

### Identidade

Quando o item carrega `pci_id` e a linha candidata tem `pci_id` nao nulo e diferente, **nao e a mesma linha**,
e nenhum fallback mais fraco pode dizer que e. Vale nos tres fallbacks.

- Linha candidata com `pci_id` **nulo** continua casando pelas regras de antes, e recebe o `pci_id` (a
  rechave da ADR-0001, que rechaveou 59 linhas em 24/11 sem perder nenhuma).
- Item **sem** `pci_id` (blog do Gran, portas de HTML de reserva) segue a ordem de sempre, sem restricao.
- Na troca de nome (`_resolver_nome_sem_colisao`), a linha que disputa o nome e tem outro `pci_id` e o
  terceiro caso, mesmo orgao com dois concursos: nao se funde. Os dois primeiros casos (mesmo orgao escrito
  de duas formas, que se funde; orgaos distintos que disputam o nome, que mantem o nome antigo) seguem como
  eram.
- Escrita que, mesmo assim, bate na unicidade e logada como erro com nome proprio, `COLISAO DE IDENTIDADE`,
  com area, nome, `pci_id` e link. Nunca vira silencio (R-86).

### Unicidade: as duas opcoes e a escolha do dono

A SPEC-003, secao 4 item 1, pos duas opcoes:

1. **Indice unico por expressao**, `(area, nome, COALESCE(pci_id, ''))`, no lugar do `UNIQUE(area, nome)` de
   tabela. Em SQLite um `UNIQUE` de tabela so sai recriando a tabela, o que colide com a regra «migracao e
   aditiva, nunca recriar tabela com dado dentro». O `COALESCE` e necessario: em SQLite `NULL` nao colide com
   `NULL` numa chave unica, e sem ele duas linhas do Gran com o mesmo nome passariam a ser aceitas, que e a
   duplicata que o `_resolver_nome_sem_colisao` existe para matar.
2. **Desambiguar o `nome`** na escrita, acrescentando ao nome da segunda linha algo do proprio edital. Nao
   mexe no schema, mas polui o campo que o Lucas le no card, e e o campo pelo qual o Gran e as portas de HTML
   casam.

**O dono escolheu a primeira**, no chat, em 25/11/2026: «Recria a tabela». A excecao a regra de migracao
aditiva foi aberta por escrito, com escopo de um caso so: a unicidade da tabela `editais`. Qualquer outra
recriacao de tabela segue proibida.

### Como a migracao roda (schema v7)

Em `DatabaseManager._abrir_unicidade`, chamada por `_ensure_schema` depois das colunas aditivas:

- So roda se a tabela ainda tem o `UNIQUE` de tabela (`PRAGMA index_list`, `origin = 'u'`). Sem ele, so
  garante que o indice existe. Rodada duas vezes, a segunda nao escreve nada no arquivo.
- Uma transacao so, pelo procedimento documentado do SQLite, com o `_migrate_to_v3` como molde: cria
  `editais_v7` sem o `UNIQUE`, copia **todas** as colunas, `id` inclusive, troca os nomes e cria o indice.
- Devolve ao `sqlite_sequence` o maior `id` ja emitido. Sem isso, o `id` de uma linha apagada numa fusao
  voltaria a circular, e um botao antigo do Telegram passaria a apontar para outro concurso.
- Nenhuma linha e apagada, fundida ou dividida (R-84, R-85). A troca de unicidade nao pode falhar por dado:
  todo banco que cumpria `UNIQUE(area, nome)` cumpre `(area, nome, COALESCE(pci_id, ''))`, que e mais frouxa.
- Se algo falhar, a transacao volta inteira e o banco fica no formato anterior, com o erro no log.

O backup do arquivo do banco antes da primeira execucao em producao e passo do deploy, nao do codigo.

## Consequencias

- Dois editais do mesmo orgao viram duas linhas, cada uma com o seu `pci_id`, prazo, fase e botoes. O laco
  de renotificacao de 25/11 deixa de ter onde se apoiar.
- As linhas que **ja** colidiram ficam como estao: a migracao nao as divide, porque separar exige julgamento
  sobre qual dado pertence a qual edital. O reparo delas e separado (SPEC-003, secao 3.3). Depois desta
  mudanca, uma linha colidida fica com o `pci_id` que tinha por ultimo, e o outro edital entra como linha
  nova, uma vez.
- Item do Gran ou das portas de HTML que casa por nome com um orgao de dois editais casa com uma das duas
  linhas, como antes casava com a unica. Ele nao traz `pci_id` para desempatar, e a ordem de identidade dele
  nao muda (R-82).
- O `UNIQUE` saiu da definicao da tabela. Quem procurar a unicidade no `CREATE TABLE` nao a acha: ela esta
  em `idx_editais_identidade`.

## O que nao se vai fazer

- Reescrever o `_buscar_por_entidade`. Ele continua necessario para o mesmo orgao escrito de formas
  diferentes entre o Gran e o PCI; o que muda e so que um `pci_id` discordante o bloqueia.
- Usar `UNIQUE(area, nome, pci_id)` cru, sem `COALESCE`: deixaria passar nome repetido entre linhas sem
  `pci_id`.
- Recriar outra tabela, ou recriar esta de novo, apoiado nesta excecao.
