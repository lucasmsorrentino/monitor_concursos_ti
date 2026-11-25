---
id: T-020
titulo: Identidade do concurso: o pci_id que discorda vence o nome
tipo: codigo
nivel: G-
status: backlog
repo: principal
spec: [SPEC-003, R-80, R-81, R-82, R-83, R-84, R-85, R-86]
depende_de: []
toca: [src/database/manager.py, tests/test_database_manager.py, docs/adr/0005-identidade-do-concurso.md]
recursos: []
afinidade:
retornos: 0
---
# T-020 · Identidade do concurso: o pci_id que discorda vence o nome

## Contexto

Dois editais distintos do mesmo orgao, na mesma area, ocupam uma linha so do banco, e cada rodada
sobrescreve o dado do outro. Em 25/11/2026 isso rendeu as 68 transicoes do dia (IFSP 24, IFMS 24, IFPB 20)
e 12 cards de «detectado pela primeira vez» do UNESP: 80 notificacoes para quatro concursos. A medida e o
mecanismo estao na SPEC-003 secao 1. Nenhum requisito de notificacao foi violado: o que esta errado e a
premissa de que aquela linha representa um concurso so.

`buscar_registro` em `src/database/manager.py` **ja** aplica a ordem de identidade com o `pci_id` na frente,
e o `pci_id` ja e descrito como chave canonica desde o schema v5. O furo e a cadeia de fallback nao parar
quando a chave canonica **discorda**: item com `pci_id` que nao casa cai no fallback por link especifico, por
`(area, nome)` COLLATE NOCASE e por casamento de entidade, e acaba casando com a linha do outro edital do
mesmo orgao. O `_resolver_nome_sem_colisao` modela dois casos, mesmo orgao e orgaos distintos que disputam o
nome; falta o terceiro, mesmo orgao com dois concursos.

Corrigir so o casamento troca spam por silencio: o segundo edital vira um `INSERT` que bate no
`UNIQUE(area, nome)`, cai no `except sqlite3.Error` de `atualizar_concurso` e devolve `0`. Por isso a
unicidade tem de abrir junto, e e isso que faz deste um ticket de mao unica.

## Critério de aceite
- [ ] Item com `pci_id` **nao** casa com linha cujo `pci_id` seja nao nulo e diferente, nos tres fallbacks:
      link especifico, `(area, nome)` e casamento de entidade (R-80)
- [ ] Item com `pci_id` **casa** com linha de `pci_id` nulo e grava o `pci_id` nela, mantendo a rechave da
      ADR-0001 (R-81)
- [ ] Item **sem** `pci_id` mantem a ordem de identidade de hoje, sem mudanca de comportamento (R-82)
- [ ] Dois editais do mesmo orgao e da mesma area coexistem como duas linhas, cada uma com o seu `pci_id`,
      `data_fim_inscricao` e `fase` (R-83)
- [ ] A migracao preserva `id`, `estado_usuario` e todos os campos de todas as linhas; a contagem de linhas
      antes e depois e a mesma; nenhuma linha e apagada e nenhuma e fundida (R-84)
- [ ] A migracao **nao** divide linha que ja colidiu (R-85)
- [ ] Colisao de identidade que o codigo nao consiga resolver entra no log como erro nomeado, nunca como
      silencio (R-86)
- [ ] A migracao e idempotente: rodada duas vezes no mesmo banco, a segunda nao muda nada
- [ ] `docs/adr/0005-identidade-do-concurso.md` registra a decisao, as duas opcoes da SPEC-003 secao 4 item 1
      e qual delas o dono escolheu
- [ ] Suite inteira verde; nenhum teste existente afrouxado, renomeado ou apagado

## Plano de testes
Costura: `DatabaseManager.buscar_registro` e `DatabaseManager.atualizar_concurso`, sobre banco temporario em
**arquivo** (nao `:memory:`, para a migracao ser exercitada de verdade). Pega: a ordem de identidade, o
`INSERT` de dois editais do mesmo orgao, a migracao e a idempotencia dela. Nao pega: a decisao de notificar,
que e do `src/core/bot.py` e nao muda neste ticket.
Oráculo: literais escritos a mao a partir dos dados reais de 25/11 (os dois editais do IFSP, com `pci_id`
distintos e prazos distintos) e a tabela de requisitos da SPEC-003 secao 3.1.

Testes que nascem vermelhos:

- `test_pci_id_diferente_nao_casa_por_nome` — linha com `pci_id` gravado, item com outro `pci_id` e o mesmo
  `nome`: devolve `None`.
- `test_pci_id_diferente_nao_casa_por_link` — o mesmo caso, com o link especifico igual nos dois.
- `test_pci_id_diferente_nao_casa_por_entidade` — o mesmo caso, com o nome escrito de outra forma, daquelas
  que o `_buscar_por_entidade` casaria.
- `test_pci_id_casa_com_linha_sem_pci_id_e_rechaveia` — linha de `pci_id` nulo: casa, e a linha sai com o
  `pci_id` gravado.
- `test_item_sem_pci_id_mantem_a_ordem_de_hoje` — guarda de nao-regressao do Gran e das portas de HTML.
- `test_dois_editais_do_mesmo_orgao_viram_duas_linhas` — dois `atualizar_concurso` com `pci_id` distintos e o
  mesmo nome: dois `id` distintos, os dois prazos preservados.
- `test_segunda_linha_nao_sobrescreve_o_prazo_da_primeira` — o caso exato do IFSP. **E o teste que mata o
  laco de renotificacao**, e o que prova o PED-07.
- `test_migracao_preserva_id_estado_usuario_e_contagem` — banco no schema anterior, com linhas, inclusive uma
  marcada `seguindo`.
- `test_migracao_rodada_duas_vezes_nao_muda_nada`
- `test_colisao_irresolvivel_vira_erro_no_log_nao_silencio`

## Fora do escopo
- Reparar as linhas que **ja** colidiram. E outro ticket, que depende deste.
- Mexer na matriz de decisao ou na elegibilidade. Foram conferidas e estao corretas.
- Dividir linha colidida durante a migracao: o R-85 proibe, porque separar exige julgamento sobre qual dado
  pertence a qual edital.
- Ampliar a lista fechada de esfera, ou qualquer outra mudanca no `_buscar_por_entidade` alem de passar a
  respeitar o `pci_id`.

## Notas do arquiteto

**Por que G−:** decide a identidade do concurso, que e o contrato que todo o resto do sistema consome, e
carrega migracao de schema sobre 1.700 linhas de producao onde vivem as estrelas do Lucas. Errar para um lado
funde concursos distintos, que e o defeito de hoje; para o outro divide um concurso em duas linhas e
renotifica. Nao e volume de codigo, e densidade de consequencia.

**Porta de mao unica, e e por isso que o integrador espera o OK do dono.** A migracao altera a unicidade da
tabela `editais`. A SPEC-003 secao 4 item 1 poe as duas opcoes e recomenda o indice unico por expressao
`(area, nome, COALESCE(pci_id, ''))`, que exige recriar a tabela uma vez e colide com a regra «migracao e
aditiva, nunca recriar tabela com dado dentro» do `kanban/REGRAS.md`. Essa regra e do dono. **Nao escolha
sozinho:** se o OK dele no ticket nao disser qual caminho, pare e pergunte em vez de adivinhar.

O `COALESCE` nao e enfeite: em SQLite `NULL` nao colide com `NULL` numa chave unica, entao um
`UNIQUE(area, nome, pci_id)` cru deixaria passar duas linhas do Gran com o mesmo nome, que e exatamente a
duplicata que o `_resolver_nome_sem_colisao` foi escrito para matar depois da varredura de 08/08/2026. O
SQLite de producao e 3.45.1, e indice por expressao existe desde a 3.9.

Se o caminho escolhido for recriar a tabela, siga o procedimento documentado do SQLite (criar a nova, copiar,
trocar os nomes), dentro de uma transacao, e use o `_migrate_to_v3` do proprio arquivo como molde: ele ja faz
isso. O backup do arquivo do banco e passo de producao, nao deste ticket.

**Nao reescreva o `_buscar_por_entidade`.** Ele existe para o mesmo orgao escrito de formas diferentes entre
o Gran e o PCI, e continua necessario. O que muda e so que um `pci_id` discordante passa a bloquea-lo.
